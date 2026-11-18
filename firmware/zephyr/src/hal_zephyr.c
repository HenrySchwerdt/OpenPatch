/*
 * Zephyr implementation of op_hal_t for the OpenPatch pod (nRF52840 / ISP1807).
 * UNTESTED ON HARDWARE (no board exists yet): every timing, sign and register value marked
 * VERIFY must be checked with a scope and a scale before the first delivery.
 *
 * Motor power-up sequence (motor_enable(true)):
 *   1. MODE1..4 levels with STBY low  (STSPIN220 samples them when STBY is released)
 *   2. ARM_CLK edge -> safety latch -> VMOT (read back LATCH_Q_MON and check VMOT on SAADC)
 *   3. STBY high, DIR set
 * Power-down (motor_enable(false)): STBY low, then KILL_N pulse clears the latch.
 */
#include "hal_zephyr.h"

#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "battery.h"
#include "board_io.h"
#include "buzzer.h"
#include "encoder.h"
#include "safety_latch.h"
#include "step_gen.h"
#include "wdt_tpl5010.h"

LOG_MODULE_REGISTER(hal, LOG_LEVEL_INF);

static const struct gpio_dt_spec g_dir = GPIO_DT_SPEC_GET(OP_ZU, motor_dir_gpios);
static const struct gpio_dt_spec g_mode1 = GPIO_DT_SPEC_GET(OP_ZU, motor_mode1_gpios);
static const struct gpio_dt_spec g_mode2 = GPIO_DT_SPEC_GET(OP_ZU, motor_mode2_gpios);
static const struct gpio_dt_spec g_stby = GPIO_DT_SPEC_GET(OP_ZU, motor_stby_gpios);
static const struct gpio_dt_spec g_fault = GPIO_DT_SPEC_GET(OP_ZU, motor_fault_gpios);
/* STCK (= MODE3) is owned by step_gen; DIR (= MODE4) is set here */
static const struct gpio_dt_spec g_stck_mode = GPIO_DT_SPEC_GET(OP_ZU, motor_stck_gpios);

#define STBY_WAKE_MS 2 /* VERIFY: driver wake-up time after STBY/RESET release */
#define LATCH_SETTLE_MS 4 /* VERIFY: TPS22916C rise time + VMOT sense divider settling */
#define MODE_BIT(n) ((CONFIG_OPENPATCH_STSPIN_MODE_BITS >> (n)) & 1)

static bool g_armed;
static uint32_t g_unseen_steps; /* steps commanded since the last hall (QDEC) count */
static uint32_t g_last_qdec;

static int hal_motor_step(void *ctx, uint32_t steps)
{
    ARG_UNUSED(ctx);
    if (!g_armed || steps == 0) return 0; /* not armed: nothing ran, the supervisor will latch INTERNAL */
    uint32_t done = step_gen_run(steps);
    encoder_sim_advance(done);

    uint32_t q;
    if (encoder_qdec_counts(&q)) { /* hall path B: independent "does it move at all" check */
        if (q != g_last_qdec) {
            g_last_qdec = q;
            g_unseen_steps = 0;
        } else {
            g_unseen_steps += done;
            if (g_unseen_steps > CONFIG_OPENPATCH_QDEC_MAX_UNSEEN_STEPS)
                wdt_tpl5010_set_unhealthy("hall counter silent while stepping");
        }
    }
    return (int)done;
}

static void hal_motor_enable(void *ctx, bool enable)
{
    ARG_UNUSED(ctx);
    if (!enable) {
        gpio_pin_set_dt(&g_stby, 0);
        safety_latch_kill();
        g_armed = false;
        return;
    }
    if (g_armed) return;

    gpio_pin_set_dt(&g_stby, 0);
    gpio_pin_configure_dt(&g_stck_mode, GPIO_OUTPUT_INACTIVE);
    gpio_pin_set_dt(&g_mode1, MODE_BIT(0));
    gpio_pin_set_dt(&g_mode2, MODE_BIT(1));
    gpio_pin_set_dt(&g_stck_mode, MODE_BIT(2)); /* MODE3 */
    gpio_pin_set_dt(&g_dir, MODE_BIT(3));       /* MODE4 */

    if (!safety_latch_arm()) return; /* stays off; motor_step() returns 0 */
    if (safety_latch_present()) {
        k_msleep(LATCH_SETTLE_MS);
        uint16_t vmot = battery_vmot_mv();
        if (!IS_ENABLED(CONFIG_OPENPATCH_SIM_BATTERY) && vmot < CONFIG_OPENPATCH_VMOT_MIN_MV) {
            LOG_ERR("VMOT %u mV after arming - load switch not conducting", vmot);
            safety_latch_kill();
            return;
        }
    }
    gpio_pin_set_dt(&g_stby, 1);
    k_msleep(STBY_WAKE_MS);
    gpio_pin_set_dt(&g_stck_mode, 0);
    gpio_pin_set_dt(&g_dir, CONFIG_OPENPATCH_MOTOR_DIR_FORWARD_LEVEL);
    if (gpio_pin_get_dt(&g_fault) > 0) { /* EN/FAULT pulled low by the driver */
        LOG_ERR("STSPIN220 reports a fault");
        gpio_pin_set_dt(&g_stby, 0);
        safety_latch_kill();
        return;
    }
    g_armed = true;
}

static int32_t hal_encoder_read(void *ctx)
{
    ARG_UNUSED(ctx);
    return encoder_read_substeps();
}

static void hal_watchdog_kick(void *ctx)
{
    ARG_UNUSED(ctx);
    /* Called at the end of op_pump_tick(): all supervisor checks of this tick passed. */
    wdt_tpl5010_heartbeat();
}

static void hal_buzzer(void *ctx, op_buzzer_t pattern)
{
    ARG_UNUSED(ctx);
    buzzer_set(pattern);
}

static uint16_t hal_battery_mv(void *ctx)
{
    ARG_UNUSED(ctx);
    return battery_vbat_mv();
}

static uint64_t hal_time_ms(void *ctx)
{
    ARG_UNUSED(ctx);
    return (uint64_t)k_uptime_get();
}

int hal_zephyr_init(op_hal_t *out)
{
    const struct gpio_dt_spec *outs[] = {&g_dir, &g_mode1, &g_mode2, &g_stby};
    for (size_t i = 0; i < ARRAY_SIZE(outs); i++) {
        if (!gpio_is_ready_dt(outs[i]) || gpio_pin_configure_dt(outs[i], GPIO_OUTPUT_INACTIVE) != 0) return -ENODEV;
    }
    if (!gpio_is_ready_dt(&g_fault) || gpio_pin_configure_dt(&g_fault, GPIO_INPUT) != 0) return -ENODEV;

    int rc = safety_latch_init();
    if (!rc) rc = step_gen_init();
    if (!rc) rc = battery_init();
    if (!rc) rc = buzzer_init();
    if (!rc) rc = encoder_init();
    if (!rc) rc = wdt_tpl5010_init();
    if (rc) {
        LOG_ERR("HAL init failed (%d)", rc);
        return rc;
    }
    uint32_t q;
    if (encoder_qdec_counts(&q)) g_last_qdec = q;

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
