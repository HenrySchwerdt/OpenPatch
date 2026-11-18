/* Two-pod system (spec/design-parameters.md section 1b): dock input, wear timer, pairing,
 * Activate / Release, charger. */
#include "cal_fixture.h"
#include "mock_hal.h"
#include "op/pump_controller.h"
#include "op_test.h"

#define HOUR_MS 3600000ull

typedef struct {
    mock_hal_t hal;
    op_hal_t ops;
    op_pump_t pump;
} rig_t;

static void rig_init(rig_t *r)
{
    mock_hal_init(&r->hal);
    r->ops = mock_hal_make(&r->hal);
    op_pump_init(&r->pump, &r->ops, test_cal_5_1(), OP_CAPACITY_100_MU, 1);
}

static void advance(rig_t *r, uint32_t seconds)
{
    for (uint32_t i = 0; i < seconds; i++) {
        r->hal.now_ms += 1000;
        op_pump_tick(&r->pump);
    }
}

/* big jumps for the wear timer: one tick per hour */
static void advance_hours(rig_t *r, uint32_t hours)
{
    for (uint32_t i = 0; i < hours; i++) {
        r->hal.now_ms += HOUR_MS;
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

static int32_t log_count(const rig_t *r, uint8_t type)
{
    op_event_t e[OP_LOG_CAPACITY];
    uint32_t n = op_log_read(&r->pump.log, 0, e, OP_LOG_CAPACITY);
    int32_t c = 0;
    for (uint32_t i = 0; i < n; i++)
        if (e[i].type == type) c++;
    return c;
}

/* filled, paired, activated and resumed: delivering basal `rate` */
static void rig_running(rig_t *r, uint32_t rate)
{
    rig_init(r);
    CHECK_EQ(op_pump_fill(&r->pump, 100000), OP_OK);
    CHECK_EQ(test_activate(&r->pump, rate), OP_OK);
    CHECK_EQ(op_pump_resume(&r->pump), OP_OK);
}

static op_status_t status(rig_t *r)
{
    op_status_t st;
    op_pump_get_status(&r->pump, &st);
    return st;
}

/* ---- dock input ------------------------------------------------------------ */
TEST(dock_undocked_pod_never_steps_and_reports_paused)
{
    rig_t r;
    rig_running(&r, 3000);
    advance(&r, 600);
    uint32_t before = r.hal.total_steps;
    CHECK(before > 0);
    r.hal.docked = false;
    advance(&r, 3600);
    CHECK_EQ(r.hal.total_steps, before); /* not a single step */
    op_status_t st = status(&r);
    CHECK_EQ(st.delivery_state, OP_DS_PAUSED_UNDOCKED);
    CHECK(!(st.flags & OP_ST_DOCKED));
    CHECK(st.flags & OP_ST_ACTIVE);
    CHECK_EQ(st.faults, 0); /* a pause, not a latched fault */
    CHECK_EQ(log_count(&r, OP_EV_UNDOCKED), 1);
}

TEST(dock_resumes_basal_without_catch_up_when_redocked)
{
    rig_t r;
    rig_running(&r, 3000);
    r.hal.docked = false;
    advance(&r, 1800);
    CHECK_EQ(r.hal.total_steps, 0);
    r.hal.docked = true;
    advance(&r, 1);
    CHECK_EQ(log_count(&r, OP_EV_DOCKED), 1);
    CHECK_EQ(status(&r).delivery_state, OP_DS_ACTIVE);
    advance(&r, 3600);
    /* one hour of 3 U/h = 114.9 steps; the missed half hour is NOT made up */
    CHECK(r.hal.total_steps >= 114 && r.hal.total_steps <= 116);
}

TEST(dock_loss_cancels_running_bolus_and_blocks_new_ones)
{
    rig_t r;
    rig_running(&r, 0);
    CHECK_EQ(op_pump_bolus(&r.pump, 5000), OP_OK);
    advance(&r, 10);
    uint32_t mid = r.hal.total_steps;
    CHECK(mid > 0);
    r.hal.docked = false;
    advance(&r, 1);
    CHECK_EQ(r.hal.total_steps, mid);
    CHECK(!r.pump.de.bolus_active);
    CHECK(log_has(&r, OP_EV_BOLUS_CANCEL));
    CHECK_EQ(op_pump_bolus(&r.pump, 50), OP_ERR_NOT_DOCKED);
    r.hal.docked = true;
    advance(&r, 60);
    CHECK_EQ(r.hal.total_steps, mid); /* the cancelled bolus does not come back */
}

TEST(dock_is_sampled_before_every_motor_action_not_once_a_second)
{
    rig_t r;
    rig_running(&r, 0);
    r.hal.docked = false; /* no tick since */
    CHECK_EQ(op_pump_bolus(&r.pump, 50), OP_ERR_NOT_DOCKED);
    op_pump_suspend(&r.pump);
    CHECK_EQ(op_pump_resume(&r.pump), OP_ERR_NOT_DOCKED);
    CHECK_EQ(op_pump_prime(&r.pump, 5), OP_ERR_NOT_DOCKED);
    CHECK_EQ(r.hal.total_steps, 0);
}

TEST(dock_supervisor_is_the_hard_gate)
{
    op_sv_t sv;
    op_sv_init(&sv, 0, 0, TEST_UU);
    CHECK_EQ(op_sv_approve_steps(&sv, 0, 5, 100000), 0); /* starts closed: neither docked nor active */
    op_sv_set_active(&sv, true);
    CHECK_EQ(op_sv_approve_steps(&sv, 0, 5, 100000), 0);
    op_sv_set_docked(&sv, true);
    CHECK_EQ(op_sv_approve_steps(&sv, 0, 5, 100000), 5);
    op_sv_set_docked(&sv, false);
    CHECK_EQ(op_sv_approve_steps(&sv, 0, 5, 100000), 0);
    CHECK_EQ(sv.faults, 0); /* gating is not a fault */
    op_sv_set_docked(&sv, true);
    op_sv_set_active(&sv, false);
    CHECK_EQ(op_sv_approve_steps(&sv, 0, 5, 100000), 0);
}

TEST(dock_missing_hal_hooks_mean_not_docked)
{
    rig_t r;
    mock_hal_init(&r.hal);
    r.ops = mock_hal_make(&r.hal);
    r.ops.docked = NULL;
    r.ops.charger_present = NULL;
    op_pump_init(&r.pump, &r.ops, test_cal_5_1(), OP_CAPACITY_100_MU, 1);
    CHECK_EQ(op_pump_fill(&r.pump, 100000), OP_OK);
    CHECK_EQ(op_pump_set_pairing(&r.pump, TEST_PAIR, OP_ROLE_A), OP_OK);
    op_activate_args_t a;
    memset(&a, 0, sizeof a);
    a.pair_id = TEST_PAIR;
    a.activation_id = 1;
    a.schedule.count = 1;
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_ERR_NOT_DOCKED);
}

/* ---- wear timer ------------------------------------------------------------- */
TEST(wear_warning_at_44h_stop_and_alarm_at_52h)
{
    rig_t r;
    rig_running(&r, 0);
    advance_hours(&r, 43);
    op_status_t st = status(&r);
    CHECK(!(st.flags & OP_ST_WEAR_WARNING));
    CHECK_EQ(st.wear_s, 43 * 3600);
    advance_hours(&r, 1); /* 44 h */
    st = status(&r);
    CHECK(st.flags & OP_ST_WEAR_WARNING);
    CHECK_EQ(st.faults, 0);
    CHECK_EQ(st.delivery_state, OP_DS_ACTIVE);
    CHECK_EQ(log_count(&r, OP_EV_WEAR_WARNING), 1);
    advance_hours(&r, 7); /* 51 h: still delivering, warned only once */
    CHECK_EQ(log_count(&r, OP_EV_WEAR_WARNING), 1);
    CHECK_EQ(status(&r).delivery_state, OP_DS_ACTIVE);
    CHECK_EQ(status(&r).faults, 0);
    advance_hours(&r, 1); /* 52 h */
    st = status(&r);
    CHECK(st.faults & OP_FAULT_WEAR_EXPIRED);
    CHECK_EQ(st.delivery_state, OP_DS_STOPPED_WEAR);
    CHECK(st.flags & OP_ST_ALARM);
    CHECK(st.flags & OP_ST_SUSPENDED);
    CHECK_EQ(r.hal.buzzer, OP_BUZZER_ALARM);
    CHECK_EQ(log_count(&r, OP_EV_WEAR_EXPIRED), 1);
}

TEST(wear_expired_pod_delivers_nothing_and_cannot_be_resumed_or_acknowledged)
{
    rig_t r;
    rig_running(&r, 3000);
    advance_hours(&r, 52);
    uint32_t steps = r.hal.total_steps;
    advance(&r, 3600);
    CHECK_EQ(r.hal.total_steps, steps);
    CHECK_EQ(op_pump_resume(&r.pump), OP_ERR_FAULT);
    CHECK_EQ(op_pump_bolus(&r.pump, 50), OP_ERR_FAULT);
    CHECK_EQ(op_pump_acknowledge(&r.pump, 0xFFFF), OP_ERR_PERSISTS);
    CHECK(status(&r).faults & OP_FAULT_WEAR_EXPIRED);
}

TEST(wear_counts_a_stalled_loop_in_full)
{
    rig_t r;
    rig_running(&r, 0);
    r.hal.now_ms += 52 * HOUR_MS; /* one single tick after a 52 h stall */
    op_pump_tick(&r.pump);
    CHECK(status(&r).faults & OP_FAULT_WEAR_EXPIRED);
}

TEST(wear_timer_restarts_with_a_new_activation_and_is_frozen_while_released)
{
    rig_t r;
    rig_running(&r, 0);
    advance_hours(&r, 52);
    CHECK_EQ(op_pump_release(&r.pump, TEST_PAIR, NULL), OP_OK);
    uint32_t frozen = status(&r).wear_s;
    advance_hours(&r, 10);
    CHECK_EQ(status(&r).wear_s, frozen);
    op_activate_args_t a;
    memset(&a, 0, sizeof a);
    a.pair_id = TEST_PAIR;
    a.activation_id = 2;
    a.schedule.count = 1;
    a.schedule.seg[0].rate_mu_h = 1000;
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_OK);
    op_status_t st = status(&r);
    CHECK_EQ(st.wear_s, 0);
    CHECK_EQ(st.faults & OP_FAULT_WEAR_EXPIRED, 0);
    CHECK(!(st.flags & OP_ST_WEAR_WARNING));
    CHECK_EQ(op_pump_resume(&r.pump), OP_OK);
    advance(&r, 3600);
    CHECK(r.hal.total_steps > 0);
}

