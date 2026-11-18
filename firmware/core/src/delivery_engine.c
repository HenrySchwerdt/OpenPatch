#include "op/delivery_engine.h"

#include <string.h>

void op_de_init(op_de_t *de)
{
    memset(de, 0, sizeof *de);
    de->suspended = true; /* safe default: nothing runs until explicitly resumed */
}

op_err_t op_de_validate_schedule(const op_basal_schedule_t *s)
{
    if (!s || s->count == 0 || s->count > OP_BASAL_SEGMENTS_MAX) return OP_ERR_BAD_ARG;
    if (s->seg[0].start_slot != 0) return OP_ERR_BAD_ARG;
    for (uint8_t i = 0; i < s->count; i++) {
        if (s->seg[i].start_slot >= OP_SLOTS_PER_DAY) return OP_ERR_BAD_ARG;
        if (i > 0 && s->seg[i].start_slot <= s->seg[i - 1].start_slot) return OP_ERR_BAD_ARG;
    }
    return OP_OK;
}

op_err_t op_de_set_schedule(op_de_t *de, const op_basal_schedule_t *s)
{
    op_err_t e = op_de_validate_schedule(s);
    if (e != OP_OK) return e;
    de->schedule = *s;
    de->has_schedule = true;
    return OP_OK;
}

void op_de_set_time_of_day(op_de_t *de, uint32_t ms_of_day) { de->ms_of_day = ms_of_day % OP_DAY_MS; }

void op_de_comm_heartbeat(op_de_t *de) { de->ms_since_comm = 0; }

static uint32_t basal_rate_at(const op_de_t *de, uint32_t ms_of_day)
{
    if (!de->has_schedule) return 0;
    uint32_t slot = ms_of_day / OP_SLOT_MS;
    uint32_t rate = de->schedule.seg[0].rate_mu_h;
    for (uint8_t i = 1; i < de->schedule.count; i++) {
        if (de->schedule.seg[i].start_slot > slot) break;
        rate = de->schedule.seg[i].rate_mu_h;
    }
    return rate;
}

op_err_t op_de_start_temp_basal(op_de_t *de, uint32_t rate_mu_h, uint32_t duration_min)
{
    if (duration_min == 0 || duration_min > OP_TEMP_MAX_MIN || duration_min % OP_TEMP_GRANULARITY_MIN != 0)
        return OP_ERR_BAD_ARG;
    if (de->suspended) return OP_ERR_SUSPENDED;
    de->temp_active = true;
    de->temp_rate_mu_h = rate_mu_h;
    de->temp_remaining_ms = duration_min * 60000u;
    return OP_OK;
}

bool op_de_cancel_temp_basal(op_de_t *de)
{
    bool was = de->temp_active;
    de->temp_active = false;
    de->temp_remaining_ms = 0;
    return was;
}

op_err_t op_de_start_bolus(op_de_t *de, uint32_t amount_mu)
{
    if (amount_mu == 0) return OP_ERR_BAD_ARG;
    if (de->suspended) return OP_ERR_SUSPENDED;
    if (de->bolus_active) return OP_ERR_BUSY;
    de->bolus_active = true;
    de->bolus_remaining_scaled = (int64_t)amount_mu * OP_SCALED_PER_MU;
    return OP_OK;
}

uint32_t op_de_cancel_bolus(op_de_t *de)
{
    if (!de->bolus_active) return 0;
    uint32_t left = op_de_bolus_remaining_mu(de);
    de->bolus_active = false;
    de->bolus_remaining_scaled = 0;
    return left;
}

void op_de_suspend(op_de_t *de)
{
    op_de_cancel_bolus(de);
    op_de_cancel_temp_basal(de);
    de->suspended = true;
}

op_err_t op_de_resume(op_de_t *de)
{
    de->suspended = false;
    return OP_OK;
}

