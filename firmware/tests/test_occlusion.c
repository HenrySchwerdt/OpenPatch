#include "op/occlusion.h"
#include "op_test.h"

static op_occ_t mk(void)
{
    op_occ_cfg_t c;
    op_occ_default_cfg(&c);
    op_occ_t o;
    op_occ_init(&o, &c);
    return o;
}

/* Feed `steps` one at a time. enc_pct = % of the commanded travel the encoder sees. */
static bool feed_steps(op_occ_t *o, int steps, int enc_pct, uint16_t peak, uint16_t mean)
{
    bool hit = false;
    for (int i = 0; i < steps; i++) hit |= op_occ_feed(o, 1, 16 * enc_pct / 100, peak, mean, 10);
    return hit;
}

TEST(occ_disabled_without_cfg)
{
    op_occ_t o;
    op_occ_init(&o, NULL);
    CHECK(!o.enabled);
    CHECK(!op_occ_feed(&o, 100, 0, 500, 500, 10));
    CHECK_EQ(o.windows, 0);
}

TEST(occ_healthy_delivery_learns_baseline_and_never_trips)
{
    op_occ_t o = mk();
    CHECK(!feed_steps(&o, 80, 100, 60, 40));
    CHECK(!o.occluded);
    CHECK_EQ(o.windows, 10);
    CHECK_EQ(o.baseline_ma, 40);
    CHECK_EQ(o.healthy_windows, 10);
    CHECK_EQ(o.strikes, 0);
}

TEST(occ_stall_without_current_data_trips_after_two_windows)
{
    op_occ_t o = mk();
    CHECK(!feed_steps(&o, 8, 0, 0, 0)); /* first strike window */
    CHECK_EQ(o.strikes, 1);
    CHECK(!o.occluded);
    bool hit = false;
    for (int i = 0; i < 8; i++) hit |= op_occ_feed(&o, 1, 0, 0, 0, 0);
    CHECK(hit);
    CHECK(o.occluded);
    CHECK(!op_occ_feed(&o, 8, 0, 0, 0, 0)); /* reported exactly once */
}

TEST(occ_current_rise_with_slip_trips_once_baseline_is_armed)
{
    op_occ_t o = mk();
    CHECK(!feed_steps(&o, 32, 100, 60, 40)); /* 4 healthy windows: baseline 40 mA, armed */
    CHECK(!feed_steps(&o, 8, 50, 90, 70));   /* mean 70 >= 60 (150 %), slip 50 %: strike 1, peak < abs */
    CHECK(feed_steps(&o, 8, 50, 90, 70));    /* strike 2 */
    CHECK(o.occluded);
}

TEST(occ_current_rise_before_baseline_is_not_enough)
{
    op_occ_t o = mk();
    CHECK(!feed_steps(&o, 8, 100, 60, 40)); /* only one healthy window */
    CHECK(!feed_steps(&o, 24, 50, 90, 70)); /* slip 50 % < stall 60 %, peak < abs, baseline not armed */
    CHECK(!o.occluded);
}

TEST(occ_abs_peak_with_slip_trips_without_baseline)
{
    op_occ_t o = mk();
    CHECK(feed_steps(&o, 16, 60, 200, 120)); /* slip 40 % >= 30 %, peak 200 >= 150: two strike windows */
    CHECK(o.occluded);
}

TEST(occ_high_current_without_slip_is_not_an_occlusion)
{
    op_occ_t o = mk();
    CHECK(!feed_steps(&o, 80, 100, 250, 200)); /* heavy load but the spindle follows */
    CHECK(!o.occluded);
    CHECK_EQ(o.healthy_windows, 10);
}

TEST(occ_slip_without_current_evidence_is_not_enough_below_stall_level)
{
    op_occ_t o = mk();
    CHECK(!feed_steps(&o, 40, 50, 60, 40)); /* slip 50 %: above 30 % but current normal and < 60 % stall */
    CHECK(!o.occluded);
}

TEST(occ_strikes_must_be_consecutive)
{
    op_occ_t o = mk();
    for (int i = 0; i < 4; i++) {
        CHECK(!feed_steps(&o, 8, 0, 0, 0));   /* strike */
        CHECK(!feed_steps(&o, 8, 100, 60, 40)); /* healthy window clears the count */
        CHECK_EQ(o.strikes, 0);
    }
    CHECK(!o.occluded);
}

TEST(occ_strike_windows_do_not_move_the_baseline)
{
    op_occ_t o = mk();
    CHECK(!feed_steps(&o, 24, 100, 60, 40));
    uint16_t base = o.baseline_ma;
    CHECK(!feed_steps(&o, 8, 0, 300, 250));
    CHECK_EQ(o.baseline_ma, base);
}

TEST(occ_reset_clears_latch_but_keeps_baseline)
{
    op_occ_t o = mk();
    CHECK(!feed_steps(&o, 24, 100, 60, 40));
    CHECK(feed_steps(&o, 16, 0, 0, 0));
    op_occ_reset(&o);
    CHECK(!o.occluded);
    CHECK_EQ(o.strikes, 0);
    CHECK_EQ(o.win_steps, 0);
    CHECK_EQ(o.baseline_ma, 40);
    CHECK(!feed_steps(&o, 16, 100, 60, 40));
}

TEST(occ_multi_step_bursts_accumulate_into_windows)
{
    op_occ_t o = mk();
    CHECK(!op_occ_feed(&o, 5, 80, 60, 40, 10)); /* 5 steps: window still open */
    CHECK_EQ(o.windows, 0);
    CHECK(!op_occ_feed(&o, 5, 80, 60, 40, 10)); /* 10 steps: closed */
    CHECK_EQ(o.windows, 1);
    CHECK_EQ(o.last_slip_pct, 0);
    CHECK_EQ(o.last_mean_ma, 40);
    CHECK_EQ(o.last_peak_ma, 60);
}

TEST(occ_encoder_ahead_of_command_counts_as_no_slip)
{
    op_occ_t o = mk();
    CHECK(!op_occ_feed(&o, 8, 8 * 16 + 40, 60, 40, 10));
    CHECK_EQ(o.last_slip_pct, 0);
}
