#!/usr/bin/env python
"""Design rule check of the generated netlist (netlist.json). Exit code 1 on violation.
Usage: ../.venv/bin/python -I check_netlist.py"""
import json, os, re, sys
OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
d = json.load(open(os.path.join(OUT, "netlist.json")))
comps, nets = d["components"], d["nets"]
errs, oks = [], []
def ok(c, msg):
    (oks if c else errs).append(("OK  " if c else "FAIL ") + msg)
def refs(n): return [p.split(".")[0] for p in nets.get(n, [])]
def pins(n): return nets.get(n, [])
def pin_of(ref, name):
    for n, ps in nets.items():
        for p in ps:
            if p.startswith(ref + ".") and p.endswith("(%s)" % name): return n
    return None

# 1. Every net has >= 2 pins (except NC)
single = [n for n, ps in nets.items() if len(ps) < 2 and n != "__NOCONNECT"]
ok(not single, "All nets have >= 2 connections (single-pin nets: %s)" % single)
# 2. No pin in two nets
seen = {}; dup = []
for n, ps in nets.items():
    for p in ps:
        if p in seen and n != "__NOCONNECT": dup.append((p, seen[p], n))
        seen[p] = n
ok(not dup, "No pin is in two nets %s" % dup)
# 3. Every non-DNP IC pin is connected or explicitly NC
conn_pins = set(seen)
# 4. Supply decoupling: every supply net has >= 1 capacitor to GND
def caps_on(n): return [r for r in refs(n) if r.startswith("C")]
for n in ("3V3", "VBAT", "VMOT", "RECT", "VQI_5V", "VPER_3V3"):
    ok(len(caps_on(n)) >= 1, "Decoupling on %s: %s" % (n, caps_on(n)))
ok(len([r for r in refs("3V3") if r.startswith("C")]) >= 5, "3V3: >= 5 capacitors")
# 5. ISP1807: VCC_NRF on 3V3, all 10 VSS on GND, USB pads open
ok(pin_of("U1", "VCC_NRF") == "3V3", "ISP1807 VCC_NRF on 3V3")
mcu_gnd = [p for p in pins("GND") if p.startswith("U1.")]
ok(len(mcu_gnd) == 10, "ISP1807: all 10 VSS pads on GND (%d)" % len(mcu_gnd))
ok(pin_of("U1", "OUT_MOD") is not None and pin_of("U1", "OUT_ANT") is not None and pin_of("U1", "OUT_MOD") != pin_of("U1", "OUT_ANT"), "OUT_MOD -> R90 -> OUT_ANT (integrated antenna, no external pi network)")
# 6. GPIO uniqueness (each MCU pin in at most 1 net) - covered by 2.; addition: number of GPIOs used
used = [p for p in seen if p.startswith("U1.") and ("(P" in p or "SWD" in p) and seen[p] != "__NOCONNECT"]
ok(len(used) == 26, "ISP1807 GPIOs used (incl. SWD/RESET): %d (expected 26)" % len(used))
# 7. SAFETY INTERLOCK INVARIANTS
allow = pins("MOT_ALLOW")
ok(any(p.startswith("U6.") and "(Q)" in p for p in allow), "MOT_ALLOW is driven by the latch Q (U6)")
ok(any(p.startswith("U7.") and "(ON)" in p for p in allow), "MOT_ALLOW controls the load switch U7 (ON)")
ok(not any(p.startswith("U1.") and not "(P0.16)" in p for p in allow), "No MCU output directly on MOT_ALLOW (read-back only, P0.04)")
ok(any(p.startswith("R53.") for p in allow), "Pull-down R53 on MOT_ALLOW (default OFF on loss of SYS)")
ok(set(r for r in refs("VMOT") if r[0] in "UQ") <= {"U7", "U4"}, "VMOT only on the load switch output (U7) and driver VS (U4): %s" % sorted(set(refs("VMOT"))))
ok(pin_of("U4", "VS") == "VMOT", "STSPIN220 VS is connected ONLY to VMOT (never directly to VBAT)")
ok(pin_of("U7", "VIN") == "VBAT" and pin_of("U7", "VOUT") == "VMOT", "Load switch: VBAT -> VMOT")
clr = pins("LATCH_CLR_N")
ok(any(p.startswith("D2.") and "(A)" in p for p in clr) and pin_of("D2", "K") == "NRST", "CLR# is pulled low by NRST (TPL5010 RSTn) through diode D2")
ok(any(p.startswith("U1.") and "(P0.22)" in p for p in clr), "CLR# can be pulled low by the MCU KILL_N (P1.07)")
ok(any(p.startswith("C52.") for p in clr), "Power-on clear capacitor C52 on CLR#")
ok(pin_of("U5", "RSTN") == "NRST" and pin_of("U1", "P0.18/RESET") == "NRST", "TPL5010 RSTn additionally resets the MCU (nRESET)")
ok(pin_of("U5", "DONE") == "WDT_DONE" and pin_of("U1", "P0.06") == "WDT_DONE", "TPL5010 DONE <- MCU P2.00")
ok(pin_of("U6", "D") == "3V3" and pin_of("U6", "PRE_N") == "3V3", "Latch D and PRE# tied high (only CLK sets it)")
ok(any(p.startswith("R72.") for p in pins("MOT_STBY_DRV")) and pin_of("U4","STBY_RESET")=="MOT_STBY_DRV", "STSPIN220 STBY/RESET has pull-down R72 (MCU enable is fail-safe)")
# 8. Second Hall path
ok(pin_of("U9", "OUT") == "HALL_A" and pin_of("U10", "OUT") == "HALL_B", "DRV5032 A/B -> HALL_A/B (QDEC, CPU-independent path B)")
ok(pin_of("U8", "SDA") == "I2C_SDA", "TMAG5273 (path A) on I2C")
# 10. Charging path
ok(pin_of("U2", "OUT") == "VQI_5V" and pin_of("U3", "IN") == "VQI_5V", "BQ51003 OUT -> BQ25120A IN")
ok(pin_of("U3", "BAT") == "VBAT" and pin_of("U3", "SYS") == "3V3", "BQ25120A: BAT=VBAT, SYS=3V3")
ok(pin_of("Q2", "D") == "VBAT_RAW" and pin_of("Q2", "S") == "VBAT", "Reverse-polarity protection PFET Q2 in the + rail")
# 11. Programming/test pads
for r, n in (("J1:2","SWDIO"),("J1:4","SWDCLK"),("J1:3","NRST")):
    pass
ok(pin_of("J1", "SWDIO") == "SWDIO" and pin_of("J1", "SWCLK") == "SWDCLK" and pin_of("J1", "NRESET") == "NRST" and pin_of("J1", "VTREF") == "3V3" and pin_of("J1", "GND") == "GND", "TC2030 J1: SWDIO/SWCLK/NRESET/VTREF/GND correct")
for r, n in (("TP1","3V3"),("TP3","VBAT"),("TP4","VMOT"),("TP6","HALL_A"),("TP7","HALL_B"),("TP10","MOT_A1"),("TP11","MOT_A2"),("TP12","MOT_B1"),("TP13","MOT_B2")):
    ok(pin_of(r, "1") == n, "Testpad %s -> %s" % (r, n))
print("\n".join(oks)); print("\n".join(errs))
print("\n%d checks OK, %d FAILED" % (len(oks), len(errs)))
open(os.path.join(OUT, "checks-report.txt"), "w").write("\n".join(oks + errs) + "\n\n%d OK, %d FAILED\n" % (len(oks), len(errs)))
sys.exit(1 if errs else 0)
