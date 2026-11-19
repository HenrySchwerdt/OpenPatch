/* Bench test mode: shell commands (shell thread) -> queued events -> executed in main(). */
#include "bench.h"

#ifdef CONFIG_OPENPATCH_BENCH_MODE

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/shell/shell.h>

#include "board_io.h"
#include "encoder.h"
#include "op/bench_test.h"

LOG_MODULE_REGISTER(bench, LOG_LEVEL_INF);

enum bench_op { BOP_PREP = 1, BOP_RUN, BOP_STOP, BOP_STATUS, BOP_ACK, BOP_RESUME, BOP_LOG, BOP_OCC };

struct bench_cmd {
    uint8_t op;
    uint8_t nargs;
    uint32_t a[6];
};

static op_pump_t *g_pump;
static op_bench_t g_bench;
static const struct shell *g_sh; /* where answers and CSV go: the shell that issued the last command */
static uint32_t g_last_qdec;

/* ---- output ---------------------------------------------------------------------------- */
static void out(const char *fmt, ...)
{
    char line[160];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(line, sizeof line, fmt, ap);
    va_end(ap);
    if (g_sh) shell_print(g_sh, "%s", line);
    else LOG_INF("%s", line);
}

static const char *err_name(op_err_t e)
{
    static const char *const n[] = {"OK", "BAD_ARG", "LIMIT", "BUSY", "FAULT", "SUSPENDED", "NOT_SUSPENDED",
                                    "RESERVOIR", "PERSISTS", "UNSUPPORTED", "FRAME", "CRC", "VERSION", "REPLAY",
                                    "AUTH", "TOO_LARGE", "HOURLY", "NOT_FOUND", "SESSION", "NOT_DOCKED",
                                    "RELEASED", "ALREADY_ACTIVE", "PAIR", "WEAR_EXPIRED", "CHARGING"};
    return (unsigned)e < ARRAY_SIZE(n) ? n[e] : "?";
}

static const char *state_name(op_bench_state_t s)
{
    static const char *const n[] = {"idle", "pulsing", "pausing", "wait_rate", "done", "aborted"};
    return (unsigned)s < ARRAY_SIZE(n) ? n[s] : "?";
}

static void csv_header(void)
{
    out("CSV,pulse,cmd_mU,t_start_ms,t_end_ms,steps,expected_steps,total_steps,enc_substeps,qdec_counts,"
        "peak_mA,bursts,faults,result");
}

static void sink(void *ctx, const op_bench_rec_t *r)
{
    ARG_UNUSED(ctx);
    uint32_t q = g_last_qdec;
    (void)encoder_qdec_counts(&q);
    uint32_t dq = q - g_last_qdec;
    g_last_qdec = q;
    out("CSV,%u,%u,%u,%u,%u,%u,%u,%d,%u,%u,%u,0x%04x,%u", (unsigned)r->pulse, (unsigned)r->cmd_mu,
        (unsigned)r->t_start_ms, (unsigned)r->t_end_ms, (unsigned)r->steps, (unsigned)r->expected_steps,
        (unsigned)r->total_steps, (int)r->enc_substeps, (unsigned)dq, (unsigned)r->peak_ma, (unsigned)r->bursts,
        (unsigned)r->faults, (unsigned)r->result);
}

/* ---- commands executed on the main thread ---------------------------------------------- */
static void do_status(void)
{
    const op_pump_t *p = g_pump;
    out("bench: state=%s pulse=%u/%u completed=%u end_reason=%u", state_name(g_bench.state),
        (unsigned)g_bench.pulse, (unsigned)g_bench.cfg.pulses, (unsigned)g_bench.completed,
        (unsigned)g_bench.end_reason);
    out("pump: active=%d docked=%d suspended=%d bolus=%d faults=0x%04x reservoir_mU=%u delivered_steps=%u "
        "uU_per_step=%u",
        p->pod.active, p->pod.docked, p->de.suspended, p->de.bolus_active, (unsigned)p->sv.faults,
        (unsigned)op_res_remaining_mu(&p->res), (unsigned)p->de.delivered_steps, (unsigned)p->cal.micro_u_per_step);
    out("encoder=%s occ: enabled=%d tripped=%d windows=%u strikes=%u baseline_mA=%u last_slip=%u%% last_mean_mA=%u "
        "last_peak_mA=%u",
        encoder_is_simulated() ? "SIMULATED" : "TMAG5273", p->occ.enabled, p->occ.occluded,
        (unsigned)p->occ.windows, (unsigned)p->occ.strikes, (unsigned)p->occ.baseline_ma,
        (unsigned)p->occ.last_slip_pct, (unsigned)p->occ.last_mean_ma, (unsigned)p->occ.last_peak_ma);
    if (DT_NODE_HAS_PROP(OP_ZU, openpatch_placeholder_pins))
        out("WARNING: PLACEHOLDER PIN MAP - this firmware does not match the real board wiring");
}

