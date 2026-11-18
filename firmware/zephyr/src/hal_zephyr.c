/*
 * Zephyr implementation of op_hal_t for the OpenPatch pod (nRF54L15).
 * SKELETON - UNTESTED, no NCS available when written. Verify every pin,
 * timing and sign convention on hardware.
 */
#include "hal_zephyr.h"

#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/adc.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(hal, LOG_LEVEL_INF);

static const struct gpio_dt_spec g_step = GPIO_DT_SPEC_GET(DT_ALIAS(motor_step), gpios);
static const struct gpio_dt_spec g_stby = GPIO_DT_SPEC_GET(DT_ALIAS(motor_stby), gpios);
static const struct gpio_dt_spec g_gate = GPIO_DT_SPEC_GET(DT_ALIAS(motor_gate), gpios);
static const struct gpio_dt_spec g_wdt = GPIO_DT_SPEC_GET(DT_ALIAS(wdt_done), gpios);
static const struct gpio_dt_spec g_buzz = GPIO_DT_SPEC_GET(DT_ALIAS(buzzer_pin), gpios);
static const struct i2c_dt_spec g_enc = I2C_DT_SPEC_GET(DT_ALIAS(encoder));
static const struct adc_dt_spec g_vbat = ADC_DT_SPEC_GET_BY_IDX(DT_PATH(zephyr_user), 0);

/* Motor timing: STSPIN220 full-step, ~100 steps/s keeps torque margin. TODO tune. */
#define STEP_HIGH_US 2000
#define STEP_LOW_US 8000

/* AS5600: 4096 counts per spindle revolution = 200 motor steps -> 20.48 counts/step.
 * substeps (1/16 step) = counts * 16 / 20.48 = counts * 25 / 32 (exact). */
#define AS5600_REG_ANGLE 0x0E
#define COUNTS_PER_REV 4096
static int32_t g_enc_counts;
static uint16_t g_enc_last;
static bool g_enc_primed;

static int hal_motor_step(void *ctx, uint32_t steps)
{
    ARG_UNUSED(ctx);
    for (uint32_t i = 0; i < steps; i++) {
        gpio_pin_set_dt(&g_step, 1);
        k_busy_wait(STEP_HIGH_US);
        gpio_pin_set_dt(&g_step, 0);
        k_busy_wait(STEP_LOW_US);
    }
    return (int)steps; /* open loop: the encoder (supervisor) verifies the result */
}

static void hal_motor_enable(void *ctx, bool enable)
{
    ARG_UNUSED(ctx);
    gpio_pin_set_dt(&g_gate, enable); /* power path first on, last off */
    gpio_pin_set_dt(&g_stby, enable);
}

static int32_t hal_encoder_read(void *ctx)
{
    ARG_UNUSED(ctx);
    uint8_t buf[2] = {0};
    if (i2c_burst_read_dt(&g_enc, AS5600_REG_ANGLE, buf, 2) != 0) {
        LOG_ERR("encoder read failed"); /* position freezes -> supervisor sees a stall */
        return (int32_t)((int64_t)g_enc_counts * 25 / 32);
    }
    uint16_t raw = (uint16_t)((((uint16_t)buf[0] << 8) | buf[1]) & 0x0FFF);
    if (g_enc_primed) {
        int16_t delta = (int16_t)(raw - g_enc_last);
        if (delta > COUNTS_PER_REV / 2) delta -= COUNTS_PER_REV;
        if (delta < -COUNTS_PER_REV / 2) delta += COUNTS_PER_REV;
        g_enc_counts += delta; /* TODO sign depends on magnet orientation */
    }
    g_enc_primed = true;
    g_enc_last = raw;
    return (int32_t)((int64_t)g_enc_counts * 25 / 32);
}

static void hal_watchdog_kick(void *ctx)
{
    ARG_UNUSED(ctx);
    gpio_pin_set_dt(&g_wdt, 1);
    k_busy_wait(50);
    gpio_pin_set_dt(&g_wdt, 0);
}

static void hal_buzzer(void *ctx, op_buzzer_t pattern)
{
    ARG_UNUSED(ctx);
    /* TODO: PWM tones / repeating alarm pattern via a k_work_delayable. */
    gpio_pin_set_dt(&g_buzz, pattern != OP_BUZZER_OFF);
}

static uint16_t hal_battery_mv(void *ctx)
{
    ARG_UNUSED(ctx);
    int16_t sample = 0;
    struct adc_sequence seq = {.buffer = &sample, .buffer_size = sizeof(sample)};
    adc_sequence_init_dt(&g_vbat, &seq);
    if (adc_read_dt(&g_vbat, &seq) != 0) return 0; /* 0 mV -> critical fault: fail safe */
    int32_t mv = sample;
    adc_raw_to_millivolts_dt(&g_vbat, &mv);
    return (uint16_t)(mv * 2); /* TODO: divider ratio from the schematic */
}

static uint64_t hal_time_ms(void *ctx)
{
    ARG_UNUSED(ctx);
    return (uint64_t)k_uptime_get();
}

int hal_zephyr_init(op_hal_t *out)
{
    const struct gpio_dt_spec *outs[] = {&g_step, &g_stby, &g_gate, &g_wdt, &g_buzz};
    for (size_t i = 0; i < ARRAY_SIZE(outs); i++) {
        if (!gpio_is_ready_dt(outs[i]) || gpio_pin_configure_dt(outs[i], GPIO_OUTPUT_INACTIVE) != 0) return -ENODEV;
    }
    if (!i2c_is_ready_dt(&g_enc) || !adc_is_ready_dt(&g_vbat)) return -ENODEV;
    if (adc_channel_setup_dt(&g_vbat) != 0) return -ENODEV;

    *out = (op_hal_t){
        .ctx = NULL,
        .motor_step = hal_motor_step,
        .motor_enable = hal_motor_enable,
        .encoder_read = hal_encoder_read,
        .watchdog_kick = hal_watchdog_kick,
        .buzzer = hal_buzzer,
        .battery_mv = hal_battery_mv,
        .time_ms = hal_time_ms,
    };
    return 0;
}
