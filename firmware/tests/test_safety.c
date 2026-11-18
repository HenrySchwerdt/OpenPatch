#include "op/safety_supervisor.h"
#include "cal_fixture.h"
#include "op_test.h"

#define MIN 60000ull

static op_sv_t mk(void)
{
    op_sv_t sv;
    op_sv_init(&sv, 0, 0, TEST_UU);
    op_sv_set_docked(&sv, true); /* delivery preconditions: docked + active pod */
    op_sv_set_active(&sv, true);
    return sv;
}

TEST(sv_defaults_and_configure)
{
    op_sv_t sv = mk();
    CHECK_EQ(sv.max_bolus_mu, 10000);
    CHECK_EQ(sv.max_basal_mu_h, 5000);
    CHECK_EQ(op_sv_configure(&sv, 25000, 30000), OP_OK);
    CHECK_EQ(op_sv_configure(&sv, 25001, 5000), OP_ERR_LIMIT);
    CHECK_EQ(op_sv_configure(&sv, 10000, 30001), OP_ERR_LIMIT);
    CHECK_EQ(op_sv_configure(&sv, 0, 5000), OP_ERR_LIMIT);
    CHECK_EQ(op_sv_configure(&sv, 5000, 0), OP_ERR_LIMIT);
    CHECK_EQ(sv.max_bolus_mu, 25000); /* failed calls leave config untouched */
}

TEST(sv_check_bolus_rules)
{
    op_sv_t sv = mk();
    CHECK_EQ(op_sv_check_bolus(&sv, 0, 1000, 50000), OP_OK);
    CHECK_EQ(op_sv_check_bolus(&sv, 0, 10000, 50000), OP_OK);
    CHECK_EQ(op_sv_check_bolus(&sv, 0, 10050, 50000), OP_ERR_LIMIT);
    CHECK_EQ(op_sv_check_bolus(&sv, 0, 0, 50000), OP_ERR_BAD_ARG);
    CHECK_EQ(op_sv_check_bolus(&sv, 0, 1025, 50000), OP_ERR_BAD_ARG); /* 0.05 U grid */
    CHECK_EQ(op_sv_check_bolus(&sv, 0, 5000, 4000), OP_ERR_RESERVOIR);
}

TEST(sv_check_bolus_respects_rolling_hour)
{
    op_sv_t sv = mk();
    uint64_t t = 0;
    uint32_t steps = op_mu_to_steps(TEST_UU, 10000); /* 383 */
    for (int i = 0; i < 8; i++) { /* spread so the per-minute cap is not hit */
        CHECK_EQ(op_sv_approve_steps(&sv, t, steps / 8, 100000), steps / 8);
        t += MIN;
    }
    CHECK_EQ(op_sv_check_bolus(&sv, t, 10000, 100000), OP_ERR_HOURLY); /* 10 + 10 > 15 */
    CHECK_EQ(op_sv_check_bolus(&sv, t, 4000, 100000), OP_OK);
    CHECK_EQ(op_sv_check_bolus(&sv, t + 61 * MIN, 10000, 100000), OP_OK); /* window slid */
}

TEST(sv_check_schedule_and_temp)
{
    op_sv_t sv = mk();
    op_basal_schedule_t s = {0};
    s.count = 2;
    s.seg[0] = (op_basal_seg_t){0, 1000};
    s.seg[1] = (op_basal_seg_t){10, 5000};
    CHECK_EQ(op_sv_check_basal_schedule(&sv, &s), OP_OK);
    s.seg[1].rate_mu_h = 5050;
    CHECK_EQ(op_sv_check_basal_schedule(&sv, &s), OP_ERR_LIMIT);
    s.seg[1].rate_mu_h = 1025;
    CHECK_EQ(op_sv_check_basal_schedule(&sv, &s), OP_ERR_BAD_ARG);
    s.seg[1].start_slot = 0; /* structurally invalid */
    s.seg[1].rate_mu_h = 1000;
    CHECK_EQ(op_sv_check_basal_schedule(&sv, &s), OP_ERR_BAD_ARG);
    CHECK_EQ(op_sv_check_temp_basal(&sv, 5000, 30), OP_OK);
    CHECK_EQ(op_sv_check_temp_basal(&sv, 0, 720), OP_OK);
    CHECK_EQ(op_sv_check_temp_basal(&sv, 5050, 30), OP_ERR_LIMIT);
    CHECK_EQ(op_sv_check_temp_basal(&sv, 1025, 30), OP_ERR_BAD_ARG);
    CHECK_EQ(op_sv_check_temp_basal(&sv, 1000, 20), OP_ERR_BAD_ARG);
    CHECK_EQ(op_sv_check_temp_basal(&sv, 1000, 750), OP_ERR_BAD_ARG);
}

