/* Drive calibration: per-step volume is data (not a constant), validated, and gates delivery. */
#include "cal_fixture.h"
#include "mock_hal.h"
#include "op/pump_controller.h"
#include "op_test.h"

typedef struct {
    mock_hal_t hal;
    op_hal_t ops;
    op_pump_t pump;
} rig_t;

static void rig_init(rig_t *r, const op_drive_cal_t *cal)
{
    mock_hal_init(&r->hal);
    r->ops = mock_hal_make(&r->hal);
    op_pump_init(&r->pump, &r->ops, cal, OP_CAPACITY_200_MU, 1);
}

static void advance(rig_t *r, uint32_t seconds)
{
    for (uint32_t i = 0; i < seconds; i++) {
        r->hal.now_ms += 1000;
        op_pump_tick(&r->pump);
    }
}

static uint32_t run_ms(op_de_t *de, uint32_t ms)
{
    uint32_t steps = 0;
    for (uint32_t t = 0; t < ms; t += 1000) {
        op_de_comm_heartbeat(de);
        steps += op_de_tick(de, 1000);
    }
    return steps;
}

/* ---- presets -------------------------------------------------------------- */
TEST(cal_presets_are_valid_and_match_spec)
{
    op_drive_cal_t a = test_cal(OP_DRIVE_ZWBPD006006_5_1), f = test_cal(OP_DRIVE_FAULHABER_16_1);
    CHECK_EQ(op_drive_cal_validate(&a), OP_OK);
    CHECK_EQ(op_drive_cal_validate(&f), OP_OK);
    CHECK_EQ(a.micro_u_per_step, 26100); /* spec/design-parameters.md section 4: 0.0261 U/step */
    CHECK_EQ(a.steps_per_rev, 20);
    CHECK_EQ(a.gear_ratio_x100, 500);
    CHECK_EQ(f.gear_ratio_x100, 1600);
    CHECK_EQ(op_drive_cal_steps_per_spindle_rev(&a), 100);
    CHECK_EQ(op_drive_cal_steps_per_spindle_rev(&f), 320);
    op_drive_cal_t bad;
    CHECK_EQ(op_drive_cal_preset((op_drive_id_t)99, &bad), OP_ERR_BAD_ARG);
    CHECK_EQ(op_drive_cal_preset(OP_DRIVE_NONE, &bad), OP_ERR_BAD_ARG);
}

TEST(cal_rejects_missing_corrupt_out_of_range_and_wrong_volume)
{
    CHECK_EQ(op_drive_cal_validate(NULL), OP_ERR_NOT_FOUND);
    op_drive_cal_t c = test_cal(OP_DRIVE_ZWBPD006006_5_1);
    c.micro_u_per_step ^= 1; /* bit flip, stale CRC */
    CHECK_EQ(op_drive_cal_validate(&c), OP_ERR_CRC);
    op_drive_cal_t z = {0}; /* erased / zero flash */
    CHECK_EQ(op_drive_cal_validate(&z), OP_ERR_NOT_FOUND);
    c = test_cal(OP_DRIVE_ZWBPD006006_5_1);
    c.micro_u_per_step = 100000; /* > sane range, valid CRC */
    c.crc32 = op_drive_cal_crc(&c);
    CHECK_EQ(op_drive_cal_validate(&c), OP_ERR_LIMIT);
    c.micro_u_per_step = 0;
    c.crc32 = op_drive_cal_crc(&c);
    CHECK_EQ(op_drive_cal_validate(&c), OP_ERR_LIMIT);
    /* the OLD 10:1 value (13.1 mU) is in range but is not the 5:1 drive: must not pass */
    c.micro_u_per_step = 13100;
    c.crc32 = op_drive_cal_crc(&c);
    CHECK_EQ(op_drive_cal_validate(&c), OP_ERR_BAD_ARG);
    c = test_cal(OP_DRIVE_ZWBPD006006_5_1);
    c.drive_id = 7;
    c.crc32 = op_drive_cal_crc(&c);
    CHECK_EQ(op_drive_cal_validate(&c), OP_ERR_BAD_ARG);
}

