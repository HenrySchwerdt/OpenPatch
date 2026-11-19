#!/usr/bin/env python3
"""ngspice: supply switch (two series P-FETs + series gate chain), over-current latch, bleeder.  Writes results/*.csv, switch_oc.png, switch_oc_results.md.

Cases: A normal start+stall (no false trip), B bridge short (trip), C MCU_EN falls (collapse time), D undocked forward (stays off),
E undocked reverse (draw, on), F Q4 shorted (Q15 still cuts), G Q15 shorted (Q4 still cuts).
Behavioural blocks: INA180 (20 V/V, supply limited), TLV7011 comparator, latch U12 (cap + switches), motor = 2 x (26.5 + 2.3 ohm) with 160 mA chopper cap.
"""
import os
import subprocess
import csv

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)

DECK = """* v010 switch + OC, case {case}
.param vcell={vcell} rint={rint}
Vcell vc 0 {{vcell}}
Rint vc vbat {{rint}}
C5 vbat 0 10u
Cbulk vmot 0 32u
C24 vraw 0 10u
* gate drive: LATCH_Q, MCU_EN, DOCKED_H, DIR_REV (3.3 V logic)
Vlatch latch 0 PWL(0 0 2m 0 2.001m 3.3)
Vmcuen mcuen 0 {mcuen}
Vdock dockedh 0 {docked}
Vdir dirrev 0 {dirrev}
.model PM pmos level=1 vto=-1.0 kp=8 lambda=0.02
.model NM nmos level=1 vto=1.6 kp=0.07 lambda=0.02
* series P-FETs (second one shares PGATE); case F/G replace one by a short
{q4}
{q15}
Cgs4 pgate vbat 600p
R9 vbat pgate 100k
R10 vbat pgate 100k
C11 pgate vbat 100n
R11 pgate chtop 10k
M5 chtop latch mid1 mid1 NM
M8 mid1 mcuen mid2 mid2 NM
M13 mid2 ocok mid2a mid2a NM
* H15: interlock leg = DOCKED XOR DIR_REV (branch 1: docked AND forward, branch 2: undocked AND reverse)
Bnot docknot 0 V=3.3-v(dockedh)
Bfwd fwd 0 V=3.3-v(dirrev)
M6 mid2a dockedh xa xa NM
M21 xa fwd 0 0 NM
M10 mid2a docknot xb xb NM
M22 xb dirrev 0 0 NM
* bleeder (turns on when PGATE is high)
M17 bldn pgate 0 0 NM
Rb1 vmot bldn 100
Rb2 vmot bldn 100
* shunt + INA180A1 (supplied from VRAW) + 10k/10n blanking
Rbyp vraw vpre 0.01
Rsh vpre vmot 0.22
Bina inaraw 0 V=min(max(20*(v(vpre)-v(vmot)),0),max(v(vraw)-0.05,0))
Rina inaraw inaout 1k
Cina inaout 0 0.5n
Rpd inaout 0 100k
Roc inaout ocin 10k
Coc ocin 0 10n
* reference 3.3 V * 100k/110k... (R49 100k, R50+R51 = 110k)
Vrail v3v3 0 3.3
Rr1 v3v3 ocref 100k
Rr2 ocref 0 110k
* comparator (TLV7011): out high when ocin > ocref
Bcmp cmpraw 0 V=3.3*(0.5+0.5*tanh((v(ocin)-v(ocref))*200))
Rcmp cmpraw ocmp 100
Ccmp ocmp 0 5p
* OC_CLR_N: R54 100k from MCU_EN, C30 100n, diode D5 discharges when MCU_EN falls
R54 mcuen clrn 100k
C30 clrn 0 100n
.model DD d(is=1e-9 n=1.8 rs=10)
D5 clrn mcuen DD
* OC latch: lat node = Q (trip). set when ocmp high, cleared when clrn low
.model SW sw(vt=1.65 vh=0.1 ron=10 roff=1e12)
Clat lat 0 1n IC=0
Rlat lat 0 1e9
Bset sset 0 V=v(ocmp)
Bclr sclr 0 V=3.3-v(clrn)
Sset v3v3 lat sset 0 SW
Sclr lat 0 sclr 0 SW
Bocok ocok 0 V=3.3*(1-0.5*(1+tanh((v(lat)-1.65)*50)))
* motor: two phases, 26.5+2.3 ohm each, chopper limits each phase to 160 mA; optional bridge short
Bmot vmot 0 I=2*min(0.16, max(v(vmot),0)/28.8) + {shortI}
.ic v(lat)=0 v(vmot)=0 v(clrn)=0 v(pgate)={vcell} v(vbat)={vcell} v(vc)={vcell}
.tran 20u 400m uic
.control
set noaskquit
run
wrdata {out} v(vbat) v(vmot) v(vraw) v(pgate) v(ocok) v(inaout) v(ocmp) i(Vcell)
.endc
.end
"""

