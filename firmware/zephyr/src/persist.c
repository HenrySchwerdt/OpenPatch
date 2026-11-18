#include "persist.h"

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/settings/settings.h>

LOG_MODULE_REGISTER(persist, LOG_LEVEL_INF);

/* IDs between syncs: a tick appends <= ~6 events, a command <= 2 */
#define EVT_HEADROOM 16u
#define EVT_STEP 64u
/* worst case a prime burst (40 steps) between two syncs, plus slack */
#define RES_HEADROOM_STEPS 48u
#define RES_STEP_STEPS 64u

struct res_rec {
    uint32_t fill_mu;
    uint32_t consumed_steps; /* includes the safety margin */
    uint8_t filled;
} __packed;

static struct persist_state g_loaded;
static uint32_t g_evt_ceiling;   /* what is in flash */
static struct res_rec g_res_stored;
static bool g_res_stored_valid;
static uint32_t g_res_baseline = UINT32_MAX; /* consumed right after restore: no write until it changes */

static int on_set(const char *name, size_t len, settings_read_cb read_cb, void *cb_arg)
{
    const char *next;
    if (settings_name_steq(name, "evt", &next) && !next) {
        return read_cb(cb_arg, &g_loaded.next_event_id, MIN(len, sizeof g_loaded.next_event_id)) >= 0 ? 0 : -EIO;
    }
    if (settings_name_steq(name, "seq", &next) && !next) {
        if (read_cb(cb_arg, &g_loaded.last_seq, MIN(len, sizeof g_loaded.last_seq)) < 0) return -EIO;
        g_loaded.seq_valid = true;
        return 0;
    }
    if (settings_name_steq(name, "res", &next) && !next) {
        struct res_rec r;
        if (len != sizeof r || read_cb(cb_arg, &r, sizeof r) < 0) return -EIO;
        g_res_stored = r;
        g_res_stored_valid = true;
        g_loaded.res_valid = true;
        g_loaded.res_fill_mu = r.fill_mu;
        g_loaded.res_consumed_steps = r.consumed_steps;
        return 0;
    }
    return -ENOENT;
}

SETTINGS_STATIC_HANDLER_DEFINE(openpatch, "op", NULL, on_set, NULL, NULL);

int persist_init(struct persist_state *out)
{
    memset(&g_loaded, 0, sizeof g_loaded);
    g_loaded.next_event_id = 1;
    int rc = settings_subsys_init();
    if (rc) return rc;
    rc = settings_load_subtree("op");
    if (rc) return rc;
    g_evt_ceiling = g_loaded.next_event_id;
    *out = g_loaded;
    LOG_INF("restored: next event %u, seq %s%u, reservoir %s", (unsigned)g_loaded.next_event_id,
            g_loaded.seq_valid ? "" : "(none) ", (unsigned)g_loaded.last_seq,
            g_loaded.res_valid ? "yes" : "no");
    return 0;
}

void persist_apply_reservoir(op_pump_t *p, const struct persist_state *st)
{
    if (!st->res_valid) return;
    p->res.filled = true;
    p->res.fill_mu = st->res_fill_mu;
    p->res.consumed_steps = st->res_consumed_steps;
    p->low_res_reported = op_res_is_low(&p->res);
    g_res_baseline = p->res.consumed_steps;
}

void persist_save_seq(void *ctx, uint16_t seq)
{
    ARG_UNUSED(ctx);
    int rc = settings_save_one("op/seq", &seq, sizeof seq);
    if (rc) LOG_ERR("saving seq failed (%d)", rc); /* worst case: one replayable frame after a reset */
}

static void sync_events(const op_pump_t *p)
{
    uint32_t next = op_log_next_id(&p->log);
    if (g_evt_ceiling >= next + EVT_HEADROOM) return;
    uint32_t ceiling = next + EVT_STEP;
    int rc = settings_save_one("op/evt", &ceiling, sizeof ceiling);
    if (rc) {
        LOG_ERR("saving event ceiling failed (%d)", rc);
        return;
    }
    g_evt_ceiling = ceiling;
}

static void sync_reservoir(const op_pump_t *p)
{
    if (!p->res.filled) return;
    bool refill = !g_res_stored_valid || g_res_stored.fill_mu != p->res.fill_mu;
    /* consumed is reset by a fill: stored value must never be below the real one */
    bool low_margin = g_res_stored_valid && g_res_stored.consumed_steps < p->res.consumed_steps + RES_HEADROOM_STEPS;
    bool lowered = g_res_stored_valid && g_res_stored.consumed_steps > p->res.consumed_steps + RES_STEP_STEPS + 16u;
    if (!refill && p->res.consumed_steps == g_res_baseline && !lowered) return; /* nothing happened since boot */
    if (!refill && !low_margin && !lowered) return;
    struct res_rec r = {
        .fill_mu = p->res.fill_mu,
        .consumed_steps = p->res.consumed_steps + (refill ? 0u : RES_STEP_STEPS),
        .filled = 1,
    };
    if (refill && r.consumed_steps < p->res.consumed_steps + RES_HEADROOM_STEPS)
        r.consumed_steps = p->res.consumed_steps + RES_HEADROOM_STEPS; /* margin from the first write */
    int rc = settings_save_one("op/res", &r, sizeof r);
    if (rc) {
        LOG_ERR("saving reservoir failed (%d)", rc);
        return;
    }
    g_res_stored = r;
    g_res_stored_valid = true;
    g_res_baseline = UINT32_MAX;
}

void persist_sync(const op_pump_t *p)
{
    sync_events(p);
    sync_reservoir(p);
}