/* ---- pairing ------------------------------------------------------------------ */
TEST(pairing_validation)
{
    rig_t r;
    rig_init(&r);
    CHECK_EQ(op_pump_set_pairing(&r.pump, 0, OP_ROLE_A), OP_ERR_BAD_ARG);
    CHECK_EQ(op_pump_set_pairing(&r.pump, 5, OP_ROLE_NONE), OP_ERR_BAD_ARG);
    CHECK_EQ(op_pump_set_pairing(&r.pump, 5, 3), OP_ERR_BAD_ARG);
    CHECK_EQ(op_pump_set_pairing(&r.pump, 5, OP_ROLE_B), OP_OK);
    op_status_t st = status(&r);
    CHECK_EQ(st.pair_id, 5);
    CHECK_EQ(st.role, OP_ROLE_B);
    CHECK(log_has(&r, OP_EV_PAIRED));
}

TEST(pairing_refused_while_active)
{
    rig_t r;
    rig_running(&r, 0);
    CHECK_EQ(op_pump_set_pairing(&r.pump, 77, OP_ROLE_B), OP_ERR_ALREADY_ACTIVE);
    CHECK_EQ(status(&r).pair_id, TEST_PAIR);
}

/* ---- Activate ------------------------------------------------------------------ */
static op_activate_args_t act_args(uint32_t activation_id)
{
    op_activate_args_t a;
    memset(&a, 0, sizeof a);
    a.pair_id = TEST_PAIR;
    a.activation_id = activation_id;
    a.schedule.count = 1;
    a.schedule.seg[0].rate_mu_h = 1000;
    return a;
}

