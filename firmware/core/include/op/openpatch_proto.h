/*
 * OpenPatch binary protocol v1 (see docs/openpatch-protocol.md).
 *
 * Frame (little endian):
 *   [0] version  [1] type  [2] flags  [3..4] seq  [5..6] len  [7..] payload  [..] crc16
 * CRC16-CCITT-FALSE (poly 0x1021, init 0xFFFF) over header+payload.
 * Payload is a TLV list: tag(u8) len(u8) value. Unknown tags are skipped.
 * With OP_FLAG_ENCRYPTED the payload is ciphertext || 8-byte AES-CCM tag,
 * AAD = the 7 header bytes.
 */
#ifndef OP_OPENPATCH_PROTO_H
#define OP_OPENPATCH_PROTO_H

#include "op/delivery_engine.h"
#include "op/event_log.h"
#include "op/op_types.h"

#define OP_PROTO_VERSION 1u
#define OP_FRAME_HEADER 7u
#define OP_FRAME_CRC 2u
#define OP_FRAME_MAX 244u /* ATT MTU 247 - 3, so one frame = one notification */
#define OP_CCM_TAG_LEN 8u
#define OP_CCM_NONCE_LEN 13u
#define OP_SEQ_MAX 0xFFFEu /* 0xFFFF reserved: forces rekey before nonce reuse */
#define OP_HIST_MAX_PER_RESPONSE 10u

enum { OP_FLAG_ENCRYPTED = 1u << 0, OP_FLAG_RESPONSE = 1u << 1 };

typedef enum {
    OP_CMD_GET_STATUS = 0x01,
    OP_CMD_SET_BASAL_SCHEDULE = 0x02,
    OP_CMD_SET_TEMP_BASAL = 0x03,
    OP_CMD_CANCEL_TEMP_BASAL = 0x04,
    OP_CMD_BOLUS = 0x05,
    OP_CMD_CANCEL_BOLUS = 0x06,
    OP_CMD_SUSPEND = 0x07,
    OP_CMD_RESUME = 0x08,
    OP_CMD_FILL_PRIME = 0x09,
    OP_CMD_ACKNOWLEDGE = 0x0A,
    OP_CMD_GET_HISTORY = 0x0B,
    OP_CMD_SET_PAIRING = 0x0C,  /* pair id + role (released pods only) */
    OP_CMD_ACTIVATE = 0x0D,     /* become the active pod: schedule + temp basal; pod must be docked */
    OP_CMD_RELEASE = 0x0E       /* stop delivering, report totals; idempotent */
} op_cmd_type_t;
#define OP_RSP_BIT 0x80u /* response type = command type | 0x80 */

typedef enum {
    OP_TAG_RESULT = 0x01,          /* u8  op_err_t */
    OP_TAG_BASAL_SEG = 0x02,       /* u8 start_slot, u16 rate mU/h */
    OP_TAG_RATE_MU_H = 0x03,       /* u16 */
    OP_TAG_DURATION_MIN = 0x04,    /* u16 */
    OP_TAG_AMOUNT_MU = 0x05,       /* u32 */
    OP_TAG_FILL_MU = 0x06,         /* u32 */
    OP_TAG_PRIME_STEPS = 0x07,     /* u16 */
    OP_TAG_SUB_OP = 0x08,          /* u8: 1 fill, 2 prime */
    OP_TAG_FAULT_MASK = 0x09,      /* u16 */
    OP_TAG_FROM_ID = 0x0A,         /* u32 */
    OP_TAG_MAX_EVENTS = 0x0B,      /* u8 */
    OP_TAG_TIME_OF_DAY_MS = 0x0C,  /* u32 local ms since midnight, optional on any command */
    OP_TAG_HISTORY_EVENT = 0x0D,   /* u32 id, u32 time_s, u8 type, i32 a, i32 b */
    OP_TAG_NEXT_EVENT_ID = 0x0E,   /* u32 */
    OP_TAG_OLDEST_EVENT_ID = 0x0F, /* u32 */
    OP_TAG_STATE_FLAGS = 0x10,     /* u16 */
    OP_TAG_RESERVOIR_MU = 0x11,    /* u32 */
    OP_TAG_BATTERY_MV = 0x12,      /* u16 */
    OP_TAG_BOLUS_REMAINING_MU = 0x13,
    OP_TAG_TEMP_RATE_MU_H = 0x14,  /* u16 */
    OP_TAG_TEMP_REMAINING_MIN = 0x15,
    OP_TAG_CURRENT_RATE_MU_H = 0x16,
    OP_TAG_DELIVERED_MU = 0x17,    /* u32 lifetime */
    OP_TAG_SCHEDULED_MU = 0x18,    /* u32 */
    OP_TAG_FW_VERSION = 0x19,      /* u16 */
    OP_TAG_LAST_SEQ = 0x1A,        /* u16 highest accepted command seq (GetStatus; resync after pod reboot) */
    OP_TAG_DRIVE_CAL = 0x1B,       /* 10 bytes: u16 drive_id, u32 uU/step, u16 steps/rev, u16 gear ratio x100 (GetStatus) */
    OP_TAG_POD_INFO = 0x1C,        /* 10 bytes: u32 pair_id, u8 role, u8 delivery_state, u32 wear_s (GetStatus) */
    OP_TAG_PAIR_ID = 0x1D,         /* u32, SetPairing / Activate / Release */
    OP_TAG_ROLE = 0x1E,            /* u8 op_role_t, SetPairing */
    OP_TAG_ACTIVATION_ID = 0x1F,   /* u32 chosen by the app, makes Activate idempotent */
    OP_TAG_ACT_DELIVERED_MU = 0x20 /* u32 mU delivered since activation (Release/Activate response) */
} op_tag_t;

