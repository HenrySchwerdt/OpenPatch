/*
 * Occlusion detector fed by motor-current samples and encoder slip.
 *
 * Complements (never replaces) the supervisor's own checks (2 U undelivered, 10 % encoder window):
 * it reacts faster, because a blocked line shows up as a current rise together with spindle slip.
 * Portable, integer only, no hardware access. The pump controller feeds it once per motor burst.
 *
 * Bursts are accumulated into windows of `window_steps` steps (one step per second at the bolus
 * rate is too little data for a decision). Per window:
 *   slip_pct = (commanded - encoder travel) / commanded, clamped to 0..100
 * A window is a STRIKE if
 *   - slip_pct >= stall_slip_pct (spindle barely moves: no current needed), or
 *   - slip_pct >= slip_pct_min AND (peak >= abs_peak_ma OR the baseline is armed and
 *     mean >= baseline * rise_pct / 100)
 * `strikes_needed` consecutive strike windows latch the occlusion. Windows without a strike
 * teach the baseline (exponential average of the mean current), which arms after
 * `baseline_windows` healthy windows. Strike windows never change the baseline.
 */
#ifndef OP_OCCLUSION_H
#define OP_OCCLUSION_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint16_t abs_peak_ma;     /* peak current that counts as stalled (with slip) */
    uint16_t rise_pct;        /* mean current >= baseline * rise_pct / 100 counts as loaded (with slip) */
    uint8_t slip_pct_min;     /* minimum slip for the current-based strikes */
    uint8_t stall_slip_pct;   /* slip alone that counts as a strike */
    uint16_t window_steps;    /* steps per evaluation window */
    uint8_t strikes_needed;   /* consecutive strike windows to declare an occlusion */
    uint8_t baseline_windows; /* healthy windows before the relative current test is armed */
} op_occ_cfg_t;

typedef struct {
    op_occ_cfg_t cfg;
    bool enabled;
    bool occluded;            /* latched until op_occ_reset() */
    uint8_t strikes;
    uint8_t healthy_windows;
    uint16_t baseline_ma;     /* 0 until the first healthy window with current data */
    /* open window */
    uint32_t win_steps;
    int64_t win_cmd_sub;
    int64_t win_enc_sub;
    uint32_t win_mean_x_steps; /* sum of mean_ma * steps over bursts with current data */
    uint32_t win_cur_steps;    /* steps covered by current data */
    uint16_t win_peak_ma;
    /* last closed window, for diagnostics */
    uint32_t windows;
    uint8_t last_slip_pct;
    uint16_t last_mean_ma;
    uint16_t last_peak_ma;
} op_occ_t;

void op_occ_default_cfg(op_occ_cfg_t *cfg);
/* cfg == NULL: detector disabled (op_occ_feed returns false and keeps no state). */
void op_occ_init(op_occ_t *o, const op_occ_cfg_t *cfg);
/* Drop the open window, the strikes and the latch (fault acknowledged, fill, new activation).
 * The learned baseline survives. */
void op_occ_reset(op_occ_t *o);
/*
 * One motor burst. steps: steps really executed; enc_substeps: encoder travel in 1/16 steps
 * during the burst; samples == 0 means no current data. Returns true exactly once, when the
 * occlusion is declared.
 */
bool op_occ_feed(op_occ_t *o, uint32_t steps, int32_t enc_substeps, uint16_t peak_ma, uint16_t mean_ma,
                 uint16_t samples);

#endif
