"""Geometry of the cart pump A v2 main board (TEST PROJECT, bench only, water only).

Single source: mechanical/out/cart_a_v2/board_A_interface.json (mechanical/cart_a_v2/board_interface.py), pump coordinates in mm
(x = length, 0 rear; y = width, far wall / USB-C side high; z = height). OVERRIDE below carries the coordinator's changes of 2026-11-27
(4 mm pinion) until the regenerated interface JSON is on this branch; a newer JSON that already carries them wins.

Board frame (KiCad, seen from the top, y down): bx = x - X0, by = Y1 - y. KiCad page position = (100 + bx, 80 + by).

Decisions taken here (README "Interface"):
  * USB-C moved from x 40.0 to x 42.0: the TYPE-C-31-M-14 front shield-tab slots (+-5.58 from the centre, 2.14 behind the mouth) and
    its board notch (+-4.57) leave only 2.03 mm of board between the pinion notch (x 33.0) and the USB notch (x 35.43) at the TMAG
    height; a SOT-23-6 needs 2.5 mm of pads. With the USB at 42.0 the TMAG5273 sits at the requested spot (magnet axis y 33.435).
  * HJ-840 at x 54.2-60.4, row A (antenna) toward +y, A end y 38.76: the antenna (last 1.0 mm of the module) is 3.0 mm from the cell
    pouch (pouch edge y 34.9 at z >= 11.1; module top z 10.14). The antenna wing follows antenna_wing_max but stops 2.0 mm beyond the
    A end (y 40.76); keep-out = module A end - 1.0 mm to the board edge, no copper on any layer (F.Cu: A1 stub + A7-A8 bridge only).
  * Lock switch Alps SPVS410100 on the tongue underside, lever toward +x, lever-side body edge x 63.94 (pads 0.2 from the tongue edge).
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
IFACE_PATH = os.path.join(HERE, "..", "..", "..", "..", "mechanical", "out", "cart_a_v2", "board_A_interface.json")
IFACE = json.load(open(IFACE_PATH))

# coordinator 2026-11-27 (pinion 4 mm long, reaches x 32.66): notch at the rear-far corner, TMAG +0.4 in x, far strip from x 33.0
OVERRIDE = {
    "rear_far_notch": {"x": [32.6, 33.0], "y": [31.0, 36.3]},
    "tmag_x": [33.2, 35.2],
    "far_strip_x": [[33.0, 35.0], [45.0, 59.0]],
    "motor_connector_min_x": 33.2,
}
NOTCH = IFACE["outline"].get("rear_far_notch", OVERRIDE["rear_far_notch"])

X0, Y1 = 32.6, 41.0
BOARD_T = IFACE["thickness_mm"]
PCB_Z = IFACE["pcb_z"]
MAIN = IFACE["outline"]["main_rect"]
TONGUE = IFACE["outline"]["tongue"]
WING = IFACE["outline"]["antenna_wing_max"]["far_edge_y_by_x"]
CORNER_R = min(0.5, IFACE["outline"]["corner_r_max"])

TOP_LIMIT = IFACE["height_limits"]["top_mm"]
BOTTOM_LIMIT = IFACE["height_limits"]["bottom_mm"]
BOSS = IFACE["height_limits"]["bottom_boss_zone"]

NEAR_STRIP = IFACE["part_free_strips_both_faces"]["near"]
FAR_STRIP_Y = IFACE["part_free_strips_both_faces"]["far"]["y"]
FAR_STRIP_X = OVERRIDE["far_strip_x"] if IFACE["part_free_strips_both_faces"]["far"]["x"][0][0] < 33.0 else IFACE["part_free_strips_both_faces"]["far"]["x"]

FIX = IFACE["fixed_parts"]
USB_X_IFACE = FIX["usb_c"]["centre_x"]
USB_X = 42.0                              # see the module docstring (TMAG vs USB-C tab slots)
USB_MOUTH_Y = FIX["usb_c"]["front_face_y"]
SW1_XY = (FIX["sw1"]["x"], FIX["sw1"]["y"])
LED_XY = (FIX["led"]["x"], FIX["led"]["y"])
TMAG_BOX = (OVERRIDE["tmag_x"] if FIX["tmag5273"]["x"][0] < 33.2 else FIX["tmag5273"]["x"], FIX["tmag5273"]["y"])
SOUNDER_XY = (FIX["sounder"]["x"], FIX["sounder"]["y"])
LOCK = FIX["lock_switch"]
LOCK_LINE_Y = 37.46                       # actuator line (interface "line y 37.46")
KEEPOUTS_TOP = IFACE["keepouts_top"]
MOTOR_CONN_NEAR = IFACE["connectors_no_soldering"]["motor"]["near"]
CELL_CONN_NEAR = IFACE["connectors_no_soldering"]["cell"]["near"]

# cell pouch above the board (interface "radio" / brief section 9)
POUCH_Y_MAX, POUCH_Z_MIN = 34.9, 11.1

# HJ-840 placement (pump coordinates): module 6.2 x 7.0, row A toward +y
U1_C = (57.3, 35.26)
U1_A_END = U1_C[1] + 3.5                  # 38.76
ANT_DEPTH_IN_MODULE = 1.0                 # B convention: the keep-out starts 1.0 mm inside the module's A end
WING_TOP = U1_A_END + 2.0                 # 40.76: board edge 2.0 beyond the A end where antenna_wing_max allows
U1_X = (U1_C[0] - 3.1, U1_C[0] + 3.1)

# lock switch (SPVS410100): lever-side body edge on the tongue (pads 3 / 4 end 0.19 inside the body edge, copper-to-edge 0.2)
SW2_LEVER_EDGE_X = TONGUE["x"][1] - 0.02


def b(x: float, y: float) -> tuple:
    """pump (x, y) -> board frame (bx, by)"""
    return (round(x - X0, 4), round(Y1 - y, 4))


def p(bx: float, by: float) -> tuple:
    """board frame -> pump"""
    return (round(bx + X0, 4), round(Y1 - by, 4))


def wing_edge(x: float) -> float:
    """antenna_wing_max far edge at x (linear interpolation), clipped to WING_TOP"""
    pts = WING
    if x <= pts[0][0]:
        y = pts[0][1]
    elif x >= pts[-1][0]:
        y = pts[-1][1]
    else:
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            if xa <= x <= xb:
                y = ya + (yb - ya) * (x - xa) / (xb - xa)
                break
    return min(y, WING_TOP)


def _fillet(poly: list, radii: list, n: int = 6) -> list:
    """round every corner of a closed polygon (pump coords) with its radius (0 = sharp); works for convex and concave corners"""
    out = []
    m = len(poly)
    for i in range(m):
        a, c, d = poly[i - 1], poly[i], poly[(i + 1) % m]
        r = radii[i]
        if r <= 0:
            out.append(c)
            continue
        u1 = (a[0] - c[0], a[1] - c[1]); l1 = math.hypot(*u1); u1 = (u1[0] / l1, u1[1] / l1)
        u2 = (d[0] - c[0], d[1] - c[1]); l2 = math.hypot(*u2); u2 = (u2[0] / l2, u2[1] / l2)
        cosang = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
        half = math.acos(cosang) / 2
        if abs(math.sin(half)) < 1e-6 or abs(half - math.pi / 2) < 1e-6 and False:
            out.append(c)
            continue
        t = r / math.tan(half)
        t = min(t, 0.45 * l1, 0.45 * l2)
        r_eff = t * math.tan(half)
        t1 = (c[0] + u1[0] * t, c[1] + u1[1] * t)
        t2 = (c[0] + u2[0] * t, c[1] + u2[1] * t)
        bis = (u1[0] + u2[0], u1[1] + u2[1]); lb = math.hypot(*bis)
        if lb < 1e-9:
            out.append(c)
            continue
        cen = (c[0] + bis[0] / lb * r_eff / math.sin(half), c[1] + bis[1] / lb * r_eff / math.sin(half))
        a0 = math.atan2(t1[1] - cen[1], t1[0] - cen[0])
        a1 = math.atan2(t2[1] - cen[1], t2[0] - cen[0])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for k in range(n + 1):
            ang = a0 + da * k / n
            out.append((round(cen[0] + r_eff * math.cos(ang), 4), round(cen[1] + r_eff * math.sin(ang), 4)))
    res = []
    for q in out:
        if not res or math.hypot(q[0] - res[-1][0], q[1] - res[-1][1]) > 1e-3:
            res.append(q)
    if math.hypot(res[0][0] - res[-1][0], res[0][1] - res[-1][1]) < 1e-3:
        res.pop()
    return res


def usb_notch_pump() -> list:
    """USB-C notch (cup pre-order review H4 geometry relative to the mouth, as on B): main cut +-4.57 to 6.22 behind the mouth, rear
    sub-notch +-3.15 to 7.00; corner points from the far edge (west to east), pump coordinates; fillets added by the outline"""
    cx, hw, hs = USB_X, 4.57, 3.15
    ye = MAIN["y"][1]
    d1, d2 = USB_MOUTH_Y - 6.22, USB_MOUTH_Y - 7.00
    return [(cx - hw, ye), (cx - hw, d1), (cx - hs, d1), (cx - hs, d2), (cx + hs, d2), (cx + hs, d1), (cx + hw, d1), (cx + hw, ye)]


def outline_pump() -> list:
    """board outline, pump coordinates, counter-clockwise (interior on the left), corners filleted"""
    (x0, x1), (y0, y1) = MAIN["x"], MAIN["y"]
    tx1, (ty0, ty1) = TONGUE["x"][1], TONGUE["y"]
    wx0, wx1 = WING[0][0], TONGUE["x"][0]            # wing between x 52.0 and 59.0
    pts, rad = [], []

    def add(q, r=CORNER_R):
        pts.append(q); rad.append(r)
    add((x0, y0)); add((x1, y0)); add((x1, ty0)); add((tx1, ty0)); add((tx1, ty1), 0.2); add((wx1, ty1), 0.3)   # 0.2: SW2 frame pad 3
    # wing: from the tongue back along min(antenna_wing_max, WING_TOP), sampled every 0.25 mm
    add((wx1, wing_edge(wx1)), 0.3)
    xs = [wx1 - 0.25 * k for k in range(1, int((wx1 - wx0) / 0.25) + 1)]
    for x in xs:
        add((x, wing_edge(x)), 0.0)
    rad[-1] = 0.3
    add((wx0, y1), 0.3)
    # far edge westward with the USB-C notch (concave corners need the milling radius: 0.5)
    for q in reversed(usb_notch_pump()):
        add(q, 0.5)
    # rear-far notch (pinion): board absent x 32.6-33.0, y 31.0-36.3
    add((NOTCH["x"][1], y1)); add((NOTCH["x"][1], NOTCH["y"][0]), 0.2); add((x0, NOTCH["y"][0]), 0.2)
    return _fillet(pts, rad)


OUTLINE_P = outline_pump()
OUTLINE = [b(x, y) for x, y in OUTLINE_P]      # board frame (KiCad y down: clockwise on screen, orientation does not matter)


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


def edge_dist(x: float, y: float, poly: list = None) -> float:
    poly = poly or OUTLINE
    return min(seg_dist(x, y, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def inside(bb: list, poly: list = None, m: float = 0.3) -> bool:
    """box [x0, y0, x1, y1] (board frame) inside the polygon with margin m to every edge"""
    poly = poly or OUTLINE
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


def rect_b(x0: float, x1: float, y0: float, y1: float) -> list:
    """pump rectangle -> board-frame box [bx0, by0, bx1, by1]"""
    a, c = b(x0, y1), b(x1, y0)
    return [a[0], a[1], c[0], c[1]]


# part-free strips (both faces), board frame boxes
STRIPS = [rect_b(MAIN["x"][0], MAIN["x"][1], NEAR_STRIP["y"][0], NEAR_STRIP["y"][1])]
STRIPS += [rect_b(xa, xb, FAR_STRIP_Y[0], FAR_STRIP_Y[1]) for xa, xb in FAR_STRIP_X]
# antenna keep-out (board frame box): module x range, from 1.0 mm inside the A end to beyond the board edge
ANT = rect_b(U1_X[0], U1_X[1], U1_A_END - ANT_DEPTH_IN_MODULE, 45.0)
TOP_KEEPOUT_CIRCLES = [(*b(k["x"], k["y"]), k["d"]) for k in KEEPOUTS_TOP]
BOSS_ZONE = rect_b(BOSS["x"][0], BOSS["x"][1], BOSS["y"][0], BOSS["y"][1])


def antenna_clearance() -> float:
    """3D distance from the antenna (module A end band, top z) to the cell pouch edge (y 34.9, z 11.1)"""
    ytop = PCB_Z[1] + 1.0
    return math.hypot(U1_A_END - ANT_DEPTH_IN_MODULE - POUCH_Y_MAX, POUCH_Z_MIN - ytop)


if __name__ == "__main__":
    xs = [q[0] for q in OUTLINE_P]; ys = [q[1] for q in OUTLINE_P]
    print("outline points", len(OUTLINE_P), "x %.2f..%.2f y %.2f..%.2f" % (min(xs), max(xs), min(ys), max(ys)))
    print("antenna clearance to the pouch %.2f mm" % antenna_clearance(), "ANT box", ANT)
    print("strips", STRIPS)
