"""Case 3: enable logic.  MOT_ALLOW = LATCH_Q AND SUP_PERMIT AND MCU_EN AND (DOCK_N XOR MOT_FWD)  (corrected design: XOR + AND3).
(a) all 32 input combinations at DC with the real gate models and pulls, (b) the same 32 through the whole chain (boost + TPS2553 -> VMOT),
(c) undefined / floating inputs, (d) power-up ramps, (e) brown-out dips, (f) single faults (stuck inputs, opened resistors)."""
import itertools
import json
import re
import numpy as np
import simlib as S
import chain as C

DOCKED = {"dock_n": "0"}          # DRV5032FA output is active low
UNDOCKED = {"dock_n": "3.3"}


def dc_deck(lq, sp, me, dn, mf):
    return ("* DC truth table\n.include @LIB@/aup.inc\n.include @LIB@/aup2.inc\nVr v3v3 0 3.3\n"
            "Vlq latch_q 0 %g\nVsp sup_permit 0 %g\nVme mcu_en 0 %g\nVdn dock_n 0 %g\nVmf mot_fwd 0 %g\n"
            "XU36 latch_q sup_permit mcu_en perm_l v3v3 0 aup_and3\nXU33 dock_n mot_fwd dock_ok v3v3 0 aup_xor2\nXU34 perm_l dock_ok mot_allow v3v3 0 aup_and2\n"
            "R90 mot_allow 0 100k\n.options gmin=1e-12\n.control\nop\nprint v(mot_allow)\n.endc\n.end\n" % (3.3 * lq, 3.3 * sp, 3.3 * me, 3.3 * dn, 3.3 * mf))


def truth_dc():
    rows = []
    for lq, sp, me, dn, mf in itertools.product((0, 1), repeat=5):
        out = S.ngspice(dc_deck(lq, sp, me, dn, mf), "c3_dc", mode="std")
        m = re.search(r"v\(mot_allow\)\s*=\s*([-0-9.e+]+)", out)
        v = float(m.group(1)) if m else float("nan")
        exp = int(lq and sp and me and (dn != mf))
        rows.append(dict(latch_q=lq, permit=sp, mcu_en=me, dock_n=dn, mot_fwd=mf, allow_v=v, expected=exp, ok=(v > 2.5) == bool(exp)))
    return rows


def chain_params(name, lq, sp, me, dn, mf, tstop="30m"):
    drv = {"sup_permit": C.step(1e-3) if sp else "0", "mcu_en": C.step(1e-3) if me else "0", "dock_n": "3.3" if dn else "0", "mot_fwd": "3.3" if mf else "0"}
    drv["arm_clk"] = C.pulse(8e-3) if lq else "0"
    return dict(name=name, ocv=3.7, drv=drv, tstop=tstop, tstep="10u")


def truth_chain():
    rows = []
    for lq, sp, me, dn, mf in itertools.product((0, 1), repeat=5):
        w, log = C.run(chain_params("c3_chain", lq, sp, me, dn, mf, "25m"))
        exp = int(lq and sp and me and (dn != mf))
        if w is None:
            rows.append(dict(latch_q=lq, permit=sp, mcu_en=me, dock_n=dn, mot_fwd=mf, vmot=None, expected=exp, ok=False))
            continue
        v = w.at("vmot", 24e-3)
        rows.append(dict(latch_q=lq, permit=sp, mcu_en=me, dock_n=dn, mot_fwd=mf, vmot=v, expected=exp, ok=(v > 4.0) == bool(exp)))
    return rows


def scen(name, desc, p, expect_off=True, t0=15e-3, t1=None):
    """run one scenario; verdict: motor supply (VMOT) must stay < 0.5 V and MOT_ALLOW < 0.66 V in [t0, end] when expect_off."""
    p = dict(p, name="c3_" + name)
    w, log = C.run(p)
    if w is None:
        return dict(name=name, desc=desc, error=log[-200:], verdict="ERROR")
    t1 = t1 or w.t[-1]
    vm = float(w.window("vmot", t0, t1).max())
    al = float(w.window("allow", t0, t1).max())
    on = vm > 4.0
    if expect_off:
        verdict = "PASS" if (vm < 0.5 and al < 0.66) else "FAIL"
    else:
        verdict = "PASS" if on else "FAIL"
    return dict(name=name, desc=desc, vmot_max=vm, allow_max=al, expect="OFF" if expect_off else "ON", verdict=verdict)


ARMED_UNDOCKED_FWD = {"sup_permit": C.step(1e-3), "mcu_en": C.step(1e-3), "dock_n": "3.3", "mot_fwd": "3.3", "arm_clk": C.pulse(8e-3)}
ARMED_DOCKED_FWD = dict(ARMED_UNDOCKED_FWD, dock_n="0")