TEST(sv_checks_refuse_while_fault_latched)
{
    op_sv_t sv = mk();
    op_sv_observe(&sv, 0, 3000, 50000, 0); /* battery critical */
    op_basal_schedule_t s = {0};
    s.count = 1;
    CHECK_EQ(op_sv_check_bolus(&sv, 0, 1000, 50000), OP_ERR_FAULT);
    CHECK_EQ(op_sv_check_temp_basal(&sv, 1000, 30), OP_ERR_FAULT);
    CHECK_EQ(op_sv_check_basal_schedule(&sv, &s), OP_ERR_FAULT);
}

TEST(sv_approves_normal_steps)
{
    op_sv_t sv = mk();
    CHECK_EQ(op_sv_approve_steps(&sv, 0, 5, 50000), 5);
    CHECK_EQ(op_sv_approve_steps(&sv, 1000, 0, 50000), 0);
    CHECK_EQ(op_sv_faults(&sv), 0);
}

TEST(sv_hourly_cap_trims_and_latches)
{
    op_sv_t sv = mk();
    uint64_t t = 0;
    uint32_t total = 0, cap = op_mu_to_steps(TEST_UU, OP_MAX_HOURLY_MU); /* 574 */
    CHECK_EQ(cap, 574);
    for (int i = 0; i < 12; i++) { /* 60 steps/min is under the minute cap (65) */
        total += op_sv_approve_steps(&sv, t, 60, 1000000);
        t += MIN;
    }
    CHECK_EQ(total, cap);
    CHECK(op_sv_faults(&sv) & OP_FAULT_LIMIT_EXCEEDED);
    CHECK(!op_sv_motor_allowed(&sv));
    CHECK_EQ(op_sv_approve_steps(&sv, t, 1, 1000000), 0); /* latched: everything vetoed */
}

TEST(sv_rolling_window_slides)
{
    op_sv_t sv = mk();
    op_sv_approve_steps(&sv, 0, 60, 1000000);
    CHECK_EQ(op_sv_hourly_steps(&sv, 30 * MIN), 60);
    CHECK_EQ(op_sv_hourly_steps(&sv, 59 * MIN), 60);
    CHECK_EQ(op_sv_hourly_steps(&sv, 60 * MIN), 0);
    CHECK_EQ(op_sv_hourly_steps(&sv, 500 * MIN), 0);
}

TEST(sv_window_allows_full_cap_again_after_ack)
{
    op_sv_t sv = mk();
    uint64_t t = 0;
    for (int i = 0; i < 12; i++) { op_sv_approve_steps(&sv, t, 60, 1000000); t += MIN; }
    t += 61 * MIN;
    CHECK_EQ(op_sv_acknowledge(&sv, 0xFFFF), OP_OK);
    CHECK_EQ(op_sv_approve_steps(&sv, t, 60, 1000000), 60);
}

TEST(sv_per_minute_backstop)
{
    op_sv_t sv = mk();
    CHECK_EQ(op_sv_approve_steps(&sv, 0, 200, 1000000), op_mu_to_steps(TEST_UU, OP_MAX_MU_PER_MIN));
    CHECK(op_sv_faults(&sv) & OP_FAULT_LIMIT_EXCEEDED);
}

TEST(sv_reservoir_trim_latches_empty)
{
    op_sv_t sv = mk();
    CHECK_EQ(op_sv_approve_steps(&sv, 0, 10, 100), 3); /* floor(100 mU / 26.1 mU) */
    CHECK(op_sv_faults(&sv) & OP_FAULT_RESERVOIR_EMPTY);
}

