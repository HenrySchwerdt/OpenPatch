#include "op/pump_controller.h"

#include <string.h>

/* ---- helpers --------------------------------------------------------------- */
static uint64_t now_ms(const op_pump_t *p) { return p->hal->time_ms(p->hal->ctx); }
static uint32_t now_s(const op_pump_t *p) { return (uint32_t)(now_ms(p) / 1000u); }
static int32_t enc_now(const op_pump_t *p) { return p->hal->encoder_read(p->hal->ctx); }

static void log_ev(op_pump_t *p, uint8_t type, int32_t a, int32_t b)
{
    op_log_append(&p->log, now_s(p), type, a, b);
}

/* Unfilled reservoirs are not monitored (no alarm at first boot). */
static uint32_t res_for_observe(const op_pump_t *p)
{
    return p->res.filled ? op_res_remaining_mu(&p->res) : UINT32_MAX;
}

static uint32_t run_motor(op_pump_t *p, uint32_t steps)
{
    p->hal->motor_enable(p->hal->ctx, true);
    int n = p->hal->motor_step(p->hal->ctx, steps);
    p->hal->motor_enable(p->hal->ctx, false);
    uint32_t done = n < 0 ? 0u : (uint32_t)n;
    if (done > steps) done = steps;
    op_res_consume(&p->res, done);
    return done;
}

/* New faults: log, stop all delivery, alarm, keep the driver off. */
static void sync_faults(op_pump_t *p, uint16_t before)
{
    uint16_t added = (uint16_t)(p->sv.faults & ~before);
    if (!added) return;
    log_ev(p, OP_EV_FAULT, added, 0);
    op_de_suspend(&p->de);
    p->hal->motor_enable(p->hal->ctx, false);
    p->hal->buzzer(p->hal->ctx, OP_BUZZER_ALARM);
}

static void observe(op_pump_t *p)
{
    op_sv_observe(&p->sv, now_ms(p), p->hal->battery_mv(p->hal->ctx), res_for_observe(p), enc_now(p));
    if (op_sv_battery_low(&p->sv) && !p->low_batt_reported) {
        p->low_batt_reported = true;
        log_ev(p, OP_EV_LOW_BATTERY, p->hal->battery_mv(p->hal->ctx), 0);
    } else if (!op_sv_battery_low(&p->sv)) {
        p->low_batt_reported = false;
    }
}

/* ---- two-pod helpers -------------------------------------------------------- */
static bool hal_docked(const op_pump_t *p) { return p->hal->docked && p->hal->docked(p->hal->ctx); }
static bool hal_charger(const op_pump_t *p) { return p->hal->charger_present && p->hal->charger_present(p->hal->ctx); }

/* Sample the DOCKED input into the supervisor. Called before every action that could move the motor. */
static void refresh_dock(op_pump_t *p)
{
    bool d = hal_docked(p);
    op_sv_set_docked(&p->sv, d);
    if (d == p->pod.docked) return;
    p->pod.docked = d;
    log_ev(p, d ? OP_EV_DOCKED : OP_EV_UNDOCKED, 0, 0);
    if (!d && p->de.bolus_active) /* a bolus is never resumed or "caught up" after an undock */
        log_ev(p, OP_EV_BOLUS_CANCEL, (int32_t)op_de_cancel_bolus(&p->de), 0);
}

static uint32_t act_delivered_mu(const op_pump_t *p)
{
    return op_steps_to_mu(p->cal.micro_u_per_step, p->de.delivered_steps - p->pod.act_base_steps);
}

static void release_now(op_pump_t *p, int32_t reason)
{
    op_de_suspend(&p->de); /* also cancels bolus and temp basal */
    p->hal->motor_enable(p->hal->ctx, false);
    p->pod.active = false;
    p->pod.pending_temp = false;
    op_sv_set_active(&p->sv, false);
    p->pod.last_release_mu = act_delivered_mu(p);
    log_ev(p, OP_EV_RELEASE, (int32_t)p->pod.last_release_mu, reason);
}

static void wear_step(op_pump_t *p, uint64_t dt)
{
    if (!p->pod.active) return;
    p->pod.wear_ms += dt;
    int32_t minutes = (int32_t)(p->pod.wear_ms / 60000u);
    if (!p->pod.wear_warned && p->pod.wear_ms >= OP_WEAR_WARN_MS) {
        p->pod.wear_warned = true;
        log_ev(p, OP_EV_WEAR_WARNING, minutes, 0);
        if (!p->sv.faults) p->hal->buzzer(p->hal->ctx, OP_BUZZER_BEEP);
    }
    bool was = p->sv.wear_expired;
    op_sv_observe_wear(&p->sv, p->pod.wear_ms);
    if (p->sv.wear_expired && !was) log_ev(p, OP_EV_WEAR_EXPIRED, minutes, 0);
}

