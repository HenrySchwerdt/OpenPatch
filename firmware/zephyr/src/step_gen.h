/*
 * Step pulse generator: an RTC (counter API) alarm chain toggles STCK, so the CPU sleeps
 * between pulses and BLE is never starved by busy-waiting. The STSPIN220 steps on the
 * rising edge of STCK.
 */
#ifndef STEP_GEN_H
#define STEP_GEN_H

#include <stdbool.h>
#include <stdint.h>

int step_gen_init(void);
/* Blocking: emit `steps` pulses at CONFIG_OPENPATCH_STEP_RATE_HZ. Returns pulses actually
 * emitted (< steps on timeout / abort). Main thread only. */
uint32_t step_gen_run(uint32_t steps);
/* Abort a running burst from any context (idempotent). */
void step_gen_abort(void);

#endif
