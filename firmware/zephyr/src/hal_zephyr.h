#ifndef HAL_ZEPHYR_H
#define HAL_ZEPHYR_H

#include "op/op_hal.h"

/* Initialise GPIO/ADC/I2C and return the HAL for op_pump_init(). */
int hal_zephyr_init(op_hal_t *out);

#endif
