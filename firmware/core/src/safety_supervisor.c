#include "op/safety_supervisor.h"

#include <string.h>

#define MINUTE_MS 60000ull
#define WINDOW_MIN 60u

static uint16_t u16_sat(uint32_t v) { return v > 0xFFFFu ? 0xFFFFu : (uint16_t)v; }

void op_sv_init(op_sv_t *sv, uint64_t now_ms, int32_t encoder_substeps, uint32_t uu_per_step)
{
    memset(sv, 0, sizeof *sv);
    if (uu_per_step >= OP_CAL_UU_MIN && uu_per_step <= OP_CAL_UU_MAX) {
        sv->uu_per_step = uu_per_step;
        sv->calibrated = true;
        sv->max_steps_per_min = op_mu_to_steps(uu_per_step, OP_MAX_MU_PER_MIN);
    } else {
        sv->faults = OP_FAULT_NO_CALIBRATION;
        sv->last_new_faults = OP_FAULT_NO_CALIBRATION;
    }
    sv->max_bolus_mu = OP_DEFAULT_MAX_BOLUS_MU;
    sv->max_basal_mu_h = OP_DEFAULT_MAX_BASAL_MU_H;
    sv->last_minute = now_ms / MINUTE_MS;
    sv->clock_started = true;
    sv->last_battery_mv = 0xFFFF;
    sv->last_reservoir_mu = UINT32_MAX;
    op_sv_rebaseline(sv, encoder_substeps);
}

op_err_t op_sv_configure(op_sv_t *sv, uint32_t max_bolus_mu, uint32_t max_basal_mu_h)
{
    if (max_bolus_mu == 0 || max_basal_mu_h == 0) return OP_ERR_LIMIT;
    if (max_bolus_mu > OP_HARD_MAX_BOLUS_MU || max_basal_mu_h > OP_HARD_MAX_BASAL_MU_H) return OP_ERR_LIMIT;
    sv->max_bolus_mu = max_bolus_mu;
    sv->max_basal_mu_h = max_basal_mu_h;
    return OP_OK;
}

/* ---- rolling window ------------------------------------------------------- */
static void roll(op_sv_t *sv, uint64_t now_ms)
{
    uint64_t m = now_ms / MINUTE_MS;
    if (m <= sv->last_minute) return; /* time never goes backwards */
    if (m - sv->last_minute >= WINDOW_MIN) {
        memset(sv->minute_steps, 0, sizeof sv->minute_steps);
    } else {
        for (uint64_t k = sv->last_minute + 1; k <= m; k++) sv->minute_steps[k % WINDOW_MIN] = 0;
    }
    sv->last_minute = m;
}

uint32_t op_sv_hourly_steps(op_sv_t *sv, uint64_t now_ms)
{
    roll(sv, now_ms);
    uint32_t sum = 0;
    for (unsigned i = 0; i < WINDOW_MIN; i++) sum += sv->minute_steps[i];
    return sum;
}

/* ---- command validation ------------------------------------------------------ */
void op_sv_set_docked(op_sv_t *sv, bool docked) { sv->docked = docked; }
void op_sv_set_active(op_sv_t *sv, bool active) { sv->active = active; }

void op_sv_observe_wear(op_sv_t *sv, uint64_t wear_ms)
{
    if (wear_ms < OP_WEAR_MAX_MS) return;
    sv->wear_expired = true;
    op_sv_latch(sv, OP_FAULT_WEAR_EXPIRED);
}

void op_sv_reset_wear(op_sv_t *sv)
{
    sv->wear_expired = false;
    sv->faults = (uint16_t)(sv->faults & ~OP_FAULT_WEAR_EXPIRED);
}

