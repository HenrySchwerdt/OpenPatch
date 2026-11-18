#!/usr/bin/env python3
"""Fab netlist: SKiDL netlist.json + datasheet-verified pad mapping + ECOs.

Why: the SKiDL netlist used pin NAMES as pin numbers for every IC except the ISP1807, and it
missed pins that the datasheets require. This module (1) maps names to real package pads
(checked against the TI/ST/Insight datasheets in ../datasheets), (2) applies the ECOs listed
in ECO below, (3) emits a plain dict used by build_board.py and the BOM/CPL exporters.
"""
from __future__ import annotations

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "netlist.json")
KL = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"

# name -> pad(s) per datasheet package pin tables
PADMAP = {
    "U2": {  # BQ51013B RHL VQFN-20 (replaces BQ51003 YFP, same pin functions)
        "AC1": 2, "AC2": 19, "AD": 9, "AD_EN": 8, "BOOT1": 3, "BOOT2": 17, "CHG": 7,
        "CLAMP1": 5, "CLAMP2": 16, "COM1": 6, "COM2": 15, "EN1": 10, "EN2": 11, "FOD": 14,
        "ILIM": 12, "OUT": 4, "PGND1": 1, "PGND2": 20, "RECT": 18, "TS_CTRL": 13, "EP": 21},
    "U4": {  # STSPIN220 VFQFPN-16 (DS11633 Table 6)
        "DIR_MODE4": 1, "STCK_MODE3": 2, "OUT1A": 3, "SENSEA": 4, "OUT1B": 5, "VS": 6, "GND": 7,
        "OUT2B": 8, "SENSEB": 9, "OUT2A": 10, "REF": 11, "TOFF": 12, "EN_FAULT": 13,
        "STBY_RESET": 14, "MODE2": 15, "MODE1": 16, "EP": 17},
    "U5": {"VDD": 1, "GND": 2, "DELAY": 3, "DONE": 4, "WAKE": 5, "RSTN": 6},  # TPL5010 DDC
    "U6": {"CLK": 1, "D": 2, "Q_N": 3, "GND": 4, "Q": 5, "CLR_N": 6, "PRE_N": 7, "VCC": 8},  # 74AUP1G74 DQE/DCU
    "U8": {"SCL": 1, "GND": 2, "GND_TEST": 3, "VCC": 4, "INT": 5, "SDA": 6},  # TMAG5273 DBV
    "U9": {"VCC": 1, "GND": 2, "NC": 3, "OUT": 4, "EP": 5},  # DRV5032 DMR X2SON-4
    "U10": {"VCC": 1, "GND": 2, "NC": 3, "OUT": 4, "EP": 5},
    "U13": {"VCC": 1, "GND": 2, "NC": 3, "OUT": 4, "EP": 5},  # dock hall (new)
    "U3": {"STAT": 1, "VSS": 2, "VBAT": 3, "VDD": 4, "PROG": 5},  # MCP73832 SOT-23-5
    "U12": {"VSS": 1, "VOUT": 2, "VIN": 3},  # XC6206 SOT-23 (Torex pin table)
    "D1": {"K": 1, "A": 2}, "D2": {"K": 1, "A": 2},
}
FETMAP = {"G": 1, "S": 2, "D": 3}

