#!/usr/bin/env python3
"""ngspice (XSPICE digital models + analog RC): HW-A arm window, 32-pulse step budget and re-arm dead time.

Logic exactly as netlist.py: U13 window FF (CLK=ARM_CLK, CLR from the Schmitt buffer U14 on the RC node), R59||R60 = 500 k, C33 = 1 uF,
U15 6-stage ripple counter (falling-edge, reset by WIN_N), Q18 inverter, U16 AND, U17 OR, U18 AND (STCK gate), U19 AND (count only forward pulses).
Scenarios: S1 one normal tick, S2 runaway (STCK 1 kHz + ARM_CLK 1 kHz for 4 s), S3 reverse draw (600 pps, 500 pulses), S4 ARM_CLK stuck high, S5 slow re-arm (every 1 s).
Writes results/hwa_*.csv, hwa.png, hwa_results.md.  Threshold/RC tolerance Monte Carlo: hwa_mc.py.
"""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)

DECK = """* HW-A {name}
.model adc adc_bridge(in_low=1.0 in_high=2.0)
.model dac dac_bridge(out_low=0.0 out_high=3.3)
.model ff d_dff(ic=0)
.model inv d_inverter
.model and2 d_and
.model or2 d_or
.model pd d_pulldown
.model pu d_pullup
.model SWm sw(vt=0 vh=0.02 ron=100 roff=1e12)
Varm arm_a 0 {arm}
Vstck stck_a 0 {stck}
Vrev rev_a 0 {rev}
A1 [arm_a] [arm] adc
A2 [stck_a] [stck] adc
A3 [rev_a] [rev] adc
Az zero pd
Ao one pu
Ainv_fwd rev fwd inv
* window FF U13: D=1, CLK=ARM, reset (active high here) = not TS
Ats_n ts ts_n inv
Awin one arm zero ts_n win win_n ff
* RC timer: WIN_N -> 500k -> TN, C = 1uF, Schmitt buffer -> TS
Adac1 [win_n] [winn_a] dac
Rt winn_a tn {rt}
Ct tn 0 {ct}
* Schmitt buffer U14 (VT+ = {vth} V, VT- = {vtl} V) as an analog latch
Bs1 cs 0 V=v(tn)-{vth}
Bs2 cr 0 V={vtl}-v(tn)
Vh vhi 0 3.3
Ssh vhi ts_a cs 0 SWm
Ssl ts_a 0 cr 0 SWm
Cts ts_a 0 1n IC=0
Rts ts_a 0 1e9
A4 [ts_a] [ts] adc
* gating
Afull_n full full_n inv
Ax [win full_n] x and2
Ay [rev x] y or2
Ag [stck y] stck_g and2
Ac [stck_g fwd] cnt_clk and2
* 6-stage ripple counter, reset by WIN_N (U15), counts on falling edges of CNT_CLK
Ack cnt_clk clk1 inv
As1 qb1 clk1 zero win_n q1 qb1 ff
As2 qb2 qb1 zero win_n q2 qb2 ff
As3 qb3 qb2 zero win_n q3 qb3 ff
As4 qb4 qb3 zero win_n q4 qb4 ff
As5 qb5 qb4 zero win_n q5 qb5 ff
As6 qb6 qb5 zero win_n full qb6 ff
Adac2 [stck_g] [stckg_a] dac
Adac3 [win] [win_a] dac
Adac4 [full] [full_a] dac
Adac5 [stck] [stck_ma] dac
.tran 20u {tend}
.control
set noaskquit
run
wrdata {out} v(stck_ma) v(stckg_a) v(win_a) v(full_a) v(tn)
.endc
.end
"""


def pulses(f, t0, t1, width=0.4e-3, v=3.3):
    """PWL pulse train: frequency f, 50 % duty, between t0 and t1."""
    pts = ["0 0"]
    t = t0
    per = 1.0 / f
    while t < t1:
        pts += ["%.7f 0" % t, "%.7f %g" % (t + 1e-6, v), "%.7f %g" % (t + per / 2, v), "%.7f 0" % (t + per / 2 + 1e-6)]
        t += per
    return "PWL(" + " ".join(pts) + ")"


