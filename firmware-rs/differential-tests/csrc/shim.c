/*
 * Flat C ABI shim over the C reference core (firmware/core, NOT modified) for the Rust
 * differential tests. HOST ONLY. Test project: not a medical device.
 *
 * The mock HAL is a port of firmware/tests/mock_hal.c (same arithmetic).
 *
 * Flat command layout (u32 array, SHIM_CMD_LEN):
 *   0 type 1 seq 2 has_tod 3 tod 4 nseg 5..28 seg slot 29..52 seg rate 53 temp rate 54 temp duration
 *   55 bolus amount 56 sub_op 57 fill_mu 58 prime_steps 59 fault_mask 60 history from_id
 *   61 history max 62 pair_id 63 role 64 activation_id 65 act has_temp 66 act temp rate 67 act temp min
 * Flat response layout (u32 array, SHIM_RSP_LEN):
 *   0 type 1 seq 2 result 3 has_status 4 flags 5 faults 6 battery 7 temp_rate 8 temp_rem 9 cur_rate
 *   10 fw 11 reservoir 12 bolus_rem 13 delivered 14 scheduled 15 next_event_id 16 last_seq
 *   17 cal_id 18 cal_spr 19 cal_ratio 20 cal_uu 21 pair 22 wear_s 23 role 24 delivery_state
 *   25 has_act 26 act 27 has_hist 28 hist_next 29 hist_oldest 30 n_events 31.. events (5 each)
 */
#include "shim.h"

#include <stdlib.h>
#include <string.h>

#include "op/pump_controller.h"

/* ---------------------------------------------------------------- mock HAL (port) */
typedef struct {
    uint64_t now_ms;
    uint16_t battery_mv;
    int64_t enc_x100;
    uint32_t delivered_pct;
    int steps_limit;
    uint32_t total_steps;
    bool enabled;
    bool stepped_while_disabled;
    int kicks;
    int enable_calls;
    op_buzzer_t buzzer;
    bool docked;
    bool charger;
} mock_t;

static int m_step(void *c, uint32_t steps)
{
    mock_t *m = c;
    if (!m->enabled) m->stepped_while_disabled = true;
    uint32_t n = steps;
    if (m->steps_limit >= 0 && (uint32_t)m->steps_limit < n) n = (uint32_t)m->steps_limit;
    m->total_steps += n;
    m->enc_x100 += (int64_t)n * 16 * m->delivered_pct;
    return (int)n;
}
static void m_enable(void *c, bool e)
{
    mock_t *m = c;
    m->enabled = e;
    m->enable_calls++;
}
static int32_t m_enc(void *c) { return (int32_t)(((mock_t *)c)->enc_x100 / 100); }
static void m_kick(void *c) { ((mock_t *)c)->kicks++; }
static void m_buzz(void *c, op_buzzer_t p) { ((mock_t *)c)->buzzer = p; }
static uint16_t m_batt(void *c) { return ((mock_t *)c)->battery_mv; }
static uint64_t m_time(void *c) { return ((mock_t *)c)->now_ms; }
static bool m_docked(void *c) { return ((mock_t *)c)->docked; }
static bool m_charger(void *c) { return ((mock_t *)c)->charger; }

struct shim_sess {
    op_session_t s;
};
struct shim {
    mock_t m;
    op_hal_t hal;
    op_drive_cal_t cal;
    bool has_cal;
    op_pump_t pump;
    op_session_t sess;
};
struct shim_de {
    op_de_t de;
};
struct shim_res {
    op_res_t r;
};
struct shim_log {
    op_log_t l;
};

static const uint8_t SALT[4] = {0, 0, 0, 0};

/* ---------------------------------------------------------------- codec */
uint16_t shim_crc16(const uint8_t *d, size_t n) { return op_crc16(d, n); }

int shim_frame_encode(uint8_t version, uint8_t type, uint8_t flags, uint16_t seq, const uint8_t *payload,
                      uint16_t plen, uint8_t *out, size_t cap)
{
    op_frame_t f = {version, type, flags, seq, payload, plen};
    return op_frame_encode(&f, out, cap);
}

