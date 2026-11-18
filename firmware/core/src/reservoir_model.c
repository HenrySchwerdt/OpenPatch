#include "op/reservoir_model.h"

#include <string.h>

void op_res_init(op_res_t *r, uint32_t capacity_mu, uint32_t uu_per_step)
{
    memset(r, 0, sizeof *r);
    r->uu_per_step = uu_per_step;
    r->capacity_mu = capacity_mu;
    r->low_threshold_mu = OP_DEFAULT_LOW_RESERVOIR_MU;
}

op_err_t op_res_fill(op_res_t *r, uint32_t fill_mu)
{
    if (fill_mu == 0) return OP_ERR_BAD_ARG;
    if (fill_mu > r->capacity_mu) return OP_ERR_LIMIT;
    r->fill_mu = fill_mu;
    r->consumed_steps = 0;
    r->filled = true;
    return OP_OK;
}

op_err_t op_res_set_low_threshold(op_res_t *r, uint32_t mu)
{
    if (mu > r->capacity_mu) return OP_ERR_BAD_ARG;
    r->low_threshold_mu = mu;
    return OP_OK;
}

void op_res_consume(op_res_t *r, uint32_t steps)
{
    uint64_t sum = (uint64_t)r->consumed_steps + steps;
    r->consumed_steps = sum > UINT32_MAX ? UINT32_MAX : (uint32_t)sum;
}

uint32_t op_res_remaining_mu(const op_res_t *r)
{
    if (!r->filled || r->uu_per_step == 0) return 0;
    uint64_t fill_uu = (uint64_t)r->fill_mu * 1000ull;
    uint64_t used_uu = (uint64_t)r->consumed_steps * r->uu_per_step;
    return used_uu >= fill_uu ? 0 : (uint32_t)((fill_uu - used_uu) / 1000ull);
}

bool op_res_is_empty(const op_res_t *r) { return r->filled && op_res_remaining_mu(r) == 0; }

bool op_res_is_low(const op_res_t *r) { return r->filled && op_res_remaining_mu(r) <= r->low_threshold_mu; }