CASES = {
    "A": dict(desc="docked + FORWARD: normal start at t=5 ms; stalled motor (2 x 160 mA) from t=150 ms: must NOT trip", vcell=4.2, rint=3.0, mcuen="PWL(0 0 5m 0 5.001m 3.3)", docked="3.3", dirrev="0",
              q4="M4 vmota pgate vbat vbat PM", q15="M15 vraw pgate vmota vmota PM", shortI="0"),
    "A2": dict(desc="same at a low cell (3.1 V, R_int 4 ohm)", vcell=3.1, rint=4.0, mcuen="PWL(0 0 5m 0 5.001m 3.3)", docked="3.3", dirrev="0",
               q4="M4 vmota pgate vbat vbat PM", q15="M15 vraw pgate vmota vmota PM", shortI="0"),
    "B": dict(desc="bridge short (4 ohm on VMOT) at t=150 ms: over-current latch trips, supply cut", vcell=4.2, rint=3.0, mcuen="PWL(0 0 5m 0 5.001m 3.3)", docked="3.3", dirrev="0",
              q4="M4 vmota pgate vbat vbat PM", q15="M15 vraw pgate vmota vmota PM", shortI="(time>150m ? v(vmot)/4 : 0)"),
    "C": dict(desc="MCU_EN falls at t=150 ms: VMOT must collapse below 0.5 V within 20 ms", vcell=4.2, rint=3.0, mcuen="PWL(0 0 5m 0 5.001m 3.3 150m 3.3 150.001m 0)", docked="3.3", dirrev="0",
              q4="M4 vmota pgate vbat vbat PM", q15="M15 vraw pgate vmota vmota PM", shortI="0"),
    "D": dict(desc="H15: undocked + FORWARD: VMOT stays off", vcell=4.2, rint=3.0, mcuen="PWL(0 0 5m 0 5.001m 3.3)", docked="0", dirrev="0",
              q4="M4 vmota pgate vbat vbat PM", q15="M15 vraw pgate vmota vmota PM", shortI="0"),
    "E": dict(desc="undocked + REVERSE (draw): VMOT on", vcell=4.2, rint=3.0, mcuen="PWL(0 0 5m 0 5.001m 3.3)", docked="0", dirrev="3.3",
              q4="M4 vmota pgate vbat vbat PM", q15="M15 vraw pgate vmota vmota PM", shortI="0"),
    "H": dict(desc="H15: docked + REVERSE: VMOT stays off", vcell=4.2, rint=3.0, mcuen="PWL(0 0 5m 0 5.001m 3.3)", docked="3.3", dirrev="3.3",
              q4="M4 vmota pgate vbat vbat PM", q15="M15 vraw pgate vmota vmota PM", shortI="0"),
    "F": dict(desc="Q4 shorted drain-source; MCU_EN falls at 150 ms: Q15 must still cut", vcell=4.2, rint=3.0, mcuen="PWL(0 0 5m 0 5.001m 3.3 150m 3.3 150.001m 0)", docked="3.3", dirrev="0",
              q4="Rq4 vbat vmota 0.01", q15="M15 vraw pgate vmota vmota PM", shortI="0"),
    "G": dict(desc="Q15 shorted drain-source; MCU_EN falls at 150 ms: Q4 must still cut", vcell=4.2, rint=3.0, mcuen="PWL(0 0 5m 0 5.001m 3.3 150m 3.3 150.001m 0)", docked="3.3", dirrev="0",
              q4="M4 vmota pgate vbat vbat PM", q15="Rq15 vmota vraw 0.01", shortI="0"),
}