/* ---- dose arithmetic with the 5:1 drive ------------------------------------ */
TEST(cal_one_unit_bolus_is_38_steps_on_5_1_drive)
{
    rig_t r;
    op_drive_cal_t cal = test_cal(OP_DRIVE_ZWBPD006006_5_1);
    rig_init(&r, &cal);
    CHECK_EQ(op_pump_fill(&r.pump, 100000), OP_OK);
    CHECK_EQ(test_activate(&r.pump, 0), OP_OK);
    CHECK_EQ(op_pump_resume(&r.pump), OP_OK);
    CHECK_EQ(op_pump_bolus(&r.pump, 1000), OP_OK);
    advance(&r, 60);
    CHECK(r.hal.total_steps == 38 || r.hal.total_steps == 39);
    CHECK_EQ(r.hal.total_steps, 38); /* floor(1000 / 26.1) */
    op_status_t st;
    op_pump_get_status(&r.pump, &st);
    CHECK_EQ(st.faults, 0);
    CHECK_EQ(st.delivered_mu, 991);
    CHECK_EQ(st.reservoir_mu, 99008); /* 100000 - 38 * 26.1 = 99008.2 */
}

TEST(cal_remainder_stays_exact_over_many_pulses_5_1)
{
    op_de_t de;
    op_de_init(&de, TEST_UU);
    op_de_resume(&de);
    uint64_t requested_mu = 0;
    uint32_t steps = 0;
    for (int i = 0; i < 1000; i++) { /* 1000 pulses of 0.05 U */
        CHECK_EQ(op_de_start_bolus(&de, 50), OP_OK);
        steps += run_ms(&de, 5000);
        CHECK(!de.bolus_active);
        requested_mu += 50;
        /* running invariant: |requested - delivered| < 1 step + what is still in the accumulator */
        int64_t delivered_uu = (int64_t)steps * TEST_UU;
        int64_t requested_uu = (int64_t)requested_mu * 1000;
        CHECK(requested_uu - delivered_uu >= 0);
        CHECK(requested_uu - delivered_uu < TEST_UU);
    }
    CHECK_EQ(requested_mu, 50000);
    CHECK_EQ(steps, 1915); /* floor(50 U / 26.1 mU) */
    /* average pulse = 0.05 U within 0.1 % */
    double avg_u = (double)steps * 0.0261 / 1000.0;
    CHECK(avg_u > 0.05 * 0.999 && avg_u < 0.05 * 1.001);
    /* exact remainder: accumulator holds (requested - delivered) uU, scaled by OP_SCALED_PER_UU */
    CHECK_EQ(de.acc, ((int64_t)50000 * 1000 - (int64_t)steps * TEST_UU) * OP_SCALED_PER_UU);
}

TEST(cal_basal_day_delivers_scheduled_volume_5_1)
{
    op_de_t de;
    op_de_init(&de, TEST_UU);
    op_basal_schedule_t s = {0};
    s.count = 1;
    s.seg[0].rate_mu_h = 1000;
    CHECK_EQ(op_de_set_schedule(&de, &s), OP_OK);
    op_de_resume(&de);
    uint32_t steps = 0;
    for (int i = 0; i < 24 * 60; i++) steps += run_ms(&de, 60000);
    CHECK_EQ(steps, 919); /* 24 U / 26.1 mU = 919.5 */
}

/* ---- Faulhaber preset -------------------------------------------------------- */
TEST(cal_faulhaber_preset_gives_about_122_5_steps_per_unit)
{
    op_de_t de;
    op_drive_cal_t f = test_cal(OP_DRIVE_FAULHABER_16_1);
    op_de_init(&de, f.micro_u_per_step);
    op_de_resume(&de);
    uint32_t steps = 0;
    for (int i = 0; i < 100; i++) { /* 100 U in 1 U boluses */
        CHECK_EQ(op_de_start_bolus(&de, 1000), OP_OK);
        steps += run_ms(&de, 40000);
    }
    double per_u = (double)steps / 100.0;
    CHECK(per_u > 122.0 && per_u < 123.0);
    CHECK_EQ(steps, 12260); /* floor(100 U / 8.156 mU) */
    CHECK_EQ(op_mu_to_steps(f.micro_u_per_step, 1000), 122);
    CHECK_EQ(op_steps_to_mu(f.micro_u_per_step, 1000), 8156);
}