FP = {  # ref-prefix/ref -> (library path or None for lib in OpenPatch.pretty, footprint name)
    "R": ("Resistor_SMD", "R_0402_1005Metric"),
    "C0402": ("Capacitor_SMD", "C_0402_1005Metric"),
    "C0603": ("Capacitor_SMD", "C_0603_1608Metric"),
    "C1206": ("Capacitor_SMD", "C_1206_3216Metric"),
    "U1": ("OpenPatch", "ISP1807"),
    "U2": ("Package_DFN_QFN", "Texas_VQFN-RHL-20"),
    "U3": ("Package_TO_SOT_SMD", "SOT-23-5"),
    "U4": ("Package_DFN_QFN", "QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm"),
    "U5": ("Package_TO_SOT_SMD", "SOT-23-6"),
    "U6": ("Package_SON", "X2SON-8_1.4x1mm_P0.35mm"),
    "U8": ("Package_TO_SOT_SMD", "SOT-23-6"),
    "U9": ("Package_SON", "Texas_X2SON-4-1EP_1.1x1.4mm_P0.5mm_EP0.8x0.6mm"),
    "U10": ("Package_SON", "Texas_X2SON-4-1EP_1.1x1.4mm_P0.5mm_EP0.8x0.6mm"),
    "U13": ("Package_SON", "Texas_X2SON-4-1EP_1.1x1.4mm_P0.5mm_EP0.8x0.6mm"),
    "U12": ("Package_TO_SOT_SMD", "SOT-23"),
    "Q": ("Package_TO_SOT_SMD", "SOT-23"),
    "Q2": ("Package_TO_SOT_SMD", "SOT-323_SC-70"),
    "D1": ("Diode_SMD", "D_0402_1005Metric"),
    "D2": ("Diode_SMD", "D_SOD-523"),
    "SW1": ("Button_Switch_SMD", "SW_SPST_B3U-1000P"),
    "J1": ("Connector", "Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical"),
    "TP": ("TestPoint", "TestPoint_Pad_D1.0mm"),
    "BT1": ("OpenPatch", "Contact_Pads_Battery_2x_1.5x1.2"),
    "LRX1": ("OpenPatch", "Contact_Pads_Coil_2x_1.5x1.2"),
    "MP1": ("OpenPatch", "Hirose_FH12-4S-0.5SH_derived"),
}

REMOVE = {"R90", "U3", "L4", "U7", "U11", "Q3", "R41", "R42", "C44", "R30", "R32", "R33", "R34",
          "BZ1", "Q1", "R80", "R81"}
RENAME_NET = {"BQ_INT": "CHG_STAT", "VPER_3V3": "3V3"}
DROP_NETS = {"BQ_CD", "BQ_MR", "BQ_SW", "BQ_TS", "PER_EN", "BUZ_DRAIN", "BUZ_GATE", "BUZ_PWM",
             "PCM_CS", "PCM_MID", "PCM_OC", "PCM_OD", "PCM_VCC"}

# value changes: ref -> (value, note)
VALUES = {
    "R50": ("6.8k", "TPL5010 2 s interval: REXT=6.788k (DS Table 3) -> 6.8k 1%"),
    "R68": ("100k", "STSPIN220 REF divider: VREF = 3.3*R69/(R68+R69) = 0.105 V (range 0.1-0.5 V)"),
    "R69": ("3.3k", "see R68"),
    "R20": ("3.16k", "BQ51013B RILIM"),
}

ECO = [
    "U2 BQ51003YFP (DSBGA-28, 0.4 mm pitch) -> BQ51013BRHLR (VQFN-20 4.5x3.5, same pin functions): no via-in-pad, assemblable on JLC.",
    "U2 AD pin -> GND and AD_EN left floating (SKiDL had AD_EN=GND, AD=NC: datasheet says AD tied to PGND if unused, AD-EN is a push-pull output, float).",
    "U3 BQ25120AYFP (DSBGA-25, 0.4 mm) removed -> MCP73832T-2ACI/OT (SOT-23-5) charger, PROG=47k (~21 mA) + U12 XC6206P332MR 3.3 V LDO (VIN=VBAT). Loses I2C charger/VBAT monitor/LS-LDO/MR. PER_EN pin unused; BQ_INT net renamed CHG_STAT (STAT open drain).",
    "U7 TPS22916 (DSBGA-4) removed -> discrete high-side switch Q4 AO3401A + Q5/Q6 2N7002 series gate pull-down: VMOT on only if MOT_ALLOW AND DOCKED (new interlock). R92 gate pull-up (fail-safe off).",
    "NEW dock hall U13 DRV5032FA + inverter Q7 + R93/R96 (fail-safe: no signal = not docked) ; DOCK_N routed to ISP1807 pad 38 (P0.03).",
    "U4 STSPIN220: added SENSEA/SENSEB sense resistors (1.0 ohm, R97/R98) and TOFF resistor R99=47k to GND (all required by datasheet, missing in SKiDL netlist); REF divider R68/R69 set for VREF=0.105 V (Ipk ~ 105 mA, verify against motor).",
    "U8 TMAG5273 pin 3 'GND (TEST)' must be tied to GND (SKiDL had it NC).",
    "R50 TPL5010 DELAY resistor 6.8k -> 2 s watchdog interval (MCUboot); DS Table 3: 6.788k.",
    "Removed: 9x9 piezo BZ1, Q1, R80, R81 (bench sample, no buzzer); DW01A/FS8205A PCM option (U11,Q3,R41,R42,C44); BQ25120A TS/MR/CD pulls (R30,R32,R33,R34); L4.",
    "BT1 -> 2 spring-contact lands at layout.json contacts.battery_tabs; MP1 -> FH12-4S FPC connector (bottom); LRX1 -> 2 coil spring-contact lands (provisional).",
    "VPER_3V3 merged into 3V3 (no BQ25120A load switch; halls are ultra-low-power).",
    "U6 SN74AUP1G74DQER X2SON-8 (LCSC C2677745) kept.",
    "R90 0-ohm OUT_MOD-OUT_ANT bridge replaced by a direct copper bridge between ISP1807 pads 20 and 22 (datasheet 3: 'should be connected to pin 22 for normal operation').",
]

