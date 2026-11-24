"""Case 4: 2 x DRV8838 (formerly DRV8835; same PHASE/ENABLE truth table; behavioural switch-level bridge, PHASE/ENABLE mode, full steps) driving the 26.5 ohm / L coil from VM = 5 V (boost + TPS2553 chain).
Full-step sequence per INTERLOCK I.6: every step toggles exactly one PHASE line: A+B+ -> A-B+ -> A-B- -> A+B-.  ENABLE high while stepping.
Measured: coil current, current into VM (through the TPS2553), VMOT spikes (energy returned by the winding), cell current, FAULT (incl. reverse-voltage deglitch)."""
import json
import numpy as np
import simlib as S
import chain as C

NAMES = ["vmot", "vpre", "ia", "ib", "isw", "icell", "ocok", "vbat", "aout1", "aout2"]


def bridge(tag, ph, en, o1, o2, ron_h=0.15, ron_l=0.15):
    """one H-bridge: PH/EN mode. ENABLE low -> both outputs low (brake). Body diodes included. Dead time 100 ns is not resolved."""
    s = ("B%(t)s_h1 h1%(t)s 0 V = (v(%(en)s) > 1.65 && v(%(ph)s) > 1.65) ? 1 : 0\nB%(t)s_l1 l1%(t)s 0 V = (v(%(en)s) > 1.65 && v(%(ph)s) > 1.65) ? 0 : 1\n"
         "B%(t)s_h2 h2%(t)s 0 V = (v(%(en)s) > 1.65 && v(%(ph)s) < 1.65) ? 1 : 0\nB%(t)s_l2 l2%(t)s 0 V = (v(%(en)s) > 1.65 && v(%(ph)s) < 1.65) ? 0 : 1\n"
         "S%(t)s_h1 vmot %(o1)s h1%(t)s 0 swh\nS%(t)s_l1 %(o1)s 0 l1%(t)s 0 swl\nS%(t)s_h2 vmot %(o2)s h2%(t)s 0 swh\nS%(t)s_l2 %(o2)s 0 l2%(t)s 0 swl\n"
         "D%(t)s_a1 %(o1)s vmot dbody\nD%(t)s_b1 0 %(o1)s dbody\nD%(t)s_a2 %(o2)s vmot dbody\nD%(t)s_b2 0 %(o2)s dbody\n"
         % dict(t=tag, ph=ph, en=en, o1=o1, o2=o2))
    return s


def deck(rate, nsteps, lcoil=S.L_COIL, rscale=1.0, ocv=3.7, rint=S.RINT_NOM, t0=5e-3, tstop=None, name="c4", ke=0.0):
    per = 1.0 / rate
    # states after each step (A, B)
    seq = [(1, 1), (0, 1), (0, 0), (1, 0)]
    ptsA, ptsB = [(0, 0)], [(0, 0)]
    for k in range(nsteps + 1):
        a, b = seq[k % 4]
        t = t0 + k * per
        ptsA += [(t, ptsA[-1][1]), (t + 1e-7, 3.3 * a)]
        ptsB += [(t, ptsB[-1][1]), (t + 1e-7, 3.3 * b)]
    tstop = tstop or (t0 + (nsteps + 1) * per + 2e-3)
    p = dict(name=name, ocv=ocv, rint=rint, drv={"sup_permit": C.step(1e-3), "mcu_en": C.step(1e-3), "dock_n": "0", "mot_fwd": "3.3", "arm_clk": C.pulse(3e-3)},
             tstop="%g" % tstop, tstep="2u")
    s = C.chain(p)
    # replace the resistive motor load by the two DRV8838 bridges + coils
    lines = [l for l in s.splitlines() if not l.startswith("Bmot ")]
    s = "\n".join(lines) + "\n"
    blk = ("* 2 x DRV8838 + NFP-608 coils (L = %g H assumed, R = %g ohm +/-)\n.model swh sw vt=0.5 vh=0.1 ron=%g roff=1e9\n.model swl sw vt=0.5 vh=0.1 ron=%g roff=1e9\n"
           ".model dbody d is=1e-9 n=1.1 rs=0.3\nVph_a pa 0 PWL(%s)\nVph_b pb 0 PWL(%s)\nVen_a ea 0 PWL(0 0 4m 0 4.001m 3.3)\nVen_b eb 0 PWL(0 0 4m 0 4.001m 3.3)\n"
           % (lcoil, S.R_COIL * rscale, 0.15, 0.15, " ".join("%g %g" % q for q in ptsA), " ".join("%g %g" % q for q in ptsB)))
    blk += bridge("A", "pa", "ea", "aout1", "aout2") + bridge("B", "pb", "eb", "bout1", "bout2")
    blk += ("Rca aout1 ca %g\nLca ca ca2 %g\nBea ca2 aout2 V = %g * sin(0) \nRcb bout1 cb %g\nLcb cb cb2 %g\nBeb cb2 bout2 V = 0\n"
            % (S.R_COIL * rscale, lcoil, ke, S.R_COIL * rscale, lcoil))
    blk += "Vsa ia_x 0 0\n"
    s = s.replace(".control\nrun\n", blk + ".control\nrun\n")
    # the vector list: add coil currents by inserting zero-volt sources? use branch currents of the inductors
    s = s.replace("wrdata @RES@/%s.csv" % name, "wrdata @RES@/%s.csv" % name)
    s = s.replace("i(Vsm) v(dock_ok) v(perm_l)", "i(Vsm) v(dock_ok) v(perm_l) i(Lca) i(Lcb) v(aout1) v(aout2)")
    return s, tstop


