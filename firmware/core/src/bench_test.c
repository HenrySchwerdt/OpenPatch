#include "op/bench_test.h"

#include <string.h>

#define BENCH_PAIR_ID 0xBE0C0001u /* bench pods pair with themselves; water tests only */
#define BENCH_ACTIVATION_ID 1u

static uint64_t now_ms(const op_pump_t *p) { return p->hal->time_ms(p->hal->ctx); }

static void log_bench(op_pump_t *p, uint8_t type, int32_t a, int32_t b)
{
    op_log_append(&p->log, (uint32_t)(now_ms(p) / 1000u), type, a, b);
}

void op_bench_init(op_bench_t *b, op_bench_sink_t sink, void *sink_ctx)
{
    memset(b, 0, sizeof *b);
    b->sink = sink;
    b->sink_ctx = sink_ctx;
}

static void finish(op_bench_t *b, op_pump_t *p, op_bench_state_t st, uint8_t reason)
{
    b->state = st;
    b->end_reason = reason;
    log_bench(p, OP_EV_BENCH_END, (int32_t)b->completed, reason);
}

/*
 * True if the supervisor's windows have too little room for another pulse:
 *  - the current wall minute could not take a bolus at 1.5 U/min (typically right after priming),
 *  - the rolling hour could not take the pulse plus the fractional-step carry (2 steps margin: the
 *    supervisor's start check is exact, the engine may emit one step more or less per pulse).
 */
static bool window_busy(op_pump_t *p, uint32_t amount_mu)
{
    uint32_t hour_used = op_sv_hourly_steps(&p->sv, now_ms(p)); /* also rolls the window to "now" */
    uint32_t minute_used = p->sv.minute_steps[p->sv.last_minute % 60u];
    uint32_t minute_need = op_mu_to_steps(p->sv.uu_per_step, OP_BOLUS_RATE_MU_H / 60u) + 1u;
    uint32_t hour_cap = op_mu_to_steps(p->sv.uu_per_step, OP_MAX_HOURLY_MU);
    uint32_t pulse = op_mu_to_steps(p->sv.uu_per_step, amount_mu);
    return minute_used + minute_need > p->sv.max_steps_per_min || hour_used + pulse + 2u > hour_cap;
}

/* Try to start the next pulse. Returns OP_OK when it runs, OP_ERR_HOURLY to "retry later". */
static op_err_t start_pulse(op_bench_t *b, op_pump_t *p)
{
    if (window_busy(p, b->cfg.amount_mu)) {
        /* report real refusals now; only a pure rate-window wait is retried */
        op_err_t c = op_sv_check_bolus(&p->sv, now_ms(p), b->cfg.amount_mu, op_res_remaining_mu(&p->res));
        return c == OP_OK ? OP_ERR_HOURLY : c;
    }
    op_err_t e = op_pump_bolus(p, b->cfg.amount_mu);
    if (e != OP_OK) return e;
    b->pulse++;
    b->state = OP_BENCH_PULSING;
    b->t_start_ms = now_ms(p);
    b->steps0 = p->de.delivered_steps;
    b->enc0 = p->sv.last_enc;
    (void)op_pump_take_motor_peak(p, NULL); /* peak and bursts are per pulse */
    return OP_OK;
}

op_err_t op_bench_start(op_bench_t *b, op_pump_t *p, const op_bench_cfg_t *cfg)
{
    if (op_bench_running(b)) return OP_ERR_BUSY;
    if (!cfg || cfg->pulses == 0 || cfg->pulses > OP_BENCH_MAX_PULSES || cfg->pause_ms > OP_BENCH_MAX_PAUSE_MS)
        return OP_ERR_BAD_ARG;
    if (cfg->amount_mu == 0 || cfg->amount_mu % OP_BOLUS_GRANULARITY_MU != 0) return OP_ERR_BAD_ARG;
    if (cfg->amount_mu > p->sv.max_bolus_mu) return OP_ERR_LIMIT;

    op_bench_sink_t sink = b->sink;
    void *ctx = b->sink_ctx;
    op_bench_init(b, sink, ctx);
    b->cfg = *cfg;
    b->seq_steps0 = p->de.delivered_steps;
    op_err_t e = start_pulse(b, p);
    if (e == OP_ERR_HOURLY) {
        b->state = OP_BENCH_WAIT_RATE; /* accepted; pulse 1 starts when the window has room */
    } else if (e != OP_OK) {
        b->state = OP_BENCH_IDLE;
        return e;
    }
    log_bench(p, OP_EV_BENCH_START, (int32_t)cfg->pulses, (int32_t)cfg->amount_mu);
    return OP_OK;
}