NEW_COMPS = {  # ref: (value, kind, pins{padname: net})
    "U3": ("MCP73832T-2ACI/OT", "ic", {"STAT": "CHG_STAT", "VSS": "GND", "VBAT": "VBAT", "VDD": "VQI_5V", "PROG": "CHG_PROG"}),
    "R91": ("47k", "r", {"1": "CHG_PROG", "2": "GND"}),
    "U12": ("XC6206P332MR-G", "ic", {"VSS": "GND", "VOUT": "3V3", "VIN": "VBAT"}),
    "C80": ("1uF", "c", {"1": "VBAT", "2": "GND"}),  # LDO input cap (MCP73832 VBAT / LDO VIN)
    "Q4": ("AO3401A", "fet", {"G": "PGATE", "S": "VBAT", "D": "VMOT"}),
    "Q5": ("2N7002", "fet", {"G": "MOT_ALLOW", "S": "PG_MID", "D": "PGATE"}),
    "Q6": ("2N7002", "fet", {"G": "DOCKED_H", "S": "GND", "D": "PG_MID"}),
    "Q7": ("2N7002", "fet", {"G": "DOCK_N", "S": "GND", "D": "DOCKED_H"}),
    "R92": ("100k", "r", {"1": "VBAT", "2": "PGATE"}),
    "R93": ("100k", "r", {"1": "3V3", "2": "DOCKED_H"}),
    "R96": ("100k", "r", {"1": "3V3", "2": "DOCK_N"}),
    "R94": ("100k", "r", {"1": "VMOT", "2": "GND"}),
    "U13": ("DRV5032FADMRR", "ic", {"VCC": "3V3", "GND": "GND", "NC": "GND", "OUT": "DOCK_N", "EP": "GND"}),
    "C81": ("100nF", "c", {"1": "3V3", "2": "GND"}),
    "R97": ("1R0", "r", {"1": "SNSA", "2": "GND"}),
    "R98": ("1R0", "r", {"1": "SNSB", "2": "GND"}),
    "R99": ("47k", "r", {"1": "TOFF", "2": "GND"}),
}
# extra pad connections for existing ICs
EXTRA = {
    "U4": {"SENSEA": "SNSA", "SENSEB": "SNSB", "TOFF": "TOFF", "EP": "GND"},
    "U8": {"GND_TEST": "GND"},
    "U9": {"EP": "GND"}, "U10": {"EP": "GND"},
    "U2": {"EP": "GND"},
}
FORCE = {  # (ref, pin) -> net override
    ("U2", "AD"): "GND", ("U2", "AD_EN"): None,
    ("U1", "19"): None,  # PER_EN
    ("U1", "38"): "DOCK_N",
    ("U1", "47"): None,  # BUZ_PWM
    ("U1", "20"): "RF_LINK", ("U1", "22"): "RF_LINK",
}


def fp_for(ref: str, value: str, orig_fp: str) -> tuple[str, str]:
    if ref in FP:
        return FP[ref]
    m = re.match(r"[A-Z]+", ref).group(0)
    if m == "R":
        return FP["R"]
    if m == "C":
        if "0805" in orig_fp:
            return FP["C1206"]
        return FP["C0603"] if "0603" in orig_fp else FP["C0402"]
    if m in ("Q", "TP"):
        return FP[m]
    raise KeyError(ref)


LEAN_REMOVE = {"R62", "R63", "R64", "R65", "R66", "R67", "R70", "R71", "C62", "C70", "C71", "C72"}
LEAN_MERGE = {"MOT_STCK_DRV": "MOT_STCK", "MOT_DIR_DRV": "MOT_DIR", "MOT_MODE1_DRV": "MOT_MODE1",
              "MOT_MODE2_DRV": "MOT_MODE2", "MOT_STBY_DRV": "MOT_STBY", "MOT_EN_FAULT_DRV": "MOT_EN_FAULT"}
