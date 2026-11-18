/*
 * OpenPatch core: shared units, limits, error codes.
 *
 * EXPERIMENTAL DIY DEVICE - NOT A MEDICAL DEVICE. See docs/openpatch-protocol.md.
 * All numeric values come from spec/design-parameters.md (single source of truth).
 *
 * Unit conventions (integer only, no floats anywhere in the core):
 *   mU      = milli-unit of insulin = 0.001 U (U100: 1 U = 10 ul)
 *   mU/h    = rate in milli-units per hour
 *   step    = one motor step = 0.0131 U = 13.1 mU  (exactly 131/10 mU)
 *   substep = 1/16 step, resolution of the spindle encoder
 */
#ifndef OP_TYPES_H
#define OP_TYPES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* ---- dosing geometry -------------------------------------------------- */
#define OP_STEP_MU_NUM 131u      /* one step = 131/10 mU */
#define OP_STEP_MU_DEN 10u
#define OP_ENC_SUBSTEPS 16u      /* encoder counts per step */

/*
 * Rate accumulator scale. A rate of R mU/h held for dt ms delivers
 * R*dt/3_600_000 mU. We accumulate the numerator R*dt exactly ("scaled"
 * units) and emit a step every OP_SCALED_PER_STEP:
 *   13.1 mU * 3_600_000 = 47_160_000.
 */
#define OP_SCALED_PER_MU 3600000ll
#define OP_SCALED_PER_STEP 47160000ll

/* ---- schedule / timing ------------------------------------------------- */
#define OP_SLOT_MS 1800000u      /* 30 min */
#define OP_SLOTS_PER_DAY 48u
#define OP_DAY_MS 86400000u
#define OP_BASAL_SEGMENTS_MAX 24u
#define OP_RATE_GRANULARITY_MU 50u    /* 0.05 U (U/h) */
#define OP_BOLUS_GRANULARITY_MU 50u
#define OP_TEMP_MAX_MIN 720u          /* 12 h */
#define OP_TEMP_GRANULARITY_MIN 30u
#define OP_COMM_LOSS_TEMP_MS 1800000u /* spec 7: temp basal survives 30 min without comm */

/* ---- safety limits (spec section 7) ------------------------------------ */
#define OP_BOLUS_RATE_MU_H 90000u         /* 1.5 U/min */
#define OP_HARD_MAX_BOLUS_MU 25000u       /* configurable <= 25 U */
#define OP_HARD_MAX_BASAL_MU_H 30000u     /* configurable <= 30 U/h */
#define OP_DEFAULT_MAX_BOLUS_MU 10000u
#define OP_DEFAULT_MAX_BASAL_MU_H 5000u
#define OP_MAX_HOURLY_MU 15000u           /* rolling 60 min, all delivery */
#define OP_MAX_STEPS_PER_MIN 130u         /* backstop ~1.7 U/min; bolus is 1.5 U/min */
#define OP_OCCLUSION_MU 2000u             /* undelivered (commanded - encoder) */
#define OP_ENCODER_WINDOW_MU 1000u        /* deviation evaluated per >= 1 U */
#define OP_ENCODER_TOLERANCE_PCT 10u
#define OP_BATTERY_CRITICAL_MV 3300u      /* assumption, see docs */
#define OP_BATTERY_LOW_MV 3500u
#define OP_BATTERY_HYSTERESIS_MV 100u
#define OP_DEFAULT_LOW_RESERVOIR_MU 10000u
#define OP_MAX_PRIME_STEPS 40u            /* ~0.52 U, needle dead volume only */
#define OP_TICK_MAX_DT_MS 5000u           /* controller clamps stalls (no catch-up) */

/* ---- reservoir variants ------------------------------------------------- */
#define OP_CAPACITY_70_MU 70000u
#define OP_CAPACITY_100_MU 100000u
#define OP_CAPACITY_200_MU 200000u

#define OP_FW_VERSION 0x0100u /* major<<8 | minor */

/* ---- error codes: 0 = OK; length-returning functions use -OP_ERR_x ----- */
typedef enum {
    OP_OK = 0,
    OP_ERR_BAD_ARG = 1,
    OP_ERR_LIMIT = 2,           /* above configured/hard limit */
    OP_ERR_BUSY = 3,            /* e.g. bolus already running */
    OP_ERR_FAULT = 4,           /* a fault is latched */
    OP_ERR_SUSPENDED = 5,
    OP_ERR_NOT_SUSPENDED = 6,
    OP_ERR_RESERVOIR = 7,       /* insufficient / not filled */
    OP_ERR_PERSISTS = 8,        /* cannot acknowledge: cause still present */
    OP_ERR_UNSUPPORTED = 9,
    OP_ERR_FRAME = 10,          /* malformed / truncated frame or TLV */
    OP_ERR_CRC = 11,
    OP_ERR_VERSION = 12,
    OP_ERR_REPLAY = 13,
    OP_ERR_AUTH = 14,           /* AES-CCM tag mismatch or plaintext refused */
    OP_ERR_TOO_LARGE = 15,      /* output buffer / frame size exceeded */
    OP_ERR_HOURLY = 16,         /* would exceed rolling-hour delivery cap */
    OP_ERR_NOT_FOUND = 17,
    OP_ERR_SESSION = 18         /* sequence space exhausted, rekey needed */
} op_err_t;

/* ---- latched fault bits ------------------------------------------------ */
typedef enum {
    OP_FAULT_OCCLUSION = 1u << 0,
    OP_FAULT_ENCODER_DEVIATION = 1u << 1,
    OP_FAULT_RESERVOIR_EMPTY = 1u << 2,
    OP_FAULT_BATTERY_CRITICAL = 1u << 3,
    OP_FAULT_LIMIT_EXCEEDED = 1u << 4, /* hourly / per-minute veto */
    OP_FAULT_INTERNAL = 1u << 5        /* motor did not execute what was approved */
} op_fault_t;

/* ---- conversions (all integer, floor) ---------------------------------- */
static inline uint32_t op_steps_to_mu(uint32_t steps)
{
    return (uint32_t)(((uint64_t)steps * OP_STEP_MU_NUM) / OP_STEP_MU_DEN);
}
static inline uint32_t op_mu_to_steps(uint32_t mu)
{
    return (uint32_t)(((uint64_t)mu * OP_STEP_MU_DEN) / OP_STEP_MU_NUM);
}
static inline int64_t op_mu_to_substeps(uint32_t mu)
{
    return (int64_t)(((uint64_t)mu * OP_STEP_MU_DEN * OP_ENC_SUBSTEPS) / OP_STEP_MU_NUM);
}

#endif /* OP_TYPES_H */