static void rig_ready(rig_t *r)
{
    rig_init(r);
    CHECK_EQ(op_pump_fill(&r->pump, 100000), OP_OK);
    CHECK_EQ(op_pump_set_pairing(&r->pump, TEST_PAIR, OP_ROLE_A), OP_OK);
}

TEST(activate_refuses_unpaired_and_wrong_pair)
{
    rig_t r;
    rig_init(&r);
    op_pump_fill(&r.pump, 100000);
    op_activate_args_t a = act_args(1);
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_ERR_PAIR); /* not paired */
    op_pump_set_pairing(&r.pump, TEST_PAIR, OP_ROLE_A);
    a.pair_id = TEST_PAIR + 1;
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_ERR_PAIR);
    CHECK(!r.pump.pod.active);
}

TEST(activate_refuses_when_not_docked)
{
    rig_t r;
    rig_ready(&r);
    r.hal.docked = false;
    op_activate_args_t a = act_args(1);
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_ERR_NOT_DOCKED);
    CHECK(!r.pump.pod.active);
    CHECK_EQ(status(&r).delivery_state, OP_DS_RELEASED);
    r.hal.docked = true;
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_OK);
}

TEST(activate_refuses_unfilled_charging_and_faulted_pods)
{
    rig_t r;
    rig_init(&r);
    op_pump_set_pairing(&r.pump, TEST_PAIR, OP_ROLE_A);
    op_activate_args_t a = act_args(1);
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_ERR_RESERVOIR);
    op_pump_fill(&r.pump, 100000);
    r.hal.charger = true;
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_ERR_CHARGING);
    r.hal.charger = false;
    r.hal.battery_mv = 3000; /* critical battery */
    advance(&r, 2);
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_ERR_FAULT);
    CHECK(!r.pump.pod.active);
}

