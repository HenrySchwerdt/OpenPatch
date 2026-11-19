#include "mock_hal.h"
#include "op/bench_test.h"
#include "cal_fixture.h"
#include "op_test.h"

#define MAX_RECS 64

typedef struct {
    mock_hal_t hal;
    op_hal_t ops;
    op_pump_t pump;
    op_bench_t bench;
    op_bench_rec_t recs[MAX_RECS];
    int nrecs;
} rig_t;

static void sink(void *ctx, const op_bench_rec_t *r)
{
    rig_t *g = ctx;
    if (g->nrecs < MAX_RECS) g->recs[g->nrecs++] = *r;
}

static void rig_init(rig_t *g, bool current_sense)
{
    memset(g, 0, sizeof *g);
    mock_hal_init(&g->hal);
    g->hal.has_stats = current_sense;
    g->hal.peak_ma = 80;
    g->hal.mean_ma = 50;
    g->ops = mock_hal_make(&g->hal);
    op_pump_init(&g->pump, &g->ops, test_cal_5_1(), OP_CAPACITY_200_MU, 1);
    op_bench_init(&g->bench, sink, g);
}

static void rig_ready(rig_t *g, bool current_sense)
{
    rig_init(g, current_sense);
    CHECK_EQ(op_bench_prepare(&g->pump, 100000, 10), OP_OK);
}

static void second(rig_t *g)
{
    g->hal.now_ms += 1000;
    op_pump_tick(&g->pump);
    op_bench_tick(&g->bench, &g->pump);
}

/* let the wall minute of the prime pass, so the first pulse starts at once */
static void settle(rig_t *g)
{
    for (int i = 0; i < 61; i++) second(g);
}

static void run_until_idle(rig_t *g, int max_s)
{
    for (int i = 0; i < max_s && op_bench_running(&g->bench); i++) second(g);
}

static bool log_has(const rig_t *g, uint8_t type)
{
    op_event_t e[OP_LOG_CAPACITY];
    uint32_t n = op_log_read(&g->pump.log, 0, e, OP_LOG_CAPACITY);
    for (uint32_t i = 0; i < n; i++)
        if (e[i].type == type) return true;
    return false;
}

TEST(bench_start_validates_arguments)
{
    rig_t g;
    rig_ready(&g, false);
    op_bench_cfg_t c = {3, 500, 1000};
    c.pulses = 0;
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_ERR_BAD_ARG);
    c.pulses = OP_BENCH_MAX_PULSES + 1;
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_ERR_BAD_ARG);
    c = (op_bench_cfg_t){3, 25, 1000}; /* off the 0.05 U grid */
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_ERR_BAD_ARG);
    c = (op_bench_cfg_t){3, 0, 1000};
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_ERR_BAD_ARG);
    c = (op_bench_cfg_t){3, 500, OP_BENCH_MAX_PAUSE_MS + 1};
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_ERR_BAD_ARG);
    c = (op_bench_cfg_t){3, 10050, 1000}; /* above the supervisor's max bolus */
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_ERR_LIMIT);
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, NULL), OP_ERR_BAD_ARG);
    CHECK_EQ(g.bench.state, OP_BENCH_IDLE);
    CHECK(!g.pump.de.bolus_active);
}

