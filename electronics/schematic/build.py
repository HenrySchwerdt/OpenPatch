#!/usr/bin/env python
"""OpenPatch OP-100 - schematic as code (SKiDL, without KiCad libraries).

Usage:  ../.venv/bin/python build.py
Generates (in ../): openpatch-op100.net (KiCad netlist), netlist.json, bom.csv, erc.txt,
and replaces the pin table in ../README.md between the PINTABLE markers.

WARNING: The symbols are *functional* symbols. Pin numbers are real pin numbers only for the
nRF54L15 (QFN48) (source: Nordic PS table 'QFN48 (QFAA) pin assignments', via third-party
extraction - compare against PS v1.x!). For all other ICs 'num' = pin name;
map to the package ball/pin mapping of the datasheet before layout.
"""
import csv, json, os, re, sys
from collections import defaultdict
from skidl import Part, Pin, Net, SKIDL, TEMPLATE, ERC, generate_netlist, POWER, reset
import skidl
from parts_db import PARTS

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, ".."))
T = Pin.types
reset()

REG = {}  # ref -> dict(key, dnp)

def _pins(spec):
    """spec: list of 'name[:type]'; type p=passive i=in o=out b=bidir w=pwrin x=pwrout"""
    tmap = {"p": T.PASSIVE, "i": T.INPUT, "o": T.OUTPUT, "b": T.BIDIR, "w": T.PWRIN, "x": T.PWROUT, "t": T.TRISTATE}
    res = []
    for s in spec:
        a, b = s.split(":")
        if b in tmap: num = name = a; ty = b          # 'name:type' (num = name)
        else: num, name, ty = a, b, "p"                # 'num:name' (passiv)
        res.append(Pin(num=num, name=name, func=tmap[ty]))
    return res

def part(ref, key, pins, fp="", dnp=False, value=None):
    db = PARTS[key]
    p = Part(name=db["value"], tool=SKIDL, ref_prefix=ref.rstrip("0123456789"), pins=pins,
             footprint=fp or db["pkg"], value=value or db["value"], dest=skidl.NETLIST)
    p.ref = ref
    p.tag = ref  # stable tags for a reproducible netlist
    REG[ref] = dict(key=key, dnp=dnp)
    return p

def two(ref, key, fp, dnp=False):
    return part(ref, key, _pins(["1:p", "2:p"]), fp=fp, dnp=dnp)

SIG = {}
def sig(name):
    if name not in SIG: SIG[name] = Net(name)
    return SIG[name]
def L(name, *pins):
    n = sig(name)
    for p in pins: n += p
    return n
GND = Net("GND"); GND.drive = POWER
def N(name, power=False):
    n = Net(name)
    if power: n.drive = POWER
    return n
SYS = N("3V3", True); VBAT_RAW = N("VBAT_RAW", True); VBAT = N("VBAT", True)
VQI = N("VQI_5V", True); RECT = N("RECT", True); VMOT = N("VMOT", True); VPER = N("VPER_3V3", True)
CELL_N = N("CELL_N", True)

def cap(ref, key, a, b, fp, dnp=False):
    c = two(ref, key, fp, dnp); a += c[1]; b += c[2]; return c
def res(ref, key, a, b, dnp=False):
    r = two(ref, key, "Resistor_SMD:R_0402_1005Metric", dnp); a += r[1]; b += r[2]; return r
C0402 = "Capacitor_SMD:C_0402_1005Metric"; C0603 = "Capacitor_SMD:C_0603_1608Metric"; C0805 = "Capacitor_SMD:C_0805_2012Metric"

