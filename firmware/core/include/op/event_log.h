/*
 * Event log: ring buffer with persistent, strictly increasing 32-bit IDs.
 * IDs survive power cycles if the platform stores op_log_next_id() and
 * passes it to op_log_restore() at boot (events themselves are RAM here;
 * flash persistence is a platform concern).
 */
#ifndef OP_EVENT_LOG_H
#define OP_EVENT_LOG_H

#include "op/op_types.h"

#define OP_LOG_CAPACITY 128u

typedef enum {
    OP_EV_BOOT = 1,
    OP_EV_BOLUS_START = 2,   /* a = amount mU */
    OP_EV_BOLUS_DONE = 3,
    OP_EV_BOLUS_CANCEL = 4,  /* a = undelivered mU */
    OP_EV_TEMP_START = 5,    /* a = rate mU/h, b = minutes */
    OP_EV_TEMP_DONE = 6,
    OP_EV_TEMP_CANCEL = 7,
    OP_EV_TEMP_COMM_FALLBACK = 8,
    OP_EV_BASAL_SET = 9,     /* a = segment count */
    OP_EV_SUSPEND = 10,
    OP_EV_RESUME = 11,
    OP_EV_FILL = 12,         /* a = fill mU */
    OP_EV_PRIME = 13,        /* a = steps */
    OP_EV_FAULT = 14,        /* a = new fault bits */
    OP_EV_ACK = 15,          /* a = acknowledged mask */
    OP_EV_LOW_RESERVOIR = 16,/* a = remaining mU */
    OP_EV_LOW_BATTERY = 17   /* a = mV */
} op_event_type_t;

typedef struct {
    uint32_t id;
    uint32_t time_s;
    uint8_t type;
    int32_t a;
    int32_t b;
} op_event_t;

typedef struct {
    op_event_t ev[OP_LOG_CAPACITY];
    uint32_t next_id; /* id the next appended event receives (starts at 1) */
    uint32_t count;   /* number of valid events, <= OP_LOG_CAPACITY */
} op_log_t;

void op_log_init(op_log_t *l);
void op_log_restore(op_log_t *l, uint32_t next_id);
uint32_t op_log_append(op_log_t *l, uint32_t time_s, uint8_t type, int32_t a, int32_t b);
uint32_t op_log_next_id(const op_log_t *l);
uint32_t op_log_oldest_id(const op_log_t *l); /* == next_id when empty */
/* copy up to max events with id >= from_id (oldest first); returns count */
uint32_t op_log_read(const op_log_t *l, uint32_t from_id, op_event_t *out, uint32_t max);

#endif
