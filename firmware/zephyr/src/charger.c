/*
 * Charger presence, board-configurable through the devicetree (no charger driver, no I2C):
 *   qi-chg-gpios   Qi receiver CHG output (BQ51013B, open drain): Qi field present / charging
 *   chg-stat-gpios charge controller STAT output (MCP73832, open drain, low = charging)
 * A board lists the pins it has: Rev A pod has both, the dev kit and the USB-powered bench
 * controller have none (charger_active() is then always false and no event is ever posted).
 * Either input asserted means "on a charger": the core forces a pod that is on a charger to
 * RELEASED (two-pod rule, docs/openpatch-protocol.md 3.4), and main() stops delivery at once.
 * The MCP73832 has no charge-current or voltage registers: both are set by hardware (PROG resistor).
 */
#include "charger.h"

#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "app_events.h"
#include "board_io.h"

LOG_MODULE_REGISTER(charger, LOG_LEVEL_INF);

struct chg_input {
    const struct gpio_dt_spec *spec;
    struct gpio_callback cb;
};

static void chg_isr(const struct device *port, struct gpio_callback *cb, uint32_t pins)
{
    ARG_UNUSED(port);
    ARG_UNUSED(cb);
    ARG_UNUSED(pins);
    app_evt_post(APP_EVT_CHARGER_CHANGED, NULL, 0);
}

#if OP_HAS(qi_chg_gpios)
static const struct gpio_dt_spec g_qi = GPIO_DT_SPEC_GET(OP_ZU, qi_chg_gpios);
#endif
#if OP_HAS(chg_stat_gpios)
static const struct gpio_dt_spec g_stat = GPIO_DT_SPEC_GET(OP_ZU, chg_stat_gpios);
#endif

static struct chg_input g_inputs[] = {
#if OP_HAS(qi_chg_gpios)
    {.spec = &g_qi},
#endif
#if OP_HAS(chg_stat_gpios)
    {.spec = &g_stat},
#endif
};

bool charger_active(void)
{
    for (size_t i = 0; i < ARRAY_SIZE(g_inputs); i++)
        if (gpio_pin_get_dt(g_inputs[i].spec) > 0) return true;
    return false;
}

int charger_init(void)
{
    if (ARRAY_SIZE(g_inputs) == 0) {
        LOG_INF("no charger on this board");
        return 0;
    }
    for (size_t i = 0; i < ARRAY_SIZE(g_inputs); i++) {
        const struct gpio_dt_spec *s = g_inputs[i].spec;
        if (!gpio_is_ready_dt(s)) return -ENODEV;
        int rc = gpio_pin_configure_dt(s, GPIO_INPUT);
        if (!rc) rc = gpio_pin_interrupt_configure_dt(s, GPIO_INT_EDGE_BOTH);
        if (rc) return rc;
        gpio_init_callback(&g_inputs[i].cb, chg_isr, BIT(s->pin));
        rc = gpio_add_callback(s->port, &g_inputs[i].cb);
        if (rc) return rc;
    }
    return 0;
}
