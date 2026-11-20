#!/usr/bin/env python3
"""Regenerate the V010 footprints that the independent pin check (cup/PIN-CHECK.md) found wrong.

usage: python3 gen_fp_pincheck.py   (plain python, writes into ../footprints/V010.pretty)

Sources (all dimensions from vendor drawings read on 2026-11-20, no PDFs committed):
  USB_C_HRO_31_M_14   HRO TYPE-C-31-M-14 (LCSC C223907): 12 SMD pads in ONE row (merged power pads) + 4 shield THT slots + 2 peg holes, board notch 9.14 x 6.3 (+6.4 x 0.7)
                      origin = receptacle mouth at the board edge (centre), body toward +y (into the board), pads at y = 8.02
  SW_SKSCLAE010       ALPS SKSCLAE010 (LCSC C130445) side-push 4.85 x 3.55 x 1.25, actuator toward local -y
  LED_RGB_1615_4P     Yongyu SZYY1615RGB-B (C3029071) pads 0.65 x 0.65 at 1.0 x 1.45, pin 4 (anode) top-left, 1 top-right, 3 bottom-left, 2 bottom-right
  BZ_4020             Fusheng FUET-4020 (C391027) vendor land pattern 4.4 x 1.8, gap 0.9
  UFQFPN-20_3x3_P0.5  ST DS13866 UFQFPN20 has NO exposed pad: pad 21 removed
  HJ840               pad size stays 0.30 x 0.40 (HJ-840 manual b x a): 0.40 along the 0.65 pitch would leave 0.25 between pads, too little for a 0.12 track with 0.10 clearance
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
FP = os.path.join(HERE, "..", "footprints", "V010.pretty")


def w(name, text):
    open(os.path.join(FP, name + ".kicad_mod"), "w").write(text)


def line(x0, y0, x1, y1, layer="F.CrtYd", wd=0.05):
    return '  (fp_line (start %.3f %.3f) (end %.3f %.3f) (stroke (width %.2f) (type solid)) (layer "%s"))\n' % (x0, y0, x1, y1, wd, layer)


def rect(x0, y0, x1, y1, layer="F.CrtYd", wd=0.05):
    return line(x0, y0, x1, y0, layer, wd) + line(x1, y0, x1, y1, layer, wd) + line(x1, y1, x0, y1, layer, wd) + line(x0, y1, x0, y0, layer, wd)


def head(name, descr, ref_y=-3.0, val_y=3.0, attr="smd"):
    return ('(footprint "%s" (version 20240108) (generator "v010_gen")\n  (layer "F.Cu")\n  (descr "%s")\n  (attr %s)\n'
            '  (fp_text reference "REF**" (at 0 %.1f) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))\n'
            '  (fp_text value "%s" (at 0 %.1f) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))\n') % (name, descr, attr, ref_y, name, val_y)


def smd(num, x, y, sx, sy):
    return '  (pad "%s" smd rect (at %.3f %.3f) (size %.3f %.3f) (layers F.Cu F.Paste F.Mask))\n' % (num, x, y, sx, sy)


# ---------------------------------------------------------------- USB-C
t = head("USB_C_HRO_31_M_14",
         "HRO TYPE-C-31-M-14 (LCSC C223907) sink-board 16P receptacle, land pattern = LCSC/EasyEDA footprint (matches the HRO drawing: 12 pads in one row, A1/B12 B1/A12 A4/B9 B4/A9 merged). "
         "Origin = mouth at the board edge, centre; body toward +y; pad row at y 8.02; board notch x +-4.57 (+0.13 clearance) from the edge to y 6.3 and x +-3.2 to y 7.0 (Edge.Cuts in cupgeom.OUTLINE). "
         "Pad names are the merged HRO names; 4 x S = shield tabs (THT slots), 2 peg holes d0.6", ref_y=-1.5, val_y=10.0)
# EasyEDA (x, y) -> (-x, 5.08 - y)
sig = [("B1A12", 3.20, 0.55), ("B4A9", 2.45, 0.55), ("B5", 1.75, 0.30), ("A8", 1.25, 0.30), ("B6", 0.75, 0.30), ("A7", 0.25, 0.30), ("A6", -0.25, 0.30),
       ("B7", -0.75, 0.30), ("A5", -1.25, 0.30), ("B8", -1.75, 0.30), ("A4B9", -2.45, 0.55), ("A1B12", -3.20, 0.55)]
for nm, x, sx in sig:
    t += smd(nm, -x, 5.08 + 2.94, sx, 1.4)
for (x, y) in ((5.58, 2.94), (5.58, -1.66), (-5.58, 2.94), (-5.58, -1.66)):
    t += '  (pad "S" thru_hole oval (at %.3f %.3f) (size 0.8 1.9) (drill oval 0.5 1.65) (layers *.Cu *.Mask))\n' % (-x, 5.08 - y)
for x in (3.75, -3.75):
    t += '  (pad "" np_thru_hole circle (at %.3f %.3f) (size 0.6 0.6) (drill 0.6) (layers *.Cu *.Mask))\n' % (-x, 5.08 + 1.74)
t += rect(-4.57, 0.0, 4.57, 6.3, "F.SilkS", 0.12)
t += rect(-6.1, -0.3, 6.1, 9.0)
w("USB_C_HRO_31_M_14", t + ")\n")

# ---------------------------------------------------------------- side tact
t = head("SW_SKSCLAE010", "ALPS SKSCLAE010 (LCSC C130445) side-push tact 4.85 x 3.55 x 1.25; land pattern from the ALPS drawing (pads 1.4 x 0.9 at x +-1.8, y +-0.65); "
         "pins 1+2 are the pair on the actuator side (local -y), 3+4 the far pair; actuator faces local -y", ref_y=-2.6, val_y=2.6)
t += smd("1", -1.8, -0.65, 1.4, 0.9) + smd("2", 1.8, -0.65, 1.4, 0.9) + smd("3", -1.8, 0.65, 1.4, 0.9) + smd("4", 1.8, 0.65, 1.4, 0.9)
t += rect(-2.9, -2.1, 2.9, 2.0)
w("SW_SKSCLAE010", t + ")\n")

# ---------------------------------------------------------------- RGB LED
t = head("LED_RGB_1615_4P", "SZYY1615RGB-B (C3029071) RGB LED 1.6 x 1.5 mm, common anode = pin 4. Vendor drawing, top view: 4 top-left, 1 top-right, 3 bottom-left, 2 bottom-right; "
         "pads 0.65 x 0.65 at pitch 1.0 x 1.45 (vendor suggested pad 0.75 x 0.65, gaps 0.25 / 0.80)", ref_y=-1.9, val_y=1.9)
t += smd("4", -0.5, -0.725, 0.65, 0.65) + smd("1", 0.5, -0.725, 0.65, 0.65) + smd("3", -0.5, 0.725, 0.65, 0.65) + smd("2", 0.5, 0.725, 0.65, 0.65)
t += rect(-1.15, -1.2, 1.15, 1.2)
w("LED_RGB_1615_4P", t + ")\n")

# ---------------------------------------------------------------- sounder
t = head("BZ_4020", "Fusheng FUET-4020 (LCSC C391027) 4 x 4 x 2.0 mm SMD magnetic sounder; vendor land pattern: two pads 1.75 x 1.8, outer span 4.4, gap 0.9 (pad 1 = '+' side)",
         ref_y=-2.8, val_y=2.8)
t += smd("1", -1.325, 0, 1.75, 1.8) + smd("2", 1.325, 0, 1.75, 1.8)
t += rect(-2.3, -2.2, 2.3, 2.2)
w("BZ_4020", t + ")\n")

# ---------------------------------------------------------------- STM32 UFQFPN20: drop the (non-existent) exposed pad
p = os.path.join(FP, "UFQFPN-20_3x3_P0.5.kicad_mod")
s = open(p).read()
s = re.sub(r'  \(pad "21"[^\n]*\n', "", s)
s = s.replace("EP 1.6x1.6 (pin 21)", "no exposed pad (ST DS13866 table 69: 20 terminals only)")
open(p, "w").write(s)

# ---------------------------------------------------------------- HJ-840 pad size = LCSC footprint (0.44 along the 0.9 row pitch x 0.40 along the 0.65 column pitch)
p = os.path.join(FP, "HJ840.kicad_mod")
s = open(p).read()
s = s.replace("(size 0.40 0.44)", "(size 0.30 0.40)")
open(p, "w").write(s)

# ---------------------------------------------------------------- bare test pad 0.6 mm (no paste), DFN-6 for the 3-input AND
t = head("TP_Pad_D0.6", "bare round test pad D0.6 mm (copper + mask opening, no paste)", ref_y=-1.5, val_y=1.5)
t += '  (pad "1" smd circle (at 0 0) (size 0.60 0.60) (layers F.Cu F.Mask))\n' + rect(-0.45, -0.45, 0.45, 0.45)
w("TP_Pad_D0.6", t + ")\n")

t = head("UFDFN-6_1.45x1.0_P0.5", "EM74AUP1G11GM (LCSC C54929506) UFDFN-6 1.45 x 1.0 mm, pitch 0.5; pads from the LCSC footprint: 1 bottom-left, 2 bottom-mid, 3 bottom-right, 4 top-right, 5 top-mid, 6 top-left (top view)", ref_y=-1.3, val_y=1.3)
for n, x, y in ((1, -0.5, 0.36), (2, 0.0, 0.37), (3, 0.5, 0.37), (4, 0.5, -0.37), (5, 0.0, -0.37), (6, -0.5, -0.37)):
    t += smd(str(n), x, y, 0.30, 0.50)
t += rect(-0.85, -0.75, 0.85, 0.75)
w("UFDFN-6_1.45x1.0_P0.5", t + ")\n")
print("footprints regenerated")
