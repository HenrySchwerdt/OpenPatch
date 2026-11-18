/*
 * OpenPatch pod firmware entry point: wires the portable core (firmware/core)
 * to the Zephyr HAL and the BLE GATT stub.
 *
 * SKELETON - UNTESTED (no nRF Connect SDK available when written).
 * EXPERIMENTAL DIY DEVICE - NOT A MEDICAL DEVICE.
 *
 * Threading: BLE writes are queued from the BT context and processed here, so the
 * core (not thread-safe) is only ever touched by the main thread.
 */
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "ble_openpatch.h"
#include "hal_zephyr.h"
#include "op/pump_controller.h"

LOG_MODULE_REGISTER(main, LOG_LEVEL_INF);

#define TICK_MS 1000

struct rx_msg {
    uint8_t len;
    uint8_t data[OP_FRAME_MAX];
};
K_MSGQ_DEFINE(rx_q, sizeof(struct rx_msg), 4, 4);

static op_hal_t g_hal;
static op_pump_t g_pump;
static op_session_t g_session;

static void on_rx(const uint8_t *data, size_t len)
{
    struct rx_msg m = {.len = (uint8_t)len};
    memcpy(m.data, data, len);
    if (k_msgq_put(&rx_q, &m, K_NO_WAIT) != 0) LOG_WRN("rx queue full, frame dropped");
}

static void handle_rx(const struct rx_msg *m)
{
    uint8_t out[OP_FRAME_MAX];
    int n = op_pump_handle_frame(&g_pump, &g_session, m->data, m->len, out, sizeof out);
    if (n < 0) {
        LOG_WRN("frame rejected (%d)", n); /* corrupt / replayed / unauthenticated: silent on air */
        return;
    }
    int err = openpatch_ble_notify(out, (size_t)n);
    if (err) LOG_WRN("notify failed (%d)", err);
}

int main(void)
{
    if (hal_zephyr_init(&g_hal) != 0) {
        LOG_ERR("HAL init failed - refusing to run");
        return 0; /* TPL5010 will cut the motor supply; no delivery without a working HAL */
    }
    /* TODO: restore next event id / seq counter / reservoir from persistent storage. */
    op_pump_init(&g_pump, &g_hal, CONFIG_OPENPATCH_RESERVOIR_MU, 1);

    /* TODO: no AES-CCM backend yet -> ccm = NULL. Plaintext only with dev.conf. */
    static const uint8_t salt[4] = {0}; /* TODO: from the session key agreement */
    op_session_init(&g_session, NULL, salt, IS_ENABLED(CONFIG_OPENPATCH_ALLOW_PLAINTEXT));

    int err = openpatch_ble_init(on_rx);
    if (err) LOG_ERR("BLE init failed (%d)", err);

    int64_t next_tick = k_uptime_get() + TICK_MS;
    for (;;) {
        int64_t wait = next_tick - k_uptime_get();
        struct rx_msg m;
        if (wait > 0 && k_msgq_get(&rx_q, &m, K_MSEC(wait)) == 0) handle_rx(&m);
        if (k_uptime_get() >= next_tick) {
            op_pump_tick(&g_pump);
            next_tick += TICK_MS;
        }
    }
    return 0;
}