int shim_frame_decode(const uint8_t *in, size_t len, uint32_t out[8])
{
    op_frame_t f;
    int rc = op_frame_decode(in, len, &f);
    if (rc < 0) return rc;
    out[0] = f.version;
    out[1] = f.type;
    out[2] = f.flags;
    out[3] = f.seq;
    out[4] = f.payload_len;
    out[5] = (uint32_t)(f.payload - in);
    return 0;
}

shim_sess_t *shim_sess_new(void)
{
    shim_sess_t *s = calloc(1, sizeof *s);
    op_session_init(&s->s, NULL, SALT, true);
    return s;
}
void shim_sess_free(shim_sess_t *s) { free(s); }

static void cmd_to_flat(const op_cmd_t *c, uint32_t o[SHIM_CMD_LEN])
{
    memset(o, 0, SHIM_CMD_LEN * sizeof(uint32_t));
    o[0] = c->type;
    o[1] = c->seq;
    o[2] = c->has_time_of_day;
    o[3] = c->time_of_day_ms;
    const op_basal_schedule_t *sched = NULL;
    switch (c->type) {
    case OP_CMD_SET_BASAL_SCHEDULE: sched = &c->u.basal; break;
    case OP_CMD_SET_TEMP_BASAL:
        o[53] = c->u.temp.rate_mu_h;
        o[54] = c->u.temp.duration_min;
        break;
    case OP_CMD_BOLUS: o[55] = c->u.bolus.amount_mu; break;
    case OP_CMD_FILL_PRIME:
        o[56] = c->u.fill.sub_op;
        o[57] = c->u.fill.fill_mu;
        o[58] = c->u.fill.prime_steps;
        break;
    case OP_CMD_ACKNOWLEDGE: o[59] = c->u.ack.fault_mask; break;
    case OP_CMD_GET_HISTORY:
        o[60] = c->u.history.from_id;
        o[61] = c->u.history.max_events;
        break;
    case OP_CMD_SET_PAIRING:
        o[62] = c->u.pairing.pair_id;
        o[63] = c->u.pairing.role;
        break;
    case OP_CMD_RELEASE: o[62] = c->u.release.pair_id; break;
    case OP_CMD_ACTIVATE:
        sched = &c->u.activate.schedule;
        o[62] = c->u.activate.pair_id;
        o[64] = c->u.activate.activation_id;
        o[65] = c->u.activate.has_temp;
        o[66] = c->u.activate.temp_rate_mu_h;
        o[67] = c->u.activate.temp_remaining_min;
        break;
    default: break;
    }
    if (sched) {
        o[4] = sched->count;
        for (unsigned i = 0; i < sched->count && i < OP_BASAL_SEGMENTS_MAX; i++) {
            o[5 + i] = sched->seg[i].start_slot;
            o[29 + i] = sched->seg[i].rate_mu_h;
        }
    }
}

static void flat_to_cmd(const uint32_t o[SHIM_CMD_LEN], op_cmd_t *c)
{
    memset(c, 0, sizeof *c);
    c->type = (uint8_t)o[0];
    c->seq = (uint16_t)o[1];
    c->has_time_of_day = o[2] != 0;
    c->time_of_day_ms = o[3];
    op_basal_schedule_t *sched = NULL;
    switch (c->type) {
    case OP_CMD_SET_BASAL_SCHEDULE: sched = &c->u.basal; break;
    case OP_CMD_SET_TEMP_BASAL:
        c->u.temp.rate_mu_h = o[53];
        c->u.temp.duration_min = o[54];
        break;
    case OP_CMD_BOLUS: c->u.bolus.amount_mu = o[55]; break;
    case OP_CMD_FILL_PRIME:
        c->u.fill.sub_op = (uint8_t)o[56];
        c->u.fill.fill_mu = o[57];
        c->u.fill.prime_steps = (uint16_t)o[58];
        break;
    case OP_CMD_ACKNOWLEDGE: c->u.ack.fault_mask = (uint16_t)o[59]; break;
    case OP_CMD_GET_HISTORY:
        c->u.history.from_id = o[60];
        c->u.history.max_events = (uint8_t)o[61];
        break;
    case OP_CMD_SET_PAIRING:
        c->u.pairing.pair_id = o[62];
        c->u.pairing.role = (uint8_t)o[63];
        break;
    case OP_CMD_RELEASE: c->u.release.pair_id = o[62]; break;
    case OP_CMD_ACTIVATE:
        sched = &c->u.activate.schedule;
        c->u.activate.pair_id = o[62];
        c->u.activate.activation_id = o[64];
        c->u.activate.has_temp = o[65] != 0;
        c->u.activate.temp_rate_mu_h = o[66];
        c->u.activate.temp_remaining_min = o[67];
        break;
    default: break;
    }
    if (sched) {
        uint32_t n = o[4] > OP_BASAL_SEGMENTS_MAX ? OP_BASAL_SEGMENTS_MAX : o[4];
        sched->count = (uint8_t)n;
        for (uint32_t i = 0; i < n; i++) sched->seg[i] = (op_basal_seg_t){(uint8_t)o[5 + i], o[29 + i]};
    }
}

