#!/usr/bin/env python3
"""v0.1.0 split design v3 (decision 2026-11-19: radio = Insight ISP1807, MAIN <= 400 mm2, partition of MINIATURIZATION.md section 11).

TEST ONLY - NOT FOR HUMAN USE.  Water only.

MAIN   : ISP1807 + supervisor STM32C011F4U6 (UFQFPN-20) + AND gate + STSPIN220 + VREF + 3V3 LDO + LED + hall gating (Q7/Q7B) + spring pads
         (cell 2, motor 4) + board-to-board pads (to POWER, to SENSOR) + SWD / test pads.  0201 passives.
POWER  : (rename of USB-CHARGE) USB-C + TVS/ESD + MCP73832 + 5 V boost + clamp + shunt + INA180 + OC comparator/latch + both series P-FETs + discrete
         gate legs (MCU_EN, OC_OK, dock-xor-dir, supervisor leg QS) + bleeders + battery sense / NTC switch + piezo bridge + side tact.
SENSOR : unchanged (netlist_v2 SENSOR part list, 9-pin FFC).
Every safety element of INTERLOCK.md is kept (moved, not dropped); the truth table is unchanged.

Run: python3 netlist_v3.py -> ../netlist_v3_{main,power,sensor}.json, ../netlist_v3_cross.json, ERC summary (per board + union).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import netlist as nl
import netlist_v2 as v2
from netlist import R0402, R0603, C0402, C0603, SOT23, SOT235, SOT236, SOD123

OUT = os.path.join(HERE, "..")
R0201, C0201 = ("Resistor_SMD", "R_0201_0603Metric"), ("Capacitor_SMD", "C_0201_0603Metric")
SC70_5 = ("Package_TO_SOT_SMD", "SOT-353_SC-70-5")

R201 = {"100k": ("C106224", "RC0201FR-07100KL"), "10k": ("C106225", "RC0201FR-0710KL"), "4.7k": ("C138135", "RC0201FR-074K7L"),
        "5.1k": ("C143995", "AF0201FR-075K1L"), "1k": ("C138165", "RC0201FR-071KL"), "100R": ("C77623", "RC0201FR-07100RL"),
        "47k": ("C138139", "RC0201FR-0747KL"), "3.3k": ("C270350", "0201WMF3301TEE"), "1M": ("C102686", "RTT011004FTH"),
        "4.7M": ("C423341", "0201WMJ0475TEE"), "22R": ("C142011", "RC0201JR-0722RL"), "0R": ("C106228", "RC0201JR-070RL")}
C201 = {"100nF": ("C66938", "0201X104K6R3NT"), "1uF": ("C53067", "CL03A105MQ3CSNH"), "10nF": ("C76940", "GRM033R70J103KA01D"),
        "4.7uF": ("C335103", "GRM035R60J475ME15D"), "15pF": ("C64554", "0201CG150J500NT")}

B2B_A = ["GND", "VBAT", "VBAT", "GND", "VMOT", "VMOT", "GND", "3V3", "VBUS_P", "USB_DP", "USB_DM", "CHG_STAT", "VBUS_SENSE", "VBAT_SENSE", "NTC", "SENSE_EN"]
B2B_B = ["GND", "VMOT_SENSE", "I_SENSE", "MCU_EN", "MOT_DIR", "DIR_REV", "DOCKED_H", "DOCK_TEST", "SUP_PERMIT", "OC_OK", "OC_TEST", "PGATE_MON", "BTN_N", "BUZ_A", "BUZ_B", "GND"]
B2B = {str(i + 1): n for i, n in enumerate(B2B_A + B2B_B)}
SENSOR_PINS = {1: "GND", 2: "3V3", 3: "I2C_SDA", 4: "I2C_SCL", 5: "DOCK_N", 6: "DOCK_NB", 7: "TMAG_INT", 8: "GND", 9: "GND"}

# ISP1807 pad -> net (local pad numbers of OpenPatch ISP1807 footprint; see pad table in ISP-PINMAP in FIRMWARE-PINMAP.md)
ISP_PADS = {
    # supplies / USB / reset / SWD / RF bridge
    26: "3V3", 12: "VBUS_P", 8: "USB_DP", 10: "USB_DM", 13: "NRST", 28: "SWDIO", 30: "SWDCLK", 20: "RF_BRIDGE", 22: "RF_BRIDGE",
    1: "GND", 7: "GND", 25: "GND", 31: "GND", 14: "GND", 16: "GND", 18: "GND", 21: "GND", 23: "GND", 24: "GND",
    # outer ring GPIO
    32: "MOT_STBY", 34: "STCK_MCU", 36: "VBAT_SENSE", 38: "I_SENSE", 40: "VMOT_SENSE", 42: "NTC", 44: "DOCKED_H", 46: "VBUS_SENSE", 48: "CHG_STAT",
    2: "OC_OK", 4: "PGATE_MON", 6: "TMAG_INT",
    # second row (via-in-pad)
    33: "MOT_DIR", 35: "MOT_EN_FAULT", 37: "BTN_N", 39: "I2C_SCL", 41: "I2C_SDA", 43: "ARM_CLK", 45: "MCU_EN", 47: "SENSE_EN",
    3: "DOCK_N", 5: "SUP_OK", 27: "SUP_TXD", 29: "SUP_RXD", 49: "OC_TEST", 50: "DOCK_TEST", 51: "BUZ_A", 52: "BUZ_B", 53: "LED_ST",
}


def to201(p):
    """convert an 0402 passive of the monolith to 0201 (MAIN only)"""
    v = p["value"]
    if tuple(p["fp"]) == R0402 and v in R201:
        p["fp"] = list(R0201); p["lcsc"], p["mpn"] = R201[v]
    elif tuple(p["fp"]) == C0402 and v in C201:
        p["fp"] = list(C0201); p["lcsc"], p["mpn"] = C201[v]
    return p


def build():
    base = nl.build()
    P = {p["ref"]: p for p in base}
    main, power = [], []

    def take(ref, board, **kw):
        p = dict(P[ref]); p.update(kw); p["pins"] = dict(p["pins"]); p["board"] = board
        (main if board == "MAIN" else power).append(p)
        return p

    def new(board, ref, value, fp, pins, lcsc=None, mpn=None, side="F", bom=True, note="", group="", dnp=False):
        p = dict(ref=ref, value=value, fp=list(fp), pins={str(k): v for k, v in pins.items()}, lcsc=lcsc, mpn=mpn, side=side, bom=bom and not dnp, dnp=dnp, note=note, group=group, board=board)
        (main if board == "MAIN" else power).append(p)
        return p

    def R(board, ref, val, a, b, group="", fp=None, **kw):
        if board == "MAIN":
            new(board, ref, val, R0201, {1: a, 2: b}, R201[val][0], R201[val][1], group=group, **kw)
        else:
            new(board, ref, val, R0402, {1: a, 2: b}, nl.RV[val][0], nl.RV[val][1], group=group, **kw)

    def C(board, ref, val, a, b, group="", **kw):
        if board == "MAIN":
            new(board, ref, val, C0201, {1: a, 2: b}, C201[val][0], C201[val][1], group=group, **kw)
        else:
            new(board, ref, val, C0402, {1: a, 2: b}, nl.CV[val][0], nl.CV[val][1], group=group, **kw)

    def NM(board, ref, g, s, d, group="", note=""):
        new(board, ref, "2N7002", SOT23, {1: g, 2: s, 3: d}, "C8545", "2N7002", group=group, note=note)

    # =========================================================================================== MAIN
    new("MAIN", "U1", "ISP1807-LR (consigned)", ("V010", "ISP1807"), {str(k): v for k, v in ISP_PADS.items()}, None, "ISP1807-LR", side="F", group="mcu",
        note="Insight SiP nRF52840 module 8x8x1.0, integrated antenna (pads 20/22 bridged), CONSIGNED: not in the JLC library; internal 32.768 kHz crystal. NFC pins P0.09/P0.10 used as GPIO: UICR NFCPINS=1. Antenna half (local +Y) toward the board edge")
    C("MAIN", "C1", "100nF", "3V3", "GND", "mcu"); C("MAIN", "C2", "4.7uF", "3V3", "GND", "mcu")
    R("MAIN", "R1", "100k", "3V3", "NRST", "mcu")
    for ref, net in (("SP1", "VBAT"), ("SP2", "GND")):
        take(ref, "MAIN")
    for i, (net) in enumerate(("MOT_B2", "MOT_A2", "MOT_B1", "MOT_A1")):
        new("MAIN", "MP%d" % (i + 1), "BWCD-L3.5W2.0H1.0 motor pad", ("V010", "Spring_Contact_3.5x2.0"), {1: net}, "C2826547", "BWCD-L3.5W2.0H1.0", side="B", group="mot",
            note="replaces the PicoBlade J1 (pin %d): motor lead pad, spring contact on the motor flex; VERIFY geometry" % (i + 1))
    for ref in ("U2", "C6", "C7"):
        take(ref, "MAIN")
    for ref in ("R1",):
        pass
    # STSPIN220 + VREF + bulk (motor, local to the driver)
    u7 = take("U7", "MAIN"); u7["pins"]["15"] = "GND"; u7["pins"]["16"] = "GND"
    u7["note"] = "MODE1/MODE2 hard-wired to GND (full step), the 10 k resistors R41/R42 are dropped (area)"
    for ref in ("R34", "R35"):
        take(ref, "MAIN")
    for ref in ("R36", "R37", "R38", "C19", "R39", "R40", "C20", "C23", "R43"):
        to201(take(ref, "MAIN"))
    take("C21", "MAIN"); take("C22", "MAIN")
    for p in main:
        if p["ref"] == "C21":
            p.update(value="22uF", fp=list(C0603), lcsc="C380323", mpn="TCC0603X5R226M6R3CT")
    # hall gating: DOCKED_H = both halls asserted (2oo2)
    NM("MAIN", "Q7", "DOCK_N", "GND", "DOCKED_H", "dock"); NM("MAIN", "Q7B", "DOCK_NB", "GND", "DOCKED_H", "dock")
    R("MAIN", "R19", "4.7M", "3V3", "DOCK_N", "dock"); R("MAIN", "R20", "4.7M", "3V3", "DOCK_NB", "dock"); R("MAIN", "R21", "100k", "3V3", "DOCKED_H", "dock")
    # LED, I2C pull-ups, button pull-up
    for ref in ("LD1", "R74", "R75", "R67", "R68", "R73"):
        to201(take(ref, "MAIN"))
    # supervisor MCU (UFQFPN-20) + AND gate
    new("MAIN", "U30", "STM32C011F4U6", ("V010", "UFQFPN-20_3x3_P0.5"),
        {1: "MCU_EN", 4: "3V3", 5: "GND", 6: "SUP_NRST", 7: "ARM_CLK", 8: "STCK_MCU", 9: "DIR_REV", 10: "OC_OK", 11: "SUP_STCK_EN", 12: "SUP_PERMIT",
         13: "SUP_OK", 14: "NRST", 16: "SUP_TXD", 17: "SUP_RXD", 18: "SUP_SWDIO", 19: "SUP_SWDCLK", 20: "DOCKED_H", 21: "GND"}, "C5456188", "STM32C011F4U6", group="sup",
        note="independent supervisor (INTERLOCK.md section H); UFQFPN-20 pin map assumed equal to the TSSOP-20 map of netlist_v2 (G0/C0 family keeps numbering): VERIFY against DS13866 before ordering. EP = VSS")
    C("MAIN", "C50", "100nF", "3V3", "GND", "sup"); C("MAIN", "C51", "1uF", "3V3", "GND", "sup")
    R("MAIN", "R80", "100k", "SUP_NRST", "3V3", "sup"); R("MAIN", "R81", "100k", "SUP_STCK_EN", "GND", "sup")
    new("MAIN", "U31", "SN74AUP1G08DCKR", SC70_5, {1: "STCK_MCU", 2: "SUP_STCK_EN", 3: "GND", 4: "STCK_DRV", 5: "3V3"}, "C507223", "SN74AUP1G08DCKR", group="sup",
        note="STCK_DRV = STCK_MCU AND SUP_STCK_EN (SC-70-5 TI part, same pinout as the clone)")
    C("MAIN", "C52", "100nF", "3V3", "GND", "sup")
    # driver STCK pin: net STCK_DRV (in nl: STCK_DRV already)
    # connectors / pads
    new("MAIN", "J7", "board-to-board pads to POWER (2 x 16)", ("V010", "B2B_Pads_2x16_P0.8_M"), B2B, bom=False, side="B", group="b2b",
        note="bare ENIG pad rows for an elastomeric strip / spring contacts; POWER carries the mirror pattern")
    new("MAIN", "J3", "SENSOR link pads (9)", ("V010", "SENSOR_Pads_9_P0.8"), SENSOR_PINS, bom=False, side="B", group="b2b",
        note="bare pads for the SENSOR FFC (hot-bar/ACF or elastomer); SENSOR keeps its FH12-10S J3S: mating method is OPEN (no <= 1 mm ZIF verified)")
    swd = [("SWDIO", "SWDIO"), ("SWDCLK", "SWDCLK"), ("NRST", "NRST"), ("GND", "GND"), ("SUP_SWDIO", "SUP_SWDIO"), ("SUP_SWDCLK", "SUP_SWDCLK"), ("SUP_NRST", "SUP_NRST")]
    for i, (v, n) in enumerate(swd):
        new("MAIN", "J%d" % (10 + i), "SWD pad " + v, ("V010", "TP_Pad_D0.8"), {1: n}, bom=False, group="swd", note="SWD pad (spring probe jig)")
    tps = ["3V3", "VMOT", "STCK_DRV", "SUP_STCK_EN", "SUP_OK", "SUP_TXD", "SUP_RXD", "ARM_CLK", "MOT_EN_FAULT", "I2C_SDA", "I2C_SCL", "GND"]
    for i, n in enumerate(tps):
        new("MAIN", "TP%d" % (i + 1), n, ("V010", "TP_Pad_D0.8"), {1: n}, bom=False, group="tp", note="test pad")

    # =========================================================================================== POWER
    for ref in ("C5", "D4", "C8", "U3", "R2", "R3", "R4", "C9", "Q1", "Q2", "R5", "R6", "R7", "C10", "R8", "RT1",
                "Q4", "Q15", "R9", "R10", "C11", "R11", "Q8", "Q13", "Q6", "Q21", "Q10", "Q22", "Q20", "R87", "Q11", "R12", "R13", "R14", "R15", "R16", "R18", "Q16", "Q17", "R24", "R25",
                "Q12", "R22",
                "R44", "C24", "U9", "C25", "R46", "R47", "C26", "R48", "C27", "U11", "C28", "R49", "R50", "R51", "Q14", "R52", "R53", "U12", "C29", "R54", "C30", "D5",
                "R57", "R58", "C32", "SW1", "C42", "R62", "R63"):
        take(ref, "POWER")
    pw = {p["ref"]: p for p in power}
    pw["R2"]["pins"]["1"] = "VBUS_P"
    pw["Q8"]["pins"]["3"] = "CH_TOP"           # latch leg Q5 is gone (supervisor MCU), chain PGATE-R11-Q8-Q13-(Q6|Q10)
    # second series switch owned by the supervisor through QS (PGATE2)
    pw["Q15"]["pins"]["1"] = "PGATE2"
    pw["Q15"]["note"] = "second series switch, gate owned by the supervisor MCU through QS"
    R("POWER", "R83", "100k", "VMOT_A", "PGATE2", "sw"); new("POWER", "C60", "100nF", C0402, {1: "PGATE2", 2: "VMOT_A"}, "C1525", "CL05B104KO5NNNC", group="sw")
    NM("POWER", "QS", "SUP_PERMIT", "GND", "QS_D", "sw", "supervisor leg: pulls PGATE2 low only while SUP_PERMIT is high"); R("POWER", "R84", "10k", "PGATE2", "QS_D", "sw")
    R("POWER", "R82", "100k", "SUP_PERMIT", "GND", "sw")
    NM("POWER", "Q17B", "PGATE2", "GND", "BLD", "sw", "bleeder also when only the supervisor has cut")
    pw["Q17"]["note"] = "turns on when PGATE is high = supply off"
    # PGATE_MON readback (Q16) is part of the monolith list: add it (not in the take-list above)
    # direction legs: DIR_REV = MOT_DIR (R13) , MOT_DIR pulled down on MAIN side via R16 -> POWER keeps it
    # boost 5 V populated (as v2)
    for ref in ("U8", "L1", "D6", "R55", "R56", "C31"):
        p = take(ref, "POWER"); p["dnp"] = False; p["bom"] = True; p["side"] = "F"
    pw = {p["ref"]: p for p in power}
    pw["L1"].update(value="CKCS4018-4.7uH", lcsc="C354574", mpn="CKCS4018-4.7uH/M", note="boost inductor 4.7 uH 4x4x1.8, Isat to be checked >= 1.5 A (VERIFY)")
    pw["R55"].update(value="220k", lcsc="C25767", mpn="0402WGF2203TCE"); pw["R56"].update(value="30k", lcsc="C25776", mpn="0402WGF3002TCE")
    pw["U8"]["note"] = "MT3608 5 V boost (EN tied to switched VMOT_RAW); VERIFY stability/efficiency; 3 V motor option: depopulate, fit R45"
    pw["C31"].update(value="10uF")
    new("POWER", "R45", "0R DNP (boost bypass)", R0603, {1: "VMOT_RAW", 2: "VMOT_PRE"}, "C21189", "0603WAF0000T5E", group="oc", dnp=True, note="fit instead of the boost for a 3 V motor (spec 4b)")
    new("POWER", "DZ1", "BZT52C6V2 (VMOT overvoltage clamp)", SOD123, {1: "VMOT_PRE", 2: "GND"}, "C27091", "LBZT52C6V2T1G", group="oc", note="clamps a boost overvoltage; cathode (pad 1) to VMOT_PRE")
    # VBUS sense
    R("POWER", "R85", "100k", "VBUS_P", "VBUS_SENSE", "pwr"); R("POWER", "R86", "100k", "VBUS_SENSE", "GND", "pwr")
    # piezo bridge (2 NFETs + 2 pull-ups), 2 spring pads for the piezo disc glued to the lid
    for s in "AB":
        NM("POWER", "QB" + s, "BZ_G" + s, "GND", "PZ_" + s, "ui", "piezo bridge leg " + s)
        R("POWER", "RB" + s, "1k", "VBAT", "PZ_" + s, "ui"); R("POWER", "RG" + s, "100R", "BUZ_" + s, "BZ_G" + s, "ui"); R("POWER", "RD" + s, "100k", "BZ_G" + s, "GND", "ui")
        new("POWER", "PZ" + ("1" if s == "A" else "2"), "piezo spring pad " + s, ("V010", "Spring_Contact_3.5x2.0"), {1: "PZ_" + s}, "C2826547", "BWCD-L3.5W2.0H1.0", side="B", group="ui",
            note="spring pad to the piezo disc (9 x 9, C910763) glued to the lid")
    # button, decoupling of the button on POWER
    pw["SW1"]["note"] = "PROXY: XKB TS-1187A (5.1 mm). A side-actuated tact <= 1.0 mm high must be selected (none verified at JLC); footprint to be replaced"
    # USB-C block (from netlist_v2 usb)
    _m, _s, usb = v2.build()
    for u in usb:
        if u["ref"] == "J3U":
            continue
        q = dict(u); q["board"] = "POWER"
        q["pins"] = {k: {"UDP_C": "USB_DP", "UDM_C": "USB_DM"}.get(v, v) for k, v in q["pins"].items()}
        power.append(q)
    pw = {p["ref"]: p for p in power}
    # board-to-board pad row + test pads
    new("POWER", "J7P", "board-to-board pads to MAIN (2 x 16)", ("V010", "B2B_Pads_2x16_P0.8"), B2B, bom=False, group="b2b", note="mirror of MAIN J7")
    tp = ["GND", "VBAT", "VMOT", "VMOT_RAW", "VMOT_PRE", "PGATE", "PGATE2", "INA_OUT", "OC_CMP", "CH_TOP", "PG_MID2", "VCHG"]
    for i, n in enumerate(tp):
        new("POWER", "TP%d" % (i + 1), n, nl.TP, {1: n}, bom=False, group="tp", note="test pad")
    for i in range(3):
        new("POWER", "H%d" % (i + 1), "NPTH 1.2", ("Bench", "NPTH_1.2mm"), {}, bom=False, group="mech")

    # dual NFET packages (2N7002DW-7-F, SOT-363) on POWER: no package holds two legs of the same series chain (common-cause)
    SOT363 = ("Package_TO_SOT_SMD", "SOT-363_SC-70-6")
    pairs = [("Q8", "Q16"), ("Q13", "Q17"), ("Q6", "Q20"), ("Q21", "Q14"), ("Q10", "Q12"), ("Q22", "Q2"), ("QS", "QBA"), ("Q17B", "QBB")]
    byref = {p["ref"]: p for p in power}
    for k, (ra, rb) in enumerate(pairs):
        a, b2 = byref[ra], byref[rb]
        pins = {"2": a["pins"]["1"], "1": a["pins"]["2"], "6": a["pins"]["3"], "5": b2["pins"]["1"], "4": b2["pins"]["2"], "3": b2["pins"]["3"]}
        new("POWER", "QD%d" % (k + 1), "2N7002DW (%s + %s)" % (ra, rb), SOT363, pins, "C83571", "2N7002DW-7-F", group=a["group"],
            note="dual N-FET replacing %s (S1 G2 D6) and %s (S4 G5 D3): %s | %s" % (ra, rb, a.get("note", ""), b2.get("note", "")))
    power[:] = [p for p in power if p["ref"] not in {x for pr in pairs for x in pr}]
    for p in power + main:
        to201(p)
    # =========================================================================================== SENSOR (unchanged)
    sens = [dict(p, board="SENSOR", group="sensor") for p in v2.build()[1]]
    return main, power, sens


def nets_of(parts):
    nets = {}
    for p in parts:
        for pad, n in p["pins"].items():
            if n:
                nets.setdefault(n, []).append((p["ref"], pad))
    return nets


def erc(main, power, sens):
    bad = []
    nm, np_, ns = nets_of(main), nets_of(power), nets_of(sens)
    B2BREF = ("J7", "J7P")
    for name, n in (("MAIN", nm), ("POWER", np_), ("SENSOR", ns)):
        for net, l in sorted(n.items()):
            if len(l) < 2 and not net.startswith(("SUP_SWD", "OC_TRIP")):
                bad.append("%s: single-pin net %s %s" % (name, net, l))
    cross = sorted(set(nm) & set(np_))
    # union check: a cross net must be on the b2b pads of both boards, non-b2b pin count >= 2 across the union
    for net in cross:
        for n in (nm, np_):
            if not any(r in B2BREF for r, _ in n[net]):
                bad.append("cross net %s has no b2b pad on one board" % net)
    for net in sorted(set(nm) | set(np_)):
        cnt = sum(1 for n in (nm, np_) for r, _ in n.get(net, []) if r not in B2BREF)
        if cnt < 2 and not net.startswith(("SUP_SWD", "SWD", "OC_TRIP")):
            bad.append("union: net %s has %d non-connector pins" % (net, cnt))
    # sensor link
    for net in set(nm) & set(ns):
        pass
    sensor_nets = set(ns)
    for k, v in SENSOR_PINS.items():
        if v not in nm:
            bad.append("sensor net %s missing on MAIN" % v)
    return cross, bad


if __name__ == "__main__":
    main, power, sens = build()
    cross, bad = erc(main, power, sens)
    for name, parts in (("main", main), ("power", power), ("sensor", sens)):
        json.dump(parts, open(os.path.join(OUT, "netlist_v3_%s.json" % name), "w"), indent=1)
        print(name, len(parts), "parts", len(nets_of(parts)), "nets", "BOM lines", len(set((p["value"], tuple(p["fp"])) for p in parts if p["bom"])), "BOM parts", sum(1 for p in parts if p["bom"]))
    json.dump(dict(b2b_pads=B2B, cross_nets=cross, sensor_link=SENSOR_PINS), open(os.path.join(OUT, "netlist_v3_cross.json"), "w"), indent=1)
    print("cross nets (MAIN-POWER):", len(cross), cross)
    print("b2b pads", len(B2B), "(unique nets %d)" % len(set(B2B.values())))
    for b in bad:
        print("ERC:", b)
    print("ERC problems:", len(bad))
