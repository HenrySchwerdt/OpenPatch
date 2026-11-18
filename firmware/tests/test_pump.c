#include "fake_ccm.h"
#include "mock_hal.h"
#include "op/pump_controller.h"
#include "op_test.h"

#define MIN 60000ull

typedef struct {
    mock_hal_t hal;
    op_hal_t ops;
    op_pump_t pump;
} rig_t;

static op_basal_schedule_t flat(uint32_t rate)
{
    op_basal_schedule_t s = {0};
    s.count = 1;
    s.seg[0].rate_mu_h = rate;
    return s;
}

static void rig_init(rig_t *r)
{
    mock_hal_init(&r->hal);
    r->ops = mock_hal_make(&r->hal);
    op_pump_init(&r->pump, &r->ops, OP_CAPACITY_200_MU, 1);
}

/* fill + schedule + resume, ready to deliver */
static void rig_running(rig_t *r, uint32_t fill_mu, uint32_t rate)
{
    rig_init(r);
    op_basal_schedule_t s = flat(rate);
    CHECK_EQ(op_pump_fill(&r->pump, fill_mu), OP_OK);
    CHECK_EQ(op_pump_set_schedule(&r->pump, &s), OP_OK);
    CHECK_EQ(op_pump_resume(&r->pump), OP_OK);
}

static void advance(rig_t *r, uint32_t seconds)
{
    for (uint32_t i = 0; i < seconds; i++) {
        r->hal.now_ms += 1000;
        op_pump_tick(&r->pump);
    }
}

static bool log_has(const rig_t *r, uint8_t type)
{
    op_event_t e[OP_LOG_CAPACITY];
    uint32_t n = op_log_read(&r->pump.log, 0, e, OP_LOG_CAPACITY);
    for (uint32_t i = 0; i < n; i++)
        if (e[i].type == type) return true;
    return false;
}

TEST(pump_boots_suspended_with_boot_event_and_restored_ids)
{
    rig_t r;
    mock_hal_init(&r.hal);
    r.ops = mock_hal_make(&r.hal);
    op_pump_init(&r.pump, &r.ops, OP_CAPACITY_70_MU, 500);
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK(st.flags & OP_ST_SUSPENDED);
    CHECK(!(st.flags & OP_ST_FILLED));
    CHECK_EQ(st.fw_version, OP_FW_VERSION);
    CHECK_EQ(op_log_oldest_id(&r.pump.log), 500);
    CHECK(log_has(&r, OP_EV_BOOT));
    CHECK(!r.hal.enabled);
}

TEST(pump_basal_hour_delivers_expected_steps_and_updates_reservoir)
{
    rig_t r;
    rig_running(&r, 100000, 1000);
    advance(&r, 3600);
    CHECK_EQ(r.hal.total_steps, 76);
    CHECK(!r.hal.stepped_while_disabled);
    CHECK(!r.hal.enabled); /* driver gated off between steps */
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK_EQ(st.reservoir_mu, 99004); /* 100000 - 76*13.1 = 99004.4 */
    CHECK_EQ(st.delivered_mu, 995);
    CHECK_EQ(st.faults, 0);
    CHECK_EQ(st.current_rate_mu_h, 1000);
    CHECK_EQ(r.hal.kicks, 3600);
}

TEST(pump_bolus_flow_and_log)
{
    rig_t r;
    rig_running(&r, 100000, 0);
    CHECK_EQ(op_pump_bolus(&r.pump, 2000), OP_OK);
    op_status_t st;
    advance(&r, 20);
    op_pump_get_status(&r.pump, &st);
    CHECK(st.flags & OP_ST_BOLUS_ACTIVE);
    CHECK_EQ(st.bolus_remaining_mu, 1500);
    advance(&r, 61);
    op_pump_get_status(&r.pump, &st);
    CHECK(!(st.flags & OP_ST_BOLUS_ACTIVE));
    CHECK_EQ(r.hal.total_steps, 152); /* floor(2000/13.1) */
    CHECK(log_has(&r, OP_EV_BOLUS_START));
    CHECK(log_has(&r, OP_EV_BOLUS_DONE));
}