op_err_t op_sv_check_bolus(op_sv_t *sv, uint64_t now_ms, uint32_t amount_mu, uint32_t reservoir_mu)
{
    if (sv->faults) return OP_ERR_FAULT;
    if (!sv->active) return OP_ERR_RELEASED;
    if (!sv->docked) return OP_ERR_NOT_DOCKED;
    if (amount_mu == 0 || amount_mu % OP_BOLUS_GRANULARITY_MU != 0) return OP_ERR_BAD_ARG;
    if (amount_mu > sv->max_bolus_mu) return OP_ERR_LIMIT;
    if (amount_mu > reservoir_mu) return OP_ERR_RESERVOIR;
    uint32_t cap = op_mu_to_steps(sv->uu_per_step, OP_MAX_HOURLY_MU);
    if (op_sv_hourly_steps(sv, now_ms) + op_mu_to_steps(sv->uu_per_step, amount_mu) > cap) return OP_ERR_HOURLY;
    return OP_OK;
}

static op_err_t check_rate(const op_sv_t *sv, uint32_t rate_mu_h)
{
    if (rate_mu_h % OP_RATE_GRANULARITY_MU != 0) return OP_ERR_BAD_ARG;
    if (rate_mu_h > sv->max_basal_mu_h) return OP_ERR_LIMIT;
    return OP_OK;
}

op_err_t op_sv_check_basal_schedule(const op_sv_t *sv, const op_basal_schedule_t *s)
{
    if (sv->faults) return OP_ERR_FAULT;
    op_err_t e = op_de_validate_schedule(s);
    if (e != OP_OK) return e;
    for (uint8_t i = 0; i < s->count; i++) {
        e = check_rate(sv, s->seg[i].rate_mu_h);
        if (e != OP_OK) return e;
    }
    return OP_OK;
}

op_err_t op_sv_check_temp_basal(const op_sv_t *sv, uint32_t rate_mu_h, uint32_t duration_min)
{
    if (sv->faults) return OP_ERR_FAULT;
    if (duration_min == 0 || duration_min > OP_TEMP_MAX_MIN || duration_min % OP_TEMP_GRANULARITY_MIN != 0)
        return OP_ERR_BAD_ARG;
    return check_rate(sv, rate_mu_h);
}

/* ---- step veto ----------------------------------------------------------------- */
void op_sv_latch(op_sv_t *sv, uint16_t mask)
{
    sv->last_new_faults = (uint16_t)(sv->last_new_faults | (mask & (uint16_t)~sv->faults));
    sv->faults = (uint16_t)(sv->faults | mask);
}

uint32_t op_sv_approve_steps(op_sv_t *sv, uint64_t now_ms, uint32_t requested, uint32_t reservoir_mu)
{
    if (requested == 0) return 0;
    if (sv->faults || !sv->calibrated || sv->wear_expired) return 0;
    if (!sv->active || !sv->docked) return 0; /* released or off the cannula adapter: never a step */
    uint32_t allowed = requested;

    uint32_t res_steps = op_mu_to_steps(sv->uu_per_step, reservoir_mu);
    if (res_steps < allowed) {
        allowed = res_steps;
        op_sv_latch(sv, OP_FAULT_RESERVOIR_EMPTY);
    }
    uint32_t used = op_sv_hourly_steps(sv, now_ms);
    uint32_t cap = op_mu_to_steps(sv->uu_per_step, OP_MAX_HOURLY_MU);
    uint32_t room = used >= cap ? 0 : cap - used;
    if (room < allowed) {
        allowed = room;
        op_sv_latch(sv, OP_FAULT_LIMIT_EXCEEDED);
    }
    uint32_t bucket = (uint32_t)(sv->last_minute % WINDOW_MIN);
    uint32_t minute_used = sv->minute_steps[bucket] > sv->max_steps_per_min ? sv->max_steps_per_min
                                                                           : sv->minute_steps[bucket];
    uint32_t minute_room = sv->max_steps_per_min - minute_used;
    if (minute_room < allowed) {
        allowed = minute_room;
        op_sv_latch(sv, OP_FAULT_LIMIT_EXCEEDED);
    }
    sv->minute_steps[bucket] = u16_sat(sv->minute_steps[bucket] + allowed);
    sv->cmd_sub += (int64_t)allowed * OP_ENC_SUBSTEPS;
    return allowed;
}

