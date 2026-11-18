/*
 * BQ25120A is only probed (STATUS register 0x00) and its INT pin logged; charge current and
 * SYS voltage are left at the resistor/OTP defaults for Rev A bring-up (TODO: program
 * fast-charge current <= 0.5 C and SYS_VOUT over I2C once the board exists).
 */
#include "charger.h"

#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "app_events.h"
#include "board_io.h"

LOG_MODULE_REGISTER(charger, LOG_LEVEL_INF);

#if OP_HAS(qi_chg_gpios)
static const struct gpio_dt_spec g_qi = GPIO_DT_SPEC_GET(OP_ZU, qi_chg_gpios);
static struct gpio_callback g_qi_cb;

static void qi_isr(const struct device *port, struct gpio_callback *cb, uint32_t pins)
{
    ARG_UNUSED(port);
    ARG_UNUSED(cb);
    ARG_UNUSED(pins);
    app_evt_post(APP_EVT_CHARGER_CHANGED, NULL, 0);
}

bool charger_active(void) { return gpio_pin_get_dt(&g_qi) > 0; }
#else
bool charger_active(void) { return false; }
#endif

#if OP_HAS(charger_int_gpios)
static const struct gpio_dt_spec g_int = GPIO_DT_SPEC_GET(OP_ZU, charger_int_gpios);
static struct gpio_callback g_int_cb;

static void int_isr(const struct device *port, struct gpio_callback *cb, uint32_t pins)
{
    ARG_UNUSED(port);
    ARG_UNUSED(cb);
    ARG_UNUSED(pins);
    app_evt_post(APP_EVT_CHARGER_CHANGED, NULL, 0);
}
#endif

int charger_init(void)
{
#if DT_NODE_HAS_STATUS(DT_NODELABEL(bq25120a), okay)
    static const struct i2c_dt_spec bq = I2C_DT_SPEC_GET(DT_NODELABEL(bq25120a));
    uint8_t status;
    if (i2c_is_ready_dt(&bq) && i2c_reg_read_byte_dt(&bq, 0x00, &status) == 0)
        LOG_INF("BQ25120A status 0x%02x", status);
    else
        LOG_WRN("BQ25120A not answering on I2C");
#endif
#if OP_HAS(qi_chg_gpios)
    if (!gpio_is_ready_dt(&g_qi)) return -ENODEV;
    gpio_pin_configure_dt(&g_qi, GPIO_INPUT);
    gpio_pin_interrupt_configure_dt(&g_qi, GPIO_INT_EDGE_BOTH);
    gpio_init_callback(&g_qi_cb, qi_isr, BIT(g_qi.pin));
    gpio_add_callback(g_qi.port, &g_qi_cb);
#endif
#if OP_HAS(charger_int_gpios)
    if (!gpio_is_ready_dt(&g_int)) return -ENODEV;
    gpio_pin_configure_dt(&g_int, GPIO_INPUT);
    gpio_pin_interrupt_configure_dt(&g_int, GPIO_INT_EDGE_TO_ACTIVE);
    gpio_init_callback(&g_int_cb, int_isr, BIT(g_int.pin));
    gpio_add_callback(g_int.port, &g_int_cb);
#endif
    return 0;
}