TEST(activate_is_all_or_nothing)
{
    rig_t r;
    rig_ready(&r);
    op_activate_args_t a = act_args(1);
    a.schedule.seg[0].rate_mu_h = 5050; /* above the configured max basal */
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_ERR_LIMIT);
    CHECK(!r.pump.pod.active);
    CHECK(!r.pump.de.has_schedule);
    a = act_args(1);
    a.has_temp = true;
    a.temp_rate_mu_h = 1000;
    a.temp_remaining_min = 20; /* not a multiple of 30 */
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_ERR_BAD_ARG);
    a.temp_remaining_min = 30;
    a.temp_rate_mu_h = 9000; /* above max basal */
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_ERR_LIMIT);
    a = act_args(0); /* activation id 0 is reserved */
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_ERR_BAD_ARG);
    CHECK(!r.pump.pod.active);
    CHECK(!r.pump.de.has_schedule);
    CHECK(!log_has(&r, OP_EV_ACTIVATE));
}

TEST(activate_carries_schedule_and_leaves_delivery_suspended_until_resume)
{
    rig_t r;
    rig_ready(&r);
    op_activate_args_t a = act_args(7);
    a.schedule.count = 2;
    a.schedule.seg[1] = (op_basal_seg_t){4, 2000};
    a.has_temp = true;
    a.temp_rate_mu_h = 2500;
    a.temp_remaining_min = 90;
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_OK);
    op_status_t st = status(&r);
    CHECK_EQ(st.delivery_state, OP_DS_ACTIVE);
    CHECK(st.flags & OP_ST_ACTIVE);
    CHECK(st.flags & OP_ST_SUSPENDED);
    CHECK(st.flags & OP_ST_HAS_SCHEDULE);
    CHECK_EQ(st.wear_s, 0);
    advance(&r, 120);
    CHECK_EQ(r.hal.total_steps, 0); /* nothing before Resume */
    CHECK_EQ(op_pump_prime(&r.pump, 10), OP_OK); /* connector prime works while suspended */
    CHECK_EQ(r.hal.total_steps, 10);
    CHECK_EQ(op_pump_resume(&r.pump), OP_OK);
    st = status(&r);
    CHECK(st.flags & OP_ST_TEMP_ACTIVE);
    CHECK_EQ(st.temp_rate_mu_h, 2500);
    CHECK_EQ(st.temp_remaining_min, 90);
    CHECK_EQ(st.current_rate_mu_h, 2500);
    CHECK(log_has(&r, OP_EV_ACTIVATE));
    advance(&r, 1800);
    CHECK(r.hal.total_steps > 10 + 40); /* 2.5 U/h for 30 min = 47 steps */
}

