/*
 * OpenPatch pod firmware entry point: wires the portable core (firmware/core) to the Zephyr
 * HAL, the BLE GATT service, persistence and DFU.
 *
 * EXPERIMENTAL DIY DEVICE - NOT A MEDICAL DEVICE. UNTESTED ON HARDWARE.
 *
 * Threading: BLE writes, button and charger events are queued from their contexts and
 * handled here, so the core (not thread-safe) is only ever touched by the main thread.
 */
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/reboot.h>

#include "app_events.h"
#include "bench.h"
#include "ble_openpatch.h"
#include "board_io.h"
#include "button.h"
#include "buzzer.h"
#include "charger.h"
#include "dfu.h"
#include "encoder.h"
#include "hal_zephyr.h"
#include "leds.h"
#include "op/pump_controller.h"
#include "persist.h"

LOG_MODULE_REGISTER(main, LOG_LEVEL_INF);

#define TICK_MS 1000
#define CONFIRM_AFTER_TICKS 10 /* self-test: ten clean ticks, then the new image is confirmed */

static op_hal_t g_hal;
static op_pump_t g_pump;
static op_session_t g_session;
static bool g_charging;

static const op_ccm_ops_t g_session_ops = {
    /* encrypt/decrypt are NULL until the key agreement + AES-CCM backend exist (open issue):
     * encrypted frames are rejected with AUTH, plaintext only if CONFIG_OPENPATCH_ALLOW_PLAINTEXT. */
    .on_seq_accepted = persist_save_seq,
};

static void publish_dfu_state(void) { dfu_set_allowed(g_pump.de.suspended); }

static void handle_rx(const struct app_evt *e)
{
    uint8_t out[OP_FRAME_MAX];
    int n = op_pump_handle_frame(&g_pump, &g_session, e->data, e->len, out, sizeof out);
    persist_sync(&g_pump);
    publish_dfu_state();
    if (n < 0) {
        LOG_WRN("frame rejected (%d)", n); /* corrupt / replayed / unauthenticated: silent on air */
        return;
    }
    int err = openpatch_ble_notify(out, (size_t)n);
    if (err) LOG_WRN("notify failed (%d)", err);
}

static void emergency_stop(const char *why)
{
    LOG_WRN("%s: suspending delivery", why);
    bench_abort(); /* a running bench sequence ends here too */
    op_pump_cancel_bolus(&g_pump);
    op_pump_suspend(&g_pump);
    persist_sync(&g_pump);
    publish_dfu_state();
    buzzer_set(OP_BUZZER_BEEP);
}

static void handle_evt(const struct app_evt *e)
{
    switch (e->type) {
    case APP_EVT_RX_FRAME: handle_rx(e); break;
    case APP_EVT_BUTTON_SHORT:
        buzzer_silence();
        openpatch_ble_open_pairing_window();
        buzzer_set(OP_BUZZER_BEEP);
        break;
    case APP_EVT_BUTTON_LONG: emergency_stop("emergency stop (long press)"); break;
    case APP_EVT_BENCH_CMD:
        bench_handle_cmd(e);
        persist_sync(&g_pump);
        publish_dfu_state();
        break;
    case APP_EVT_CHARGER_CHANGED: {
        bool now = charger_active();
        if (now && !g_charging) {
            emergency_stop("on charger"); /* no delivery while charging (H8/H9) */
            op_pump_tick(&g_pump);        /* a pod on a charger is forced RELEASED right away */
            persist_sync(&g_pump);
        }
        g_charging = now;
        break;
    }
    default: break;
    }
}

/* Occlusion detector thresholds from Kconfig; the detector only runs where the HAL has current sense. */
static void configure_occlusion(void)
{
    const op_occ_cfg_t cfg = {
        .abs_peak_ma = CONFIG_OPENPATCH_OCC_ABS_PEAK_MA,
        .rise_pct = CONFIG_OPENPATCH_OCC_RISE_PCT,
        .slip_pct_min = CONFIG_OPENPATCH_OCC_SLIP_PCT_MIN,
        .stall_slip_pct = CONFIG_OPENPATCH_OCC_STALL_SLIP_PCT,
        .window_steps = CONFIG_OPENPATCH_OCC_WINDOW_STEPS,
        .strikes_needed = CONFIG_OPENPATCH_OCC_STRIKES,
        .baseline_windows = CONFIG_OPENPATCH_OCC_BASELINE_WINDOWS,
    };
    op_pump_set_occlusion_cfg(&g_pump, &cfg);
}

int main(void)
{
    struct persist_state st;
    int err = persist_init(&st);
    if (err) {
        LOG_ERR("persistent storage failed (%d) - refusing to run", err);
        return 0; /* no heartbeat reaches the TPL5010: motor path stays dead */
    }

    err = hal_zephyr_init(&g_hal);
    if (err == 0) err = button_init();
    if (err == 0) err = charger_init();
    if (err == 0) err = leds_init();
    if (err) {
        LOG_ERR("init failed (%d) - refusing to run", err);
        return 0; /* TPL5010 will cut the motor supply; no delivery without a working HAL */
    }

    const op_drive_cal_t *cal = persist_drive_cal(&st); /* NULL -> pump refuses to deliver */
    op_pump_init(&g_pump, &g_hal, cal, CONFIG_OPENPATCH_RESERVOIR_MU, st.next_event_id);
    encoder_set_steps_per_spindle_rev(op_drive_cal_steps_per_spindle_rev(cal));
    persist_apply_pod(&g_pump, &st);
    persist_apply_reservoir(&g_pump, &st);
    persist_sync(&g_pump);

    static const uint8_t salt[4] = {0}; /* TODO: from the session key agreement */
    op_session_init(&g_session, &g_session_ops, salt, IS_ENABLED(CONFIG_OPENPATCH_ALLOW_PLAINTEXT));
    if (st.seq_valid) { /* replay protection survives resets */
        g_session.rx_seen = true;
        g_session.last_rx_seq = st.last_seq;
    }

    bench_init(&g_pump);
    if (DT_NODE_HAS_PROP(OP_ZU, openpatch_placeholder_pins))
        LOG_ERR("PLACEHOLDER PIN MAP: the pin numbers in this build are NOT the real board wiring");
    configure_occlusion();

    dfu_init();
    publish_dfu_state();
    err = openpatch_ble_init();
    if (err) LOG_ERR("BLE init failed (%d)", err);
    g_charging = charger_active();
    if (g_charging) emergency_stop("booted on charger");

    int64_t next_tick = k_uptime_get() + TICK_MS;
    int clean_ticks = 0;
    for (;;) {
        int64_t wait = next_tick - k_uptime_get();
        struct app_evt e;
        if (wait > 0 && app_evt_wait(&e, (int32_t)wait) == 0) handle_evt(&e);
        if (k_uptime_get() >= next_tick) {
            op_pump_tick(&g_pump);
            bench_tick();
            persist_sync(&g_pump);
            publish_dfu_state();
            leds_update(g_pump.pod.active && g_pump.pod.docked, bench_running(), g_pump.sv.faults != 0);
            next_tick += TICK_MS;
            if (g_pump.sv.faults == 0 && ++clean_ticks == CONFIRM_AFTER_TICKS) dfu_confirm_image();
            if (g_pump.sv.faults) clean_ticks = 0;
        }
    }
    return 0;
}
