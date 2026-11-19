#!/usr/bin/env python3
"""Bench controller board (E73 nRF52840 module + STSPIN220 + hardware interlock). Run with KiCad's python3.

usage: build_controller.py build        -> controller.kicad_pcb (placed, nets assigned, no routing)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import pcbnew
from benchlib import OX as bl_OX, OY as bl_OY
from benchlib import Board, write_project, legalize, place_labels, tidy_refs

W, H = 44.0, 56.0
PCB = os.path.join(HERE, "controller.kicad_pcb")

R0402, R0603 = ("Resistor_SMD", "R_0402_1005Metric"), ("Resistor_SMD", "R_0603_1608Metric")
C0402, C0603 = ("Capacitor_SMD", "C_0402_1005Metric"), ("Capacitor_SMD", "C_0603_1608Metric")
SOT23, SOT235, SOT236 = [("Package_TO_SOT_SMD", n) for n in ("SOT-23", "SOT-23-5", "SOT-23-6")]
TP = ("TestPoint", "TestPoint_Pad_D1.0mm")

# value -> (LCSC, MPN)
RV = {"100k": ("C25741", "0402WGF1003TCE"), "10k": ("C25744", "0402WGF1002TCE"), "4.7k": ("C25900", "0402WGF4701TCE"),
      "5.1k": ("C25905", "0402WGF5101TCE"), "3.3k": ("C25890", "0402WGF3301TCE"), "1k": ("C11702", "0402WGF1001TCE"),
      "100R": ("C25076", "0402WGF1000TCE"), "22k": ("C25768", "0402WGF2202TCE"), "47k": ("C25792", "0402WGF4702TCE"),
      "22R": ("C25092", "0402WGF220JTCE")}
CV = {"100nF": ("C1525", "CL05B104KO5NNNC"), "1uF": ("C52923", "CL05A105KA5NQNC"), "4.7uF": ("C23733", "CL05A475MP5NRNC"),
      "15pF": ("C1548", "0402CG150J500NT"), "10nF": ("C15195", "CL05B103KB5NNNC")}
CV6 = {"10uF": ("C19702", "CL10A106KP8NNNC"), "10uF 25V": ("C96446", "CL10A106MA8NRNC")}


POWER = ("VBUS", "3V3", "VMOT", "VMOT_RAW", "MOT_A1", "MOT_A2", "MOT_B1", "MOT_B2")
POS = {
    "C22": (8.5, 33.3, 0), "C23": (10.9, 35.6, 0), "C24": (6.1, 35.6, 0),
    "U1": (22.0, 9.3, 180), "C4": (21.0, 20.8, 0), "C5": (23.6, 20.8, 0), "Y1": (18.9, 23.0, 0), "C6": (17.0, 25.0, 0), "C7": (20.8, 25.0, 0),
    "J1": (22.0, 52.0, 0), "U3": (30.5, 47.2, 0), "R1": (33.5, 46.2, 0), "R2": (33.5, 47.8, 0), "U2": (29.5, 53.2, 0), "C1": (27.8, 50.4, 0),
    "C2": (32.6, 53.4, 0), "LD1": (35.5, 51.2, 0), "R3": (35.5, 53.2, 0),
    "J2": (38.0, 19.8, 0), "J3": (37.6, 27.4, 0), "R4": (32.6, 21.2, 0), "SW1": (36.0, 11.0, 0), "R5": (33.6, 13.8, 0),
    "LD2": (31.5, 16.0, 0), "R6": (34.4, 16.0, 0), "R7": (29.9, 17.6, 0), "LD3": (31.5, 17.6, 0), "R8": (34.4, 17.6, 0), "R9": (29.9, 16.0, 0),
    "Q5": (23.0, 27.5, 0), "Q8": (26.5, 27.5, 0), "Q6": (30.0, 27.5, 0), "Q7": (30.0, 32.5, 0), "R40": (33.0, 33.2, 0), "R41": (33.0, 31.6, 0),
    "R42": (23.0, 30.5, 0), "R43": (26.5, 30.5, 0), "D2": (30.5, 44.0, 0), "R46": (26.5, 41.5, 0), "C29": (28.4, 41.5, 0),
    "J4": (39.6, 41.0, 90), "BZ1": (10.0, 12.0, 0), "J5": (4.2, 41.0, -90), "J6": (4.2, 49.0, -90), "R50": (27.0, 21.8, 0), "R51": (27.0, 23.4, 0), "R52": (33.0, 36.6, 0), "R53": (33.0, 38.2, 0),
    "R35": (29.0, 50.2, 0), "R36": (31.0, 50.2, 0),
}
def build():
    b = Board("controller", W, H, corner=1.5)
    b.pos = POS
    b.rounded_outline()
    tps_labels = []

    def R(ref, val, a, c, x, y, rot=0):
        b.add(ref, val, R0402, x, y, rot, pins={"1": a, "2": c}, lcsc=RV[val][0], mpn=RV[val][1])

    def C(ref, val, a, c, x, y, rot=0):
        b.add(ref, val, C0402, x, y, rot, pins={"1": a, "2": c}, lcsc=CV[val][0], mpn=CV[val][1])

    def C6(ref, val, a, c, x, y, rot=0):
        b.add(ref, val, C0603, x, y, rot, pins={"1": a, "2": c}, lcsc=CV6[val][0], mpn=CV6[val][1])

    def tp(ref, net, x, y, label=None, lx=0.0, ly=1.4):
        b.add(ref, net, TP, x, y, pins={"1": net}, bom=False, hide_ref=True)
        tps_labels.append((label or net, ref))

    # ------------------------------------------------------------------ MCU module (antenna end at the top edge)
    MX, MY = 22.0, 9.3
    u1 = {"19": "3V3", "5": "GND", "21": "GND", "24": "GND", "26": "NRST", "37": "SWDIO", "39": "SWDCLK",
          "11": "XL1", "13": "XL2", "1": "MOT_STBY", "2": "MOT_MODE2", "3": "DOCK_N", "4": "WDT_DONE", "6": "MOT_MODE1",
          "7": "I_SENSE", "8": "BUZ_PWM", "9": "UART_TX", "10": "UART_RX", "12": "I2C_SDA", "14": "I2C_SCL",
          "15": "VBUS_SENSE", "16": "TMAG_INT",  "17": "MOT_EN_FAULT", "18": "VMOT_SENSE", "20": "MOT_STCK", "22": "MOT_DIR",
          "28": "BTN_N", "30": "WDT_WAKE", "32": "ARM_CLK", "33": "MOT_ALLOW", "34": "LATCH_CLR_N", "35": "MCU_EN",
          "36": "LED_ST_G", "38": "HALL_A", "40": "HALL_B", "42": "LED_ALM_G"}
    b.add("U1", "E73-2G4M08S1CX", ("Bench", "Ebyte_E73-2G4M08S1C_13x18"), MX, MY, 180, pins=u1, lcsc="C2764963", mpn="E73-2G4M08S1CX",
          note="nRF52840 module, IPEX antenna connector (C variant C356849 has ceramic antenna, same footprint)")
    b.keepout(MX - 7.0, 0.0, MX + 7.0, 3.6, "ANT_KEEPOUT")          # no copper under the antenna end of the module
    C("C4", "100nF", "3V3", "GND", 18.0, 20.2)
    C("C5", "4.7uF", "3V3", "GND", 19.8, 20.2)
    b.add("Y1", "32.768kHz 12.5pF", ("Crystal", "Crystal_SMD_3215-2Pin_3.2x1.5mm"), 25.6, 21.0, 0, pins={"1": "XL1", "2": "XL2"},
          lcsc="C32346", mpn="Q13FC13500004")
    C("C6", "15pF", "XL1", "GND", 23.4, 22.6)
    C("C7", "15pF", "XL2", "GND", 28.0, 22.6)

    # ------------------------------------------------------------------ USB-C power input + 3V3 LDO
    b.add("J1", "TYPE-C-31-M-12 (power only)", ("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12"), 22.0, 54.4, 0,
          pins={"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND", "A4": "VBUS", "A9": "VBUS", "B4": "VBUS",
                "B9": "VBUS", "A5": "CC1", "B5": "CC2"}, lcsc="C165948", mpn="TYPE-C-31-M-12")
    b.add("U3", "USBLC6-2SC6", SOT236, 29.0, 46.5, 0, pins={"1": "CC1", "6": "CC1", "3": "CC2", "4": "CC2", "2": "GND", "5": "VBUS"},
          lcsc="C7519", mpn="USBLC6-2SC6")
    R("R1", "5.1k", "CC1", "GND", 33.0, 46.5)
    R("R2", "5.1k", "CC2", "GND", 33.0, 48.0)
    b.add("U2", "XC6206P332MR-G", SOT23, 35.0, 52.0, 0, pins={"1": "GND", "2": "3V3", "3": "VBUS"}, lcsc="C5446", mpn="XC6206P332MR-G",
          note="Torex pinout 1 GND, 2 OUT, 3 IN (differs from clones)")
    C("C1", "1uF", "VBUS", "GND", 37.5, 50.6)
    C6("C2", "10uF", "3V3", "GND", 38.5, 53.2)
    b.add("LD1", "green 3V3", ("LED_SMD", "LED_0805_2012Metric"), 40.2, 49.0, 90, pins={"1": "LD1_K", "2": "3V3"}, lcsc="C2297", mpn="KT-0805G")
    R("R3", "100R", "LD1_K", "GND", 40.2, 46.8, 90)

    # ------------------------------------------------------------------ SWD / reset / button / LEDs
    b.add("J2", "TC2030-IDC-NL", ("Connector", "Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical"), 37.0, 21.0, 0,
          pins={"1": "3V3", "2": "SWDIO", "3": "NRST", "4": "SWDCLK", "5": "GND"}, bom=False)
    b.add("J3", "SWD 2x5 1.27 mm", ("Connector_PinHeader_1.27mm", "PinHeader_2x05_P1.27mm_Vertical_SMD"), 39.5, 31.0, 0,
          pins={"1": "3V3", "2": "SWDIO", "3": "GND", "4": "SWDCLK", "5": "GND", "9": "GND", "10": "NRST"},
          lcsc="C41376037", mpn="PZ1.27-2x5P TP")
    R("R4", "100k", "NRST", "3V3", 33.0, 19.6)
    b.add("SW1", "TS-1187A-B-A-B", ("Button_Switch_SMD", "SW_Push_1P1T_XKB_TS-1187A"), 38.0, 8.0, 0, pins={"1": "BTN_N", "2": "GND"},
          lcsc="C318884", mpn="TS-1187A-B-A-B")
    R("R5", "100k", "BTN_N", "3V3", 33.2, 12.4)
    b.add("LD2", "green status", ("LED_SMD", "LED_0805_2012Metric"), 31.5, 14.8, 0, pins={"1": "LD2_K", "2": "LED_ST_R"}, lcsc="C2297", mpn="KT-0805G")
    R("R6", "100R", "LED_ST_G", "LED_ST_R", 34.2, 14.8)
    R("R7", "100R", "LD2_K", "GND", 29.4, 14.8)
    b.add("LD3", "red alarm", ("LED_SMD", "LED_0603_1608Metric"), 31.5, 17.0, 0, pins={"1": "LD3_K", "2": "LED_ALM_R"}, lcsc="C2286", mpn="KT-0603R")
    R("R8", "1k", "LED_ALM_G", "LED_ALM_R", 34.2, 17.0)
    R("R9", "100R", "LD3_K", "GND", 29.4, 17.0)

    # ------------------------------------------------------------------ buzzer
    b.add("BZ1", "MLT-8530", ("Bench", "Buzzer_MLT-8530_8.5x8.5"), 9.5, 11.0, 0, pins={"1": "3V3", "2": "BZ_N"}, lcsc="C94599", mpn="MLT-8530")
    b.add("D1", "1N4148W", ("Diode_SMD", "D_SOD-123"), 5.0, 17.5, 0, pins={"1": "3V3", "2": "BZ_N"}, lcsc="C81598", mpn="1N4148W")
    R("R10", "22R", "BZ_N", "BZ_D", 5.0, 19.3)
    b.add("Q9", "2N7002", SOT23, 8.0, 19.0, 0, pins={"1": "BZ_G", "2": "GND", "3": "BZ_D"}, lcsc="C8545", mpn="2N7002")
    R("R11", "100R", "BUZ_PWM", "BZ_G", 11.2, 18.0)
    R("R12", "100k", "BZ_G", "GND", 11.2, 19.6)

    # ------------------------------------------------------------------ STSPIN220 + current sense
    b.add("U4", "STSPIN220", ("Package_DFN_QFN", "QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm"), 8.5, 29.0, 0,
          pins={"1": "MOT_DIR", "2": "MOT_STCK", "3": "MOT_A1", "4": "SNSA", "5": "MOT_A2", "6": "VMOT", "7": "GND", "8": "MOT_B2",
                "9": "SNSB", "10": "MOT_B1", "11": "MOT_REF", "12": "TOFF", "13": "MOT_EN_FAULT", "14": "MOT_STBY", "15": "MOT_MODE2",
                "16": "MOT_MODE1", "17": "GND"}, lcsc="C2150516", mpn="STSPIN220")
    b.add("R20", "1.0R", R0603, 5.0, 33.0, 0, pins={"1": "SNSA", "2": "GND"}, lcsc="C174300", mpn="RS-03L1R00FT")
    b.add("R21", "1.0R", R0603, 12.0, 33.0, 0, pins={"1": "SNSB", "2": "GND"}, lcsc="C174300", mpn="RS-03L1R00FT")
    R("R22", "47k", "TOFF", "GND", 11.8, 26.2)
    R("R23", "100k", "3V3", "MOT_REF", 12.8, 28.0)
    R("R24", "5.1k", "MOT_REF", "GND", 12.8, 29.6)
    C("C20", "100nF", "MOT_REF", "GND", 14.2, 28.8)
    R("R25", "100k", "MOT_STBY", "GND", 5.0, 25.5)
    R("R26", "10k", "3V3", "MOT_EN_FAULT", 14.0, 31.0)
    C("C21", "10nF", "MOT_EN_FAULT", "GND", 15.6, 31.0)
    C6("C22", "10uF 25V", "VMOT", "GND", 5.5, 36.0)
    C6("C23", "10uF 25V", "VMOT", "GND", 8.3, 36.0)
    C("C24", "100nF", "VMOT", "GND", 11.0, 36.0)

    # ------------------------------------------------------------------ motor supply switch (interlock) + shunt
    b.add("Q4", "AO3401A", SOT23, 8.0, 46.0, 0, pins={"1": "PGATE", "2": "VBUS", "3": "VMOT_RAW"}, lcsc="C15127", mpn="AO3401A")
    R("R30", "100k", "VBUS", "PGATE", 11.5, 46.0)
    b.add("R31", "1.0R", R0603, 8.0, 41.5, 0, pins={"1": "VMOT_RAW", "2": "VMOT"}, lcsc="C174300", mpn="RS-03L1R00FT")
    b.add("R39", "1.0R", R0603, 8.0, 43.4, 0, pins={"1": "VMOT_RAW", "2": "VMOT"}, lcsc="C174300", mpn="RS-03L1R00FT", note="parallel with R31: 0.5 ohm shunt")
    b.add("U7", "INA180A1IDBVR", SOT235, 17.0, 40.0, 0, pins={"1": "INA_OUT", "2": "GND", "3": "VMOT_RAW", "4": "VMOT", "5": "3V3"},
          lcsc="C122228", mpn="INA180A1IDBVR", note="Pinout A: 1 OUT, 2 GND, 3 IN+, 4 IN-, 5 VS")
    C("C25", "100nF", "3V3", "GND", 17.0, 37.6)
    R("R32", "1k", "INA_OUT", "I_SENSE", 20.0, 40.0)
    C("C26", "100nF", "I_SENSE", "GND", 21.8, 40.0)
    R("R33", "100k", "VMOT", "VMOT_SENSE", 4.0, 40.0)
    R("R34", "100k", "VMOT_SENSE", "GND", 4.0, 41.6)
    R("R35", "100k", "VBUS", "VBUS_SENSE", 27.0, 51.0)
    R("R36", "100k", "VBUS_SENSE", "GND", 27.0, 52.6)
    b.add("LD4", "red VMOT on", ("LED_SMD", "LED_0603_1608Metric"), 15.0, 52.0, 0, pins={"1": "LD4_K", "2": "LD4_A"}, lcsc="C2286", mpn="KT-0603R")
    R("R37", "1k", "VMOT", "LD4_A", 15.0, 50.4)
    R("R38", "100R", "LD4_K", "GND", 15.0, 53.6)

    # chain of three series pull-down FETs: PGATE - Q5 - Q8 - Q6 - GND
    b.add("Q5", "2N7002", SOT23, 24.0, 28.0, 0, pins={"1": "MOT_ALLOW", "2": "PG_MID1", "3": "PGATE"}, lcsc="C8545", mpn="2N7002")
    b.add("Q8", "2N7002", SOT23, 27.5, 28.0, 0, pins={"1": "MCU_EN", "2": "PG_MID2", "3": "PG_MID1"}, lcsc="C8545", mpn="2N7002")
    b.add("Q6", "2N7002", SOT23, 31.0, 28.0, 0, pins={"1": "DOCKED_H", "2": "GND", "3": "PG_MID2"}, lcsc="C8545", mpn="2N7002")
    b.add("Q7", "2N7002", SOT23, 31.0, 33.0, 0, pins={"1": "DOCK_N", "2": "GND", "3": "DOCKED_H"}, lcsc="C8545", mpn="2N7002")
    R("R40", "100k", "3V3", "DOCKED_H", 34.2, 33.0)
    R("R41", "100k", "3V3", "DOCK_N", 34.2, 31.2)
    R("R42", "100k", "MOT_ALLOW", "GND", 24.0, 31.0)
    R("R43", "100k", "MCU_EN", "GND", 27.5, 31.0)

    # ------------------------------------------------------------------ watchdog + latch
    b.add("U5", "TPL5010DDCR", SOT236, 22.0, 35.0, 0, pins={"1": "3V3", "2": "GND", "3": "WDT_DELAY", "4": "WDT_DONE", "5": "WDT_WAKE", "6": "NRST"},
          lcsc="C473912", mpn="TPL5010DDCR")
    R("R44", "10k", "WDT_DELAY", "GND", 19.0, 33.0)
    R("R45", "22k", "WDT_DELAY", "GND", 19.0, 34.6)
    C("C27", "100nF", "3V3", "GND", 22.0, 32.6)
    b.add("U6", "SN74AUP1G74DCUR", ("Package_SO", "VSSOP-8_2.3x2mm_P0.5mm"), 28.0, 38.5, 0,
          pins={"1": "ARM_CLK", "2": "3V3", "3": None, "4": "GND", "5": "MOT_ALLOW", "6": "LATCH_CLR_N", "7": "3V3", "8": "3V3"},
          lcsc="C140267", mpn="SN74AUP1G74DCUR")
    C("C28", "100nF", "3V3", "GND", 31.0, 38.0)
    R("R46", "100k", "LATCH_CLR_N", "3V3", 28.0, 41.5)
    C("C29", "100nF", "LATCH_CLR_N", "GND", 30.0, 41.5)
    b.add("D2", "SS14", ("Diode_SMD", "D_SMA"), 36.5, 38.5, 90, pins={"1": "NRST", "2": "LATCH_CLR_N"}, lcsc="C2480", mpn="SS14")

    # ------------------------------------------------------------------ FFC to the pod
    ffc = {"1": "GND", "2": "3V3", "3": "HALL_A", "4": "HALL_B", "5": "DOCK_N", "6": "I2C_SDA", "7": "I2C_SCL", "8": "TMAG_INT", "10": "GND"}
    b.add("J4", "FH12-10S-0.5SH(55)", ("Connector_FFC-FPC", "Hirose_FH12-10S-0.5SH_1x10-1MP_P0.50mm_Horizontal"), 39.6, 41.0, 90, pins=ffc,
          lcsc="C506791", mpn="FH12-10S-0.5SH(55)")
    # motor: factory lead of NFP-608-26.45-SGM, 4-pin 1.25 mm plug; pin order B-, A-, B+, A+ (UNVERIFIED connector family: PicoBlade/GH)
    mot = {"1": "MOT_B2", "2": "MOT_A2", "3": "MOT_B1", "4": "MOT_A1"}
    b.add("J5", "PicoBlade 4P (A1251WR-S-4P)", ("Connector_Molex", "Molex_PicoBlade_53261-0471_1x04-1MP_P1.25mm_Horizontal"), 4.2, 41.0, -90, pins=mot,
          lcsc="C225113", mpn="A1251WR-S-4P-LCP", note="Molex 53261-0471 compatible; confirm the plug on the first motor")
    b.add("J6", "JST GH SM04B-GHS-TB (DNP alt.)", ("Connector_JST", "JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal"), 4.2, 49.0, -90, pins=mot,
          bom=False, note="DNP alternative footprint for a JST GH plug, parallel to J5")
    b.text("MOTOR  B- A- B+ A+", 2.0, 36.5, 0.8, thick=0.12, rot=0)
    R("R50", "4.7k", "3V3", "I2C_SDA", 27.5, 17.0)
    R("R51", "4.7k", "3V3", "I2C_SCL", 27.5, 18.6)
    R("R52", "100k", "3V3", "HALL_A", 36.0, 36.0)
    R("R53", "100k", "3V3", "HALL_B", 36.0, 37.6)

    # ------------------------------------------------------------------ test points
    tps = [("TP1", "GND", 2.0, 22.0), ("TP2", "3V3", 17.0, 24.0), ("TP3", "VBUS", 17.5, 50.0), ("TP4", "VMOT", 3.0, 44.0),
           ("TP5", "PGATE", 12.0, 49.5), ("TP6", "MOT_ALLOW", 23.0, 25.0), ("TP7", "MCU_EN", 27.0, 25.0), ("TP8", "DOCKED_H", 34.5, 26.0),
           ("TP9", "DOCK_N", 30.0, 25.0), ("TP10", "LATCH_CLR_N", 35.5, 41.5), ("TP11", "ARM_CLK", 25.0, 43.5), ("TP12", "WDT_WAKE", 19.0, 37.5),
           ("TP13", "WDT_DONE", 16.0, 36.0), ("TP14", "NRST", 33.5, 23.5), ("TP15", "MOT_A1", 3.0, 28.0), ("TP16", "MOT_A2", 3.0, 31.0),
           ("TP17", "MOT_B1", 14.0, 24.0), ("TP18", "MOT_B2", 3.0, 34.0), ("TP19", "MOT_STCK", 2.0, 15.0), ("TP20", "MOT_DIR", 2.0, 18.0),
           ("TP21", "MOT_STBY", 2.0, 25.0), ("TP22", "I_SENSE", 23.5, 43.0), ("TP23", "HALL_A", 41.5, 36.0), ("TP24", "HALL_B", 41.5, 38.5),
           ("TP28", "I2C_SDA", 12.0, 21.5), ("TP29", "I2C_SCL", 14.0, 22.5), ("TP25", "UART_TX", 14.0, 20.5), ("TP26", "UART_RX", 16.5, 22.5), ("TP27", "GND", 41.0, 14.0)]
    for ref, net, x, y in tps:
        tp(ref, net, x, y)

    # ------------------------------------------------------------------ mechanical, silk
    for i, (x, y) in enumerate(((3.5, 3.5), (W - 3.5, 3.5), (3.5, H - 3.5), (W - 3.5, H - 3.5))):
        b.add(f"H{i+1}", "M3", ("MountingHole", "MountingHole_3.2mm_M3"), x, y, bom=False, hide_ref=True)
    for i, t in enumerate(("TEST ONLY", "NOT FOR", "HUMAN USE")):
        b.text(t, 33.6, 1.5 + 1.25 * i, 0.9, thick=0.14)
    b.text("TEST ONLY - NOT FOR HUMAN USE", 22.0, 20.0, 1.2, layer=pcbnew.B_SilkS, mirror=True, thick=0.18)
    b.text("OpenPatch bench controller rev A (DISCLAIMER.md)", 22.0, 22.5, 0.9, layer=pcbnew.B_SilkS, mirror=True, thick=0.14)

    fixed = ["U1", "J1", "J2", "J3", "J4", "J5", "J6", "SW1", "BZ1", "U4"]
    print("legalize moved", legalize(b, fixed, extra_boxes=[[15.0, 0.0, 29.0, 3.7]]))
    tidy_refs(b)
    fps = {f.GetReference(): f for f in b.b.GetFootprints()}
    import pcbnew as _p
    lab = [(t, _p.ToMM(fps[r].GetPosition().x) - bl_OX, _p.ToMM(fps[r].GetPosition().y) - bl_OY) for t, r in tps_labels]
    dropped = place_labels(b, lab, 0.7, avoid=[[15.0, 0.0, 29.0, 3.7], [30.5, 0.5, 38.5, 5.2], [11.0, 19.0, 33.0, 21.5]],
                          back_avoid=[[5.0, 18.5, 39.0, 21.5], [5.0, 21.5, 39.0, 24.0]])
    print("test point labels dropped (front and back full):", dropped)
    b.rules(power_nets=POWER, power_w=0.3)
    b.save(PCB)
    json.dump(b.parts, open(os.path.join(HERE, "parts.json"), "w"), indent=1)
    write_project(os.path.join(HERE, "controller.kicad_pro"), POWER)
    print("controller board written:", PCB, len(b.parts), "parts")


if __name__ == "__main__":
    build()