TEST(activate_is_idempotent_for_the_same_activation_id)
{
    rig_t r;
    rig_ready(&r);
    op_activate_args_t a = act_args(7);
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_OK);
    CHECK_EQ(op_pump_resume(&r.pump), OP_OK);
    advance(&r, 600);
    uint32_t steps = r.hal.total_steps;
    CHECK_EQ(op_pump_activate(&r.pump, &a), OP_OK); /* lost response, app retries */
    CHECK_EQ(log_count(&r, OP_EV_ACTIVATE), 1);
    CHECK(!(status(&r).flags & OP_ST_SUSPENDED)); /* untouched: still delivering */
    advance(&r, 60);
    CHECK(r.hal.total_steps >= steps);
    op_activate_args_t b = act_args(8);
    CHECK_EQ(op_pump_activate(&r.pump, &b), OP_ERR_ALREADY_ACTIVE);
}

/* ---- Release -------------------------------------------------------------------- */
TEST(release_stops_delivery_reports_totals_and_is_idempotent)
{
    rig_t r;
    rig_running(&r, 0);
    CHECK_EQ(op_pump_bolus(&r.pump, 2000), OP_OK);
    advance(&r, 90);
    uint32_t delivered = 0;
    CHECK_EQ(op_pump_release(&r.pump, TEST_PAIR, &delivered), OP_OK);
    CHECK_EQ(delivered, 1983); /* 76 steps * 26.1 mU */
    op_status_t st = status(&r);
    CHECK_EQ(st.delivery_state, OP_DS_RELEASED);
    CHECK(!(st.flags & OP_ST_ACTIVE));
    CHECK(st.flags & OP_ST_SUSPENDED);
    CHECK_EQ(st.delivered_mu, 1983);
    CHECK_EQ(st.reservoir_mu, 98016); /* 100000 - 1983.6 */
    CHECK(!r.hal.enabled);
    uint32_t steps = r.hal.total_steps;
    advance(&r, 3600);
    CHECK_EQ(r.hal.total_steps, steps);
    uint32_t again = 0;
    CHECK_EQ(op_pump_release(&r.pump, TEST_PAIR, &again), OP_OK); /* retry after BLE loss */
    CHECK_EQ(again, 1983);
    CHECK_EQ(log_count(&r, OP_EV_RELEASE), 1);
    CHECK_EQ(op_pump_release(&r.pump, TEST_PAIR + 1, NULL), OP_ERR_PAIR);
}

TEST(release_works_while_undocked_and_cancels_bolus_and_temp)
{
    rig_t r;
    rig_running(&r, 1000);
    CHECK_EQ(op_pump_set_temp_basal(&r.pump, 2000, 60), OP_OK);
    CHECK_EQ(op_pump_bolus(&r.pump, 1000), OP_OK);
    r.hal.docked = false;
    CHECK_EQ(op_pump_release(&r.pump, TEST_PAIR, NULL), OP_OK);
    CHECK(!r.pump.de.bolus_active);
    CHECK(!r.pump.de.temp_active);
}

