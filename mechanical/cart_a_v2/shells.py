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
SADDLES_CART = (36.5, 46.5, 56.5)   # chamber saddles (x0, 1.6 thick)
SADDLES_MOTOR = (12.76, 21.76)
HOOK_Y = ((5.2, 8.2), (29.4, 32.9))  # rear hooks, beside the yoke (yoke y 8.71-28.9)
T = 1.6                             # rib / wall thickness of inner structure


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
    dome = [_wire(R - (R - e) * math.cos(th), R - (R - e) * math.sin(th)) for th in [math.pi / 2 * i / 10 for i in range(11)]]
    p_dome = Solid.make_loft(dome, ruled=False)
    p_body = Solid.extrude(Face(_wire(R, e)), Vector(pk.FLARE_X0 - R, 0, 0))
    xs = [pk.FLARE_X0 + i * 2.0 for i in range(int((x_end - pk.FLARE_X0) / 2.0) + 1)]
    xs = [x for x in xs if x < x_end - 0.3] + [x_end]
    p_flare = Solid.make_loft([_wire(x, e) for x in xs], ruled=False)
    return p_dome.fuse(p_body, p_flare).clean()


def ring_prism(d_out: float, d_in: float, x0: float, x1: float) -> Solid:
    """Ring between two insets of the head section, extruded along x (the lip that enters the head's rear groove)."""
    def wire(d: float) -> Wire:
        return Wire.make_polygon([Vector(x0, y, z) for y, z in pk.section_yz(pk.HEAD_L, pk.HEAD_W, d)], close=True)
    return Solid.extrude(Face(wire(d_out), [wire(d_in)]), Vector(x1 - x0, 0, 0))


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
            C(27.4, 28.7, pk.YM, pk.ZC, 3.4), B((27.4, 28.7), (34.0, 37.5), (12.5, 15.5))]          # wire notch (motor -> board)
    add.append(B((28.56, XJ), pk.PART_Y, UP))                                                       # chamber partition
    add.append(B((30.96, 31.96), (PY1 - 0.01, 60.0), UP))                                            # rib_f: screw front, magnet window
    cut += [C(30.8, 32.1, pk.YS, pk.ZC, 2.4), C(30.8, 32.1, pk.YM, pk.ZC, 2.8), B((30.8, 32.1), (34.0, 37.5), (12.5, 15.5))]
    for x0 in SADDLES_CART:                                                                         # cartridge half-saddles
        add.append(B((x0, x0 + T), (-1.0, PY0 + 0.01), UP))
        cut.append(C(x0 - 0.1, x0 + T + 0.1, pk.YC, pk.ZC, 11.55))
    for x0 in SADDLES_MOTOR:                                                                        # motor / gearhead half-saddles
        add.append(B((x0, x0 + T), (29.3, 60.0), UP))
        cut.append(C(x0 - 0.1, x0 + T + 0.1, pk.YM, pk.ZC, 6.2))
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
    for xr in ((31.9, 35.0), (45.0, 58.0)):                                                         # board ledge at the far side (not at USB)
        f.append(B(xr, (35.3, 36.9), (-1.0, pz0)))
    f.append(B((31.97, 32.5), (PY1 - 0.01, 21.0), (pz0, pz1 + 0.46)))                               # board rear stop (clear of rib_f top half)
    f.append(B((pk.BOARD["x"][1] + 0.1, pk.BOARD["x"][1] + 1.2), (PY1 - 0.01, 22.0), (pz0 - 1.0, pz1 + 0.46)))   # board front stop
    for y in HOOK_Y:                                                                                # rear catch bars
        f.append(B((0.5, 2.6), y, (6.4, 7.4)))
    return f


def top_features() -> tuple[list[Solid], list[Solid]]:
    f, cut = [], []
    f.append(B((32.6, 62.0), (PY1 - 0.01, 20.1), (pz1, 10.6)))                                      # board clamp, partition side
    for xr in ((32.6, 35.0), (45.0, 58.0)):
        f.append(B(xr, (35.3, 36.9), (pz1, 10.6)))                                                  # board clamp, far side
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
    common = shell + (fuse(add) & cavity) + ring_prism(1.15, 2.25, XJ - 1.0, XJ + 1.8)
    log("shell + common structure", t0)
    below = B((-5, 90), (-5, 70), (-5, SEAM))
    above = B((-5, 90), (-5, 70), (SEAM, 30))
    lip = (loft(0.6, XJ) - cavity) & B((-5, XJ), (-5, 70), (SEAM - 0.01, SEAM + LAP_UP))
    groove = (loft(0.5, XJ + 2.0) - loft(1.3, XJ + 2.0)) & B((-5, XJ + 2.0), (-5, 70), (SEAM - 0.01, SEAM + LAP_UP + 0.1))
    log("lap joint", t0)
    tf, tcut = top_features()
    bottom = (common & below) + lip + (fuse(bottom_features()) & cavity)
    top = ((common & above) + (fuse(tf) & cavity)) - groove
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
    return res


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    parts = build()
    for k, s in parts.items():
        export_stl(s, str(OUT / f"placed_{k}.stl"), tolerance=0.01, angular_tolerance=0.1)
    orient = {"bottom": Rot(0, 0, 0), "top": Rot(180, 0, 0), "yoke": Rot(0, 90, 0), "button_plunger": Rot(180, 0, 0),
              "light_pipe": Rot(0, 0, 0), "pusher": Rot(0, 90, 0)}   # disc on the bed
    report = {"parts": {}, "check": check(parts)}
    for k, s in parts.items():
        o = orient[k] * s
        bb = o.bounding_box()
        c = Pos(-(bb.min.X + bb.max.X) / 2, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * o
        export_stl(c, str(OUT / f"v2_{k}.stl"), tolerance=0.01, angular_tolerance=0.1)
        report["parts"][k] = {"volume_cm3": round(s.volume / 1000, 2), "valid": s.is_valid, "solids": len(s.solids()),
                              "print_bbox_mm": [round(bb.max.X - bb.min.X, 2), round(bb.max.Y - bb.min.Y, 2), round(bb.max.Z - bb.min.Z, 2)]}
    report["pass"] = not any(report["check"].values()) and all(v["solids"] == 1 for v in report["parts"].values())
    (OUT / "shells_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