def run(case, c):
    out = os.path.join(RES, "switch_%s.csv" % case)
    deck = DECK.format(case=case, out=out, **c)
    cir = os.path.join(RES, "switch_%s.cir" % case)
    open(cir, "w").write(deck)
    r = subprocess.run(["ngspice", "-b", cir], capture_output=True, text=True)
    open(os.path.join(RES, "switch_%s.log" % case), "w").write(r.stdout + r.stderr)
    return out


def load(path):
    t, cols = [], [[] for _ in range(8)]
    for line in open(path):
        v = [float(x) for x in line.split()]
        t.append(v[0])
        for i in range(8):
            cols[i].append(v[1 + 2 * i])
    return t, cols


def first_after(t, y, t0, cond):
    for a, b in zip(t, y):
        if a >= t0 and cond(b):
            return a
    return None


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = []
    fig, axs = plt.subplots(len(CASES), 1, figsize=(9, 2.2 * len(CASES)), sharex=True)
    for ax, (case, c) in zip(axs, CASES.items()):
        path = run(case, c)
        if not os.path.exists(path):
            rows.append((case, c["desc"], "SIMULATION FAILED (see switch_%s.log)" % case))
            continue
        t, (vbat, vmot, vraw, pg, ocok, ina, ocmp, ibat) = load(path)
        vmax = max(vmot)
        t_on = first_after(t, vmot, 0, lambda v: v > 0.9 * 4.0 if c["vcell"] > 4 else v > 2.7)
        info = "VMOT max %.2f V" % vmax
        if t_on is not None:
            info += ", on at %.1f ms (%.1f ms after MCU_EN)" % (t_on * 1e3, (t_on - 5e-3) * 1e3)
        ibatmax = max(abs(x) for x in ibat)
        info += ", battery current max %.0f mA" % (ibatmax * 1e3)
        if case in ("A", "A2"):
            info += ", OC_OK final %.2f V (3.3 = no trip)" % ocok[-1]
            # inrush peak before the motor runs
            inr = max(abs(x) for x, tt in zip(ibat, t) if tt < 0.12)
            info += ", inrush+run peak %.0f mA" % (inr * 1e3)
        if case == "B":
            tt = first_after(t, ocok, 0.15, lambda v: v < 1.65)
            tc = first_after(t, vmot, 0.15, lambda v: v < 0.5)
            info += ", OC_OK low at %s ms (trip delay %s ms), VMOT < 0.5 V at %s ms" % (
                "%.2f" % (tt * 1e3) if tt else "never", "%.2f" % ((tt - 0.15) * 1e3) if tt else "-", "%.2f" % (tc * 1e3) if tc else "never")
        if case in ("C", "F", "G"):
            tc = first_after(t, vmot, 0.1501, lambda v: v < 0.5)
            info += ", VMOT < 0.5 V %s ms after MCU_EN fell (limit 20 ms)" % ("%.1f" % ((tc - 0.15) * 1e3) if tc else "NEVER")
        if case in ("D", "H"):
            info += ", final VMOT %.3f V (must be ~0)" % vmot[-1]
        rows.append((case, c["desc"], info))
        ax.plot([x * 1e3 for x in t], vmot, label="VMOT"); ax.plot([x * 1e3 for x in t], pg, label="PGATE", lw=0.8)
        ax.plot([x * 1e3 for x in t], [x for x in ocok], label="OC_OK", lw=0.8); ax.plot([x * 1e3 for x in t], ina, label="INA out", lw=0.8)
        ax.set_ylabel("case " + case); ax.grid(alpha=0.3)
        if case == "A":
            ax.legend(ncol=4, fontsize=7, loc="upper left")
    axs[-1].set_xlabel("ms")
    fig.suptitle("v0.1.0 supply switch, gate chain, over-current latch (ngspice)")
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "switch_oc.png"), dpi=110)
    with open(os.path.join(HERE, "switch_oc_results.md"), "w") as f:
        f.write("# ngspice: supply switch + over-current latch (generated by run_switch_oc.py)\n\n| Case | Scenario | Result |\n|---|---|---|\n")
        for r in rows:
            f.write("| %s | %s | %s |\n" % r)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
