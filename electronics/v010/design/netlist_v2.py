#!/usr/bin/env python3
"""v0.1.0 split design (decisions 2026-11-19): MAIN (radio, STSPIN220, boost, supervisor MCU, safety legs, charger) + USB-CHARGE + SENSOR boards.

Derived from netlist.py (monolith, kept as the reference): applies the supervisor-MCU variant, populates the 5 V boost, replaces the charge pads by USB-C and
splits the board into three with 10-pin FFC cables.  Writes netlist_main.json, netlist_sensor.json, netlist_usb.json (+ netlist_all.json) in ..
Run: python3 netlist_v2.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import netlist as nl
from netlist import R, C, NMOS, dec, add, R0402, R0603, C0402, C0603, SOT23, SOT235, SOT236, SOD123

OUT = os.path.join(HERE, "..")
FFC10 = ("Connector_FFC-FPC", "Hirose_FH12-10S-0.5SH_1x10-1MP_P0.50mm_Horizontal")

REMOVE = set("""U5 R26 R27 U6 C14 R28 C15 D2 U10 C16 R30 R31 C17 D1 R32 R33 U13 R59 R60 C33 U14 U15 Q18 R61 U16 U17 U18 U19
C34 C35 C36 C37 Q5 R17 D3 PAD1 PAD2 R45 U10T U4A U4B C41 R69 BZ1_none""".split())
SENSOR_KEEP = ("U10T", "U4A", "U4B", "C41", "R69")


def build():
    parts = nl.build()
    sensor = [p for p in parts if p["ref"] in SENSOR_KEEP]
    parts[:] = [p for p in parts if p["ref"] not in REMOVE]
    nl.PARTS = parts
    P = {p["ref"]: p for p in parts}

    def setpins(ref, **kw):
        for pad, net in kw.items():
            P[ref]["pins"][pad.lstrip("p")] = net

    # ---- U1 pin changes: supervisor link, USB, VBUS sense
    setpins("U1", p4="SUP_RXD", p30="SUP_TXD", p33="SUP_OK", p6=None, p9="VBUS_SENSE", p34=None, p27="VBUS_P", p29="USB_DM", p31="USB_DP")
    # ---- safety chain: latch leg Q5 gone; chain PGATE-R11-Q8-Q13-(Q6|Q10)
    P["Q8"]["pins"].update({"3": "CH_TOP"})
    # ---- second series switch Q15 owned by the supervisor: own gate net PGATE2
    P["Q15"]["pins"]["1"] = "PGATE2"
    P["Q15"]["note"] = "second series switch, gate owned by the supervisor MCU through QS"
    R("R83", "100k", "VMOT_A", "PGATE2", "sw"); add("C60", "100nF", C0402, {1: "PGATE2", 2: "VMOT_A"}, "C1525", "CL05B104KO5NNNC", group="sw")
    NMOS("QS", "SUP_PERMIT", "GND", "QS_D", "sw", note="supervisor leg: pulls PGATE2 low only while SUP_PERMIT is high"); R("R84", "10k", "PGATE2", "QS_D", "sw")
    R("R82", "100k", "SUP_PERMIT", "GND", "sw")
    NMOS("Q17B", "PGATE2", "GND", "BLD", "sw", note="bleeder also when only the supervisor has cut")
    # ---- supervisor MCU STM32C011F4P6 (TSSOP-20), own clock (HSI), own firmware (INTERLOCK.md section H)
    add("U30", "STM32C011F4P6", ("Package_SO", "TSSOP-20_4.4x6.5mm_P0.65mm"),
        {1: "SUP_PB7_MCUEN", 4: "3V3", 5: "GND", 6: "SUP_NRST", 7: "ARM_CLK", 8: "STCK_MCU", 9: "DIR_REV", 10: "OC_OK", 11: "SUP_STCK_EN", 12: "SUP_PERMIT",
         13: "SUP_OK", 14: "NRST", 16: "SUP_TXD", 17: "SUP_RXD", 18: "SUP_SWDIO", 19: "SUP_SWDCLK", 20: "SUP_PB6_DOCKED"}, "C5452432", "STM32C011F4P6", group="sup",
        note="independent supervisor: window watchdog (UART challenge/response), HW-A step budget (EXTI count of STCK_MCU), OC/permit state machine; pin names PB7 MCU_EN, PA0 ARM, PA1 STCK, PA2 DIR_REV, PA3 OC_OK, PA4 STCK_EN, PA5 PERMIT, PA6 OK, PA7 NRST_MAIN, PA11 TX, PA12 RX, PB6 DOCKED_H")
    # monitored inputs share nets with the main safety nets through 0 R-free direct connections (inputs only)
    P.update({p["ref"]: p for p in parts})
    P["U30"]["pins"]["1"] = "MCU_EN"; P["U30"]["pins"]["20"] = "DOCKED_H"
    dec("C50", "3V3", "sup"); add("C51", "1uF", C0402, {1: "3V3", 2: "GND"}, "C52923", "CL05A105KA5NQNC", group="sup")
    R("R80", "100k", "SUP_NRST", "3V3", "sup"); R("R81", "100k", "SUP_STCK_EN", "GND", "sup")
    add("J4", "SUP SWD pads", ("TestPoint", "TestPoint_Pad_D1.0mm"), {1: "SUP_SWDIO"}, bom=False, group="sup", note="SWD pad")
    add("J5", "SUP SWCLK pad", ("TestPoint", "TestPoint_Pad_D1.0mm"), {1: "SUP_SWDCLK"}, bom=False, group="sup")
    add("J6", "SUP NRST pad", ("TestPoint", "TestPoint_Pad_D1.0mm"), {1: "SUP_NRST"}, bom=False, group="sup")
    nl.gate("U31", "AND", "STCK_MCU", "SUP_STCK_EN", "STCK_DRV", "sup"); dec("C52", "3V3", "sup")
    # ---- boost populated (5 V): R45 removed above, parts become real
    P.update({p["ref"]: p for p in parts})
    for ref in ("U8", "L1", "D6", "R55", "R56", "C31"):
        P[ref]["dnp"] = False; P[ref]["bom"] = True; P[ref]["side"] = "F"
    P["L1"].update(value="CKCS4018-4.7uH", lcsc="C354574", mpn="CKCS4018-4.7uH/M", note="boost inductor 4.7 uH 4x4x1.8, Isat to be checked >= 1.5 A (VERIFY)")
    P["R55"].update(value="220k", lcsc="C25767", mpn="0402WGF2203TCE"); P["R56"].update(value="30k", lcsc="C25776", mpn="0402WGF3002TCE")
    P["U8"]["note"] = "MT3608 5 V boost (EN tied to switched VMOT_RAW); VERIFY stability/efficiency; Zhaowei 3 V motor option: depopulate, fit R45"
    P["C31"].update(value="10uF"); P["D6"]["side"] = "F"
    add("R45", "0R DNP (boost bypass)", R0603, {1: "VMOT_RAW", 2: "VMOT_PRE"}, dnp=True, group="oc", note="fit instead of the boost for a 3 V motor (spec 4b)")
    add("DZ1", "BZT52C6V2 (VMOT overvoltage clamp)", SOD123, {1: "VMOT_PRE", 2: "GND"}, "C27091", "LBZT52C6V2T1G", group="oc", note="clamps a boost overvoltage (MT3608 has no OVP); cathode (pad 1) to VMOT_PRE")
    # ---- USB: VBUS sense divider and charger input
    R("R85", "100k", "VBUS_P", "VBUS_SENSE", "pwr"); R("R86", "100k", "VBUS_SENSE", "GND", "pwr")
    P["R2"]["pins"]["1"] = "VBUS_P"
    # ---- FFC connectors on MAIN
    add("J3", "FH12-10S-0.5SH(55) to SENSOR", FFC10, {1: "GND", 2: "3V3", 3: "I2C_SDA", 4: "I2C_SCL", 5: "DOCK_N", 6: "DOCK_NB", 7: "TMAG_INT", 8: "GND", 9: "GND"},
        "C506791", "FH12-10S-0.5SH(55)", group="ffc", note="2.0 mm tall (CAD note): <= 1.0 mm class connector is an open point")
    add("J7", "FH12-10S-0.5SH(55) to USB", FFC10, {1: "VBUS_P", 2: "GND", 3: "USB_DP", 4: "USB_DM", 5: "GND", 6: "VBUS_P"}, "C506791", "FH12-10S-0.5SH(55)", group="ffc")
    main = [dict(p, board="MAIN") for p in parts]
    # ---- test pads (>= 0.8 mm, labelled in silk): the board must be debuggable on its own
    main[:] = [p for p in main if not p["ref"].startswith("TP") and p["ref"] != "J2"]
    tps = [("GND", 2), ("3V3", 1), ("VBAT", 1), ("VMOT", 1), ("VMOT_RAW", 1), ("PGATE", 1), ("PGATE2", 1), ("INA_OUT", 1), ("ARM_CLK", 1), ("SUP_PERMIT", 1), ("SUP_STCK_EN", 1),
           ("SUP_OK", 1), ("SUP_TXD", 1), ("SUP_RXD", 1), ("OC_OK", 1), ("OC_CMP", 1), ("VBUS_P", 1), ("NRST", 1), ("STCK_DRV", 1), ("MCU_EN", 1), ("DOCKED_H", 1),
           ("SWDIO", 1), ("SWDCLK", 1), ("I2C_SDA", 1), ("I2C_SCL", 1), ("PGATE_MON", 1)]
    k = 0
    for n, cnt in tps:
        for _ in range(cnt):
            k += 1
            main.append(dict(ref="TP%d" % k, value=n, fp=list(nl.TP), pins={"1": n}, lcsc=None, mpn=None, side="F", bom=False, dnp=False, note="test pad", group="tp", board="MAIN"))
    # ---- SENSOR board
    sens = [dict(p, board="SENSOR", group="sensor") for p in sensor]
    for p in sens:
        if p["ref"] == "R69":
            p["pins"] = {"1": "3V3", "2": "TMAG_INT"}
    sens.append(dict(ref="J3S", value="FH12-10S-0.5SH(55)", fp=list(FFC10), pins={"1": "GND", "2": "3V3", "3": "I2C_SDA", "4": "I2C_SCL", "5": "DOCK_N", "6": "DOCK_NB", "7": "TMAG_INT", "8": "GND", "9": "GND"},
                     lcsc="C506791", mpn="FH12-10S-0.5SH(55)", side="F", bom=True, dnp=False, note="FFC to MAIN", group="sensor", board="SENSOR"))
    # ---- USB-CHARGE board
    usb = []

    def u(ref, value, fp, pins, lcsc=None, mpn=None, side="F", bom=True, note=""):
        usb.append(dict(ref=ref, value=value, fp=list(fp), pins={str(k): v for k, v in pins.items()}, lcsc=lcsc, mpn=mpn, side=side, bom=bom, dnp=False, note=note, group="usb", board="USB"))

    u("JU1", "USB-C receptacle (proxy: TYPE-C-31-M-12; IPX7 part to be confirmed)", ("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12"),
      {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND", "A4": "VBUS_R", "A9": "VBUS_R", "B4": "VBUS_R", "B9": "VBUS_R", "A5": "CC1", "B5": "CC2",
       "A6": "UDP_C", "B6": "UDP_C", "A7": "UDM_C", "B7": "UDM_C"}, "C165948", "TYPE-C-31-M-12", note="placeholder for the IPX7 gasketed receptacle (vendor confirmation needed); XKB U262-161N-4BVC11 C319148 / G-Switch GT-USB-7010 candidates")
    u("DU1", "SMF5.0A TVS", ("Diode_SMD", "D_SOD-123F"), {1: "VBUS_R", 2: "GND"}, "C193402", "SMF5.0A")
    u("RU1", "5.1k", R0402, {1: "CC1", 2: "GND"}, "C25905", "0402WGF5101TCE"); u("RU2", "5.1k", R0402, {1: "CC2", 2: "GND"}, "C25905", "0402WGF5101TCE")
    u("UU1", "USBLC6-2SC6", SOT236, {1: "UDP_C", 2: "GND", 3: "UDM_C", 4: "UDM_C", 5: "VBUS_R", 6: "UDP_C"}, "C7519", "USBLC6-2SC6", note="ESD on D+/D-")
    u("QU1", "AO3401A (ideal diode / reverse protect)", SOT23, {1: "VBUS_G", 2: "VBUS_P", 3: "VBUS_R"}, "C15127", "AO3401A", note="P-FET, body diode orientation: source = output side VBUS_P; gate low through RU3")
    u("RU3", "100k", R0402, {1: "VBUS_G", 2: "GND"}, "C25741", "0402WGF1003TCE")
    u("CU1", "10uF", C0603, {1: "VBUS_P", 2: "GND"}, "C19702", "CL10A106KP8NNNC"); u("CU2", "1uF", C0402, {1: "VBUS_R", 2: "GND"}, "C52923", "CL05A105KA5NQNC")
    u("DU2", "B5819W SL (OV clamp not fitted)", SOD123, {1: "VBUS_P", 2: "VBUS_P"}, bom=False, note="n/a") if False else None
    u("J3U", "FH12-10S-0.5SH(55)", FFC10, {1: "VBUS_P", 2: "GND", 3: "UDP_C", 4: "UDM_C", 5: "GND", 6: "VBUS_P"}, "C506791", "FH12-10S-0.5SH(55)", note="FFC to MAIN")
    # USB D+/D- go straight through to the cable
    return main, sens, usb


def rename_usb(main, usb):
    # MAIN sees USB_DP/USB_DM, the USB board UDP_C/UDM_C: same cable conductors
    return


def erc(parts, name):
    nets = {}
    for p in parts:
        for pad, n in p["pins"].items():
            if n:
                nets.setdefault(n, []).append((p["ref"], pad))
    bad = ["single-pin net %s %s" % (n, l) for n, l in sorted(nets.items()) if len(l) < 2]
    return nets, bad


if __name__ == "__main__":
    main, sens, usb = build()
    for name, parts in (("main", main), ("sensor", sens), ("usb", usb)):
        nets, bad = erc(parts, name)
        json.dump(parts, open(os.path.join(OUT, "netlist_%s.json" % name), "w"), indent=1)
        print(name, len(parts), "parts", len(nets), "nets", "BOM", sum(1 for p in parts if p["bom"]))
        for b in bad:
            print("  ERC:", b)