NAMES4 = C.NAMES + ["ia", "ib", "aout1", "aout2"]


def one(rate, nsteps, **kw):
    name = kw.pop("name", "c4_%g" % rate)
    s, tstop = deck(rate, nsteps, name=name, **kw)
    s = s.replace(".control\nrun\n", ".control\nrun\n")
    w, log = S.run_wave(s, name, NAMES4, mode="ps")
    return w, log


def metrics(w, t0, t1):
    m = {}
    m["ia_pk_a"] = float(np.max(np.abs(w.window("ia", t0, t1))))
    m["ib_pk_a"] = float(np.max(np.abs(w.window("ib", t0, t1))))
    isw = w.window("isw", t0, t1)
    m["isupply_pk_a"] = float(isw.max())
    m["isupply_min_a"] = float(isw.min())
    m["isupply_mean_a"] = float(isw.mean())
    vm = w.window("vmot", t0, t1)
    m["vmot_max_v"] = float(vm.max())
    m["vmot_min_v"] = float(vm.min())
    m["icell_pk_a"] = float(-w.window("icell", t0, t1).min())
    m["fault"] = bool((w.window("ocok", t0, t1) < 1.65).any())
    return m


def run(plot=True):
    out = {"rates": {}, "L": {}, "rcoil": {}}
    waves = {}
    for rate, n in ((5, 2), (50, 8), (200, 24), (500, 40)):
        w, log = one(rate, n)
        if w is None:
            out["rates"][str(rate)] = {"error": log[-300:]}
            continue
        t0 = 5e-3 + 1.0 / rate
        t1 = 5e-3 + n / rate
        out["rates"][str(rate)] = metrics(w, 5e-3 + 1.5 / rate, 5e-3 + (n + 1) / rate)
        waves[rate] = w
    for L in (2e-3, 15e-3):
        w, log = one(200, 24, lcoil=L, name="c4_L%g" % (L * 1e3))
        out["L"]["%g" % (L * 1e3)] = metrics(w, 5e-3 + 1.5 / 200.0, 5e-3 + 25 / 200.0) if w is not None else {"error": log[-200:]}
    for rs in (0.9, 1.1):
        w, log = one(200, 24, rscale=rs, ocv=4.2, name="c4_rs%g" % rs)
        out["rcoil"]["%g" % rs] = metrics(w, 5e-3 + 1.5 / 200.0, 5e-3 + 25 / 200.0) if w is not None else {"error": log[-200:]}
    json.dump(out, open(S.os.path.join(S.RES, "case4.json"), "w"), indent=1)
    if plot and 200 in waves:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axs = plt.subplots(3, 1, figsize=(8, 6), sharex=True)
        w = waves[200]
        axs[0].plot(w.t * 1e3, w["ia"], label="coil A")
        axs[0].plot(w.t * 1e3, w["ib"], label="coil B")
        axs[0].set_ylabel("A")
        axs[0].legend(fontsize=7)
        axs[1].plot(w.t * 1e3, w["isw"], color="tab:red", label="into VM (TPS2553)")
        axs[1].plot(w.t * 1e3, -w["icell"], color="tab:green", lw=0.8, label="cell")
        axs[1].set_ylabel("A")
        axs[1].legend(fontsize=7)
        axs[2].plot(w.t * 1e3, w["vmot"], label="VMOT")
        axs[2].plot(w.t * 1e3, w["vpre"], label="VMOT_PRE", lw=0.8)
        axs[2].set_ylabel("V")
        axs[2].set_xlabel("ms")
        axs[2].legend(fontsize=7)
        axs[2].set_xlim(4, 40)
        for a in axs:
            a.grid(alpha=0.3)
        fig.suptitle("Case 4: DRV8838 full steps at 200 steps/s, 26.5 ohm / 5 mH", fontsize=10)
        fig.tight_layout()
        fig.savefig(S.os.path.join(S.HERE, "plots", "case4_drv8835.png"), dpi=70)
        plt.close(fig)
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
