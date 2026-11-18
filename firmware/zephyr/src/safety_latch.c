#include "safety_latch.h"

#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "board_io.h"

LOG_MODULE_REGISTER(latch, LOG_LEVEL_INF);

#if OP_HAS(latch_arm_gpios) && OP_HAS(latch_kill_gpios) && OP_HAS(latch_mon_gpios)
#define HAVE_LATCH 1
static const struct gpio_dt_spec g_arm = GPIO_DT_SPEC_GET(OP_ZU, latch_arm_gpios);
static const struct gpio_dt_spec g_kill = GPIO_DT_SPEC_GET(OP_ZU, latch_kill_gpios);
static const struct gpio_dt_spec g_mon = GPIO_DT_SPEC_GET(OP_ZU, latch_mon_gpios);

int safety_latch_init(void)
{
    if (!gpio_is_ready_dt(&g_arm) || !gpio_is_ready_dt(&g_kill) || !gpio_is_ready_dt(&g_mon)) return -ENODEV;
    int rc = gpio_pin_configure_dt(&g_arm, GPIO_OUTPUT_INACTIVE);
    if (!rc) rc = gpio_pin_configure_dt(&g_kill, GPIO_OUTPUT_INACTIVE); /* released (open drain) */
    if (!rc) rc = gpio_pin_configure_dt(&g_mon, GPIO_INPUT);
    if (rc) return rc;
    safety_latch_kill(); /* boot state is always "off" */
    return 0;
}

bool safety_latch_present(void) { return true; }

bool safety_latch_arm(void)
{
    gpio_pin_set_dt(&g_kill, 0); /* release KILL_N */
    gpio_pin_set_dt(&g_arm, 0);
    k_busy_wait(20);
    gpio_pin_set_dt(&g_arm, 1); /* rising edge arms */
    k_busy_wait(20);
    gpio_pin_set_dt(&g_arm, 0);
    k_msleep(1);
    bool armed = gpio_pin_get_dt(&g_mon) > 0;
    if (!armed) LOG_ERR("safety latch did not arm (watchdog/kill path active?)");
    return armed;
}

void safety_latch_kill(void)
{
    gpio_pin_set_dt(&g_kill, 1); /* KILL_N low */
    k_busy_wait(200);
    gpio_pin_set_dt(&g_kill, 0);
}
#else
int safety_latch_init(void) { return 0; }
bool safety_latch_present(void) { return false; }
bool safety_latch_arm(void) { return true; }
void safety_latch_kill(void) {}
#endif