/* ---- lifecycle --------------------------------------------------------------- */
void op_pump_init(op_pump_t *p, const op_hal_t *hal, const op_drive_cal_t *cal, uint32_t capacity_mu,
                  uint32_t restored_next_event_id)
{
    memset(p, 0, sizeof *p);
    p->hal = hal;
    p->cal_valid = op_drive_cal_validate(cal) == OP_OK;
    if (p->cal_valid) p->cal = *cal;
    uint32_t uu = p->cal_valid ? p->cal.micro_u_per_step : 0u;
    op_de_init(&p->de, uu);
    op_res_init(&p->res, capacity_mu, uu);
    op_log_restore(&p->log, restored_next_event_id);
    uint64_t t = now_ms(p);
    op_sv_init(&p->sv, t, enc_now(p), uu);
    p->pod.docked = hal_docked(p); /* no event for the boot state */
    op_sv_set_docked(&p->sv, p->pod.docked);
    p->last_tick_ms = t;
    hal->motor_enable(hal->ctx, false);
    hal->buzzer(hal->ctx, OP_BUZZER_OFF);
    log_ev(p, OP_EV_BOOT, 0, 0);
    observe(p);
    if (p->sv.faults) sync_faults(p, 0); /* e.g. NO_CALIBRATION: log + alarm, driver stays off */
}

void op_pump_tick(op_pump_t *p)
{
    uint64_t t = now_ms(p);
    uint64_t dt = t > p->last_tick_ms ? t - p->last_tick_ms : 0;
    uint64_t wear_dt = dt; /* a stalled loop still wears the pod: never clamped */
    p->last_tick_ms = t;
    if (dt > OP_TICK_MAX_DT_MS) { /* stalled loop: never "catch up" with a burst */
        dt = OP_TICK_MAX_DT_MS;
        p->tick_overruns++;
    }
    uint16_t before = p->sv.faults;

    refresh_dock(p);
    if (p->pod.active && hal_charger(p)) release_now(p, OP_REL_CHARGER); /* on a charger: forced released */
    wear_step(p, wear_dt);

    uint32_t requested = op_de_tick(&p->de, (uint32_t)dt);
    uint32_t approved = op_sv_approve_steps(&p->sv, t, requested, op_res_remaining_mu(&p->res));
    uint32_t executed = approved ? run_motor(p, approved) : 0;
    op_de_commit(&p->de, executed);
    if (executed < approved) op_sv_latch(&p->sv, OP_FAULT_INTERNAL);

    uint32_t ev = op_de_take_events(&p->de);
    if (ev & OP_DE_EV_BOLUS_DONE) log_ev(p, OP_EV_BOLUS_DONE, 0, 0);
    if (ev & OP_DE_EV_TEMP_DONE) log_ev(p, OP_EV_TEMP_DONE, 0, 0);
    if (ev & OP_DE_EV_TEMP_COMM_FALLBACK) log_ev(p, OP_EV_TEMP_COMM_FALLBACK, 0, 0);

    if (op_res_is_low(&p->res) && !p->low_res_reported) {
        p->low_res_reported = true;
        log_ev(p, OP_EV_LOW_RESERVOIR, (int32_t)op_res_remaining_mu(&p->res), 0);
    }
    observe(p);
    sync_faults(p, before);
    p->hal->watchdog_kick(p->hal->ctx);
}

/* ---- commands ------------------------------------------------------------------ */
static op_err_t require_active(const op_pump_t *p) { return p->pod.active ? OP_OK : OP_ERR_RELEASED; }

op_err_t op_pump_set_schedule(op_pump_t *p, const op_basal_schedule_t *s)
{
    op_err_t e = op_sv_check_basal_schedule(&p->sv, s);
    if (e != OP_OK) return e;
    if ((e = require_active(p)) != OP_OK) return e;
    e = op_de_set_schedule(&p->de, s);
    if (e == OP_OK) log_ev(p, OP_EV_BASAL_SET, s->count, 0);
    return e;
}

