/*
 * Bench test mode: gravimetric test sequences for the WATER tests in docs/02-safety.md section 3.
 * TEST ONLY - NOT FOR HUMAN USE. Water only, never insulin, never on a body.
 *
 * A sequence is N bolus pulses of X mU separated by a configurable pause. Every pulse goes through
 * the normal path (op_pump_bolus -> delivery engine -> safety supervisor): all limits, the dock
 * precondition, faults, the encoder check and the occlusion detector stay active. The bench layer
 * only starts pulses and measures; it cannot bypass anything. A pulse the supervisor refuses
 * because of the rolling-hour cap (OP_ERR_HOURLY) is retried until the window has room (documented:
 * large gravimetric totals are throttled to 15 U/h). A pulse is also held back while the current
 * wall minute is so full (e.g. right after priming) that the 1.7 U/min backstop could latch a
 * fault. Every other refusal ends the sequence.
 *
 * Each finished pulse produces one op_bench_rec_t for the platform sink (UART/RTT CSV) and one
 * OP_EV_BENCH_PULSE event in the event log.
 */
#ifndef OP_BENCH_TEST_H
#define OP_BENCH_TEST_H

#include "op/pump_controller.h"

#define OP_BENCH_MAX_PULSES 1000u
#define OP_BENCH_MAX_PAUSE_MS 3600000u

typedef enum {
    OP_BENCH_IDLE = 0,
    OP_BENCH_PULSING = 1,      /* a bolus pulse is running */
    OP_BENCH_PAUSING = 2,      /* waiting out the pause between pulses */
    OP_BENCH_WAIT_RATE = 3,    /* waiting for room in the supervisor's per-minute / rolling-hour window */
    OP_BENCH_DONE = 4,
    OP_BENCH_ABORTED = 5       /* operator stop, or the supervisor/pump refused or faulted */
} op_bench_state_t;

enum { /* OP_EV_BENCH_END.b and op_bench_t.end_reason */
    OP_BENCH_END_DONE = 0,
    OP_BENCH_END_ABORTED = 1,  /* operator stop */
    OP_BENCH_END_FAULT = 2,    /* a fault latched during a pulse */
    OP_BENCH_END_REFUSED = 3   /* the pump refused to start a pulse (undocked, suspended, ...) */
};

enum { /* op_bench_rec_t.result */
    OP_BENCH_PULSE_OK = 0,
    OP_BENCH_PULSE_SHORT = 1,  /* bolus ended before all steps ran (cancelled, undocked) */
    OP_BENCH_PULSE_FAULT = 2
};

typedef struct {
    uint32_t pulses;
    uint32_t amount_mu;   /* per pulse, multiple of OP_BOLUS_GRANULARITY_MU */
    uint32_t pause_ms;    /* from the end of a pulse to the start of the next */
} op_bench_cfg_t;

typedef struct {
    uint32_t pulse;           /* 1-based */
    uint32_t cmd_mu;
    uint64_t t_start_ms;      /* since boot (hal time) */
    uint64_t t_end_ms;
    uint32_t steps;           /* motor steps delivered in this pulse */
    uint32_t total_steps;     /* since the sequence started */
    uint32_t expected_steps;  /* what cmd_mu converts to with the drive calibration */
    int32_t enc_substeps;     /* spindle travel in 1/16 steps (encoder, as sampled by the supervisor) */
    uint16_t peak_ma;         /* highest motor current in the pulse, 0 = no current sense / no sample */
    uint32_t bursts;          /* motor bursts with a current sample */
    uint16_t faults;          /* supervisor fault bits at the end of the pulse */
    uint8_t result;           /* OP_BENCH_PULSE_* */
} op_bench_rec_t;

typedef void (*op_bench_sink_t)(void *ctx, const op_bench_rec_t *rec);

typedef struct {
    op_bench_state_t state;
    op_bench_cfg_t cfg;
    op_bench_sink_t sink;
    void *sink_ctx;
    uint32_t pulse;            /* index of the running / last started pulse (1-based) */
    uint32_t completed;        /* pulses that finished with OP_BENCH_PULSE_OK */
    uint8_t end_reason;        /* valid in DONE / ABORTED */
    uint64_t pause_until_ms;
    /* snapshot at pulse start */
    uint64_t t_start_ms;
    uint32_t steps0;
    uint32_t seq_steps0;
    int32_t enc0;
} op_bench_t;

void op_bench_init(op_bench_t *b, op_bench_sink_t sink, void *sink_ctx);
/* Validate (pulses 1..1000, amount > 0 on the 0.05 U grid and within the supervisor's bolus limit,
 * pause <= 1 h) and start pulse 1 immediately. OP_ERR_BUSY while a sequence runs. Errors of the
 * first op_pump_bolus() (not active, suspended, undocked, fault, reservoir) are returned and nothing starts. */
op_err_t op_bench_start(op_bench_t *b, op_pump_t *p, const op_bench_cfg_t *cfg);
/* Operator stop: cancels a running bolus, logs the end. No-op unless a sequence runs. */
void op_bench_abort(op_bench_t *b, op_pump_t *p);
/* Call after every op_pump_tick(). */
void op_bench_tick(op_bench_t *b, op_pump_t *p);
static inline bool op_bench_running(const op_bench_t *b)
{
    return b->state == OP_BENCH_PULSING || b->state == OP_BENCH_PAUSING || b->state == OP_BENCH_WAIT_RATE;
}

/*
 * Bench convenience: pair (if needed), fill, activate with a flat zero basal schedule, optionally
 * prime, resume. Uses only the public pump API (same checks as the protocol commands); needs the
 * pod docked and fault free. prime_steps <= the prime limit (about 20 steps on the 5:1 drive).
 */
op_err_t op_bench_prepare(op_pump_t *p, uint32_t fill_mu, uint32_t prime_steps);

#endif
