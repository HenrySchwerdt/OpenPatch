#include "dock.h"

#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "board_io.h"

LOG_MODULE_REGISTER(dock, LOG_LEVEL_INF);

#if OP_HAS(dock_gpios)
static const struct gpio_dt_spec g_dock = GPIO_DT_SPEC_GET(OP_ZU, dock_gpios);
#endif

#if IS_ENABLED(CONFIG_OPENPATCH_SIM_DOCK) && OP_HAS(dock_gpios)
/* Dev kit: the "dock" GPIO is a push button; every (debounced) press toggles the simulated input. */
static struct gpio_callback g_cb;
static struct k_work_delayable g_debounce;
static volatile bool g_sim_docked; /* starts undocked: nothing delivers until the bench says so */

static void isr(const struct device *port, struct gpio_callback *cb, uint32_t pins)
{
    ARG_UNUSED(port);
    ARG_UNUSED(cb);
    ARG_UNUSED(pins);
    k_work_reschedule(&g_debounce, K_MSEC(30));
}

static void debounce_fn(struct k_work *w)
{
    ARG_UNUSED(w);
    if (gpio_pin_get_dt(&g_dock) > 0) { /* pressed */
        g_sim_docked = !g_sim_docked;
        LOG_WRN("SIMULATED dock input: %s", g_sim_docked ? "DOCKED" : "UNDOCKED");
    }
}

int dock_init(void)
{
    if (!gpio_is_ready_dt(&g_dock)) return -ENODEV;
    k_work_init_delayable(&g_debounce, debounce_fn);
    int rc = gpio_pin_configure_dt(&g_dock, GPIO_INPUT);
    if (!rc) rc = gpio_pin_interrupt_configure_dt(&g_dock, GPIO_INT_EDGE_TO_ACTIVE);
    if (rc) return rc;
    gpio_init_callback(&g_cb, isr, BIT(g_dock.pin));
    return gpio_add_callback(g_dock.port, &g_cb);
}

bool dock_present(void) { return g_sim_docked; }

#elif OP_HAS(dock_gpios)

int dock_init(void)
{
    if (!gpio_is_ready_dt(&g_dock)) return -ENODEV;
    return gpio_pin_configure_dt(&g_dock, GPIO_INPUT);
}

bool dock_present(void) { return gpio_pin_get_dt(&g_dock) > 0; }

#else

int dock_init(void)
{
    LOG_ERR("no dock-gpios in the devicetree: the pod will never deliver");
    return 0;
}

bool dock_present(void) { return false; }

#endif