/* ---- monitoring ------------------------------------------------------------------ */
void op_sv_rebaseline(op_sv_t *sv, int32_t encoder_substeps)
{
    sv->cmd_sub = 0;
    sv->enc_base = encoder_substeps;
    sv->last_enc = encoder_substeps;
    sv->win_cmd0 = 0;
    sv->win_enc0 = encoder_substeps;
}

static int64_t i64abs(int64_t v) { return v < 0 ? -v : v; }

static void check_encoder(op_sv_t *sv, int32_t enc)
{
    sv->last_enc = enc;
    if (!sv->calibrated) return;
    int64_t travelled = (int64_t)enc - sv->enc_base;
    int64_t undelivered = sv->cmd_sub - travelled;
    if (undelivered > op_mu_to_substeps(sv->uu_per_step, OP_OCCLUSION_MU)) op_sv_latch(sv, OP_FAULT_OCCLUSION);

    int64_t cmd_win = sv->cmd_sub - sv->win_cmd0;
    if (cmd_win < op_mu_to_substeps(sv->uu_per_step, OP_ENCODER_WINDOW_MU)) return;
    int64_t enc_win = (int64_t)enc - sv->win_enc0;
    int64_t err = i64abs(cmd_win - enc_win);
    if (err * 100 > cmd_win * (int64_t)OP_ENCODER_TOLERANCE_PCT) {
        op_sv_latch(sv, OP_FAULT_ENCODER_DEVIATION);
        /* "no travel despite steps": the spindle barely moved at all */
        if (enc_win * 10 < cmd_win) op_sv_latch(sv, OP_FAULT_OCCLUSION);
    }
    sv->win_cmd0 = sv->cmd_sub;
    sv->win_enc0 = enc;
}

uint16_t op_sv_observe(op_sv_t *sv, uint64_t now_ms, uint16_t battery_mv, uint32_t reservoir_mu,
                       int32_t encoder_substeps)
{
    (void)now_ms;
    sv->last_new_faults = 0;
    sv->last_battery_mv = battery_mv;
    sv->last_reservoir_mu = reservoir_mu;
    sv->battery_low = battery_mv < OP_BATTERY_LOW_MV;
    if (battery_mv < OP_BATTERY_CRITICAL_MV) op_sv_latch(sv, OP_FAULT_BATTERY_CRITICAL);
    if (reservoir_mu == 0) op_sv_latch(sv, OP_FAULT_RESERVOIR_EMPTY);
    check_encoder(sv, encoder_substeps);
    return sv->last_new_faults;
}

op_err_t op_sv_acknowledge(op_sv_t *sv, uint16_t mask)
{
    uint16_t target = (uint16_t)(sv->faults & mask);
    uint16_t blocked = 0;
    if ((target & OP_FAULT_BATTERY_CRITICAL) &&
        sv->last_battery_mv < OP_BATTERY_CRITICAL_MV + OP_BATTERY_HYSTERESIS_MV)
        blocked |= OP_FAULT_BATTERY_CRITICAL;
    if ((target & OP_FAULT_NO_CALIBRATION) && !sv->calibrated) blocked |= OP_FAULT_NO_CALIBRATION;
    if ((target & OP_FAULT_WEAR_EXPIRED) && sv->wear_expired) blocked |= OP_FAULT_WEAR_EXPIRED;
    if ((target & OP_FAULT_RESERVOIR_EMPTY) && sv->last_reservoir_mu == 0) blocked |= OP_FAULT_RESERVOIR_EMPTY;

    uint16_t clear = (uint16_t)(target & ~blocked);
    sv->faults = (uint16_t)(sv->faults & ~clear);
    if (clear & (OP_FAULT_OCCLUSION | OP_FAULT_ENCODER_DEVIATION | OP_FAULT_INTERNAL))
        op_sv_rebaseline(sv, sv->last_enc);
    return blocked ? OP_ERR_PERSISTS : OP_OK;
}