TEST(pump_bolus_rejections)
{
    rig_t r;
    rig_init(&r);
    CHECK_EQ(op_pump_fill(&r.pump, 100000), OP_OK);
    CHECK_EQ(op_pump_bolus(&r.pump, 1000), OP_ERR_SUSPENDED);
    op_pump_resume(&r.pump);
    CHECK_EQ(op_pump_bolus(&r.pump, 10050), OP_ERR_LIMIT);
    CHECK_EQ(op_pump_bolus(&r.pump, 1025), OP_ERR_BAD_ARG);
    CHECK_EQ(op_pump_bolus(&r.pump, 10000), OP_OK);
    CHECK_EQ(op_pump_bolus(&r.pump, 1000), OP_ERR_BUSY);
    CHECK_EQ(op_pump_cancel_bolus(&r.pump), OP_OK);
    advance(&r, 100); /* nothing was delivered after cancel */
    CHECK_EQ(op_pump_bolus(&r.pump, 10000), OP_OK);
}

TEST(pump_hourly_cap_rejects_second_large_bolus)
{
    rig_t r;
    rig_running(&r, 150000, 0);
    CHECK_EQ(op_pump_bolus(&r.pump, 10000), OP_OK);
    advance(&r, 7 * 60); /* 10 U at 1.5 U/min = 6.7 min */
    CHECK_EQ(op_pump_bolus(&r.pump, 10000), OP_ERR_HOURLY);
    CHECK_EQ(op_pump_bolus(&r.pump, 4000), OP_OK);
}

TEST(pump_bolus_larger_than_reservoir_is_rejected)
{
    rig_t r;
    rig_running(&r, 3000, 0);
    CHECK_EQ(op_pump_bolus(&r.pump, 4000), OP_ERR_RESERVOIR);
    rig_t u;
    rig_init(&u); /* never filled */
    op_pump_resume(&u.pump);
    CHECK_EQ(op_pump_bolus(&u.pump, 1000), OP_ERR_RESERVOIR);
}

TEST(pump_occlusion_stops_everything_until_acknowledged)
{
    rig_t r;
    rig_running(&r, 100000, 0);
    r.hal.delivered_pct = 0; /* spindle does not move */
    CHECK_EQ(op_pump_bolus(&r.pump, 5000), OP_OK);
    advance(&r, 120);
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK(st.faults & OP_FAULT_OCCLUSION);
    CHECK(st.flags & OP_ST_ALARM);
    CHECK(st.flags & OP_ST_SUSPENDED);
    CHECK(!(st.flags & OP_ST_BOLUS_ACTIVE));
    CHECK_EQ(r.hal.buzzer, OP_BUZZER_ALARM);
    CHECK(!r.hal.enabled);
    uint32_t frozen = r.hal.total_steps;
    CHECK(frozen < op_mu_to_steps(2000)); /* stopped before 2 U */
    advance(&r, 120);
    CHECK_EQ(r.hal.total_steps, frozen);
    CHECK(log_has(&r, OP_EV_FAULT));
    /* cannot restart with a latched fault, ack alone does not resume */
    CHECK_EQ(op_pump_resume(&r.pump), OP_ERR_FAULT);
    CHECK_EQ(op_pump_bolus(&r.pump, 1000), OP_ERR_FAULT);
    r.hal.delivered_pct = 100;
    CHECK_EQ(op_pump_acknowledge(&r.pump, 0xFFFF), OP_OK);
    CHECK_EQ(r.hal.buzzer, OP_BUZZER_OFF);
    op_pump_get_status(&r.pump, &st);
    CHECK(st.flags & OP_ST_SUSPENDED);
    CHECK_EQ(op_pump_resume(&r.pump), OP_OK);
    CHECK(log_has(&r, OP_EV_ACK));
}

TEST(pump_encoder_deviation_stops_delivery)
{
    rig_t r;
    rig_running(&r, 100000, 5000);
    r.hal.delivered_pct = 80;
    advance(&r, 1800);
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK(st.faults & OP_FAULT_ENCODER_DEVIATION);
    CHECK(r.hal.total_steps < op_mu_to_steps(1500));
}

TEST(pump_reservoir_runs_dry_never_over_delivers)
{
    rig_t r;
    rig_running(&r, 1000, 5000);
    advance(&r, 3600);
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK(st.faults & OP_FAULT_RESERVOIR_EMPTY);
    CHECK(r.hal.total_steps <= op_mu_to_steps(1000));
    CHECK(r.hal.total_steps >= op_mu_to_steps(1000) - 2);
    CHECK_EQ(st.reservoir_mu < 14, true);
}

