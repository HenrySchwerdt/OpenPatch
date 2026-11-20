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

# HJ-840 (nRF52840 SiP, LGA64) pad -> nRF pin (hardware design manual table 2-2); pads not listed are not connected
HJ_PIN = {
    "A1": "GND", "A2": "P1.01", "A3": "P0.21", "A4": "P0.20", "A5": "P0.17", "A6": "P0.14", "A7": "ANT", "A8": "BOARD_ANT",
    "B1": "P0.22", "B2": "P1.04", "B3": "P1.07", "B4": "P0.09", "B5": "P1.05", "B6": "P0.24", "B7": "P1.06", "B8": "P1.14",
    "C1": "P0.25", "C2": "SWDIO", "C3": "SWCLK", "C4": "DEC5", "C5": "P0.10", "C6": "P0.13", "C7": "P1.11", "C8": "P1.12",
    "D1": "P0.19", "D2": "P1.00", "D3": "P1.02", "D4": "P1.03", "D5": "P0.23", "D6": "P1.10", "D7": "P1.13", "D8": "P0.31",
    "E1": "P0.18/RESET", "E2": "P0.15", "E3": "P0.16", "E4": "P1.08", "E5": "P1.15", "E6": "P0.02", "E7": "P0.28", "E8": "P0.03",
    "F1": "D+", "F2": "VBUS", "F3": "P0.11", "F4": "P0.07", "F5": "P0.27", "F6": "P0.00", "F7": "P0.30", "F8": "P0.29",
    "G1": "D-", "G2": "DECUSB", "G3": "P0.12", "G4": "P1.09", "G5": "P0.05", "G6": "P0.01", "G7": "P0.26", "G8": "P0.06",
    "H1": "DCCH", "H2": "VDDH", "H3": "VDD", "H4": "VDD", "H5": "P0.08", "H6": "DEC1", "H7": "P0.04", "H8": "GND"}
HJ_FIXED = {"A1": "GND", "H8": "GND", "A7": "ANT_A", "A8": "ANT_B", "H2": "3V3", "H3": "3V3", "H4": "3V3", "F1": "USB_DP", "G1": "USB_DM", "F2": "VBUS_P",
            "E1": "NRST", "C2": "SWDIO", "C3": "SWDCLK", "G5": "VBAT_SENSE", "E6": "SNSA", "H7": "VMOT_SENSE"}
# signals that go to GPIO pads (the pad is chosen by cup/pinassign.py, initial order below); NFC pins B4/C5 are not used
HJ_SIGNALS = ["MOT_STBY", "STCK_MCU", "DOCKED_H", "CHG_STAT", "OC_OK", "LATCH_Q", "DOCK_N", "SUP_OK", "LED_R", "LED_G", "LED_B", "SUP_TXD", "SUP_RXD",
              "SUP_BOOT0", "SUP_NRST", "MOT_DIR", "MOT_EN_FAULT", "BTN_N", "I2C_SCL", "I2C_SDA", "ARM_CLK", "MCU_EN", "BUZ_A"]