ECO.append("LEAN (needed to fit the 17.1x29 mm outline): removed 10k series resistors R62-R67 on STSPIN220 logic lines (MCU pins drive the driver directly; MOT_STBY keeps pulldown R72), removed VMOT_SENSE divider R70/R71/C62 (VMOT rail check lost) and hall decoupling C70-C72 (C43 + C81 remain).")


def build(lean: bool = True) -> dict:
    d = json.load(open(SRC))
    if lean:
        d["components"] = {r: c for r, c in d["components"].items() if r not in LEAN_REMOVE}
        merged = {}
        for n, ps in d["nets"].items():
            if n != "VMOT_SENSE":
                merged.setdefault(LEAN_MERGE.get(n, n), []).extend(ps)
        d["nets"] = merged
        d["nets"]["__NOCONNECT"] = d["nets"].get("__NOCONNECT", []) + ["U1.35(P0.04/AIN2)"]
    comps = {}
    for ref, c in d["components"].items():
        if ref in REMOVE or ref == "R90" and False:
            continue
        lib, name = fp_for(ref, c["value"], c["footprint"])
        comps[ref] = {"value": c["value"], "lib": lib, "fp": name, "pads": {}, "src": "skidl"}
    # nets
    for net, pins in d["nets"].items():
        if net == "__NOCONNECT" or net in DROP_NETS:
            continue
        net = RENAME_NET.get(net, net)
        for p in pins:
            ref, pin = p.split(".", 1)
            pin = re.sub(r"\(.*\)$", "", pin) if not ref == "U1" else re.match(r"\d+", pin).group(0)
            if ref not in comps:
                continue
            comps[ref]["pads"][pin] = net
    for ref, c in comps.items():
        if ref in PADMAP:
            c["pads"] = {str(PADMAP[ref][k]): v for k, v in c["pads"].items() if k in PADMAP[ref]}
        elif ref.startswith("Q"):
            c["pads"] = {str(FETMAP[k]): v for k, v in c["pads"].items()}
        elif ref == "MP1":
            c["pads"] = {{"A1": "1", "A2": "2", "B1": "3", "B2": "4"}[k]: v for k, v in c["pads"].items()}
        elif ref == "BT1":
            c["pads"] = {"1": c["pads"]["PLUS"], "2": c["pads"]["MINUS"]} if "PLUS" in c["pads"] else c["pads"]
    # ECO new components
    for ref, (val, kind, pins) in NEW_COMPS.items():
        if ref in comps and ref != "U3":
            raise SystemExit(f"duplicate {ref}")
        if kind == "r":
            lib, name = FP["R"]; pads = pins
        elif kind == "c":
            lib, name = FP["C0402"]; pads = pins
        elif kind == "fet":
            lib, name = FP["Q"]; pads = {str(FETMAP[k]): v for k, v in pins.items()}
        else:
            lib, name = FP[ref]; pads = {str(PADMAP[ref][k]): v for k, v in pins.items()}
        comps[ref] = {"value": val, "lib": lib, "fp": name, "pads": pads, "src": "eco"}
    for ref, ex in EXTRA.items():
        for k, v in ex.items():
            comps[ref]["pads"][str(PADMAP[ref][k])] = v
    for (ref, pin), net in FORCE.items():
        if ref in comps:
            pk = str(PADMAP[ref][pin]) if ref in PADMAP and pin in PADMAP[ref] else pin
            if net is None:
                comps[ref]["pads"].pop(pk, None)
            else:
                comps[ref]["pads"][pk] = net
    for ref, (val, _n) in VALUES.items():
        if ref in comps:
            comps[ref]["value"] = val
    # R40: keep (battery minus bridge). VMOT_SENSE etc. unchanged.
    return comps


if __name__ == "__main__":
    c = build()
    print(len(c), "components")
    nets = {}
    for r, v in c.items():
        for p, n in v["pads"].items():
            nets.setdefault(n, []).append(f"{r}.{p}")
    for n in sorted(nets):
        if len(nets[n]) < 2:
            print("SINGLE-PIN NET", n, nets[n])
    json.dump({"components": c, "eco": ECO}, open(os.path.join(HERE, "netlist-fab.json"), "w"), indent=1)
