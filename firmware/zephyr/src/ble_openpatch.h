#ifndef BLE_OPENPATCH_H
#define BLE_OPENPATCH_H

#include <stddef.h>
#include <stdint.h>

/* Called from the Bluetooth RX context for every Command write (one frame). */
typedef void (*openpatch_rx_cb_t)(const uint8_t *data, size_t len);

int openpatch_ble_init(openpatch_rx_cb_t rx);
/* Send one frame (<= 244 B) as notification on the Response characteristic. */
int openpatch_ble_notify(const uint8_t *data, size_t len);

#endif
