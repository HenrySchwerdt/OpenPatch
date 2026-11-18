#include "op/event_log.h"

#include <string.h>

void op_log_init(op_log_t *l)
{
    memset(l, 0, sizeof *l);
    l->next_id = 1;
}

void op_log_restore(op_log_t *l, uint32_t next_id)
{
    memset(l, 0, sizeof *l);
    l->next_id = next_id == 0 ? 1 : next_id;
}

uint32_t op_log_next_id(const op_log_t *l) { return l->next_id; }

uint32_t op_log_oldest_id(const op_log_t *l) { return l->next_id - l->count; }

uint32_t op_log_append(op_log_t *l, uint32_t time_s, uint8_t type, int32_t a, int32_t b)
{
    uint32_t id = l->next_id++;
    op_event_t *e = &l->ev[id % OP_LOG_CAPACITY];
    e->id = id;
    e->time_s = time_s;
    e->type = type;
    e->a = a;
    e->b = b;
    if (l->count < OP_LOG_CAPACITY) l->count++;
    return id;
}

uint32_t op_log_read(const op_log_t *l, uint32_t from_id, op_event_t *out, uint32_t max)
{
    if (!out || max == 0) return 0;
    uint32_t id = op_log_oldest_id(l);
    if (from_id > id) id = from_id;
    uint32_t n = 0;
    for (; id < l->next_id && n < max; id++) out[n++] = l->ev[id % OP_LOG_CAPACITY];
    return n;
}
