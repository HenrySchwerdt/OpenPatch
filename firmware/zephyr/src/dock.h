/*
 * DOCKED input: magnet in the cannula adapter + Hall switch on the PCB (spec/design-parameters.md
 * section 1b). A pod that is not docked never delivers: the portable core samples this through
 * op_hal_t.docked and the safety supervisor vetoes every step while it is false.
 * Fail-safe: a missing devicetree property or an unready GPIO reads as "not docked".
 * With CONFIG_OPENPATCH_SIM_DOCK (dev kit) a button press toggles a simulated dock input.
 */
#ifndef DOCK_H
#define DOCK_H

#include <stdbool.h>

int dock_init(void);
bool dock_present(void);

#endif
