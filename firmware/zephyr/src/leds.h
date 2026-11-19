/* Two status LEDs of the bench controller (status-led-gpios / fault-led-gpios in the devicetree).
 * Boards without them: every function is a no-op. */
#ifndef LEDS_H
#define LEDS_H

#include <stdbool.h>

int leds_init(void);
/* status: on = active and docked, off = otherwise; blink = bench sequence running (overrides on).
 * fault: on = a fault is latched. Called from the main loop once per tick. */
void leds_update(bool status_on, bool blink, bool fault);

#endif
