#!/usr/bin/env python3
"""OpenPatch v0.1.0 integrated pod board: scripted netlist (single source of truth for the board, BOM and the docs).

TEST ONLY - NOT FOR HUMAN USE.  Water only.

Run:  python3 netlist.py   -> ../netlist.json, ../v010.net (KiCad legacy netlist), ERC summary on stdout.

A part is a dict(ref, value, fp=(lib, name), pins={pad: net}, lcsc, mpn, side, bom, note, group).  Sub-circuits A..E of the
interlock are copied from electronics/bench/INTERLOCK.md (bench controller final) and adapted to the battery supply.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..")

R0402, R0603 = ("Resistor_SMD", "R_0402_1005Metric"), ("Resistor_SMD", "R_0603_1608Metric")
C0402, C0603, C0805 = ("Capacitor_SMD", "C_0402_1005Metric"), ("Capacitor_SMD", "C_0603_1608Metric"), ("Capacitor_SMD", "C_0805_2012Metric")
SOT23, SOT235, SOT236, SC705 = [("Package_TO_SOT_SMD", n) for n in ("SOT-23", "SOT-23-5", "SOT-23-6", "SOT-353_SC-70-5")]
VSSOP8 = ("Package_SO", "VSSOP-8_2.3x2mm_P0.5mm")
SOD123 = ("Diode_SMD", "D_SOD-123")
TP = ("TestPoint", "TestPoint_Pad_D1.0mm")

RV = {"100k": ("C25741", "0402WGF1003TCE"), "10k": ("C25744", "0402WGF1002TCE"), "4.7k": ("C25900", "0402WGF4701TCE"),
      "5.1k": ("C25905", "0402WGF5101TCE"), "3.3k": ("C25890", "0402WGF3301TCE"), "1k": ("C11702", "0402WGF1001TCE"),
      "100R": ("C25076", "0402WGF1000TCE"), "22k": ("C25768", "0402WGF2202TCE"), "47k": ("C25792", "0402WGF4702TCE"),
      "22R": ("C25092", "0402WGF220JTCE"), "1M": ("C26083", "0402WGF1004TCE"), "4.7M": ("C26091", "0402WGJ0475TCE")}
CV = {"100nF": ("C1525", "CL05B104KO5NNNC"), "1uF": ("C52923", "CL05A105KA5NQNC"), "4.7uF": ("C23733", "CL05A475MP5NRNC"),
      "15pF": ("C1548", "0402CG150J500NT"), "10nF": ("C15195", "CL05B103KB5NNNC")}

PARTS = []
_n = {}


def add(ref, value, fp, pins, lcsc=None, mpn=None, side="F", bom=True, note="", group="", dnp=False):
    assert ref not in [p["ref"] for p in PARTS], ref
    PARTS.append(dict(ref=ref, value=value, fp=list(fp), pins={str(k): v for k, v in pins.items()}, lcsc=lcsc, mpn=mpn, side=side,
                      bom=bom and not dnp, dnp=dnp, note=note, group=group))


def R(ref, val, a, b, group="", **kw):
    add(ref, val, R0402, {1: a, 2: b}, RV[val][0], RV[val][1], group=group, **kw)


def C(ref, val, a, b, group="", **kw):
    add(ref, val, C0402, {1: a, 2: b}, CV[val][0], CV[val][1], group=group, **kw)


def NMOS(ref, g, s, d, group="", note=""):
    add(ref, "2N7002", SOT23, {1: g, 2: s, 3: d}, "C8545", "2N7002", group=group, note=note)


def FF(ref, clk, d, qn, q, clr, pre, group="", note=""):
    add(ref, "SN74AUP1G74DCUR", VSSOP8, {1: clk, 2: d, 3: qn, 4: "GND", 5: q, 6: clr, 7: pre, 8: "3V3"}, "C140267", "SN74AUP1G74DCUR", group=group, note=note)


def dec(ref, net="3V3", group=""):
    C(ref, "100nF", net, "GND", group=group)


def gate(ref, kind, a, b, y, group=""):
    lc, mpn = {"AND": ("C48886815", "TP74AUP1G08S5"), "OR": ("C49333203", "TP74AUP1G32S5")}[kind]
    add(ref, mpn, SOT235, {1: a, 2: b, 3: "GND", 4: y, 5: "3V3"}, lc, mpn, group=group, note="74AUP1G%s clone (Tech Public), pinout A B GND Y VCC" % ("08" if kind == "AND" else "32"))


def build():
    PARTS.clear()
    # ======================================================================= MCU E73 (bottom side)
    pins = {19: "3V3", 5: "GND", 21: "GND", 24: "GND", 26: "NRST", 37: "SWDIO", 39: "SWDCLK", 11: "XL1", 13: "XL2",
            1: "MOT_STBY", 2: "DOCK_TEST", 3: "DOCK_N", 4: "WDT_DONE", 6: "WIN", 7: "I_SENSE", 8: "NTC", 9: "HWA_FULL",
            10: "DOCKED_H", 12: "I2C_SDA", 14: "I2C_SCL", 15: "VBAT_SENSE", 16: "OC_TEST", 17: "MOT_EN_FAULT", 18: "VMOT_SENSE",
            20: "STCK_MCU", 22: "MOT_DIR", 28: "BTN_N", 30: "WDT_WAKE", 32: "ARM_CLK", 33: "LATCH_Q", 34: "LATCH_CLR_N", 35: "MCU_EN",
            36: "LED_ST", 38: "BUZ_PWM", 40: "SENSE_EN", 41: "OC_OK", 42: "CHG_STAT", 43: "PGATE_MON"}
    add("U1", "E73-2G4M08S1C", ("Bench", "Ebyte_E73-2G4M08S1C_13x18"), pins, "C356849", "E73-2G4M08S1C", side="B", group="mcu",
        note="nRF52840 module, ceramic antenna. JLC stock 1 on 2026-11-19 -> CX variant C2764963 (IPEX, 729 pcs) is footprint-identical but needs an IPEX antenna")
    C("C1", "100nF", "3V3", "GND", "mcu"); C("C2", "4.7uF", "3V3", "GND", "mcu")
    add("Y1", "32.768kHz 12.5pF", ("Crystal", "Crystal_SMD_3215-2Pin_3.2x1.5mm"), {1: "XL1", 2: "XL2"}, "C32346", "Q13FC13500004", group="mcu")
    C("C3", "15pF", "XL1", "GND", "mcu"); C("C4", "15pF", "XL2", "GND", "mcu")
    R("R1", "100k", "3V3", "NRST", "mcu")
    add("J2", "TC2030-IDC-NL (pads)", ("Connector", "Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical"),
        {1: "3V3", 2: "SWDIO", 3: "NRST", 4: "SWDCLK", 5: "GND"}, bom=False, group="swd", note="Tag-Connect pads, no part")

    # ======================================================================= battery, charger, 3V3
    for ref, net, y in (("SP1", "VBAT", 0), ("SP2", "GND", 1)):
        add(ref, "BWCD-L3.5W2.0H1.0 spring", ("V010", "Spring_Contact_3.5x2.0"), {1: net}, "C2826547", "BWCD-L3.5W2.0H1.0", side="B", group="batt",
            note="SMD spring contact on the cell tab; free height 1.0 mm vs 1.05 mm gap: VERIFY preload (see ORDER.md)")
    add("C5", "10uF", C0603, {1: "VBAT", 2: "GND"}, "C19702", "CL10A106KP8NNNC", group="pwr")
    add("U2", "XC6206P332MR-G", SOT23, {1: "GND", 2: "3V3", 3: "VBAT"}, "C5446", "XC6206P332MR-G", group="pwr", note="Torex pinout 1 GND 2 OUT 3 IN")
    C("C6", "1uF", "VBAT", "GND", "pwr")
    add("C7", "10uF", C0603, {1: "3V3", 2: "GND"}, "C19702", "CL10A106KP8NNNC", group="pwr")
    # charge pads (ENIG, lid window) + protection + MCP73832
    add("PAD1", "charge pad +", ("V010", "Charge_Pad_4x3"), {1: "CHG_PAD"}, bom=False, group="chg", note="ENIG pad in lid window")
    add("PAD2", "charge pad -", ("V010", "Charge_Pad_4x3"), {1: "GND"}, bom=False, group="chg", note="ENIG pad in lid window")
    add("D3", "SMF5.0A", ("Diode_SMD", "D_SOD-123F"), {1: "CHG_PAD", 2: "GND"}, "C193402", "SMF5.0A", group="chg", note="TVS, cathode (pad 1) to CHG_PAD")
    R("R2", "22R", "CHG_PAD", "CHG_R", "chg")
    add("D4", "B5819W SL", SOD123, {1: "VCHG", 2: "CHG_R"}, "C8598", "B5819W SL", group="chg", note="reverse-polarity / back-feed Schottky")
    C("C8", "4.7uF", "VCHG", "GND", "chg")
    add("U3", "MCP73832T-2ACI/OT", SOT235, {1: "CHG_STAT", 2: "GND", 3: "VBAT", 4: "VCHG", 5: "CHG_PROG"}, "C38066", "MCP73832T-2ACI/OT", group="chg")
    R("R3", "47k", "CHG_PROG", "CHG_P2", "chg"); R("R4", "3.3k", "CHG_P2", "GND", "chg")
    C("C9", "4.7uF", "VBAT", "GND", "chg")
    # battery voltage + NTC, only powered while SENSE_EN is high
    add("Q1", "AO3401A", SOT23, {1: "SP_G", 2: "VBAT", 3: "VBAT_SW"}, "C15127", "AO3401A", group="sense")
    NMOS("Q2", "SENSE_EN", "GND", "SP_G", "sense"); R("R5", "100k", "VBAT", "SP_G", "sense")
    R("R6", "100k", "VBAT_SW", "VBAT_SENSE", "sense"); R("R7", "100k", "VBAT_SENSE", "GND", "sense"); C("C10", "100nF", "VBAT_SENSE", "GND", "sense")
    R("R8", "10k", "SENSE_EN", "NTC", "sense")
    add("RT1", "NTC 10k NCP15XH103F03RC", C0402, {1: "NTC", 2: "GND"}, "C77131", "NCP15XH103F03RC", group="sense")

    # ======================================================================= motor supply switch: two series P-FETs, gate network (bench blocks A)
    add("Q4", "AO3401A", SOT23, {1: "PGATE", 2: "VBAT", 3: "VMOT_A"}, "C15127", "AO3401A", group="sw", note="first series switch")
    add("Q15", "AO3401A", SOT23, {1: "PGATE", 2: "VMOT_A", 3: "VMOT_RAW"}, "C15127", "AO3401A", group="sw",
        note="second, independent series switch: a shorted Q4 (or Q15) alone cannot keep VMOT on (no USB 'last off switch' on battery)")
    R("R9", "100k", "VBAT", "PGATE", "sw"); R("R10", "100k", "VBAT", "PGATE", "sw", note="parallel pull-up: one open resistor does not float the gate")
    add("C11", "100nF", C0402, {1: "PGATE", 2: "VBAT"}, "C1525", "CL05B104KO5NNNC", group="sw", note="gate-source: slow turn-on (soft start)")
    R("R11", "10k", "PGATE", "CH_TOP", "sw")
    NMOS("Q5", "LATCH_Q", "PG_MID1", "CH_TOP", "sw"); NMOS("Q8", "MCU_EN", "PG_MID2", "PG_MID1", "sw")
    NMOS("Q13", "OC_OK", "PG_MID2A", "PG_MID2", "sw"); NMOS("Q6", "DOCKED_H", "XA", "PG_MID2A", "sw", note="H15 branch 1: docked AND forward")
    NMOS("Q21", "FWD", "GND", "XA", "sw")
    NMOS("Q10", "DOCK_NOT", "XB", "PG_MID2A", "sw", note="H15 branch 2: undocked AND reverse (interlock = DOCKED XOR DIR_REV)")
    NMOS("Q22", "DIR_REV", "GND", "XB", "sw")
    NMOS("Q20", "DOCKED_H", "GND", "DOCK_NOT", "sw", note="inverter: DOCK_NOT high = not both halls asserted"); R("R87", "100k", "3V3", "DOCK_NOT", "sw")
    NMOS("Q11", "MOT_DIR", "GND", "DIR_INV", "sw"); R("R12", "100k", "3V3", "DIR_INV", "sw")
    add("R13", "0R", R0603, {1: "MOT_DIR", 2: "DIR_REV"}, "C21189", "0603WAF0000T5E", group="sw", note="DIR_REV = DIR (default: DIR high = reverse/retract; confirm on the first motor, bench test T5)")
    add("R14", "0R DNP", R0603, {1: "DIR_INV", 2: "DIR_REV"}, dnp=True, group="sw", note="fit instead of R13 if DIR low retracts")
    R("R15", "100k", "DIR_REV", "GND", "sw"); R("R16", "100k", "MOT_DIR", "GND", "sw")
    R("R17", "100k", "LATCH_Q", "GND", "sw"); R("R18", "100k", "MCU_EN", "GND", "sw")
    # dock: two hall sensors that must BOTH assert (2oo2) -> a single stuck-low hall cannot enable undocked delivery
    add("U4A", "DRV5032AJDMRR", ("Bench", "DRV5032_X2SON-4_DMR0004B"), {1: "3V3", 2: "GND", 4: "DOCK_N", 5: "GND"}, "C2152498", "DRV5032AJDMRR", side="B", group="dock",
        note="AJ: BOP 4/7/9.5 mT open drain, asserts only when latched; JLC stock 0 on 2026-11-19 (C2152456/C2152498): order via LCSC or use FA C2152496 + weaker insert magnet geometry")
    add("U4B", "DRV5032AJDMRR", ("Bench", "DRV5032_X2SON-4_DMR0004B"), {1: "3V3", 2: "GND", 4: "DOCK_NB", 5: "GND"}, "C2152498", "DRV5032AJDMRR", side="B", group="dock",
        note="redundant second dock hall (2oo2)")
    R("R19", "4.7M", "3V3", "DOCK_N", "dock"); R("R20", "4.7M", "3V3", "DOCK_NB", "dock")
    NMOS("Q7", "DOCK_N", "GND", "DOCKED_H", "dock"); NMOS("Q7B", "DOCK_NB", "GND", "DOCKED_H", "dock")
    R("R21", "100k", "3V3", "DOCKED_H", "dock")
    NMOS("Q12", "DOCK_TEST", "GND", "DOCKED_H", "dock", note="POST: forces 'undocked' at the gate"); R("R22", "100k", "DOCK_TEST", "GND", "dock")
    # PGATE readback (high impedance: NFET gate, no load on the P-FET gate). PGATE_MON high = supply allowed
    NMOS("Q16", "PGATE", "GND", "PGATE_MON", "sw", note="no external pull-up (idle current): firmware enables the MCU internal pull-up while reading")
    # bleeder: discharges VMOT when the gate network is open (VMOT must fall below 0.5 V within 20 ms)
    NMOS("Q17", "PGATE", "GND", "BLD", "sw", note="turns on when PGATE is high = supply off"); R("R24", "100R", "VMOT", "BLD", "sw"); R("R25", "100R", "VMOT", "BLD", "sw")

    # ======================================================================= watchdog, latch, DONE qualifier (bench B)
    add("U5", "TPL5010DDCR", SOT236, {1: "3V3", 2: "GND", 3: "WDT_DELAY", 4: "DONE_TPL", 5: "WDT_WAKE", 6: "NRST"}, "C473912", "TPL5010DDCR", group="wdt")
    R("R26", "10k", "WDT_DELAY", "GND", "wdt"); R("R27", "22k", "WDT_DELAY", "GND", "wdt")
    FF("U6", "ARM_CLK", "3V3", None, "LATCH_Q", "LATCH_CLR_N", "3V3", "wdt", "interlock latch")
    dec("C14", "3V3", "wdt"); R("R28", "100k", "LATCH_CLR_N", "3V3", "wdt"); C("C15", "100nF", "LATCH_CLR_N", "GND", "wdt")
    add("D2", "B5819W SL", SOD123, {1: "NRST", 2: "LATCH_CLR_N"}, "C8598", "B5819W SL", group="wdt", note="TPL5010 RSTn clears the latch even if the MCU is dead")
    R("R29", "100k", "ARM_CLK", "GND", "wdt")
    FF("U10", "DONE_PULSE", "WDT_WAKE", None, "DONE_TPL", "WAKE_CLR", "3V3", "wdt", "DONE qualifier: DONE edge only valid while WAKE is high")
    C("C16", "10nF", "WDT_DONE", "DONE_PULSE", "wdt"); R("R30", "1k", "DONE_PULSE", "GND", "wdt"); R("R31", "4.7k", "WAKE_CLR", "WDT_WAKE", "wdt")
    C("C17", "10nF", "WAKE_CLR", "GND", "wdt")
    add("D1", "1N4148W", SOD123, {1: "WAKE_CLR", 2: "WDT_WAKE"}, "C81598", "1N4148W", group="wdt")
    R("R32", "100k", "DONE_TPL", "GND", "wdt")
    add("R33", "0R DNP", R0603, {1: "WDT_DONE", 2: "DONE_TPL"}, dnp=True, group="wdt", note="bring-up bypass of the DONE qualifier")

    # ======================================================================= STSPIN220, current limit 160 mA, sense, over-current latch
    add("U7", "STSPIN220", ("Package_DFN_QFN", "QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm"),
        {1: "MOT_DIR", 2: "STCK_DRV", 3: "MOT_A1", 4: "SNSA", 5: "MOT_A2", 6: "VMOT", 7: "GND", 8: "MOT_B2", 9: "SNSB", 10: "MOT_B1", 11: "MOT_REF",
         12: "TOFF", 13: "MOT_EN_FAULT", 14: "MOT_STBY", 15: "MODE2_L", 16: "MODE1_L", 17: "GND"}, "C2150516", "STSPIN220", group="drv")
    add("R34", "1.0R", R0603, {1: "SNSA", 2: "GND"}, "C174300", "RS-03L1R00FT", group="drv"); add("R35", "1.0R", R0603, {1: "SNSB", 2: "GND"}, "C174300", "RS-03L1R00FT", group="drv")
    R("R36", "47k", "TOFF", "GND", "drv"); R("R37", "100k", "MOT_STBY", "MOT_REF", "drv", note="VREF divider is fed from MOT_STBY: no idle current"); R("R38", "5.1k", "MOT_REF", "GND", "drv"); C("C19", "100nF", "MOT_REF", "GND", "drv")
    R("R39", "100k", "MOT_STBY", "GND", "drv"); R("R40", "10k", "3V3", "MOT_EN_FAULT", "drv"); C("C20", "10nF", "MOT_EN_FAULT", "GND", "drv")
    R("R41", "10k", "MODE1_L", "GND", "drv"); R("R42", "10k", "MODE2_L", "GND", "drv")
    add("C21", "22uF", C0805, {1: "VMOT", 2: "GND"}, "C45783", "CL21A226MAQNNNE", group="drv"); add("C22", "10uF", C0603, {1: "VMOT", 2: "GND"}, "C19702", "CL10A106KP8NNNC", group="drv")
    dec("C23", "VMOT", "drv")
    R("R43", "100k", "STCK_MCU", "GND", "drv")
    add("J1", "PicoBlade A1251WR-S-4P", ("Connector_Molex", "Molex_PicoBlade_53261-0471_1x04-1MP_P1.25mm_Horizontal"),
        {1: "MOT_B2", 2: "MOT_A2", 3: "MOT_B1", 4: "MOT_A1"}, "C225113", "A1251WR-S-4P-LCP", side="B", group="mot",
        note="Molex 53261-0471 compatible; motor factory lead plugs in (no soldering); confirm plug on the first motor")
    # supply shunt, INA180, over-current comparator and latch (bench C, adapted: 400 mA trip, shunt 0.22 ohm)
    add("R44", "0.22R", R0603, {1: "VMOT_PRE", 2: "VMOT"}, "C326952", "RL0603FR-070R22L", group="oc", note="supply shunt; 20 V/V -> 4.4 V/A")
    add("R45", "0R bypass", R0603, {1: "VMOT_RAW", 2: "VMOT_PRE"}, "C21189", "0603WAF0000T5E", group="oc", note="REMOVE when the boost option (U8 block) is populated")
    add("C24", "10uF", C0603, {1: "VMOT_RAW", 2: "GND"}, "C19702", "CL10A106KP8NNNC", group="oc")
    add("U9", "INA180A1IDBVR", SOT235, {1: "INA_OUT", 2: "GND", 3: "VMOT_PRE", 4: "VMOT", 5: "VMOT_RAW"}, "C122228", "INA180A1IDBVR", group="oc",
        note="supplied from the switched VMOT_RAW: zero idle drain; pinout A")
    dec("C25", "VMOT_RAW", "oc"); R("R46", "100k", "INA_OUT", "GND", "oc")
    R("R47", "10k", "INA_OUT", "I_SENSE", "oc"); C("C26", "100nF", "I_SENSE", "GND", "oc")
    R("R48", "10k", "INA_OUT", "OC_IN", "oc"); C("C27", "10nF", "OC_IN", "GND", "oc")
    add("U11", "TLV7011DCKR", SC705, {1: "OC_CMP", 2: "GND", 3: "OC_IN", 4: "OC_REF", 5: "3V3"}, "C193688", "TLV7011DCKR", group="oc",
        note="nano-power push-pull comparator on 3V3; output rises on over-current")
    dec("C28", "3V3", "oc"); R("R49", "1M", "3V3", "OC_REF", "oc"); R("R50", "1M", "OC_REF", "OC_REF2", "oc"); R("R51", "100k", "OC_REF2", "GND", "oc")
    NMOS("Q14", "OC_TEST", "GND", "OC_TEST_D", "oc", note="POST: pulls the reference down, trips easier only"); R("R52", "1k", "OC_TEST_D", "OC_REF", "oc"); R("R53", "100k", "OC_TEST", "GND", "oc")
    FF("U12", "OC_CMP", "3V3", "OC_OK", "OC_TRIP", "OC_CLR_N", "3V3", "oc", "over-current latch: Q_N = OC_OK is the 4th series leg; cleared only by MCU_EN low")
    dec("C29", "3V3", "oc"); R("R54", "100k", "MCU_EN", "OC_CLR_N", "oc"); C("C30", "100nF", "OC_CLR_N", "GND", "oc")
    add("D5", "1N4148W", SOD123, {1: "MCU_EN", 2: "OC_CLR_N"}, "C81598", "1N4148W", group="oc")
    # optional boost (DNP): VMOT_RAW -> 5 V into VMOT_PRE instead of R45
    add("U8", "MT3608 (DNP)", SOT236, {1: "BST_SW", 2: "GND", 3: "BST_FB", 4: "VMOT_RAW", 5: "VMOT_RAW", 6: None}, "C84817", "MT3608", side="B", dnp=True, group="boost",
        note="optional 5 V boost, populate with R45 removed; VERIFY before use")
    add("L1", "4.7uH 4x4 (DNP)", ("Inductor_SMD", "L_APV_ANR4018"), {1: "VMOT_RAW", 2: "BST_SW"}, side="B", dnp=True, group="boost", note="MPN to select, Isat >= 1.5 A")
    add("D6", "B5819W SL (DNP)", SOD123, {1: "VMOT_PRE", 2: "BST_SW"}, side="B", dnp=True, group="boost")
    add("R55", "220k (DNP)", R0402, {1: "VMOT_PRE", 2: "BST_FB"}, side="B", dnp=True, group="boost"); add("R56", "30k (DNP)", R0402, {1: "BST_FB", 2: "GND"}, side="B", dnp=True, group="boost")
    add("C31", "10uF (DNP)", C0603, {1: "VMOT_PRE", 2: "GND"}, side="B", dnp=True, group="boost")
    # VMOT sense (VMOT is 0 when off; 20 uA only while running)
    R("R57", "100k", "VMOT", "VMOT_SENSE", "oc"); R("R58", "100k", "VMOT_SENSE", "GND", "oc"); C("C32", "10nF", "VMOT_SENSE", "GND", "oc")

    # ======================================================================= HW-A: arm window + 32-pulse step budget + re-arm dead time (new, spec 7a)
    FF("U13", "ARM_CLK", "3V3", "WIN_N", "WIN", "TS", "3V3", "hwa", "HW-A arm window: set by ARM_CLK, ended by the RC timer through the Schmitt gate")
    R("R59", "1M", "WIN_N", "TN", "hwa"); R("R60", "1M", "WIN_N", "TN", "hwa"); C("C33", "1uF", "TN", "GND", "hwa")
    add("U14", "TP74AUP1G17S5", SOT235, {1: None, 2: "TN", 3: "GND", 4: "TS", 5: "3V3"}, "C49333201", "TP74AUP1G17S5", group="hwa",
        note="Schmitt buffer: TS low = window over AND dead time running (re-arm edges ignored)")
    add("U15", "SN74LV4040APWR", ("Package_SO", "TSSOP-16_4.4x5mm_P0.65mm"),
        {1: None, 2: "HWA_FULL", 3: None, 4: None, 5: None, 6: None, 7: None, 8: "GND", 9: None, 10: "CNT_CLK", 11: "WIN_N", 12: None, 13: None, 14: None, 15: None, 16: "3V3"},
        "C180412", "SN74LV4040APWR", group="hwa", note="Q6 (pin 2) goes high after 32 clock pulses; held in reset while the window is closed")
    NMOS("Q18", "HWA_FULL", "GND", "HWA_FULL_N", "hwa"); R("R61", "100k", "3V3", "HWA_FULL_N", "hwa")
    gate("U16", "AND", "WIN", "HWA_FULL_N", "HWA_X", "hwa")
    gate("U17", "OR", "DIR_REV", "HWA_X", "HWA_Y", "hwa")
    gate("U18", "AND", "STCK_MCU", "HWA_Y", "STCK_DRV", "hwa")
    gate("U19", "AND", "STCK_DRV", "FWD", "CNT_CLK", "hwa")
    add("R62", "0R", R0603, {1: "DIR_INV", 2: "FWD"}, "C21189", "0603WAF0000T5E", group="hwa", note="FWD = not DIR_REV (R13 variant)")
    add("R63", "0R DNP", R0603, {1: "MOT_DIR", 2: "FWD"}, dnp=True, group="hwa", note="fit instead of R62 together with R14")
    for i, n in enumerate(("C34", "C35", "C36", "C37")):
        dec(n, "3V3", "hwa")
    # WIN readback: WIN is a logic node, read it directly through 1 k (protects against a shorted MCU pin)

    # ======================================================================= I2C sensors on the pod board = same board here
    add("U10T", "TMAG5273A1QDBVR", SOT236, {1: "I2C_SCL", 2: "GND", 3: "GND", 4: "3V3", 5: "TMAG_INT", 6: "I2C_SDA"}, "C3716049", "TMAG5273A1QDBVR", side="B", group="tmag",
        note="directly under the spindle magnet (mechanical/out/bench/OP-100.layout.json HALL_3D); I2C 0x35")
    dec("C41", "3V3", "tmag"); R("R67", "4.7k", "3V3", "I2C_SDA", "tmag"); R("R68", "4.7k", "3V3", "I2C_SCL", "tmag"); R("R69", "100k", "3V3", "TMAG_INT", "tmag")

    # ======================================================================= buzzer (battery side), button, LED
    add("BZ1", "MLT-8530", ("Bench", "Buzzer_MLT-8530_8.5x8.5"), {1: "VBAT", 2: "BZ_N"}, "C94599", "MLT-8530", side="B", group="ui")
    add("D7", "1N4148W", SOD123, {1: "VBAT", 2: "BZ_N"}, "C81598", "1N4148W", group="ui"); R("R70", "22R", "BZ_N", "BZ_D", "ui")
    NMOS("Q19", "BZ_G", "GND", "BZ_D", "ui"); R("R71", "100R", "BUZ_PWM", "BZ_G", "ui"); R("R72", "100k", "BZ_G", "GND", "ui")
    add("SW1", "TS-1187A-B-A-B", ("Button_Switch_SMD", "SW_Push_1P1T_XKB_TS-1187A"), {1: "BTN_N", 2: "GND"}, "C318884", "TS-1187A-B-A-B", group="ui",
        note="1.5 mm = exactly the top height limit: membrane contact with zero gap; VERIFY")
    R("R73", "100k", "3V3", "BTN_N", "ui"); C("C42", "100nF", "BTN_N", "GND", "ui")
    add("LD1", "red status", ("LED_SMD", "LED_0603_1608Metric"), {1: "LD1_K", 2: "LED_A"}, "C2286", "KT-0603R", group="ui", note="red 0603 status LED")
    R("R74", "1k", "LED_ST", "LED_A", "ui"); R("R75", "100R", "LD1_K", "GND", "ui")

    # ======================================================================= test points (top side)
    tps = ["GND", "3V3", "VBAT", "VMOT", "PGATE", "LATCH_Q", "MCU_EN", "DOCKED_H", "ARM_CLK", "LATCH_CLR_N", "NRST", "STCK_DRV", "WIN", "HWA_FULL", "OC_OK", "INA_OUT", "VCHG"]
    for i, n in enumerate(tps):
        add("TP%d" % (i + 1), n, TP, {1: n}, bom=False, group="tp")
    for i in range(3):
        add("H%d" % (i + 1), "NPTH 1.2", ("Bench", "NPTH_1.2mm"), {}, bom=False, group="mech")
    return PARTS


def erc(parts):
    nets = {}
    for p in parts:
        for pad, n in p["pins"].items():
            if n:
                nets.setdefault(n, []).append((p["ref"], pad))
    problems = []
    for n, l in sorted(nets.items()):
        if len(l) < 2 and not n.startswith(("SWD", "XL")):
            problems.append("single-pin net %s %s" % (n, l))
    return nets, problems


def write_kicad_net(parts, nets, path):
    out = ['(export (version "E")', ' (design (source "netlist.py") (tool "OpenPatch v010"))', ' (components']
    for p in parts:
        out.append('  (comp (ref "%s") (value "%s") (footprint "%s:%s"))' % (p["ref"], p["value"], p["fp"][0], p["fp"][1]))
    out.append(" )"); out.append(" (nets")
    for i, (n, l) in enumerate(sorted(nets.items())):
        out.append('  (net (code "%d") (name "%s")' % (i + 1, n))
        for r, pad in l:
            out.append('   (node (ref "%s") (pin "%s"))' % (r, pad))
        out.append("  )")
    out.append(" )"); out.append(")")
    open(path, "w").write("\n".join(out))


if __name__ == "__main__":
    parts = build()
    nets, problems = erc(parts)
    json.dump(parts, open(os.path.join(OUT, "netlist.json"), "w"), indent=1)
    write_kicad_net(parts, nets, os.path.join(OUT, "v010.net"))
    print(len(parts), "parts,", len(nets), "nets;", sum(1 for p in parts if p["bom"]), "in BOM,", sum(1 for p in parts if p["dnp"]), "DNP")
    for p in problems:
        print("ERC:", p)