void op_bench_abort(op_bench_t *b, op_pump_t *p)
{
    if (!op_bench_running(b)) return;
    if (b->state == OP_BENCH_PULSING) {
        (void)op_pump_cancel_bolus(p);
        /* the partial pulse is reported like any other */
        op_bench_rec_t r;
        memset(&r, 0, sizeof r);
        r.pulse = b->pulse;
        r.cmd_mu = b->cfg.amount_mu;
        r.t_start_ms = b->t_start_ms;
        r.t_end_ms = now_ms(p);
        r.steps = p->de.delivered_steps - b->steps0;
        r.total_steps = p->de.delivered_steps - b->seq_steps0;
        r.expected_steps = op_mu_to_steps(p->sv.uu_per_step, b->cfg.amount_mu);
        r.enc_substeps = p->sv.last_enc - b->enc0;
        r.peak_ma = op_pump_take_motor_peak(p, &r.bursts);
        r.faults = op_sv_faults(&p->sv);
        r.result = OP_BENCH_PULSE_SHORT;
        log_bench(p, OP_EV_BENCH_PULSE, (int32_t)r.pulse, (int32_t)r.steps);
        if (b->sink) b->sink(b->sink_ctx, &r);
    }
    finish(b, p, OP_BENCH_ABORTED, OP_BENCH_END_ABORTED);
}

static void pulse_ended(op_bench_t *b, op_pump_t *p)
{
    op_bench_rec_t r;
    memset(&r, 0, sizeof r);
    r.pulse = b->pulse;
    r.cmd_mu = b->cfg.amount_mu;
    r.t_start_ms = b->t_start_ms;
    r.t_end_ms = now_ms(p);
    r.steps = p->de.delivered_steps - b->steps0;
    r.total_steps = p->de.delivered_steps - b->seq_steps0;
    r.expected_steps = op_mu_to_steps(p->sv.uu_per_step, b->cfg.amount_mu);
    r.enc_substeps = p->sv.last_enc - b->enc0;
    r.peak_ma = op_pump_take_motor_peak(p, &r.bursts);
    r.faults = op_sv_faults(&p->sv);
    if (r.faults) r.result = OP_BENCH_PULSE_FAULT;
    else r.result = (r.steps + 1u >= r.expected_steps) ? OP_BENCH_PULSE_OK : OP_BENCH_PULSE_SHORT;
    if (r.result == OP_BENCH_PULSE_OK) b->completed++;
    log_bench(p, OP_EV_BENCH_PULSE, (int32_t)r.pulse, (int32_t)r.steps);
    if (b->sink) b->sink(b->sink_ctx, &r);

    if (r.result == OP_BENCH_PULSE_FAULT) {
        finish(b, p, OP_BENCH_ABORTED, OP_BENCH_END_FAULT);
    } else if (r.result == OP_BENCH_PULSE_SHORT) {
        finish(b, p, OP_BENCH_ABORTED, OP_BENCH_END_REFUSED); /* cancelled / undocked: do not guess, stop */
    } else if (b->pulse >= b->cfg.pulses) {
        finish(b, p, OP_BENCH_DONE, OP_BENCH_END_DONE);
    } else {
        b->state = OP_BENCH_PAUSING;
        b->pause_until_ms = r.t_end_ms + b->cfg.pause_ms;
    }
}

static void try_next(op_bench_t *b, op_pump_t *p)
{
    op_err_t e = start_pulse(b, p);
    if (e == OP_OK) return;
    if (e == OP_ERR_HOURLY) {
        b->state = OP_BENCH_WAIT_RATE;
        return;
    }
    finish(b, p, OP_BENCH_ABORTED, p->sv.faults ? OP_BENCH_END_FAULT : OP_BENCH_END_REFUSED);
}

void op_bench_tick(op_bench_t *b, op_pump_t *p)
{
    switch (b->state) {
    case OP_BENCH_PULSING:
        if (!p->de.bolus_active) pulse_ended(b, p);
        break;
    case OP_BENCH_PAUSING:
        if (now_ms(p) >= b->pause_until_ms) try_next(b, p);
        break;
    case OP_BENCH_WAIT_RATE:
        try_next(b, p);
        break;
    default: break;
    }
}

op_err_t op_bench_prepare(op_pump_t *p, uint32_t fill_mu, uint32_t prime_steps)
{
    op_err_t e;
    if (!p->de.suspended) {
        e = op_pump_suspend(p);
        if (e != OP_OK) return e;
    }
    if (!p->pod.active) {
        if (p->pod.pair_id == 0) {
            e = op_pump_set_pairing(p, BENCH_PAIR_ID, OP_ROLE_A);
            if (e != OP_OK) return e;
        }
        e = op_pump_fill(p, fill_mu);
        if (e != OP_OK) return e;
        op_activate_args_t a;
        memset(&a, 0, sizeof a);
        a.pair_id = p->pod.pair_id;
        a.activation_id = BENCH_ACTIVATION_ID + p->pod.activation_id;
        a.schedule.count = 1; /* flat 0 U/h: the bench delivers boluses only */
        e = op_pump_activate(p, &a);
        if (e != OP_OK) return e;
    } else {
        e = op_pump_fill(p, fill_mu);
        if (e != OP_OK) return e;
    }
    if (prime_steps) {
        e = op_pump_prime(p, prime_steps);
        if (e != OP_OK) return e;
    }
    return op_pump_resume(p);
}
