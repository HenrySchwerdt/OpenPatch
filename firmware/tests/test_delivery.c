#include "op/delivery_engine.h"
#include "op_test.h"

#define H (3600u * 1000u)

static op_basal_schedule_t flat(uint32_t rate)
{
    op_basal_schedule_t s = {0};
    s.count = 1;
    s.seg[0].start_slot = 0;
    s.seg[0].rate_mu_h = rate;
    return s;
}

static void setup(op_de_t *de, uint32_t rate)
{
    op_de_init(de);
    op_basal_schedule_t s = flat(rate);
    CHECK_EQ(op_de_set_schedule(de, &s), OP_OK);
    op_de_comm_heartbeat(de);
    CHECK_EQ(op_de_resume(de), OP_OK);
}

/* run `ms` in 1 s ticks, committing everything; returns total steps */
static uint32_t run(op_de_t *de, uint32_t ms)
{
    uint32_t total = 0;
    for (uint32_t t = 0; t < ms; t += 1000) {
        uint32_t n = op_de_tick(de, 1000);
        op_de_commit(de, n);
        total += n;
    }
    return total;
}

TEST(de_starts_suspended_and_delivers_nothing)
{
    op_de_t de;
    op_de_init(&de);
    op_basal_schedule_t s = flat(1000);
    op_de_set_schedule(&de, &s);
    CHECK_EQ(run(&de, H), 0);
    CHECK(de.suspended);
}

TEST(de_zero_dt_returns_zero)
{
    op_de_t de;
    setup(&de, 1000);
    CHECK_EQ(op_de_tick(&de, 0), 0);
}

TEST(de_flat_basal_one_hour_exact_steps)
{
    op_de_t de;
    setup(&de, 1000); /* 1 U/h = 76.33 steps */
    CHECK_EQ(run(&de, H), 76);
    op_de_report_t r;
    op_de_report(&de, &r);
    CHECK_EQ(r.scheduled_mu, 1000);
    CHECK_EQ(r.delivered_steps, 76);
    CHECK_EQ(r.delivered_mu, 995);
}

TEST(de_fractional_steps_accumulate_over_a_day)
{
    op_de_t de;
    setup(&de, 5000); /* 120 U/day = 9160.3 steps */
    CHECK_EQ(run(&de, 24 * H), 9160);
    op_de_report_t r;
    op_de_report(&de, &r);
    CHECK_EQ(r.scheduled_mu, 120000);
    /* |scheduled - delivered| < 1 step (13.1 mU) */
    CHECK(r.scheduled_mu - r.delivered_mu < 14);
}

TEST(de_segments_apply_by_time_of_day)
{
    op_de_t de;
    op_de_init(&de);
    op_basal_schedule_t s = {0};
    s.count = 3;
    s.seg[0] = (op_basal_seg_t){0, 1000};
    s.seg[1] = (op_basal_seg_t){2, 0};     /* 01:00 */
    s.seg[2] = (op_basal_seg_t){4, 2000};  /* 02:00 */
    CHECK_EQ(op_de_set_schedule(&de, &s), OP_OK);
    op_de_resume(&de);
    op_de_comm_heartbeat(&de);
    /* 1 U + 0 U + 2 U = 3 U = 229.01 steps */
    CHECK_EQ(run(&de, 3 * H), 229);
    CHECK_EQ(op_de_current_rate_mu_h(&de), 2000);
}

TEST(de_big_tick_equals_small_ticks_across_boundaries)
{
    op_de_t a, b;
    op_basal_schedule_t s = {0};
    s.count = 3;
    s.seg[0] = (op_basal_seg_t){0, 1000};
    s.seg[1] = (op_basal_seg_t){2, 0};
    s.seg[2] = (op_basal_seg_t){4, 2000};
    op_de_init(&a);
    op_de_init(&b);
    op_de_set_schedule(&a, &s);
    op_de_set_schedule(&b, &s);
    op_de_resume(&a);
    op_de_resume(&b);
    uint32_t big = op_de_tick(&a, 3 * H);
    CHECK_EQ(big, run(&b, 3 * H));
    CHECK_EQ(a.acc, b.acc);
}

