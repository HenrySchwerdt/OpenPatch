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
HJ_FIXED = {"A1": "GND", "H8": "GND", "A7": "ANT_A", "A8": "ANT_B", "H2": "VBAT", "H3": "3V3", "H4": "3V3", "F1": "USB_DP", "G1": "USB_DM", "F2": "VBUS_P",
            "E1": "NRST", "C2": "SWDIO", "C3": "SWDCLK", "H7": "VMOT_SENSE"}
# signals that go to GPIO pads (the pad is chosen by cup/pinassign.py, initial order below); NFC pins B4/C5 are not used
HJ_SIGNALS = ["APHASE", "BPHASE", "AENBL", "BENBL", "CHG_STAT", "OC_OK", "LATCH_Q", "DOCK_N", "SUP_OK", "LED_R", "LED_G", "LED_B", "SUP_TXD", "SUP_RXD",
              "SUP_BOOT0", "SUP_NRST", "MOT_FWD", "BTN_N", "I2C_SCL", "I2C_SDA", "ARM_CLK", "MCU_EN", "BUZ_A"]
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
        note="HJSIP HJ-840 LGA64 6.2 x 7.0 x 1.0, JLC stock about 90, integrated antenna (A7 ANT -> pi match -> A8 BOARD_ANT), HIGH-VOLTAGE mode: VDDH = VBAT, VDD pins H3/H4 = the 3V3 rail supplied by the module regulator REG0 (UICR REGOUT0 must be set to 3.3 V once, default 1.8 V; flash with 3.3 V on both the cell + pad and the SWD 3V3 pad = normal-voltage mode); DCCH, DEC1, DEC5, DECUSB not connected (module has its own filter capacitors; DC/DC off, LDO mode: VERIFY with figure 2.4 of the manual); NFC pins not used; no parts under the module, no copper in the antenna area")
    new("C70", "4.7uF 16V 0603", C0603, {1: "3V3", 2: "GND"}, "C19666", "CL10A475KO8NNNC", group="mcu", note="3V3 = nRF52840 REG0 output: 4.7 uF at VDD H3/H4 (review C3); HV mode relies on REG0, max 25 mA external at TX <= 4 dBm (nRF52840 PS v1.7 p.84 via DevZone, verify)")
    new("PI1", "pi match shunt C (DNP)", C0402, {1: "ANT_A", 2: "GND"}, "C1525", "CL05B104KO5NNNC", group="mcu", dnp=True, note="pi match shunt, value to be tuned (about 0.5 to 1 pF), DNP")
    new("PI2", "pi match series 0R", R0402, {1: "ANT_A", 2: "ANT_B"}, "C17168", "0402WGF0000TCE", group="mcu", note="series element: 0 ohm connects A7 to A8 (internal antenna)")
    new("PI3", "pi match shunt C (DNP)", C0402, {1: "ANT_B", 2: "GND"}, "C1525", "CL05B104KO5NNNC", group="mcu", dnp=True, note="pi match shunt, DNP")
    # ---------------------------------------------------------------- supply: cell pads, LDO
    for ref, net, lab in (("SP1", "VBAT", "+"), ("SP2", "GND", "-")):
        new(ref, "cell lead pad %s" % lab, ("V010", "Wire_Pad_1.0x1.8"), {1: net}, bom=False, group="batt",
            note="hand-solder pad 2.0 x 3.0 for the cell lead %s (Ampul 301030 has two flying wires, user solders them); silkscreen label; near the cell wire exit (position VERIFY); strain-relief edge notch not added" % lab)
    take("C5", "pwr")
    # ---------------------------------------------------------------- USB-C + charger
    for ref in ("JU1", "RU1", "RU2", "UU1", "CU1"):
        p = take(ref, "usb")
        p["pins"] = {k: ("VBUS_P" if v == "VBUS_R" else v) for k, v in p["pins"].items()}
        if ref == "JU1":
            p.update(value="USB-C 16P sink-board TYPE-C-31-M-14", fp=["V010", "USB_C_HRO_31_M_14"], lcsc="C223907", mpn="TYPE-C-31-M-14",
                     pins={"A1B12": "GND", "B1A12": "GND", "S": "GND", "A4B9": "VBUS_P", "B4A9": "VBUS_P", "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM", "B7": "USB_DM"},
                     note="JLC-stocked (2143) HRO sink-board 16P USB-C receptacle in a 9.4 x 6.7 mm notch of the +Y edge (+ 6.6 x 0.7 sub-notch), centre x 23.5; pads = the official LCSC/HRO land pattern (12 SMD pads in one row, merged power pads, 4 shield THT slots, 2 peg holes); SBU pads A8/B8 not connected; pin check 2026-11-20 (cup/PIN-CHECK.md); height vs lid inner z 7.6 and cell top 4.1: mechanics VERIFY")
    take("U3", "chg", pins={"1": "CHG_STAT", "2": "GND", "3": "VBAT", "4": "VBUS_P", "5": "CHG_PROG"})
    take("R3", "chg", pins={"1": "CHG_PROG", "2": "GND"}, value="47k", note="PROG 47k -> about 21 mA charge current")
    # VBAT sense: SAADC VDDHDIV5 channel (VDDH = VBAT), no divider
    # ---------------------------------------------------------------- motor driver: DRV8835 (no chopper: 26.5 ohm coil, 5 V -> about 0.18 A per phase, resistance limited), full steps
    new("U7", "DRV8835DSSR", ("Package_SON", "WSON-12-1EP_3x2mm_P0.5mm_EP1x2.65"),
        {1: "VMOT", 2: "MOT_A1", 3: "MOT_A2", 4: "MOT_B1", 5: "MOT_B2", 6: "GND", 7: "BENBL", 8: "BPHASE", 9: "AENBL", 10: "APHASE", 11: "3V3", 12: "3V3", 13: "GND"},
        "C129328", "DRV8835DSSR", group="drv",
        note="dual H-bridge, VM 0-11 V, VCC 2-7 V, 1.5 A per bridge, MODE tied to VCC = PHASE/ENABLE (ENABLE low = brake: both outputs low); no current sense / limit (TI SLVSB18H): the current is set by the 26.5 ohm coil; pin map verified in SLVSB18H; land pattern matches the LCSC WSON-12 footprint (topology and pitch); JLC STOCK = 0 on 2026-11-20 (see cup/PIN-CHECK.md)")
    C("C19", "100nF", "3V3", "GND", "drv")
    take("C21", "drv")
    for i, (net, lab) in enumerate((("MOT_A1", "A+"), ("MOT_A2", "A-"), ("MOT_B1", "B+"), ("MOT_B2", "B-"))):
        new("MP%d" % (i + 1), "motor lead pad %s" % lab, ("V010", "Wire_Pad_1.0x1.8"), {1: net}, bom=False, group="mot",
            note="hand-solder pad 1.0 x 1.8 for the motor lead %s (cut the JST plug of the NFP-608 lead, solder 4 wires, strain relief by glue/tie), silkscreen label, west edge next to the motor lead exit (x 7.5 to 13, y about 24); VERIFY against the motor CAD" % lab)
    for i, net in enumerate(("3V3", "GND", "I2C_SDA", "I2C_SCL")):
        new("TL%d" % (i + 1), "REAR strip pad (%s)" % net, ("V010", "FPC_Pad_1.2x0.6"), {1: net}, bom=False, side="B", group="rear",
            note="ENIG pad pair with the REAR flex strip (TMAG5273 at gear B)")
        # ---------------------------------------------------------------- UI: LED, button, piezo
    new("LD1", "RGB LED SZYY1615RGB-B (common anode)", ("V010", "LED_RGB_1615_4P"), {1: "LED_R", 2: "LED_G", 3: "LED_B", 4: "LED_A"}, "C3029071", "SZYY1615RGB-B", group="ui",
        note="top-facing status RGB LED under the clear lid, common anode through ONE 1k from VBAT (GPIO high = off even at 4.2 V, no idle current); one lit channel about 0.7 to 1.7 mA; pad order and common anode (pin 4) verified in the vendor drawing; green and blue VF 2.8 to 3.4 V: dim below about 3.4 V cell voltage")
    R("R74", "1k", "VBAT", "LED_A", "ui")
    new("SW1", "SKSCLAE010 side tact", ("V010", "SW_SKSCLAE010"), {1: "BTN_N", 2: "BTN_N", 3: "GND", 4: "GND"}, "C130445", "SKSCLAE010", group="ui",
        note="ALPS SKSCLAE010 side-push tact 4.85 x 3.55 x 1.25 (JLC stock 873, extended). Pin check 2026-11-20: the earlier SKRPACE010 (C139797) is a TOP-push switch 2.5 mm high and was replaced; pins 1+2 and 3+4 are two contact pairs, actuator faces local -y (north wall when placed at rot 0); internal nRF pull-up, no external resistor")
    new("BZ1", "FUET-4020 SMD magnetic sounder", ("V010", "BZ_4020"), {1: "VBAT", 2: "PZ_C"}, "C391027", "FUET-4020", side="B", group="ui",
        note="fitted: 4 x 4 x 2.0 mm SMD magnetic sounder on the bottom side of the side_b block (2.0 mm part, 4.3 mm free below the board, 2.3 mm spare), pod position about (39.0, 20.2), z 3.3 to 5.3; driven by QBA + D6, off by default; vendor data: 4 kHz square wave 2 to 4 Vp, rated 3 V / max 90 mA, coil 17 ohm, MIN 65 dB at 10 cm (drive with PWM at 4 kHz, never DC: 4.2 V / 17 ohm = 0.25 A); alternatives MLT-5020 C94598 (5 x 5), Cy-SMD-4020-3040 C968744")
    new("D6", "1N4148W (sounder flyback)", ("Diode_SMD", "D_SOD-123"), {1: "VBAT", 2: "PZ_C"}, "C81598", "1N4148W", group="ui", note="flyback across the sounder coil (cathode pad 1 on VBAT)")
    R("RDA", "100k", "BUZ_A", "GND", "ui")
    new("RBZ", "22R 0603", ("Resistor_SMD", "R_0603_1608Metric"), {1: "PZ_C", 2: "PZ_A"}, "C23345", "0603WAF220JT5E", group="ui",
        note="series resistor of the sounder (review m4): coil 17 +-3 ohm (vendor), 4.2 V / (17 + 22 + about 3 ohm) = 100 mA peak, vendor maximum 90 mA at 3 V; 0.1 W 0603 at 50 % duty, alarm bursts only; flyback D6 across the coil only")
    # ---------------------------------------------------------------- dock hall (single, see INTERLOCK.md section I: 2oo2 dropped, one magnet) + inverter into DOCKED_H
    R("RI1", "4.7k", "3V3", "I2C_SDA", "mcu", note="I2C pull-up (review m2)")
    R("RI2", "4.7k", "3V3", "I2C_SCL", "mcu", note="I2C pull-up (review m2)")
    new("U4A", "DRV5032FADMRR", ("Bench", "DRV5032_X2SON-4_DMR0004B"), {1: "3V3", 2: "GND", 4: "DOCK_N", 5: "GND"}, "C2152496", "DRV5032FADMRR", side="B", group=DOCK_LEG,
        note="dock hall on the underside of the dock leg, centred on the dock magnet axis (z 4.9-5.3); VERIFY threshold. Single hall: a second hall cannot see the d1 x 0.5 magnet (Bz of the dipole changes sign about 1 mm off axis)")

    # ---------------------------------------------------------------- bare test pads (zero BOM, review M4 / M5); 0.6 mm
    for i, (net, why) in enumerate((("SUP_NRST", "supervisor NRST (nRF drives it open drain only)"), ("SUP_BOOT0", "supervisor BOOT0 = PA14 = SWCLK"), ("BPHASE", "supervisor SWDIO = PA13 (also BPHASE)"),
                                    ("VBAT", ""), ("VMOT_PRE", ""), ("VMOT", ""), ("MOT_ALLOW", ""), ("LATCH_Q", ""), ("SUP_PERMIT", ""), ("OC_OK", ""), ("DOCK_N", ""),
                                    ("SUP_TXD", ""), ("SUP_RXD", ""), ("VBUS_P", ""))):
        new("TP%d" % (i + 1), "test pad %s" % net, ("V010", "TP_Pad_D0.6"), {1: net}, bom=False, group="tpx", note="bare test pad 0.6 mm %s" % why)
    # ---------------------------------------------------------------- supervisor + step gate + TPL5010 latch
    new("U30", "STM32C011F4U6", ("V010", "UFQFPN-20_3x3_P0.5"),
        {19: "MCU_EN", 20: "SUP_DONE", 1: "SUP_WAKE", 2: "3V3", 3: "GND", 4: "SUP_NRST", 5: "ARM_CLK", 6: "APHASE", 7: "MOT_FWD", 8: "OC_OK",
         10: "SUP_PERMIT", 11: "SUP_OK", 12: "NRST", 14: "SUP_TXD", 15: "SUP_RXD", 16: "BPHASE", 17: "SUP_BOOT0", 18: "DOCK_N"}, "C5456188", "STM32C011F4U6", group="sup",
        note="independent supervisor (INTERLOCK.md H, I); UFQFPN20 pin map from DS13866 rev 5 table 12 (pin check 2026-11-20: the earlier TSSOP20 numbering was wrong on this package): 19 PB7 MCU_EN, 20 PC14 SUP_DONE, 1 PC15 SUP_WAKE, 2 VDD, 3 VSS, 4 NRST, 5 PA0 ARM_CLK, 6 PA1 APHASE, 7 PA2 MOT_FWD, 8 PA3 OC_OK, 10 PA5 SUP_PERMIT, 11 PA6 SUP_OK, 12 PA7 NRST(nRF), 14 PA11 TXD (bootloader USART1 TX), 15 PA12 RXD, 16 PA13 BPHASE (SWDIO at reset, pull-up), 17 PA14-BOOT0 (internal pull-down at reset), 18 PB6 DOCK_N; no exposed pad; BOOT0 pin only effective when option bit nBOOT_SEL = 0 (blank part boots the system loader through the empty-flash check)")
    C("C50", "100nF", "3V3", "GND", "sup")
    
    new("U5", "TPL5010DDCR", SOT236, {1: "3V3", 2: "GND", 3: "WDT_DELAY", 4: "SUP_DONE", 5: "SUP_WAKE", 6: "SUP_NRST"}, "C473912", "TPL5010DDCR", group="wdt",
        note="independent timer now watches the SUPERVISOR: no DONE after WAKE -> RSTn low: resets the supervisor and clears the latch")
    new("R26", "6.8k", R0402, {1: "WDT_DELAY", 2: "GND"}, "C25917", "0402WGF6801TCE", group="wdt", note="TPL5010 interval resistor: 6.79 kohm = 2 s (SNAS651A table 3), 1 %; 10 k would give about 7.6 s (review C1)")
    new("U6", "SN74AUP1G74DCUR", ("Package_SO", "VSSOP-8_2.3x2mm_P0.5mm"), {1: "ARM_CLK", 2: "3V3", 3: None, 4: "GND", 5: "LATCH_Q", 6: "LATCH_CLR_N", 7: "3V3", 8: "3V3"},
        "C140267", "SN74AUP1G74DCUR", group="wdt", note="interlock latch: set by an ARM_CLK edge, cleared by LATCH_CLR_N (power-up, TPL5010 timeout, supervisor reset, over-current)")
    new("U32", "TP74AUP1G08S5 (AND)", SOT235, {1: "SUP_NRST", 2: "OC_OK", 3: "GND", 4: "LATCH_CLR_N", 5: "3V3"}, "C48886815", "TP74AUP1G08S5", group="wdt",
        note="LATCH_CLR_N = SUP_NRST AND OC_OK: any supervisor reset / TPL5010 timeout or an over-current trip clears the latch (no diodes)")
    R("R29", "100k", "ARM_CLK", "GND", "wdt")
    # ---------------------------------------------------------------- motor supply: boost (supervisor EN) -> current-limited load switch (hardware EN) -> VMOT
    R("R82", "100k", "SUP_PERMIT", "GND", "sw")
    R("R16", "100k", "3V3", "MOT_FWD", "sw", note="forward-intent line pull-up: default = forward = blocked when undocked")
    new("QBA", "2N7002", SOT23, {1: "BUZ_A", 2: "GND", 3: "PZ_A"}, "C8545", "2N7002", group="ui", note="sounder drive leg (100 k pull-down RDA), off by default")
    new("U33", "74AUP1G86GW-TP (XOR)", SC70_5, {1: "DOCK_N", 2: "MOT_FWD", 3: "GND", 4: "DOCK_XOR", 5: "3V3"}, "C48995440", "74AUP1G86GW-TP", group="sw",
        note="DOCK_XOR = DOCK_N XOR MOT_FWD = DOCKED XOR DIR_REVERSE (DOCK_N is active low, MOT_FWD high = forward): docked+forward and undocked+reverse allowed, undocked+forward and docked+reverse (H15) blocked; reset default MOT_FWD high (R16) = forward = blocked when undocked; JLC stock 3001 (review C2)")
    new("U36", "EM74AUP1G11GM (AND3)", ("V010", "UFDFN-6_1.45x1.0_P0.5"), {1: "LATCH_Q", 2: "GND", 3: "SUP_PERMIT", 4: "PERM_L", 5: "3V3", 6: "MCU_EN"}, "C54929506", "EM74AUP1G11GM", group="sw",
        note="PERM_L = LATCH_Q AND SUP_PERMIT AND MCU_EN (review M1: CLAUDE.md rule motor only with MCU enable AND watchdog in hardware); 74AUP1G11 pinout 1 A 2 GND 3 B 4 Y 5 VCC 6 C (LCSC symbol); the SC-70-6 74AUP1G11GW has JLC stock 3, this DFN-6 1.0 x 1.45 clone has 9000")
    R("R18", "100k", "MCU_EN", "GND", "sw")
    new("U34", "TP74AUP1G08S5 (AND)", SOT235, {1: "PERM_L", 2: "DOCK_XOR", 3: "GND", 4: "MOT_ALLOW", 5: "3V3"}, "C48886815", "TP74AUP1G08S5", group="sw",
        note="MOT_ALLOW = LATCH_Q AND SUP_PERMIT AND MCU_EN AND (DOCKED XOR reverse): the single hardware enable of the load switch (pure logic, no software)")
    R("R90", "100k", "MOT_ALLOW", "GND", "sw")
    R("RDK", "100k", "3V3", "DOCK_N", "sw", note="SPICE F1: pull-up on the hall output so an open hall joint reads UNDOCKED (a floating low line would read docked and enable forward undocked)")
    R("RNR", "100k", "3V3", "SUP_NRST", "wdt", note="SPICE F5: pull-up for the open-drain TPL5010 RSTn (the STM32C011 NRST weak pull-up is not relied on)")
    C("C61", "100nF", "VMOT", "GND", "drv", note="SPICE F6: 0.1 uF at the DRV8835 VM pin (datasheet requirement, next to U7.1) in addition to the bulk C21")
    new("C71", "10uF 10V 0603", C0603, {1: "VBAT", 2: "GND"}, "C19702", "CL10A106KP8NNNC", group="boost", note="SPICE F3: second 10 uF at the TPS61023 VIN (boost pre-charge dip), next to U8")
    new("U20", "TPS2553DBVR", SOT236, {1: "VMOT_PRE", 2: "GND", 3: "MOT_ALLOW", 4: "OC_OK", 5: "ILIM", 6: "VMOT"}, "C55266", "TPS2553DBVR", group="sw",
        note="current-limited high-side switch 2.5-6.5 V, 85 mohm, EN active high (hardware cut), FAULT open drain = OC_OK (low when the limit is active > deglitch), NOT the -1 latch variant; pinout 1 IN 2 GND 3 EN 4 FAULT 5 ILIM 6 OUT verified in SLVS841G table 5-1")
    new("R91", "47k", R0402, {1: "ILIM", 2: "GND"}, "C25792", "0402WGF4702TCE", group="sw", note="ILIM resistor 47k: TI table 49.9k = 475/520/565 mA, from the TPS2553 equations (SLVS841G eq. 1-3) 47 k gives 506/557/616 mA (min/typ/max): above the worst-case motor current 0.40 A (5 V, 23.9 ohm coil, 1 ohm bridge), well below the 1.5 A bridge rating")
    R("R92", "100k", "3V3", "OC_OK", "sw")
    C("C60", "100nF", "VMOT_PRE", "GND", "sw")
    new("R57", "10k", R0402, {1: "VMOT", 2: "VMOT_SENSE"}, "C25744", "0402WGF1002TCE", group="oc", note="VMOT sense divider 10k/10k = also the bleeder of the VM capacitors (time constant about 0.6 s), reads 2.5 V at 5 V")
    new("R58", "10k", R0402, {1: "VMOT_SENSE", 2: "GND"}, "C25744", "0402WGF1002TCE", group="oc")
    # ---------------------------------------------------------------- 5 V boost (motor NFP-608-26.45-SGM, 4.8 V rated), EN = supervisor permission
    new("U8", "TPS61023DRLR", ("Package_TO_SOT_SMD", "SOT-563"), {1: "BST_FB", 2: "SUP_PERMIT", 3: "VBAT", 4: "GND", 5: "BST_SW", 6: "VMOT_PRE"}, "C919459", "TPS61023DRLR", group="boost",
        note="sync boost 3.7 A switch, 0.5-5.5 V in, 1 uA off, about 90 % at 0.3 A out; VIN from the cell, EN = SUP_PERMIT (supervisor second cut); pinout verified in SLVSF14B: 1 FB 2 EN 3 VIN 4 GND 5 SW 6 VOUT; output OVP 5.7 V typ")
    new("L1", "1uH 2520 (WPN252012E1R0MT)", ("Inductor_SMD", "L_1008_2520Metric"), {1: "VBAT", 2: "BST_SW"}, "C370610", "WPN252012E1R0MT", group="boost", note="1 uH 2.5 x 2.0 x 1.2; Isat VERIFY >= 2.5 A")
    new("R55", "220k", R0402, {1: "VMOT_PRE", 2: "BST_FB"}, "C25767", "0402WGF2203TCE", group="boost", note="FB divider 220k/30k, FB 0.595 V -> 4.96 V")
    new("R56", "30k", R0402, {1: "BST_FB", 2: "GND"}, "C25776", "0402WGF3002TCE", group="boost")
    C0805 = ("Capacitor_SMD", "C_0805_2012Metric")
    for i in (1,):
        new("CB%d" % i, "22uF 6.3V X5R 0805", C0805, {1: "VMOT_PRE", 2: "GND"}, "C45783", "CL21A226MAQNNNE", group="boost",
            note="bulk on the boost output (basic part); about 8 uF effective at 5 V DC bias")
    # ---------------------------------------------------------------- SWD + test pads (top side)
    swd = [("SWDIO", "SWDIO"), ("SWDCLK", "SWDCLK"), ("NRST", "NRST"), ("GND", "GND"), ("3V3", "3V3")]
    for i, (v, n) in enumerate(swd):
        new("J%d" % (10 + i), "SWD pad " + v, ("V010", "TP_Pad_D0.8"), {1: n}, bom=False, group="swd", note="SWD pad (spring probe jig)")
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
