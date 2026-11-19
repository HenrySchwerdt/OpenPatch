/*
 * Spindle position for the delivery verification.
 *  Path A: TMAG5273 (I2C) absolute angle, unwrapped to a cumulative position in 1/16 steps.
 *  Path B: QDEC counts of two DRV5032 hall sensors, CPU-independent (coarse, ~1 count per spindle half-turn).
 * Without a TMAG node, or with CONFIG_OPENPATCH_SIM_ENCODER, path A is simulated (open loop).
 */
#ifndef ENCODER_H
#define ENCODER_H

#include <stdbool.h>
#include <stdint.h>

int encoder_init(void);
/* cumulative position in 1/OP_ENC_SUBSTEPS steps (what op_hal_t.encoder_read returns) */
int32_t encoder_read_substeps(void);
/* motor steps per spindle revolution (drive calibration); call once after op_pump_init() */
void encoder_set_steps_per_spindle_rev(uint32_t steps);
/* tell the simulated encoder how many steps really ran (no-op with real hardware) */
void encoder_sim_advance(uint32_t steps);
/* true if path A is open loop (no TMAG5273 node, CONFIG_OPENPATCH_SIM_ENCODER, or an optional TMAG that did not answer) */
bool encoder_is_simulated(void);
/* path B: |QDEC counts| accumulated since boot; false if there is no QDEC */
bool encoder_qdec_counts(uint32_t *abs_counts);

#endif