TEST(pump_low_reservoir_logged_once)
{
    rig_t r;
    rig_running(&r, 10500, 5000);
    advance(&r, 600);
    int count = 0;
    op_event_t e[OP_LOG_CAPACITY];
    uint32_t n = op_log_read(&r.pump.log, 0, e, OP_LOG_CAPACITY);
    for (uint32_t i = 0; i < n; i++) count += e[i].type == OP_EV_LOW_RESERVOIR;
    CHECK_EQ(count, 1);
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK(st.flags & OP_ST_LOW_RESERVOIR);
}

TEST(pump_critical_battery_blocks_delivery)
{
    rig_t r;
    rig_running(&r, 100000, 5000);
    r.hal.battery_mv = 3200;
    advance(&r, 60);
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK(st.faults & OP_FAULT_BATTERY_CRITICAL);
    uint32_t frozen = r.hal.total_steps;
    advance(&r, 600);
    CHECK_EQ(r.hal.total_steps, frozen);
    CHECK_EQ(op_pump_acknowledge(&r.pump, 0xFFFF), OP_ERR_PERSISTS);
    r.hal.battery_mv = 3800;
    advance(&r, 1);
    CHECK_EQ(op_pump_acknowledge(&r.pump, 0xFFFF), OP_OK);
}

TEST(pump_low_battery_warning_logged)
{
    rig_t r;
    rig_running(&r, 100000, 0);
    r.hal.battery_mv = 3450;
    advance(&r, 2);
    CHECK(log_has(&r, OP_EV_LOW_BATTERY));
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK(st.flags & OP_ST_LOW_BATTERY);
    CHECK_EQ(st.faults, 0);
}

TEST(pump_temp_basal_falls_back_after_comm_loss)
{
    rig_t r;
    rig_running(&r, 100000, 1000);
    CHECK_EQ(op_pump_set_temp_basal(&r.pump, 3000, 120), OP_OK);
    advance(&r, 29 * 60);
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK(st.flags & OP_ST_TEMP_ACTIVE);
    CHECK_EQ(st.current_rate_mu_h, 3000);
    advance(&r, 2 * 60);
    op_pump_get_status(&r.pump, &st);
    CHECK(!(st.flags & OP_ST_TEMP_ACTIVE));
    CHECK_EQ(st.current_rate_mu_h, 1000);
    CHECK(log_has(&r, OP_EV_TEMP_COMM_FALLBACK));
}

TEST(pump_temp_basal_validation_and_cancel)
{
    rig_t r;
    rig_running(&r, 100000, 1000);
    CHECK_EQ(op_pump_set_temp_basal(&r.pump, 5050, 30), OP_ERR_LIMIT);
    CHECK_EQ(op_pump_set_temp_basal(&r.pump, 2000, 31), OP_ERR_BAD_ARG);
    CHECK_EQ(op_pump_set_temp_basal(&r.pump, 2000, 30), OP_OK);
    CHECK_EQ(op_pump_cancel_temp_basal(&r.pump), OP_OK);
    CHECK_EQ(op_pump_cancel_temp_basal(&r.pump), OP_ERR_NOT_FOUND);
    CHECK(log_has(&r, OP_EV_TEMP_START));
    CHECK(log_has(&r, OP_EV_TEMP_CANCEL));
}

TEST(pump_temp_basal_end_is_logged)
{
    rig_t r;
    rig_running(&r, 100000, 1000);
    op_pump_set_temp_basal(&r.pump, 2000, 30);
    advance(&r, 31 * 60);
    CHECK(log_has(&r, OP_EV_TEMP_DONE));
    CHECK(!log_has(&r, OP_EV_TEMP_COMM_FALLBACK));
}

TEST(pump_schedule_validation_and_log)
{
    rig_t r;
    rig_init(&r);
    op_basal_schedule_t s = flat(5050);
    CHECK_EQ(op_pump_set_schedule(&r.pump, &s), OP_ERR_LIMIT);
    s = flat(1000);
    CHECK_EQ(op_pump_set_schedule(&r.pump, &s), OP_OK);
    CHECK(log_has(&r, OP_EV_BASAL_SET));
}