int shim_sess_decode(shim_sess_t *s, const uint8_t *in, size_t len, uint32_t out[SHIM_CMD_LEN])
{
    uint8_t plain[OP_FRAME_MAX];
    op_frame_t f;
    int rc = op_session_open(&s->s, in, len, &f, plain, sizeof plain);
    if (rc < 0) return rc;
    op_cmd_t cmd;
    int d = op_cmd_decode(f.type, f.seq, f.payload, f.payload_len, &cmd);
    if (d < 0) return d;
    cmd_to_flat(&cmd, out);
    return 0;
}

int shim_decode_payload(uint8_t type, uint16_t seq, const uint8_t *payload, size_t len, uint32_t out[SHIM_CMD_LEN])
{
    op_cmd_t cmd;
    int d = op_cmd_decode(type, seq, payload, len, &cmd);
    if (d < 0) return d;
    cmd_to_flat(&cmd, out);
    return 0;
}

int shim_encode_cmd(const uint32_t in[SHIM_CMD_LEN], uint8_t *out, size_t cap)
{
    op_cmd_t c;
    flat_to_cmd(in, &c);
    return op_cmd_encode_payload(&c, out, cap);
}

int shim_encode_rsp(const uint32_t o[SHIM_RSP_LEN], uint8_t *out, size_t cap)
{
    op_rsp_t r;
    memset(&r, 0, sizeof r);
    r.type = (uint8_t)o[0];
    r.seq = (uint16_t)o[1];
    r.result = (uint8_t)o[2];
    r.has_status = o[3] != 0;
    r.status.flags = (uint16_t)o[4];
    r.status.faults = (uint16_t)o[5];
    r.status.battery_mv = (uint16_t)o[6];
    r.status.temp_rate_mu_h = (uint16_t)o[7];
    r.status.temp_remaining_min = (uint16_t)o[8];
    r.status.current_rate_mu_h = (uint16_t)o[9];
    r.status.fw_version = (uint16_t)o[10];
    r.status.reservoir_mu = o[11];
    r.status.bolus_remaining_mu = o[12];
    r.status.delivered_mu = o[13];
    r.status.scheduled_mu = o[14];
    r.status.next_event_id = o[15];
    r.status.last_seq = (uint16_t)o[16];
    r.status.cal_drive_id = (uint16_t)o[17];
    r.status.cal_steps_per_rev = (uint16_t)o[18];
    r.status.cal_gear_ratio_x100 = (uint16_t)o[19];
    r.status.cal_uu_per_step = o[20];
    r.status.pair_id = o[21];
    r.status.wear_s = o[22];
    r.status.role = (uint8_t)o[23];
    r.status.delivery_state = (uint8_t)o[24];
    r.has_act_delivered = o[25] != 0;
    r.act_delivered_mu = o[26];
    r.has_history = o[27] != 0;
    r.next_event_id = o[28];
    r.oldest_event_id = o[29];
    r.n_events = (uint8_t)(o[30] > OP_HIST_MAX_PER_RESPONSE ? OP_HIST_MAX_PER_RESPONSE : o[30]);
    for (unsigned i = 0; i < r.n_events; i++) {
        const uint32_t *e = o + 31 + 5 * i;
        r.events[i] = (op_event_t){e[0], e[1], (uint8_t)e[2], (int32_t)e[3], (int32_t)e[4]};
    }
    return op_rsp_encode_payload(&r, out, cap);
}

