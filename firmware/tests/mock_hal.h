#ifndef MOCK_HAL_H
#define MOCK_HAL_H

#include "op/op_hal.h"

typedef struct {
    uint64_t now_ms;
    uint16_t battery_mv;
    int64_t enc_x100;          /* encoder position * 100 (substeps) */
    uint32_t delivered_pct;    /* % of commanded steps the encoder sees (100 = healthy) */
    int steps_limit;           /* -1 unlimited; else max steps motor executes */
    uint32_t total_steps;
    bool enabled;
    bool stepped_while_disabled;
    int kicks;
    int enable_calls;
    op_buzzer_t buzzer;
    uint32_t call_order_violations;
    bool docked;               /* DOCKED input; default true */
    bool charger;              /* charger present; default false */
    bool has_stats;            /* motor current sense present (enables the occlusion detector); default false */
    uint16_t peak_ma, mean_ma; /* what the current sense reports for every burst */
    uint16_t stats_samples;    /* default 10 */
    bool no_battery;           /* battery_mv hook is NULL (USB-powered bench board) */
} mock_hal_t;

void mock_hal_init(mock_hal_t *m);
op_hal_t mock_hal_make(mock_hal_t *m);
/* the same HAL without battery monitoring: battery_mv == NULL */
op_hal_t mock_hal_make_no_battery(mock_hal_t *m);

#endif