static void do_log(uint32_t n)
{
    op_event_t ev[16];
    uint32_t from = op_log_next_id(&g_pump->log);
    from = from > n ? from - n : 0;
    uint32_t c = op_log_read(&g_pump->log, from, ev, n > 16 ? 16 : n);
    out("LOG,id,time_s,type,a,b");
    for (uint32_t i = 0; i < c; i++)
        out("LOG,%u,%u,%u,%d,%d", (unsigned)ev[i].id, (unsigned)ev[i].time_s, (unsigned)ev[i].type, (int)ev[i].a,
            (int)ev[i].b);
}

static void do_occ(const struct bench_cmd *c)
{
    op_occ_cfg_t cfg = g_pump->occ.cfg;
    if (c->nargs >= 6) {
        cfg = (op_occ_cfg_t){.abs_peak_ma = (uint16_t)c->a[0], .rise_pct = (uint16_t)c->a[1],
                             .slip_pct_min = (uint8_t)c->a[2], .stall_slip_pct = (uint8_t)c->a[3],
                             .window_steps = (uint16_t)c->a[4], .strikes_needed = (uint8_t)c->a[5],
                             .baseline_windows = g_pump->occ.cfg.baseline_windows};
        op_pump_set_occlusion_cfg(g_pump, &cfg);
    }
    out("occ: abs_peak_mA=%u rise_pct=%u slip_min=%u%% stall_slip=%u%% window_steps=%u strikes=%u enabled=%d",
        cfg.abs_peak_ma, cfg.rise_pct, cfg.slip_pct_min, cfg.stall_slip_pct, cfg.window_steps, cfg.strikes_needed,
        g_pump->occ.enabled);
}

void bench_handle_cmd(const struct app_evt *e)
{
    struct bench_cmd c;
    if (e->len != sizeof c) return;
    memcpy(&c, e->data, sizeof c);
    op_err_t err = OP_OK;
    switch (c.op) {
    case BOP_PREP:
        err = op_bench_prepare(g_pump, c.a[0], c.nargs > 1 ? c.a[1] : 0);
        out("prep: %s", err_name(err));
        break;
    case BOP_RUN: {
        op_bench_cfg_t cfg = {.pulses = c.a[0], .amount_mu = c.a[1], .pause_ms = c.a[2]};
        (void)encoder_qdec_counts(&g_last_qdec);
        err = op_bench_start(&g_bench, g_pump, &cfg);
        if (err == OP_OK) {
            csv_header();
            out("run: started %u x %u mU, pause %u ms (state %s)", (unsigned)cfg.pulses, (unsigned)cfg.amount_mu,
                (unsigned)cfg.pause_ms, state_name(g_bench.state));
        } else {
            out("run: refused: %s", err_name(err));
        }
        break;
    }
    case BOP_STOP:
        op_bench_abort(&g_bench, g_pump);
        out("stop: state=%s", state_name(g_bench.state));
        break;
    case BOP_ACK:
        err = op_pump_acknowledge(g_pump, 0xFFFF);
        out("ack: %s, faults now 0x%04x", err_name(err), (unsigned)g_pump->sv.faults);
        break;
    case BOP_RESUME:
        err = op_pump_resume(g_pump);
        out("resume: %s", err_name(err));
        break;
    case BOP_STATUS: do_status(); break;
    case BOP_LOG: do_log(c.nargs ? c.a[0] : 8); break;
    case BOP_OCC: do_occ(&c); break;
    default: break;
    }
}

void bench_tick(void)
{
    bool was = op_bench_running(&g_bench);
    op_bench_tick(&g_bench, g_pump);
    if (was && !op_bench_running(&g_bench))
        out("run: %s (completed %u of %u, reason %u)", state_name(g_bench.state), (unsigned)g_bench.completed,
            (unsigned)g_bench.cfg.pulses, (unsigned)g_bench.end_reason);
}

void bench_abort(void)
{
    if (op_bench_running(&g_bench)) {
        op_bench_abort(&g_bench, g_pump);
        out("run: aborted by emergency stop");
    }
}

bool bench_running(void) { return op_bench_running(&g_bench); }

