"""Case 2: TPS2553 current limit (ILIM 47 k), FAULT timing, FAULT -> U32 -> latch clear -> supply cut and stays cut until a fresh ARM_CLK edge;
TPL5010 timeout path; supply-domain mismatch (3V3 collapses while VBAT/boost is up)."""
import json
import numpy as np
import simlib as S
import chain as C

DOCKED_FWD = {"dock_n": "0", "mot_fwd": "3.3", "sup_permit": C.step(1e-3), "mcu_en": C.step(1e-3)}


def t_first(w, name, level, t0, rising):
    return w.first_cross(name, level, t0, rising)


def s1_short():
    p = dict(name="c2_short", ocv=3.7, drv=dict(DOCKED_FWD, arm_clk=C.pulse(8e-3)), load="short", short_t=25e-3, short_end=80e-3, short_r=0.5,
             tstop="160m", tstep="10u")
    # re-arm (fresh enable) at 110 ms: second ARM_CLK pulse
    p["drv"]["arm_clk"] = C.pwl([(0, 0), (8e-3, 0), (8.001e-3, 3.3), (8.1e-3, 3.3), (8.101e-3, 0), (110e-3, 0), (110.001e-3, 3.3), (110.1e-3, 3.3), (110.101e-3, 0)])
    w, log = C.run(p)
    m = {}
    if w is None:
        return None, {"error": log[-400:]}
    m["vmot_run_v"] = w.at("vmot", 20e-3)
    m["i_run_a"] = w.at("isw", 20e-3)
    m["ios_a"] = float(np.mean(w.window("isw", 26e-3, 31e-3)))
    m["ios_min_a"] = float(np.min(w.window("isw", 26e-3, 31e-3)))
    tf = t_first(w, "ocok", 1.65, 25e-3, False)
    m["t_fault_ms"] = None if tf is None else (tf - 25e-3) * 1e3
    if tf:
        tc = t_first(w, "clrn", 1.65, tf - 1e-3, False)
        tq = t_first(w, "latch_q", 1.65, tf - 1e-3, False) if "latch_q" in w.v else t_first(w, "perml", 1.65, tf - 1e-3, False)
        ta = t_first(w, "allow", 1.65, tf - 1e-3, False)
        tv = t_first(w, "vmot", 0.5, tf, False)
        m["t_clrn_after_fault_us"] = None if tc is None else (tc - tf) * 1e6
        m["t_allow_low_after_fault_us"] = None if ta is None else (ta - tf) * 1e6
        m["t_vmot_lt_0v5_after_fault_ms"] = None if tv is None else (tv - tf) * 1e3
    m["vmot_max_80_105ms"] = float(w.window("vmot", 85e-3, 105e-3).max())    # short removed at 80 ms, NO new ARM_CLK edge yet
    m["allow_max_80_105ms"] = float(w.window("allow", 85e-3, 105e-3).max())
    m["ocok_released_after_cut"] = bool(w.at("ocok", 100e-3) > 3.0)
    m["vmot_after_rearm"] = w.at("vmot", 150e-3)
    return w, m


def s_stall_worst():
    p = dict(name="c2_stall", ocv=3.7, rscale=0.9, drv=dict(DOCKED_FWD, arm_clk=C.pulse(8e-3)), tstop="50m", tstep="10u")
    w, log = C.run(p)
    if w is None:
        return None, {"error": log[-300:]}
    return w, {"i_a": float(np.mean(w.window("isw", 30e-3, 50e-3))), "fault": bool((w.window("ocok", 10e-3, 50e-3) < 1.65).any()), "vmot": w.at("vmot", 45e-3)}


def s_watchdog():
    # TPL5010 missed DONE: RSTn low (open drain) for tRSTn <= 320 ms; datasheet-timed source, not a model of the IC
    p = dict(name="c2_wdt", ocv=3.7, drv=dict(DOCKED_FWD, arm_clk=C.pulse(8e-3)), rstn_wave=C.pwl([(0, 0), (50e-3, 0), (50.001e-3, 3.3), (370e-3, 3.3), (370.001e-3, 0)]),
             tstop="480m", tstep="50u")
    w, log = C.run(p)
    if w is None:
        return None, {"error": log[-300:]}
    tq = t_first(w, "perml", 1.65, 50e-3, False)
    tv = t_first(w, "vmot", 0.5, 50e-3, False)
    return w, {"t_perml_low_after_rstn_us": None if tq is None else (tq - 50e-3) * 1e6, "t_vmot_lt_0v5_ms": None if tv is None else (tv - 50e-3) * 1e3,
               "vmot_max_after_rstn_release": float(w.window("vmot", 380e-3, 480e-3).max()), "vmot_before": w.at("vmot", 40e-3)}


