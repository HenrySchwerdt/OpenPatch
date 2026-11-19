/*
 * OpenPatch core: shared units, limits, error codes.
 *
 * EXPERIMENTAL DIY DEVICE - NOT A MEDICAL DEVICE. See docs/openpatch-protocol.md.
 * All numeric values come from spec/design-parameters.md (single source of truth).
 *
 * Unit conventions (integer only, no floats anywhere in the core):
 *   mU      = milli-unit of insulin = 0.001 U (U100: 1 U = 10 ul)
 *   mU/h    = rate in milli-units per hour
 *   uU      = micro-unit of insulin = 0.000001 U (drive calibration resolution)
 *   step    = one motor step. Its volume is NOT a compile-time constant: it comes from the
 *             drive calibration (op/drive_cal.h), e.g. 26100 uU = 0.0261 U for the Rev A
 *             5:1 drive. Every conversion below takes it as `uu_per_step` and a value of 0
 *             (= no valid calibration) converts to zero steps / zero volume.
 *   substep = 1/16 step, resolution of the spindle encoder
 */
#ifndef OP_TYPES_H
#define OP_TYPES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* ---- dosing geometry -------------------------------------------------- */
#define OP_UU_PER_MU 1000u       /* micro-units per milli-unit */
/* Sane range of the per-step volume (4 mU .. 60 mU). The shipped drives are 8.2 mU (16:1)
 * and 26.1 mU (5:1). Anything outside is a corrupted or wrong calibration. */
#define OP_CAL_UU_MIN 4000u
#define OP_CAL_UU_MAX 60000u
#define OP_ENC_SUBSTEPS 16u      /* encoder counts per step */

/*
 * Rate accumulator scale. A rate of R mU/h held for dt ms delivers
 * R*dt/3_600_000 mU. We accumulate the numerator R*dt exactly ("scaled"
 * units) and emit a step every `uu_per_step * OP_SCALED_PER_UU` scaled units
 * (5:1 drive: 26.1 mU * 3_600_000 = 93_960_000).
 */
#define OP_SCALED_PER_MU 3600000ll
#define OP_SCALED_PER_UU 3600ll

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
#define OP_MAX_MU_PER_MIN 1700u           /* per-minute backstop 1.7 U/min; bolus is 1.5 U/min */
#define OP_OCCLUSION_MU 2000u             /* undelivered (commanded - encoder) */
#define OP_ENCODER_WINDOW_MU 1000u        /* deviation evaluated per >= 1 U */
#define OP_ENCODER_TOLERANCE_PCT 10u
#define OP_BATTERY_CRITICAL_MV 3300u      /* assumption, see docs */
#define OP_BATTERY_LOW_MV 3500u
#define OP_BATTERY_HYSTERESIS_MV 100u
#define OP_BATTERY_NONE_MV 0xFFFFu        /* reported when the board has no battery monitoring */
#define OP_DEFAULT_LOW_RESERVOIR_MU 10000u
#define OP_MAX_PRIME_MU 524u              /* ~0.52 U, needle dead volume only (volume, not steps) */
#define OP_TICK_MAX_DT_MS 5000u           /* controller clamps stalls (no catch-up) */

/* ---- reservoir variants ------------------------------------------------- */
#define OP_CAPACITY_70_MU 70000u
#define OP_CAPACITY_100_MU 100000u
#define OP_CAPACITY_200_MU 200000u

/* ---- two-pod system (spec/design-parameters.md section 1b) ------------- */
#define OP_WEAR_WARN_MS (44ull * 3600000ull) /* app-visible warning */
#define OP_WEAR_MAX_MS (52ull * 3600000ull)  /* delivery stop + alarm */

typedef enum { OP_ROLE_NONE = 0, OP_ROLE_A = 1, OP_ROLE_B = 2 } op_role_t;

/* what the pod is doing, reported in GetStatus */
typedef enum {
    OP_DS_RELEASED = 0,         /* not the active pod of its pair: never delivers */
    OP_DS_ACTIVE = 1,           /* active and docked (may still be suspended by a command) */
    OP_DS_PAUSED_UNDOCKED = 2,  /* active but off the cannula adapter: no steps */
    OP_DS_STOPPED_WEAR = 3      /* wear limit reached: delivery stopped, alarm */
} op_delivery_state_t;

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
    OP_ERR_SESSION = 18,        /* sequence space exhausted, rekey needed */
    OP_ERR_NOT_DOCKED = 19,     /* dock input says the pod is not on the cannula adapter */
    OP_ERR_RELEASED = 20,       /* pod is not the active pod: delivery commands refused */
    OP_ERR_ALREADY_ACTIVE = 21, /* Activate while active (different activation id) */
    OP_ERR_PAIR = 22,           /* pair id / role mismatch or pod not paired */
    OP_ERR_WEAR_EXPIRED = 23,   /* wear limit reached */
    OP_ERR_CHARGING = 24        /* pod is on a charger: forced released, cannot activate */
} op_err_t;

/* ---- latched fault bits ------------------------------------------------ */
typedef enum {
    OP_FAULT_OCCLUSION = 1u << 0,
    OP_FAULT_ENCODER_DEVIATION = 1u << 1,
    OP_FAULT_RESERVOIR_EMPTY = 1u << 2,
    OP_FAULT_BATTERY_CRITICAL = 1u << 3,
    OP_FAULT_LIMIT_EXCEEDED = 1u << 4, /* hourly / per-minute veto */
    OP_FAULT_INTERNAL = 1u << 5,       /* motor did not execute what was approved */
    OP_FAULT_NO_CALIBRATION = 1u << 6, /* drive calibration missing / invalid: no delivery, not acknowledgeable */
    OP_FAULT_WEAR_EXPIRED = 1u << 7    /* >= 52 h since activation: delivery stopped, cleared only by a new Activate */
} op_fault_t;

/* ---- conversions (all integer, floor) ---------------------------------- */
static inline uint32_t op_steps_to_mu(uint32_t uu_per_step, uint32_t steps)
{
    return (uint32_t)(((uint64_t)steps * uu_per_step) / OP_UU_PER_MU);
}
static inline uint32_t op_mu_to_steps(uint32_t uu_per_step, uint32_t mu)
{
    return uu_per_step == 0 ? 0u : (uint32_t)(((uint64_t)mu * OP_UU_PER_MU) / uu_per_step);
}
static inline int64_t op_mu_to_substeps(uint32_t uu_per_step, uint32_t mu)
{
    return uu_per_step == 0 ? 0 : (int64_t)(((uint64_t)mu * OP_UU_PER_MU * OP_ENC_SUBSTEPS) / uu_per_step);
}

#endif /* OP_TYPES_H */
