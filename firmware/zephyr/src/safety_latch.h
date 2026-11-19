/*
 * Interface to the hardware motor-power latch (electronics/README.md section 3):
 *   ARM_CLK  rising edge sets MOT_ALLOW (U7 connects VBAT -> VMOT)
 *   KILL_N   low clears the latch (MCU path "motor off")
 *   LATCH_Q_MON reads MOT_ALLOW back
 * The TPL5010 clears the latch on its own when it is not served. The bench controller has a plain
 * MCU enable input instead (motor-enable-gpios + optional motor-allow-mon-gpios). Without the devicetree
 * properties (dev kit) every function is a successful no-op.
 */
#ifndef SAFETY_LATCH_H
#define SAFETY_LATCH_H

#include <stdbool.h>

int safety_latch_init(void);
/* true only if the latch really reads back armed; false -> motor must stay off */
bool safety_latch_arm(void);
void safety_latch_kill(void);
bool safety_latch_present(void);

#endif
