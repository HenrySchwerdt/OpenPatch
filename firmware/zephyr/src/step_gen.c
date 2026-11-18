#include "step_gen.h"

#include <zephyr/device.h>
#include <zephyr/drivers/counter.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "board_io.h"

LOG_MODULE_REGISTER(step_gen, LOG_LEVEL_INF);

static const struct device *const g_cnt = DEVICE_DT_GET(DT_NODELABEL(rtc2));
static const struct gpio_dt_spec g_stck = GPIO_DT_SPEC_GET(OP_ZU, motor_stck_gpios);

static K_SEM_DEFINE(g_done, 0, 1);
static struct counter_alarm_cfg g_alarm;
static uint32_t g_half_ticks;
static volatile uint32_t g_target;
static volatile uint32_t g_emitted;
static volatile bool g_high;
static volatile bool g_running;

static void rearm(const struct device *dev)
{
    g_alarm.ticks = g_half_ticks;
    if (counter_set_channel_alarm(dev, 0, &g_alarm) != 0) {
        /* cannot continue the pulse train: fail towards "motor stopped" */
        gpio_pin_set_dt(&g_stck, 0);
        g_high = false;
        g_running = false;
        k_sem_give(&g_done);
    }
}

static void alarm_cb(const struct device *dev, uint8_t chan, uint32_t ticks, void *user_data)
{
    ARG_UNUSED(chan);
    ARG_UNUSED(ticks);
    ARG_UNUSED(user_data);
    if (!g_running) return;
    if (g_high) {
        gpio_pin_set_dt(&g_stck, 0);
        g_high = false;
        if (g_emitted >= g_target) {
            g_running = false;
            k_sem_give(&g_done);
            return;
        }
    } else {
        gpio_pin_set_dt(&g_stck, 1); /* rising edge = one step */
        g_high = true;
        g_emitted++;
    }
    rearm(dev);
}

int step_gen_init(void)
{
    if (!device_is_ready(g_cnt) || !gpio_is_ready_dt(&g_stck)) return -ENODEV;
    uint32_t freq = counter_get_frequency(g_cnt);
    g_half_ticks = freq / (2u * CONFIG_OPENPATCH_STEP_RATE_HZ);
    if (g_half_ticks < 3) return -EINVAL;
    g_alarm.flags = 0;
    g_alarm.callback = alarm_cb;
    int rc = gpio_pin_configure_dt(&g_stck, GPIO_OUTPUT_INACTIVE);
    if (rc) return rc;
    return counter_start(g_cnt);
}

uint32_t step_gen_run(uint32_t steps)
{
    if (steps == 0) return 0;
    k_sem_reset(&g_done);
    g_target = steps;
    g_emitted = 0;
    g_high = false;
    g_running = true;
    rearm(g_cnt);
    int64_t budget_ms = (int64_t)steps * 1000 / CONFIG_OPENPATCH_STEP_RATE_HZ * 3 / 2 + 100;
    if (k_sem_take(&g_done, K_MSEC(budget_ms)) != 0) {
        LOG_ERR("step burst timed out");
        step_gen_abort();
    }
    return g_emitted > steps ? steps : g_emitted;
}

void step_gen_abort(void)
{
    g_running = false;
    counter_cancel_channel_alarm(g_cnt, 0);
    gpio_pin_set_dt(&g_stck, 0);
    g_high = false;
}
