/*
 * OpenPatch GATT service STUB (UUIDs: firmware/docs/openpatch-protocol.md).
 * UNTESTED. Bonding/pairing policy and connection-parameter tuning are TODO.
 */
#include "ble_openpatch.h"

#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(ble_op, LOG_LEVEL_INF);

/* 2E092A48-506C-477E-ADD4-448BF149xxxx */
#define OP_UUID(x16) BT_UUID_128_ENCODE(0x2E092A48, 0x506C, 0x477E, 0xADD4, (0x448BF1490000ULL | (x16)))

static struct bt_uuid_128 svc_uuid = BT_UUID_INIT_128(OP_UUID(0x0001));
static struct bt_uuid_128 cmd_uuid = BT_UUID_INIT_128(OP_UUID(0x0002));
static struct bt_uuid_128 rsp_uuid = BT_UUID_INIT_128(OP_UUID(0x0003));

static openpatch_rx_cb_t g_rx;
static bool g_notify_enabled;

static ssize_t on_cmd_write(struct bt_conn *conn, const struct bt_gatt_attr *attr, const void *buf, uint16_t len,
                            uint16_t offset, uint8_t flags)
{
    ARG_UNUSED(conn);
    ARG_UNUSED(attr);
    ARG_UNUSED(flags);
    if (offset != 0) return BT_GATT_ERR(BT_ATT_ERR_INVALID_OFFSET);
    if (len == 0 || len > 244) return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
    if (g_rx) g_rx(buf, len);
    return len;
}

static void on_ccc_changed(const struct bt_gatt_attr *attr, uint16_t value)
{
    ARG_UNUSED(attr);
    g_notify_enabled = (value == BT_GATT_CCC_NOTIFY);
}

BT_GATT_SERVICE_DEFINE(openpatch_svc,
    BT_GATT_PRIMARY_SERVICE(&svc_uuid),
    BT_GATT_CHARACTERISTIC(&cmd_uuid.uuid, BT_GATT_CHRC_WRITE | BT_GATT_CHRC_WRITE_WITHOUT_RESP,
                           BT_GATT_PERM_WRITE_ENCRYPT, NULL, on_cmd_write, NULL),
    BT_GATT_CHARACTERISTIC(&rsp_uuid.uuid, BT_GATT_CHRC_NOTIFY, BT_GATT_PERM_NONE, NULL, NULL, NULL),
    BT_GATT_CCC(on_ccc_changed, BT_GATT_PERM_READ_ENCRYPT | BT_GATT_PERM_WRITE_ENCRYPT));

static const struct bt_data ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
    BT_DATA_BYTES(BT_DATA_UUID128_ALL, OP_UUID(0x0001)),
};
static const struct bt_data sd[] = {
    BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME, sizeof(CONFIG_BT_DEVICE_NAME) - 1),
};

int openpatch_ble_init(openpatch_rx_cb_t rx)
{
    g_rx = rx;
    int err = bt_enable(NULL);
    if (err) return err;
    err = bt_le_adv_start(BT_LE_ADV_CONN_FAST_1, ad, ARRAY_SIZE(ad), sd, ARRAY_SIZE(sd));
    if (err) LOG_ERR("advertising failed (%d)", err);
    return err;
}

int openpatch_ble_notify(const uint8_t *data, size_t len)
{
    if (!g_notify_enabled) return -ENOTCONN;
    return bt_gatt_notify_uuid(NULL, &rsp_uuid.uuid, openpatch_svc.attrs, data, (uint16_t)len);
}