# ===================================================================================
# 1. Radio module Insight SiP ISP1807 (nRF52840 SiP, 8x8x1 mm LGA, integrated antenna + crystals)
#    Pin list: community symbol (flux.ai 'isp1807-lr-rs') - NOT verified against the Insight datasheet!
# ===================================================================================
ISP_PINS = {1:"VSS_1",2:"P0.09/NFC1",3:"P0.12/TRACEDATA1",4:"P0.10/NFC2",5:"P0.14",6:"P0.26",7:"VSS_2",8:"D+",9:"P0.16",10:"D-",
 11:"P0.21",12:"VBUS",13:"P0.18/RESET",14:"VSS_3",15:"P0.20",16:"VSS_4",17:"P0.22",18:"VSS_5",19:"P0.24",20:"OUT_ANT",21:"VSS_6",
 22:"OUT_MOD",23:"VSS_7",24:"VSS_8",25:"VSS_9",26:"VCC_NRF",27:"P0.17",28:"SWDIO",29:"P0.13",30:"SWDCLK",31:"VSS_10",32:"P0.08",
 33:"P0.07/TRACECLK",34:"P0.06",35:"P0.04/AIN2",36:"P0.05/AIN3",37:"P0.15",38:"P0.03/AIN1",39:"P0.27",40:"P0.02/AIN0",41:"P0.25",
 42:"P0.31/AIN7",43:"P0.11/TRACEDATA2",44:"P0.30/AIN6",45:"P0.19",46:"P0.29/AIN5",47:"P0.23",48:"P0.28/AIN4",49:"P1.02",50:"P1.06",
 51:"P1.15",52:"P1.14",53:"P1.13",54:"P1.05",55:"P1.08",56:"P1.09/TRACEDATA3",57:"P1.00/TRACEDATA0",58:"P1.03",59:"P1.12",60:"P1.10",
 61:"P1.11",62:"P1.07",63:"P1.04",64:"P1.01"}
for k in range(65, 79): ISP_PINS[k] = "NC_%d" % (k - 64)
MCU_PINS = ISP_PINS
mcu_pins = []
for n, nm in ISP_PINS.items():
    ty = T.PWRIN if nm.startswith(("VSS", "VCC")) else (T.PASSIVE if nm in ("OUT_ANT","OUT_MOD","VBUS","D+","D-") or nm.startswith("NC_") else T.BIDIR)
    mcu_pins.append(Pin(num=str(n), name=nm, func=ty))
U1 = part("U1", "isp1807", mcu_pins, fp="OpenPatch:ISP1807")
def mp(name): return U1[name]
for n, nm in ISP_PINS.items():
    if nm.startswith("VSS"): GND += U1[str(n)]
SYS += U1["VCC_NRF"]
for nm in ("VBUS", "D+", "D-") : U1[nm] += NC     # USB unused (check the VBUS handling in the datasheet)
for n, nm in ISP_PINS.items():
    if nm.startswith("NC_"): U1[str(n)] += NC
# Integrated antenna: OUT_MOD (RF output of the module) -> 0R -> OUT_ANT (antenna input). No pi network needed (Insight: already tuned).
RA = two("R90", "r_0r", "Resistor_SMD:R_0402_1005Metric"); U1["OUT_MOD"] += RA[1]; U1["OUT_ANT"] += RA[2]

