/*
 * Persistent state (Zephyr settings on NVS, "storage" partition), closing protocol open issue #3:
 *   op/evt   event-ID ceiling. IDs stay strictly increasing across resets: the stored ceiling is
 *            always >= every issued ID; after a reset the log continues AT the ceiling (gap).
 *   op/seq   highest accepted command sequence number (replay protection across resets)
 *   op/pod   two-pod state: pair id, role, active flag, activation id, wear time. Wear is stored as
 *            an UPPER bound (ceiling, refreshed every few minutes), so a reset can only make the pod
 *            look older, never younger.
 *   op/res   reservoir fill + consumed steps, stored with a safety margin (the model can only
 *            err towards "less insulin left" after a power loss)
 * Main thread only.
 */
#ifndef PERSIST_H
#define PERSIST_H

#include <stdbool.h>
#include <stdint.h>

#include "op/pump_controller.h"

struct persist_state {
    uint32_t next_event_id; /* 1 on a virgin device */
    bool seq_valid;
    uint16_t last_seq;
    bool res_valid;
    uint32_t res_fill_mu;
    uint32_t res_consumed_steps;
    bool pod_valid;
    uint32_t pod_pair_id;
    uint8_t pod_role;
    bool pod_active;
    uint32_t pod_activation_id;
    uint32_t pod_wear_ceiling_s;
    bool cal_stored;        /* a calibration record exists in flash */
    op_drive_cal_t cal;     /* as read; NOT validated here */
};

/* settings_subsys_init() + load; fills *out (defaults on a virgin device). */
int persist_init(struct persist_state *out);
/*
 * Drive calibration for op_pump_init(). First boot stores the build-time preset (Kconfig
 * OPENPATCH_DRIVE_*). Later boots return the stored record only if it is valid AND identical to
 * this build's preset; otherwise NULL, which leaves the pump without delivery.
 */
const op_drive_cal_t *persist_drive_cal(const struct persist_state *st);
/* Apply the restored pair / activation / wear state to a freshly initialised pump. */
void persist_apply_pod(op_pump_t *p, const struct persist_state *st);
/* Apply the restored reservoir to a freshly initialised pump. */
void persist_apply_reservoir(op_pump_t *p, const struct persist_state *st);
/* Write what changed since the last call (cheap when nothing did). Call after every tick/command. */
void persist_sync(const op_pump_t *p);
/* op_ccm_ops_t.on_seq_accepted hook */
void persist_save_seq(void *ctx, uint16_t seq);

#endif