CASES = [
    ("S1", "one normal tick: ARM at 0.1 s, 40 STCK pulses at 200 Hz (forward)", "PWL(0 0 0.1 0 0.1001 3.3 0.15 3.3 0.1501 0)", pulses(200, 0.12, 0.32), "0", 0.6),
    ("S2", "runaway: STCK 1 kHz and ARM_CLK 1 kHz for 4 s (forward)", pulses(1000, 0.05, 4.05), pulses(1000, 0.05, 4.05), "0", 4.1),
    ("S3", "reverse draw: 500 pulses at 600 pps with DIR = reverse (no budget)", "PWL(0 0 0.05 0 0.0501 3.3 0.9 3.3)", pulses(600, 0.06, 0.06 + 500 / 600.0), "3.3", 1.0),
    ("S4", "ARM_CLK stuck high from 0.05 s, STCK 1 kHz for 2 s", "PWL(0 0 0.05 0 0.0501 3.3 3 3.3)", pulses(1000, 0.1, 2.1), "0", 2.2),
    ("S5", "firmware re-arms every 1 s and steps 32 pulses at 200 Hz each tick (4 ticks)", None, None, "0", 4.2),
]


def s5():
    arm, stck = ["0 0"], ["0 0"]
    for k in range(4):
        t = 0.1 + k * 1.0
        arm += ["%.5f 0" % t, "%.5f 3.3" % (t + 1e-6), "%.5f 3.3" % (t + 0.02), "%.5f 0" % (t + 0.02 + 1e-6)]
        for j in range(32):
            ts = t + 0.05 + j * 0.005
            stck += ["%.6f 0" % ts, "%.6f 3.3" % (ts + 1e-6), "%.6f 3.3" % (ts + 0.0025), "%.6f 0" % (ts + 0.0025 + 1e-6)]
    return "PWL(" + " ".join(arm) + ")", "PWL(" + " ".join(stck) + ")"


def edges(t, y, thr=1.65):
    n, prev, times = 0, 0, []
    for a, b in zip(t, y):
        s = 1 if b > thr else 0
        if s and not prev:
            n += 1
            times.append(a)
        prev = s
    return n, times


def load(path):
    t, c = [], [[] for _ in range(5)]
    for line in open(path):
        v = [float(x) for x in line.split()]
        t.append(v[0])
        for i in range(5):
            c[i].append(v[1 + 2 * i])
    return t, c


def run(name, arm, stck, rev, tend, rt=500e3, ct=1e-6, vth=1.9, vtl=1.0):
    out = os.path.join(RES, "hwa_%s.csv" % name)
    cir = os.path.join(RES, "hwa_%s.cir" % name)
    open(cir, "w").write(DECK.format(name=name, arm=arm, stck=stck, rev="DC " + rev, tend=tend, out=out, rt=rt, ct=ct, vth=vth, vtl=vtl))
    r = subprocess.run(["ngspice", "-b", cir], capture_output=True, text=True)
    open(os.path.join(RES, "hwa_%s.log" % name), "w").write(r.stdout + r.stderr)
    return out


def main(unit_dose=0.003951):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = []
    fig, axs = plt.subplots(len(CASES), 1, figsize=(10, 2.3 * len(CASES)))
    for ax, (name, desc, arm, stck, rev, tend) in zip(axs, CASES):
        if name == "S5":
            arm, stck = s5()
        path = run(name, arm, stck, rev, tend)
        if not os.path.exists(path):
            rows.append((name, desc, "FAILED, see results/hwa_%s.log" % name))
            continue
        t, (sm, sg, win, full, tn) = load(path)
        n_in, _ = edges(t, sm)
        n_out, tout = edges(t, sg)
        wins, _ = edges(t, win)
        info = "STCK pulses in %d, delivered to the driver %d" % (n_in, n_out)
        if rev == "0":
            info += " = %.3f U (16:20 0.003951 U/step) / %.3f U (18:18 0.00494 U/step); arm windows opened: %d" % (n_out * 0.003951, n_out * 0.00494, wins)
        rows.append((name, desc, info))
        ax.plot(t, [x + 4 for x in sm], lw=0.5, label="STCK (MCU)"); ax.plot(t, [x + 0 for x in sg], lw=0.5, label="STCK to driver")
        ax.plot(t, [x - 4 for x in win], lw=0.8, label="WIN"); ax.plot(t, [x - 8 for x in full], lw=0.8, label="FULL")
        ax.set_ylabel(name); ax.set_yticks([])
        if name == "S1":
            ax.legend(ncol=4, fontsize=7, loc="upper right")
    fig.suptitle("HW-A step budget (ngspice, XSPICE digital)")
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "hwa.png"), dpi=110)
    with open(os.path.join(HERE, "hwa_results.md"), "w") as f:
        f.write("# ngspice: HW-A arm window + 32-pulse budget (generated by run_hwa.py)\n\n| Case | Scenario | Result |\n|---|---|---|\n")
        for r in rows:
            f.write("| %s | %s | %s |\n" % r)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
