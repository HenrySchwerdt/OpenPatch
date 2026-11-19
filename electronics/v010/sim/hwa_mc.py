#!/usr/bin/env python3
"""HW-A tolerance Monte Carlo (closed form of the RC window): window t_w = RC ln(Vcc/VT-), dead time t_d = RC ln((Vcc-VT-)/(Vcc-VT+)).
R59||R60 = 500 k +-1 %, C33 1 uF X5R -30..+10 % at 3.3 V bias and temperature (pessimistic), VT+ 1.5..2.2 V, VT- 0.8..1.4 V (74AUP1G17 at 3.3 V, datasheet range, ASSUMED),
Vcc 3.0..3.6 V.  Bound per watchdog interval T_wd (TPL5010 ~2 s, up to 4 s worst case in 06-diagnostics 1.3) = (floor(T_wd / t_cycle_min) + 1) windows x 32 pulses.
"""
import math
import random

random.seed(7)
N = 200000
cyc, win, dead = [], [], []
for _ in range(N):
    R = 500e3 * random.uniform(0.99, 1.01)
    C = 1e-6 * random.uniform(0.7, 1.1)
    vcc = random.uniform(3.0, 3.6)
    vtp = random.uniform(1.5, 2.2)
    vtn = random.uniform(0.8, min(1.4, vtp - 0.2))
    tw = R * C * math.log(vcc / vtn)
    td = R * C * math.log((vcc - vtn) / (vcc - vtp))
    win.append(tw); dead.append(td); cyc.append(tw + td)
cyc_min = min(cyc)
res = ["window t_w   min %.2f  max %.2f s" % (min(win), max(win)),
       "dead time    min %.2f  max %.2f s" % (min(dead), max(dead)),
       "arm cycle    min %.2f  max %.2f s (min distance between two accepted ARM edges)" % (cyc_min, max(cyc))]
for twd in (2.0, 4.0):
    arms = int(twd / cyc_min) + 1
    steps = arms * 32
    res.append("watchdog interval %.0f s: at most %d windows = %d pulses = %.2f U (16:20, 3.951 mU/step) / %.2f U (18:18, 4.94 mU/step)" % (twd, arms, steps, steps * 0.003951, steps * 0.00494))
res.append("legitimate use: one tick per 1 s with <= 32 forward steps = 0.126 U per tick (more than the 3.4..6.3 steps/s of a 1.5 U/min bolus)")
res.append("sustained rate bound with re-arm at the minimum cycle: 32 pulses / %.2f s = %.1f U/min (16:20)" % (cyc_min, 32 / cyc_min * 0.003951 * 60))
open(__file__.replace("hwa_mc.py", "hwa_mc_results.txt"), "w").write("\n".join(res) + "\n")
print("\n".join(res))
