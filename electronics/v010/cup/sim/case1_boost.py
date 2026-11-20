"""Case 1: TPS61023 5 V boost start-up from the cell, bulk-cap sizing, cell droop at motor peak current, UVLO / collapse.

Boost = behavioural averaged model (lib/tps61023_beh.inc); load switch = TI TPS2553 PSpice model; motor = 2 x (26.5 + 0.305) ohm + 5 mH, both phases on.
"""
import json
import numpy as np
import simlib as S

DECK = """* case 1 boost start-up (%(tag)s)
.include @LIB@/tps61023_beh.inc
.include @MODELS@/TPS2553_ng.lib
Vrail v3v3 0 3.3
%(cell)s
Vsp sup_permit 0 PWL(0 0 1m 0 1.001m 3.3)
Vma mot_allow 0 PWL(0 0 6m 0 6.001m 3.3)
%(boost)s
%(sw)s
%(motor)s
%(opts)s
.tran 2u %(tstop)s
.control
run
wrdata @RES@/%(name)s.csv v(vbat) v(vmot_pre) v(vmot) i(Vcell) v(oc_ok) v(xu8.ss)
.endc
.end
"""
P_NEED = 2.09   # W from the cell: 2 x 0.184 A x 4.96 V / eta 0.88 (case 4 gives the same coil current)
NAMES = ["vbat", "vpre", "vmot", "icell", "ocok", "ss"]


def one(ocv, rint, cb=S.CB1_EFF, c21=S.C21_EFF, rscale=1.0, tag="", tstop="25m", vcell_extra=""):
    name = "c1_%s" % tag
    deck = DECK % dict(tag=tag, cell=S.snip_cell(ocv, rint, vcell_extra), boost=S.snip_boost("sup_permit", cb), sw=S.snip_switch("mot_allow", c21),
                       motor=S.snip_motor_res(rscale), opts=S.SPICE_OPTS, tstop=tstop, name=name)
    w, log = S.run_wave(deck, name, NAMES, mode="ps")
    return w, log


def metrics(w):
    m = {}
    t5 = w.first_cross("vpre", 4.8, 1.0e-3)
    m["t_boost_ms"] = None if t5 is None else (t5 - 1.0e-3) * 1e3
    a = (w.t >= 1.0e-3) & (w.t <= 5.9e-3)         # boost alone, switch still open
    b = (w.t >= 6.0e-3) & (w.t <= 12e-3)           # switch closes into C21 + motor
    c = (w.t >= 15e-3)
    m["inrush_a"] = float(-w["icell"][a].min())    # cell current is negative out of Vcell in ngspice
    m["vbat_min_boost"] = float(w["vbat"][a].min())
    dt = np.diff(w.t, prepend=w.t[0])
    m["dip_us_below_2v5"] = float(1e6 * np.sum(dt[a & (w["vbat"] < 2.5)]))
    m["vpre_max_boost"] = float(w["vpre"][a].max())
    m["vbat_min_motor"] = float(w["vbat"][b].min())
    m["icell_peak_motor"] = float(-w["icell"][b].min())
    m["vpre_min_motor"] = float(w["vpre"][b].min())
    m["vmot_ss"] = float(np.mean(w["vmot"][c]))
    m["vpre_ss"] = float(np.mean(w["vpre"][c]))
    m["icell_ss"] = float(-np.mean(w["icell"][c]))
    m["vbat_ss"] = float(np.mean(w["vbat"][c]))
    m["vpre_ripple"] = float(np.ptp(w["vpre"][c]))
    m["fault_seen"] = bool((w["ocok"][b | c] < 1.65).any())
    return m


def collapse_sweep(rint):
    """OCV ramps 4.2 -> 2.2 V in 400 ms with the motor running (quasi-static); find where the 5 V rail and the nRF VDDH limit give up."""
    name = "c1_sweep_r%g" % rint
    deck = DECK % dict(tag="sweep", cell=S.snip_cell("PWL(0 4.2 30m 4.2 430m 2.2)", rint), boost=S.snip_boost("sup_permit"),
                       sw=S.snip_switch("mot_allow"), motor=S.snip_motor_res(1.0), opts=S.SPICE_OPTS, tstop="440m", name=name)
    deck = deck.replace("Vsp sup_permit 0 PWL(0 0 1m 0 1.001m 3.3)", "Vsp sup_permit 0 PWL(0 0 1m 0 1.001m 3.3)")
    w, log = S.run_wave(deck, name, NAMES, mode="ps")
    if w is None:
        return None, None
    ocv = np.interp(w.t, [0, 30e-3, 430e-3, 1], [4.2, 4.2, 2.2, 2.2])
    res = {}
    i = np.where((w.t > 40e-3) & (w["vpre"] < 4.5))[0]
    res["ocv_vpre_lt_4v5"] = float(ocv[i[0]]) if len(i) else None
    i = np.where((w.t > 40e-3) & (w["vbat"] < 2.5))[0]
    res["ocv_vbat_lt_2v5"] = float(ocv[i[0]]) if len(i) else None
    i = np.where((w.t > 40e-3) & (w["vbat"] < 2.9))[0]
    res["ocv_vbat_lt_2v9"] = float(ocv[i[0]]) if len(i) else None
    res["ocv_collapse"] = float(ocv[-1]) if w.aborted else None   # run stopped = no operating point left (constant-power fold)
    return w, res