TEST(cal_faulhaber_pump_runs_and_limits_follow_calibration)
{
    rig_t r;
    op_drive_cal_t f = test_cal(OP_DRIVE_FAULHABER_16_1);
    rig_init(&r, &f);
    CHECK_EQ(op_pump_fill(&r.pump, 100000), OP_OK);
    CHECK_EQ(test_activate(&r.pump, 0), OP_OK);
    /* prime limit is a VOLUME (0.52 U), so it is more steps on the finer drive */
    CHECK_EQ(op_pump_prime(&r.pump, 65), OP_ERR_LIMIT);
    CHECK_EQ(op_pump_prime(&r.pump, 64), OP_OK);
    CHECK_EQ(op_pump_resume(&r.pump), OP_OK);
    CHECK_EQ(op_pump_bolus(&r.pump, 1000), OP_OK);
    uint32_t before = r.hal.total_steps;
    advance(&r, 60);
    CHECK(r.hal.total_steps - before == 122 || r.hal.total_steps - before == 123);
}

/* ---- invalid calibration blocks delivery ---------------------------------- */
static void expect_blocked(rig_t *r)
{
    op_status_t st;
    op_pump_get_status(&r->pump, &st);
    CHECK(st.faults & OP_FAULT_NO_CALIBRATION);
    CHECK(st.flags & OP_ST_ALARM);
    CHECK_EQ(st.cal_uu_per_step, 0);
    CHECK_EQ(st.cal_drive_id, 0);
    CHECK_EQ(r->hal.buzzer, OP_BUZZER_ALARM);
    CHECK_EQ(op_pump_resume(&r->pump), OP_ERR_FAULT);
    CHECK_EQ(op_pump_bolus(&r->pump, 50), OP_ERR_FAULT);
    op_basal_schedule_t s = {0};
    s.count = 1;
    s.seg[0].rate_mu_h = 1000;
    CHECK_EQ(op_pump_set_schedule(&r->pump, &s), OP_ERR_FAULT);
    CHECK_EQ(op_pump_set_temp_basal(&r->pump, 1000, 30), OP_ERR_FAULT);
    /* priming goes through the same veto: no steps */
    op_pump_fill(&r->pump, 50000);
    CHECK(op_pump_prime(&r->pump, 5) != OP_OK);
    advance(r, 120);
    CHECK_EQ(r->hal.total_steps, 0);
    CHECK(!r->hal.stepped_while_disabled);
    CHECK(!r->hal.enabled);
    /* not acknowledgeable */
    CHECK_EQ(op_pump_acknowledge(&r->pump, 0xFFFF), OP_ERR_PERSISTS);
    op_pump_get_status(&r->pump, &st);
    CHECK(st.faults & OP_FAULT_NO_CALIBRATION);
    CHECK_EQ(op_pump_resume(&r->pump), OP_ERR_FAULT);
}

TEST(cal_missing_blocks_delivery)
{
    rig_t r;
    rig_init(&r, NULL);
    CHECK(!r.pump.cal_valid);
    expect_blocked(&r);
}

TEST(cal_corrupt_crc_blocks_delivery)
{
    rig_t r;
    op_drive_cal_t c = test_cal(OP_DRIVE_ZWBPD006006_5_1);
    c.micro_u_per_step = 13100; /* the old, wrong value written without fixing the CRC */
    rig_init(&r, &c);
    expect_blocked(&r);
}

TEST(cal_out_of_range_with_valid_crc_blocks_delivery)
{
    const uint32_t bad[] = {0, 1, 3999, 60001, 1000000, 0xFFFFFFFFu};
    for (unsigned i = 0; i < sizeof bad / sizeof bad[0]; i++) {
        rig_t r;
        op_drive_cal_t c = test_cal(OP_DRIVE_ZWBPD006006_5_1);
        c.micro_u_per_step = bad[i];
        c.crc32 = op_drive_cal_crc(&c);
        rig_init(&r, &c);
        expect_blocked(&r);
    }
}

