/* Qi / BQ25120A charging state. The pod pauses delivery while it sits on a charger (hazard H8/H9). */
#ifndef CHARGER_H
#define CHARGER_H

#include <stdbool.h>

int charger_init(void);
bool charger_active(void);

#endif
