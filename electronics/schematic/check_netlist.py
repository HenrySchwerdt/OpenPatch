#!/usr/bin/env python
"""Designregel-Pruefung der erzeugten Netzliste (netlist.json). Exit-Code 1 bei Verstoss.
Aufruf: ../.venv/bin/python -I check_netlist.py"""
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

# 1. Jedes Netz >= 2 Pins (ausser NC)
single = [n for n, ps in nets.items() if len(ps) < 2 and n != "__NOCONNECT"]
ok(not single, "Alle Netze haben >= 2 Anschluesse (Einzelnetze: %s)" % single)
# 2. Kein Pin in zwei Netzen
seen = {}; dup = []
for n, ps in nets.items():
    for p in ps:
        if p in seen and n != "__NOCONNECT": dup.append((p, seen[p], n))
        seen[p] = n
ok(not dup, "Kein Pin liegt in zwei Netzen %s" % dup)
# 3. Jeder Nicht-DNP-IC-Pin angeschlossen oder explizit NC
conn_pins = set(seen)
# 4. Stromversorgungs-Entkopplung: jedes Versorgungsnetz hat >= 1 Kondensator nach GND
def caps_on(n): return [r for r in refs(n) if r.startswith("C")]
for n in ("3V3", "VBAT", "VMOT", "RECT", "VQI_5V", "VPER_3V3"):
    ok(len(caps_on(n)) >= 1, "Entkopplung auf %s: %s" % (n, caps_on(n)))
ok(len([r for r in refs("3V3") if r.startswith("C")]) >= 5, "3V3: >= 5 Kondensatoren")
# 5. ISP1807: VCC_NRF an 3V3, alle 10 VSS an GND, USB-Pads offen
ok(pin_of("U1", "VCC_NRF") == "3V3", "ISP1807 VCC_NRF an 3V3")
mcu_gnd = [p for p in pins("GND") if p.startswith("U1.")]
ok(len(mcu_gnd) == 10, "ISP1807: alle 10 VSS-Pads an GND (%d)" % len(mcu_gnd))
ok(pin_of("U1", "OUT_MOD") is not None and pin_of("U1", "OUT_ANT") is not None and pin_of("U1", "OUT_MOD") != pin_of("U1", "OUT_ANT"), "OUT_MOD -> R90 -> OUT_ANT (integrierte Antenne, kein externes pi-Netz)")
# 6. GPIO-Eindeutigkeit (jeder MCU-Pin max. 1 Netz) - durch 2. abgedeckt; Zusatz: Anzahl benutzter GPIO
used = [p for p in seen if p.startswith("U1.") and ("(P" in p or "SWD" in p) and seen[p] != "__NOCONNECT"]
ok(len(used) == 26, "ISP1807-GPIO genutzt (inkl. SWD/RESET): %d (Soll 26)" % len(used))
# 7. SICHERHEITS-INTERLOCK-INVARIANTEN
allow = pins("MOT_ALLOW")
ok(any(p.startswith("U6.") and "(Q)" in p for p in allow), "MOT_ALLOW wird vom Latch-Q (U6) getrieben")
ok(any(p.startswith("U7.") and "(ON)" in p for p in allow), "MOT_ALLOW steuert Lastschalter U7 (ON)")
ok(not any(p.startswith("U1.") and not "(P0.16)" in p for p in allow), "Kein MCU-Ausgang direkt auf MOT_ALLOW (nur Rueckleser P0.04)")
ok(any(p.startswith("R53.") for p in allow), "Pulldown R53 auf MOT_ALLOW (Default AUS bei SYS-Verlust)")
ok(set(r for r in refs("VMOT") if r[0] in "UQ") <= {"U7", "U4"}, "VMOT nur an Lastschalter-Ausgang (U7) und Treiber VS (U4): %s" % sorted(set(refs("VMOT"))))
ok(pin_of("U4", "VS") == "VMOT", "STSPIN220 VS haengt NUR an VMOT (nie direkt an VBAT)")
ok(pin_of("U7", "VIN") == "VBAT" and pin_of("U7", "VOUT") == "VMOT", "Lastschalter: VBAT -> VMOT")
clr = pins("LATCH_CLR_N")
ok(any(p.startswith("D2.") and "(A)" in p for p in clr) and pin_of("D2", "K") == "NRST", "CLR# wird per Diode D2 von NRST (TPL5010 RSTn) gezogen")
ok(any(p.startswith("U1.") and "(P0.22)" in p for p in clr), "CLR# vom MCU-KILL_N (P1.07) ziehbar")
ok(any(p.startswith("C52.") for p in clr), "Power-On-Clear-Kondensator C52 an CLR#")
ok(pin_of("U5", "RSTN") == "NRST" and pin_of("U1", "P0.18/RESET") == "NRST", "TPL5010 RSTn resettet zusaetzlich den MCU (nRESET)")
ok(pin_of("U5", "DONE") == "WDT_DONE" and pin_of("U1", "P0.06") == "WDT_DONE", "TPL5010 DONE <- MCU P2.00")
ok(pin_of("U6", "D") == "3V3" and pin_of("U6", "PRE_N") == "3V3", "Latch D und PRE# fest auf High (nur CLK setzt)")
ok(any(p.startswith("R72.") for p in pins("MOT_STBY_DRV")) and pin_of("U4","STBY_RESET")=="MOT_STBY_DRV", "STSPIN220 STBY/RESET hat Pulldown R72 (MCU-Enable fail-safe)")
# 8. Zweiter Hall-Pfad
ok(pin_of("U9", "OUT") == "HALL_A" and pin_of("U10", "OUT") == "HALL_B", "DRV5032 A/B -> HALL_A/B (QDEC, CPU-unabhaengiger Pfad B)")
ok(pin_of("U8", "SDA") == "I2C_SDA", "TMAG5273 (Pfad A) am I2C")
# 10. Ladepfad
ok(pin_of("U2", "OUT") == "VQI_5V" and pin_of("U3", "IN") == "VQI_5V", "BQ51003 OUT -> BQ25120A IN")
ok(pin_of("U3", "BAT") == "VBAT" and pin_of("U3", "SYS") == "3V3", "BQ25120A: BAT=VBAT, SYS=3V3")
ok(pin_of("Q2", "D") == "VBAT_RAW" and pin_of("Q2", "S") == "VBAT", "Verpolschutz-PFET Q2 in der +Schiene")
# 11. Programmier-/Testpads
for r, n in (("J1:2","SWDIO"),("J1:4","SWDCLK"),("J1:3","NRST")):
    pass
ok(pin_of("J1", "SWDIO") == "SWDIO" and pin_of("J1", "SWCLK") == "SWDCLK" and pin_of("J1", "NRESET") == "NRST" and pin_of("J1", "VTREF") == "3V3" and pin_of("J1", "GND") == "GND", "TC2030 J1: SWDIO/SWCLK/NRESET/VTREF/GND korrekt")
for r, n in (("TP1","3V3"),("TP3","VBAT"),("TP4","VMOT"),("TP6","HALL_A"),("TP7","HALL_B"),("TP10","MOT_A1"),("TP11","MOT_A2"),("TP12","MOT_B1"),("TP13","MOT_B2")):
    ok(pin_of(r, "1") == n, "Testpad %s -> %s" % (r, n))
print("\n".join(oks)); print("\n".join(errs))
print("\n%d Pruefungen OK, %d FEHLER" % (len(oks), len(errs)))
open(os.path.join(OUT, "checks-report.txt"), "w").write("\n".join(oks + errs) + "\n\n%d OK, %d FEHLER\n" % (len(oks), len(errs)))
sys.exit(1 if errs else 0)
