/* Single event queue into the main thread: the portable core is not thread-safe and is only
 * ever touched from main(). ISRs, the BLE stack and workqueues post events here. */
#ifndef APP_EVENTS_H
#define APP_EVENTS_H

#include <stddef.h>
#include <stdint.h>

#include "op/openpatch_proto.h"

enum app_evt_type {
    APP_EVT_RX_FRAME = 1,
    APP_EVT_BUTTON_SHORT,
    APP_EVT_BUTTON_LONG,
    APP_EVT_CHARGER_CHANGED,
    APP_EVT_BENCH_CMD, /* bench shell command, see bench.h (bench boards only) */
};

struct app_evt {
    uint8_t type;
    uint8_t len;
    uint8_t data[OP_FRAME_MAX];
};

/* ISR-safe, non-blocking; returns 0 or -ENOMEM when the queue is full. */
int app_evt_post(enum app_evt_type type, const uint8_t *data, size_t len);
/* Wait up to timeout_ms; returns 0 and fills *out, or -EAGAIN on timeout. */
int app_evt_wait(struct app_evt *out, int32_t timeout_ms);

#endif