TEST(de_schedule_wraps_at_midnight)
{
    op_de_t de;
    op_de_init(&de);
    op_basal_schedule_t s = {0};
    s.count = 2;
    s.seg[0] = (op_basal_seg_t){0, 1000};
    s.seg[1] = (op_basal_seg_t){46, 3000}; /* 23:00 */
    op_de_set_schedule(&de, &s);
    op_de_resume(&de);
    op_de_set_time_of_day(&de, 23 * H + 30 * 60000u);
    op_de_comm_heartbeat(&de);
    run(&de, H); /* 30 min @3 U/h + 30 min @1 U/h = 2 U */
    op_de_report_t r;
    op_de_report(&de, &r);
    CHECK_EQ(r.scheduled_mu, 2000);
    CHECK_EQ(de.ms_of_day, 30 * 60000u);
}

TEST(de_schedule_validation)
{
    op_basal_schedule_t s = flat(1000);
    CHECK_EQ(op_de_validate_schedule(&s), OP_OK);
    s.count = 0;
    CHECK_EQ(op_de_validate_schedule(&s), OP_ERR_BAD_ARG);
    s = flat(1000);
    s.seg[0].start_slot = 1; /* must start at 0 */
    CHECK_EQ(op_de_validate_schedule(&s), OP_ERR_BAD_ARG);
    s = flat(1000);
    s.count = 2;
    s.seg[1] = (op_basal_seg_t){0, 5}; /* not ascending */
    CHECK_EQ(op_de_validate_schedule(&s), OP_ERR_BAD_ARG);
    s.seg[1].start_slot = 48; /* out of range */
    CHECK_EQ(op_de_validate_schedule(&s), OP_ERR_BAD_ARG);
    op_basal_schedule_t big = {0};
    big.count = 25;
    CHECK_EQ(op_de_validate_schedule(&big), OP_ERR_BAD_ARG);
    CHECK_EQ(op_de_validate_schedule(NULL), OP_ERR_BAD_ARG);
    op_de_t de;
    op_de_init(&de);
    s.count = 0;
    CHECK_EQ(op_de_set_schedule(&de, &s), OP_ERR_BAD_ARG);
    CHECK(!de.has_schedule);
}

TEST(de_temp_basal_overrides_then_returns_to_basal)
{
    op_de_t de;
    setup(&de, 1000);
    CHECK_EQ(op_de_start_temp_basal(&de, 2000, 30), OP_OK);
    CHECK_EQ(op_de_current_rate_mu_h(&de), 2000);
    CHECK_EQ(op_de_temp_remaining_min(&de), 30);
    run(&de, 30 * 60000u); /* 1000 mU */
    CHECK(!de.temp_active);
    CHECK(op_de_take_events(&de) & OP_DE_EV_TEMP_DONE);
    CHECK_EQ(op_de_take_events(&de), 0);
    CHECK_EQ(op_de_current_rate_mu_h(&de), 1000);
    op_de_comm_heartbeat(&de);
    run(&de, 30 * 60000u); /* + 500 mU */
    op_de_report_t r;
    op_de_report(&de, &r);
    CHECK_EQ(r.scheduled_mu, 1500);
}

TEST(de_temp_basal_zero_rate_is_allowed)
{
    op_de_t de;
    setup(&de, 1000);
    CHECK_EQ(op_de_start_temp_basal(&de, 0, 60), OP_OK);
    CHECK_EQ(run(&de, 25 * 60000u), 0); /* before the 30 min comm-loss fallback */
}