TEST(released_pod_refuses_every_delivery_command)
{
    rig_t r;
    rig_running(&r, 1000);
    CHECK_EQ(op_pump_release(&r.pump, TEST_PAIR, NULL), OP_OK);
    op_basal_schedule_t s = {0};
    s.count = 1;
    s.seg[0].rate_mu_h = 1000;
    CHECK_EQ(op_pump_set_schedule(&r.pump, &s), OP_ERR_RELEASED);
    CHECK_EQ(op_pump_set_temp_basal(&r.pump, 1000, 30), OP_ERR_RELEASED);
    CHECK_EQ(op_pump_bolus(&r.pump, 50), OP_ERR_RELEASED);
    CHECK_EQ(op_pump_resume(&r.pump), OP_ERR_RELEASED);
    CHECK_EQ(op_pump_prime(&r.pump, 5), OP_ERR_RELEASED);
    advance(&r, 3600);
    uint32_t steps = r.hal.total_steps;
    advance(&r, 3600);
    CHECK_EQ(r.hal.total_steps, steps);
    /* the spare can still be filled (it is refilled while parked on the charger) */
    CHECK_EQ(op_pump_fill(&r.pump, 90000), OP_OK);
}

/* ---- charger -------------------------------------------------------------------- */
TEST(charger_forces_release)
{
    rig_t r;
    rig_running(&r, 3000);
    advance(&r, 120);
    r.hal.charger = true;
    advance(&r, 1);
    op_status_t st = status(&r);
    CHECK_EQ(st.delivery_state, OP_DS_RELEASED);
    CHECK(!(st.flags & OP_ST_ACTIVE));
    CHECK(log_has(&r, OP_EV_RELEASE));
    uint32_t steps = r.hal.total_steps;
    r.hal.charger = false;
    advance(&r, 600);
    CHECK_EQ(r.hal.total_steps, steps); /* leaving the charger does NOT re-activate */
    CHECK_EQ(op_pump_resume(&r.pump), OP_ERR_RELEASED);
}

/* ---- persistence hook ------------------------------------------------------------- */
TEST(restore_active_pod_comes_up_suspended_with_wear_and_pairing)
{
    rig_t r;
    rig_init(&r);
    op_pump_restore_pod(&r.pump, TEST_PAIR, OP_ROLE_B, true, 42, 45 * HOUR_MS);
    op_status_t st = status(&r);
    CHECK_EQ(st.pair_id, TEST_PAIR);
    CHECK_EQ(st.role, OP_ROLE_B);
    CHECK(st.flags & OP_ST_ACTIVE);
    CHECK(st.flags & OP_ST_SUSPENDED);
    CHECK(st.flags & OP_ST_WEAR_WARNING);
    CHECK_EQ(st.wear_s, 45 * 3600);
}

TEST(restore_beyond_wear_limit_latches_the_fault_at_boot)
{
    rig_t r;
    rig_init(&r);
    op_pump_restore_pod(&r.pump, TEST_PAIR, OP_ROLE_A, true, 42, 53 * HOUR_MS);
    CHECK(status(&r).faults & OP_FAULT_WEAR_EXPIRED);
    CHECK_EQ(status(&r).delivery_state, OP_DS_STOPPED_WEAR);
}

