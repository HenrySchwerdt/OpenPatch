#include <string.h>

#include "op/openpatch_proto.h"

#define EVENT_TLV_LEN 17u
#define POD_INFO_TLV_LEN 10u /* u32 pair id, u8 role, u8 delivery state, u32 wear s */
#define DRIVE_CAL_TLV_LEN 10u /* u16 id, u32 uU/step, u16 steps/rev, u16 ratio x100 */

static uint16_t rd16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static uint32_t rd32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static void wr16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
}
static void wr32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
    p[2] = (uint8_t)(v >> 16);
    p[3] = (uint8_t)(v >> 24);
}

static bool known_cmd(uint8_t t) { return t >= OP_CMD_GET_STATUS && t <= OP_CMD_RELEASE; }

/* ---- commands -------------------------------------------------------------- */
int op_cmd_encode_payload(const op_cmd_t *c, uint8_t *out, size_t cap)
{
    if (!c || !out) return -OP_ERR_BAD_ARG;
    if (!known_cmd(c->type)) return -OP_ERR_UNSUPPORTED;
    op_tlv_w_t w;
    op_tlv_w_init(&w, out, cap);
    if (c->has_time_of_day) op_tlv_put_u32(&w, OP_TAG_TIME_OF_DAY_MS, c->time_of_day_ms);
    switch (c->type) {
    case OP_CMD_SET_BASAL_SCHEDULE:
        for (uint8_t i = 0; i < c->u.basal.count && i < OP_BASAL_SEGMENTS_MAX; i++) {
            uint8_t seg[3] = {c->u.basal.seg[i].start_slot, (uint8_t)c->u.basal.seg[i].rate_mu_h,
                              (uint8_t)(c->u.basal.seg[i].rate_mu_h >> 8)};
            op_tlv_put(&w, OP_TAG_BASAL_SEG, seg, 3);
        }
        break;
    case OP_CMD_SET_TEMP_BASAL:
        op_tlv_put_u16(&w, OP_TAG_RATE_MU_H, (uint16_t)c->u.temp.rate_mu_h);
        op_tlv_put_u16(&w, OP_TAG_DURATION_MIN, (uint16_t)c->u.temp.duration_min);
        break;
    case OP_CMD_BOLUS:
        op_tlv_put_u32(&w, OP_TAG_AMOUNT_MU, c->u.bolus.amount_mu);
        break;
    case OP_CMD_FILL_PRIME:
        op_tlv_put_u8(&w, OP_TAG_SUB_OP, c->u.fill.sub_op);
        if (c->u.fill.sub_op == OP_SUBOP_FILL) op_tlv_put_u32(&w, OP_TAG_FILL_MU, c->u.fill.fill_mu);
        else op_tlv_put_u16(&w, OP_TAG_PRIME_STEPS, c->u.fill.prime_steps);
        break;
    case OP_CMD_ACKNOWLEDGE:
        op_tlv_put_u16(&w, OP_TAG_FAULT_MASK, c->u.ack.fault_mask);
        break;
    case OP_CMD_GET_HISTORY:
        op_tlv_put_u32(&w, OP_TAG_FROM_ID, c->u.history.from_id);
        op_tlv_put_u8(&w, OP_TAG_MAX_EVENTS, c->u.history.max_events);
        break;
    case OP_CMD_SET_PAIRING:
        op_tlv_put_u32(&w, OP_TAG_PAIR_ID, c->u.pairing.pair_id);
        op_tlv_put_u8(&w, OP_TAG_ROLE, c->u.pairing.role);
        break;
    case OP_CMD_RELEASE:
        op_tlv_put_u32(&w, OP_TAG_PAIR_ID, c->u.release.pair_id);
        break;
    case OP_CMD_ACTIVATE:
        op_tlv_put_u32(&w, OP_TAG_PAIR_ID, c->u.activate.pair_id);
        op_tlv_put_u32(&w, OP_TAG_ACTIVATION_ID, c->u.activate.activation_id);
        for (uint8_t i = 0; i < c->u.activate.schedule.count && i < OP_BASAL_SEGMENTS_MAX; i++) {
            const op_basal_seg_t *g = &c->u.activate.schedule.seg[i];
            uint8_t seg[3] = {g->start_slot, (uint8_t)g->rate_mu_h, (uint8_t)(g->rate_mu_h >> 8)};
            op_tlv_put(&w, OP_TAG_BASAL_SEG, seg, 3);
        }
        if (c->u.activate.has_temp) {
            op_tlv_put_u16(&w, OP_TAG_RATE_MU_H, (uint16_t)c->u.activate.temp_rate_mu_h);
            op_tlv_put_u16(&w, OP_TAG_DURATION_MIN, (uint16_t)c->u.activate.temp_remaining_min);
        }
        break;
    default:
        break; /* no arguments */
    }
    return w.overflow ? -OP_ERR_TOO_LARGE : (int)w.len;
}

