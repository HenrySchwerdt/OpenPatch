/*
 * Pump controller: wires delivery engine, safety supervisor, reservoir and
 * log to the HAL and exposes command-level operations plus the protocol
 * dispatcher. This is the only module that knows all the others.
 */
#ifndef OP_PUMP_CONTROLLER_H
#define OP_PUMP_CONTROLLER_H

#include "op/delivery_engine.h"
#include "op/drive_cal.h"
#include "op/event_log.h"
#include "op/op_hal.h"
#include "op/openpatch_proto.h"
#include "op/reservoir_model.h"
#include "op/safety_supervisor.h"

/* Two-pod state (spec section 1b). Persisted by the platform (see op_pump_restore_pod). */
typedef struct {
    uint32_t pair_id;        /* 0 = not paired */
    uint8_t role;            /* op_role_t */
    bool active;             /* this pod is the active pod of its pair */
    uint32_t activation_id;  /* of the current/last activation (idempotent Activate) */
    uint64_t wear_ms;        /* since activation, frozen while released */
    bool wear_warned;
    bool docked;             /* last sampled DOCKED input */
    bool pending_temp;       /* temp basal from Activate, started by the first Resume */
    uint32_t pending_temp_rate_mu_h, pending_temp_min;
    uint32_t act_base_steps; /* de.delivered_steps at activation */
    uint32_t last_release_mu;/* delivered since activation, as of the last release */
} op_pod_t;

typedef struct {
    uint32_t pair_id, activation_id;
    op_basal_schedule_t schedule;
    bool has_temp;
    uint32_t temp_rate_mu_h, temp_remaining_min;
} op_activate_args_t;

typedef struct {
    const op_hal_t *hal;
    op_pod_t pod;
    op_drive_cal_t cal;   /* zeroed when missing/invalid */
    bool cal_valid;
    op_de_t de;
    op_sv_t sv;
    op_res_t res;
    op_log_t log;
    uint64_t last_tick_ms;
    bool low_res_reported;
    bool low_batt_reported;
    uint32_t tick_overruns;
} op_pump_t;

/* cal may be NULL (missing). A missing or invalid calibration (op_drive_cal_validate) leaves the
 * pump permanently without delivery: OP_FAULT_NO_CALIBRATION is latched and cannot be acknowledged. */
void op_pump_init(op_pump_t *p, const op_hal_t *hal, const op_drive_cal_t *cal, uint32_t capacity_mu,
                  uint32_t restored_next_event_id);
/* call every ~1 s from the main loop */
void op_pump_tick(op_pump_t *p);

/* ---- two-pod commands ---------------------------------------------------------- */
/* Pair id + role. Only a released pod accepts it; a different id than the stored one is accepted
 * only while released. pair_id 0 and unknown roles are rejected. */
op_err_t op_pump_set_pairing(op_pump_t *p, uint32_t pair_id, uint8_t role);
/*
 * Become the active pod. Refused unless paired (matching pair id), docked, filled, not on a
 * charger, fault free (except an old wear fault) and not already active. Re-sending the same
 * activation id to an already active pod is an OK no-op (lost response). Delivery stays
 * SUSPENDED: the app primes the connector, then sends Resume (which also starts the temp basal).
 */
op_err_t op_pump_activate(op_pump_t *p, const op_activate_args_t *a);
/* Stop delivering and become released. Idempotent. *delivered_since_activation_mu may be NULL. */
op_err_t op_pump_release(op_pump_t *p, uint32_t pair_id, uint32_t *delivered_since_activation_mu);
/* Boot: restore what the platform persisted. The pod comes up suspended even if it was active. */
void op_pump_restore_pod(op_pump_t *p, uint32_t pair_id, uint8_t role, bool active, uint32_t activation_id,
                         uint64_t wear_ms);

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
