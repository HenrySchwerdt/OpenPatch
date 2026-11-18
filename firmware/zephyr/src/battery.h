#ifndef BATTERY_H
#define BATTERY_H

#include <stdint.h>

int battery_init(void);
/* VBAT in mV; 0 on measurement failure (the core treats 0 as BATTERY_CRITICAL: fail safe) */
uint16_t battery_vbat_mv(void);
/* VMOT in mV (rail check after arming the latch); 0 on failure */
uint16_t battery_vmot_mv(void);

#endif