TEST(pump_fill_and_prime_rules)
{
    rig_t r;
    rig_init(&r);
    CHECK_EQ(op_pump_fill(&r.pump, 0), OP_ERR_BAD_ARG);
    CHECK_EQ(op_pump_fill(&r.pump, OP_CAPACITY_200_MU + 1), OP_ERR_LIMIT);
    CHECK_EQ(op_pump_prime(&r.pump, 10), OP_ERR_RESERVOIR); /* nothing filled yet */
    CHECK_EQ(op_pump_fill(&r.pump, 50000), OP_OK);
    CHECK_EQ(op_pump_prime(&r.pump, OP_MAX_PRIME_STEPS + 1), OP_ERR_LIMIT);
    CHECK_EQ(op_pump_prime(&r.pump, 0), OP_ERR_BAD_ARG);
    CHECK_EQ(op_pump_prime(&r.pump, 20), OP_OK);
    CHECK_EQ(r.hal.total_steps, 20);
    CHECK(!r.hal.stepped_while_disabled);
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK_EQ(st.reservoir_mu, 50000 - 262); /* 20 steps = 262 mU */
    CHECK(log_has(&r, OP_EV_FILL));
    CHECK(log_has(&r, OP_EV_PRIME));
    op_pump_resume(&r.pump);
    CHECK_EQ(op_pump_fill(&r.pump, 50000), OP_ERR_NOT_SUSPENDED);
    CHECK_EQ(op_pump_prime(&r.pump, 5), OP_ERR_NOT_SUSPENDED);
}

TEST(pump_prime_respects_motor_failure_and_encoder)
{
    rig_t r;
    rig_init(&r);
    op_pump_fill(&r.pump, 50000);
    r.hal.steps_limit = 5; /* motor only manages 5 of 20 */
    CHECK_EQ(op_pump_prime(&r.pump, 20), OP_ERR_FAULT);
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK(st.faults & OP_FAULT_INTERNAL);
    CHECK_EQ(r.hal.total_steps, 5);
}

TEST(pump_motor_shortfall_latches_internal_fault)
{
    rig_t r;
    rig_running(&r, 100000, 5000);
    r.hal.steps_limit = 0; /* motor refuses to move */
    advance(&r, 120);
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK(st.faults & OP_FAULT_INTERNAL);
    CHECK(st.flags & OP_ST_SUSPENDED);
}

TEST(pump_suspend_resume_and_log)
{
    rig_t r;
    rig_running(&r, 100000, 5000);
    CHECK_EQ(op_pump_suspend(&r.pump), OP_OK);
    advance(&r, 600);
    CHECK_EQ(r.hal.total_steps, 0);
    CHECK_EQ(op_pump_resume(&r.pump), OP_OK);
    advance(&r, 600);
    CHECK(r.hal.total_steps > 0);
    CHECK(log_has(&r, OP_EV_SUSPEND));
    CHECK(log_has(&r, OP_EV_RESUME));
}

TEST(pump_tick_clamps_time_jumps_instead_of_catching_up)
{
    rig_t r;
    rig_running(&r, 100000, 5000);
    r.hal.now_ms += 3600000; /* main loop stalled for an hour */
    op_pump_tick(&r.pump);
    CHECK_EQ(r.pump.tick_overruns, 1);
    CHECK(r.hal.total_steps <= 2); /* only 5 s worth */
}

TEST(pump_watchdog_is_kicked_every_tick)
{
    rig_t r;
    rig_init(&r);
    advance(&r, 10);
    CHECK_EQ(r.hal.kicks, 10);
}

/* ---- protocol path -------------------------------------------------------- */
typedef struct { op_session_t s; uint16_t seq; } link_t;

