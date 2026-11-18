#include "persist.h"

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/settings/settings.h>

LOG_MODULE_REGISTER(persist, LOG_LEVEL_INF);

/* IDs between syncs: a tick appends <= ~6 events, a command <= 2 */
#define EVT_HEADROOM 16u
#define EVT_STEP 64u
/* worst case a prime burst (0.52 U = 64 steps on the finest drive) between two syncs, plus slack */
#define RES_HEADROOM_STEPS 80u
#define RES_STEP_STEPS 96u

struct res_rec {
    uint32_t fill_mu;
    uint32_t consumed_steps; /* includes the safety margin */
    uint8_t filled;
} __packed;

struct pod_rec {
    uint32_t pair_id;
    uint32_t activation_id;
    uint32_t wear_ceiling_s; /* >= real wear */
    uint8_t role;
    uint8_t active;
} __packed;

/* wear: rewrite when the stored ceiling is closer than WEAR_REFRESH_S to the real value */
#define WEAR_CEILING_S 900u
#define WEAR_REFRESH_S 300u

static struct persist_state g_loaded;
static struct pod_rec g_pod_stored;
static bool g_pod_stored_valid;
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
    if (settings_name_steq(name, "pod", &next) && !next) {
        struct pod_rec r;
        if (len != sizeof r || read_cb(cb_arg, &r, sizeof r) < 0) return -EIO;
        g_pod_stored = r;
        g_pod_stored_valid = true;
        g_loaded.pod_valid = true;
        g_loaded.pod_pair_id = r.pair_id;
        g_loaded.pod_role = r.role;
        g_loaded.pod_active = r.active != 0;
        g_loaded.pod_activation_id = r.activation_id;
        g_loaded.pod_wear_ceiling_s = r.wear_ceiling_s;
        return 0;
    }
    if (settings_name_steq(name, "cal", &next) && !next) {
        if (len != sizeof g_loaded.cal || read_cb(cb_arg, &g_loaded.cal, sizeof g_loaded.cal) < 0) return -EIO;
        g_loaded.cal_stored = true;
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

#if defined(CONFIG_OPENPATCH_DRIVE_FAULHABER_16_1)
#define BUILD_DRIVE OP_DRIVE_FAULHABER_16_1
#else
#define BUILD_DRIVE OP_DRIVE_ZWBPD006006_5_1 /* default, CONFIG_OPENPATCH_DRIVE_ZWBPD006006_5_1 */
#endif

const op_drive_cal_t *persist_drive_cal(const struct persist_state *st)
{
    static op_drive_cal_t build;
    static op_drive_cal_t chosen;
    if (op_drive_cal_preset(BUILD_DRIVE, &build) != OP_OK) return NULL; /* cannot happen */
    if (!st->cal_stored) {
        /* virgin pod: the build's drive becomes the pod's drive */
        int rc = settings_save_one("op/cal", &build, sizeof build);
        if (rc) {
            LOG_ERR("saving drive calibration failed (%d) - refusing to deliver", rc);
            return NULL;
        }
        LOG_INF("drive calibration stored: %u uU/step", (unsigned)build.micro_u_per_step);
        chosen = build;
        return &chosen;
    }
    if (op_drive_cal_validate(&st->cal) != OP_OK || memcmp(&st->cal, &build, sizeof build) != 0) {
        LOG_ERR("stored drive calibration is invalid or differs from this build - refusing to deliver");
        return NULL;
    }
    chosen = st->cal;
    return &chosen;
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

void persist_apply_pod(op_pump_t *p, const struct persist_state *st)
{
    if (!st->pod_valid) return;
    op_pump_restore_pod(p, st->pod_pair_id, st->pod_role, st->pod_active, st->pod_activation_id,
                        (uint64_t)st->pod_wear_ceiling_s * 1000u);
}

static void sync_pod(const op_pump_t *p)
{
    uint32_t wear_s = (uint32_t)(p->pod.wear_ms / 1000u);
    struct pod_rec r = {
        .pair_id = p->pod.pair_id,
        .activation_id = p->pod.activation_id,
        .wear_ceiling_s = p->pod.active ? wear_s + WEAR_CEILING_S : 0u,
        .role = p->pod.role,
        .active = p->pod.active ? 1 : 0,
    };
    if (g_pod_stored_valid) {
        bool same_ident = g_pod_stored.pair_id == r.pair_id && g_pod_stored.role == r.role &&
                          g_pod_stored.active == r.active && g_pod_stored.activation_id == r.activation_id;
        bool wear_ok = !r.active || g_pod_stored.wear_ceiling_s >= wear_s + WEAR_REFRESH_S;
        if (same_ident && wear_ok) return;
    } else if (r.pair_id == 0 && !r.active) {
        return; /* virgin pod, nothing to remember */
    }
    int rc = settings_save_one("op/pod", &r, sizeof r);
    if (rc) {
        LOG_ERR("saving pod state failed (%d)", rc);
        return;
    }
    g_pod_stored = r;
    g_pod_stored_valid = true;
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
    sync_pod(p);
}
