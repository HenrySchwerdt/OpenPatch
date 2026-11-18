#include "dfu.h"

#include <zephyr/dfu/mcuboot.h>
#include <zephyr/logging/log.h>
#include <zephyr/mgmt/mcumgr/mgmt/callbacks.h>
#include <zephyr/mgmt/mcumgr/mgmt/mgmt.h>
#include <zephyr/mgmt/mcumgr/grp/img_mgmt/img_mgmt_callbacks.h>
#include <zephyr/sys/atomic.h>

LOG_MODULE_REGISTER(dfu, LOG_LEVEL_INF);

static atomic_t g_allowed;

static enum mgmt_cb_return upload_check(uint32_t event, enum mgmt_cb_return prev_status, int32_t *rc,
                                        uint16_t *group, bool *abort_more, void *data, size_t data_size)
{
    ARG_UNUSED(event);
    ARG_UNUSED(prev_status);
    ARG_UNUSED(group);
    ARG_UNUSED(data);
    ARG_UNUSED(data_size);
    if (atomic_get(&g_allowed)) return MGMT_CB_OK;
    LOG_WRN("DFU upload refused: delivery is active");
    *rc = MGMT_ERR_EACCESSDENIED;
    *abort_more = true;
    return MGMT_CB_ERROR_RC;
}

static struct mgmt_callback g_check_cb = {.callback = upload_check, .event_id = MGMT_EVT_OP_IMG_MGMT_DFU_CHUNK};

int dfu_init(void)
{
    mgmt_callback_register(&g_check_cb);
    return 0;
}

void dfu_set_allowed(bool allowed) { atomic_set(&g_allowed, allowed ? 1 : 0); }

void dfu_confirm_image(void)
{
    if (boot_is_img_confirmed()) return;
    int rc = boot_write_img_confirmed();
    if (rc) LOG_ERR("confirming the image failed (%d)", rc);
    else LOG_INF("running image confirmed");
}