void bench_init(op_pump_t *pump)
{
    g_pump = pump;
    op_bench_init(&g_bench, sink, NULL);
    LOG_WRN("BENCH TEST MODE: water only, never insulin, never on a body");
    if (DT_NODE_HAS_PROP(OP_ZU, openpatch_placeholder_pins))
        LOG_ERR("PLACEHOLDER PIN MAP: electronics/bench/pin-assignment.md has not been applied");
}

/* ---- shell (shell thread): parse, queue ------------------------------------------------- */
static int queue(const struct shell *sh, enum bench_op op, size_t argc, char **argv, size_t first, size_t min_args,
                 size_t max_args)
{
    size_t n = argc - first;
    if (n < min_args || n > max_args) {
        shell_error(sh, "expected %u..%u argument(s)", (unsigned)min_args, (unsigned)max_args);
        return -EINVAL;
    }
    struct bench_cmd c = {.op = (uint8_t)op, .nargs = (uint8_t)n};
    for (size_t i = 0; i < n; i++) {
        int err = 0;
        unsigned long v = shell_strtoul(argv[first + i], 10, &err);
        if (err || v > UINT32_MAX) {
            shell_error(sh, "bad number '%s'", argv[first + i]);
            return -EINVAL;
        }
        c.a[i] = (uint32_t)v;
    }
    g_sh = sh;
    if (app_evt_post(APP_EVT_BENCH_CMD, (const uint8_t *)&c, sizeof c) != 0) {
        shell_error(sh, "busy, try again");
        return -EBUSY;
    }
    return 0;
}

static int cmd_prep(const struct shell *sh, size_t argc, char **argv) { return queue(sh, BOP_PREP, argc, argv, 1, 1, 2); }
static int cmd_run(const struct shell *sh, size_t argc, char **argv) { return queue(sh, BOP_RUN, argc, argv, 1, 3, 3); }
static int cmd_stop(const struct shell *sh, size_t argc, char **argv) { return queue(sh, BOP_STOP, argc, argv, 1, 0, 0); }
static int cmd_status(const struct shell *sh, size_t argc, char **argv) { return queue(sh, BOP_STATUS, argc, argv, 1, 0, 0); }
static int cmd_ack(const struct shell *sh, size_t argc, char **argv) { return queue(sh, BOP_ACK, argc, argv, 1, 0, 0); }
static int cmd_resume(const struct shell *sh, size_t argc, char **argv) { return queue(sh, BOP_RESUME, argc, argv, 1, 0, 0); }
static int cmd_log(const struct shell *sh, size_t argc, char **argv) { return queue(sh, BOP_LOG, argc, argv, 1, 0, 1); }
static int cmd_occ(const struct shell *sh, size_t argc, char **argv)
{
    if (argc != 1 && argc != 7) {
        shell_error(sh, "usage: bench occ [<abs_peak_mA> <rise_pct> <slip_min_pct> <stall_slip_pct> <window_steps> <strikes>]");
        return -EINVAL;
    }
    return queue(sh, BOP_OCC, argc, argv, 1, argc - 1, argc - 1);
}

SHELL_STATIC_SUBCMD_SET_CREATE(
    sub_bench,
    SHELL_CMD_ARG(prep, NULL, "prep <fill_mU> [prime_steps]: pair, fill, activate, prime, resume (WATER ONLY)",
                  cmd_prep, 2, 1),
    SHELL_CMD_ARG(run, NULL, "run <pulses> <amount_mU> <pause_ms>: gravimetric pulse sequence, CSV per pulse",
                  cmd_run, 4, 0),
    SHELL_CMD_ARG(stop, NULL, "stop the running sequence", cmd_stop, 1, 0),
    SHELL_CMD_ARG(status, NULL, "pump, sequence and occlusion detector state", cmd_status, 1, 0),
    SHELL_CMD_ARG(ack, NULL, "acknowledge latched faults (refused while the cause persists)", cmd_ack, 1, 0),
    SHELL_CMD_ARG(resume, NULL, "resume delivery after a fault or stop", cmd_resume, 1, 0),
    SHELL_CMD_ARG(log, NULL, "log [n]: last n events (CSV)", cmd_log, 1, 1),
    SHELL_CMD_ARG(occ, NULL, "occ [abs_mA rise_pct slip_min stall_slip window strikes]: show/set detector",
                  cmd_occ, 1, 6),
    SHELL_SUBCMD_SET_END);

SHELL_CMD_REGISTER(bench, &sub_bench, "OpenPatch bench test mode (TEST ONLY, WATER ONLY)", NULL);

#endif /* CONFIG_OPENPATCH_BENCH_MODE */
