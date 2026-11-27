#!/usr/bin/env python3
"""Cart pump A v2 print parts: bottom and top shell halves, yoke, button plunger, light pipe (../CART-A-V2-BRIEF.md).
TEST ONLY - water only, never on a person.

The halves split at the cartridge axis height (z 8.74, the seam): every bulkhead / saddle that crosses it is cut in two, so each part
round the axis (cartridge, screw, motor) is clamped between a lower and an upper half-saddle. Bottom half: printed bottom-down.
Top half: printed roof-down (flat top). The head (KOPF9, unchanged) closes the front: the shells' lip ring enters its rear groove and
two axial M2 go through the head face into the bosses. The rear end is held by hooks of the top half under bars of the bottom half
(the top half is swung in from the front, then the head goes on).

Checks every part of package.py (FULL and EMPTY) against both halves and writes print STLs (centred, print orientation) plus placed
STLs for the renders. Run: ../../.venv/bin/python shells.py
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
LAP_UP = 0.8                        # bottom lip rises this far above the seam (inner half of the wall)
# far board edge on the routed board (cart_a6): USB-C at x 42 (its tab slot needs x 47.0-48.2 free), HJ-840 crosses the strip on top
# over x 54.2-59.0 (top clamp stops at 53.9); the bottom ledge may run under the module
FAR_LEDGES = ((33.0, 35.0), (48.2, 58.0))
SHADOW = (0.3, 0.5)                 # seam shadow groove: depth, height
FAR_CLAMPS = ((33.0, 35.0), (48.2, 53.9))
SADDLES_CART = (36.5, 46.5, 56.5)   # chamber saddles (x0, 1.6 thick)
SADDLES_MOTOR = (12.76, 21.76)
HOOK_Y = ((5.2, 8.2), (29.4, 32.9))  # rear hooks, beside the yoke (yoke y 8.71-28.9)
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


def ring_prism(d_out: float, d_in: float, x0: float, x1: float) -> Solid:
    """Ring between two insets of the head section, extruded along x (the lip that enters the head's rear groove)."""
    def wire(d: float) -> Wire:                                         # exact offsets, like the head's groove (make_face offset)
        return Wire.make_polygon([Vector(x0, y, z) for y, z in pk.exact_inset(pk.section_yz(pk.HEAD_L, pk.HEAD_W), d)], close=True)
    return Solid.extrude(Face(wire(d_out), [wire(d_in)]), Vector(x1 - x0, 0, 0))


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
    for k, (y, z) in enumerate(pk.HEAD_SCREWS):                                                     # head screw bosses + webs
        add.append(C(XJ - 3.4, XJ, y, z, 4.0))
        add.append(B((XJ - 3.4, XJ), (y - 1.0, y + 1.0), (-1.0, z) if k == 0 else (z, 25.0)))
        add.append(B((XJ - 3.4, XJ), (PY1 - 0.01, y), (z - 1.0, z + 1.0)))
        cut.append(C(XJ - 6.0, XJ + 0.1, y, z, 1.6))
    cut.append(C(0.45, 1.3, pk.YS, pk.ZC, 2.3))                                                    # screw rear pocket in the rear wall
    return add, cut


def bottom_features() -> list[Solid]:
    f = []
    f.append(B((31.9, pk.BOARD["x"][1] + 0.2), (PY1 - 0.01, 20.35), (-1.0, pz0)))                  # board ledge along the partition
    for xr in FAR_LEDGES:                                                                           # board ledge at the far side (not at USB, not at the pinion)
        f.append(B(xr, (35.3, 36.9), (-1.0, pz0)))
    f.append(B((31.97, 32.5), (PY1 - 0.01, 21.0), (pz0, pz1 + 0.46)))                               # board rear stop (clear of rib_f top half)
    f.append(B((pk.BOARD["x"][1] + 0.1, pk.BOARD["x"][1] + 1.2), (PY1 - 0.01, 22.0), (5.0, pz1 + 0.46)))   # board front stop, standing on the head boss (no floating block)
    for y in HOOK_Y:                                                                                # rear catch bars
        f.append(B((0.5, 2.6), y, (6.4, 7.4)))                                                      # no gusset: the top half's hook nose sits under it (1.4 overhang is fine)
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
    for y in HOOK_Y:                                                                                # rear hooks: plate from the roof, tab, nose
        f += [B((1.35, 4.4), y, (7.55, 25.0)), B((0.5, 4.4), y, (SEAM + LAP_UP + 0.15, 25.0)),
              B((2.8, 4.4), y, (5.0, 7.55)), B((1.5, 2.8), y, (5.0, 6.25))]
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
    yk = yk - C(1.5, 3.7, pk.YC, pk.ZC, 1.95) - C(1.5, 3.7, pk.YS, pk.ZC, 2.4) - nut               # stem press hole, screw, M2 nut pocket
    bx, by = pk.BUTTON_XY
    top = pk.HEAD_W
    plunger = Z(bx, by, top - 1.32, top - 0.12, 5.0) + Z(bx, by, pz1 + 1.6, top - 1.32, 3.0) + Z(bx, by, 13.6, 14.2, 4.2)   # collar under the guide
    lx, ly = pk.LED_XY
    pipe = Z(lx, ly, pz1 + 0.75, top - 0.05, 2.0)
    c0 = 27.56 + pk.XS                                                                              # barrel rear end (on the stop ring)
    pusher = C(c0 - 0.5, c0 + 0.3, pk.YC, pk.ZC, 8.5) + C(c0 - 2.0, c0 - 0.5, pk.YC, pk.ZC, 4.0) - C(c0 - 2.1, c0 - 0.1, pk.YC, pk.ZC, 1.95)
    return {"yoke": yk, "button_plunger": plunger, "light_pipe": pipe, "pusher": pusher}   # pusher d8.5 passes the d8.9 stop ring


def build() -> dict[str, Solid]:
    t0 = [time.time()]
    outer = loft(0.0, XJ)
    cavity = loft(pk.WALL, XJ + 0.5)
    log("lofts", t0)
    shell = outer - cavity
    add, cut = common_features()
    # joint ring into the head groove (KOPF10 0.85..2.55): 1.1 thick, 0.3 play per side, stepped 0.4 lead-in at the tip
    # it sticks out only 1.0 beyond the shell edge: its top / bottom segments print as a free overhang (1.5 was ragged-prone)
    common = shell + (fuse(add) & cavity) + ring_prism(1.15, 2.25, XJ - 1.0, XJ + 0.7) + ring_prism(1.3, 2.1, XJ + 0.6, XJ + 1.0)
    log("shell + common structure", t0)
    below = B((-5, 90), (-5, 70), (-5, SEAM))
    above = B((-5, 90), (-5, 70), (SEAM, 30))
    # owner print 2026-11-27: the stepped lap left only 0.5 mm of outer wall on the top half at the seam (ragged rim). Now a butt
    # joint with the full 1.2 wall on both halves and a 0.3 x 0.5 shadow groove on the seam line; the halves are located by the
    # head ring (front), the rear hooks and the cartridge / motor / screw clamped in both half-saddles.
    shadow = (outer - loft(SHADOW[0], XJ)) & B((-5, XJ + 0.1), (-5, 70), (SEAM - SHADOW[1] / 2, SEAM + SHADOW[1] / 2))
    log("seam shadow groove", t0)
    tf, tcut = top_features()
    bottom = (common & below) + (fuse(bottom_features()) & cavity) - shadow
    top = ((common & above) + (fuse(tf) & cavity)) - shadow
    pc = port_cuts()
    bottom = bottom - fuse(cut + pc)
    top = top - fuse(cut + pc + tcut)
    log("halves", t0)
    return {"bottom": bottom, "top": top} | extra_parts()


EXCLUDE = {("bottom", "cartridge_glass"), ("top", "cartridge_glass"), ("bottom", "board"), ("top", "board"),
           ("top", "yoke"), ("bottom", "yoke")}   # glass rests on the ring, board sits on its ledges (touching); yoke checked separately


def check(parts: dict[str, Solid]) -> dict:
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
        res[state] = hits
    # the head (KOPF10, a real solid): no overlap with either half, and the joint ring keeps >= 0.25 play per side in its groove
    import head as hd
    hs_ = hd.place(hd.build())
    res["head"] = []
    for hn, hh in halves.items():
        inter = hh & hs_
        v = inter.volume if inter is not None else 0.0
        if v > 0.01:
            res["head"].append([hn, "head", round(v, 3)])
    grown = ring_prism(0.9, 2.5, XJ, XJ + 1.5)
    inter = grown & hs_
    v = inter.volume if inter is not None else 0.0
    if v > 0.01:
        res["head"].append(["ring + 0.25 play", "head", round(v, 3)])
    return res


def overhang_outer() -> dict:
    """Outer skin steeper than 45 deg toward the bed, per side (near y < centre / far), for the bottom half printed bottom-down
    and the top half printed roof-down (owner 2026-11-27: the two sides printed differently). mm2, the bed layer excluded."""
    import numpy as np
    t = pk.rings_to_tris(pk.body_rings())
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    a = np.linalg.norm(n, axis=1) / 2
    nz = n[:, 2] / np.maximum(2 * a, 1e-12)
    c = t.mean(axis=1)
    mid = np.array([pk.extents(x)[0] / 2 for x in c[:, 0]])
    out = {}
    for half, sel in (("bottom", (c[:, 2] < SEAM) & (nz < -0.72) & (c[:, 2] > 0.25)),
                      ("top", (c[:, 2] > SEAM) & (nz > 0.72) & (c[:, 2] < pk.HEAD_W - 0.25))):
        out[half] = {"near": round(float(a[sel & (c[:, 1] < mid)].sum()), 2), "far": round(float(a[sel & (c[:, 1] >= mid)].sum()), 2)}
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    parts = build()
    for k, s in parts.items():
        export_stl(s, str(OUT / f"placed_{k}.stl"), tolerance=0.01, angular_tolerance=0.1)
    # halves: rear end toward the bed's back (+Y) so the slicer's "back" seam sits on the rear rounding, not on a side
    orient = {"bottom": Rot(0, 0, -90), "top": Rot(0, 0, -90) * Rot(180, 0, 0), "yoke": Rot(0, 90, 0), "button_plunger": Rot(180, 0, 0),
              "light_pipe": Rot(0, 0, 0), "pusher": Rot(0, 90, 0)}   # disc on the bed
    report = {"parts": {}, "check": check(parts)}
    for k, s in parts.items():
        o = orient[k] * s
        bb = o.bounding_box()
        c = Pos(-(bb.min.X + bb.max.X) / 2, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * o
        export_stl(c, str(OUT / f"v2_{k}.stl"), tolerance=0.01, angular_tolerance=0.1)
        report["parts"][k] = {"volume_cm3": round(s.volume / 1000, 2), "valid": s.is_valid, "solids": len(s.solids()),
                              "print_bbox_mm": [round(bb.max.X - bb.min.X, 2), round(bb.max.Y - bb.min.Y, 2), round(bb.max.Z - bb.min.Z, 2)]}
    report["overhang_outer_mm2"] = ov = overhang_outer()
    report["pass"] = (not any(report["check"].values()) and all(v["solids"] == 1 for v in report["parts"].values())
                      and all(max(v.values()) < 2.0 for v in ov.values()))
    (OUT / "shells_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