typedef struct {
    bool amount, rate, duration, sub_op, fill, prime, pair_id, role, activation_id;
} seen_t;

static bool take_cmd_tag(op_cmd_t *out, seen_t *seen, uint8_t tag, const uint8_t *v, uint8_t vl)
{
    switch (tag) {
    case OP_TAG_TIME_OF_DAY_MS:
        if (vl != 4) return false;
        out->has_time_of_day = true;
        out->time_of_day_ms = rd32(v);
        return true;
    case OP_TAG_BASAL_SEG:
        if (out->type == OP_CMD_ACTIVATE) {
            op_basal_schedule_t *s = &out->u.activate.schedule;
            if (vl != 3 || s->count >= OP_BASAL_SEGMENTS_MAX) return false;
            s->seg[s->count++] = (op_basal_seg_t){v[0], rd16(v + 1)};
            return true;
        }
        if (out->type != OP_CMD_SET_BASAL_SCHEDULE) return true;
        if (vl != 3 || out->u.basal.count >= OP_BASAL_SEGMENTS_MAX) return false;
        out->u.basal.seg[out->u.basal.count++] = (op_basal_seg_t){v[0], rd16(v + 1)};
        return true;
    case OP_TAG_PAIR_ID:
        if (vl != 4) return false;
        if (out->type == OP_CMD_SET_PAIRING) out->u.pairing.pair_id = rd32(v);
        else if (out->type == OP_CMD_RELEASE) out->u.release.pair_id = rd32(v);
        else if (out->type == OP_CMD_ACTIVATE) out->u.activate.pair_id = rd32(v);
        else return true;
        seen->pair_id = true;
        return true;
    case OP_TAG_ROLE:
        if (out->type != OP_CMD_SET_PAIRING) return true;
        if (vl != 1) return false;
        out->u.pairing.role = v[0];
        seen->role = true;
        return true;
    case OP_TAG_ACTIVATION_ID:
        if (out->type != OP_CMD_ACTIVATE) return true;
        if (vl != 4) return false;
        out->u.activate.activation_id = rd32(v);
        seen->activation_id = true;
        return true;
    case OP_TAG_RATE_MU_H:
        if (out->type == OP_CMD_ACTIVATE) {
            if (vl != 2) return false;
            out->u.activate.temp_rate_mu_h = rd16(v);
            seen->rate = true;
            return true;
        }
        if (out->type != OP_CMD_SET_TEMP_BASAL) return true;
        if (vl != 2) return false;
        out->u.temp.rate_mu_h = rd16(v);
        seen->rate = true;
        return true;
    case OP_TAG_DURATION_MIN:
        if (out->type == OP_CMD_ACTIVATE) {
            if (vl != 2) return false;
            out->u.activate.temp_remaining_min = rd16(v);
            seen->duration = true;
            return true;
        }
        if (out->type != OP_CMD_SET_TEMP_BASAL) return true;
        if (vl != 2) return false;
        out->u.temp.duration_min = rd16(v);
        seen->duration = true;
        return true;
    case OP_TAG_AMOUNT_MU:
        if (out->type != OP_CMD_BOLUS) return true;
        if (vl != 4) return false;
        out->u.bolus.amount_mu = rd32(v);
        seen->amount = true;
        return true;
    case OP_TAG_SUB_OP:
        if (out->type != OP_CMD_FILL_PRIME) return true;
        if (vl != 1) return false;
        out->u.fill.sub_op = v[0];
        seen->sub_op = true;
        return true;
    case OP_TAG_FILL_MU:
        if (out->type != OP_CMD_FILL_PRIME) return true;
        if (vl != 4) return false;
        out->u.fill.fill_mu = rd32(v);
        seen->fill = true;
        return true;
    case OP_TAG_PRIME_STEPS:
        if (out->type != OP_CMD_FILL_PRIME) return true;
        if (vl != 2) return false;
        out->u.fill.prime_steps = rd16(v);
        seen->prime = true;
        return true;
    case OP_TAG_FAULT_MASK:
        if (out->type != OP_CMD_ACKNOWLEDGE) return true;
        if (vl != 2) return false;
        out->u.ack.fault_mask = rd16(v);
        return true;
    case OP_TAG_FROM_ID:
        if (out->type != OP_CMD_GET_HISTORY) return true;
        if (vl != 4) return false;
        out->u.history.from_id = rd32(v);
        return true;
    case OP_TAG_MAX_EVENTS:
        if (out->type != OP_CMD_GET_HISTORY) return true;
        if (vl != 1) return false;
        out->u.history.max_events = v[0];
        return true;
    default:
        return true; /* unknown tags are skipped (forward compatibility) */
    }
}

