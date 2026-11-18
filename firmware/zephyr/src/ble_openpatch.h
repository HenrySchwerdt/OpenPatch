#ifndef BLE_OPENPATCH_H
#define BLE_OPENPATCH_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Bring up the Bluetooth stack, load bonds, start advertising. Frames from Command writes are
 * posted to the main thread with app_evt_post(APP_EVT_RX_FRAME, ...). */
int openpatch_ble_init(void);
/* Send one frame (<= 244 B) as notification on the Response characteristic. */
int openpatch_ble_notify(const uint8_t *data, size_t len);
/* Button press: accept pairing (LE Secure Connections, Just Works) for CONFIG_OPENPATCH_PAIRING_WINDOW_S. */
void openpatch_ble_open_pairing_window(void);
bool openpatch_ble_pairing_window_open(void);

#endif