TEST(sv_zero_reservoir_vetoes_everything)
{
    op_sv_t sv = mk();
    CHECK_EQ(op_sv_approve_steps(&sv, 0, 4, 0), 0);
    CHECK(op_sv_faults(&sv) & OP_FAULT_RESERVOIR_EMPTY);
}

TEST(sv_battery_critical_latches_and_low_flag)
{
    op_sv_t sv = mk();
    CHECK_EQ(op_sv_observe(&sv, 0, 3400, 50000, 0), 0);
    CHECK(op_sv_battery_low(&sv));
    CHECK_EQ(op_sv_observe(&sv, 1000, 3200, 50000, 0), OP_FAULT_BATTERY_CRITICAL);
    CHECK_EQ(op_sv_observe(&sv, 2000, 3200, 50000, 0), 0); /* not reported twice */
    CHECK_EQ(op_sv_approve_steps(&sv, 3000, 5, 50000), 0);
    /* recovery does not clear the latch */
    op_sv_observe(&sv, 4000, 3900, 50000, 0);
    CHECK(op_sv_faults(&sv) & OP_FAULT_BATTERY_CRITICAL);
    CHECK(!op_sv_battery_low(&sv));
}

TEST(sv_observe_latches_reservoir_empty)
{
    op_sv_t sv = mk();
    CHECK_EQ(op_sv_observe(&sv, 0, 3900, 0, 0), OP_FAULT_RESERVOIR_EMPTY);
}

/* drive supervisor + a simulated encoder; returns total new faults */
static uint16_t drive(op_sv_t *sv, int iterations, uint32_t steps_each, uint32_t pct)
{
    uint16_t faults = 0;
    int64_t enc_x100 = sv->last_enc * 100ll;
    uint64_t t = 0;
    for (int i = 0; i < iterations; i++) {
        uint32_t ok = op_sv_approve_steps(sv, t, steps_each, 1000000);
        enc_x100 += (int64_t)ok * 16 * pct;
        faults |= op_sv_observe(sv, t, 3900, 1000000, (int32_t)(enc_x100 / 100));
        t += MIN;
        if (faults) break;
    }
    return faults;
}

TEST(sv_healthy_encoder_never_faults)
{
    op_sv_t sv = mk();
    CHECK_EQ(drive(&sv, 200, 8, 100), 0); /* 8 steps/min stays under the hourly cap */
    CHECK(op_sv_motor_allowed(&sv));
}

TEST(sv_small_encoder_noise_is_tolerated)
{
    op_sv_t sv = mk();
    CHECK_EQ(drive(&sv, 100, 8, 97), 0); /* 3 % slip */
    CHECK(op_sv_motor_allowed(&sv));
}

TEST(sv_encoder_deviation_over_10_percent_stops)
{
    op_sv_t sv = mk();
    uint16_t f = drive(&sv, 100, 10, 85);
    CHECK(f & OP_FAULT_ENCODER_DEVIATION);
    CHECK(!(f & OP_FAULT_OCCLUSION)); /* 85 % travel is deviation, not occlusion */
    CHECK(sv.cmd_sub < op_mu_to_substeps(TEST_UU, 1400)); /* caught right after the first 1 U window */
}

TEST(sv_full_stall_is_occlusion_and_deviation)
{
    op_sv_t sv = mk();
    uint16_t f = drive(&sv, 100, 10, 0);
    CHECK(f & OP_FAULT_OCCLUSION);
    CHECK(f & OP_FAULT_ENCODER_DEVIATION);
    CHECK(sv.cmd_sub < op_mu_to_substeps(TEST_UU, OP_OCCLUSION_MU)); /* before 2 U went undelivered */
}

TEST(sv_over_delivery_is_deviation_not_occlusion)
{
    op_sv_t sv = mk();
    uint16_t f = drive(&sv, 100, 10, 130);
    CHECK(f & OP_FAULT_ENCODER_DEVIATION);
    CHECK(!(f & OP_FAULT_OCCLUSION));
}