op_err_t op_pump_set_temp_basal(op_pump_t *p, uint32_t rate_mu_h, uint32_t duration_min)
{
    op_err_t e = op_sv_check_temp_basal(&p->sv, rate_mu_h, duration_min);
    if (e != OP_OK) return e;
    if ((e = require_active(p)) != OP_OK) return e;
    e = op_de_start_temp_basal(&p->de, rate_mu_h, duration_min);
    if (e == OP_OK) log_ev(p, OP_EV_TEMP_START, (int32_t)rate_mu_h, (int32_t)duration_min);
    return e;
}

op_err_t op_pump_cancel_temp_basal(op_pump_t *p)
{
    if (!op_de_cancel_temp_basal(&p->de)) return OP_ERR_NOT_FOUND;
    log_ev(p, OP_EV_TEMP_CANCEL, 0, 0);
    return OP_OK;
}

op_err_t op_pump_bolus(op_pump_t *p, uint32_t amount_mu)
{
    refresh_dock(p);
    op_err_t e = op_sv_check_bolus(&p->sv, now_ms(p), amount_mu, op_res_remaining_mu(&p->res));
    if (e != OP_OK) return e;
    e = op_de_start_bolus(&p->de, amount_mu);
    if (e == OP_OK) log_ev(p, OP_EV_BOLUS_START, (int32_t)amount_mu, 0);
    return e;
}

op_err_t op_pump_cancel_bolus(op_pump_t *p)
{
    if (!p->de.bolus_active) return OP_ERR_NOT_FOUND;
    log_ev(p, OP_EV_BOLUS_CANCEL, (int32_t)op_de_cancel_bolus(&p->de), 0);
    return OP_OK;
}

op_err_t op_pump_suspend(op_pump_t *p)
{
    if (!p->de.suspended) log_ev(p, OP_EV_SUSPEND, 0, 0);
    op_de_suspend(&p->de);
    return OP_OK;
}

op_err_t op_pump_resume(op_pump_t *p)
{
    refresh_dock(p);
    if (!op_sv_motor_allowed(&p->sv)) return OP_ERR_FAULT;
    if (!p->pod.active) return OP_ERR_RELEASED;
    if (!p->pod.docked) return OP_ERR_NOT_DOCKED;
    if (p->de.suspended) log_ev(p, OP_EV_RESUME, 0, 0);
    op_err_t e = op_de_resume(&p->de);
    if (e == OP_OK && p->pod.pending_temp) { /* temp basal handed over by Activate */
        p->pod.pending_temp = false;
        e = op_de_start_temp_basal(&p->de, p->pod.pending_temp_rate_mu_h, p->pod.pending_temp_min);
        if (e == OP_OK)
            log_ev(p, OP_EV_TEMP_START, (int32_t)p->pod.pending_temp_rate_mu_h, (int32_t)p->pod.pending_temp_min);
    }
    return e;
}

op_err_t op_pump_fill(op_pump_t *p, uint32_t fill_mu)
{
    if (!p->de.suspended) return OP_ERR_NOT_SUSPENDED;
    op_err_t e = op_res_fill(&p->res, fill_mu);
    if (e != OP_OK) return e;
    op_sv_rebaseline(&p->sv, enc_now(p)); /* the piston moved while filling */
    p->low_res_reported = op_res_is_low(&p->res);
    log_ev(p, OP_EV_FILL, (int32_t)fill_mu, 0);
    return OP_OK;
}

op_err_t op_pump_prime(op_pump_t *p, uint32_t steps)
{
    if (steps == 0) return OP_ERR_BAD_ARG;
    if (steps > op_mu_to_steps(p->sv.uu_per_step, OP_MAX_PRIME_MU)) return OP_ERR_LIMIT;
    if (!p->de.suspended) return OP_ERR_NOT_SUSPENDED;
    if (!p->res.filled) return OP_ERR_RESERVOIR;
    refresh_dock(p);
    if (!p->pod.active) return OP_ERR_RELEASED; /* only the active pod primes, and only docked */
    if (!p->pod.docked) return OP_ERR_NOT_DOCKED;
    uint16_t before = p->sv.faults;
    uint32_t approved = op_sv_approve_steps(&p->sv, now_ms(p), steps, op_res_remaining_mu(&p->res));
    uint32_t executed = approved ? run_motor(p, approved) : 0;
    if (executed < approved) op_sv_latch(&p->sv, OP_FAULT_INTERNAL);
    if (executed == steps) {
        log_ev(p, OP_EV_PRIME, (int32_t)steps, 0);
        observe(p); /* the encoder verifies the prime like any other delivery */
    }
    sync_faults(p, before);
    return executed == steps && p->sv.faults == before ? OP_OK : OP_ERR_FAULT;
}