int op_cmd_decode(uint8_t type, uint16_t seq, const uint8_t *payload, size_t len, op_cmd_t *out)
{
    if (!out) return -OP_ERR_BAD_ARG;
    memset(out, 0, sizeof *out);
    if (!known_cmd(type)) return -OP_ERR_UNSUPPORTED;
    out->type = type;
    out->seq = seq;
    if (type == OP_CMD_ACKNOWLEDGE) out->u.ack.fault_mask = 0xFFFF;
    if (type == OP_CMD_GET_HISTORY) out->u.history.max_events = OP_HIST_MAX_PER_RESPONSE;

    seen_t seen = {0};
    op_tlv_r_t r;
    op_tlv_r_init(&r, payload, len);
    uint8_t tag, vl;
    const uint8_t *v;
    while (op_tlv_next(&r, &tag, &v, &vl)) {
        if (!take_cmd_tag(out, &seen, tag, v, vl)) return -OP_ERR_FRAME;
    }
    if (r.error) return -OP_ERR_FRAME;

    switch (type) {
    case OP_CMD_SET_BASAL_SCHEDULE:
        if (out->u.basal.count == 0) return -OP_ERR_FRAME;
        break;
    case OP_CMD_SET_TEMP_BASAL:
        if (!seen.rate || !seen.duration) return -OP_ERR_FRAME;
        break;
    case OP_CMD_BOLUS:
        if (!seen.amount) return -OP_ERR_FRAME;
        break;
    case OP_CMD_SET_PAIRING:
        if (!seen.pair_id || !seen.role) return -OP_ERR_FRAME;
        break;
    case OP_CMD_RELEASE:
        if (!seen.pair_id) return -OP_ERR_FRAME;
        break;
    case OP_CMD_ACTIVATE:
        if (!seen.pair_id || !seen.activation_id || out->u.activate.schedule.count == 0) return -OP_ERR_FRAME;
        if (seen.rate != seen.duration) return -OP_ERR_FRAME; /* temp basal needs both or neither */
        out->u.activate.has_temp = seen.rate && seen.duration;
        break;
    case OP_CMD_FILL_PRIME:
        if (!seen.sub_op) return -OP_ERR_FRAME;
        break;
    default:
        break;
    }
    return 0;
}

