/*
 * Delivery engine: turns basal schedule / temp basal / bolus into motor
 * steps on a tick basis. Fixed-point only; fractional steps are accumulated
 * exactly (see OP_SCALED_PER_STEP), so over any period
 * |scheduled - delivered| < 1 step (+ whatever was explicitly dropped).
 *
 * The engine knows NOTHING about safety limits. Every step it requests must
 * be approved by the safety supervisor before it reaches the motor.
 *
 * Semantics (DASH-like):
 *  - starts SUSPENDED; nothing is delivered until op_de_resume().
 *  - basal is paused while a bolus runs (no catch-up), bolus runs at 1.5 U/min.
 *  - suspend cancels bolus and temp basal; resume returns to programmed basal.
 *  - temp basal falls back to the programmed basal OP_COMM_LOSS_TEMP_MS after
 *    the last op_de_comm_heartbeat().
 */
#ifndef OP_DELIVERY_ENGINE_H
#define OP_DELIVERY_ENGINE_H

#include "op/op_types.h"

typedef struct {
    uint8_t start_slot;   /* 0..47, 30-min slot where this segment starts */
    uint32_t rate_mu_h;
} op_basal_seg_t;

/* up to 24 segments; seg[0].start_slot == 0; strictly ascending; a segment
 * ends where the next starts (last one at midnight). */
typedef struct {
    uint8_t count;
    op_basal_seg_t seg[OP_BASAL_SEGMENTS_MAX];
} op_basal_schedule_t;

enum { /* op_de_take_events() bits */
    OP_DE_EV_BOLUS_DONE = 1u << 0,
    OP_DE_EV_TEMP_DONE = 1u << 1,
    OP_DE_EV_TEMP_COMM_FALLBACK = 1u << 2
};

typedef struct {
    op_basal_schedule_t schedule;
    bool has_schedule;
    bool suspended;
    bool temp_active;
    uint32_t temp_rate_mu_h;
    uint32_t temp_remaining_ms;
    bool bolus_active;
    int64_t bolus_remaining_scaled;
    uint32_t ms_of_day;
    uint32_t ms_since_comm;
    int64_t acc;              /* exact fractional-step accumulator */
    int64_t scheduled_scaled; /* what the program asked for */
    uint32_t requested_steps;
    uint32_t delivered_steps;
    uint32_t dropped_steps;   /* vetoed / not executed */
    uint32_t pending_steps;   /* returned by tick, not yet committed */
    uint32_t events;
} op_de_t;

typedef struct {
    uint32_t scheduled_mu;
    uint32_t delivered_mu;
    uint32_t delivered_steps;
    uint32_t dropped_steps;
} op_de_report_t;

void op_de_init(op_de_t *de);
op_err_t op_de_validate_schedule(const op_basal_schedule_t *s);
op_err_t op_de_set_schedule(op_de_t *de, const op_basal_schedule_t *s);
void op_de_set_time_of_day(op_de_t *de, uint32_t ms_of_day);
void op_de_comm_heartbeat(op_de_t *de);

op_err_t op_de_start_temp_basal(op_de_t *de, uint32_t rate_mu_h, uint32_t duration_min);
bool op_de_cancel_temp_basal(op_de_t *de);
op_err_t op_de_start_bolus(op_de_t *de, uint32_t amount_mu);
/* returns the amount (mU) that will NOT be delivered, 0 if none was active */
uint32_t op_de_cancel_bolus(op_de_t *de);
void op_de_suspend(op_de_t *de);
op_err_t op_de_resume(op_de_t *de);

/* Advance by dt_ms; returns steps the engine wants executed now. */
uint32_t op_de_tick(op_de_t *de, uint32_t dt_ms);
/* Report how many of the pending steps were really executed. */
void op_de_commit(op_de_t *de, uint32_t executed);

uint32_t op_de_take_events(op_de_t *de);
uint32_t op_de_current_rate_mu_h(const op_de_t *de);
uint32_t op_de_bolus_remaining_mu(const op_de_t *de);
uint32_t op_de_temp_remaining_min(const op_de_t *de);
void op_de_report(const op_de_t *de, op_de_report_t *out);

#endif