/* ---------------------------------------------------------------- whole pump */
shim_t *shim_create(uint32_t cal_id, uint32_t capacity_mu, uint32_t next_event_id)
{
    shim_t *s = calloc(1, sizeof *s);
    s->m.battery_mv = 3900;
    s->m.delivered_pct = 100;
    s->m.steps_limit = -1;
    s->m.docked = true;
    s->hal = (op_hal_t){&s->m, m_step, m_enable, m_enc, m_kick, m_buzz, m_batt, m_time, m_docked, m_charger};
    s->has_cal = cal_id != 0 && op_drive_cal_preset((op_drive_id_t)cal_id, &s->cal) == OP_OK;
    op_pump_init(&s->pump, &s->hal, s->has_cal ? &s->cal : NULL, capacity_mu, next_event_id);
    op_session_init(&s->sess, NULL, SALT, true);
    return s;
}
void shim_destroy(shim_t *s) { free(s); }
void shim_new_session(shim_t *s) { op_session_init(&s->sess, NULL, SALT, true); }
void shim_set_time(shim_t *s, uint64_t ms) { s->m.now_ms = ms; }
void shim_set_docked(shim_t *s, int v) { s->m.docked = v != 0; }
void shim_set_charger(shim_t *s, int v) { s->m.charger = v != 0; }
void shim_set_battery(shim_t *s, uint16_t mv) { s->m.battery_mv = mv; }
void shim_set_delivered_pct(shim_t *s, uint32_t pct) { s->m.delivered_pct = pct; }
void shim_set_steps_limit(shim_t *s, int32_t lim) { s->m.steps_limit = lim; }
void shim_tick(shim_t *s) { op_pump_tick(&s->pump); }
int shim_handle_frame(shim_t *s, const uint8_t *in, size_t len, uint8_t *out, size_t cap)
{
    return op_pump_handle_frame(&s->pump, &s->sess, in, len, out, cap);
}
void shim_restore_pod(shim_t *s, uint32_t pair, uint8_t role, int active, uint32_t act_id, uint64_t wear_ms)
{
    op_pump_restore_pod(&s->pump, pair, role, active != 0, act_id, wear_ms);
}

void shim_mock(const shim_t *s, uint64_t o[SHIM_MOCK_LEN])
{
    const mock_t *m = &s->m;
    o[0] = m->total_steps;
    o[1] = (uint64_t)m->enable_calls;
    o[2] = (uint64_t)m->kicks;
    o[3] = (uint64_t)m->buzzer;
    o[4] = m->stepped_while_disabled;
    o[5] = m->enabled;
    o[6] = (uint64_t)m->enc_x100;
    o[7] = m->now_ms;
}

