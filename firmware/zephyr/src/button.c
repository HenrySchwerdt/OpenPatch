#include "button.h"

#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "app_events.h"
#include "board_io.h"

LOG_MODULE_REGISTER(button, LOG_LEVEL_INF);

static const struct gpio_dt_spec g_btn = GPIO_DT_SPEC_GET(OP_ZU, button_gpios);
static struct gpio_callback g_cb;
static struct k_work_delayable g_debounce;
static struct k_work_delayable g_long;
static bool g_pressed;
static bool g_long_fired;

#define DEBOUNCE_MS 30

static void isr(const struct device *port, struct gpio_callback *cb, uint32_t pins)
{
    ARG_UNUSED(port);
    ARG_UNUSED(cb);
    ARG_UNUSED(pins);
    k_work_reschedule(&g_debounce, K_MSEC(DEBOUNCE_MS));
}

static void debounce_fn(struct k_work *w)
{
    ARG_UNUSED(w);
    bool now = gpio_pin_get_dt(&g_btn) > 0;
    if (now == g_pressed) return;
    g_pressed = now;
    if (now) {
        g_long_fired = false;
        k_work_reschedule(&g_long, K_MSEC(CONFIG_OPENPATCH_LONG_PRESS_MS));
    } else {
        k_work_cancel_delayable(&g_long);
        if (!g_long_fired) app_evt_post(APP_EVT_BUTTON_SHORT, NULL, 0);
    }
}

static void long_fn(struct k_work *w)
{
    ARG_UNUSED(w);
    g_long_fired = true;
    app_evt_post(APP_EVT_BUTTON_LONG, NULL, 0);
}

int button_init(void)
{
    if (!gpio_is_ready_dt(&g_btn)) return -ENODEV;
    k_work_init_delayable(&g_debounce, debounce_fn);
    k_work_init_delayable(&g_long, long_fn);
    int rc = gpio_pin_configure_dt(&g_btn, GPIO_INPUT);
    if (!rc) rc = gpio_pin_interrupt_configure_dt(&g_btn, GPIO_INT_EDGE_BOTH);
    if (rc) return rc;
    gpio_init_callback(&g_cb, isr, BIT(g_btn.pin));
    return gpio_add_callback(g_btn.port, &g_cb);
}
