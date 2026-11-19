#include "leds.h"

#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>

#include "board_io.h"

#if OP_HAS(status_led_gpios)
static const struct gpio_dt_spec g_status = GPIO_DT_SPEC_GET(OP_ZU, status_led_gpios);
#endif
#if OP_HAS(fault_led_gpios)
static const struct gpio_dt_spec g_fault = GPIO_DT_SPEC_GET(OP_ZU, fault_led_gpios);
#endif

int leds_init(void)
{
#if OP_HAS(status_led_gpios)
    if (!gpio_is_ready_dt(&g_status) || gpio_pin_configure_dt(&g_status, GPIO_OUTPUT_INACTIVE) != 0) return -ENODEV;
#endif
#if OP_HAS(fault_led_gpios)
    if (!gpio_is_ready_dt(&g_fault) || gpio_pin_configure_dt(&g_fault, GPIO_OUTPUT_INACTIVE) != 0) return -ENODEV;
#endif
    return 0;
}

void leds_update(bool status_on, bool blink, bool fault)
{
    static bool phase;
    phase = !phase; /* one tick = half a blink period: 0.5 Hz at the 1 s tick is slow, but visible */
#if OP_HAS(status_led_gpios)
    gpio_pin_set_dt(&g_status, blink ? phase : status_on);
#endif
#if OP_HAS(fault_led_gpios)
    gpio_pin_set_dt(&g_fault, fault);
#endif
#if !OP_HAS(status_led_gpios) && !OP_HAS(fault_led_gpios)
    ARG_UNUSED(status_on);
    ARG_UNUSED(blink);
    ARG_UNUSED(fault);
    ARG_UNUSED(phase);
#endif
}
