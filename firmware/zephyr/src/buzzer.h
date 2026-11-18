#ifndef BUZZER_H
#define BUZZER_H

#include "op/op_hal.h"

int buzzer_init(void);
void buzzer_set(op_buzzer_t pattern);
/* user pressed the button: silence an active alarm until the next alarm is raised */
void buzzer_silence(void);

#endif
