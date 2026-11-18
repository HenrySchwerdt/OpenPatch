#include "app_events.h"

#include <string.h>

#include <zephyr/kernel.h>

K_MSGQ_DEFINE(app_q, sizeof(struct app_evt), 6, 4);

int app_evt_post(enum app_evt_type type, const uint8_t *data, size_t len)
{
    struct app_evt e = {.type = (uint8_t)type};
    if (len > sizeof e.data) return -EMSGSIZE;
    if (data && len) memcpy(e.data, data, len);
    e.len = (uint8_t)len;
    return k_msgq_put(&app_q, &e, K_NO_WAIT) == 0 ? 0 : -ENOMEM;
}

int app_evt_wait(struct app_evt *out, int32_t timeout_ms)
{
    return k_msgq_get(&app_q, out, timeout_ms < 0 ? K_FOREVER : K_MSEC(timeout_ms)) == 0 ? 0 : -EAGAIN;
}