HJ_GPIO_POOL = [k for k, v in HJ_PIN.items() if v.startswith("P") and k not in HJ_FIXED and k not in ("B4", "C5") and v != "P0.18/RESET"]
ISP = dict(HJ_FIXED)
import os as _os, json as _json
_ASSIGN = _os.path.join(HERE, "..", "cup", "pin_assign.json")
_assign = _json.load(open(_ASSIGN)) if _os.path.exists(_ASSIGN) else {sig: pad for sig, pad in zip(HJ_SIGNALS, HJ_GPIO_POOL)}
for sig, pad in _assign.items():
    ISP[pad] = sig

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
    new("U1", "HJ-840 nRF52840 SiP", ("V010", "HJ840"), dict(ISP), "C50052094", "HJ-840", group="mcu",
        note="HJSIP HJ-840 LGA64 6.2 x 7.0 x 1.0, JLC stock about 90, integrated antenna (A7 ANT -> pi match -> A8 BOARD_ANT), normal-voltage mode: VDD = VDDH = 3V3 from the LDO; DCCH, DEC1, DEC5, DECUSB not connected (module has its own filter capacitors; DC/DC off, LDO mode: VERIFY with figure 2.4 of the manual); NFC pins not used; no parts under the module, no copper in the antenna area")
    C("C1", "100nF", "3V3", "GND", "mcu")
    R("R1", "100k", "3V3", "NRST", "mcu")
    new("PI1", "pi match shunt C (DNP)", C0402, {1: "ANT_A", 2: "GND"}, "C1525", "CL05B104KO5NNNC", group="mcu", dnp=True, note="pi match shunt, value to be tuned (about 0.5 to 1 pF), DNP")
    new("PI2", "pi match series 0R", R0402, {1: "ANT_A", 2: "ANT_B"}, "C17168", "0402WGF0000TCE", group="mcu", note="series element: 0 ohm connects A7 to A8 (internal antenna)")
    new("PI3", "pi match shunt C (DNP)", C0402, {1: "ANT_B", 2: "GND"}, "C1525", "CL05B104KO5NNNC", group="mcu", dnp=True, note="pi match shunt, DNP")
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
    new("BZ1", "FUET-4020 SMD magnetic sounder", ("V010", "BZ_4020"), {1: "VBAT", 2: "PZ_A"}, "C391027", "FUET-4020", side="B", group="ui",
        note="fitted: 4 x 4 x 2.0 mm SMD magnetic sounder on the bottom side of the side_b block (2.0 mm part, 4.3 mm free below the board, 2.3 mm spare), pod position about (39.0, 20.2), z 3.3 to 5.3; driven by QBA + D6, off by default; loudness about 80 dB at 10 cm (class figure, VERIFY); alternatives MLT-5020 C94598 (5 x 5), Cy-SMD-4020-3040 C968744")
    new("D6", "1N4148W (sounder flyback)", ("Diode_SMD", "D_SOD-123"), {1: "VBAT", 2: "PZ_A"}, "C81598", "1N4148W", group="ui", note="flyback across the sounder coil (cathode pad 1 on VBAT)")
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
    # ---------------------------------------------------------------- motor supply: boost (supervisor EN) -> current-limited load switch (hardware EN) -> VMOT
    R("R82", "100k", "SUP_PERMIT", "GND", "sw")
    R("R16", "100k", "MOT_DIR", "GND", "sw")
    new("Q7", "2N7002", SOT23, {1: "DOCK_N", 2: "GND", 3: "DOCKED_H"}, "C8545", "2N7002", group="sw", note="hall inverter: DOCK_N low (hall asserted) -> DOCKED_H high (R21 pull-up)")
    new("QBA", "2N7002", SOT23, {1: "BUZ_A", 2: "GND", 3: "PZ_A"}, "C8545", "2N7002", group="ui", note="sounder drive leg (100 k pull-down RDA), off by default")
    new("U33", "TP74AUP1G32S5 (OR)", SC70_5, {1: "DOCKED_H", 2: "MOT_DIR", 3: "GND", 4: "DOCK_OR", 5: "3V3"}, "C49333203", "TP74AUP1G32S5", group="sw",
        note="DOCK_OR = DOCKED_H OR MOT_DIR[reverse]: forward undocked blocked, reverse undocked allowed (refill / draw)")
    new("U34", "TP74AUP1G08S5 (AND)", SC70_5, {1: "LATCH_Q", 2: "DOCK_OR", 3: "GND", 4: "MOT_ALLOW", 5: "3V3"}, "C48886815", "TP74AUP1G08S5", group="sw",
        note="MOT_ALLOW = LATCH_Q AND DOCK_OR: the pure-hardware cut path, drives the EN pin of the load switch")
    R("R90", "100k", "MOT_ALLOW", "GND", "sw")
    new("U20", "TPS2553DBVR", SOT236, {1: "VMOT_PRE", 2: "GND", 3: "MOT_ALLOW", 4: "OC_OK", 5: "ILIM", 6: "VMOT"}, "C55266", "TPS2553DBVR", group="sw",
        note="current-limited high-side switch 2.5-6.5 V, 85 mohm, EN active high (hardware cut), FAULT open drain = OC_OK (low when the limit is active > deglitch), NOT the -1 latch variant; pinout 1 IN 2 GND 3 EN 4 FAULT 5 ILIM 6 OUT: VERIFY")
    new("R91", "56k", R0402, {1: "ILIM", 2: "GND"}, "C25796", "0402WGF5602TCE", group="sw", note="ILIM resistor: I_OS about 23950 / R^1.0056 (kohm -> mA) = about 0.42 A typ (datasheet table, tolerance about +-10 to 15 %, VERIFY); motor needs 0.35 A")
    R("R92", "100k", "3V3", "OC_OK", "sw")
    C("C60", "100nF", "VMOT_PRE", "GND", "sw")
    R("R24", "10k", "VMOT_PRE", "GND", "sw"); R("R25", "10k", "VMOT", "GND", "sw")
    take("R57", "oc"); take("R58", "oc")
    # ---------------------------------------------------------------- 5 V boost (motor NFP-608-26.45-SGM, 4.8 V rated), EN = supervisor permission
    new("U8", "TPS61023DRLR", ("Package_TO_SOT_SMD", "SOT-563"), {1: "SUP_PERMIT", 2: "GND", 3: "BST_SW", 4: "VBAT", 5: "VMOT_PRE", 6: "BST_FB"}, "C919459", "TPS61023DRLR", group="boost",
        note="sync boost 3.7 A switch, 0.5-5.5 V in, 1 uA off, about 90 % at 0.3 A out; VIN from the cell, EN = SUP_PERMIT (supervisor second cut); pinout 1 EN 2 GND 3 SW 4 VIN 5 VOUT 6 FB: VERIFY")
    new("L1", "1uH 2520 (WPN252012E1R0MT)", ("Inductor_SMD", "L_1008_2520Metric"), {1: "VBAT", 2: "BST_SW"}, "C370610", "WPN252012E1R0MT", group="boost", note="1 uH 2.5 x 2.0 x 1.2; Isat VERIFY >= 2.5 A")
    new("R55", "220k", R0402, {1: "VMOT_PRE", 2: "BST_FB"}, "C25767", "0402WGF2203TCE", group="boost", note="FB divider 220k/30k, FB 0.595 V -> 4.96 V")
    new("R56", "30k", R0402, {1: "BST_FB", 2: "GND"}, "C25776", "0402WGF3002TCE", group="boost")
    take("DZ1", "boost", pins={"1": "VMOT_PRE", "2": "GND"})
    C0805 = ("Capacitor_SMD", "C_0805_2012Metric")
    for i in (1, 2):
        new("CB%d" % i, "22uF 6.3V X5R 0805", C0805, {1: "VMOT_PRE", 2: "GND"}, "C45783", "CL21A226MAQNNNE", group="boost",
            note="bulk on the boost output (basic part); about 8 uF effective at 5 V DC bias")
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
