#!/usr/bin/env python3
"""Hand placement of the cart A v2 main board (style of ../place_cart.py).  usage: kpy place_cart_a.py -> placement.json + rule check.

TEST PROJECT, water only. Positions are written in PUMP coordinates (x, y) and converted to the board frame (cartgeom_a.b); rotations and
sides follow ../place_cart.py (bottom parts: local x mirrored, then rotated; build_cart_a.py checks every pad against this transform).

Floorplan (pump x 32.6-62.8 rear -> front, y 19.35 near -> 36.3 far, + tongue / antenna wing):
  rear-far corner   TMAG5273 U10 (top, on the magnet axis y 33.435) + I2C pull-ups
  x 37.4-46.6 far   USB-C JU1 in its notch (moved to x 42.0, cartgeom_a), CC resistors, VBUS cap; ESD UU1 below (bottom)
  x 33-52 near/mid  supervisor U30, TPL5010 U5, latch U6, gates U32/U33/U34/U36, pulls, supervisor SWD pads TPS1-3, LED LD1 (39, 22.05),
                    button SW1 (46.5, 22.05), charger U3; bottom: nRF SWD pogo pads TPR1-4, pulls, debounce RLK / CLK
  x 48-54 bottom    motor header J2 (PicoBlade, opening toward -x; the plug lies under the board in the free zone PLUG_ZONE)
  x 52-62.8 top     power chain: cell P-FET Q1, boost L1 / U8 / CB1, load switch U20, drivers U7A / U7B, VMOT caps, VMOT sense divider
  bottom front      sounder BZ1 (57, 26, floor slots) + its driver, cell IDC J3 (front edge), lock switch SW2 on the tongue
  far front corner  HJ-840 U1 (row A = antenna toward the far wall, in the wing), nothing on the bottom under it
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "bench", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "cup"))
sys.path.insert(0, HERE)
import pcbnew  # noqa: E402
import place_cup as PC  # noqa: E402  (footprint loading, heights, transforms)
import cartgeom_a as G  # noqa: E402

T = pcbnew.ToMM
F, B = "F", "B"
EDGE = 0.30
CARTA = os.path.join(HERE, "CARTA.pretty")
_load = PC.load_fp


def load_fp(lib: str, nm: str):
    if lib == "CARTA":
        return pcbnew.FootprintLoad(CARTA, nm)
    return _load(lib, nm)


PC.load_fp = load_fp
HEIGHT = {"U5": 1.1, "BZ1": 2.5, "SW1": 1.4, "SW2": 1.0, "J2": 3.4, "J3": 4.6, "U10": 1.45, "U3": 1.45, "L1": 1.2, "U1": 1.0}
CRT_LIB = ("JU1", "SW1", "SW2", "J3", "U1", "BZ1")
# J2 PicoBlade: courtyard is 12 mm (MP tabs + 0.55); placement box = MP tabs / rear pads + 0.07, body front face at local y +2.9
J2_BOX = [-5.55, -3.27, 5.55, 2.95]       # use the library courtyard as the placement box


def P(x: float, y: float, rot: float, side: str) -> tuple:
    bx, by = G.b(x, y)
    return (bx, by, rot, side)


FIXED = {
    "U1": P(*G.U1_C, 0, F),                                   # row A (antenna) toward +y (far wall)
    "JU1": P(G.USB_X, G.USB_MOUTH_Y, 0, F),                   # origin = receptacle mouth, 0.5 beyond the far edge
    "SW1": P(*G.SW1_XY, 0, F),
    "LD1": P(*G.LED_XY, 0, F),
    "U10": P(34.47, 33.38, 90, F),                            # pads 0.22 from the notch edge x 33.0, sensor 0.055 below the magnet axis
    "BZ1": P(*G.SOUNDER_XY, 0, B),
    "SW2": P(G.SW2_LEVER_EDGE_X - 1.32, G.LOCK_LINE_Y - 0.10, 270, B),   # lever (local -y) toward +x, tip on y 37.46
    "J2": P(51.10, 25.90, 270, B),                            # opening (local +y) toward -x at x 48.2
    "J3": P(61.00, 28.50, 90, B),                             # pitch along y, wires along x from the front edge
}
PLACE = {}
# underside obstacles of the USB-C receptacle: the four plated shield-tab slots (both faces), pump coordinates
JU1_SLOTS = [G.rect_b(G.USB_X + s * 5.58 - 0.4, G.USB_X + s * 5.58 + 0.4, G.USB_MOUTH_Y - yy - 0.95, G.USB_MOUTH_Y - yy + 0.95)
             for s in (-1, 1) for yy in (2.14, 6.74)]
# free zone under the board for the motor plug (PicoBlade housing + leads) in front of J2's opening
PLUG_ZONE = G.rect_b(41.6, 48.2, 22.6, 29.2)


def geometry(parts: list) -> dict:
    geo = PC.geometry(parts)
    for p in parts:
        r = p["ref"]
        if r in CRT_LIB:
            f = load_fp(*p["fp"])
            f.BuildCourtyardCaches()
            c = f.GetCourtyard(pcbnew.F_CrtYd)
            if c.OutlineCount():
                bb = c.BBox()
                geo[r]["crt"] = [T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom())]
        if r == "J2":
            geo[r]["crt"] = list(J2_BOX)
        geo[r]["h"] = HEIGHT.get(r, geo[r]["h"])
    return geo


def ov(a: list, c: list, m: float = 0.0) -> bool:
    return a[2] > c[0] - m + 1e-6 and c[2] > a[0] - m + 1e-6 and a[3] > c[1] - m + 1e-6 and c[3] > a[1] - m + 1e-6


def check(parts: list, geo: dict, pl: dict) -> list:
    errs = []
    box = {r: PC.box_of(geo[r], pl[r]) for r in pl}
    # the mid-mount USB-C sits in its notch: on the board it occupies only the SMD leg row and the sub-notch rim (+ the tab slots, below)
    box["JU1"] = G.rect_b(G.USB_X - 4.6, G.USB_X + 4.6, G.USB_MOUTH_Y - 8.82, G.USB_MOUTH_Y + 0.3)
    u1_body = G.rect_b(G.U1_X[0], G.U1_X[1], G.U1_C[1] - 3.5, G.U1_A_END)
    for r, bb in box.items():
        side = pl[r][3]
        if r not in ("JU1", "SW2", "J3", "U10") and not G.inside(bb, G.OUTLINE, 0.15 if r == "U1" else EDGE):
            errs.append("%s outside the outline / edge margin %s" % (r, [round(v, 2) for v in bb]))
        if r != "U1" and ov(bb, G.ANT):
            errs.append("%s in the antenna zone" % r)
        if side == B and ov(bb, u1_body):
            errs.append("%s on the underside under the HJ-840" % r)
        h = geo[r]["h"]
        if side == F and h > G.TOP_LIMIT + 1e-6:
            errs.append("%s %.2f mm > top limit %.2f" % (r, h, G.TOP_LIMIT))
        if side == B and h > G.BOTTOM_LIMIT + 1e-6:
            errs.append("%s %.2f mm > bottom limit" % (r, h))
        if side == B and ov(bb, G.BOSS_ZONE) and h > G.BOSS["max_mm"]:
            errs.append("%s in the boss zone" % r)
        for k, s in enumerate(G.STRIPS):
            if r == "JU1" or (r == "U1" and k == 2 and side == F):
                continue
            if ov(bb, s):
                errs.append("%s in the part-free strip %d %s" % (r, k, s))
        if side == F:
            for cx, cy, d in G.TOP_KEEPOUT_CIRCLES:
                if r in ("SW1", "LD1"):
                    continue
                if PC_dist(cx, cy, bb) < d / 2:
                    errs.append("%s in the top keep-out circle (%.1f, %.1f) d%.1f" % (r, cx, cy, d))
        if r != "JU1":
            for q in JU1_SLOTS:
                if ov(bb, q, 0.15):
                    errs.append("%s on a JU1 shield-tab slot" % r)
        if side == B and r != "J2" and ov(bb, PLUG_ZONE):
            errs.append("%s in the motor plug zone" % r)
    refs = sorted(box)
    for i, a in enumerate(refs):
        for c in refs[i + 1:]:
            if pl[a][3] != pl[c][3]:
                continue
            if ov(box[a], box[c], -1e-6) and box[a][2] > box[c][0] + 1e-6 and box[c][2] > box[a][0] + 1e-6 \
                    and box[a][3] > box[c][1] + 1e-6 and box[c][3] > box[a][1] + 1e-6:
                errs.append("overlap %s %s" % (a, c))
    return errs


def PC_dist(x: float, y: float, bb: list) -> float:
    return math.hypot(max(bb[0] - x, 0, x - bb[2]), max(bb[1] - y, 0, y - bb[3]))


def load_place() -> dict:
    fn = os.path.join(HERE, "place_table.json")
    if not os.path.exists(fn):
        return {}
    t = json.load(open(fn))
    return {r: P(v[0], v[1], v[2], v[3]) for r, v in t.items() if not r.startswith("_")}


def main() -> None:
    parts = json.load(open(os.path.join(HERE, "netlist_cart_a.json")))
    geo = geometry(parts)
    pl = dict(FIXED)
    pl.update(load_place())
    missing = [p["ref"] for p in parts if p["ref"] not in pl]
    extra = [r for r in pl if r not in geo]
    errs = check(parts, geo, {r: v for r, v in pl.items() if r in geo})
    for e in errs:
        print("RULE", e)
    print("missing", missing, "extra", extra, "violations", len(errs))
    json.dump({r: list(v) for r, v in pl.items()}, open(os.path.join(HERE, "placement.json"), "w"), indent=1)
    if "--boxes" in sys.argv:
        json.dump({r: [round(v, 3) for v in PC.box_of(geo[r], pl[r])] for r in pl if r in geo}, open(os.path.join(HERE, "_boxes.json"), "w"))
    if missing or extra:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
