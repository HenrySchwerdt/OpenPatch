#!/usr/bin/env python3
"""Cart pump A v2.2 print parts: bottom and top shell halves (with the lock face), yoke, button plunger, light pipe, pusher
(../CART-A-V2-BRIEF.md sections 8, 11, 12). TEST ONLY - water only, never on a person.

The halves split at the cartridge axis height (the seam: z 9.90 from v2.3, FACE4 bore; v2.2 8.74): every bulkhead / saddle that crosses it is cut in two, so each part
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
DZ = pk.DZ                          # v2.3: inner heights drawn for the bore at z 8.74 move with the bore (FACE4: 9.90)
CLAMP_Z = pz1 + 1.46                # top of the board clamps (v2.2: 10.6)
# far board edge on the routed board (cart_a6): USB-C at x 42 (its tab slot needs x 47.0-48.2 free), HJ-840 crosses the strip on top
# over x 54.2-59.0 (top clamp stops at 53.9); the bottom ledge may run under the module
FAR_LEDGES = ((33.0, 35.0), (48.2, 58.0))
# v2.3 (owner 2026-11-28: 'die Rille bei den Haelften sieht nicht seamless aus'): no groove on the seam any more (v2.1-v2.2: a
# 0.3 x 0.5 shadow groove, MJF 0.4 x 0.6); the halves butt flush, held in line by the 2 pins, the tongue + groove and the 5 screws
SEAM_BAND = 0.05                    # skin check: half height of the band at the seam (the two seam faces touch there)
FAR_CLAMPS = ((33.0, 35.0), (48.2, 53.9))
SADDLES_CART = (36.5, 46.5, 56.5)   # chamber saddles (x0, 1.6 thick)
SADDLES_MOTOR = (12.76, 21.76)
XF = pk.X_FACE
# v2.2 closing: M2 countersunk from the underside (head flush) through a column of the bottom half into an M2 nut pressed into the
# top half's column at the seam. (x, y): rear near / rear far (behind the yoke and the motor), front near (beside the cartridge
# cone), front far (beside the board tongue), lock face zone (between bore and board)
SCREWS = ((8.0, 3.8), (8.0, 34.0), (62.6, 3.8), (63.0, 42.8), (66.4, 22.0))   # rear pair at x 8, out of the lofted rear dome (x 6 cut its
                                    # doubly curved corner faces and the STL mesher left 9863 open edges there)
COL_D, HOLE_D, CSK_D, NUT_AF, NUT_H, SCREW_L = 4.4, (2.4 if pk.MJF else 2.3), 4.1, (4.15 if pk.MJF else 4.1), 1.8, 12.0
PINS = ((69.0, 25.2), (68.6, 31.0))  # d2 alignment pins in the lock face zone (bottom half), d2.3 holes in the top half; the only
                                    # solid spots at the seam (mesh scan: x 67.8-69.4, y 21.5-31.5); bore and lock features fill the rest
TG = {"rim": 3.0, "tongue": (1.15, 1.85) if pk.MJF else (1.1, 1.9), "groove": (0.95, 2.05), "t_h": 1.1, "g_h": 1.3, "x": (7.0, None)}   # cartridge-side wall
# (MJF: tongue 0.7 for 0.2 play per side; MJF parts mate within about +-0.2)
CELL_RECESS = pk.CELL_RECESS        # 32 mm cell (owner measured) + its wires: 2 mm into the back of the lock face zone (top half),
                                    # clear of every lock feature (zone_holes check)
COUPON_X = 64.0                     # test coupon: lock face zone + 1.3 mm of body (zone screw + both pins inside)
Z_COMP = 0.0 if pk.MJF else 0.15    # the slicer's Z_ADJUST -0.15 prints every half 0.15 low: the FDM print STLs are stretched by it
PRESS_D = 2.0 if pk.MJF else 1.95   # stem press holes (MJF holes come out about 0.1 small)
PIN_HOLE_D = 2.45 if pk.MJF else 2.3
T = 1.6                             # rib / wall thickness of inner structure
WIRE_Y, WIRE_Z = (34.0, 37.5), (1.0, 5.2)   # motor leads run along the floor to the connector under the board (no soldering)
LEADS: list[Solid] = []             # lead notches through the inner ribs: cut ONLY inside the cavity (owner print 2026-11-28: as plain
                                    # cuts they went through the skin at the far-bottom rounding = 4 rectangular holes)


def log(msg: str, t0: list[float]) -> None:
    print(f"[{time.time() - t0[0]:6.1f}s] {msg}", flush=True)


def _wire(x: float, d: float) -> Wire:
    """Shell section at x, inset by d: package.section_at, the one form the package check, the renders and the gates use.
    (v2 .. v2.3 first build called section_yz(L, W, d) with its defaults: the adapter corners with 45 deg facets along the whole body,
    which met the round lock face zone with a step at every corner; owner 2026-11-28: 'die Ecken in jeder Ecke'.)"""
    return Wire.make_polygon([Vector(x, y, z) for y, z in pk.section_at(x, d)], close=True)


def loft(e: float, x_end: float) -> Solid:
    """Outer skin offset inward by e, built in three pieces so the B-spline loft cannot overshoot: rear dome (loft), straight body
    (exact prism), flare into the head (loft through gently changing sections). One loft through all stations waved by up to 2 mm."""
    import math
    R = pk.REAR_R
    st = pk.dome_stations(e)                                            # rear end: quarter circle (pure rounds)
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
            C(27.4, 28.7, pk.YM, pk.ZC, 3.8)]                                                       # front boss d3.5
    LEADS.append(B((27.4, 28.7), WIRE_Y, WIRE_Z))                                                   # motor lead notch
    add.append(B((28.56, XJ), pk.PART_Y, UP))                                                       # chamber partition
    add.append(B((30.96, 31.96), (PY1 - 0.3, 60.0), UP))                                            # rib_f: screw front, magnet window
    cut += [C(30.8, 32.1, pk.YS, pk.ZC, 2.4), C(30.8, 32.1, pk.YM, pk.ZC, 4.8)]                    # 4 mm pinion passes
    LEADS.append(B((30.8, 32.1), WIRE_Y, WIRE_Z))
    for x0 in SADDLES_CART:                                                                         # cartridge half-saddles
        add.append(B((x0, x0 + T), (-1.0, PY0 + 0.3), UP))
        cut.append(C(x0 - 0.1, x0 + T + 0.1, pk.YC, pk.ZC, 11.55))
    for x0 in SADDLES_MOTOR:                                                                        # motor / gearhead half-saddles
        add.append(B((x0, x0 + T), (29.3, 60.0), UP))
        cut.append(C(x0 - 0.1, x0 + T + 0.1, pk.YM, pk.ZC, 6.2))
        LEADS.append(B((x0 - 0.1, x0 + T + 0.1), WIRE_Y, WIRE_Z))                                    # lead notch
    # motor rear stop: bar from the far wall behind the rear boss, 45 deg gussets above and below (prints in both halves without support)
    yb, zb = pk.YM - 1.5, pk.ZC
    prof = [Vector(9.86, yb, zb - 1.5), Vector(9.86, yb, zb + 1.5), Vector(9.86, 42.0, zb + 1.5 + 42.0 - yb), Vector(9.86, 42.0, zb - 1.5 - (42.0 - yb))]
    add.append(Solid.extrude(Face(Wire.make_polygon(prof, close=True)), Vector(1.2, 0, 0)))
    add.append(B((32.6, pk.BOARD["x"][1]), (PY1 - 0.3, 19.3), (pz0, pz1 + 0.46)))                  # board edge stop at the partition
    for x, y in SCREWS:                                                                             # closing screw columns
        add.append(Z(x, y, -1.0, 25.0, COL_D))
    cut.append(C(0.45, 1.3, pk.YS, pk.ZC, 2.3))                                                    # screw rear pocket in the rear wall
    return add, cut


def bottom_features() -> list[Solid]:
    f = []
    f.append(B((31.5, pk.BOARD["x"][1] + 0.2), (PY1 - 0.3, 20.35), (-1.0, pz0)))                  # board ledge along the partition (0.5 into rib_f, no sliver)
    for xr in FAR_LEDGES:                                                                           # board ledge at the far side (not at USB, not at the pinion)
        f.append(B(xr, (35.3, 36.9), (-1.0, pz0)))
    f.append(B((31.5, 32.5), (PY1 - 0.3, 21.0), (pz0, SEAM)))                                       # board rear stop: below the seam it
    f.append(B((32.0, 32.5), (PY1, 21.0), (SEAM - 0.3, pz1 + 0.46)))                               # merges into rib_f, above it stays clear of the top half's rib_f / partition
    f.append(B((pk.BOARD["x"][1] + 0.1, pk.BOARD["x"][1] + 1.2), (PY1 - 0.3, 22.0), (-1.0, SEAM)))   # board front stop, from the floor;
    f.append(B((pk.BOARD["x"][1] + 0.1, pk.BOARD["x"][1] + 1.2), (PY1, 22.0), (SEAM - 0.3, pz1 + 0.46)))   # above the seam clear of the top partition
    return f


def top_features() -> tuple[list[Solid], list[Solid]]:
    f, cut = [], []
    f += [B((32.6, 62.0), (PY1 - 0.3, 20.1), (pz1, CLAMP_Z)), wedge_x((32.6, 62.0), PY1 - 0.3, 20.1, CLAMP_Z)]   # board clamp, partition side + gusset
    for xr in FAR_CLAMPS:
        f += [B(xr, (35.3, 36.9), (pz1, CLAMP_Z)), wedge_x(xr, 36.9, 35.3, CLAMP_Z)]                    # board clamp, far side + gusset
    cx, cy = pk.CELL["x"], pk.CELL["y"]
    f.append(B((31.96, cx[0] - 0.2), (cy[0] - 0.2, 36.9), (12.0 + DZ, 25.0)))                            # cell pocket: rear wall
    f.append(B((cx[0] - 0.2, cx[1] - 0.2), (cy[1] + 0.2, cy[1] + 0.2 + T), (11.5 + DZ, 25.0)))           # far wall (down to 11.5: overlaps the
                                                                                                    # clamp gussets instead of touching them along an edge)
    for xr in ((31.96, 37.4), (49.8, 61.6)):                                                        # near wall, open at LED / button (from the rear
                                                                                                    # wall's back face: overlap, not an edge contact)
        f.append(B(xr, (cy[0] - 0.2 - T, cy[0] - 0.2), (12.0 + DZ, 25.0)))
    for x0 in (41.0, 55.0):                                                                         # ribs pressing the cell onto its foam
        f.append(B((x0, x0 + T), (cy[0] - 0.2, cy[1] + 0.2), (pk.CELL["z"][1] + 0.1, 25.0)))
    bx, by = pk.BUTTON_XY
    f.append(Z(bx, by, 14.5 + DZ, 25.0, 7.0))                                                            # plunger guide tube (above the cell), wider than the cap recess so it stays on the roof
    cut += [Z(bx, by, 12.0 + DZ, 30.0, 3.4), Z(bx, by, ROOF - 0.5, 30.0, 5.6)]
    lx, ly = pk.LED_XY
    f.append(Z(lx, ly, 13.0 + DZ, 25.0, 4.2))                                                            # light pipe guide
    cut.append(Z(lx, ly, 12.0 + DZ, 30.0, 2.2))
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
    plunger = Z(bx, by, top - 1.32, top - 0.12, 5.0) + Z(bx, by, pz1 + 1.6, top - 1.32, 3.0) + Z(bx, by, 13.6 + DZ, 14.2 + DZ, 4.2)   # collar under the guide
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
    tongue = (loft(t0_, x1) - loft(t1_, x1)) & near & B((x0, x1 - 0.3), (-1.0, 9.0), (SEAM - 0.3, SEAM + TG["t_h"]))
    groove = (loft(g0_, x1 + 0.2) - loft(g1_, x1 + 0.2)) & B((x0 - 0.2, x1 - 0.1), (-1.0, 9.0), (SEAM - 0.3, SEAM + TG["g_h"]))
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


def drop_dust(s: Solid) -> Solid:
    """Booleans can leave zero-volume slivers as extra 'solids' (MJF bottom 2026-11-28: one at the tongue start); keep the part."""
    from build123d import Compound
    big = [x for x in s.solids() if x.volume > 0.01]
    if len(big) == 1 and len(s.solids()) > 1:
        return big[0]
    return s if len(big) != 1 else (big[0] if not isinstance(s, Compound) else big[0])


def build() -> dict[str, Solid]:
    import head as hd
    t0 = [time.time()]
    outer = loft(0.0, XJ)
    cavity = loft(pk.WALL, XJ)
    log("lofts", t0)
    zone = hd.zone_placed()                                               # lock face zone x 65.26-71.86, exact adapter outline
    shell = (outer - cavity).fuse(zone).clean()
    LEADS.clear()
    add, cut = common_features()
    common = shell + (fuse(add) & cavity)
    cut = cut + [ld & loft(pk.WALL + 0.05, XJ) for ld in LEADS]                 # notches stop 0.05 inside the wall
    rim, tongue, groove = tongue_groove(cavity)
    common = common + rim
    log("shell + lock face zone + common structure + rim", t0)
    below = B((-5, 90), (-5, 70), (-5, SEAM))
    above = B((-5, 90), (-5, 70), (SEAM, 30))
    tf, tcut = top_features()
    sb, st = screw_cuts()
    pb, pt = pins()
    tongue = tongue - fuse([Z(x, y, SEAM - 0.02, SEAM + 2.0, COL_D + 0.8) for x, y in SCREWS])   # no tongue in the nut pockets
    bottom = (common & below) + (fuse(bottom_features()) & cavity) + tongue + fuse(pb)
    top = ((common & above) + (fuse(tf) & cavity)) - groove
    pc = port_cuts()
    bottom = drop_dust(bottom - fuse(cut + pc + sb))
    top = drop_dust(top - fuse(cut + pc + tcut + st + pt + [B(*CELL_RECESS)]))
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
    # seamless: the section the shells are lofted through at the joint (_wire) is the lock face zone's outline, both ways
    a = np.array([(v.Y, v.Z) for v in _wire(XJ, 0.0).vertices()])
    b = np.array([(pk.YC + x, pk.ZC + y) for x, y in hd.mf.outline()])
    dev = max(float(poly_dist(a, b).max()), float(poly_dist(b, a).max()))
    res["seamless_joint"] = [] if dev < 1e-3 else [["shell section at the joint differs from the lock face outline by", round(dev, 4)]]
    # every opening in the outer skin must be one we want (owner print 2026-11-28 found 4 unwanted holes): exact CAD test, the skin
    # layer 0.35 under the surface minus both halves; each leftover piece must sit inside a known opening
    res["skin_openings"] = skin_openings(halves)
    # lock face features must not be touched by the screw / pin holes (they would open into the bayonet)
    cutz = hd.cut_placed()
    sb, st = screw_cuts()
    pb, pt = pins()
    res["zone_holes"] = []
    for nm, sol in [(f"screw{i}", Z(x, y, -1.0, SCREW_L + 0.6, COL_D - 0.4)) for i, (x, y) in enumerate(SCREWS)] + \
                   [(f"pin{i}", Z(x, y, SEAM - 1.0, SEAM + 2.2, 3.3)) for i, (x, y) in enumerate(PINS)] + \
                   [("cell recess", B((CELL_RECESS[0][0], CELL_RECESS[0][1] + 0.6), (CELL_RECESS[1][0] - 0.6, CELL_RECESS[1][1] + 0.6),
                                      (CELL_RECESS[2][0] - 0.6, CELL_RECESS[2][1] + 0.6)))]:
        inter = sol & cutz
        if inter is not None and inter.volume > 0.01:
            res["zone_holes"].append([nm, "lock face feature", round(inter.volume, 3)])
    return res


def poly_dist(P, Q):
    """Distance of each point of P to the closed polyline Q (numpy arrays of (y, z))."""
    import numpy as np
    a, b = Q, np.roll(Q, -1, 0)
    ab, ap = b - a, P[:, None, :] - a[None]
    t = np.clip((ap * ab[None]).sum(-1) / np.maximum((ab ** 2).sum(-1), 1e-12)[None], 0, 1)
    return np.hypot(*(ap - t[..., None] * ab[None]).transpose(2, 0, 1)).min(1)


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


def skin_openings(halves: dict[str, Solid], depth: float = 0.35) -> list:
    """Pieces of the outer skin layer (depth under the surface, sides, top, bottom, rear; not the lock face itself) that neither half
    fills and that are not a wanted opening. Returns [] when the skin only has the wanted openings."""
    import head as hd
    # the layer starts 0.02 under the surface: with the outer faces coincident with the halves' skin, OpenCascade returned no result
    # for the v2.3 MJF bottom (skin & bottom = None, so the whole skin came out 'missing'); 0.02 cannot hide a real opening
    top = 0.02
    env = loft(top, XJ).fuse(hd.place(hd.prism_inset(top))) & B((-5, XF - top), (-5, 70), (-5, 30))
    inner = loft(depth, XJ).fuse(hd.place(hd.prism_inset(depth)))
    missing = (env - inner) - halves["bottom"] - halves["top"] - B((-5, XF + 5), (-5, 70), (SEAM - SEAM_BAND, SEAM + SEAM_BAND))
    r = HOLE_D / 2 + (CSK_D - HOLE_D) / 2 + 0.6
    wanted = [("USB-C", (pk.USB_X - 6.0, pk.USB_X + 6.0), (35.0, 40.0), (pk.USB_Z - 3.5, pk.USB_Z + 3.5)),
              ("sound slots", (54.0, 62.0), (23.5, 28.5), (-0.5, 1.5)),
              ("button", (pk.BUTTON_XY[0] - 3.5, pk.BUTTON_XY[0] + 3.5), (pk.BUTTON_XY[1] - 3.5, pk.BUTTON_XY[1] + 3.5), (17.0, 19.5)),
              ("light pipe", (pk.LED_XY[0] - 1.8, pk.LED_XY[0] + 1.8), (pk.LED_XY[1] - 1.8, pk.LED_XY[1] + 1.8), (17.0, 19.5)),
              ("lock face edge (lowered areas + rounded far edge of the tested face, under the adapter)", (XF - 2.5, XF + 0.1), (-1.0, 50.0), (-0.5, 19.5)),
              ]
    wanted += [(f"screw {i} countersink", (x - r, x + r), (y - r, y + r), (-0.5, 2.0)) for i, (x, y) in enumerate(SCREWS)]
    out = []
    for piece in (missing.solids() if missing is not None else []):
        if piece.volume < 0.002:
            continue
        b = piece.bounding_box()
        if any(xr[0] <= b.min.X and b.max.X <= xr[1] and yr[0] <= b.min.Y and b.max.Y <= yr[1] and zr[0] <= b.min.Z and b.max.Z <= zr[1]
               for _n, xr, yr, zr in wanted):
            continue
        out.append({"x": [round(b.min.X, 2), round(b.max.X, 2)], "y": [round(b.min.Y, 2), round(b.max.Y, 2)],
                    "z": [round(b.min.Z, 2), round(b.max.Z, 2)], "volume_mm3": round(piece.volume, 3)})
    return out


def solidcraft_import(step: Path) -> str:
    """Second, stricter kernel (SolidCraft / SMLib, owner's CAD app): '' if it imports the STEP as a body, else its error. It found
    edge contacts inside the top half that OpenCascade accepted (2026-11-28)."""
    import subprocess
    sc = Path("/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli")
    if not sc.exists():
        return ""
    r = subprocess.run([str(sc), "eval", "--in", str(step)], capture_output=True, text=True, timeout=600)
    out = (r.stdout + r.stderr).strip()
    return "" if r.returncode == 0 and "no bodies" not in out and "error" not in out.lower()[:200] else out[-400:]


def mf_adapter() -> tuple[Solid, Solid]:
    import head as hd
    hd.mf.FACE_Z = hd.mf.MODULE_DEPTH
    ad, nd = hd.mf.adapter_dummy()
    return hd.place(ad), hd.place(nd)


def overhang_outer() -> dict:
    """Outer skin steeper than 45 deg toward the bed, per side (near y < centre / far), for the bottom half printed bottom-down
    and the top half printed roof-down (owner 2026-11-27: the two sides printed differently). mm2, the bed layer excluded.
    v2.3: with pure rounds (package.PURE_ROUNDS, owner: everything smooth) this is reported, not a pass condition: the lowest
    part of each bed-side round overhangs by design."""
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


def open_edges(path: Path) -> int:
    """Edges of a binary STL that are not shared by exactly two triangles (0 = watertight)."""
    import collections
    import struct
    import numpy as np
    d = path.read_bytes()
    n = struct.unpack("<I", d[80:84])[0]
    v = np.frombuffer(d[84:84 + n * 50], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))["v"].reshape(-1, 3)
    _, ids = np.unique(np.round(v.astype(float), 4), axis=0, return_inverse=True)
    ids = ids.reshape(-1, 3)
    e = np.sort(np.concatenate([ids[:, [0, 1]], ids[:, [1, 2]], ids[:, [2, 0]]]), axis=1)
    _, cnt = np.unique(e, axis=0, return_counts=True)
    return int((cnt != 2).sum())


def mesh_edges(path: Path) -> dict:
    """Edge use counts of a binary STL after welding: holes = edges used once or three times (open), over = edges used 4+ times
    (zero-area slivers stacked on a line: closed but untidy; slicers and print services drop them)."""
    import struct
    import numpy as np
    d = path.read_bytes()
    n = struct.unpack("<I", d[80:84])[0]
    v = np.frombuffer(d[84:84 + n * 50], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))["v"].reshape(-1, 3)
    _, ids = np.unique(np.round(v.astype(float), 4), axis=0, return_inverse=True)
    ids = ids.reshape(-1, 3)
    e = np.sort(np.concatenate([ids[:, [0, 1]], ids[:, [1, 2]], ids[:, [2, 0]]]), axis=1)
    _, cnt = np.unique(e, axis=0, return_counts=True)
    return {"holes": int((cnt % 2 == 1).sum()), "over": int((cnt > 2).sum() - (cnt[cnt > 2] % 2 == 1).sum())}


def export_closed(s: Solid, path: Path, tol: float = 0.01, ang: float = 0.1) -> dict:
    """STL export that must be watertight: retries with other tessellation settings (owner 2026-11-28: the first v2.2 bottom
    STL had 827 open edges, some faces had not been meshed). Returns the settings used and the open-edge count."""
    best = None
    for t, a in ((tol, ang), (tol * 2, ang * 2), (tol / 2, ang / 2), (0.02, 0.25), (0.05, 0.3)):
        export_stl(s, str(path), tolerance=t, angular_tolerance=a)
        oe = mesh_edges(path)["holes"]
        if best is None or oe < best[0]:
            best = (oe, t, a)
        if oe == 0:
            break
    if best[0] != 0 or (best[1], best[2]) != (t, a):
        export_stl(s, str(path), tolerance=best[1], angular_tolerance=best[2])
    return {"open_edges": best[0], "tolerance": best[1], "angular": best[2], "sliver_edges": mesh_edges(path)["over"]}


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
    from build123d import export_step
    mesh = {}
    for k, s in parts.items():
        mesh[f"placed_{k}"] = export_closed(s, OUT / f"placed_{k}.stl")
        if k in ("bottom", "top"):
            stp = OUT / f"{'OpenTube_A' if pk.MJF else 'v2'}_{k}.step"
            export_step(s, str(stp))
            mesh[f"{stp.stem}_solidcraft"] = {"open_edges": 0 if not (err := solidcraft_import(stp)) else 1, "error": err}
    # halves: rear end toward the bed's back (+Y) so the slicer's "back" seam sits on the rear rounding, not on a side
    orient = {"bottom": Rot(0, 0, -90), "top": Rot(0, 0, -90) * Rot(180, 0, 0), "yoke": Rot(0, 90, 0), "button_plunger": Rot(180, 0, 0),
              "light_pipe": Rot(0, 0, 0), "pusher": Rot(0, 90, 0)}   # disc on the bed
    report = {"parts": {}, "check": check(parts)}
    if pk.MJF:                                                         # nylon order set: pump coordinates, mm, one STL per part
        report = {"parts": {}, "check": check(parts), "mode": "MJF PA12 black (no FDM facets, MJF clearances, no z stretch)"}
        for k, s in parts.items():
            if k == "light_pipe":
                continue                                                  # must be clear: acrylic rod / clear filament, not nylon
            mesh[f"OpenTube_A_{k}"] = export_closed(s, OUT / f"OpenTube_A_{k}.stl", 0.005, 0.05)
            bb = s.bounding_box()
            report["parts"][k] = {"volume_cm3": round(s.volume / 1000, 2), "valid": s.is_valid, "solids": len(s.solids()),
                                  "bbox_mm": [round(bb.max.X - bb.min.X, 2), round(bb.max.Y - bb.min.Y, 2), round(bb.max.Z - bb.min.Z, 2)]}
        report["mesh"] = mesh
        report["pass"] = (not any(report["check"].values()) and all(v["solids"] == 1 for v in report["parts"].values())
                          and all(m["open_edges"] == 0 for m in mesh.values()))
        (OUT / "mjf_report.json").write_text(json.dumps(report, indent=1))
        print(json.dumps(report, indent=1))
        return
    for k, s in parts.items():
        o = orient[k] * s
        bb = o.bounding_box()
        c = Pos(-(bb.min.X + bb.max.X) / 2, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * o
        mesh[f"v2_{k}"] = export_closed(c, OUT / f"v2_{k}.stl")
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
    mesh["v2_coupon_bottom"] = export_closed(ob, OUT / "v2_coupon_bottom.stl")
    mesh["v2_coupon_top"] = export_closed(ot, OUT / "v2_coupon_top.stl")
    for k in ("bottom", "top"):
        stretch_z(OUT / f"v2_coupon_{k}.stl", Z_COMP)
    report["coupon"] = {"x_from": COUPON_X, "files": ["v2_coupon_bottom.stl", "v2_coupon_top.stl"]}
    report["overhang_outer_mm2"] = ov = overhang_outer()
    report["z_comp_mm"] = Z_COMP
    report["mesh"] = mesh
    report["pass"] = (not any(report["check"].values()) and all(v["solids"] == 1 for v in report["parts"].values())
                      and (pk.PURE_ROUNDS or all(max(v.values()) < 2.0 for v in ov.values()))   # v2.3: rounds by owner choice
                      and all(m["open_edges"] == 0 for m in mesh.values()))
    (OUT / "shells_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