op_err_t op_pump_acknowledge(op_pump_t *p, uint16_t mask)
{
    uint16_t before = p->sv.faults;
    op_err_t e = op_sv_acknowledge(&p->sv, mask);
    uint16_t cleared = (uint16_t)(before & ~p->sv.faults);
    if (cleared) log_ev(p, OP_EV_ACK, cleared, 0);
    if (p->sv.faults == 0) p->hal->buzzer(p->hal->ctx, OP_BUZZER_OFF);
    return e;
}

void op_pump_get_status(const op_pump_t *p, op_status_t *out)
{
    op_de_report_t rep;
    op_de_report(&p->de, &rep);
    memset(out, 0, sizeof *out);
    uint16_t f = 0;
    if (p->de.suspended) f |= OP_ST_SUSPENDED;
    if (p->de.bolus_active) f |= OP_ST_BOLUS_ACTIVE;
    if (p->de.temp_active) f |= OP_ST_TEMP_ACTIVE;
    if (p->de.has_schedule) f |= OP_ST_HAS_SCHEDULE;
    if (op_res_is_low(&p->res)) f |= OP_ST_LOW_RESERVOIR;
    if (p->sv.faults) f |= OP_ST_ALARM;
    if (p->res.filled) f |= OP_ST_FILLED;
    if (p->sv.battery_low) f |= OP_ST_LOW_BATTERY;
    out->flags = f;
    out->faults = p->sv.faults;
    out->reservoir_mu = op_res_remaining_mu(&p->res);
    out->battery_mv = p->hal->battery_mv(p->hal->ctx);
    out->bolus_remaining_mu = op_de_bolus_remaining_mu(&p->de);
    out->temp_rate_mu_h = p->de.temp_active ? (uint16_t)p->de.temp_rate_mu_h : 0;
    out->temp_remaining_min = (uint16_t)op_de_temp_remaining_min(&p->de);
    out->current_rate_mu_h = (uint16_t)op_de_current_rate_mu_h(&p->de);
    out->delivered_mu = rep.delivered_mu;
    out->scheduled_mu = rep.scheduled_mu;
    out->next_event_id = op_log_next_id(&p->log);
    out->fw_version = OP_FW_VERSION;
    if (p->pod.docked) f |= OP_ST_DOCKED;
    if (p->pod.active) f |= OP_ST_ACTIVE;
    if (p->pod.wear_warned && p->pod.active) f |= OP_ST_WEAR_WARNING;
    out->flags = f;
    out->pair_id = p->pod.pair_id;
    out->role = p->pod.role;
    out->wear_s = (uint32_t)(p->pod.wear_ms / 1000u);
    if (!p->pod.active) out->delivery_state = OP_DS_RELEASED;
    else if (p->sv.wear_expired) out->delivery_state = OP_DS_STOPPED_WEAR;
    else if (!p->pod.docked) out->delivery_state = OP_DS_PAUSED_UNDOCKED;
    else out->delivery_state = OP_DS_ACTIVE;
    if (p->cal_valid) {
        out->cal_drive_id = p->cal.drive_id;
        out->cal_uu_per_step = p->cal.micro_u_per_step;
        out->cal_steps_per_rev = p->cal.steps_per_rev;
        out->cal_gear_ratio_x100 = p->cal.gear_ratio_x100;
    } /* else all zero: the app must refuse */
}

/* ---- two-pod commands ---------------------------------------------------------- */
op_err_t op_pump_set_pairing(op_pump_t *p, uint32_t pair_id, uint8_t role)
{
    if (pair_id == 0 || (role != OP_ROLE_A && role != OP_ROLE_B)) return OP_ERR_BAD_ARG;
    if (p->pod.active) return OP_ERR_ALREADY_ACTIVE; /* never re-pair a delivering pod */
    p->pod.pair_id = pair_id;
    p->pod.role = role;
    log_ev(p, OP_EV_PAIRED, role, (int32_t)pair_id);
    return OP_OK;
}