TEST(bench_runs_n_pulses_with_pause_and_reports_each)
{
    rig_t g;
    rig_ready(&g, true);
    settle(&g);
    op_bench_cfg_t c = {3, 500, 5000};
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_OK);
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_ERR_BUSY);
    run_until_idle(&g, 600);
    CHECK_EQ(g.bench.state, OP_BENCH_DONE);
    CHECK_EQ(g.bench.end_reason, OP_BENCH_END_DONE);
    CHECK_EQ(g.bench.completed, 3);
    CHECK_EQ(g.nrecs, 3);
    uint32_t expect = op_mu_to_steps(TEST_UU, 500); /* 19 */
    for (int i = 0; i < 3; i++) {
        const op_bench_rec_t *r = &g.recs[i];
        CHECK_EQ(r->pulse, i + 1);
        CHECK_EQ(r->cmd_mu, 500);
        CHECK_EQ(r->result, OP_BENCH_PULSE_OK);
        CHECK(r->steps + 1 >= expect && r->steps <= expect + 1);
        CHECK_EQ(r->expected_steps, expect);
        CHECK(r->enc_substeps >= (int32_t)(r->steps * 16) - 32 && r->enc_substeps <= (int32_t)(r->steps * 16) + 32);
        CHECK_EQ(r->peak_ma, 80);
        CHECK(r->bursts > 0);
        CHECK(r->t_end_ms > r->t_start_ms);
        CHECK_EQ(r->faults, 0);
        if (i > 0) CHECK(r->t_start_ms >= g.recs[i - 1].t_end_ms + 5000);
    }
    CHECK_EQ(g.recs[2].total_steps, g.recs[0].steps + g.recs[1].steps + g.recs[2].steps);
    CHECK(log_has(&g, OP_EV_BENCH_START));
    CHECK(log_has(&g, OP_EV_BENCH_PULSE));
    CHECK(log_has(&g, OP_EV_BENCH_END));
}

TEST(bench_without_current_sense_reports_zero_peak)
{
    rig_t g;
    rig_ready(&g, false);
    op_bench_cfg_t c = {1, 500, 0};
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_OK);
    run_until_idle(&g, 200);
    CHECK_EQ(g.bench.state, OP_BENCH_DONE);
    CHECK_EQ(g.recs[0].peak_ma, 0);
    CHECK_EQ(g.recs[0].bursts, 0);
}

TEST(bench_refuses_to_start_when_pod_is_not_active)
{
    rig_t g;
    rig_init(&g, false);
    op_bench_cfg_t c = {1, 500, 0};
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_ERR_RELEASED);
    CHECK_EQ(g.bench.state, OP_BENCH_IDLE);
}

TEST(bench_prepare_respects_the_normal_preconditions)
{
    rig_t g;
    rig_init(&g, false);
    g.hal.docked = false;
    CHECK_EQ(op_bench_prepare(&g.pump, 100000, 0), OP_ERR_NOT_DOCKED);
    g.hal.docked = true;
    g.hal.charger = true;
    CHECK_EQ(op_bench_prepare(&g.pump, 100000, 0), OP_ERR_CHARGING);
    g.hal.charger = false;
    CHECK_EQ(op_bench_prepare(&g.pump, 100000, 21), OP_ERR_LIMIT); /* above the 0.52 U prime limit */
    rig_t h;
    rig_init(&h, false);
    CHECK_EQ(op_bench_prepare(&h.pump, 100000, 20), OP_OK);
    CHECK(h.pump.pod.active);
    CHECK(!h.pump.de.suspended);
    CHECK_EQ(h.pump.res.fill_mu, 100000);
}

TEST(bench_abort_cancels_the_running_pulse_and_reports_it)
{
    rig_t g;
    rig_ready(&g, true);
    settle(&g);
    op_bench_cfg_t c = {5, 1000, 0};
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_OK);
    for (int i = 0; i < 10; i++) second(&g);
    op_bench_abort(&g.bench, &g.pump);
    CHECK_EQ(g.bench.state, OP_BENCH_ABORTED);
    CHECK_EQ(g.bench.end_reason, OP_BENCH_END_ABORTED);
    CHECK(!g.pump.de.bolus_active);
    CHECK_EQ(g.nrecs, 1);
    CHECK_EQ(g.recs[0].result, OP_BENCH_PULSE_SHORT);
    CHECK(g.recs[0].steps > 0 && g.recs[0].steps < g.recs[0].expected_steps);
    uint32_t steps = g.pump.de.delivered_steps;
    for (int i = 0; i < 20; i++) second(&g);
    CHECK_EQ(g.pump.de.delivered_steps, steps); /* nothing more is delivered */
    op_bench_abort(&g.bench, &g.pump);            /* second abort is a no-op */
    CHECK_EQ(g.nrecs, 1);
}

