/*
 * Signed DFU over BLE (mcumgr SMP, MCUboot). Uploads are only accepted while delivery is
 * suspended (never swap firmware while the pod doses). A new image is confirmed by the
 * application after a self-test; otherwise MCUboot reverts at the next reset.
 */
#ifndef DFU_H
#define DFU_H

#include <stdbool.h>

int dfu_init(void);
/* main thread publishes whether DFU may start (pump suspended and no fault pending delivery) */
void dfu_set_allowed(bool allowed);
/* mark the running image good (idempotent) */
void dfu_confirm_image(void);

#endif
