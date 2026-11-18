/*
 * Pump controller: wires delivery engine, safety supervisor, reservoir and
 * log to the HAL and exposes command-level operations plus the protocol
 * dispatcher. This is the only module that knows all the others.
 */
#ifndef OP_PUMP_CONTROLLER_H
#define OP_PUMP_CONTROLLER_H

#include "op/delivery_engine.h"
#include "op/event_log.h"
#include "op/op_hal.h"
#include "op/openpatch_proto.h"
#include "op/reservoir_model.h"
#include "op/safety_supervisor.h"

typedef struct {
    const op_hal_t *hal;
    op_de_t de;
    op_sv_t sv;
    op_res_t res;
    op_log_t log;
    uint64_t last_tick_ms;
    bool low_res_reported;
    bool low_batt_reported;
    uint32_t tick_overruns;
} op_pump_t;

void op_pump_init(op_pump_t *p, const op_hal_t *hal, uint32_t capacity_mu, uint32_t restored_next_event_id);
/* call every ~1 s from the main loop */
void op_pump_tick(op_pump_t *p);

op_err_t op_pump_set_schedule(op_pump_t *p, const op_basal_schedule_t *s);
op_err_t op_pump_set_temp_basal(op_pump_t *p, uint32_t rate_mu_h, uint32_t duration_min);
op_err_t op_pump_cancel_temp_basal(op_pump_t *p);
op_err_t op_pump_bolus(op_pump_t *p, uint32_t amount_mu);
op_err_t op_pump_cancel_bolus(op_pump_t *p);
op_err_t op_pump_suspend(op_pump_t *p);
op_err_t op_pump_resume(op_pump_t *p);
op_err_t op_pump_fill(op_pump_t *p, uint32_t fill_mu);
op_err_t op_pump_prime(op_pump_t *p, uint32_t steps);
op_err_t op_pump_acknowledge(op_pump_t *p, uint16_t mask);
void op_pump_get_status(const op_pump_t *p, op_status_t *out);

/* Full protocol path: decode/authenticate -> execute -> response frame.
 * Returns response length, or -err when no response can be produced
 * (undecodable / unauthenticated frames are dropped silently). */
int op_pump_handle_frame(op_pump_t *p, op_session_t *s, const uint8_t *in, size_t len, uint8_t *out,
                         size_t out_cap);
/* Execute an already-decoded command (used by the dispatcher and tests). */
void op_pump_execute(op_pump_t *p, const op_cmd_t *cmd, op_rsp_t *rsp);

#endif