op_err_t op_pump_activate(op_pump_t *p, const op_activate_args_t *a)
{
    if (!a || p->pod.pair_id == 0 || a->pair_id != p->pod.pair_id) return OP_ERR_PAIR;
    if (p->pod.active) return a->activation_id == p->pod.activation_id ? OP_OK : OP_ERR_ALREADY_ACTIVE;
    if (a->activation_id == 0) return OP_ERR_BAD_ARG;
    refresh_dock(p);
    if (hal_charger(p)) return OP_ERR_CHARGING;
    if (!p->pod.docked) return OP_ERR_NOT_DOCKED;
    if (p->sv.faults & (uint16_t)~OP_FAULT_WEAR_EXPIRED) return OP_ERR_FAULT;
    if (!p->res.filled) return OP_ERR_RESERVOIR;
    /* validate everything before touching anything: Activate is all or nothing */
    op_sv_t probe = p->sv; /* an old wear fault must not hide schedule errors: check against a fault-free copy */
    probe.faults = 0;
    op_err_t e = op_sv_check_basal_schedule(&probe, &a->schedule);
    if (e != OP_OK) return e;
    if (a->has_temp) {
        if (a->temp_remaining_min == 0 || a->temp_remaining_min > OP_TEMP_MAX_MIN ||
            a->temp_remaining_min % OP_TEMP_GRANULARITY_MIN != 0 || a->temp_rate_mu_h % OP_RATE_GRANULARITY_MU != 0 ||
            a->temp_rate_mu_h > p->sv.max_basal_mu_h)
            return a->temp_rate_mu_h > p->sv.max_basal_mu_h ? OP_ERR_LIMIT : OP_ERR_BAD_ARG;
    }
    e = op_de_set_schedule(&p->de, &a->schedule);
    if (e != OP_OK) return e;
    op_de_suspend(&p->de); /* stays suspended until Resume, so the connector can be primed first */
    p->pod.pending_temp = a->has_temp;
    p->pod.pending_temp_rate_mu_h = a->temp_rate_mu_h;
    p->pod.pending_temp_min = a->temp_remaining_min;
    op_sv_reset_wear(&p->sv);
    p->pod.wear_ms = 0;
    p->pod.wear_warned = false;
    p->pod.activation_id = a->activation_id;
    p->pod.act_base_steps = p->de.delivered_steps;
    p->pod.last_release_mu = 0;
    p->pod.active = true;
    op_sv_set_active(&p->sv, true);
    p->hal->buzzer(p->hal->ctx, OP_BUZZER_OFF);
    log_ev(p, OP_EV_BASAL_SET, a->schedule.count, 0);
    log_ev(p, OP_EV_ACTIVATE, p->pod.role, (int32_t)a->activation_id);
    return OP_OK;
}

op_err_t op_pump_release(op_pump_t *p, uint32_t pair_id, uint32_t *delivered_since_activation_mu)
{
    if (p->pod.pair_id == 0 || pair_id != p->pod.pair_id) return OP_ERR_PAIR;
    if (p->pod.active) release_now(p, OP_REL_COMMAND);
    if (delivered_since_activation_mu) *delivered_since_activation_mu = p->pod.last_release_mu;
    return OP_OK;
}

void op_pump_restore_pod(op_pump_t *p, uint32_t pair_id, uint8_t role, bool active, uint32_t activation_id,
                         uint64_t wear_ms)
{
    p->pod.pair_id = pair_id;
    p->pod.role = role;
    p->pod.active = active;
    p->pod.activation_id = activation_id;
    p->pod.wear_ms = active ? wear_ms : 0;
    p->pod.wear_warned = active && wear_ms >= OP_WEAR_WARN_MS;
    op_sv_set_active(&p->sv, active);
    if (active) {
        op_sv_observe_wear(&p->sv, p->pod.wear_ms);
        if (p->sv.faults) sync_faults(p, 0);
    }
}

