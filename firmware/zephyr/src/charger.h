/* Qi field / charge-controller status inputs. The pod pauses delivery while it sits on a charger (hazard H8/H9).
 * Boards without a charger (dev kit, bench controller): charger_active() is always false. */
#ifndef CHARGER_H
#define CHARGER_H

#include <stdbool.h>

int charger_init(void);
bool charger_active(void);

#endif