TEST(cal_supervisor_range_check_is_independent)
{
    /* the supervisor does its own range check on the raw number it is handed */
    const uint32_t bad[] = {0, 3999, 60001};
    for (unsigned i = 0; i < 3; i++) {
        op_sv_t sv;
        op_sv_init(&sv, 0, 0, bad[i]);
        op_sv_set_docked(&sv, true);
        op_sv_set_active(&sv, true);
        CHECK(sv.faults & OP_FAULT_NO_CALIBRATION);
        CHECK_EQ(op_sv_approve_steps(&sv, 0, 10, 100000), 0);
        CHECK_EQ(op_sv_check_bolus(&sv, 0, 50, 100000), OP_ERR_FAULT);
        CHECK_EQ(op_sv_acknowledge(&sv, 0xFFFF), OP_ERR_PERSISTS);
        CHECK(sv.faults & OP_FAULT_NO_CALIBRATION);
    }
    const uint32_t good[] = {OP_CAL_UU_MIN, OP_CAL_UU_MAX, 26100, 8156};
    for (unsigned i = 0; i < 4; i++) {
        op_sv_t sv;
        op_sv_init(&sv, 0, 0, good[i]);
        op_sv_set_docked(&sv, true);
        op_sv_set_active(&sv, true);
        CHECK_EQ(sv.faults, 0);
        CHECK(op_sv_approve_steps(&sv, 0, 1, 100000) == 1);
    }
}

TEST(cal_engine_without_calibration_never_requests_steps)
{
    op_de_t de;
    op_de_init(&de, 0);
    op_de_resume(&de);
    CHECK_EQ(op_de_start_bolus(&de, 1000), OP_OK);
    CHECK_EQ(run_ms(&de, 60000), 0);
    CHECK_EQ(de.acc, 0);
}

TEST(cal_valid_status_reports_calibration_over_protocol)
{
    rig_t r;
    op_drive_cal_t cal = test_cal(OP_DRIVE_ZWBPD006006_5_1);
    rig_init(&r, &cal);
    op_cmd_t cmd = {0};
    cmd.type = OP_CMD_GET_STATUS;
    cmd.seq = 1;
    op_rsp_t rsp;
    memset(&rsp, 0, sizeof rsp);
    op_pump_execute(&r.pump, &cmd, &rsp);
    uint8_t buf[200];
    int n = op_rsp_encode_payload(&rsp, buf, sizeof buf);
    CHECK(n > 0);
    op_rsp_t d;
    CHECK_EQ(op_rsp_decode(OP_CMD_GET_STATUS, 1, buf, (size_t)n, &d), 0);
    CHECK_EQ(d.status.cal_drive_id, OP_DRIVE_ZWBPD006006_5_1);
    CHECK_EQ(d.status.cal_uu_per_step, 26100);
    CHECK_EQ(d.status.cal_steps_per_rev, 20);
    CHECK_EQ(d.status.cal_gear_ratio_x100, 500);
    CHECK_EQ(d.status.faults & OP_FAULT_NO_CALIBRATION, 0);
}

TEST(cal_status_tlv_wire_format)
{
    op_rsp_t r;
    memset(&r, 0, sizeof r);
    r.has_status = true;
    r.status.cal_drive_id = 1;
    r.status.cal_uu_per_step = 26100;
    r.status.cal_steps_per_rev = 20;
    r.status.cal_gear_ratio_x100 = 500;
    uint8_t buf[200];
    int n = op_rsp_encode_payload(&r, buf, sizeof buf);
    CHECK(n > 0);
    op_tlv_r_t rd;
    op_tlv_r_init(&rd, buf, (size_t)n);
    uint8_t tag, vl;
    const uint8_t *v;
    bool found = false;
    while (op_tlv_next(&rd, &tag, &v, &vl)) {
        if (tag != OP_TAG_DRIVE_CAL) continue;
        found = true;
        CHECK_EQ(vl, 10);
        CHECK_EQ(v[0] | (v[1] << 8), 1);
        CHECK_EQ(v[2] | (v[3] << 8) | (v[4] << 16) | ((uint32_t)v[5] << 24), 26100);
        CHECK_EQ(v[6] | (v[7] << 8), 20);
        CHECK_EQ(v[8] | (v[9] << 8), 500);
    }
    CHECK(found);
}
