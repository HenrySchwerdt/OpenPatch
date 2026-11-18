#include "wdt_tpl5010.h"

#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/atomic.h>

#include "board_io.h"

LOG_MODULE_REGISTER(wdt, LOG_LEVEL_INF);

#if OP_HAS(wdt_done_gpios) && OP_HAS(wdt_wake_gpios)
static const struct gpio_dt_spec g_done = GPIO_DT_SPEC_GET(OP_ZU, wdt_done_gpios);
static const struct gpio_dt_spec g_wake = GPIO_DT_SPEC_GET(OP_ZU, wdt_wake_gpios);
static struct gpio_callback g_wake_cb;
static atomic_t g_last_beat_ms;
static atomic_t g_unhealthy;

void wdt_tpl5010_heartbeat(void) { atomic_set(&g_last_beat_ms, (atomic_val_t)k_uptime_get_32()); }

void wdt_tpl5010_set_unhealthy(const char *why)
{
    atomic_set(&g_unhealthy, 1);
    LOG_ERR("watchdog starved: %s", why);
}

static void wake_isr(const struct device *port, struct gpio_callback *cb, uint32_t pins)
{
    ARG_UNUSED(port);
    ARG_UNUSED(cb);
    ARG_UNUSED(pins);
    uint32_t age = k_uptime_get_32() - (uint32_t)atomic_get(&g_last_beat_ms);
    if (atomic_get(&g_unhealthy) || age > CONFIG_OPENPATCH_WDT_HEARTBEAT_MS) return;
    gpio_pin_set_dt(&g_done, 1);
    k_busy_wait(20);
    gpio_pin_set_dt(&g_done, 0);
}

int wdt_tpl5010_init(void)
{
    if (!gpio_is_ready_dt(&g_done) || !gpio_is_ready_dt(&g_wake)) return -ENODEV;
    wdt_tpl5010_heartbeat(); /* the first WAKE can arrive before the first tick */
    int rc = gpio_pin_configure_dt(&g_done, GPIO_OUTPUT_INACTIVE);
    if (!rc) rc = gpio_pin_configure_dt(&g_wake, GPIO_INPUT);
    if (!rc) rc = gpio_pin_interrupt_configure_dt(&g_wake, GPIO_INT_EDGE_TO_ACTIVE);
    if (rc) return rc;
    gpio_init_callback(&g_wake_cb, wake_isr, BIT(g_wake.pin));
    return gpio_add_callback(g_wake.port, &g_wake_cb);
}
#else
void wdt_tpl5010_heartbeat(void) {}
void wdt_tpl5010_set_unhealthy(const char *why) { LOG_WRN("unhealthy (no TPL5010 in this build): %s", why); }
int wdt_tpl5010_init(void) { return 0; }
#endif