# GPIO assignment (single source of truth for the README table). Pin = module pad name
GPIO = [  # (pin, signal, direction, note)
 ("P0.15","BTN_N","in","Button, wake from System OFF (GPIO SENSE)"),
 ("P0.17","QI_CHG_N","in","BQ51003 CHG (open drain), Qi field detected/charging, wake"),
 ("P0.13","BQ_INT","in","BQ25120A INT (open drain), wake"),
 ("P0.14","WDT_WAKE","in","TPL5010 WAKE pulse (GPIOTE interrupt)"),
 ("P0.16","LATCH_Q_MON","in","Read-back of the safety latch Q (MOT_ALLOW)"),
 ("P0.26","I2C_SDA","io","I2C (TWIM): BQ25120A (0x6A), TMAG5273 (0x35), 4.7k pull-up to 3V3"),
 ("P0.27","I2C_SCL","io","I2C"),
 ("P0.20","ARM_CLK","out","Clock input of the safety latch (rising edge = ARM)"),
 ("P0.22","KILL_N","out(od)","Open-drain, low = clear latch (MCU path 'motor off')"),
 ("P0.24","PER_EN","out","BQ25120A LSCTRL -> switch VPER (Hall sensors)"),
 ("P1.02","HALL_A","in","DRV5032 #1 -> QDEC A (counts independently of the CPU)"),
 ("P1.06","HALL_B","in","DRV5032 #2 -> QDEC B"),
 ("P0.04/AIN2","VMOT_SENSE","ain","SAADC AIN2: 1.5M/1M divider on VMOT (rail check, load switch test)"),
 ("P0.05/AIN3","VBAT_SENSE","ain","SAADC AIN3: 1.5M/1M divider on VBAT (redundancy to BQ25120A VBMON)"),
 ("P0.08","TMAG_INT","in","TMAG5273 INT (Data-Ready)"),
 ("P0.06","WDT_DONE","out","TPL5010 DONE (CPU-serviced only, NOT via PPI while the motor is armed!)"),
 ("P0.23","BUZ_PWM","out","Piezo driver (gate of Q1), PWM"),
 ("P0.19","MOT_STCK","out","STSPIN220 STCK/MODE3 (step clock, PWM/GPIOTE)"),
 ("P0.21","MOT_DIR","out","STSPIN220 DIR/MODE4"),
 ("P1.15","MOT_MODE1","out","STSPIN220 MODE1"),
 ("P1.14","MOT_MODE2","out","STSPIN220 MODE2"),
 ("P1.13","MOT_STBY","out","STSPIN220 STBY/RESET: high = driver active (MCU enable, 100k pull-down R72 -> fail-safe)"),
 ("P1.05","MOT_EN_FAULT","io(od)","STSPIN220 EN/FAULT: read fault / optionally disable by driving low (internal driver pull-up -> NOT fail-safe)"),
 ("P0.18/RESET","NRST","io","TPL5010 RSTn (watchdog reset) + TC2030 pad; P0.18 must be configured as RESET (UICR PSELRESET)"),
 ("SWDIO","SWDIO","io","SWD (J1 TC2030 Pad 2)"),
 ("SWDCLK","SWDCLK","in","SWD (J1 TC2030 Pad 4)"),
 ("OUT_MOD / OUT_ANT","RF_LINK","rf","0R R90 between module RF output and module antenna (integrated antenna)"),
 ("P0.09/NFC1","(free)","-","NC, NFC pad (unused)"),("P0.10/NFC2","(free)","-","NC, NFC pad"),
]
GPIO_FREE = ["P0.02/AIN0","P0.03/AIN1","P0.07/TRACECLK","P0.11/TRACEDATA2","P0.12/TRACEDATA1","P0.25","P0.28/AIN4","P0.29/AIN5","P0.30/AIN6","P0.31/AIN7",
             "P1.00/TRACEDATA0","P1.01","P1.03","P1.04","P1.07","P1.08","P1.09/TRACEDATA3","P1.10","P1.11","P1.12"]
for pin, sname, *_ in GPIO:
    if sname in ("(free)", "RF_LINK"): continue
    if pin in ("SWDIO", "SWDCLK"): L(sname, U1[pin]); continue
    if sname == "LATCH_Q_MON" or sname == "KILL_N": continue
    L(sname, U1[pin])
for pin in ("P0.09/NFC1", "P0.10/NFC2"): U1[pin] += NC
for pin in GPIO_FREE: U1[pin] += NC
# NFC/spare pins as test pads not needed; decoupling of VCC_NRF (module has an internal filter; check the datasheet recommendation)
cap("C1", "c_100n", SYS, GND, C0402); cap("C2", "c_4u7", SYS, GND, C0402)

# ===================================================================================
# 2. Qi receiver BQ51003 + coil
# ===================================================================================
U2 = part("U2", "bq51003", _pins(["AC1:p","AC2:p","BOOT1:p","BOOT2:p","CLAMP1:p","CLAMP2:p","COM1:p","COM2:p",
    "RECT:p","OUT:x","ILIM:p","FOD:p","TS_CTRL:p","CHG:o","EN1:i","EN2:i","AD:p","AD_EN:i","PGND1:w","PGND2:w"]),
    fp="OpenPatch:DSBGA-28_BQ51003_YFP")
