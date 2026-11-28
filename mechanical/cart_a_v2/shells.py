#!/usr/bin/env python3
"""Cart pump A v2.2 print parts: bottom and top shell halves (with the lock face), yoke, button plunger, light pipe, pusher
(../CART-A-V2-BRIEF.md sections 8, 11, 12). TEST ONLY - water only, never on a person.

The halves split at the cartridge axis height (z 8.74, the seam): every bulkhead / saddle that crosses it is cut in two, so each part
round the axis (cartridge, screw, motor) is clamped between a lower and an upper half-saddle. Bottom half: printed bottom-down.
Top half: printed roof-down (flat top). v2.2 (owner 2026-11-28): no separate head - the front 6.6 mm (lock face zone, head.py) are
part of both halves, in exactly the Accu-Chek adapter outline, so the skin runs seamless into the adapter. The halves are closed by
5 hidden M2 screws from the underside into nuts pressed into the top half, a tongue and groove along the cartridge side and two pins
in the lock face zone; no hooks.

Checks every part of package.py (FULL and EMPTY) against both halves, the closed halves against each other, the adapter on the
face, the screws, and writes print STLs (centred, print orientation, height-compensated) plus placed STLs for the renders and a
front test coupon. Run: ../../.venv/bin/python shells.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from build123d import Face, Pos, Rot, Solid, Vector, Wire, export_stl

import package as pk

OUT = pk.OUT / "print"
SEAM = pk.SEAM_Z
XJ = pk.X_JOINT
ROOF = pk.HEAD_W - pk.WALL          # inner roof 17.8 (flat top)
PY0, PY1 = pk.PART_Y
pz0, pz1 = pk.BOARD["pcb_z"]
# far board edge on the routed board (cart_a6): USB-C at x 42 (its tab slot needs x 47.0-48.2 free), HJ-840 crosses the strip on top
# over x 54.2-59.0 (top clamp stops at 53.9); the bottom ledge may run under the module
FAR_LEDGES = ((33.0, 35.0), (48.2, 58.0))
SHADOW = (0.4, 0.6) if pk.MJF else (0.3, 0.5)   # seam shadow groove: depth, height (MJF: a little deeper so it stays crisp)
FAR_CLAMPS = ((33.0, 35.0), (48.2, 53.9))
SADDLES_CART = (36.5, 46.5, 56.5)   # chamber saddles (x0, 1.6 thick)
SADDLES_MOTOR = (12.76, 21.76)
XF = pk.X_FACE
# v2.2 closing: M2 countersunk from the underside (head flush) through a column of the bottom half into an M2 nut pressed into the
# top half's column at the seam. (x, y): rear near / rear far (behind the yoke and the motor), front near (beside the cartridge
# cone), front far (beside the board tongue), lock face zone (between bore and board)
SCREWS = ((6.0, 3.8), (6.0, 34.0), (62.6, 3.8), (63.0, 42.8), (66.4, 22.0))
COL_D, HOLE_D, CSK_D, NUT_AF, NUT_H, SCREW_L = 4.4, (2.4 if pk.MJF else 2.3), 4.1, (4.15 if pk.MJF else 4.1), 1.8, 12.0
PINS = ((69.0, 25.2), (68.6, 31.0))  # d2 alignment pins in the lock face zone (bottom half), d2.3 holes in the top half; the only
                                    # solid spots at the seam (mesh scan: x 67.8-69.4, y 21.5-31.5); bore and lock features fill the rest
TG = {"rim": 3.0, "tongue": (1.15, 1.85) if pk.MJF else (1.1, 1.9), "groove": (0.95, 2.05), "t_h": 1.1, "g_h": 1.3, "x": (7.0, None)}   # cartridge-side wall
# (MJF: tongue 0.7 for 0.2 play per side; MJF parts mate within about +-0.2)
COUPON_X = 64.0                     # test coupon: lock face zone + 1.3 mm of body (zone screw + both pins inside)
Z_COMP = 0.0 if pk.MJF else 0.15    # the slicer's Z_ADJUST -0.15 prints every half 0.15 low: the FDM print STLs are stretched by it
PRESS_D = 2.0 if pk.MJF else 1.95   # stem press holes (MJF holes come out about 0.1 small)
PIN_HOLE_D = 2.45 if pk.MJF else 2.3
T = 1.6                             # rib / wall thickness of inner structure
WIRE_Y, WIRE_Z = (34.0, 37.5), (1.0, 5.2)   # motor leads run along the floor to the connector under the board (no soldering)


def log(msg: str, t0: list[float]) -> None:
    print(f"[{time.time() - t0[0]:6.1f}s] {msg}", flush=True)


def _wire(x: float, d: float) -> Wire:
    L, W = pk.extents(x)
    return Wire.make_polygon([Vector(x, y, z) for y, z in pk.section_yz(L, W, d)], close=True)


def loft(e: float, x_end: float) -> Solid:
    """Outer skin offset inward by e, built in three pieces so the B-spline loft cannot overshoot: rear dome (loft), straight body
    (exact prism), flare into the head (loft through gently changing sections). One loft through all stations waved by up to 2 mm."""
    import math
    R = pk.REAR_R
    st = pk.dome_stations(e)                                            # quarter circle to 45 deg + 45 deg facet (prints bed-side down)
    p_dome = Solid.make_loft([_wire(x, d) for x, d in st[:-1]], ruled=False)
    p_facet = Solid.make_loft([_wire(*st[-2]), _wire(*st[-1])], ruled=True)
    xe = st[-1][0]
    p_body = Solid.extrude(Face(_wire(xe, e)), Vector(pk.FLARE_X0 - xe, 0, 0))
    xs = [pk.FLARE_X0 + i * 2.0 for i in range(int((x_end - pk.FLARE_X0) / 2.0) + 1)]
    xs = [x for x in xs if x < x_end - 0.3] + [x_end]
    p_flare = Solid.make_loft([_wire(x, e) for x in xs], ruled=False)
    return p_dome.fuse(p_facet, p_body, p_flare).clean()


def wedge_y(xr: tuple[float, float], yr: tuple[float, float], z: float, down: bool = True) -> Solid:
    """45 deg gusset along y under (down) a ledge that sticks out from x0 to x1 at height z: triangle (x0, z - w), (x0, z), (x1, z)."""
    x0, x1 = xr
    w = x1 - x0
    zz = z - w if down else z + w
    prof = [Vector(x0, yr[0], zz), Vector(x0, yr[0], z), Vector(x1, yr[0], z)]
    return Solid.extrude(Face(Wire.make_polygon(prof, close=True)), Vector(0, yr[1] - yr[0], 0))


def wedge_x(xr: tuple[float, float], y_wall: float, y_tip: float, z: float) -> Solid:
    """45 deg gusset along x ABOVE a ledge at height z that sticks out from a wall at y_wall to y_tip (supports it when the half
    prints roof-down): triangle (y_wall, z), (y_tip, z), (y_wall, z + |y_tip - y_wall|)."""
    h = abs(y_tip - y_wall)
    prof = [Vector(xr[0], y_wall, z), Vector(xr[0], y_tip, z), Vector(xr[0], y_wall, z + h)]
    return Solid.extrude(Face(Wire.make_polygon(prof, close=True)), Vector(xr[1] - xr[0], 0, 0))


def fuse(solids: list[Solid]) -> Solid:
    return solids[0].fuse(*solids[1:]) if len(solids) > 1 else solids[0]


B, C, Z = pk.box, pk.cyl_x, pk.cyl_z
BIG = (-1.0, 60.0)
UP = (-1.0, 25.0)


def common_features() -> tuple[list[Solid], list[Solid]]:
    """Structure that crosses the seam (split between the halves) and the holes through it."""
    add, cut = [], []
    # rear bulkhead = cartridge stop ring + chamber rear wall + screw thrust rib (washer_r bears on it) + motor front seat
    add.append(B((27.56, 28.56), BIG, UP))
    cut += [C(27.4, 28.7, pk.YC, pk.ZC, 8.9), C(27.4, 28.7, pk.YS, pk.ZC, 2.4), C(27.4, 27.96, pk.YM, pk.ZC, 6.2),
            C(27.4, 28.7, pk.YM, pk.ZC, 3.8), B((27.4, 28.7), WIRE_Y, WIRE_Z)]                       # front boss d3.5; motor lead notch
    add.append(B((28.56, XJ), pk.PART_Y, UP))                                                       # chamber partition
    add.append(B((30.96, 31.96), (PY1 - 0.01, 60.0), UP))                                            # rib_f: screw front, magnet window
    cut += [C(30.8, 32.1, pk.YS, pk.ZC, 2.4), C(30.8, 32.1, pk.YM, pk.ZC, 4.8), B((30.8, 32.1), WIRE_Y, WIRE_Z)]   # 4 mm pinion passes
    for x0 in SADDLES_CART:                                                                         # cartridge half-saddles
        add.append(B((x0, x0 + T), (-1.0, PY0 + 0.01), UP))
        cut.append(C(x0 - 0.1, x0 + T + 0.1, pk.YC, pk.ZC, 11.55))
    for x0 in SADDLES_MOTOR:                                                                        # motor / gearhead half-saddles
        add.append(B((x0, x0 + T), (29.3, 60.0), UP))
        cut += [C(x0 - 0.1, x0 + T + 0.1, pk.YM, pk.ZC, 6.2), B((x0 - 0.1, x0 + T + 0.1), WIRE_Y, WIRE_Z)]   # + lead notch
    # motor rear stop: bar from the far wall behind the rear boss, 45 deg gussets above and below (prints in both halves without support)
    yb, zb = pk.YM - 1.5, pk.ZC
    prof = [Vector(9.86, yb, zb - 1.5), Vector(9.86, yb, zb + 1.5), Vector(9.86, 42.0, zb + 1.5 + 42.0 - yb), Vector(9.86, 42.0, zb - 1.5 - (42.0 - yb))]
    add.append(Solid.extrude(Face(Wire.make_polygon(prof, close=True)), Vector(1.2, 0, 0)))
    add.append(B((32.6, pk.BOARD["x"][1]), (PY1 - 0.01, 19.3), (pz0, pz1 + 0.46)))                  # board edge stop at the partition
    for x, y in SCREWS:                                                                             # closing screw columns
        add.append(Z(x, y, -1.0, 25.0, COL_D))
    cut.append(C(0.45, 1.3, pk.YS, pk.ZC, 2.3))                                                    # screw rear pocket in the rear wall
    return add, cut


def bottom_features() -> list[Solid]:
    f = []
    f.append(B((31.9, pk.BOARD["x"][1] + 0.2), (PY1 - 0.01, 20.35), (-1.0, pz0)))                  # board ledge along the partition
    for xr in FAR_LEDGES:                                                                           # board ledge at the far side (not at USB, not at the pinion)
        f.append(B(xr, (35.3, 36.9), (-1.0, pz0)))
    f.append(B((31.97, 32.5), (PY1 - 0.01, 21.0), (pz0, pz1 + 0.46)))                               # board rear stop (clear of rib_f top half)
    f.append(B((pk.BOARD["x"][1] + 0.1, pk.BOARD["x"][1] + 1.2), (PY1 - 0.01, 22.0), (-1.0, pz1 + 0.46)))   # board front stop, from the floor
    return f


def top_features() -> tuple[list[Solid], list[Solid]]:
    f, cut = [], []
    f += [B((32.6, 62.0), (PY1 - 0.01, 20.1), (pz1, 10.6)), wedge_x((32.6, 62.0), PY1 - 0.01, 20.1, 10.6)]   # board clamp, partition side + gusset
    for xr in FAR_CLAMPS:
        f += [B(xr, (35.3, 36.9), (pz1, 10.6)), wedge_x(xr, 36.9, 35.3, 10.6)]                    # board clamp, far side + gusset
    cx, cy = pk.CELL["x"], pk.CELL["y"]
    f.append(B((31.96, cx[0] - 0.2), (cy[0] - 0.2, 36.9), (12.0, 25.0)))                            # cell pocket: rear wall
    f.append(B((cx[0] - 0.2, cx[1] - 0.2), (cy[1] + 0.2, cy[1] + 0.2 + T), (12.0, 25.0)))           # far wall
    for xr in ((cx[0] - 0.2, 37.4), (49.8, 61.6)):                                                  # near wall, open at LED / button
        f.append(B(xr, (cy[0] - 0.2 - T, cy[0] - 0.2), (12.0, 25.0)))
    for x0 in (41.0, 55.0):                                                                         # ribs pressing the cell onto its foam
        f.append(B((x0, x0 + T), (cy[0] - 0.2, cy[1] + 0.2), (pk.CELL["z"][1] + 0.1, 25.0)))
    bx, by = pk.BUTTON_XY
    f.append(Z(bx, by, 14.5, 25.0, 7.0))                                                            # plunger guide tube (above the cell), wider than the cap recess so it stays on the roof
    cut += [Z(bx, by, 12.0, 30.0, 3.4), Z(bx, by, ROOF - 0.5, 30.0, 5.6)]
    lx, ly = pk.LED_XY
    f.append(Z(lx, ly, 13.0, 25.0, 4.2))                                                            # light pipe guide
    cut.append(Z(lx, ly, 12.0, 30.0, 2.2))
    return f, cut


def port_cuts() -> list[Solid]:
    import math

    def stadium_wire(w: float, h: float, y: float) -> Wire:
        r, half, pts = h / 2, (w - h) / 2, []
        for i in range(13):
            a = -math.pi / 2 + math.pi * i / 12
            pts.append(Vector(pk.USB_X + half + r * math.cos(a), y, pk.USB_Z + r * math.sin(a)))
        for i in range(13):
            a = math.pi / 2 + math.pi * i / 12
            pts.append(Vector(pk.USB_X - half + r * math.cos(a), y, pk.USB_Z + r * math.sin(a)))
        return Wire.make_polygon(pts, close=True)

    w, h, yw = 8.94 + 0.5, 3.26 + 0.5, pk.BODY_L
    usb = Solid.make_loft([stadium_wire(w, h, yw - 2.4), stadium_wire(w, h, yw - 0.5), stadium_wire(w + 3.0, h + 3.0, yw + 1.0)], ruled=True)
    slots = [B((54.5 + pk.XS, 59.5 + pk.XS), (y - 0.35, y + 0.35), (-1.0, 2.0)) for y in (24.6, 26.0, 27.4)]
    return [usb] + slots


def extra_parts() -> dict[str, Solid]:
    """Yoke (screw nut + stem), button plunger, light pipe, in pump coordinates at FULL."""
    import math
    yk = B((1.6, 3.6), (pk.YC, pk.YS), (pk.ZC - 2.75, pk.ZC + 2.75)) + C(1.6, 3.6, pk.YC, pk.ZC, 5.5) + C(1.6, 3.6, pk.YS, pk.ZC, 6.6)
    hexpts = [Vector(3.6 - 1.6, pk.YS + 2.37 * math.cos(math.radians(60 * i + 30)), pk.ZC + 2.37 * math.sin(math.radians(60 * i + 30)))
              for i in range(6)]
    nut = Solid.extrude(Face(Wire.make_polygon(hexpts, close=True)), Vector(1.7, 0, 0))
    yk = yk - C(1.5, 3.7, pk.YC, pk.ZC, PRESS_D) - C(1.5, 3.7, pk.YS, pk.ZC, 2.4) - nut            # stem press hole, screw, M2 nut pocket
    bx, by = pk.BUTTON_XY
    top = pk.HEAD_W
    plunger = Z(bx, by, top - 1.32, top - 0.12, 5.0) + Z(bx, by, pz1 + 1.6, top - 1.32, 3.0) + Z(bx, by, 13.6, 14.2, 4.2)   # collar under the guide
    lx, ly = pk.LED_XY
    pipe = Z(lx, ly, pz1 + 0.75, top - 0.05, 2.0)
    c0 = 27.56 + pk.XS                                                                              # barrel rear end (on the stop ring)
    pusher = C(c0 - 0.5, c0 + 0.3, pk.YC, pk.ZC, 8.5) + C(c0 - 2.0, c0 - 0.5, pk.YC, pk.ZC, 4.0) - C(c0 - 2.1, c0 - 0.1, pk.YC, pk.ZC, PRESS_D)
    return {"yoke": yk, "button_plunger": plunger, "light_pipe": pipe, "pusher": pusher}   # pusher d8.5 passes the d8.9 stop ring


def tongue_groove(cavity: Solid) -> tuple[Solid, Solid, Solid]:
    """Cartridge-side wall (y < 9, from x 7 to the lock face zone): rim to 3.0 from the outside within z seam +-2 (45 deg steps above
    and below, prints without support), tongue on the bottom half, groove in the top half; both skins >= 0.95. The far side has no
    room (motor, board edge and USB-C 0.4-0.5 from the wall): there the screws and the board clamps hold."""
    x0, x1 = TG["x"][0], XJ
    near = B((x0 - 0.5, x1), (-1.0, 9.0), (-1.0, 25.0))
    inner = loft(TG["rim"], x1)
    rim = (cavity - inner) & B((x0 - 0.5, x1), (-1.0, 9.0), (SEAM - 2.0, SEAM + 2.0))
    for k in range(5):                                                    # 0.3 mm steps = 45 deg chamfers below / above the rim
        band = cavity - loft(TG["rim"] - 0.3 * (k + 1), x1)
        for z0, z1 in ((SEAM - 2.0 - 0.3 * (k + 1), SEAM - 2.0 - 0.3 * k), (SEAM + 2.0 + 0.3 * k, SEAM + 2.0 + 0.3 * (k + 1))):
            rim = rim + (band & B((x0 - 0.5, x1), (-1.0, 9.0), (z0, z1)))
    t0_, t1_ = TG["tongue"]
    g0_, g1_ = TG["groove"]
    tongue = (loft(t0_, x1) - loft(t1_, x1)) & near & B((x0, x1 - 0.3), (-1.0, 9.0), (SEAM - 0.01, SEAM + TG["t_h"]))
    groove = (loft(g0_, x1 + 0.2) - loft(g1_, x1 + 0.2)) & B((x0 - 0.2, x1 - 0.1), (-1.0, 9.0), (SEAM - 0.01, SEAM + TG["g_h"]))
    return rim, tongue, groove


def screw_cuts() -> tuple[list[Solid], list[Solid]]:
    """Bottom: clearance hole + countersink from the underside (head flush with the skin). Top: hex nut pocket at the seam (press fit,
    AF 4.1 for an AF 4.0 nut) + clearance for the screw tip (M2 x 12 from z 0)."""
    import math
    bot, top = [], []
    for x, y in SCREWS:
        bot += [Z(x, y, -1.0, SEAM + 0.1, HOLE_D),                                          # 90 deg countersink, d4.1 at z 0
                Solid.make_cone((CSK_D + 2.0) / 2, (HOLE_D - 0.1) / 2, 1.0 + (CSK_D - HOLE_D) / 2 + 0.05, pk.Plane(origin=(x, y, -1.0)))]
        rc = NUT_AF / 2 / math.cos(math.radians(30))
        hexp = [Vector(x + rc * math.cos(math.radians(60 * i)), y + rc * math.sin(math.radians(60 * i)), SEAM - 0.1) for i in range(6)]
        top += [Solid.extrude(Face(Wire.make_polygon(hexp, close=True)), Vector(0, 0, NUT_H + 0.1)), Z(x, y, SEAM - 0.1, SCREW_L + 0.6, HOLE_D)]
    return bot, top


def pins() -> tuple[list[Solid], list[Solid]]:
    return ([Z(x, y, SEAM - 0.5, SEAM + 1.4, 2.0) for x, y in PINS], [Z(x, y, SEAM - 0.1, SEAM + 1.7, PIN_HOLE_D) for x, y in PINS])


def build() -> dict[str, Solid]:
    import head as hd
    t0 = [time.time()]
    outer = loft(0.0, XJ)
    cavity = loft(pk.WALL, XJ)
    log("lofts", t0)
    zone = hd.zone_placed()                                               # lock face zone x 65.26-71.86, exact adapter outline
    shell = (outer - cavity).fuse(zone).clean()
    add, cut = common_features()
    common = shell + (fuse(add) & cavity)
    rim, tongue, groove = tongue_groove(cavity)
    common = common + rim
    log("shell + lock face zone + common structure + rim", t0)
    below = B((-5, 90), (-5, 70), (-5, SEAM))
    above = B((-5, 90), (-5, 70), (SEAM, 30))
    # seam shadow groove 0.3 x 0.5 on the seam line, to the face
    shadow = (outer.fuse(zone) - loft(SHADOW[0], XJ).fuse(hd.place(hd.prism_inset(SHADOW[0])))) & B((-5, XF + 0.1), (-5, 70), (SEAM - SHADOW[1] / 2, SEAM + SHADOW[1] / 2))
    log("seam shadow groove", t0)
    tf, tcut = top_features()
    sb, st = screw_cuts()
    pb, pt = pins()
    tongue = tongue - fuse([Z(x, y, SEAM - 0.02, SEAM + 2.0, COL_D + 0.8) for x, y in SCREWS])   # no tongue in the nut pockets
    bottom = (common & below) + (fuse(bottom_features()) & cavity) + tongue + fuse(pb) - shadow
    top = ((common & above) + (fuse(tf) & cavity)) - shadow - groove
    pc = port_cuts()
    bottom = bottom - fuse(cut + pc + sb)
    top = top - fuse(cut + pc + tcut + st + pt)
    log("halves", t0)
    return {"bottom": bottom, "top": top} | extra_parts()


EXCLUDE = {("bottom", "cartridge_glass"), ("top", "cartridge_glass"), ("bottom", "board"), ("top", "board"),
           ("top", "yoke"), ("bottom", "yoke")}   # glass rests on the ring, board sits on its ledges (touching); yoke checked separately


def screw_solids() -> list[Solid]:
    """M2 x 12 DIN 965 (head d3.8 flush at z 0) + nut, for the clearance check."""
    import math
    out = []
    for x, y in SCREWS:
        s_ = Z(x, y, 0.9, SCREW_L, 2.0) + Solid.make_cone(1.9, 1.0, 0.9, pk.Plane(origin=(x, y, 0.0)))
        rc = 4.0 / 2 / math.cos(math.radians(30))
        hexp = [Vector(x + rc * math.cos(math.radians(60 * i)), y + rc * math.sin(math.radians(60 * i)), SEAM) for i in range(6)]
        out.append(s_ + Solid.extrude(Face(Wire.make_polygon(hexp, close=True)), Vector(0, 0, 1.6)))
    return out


def check(parts: dict[str, Solid]) -> dict:
    import numpy as np
    import head as hd
    res = {}
    halves = {k: parts[k] for k in ("bottom", "top")}
    extras = {k: parts[k] for k in ("yoke", "button_plunger", "light_pipe", "pusher")}
    for state in ("full", "empty"):
        P = {k: v[0] for k, v in pk.parts(state).items() if not k.startswith("ko_") and k not in ("yoke", "pusher")}
        dx = pk.STROKE if state == "empty" else 0.0
        P["yoke"] = Pos(dx, 0, 0) * extras["yoke"]
        P["pusher"] = Pos(dx, 0, 0) * extras["pusher"]
        if state == "full":
            P |= {k: extras[k] for k in ("button_plunger", "light_pipe")}
            P |= {f"screw{i}": sc for i, sc in enumerate(screw_solids())}
        hits = []
        for hn, hs in halves.items():
            hb = hs.bounding_box()
            for pn, ps in P.items():
                if not hb.overlaps(ps.bounding_box()):
                    continue
                inter = hs & ps
                v = inter.volume if inter is not None else 0.0
                if v > 0.02 and (hn, pn) not in EXCLUDE:
                    hits.append([hn, pn, round(v, 3)])
                elif v > 0.5:
                    hits.append([hn, pn, round(v, 3), "excluded but large"])
        if state == "full":                                       # screws must not touch any part inside either
            for i, sc in enumerate(screw_solids()):
                for pn, ps in P.items():
                    if pn.startswith("screw") or not sc.bounding_box().overlaps(ps.bounding_box()):
                        continue
                    inter = sc & ps
                    if inter is not None and inter.volume > 0.01:
                        hits.append([f"screw{i}", pn, round(inter.volume, 3)])
        res[state] = hits
    # closed halves: only the seam faces may touch
    inter = halves["bottom"] & halves["top"]
    v = inter.volume if inter is not None else 0.0
    res["closed_halves"] = [] if v < 0.05 else [["bottom", "top", round(v, 3)]]
    # adapter on the face: mesh slice test (the adapter dummy takes 15 min to build as a solid; its mesh comes from package.py)
    res["adapter"] = []
    for hn, hs in halves.items():
        export_stl(hs, str(OUT / f"_check_{hn}.stl"), tolerance=0.02, angular_tolerance=0.2)
        v = mesh_overlap(pk.OUT / "adapter.stl", OUT / f"_check_{hn}.stl", XJ, XF)
        (OUT / f"_check_{hn}.stl").unlink()
        if v > 0.05:
            res["adapter"].append([hn, "adapter", round(v, 3)])
    # seamless: the body section at the joint is exactly the adapter outline (no facet, no morph left)
    a = np.array(pk.section_at(XJ)); b = np.array(pk.section_yz(pk.HEAD_L, pk.HEAD_W, 0.0, w=1.0, facet=0.0))
    dev = float(np.abs(a - b).max())
    res["seamless_joint"] = [] if dev < 1e-6 else [["section at the joint differs from the adapter outline by", round(dev, 4)]]
    # lock face features must not be touched by the screw / pin holes (they would open into the bayonet)
    cutz = hd.cut_placed()
    sb, st = screw_cuts()
    pb, pt = pins()
    res["zone_holes"] = []
    for nm, sol in [(f"screw{i}", Z(x, y, -1.0, SCREW_L + 0.6, COL_D - 0.4)) for i, (x, y) in enumerate(SCREWS)] + \
                   [(f"pin{i}", Z(x, y, SEAM - 1.0, SEAM + 2.2, 3.3)) for i, (x, y) in enumerate(PINS)]:
        inter = sol & cutz
        if inter is not None and inter.volume > 0.01:
            res["zone_holes"].append([nm, "lock face feature", round(inter.volume, 3)])
    return res


def mesh_overlap(pa: Path, pb: Path, x0: float, x1: float, step: float = 0.2, grid: float = 0.1) -> float:
    """Volume (mm3) inside both STL meshes between x0 and x1: x slices, even-odd test on a (y, z) grid."""
    import struct
    import numpy as np

    def load(p: Path) -> np.ndarray:
        d = p.read_bytes()
        n = struct.unpack("<I", d[80:84])[0]
        return np.frombuffer(d[84:84 + n * 50], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))["v"].reshape(-1, 3, 3).astype(float)

    def segs(T: np.ndarray, x: float) -> np.ndarray:
        dx = T[:, :, 0] - x
        m = ~((dx > 0).all(1) | (dx < 0).all(1))
        out = []
        for tri, d in zip(T[m], dx[m]):
            pts = [(tri[i] + (tri[(i + 1) % 3] - tri[i]) * (d[i] / (d[i] - d[(i + 1) % 3])))[1:]
                   for i in range(3) if (d[i] > 0) != (d[(i + 1) % 3] > 0)]
            if len(pts) == 2:
                out.append(pts)
        return np.array(out)

    def inside(S: np.ndarray, P: np.ndarray) -> np.ndarray:
        r = np.zeros(len(P), bool)
        if len(S) == 0:
            return r
        y1, z1, y2, z2 = S[:, 0, 0], S[:, 0, 1], S[:, 1, 0], S[:, 1, 1]
        for k in range(0, len(P), 4000):
            p = P[k:k + 4000]
            py, pz = p[:, 0:1], p[:, 1:2]
            c = (z1 > pz) != (z2 > pz)
            yi = y1 + (pz - z1) * (y2 - y1) / np.where(z2 - z1 == 0, 1e-12, z2 - z1)
            r[k:k + 4000] = (np.count_nonzero(c & (py < yi), axis=1) % 2) == 1
        return r

    A, Bm = load(pa), load(pb)
    gy, gz = np.meshgrid(np.arange(grid / 2, pk.HEAD_L, grid), np.arange(grid / 2, pk.HEAD_W, grid))
    G = np.c_[gy.ravel(), gz.ravel()]
    tot = 0.0
    for x in np.arange(x0 + step / 2, x1, step):
        tot += float((inside(segs(A, x), G) & inside(segs(Bm, x), G)).sum()) * grid * grid * step
    return tot


def mf_adapter() -> tuple[Solid, Solid]:
    import head as hd
    hd.mf.FACE_Z = hd.mf.MODULE_DEPTH
    ad, nd = hd.mf.adapter_dummy()
    return hd.place(ad), hd.place(nd)


def overhang_outer() -> dict:
    """Outer skin steeper than 45 deg toward the bed, per side (near y < centre / far), for the bottom half printed bottom-down
    and the top half printed roof-down (owner 2026-11-27: the two sides printed differently). mm2, the bed layer excluded.
    The facets fade out before the lock face zone (seamless with the adapter): from x 61.26 the adapter corners print as they are."""
    import numpy as np
    t = pk.rings_to_tris(pk.body_rings(x_end=XJ - 4.0))
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    a = np.linalg.norm(n, axis=1) / 2
    nz = n[:, 2] / np.maximum(2 * a, 1e-12)
    c = t.mean(axis=1)
    mid = np.array([pk.extents(x)[0] / 2 for x in c[:, 0]])
    keep = c[:, 0] < XJ - 4.0 - 0.05
    out = {}
    for half, sel in (("bottom", keep & (c[:, 2] < SEAM) & (nz < -0.72) & (c[:, 2] > 0.25)),
                      ("top", keep & (c[:, 2] > SEAM) & (nz > 0.72) & (c[:, 2] < pk.HEAD_W - 0.25))):
        out[half] = {"near": round(float(a[sel & (c[:, 1] < mid)].sum()), 2), "far": round(float(a[sel & (c[:, 1] >= mid)].sum()), 2)}
    return out


def stretch_z(path: Path, dz: float) -> None:
    """Stretch a binary STL in z so it prints dz taller (compensates the slicer's Z_ADJUST)."""
    import struct
    import numpy as np
    d = bytearray(path.read_bytes())
    n = struct.unpack("<I", d[80:84])[0]
    a = np.frombuffer(bytes(d[84:84 + n * 50]), dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")])).copy()
    v = a["v"].reshape(-1, 3, 3)
    h = float(v[:, :, 2].max() - v[:, :, 2].min())
    v[:, :, 2] = v[:, :, 2] * (h + dz) / h
    a["v"] = v.reshape(-1, 9)
    path.write_bytes(bytes(d[:84]) + a.tobytes())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    parts = build()
    for k, s in parts.items():
        export_stl(s, str(OUT / f"placed_{k}.stl"), tolerance=0.01, angular_tolerance=0.1)
    # halves: rear end toward the bed's back (+Y) so the slicer's "back" seam sits on the rear rounding, not on a side
    orient = {"bottom": Rot(0, 0, -90), "top": Rot(0, 0, -90) * Rot(180, 0, 0), "yoke": Rot(0, 90, 0), "button_plunger": Rot(180, 0, 0),
              "light_pipe": Rot(0, 0, 0), "pusher": Rot(0, 90, 0)}   # disc on the bed
    report = {"parts": {}, "check": check(parts)}
    if pk.MJF:                                                         # nylon order set: pump coordinates, mm, one STL per part
        report = {"parts": {}, "check": check(parts), "mode": "MJF PA12 black (no FDM facets, MJF clearances, no z stretch)"}
        for k, s in parts.items():
            if k == "light_pipe":
                continue                                                  # must be clear: acrylic rod / clear filament, not nylon
            export_stl(s, str(OUT / f"OpenTube_A_{k}.stl"), tolerance=0.005, angular_tolerance=0.05)
            bb = s.bounding_box()
            report["parts"][k] = {"volume_cm3": round(s.volume / 1000, 2), "valid": s.is_valid, "solids": len(s.solids()),
                                  "bbox_mm": [round(bb.max.X - bb.min.X, 2), round(bb.max.Y - bb.min.Y, 2), round(bb.max.Z - bb.min.Z, 2)]}
        report["pass"] = not any(report["check"].values()) and all(v["solids"] == 1 for v in report["parts"].values())
        (OUT / "mjf_report.json").write_text(json.dumps(report, indent=1))
        print(json.dumps(report, indent=1))
        return
    for k, s in parts.items():
        o = orient[k] * s
        bb = o.bounding_box()
        c = Pos(-(bb.min.X + bb.max.X) / 2, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * o
        export_stl(c, str(OUT / f"v2_{k}.stl"), tolerance=0.01, angular_tolerance=0.1)
        if k in ("bottom", "top"):
            stretch_z(OUT / f"v2_{k}.stl", Z_COMP)
        report["parts"][k] = {"volume_cm3": round(s.volume / 1000, 2), "valid": s.is_valid, "solids": len(s.solids()),
                              "print_bbox_mm": [round(bb.max.X - bb.min.X, 2), round(bb.max.Y - bb.min.Y, 2), round(bb.max.Z - bb.min.Z, 2)]}
    # front test coupon (owner: test the lock face printed in the halves before the full halves): x >= COUPON_X of both halves, side by side
    cb, ct = parts["bottom"] & B((COUPON_X, 80), (-5, 70), (-5, 30)), parts["top"] & B((COUPON_X, 80), (-5, 70), (-5, 30))
    ob, ot = orient["bottom"] * cb, orient["top"] * ct
    bb1, bb2 = ob.bounding_box(), ot.bounding_box()
    ob = Pos(-(bb1.min.X + bb1.max.X) / 2, -bb1.max.Y - 3.0, -bb1.min.Z) * ob
    ot = Pos(-(bb2.min.X + bb2.max.X) / 2, -bb2.min.Y + 3.0, -bb2.min.Z) * ot
    export_stl(ob, str(OUT / "v2_coupon_bottom.stl"), tolerance=0.01, angular_tolerance=0.1)
    export_stl(ot, str(OUT / "v2_coupon_top.stl"), tolerance=0.01, angular_tolerance=0.1)
    for k in ("bottom", "top"):
        stretch_z(OUT / f"v2_coupon_{k}.stl", Z_COMP)
    report["coupon"] = {"x_from": COUPON_X, "files": ["v2_coupon_bottom.stl", "v2_coupon_top.stl"]}
    report["overhang_outer_mm2"] = ov = overhang_outer()
    report["z_comp_mm"] = Z_COMP
    report["pass"] = (not any(report["check"].values()) and all(v["solids"] == 1 for v in report["parts"].values())
                      and all(max(v.values()) < 2.0 for v in ov.values()))
    (OUT / "shells_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