/* ---- two pods, one pair: only one delivers ---------------------------------------- */
TEST(two_pods_only_the_activated_one_delivers)
{
    rig_t a, b;
    rig_init(&a);
    rig_init(&b);
    op_pump_fill(&a.pump, 100000);
    op_pump_fill(&b.pump, 100000);
    CHECK_EQ(op_pump_set_pairing(&a.pump, TEST_PAIR, OP_ROLE_A), OP_OK);
    CHECK_EQ(op_pump_set_pairing(&b.pump, TEST_PAIR, OP_ROLE_B), OP_OK);
    op_activate_args_t act = act_args(1);
    CHECK_EQ(op_pump_activate(&a.pump, &act), OP_OK);
    CHECK_EQ(op_pump_resume(&a.pump), OP_OK);
    b.hal.docked = false; /* B sits on the charger, not on the cannula */
    CHECK_EQ(op_pump_activate(&b.pump, &act), OP_ERR_NOT_DOCKED);
    for (int i = 0; i < 600; i++) {
        a.hal.now_ms += 1000;
        b.hal.now_ms += 1000;
        op_pump_tick(&a.pump);
        op_pump_tick(&b.pump);
    }
    CHECK(a.hal.total_steps > 0);
    CHECK_EQ(b.hal.total_steps, 0);
    /* handover: A released, B docked and activated */
    CHECK_EQ(op_pump_release(&a.pump, TEST_PAIR, NULL), OP_OK);
    b.hal.docked = true;
    act = act_args(2);
    CHECK_EQ(op_pump_activate(&b.pump, &act), OP_OK);
    CHECK_EQ(op_pump_resume(&b.pump), OP_OK);
    uint32_t a_steps = a.hal.total_steps;
    for (int i = 0; i < 600; i++) {
        a.hal.now_ms += 1000;
        b.hal.now_ms += 1000;
        op_pump_tick(&a.pump);
        op_pump_tick(&b.pump);
    }
    CHECK_EQ(a.hal.total_steps, a_steps);
    CHECK(b.hal.total_steps > 0);
}

/* ---- wire format ------------------------------------------------------------------- */
static op_cmd_t roundtrip_cmd(const op_cmd_t *c)
{
    uint8_t buf[200];
    int n = op_cmd_encode_payload(c, buf, sizeof buf);
    CHECK(n > 0);
    op_cmd_t d;
    CHECK_EQ(op_cmd_decode(c->type, 3, buf, (size_t)n, &d), 0);
    return d;
}

TEST(wire_pairing_activate_release_roundtrip)
{
    op_cmd_t c;
    memset(&c, 0, sizeof c);
    c.type = OP_CMD_SET_PAIRING;
    c.u.pairing.pair_id = 0x11223344u;
    c.u.pairing.role = OP_ROLE_B;
    op_cmd_t d = roundtrip_cmd(&c);
    CHECK_EQ(d.u.pairing.pair_id, 0x11223344u);
    CHECK_EQ(d.u.pairing.role, OP_ROLE_B);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_RELEASE;
    c.u.release.pair_id = 0x55667788u;
    d = roundtrip_cmd(&c);
    CHECK_EQ(d.u.release.pair_id, 0x55667788u);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_ACTIVATE;
    c.u.activate.pair_id = 9;
    c.u.activate.activation_id = 77;
    c.u.activate.schedule.count = 2;
    c.u.activate.schedule.seg[0] = (op_basal_seg_t){0, 800};
    c.u.activate.schedule.seg[1] = (op_basal_seg_t){30, 1200};
    c.u.activate.has_temp = true;
    c.u.activate.temp_rate_mu_h = 2100;
    c.u.activate.temp_remaining_min = 150;
    d = roundtrip_cmd(&c);
    CHECK_EQ(d.u.activate.pair_id, 9);
    CHECK_EQ(d.u.activate.activation_id, 77);
    CHECK_EQ(d.u.activate.schedule.count, 2);
    CHECK_EQ(d.u.activate.schedule.seg[1].rate_mu_h, 1200);
    CHECK(d.u.activate.has_temp);
    CHECK_EQ(d.u.activate.temp_rate_mu_h, 2100);
    CHECK_EQ(d.u.activate.temp_remaining_min, 150);
    c.u.activate.has_temp = false;
    d = roundtrip_cmd(&c);
    CHECK(!d.u.activate.has_temp);
}

