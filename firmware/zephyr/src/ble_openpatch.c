/*
 * OpenPatch GATT service (UUIDs: firmware/docs/openpatch-protocol.md).
 *
 * Pairing policy:
 *  - LE Secure Connections only (CONFIG_BT_SMP_SC_ONLY), one bond (a new bond replaces it).
 *  - Pairing requests are rejected unless the pairing window is open, which only a button
 *    press on the pod opens (hazard H7). The pod has no display, so the method is Just Works:
 *    encrypted but not MITM protected. The physical button press is the authorisation.
 *  - A connection from an unbonded peer outside the window is dropped immediately.
 *  - Command writes need an encrypted link. Application-layer AES-CCM comes on top (not done).
 */
#include "ble_openpatch.h"

#include <stdio.h>

#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/settings/settings.h>

#include "app_events.h"

LOG_MODULE_REGISTER(ble_op, LOG_LEVEL_INF);

/* 2E092A48-506C-477E-ADD4-448BF149xxxx */
#define OP_UUID(x16) BT_UUID_128_ENCODE(0x2E092A48, 0x506C, 0x477E, 0xADD4, (0x448BF1490000ULL | (x16)))

static struct bt_uuid_128 svc_uuid = BT_UUID_INIT_128(OP_UUID(0x0001));
static struct bt_uuid_128 cmd_uuid = BT_UUID_INIT_128(OP_UUID(0x0002));
static struct bt_uuid_128 rsp_uuid = BT_UUID_INIT_128(OP_UUID(0x0003));

static bool g_notify_enabled;
static struct k_work_delayable g_window_close;
static struct k_work g_adv_work;
static volatile bool g_window_open;