static int exchange(rig_t *r, link_t *l, op_cmd_t *cmd, bool enc, op_rsp_t *rsp)
{
    uint8_t payload[200], frame[OP_FRAME_MAX], out[OP_FRAME_MAX], plain[OP_FRAME_MAX];
    cmd->seq = l->seq++;
    int pl = op_cmd_encode_payload(cmd, payload, sizeof payload);
    CHECK(pl >= 0);
    int n = op_session_seal(&l->s, false, cmd->type, cmd->seq, enc, payload, (size_t)pl, frame, sizeof frame);
    CHECK(n > 0);
    int m = op_pump_handle_frame(&r->pump, &l->s, frame, (size_t)n, out, sizeof out);
    if (m < 0) return m;
    op_frame_t f;
    CHECK_EQ(op_frame_decode(out, (size_t)m, &f), 0);
    CHECK(f.flags & OP_FLAG_RESPONSE);
    CHECK_EQ(f.flags & OP_FLAG_ENCRYPTED, enc ? OP_FLAG_ENCRYPTED : 0);
    CHECK_EQ(f.type, cmd->type | OP_RSP_BIT);
    CHECK_EQ(f.seq, cmd->seq);
    const uint8_t *pp = f.payload;
    size_t pn = f.payload_len;
    if (enc) { /* decrypt response with the response nonce */
        uint8_t nonce[OP_CCM_NONCE_LEN];
        op_session_nonce(&l->s, true, f.seq, nonce);
        CHECK_EQ(fake_ccm_ops.decrypt(NULL, nonce, out, OP_FRAME_HEADER, f.payload, pn - OP_CCM_TAG_LEN,
                                      f.payload + pn - OP_CCM_TAG_LEN, plain), 0);
        pp = plain;
        pn -= OP_CCM_TAG_LEN;
    }
    CHECK_EQ(op_rsp_decode(cmd->type, f.seq, pp, pn, rsp), 0);
    return m;
}

static void link_plain(link_t *l)
{
    static const uint8_t salt[4] = {9, 9, 9, 9};
    op_session_init(&l->s, NULL, salt, true);
    l->seq = 1;
}

TEST(proto_get_status_over_frames)
{
    rig_t r;
    rig_running(&r, 100000, 1000);
    link_t l;
    link_plain(&l);
    op_cmd_t c = {0};
    op_rsp_t rsp;
    c.type = OP_CMD_GET_STATUS;
    CHECK(exchange(&r, &l, &c, false, &rsp) > 0);
    CHECK_EQ(rsp.result, OP_OK);
    CHECK(rsp.has_status);
    CHECK_EQ(rsp.status.reservoir_mu, 100000);
    CHECK_EQ(rsp.status.current_rate_mu_h, 1000);
    CHECK(!(rsp.status.flags & OP_ST_SUSPENDED));
    CHECK_EQ(rsp.status.last_seq, 1); /* the request itself is the last accepted sequence number */
}

TEST(proto_get_status_reports_last_accepted_seq)
{
    rig_t r;
    rig_running(&r, 100000, 1000);
    link_t l;
    link_plain(&l);
    op_cmd_t c = {0};
    op_rsp_t rsp;
    c.type = OP_CMD_SUSPEND;
    CHECK(exchange(&r, &l, &c, false, &rsp) > 0);
    l.seq = 40; /* the phone skips ahead; gaps are legal */
    c.type = OP_CMD_GET_STATUS;
    CHECK(exchange(&r, &l, &c, false, &rsp) > 0);
    CHECK_EQ(rsp.status.last_seq, 40);
    /* a pod restoring last_seq after a reboot reports it in the next GetStatus */
    link_t restored;
    link_plain(&restored);
    restored.s.rx_seen = true;
    restored.s.last_rx_seq = 100;
    restored.seq = 101;
    CHECK(exchange(&r, &restored, &c, false, &rsp) > 0);
    CHECK_EQ(rsp.status.last_seq, 101);
}