TEST(wire_malformed_pairing_activate_release_are_rejected)
{
    op_cmd_t d;
    CHECK(op_cmd_decode(OP_CMD_SET_PAIRING, 1, NULL, 0, &d) < 0);
    CHECK(op_cmd_decode(OP_CMD_RELEASE, 1, NULL, 0, &d) < 0);
    CHECK(op_cmd_decode(OP_CMD_ACTIVATE, 1, NULL, 0, &d) < 0);
    /* Activate without a schedule */
    uint8_t p[] = {OP_TAG_PAIR_ID, 4, 1, 0, 0, 0, OP_TAG_ACTIVATION_ID, 4, 1, 0, 0, 0};
    CHECK(op_cmd_decode(OP_CMD_ACTIVATE, 1, p, sizeof p, &d) < 0);
    /* temp rate without duration */
    uint8_t q[] = {OP_TAG_PAIR_ID, 4, 1, 0, 0, 0, OP_TAG_ACTIVATION_ID, 4, 1, 0, 0, 0,
                   OP_TAG_BASAL_SEG, 3, 0, 0x10, 0x00, OP_TAG_RATE_MU_H, 2, 0xE8, 0x03};
    CHECK(op_cmd_decode(OP_CMD_ACTIVATE, 1, q, sizeof q, &d) < 0);
}

TEST(protocol_release_response_carries_totals_and_status)
{
    rig_t r;
    rig_running(&r, 0);
    CHECK_EQ(op_pump_bolus(&r.pump, 1000), OP_OK);
    advance(&r, 60);
    op_cmd_t c;
    memset(&c, 0, sizeof c);
    c.type = OP_CMD_RELEASE;
    c.seq = 5;
    c.u.release.pair_id = TEST_PAIR;
    op_rsp_t rsp;
    memset(&rsp, 0, sizeof rsp);
    op_pump_execute(&r.pump, &c, &rsp);
    CHECK_EQ(rsp.result, OP_OK);
    CHECK(rsp.has_status);
    CHECK(rsp.has_act_delivered);
    CHECK_EQ(rsp.act_delivered_mu, 991);
    uint8_t buf[200];
    int n = op_rsp_encode_payload(&rsp, buf, sizeof buf);
    CHECK(n > 0);
    op_rsp_t d;
    CHECK_EQ(op_rsp_decode(OP_CMD_RELEASE, 5, buf, (size_t)n, &d), 0);
    CHECK(d.has_act_delivered);
    CHECK_EQ(d.act_delivered_mu, 991);
    CHECK_EQ(d.status.delivery_state, OP_DS_RELEASED);
    CHECK_EQ(d.status.reservoir_mu, 99008);
    CHECK_EQ(d.status.delivered_mu, 991);
    CHECK_EQ(d.status.pair_id, TEST_PAIR);
    CHECK_EQ(d.status.role, OP_ROLE_A);
}

TEST(protocol_status_reports_docked_role_and_wear)
{
    rig_t r;
    rig_running(&r, 0);
    advance_hours(&r, 2);
    op_cmd_t c;
    memset(&c, 0, sizeof c);
    c.type = OP_CMD_GET_STATUS;
    op_rsp_t rsp;
    memset(&rsp, 0, sizeof rsp);
    op_pump_execute(&r.pump, &c, &rsp);
    uint8_t buf[220];
    int n = op_rsp_encode_payload(&rsp, buf, sizeof buf);
    CHECK(n > 0);
    op_rsp_t d;
    CHECK_EQ(op_rsp_decode(OP_CMD_GET_STATUS, 0, buf, (size_t)n, &d), 0);
    CHECK(d.status.flags & OP_ST_DOCKED);
    CHECK(d.status.flags & OP_ST_ACTIVE);
    CHECK_EQ(d.status.role, OP_ROLE_A);
    CHECK_EQ(d.status.pair_id, TEST_PAIR);
    CHECK_EQ(d.status.wear_s, 2 * 3600);
    CHECK_EQ(d.status.delivery_state, OP_DS_ACTIVE);
}