def floating_and_power():
    out = []
    # (c) everything undefined: no GPIO drive, hall output open, latch powers up SET (worst case), DOCK_N floats at 0 V or at 3.3 V
    for lvl in (0.0, 3.3):
        out.append(scen("float_all_dock%g" % lvl, "all GPIOs Hi-Z, hall output open (DOCK_N floats at %g V), latch initially SET" % lvl,
                        dict(drv={}, latch_ic=1, ic_nodes={"dock_n": lvl}, tstop="40m"), True))
    # hall output open, everything else asserted and armed (single open joint on U4A pin 4): which level DOCK_N floats at decides
    for lvl in (0.0, 3.3):
        out.append(scen("hall_open_dock%g" % lvl, "single fault: DRV5032 output open, DOCK_N floats at %g V, undocked, forward, armed, permit+MCU_EN on" % lvl,
                        dict(drv={k: v for k, v in ARMED_UNDOCKED_FWD.items() if k != "dock_n"}, ic_nodes={"dock_n": lvl}, tstop="40m"), True))
    out.append(scen("hall_open_with_pullup", "same, with the proposed 100 k pull-up on DOCK_N (floats high = undocked)",
                    dict(drv={k: v for k, v in ARMED_UNDOCKED_FWD.items() if k != "dock_n"}, dock_pu=100e3, ic_nodes={"dock_n": 0.0}, tstop="40m"), True))
    # (d) power-up ramps of the 3V3 rail, worst case: latch SET at power-up, undefined gate outputs follow the rail, software asserts at once
    for tr, tag in ((100e-6, "100us"), (1e-3, "1ms"), (10e-3, "10ms")):
        ramp = C.pwl([(0, 0), (tr, 3.3)])
        drv = {k: C.pwl([(0, 0), (tr + 1e-6, 3.3)]) for k in ("sup_permit", "mcu_en")}
        drv["dock_n"] = "0"
        drv["mot_fwd"] = "3.3"
        out.append(scen("powerup_" + tag, "3V3 rail ramp %s, latch SET at power-up, permit/MCU_EN asserted instantly, docked + forward, supervisor BOR + TPL5010 RSTn active" % tag,
                        dict(v3v3=ramp, drv=drv, latch_ic=1, rstn_wave="3.3", tstop="30m", tstep="5u"), True, t0=0.0))
    # power-up where nothing resets the latch (no BOR, no RSTn): what the AND legs alone give with permit/MCU_EN Hi-Z (pull-downs only)
    out.append(scen("powerup_hiz", "3V3 ramp 1 ms, latch SET, ALL GPIO Hi-Z (pull resistors only), no reset help at all, docked", dict(v3v3=C.pwl([(0, 0), (1e-3, 3.3)]), drv={}, latch_ic=1,
                    ic_nodes={"dock_n": 0.0}, nrst_bor=False, tstop="30m"), True, t0=0.0))
    # (e) brown-out dips while docked-forward running
    for dip in (0.5, 1.0, 1.5, 1.8, 2.2):
        wave = C.pwl([(0, 3.3), (20e-3, 3.3), (20.2e-3, dip), (25e-3, dip), (25.2e-3, 3.3)])
        drv = dict(ARMED_DOCKED_FWD)
        out.append(scen("brownout_%g" % dip, "3V3 dips to %g V for 5 ms while running (docked, forward); after the dip NO new ARM_CLK edge: must stay cut if the dip reset the logic" % dip,
                        dict(v3v3=wave, drv=drv, tstop="60m"), expect_off=True, t0=28e-3))
    return out


