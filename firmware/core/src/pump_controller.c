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

/* ---- lifecycle --------------------------------------------------------------- */
void op_pump_init(op_pump_t *p, const op_hal_t *hal, uint32_t capacity_mu, uint32_t restored_next_event_id)
{
    memset(p, 0, sizeof *p);
    p->hal = hal;
    op_de_init(&p->de);
    op_res_init(&p->res, capacity_mu);
    op_log_restore(&p->log, restored_next_event_id);
    uint64_t t = now_ms(p);
    op_sv_init(&p->sv, t, enc_now(p));
    p->last_tick_ms = t;
    hal->motor_enable(hal->ctx, false);
    hal->buzzer(hal->ctx, OP_BUZZER_OFF);
    log_ev(p, OP_EV_BOOT, 0, 0);
    observe(p);
}

void op_pump_tick(op_pump_t *p)
{
    uint64_t t = now_ms(p);
    uint64_t dt = t > p->last_tick_ms ? t - p->last_tick_ms : 0;
    p->last_tick_ms = t;
    if (dt > OP_TICK_MAX_DT_MS) { /* stalled loop: never "catch up" with a burst */
        dt = OP_TICK_MAX_DT_MS;
        p->tick_overruns++;
    }
    uint16_t before = p->sv.faults;

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
op_err_t op_pump_set_schedule(op_pump_t *p, const op_basal_schedule_t *s)
{
    op_err_t e = op_sv_check_basal_schedule(&p->sv, s);
    if (e != OP_OK) return e;
    e = op_de_set_schedule(&p->de, s);
    if (e == OP_OK) log_ev(p, OP_EV_BASAL_SET, s->count, 0);
    return e;
}

op_err_t op_pump_set_temp_basal(op_pump_t *p, uint32_t rate_mu_h, uint32_t duration_min)
{
    op_err_t e = op_sv_check_temp_basal(&p->sv, rate_mu_h, duration_min);
    if (e != OP_OK) return e;
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
    if (!op_sv_motor_allowed(&p->sv)) return OP_ERR_FAULT;
    if (p->de.suspended) log_ev(p, OP_EV_RESUME, 0, 0);
    return op_de_resume(&p->de);
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
    if (steps > OP_MAX_PRIME_STEPS) return OP_ERR_LIMIT;
    if (!p->de.suspended) return OP_ERR_NOT_SUSPENDED;
    if (!p->res.filled) return OP_ERR_RESERVOIR;
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
