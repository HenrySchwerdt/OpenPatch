/*
 * Drive calibration: how much insulin one motor step delivers.
 *
 * SAFETY CRITICAL. This value scales every dose. A wrong value delivers a wrong amount of
 * insulin (Rev A with the 5:1 gear is 0.0261 U/step, the earlier 10:1 concept was 0.0131 U/step:
 * mixing them up doubles every dose). Therefore:
 *  - the value is an integer in micro-units (uU) of insulin per step,
 *  - it is selected at build time (Kconfig OPENPATCH_DRIVE_*) from the preset table below,
 *  - it carries a magic + CRC-32 so a corrupted copy in flash is detected,
 *  - it is persisted on first boot and must match the build on every later boot,
 *  - the safety supervisor refuses all delivery without a valid calibration,
 *  - it is reported in GetStatus (OP_TAG_DRIVE_CAL) so the app can verify it.
 *
 * steps_per_rev and gear_ratio_x100 are documentation / encoder scaling (spindle turns once per
 * steps_per_rev * gear_ratio steps); they do not influence dose arithmetic.
 */
#ifndef OP_DRIVE_CAL_H
#define OP_DRIVE_CAL_H

#include "op/op_types.h"

#define OP_DRIVE_CAL_MAGIC 0x4F504443u /* "OPDC" */

typedef enum {
    OP_DRIVE_NONE = 0,
    OP_DRIVE_ZWBPD006006_5_1 = 1,  /* Rev A: Zhaowei ZWBPD006006, 20 steps/rev, 5:1 planetary */
    OP_DRIVE_FAULHABER_16_1 = 2    /* premium: Faulhaber ADM0620 + 06/1 16:1 */
} op_drive_id_t;

typedef struct {
    uint32_t magic;             /* OP_DRIVE_CAL_MAGIC */
    uint16_t drive_id;          /* op_drive_id_t */
    uint16_t steps_per_rev;     /* motor full steps per motor revolution */
    uint16_t gear_ratio_x100;   /* gearbox ratio * 100 (5:1 -> 500) */
    uint16_t reserved;          /* must be 0 */
    uint32_t micro_u_per_step;  /* uU of insulin (U100) per motor step */
    uint32_t crc32;             /* CRC-32 over all previous fields (little-endian serialisation) */
} op_drive_cal_t;

#define OP_DRIVE_ZWBPD006006_UU_PER_STEP 26100u /* 0.261 ul = 0.0261 U (spec/design-parameters.md section 4) */
#define OP_DRIVE_FAULHABER_16_1_UU_PER_STEP 8156u /* 26100 * 5 / 16 = 8156.25 -> 0.0082 U (~122.6 steps/U) */

/* Fill *out with the preset for `id` (magic and CRC set). OP_ERR_BAD_ARG for unknown ids. */
op_err_t op_drive_cal_preset(op_drive_id_t id, op_drive_cal_t *out);
/* Recompute the CRC of *c (used after hand-building a record). */
uint32_t op_drive_cal_crc(const op_drive_cal_t *c);
/*
 * OP_OK only if: magic ok, CRC ok, reserved == 0, micro_u_per_step within
 * [OP_CAL_UU_MIN, OP_CAL_UU_MAX], and the record equals the preset of its drive_id (so a record
 * with a plausible but wrong per-step volume is refused too). NULL -> OP_ERR_NOT_FOUND.
 */
op_err_t op_drive_cal_validate(const op_drive_cal_t *c);
/* Spindle revolution in motor steps (steps_per_rev * ratio), 0 if the record is invalid. */
uint32_t op_drive_cal_steps_per_spindle_rev(const op_drive_cal_t *c);

#endif
