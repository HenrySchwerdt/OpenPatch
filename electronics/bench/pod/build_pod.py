#!/usr/bin/env python3
"""Bench pod sensor board from mechanical/out/bench/OP-100.layout.json (KiCad python3).

Board frame of the layout: bx right, by up, viewed from the TOP (lid side, F.Cu). KiCad frame used here: x = bx, y = H - by.
Deviations from the layout (all documented in ../ORDER.md and the final report):
  * DRV5032 X2SON land pattern is 2.1 mm wide when rotated: HALL_A/B centres moved +0.2 mm in x (copper-to-edge >= 0.2 mm).
  * FFC connector is the real Hirose FH12-10S footprint (8.1 x 5.6 mm body + solder tabs +-5.05 mm), not 7.4 x 4.0 mm.
  * TMAG5273 is NOT fitted (10-pin FFC has no pins for I2C).
  * Rev A bench decision: the motor is NOT on this board (factory lead plugs into the controller): no motor contacts, no motor lines on the FFC.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import pcbnew
import benchlib as bl
from benchlib import Board, write_project, legalize, box_in_poly

LAY = json.load(open(os.path.join(HERE, "..", "..", "..", "mechanical", "out", "bench", "OP-100.layout.json")))
PCB = os.path.join(HERE, "pod.kicad_pcb")
bl.TRACK, bl.CLEAR, bl.VIA_D, bl.VIA_H = 0.2, 0.15, 0.5, 0.3

OUTL = [tuple(p) for p in LAY["board"]["outline_polygon_board_mm"]]
BX = LAY["board"]["bbox_mm"]
H = BX[1]
Y = lambda by: H - by                       # layout (y up) -> KiCad (y down)
poly = [(x, Y(y)) for x, y in OUTL]

R0402, C0402 = ("Resistor_SMD", "R_0402_1005Metric"), ("Capacitor_SMD", "C_0402_1005Metric")
X2SON = ("Bench", "DRV5032_X2SON-4_DMR0004B")
POWER = ("3V3",)


def build(with_tmag=True):
    b = Board("pod", BX[0], H, layers=2, outline=poly)
    b.poly_outline(poly)
    hs = {h["id"]: h for h in LAY["hall_sensors"]}
    
    # ---- dock hall (bottom, in the tower recess), TMAG5273 (bottom, mandatory), optional DRV5032 quadrature pair (top)
    cx, cy = hs["HALL_DOCK"]["center_board_mm"]
    b.add("U3", "DRV5032FADMR", X2SON, cx, Y(cy), 0, side="B", pins={"1": "3V3", "2": "GND", "4": "DOCK_N", "5": "GND"}, lcsc="C2152496", mpn="DRV5032FADMRR",
          note="threshold 3.9 mT switches about 4 mm before full latch; AJ variant C2152498 (9.5 mT) is footprint compatible but not in JLC stock")
    cx, cy = hs["HALL_3D"]["center_board_mm"]
    b.add("U4", "TMAG5273A1QDBVR", ("Package_TO_SOT_SMD", "SOT-23-6"), cx, Y(cy), 90, side="B",
          pins={"1": "I2C_SCL", "2": "GND", "3": "GND", "4": "3V3", "5": "TMAG_INT", "6": "I2C_SDA"}, lcsc="C3716049", mpn="TMAG5273A1QDBVR", note="mandatory angle sensor")
    for ref, hid, out in (("U1", "HALL_A", "HALL_A"), ("U2", "HALL_B", "HALL_B")):
        cx, cy = hs[hid]["center_board_mm"]
        b.add(ref, "DRV5032FADMR", X2SON, cx + 0.2, Y(cy), 90, side="F", pins={"1": "3V3", "2": "GND", "4": out, "5": "GND"}, lcsc="C2152496", mpn="DRV5032FADMRR",
              note="optional coarse quadrature channel (delete from BOM/CPL to leave unpopulated)")
    # ---- decoupling
    for ref, side, x, y in (("C1", "F", 2.65, Y(17.85)), ("C3", "F", 12.8, Y(4.4)), ("C4", "B", 3.6, Y(19.8))):
        b.add(ref, "100nF", C0402, x, y, 0 if ref == "C1" else 90, side=side, pins={"1": "3V3", "2": "GND"}, lcsc="C1525", mpn="CL05B104KO5NNNC")
    # ---- FFC connector, top side, cable exit +X (rot 90), pin 1 toward -by
    ffc = {"1": "GND", "2": "3V3", "3": "HALL_A", "4": "HALL_B", "5": "DOCK_N", "6": "I2C_SDA", "7": "I2C_SCL", "8": "TMAG_INT", "10": "GND", "MP": "GND"}
    b.add("J1", "FH12-10S-0.5SH(55)", ("Connector_FFC-FPC", "Hirose_FH12-10S-0.5SH_1x10-1MP_P0.50mm_Horizontal"), float(os.environ.get("J1X", 11.25)),
          Y(float(os.environ.get("J1Y", 18.7))), 90, pins=ffc, lcsc="C506791", mpn="FH12-10S-0.5SH(55)")
    # ---- holes
    for i, h in enumerate(LAY["mounting"]["locating_pins"]):
        b.add(f"H{i+1}", "NPTH 1.2", ("Bench", "NPTH_1.2mm"), h["center_board_mm"][0], Y(h["center_board_mm"][1]), bom=False, hide_ref=True)
    s = LAY["mounting"]["screw"]
    b.add("H3", "NPTH 1.4", ("Bench", "NPTH_1.4mm"), s["center_board_mm"][0], Y(s["center_board_mm"][1]), bom=False, hide_ref=True)
    b.text("TEST ONLY - NOT FOR HUMAN USE", 5.0, Y(1.2), 0.7, layer=pcbnew.B_SilkS, mirror=True, thick=0.1)
    b.text("OP-100 bench pod sensor rev A", 3.2, Y(13.0), 0.6, layer=pcbnew.B_SilkS, mirror=True, thick=0.09)

    # keep-outs from the layout (components): circles -> square boxes (per side handled by legalize on both sides: conservative)
    forb = []
    for c in LAY["keepout_circles"]:
        cx, cy = c["center_board_mm"]; r = c["d_mm"] / 2
        forb.append([cx - r, Y(cy) - r, cx + r, Y(cy) + r])
    fixed = ["U1", "U2", "U3", "U4", "J1"]
    inside = lambda bx: box_in_poly(bx, poly, 0.15)
    print("legalize moved", legalize(b, fixed, inside=inside, forbid=forb, step=0.2, rmax=8.0))
    b.rules(power_nets=POWER, power_w=0.25, track=0.2)
    bds = b.b.GetDesignSettings(); bds.m_CopperEdgeClearance = bl.MM(0.2); bds.m_MinClearance = bl.MM(0.15)
    b.save(PCB)
    json.dump(b.parts, open(os.path.join(HERE, "parts.json"), "w"), indent=1)
    write_project(os.path.join(HERE, "pod.kicad_pro"), POWER, 0.25, 0.2, edge=0.2, clear=0.15)
    print("pod board written", len(b.parts), "parts")


if __name__ == "__main__":
    build(with_tmag=True)