static ssize_t on_cmd_write(struct bt_conn *conn, const struct bt_gatt_attr *attr, const void *buf, uint16_t len,
                            uint16_t offset, uint8_t flags)
{
    ARG_UNUSED(conn);
    ARG_UNUSED(attr);
    ARG_UNUSED(flags);
    if (offset != 0) return BT_GATT_ERR(BT_ATT_ERR_INVALID_OFFSET);
    if (len == 0 || len > OP_FRAME_MAX) return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
    if (app_evt_post(APP_EVT_RX_FRAME, buf, len) != 0) LOG_WRN("event queue full, frame dropped");
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

static char g_name[sizeof("OpenPatch-XXXX")];
static struct bt_data sd[1];

/* ---- advertising ----------------------------------------------------------------- */
static void adv_start_fn(struct k_work *w)
{
    ARG_UNUSED(w);
    /* 1 s interval: the pod lives on a ~40 mAh cell. */
    int err = bt_le_adv_start(BT_LE_ADV_PARAM(BT_LE_ADV_OPT_CONN, 0x0640, 0x0780, NULL), ad, ARRAY_SIZE(ad), sd,
                              ARRAY_SIZE(sd));
    if (err && err != -EALREADY) LOG_ERR("advertising failed (%d)", err);
}

/* ---- pairing window ---------------------------------------------------------------- */
static void window_close_fn(struct k_work *w)
{
    ARG_UNUSED(w);
    g_window_open = false;
    LOG_INF("pairing window closed");
}

void openpatch_ble_open_pairing_window(void)
{
    g_window_open = true;
    k_work_reschedule(&g_window_close, K_SECONDS(CONFIG_OPENPATCH_PAIRING_WINDOW_S));
    LOG_INF("pairing window open for %d s", CONFIG_OPENPATCH_PAIRING_WINDOW_S);
}

bool openpatch_ble_pairing_window_open(void) { return g_window_open; }

static enum bt_security_err pairing_accept(struct bt_conn *conn, const struct bt_conn_pairing_feat *const feat)
{
    ARG_UNUSED(conn);
    ARG_UNUSED(feat);
    if (!g_window_open) {
        LOG_WRN("pairing rejected: no button press");
        return BT_SECURITY_ERR_PAIR_NOT_ALLOWED;
    }
    return BT_SECURITY_ERR_SUCCESS;
}

static const struct bt_conn_auth_cb auth_cb = {.pairing_accept = pairing_accept};

static void pairing_complete(struct bt_conn *conn, bool bonded)
{
    ARG_UNUSED(conn);
    LOG_INF("paired, bonded=%d", bonded);
    g_window_open = false;
    k_work_cancel_delayable(&g_window_close);
}

static void pairing_failed(struct bt_conn *conn, enum bt_security_err reason)
{
    ARG_UNUSED(conn);
    LOG_WRN("pairing failed (%d)", reason);
}

static struct bt_conn_auth_info_cb auth_info_cb = {.pairing_complete = pairing_complete, .pairing_failed = pairing_failed};

struct bond_probe {
    const bt_addr_le_t *peer;
    bool found;
};

static void bond_cb(const struct bt_bond_info *info, void *user_data)
{
    struct bond_probe *p = user_data;
    if (bt_addr_le_eq(&info->addr, p->peer)) p->found = true;
}

static bool peer_is_bonded(struct bt_conn *conn)
{
    struct bond_probe p = {.peer = bt_conn_get_dst(conn)};
    bt_foreach_bond(BT_ID_DEFAULT, bond_cb, &p);
    return p.found;
}

/* ---- connection callbacks ---------------------------------------------------------- */
static void connected(struct bt_conn *conn, uint8_t err)
{
    if (err) {
        LOG_WRN("connect failed (0x%02x)", err);
        return;
    }
    if (!g_window_open && !peer_is_bonded(conn)) {
        LOG_WRN("unbonded peer outside the pairing window: disconnect");
        bt_conn_disconnect(conn, BT_HCI_ERR_REMOTE_USER_TERM_CONN);
        return;
    }
    LOG_INF("connected");
}

static void disconnected(struct bt_conn *conn, uint8_t reason)
{
    ARG_UNUSED(conn);
    LOG_INF("disconnected (0x%02x)", reason);
    g_notify_enabled = false;
}

static void recycled(void)
{
    k_work_submit(&g_adv_work);
}

BT_CONN_CB_DEFINE(conn_cb) = {
    .connected = connected,
    .disconnected = disconnected,
    .recycled = recycled,
};

/* ---- public API -------------------------------------------------------------------- */
int openpatch_ble_init(void)
{
    k_work_init_delayable(&g_window_close, window_close_fn);
    k_work_init(&g_adv_work, adv_start_fn);

    int err = bt_conn_auth_cb_register(&auth_cb);
    if (!err) err = bt_conn_auth_info_cb_register(&auth_info_cb);
    if (err) return err;

    err = bt_enable(NULL);
    if (err) return err;
    if (IS_ENABLED(CONFIG_SETTINGS)) {
        err = settings_load_subtree("bt");
        if (err) LOG_WRN("loading bonds failed (%d)", err);
    }

    /* name: OpenPatch-XXXX from the last two address bytes */
    bt_addr_le_t addrs[CONFIG_BT_ID_MAX];
    size_t count = ARRAY_SIZE(addrs);
    bt_id_get(addrs, &count);
    if (count > 0) snprintf(g_name, sizeof g_name, "OpenPatch-%02X%02X", addrs[0].a.val[1], addrs[0].a.val[0]);
    else snprintf(g_name, sizeof g_name, "OpenPatch");
    bt_set_name(g_name);
    sd[0] = (struct bt_data)BT_DATA(BT_DATA_NAME_COMPLETE, g_name, strlen(g_name));

    adv_start_fn(NULL);
    LOG_INF("advertising as %s", g_name);
    return 0;
}

int openpatch_ble_notify(const uint8_t *data, size_t len)
{
    if (!g_notify_enabled) return -ENOTCONN;
    return bt_gatt_notify_uuid(NULL, &rsp_uuid.uuid, openpatch_svc.attrs, data, (uint16_t)len);
}