AC1 = N("QI_AC1"); AC2 = N("QI_AC2"); COIL_A = N("QI_COIL_A")
AC1 += U2["AC1"]; AC2 += U2["AC2"]; GND += U2["PGND1"], U2["PGND2"]
LRX1 = part("LRX1", "coil_rx", _pins(["1:p","2:p"]), fp="OpenPatch:Qi_Coil_Pads")
COIL_A += LRX1[1]; AC2 += LRX1[2]
for i, ref in enumerate(("C20","C21","C22")): cap(ref, "c_cs_c0g", COIL_A, AC1, C0805)   # Cs 3x100n in parallel
cap("C23", "c_1n_c0g", AC1, AC2, C0402)                                                 # Cd
CC1 = N("QI_COM1"); CC2 = N("QI_COM2"); CC1 += U2["COM1"]; CC2 += U2["COM2"]
cap("C24", "c_22n_25v", AC1, CC1, C0402); cap("C25", "c_22n_25v", AC2, CC2, C0402)       # COM caps
CL1 = N("QI_CLAMP1"); CL2 = N("QI_CLAMP2"); CL1 += U2["CLAMP1"]; CL2 += U2["CLAMP2"]
cap("C26", "c_470n_25v", AC1, CL1, C0603); cap("C27", "c_470n_25v", AC2, CL2, C0603)    # clamp caps
BT1n = N("QI_BOOT1"); BT2n = N("QI_BOOT2"); BT1n += U2["BOOT1"]; BT2n += U2["BOOT2"]
cap("C28", "c_10n_25v", AC1, BT1n, C0402); cap("C29", "c_10n_25v", AC2, BT2n, C0402)    # boot caps
RECT += U2["RECT"]; cap("C30", "c_10u_25v", RECT, GND, C0603); cap("C31", "c_100n", RECT, GND, C0402)
VQI += U2["OUT"]; cap("C32", "c_10u_25v", VQI, GND, C0603); cap("C33", "c_1u", VQI, GND, C0402)
ILIM = N("QI_ILIM"); FOD = N("QI_FOD"); TSC = N("QI_TS_CTRL")
ILIM += U2["ILIM"]; FOD += U2["FOD"]; TSC += U2["TS_CTRL"]
res("R20", "r_3k16", ILIM, GND); res("R21", "r_200r", FOD, GND); res("R22", "r_10k", TSC, GND)
GND += U2["EN1"], U2["EN2"]; U2["AD"] += NC; U2["AD_EN"] += GND
L("QI_CHG_N", U2["CHG"]); res("R23", "r_100k", sig("QI_CHG_N"), SYS)

# ===================================================================================
# 3. Charger/PMIC BQ25120A
# ===================================================================================
U3 = part("U3", "bq25120a", _pins(["IN:w","BAT:p","SYS:x","SW:p","PGND:w","GND:w","TS:p","LS_LDO:x","VINLS:w","PG:o",
    "INT:o","MR:i","SCL:i","SDA:b","CD:i","LSCTRL:i"]), fp="OpenPatch:DSBGA-25_BQ25120A_YFP")
VQI += U3["IN"]; VBAT += U3["BAT"]; GND += U3["PGND"], U3["GND"]
SW = N("BQ_SW"); SW += U3["SW"]; L4 = two("L4", "l_2u2", "Inductor_SMD:L_0603_1608Metric"); SW += L4[1]; SYS += L4[2]
SYS += U3["SYS"]; SYS += U3["VINLS"]; VPER += U3["LS_LDO"]
cap("C40", "c_1u", VQI, GND, C0402); cap("C41", "c_10u", SYS, GND, C0603)
cap("C42", "c_10u", VBAT, GND, C0603); cap("C43", "c_1u", VPER, GND, C0402)
TS = N("BQ_TS"); TS += U3["TS"]; res("R30", "r_10k", TS, GND)   # fixed 10k instead of an NTC (Rev A)
U3["PG"] += NC
L("BQ_INT", U3["INT"]); res("R31", "r_100k", sig("BQ_INT"), SYS)
MR = N("BQ_MR"); MR += U3["MR"]; res("R32", "r_100k", MR, SYS)        # MR high = inactive
CD = N("BQ_CD"); CD += U3["CD"]; res("R33", "r_100k", CD, GND)        # CD low = charging allowed
L("PER_EN", U3["LSCTRL"]); res("R34", "r_100k", sig("PER_EN"), GND)
L("I2C_SCL", U3["SCL"]); L("I2C_SDA", U3["SDA"])
res("R35", "r_4k7", sig("I2C_SCL"), SYS); res("R36", "r_4k7", sig("I2C_SDA"), SYS)

