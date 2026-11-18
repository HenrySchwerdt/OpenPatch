/*
 * Persistent state (Zephyr settings on NVS, "storage" partition), closing protocol open issue #3:
 *   op/evt   event-ID ceiling. IDs stay strictly increasing across resets: the stored ceiling is
 *            always >= every issued ID; after a reset the log continues AT the ceiling (gap).
 *   op/seq   highest accepted command sequence number (replay protection across resets)
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
};

/* settings_subsys_init() + load; fills *out (defaults on a virgin device). */
int persist_init(struct persist_state *out);
/* Apply the restored reservoir to a freshly initialised pump. */
void persist_apply_reservoir(op_pump_t *p, const struct persist_state *st);
/* Write what changed since the last call (cheap when nothing did). Call after every tick/command. */
void persist_sync(const op_pump_t *p);
/* op_ccm_ops_t.on_seq_accepted hook */
void persist_save_seq(void *ctx, uint16_t seq);

#endif
