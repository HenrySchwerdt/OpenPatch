/* Reservoir model: fill volume, consumed steps, remaining units, low alarm. */
#ifndef OP_RESERVOIR_MODEL_H
#define OP_RESERVOIR_MODEL_H

#include "op/op_types.h"

typedef struct {
    uint32_t capacity_mu;
    uint32_t uu_per_step;    /* drive calibration; 0 = none -> nothing is left */
    uint32_t fill_mu;
    uint32_t consumed_steps; /* since last fill (delivery + prime) */
    uint32_t low_threshold_mu;
    bool filled;
} op_res_t;

void op_res_init(op_res_t *r, uint32_t capacity_mu, uint32_t uu_per_step);
/* fill_mu in (0, capacity]; resets consumption. */
op_err_t op_res_fill(op_res_t *r, uint32_t fill_mu);
op_err_t op_res_set_low_threshold(op_res_t *r, uint32_t mu);
void op_res_consume(op_res_t *r, uint32_t steps);
uint32_t op_res_remaining_mu(const op_res_t *r);   /* conservative (floor) */
bool op_res_is_empty(const op_res_t *r);            /* filled and nothing left */
bool op_res_is_low(const op_res_t *r);              /* filled and <= threshold */

#endif