enum { OP_SUBOP_FILL = 1, OP_SUBOP_PRIME = 2 };

enum { /* op_status_t.flags */
    OP_ST_SUSPENDED = 1u << 0,
    OP_ST_BOLUS_ACTIVE = 1u << 1,
    OP_ST_TEMP_ACTIVE = 1u << 2,
    OP_ST_HAS_SCHEDULE = 1u << 3,
    OP_ST_LOW_RESERVOIR = 1u << 4,
    OP_ST_ALARM = 1u << 5,
    OP_ST_FILLED = 1u << 6,
    OP_ST_LOW_BATTERY = 1u << 7,
    OP_ST_WEAR_WARNING = 1u << 8, /* >= 44 h since activation */
    OP_ST_DOCKED = 1u << 9,       /* dock input asserted */
    OP_ST_ACTIVE = 1u << 10       /* this pod is the active pod of its pair */
};

/* ---- CRC / frame ---------------------------------------------------------- */
uint16_t op_crc16(const uint8_t *data, size_t len);

typedef struct {
    uint8_t version, type, flags;
    uint16_t seq;
    const uint8_t *payload; /* points into the decoded buffer */
    uint16_t payload_len;
} op_frame_t;

int op_frame_encode(const op_frame_t *f, uint8_t *out, size_t cap);   /* len or -err */
int op_frame_decode(const uint8_t *in, size_t len, op_frame_t *out);   /* 0 or -err */

/* ---- TLV ---------------------------------------------------------------------- */
typedef struct { uint8_t *buf; size_t cap, len; bool overflow; } op_tlv_w_t;
void op_tlv_w_init(op_tlv_w_t *w, uint8_t *buf, size_t cap);
void op_tlv_put(op_tlv_w_t *w, uint8_t tag, const void *v, uint8_t vlen);
void op_tlv_put_u8(op_tlv_w_t *w, uint8_t tag, uint8_t v);
void op_tlv_put_u16(op_tlv_w_t *w, uint8_t tag, uint16_t v);
void op_tlv_put_u32(op_tlv_w_t *w, uint8_t tag, uint32_t v);

typedef struct { const uint8_t *p; size_t len, pos; bool error; } op_tlv_r_t;
void op_tlv_r_init(op_tlv_r_t *r, const uint8_t *p, size_t len);
/* false at end or on truncation (r->error set) */
bool op_tlv_next(op_tlv_r_t *r, uint8_t *tag, const uint8_t **v, uint8_t *vlen);

/* ---- typed messages --------------------------------------------------------- */
typedef struct {
    uint8_t type; /* op_cmd_type_t */
    uint16_t seq;
    bool has_time_of_day;
    uint32_t time_of_day_ms;
    union {
        op_basal_schedule_t basal;
        struct { uint32_t rate_mu_h, duration_min; } temp;
        struct { uint32_t amount_mu; } bolus;
        struct { uint8_t sub_op; uint32_t fill_mu; uint16_t prime_steps; } fill;
        struct { uint16_t fault_mask; } ack;
        struct { uint32_t from_id; uint8_t max_events; } history;
        struct { uint32_t pair_id; uint8_t role; } pairing;
        struct { uint32_t pair_id; } release;
        struct {
            uint32_t pair_id, activation_id;
            op_basal_schedule_t schedule;
            bool has_temp;
            uint32_t temp_rate_mu_h, temp_remaining_min;
        } activate;
    } u;
} op_cmd_t;

