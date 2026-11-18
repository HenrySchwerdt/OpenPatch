/*
 * Hardware abstraction layer. The core never touches hardware directly.
 * The Zephyr port implements this in zephyr/src/hal_zephyr.c, tests use
 * tests/mock_hal.c.
 */
#ifndef OP_HAL_H
#define OP_HAL_H

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    OP_BUZZER_OFF = 0,
    OP_BUZZER_BEEP = 1,   /* single short confirmation beep */
    OP_BUZZER_ALARM = 2   /* repeating alarm until set to OFF */
} op_buzzer_t;

typedef struct op_hal {
    void *ctx;
    /* Execute `steps` forward motor steps (blocking). Returns steps executed. */
    int (*motor_step)(void *ctx, uint32_t steps);
    /* Driver power gate (second, independent path from the watchdog). */
    void (*motor_enable)(void *ctx, bool enable);
    /* Cumulative spindle position in 1/OP_ENC_SUBSTEPS steps. */
    int32_t (*encoder_read)(void *ctx);
    /* Feed the external watchdog (TPL5010 DONE pulse). */
    void (*watchdog_kick)(void *ctx);
    void (*buzzer)(void *ctx, op_buzzer_t pattern);
    uint16_t (*battery_mv)(void *ctx);
    /* Monotonic milliseconds since boot. */
    uint64_t (*time_ms)(void *ctx);
    /* DOCKED input (Hall switch + magnet in the cannula adapter). A NULL hook means "not docked". */
    bool (*docked)(void *ctx);
    /* Qi / USB charger present. A NULL hook means "no charger". */
    bool (*charger_present)(void *ctx);
} op_hal_t;

#endif /* OP_HAL_H */
