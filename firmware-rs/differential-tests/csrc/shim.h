/* Flat C ABI over the C reference core, for the Rust differential tests (host only).
 * Index layouts of the u32/u64 arrays are mirrored in src/ffi.rs. */
#ifndef SHIM_H
#define SHIM_H
#include <stddef.h>
#include <stdint.h>

#define SHIM_CMD_LEN 96
#define SHIM_RSP_LEN 96
#define SHIM_SNAP_LEN 160
#define SHIM_MOCK_LEN 8
#define SHIM_DE_SNAP_LEN 32
#define SHIM_RES_SNAP_LEN 8

typedef struct shim shim_t;
typedef struct shim_sess shim_sess_t;
typedef struct shim_de shim_de_t;
typedef struct shim_res shim_res_t;
typedef struct shim_log shim_log_t;

/* ---- codec ---- */
uint16_t shim_crc16(const uint8_t *d, size_t n);
int shim_frame_encode(uint8_t version, uint8_t type, uint8_t flags, uint16_t seq, const uint8_t *payload,
                      uint16_t plen, uint8_t *out, size_t cap);
/* out[0..6] = version,type,flags,seq,plen,payload_offset */
int shim_frame_decode(const uint8_t *in, size_t len, uint32_t out[8]);
shim_sess_t *shim_sess_new(void);
void shim_sess_free(shim_sess_t *s);
/* op_session_open + op_cmd_decode (plaintext session). 0 or -err; out = flat command. */
int shim_sess_decode(shim_sess_t *s, const uint8_t *in, size_t len, uint32_t out[SHIM_CMD_LEN]);
int shim_decode_payload(uint8_t type, uint16_t seq, const uint8_t *payload, size_t len, uint32_t out[SHIM_CMD_LEN]);
int shim_encode_cmd(const uint32_t in[SHIM_CMD_LEN], uint8_t *out, size_t cap);
int shim_encode_rsp(const uint32_t in[SHIM_RSP_LEN], uint8_t *out, size_t cap);

/* ---- whole pump with mock HAL ---- */
shim_t *shim_create(uint32_t cal_id, uint32_t capacity_mu, uint32_t next_event_id);
void shim_destroy(shim_t *s);
void shim_new_session(shim_t *s);
void shim_set_time(shim_t *s, uint64_t ms);
void shim_set_docked(shim_t *s, int v);
void shim_set_charger(shim_t *s, int v);
void shim_set_battery(shim_t *s, uint16_t mv);
void shim_set_delivered_pct(shim_t *s, uint32_t pct);
void shim_set_steps_limit(shim_t *s, int32_t lim);
void shim_tick(shim_t *s);
int shim_handle_frame(shim_t *s, const uint8_t *in, size_t len, uint8_t *out, size_t cap);
void shim_restore_pod(shim_t *s, uint32_t pair, uint8_t role, int active, uint32_t act_id, uint64_t wear_ms);
void shim_mock(const shim_t *s, uint64_t out[SHIM_MOCK_LEN]);
void shim_snapshot(const shim_t *s, uint64_t out[SHIM_SNAP_LEN]);
int shim_log_event(const shim_t *s, uint32_t id, int64_t out[5]);

/* ---- delivery engine alone ---- */
shim_de_t *shim_de_create(uint32_t uu_per_step);
void shim_de_destroy(shim_de_t *d);
int shim_de_set_schedule(shim_de_t *d, uint32_t n, const uint8_t *slots, const uint32_t *rates);
void shim_de_set_tod(shim_de_t *d, uint32_t ms);
void shim_de_heartbeat(shim_de_t *d);
int shim_de_start_temp(shim_de_t *d, uint32_t rate, uint32_t dur_min);
int shim_de_cancel_temp(shim_de_t *d);
int shim_de_start_bolus(shim_de_t *d, uint32_t mu);
uint32_t shim_de_cancel_bolus(shim_de_t *d);
void shim_de_suspend(shim_de_t *d);
void shim_de_resume(shim_de_t *d);
uint32_t shim_de_tick(shim_de_t *d, uint32_t dt_ms);
void shim_de_commit(shim_de_t *d, uint32_t executed);
uint32_t shim_de_take_events(shim_de_t *d);
void shim_de_snap(const shim_de_t *d, uint64_t out[SHIM_DE_SNAP_LEN]);

/* ---- reservoir ---- */
shim_res_t *shim_res_create(uint32_t capacity_mu, uint32_t uu);
void shim_res_destroy(shim_res_t *r);
int shim_res_fill(shim_res_t *r, uint32_t mu);
int shim_res_set_low(shim_res_t *r, uint32_t mu);
void shim_res_consume(shim_res_t *r, uint32_t steps);
void shim_res_snap(const shim_res_t *r, uint64_t out[SHIM_RES_SNAP_LEN]);

/* ---- event log ---- */
shim_log_t *shim_log_create(uint32_t restore_id);
void shim_log_destroy(shim_log_t *l);
uint32_t shim_log_append(shim_log_t *l, uint32_t time_s, uint8_t type, int32_t a, int32_t b);
uint32_t shim_log_next(const shim_log_t *l);
uint32_t shim_log_oldest(const shim_log_t *l);
/* out: 5 i64 per event (id,time_s,type,a,b) */
uint32_t shim_log_read(const shim_log_t *l, uint32_t from, uint32_t max, int64_t *out);

#endif