TEST(proto_full_command_set_works_end_to_end)
{
    rig_t r;
    rig_init(&r);
    link_t l;
    link_plain(&l);
    op_cmd_t c;
    op_rsp_t rsp;

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_FILL_PRIME;
    c.u.fill.sub_op = OP_SUBOP_FILL;
    c.u.fill.fill_mu = 120000;
    exchange(&r, &l, &c, false, &rsp);
    CHECK_EQ(rsp.result, OP_OK);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_FILL_PRIME;
    c.u.fill.sub_op = OP_SUBOP_PRIME;
    c.u.fill.prime_steps = 10;
    exchange(&r, &l, &c, false, &rsp);
    CHECK_EQ(rsp.result, OP_OK);
    CHECK_EQ(r.hal.total_steps, 10);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_SET_BASAL_SCHEDULE;
    c.has_time_of_day = true;
    c.time_of_day_ms = 12 * 3600000u;
    c.u.basal.count = 2;
    c.u.basal.seg[0] = (op_basal_seg_t){0, 800};
    c.u.basal.seg[1] = (op_basal_seg_t){30, 1200}; /* 15:00 */
    exchange(&r, &l, &c, false, &rsp);
    CHECK_EQ(rsp.result, OP_OK);
    CHECK_EQ(r.pump.de.ms_of_day, 12 * 3600000u);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_RESUME;
    exchange(&r, &l, &c, false, &rsp);
    CHECK_EQ(rsp.result, OP_OK);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_SET_TEMP_BASAL;
    c.u.temp.rate_mu_h = 2000;
    c.u.temp.duration_min = 60;
    exchange(&r, &l, &c, false, &rsp);
    CHECK_EQ(rsp.result, OP_OK);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_CANCEL_TEMP_BASAL;
    exchange(&r, &l, &c, false, &rsp);
    CHECK_EQ(rsp.result, OP_OK);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_BOLUS;
    c.u.bolus.amount_mu = 1000;
    exchange(&r, &l, &c, false, &rsp);
    CHECK_EQ(rsp.result, OP_OK);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_CANCEL_BOLUS;
    exchange(&r, &l, &c, false, &rsp);
    CHECK_EQ(rsp.result, OP_OK);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_SUSPEND;
    exchange(&r, &l, &c, false, &rsp);
    CHECK_EQ(rsp.result, OP_OK);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_ACKNOWLEDGE;
    c.u.ack.fault_mask = 0xFFFF;
    exchange(&r, &l, &c, false, &rsp);
    CHECK_EQ(rsp.result, OP_OK);
}

TEST(proto_errors_are_reported_in_result_tag)
{
    rig_t r;
    rig_running(&r, 100000, 1000);
    link_t l;
    link_plain(&l);
    op_cmd_t c = {0};
    op_rsp_t rsp;
    c.type = OP_CMD_BOLUS;
    c.u.bolus.amount_mu = 20000; /* above 10 U max */
    exchange(&r, &l, &c, false, &rsp);
    CHECK_EQ(rsp.result, OP_ERR_LIMIT);
    CHECK_EQ(r.hal.total_steps, 0);
}

TEST(proto_unknown_command_gets_unsupported_response)
{
    rig_t r;
    rig_init(&r);
    link_t l;
    link_plain(&l);
    uint8_t frame[32], out[64];
    int n = op_session_seal(&l.s, false, 0x7E, 1, false, NULL, 0, frame, sizeof frame);
    int m = op_pump_handle_frame(&r.pump, &l.s, frame, (size_t)n, out, sizeof out);
    CHECK(m > 0);
    op_frame_t f;
    CHECK_EQ(op_frame_decode(out, (size_t)m, &f), 0);
    CHECK_EQ(f.type, 0x7E | OP_RSP_BIT);
    op_rsp_t rsp;
    CHECK_EQ(op_rsp_decode(0x7E, f.seq, f.payload, f.payload_len, &rsp), 0);
    CHECK_EQ(rsp.result, OP_ERR_UNSUPPORTED);
}

TEST(proto_malformed_payload_gets_frame_error_response)
{
    rig_t r;
    rig_init(&r);
    link_t l;
    link_plain(&l);
    uint8_t frame[32], out[64];
    int n = op_session_seal(&l.s, false, OP_CMD_BOLUS, 1, false, NULL, 0, frame, sizeof frame); /* amount missing */
    int m = op_pump_handle_frame(&r.pump, &l.s, frame, (size_t)n, out, sizeof out);
    CHECK(m > 0);
    op_frame_t f;
    op_rsp_t rsp;
    CHECK_EQ(op_frame_decode(out, (size_t)m, &f), 0);
    CHECK_EQ(op_rsp_decode(OP_CMD_BOLUS, f.seq, f.payload, f.payload_len, &rsp), 0);
    CHECK_EQ(rsp.result, OP_ERR_FRAME);
}