# ===================================================================================
# 4. Battery pads, reverse-polarity protection, optional PCM protection (DNP), divider
# ===================================================================================
BT = part("BT1", "bat_pads", _pins(["1:PLUS", "2:MINUS"]), fp="OpenPatch:Pad_Pair_Battery_1.0x1.5")
Q2 = part("Q2", "dmg1013", _pins(["G:p", "S:p", "D:p"]), fp="Package_TO_SOT_SMD:SOT-323_SC-70")
VBAT_RAW += BT["PLUS"]; VBAT_RAW += Q2["D"]; VBAT += Q2["S"]; GND += Q2["G"]   # P-FET in the + rail
CELL_N += BT["MINUS"]
R_J0 = two("R40", "r_0r", "Resistor_SMD:R_0402_1005Metric"); CELL_N += R_J0[1]; GND += R_J0[2]  # jumper (PCM cell)
# Optional DW01A protection for a cell WITHOUT PCM: remove R40, populate U11/Q3/R41/R42/C44 (all DNP in Rev A)
U11 = part("U11", "dw01a", _pins(["OD:o","CS:i","OC:o","TD:p","VCC:w","GND:w"]), fp="Package_TO_SOT_SMD:SOT-23-6", dnp=True)
Q3 = part("Q3", "fs8205a", _pins(["S1:p","G1:i","G2:i","S2:p","D:p"]), fp="Package_SO:TSSOP-8_4.4x3mm_P0.65mm", dnp=True)
PCM_VCC = N("PCM_VCC", True); PCM_CS = N("PCM_CS"); PCM_MID = N("PCM_MID"); PCM_OD = N("PCM_OD"); PCM_OC = N("PCM_OC")
r41 = two("R41", "r_330r", "Resistor_SMD:R_0402_1005Metric", dnp=True); VBAT_RAW += r41[1]; PCM_VCC += r41[2]
PCM_VCC += U11["VCC"]; cap("C44", "c_100n", PCM_VCC, CELL_N, C0402, dnp=True); CELL_N += U11["GND"]
r42 = two("R42", "r_1k", "Resistor_SMD:R_0402_1005Metric", dnp=True); PCM_CS += r42[1]; PCM_MID += r42[2]; PCM_CS += U11["CS"]
PCM_OD += U11["OD"]; PCM_OC += U11["OC"]; PCM_OD += Q3["G1"]; PCM_OC += Q3["G2"]
CELL_N += Q3["S1"]; PCM_MID += Q3["D"]; GND += Q3["S2"]; U11["TD"] += NC
# Measurement divider VBAT -> P1.13
res("R43", "r_1m5", VBAT, sig("VBAT_SENSE")); res("R44", "r_1m", sig("VBAT_SENSE"), GND)
cap("C45", "c_100n", sig("VBAT_SENSE"), GND, C0402)