def run(plot=True):
    out = {"grid": {}, "bulk": {}, "sweep": {}, "valid": {}}
    # validation of the behavioural boost against the datasheet start-up time (VIN 2.5 V, COUT 10 uF, no load)
    deck = open(S.os.path.join(S.HERE, "netlists", "boost_validation.cir")).read()
    w, log = S.run_wave(deck, "c1_validation", ["vpre", "vbat", "icell"])
    t = w.first_cross("vpre", 4.9, 0.1e-3)
    out["valid"] = {"t_start_us": (t - 100e-6) * 1e6, "datasheet_us": 700}
    # grid: OCV x Rint
    for ocv in (3.0, 3.4, 3.7, 4.2):
        for rint in (0.5, 0.8, 1.2, 1.6):
            w, log = one(ocv, rint, tag="v%g_r%g" % (ocv, rint))
            pmax = ocv * ocv / (4 * rint)
            if w is not None and not w.aborted and w["vbat"][w.t > 8e-3].min() > 1.0:
                m = metrics(w)
            elif w is not None:
                m = {"collapse": True, "vbat_at_stop": float(w["vbat"][-1]), "icell_at_stop": float(-w["icell"][-1]), "t_stop_ms": float(w.t[-1] * 1e3)}
            else:    # no solution: constant-power load beyond the maximum power the cell can deliver (physical collapse), check analytically
                m = {"collapse": True, "log": log[-300:]}
            m["p_max_w"] = pmax
            m["p_need_w"] = P_NEED
            out["grid"]["%g_%g" % (ocv, rint)] = m
    # bulk sizing at OCV 3.4 V / 0.8 ohm, effective capacitance on VMOT_PRE (CB1)
    for cb in (2e-6, 4e-6, 8e-6, 15e-6, 30e-6):
        w, log = one(3.4, 0.8, cb=cb, tag="cb%g" % (cb * 1e6))
        out["bulk"]["%g" % (cb * 1e6)] = metrics(w) if w is not None else {"error": "no convergence"}
    # collapse sweeps
    waves = {}
    for rint in (0.5, 0.8, 1.2, 1.6):
        w, res = collapse_sweep(rint)
        out["sweep"]["%g" % rint] = res
        waves[rint] = w
    json.dump(out, open(S.os.path.join(S.RES, "case1.json"), "w"), indent=1)
    if plot:
        make_plots(waves)
    return out


def make_plots(waves):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(2, 2, figsize=(9, 5.4))
    for ax, ocv in zip(axs.flat, (3.0, 3.4, 3.7, 4.2)):
        w, _ = one(ocv, S.RINT_NOM, tag="plot_v%g" % ocv, tstop="14m")
        if w is None:
            continue
        ax.plot(w.t * 1e3, w["vpre"], label="VMOT_PRE")
        ax.plot(w.t * 1e3, w["vmot"], label="VMOT", lw=0.9)
        ax.plot(w.t * 1e3, w["vbat"], label="VBAT")
        ax2 = ax.twinx()
        ax2.plot(w.t * 1e3, -w["icell"], color="tab:red", lw=0.8, label="cell current")
        ax2.set_ylim(0, 1.5)
        ax.set_title("OCV %.1f V, Rint %.1f ohm" % (ocv, S.RINT_NOM), fontsize=9)
        ax.set_xlabel("ms")
        ax.set_ylabel("V")
        ax2.set_ylabel("A", color="tab:red")
        ax.grid(alpha=0.3)
        ax.set_ylim(0, 5.5)
        if ocv == 3.0:
            ax.legend(fontsize=7, loc="lower right")
    fig.suptitle("Case 1: boost start-up (EN at 1 ms), load switch closes at 6 ms into the motor", fontsize=10)
    fig.tight_layout()
    fig.savefig(S.os.path.join(S.HERE, "plots", "case1_startup.png"), dpi=70)
    plt.close(fig)
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.2))
    for rint, w in waves.items():
        if w is None:
            continue
        ocv = np.interp(w.t, [0, 30e-3, 430e-3, 1], [4.2, 4.2, 2.2, 2.2])
        axs[0].plot(ocv, w["vpre"], label="Rint %.1f" % rint)
        axs[1].plot(ocv, w["vbat"], label="Rint %.1f" % rint)
    axs[0].set_title("VMOT_PRE vs cell OCV (motor running)", fontsize=9)
    axs[1].set_title("VBAT at the board vs cell OCV (limit 2.5 V)", fontsize=9)
    axs[1].axhline(2.5, color="k", ls="--", lw=0.8)
    axs[0].axhline(4.5, color="k", ls="--", lw=0.8)
    for ax in axs:
        ax.set_xlim(4.2, 2.2)
        ax.set_xlabel("OCV (V)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(S.os.path.join(S.HERE, "plots", "case1_collapse.png"), dpi=70)
    plt.close(fig)


if __name__ == "__main__":
    r = run()
    print(json.dumps(r, indent=1)[:6000])