/* ---- responses ---------------------------------------------------------------- */
static void put_event(op_tlv_w_t *w, const op_event_t *e)
{
    uint8_t b[EVENT_TLV_LEN];
    wr32(b, e->id);
    wr32(b + 4, e->time_s);
    b[8] = e->type;
    wr32(b + 9, (uint32_t)e->a);
    wr32(b + 13, (uint32_t)e->b);
    op_tlv_put(w, OP_TAG_HISTORY_EVENT, b, EVENT_TLV_LEN);
}

int op_rsp_encode_payload(const op_rsp_t *r, uint8_t *out, size_t cap)
{
    if (!r || !out) return -OP_ERR_BAD_ARG;
    op_tlv_w_t w;
    op_tlv_w_init(&w, out, cap);
    op_tlv_put_u8(&w, OP_TAG_RESULT, r->result);
    if (r->has_status) {
        const op_status_t *s = &r->status;
        op_tlv_put_u16(&w, OP_TAG_STATE_FLAGS, s->flags);
        op_tlv_put_u16(&w, OP_TAG_FAULT_MASK, s->faults);
        op_tlv_put_u32(&w, OP_TAG_RESERVOIR_MU, s->reservoir_mu);
        op_tlv_put_u16(&w, OP_TAG_BATTERY_MV, s->battery_mv);
        op_tlv_put_u32(&w, OP_TAG_BOLUS_REMAINING_MU, s->bolus_remaining_mu);
        op_tlv_put_u16(&w, OP_TAG_TEMP_RATE_MU_H, s->temp_rate_mu_h);
        op_tlv_put_u16(&w, OP_TAG_TEMP_REMAINING_MIN, s->temp_remaining_min);
        op_tlv_put_u16(&w, OP_TAG_CURRENT_RATE_MU_H, s->current_rate_mu_h);
        op_tlv_put_u32(&w, OP_TAG_DELIVERED_MU, s->delivered_mu);
        op_tlv_put_u32(&w, OP_TAG_SCHEDULED_MU, s->scheduled_mu);
        op_tlv_put_u32(&w, OP_TAG_NEXT_EVENT_ID, s->next_event_id);
        op_tlv_put_u16(&w, OP_TAG_FW_VERSION, s->fw_version);
        op_tlv_put_u16(&w, OP_TAG_LAST_SEQ, s->last_seq);
        uint8_t cal[DRIVE_CAL_TLV_LEN];
        wr16(cal, s->cal_drive_id);
        wr32(cal + 2, s->cal_uu_per_step);
        wr16(cal + 6, s->cal_steps_per_rev);
        wr16(cal + 8, s->cal_gear_ratio_x100);
        op_tlv_put(&w, OP_TAG_DRIVE_CAL, cal, DRIVE_CAL_TLV_LEN);
        uint8_t pod[POD_INFO_TLV_LEN];
        wr32(pod, s->pair_id);
        pod[4] = s->role;
        pod[5] = s->delivery_state;
        wr32(pod + 6, s->wear_s);
        op_tlv_put(&w, OP_TAG_POD_INFO, pod, POD_INFO_TLV_LEN);
    }
    if (r->has_act_delivered) op_tlv_put_u32(&w, OP_TAG_ACT_DELIVERED_MU, r->act_delivered_mu);
    if (r->has_history) {
        op_tlv_put_u32(&w, OP_TAG_NEXT_EVENT_ID, r->next_event_id);
        op_tlv_put_u32(&w, OP_TAG_OLDEST_EVENT_ID, r->oldest_event_id);
        for (uint8_t i = 0; i < r->n_events && i < OP_HIST_MAX_PER_RESPONSE; i++) put_event(&w, &r->events[i]);
    }
    return w.overflow ? -OP_ERR_TOO_LARGE : (int)w.len;
}