TEST(bench_supervisor_fault_ends_the_sequence)
{
    rig_t g;
    rig_ready(&g, true);
    settle(&g);
    g.hal.delivered_pct = 0; /* blocked line: the spindle does not move */
    op_bench_cfg_t c = {5, 2000, 0};
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_OK);
    run_until_idle(&g, 300);
    CHECK_EQ(g.bench.state, OP_BENCH_ABORTED);
    CHECK_EQ(g.bench.end_reason, OP_BENCH_END_FAULT);
    CHECK_EQ(g.nrecs, 1);
    CHECK_EQ(g.recs[0].result, OP_BENCH_PULSE_FAULT);
    CHECK(g.recs[0].faults & OP_FAULT_OCCLUSION);
    CHECK(op_sv_faults(&g.pump.sv) & OP_FAULT_OCCLUSION);
    CHECK_EQ(g.hal.buzzer, OP_BUZZER_ALARM); /* the normal fault handling ran */
}

TEST(bench_undock_ends_the_sequence)
{
    rig_t g;
    rig_ready(&g, false);
    settle(&g);
    op_bench_cfg_t c = {5, 1000, 0};
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_OK);
    for (int i = 0; i < 5; i++) second(&g);
    g.hal.docked = false;
    run_until_idle(&g, 50);
    CHECK_EQ(g.bench.state, OP_BENCH_ABORTED);
    CHECK_EQ(g.bench.end_reason, OP_BENCH_END_REFUSED);
    CHECK_EQ(g.recs[0].result, OP_BENCH_PULSE_SHORT);
}

TEST(bench_rolling_hour_cap_throttles_but_does_not_fail)
{
    rig_t g;
    rig_ready(&g, false);
    op_bench_cfg_t c = {16, 1000, 0}; /* 16 U > 15 U per rolling hour */
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_OK);
    bool waited = false;
    for (int i = 0; i < 6 * 3600 && op_bench_running(&g.bench); i++) {
        second(&g);
        if (g.bench.state == OP_BENCH_WAIT_RATE) waited = true;
    }
    CHECK(waited);
    CHECK_EQ(g.bench.state, OP_BENCH_DONE);
    CHECK_EQ(g.nrecs, 16);
    CHECK_EQ(op_sv_faults(&g.pump.sv), 0); /* the cap was respected, never tripped as a fault */
    CHECK(g.recs[15].t_start_ms > 3600000ull / 2); /* the last pulse had to wait for the window */
}

TEST(bench_waits_for_the_minute_window_after_priming)
{
    rig_t g;
    rig_ready(&g, false); /* 10 prime steps were approved in wall minute 0 */
    op_bench_cfg_t c = {1, 3000, 0};
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_OK);
    CHECK_EQ(g.bench.state, OP_BENCH_WAIT_RATE); /* a 1.5 U/min bolus would exceed 1.7 U/min in this minute */
    CHECK(!g.pump.de.bolus_active);
    run_until_idle(&g, 600);
    CHECK_EQ(g.bench.state, OP_BENCH_DONE);
    CHECK_EQ(op_sv_faults(&g.pump.sv), 0);
    CHECK(g.recs[0].t_start_ms >= 60000);
}

TEST(bench_start_still_reports_real_refusals_while_the_window_is_busy)
{
    rig_t g;
    rig_ready(&g, false);
    g.hal.docked = false;
    second(&g); /* tick samples the dock input */
    op_bench_cfg_t c = {1, 3000, 0};
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_ERR_NOT_DOCKED);
    CHECK_EQ(g.bench.state, OP_BENCH_IDLE);
}

TEST(bench_can_run_again_after_done)
{
    rig_t g;
    rig_ready(&g, false);
    op_bench_cfg_t c = {1, 500, 0};
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_OK);
    run_until_idle(&g, 200);
    CHECK_EQ(g.bench.state, OP_BENCH_DONE);
    CHECK_EQ(op_bench_start(&g.bench, &g.pump, &c), OP_OK);
    run_until_idle(&g, 200);
    CHECK_EQ(g.nrecs, 2);
    CHECK_EQ(g.recs[1].pulse, 1);
    CHECK_EQ(g.bench.completed, 1);
}