/* Snapshot layout is mirrored in src/ffi.rs (SNAP_*). */
void shim_snapshot(const shim_t *s, uint64_t o[SHIM_SNAP_LEN])
{
    const op_pump_t *p = &s->pump;
    memset(o, 0, SHIM_SNAP_LEN * sizeof(uint64_t));
    o[0] = p->sv.faults;
    o[1] = p->de.suspended;
    o[2] = p->de.temp_active;
    o[3] = p->de.temp_rate_mu_h;
    o[4] = (p->de.temp_remaining_ms + 59999u) / 60000u; /* minutes, rounded up (Rust has no ms accessor) */
    o[5] = p->de.bolus_active;
    o[6] = op_de_bolus_remaining_mu(&p->de); /* mU, rounded up (Rust has no scaled accessor) */
    o[7] = p->de.ms_of_day;
    o[8] = p->de.ms_since_comm;
    o[9] = (uint64_t)p->de.acc;
    o[10] = (uint64_t)p->de.scheduled_scaled;
    o[11] = p->de.requested_steps;
    o[12] = p->de.delivered_steps;
    o[13] = p->de.dropped_steps;
    o[14] = p->de.pending_steps;
    o[15] = p->res.fill_mu;
    o[16] = p->res.consumed_steps;
    o[17] = p->res.filled;
    o[18] = op_res_remaining_mu(&p->res);
    o[19] = p->pod.pair_id;
    o[20] = p->pod.role;
    o[21] = p->pod.active;
    o[22] = p->pod.activation_id;
    o[23] = p->pod.wear_ms;
    o[24] = p->pod.wear_warned;
    o[25] = p->pod.docked;
    o[26] = p->pod.pending_temp;
    o[27] = p->pod.pending_temp_rate_mu_h;
    o[28] = p->pod.pending_temp_min;
    o[29] = p->pod.act_base_steps;
    o[30] = p->pod.last_release_mu;
    o[31] = p->sv.docked;
    o[32] = p->sv.active;
    o[33] = p->sv.wear_expired;
    o[34] = p->sv.battery_low;
    o[35] = (uint64_t)p->sv.cmd_sub;
    o[36] = (uint64_t)(int64_t)p->sv.last_enc;
    o[37] = (uint64_t)(int64_t)p->sv.enc_base;
    o[38] = p->tick_overruns;
    o[39] = op_log_next_id(&p->log);
    o[40] = op_log_oldest_id(&p->log);
    o[41] = p->de.has_schedule;
    o[42] = p->cal_valid;
    o[46] = p->sv.calibrated;
    o[47] = op_de_current_rate_mu_h(&p->de);
    o[48] = p->sv.max_steps_per_min;
    o[49] = p->sv.max_bolus_mu;
    o[50] = p->de.schedule.count;
    for (unsigned i = 0; i < p->de.schedule.count && i < OP_BASAL_SEGMENTS_MAX; i++)
        o[64 + i] = ((uint64_t)p->de.schedule.seg[i].start_slot << 32) | p->de.schedule.seg[i].rate_mu_h;
    /* direct GetStatus (no frame) */
    op_status_t st;
    op_pump_get_status(p, &st);
    o[100] = st.flags;
    o[101] = st.faults;
    o[102] = st.reservoir_mu;
    o[103] = st.battery_mv;
    o[104] = st.bolus_remaining_mu;
    o[105] = st.temp_rate_mu_h;
    o[106] = st.temp_remaining_min;
    o[107] = st.current_rate_mu_h;
    o[108] = st.delivered_mu;
    o[109] = st.scheduled_mu;
    o[110] = st.next_event_id;
    o[111] = st.cal_uu_per_step;
    o[112] = st.pair_id;
    o[113] = st.wear_s;
    o[114] = st.role;
    o[115] = st.delivery_state;
}

int shim_log_event(const shim_t *s, uint32_t id, int64_t o[5])
{
    op_event_t e;
    if (op_log_read(&s->pump.log, id, &e, 1) != 1 || e.id != id) return 0;
    o[0] = e.id;
    o[1] = e.time_s;
    o[2] = e.type;
    o[3] = e.a;
    o[4] = e.b;
    return 1;
}

/* ---------------------------------------------------------------- engine alone */
shim_de_t *shim_de_create(uint32_t uu)
{
    shim_de_t *d = calloc(1, sizeof *d);
    op_de_init(&d->de, uu);
    return d;
}
void shim_de_destroy(shim_de_t *d) { free(d); }
int shim_de_set_schedule(shim_de_t *d, uint32_t n, const uint8_t *slots, const uint32_t *rates)
{
    op_basal_schedule_t s;
    memset(&s, 0, sizeof s);
    s.count = (uint8_t)n;
    for (uint32_t i = 0; i < n && i < OP_BASAL_SEGMENTS_MAX; i++) s.seg[i] = (op_basal_seg_t){slots[i], rates[i]};
    return op_de_set_schedule(&d->de, &s);
}
void shim_de_set_tod(shim_de_t *d, uint32_t ms) { op_de_set_time_of_day(&d->de, ms); }
void shim_de_heartbeat(shim_de_t *d) { op_de_comm_heartbeat(&d->de); }
int shim_de_start_temp(shim_de_t *d, uint32_t rate, uint32_t dur) { return op_de_start_temp_basal(&d->de, rate, dur); }
int shim_de_cancel_temp(shim_de_t *d) { return op_de_cancel_temp_basal(&d->de); }
int shim_de_start_bolus(shim_de_t *d, uint32_t mu) { return op_de_start_bolus(&d->de, mu); }
uint32_t shim_de_cancel_bolus(shim_de_t *d) { return op_de_cancel_bolus(&d->de); }
void shim_de_suspend(shim_de_t *d) { op_de_suspend(&d->de); }
void shim_de_resume(shim_de_t *d) { op_de_resume(&d->de); }
uint32_t shim_de_tick(shim_de_t *d, uint32_t dt) { return op_de_tick(&d->de, dt); }
void shim_de_commit(shim_de_t *d, uint32_t n) { op_de_commit(&d->de, n); }
uint32_t shim_de_take_events(shim_de_t *d) { return op_de_take_events(&d->de); }

