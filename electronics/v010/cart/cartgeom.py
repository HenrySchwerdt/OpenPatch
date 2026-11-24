"""Shared geometry of the CART main board (variants A and B share it). TEST PROJECT, water only.

Board frame (KiCad orientation, as the cup board): bx = mechanics x (0 = west end, motor / wire end; 57 = east end, cartridge cap end),
by = W - mechanics y, i.e. by = 0 is the NORTH edge (USB-C wall side) and by grows toward the south edge. Source of every number:
mechanical/out/v010-cart/board/cart_board_interface.json (cart_board.py) and the variant mech.json files.

Height map (mechanics, both variants, checked against OP-CART-A/B.mech.json 2026-11-24):
  top face: <= 1.45 mm everywhere (lid);
  bottom face, variant B: motor column under bx 4.5..22.1 (south half, top z 10.8 vs board bottom 12.1 -> 1.2 mm), pinion bx 22.2..24.2 and the TMAG strip
  bx 25.7..27.8 (south half, 1.6 mm); over the cell (bx 21.9..53.4, cell top z 4.4) 7.7 mm (B) / 9.4 mm (A); variant A has nothing else under the board.
  -> BOTTOM_LIMIT: 1.2 mm west of bx 28.2, 3.0 mm east of it (the 2.5 mm FUET-4020 sounder goes there).
HJ-840: row A (antenna) faces east; only row A lies in the 3 mm antenna zone, so rows B-H keep normal fan-out. The underside under the
module stays empty (HJ-840 manual: nothing on the back of the module).
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
IFACE = json.load(open(os.path.join(HERE, "..", "..", "..", "mechanical", "out", "v010-cart", "board", "cart_board_interface.json")))
L, W = IFACE["outline_mm"]
BOARD_T = IFACE["thickness_mm"]
TOP_LIMIT = IFACE["parts_height_max_mm"]["top"]
BOTTOM_LIMIT = [((0.0, 28.2), IFACE["parts_height_max_mm"]["bottom"]), ((28.2, L), 3.0)]

USB_X = IFACE["usb_c"]["centre_x"]
USB_MOUTH = -IFACE["usb_c"]["mouth_beyond_edge"]       # receptacle mouth 0.9 mm north of the board edge (housing wall inner face)
SW1_X = IFACE["button_sw1"]["x"]
ANT = (IFACE["antenna_zone"]["x"][0], 0.0, L, W)       # no copper (except the module's own A-row corridors on F.Cu), no other part
CORNER_R = IFACE["corner_r"]


def b(x: float, y: float) -> tuple[float, float]:
    """mechanics board frame (origin west-south, y north) -> board frame (by south)"""
    return (x, W - y)


SUPPORT_PADS = [(*b(x, y), d) for x, y, d in IFACE["support_pads_part_free_both_faces"]["xy_A"]]   # A and B are identical
_r = IFACE["lid_rib_pad_top_face"]
LID_RIB = (_r["x"][0], W - _r["y"][1], _r["x"][1], W - _r["y"][0])   # part-free on the TOP face

U1_POS = (51.5, 5.3)        # HJ-840 centre: row A at bx 54.65 (in the antenna zone), row B at 53.75 (0.25 west of it), body bx 47.95..55.05


def _arc(cx: float, cy: float, r: float, a0: float, a1: float, n: int = 6) -> list[tuple[float, float]]:
    return [(round(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)), 4), round(cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / n)), 4)) for k in range(n + 1)]


def _usb_notch() -> list[tuple[float, float]]:
    """USB-C notch, cup pre-order review H4 geometry relative to the mouth: main cut +-4.57 to 6.22 behind the mouth, rear sub-notch +-3.15
    to 7.00, R0.5 fillets in the four inner corners (JLC mills cut-outs, no square inner corners). Board frame, west to east along the north edge."""
    cx, hw, hs, r = USB_X, 4.57, 3.15, 0.5
    d1, d2 = USB_MOUTH + 6.22, USB_MOUTH + 7.00
    pts = [(cx - hw, 0.0)] + _arc(cx - hw + r, d1 - r, r, 180, 90) + [(cx - hs, d1)] + _arc(cx - hs + r, d2 - r, r, 180, 90)
    pts += _arc(cx + hs - r, d2 - r, r, 90, 0) + [(cx + hs, d1)] + _arc(cx + hw - r, d1 - r, r, 90, 0) + [(cx + hw, 0.0)]
    return pts


def _outline() -> list[tuple[float, float]]:
    r = CORNER_R
    pts = _arc(r, r, r, 180, 270)[:-1] + [(r, 0.0)]
    pts += [p for p in _usb_notch()]
    pts += _arc(L - r, r, r, 270, 360) + _arc(L - r, W - r, r, 0, 90) + _arc(r, W - r, r, 90, 180)
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-3:
            out.append(p)
    if math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-3:
        out.pop()
    return out


OUTLINE = _outline()


def pip(x: float, y: float, poly: list) -> bool:
    c = False
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            c = not c
    return c


def seg_dist(px: float, py: float, a: tuple, c: tuple) -> float:
    dx, dy = c[0] - a[0], c[1] - a[1]
    t = max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / (dx * dx + dy * dy or 1e-12)))
    return math.hypot(px - a[0] - t * dx, py - a[1] - t * dy)


def inside(bb: list, poly: list = OUTLINE, m: float = 0.3) -> bool:
    """box [x0, y0, x1, y1] inside the polygon with margin m to every edge"""
    x0, y0, x1, y1 = bb
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), ((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1), (x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2)]
    if not all(pip(x, y, poly) for x, y in pts):
        return False
    for i in range(len(poly)):
        a, c = poly[i], poly[(i + 1) % len(poly)]
        if x0 - m < a[0] < x1 + m and y0 - m < a[1] < y1 + m:
            return False
        for x, y in pts:
            if seg_dist(x, y, a, c) < m:
                return False
    return True


def bottom_limit(x0: float, x1: float) -> float:
    return min(h for (a, c), h in BOTTOM_LIMIT if x1 > a and x0 < c)
