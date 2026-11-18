/*
 * TPL5010 external watchdog service. The WAKE pulse interrupts the MCU; the ISR answers
 * with a DONE pulse ONLY IF the main loop proved liveness recently (heartbeat from the end
 * of op_pump_tick(), i.e. after all supervisor checks) and nothing marked the system
 * unhealthy. DONE is never produced by a hardware peripheral (no PPI) so a hung CPU cannot
 * keep the motor latch armed.
 */
#ifndef WDT_TPL5010_H
#define WDT_TPL5010_H

int wdt_tpl5010_init(void);
void wdt_tpl5010_heartbeat(void);
/* Latch an unhealthy state: DONE is withheld until reset (watchdog resets MCU, clears latch). */
void wdt_tpl5010_set_unhealthy(const char *why);

#endif