# ===================================================================================
# 5. SAFETY PATH: TPL5010 watchdog + latch + load switch (VMOT) + motor driver
# ===================================================================================
U5 = part("U5", "tpl5010", _pins(["VDD:w","GND:w","DELAY:p","DONE:i","WAKE:o","RSTN:o"]), fp="Package_TO_SOT_SMD:SOT-23-6")
SYS += U5["VDD"]; GND += U5["GND"]; cap("C50", "c_100n", SYS, GND, C0402)
DLY = N("WDT_DELAY"); DLY += U5["DELAY"]; res("R50", "r_dly", DLY, GND)
L("WDT_DONE", U5["DONE"]); L("WDT_WAKE", U5["WAKE"])
L("NRST", U5["RSTN"]); res("R51", "r_100k", sig("NRST"), SYS)  # RSTn open drain
# Latch: Q is set only by a CLK edge; CLR# (asynchronous, dominant) is driven by the watchdog RSTn AND the MCU KILL and the power-on RC
U6 = part("U6", "sn74aup1g74", _pins(["CLK:i","D:i","CLR_N:i","PRE_N:i","Q:o","Q_N:o","VCC:w","GND:w"]), fp="Package_SON:X2SON-8_1.4x1mm_P0.35mm")
SYS += U6["VCC"]; GND += U6["GND"]; SYS += U6["D"], U6["PRE_N"]; cap("C51", "c_100n", SYS, GND, C0402)
L("ARM_CLK", U6["CLK"]); U6["Q_N"] += NC
CLR = N("LATCH_CLR_N"); CLR += U6["CLR_N"]
res("R52", "r_100k", CLR, SYS); cap("C52", "c_100n", CLR, GND, C0402)    # Power-on: CLR# initially low -> Q=0
D2 = part("D2", "rb521", _pins(["A:p", "K:p"]), fp="Diode_SMD:D_SOD-523")  # NRST low -> CLR# low (anode = CLR#)
CLR += D2["A"]; L("NRST", D2["K"])
CLR += U1["P0.22"]                                                        # KILL_N: MCU open-drain pulls CLR# low
ALLOW = N("MOT_ALLOW"); ALLOW += U6["Q"], U1["P0.16"]
res("R53", "r_100k", ALLOW, GND)                                          # Default off on loss of SYS
# Load switch VBAT -> VMOT
U7 = part("U7", "tps22916c", _pins(["VIN:w","VOUT:x","ON:i","GND:w"]), fp="OpenPatch:DSBGA-4_TPS22916_YFP")
VBAT += U7["VIN"]; VMOT += U7["VOUT"]; ALLOW += U7["ON"]; GND += U7["GND"]
cap("C54", "c_1u", VBAT, GND, C0402)
# Motor driver STSPIN220
U4 = part("U4", "stspin220", _pins(["VS:w","GND:w","OUT1A:p","OUT1B:p","OUT2A:p","OUT2B:p","STCK_MODE3:i","DIR_MODE4:i",
    "MODE1:i","MODE2:i","STBY_RESET:i","EN_FAULT:b","REF:p"]), fp="Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm")
VMOT += U4["VS"]; GND += U4["GND"]; cap("C60", "c_10u", VMOT, GND, C0603); cap("C61", "c_100n", VMOT, GND, C0402)
for i, (mcu, pin) in enumerate([("MOT_STCK","STCK_MODE3"),("MOT_DIR","DIR_MODE4"),("MOT_MODE1","MODE1"),
                                ("MOT_MODE2","MODE2"),("MOT_STBY","STBY_RESET"),("MOT_EN_FAULT","EN_FAULT")]):
    d = N(mcu + "_DRV"); d += U4[pin]; res("R%d" % (62 + i), "r_10k", sig(mcu), d)   # series R against back-feeding when VMOT=0
    if mcu == "MOT_STBY": res("R72", "r_100k", d, GND)   # Default = standby (the MCU enable path is fail-safe, EN/FAULT is NOT)
REFN = N("MOT_REF"); REFN += U4["REF"]; res("R68", "r_ref", SYS, REFN); res("R69", "r_ref", REFN, GND)
MP = part("MP1", "motor_pads", _pins(["A1:p","A2:p","B1:p","B2:p"]), fp="OpenPatch:Pad_Motor_4x")
for a, b in (("A1","OUT1A"),("A2","OUT1B"),("B1","OUT2A"),("B2","OUT2B")):
    n = N("MOT_" + a); n += U4[b]; n += MP[a]
res("R70", "r_1m5", VMOT, sig("VMOT_SENSE")); res("R71", "r_1m", sig("VMOT_SENSE"), GND)
cap("C62", "c_100n", sig("VMOT_SENSE"), GND, C0402)