TEST(de_temp_basal_validation)
{
    op_de_t de;
    setup(&de, 1000);
    CHECK_EQ(op_de_start_temp_basal(&de, 1000, 0), OP_ERR_BAD_ARG);
    CHECK_EQ(op_de_start_temp_basal(&de, 1000, 45), OP_ERR_BAD_ARG);
    CHECK_EQ(op_de_start_temp_basal(&de, 1000, 750), OP_ERR_BAD_ARG);
    CHECK_EQ(op_de_start_temp_basal(&de, 1000, 720), OP_OK);
    op_de_suspend(&de);
    CHECK_EQ(op_de_start_temp_basal(&de, 1000, 30), OP_ERR_SUSPENDED);
}

TEST(de_cancel_temp_basal)
{
    op_de_t de;
    setup(&de, 1000);
    CHECK(!op_de_cancel_temp_basal(&de));
    op_de_start_temp_basal(&de, 3000, 60);
    CHECK(op_de_cancel_temp_basal(&de));
    CHECK_EQ(op_de_current_rate_mu_h(&de), 1000);
    CHECK_EQ(op_de_temp_remaining_min(&de), 0);
}

TEST(de_temp_basal_falls_back_30min_after_comm_loss)
{
    op_de_t de;
    setup(&de, 1000);
    op_de_start_temp_basal(&de, 4000, 120);
    run(&de, 29 * 60000u);
    CHECK(de.temp_active);
    run(&de, 2 * 60000u); /* crosses the 30 min mark */
    CHECK(!de.temp_active);
    CHECK(op_de_take_events(&de) & OP_DE_EV_TEMP_COMM_FALLBACK);
    CHECK_EQ(op_de_current_rate_mu_h(&de), 1000);
    op_de_report_t r;
    op_de_report(&de, &r);
    /* 30 min @4 U/h = 2000 mU, then 1 min @1 U/h = 16.67 mU */
    CHECK_EQ(r.scheduled_mu, 2016);
}

TEST(de_heartbeat_extends_temp_basal)
{
    op_de_t de;
    setup(&de, 1000);
    op_de_start_temp_basal(&de, 4000, 120);
    run(&de, 20 * 60000u);
    op_de_comm_heartbeat(&de);
    run(&de, 29 * 60000u);
    CHECK(de.temp_active);
    CHECK_EQ(op_de_take_events(&de) & OP_DE_EV_TEMP_COMM_FALLBACK, 0);
}

TEST(de_bolus_runs_at_1_5_u_per_min)
{
    op_de_t de;
    setup(&de, 0);
    CHECK_EQ(op_de_start_bolus(&de, 1000), OP_OK);
    CHECK_EQ(op_de_bolus_remaining_mu(&de), 1000);
    uint32_t steps = run(&de, 10000); /* 10 s = 250 mU = 19.08 steps */
    CHECK_EQ(steps, 19);
    CHECK_EQ(op_de_bolus_remaining_mu(&de), 750);
    steps += run(&de, 30000);
    CHECK_EQ(steps, 76); /* 1000 mU = 76.34 steps */
    CHECK(!de.bolus_active);
    CHECK(op_de_take_events(&de) & OP_DE_EV_BOLUS_DONE);
}

TEST(de_bolus_pauses_basal_without_catch_up)
{
    op_de_t de;
    setup(&de, 5000);
    op_de_start_bolus(&de, 1000);
    uint32_t during = run(&de, 40000); /* bolus only: 76.34 steps */
    CHECK_EQ(during, 76);
    op_de_report_t r;
    op_de_report(&de, &r);
    CHECK_EQ(r.scheduled_mu, 1000); /* basal not scheduled while bolus ran */
}

TEST(de_bolus_validation)
{
    op_de_t de;
    setup(&de, 0);
    CHECK_EQ(op_de_start_bolus(&de, 0), OP_ERR_BAD_ARG);
    CHECK_EQ(op_de_start_bolus(&de, 500), OP_OK);
    CHECK_EQ(op_de_start_bolus(&de, 500), OP_ERR_BUSY);
    op_de_suspend(&de);
    CHECK_EQ(op_de_start_bolus(&de, 500), OP_ERR_SUSPENDED);
}