def s_mismatch(permit_stuck=False):
    # nRF REG0 (the 3V3 rail) collapses at 30 ms while VBAT and the boost are still up
    name = "c2_mismatch_stuck" if permit_stuck else "c2_mismatch"
    p = dict(name=name, ocv=3.7, drv=dict(DOCKED_FWD, arm_clk=C.pulse(8e-3)), reg=C.pwl([(0, 1), (30e-3, 1), (30.001e-3, 0)]), tstop="120m", tstep="10u")
    if permit_stuck:
        p["force"] = {"sup_permit": 3.3}   # hard 3.3 V on SUP_PERMIT even while 3V3 is gone (worst case, not physical for a GPIO; pull-up fault)
        p["drv"] = {k: v for k, v in p["drv"].items() if k != "sup_permit"}
    w, log = C.run(p)
    if w is None:
        return None, {"error": log[-300:]}
    t0 = 30e-3
    ta = t_first(w, "allow", 0.66, t0, False)
    tp = t_first(w, "permit", 1.2, t0, False)
    tr = t_first(w, "v3v3", 0.8, t0, False)
    tvp = t_first(w, "vpre", 1.0, t0, False)
    tvm = t_first(w, "vmot", 0.5, t0, False)
    f = lambda t: None if t is None else (t - t0) * 1e3
    return w, {"t_v3v3_lt_0v8_ms": f(tr), "t_allow_lt_0v66_ms": f(ta), "t_permit_lt_1v2_ms": f(tp), "t_vpre_lt_1v_ms": f(tvp), "t_vmot_lt_0v5_ms": f(tvm),
               "allow_max_after_ms": float(w.window("allow", t0 + 0.005, 120e-3).max()), "vmot_at_120ms": w.at("vmot", 119e-3), "vpre_at_120ms": w.at("vpre", 119e-3)}


def run(plot=True):
    out = {}
    w1, out["short"] = s1_short()
    w2, out["stall_worst"] = s_stall_worst()
    w3, out["watchdog"] = s_watchdog()
    w4, out["mismatch"] = s_mismatch(False)
    w5, out["mismatch_permit_stuck"] = s_mismatch(True)
    json.dump(out, open(S.os.path.join(S.RES, "case2.json"), "w"), indent=1)
    if plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axs = plt.subplots(2, 2, figsize=(9, 5.6))
        for ax, w, ttl, xr in ((axs[0, 0], w1, "short at 25 ms, re-arm at 110 ms", None), (axs[0, 1], w3, "TPL5010 timeout (RSTn low 50..370 ms)", None),
                               (axs[1, 0], w4, "3V3 collapses at 30 ms (VBAT up)", (0.025, 0.07)), (axs[1, 1], w5, "same, SUP_PERMIT forced high", (0.025, 0.07))):
            if w is None:
                continue
            ax.plot(w.t * 1e3, w["vmot"], label="VMOT")
            ax.plot(w.t * 1e3, w["allow"], label="MOT_ALLOW")
            ax.plot(w.t * 1e3, w["permit"], label="SUP_PERMIT", lw=0.8)
            ax.plot(w.t * 1e3, w["ocok"], label="OC_OK", lw=0.8)
            ax.plot(w.t * 1e3, w["v3v3"], label="3V3", lw=0.8, ls="--")
            ax.set_title(ttl, fontsize=9)
            ax.set_xlabel("ms")
            ax.grid(alpha=0.3)
            if xr:
                ax.set_xlim(xr[0] * 1e3, xr[1] * 1e3)
        axs[0, 0].legend(fontsize=6, ncol=2)
        axs[0, 0].twinx().plot(w1.t * 1e3, w1["isw"], color="tab:red", lw=0.6)
        fig.tight_layout()
        fig.savefig(S.os.path.join(S.HERE, "plots", "case2_switch_latch.png"), dpi=70)
        plt.close(fig)
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
