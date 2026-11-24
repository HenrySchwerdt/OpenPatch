#!/usr/bin/env python3
"""Hand placement of the CART main board (style of cup/manual_place.py).  usage: kpy place_cart.py  -> placement.json, prints rule violations.

Floorplan (board frame of cartgeom.py: bx west -> east, by north edge -> south edge), 57.0 x 10.6:
  bx 0..4.5    wire end: motor pads MP1-4 + cell pads SP1/SP2 (own column, 1.0 mm gaps, pre-order review H6) on top;
               TMAG strip TL1-4 + adapter-lock pigtail LK1-3 on the bottom (one column), I2C pull-ups
  bx 4.5..17   motor power chain on top: cell P-FET Q1, boost L1 / U8 / CB1 + FB divider, load switch U20 (+ ILIM, C60), drivers U7A / U7B,
               VMOT bulk C21, VMOT sense divider; bottom (<= 1.2 mm, variant B motor below): driver bypass caps, final AND U34, R90
  bx 17..35    supervisor U30, TPL5010 U5, latch U6, AND U32, XOR U33, AND3 U36 + their pull resistors (bottom), supervisor SWD pads
               TPS1-3, LED, charger U3; bottom east of bx 28.2 (cell below, 3 mm free): side switch SW1 (north edge, bx 31.0) and sounder BZ1
  bx 35..47    USB-C in its notch, CC resistors + VBUS cap south of the pad row, ESD UU1 and nRF SWD recovery pads TPR1-4 underneath
  bx 47..57    HJ-840 (row A = antenna at the east end, only row A inside the 3 mm antenna zone), nothing on the underside under it
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bench", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "cup"))
sys.path.insert(0, HERE)
import pcbnew  # noqa: E402
import place_cup as PC  # noqa: E402  (footprint loading, heights, transforms)
import cartgeom as G  # noqa: E402

T = pcbnew.ToMM
F, B = "F", "B"
EDGE = 0.30
HEIGHT_OVERRIDE = {"U5": 1.1, "BZ1": 2.5}      # TPL5010 DDC 1.1 max; FUET-4020 2.5 per the JLC listing (pre-order review L7)

FIXED = {
    "U1": (*G.U1_POS, 270, F),                 # row A (antenna) east
    "JU1": (G.USB_X, G.USB_MOUTH, 0, F),       # origin = mouth, 0.9 north of the edge (housing wall inner face)
    "SW1": (G.SW1_X, 2.03, 0, B),              # actuator tip (local y -2.03) on the north edge
}
# wire end: motor pads 0.7 x 1.6 at 1.35 pitch (long side along x), cell pads 1.0 x 1.6 in their own column, 1.0 mm copper gaps
for k in range(4):
    FIXED["MP%d" % (k + 1)] = (1.5, 1.0 + 1.35 * k, 90, F)
FIXED["SP1"] = (3.6, 6.9, 90, F)
FIXED["SP2"] = (3.6, 8.9, 90, F)
for k, ref in enumerate(("TL1", "TL2", "TL3", "TL4", "LK1", "LK2", "LK3")):
    FIXED[ref] = (1.5, 1.0 + 1.15 * k, 90, B)
for k in range(4):
    FIXED["TPR%d" % (k + 1)] = (43.0 + 1.27 * k, 9.8, 0, B)          # 1.27 mm pogo pitch: SWDIO, SWDCLK, GND, 3V3

PLACE = {
    # ---- power chain, top
    "L1": (5.8, 1.7, 0, F), "U8": (9.1, 1.4, 0, F), "CB1": (11.6, 2.1, 90, F), "R55": (13.2, 1.4, 90, F), "R56": (13.2, 3.5, 90, F),
    "U20": (15.2, 1.7, 0, F), "C60": (15.2, 3.7, 0, F), "R91": (17.2, 1.4, 90, F),
    "U7A": (6.3, 4.6, 0, F), "U7B": (9.6, 5.4, 0, F), "C21": (13.0, 5.5, 0, F),
    "Q1": (6.8, 8.5, 0, F), "C5": (9.6, 8.7, 90, F), "R57": (11.6, 8.3, 90, F), "R58": (12.8, 8.3, 90, F),
    # ---- power chain, bottom (<= 1.2 mm)
    "C71": (9.0, 2.0, 0, B), "C61": (6.3, 3.8, 0, B), "C19": (6.3, 5.4, 0, B), "C62": (9.6, 4.2, 0, B), "C20": (9.6, 5.6, 0, B),
    "U34": (15.5, 5.5, 0, B), "R90": (15.5, 7.4, 0, B), "RI1": (3.6, 1.3, 90, B), "RI2": (3.6, 3.4, 90, B),
    # ---- supervisor block, top
    "U30": (21.0, 5.0, 0, F), "U32": (20.5, 1.8, 0, F), "U33": (21.0, 8.6, 0, F), "U36": (17.8, 8.6, 0, F),
    "U5": (25.5, 2.2, 0, F), "R26": (25.5, 4.6, 0, F), "U6": (25.9, 7.3, 0, F),
    "TPS1": (18.3, 1.0, 0, F), "TPS2": (18.3, 2.3, 0, F), "TPS3": (18.3, 3.6, 0, F),
    "LD1": (30.0, 2.0, 0, F), "R74": (29.6, 4.0, 0, F), "D6": (32.5, 5.4, 0, F), "U3": (32.5, 8.4, 0, F), "R3": (29.4, 9.6, 0, F),
    # ---- supervisor block, bottom
    "C50": (21.0, 2.5, 0, B), "C81": (24.0, 8.0, 0, B), "C82": (25.5, 3.0, 0, B),
    "R29": (19.0, 7.0, 90, B), "R82": (18.0, 4.0, 90, B), "R16": (19.0, 9.2, 90, B), "R18": (17.0, 9.2, 90, B), "RDK": (22.5, 7.0, 90, B),
    "RNR": (23.5, 5.0, 90, B), "R92": (17.0, 2.0, 90, B),
    "RBZ": (27.0, 6.9, 0, B), "QBA": (27.0, 9.1, 0, B), "RDA": (24.0, 9.6, 0, B), "BZ1": (31.5, 7.9, 0, B),
    # ---- USB strip
    "RU2": (G.USB_X - 1.7, 8.9, 0, F), "RU1": (G.USB_X + 1.3, 8.9, 0, F), "CU1": (45.0, 9.3, 0, F), "UU1": (40.8, 9.1, 0, B),
    # ---- module
    "C70": (49.5, 9.5, 0, F),
}
# underside obstacles of the USB-C receptacle: the four plated shield slots (both faces); the top uses the library courtyard
JU1_BOTTOM = [(G.USB_X - 6.14, -1.3, G.USB_X - 5.0, 7.0), (G.USB_X + 5.0, -1.3, G.USB_X + 6.14, 7.0)]


def geometry(parts: list) -> dict:
    geo = PC.geometry(parts)
    for p in parts:
        f = PC.load_fp(*p["fp"])
        f.BuildCourtyardCaches()
        c = f.GetCourtyard(pcbnew.F_CrtYd)
        if c.OutlineCount():
            bb = c.BBox()
            geo[p["ref"]]["crt"] = [T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom())]
        geo[p["ref"]]["h"] = HEIGHT_OVERRIDE.get(p["ref"], geo[p["ref"]]["h"])
    return geo


def check(parts: list, geo: dict, pl: dict) -> list:
    errs = []
    box = {r: PC.box_of(geo[r], pl[r]) for r in pl}
    u1 = box["U1"]
    for r, bb in box.items():
        side = pl[r][3]
        if r not in ("JU1", "SW1") and not G.inside(bb, G.OUTLINE, EDGE):
            errs.append("%s outside the outline / edge margin %s" % (r, [round(v, 2) for v in bb]))
        if r != "U1" and bb[2] > G.ANT[0] and bb[0] < G.ANT[2]:
            errs.append("%s in the antenna zone" % r)
        if side == B and r != "U1" and bb[2] > u1[0] and bb[0] < u1[2] and bb[3] > u1[1] and bb[1] < u1[3]:
            errs.append("%s on the underside under the HJ-840" % r)
        h = geo[r]["h"]
        if side == F and h > G.TOP_LIMIT + 1e-6:
            errs.append("%s %.2f mm > top limit" % (r, h))
        if side == B and h > G.bottom_limit(bb[0], bb[2]) + 1e-6:
            errs.append("%s %.2f mm > bottom limit %.2f" % (r, h, G.bottom_limit(bb[0], bb[2])))
        for x, y, d in G.SUPPORT_PADS:
            if PC_dist(x, y, bb) < d / 2:
                errs.append("%s on the support pad (%.1f, %.1f)" % (r, x, y))
        lr = G.LID_RIB
        if side == F and bb[2] > lr[0] and bb[0] < lr[2] and bb[3] > lr[1] and bb[1] < lr[3]:
            errs.append("%s on the lid-rib pad" % r)
        if side == B and r != "JU1":
            for q in JU1_BOTTOM:
                if bb[2] > q[0] and bb[0] < q[2] and bb[3] > q[1] and bb[1] < q[3]:
                    errs.append("%s on the JU1 shield slots (bottom)" % r)
    refs = sorted(box)
    for i, a in enumerate(refs):
        for c in refs[i + 1:]:
            if pl[a][3] != pl[c][3] and "JU1" not in (a, c):
                continue
            if "JU1" in (a, c) and pl[a][3] == B or "JU1" in (a, c) and pl[c][3] == B:
                continue
            p, q = box[a], box[c]
            if p[2] > q[0] + 1e-6 and q[2] > p[0] + 1e-6 and p[3] > q[1] + 1e-6 and q[3] > p[1] + 1e-6:
                errs.append("overlap %s %s" % (a, c))
    return errs


def PC_dist(x: float, y: float, bb: list) -> float:
    return math.hypot(max(bb[0] - x, 0, x - bb[2]), max(bb[1] - y, 0, y - bb[3]))


def main() -> None:
    parts = json.load(open(os.path.join(HERE, "netlist_cart.json")))
    geo = geometry(parts)
    pl = dict(FIXED)
    pl.update(PLACE)
    missing = [p["ref"] for p in parts if p["ref"] not in pl]
    extra = [r for r in pl if r not in geo]
    errs = check(parts, geo, pl)
    for e in errs:
        print("RULE", e)
    print("missing", missing, "extra", extra, "violations", len(errs))
    json.dump({r: list(v) for r, v in pl.items()}, open(os.path.join(HERE, "placement.json"), "w"), indent=1)
    if missing or extra:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
