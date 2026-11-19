/*
 * Motor current sense (bench controller): the SAADC samples the voltage across the STSPIN220 sense
 * resistor while a step burst runs; peak and mean go to the core through op_hal_t.motor_stats and
 * feed its occlusion detector and the bench CSV. Present only if /zephyr,user has the "imot"
 * io-channel; without it every function is a no-op and motor_stats() reports false.
 */
#ifndef CURRENT_SENSE_H
#define CURRENT_SENSE_H

#include <stdbool.h>

#include "op/op_hal.h"

int current_sense_init(void);
bool current_sense_available(void);
/* Start sampling (before the first step) / stop and read the burst statistics (after the last). */
void current_sense_begin(void);
void current_sense_end(void);
/* Statistics of the most recent begin..end pair; false if there is no current sense. */
bool current_sense_stats(op_motor_stats_t *out);

#endif
