/*
 * Safety supervisor. Deliberately independent of delivery_engine.h /
 * reservoir_model.h: it receives plain numbers and can veto every single
 * step. Faults are latched and need an explicit op_sv_acknowledge().
 *
 * Monitored:
 *  - max bolus / max basal (configurable, clamped to hard caps)
 *  - 15 U rolling 60 min window over ALL approved steps (+ per-minute backstop)
 *  - occlusion: (commanded - encoder-confirmed) > 2 U
 *  - encoder deviation > 10 % over each >= 1 U window (total stall also
 *    raises OCCLUSION: "no travel despite steps")
 *  - reservoir empty, battery critical
 *  - drive calibration present and within the sane range (else no step is ever approved)
 */
#ifndef OP_SAFETY_SUPERVISOR_H
#define OP_SAFETY_SUPERVISOR_H

#include "op/delivery_engine.h" /* only for op_basal_schedule_t validation */
#include "op/op_types.h"

typedef struct {
    uint32_t max_bolus_mu;
    uint32_t max_basal_mu_h;
    uint32_t uu_per_step;        /* validated drive calibration; 0 = missing/invalid -> no delivery */
    uint32_t max_steps_per_min;  /* per-minute backstop derived from the calibration */
    bool calibrated;
    bool docked;                 /* hard precondition for every step (starts false) */
    bool active;                 /* pod is the active pod of its pair (starts false) */
    bool wear_expired;
    uint16_t minute_steps[60];   /* ring: steps approved per wall minute */
    uint64_t last_minute;
    bool clock_started;
    uint16_t faults;             /* latched */
    uint16_t last_new_faults;
    /* encoder tracking, in substeps */
    int64_t cmd_sub;             /* cumulative commanded */
    int32_t enc_base;
    int32_t last_enc;
    int64_t win_cmd0;
    int32_t win_enc0;
    uint16_t last_battery_mv;
    uint32_t last_reservoir_mu;
    bool battery_low;
} op_sv_t;

/* uu_per_step outside [OP_CAL_UU_MIN, OP_CAL_UU_MAX] (incl. 0 = missing) latches
 * OP_FAULT_NO_CALIBRATION: every check/approve then refuses, and the fault cannot be
 * acknowledged. */
void op_sv_init(op_sv_t *sv, uint64_t now_ms, int32_t encoder_substeps, uint32_t uu_per_step);
/* reject (OP_ERR_LIMIT) values above the hard caps or zero */
op_err_t op_sv_configure(op_sv_t *sv, uint32_t max_bolus_mu, uint32_t max_basal_mu_h);

op_err_t op_sv_check_bolus(op_sv_t *sv, uint64_t now_ms, uint32_t amount_mu, uint32_t reservoir_mu);
op_err_t op_sv_check_basal_schedule(const op_sv_t *sv, const op_basal_schedule_t *s);
op_err_t op_sv_check_temp_basal(const op_sv_t *sv, uint32_t rate_mu_h, uint32_t duration_min);

/* Veto point for EVERY step. Returns how many of `requested` may run. Trimming
 * below `requested` for limit/reservoir reasons latches a fault. */
uint32_t op_sv_approve_steps(op_sv_t *sv, uint64_t now_ms, uint32_t requested, uint32_t reservoir_mu);
/* Periodic monitor: call after motor activity. Returns newly latched faults. */
uint16_t op_sv_observe(op_sv_t *sv, uint64_t now_ms, uint16_t battery_mv, uint32_t reservoir_mu,
                       int32_t encoder_substeps);
op_err_t op_sv_acknowledge(op_sv_t *sv, uint16_t mask);
/* Latch faults detected by the caller (e.g. motor did not execute approved steps). */
void op_sv_latch(op_sv_t *sv, uint16_t mask);
/* Restart encoder bookkeeping (after fill/prime or fault ack). */
void op_sv_rebaseline(op_sv_t *sv, int32_t encoder_substeps);

/* Hard preconditions for delivery. Both start false: a pod delivers nothing until the controller
 * has seen the DOCKED input and the pair state says this pod is the active one. */
void op_sv_set_docked(op_sv_t *sv, bool docked);
void op_sv_set_active(op_sv_t *sv, bool active);
/* Latches OP_FAULT_WEAR_EXPIRED at >= OP_WEAR_MAX_MS. */
void op_sv_observe_wear(op_sv_t *sv, uint64_t wear_ms);
/* New activation: wear timer restarts, the wear fault is released. */
void op_sv_reset_wear(op_sv_t *sv);

static inline uint16_t op_sv_faults(const op_sv_t *sv) { return sv->faults; }
static inline bool op_sv_motor_allowed(const op_sv_t *sv) { return sv->faults == 0; }
uint32_t op_sv_hourly_steps(op_sv_t *sv, uint64_t now_ms);
static inline bool op_sv_battery_low(const op_sv_t *sv) { return sv->battery_low; }

#endif