/* ---- protocol ------------------------------------------------------------------- */
void op_pump_execute(op_pump_t *p, const op_cmd_t *cmd, op_rsp_t *rsp)
{
    rsp->type = cmd->type;
    rsp->seq = cmd->seq;
    if (cmd->has_time_of_day) op_de_set_time_of_day(&p->de, cmd->time_of_day_ms);
    op_err_t e = OP_OK;
    switch (cmd->type) {
    case OP_CMD_GET_STATUS:
        op_pump_get_status(p, &rsp->status);
        rsp->has_status = true;
        break;
    case OP_CMD_SET_BASAL_SCHEDULE: e = op_pump_set_schedule(p, &cmd->u.basal); break;
    case OP_CMD_SET_TEMP_BASAL: e = op_pump_set_temp_basal(p, cmd->u.temp.rate_mu_h, cmd->u.temp.duration_min); break;
    case OP_CMD_CANCEL_TEMP_BASAL: e = op_pump_cancel_temp_basal(p); break;
    case OP_CMD_BOLUS: e = op_pump_bolus(p, cmd->u.bolus.amount_mu); break;
    case OP_CMD_CANCEL_BOLUS: e = op_pump_cancel_bolus(p); break;
    case OP_CMD_SUSPEND: e = op_pump_suspend(p); break;
    case OP_CMD_RESUME: e = op_pump_resume(p); break;
    case OP_CMD_FILL_PRIME:
        if (cmd->u.fill.sub_op == OP_SUBOP_FILL) e = op_pump_fill(p, cmd->u.fill.fill_mu);
        else if (cmd->u.fill.sub_op == OP_SUBOP_PRIME) e = op_pump_prime(p, cmd->u.fill.prime_steps);
        else e = OP_ERR_BAD_ARG;
        break;
    case OP_CMD_ACKNOWLEDGE: e = op_pump_acknowledge(p, cmd->u.ack.fault_mask); break;
    case OP_CMD_SET_PAIRING: e = op_pump_set_pairing(p, cmd->u.pairing.pair_id, cmd->u.pairing.role); break;
    case OP_CMD_ACTIVATE: {
        op_activate_args_t a = {.pair_id = cmd->u.activate.pair_id,
                                .activation_id = cmd->u.activate.activation_id,
                                .schedule = cmd->u.activate.schedule,
                                .has_temp = cmd->u.activate.has_temp,
                                .temp_rate_mu_h = cmd->u.activate.temp_rate_mu_h,
                                .temp_remaining_min = cmd->u.activate.temp_remaining_min};
        e = op_pump_activate(p, &a);
        op_pump_get_status(p, &rsp->status);
        rsp->has_status = true;
        break;
    }
    case OP_CMD_RELEASE:
        e = op_pump_release(p, cmd->u.release.pair_id, &rsp->act_delivered_mu);
        rsp->has_act_delivered = e == OP_OK;
        op_pump_get_status(p, &rsp->status); /* final totals + reservoir */
        rsp->has_status = true;
        break;
    case OP_CMD_GET_HISTORY: {
        uint32_t max = cmd->u.history.max_events;
        if (max == 0 || max > OP_HIST_MAX_PER_RESPONSE) max = OP_HIST_MAX_PER_RESPONSE;
        rsp->n_events = (uint8_t)op_log_read(&p->log, cmd->u.history.from_id, rsp->events, max);
        rsp->next_event_id = op_log_next_id(&p->log);
        rsp->oldest_event_id = op_log_oldest_id(&p->log);
        rsp->has_history = true;
        break;
    }
    default: e = OP_ERR_UNSUPPORTED; break;
    }
    rsp->result = (uint8_t)e;
}

int op_pump_handle_frame(op_pump_t *p, op_session_t *s, const uint8_t *in, size_t len, uint8_t *out,
                         size_t out_cap)
{
    uint8_t plain[OP_FRAME_MAX];
    op_frame_t f;
    int rc = op_session_open(s, in, len, &f, plain, sizeof plain);
    if (rc < 0) return rc; /* corrupt, forged or replayed: no response, no side effects */

    op_de_comm_heartbeat(&p->de); /* authenticated + fresh = the phone is alive */

    op_rsp_t rsp;
    memset(&rsp, 0, sizeof rsp);
    op_cmd_t cmd;
    int d = op_cmd_decode(f.type, f.seq, f.payload, f.payload_len, &cmd);
    if (d < 0) {
        rsp.type = f.type;
        rsp.seq = f.seq;
        rsp.result = (uint8_t)-d;
    } else {
        op_pump_execute(p, &cmd, &rsp);
        if (rsp.has_status) rsp.status.last_seq = s->last_rx_seq; /* lets the phone resync after a pod reboot */
    }
    uint8_t body[OP_FRAME_MAX];
    int n = op_rsp_encode_payload(&rsp, body, sizeof body);
    if (n < 0) return n;
    return op_session_seal(s, true, (uint8_t)(f.type | OP_RSP_BIT), f.seq, (f.flags & OP_FLAG_ENCRYPTED) != 0, body,
                           (size_t)n, out, out_cap);
}
