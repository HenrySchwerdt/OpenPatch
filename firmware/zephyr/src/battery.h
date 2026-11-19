#ifndef BATTERY_H
#define BATTERY_H

#include <stdbool.h>
#include <stdint.h>

int battery_init(void);
/* VBAT in mV; 0 on measurement failure (the core treats 0 as BATTERY_CRITICAL: fail safe).
 * Boards without battery monitoring (CONFIG_OPENPATCH_BATTERY_MONITOR=n, USB-powered bench
 * controller) never call this: the HAL hands the core a NULL battery hook. */
uint16_t battery_vbat_mv(void);
/* true if the board has a VMOT sense channel (rail check after arming the latch) */
bool battery_vmot_available(void);
/* VMOT in mV; 0 on failure or without a VMOT channel */
uint16_t battery_vmot_mv(void);

#endif