TEST(sv_slow_leak_below_deviation_still_trips_occlusion_at_2u)
{
    op_sv_t sv = mk();
    uint16_t f = drive(&sv, 400, 8, 92); /* 8 % each window, running balance grows */
    CHECK(f & OP_FAULT_OCCLUSION);
    CHECK(!(f & OP_FAULT_ENCODER_DEVIATION));
    int64_t undelivered = sv.cmd_sub - (sv.last_enc - sv.enc_base);
    CHECK(undelivered > op_mu_to_substeps(TEST_UU, OP_OCCLUSION_MU));
}

TEST(sv_ack_clears_latched_encoder_faults_and_rebaselines)
{
    op_sv_t sv = mk();
    drive(&sv, 100, 10, 0);
    CHECK(!op_sv_motor_allowed(&sv));
    CHECK_EQ(op_sv_acknowledge(&sv, OP_FAULT_OCCLUSION | OP_FAULT_ENCODER_DEVIATION), OP_OK);
    CHECK(op_sv_motor_allowed(&sv));
    CHECK_EQ(drive(&sv, 50, 10, 100), 0); /* clean again, old balance forgotten */
}

TEST(sv_ack_refused_while_cause_persists)
{
    op_sv_t sv = mk();
    op_sv_observe(&sv, 0, 3200, 0, 0);
    CHECK_EQ(op_sv_faults(&sv), OP_FAULT_BATTERY_CRITICAL | OP_FAULT_RESERVOIR_EMPTY);
    /* battery still low, reservoir still empty */
    CHECK_EQ(op_sv_acknowledge(&sv, 0xFFFF), OP_ERR_PERSISTS);
    CHECK_EQ(op_sv_faults(&sv), OP_FAULT_BATTERY_CRITICAL | OP_FAULT_RESERVOIR_EMPTY);
    /* reservoir refilled, battery charged above hysteresis */
    op_sv_observe(&sv, 1000, 3350, 50000, 0); /* 3350 < 3300 + 100: not yet */
    CHECK_EQ(op_sv_acknowledge(&sv, OP_FAULT_BATTERY_CRITICAL), OP_ERR_PERSISTS);
    op_sv_observe(&sv, 2000, 3500, 50000, 0);
    CHECK_EQ(op_sv_acknowledge(&sv, 0xFFFF), OP_OK);
    CHECK_EQ(op_sv_faults(&sv), 0);
}

TEST(sv_ack_mask_is_selective_and_empty_ack_is_ok)
{
    op_sv_t sv = mk();
    CHECK_EQ(op_sv_acknowledge(&sv, 0xFFFF), OP_OK); /* nothing latched */
    op_sv_approve_steps(&sv, 0, 200, 1000000); /* LIMIT_EXCEEDED, trimmed to 65 steps */
    op_sv_observe(&sv, 0, 3900, 0, 65 * 16);   /* RESERVOIR_EMPTY, encoder consistent */
    CHECK_EQ(op_sv_acknowledge(&sv, OP_FAULT_LIMIT_EXCEEDED), OP_OK);
    CHECK_EQ(op_sv_faults(&sv), OP_FAULT_RESERVOIR_EMPTY);
}

TEST(sv_motor_commanded_total_follows_rebaseline_after_prime)
{
    op_sv_t sv = mk();
    op_sv_rebaseline(&sv, 5000);
    CHECK_EQ(sv.enc_base, 5000);
    CHECK_EQ(sv.cmd_sub, 0);
    CHECK_EQ(op_sv_observe(&sv, 0, 3900, 1000, 5000), 0);
}

TEST(sv_clock_jump_clears_window)
{
    op_sv_t sv = mk();
    op_sv_approve_steps(&sv, 0, 60, 1000000);
    op_sv_approve_steps(&sv, 10 * MIN, 60, 1000000);
    CHECK_EQ(op_sv_hourly_steps(&sv, 10 * MIN), 120);
    CHECK_EQ(op_sv_hourly_steps(&sv, 1000 * MIN), 0);
    /* time never goes backwards: older timestamps do not corrupt the window */
    CHECK_EQ(op_sv_hourly_steps(&sv, 5 * MIN), 0);
}
