#!/usr/bin/env python3
"""v0.1.0 CUP pod, netlist v4: ONE rigid board (CUP, 6 layers) + a tiny REAR flex strip (TMAG5273 + motor link).

TEST ONLY - NOT FOR HUMAN USE.  Water only.

Decision 2026-11-19 (DECISION-omnipod-lessons.md): most discrete safety logic moves into the supervisor MCU (STM32C011), the pure-hardware cut path is
    VMOT = Q4 (hardware: LATCH_Q AND MCU_EN AND (DOCKED_H OR MOT_DIR[reverse]))  in series with  Q15 (supervisor SUP_PERMIT)
plus the over-current trip (INA180 + TLV7011 -> clears the TPL5010 latch).  Dropped from v3 (moved to the supervisor, see INTERLOCK.md section I):
OC_OK discrete leg, H15 XOR network (Q10/Q20/Q21/Q22/Q11), latch for OC (U12), boost, NTC + battery-sense switch, OC_TEST, PGATE_MON, board-to-board
pads, SENSOR FFC.  Added back: TPL5010 + latch (U5/U6) now watching the SUPERVISOR.

Run: python3 netlist_v4.py -> ../netlist_v4_cup.json, ../netlist_v4_rear.json, ERC summary.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import netlist as nl
import netlist_v3 as v3
from netlist import R0402, C0402, R0603, C0603, SOT23, SOT235, SOT236, SOD123
from netlist_v3 import R201, C201, R0201, C0201, SC70_5, ISP_PADS

OUT = os.path.join(HERE, "..")
SOT363 = ("Package_TO_SOT_SMD", "SOT-363_SC-70-6")

# ISP1807 pad -> net (same pad table as v3, nets no longer present are removed / re-used)
ISP = dict(ISP_PADS)
for k in (50, 52, 46):                       # TMAG_INT, NTC, SENSE_EN, OC_TEST: gone
    ISP.pop(k, None)
ISP[53] = "LED_R"; ISP[6] = "LED_G"; ISP[42] = "LED_B"   # RGB LED, low-active PWM
ISP[47] = "SUP_BOOT0"; ISP[49] = "SUP_NRST"   # nRF programs the supervisor through its system bootloader (BOOT0 strap + reset + UART)
ISP[4] = "LATCH_Q"                              # was PGATE_MON: latch output readback (RB6)

DOCK_LEG = "dock"


def build():
    v3_main, v3_power, _s = v3.build()
    byref = {p["ref"]: p for p in v3_main + v3_power}
    parts = []

    def take(ref, group=None, **kw):
        p = json.loads(json.dumps(byref[ref]))
        p.update(kw)
        p["board"] = "CUP"
        if group:
            p["group"] = group
        parts.append(p)
        return p

    def new(ref, value, fp, pins, lcsc=None, mpn=None, side="F", bom=True, note="", group="", dnp=False):
        p = dict(ref=ref, value=value, fp=list(fp), pins={str(k): v for k, v in pins.items()}, lcsc=lcsc, mpn=mpn, side=side,
                 bom=bom and not dnp, dnp=dnp, note=note, group=group, board="CUP")
        parts.append(p)
        return p

    def R(ref, val, a, b, group="", **kw):
        return new(ref, val, R0402, {1: a, 2: b}, nl.RV[val][0], nl.RV[val][1], group=group, **kw)

    def C(ref, val, a, b, group="", **kw):
        return new(ref, val, C0402, {1: a, 2: b}, nl.CV[val][0], nl.CV[val][1], group=group, **kw)

    def NM(ref, g, s, d, group="", note=""):
        return new(ref, "2N7002", SOT23, {1: g, 2: s, 3: d}, "C8545", "2N7002", group=group, note=note)

    # ---------------------------------------------------------------- MCU
    new("U1", "ISP1807-LR (consigned)", ("V010", "ISP1807"), {str(k): v for k, v in ISP.items()}, None, "ISP1807-LR", group="mcu",
        note="Insight SiP nRF52840 module 8x8x1.0, integrated antenna (pads 20/22 bridged), consigned. NFC pins as GPIO (UICR NFCPINS=1). Antenna half toward the +X board end")
    C("C1", "100nF", "3V3", "GND", "mcu"); C("C2", "4.7uF", "3V3", "GND", "mcu")
    R("R1", "100k", "3V3", "NRST", "mcu")
    # ---------------------------------------------------------------- supply: cell pads, LDO
    for ref, net, lab in (("SP1", "VBAT", "+"), ("SP2", "GND", "-")):
        new(ref, "cell lead pad %s" % lab, ("V010", "Wire_Pad_2.0x3.0"), {1: net}, bom=False, group="batt",
            note="hand-solder pad 2.0 x 3.0 for the cell lead %s (Ampul 301030 has two flying wires, user solders them); silkscreen label; near the cell wire exit (position VERIFY); strain-relief edge notch not added" % lab)
    take("C5", "pwr"); take("U2", "pwr"); take("C7", "pwr")
    # ---------------------------------------------------------------- USB-C + charger
    for ref in ("JU1", "DU1", "RU1", "RU2", "UU1", "CU1"):
        p = take(ref, "usb")
        p["pins"] = {k: ("VBUS_P" if v == "VBUS_R" else v) for k, v in p["pins"].items()}
        if ref == "JU1":
            p["note"] = "PROXY HRO TYPE-C-31-M-12 (top mount, 3.26). The pod stack needs a MID-MOUNT/sink receptacle in a board-edge notch (board plane z 5.3-5.9 inside the 4.2-7.46 body); no JLC mid-mount part verified"
    take("U3", "chg", pins={"1": "CHG_STAT", "2": "GND", "3": "VBAT", "4": "VBUS_P", "5": "CHG_PROG"})
    take("R3", "chg", pins={"1": "CHG_PROG", "2": "GND"}, value="47k", note="PROG 47k -> about 21 mA charge current")
    # VBAT sense (always on, 1M/1M = 1.9 uA, 100 nF holds the SAADC sample)
    R("R6", "1M", "VBAT", "VBAT_SENSE", "sense"); R("R7", "1M", "VBAT_SENSE", "GND", "sense"); C("C10", "100nF", "VBAT_SENSE", "GND", "sense")
    # ---------------------------------------------------------------- driver (unchanged from v3)
    for ref in ("U7", "R34", "R35", "R36", "R37", "R38", "C19", "R39", "R40", "R43", "C21"):
        take(ref, "drv")
    pr = {p["ref"]: p for p in parts}
    parts[:] = [p for p in parts if p["ref"] != "R38"]
    new("R38", "5.1k", R0402, {1: "MOT_REF", 2: "GND"}, "C25905", "0402WGF5101TCE", group="drv", note="VREF = 3.3 V x 5.1k/105.1k = 0.160 V -> current limit about 0.16 A with 1.0 ohm sense (motor 0.18 A/phase; basic part instead of 5.6k = 0.175 A); datasheet formula VERIFY")
    # ---------------------------------------------------------------- motor spring pads / FPC pads (motor via the REAR strip)
    new("J1", "PicoBlade A1251WR-S-4P (CJT, plug of the NFP-608 factory lead)", ("V010", "A1251WR-S-4P"),
        {1: "MOT_B2", 2: "MOT_A2", 3: "MOT_B1", 4: "MOT_A1"}, "C225113", "A1251WR-S-4P-LCP", side="B", group="mot",
        note="4-pin 1.25 mm right-angle socket for the factory plug, PCBA-soldered, bottom side (about 2.8 mm tall: fits only in the side_a/side_b blocks below the board, NOT over the cell/adapter); pin order and plug fit VERIFY")
    for i, net in enumerate(("3V3", "GND", "I2C_SDA", "I2C_SCL")):
        new("TL%d" % (i + 1), "REAR strip pad (%s)" % net, ("V010", "FPC_Pad_1.2x0.6"), {1: net}, bom=False, side="B", group="rear",
            note="ENIG pad pair with the REAR flex strip (TMAG5273 at gear B)")
    R("R67", "4.7k", "3V3", "I2C_SDA", "rear"); R("R68", "4.7k", "3V3", "I2C_SCL", "rear")
    # ---------------------------------------------------------------- UI: LED, button, piezo
    new("LD1", "RGB LED SZYY1615RGB-B (common anode)", ("V010", "LED_RGB_1615_4P"), {1: "LED_R", 2: "LED_G", 3: "LED_B", 4: "LED_A"}, "C3029071", "SZYY1615RGB-B", group="ui",
        note="top-facing status RGB LED under the clear lid, common anode through ONE 1k from VBAT (GPIO high = off even at 4.2 V, no idle current); one lit channel about 0.7 to 1.7 mA; pad order and polarity VERIFY")
    R("R74", "1k", "VBAT", "LED_A", "ui")
    take("D5", "ui", pins={"1": "CHG_STAT", "2": "LED_R"}, note="diode-OR: MCP73832 STAT low (charging) pulls the red cathode low even while the MCU sleeps (cathode pad 1 = STAT)")
    new("SW1", "SKRPACE010 side tact", ("V010", "SW_SKRPACE010_4.2x3.2"), {1: "BTN_N", 2: "BTN_N", 3: "GND", 4: "GND"}, "C139797", "SKRPACE010", group="ui",
        note="ALPS side-actuated tact 4.2 x 3.2 x 1.4, actuator toward the -Y long wall; pad mapping VERIFY; internal nRF pull-up, no external resistor")
    new("BZ1", "FUET-4020 SMD magnetic sounder (DNP)", ("V010", "BZ_4020"), {1: "VBAT", 2: "PZ_A"}, "C391027", "FUET-4020", side="B", group="ui", dnp=True,
        note="DNP footprint 4 x 4 x 2.0 mm (no sounder <= 1.5 mm tall exists at JLC; the smallest are 4 x 4 x 2.0), bottom side of the side_b block; fit by hand or order as an extra part; driven by QBA + D6, off by default")
    new("D6", "1N4148W (sounder flyback, DNP)", ("Diode_SMD", "D_SOD-123"), {1: "VBAT", 2: "PZ_A"}, "C81598", "1N4148W", group="ui", dnp=True, note="flyback across the sounder coil (cathode pad 1 on VBAT); fit with BZ1")
    R("RDA", "100k", "BUZ_A", "GND", "ui")
    # ---------------------------------------------------------------- dock hall (single, see INTERLOCK.md section I: 2oo2 dropped, one magnet) + inverter into DOCKED_H
    new("U4A", "DRV5032FADMRR", ("Bench", "DRV5032_X2SON-4_DMR0004B"), {1: "3V3", 2: "GND", 4: "DOCK_N", 5: "GND"}, "C2152496", "DRV5032FADMRR", side="B", group=DOCK_LEG,
        note="dock hall on the underside of the dock leg, centred on the dock magnet axis (z 4.9-5.3); VERIFY threshold. Single hall: a second hall cannot see the d1 x 0.5 magnet (Bz of the dipole changes sign about 1 mm off axis)")
    R("R21", "100k", "3V3", "DOCKED_H", DOCK_LEG)
    # ---------------------------------------------------------------- supervisor + step gate + TPL5010 latch
    new("U30", "STM32C011F4U6", ("V010", "UFQFPN-20_3x3_P0.5"),
        {1: "MCU_EN", 2: "SUP_DONE", 3: "SUP_WAKE", 4: "3V3", 5: "GND", 6: "SUP_NRST", 7: "ARM_CLK", 8: "STCK_MCU", 9: "MOT_DIR", 10: "OC_OK", 11: "SUP_STCK_EN",
         12: "SUP_PERMIT", 13: "SUP_OK", 14: "NRST", 16: "SUP_TXD", 17: "SUP_RXD", 19: "SUP_BOOT0", 20: "DOCKED_H", 21: "GND"}, "C5456188", "STM32C011F4U6", group="sup",
        note="independent supervisor (INTERLOCK.md H, I); UFQFPN-20 pin map assumed = TSSOP-20 map, pins 2/3 (SUP_DONE/SUP_WAKE) newly assigned: VERIFY against DS13866")
    C("C50", "100nF", "3V3", "GND", "sup")
    R("R80", "100k", "SUP_NRST", "3V3", "sup"); R("R79", "100k", "SUP_BOOT0", "GND", "sup"); R("R81", "100k", "SUP_STCK_EN", "GND", "sup")
    take("U31", "sup")
    new("U5", "TPL5010DDCR", SOT236, {1: "3V3", 2: "GND", 3: "WDT_DELAY", 4: "SUP_DONE", 5: "SUP_WAKE", 6: "SUP_NRST"}, "C473912", "TPL5010DDCR", group="wdt",
        note="independent timer now watches the SUPERVISOR: no DONE after WAKE -> RSTn low: resets the supervisor and clears the latch")
    R("R26", "10k", "WDT_DELAY", "GND", "wdt")
    new("U6", "SN74AUP1G74DCUR", ("Package_SO", "VSSOP-8_2.3x2mm_P0.5mm"), {1: "ARM_CLK", 2: "3V3", 3: None, 4: "GND", 5: "LATCH_Q", 6: "LATCH_CLR_N", 7: "3V3", 8: "3V3"},
        "C140267", "SN74AUP1G74DCUR", group="wdt", note="interlock latch: set by an ARM_CLK edge, cleared by LATCH_CLR_N (power-up, TPL5010 timeout, supervisor reset, over-current)")
    new("U32", "TP74AUP1G08S5 (AND)", SC70_5, {1: "SUP_NRST", 2: "OC_OK", 3: "GND", 4: "LATCH_CLR_N", 5: "3V3"}, "C48886815", "TP74AUP1G08S5", group="wdt",
        note="LATCH_CLR_N = SUP_NRST AND OC_OK: any supervisor reset / TPL5010 timeout or an over-current trip clears the latch (no diodes)")
    R("R29", "100k", "ARM_CLK", "GND", "wdt"); R("R18", "100k", "MCU_EN", "GND", "wdt")
    # ---------------------------------------------------------------- motor switch: Q4 (hardware legs) in series with Q15 (supervisor leg)
    for ref in ("Q4", "Q15", "R9", "C11", "R11", "R83", "R84", "R82"):
        take(ref, "sw")
    pw = {p["ref"]: p for p in parts}
    pw["Q15"]["pins"]["1"] = "PGATE2"
    pw["Q4"]["pins"] = {"1": "PGATE", "2": "VBAT", "3": "VMOT_A"}
    pw["Q15"]["pins"] = {"1": "PGATE2", "2": "VMOT_A", "3": "VMOT_RAW"}
    # chain: PGATE -R11- CH_TOP -QL(LATCH_Q)- PG_A -QE(MCU_EN)- PG_B -(QD DOCKED_H || QR MOT_DIR)- GND ; supervisor leg QS on PGATE2
    legs = dict(QL=("LATCH_Q", "PG_B", "CH_TOP"), QD=("DOCKED_H", "GND", "PG_B"), QR=("MOT_DIR", "GND", "PG_B"),
                QS=("SUP_PERMIT", "GND", "QS_D"), Q17=("PGATE", "GND", "BLD"), Q17B=("PGATE2", "GND", "BLD"),
                Q7=("DOCK_N", "GND", "DOCKED_H"), QBA=("BUZ_A", "GND", "PZ_A"))
    notes = dict(QL="latch leg (hardware)", QE="MCU_EN leg (hardware)", QD="docked branch of the last leg", QR="reverse branch (undocked refill / draw); forward undocked stays blocked",
                 QS="supervisor leg on Q15", Q12="DOCK_TEST: pulls DOCKED_H low (POST, can only force undocked)", Q17="bleeder: VMOT discharge while PGATE is high",
                 Q17B="bleeder: also when only the supervisor cut", Q7="hall inverter: DOCK_N low (hall asserted) -> DOCKED_H high", QBA="piezo bridge leg A")
    pairs = [("QL", "QS"), ("QD", "Q17"), ("QR", "Q17B"), ("Q7", "QBA")]   # no package holds two legs of the same chain
    for k, (a, b) in enumerate(pairs):
        ga, sa, da = legs[a]; gb, sb, db = legs[b]
        new("QD%d" % (k + 1), "2N7002DW (%s + %s)" % (a, b), SOT363, {"2": ga, "1": sa, "6": da, "5": gb, "4": sb, "3": db}, "C83571", "2N7002DW-7-F",
            group="sw", note="dual N-FET: %s (S1 G2 D6) = %s | %s (S4 G5 D3) = %s" % (a, notes[a], b, notes[b]))
    R("R24", "100R", "VMOT_PRE", "BLD", "sw")
    R("R16", "100k", "MOT_DIR", "GND", "sw")
    # ---------------------------------------------------------------- over-current trip + readbacks
    take("R44", "oc", pins={"1": "VMOT_PRE", "2": "VMOT"})
    take("U9", "oc", pins={"1": "INA_OUT", "2": "GND", "3": "VMOT_PRE", "4": "VMOT", "5": "VMOT_RAW"})
    take("C24", "oc"); take("R48", "oc", pins={"1": "INA_OUT", "2": "I_SENSE"}); take("C27", "oc", pins={"1": "I_SENSE", "2": "GND"})
    take("U11", "oc", pins={"1": "OC_OK", "2": "GND", "3": "I_SENSE", "4": "OC_REF", "5": "3V3"})
    take("R49", "oc"); take("R50", "oc", pins={"1": "OC_REF", "2": "GND"}, note="OC reference 3V3/2 = 1.65 V -> trip about 0.375 A")
    take("R57", "oc"); take("R58", "oc")
    # ---------------------------------------------------------------- 5 V boost behind the interlock switch (motor NFP-608-26.45-SGM, 4.8 V rated)
    new("U8", "TPS61023DRLR", ("Package_TO_SOT_SMD", "SOT-563"), {1: "VMOT_RAW", 2: "GND", 3: "BST_SW", 4: "VMOT_RAW", 5: "VMOT_PRE", 6: "BST_FB"}, "C919459", "TPS61023DRLR", group="boost",
        note="sync boost 3.7 A switch, 0.5-5.5 V in, 1 uA off, about 90 % at 0.3 A out; EN tied to the SWITCHED VMOT_RAW (zero idle drain, cut by Q4/Q15); pinout 1 EN 2 GND 3 SW 4 VIN 5 VOUT 6 FB: VERIFY")
    new("L1", "1uH 2520 (WPN252012E1R0MT)", ("Inductor_SMD", "L_1008_2520Metric"), {1: "VMOT_RAW", 2: "BST_SW"}, "C370610", "WPN252012E1R0MT", group="boost", note="1 uH 2.5 x 2.0 x 1.2; Isat VERIFY >= 2.5 A")
    new("R55", "220k", R0402, {1: "VMOT_PRE", 2: "BST_FB"}, "C25767", "0402WGF2203TCE", group="boost", note="FB divider 220k/30k, FB 0.595 V -> 4.96 V")
    new("R56", "30k", R0402, {1: "BST_FB", 2: "GND"}, "C25776", "0402WGF3002TCE", group="boost")
    take("DZ1", "boost", pins={"1": "VMOT_PRE", "2": "GND"})
    C0805 = ("Capacitor_SMD", "C_0805_2012Metric")
    for i in (1, 2):
        new("CB%d" % i, "22uF 6.3V X5R 0805", C0805, {1: "VMOT_PRE", 2: "GND"}, "C45783", "CL21A226MAQNNNE", group="boost",
            note="bulk on the boost output, before the shunt (no inrush through the over-current shunt); basic part; about 8 uF effective at 5 V DC bias")
    new("C31", "10uF", C0603, {1: "VMOT_PRE", 2: "GND"}, "C19702", "CL10A106KP8NNNC", group="boost")
    # ---------------------------------------------------------------- SWD + test pads (top side)
    swd = [("SWDIO", "SWDIO"), ("SWDCLK", "SWDCLK"), ("NRST", "NRST"), ("GND", "GND"), ("3V3", "3V3")]
    for i, (v, n) in enumerate(swd):
        new("J%d" % (10 + i), "SWD pad " + v, ("V010", "TP_Pad_D0.8"), {1: n}, bom=False, group="swd", note="SWD pad (spring probe jig)")
    for i, n in enumerate(("VMOT", "STCK_DRV")):
        new("TP%d" % (i + 1), n, ("V010", "TP_Pad_D0.8"), {1: n}, bom=False, group="tp", note="test pad")
    # ---------------------------------------------------------------- REAR flex strip (separate FPC, own netlist)
    rear = []

    def newr(ref, value, fp, pins, lcsc=None, mpn=None, side="F", bom=True, note="", group="rear"):
        rear.append(dict(ref=ref, value=value, fp=list(fp), pins={str(k): v for k, v in pins.items()}, lcsc=lcsc, mpn=mpn, side=side, bom=bom, note=note, group=group, board="REAR", dnp=False))

    newr("U10T", "TMAG5273A1QDBVR", SOT236, {1: "I2C_SCL", 2: "GND", 3: "GND", 4: "3V3", 5: None, 6: "I2C_SDA"}, "C3716049", "TMAG5273A1QDBVR", note="0.5 mm from the gear-B magnet (mechanics ko_tmag_board)")
    newr("C41", "100nF", C0402, {1: "3V3", 2: "GND"}, "C1525", "CL05B104KO5NNNC")
    for i, net in enumerate(("3V3", "GND", "I2C_SDA", "I2C_SCL")):
        newr("TR%d" % (i + 1), "strip pad %s" % net, ("V010", "FPC_Pad_1.2x0.6"), {1: net}, bom=False)
    for p in parts:
        fpn = p["fp"][1]
        if fpn.startswith(("R_0201", "C_0201")):
            tab = nl.RV if fpn.startswith("R") else nl.CV
            v = {"4.7M": "1M"}.get(p["value"], p["value"])
            p["fp"] = list(R0402 if fpn.startswith("R") else C0402); p["value"] = v; p["lcsc"], p["mpn"] = tab[v]
        if p["ref"] == "C21":
            p.update(value="22uF", fp=list(C0805), lcsc="C45783", mpn="CL21A226MAQNNNE")
    return parts, rear


def nets_of(parts):
    nets = {}
    for p in parts:
        for pad, n in p["pins"].items():
            if n:
                nets.setdefault(n, []).append((p["ref"], pad))
    return nets


def erc(parts, rear):
    bad = []
    n = nets_of(parts)
    nr = nets_of(rear)
    refs = [p["ref"] for p in parts]
    if len(refs) != len(set(refs)):
        bad.append("duplicate refs")
    for net, l in sorted(n.items()):
        if len(l) < 2 and not net.startswith(("SUP_SWD", "SWD")) and not (net == "3V3"):
            bad.append("single-pin net %s %s" % (net, l))
    for net, l in sorted(nr.items()):
        if len(l) < 2:
            bad.append("REAR single-pin net %s %s" % (net, l))
    for net in nr:
        if net not in n:
            bad.append("REAR net %s missing on CUP" % net)
    # every net that drives a gate must have a driver / pull
    return bad


if __name__ == "__main__":
    parts, rear = build()
    bad = erc(parts, rear)
    json.dump(parts, open(os.path.join(OUT, "netlist_v4_cup.json"), "w"), indent=1)
    json.dump(rear, open(os.path.join(OUT, "netlist_v4_rear.json"), "w"), indent=1)
    for name, ps in (("cup", parts), ("rear", rear)):
        print(name, len(ps), "parts", len(nets_of(ps)), "nets", "BOM parts", sum(1 for p in ps if p["bom"]), "BOM lines", len(set((p["value"], tuple(p["fp"])) for p in ps if p["bom"])))
    for b in bad:
        print("ERC:", b)
    print("ERC problems:", len(bad))