void shim_de_snap(const shim_de_t *d, uint64_t o[SHIM_DE_SNAP_LEN])
{
    const op_de_t *e = &d->de;
    memset(o, 0, SHIM_DE_SNAP_LEN * sizeof(uint64_t));
    o[0] = e->suspended;
    o[1] = e->temp_active;
    o[2] = e->temp_rate_mu_h;
    o[3] = (e->temp_remaining_ms + 59999u) / 60000u;
    o[4] = e->bolus_active;
    o[5] = op_de_bolus_remaining_mu(e);
    o[6] = e->ms_of_day;
    o[7] = e->ms_since_comm;
    o[8] = (uint64_t)e->acc;
    o[9] = (uint64_t)e->scheduled_scaled;
    o[10] = e->requested_steps;
    o[11] = e->delivered_steps;
    o[12] = e->dropped_steps;
    o[13] = e->pending_steps;
    o[14] = op_de_current_rate_mu_h(e);
    o[15] = op_de_bolus_remaining_mu(e);
    o[16] = op_de_temp_remaining_min(e);
    op_de_report_t r;
    op_de_report(e, &r);
    o[17] = r.scheduled_mu;
    o[18] = r.delivered_mu;
    o[19] = r.delivered_steps;
    o[20] = r.dropped_steps;
    o[21] = e->has_schedule;
    o[22] = e->schedule.count;
    for (unsigned i = 0; i < e->schedule.count && i < 8; i++)
        o[23 + i] = ((uint64_t)e->schedule.seg[i].start_slot << 32) | e->schedule.seg[i].rate_mu_h;
}

/* ---------------------------------------------------------------- reservoir / log */
shim_res_t *shim_res_create(uint32_t cap, uint32_t uu)
{
    shim_res_t *r = calloc(1, sizeof *r);
    op_res_init(&r->r, cap, uu);
    return r;
}
void shim_res_destroy(shim_res_t *r) { free(r); }
int shim_res_fill(shim_res_t *r, uint32_t mu) { return op_res_fill(&r->r, mu); }
int shim_res_set_low(shim_res_t *r, uint32_t mu) { return op_res_set_low_threshold(&r->r, mu); }
void shim_res_consume(shim_res_t *r, uint32_t steps) { op_res_consume(&r->r, steps); }
void shim_res_snap(const shim_res_t *r, uint64_t o[SHIM_RES_SNAP_LEN])
{
    o[0] = r->r.fill_mu;
    o[1] = r->r.consumed_steps;
    o[2] = r->r.filled;
    o[3] = r->r.low_threshold_mu;
    o[4] = op_res_remaining_mu(&r->r);
    o[5] = op_res_is_empty(&r->r);
    o[6] = op_res_is_low(&r->r);
    o[7] = r->r.capacity_mu;
}

shim_log_t *shim_log_create(uint32_t restore_id)
{
    shim_log_t *l = calloc(1, sizeof *l);
    op_log_restore(&l->l, restore_id);
    return l;
}
void shim_log_destroy(shim_log_t *l) { free(l); }
uint32_t shim_log_append(shim_log_t *l, uint32_t t, uint8_t type, int32_t a, int32_t b)
{
    return op_log_append(&l->l, t, type, a, b);
}
uint32_t shim_log_next(const shim_log_t *l) { return op_log_next_id(&l->l); }
uint32_t shim_log_oldest(const shim_log_t *l) { return op_log_oldest_id(&l->l); }
uint32_t shim_log_read(const shim_log_t *l, uint32_t from, uint32_t max, int64_t *out)
{
    op_event_t buf[OP_LOG_CAPACITY];
    if (max > OP_LOG_CAPACITY) max = OP_LOG_CAPACITY;
    uint32_t n = op_log_read(&l->l, from, buf, max);
    for (uint32_t i = 0; i < n; i++) {
        out[5 * i] = buf[i].id;
        out[5 * i + 1] = buf[i].time_s;
        out[5 * i + 2] = buf[i].type;
        out[5 * i + 3] = buf[i].a;
        out[5 * i + 4] = buf[i].b;
    }
    return n;
}