TEST(proto_replay_corruption_and_oversized_output_are_dropped)
{
    rig_t r;
    rig_running(&r, 100000, 0);
    link_t l;
    link_plain(&l);
    uint8_t payload[8], frame[64], out[64];
    op_cmd_t c = {0};
    c.type = OP_CMD_BOLUS;
    c.seq = 1;
    c.u.bolus.amount_mu = 500;
    int pl = op_cmd_encode_payload(&c, payload, sizeof payload);
    int n = op_session_seal(&l.s, false, c.type, 1, false, payload, (size_t)pl, frame, sizeof frame);
    CHECK(op_pump_handle_frame(&r.pump, &l.s, frame, (size_t)n, out, sizeof out) > 0);
    op_pump_cancel_bolus(&r.pump);
    /* the same bytes again: must NOT start a second bolus */
    CHECK_EQ(op_pump_handle_frame(&r.pump, &l.s, frame, (size_t)n, out, sizeof out), -OP_ERR_REPLAY);
    CHECK(!r.pump.de.bolus_active);
    frame[3] ^= 0x40;
    CHECK_EQ(op_pump_handle_frame(&r.pump, &l.s, frame, (size_t)n, out, sizeof out), -OP_ERR_CRC);
    CHECK_EQ(op_pump_handle_frame(&r.pump, &l.s, frame, (size_t)n, out, 4), -OP_ERR_CRC); /* checked before output */
}

TEST(proto_response_buffer_too_small_reports_error)
{
    rig_t r;
    rig_init(&r);
    link_t l;
    link_plain(&l);
    uint8_t frame[32], out[8];
    int n = op_session_seal(&l.s, false, OP_CMD_GET_STATUS, 1, false, NULL, 0, frame, sizeof frame);
    CHECK_EQ(op_pump_handle_frame(&r.pump, &l.s, frame, (size_t)n, out, sizeof out), -OP_ERR_TOO_LARGE);
}

TEST(proto_any_valid_command_resets_comm_loss_timer)
{
    rig_t r;
    rig_running(&r, 100000, 1000);
    link_t l;
    link_plain(&l);
    op_cmd_t c = {0};
    op_rsp_t rsp;
    c.type = OP_CMD_SET_TEMP_BASAL;
    c.u.temp.rate_mu_h = 3000;
    c.u.temp.duration_min = 120;
    exchange(&r, &l, &c, false, &rsp);
    for (int i = 0; i < 4; i++) { /* a status poll every 20 min keeps the temp alive */
        advance(&r, 20 * 60);
        memset(&c, 0, sizeof c);
        c.type = OP_CMD_GET_STATUS;
        exchange(&r, &l, &c, false, &rsp);
        CHECK(rsp.status.flags & OP_ST_TEMP_ACTIVE);
    }
    advance(&r, 31 * 60);
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK(!(st.flags & OP_ST_TEMP_ACTIVE));
}

TEST(proto_history_paging_with_persistent_ids)
{
    rig_t r;
    rig_init(&r);
    for (int i = 0; i < 25; i++) op_log_append(&r.pump.log, 0, OP_EV_PRIME, i, 0);
    link_t l;
    link_plain(&l);
    op_cmd_t c = {0};
    op_rsp_t rsp;
    c.type = OP_CMD_GET_HISTORY;
    c.u.history.from_id = 0;
    c.u.history.max_events = 10;
    exchange(&r, &l, &c, false, &rsp);
    CHECK_EQ(rsp.n_events, 10);
    CHECK_EQ(rsp.events[0].id, 1); /* BOOT */
    CHECK_EQ(rsp.next_event_id, 27);
    CHECK_EQ(rsp.oldest_event_id, 1);
    uint32_t next = rsp.events[9].id + 1;
    memset(&c, 0, sizeof c);
    c.type = OP_CMD_GET_HISTORY;
    c.u.history.from_id = next;
    c.u.history.max_events = 100; /* clamped to 10 per response */
    exchange(&r, &l, &c, false, &rsp);
    CHECK_EQ(rsp.n_events, 10);
    CHECK_EQ(rsp.events[0].id, 11);
}

TEST(proto_encrypted_path_end_to_end)
{
    rig_t r;
    rig_running(&r, 100000, 1000);
    link_t l;
    static const uint8_t salt[4] = {5, 6, 7, 8};
    op_session_init(&l.s, &fake_ccm_ops, salt, false);
    l.seq = 1;
    op_cmd_t c = {0};
    op_rsp_t rsp;
    c.type = OP_CMD_GET_STATUS;
    CHECK(exchange(&r, &l, &c, true, &rsp) > 0);
    CHECK_EQ(rsp.result, OP_OK);
    CHECK_EQ(rsp.status.reservoir_mu, 100000);
}