/* Largest time slice in which rate, bolus state and comm-loss state are constant. */
static uint32_t next_chunk(const op_de_t *de, uint32_t dt_ms)
{
    uint32_t chunk = dt_ms;
    uint32_t to_slot = OP_SLOT_MS - (de->ms_of_day % OP_SLOT_MS);
    if (to_slot < chunk) chunk = to_slot;
    if (de->temp_active) {
        if (de->temp_remaining_ms < chunk) chunk = de->temp_remaining_ms;
        if (de->ms_since_comm < OP_COMM_LOSS_TEMP_MS) {
            uint32_t left = OP_COMM_LOSS_TEMP_MS - de->ms_since_comm;
            if (left < chunk) chunk = left;
        }
    }
    return chunk;
}

uint32_t op_de_tick(op_de_t *de, uint32_t dt_ms)
{
    uint32_t steps_total = 0;
    while (dt_ms > 0) {
        if (de->temp_active && de->ms_since_comm >= OP_COMM_LOSS_TEMP_MS) {
            op_de_cancel_temp_basal(de);
            de->events |= OP_DE_EV_TEMP_COMM_FALLBACK;
        }
        uint32_t chunk = next_chunk(de, dt_ms);
        if (chunk == 0) chunk = 1; /* defensive: never spin */

        int64_t inc = 0;
        if (de->bolus_active) { /* suspend cancels the bolus, so never active while suspended */
            inc = (int64_t)OP_BOLUS_RATE_MU_H * chunk;
            if (inc >= de->bolus_remaining_scaled) {
                inc = de->bolus_remaining_scaled;
                de->bolus_active = false;
                de->events |= OP_DE_EV_BOLUS_DONE;
            }
            de->bolus_remaining_scaled -= inc;
            de->scheduled_scaled += inc;
        } else {
            uint32_t rate = de->temp_active ? de->temp_rate_mu_h : basal_rate_at(de, de->ms_of_day);
            inc = (int64_t)rate * chunk;
            de->scheduled_scaled += inc; /* counted even while suspended: shows the deficit */
        }
        if (!de->suspended) {
            de->acc += inc;
            int64_t steps = de->acc / OP_SCALED_PER_STEP;
            de->acc -= steps * OP_SCALED_PER_STEP;
            steps_total += (uint32_t)steps;
        }

        de->ms_of_day = (de->ms_of_day + chunk) % OP_DAY_MS;
        if (de->ms_since_comm < OP_COMM_LOSS_TEMP_MS) {
            uint32_t sum = de->ms_since_comm + chunk;
            de->ms_since_comm = sum > OP_COMM_LOSS_TEMP_MS ? OP_COMM_LOSS_TEMP_MS : sum;
        }
        if (de->temp_active) {
            de->temp_remaining_ms -= chunk;
            if (de->temp_remaining_ms == 0) {
                de->temp_active = false;
                de->events |= OP_DE_EV_TEMP_DONE;
            }
        }
        dt_ms -= chunk;
    }
    de->requested_steps += steps_total;
    de->pending_steps += steps_total;
    return steps_total;
}

void op_de_commit(op_de_t *de, uint32_t executed)
{
    if (executed > de->pending_steps) executed = de->pending_steps;
    de->delivered_steps += executed;
    de->dropped_steps += de->pending_steps - executed;
    de->pending_steps = 0;
}

uint32_t op_de_take_events(op_de_t *de)
{
    uint32_t e = de->events;
    de->events = 0;
    return e;
}

uint32_t op_de_current_rate_mu_h(const op_de_t *de)
{
    return de->temp_active ? de->temp_rate_mu_h : basal_rate_at(de, de->ms_of_day);
}

uint32_t op_de_bolus_remaining_mu(const op_de_t *de)
{
    if (!de->bolus_active) return 0;
    return (uint32_t)((de->bolus_remaining_scaled + OP_SCALED_PER_MU - 1) / OP_SCALED_PER_MU);
}

uint32_t op_de_temp_remaining_min(const op_de_t *de)
{
    return de->temp_active ? (de->temp_remaining_ms + 59999u) / 60000u : 0;
}

void op_de_report(const op_de_t *de, op_de_report_t *out)
{
    out->scheduled_mu = (uint32_t)(de->scheduled_scaled / OP_SCALED_PER_MU);
    out->delivered_mu = op_steps_to_mu(de->delivered_steps);
    out->delivered_steps = de->delivered_steps;
    out->dropped_steps = de->dropped_steps;
}