# ===================================================================================
# 6. Delivery verification: TMAG5273 (path A, I2C) + 2x DRV5032 (path B, QDEC)
# ===================================================================================
U8 = part("U8", "tmag5273", _pins(["VCC:w","GND:w","SCL:i","SDA:b","INT:o","ADDR_NC:p"]), fp="Package_TO_SOT_SMD:SOT-23-6")
VPER += U8["VCC"]; GND += U8["GND"]; L("I2C_SCL", U8["SCL"]); L("I2C_SDA", U8["SDA"]); L("TMAG_INT", U8["INT"])
U8["ADDR_NC"] += NC; cap("C70", "c_100n", VPER, GND, C0402)
for ref, cref, s in (("U9","C71","HALL_A"), ("U10","C72","HALL_B")):
    h = part(ref, "drv5032", _pins(["VCC:w","GND:w","OUT:o","NC:p"]), fp="OpenPatch:X2SON-4_1.1x1.4_DMR")
    VPER += h["VCC"]; GND += h["GND"]; L(s, h["OUT"]); h["NC"] += NC; cap(cref, "c_100n", VPER, GND, C0402)

# ===================================================================================
# 7. Buzzer, button, test/SWD pads
# ===================================================================================
BZ = part("BZ1", "piezo", _pins(["1:p","2:p"]), fp="OpenPatch:Piezo_9x9")
Q1 = part("Q1", "ao3400a", _pins(["G:i","S:p","D:p"]), fp="Package_TO_SOT_SMD:SOT-23")
BZD = N("BUZ_DRAIN"); VBAT += BZ["1"]; BZD += BZ["2"]; BZD += Q1["D"]; GND += Q1["S"]
BG = N("BUZ_GATE"); BG += Q1["G"]; res("R80", "r_10r", sig("BUZ_PWM"), BG); res("R81", "r_100k", BG, GND)
SW1 = part("SW1", "button", _pins(["1:p","2:p"]), fp="Button_Switch_SMD:SW_SPST_B3U-1000P")
BTN = N("BTN_RAW"); BTN += SW1["1"]; GND += SW1["2"]; res("R82", "r_1k", BTN, sig("BTN_N"))
D1 = part("D1", "tpd1e10b06", _pins(["A:p","K:p"]), fp="Diode_SMD:D_0402_1005Metric"); BTN += D1["A"]; GND += D1["K"]
def netbyname(nm): return next(n for n in default_circuit.nets if n.name == nm)
# SWD/programming: Tag-Connect TC2030-IDC-NL (pads only, no component; 3 alignment holes)
J1 = part("J1", "tc2030", _pins(["1:VTREF","2:SWDIO","3:NRESET","4:SWCLK","5:GND","6:SWO"]),
          fp="Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical")
SYS += J1["VTREF"]; sig("SWDIO"); SIG["SWDIO"] += J1["SWDIO"]; sig("NRST"); SIG["NRST"] += J1["NRESET"]
sig("SWDCLK"); SIG["SWDCLK"] += J1["SWCLK"]; GND += J1["GND"]; J1["SWO"] += NC
tp = {"TP1":SYS, "TP2":GND, "TP3":VBAT, "TP4":VMOT, "TP5":VQI, "TP6":sig("HALL_A"), "TP7":sig("HALL_B"),
      "TP8":sig("I2C_SDA"), "TP9":sig("I2C_SCL"), "TP10":netbyname("MOT_A1"), "TP11":netbyname("MOT_A2"),
      "TP12":netbyname("MOT_B1"), "TP13":netbyname("MOT_B2")}
for ref, net in tp.items():
    t = part(ref, "tp", _pins(["1:p"]), fp="TestPoint:TestPoint_Pad_D1.0mm"); net += t["1"]

