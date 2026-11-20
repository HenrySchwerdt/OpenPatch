#!/usr/bin/env python3
"""Regenerate the netlist-derived sections of cup/PART-AUDIT.md (current part list) and FIRMWARE-PINMAP.md (HJ-840 / supervisor pin tables) from
netlist_v4_cup.json.  usage: python3 gen_cup_docs.py   (idempotent: replaces the block between the GENERATED markers, or inserts it)"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..")
parts = json.load(open(os.path.join(R, "netlist_v4_cup.json")))
BEGIN, END = "<!-- GENERATED:BEGIN (tools/gen_cup_docs.py) -->", "<!-- GENERATED:END -->"


def put(path, block, at_top_after_title=False):
    t = open(path).read()
    blk = BEGIN + "\n" + block.strip() + "\n" + END + "\n"
    if BEGIN in t:
        t = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n", lambda m: blk, t, flags=re.S)
    elif at_top_after_title:
        lines = t.split("\n")
        i = next((k for k, l in enumerate(lines) if l.startswith("# ")), 0)
        lines.insert(i + 1, "\n" + blk)
        t = "\n".join(lines)
    else:
        t = t.rstrip("\n") + "\n\n" + blk
    open(path, "w").write(t)


# ------------------------------------------------------------------ part list
fitted = [p for p in parts if p["bom"] and not p["dnp"]]
rows = ["## Current part list (generated from `netlist_v4_cup.json`: %d fitted parts, %d without BOM: pads / DNP)" % (len(fitted), len(parts) - len(fitted)), "",
        "| Ref | Value | LCSC | Footprint | Group | Nets |", "|---|---|---|---|---|---|"]
for p in parts:
    if not p["bom"] or p["dnp"]:
        continue
    nets = ", ".join(sorted({v for v in p["pins"].values() if v}))
    rows.append("| %s | %s | %s | %s | %s | %s |" % (p["ref"], p["value"], p["lcsc"], p["fp"][1], p["group"], nets))
nofit = [p["ref"] + (" (DNP)" if p["dnp"] else "") for p in parts if not p["bom"] or p["dnp"]]
rows += ["", "Not fitted by the assembler (bare pads, wire pads, DNP match parts): " + ", ".join(nofit) + "."]
put(os.path.join(R, "cup", "PART-AUDIT.md"), "\n".join(rows))

# ------------------------------------------------------------------ pin maps
u1 = next(p for p in parts if p["ref"] == "U1")
u30 = next(p for p in parts if p["ref"] == "U30")
sym = {"A1": "GND", "A2": "P1.01", "A3": "P0.21", "A4": "P0.20", "A5": "P0.17", "A6": "P0.14", "A7": "ANT", "A8": "BOARD_ANT",
       "B1": "P0.22", "B2": "P1.04", "B3": "P1.07", "B4": "P0.09", "B5": "P1.05", "B6": "P0.24", "B7": "P1.06", "B8": "P1.14",
       "C1": "P0.25", "C2": "SWDIO", "C3": "SWCLK", "C4": "DEC5", "C5": "P0.10", "C6": "P0.13", "C7": "P1.11", "C8": "P1.12",
       "D1": "P0.19", "D2": "P1.00", "D3": "P1.02", "D4": "P1.03", "D5": "P0.23", "D6": "P1.10", "D7": "P1.13", "D8": "P0.31",
       "E1": "P0.18/RESET", "E2": "P0.15", "E3": "P0.16", "E4": "P1.08", "E5": "P1.15", "E6": "P0.02", "E7": "P0.28", "E8": "P0.03",
       "F1": "D+", "F2": "VBUS", "F3": "P0.11", "F4": "P0.07", "F5": "P0.27", "F6": "P0.00", "F7": "P0.30", "F8": "P0.29",
       "G1": "D-", "G2": "DECUSB", "G3": "P0.12", "G4": "P1.09", "G5": "P0.05", "G6": "P0.01", "G7": "P0.26", "G8": "P0.06",
       "H1": "DCCH", "H2": "VDDH", "H3": "VDD", "H4": "VDD", "H5": "P0.08", "H6": "DEC1", "H7": "P0.04", "H8": "GND"}
dirs = {"APHASE": "out", "BPHASE": "out", "AENBL": "out", "BENBL": "out", "CHG_STAT": "in (open drain, internal pull-up)", "OC_OK": "in (open drain, 100 k pull-up RNR-class R92)",
        "LATCH_Q": "in (readback)", "DOCK_N": "in (hall, 100 k pull-up RDK)", "SUP_OK": "in", "LED_R": "out, active low", "LED_G": "out, active low", "LED_B": "out, active low",
        "SUP_TXD": "uart (bootloader / supervisor link)", "SUP_RXD": "uart", "SUP_BOOT0": "out (BOOT0 of the supervisor, internal pull-down on the STM32)",
        "SUP_NRST": "**open-drain output only** (never drive high: the net is shared with TPL5010 RSTn, supervisor NRST and U32)", "MOT_FWD": "out (forward intent, R16 pull-up = forward)",
        "BTN_N": "in (internal pull-up)", "I2C_SCL": "TWIM (4.7 k pull-up RI2)", "I2C_SDA": "TWIM (4.7 k pull-up RI1)", "ARM_CLK": "out (latch set clock)", "MCU_EN": "out (R18 pull-down; hardware AND input U36)",
        "BUZ_A": "out (4 kHz PWM to the sounder gate, RDA pull-down)", "NRST": "reset", "VMOT_SENSE": "ain (VMOT/2)"}
blk = ["## Current pin map (generated from `netlist_v4_cup.json`, HJ-840 high-voltage mode: H2 `VDDH` = `VBAT`, H3/H4 `VDD` = `3V3` = nRF52840 REG0 output, no LDO; older ISP1807 / STSPIN tables below are history)", "",
       "UICR `REGOUT0` = 3.3 V once (flash in normal-voltage mode with 3.3 V on VDDH and VDD); **keep the radio at +4 dBm or less: REG0 external load limit 25 mA at TX <= +4 dBm** (nRF52840 PS v1.7 p. 84, second-hand), the rail load is about 8 mA worst case. "
       "The nRF drives `SUP_NRST` open drain only. SAADC `VDDHDIV5` reads the cell (VDDH = VBAT).", "",
       "| HJ-840 pad | nRF pin | Net | Direction / note |", "|---|---|---|---|"]
for pad in sorted(u1["pins"], key=lambda k: (k[0], int(k[1:]))):
    net = u1["pins"][pad]
    if net is None:
        continue
    blk.append("| %s | %s | `%s` | %s |" % (pad, sym.get(pad, ""), net, dirs.get(net, "")))
blk += ["", "Supervisor STM32C011F4U6 (U30, UFQFPN20, DS13866 table 12):", "", "| Pin | Function | Net |", "|---|---|---|"]
fn = {1: "PC15", 2: "VDD", 3: "VSS", 4: "PF2-NRST", 5: "PA0", 6: "PA1", 7: "PA2", 8: "PA3", 9: "PA4", 10: "PA5", 11: "PA6", 12: "PA7", 13: "PA8", 14: "PA11 [PA9] (bootloader USART1 TX)",
      15: "PA12 [PA10] (bootloader USART1 RX)", 16: "PA13 (SWDIO)", 17: "PA14-BOOT0 (SWCLK, internal pull-down at reset)", 18: "PB6", 19: "PB7", 20: "PC14"}
for k in range(1, 21):
    blk.append("| %d | %s | %s |" % (k, fn[k], "`%s`" % u30["pins"][str(k)] if u30["pins"].get(str(k)) else "-"))
put(os.path.join(R, "FIRMWARE-PINMAP.md"), "\n".join(blk), at_top_after_title=True)
print("docs regenerated:", len(fitted), "fitted parts")