def faults():
    o = []
    # single faults against the hardware path; baseline = undocked + forward (must be OFF) or docked + reverse (OFF, new XOR) unless noted
    o.append(scen("sf_permit_stuck_hi", "SUP_PERMIT stuck high (STM32 pin), undocked + forward, armed", dict(drv={k: v for k, v in ARMED_UNDOCKED_FWD.items() if k != "sup_permit"}, force={"sup_permit": 3.3}, tstop="40m")))
    o.append(scen("sf_mcuen_stuck_hi", "MCU_EN stuck high, undocked + forward, armed", dict(drv={k: v for k, v in ARMED_UNDOCKED_FWD.items() if k != "mcu_en"}, force={"mcu_en": 3.3}, tstop="40m")))
    o.append(scen("sf_latch_stuck_hi", "LATCH_Q stuck high (U6 / U32), permit and MCU_EN OFF", dict(drv={"dock_n": "0", "mot_fwd": "3.3", "sup_permit": "0", "mcu_en": "0"}, force={"latch_q": 3.3}, tstop="40m")))
    o.append(scen("sf_latch_stuck_hi_undocked", "LATCH_Q stuck high, permit and MCU_EN ON, undocked + forward", dict(drv={k: v for k, v in ARMED_UNDOCKED_FWD.items() if k != "arm_clk"}, force={"latch_q": 3.3}, tstop="40m")))
    o.append(scen("sf_dock_stuck_low", "DOCK_N stuck low (hall asserted / shorted), undocked + forward, all enables on (INTERLOCK I.1a open item)", dict(drv={k: v for k, v in ARMED_UNDOCKED_FWD.items() if k != "dock_n"}, force={"dock_n": 0.0}, tstop="40m")))
    o.append(scen("sf_dock_stuck_hi", "DOCK_N stuck high (hall dead), docked + forward: nuisance only", dict(drv={k: v for k, v in ARMED_DOCKED_FWD.items() if k != "dock_n"}, force={"dock_n": 3.3}, tstop="40m"), expect_off=True))
    o.append(scen("sf_fwd_stuck_lo", "MOT_FWD stuck low (reads 'reverse'), undocked, all enables on: forward motion undocked cannot be seen by the hardware gate (supervisor PHASE check only)", dict(drv={k: v for k, v in ARMED_UNDOCKED_FWD.items() if k != "mot_fwd"}, force={"mot_fwd": 0.0}, tstop="40m")))
    o.append(scen("sf_docked_reverse", "docked + reverse (H15), all enables on: new XOR must block in hardware", dict(drv=dict(ARMED_DOCKED_FWD, mot_fwd="0"), tstop="40m")))
    for lvl in (0.0, 3.3):
        o.append(scen("sf_R16_open_%g" % lvl, "R16 (MOT_FWD pull-up) open, nRF GPIO Hi-Z (reset), MOT_FWD floats at %g V, undocked, latch armed, permit+MCU_EN on" % lvl,
                      dict(drv={k: v for k, v in ARMED_UNDOCKED_FWD.items() if k != "mot_fwd"}, opens={"R16"}, ic_nodes={"mot_fwd": lvl}, tstop="40m")))
    for lvl in (0.0, 3.3):
        o.append(scen("sf_R82_open_%g" % lvl, "R82 (SUP_PERMIT pull-down) open, STM32 Hi-Z (reset), SUP_PERMIT floats at %g V; other legs on, docked + forward, latch armed" % lvl,
                      dict(drv={k: v for k, v in ARMED_DOCKED_FWD.items() if k != "sup_permit"}, opens={"R82"}, ic_nodes={"sup_permit": lvl}, tstop="40m")))
    for lvl in (0.0, 3.3):
        o.append(scen("sf_R18_open_%g" % lvl, "R18 (MCU_EN pull-down) open, nRF Hi-Z, MCU_EN floats at %g V; permit on, docked + forward, armed" % lvl,
                      dict(drv={k: v for k, v in ARMED_DOCKED_FWD.items() if k != "mcu_en"}, opens={"R18"}, ic_nodes={"mcu_en": lvl}, tstop="40m")))
    o.append(scen("sf_R90_open", "R90 (MOT_ALLOW pull-down) open, everything else normal, undocked + forward: gate output is driven, so still OFF", dict(drv=ARMED_UNDOCKED_FWD, opens={"R90"}, tstop="40m")))
    for lvl in (0.0, 3.3):
        o.append(scen("sf_R29_open_%g" % lvl, "R29 (ARM_CLK pull-down) open, nRF Hi-Z, ARM_CLK floats at %g V: no edge, latch stays clear; undocked/docked + forward" % lvl,
                      dict(drv={k: v for k, v in ARMED_DOCKED_FWD.items() if k != "arm_clk"}, opens={"R29"}, ic_nodes={"arm_clk": lvl}, tstop="40m")))
    o.append(scen("sf_R92_open_0", "R92 (OC_OK pull-up) open, OC_OK floats low: latch held clear -> motor never runs (safe, nuisance)", dict(drv=ARMED_DOCKED_FWD, opens={"R92"}, ic_nodes={"oc_ok": 0.0}, tstop="40m")))
    return o


def run(plot=True):
    out = {"dc": truth_dc(), "chain": truth_chain()}
    out["float_power"] = floating_and_power()
    out["faults"] = faults()
    out["dc_pass"] = all(r["ok"] for r in out["dc"])
    out["chain_pass"] = all(r["ok"] for r in out["chain"])
    json.dump(out, open(S.os.path.join(S.RES, "case3.json"), "w"), indent=1)
    if plot:
        make_plot(out)
    return out


def make_plot(out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(10, 3.2))
    names = ["powerup_1ms", "brownout_1", "hall_open_dock0"]
    for ax, n in zip(axs, names):
        try:
            w = S.Wave(S.os.path.join(S.RES, "c3_%s.csv" % n), C.NAMES)
        except Exception:
            continue
        for k, lab in (("v3v3", "3V3"), ("allow", "MOT_ALLOW"), ("vmot", "VMOT"), ("perml", "PERM_L")):
            ax.plot(w.t * 1e3, w[k], label=lab, lw=1)
        ax.set_title(n, fontsize=9)
        ax.set_xlabel("ms")
        ax.grid(alpha=0.3)
    axs[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(S.os.path.join(S.HERE, "plots", "case3_logic.png"), dpi=70)
    plt.close(fig)


if __name__ == "__main__":
    r = run()
    print("dc", r["dc_pass"], "chain", r["chain_pass"])
    for sec in ("float_power", "faults"):
        for x in r[sec]:
            print(sec, x["name"], x.get("verdict"), x.get("vmot_max"), x.get("allow_max"))
