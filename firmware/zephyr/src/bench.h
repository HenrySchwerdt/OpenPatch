/*
 * Bench test mode glue (bench controller, CONFIG_OPENPATCH_BENCH_MODE): the `bench` shell command
 * set on SEGGER RTT. TEST ONLY, WATER ONLY. Docs: firmware/docs/bench-testing.md.
 *
 * The shell runs on its own thread, the portable core is main-thread only: commands are queued as
 * APP_EVT_BENCH_CMD and executed (and answered) from main(). Everything goes through the normal pump
 * API, so the safety supervisor, dock precondition and fault handling are unchanged.
 */
#ifndef BENCH_H
#define BENCH_H

#include <stdbool.h>

#include "app_events.h"
#include "op/pump_controller.h"

#ifdef CONFIG_OPENPATCH_BENCH_MODE
void bench_init(op_pump_t *pump);
void bench_handle_cmd(const struct app_evt *e); /* main thread */
void bench_tick(void);                          /* main thread, once per tick, after op_pump_tick() */
void bench_abort(void);                         /* emergency stop / charger: end a running sequence */
bool bench_running(void);
#else
static inline void bench_init(op_pump_t *pump) { (void)pump; }
static inline void bench_handle_cmd(const struct app_evt *e) { (void)e; }
static inline void bench_tick(void) {}
static inline void bench_abort(void) {}
static inline bool bench_running(void) { return false; }
#endif

#endif
