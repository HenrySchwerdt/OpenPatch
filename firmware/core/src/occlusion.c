#include "op/occlusion.h"

#include <string.h>

#include "op/op_types.h"

void op_occ_default_cfg(op_occ_cfg_t *cfg)
{
    /* STSPIN220 bench defaults: coil peak about 105 mA (electronics/pin-assignment.md), so 150 mA
     * at the sense input is a clearly stalled/overdriven motor. Tune on the bench (see
     * docs/bench-testing.md). */
    cfg->abs_peak_ma = 150;
    cfg->rise_pct = 150;
    cfg->slip_pct_min = 30;
    cfg->stall_slip_pct = 60;
    cfg->window_steps = 8;
    cfg->strikes_needed = 2;
    cfg->baseline_windows = 3;
}

void op_occ_init(op_occ_t *o, const op_occ_cfg_t *cfg)
{
    memset(o, 0, sizeof *o);
    if (!cfg) return;
    o->cfg = *cfg;
    if (o->cfg.window_steps == 0) o->cfg.window_steps = 1;
    if (o->cfg.strikes_needed == 0) o->cfg.strikes_needed = 1;
    o->enabled = true;
}

void op_occ_reset(op_occ_t *o)
{
    o->occluded = false;
    o->strikes = 0;
    o->win_steps = 0;
    o->win_cmd_sub = 0;
    o->win_enc_sub = 0;
    o->win_mean_x_steps = 0;
    o->win_cur_steps = 0;
    o->win_peak_ma = 0;
}

static uint8_t slip_pct(int64_t cmd_sub, int64_t enc_sub)
{
    if (cmd_sub <= 0) return 0;
    int64_t missing = cmd_sub - enc_sub;
    if (missing <= 0) return 0;
    int64_t pct = missing * 100 / cmd_sub;
    return pct > 100 ? 100u : (uint8_t)pct;
}

/* Close the window; returns true if it is a strike window. */
static bool close_window(op_occ_t *o)
{
    const op_occ_cfg_t *c = &o->cfg;
    uint8_t slip = slip_pct(o->win_cmd_sub, o->win_enc_sub);
    bool have_current = o->win_cur_steps > 0;
    uint16_t mean = have_current ? (uint16_t)(o->win_mean_x_steps / o->win_cur_steps) : 0;
    uint16_t peak = o->win_peak_ma;

    o->windows++;
    o->last_slip_pct = slip;
    o->last_mean_ma = mean;
    o->last_peak_ma = peak;

    bool armed = o->healthy_windows >= c->baseline_windows && o->baseline_ma > 0;
    bool loaded = have_current && (peak >= c->abs_peak_ma ||
                                   (armed && (uint32_t)mean * 100u >= (uint32_t)o->baseline_ma * c->rise_pct));
    bool strike = slip >= c->stall_slip_pct || (slip >= c->slip_pct_min && loaded);

    if (!strike && have_current && slip < c->slip_pct_min) { /* healthy: learn the baseline */
        o->baseline_ma = o->baseline_ma == 0 ? mean : (uint16_t)(((uint32_t)o->baseline_ma * 3u + mean) / 4u);
        if (o->healthy_windows < 255) o->healthy_windows++;
    }

    o->win_steps = 0;
    o->win_cmd_sub = 0;
    o->win_enc_sub = 0;
    o->win_mean_x_steps = 0;
    o->win_cur_steps = 0;
    o->win_peak_ma = 0;
    return strike;
}

bool op_occ_feed(op_occ_t *o, uint32_t steps, int32_t enc_substeps, uint16_t peak_ma, uint16_t mean_ma,
                 uint16_t samples)
{
    if (!o->enabled || o->occluded || steps == 0) return false;
    o->win_steps += steps;
    o->win_cmd_sub += (int64_t)steps * OP_ENC_SUBSTEPS;
    o->win_enc_sub += enc_substeps;
    if (samples > 0) {
        o->win_mean_x_steps += (uint32_t)mean_ma * steps;
        o->win_cur_steps += steps;
        if (peak_ma > o->win_peak_ma) o->win_peak_ma = peak_ma;
    }
    if (o->win_steps < o->cfg.window_steps) return false;

    if (close_window(o)) {
        if (o->strikes < 255) o->strikes++;
    } else {
        o->strikes = 0;
    }
    if (o->strikes >= o->cfg.strikes_needed) {
        o->occluded = true;
        return true;
    }
    return false;
}