/* ---- pump-level: occlusion detector and battery-less boards ---------------------------- */

TEST(pump_occlusion_detector_trips_before_the_two_unit_supervisor_check)
{
    rig_t g;
    rig_ready(&g, true);
    settle(&g);
    g.hal.delivered_pct = 10;
    g.hal.peak_ma = 220;
    g.hal.mean_ma = 160;
    CHECK_EQ(op_pump_bolus(&g.pump, 5000), OP_OK);
    int s = 0;
    while (!(op_sv_faults(&g.pump.sv) & OP_FAULT_OCCLUSION) && s < 300) {
        second(&g);
        s++;
    }
    CHECK(op_sv_faults(&g.pump.sv) & OP_FAULT_OCCLUSION);
    CHECK(g.pump.de.suspended);
    CHECK(g.pump.occ.occluded);
    CHECK(g.pump.de.delivered_steps < op_mu_to_steps(TEST_UU, 1000)); /* well below the 2 U supervisor limit */
    CHECK_EQ(g.hal.buzzer, OP_BUZZER_ALARM);
}

TEST(pump_occlusion_detector_is_off_without_current_sense)
{
    rig_t g;
    rig_ready(&g, false);
    CHECK(!g.pump.occ.enabled);
    CHECK_EQ(g.pump.mot_bursts, 0);
}

TEST(pump_occlusion_ack_resets_the_detector)
{
    rig_t g;
    rig_ready(&g, true);
    settle(&g);
    g.hal.delivered_pct = 0;
    CHECK_EQ(op_pump_bolus(&g.pump, 5000), OP_OK);
    for (int i = 0; i < 60 && !g.pump.occ.occluded; i++) second(&g);
    CHECK(g.pump.occ.occluded);
    g.hal.delivered_pct = 100;
    CHECK_EQ(op_pump_acknowledge(&g.pump, OP_FAULT_OCCLUSION | OP_FAULT_ENCODER_DEVIATION), OP_OK);
    CHECK(!g.pump.occ.occluded);
    CHECK_EQ(g.pump.occ.strikes, 0);
}

TEST(pump_healthy_delivery_with_current_sense_never_trips)
{
    rig_t g;
    rig_ready(&g, true);
    settle(&g);
    CHECK_EQ(op_pump_bolus(&g.pump, 3000), OP_OK);
    for (int i = 0; i < 200; i++) second(&g);
    CHECK_EQ(op_sv_faults(&g.pump.sv), 0);
    CHECK(g.pump.occ.windows > 0);
    uint32_t b;
    CHECK_EQ(op_pump_take_motor_peak(&g.pump, &b), 80);
    CHECK(b > 0);
    CHECK_EQ(op_pump_take_motor_peak(&g.pump, &b), 0); /* cleared */
}

TEST(pump_without_battery_hook_never_raises_battery_faults)
{
    mock_hal_t m;
    mock_hal_init(&m);
    m.battery_mv = 100; /* would be critical if it were read */
    op_hal_t ops = mock_hal_make_no_battery(&m);
    op_pump_t p;
    op_pump_init(&p, &ops, test_cal_5_1(), OP_CAPACITY_200_MU, 1);
    CHECK_EQ(op_sv_faults(&p.sv), 0);
    CHECK_EQ(op_pump_fill(&p, 100000), OP_OK);
    CHECK_EQ(test_activate(&p, 1000), OP_OK);
    CHECK_EQ(op_pump_resume(&p), OP_OK);
    for (int i = 0; i < 3600; i++) {
        m.now_ms += 1000;
        op_pump_tick(&p);
    }
    CHECK_EQ(op_sv_faults(&p.sv), 0);
    CHECK(!op_sv_battery_low(&p.sv));
    op_status_t st;
    op_pump_get_status(&p, &st);
    CHECK_EQ(st.battery_mv, OP_BATTERY_NONE_MV);
    CHECK_EQ(st.flags & OP_ST_LOW_BATTERY, 0);
    CHECK(st.delivered_mu > 0);
}