static bool take_rsp_tag(op_rsp_t *o, uint8_t type, uint8_t tag, const uint8_t *v, uint8_t vl, bool *have_result)
{
    op_status_t *s = &o->status;
    switch (tag) {
    case OP_TAG_RESULT:
        if (vl != 1) return false;
        o->result = v[0];
        *have_result = true;
        return true;
    case OP_TAG_STATE_FLAGS:
        if (vl != 2) return false;
        s->flags = rd16(v);
        o->has_status = true;
        return true;
    case OP_TAG_FAULT_MASK:
        if (vl != 2) return false;
        s->faults = rd16(v);
        return true;
    case OP_TAG_RESERVOIR_MU:
        if (vl != 4) return false;
        s->reservoir_mu = rd32(v);
        return true;
    case OP_TAG_BATTERY_MV:
        if (vl != 2) return false;
        s->battery_mv = rd16(v);
        return true;
    case OP_TAG_BOLUS_REMAINING_MU:
        if (vl != 4) return false;
        s->bolus_remaining_mu = rd32(v);
        return true;
    case OP_TAG_TEMP_RATE_MU_H:
        if (vl != 2) return false;
        s->temp_rate_mu_h = rd16(v);
        return true;
    case OP_TAG_TEMP_REMAINING_MIN:
        if (vl != 2) return false;
        s->temp_remaining_min = rd16(v);
        return true;
    case OP_TAG_CURRENT_RATE_MU_H:
        if (vl != 2) return false;
        s->current_rate_mu_h = rd16(v);
        return true;
    case OP_TAG_DELIVERED_MU:
        if (vl != 4) return false;
        s->delivered_mu = rd32(v);
        return true;
    case OP_TAG_SCHEDULED_MU:
        if (vl != 4) return false;
        s->scheduled_mu = rd32(v);
        return true;
    case OP_TAG_FW_VERSION:
        if (vl != 2) return false;
        s->fw_version = rd16(v);
        return true;
    case OP_TAG_LAST_SEQ:
        if (vl != 2) return false;
        s->last_seq = rd16(v);
        return true;
    case OP_TAG_DRIVE_CAL:
        if (vl != DRIVE_CAL_TLV_LEN) return false;
        s->cal_drive_id = rd16(v);
        s->cal_uu_per_step = rd32(v + 2);
        s->cal_steps_per_rev = rd16(v + 6);
        s->cal_gear_ratio_x100 = rd16(v + 8);
        return true;
    case OP_TAG_POD_INFO:
        if (vl != POD_INFO_TLV_LEN) return false;
        s->pair_id = rd32(v);
        s->role = v[4];
        s->delivery_state = v[5];
        s->wear_s = rd32(v + 6);
        return true;
    case OP_TAG_ACT_DELIVERED_MU:
        if (vl != 4) return false;
        o->has_act_delivered = true;
        o->act_delivered_mu = rd32(v);
        return true;
    case OP_TAG_NEXT_EVENT_ID:
        if (vl != 4) return false;
        s->next_event_id = rd32(v);
        o->next_event_id = rd32(v);
        return true;
    case OP_TAG_OLDEST_EVENT_ID:
        if (vl != 4) return false;
        o->oldest_event_id = rd32(v);
        o->has_history = type == OP_CMD_GET_HISTORY;
        return true;
    case OP_TAG_HISTORY_EVENT:
        if (vl != EVENT_TLV_LEN || o->n_events >= OP_HIST_MAX_PER_RESPONSE) return false;
        o->events[o->n_events++] = (op_event_t){rd32(v), rd32(v + 4), v[8], (int32_t)rd32(v + 9), (int32_t)rd32(v + 13)};
        return true;
    default:
        return true;
    }
}

int op_rsp_decode(uint8_t type, uint16_t seq, const uint8_t *payload, size_t len, op_rsp_t *out)
{
    if (!out) return -OP_ERR_BAD_ARG;
    memset(out, 0, sizeof *out);
    out->type = type;
    out->seq = seq;
    bool have_result = false;
    op_tlv_r_t r;
    op_tlv_r_init(&r, payload, len);
    uint8_t tag, vl;
    const uint8_t *v;
    while (op_tlv_next(&r, &tag, &v, &vl)) {
        if (!take_rsp_tag(out, type, tag, v, vl, &have_result)) return -OP_ERR_FRAME;
    }
    if (r.error || !have_result) return -OP_ERR_FRAME;
    return 0;
}