# ===================================================================================
# Output: ERC, netlist, JSON, BOM
# ===================================================================================
def main():
    erc_path = os.path.join(OUT, "erc.txt")
    import io, contextlib
    ERC()
    generate_netlist(file_=os.path.join(OUT, "openpatch-op100.net"))
    comps, nets = {}, defaultdict(list)
    for p in default_circuit.parts:
        comps[p.ref] = dict(key=REG[p.ref]["key"], dnp=REG[p.ref]["dnp"], value=p.value, footprint=str(p.footprint))
    for n in default_circuit.nets:
        for pin in n.pins:
            nets[n.name].append("%s.%s(%s)" % (pin.part.ref, pin.num, pin.name))
    json.dump(dict(components=comps, nets=nets), open(os.path.join(OUT, "netlist.json"), "w"), indent=1, ensure_ascii=False)
    write_bom(comps)
    write_pintable()

def write_bom(comps):
    groups = defaultdict(list)
    for ref, c in comps.items():
        groups[(c["key"], c["dnp"])].append(ref)
    def natkey(r):
        m = re.match(r"([A-Za-z]+)(\d+)", r); return (m.group(1), int(m.group(2)))
    rows, total_board, total_dnp = [], 0.0, 0.0
    OFFBOARD = [("BAT1","lipo",1),("M1","motor_cheap",1),("MAG1","magnet",1)]  # not in the schematic, but relevant for the BOM
    for (key, dnp), refs in sorted(groups.items(), key=lambda kv: natkey(sorted(kv[1], key=natkey)[0])):
        d = PARTS[key]; refs = sorted(refs, key=natkey); q = len(refs)
        line = d["price"] * q
        if key in ("tp", "motor_pads", "bat_pads"): pass
        elif dnp: total_dnp += line
        else: total_board += line
        note = d["note"] + (" | DNP in Rev A" if dnp else "")
        note = (note + " | Price: " + ("web search basis" if d["price_src"] == "web" else "estimate")).strip(" |")
        rows.append([",".join(refs), d["value"], d["desc"], d["mfr"], d["mpn"], d["lcsc"] or "n/a (via DigiKey/Mouser through PCBWay)",
                     d["pkg"], q, "%.3f" % d["price"], "%.3f" % line, d["status"], note])
    for ref, key, q in OFFBOARD:
        d = PARTS[key]
        rows.append([ref, d["value"], d["desc"], d["mfr"], d["mpn"], d["lcsc"] or "n/a (hand assembly/direct purchase)", d["pkg"], q,
                     "%.3f" % d["price"], "%.3f" % (d["price"] * q), d["status"], d["note"] + " | OFFBOARD (not PCBWay SMT)"])
    with open(os.path.join(OUT, "bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ref","value","description","manufacturer","MPN","LCSC/PCBWay part no.","package","qty",
                    "unit_price_EUR_at_qty5","line_EUR_per_board","mpn_status(web|mem|unver)","notes"])
        w.writerows(rows)
    print("BOM rows: %d  components (incl. DNP/pads): %d  total/board (PCB parts + coil + piezo + button, without battery/motor/magnet): %.2f EUR  DNP: %.2f EUR"
          % (len(rows), len(comps), total_board, total_dnp))

def write_pintable():
    lines = ["| Module pad | Pad no. | Signal | Direction | Function |", "|---|---|---|---|---|"]
    num = {nm: n for n, nm in MCU_PINS.items()}
    for pin, s, d, note in GPIO:
        lines.append("| %s | %s | `%s` | %s | %s |" % (pin, num.get(pin, "22 / 20"), s, d, note))
    lines.append("| (free, NC) | %s | - | - | %d further GPIO pads deliberately left unconnected: %s |" % ("-", len(GPIO_FREE), ", ".join(GPIO_FREE)))
    block = "\n".join(lines)
    path = os.path.join(OUT, "README.md")
    if os.path.exists(path):
        txt = open(path).read()
        txt = re.sub(r"(<!-- PINTABLE:START -->).*?(<!-- PINTABLE:END -->)", lambda m: m.group(1) + "\n" + block + "\n" + m.group(2), txt, flags=re.S)
        open(path, "w").write(txt)
    open(os.path.join(OUT, "pin-assignment.md"), "w").write(block + "\n")

if __name__ == "__main__":
    main()