typedef struct {
    uint16_t flags, faults, battery_mv, temp_rate_mu_h, temp_remaining_min, current_rate_mu_h, fw_version;
    uint32_t reservoir_mu, bolus_remaining_mu, delivered_mu, scheduled_mu, next_event_id;
    uint16_t last_seq; /* highest accepted command sequence number (filled by op_pump_handle_frame) */
    uint16_t cal_drive_id, cal_steps_per_rev, cal_gear_ratio_x100; /* drive calibration, all 0 = none/invalid */
    uint32_t cal_uu_per_step;
    uint32_t pair_id;       /* 0 = not paired */
    uint32_t wear_s;        /* seconds since activation (frozen while released) */
    uint8_t role;           /* op_role_t */
    uint8_t delivery_state; /* op_delivery_state_t */
} op_status_t;

typedef struct {
    uint8_t type; /* command type (without OP_RSP_BIT) */
    uint16_t seq;
    uint8_t result; /* op_err_t */
    bool has_status;
    op_status_t status;
    bool has_act_delivered;
    uint32_t act_delivered_mu;
    bool has_history;
    uint32_t next_event_id, oldest_event_id;
    uint8_t n_events;
    op_event_t events[OP_HIST_MAX_PER_RESPONSE];
} op_rsp_t;

/* payload-level codec (TLVs only, no framing) */
int op_cmd_encode_payload(const op_cmd_t *c, uint8_t *out, size_t cap);
int op_cmd_decode(uint8_t type, uint16_t seq, const uint8_t *payload, size_t len, op_cmd_t *out);
int op_rsp_encode_payload(const op_rsp_t *r, uint8_t *out, size_t cap);
int op_rsp_decode(uint8_t type, uint16_t seq, const uint8_t *payload, size_t len, op_rsp_t *out);

/* ---- session: replay protection + AES-CCM hook ------------------------------ */
typedef struct {
    void *ctx;
    /* ct has the same length as pt; tag is OP_CCM_TAG_LEN bytes. 0 on success. */
    int (*encrypt)(void *ctx, const uint8_t nonce[OP_CCM_NONCE_LEN], const uint8_t *aad, size_t aad_len,
                   const uint8_t *pt, size_t len, uint8_t *ct, uint8_t tag[OP_CCM_TAG_LEN]);
    /* 0 on success, non-zero if the tag does not verify. */
    int (*decrypt)(void *ctx, const uint8_t nonce[OP_CCM_NONCE_LEN], const uint8_t *aad, size_t aad_len,
                   const uint8_t *ct, size_t len, const uint8_t tag[OP_CCM_TAG_LEN], uint8_t *pt);
    /* Replay hook: persist the highest accepted sequence number (optional). */
    void (*on_seq_accepted)(void *ctx, uint16_t seq);
} op_ccm_ops_t;

typedef struct {
    const op_ccm_ops_t *ccm;  /* NULL: no crypto available */
    bool allow_plaintext;     /* dev/test only; production sets false */
    uint8_t salt[4];          /* per-session nonce salt from the key agreement */
    bool rx_seen;
    uint16_t last_rx_seq;
} op_session_t;

void op_session_init(op_session_t *s, const op_ccm_ops_t *ccm, const uint8_t salt[4], bool allow_plaintext);
/* Nonce: salt(4) | dir(1: 0 cmd, 1 rsp) | seq u16 LE | 6 zero bytes */
void op_session_nonce(const op_session_t *s, bool response, uint16_t seq, uint8_t nonce[OP_CCM_NONCE_LEN]);
/* Validate, replay-check and decrypt a command frame. The returned payload
 * points into `plain` (or `in`). Sequence state advances only on success. */
int op_session_open(op_session_t *s, const uint8_t *in, size_t len, op_frame_t *out, uint8_t *plain,
                    size_t plain_cap);
/* Build a (possibly encrypted) frame. `response` selects the nonce direction and
 * the RESPONSE flag; responses echo the command's `seq`. */
int op_session_seal(const op_session_t *s, bool response, uint8_t type, uint16_t seq, bool encrypt,
                    const uint8_t *payload, size_t plen, uint8_t *out, size_t cap);

#endif