TEST(de_cancel_bolus_reports_undelivered)
{
    op_de_t de;
    setup(&de, 0);
    CHECK_EQ(op_de_cancel_bolus(&de), 0);
    op_de_start_bolus(&de, 1000);
    run(&de, 10000);
    CHECK_EQ(op_de_cancel_bolus(&de), 750);
    CHECK(!de.bolus_active);
    CHECK_EQ(run(&de, 60000), 0);
}

TEST(de_many_small_boluses_do_not_lose_fractions)
{
    op_de_t de;
    setup(&de, 0);
    uint32_t total = 0;
    for (int i = 0; i < 100; i++) {
        CHECK_EQ(op_de_start_bolus(&de, 50), OP_OK); /* 3.82 steps each */
        total += run(&de, 5000);
        CHECK(!de.bolus_active);
    }
    CHECK_EQ(total, 381); /* floor(5000 / 13.1) */
}

TEST(de_suspend_cancels_bolus_and_temp_and_shows_deficit)
{
    op_de_t de;
    setup(&de, 1000);
    op_de_start_temp_basal(&de, 2000, 120);
    op_de_start_bolus(&de, 5000);
    op_de_suspend(&de);
    CHECK(!de.bolus_active);
    CHECK(!de.temp_active);
    CHECK_EQ(run(&de, 30 * 60000u), 0);
    op_de_comm_heartbeat(&de);
    CHECK_EQ(op_de_resume(&de), OP_OK);
    run(&de, 30 * 60000u);
    op_de_report_t r;
    op_de_report(&de, &r);
    CHECK_EQ(r.scheduled_mu, 1000); /* 2 x 30 min @ 1 U/h */
    CHECK(r.delivered_mu < 520);     /* only the resumed half-hour */
    CHECK(r.delivered_mu > 480);
}

TEST(de_commit_tracks_dropped_steps)
{
    op_de_t de;
    setup(&de, 5000);
    uint32_t n = op_de_tick(&de, 60000);
    CHECK(n > 0);
    op_de_commit(&de, 0); /* supervisor vetoed everything */
    op_de_report_t r;
    op_de_report(&de, &r);
    CHECK_EQ(r.delivered_steps, 0);
    CHECK_EQ(r.dropped_steps, n);
    uint32_t m = op_de_tick(&de, 60000);
    op_de_commit(&de, m + 99); /* over-commit is clamped */
    op_de_report(&de, &r);
    CHECK_EQ(r.delivered_steps, m);
}

TEST(de_uncommitted_pending_accumulates)
{
    op_de_t de;
    setup(&de, 5000);
    uint32_t a = op_de_tick(&de, 60000);
    uint32_t b = op_de_tick(&de, 60000);
    CHECK_EQ(de.pending_steps, a + b);
    op_de_commit(&de, a + b);
    CHECK_EQ(de.pending_steps, 0);
}

TEST(de_events_for_bolus_done_not_reported_twice)
{
    op_de_t de;
    setup(&de, 0);
    op_de_start_bolus(&de, 100);
    run(&de, 10000);
    CHECK(op_de_take_events(&de) & OP_DE_EV_BOLUS_DONE);
    CHECK_EQ(op_de_take_events(&de), 0);
}

TEST(de_no_schedule_means_zero_rate)
{
    op_de_t de;
    op_de_init(&de);
    op_de_resume(&de);
    CHECK_EQ(op_de_current_rate_mu_h(&de), 0);
    CHECK_EQ(run(&de, H), 0);
}

TEST(de_time_of_day_is_normalised)
{
    op_de_t de;
    op_de_init(&de);
    op_de_set_time_of_day(&de, OP_DAY_MS + 5);
    CHECK_EQ(de.ms_of_day, 5);
}
