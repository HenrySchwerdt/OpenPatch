#!/usr/bin/env python3
"""Round-6 fit coupon: the full pump end face that the Insight adapter twists onto ("FACE").

TEST ONLY - NOT FOR HUMAN USE (see ../../../DISCLAIMER.md). Bench fit test with an empty adapter, never worn.

The lock itself is final (make_pucks.py: FINAL_BORE / FINAL_LIP, seal recess). This coupon adds everything
around it, traced from the owner's photos (2026-11-25) and ruler measurements:

  adapter outline 49 x 19, not a rounded rectangle: small corners at the cup end, a big rounded corner at the
  tube end on the side where the pocket opens, a small step where the tube leaves (photo p26)
  cup centre 11.5 from the near end, on the middle of the width
  far half raised ~4 mm (photos show ~3.4) with a ramp from u = 20.6 to 24.6 (u = distance from the near end)
  pocket in the raised half at the tube end (u 35.1..47, open on one long edge, floor ~0.5 mm proud of the face)
  seal ring d15 with a small key tab that points to the far end (r 7.4..8.7)

Coordinates: pump face up (+Z), cup axis at the origin, the adapter's far end on +X in the locked position,
the edge where the adapter's pocket and edge notch open on -Y.
Locking motion (owner 2026-11-26): looking at the pump end, the adapter goes on from the right and turns
clockwise until it is flush. In these coordinates: far end at +Y on entry, clockwise 90 deg to +X. The adapter's
pocket and edge notch open on its leading edge (-Y), so the pump-side catch and rib slide into them at the end of
the turn. Keyed windows on the Y axis, big lug window at +Y.

Pump side features:
  face (z = FACE_Z) only where the adapter's flat near half sits, through all of the turn
  recess RECESS deep wherever the raised far half sweeps during the 90 deg turn (+ clearance)
  a stop tab in the adapter's pocket, bounded by arcs around the cup axis so it can swing in; it ends at the
  pocket's closed end, which is the rotation stop
  lock: bore, windows, undercut groove, 45 deg lip underside, seal recess with an arc slot for the seal key tab
Not modelled yet (needs owner input): the snap latch into the pocket's hook-shaped lobe, the edge notch
(u 25.9..31.9) counterpart.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from build123d import (Align, BuildPart, BuildSketch, Circle, Cone, Cylinder, Locations, Mode, Plane, Polygon, Pos, offset, add, revolve, Axis,
                       Rectangle, Box, Rot, export_stl, extrude)

import make_pucks as mp

HERE = Path(__file__).resolve().parent
OUT = HERE / "pucks"

FACE_Z = 9.0               # mating face height (same as the pucks)
RECESS = 4.3               # adapter far half is raised ~4 (ruler) / ~3.4 (photo), plus clearance
CUP_U = 11.5               # cup centre from the adapter's near end (ruler 11-11.5, photo 11.9)
WIDTH = 19.0
RAMP_U0 = 20.6             # adapter face starts to rise here (photo p24)
SWEEP_CLEAR = 0.4
TURN_DEG = 90.0
# stop tab in the adapter pocket (photo p26: pocket wall u 35.1, closed end v 1.8, open on the +Y edge)
TAB_R_IN, TAB_R_OUT = 25.4, 29.5   # arcs around the cup axis: inner one clears the straight pocket wall all the way in
TAB_STOP_V = 2.2           # tab end in the locked position (pocket closed end at v 1.8 + clearance)
TAB_TOP_BELOW_FACE = 1.5   # pocket floor is ~0.5 proud of the face, keep 1 mm clearance
# seal key tab (photo p26/cup crop: r 7.4..8.7, ~1.2 wide), the slot follows the whole turn
SEAL_KEY_R0, SEAL_KEY_R1, SEAL_KEY_W = 7.2, 9.2, 1.8


def rounded_polygon(pts: list[tuple[float, float, float]], seg: int = 10) -> list[tuple[float, float]]:
    """Corners (x, y, radius) -> polyline with each corner replaced by a sampled arc."""
    out: list[tuple[float, float]] = []
    n = len(pts)
    for i in range(n):
        x, y, r = pts[i]
        if r <= 0:
            out.append((x, y))
            continue
        px, py, _ = pts[i - 1]
        nx, ny, _ = pts[(i + 1) % n]
        a = (px - x, py - y)
        b = (nx - x, ny - y)
        la, lb = math.hypot(*a), math.hypot(*b)
        a, b = (a[0] / la, a[1] / la), (b[0] / lb, b[1] / lb)
        half = math.acos(max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1]))) / 2
        d = r / math.tan(half)
        p0 = (x + a[0] * d, y + a[1] * d)
        p1 = (x + b[0] * d, y + b[1] * d)
        bis = (a[0] + b[0], a[1] + b[1])
        lbis = math.hypot(*bis)
        c = (x + bis[0] / lbis * r / math.sin(half), y + bis[1] / lbis * r / math.sin(half))
        t0 = math.atan2(p0[1] - c[1], p0[0] - c[0])
        t1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
        dt = (t1 - t0 + math.pi) % (2 * math.pi) - math.pi
        out += [(c[0] + r * math.cos(t0 + dt * k / seg), c[1] + r * math.sin(t0 + dt * k / seg)) for k in range(seg + 1)]
    return out


def outline() -> list[tuple[float, float]]:
    """Adapter outline seen on the pump face, (u, v) from the photo -> pump X = u - CUP_U, Y = v - WIDTH/2."""
    uv = [(0.0, 0.0, 2.5), (48.2, 0.0, 3.5), (48.2, 4.6, 0), (49.0, 4.6, 0), (49.0, 11.6, 0), (48.2, 11.6, 0),
          (48.2, 19.0, 6.5), (0.0, 19.0, 3.0)]
    return [(u - CUP_U, WIDTH / 2 - v) for u, v in rounded_polygon(uv)]


# adapter pocket at the tube end, traced from photo p26 (u, v), open on the +Y edge; the hook-shaped lobe at
# its closed end is where the pump-side catch sits. Pump fills it, minus clearance.
POCKET_UV = [(34.8, 19.5), (34.8, 16.9), (35.1, 6.5), (33.9, 5.5), (34.3, 2.6), (36.0, 1.2), (37.3, 1.6),
             (47.3, 1.6), (47.3, 19.5)]
POCKET_FLOOR_PROUD = 0.5   # adapter pocket floor stands ~0.5 proud of its face (side photo p25)
NOTCH_U, NOTCH_DEPTH = (25.9, 31.9), 3.3   # adapter edge notch on the +Y edge (photo p26)
CLEAR = 0.3


def uv(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(u - CUP_U, WIDTH / 2 - v) for u, v in points]


def pocket_r_in() -> float:
    """Smallest arc radius whose path from the open edge (Y = -W/2) up to the final spot clears the pocket wall."""
    wall_x = min(u for u, v in POCKET_UV if v > 6.0) - CUP_U + CLEAR
    return math.hypot(wall_x, WIDTH / 2)


ENTRY_MARGIN = 0.0   # the windows fix the entry at exactly 90 deg


# Owner 2026-11-26 (pump-end photos): the pump end face is flat everywhere except one lowered strip at the
# bottom right (far end, on the side the adapter comes in from), starting with a 45 deg step about 10-12 mm from
# the bore. It takes the adapter's raised rib ("links ne Erhoehung, rechts nicht"): a rib along one long edge of
# the adapter's far half, ramp u 20.6..24.6, ~3.4-4 high (photos p24/p25 + ruler).
RIB_W = 4.5                # rib width across the adapter (photo estimate), lowered strip gets + clearance
RIB_DEPTH = 4.3            # rib height ~3.4 (photo) .. 4 (ruler) + clearance
SWEEP_STEP_DEG = 1.5


def rib_cut() -> object:
    """Solid the adapter's rib occupies in the locked position (+clearance), 45 deg ramp at its inner end."""
    x_s = RAMP_U0 - CUP_U - CLEAR
    y_in = WIDTH / 2 - RIB_W - CLEAR
    prof = [(x_s, FACE_Z + 1), (x_s, FACE_Z), (x_s + RIB_DEPTH, FACE_Z - RIB_DEPTH), (45, FACE_Z - RIB_DEPTH),
            (45, FACE_Z + 1)]
    with BuildPart() as c:
        y_out = WIDTH / 2 + 3
        with BuildSketch(Plane.XZ.offset(-y_out)) as sk:    # Plane.XZ normal is -Y: this sits at Y = y_out
            Polygon(*prof, align=None)
        extrude(sk.sketch, amount=y_out - y_in)             # towards -Y, down to y_in
    return c.part


def face() -> object:
    """Pump end face: flat, lock in the bore, and the lowered strip the adapter's rib swings into (clockwise
    from +Y, the right side seen from the pump end)."""
    rib = rib_cut()
    bb = rib.bounding_box()
    assert bb.min.Y > 0, "rib cut must sit on the +Y side"
    with BuildPart() as p:
        with BuildSketch():
            Polygon(*outline(), align=None)
        extrude(amount=FACE_Z)
        n = int(round((TURN_DEG + ENTRY_MARGIN) / SWEEP_STEP_DEG))
        for k in range(n + 1):
            add(rib.rotate(Axis.Z, k * SWEEP_STEP_DEG), mode=Mode.SUBTRACT)
        lock_cuts(mp.FINAL_BORE, mp.FINAL_LIP)
    return p.part


def lock_cuts(bore: float, lip: float) -> None:
    """The final bayonet from make_pucks, turned so the windows sit on the Y axis (entry position)."""
    top = FACE_Z
    Cylinder(bore / 2, FACE_Z, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    for sy, w in ((1, mp.WIN_BIG), (-1, mp.WIN_SMALL)):     # big lug points to the far end, which enters at +Y
        with Locations((0, sy * mp.WIN_X / 2, top - lip)):
            Box(w, mp.WIN_X, lip, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    with Locations((0, 0, top - mp.SEAL_DEPTH)):
        Cylinder(mp.SEAL_D / 2, mp.SEAL_DEPTH, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    # arc slot for the seal's key tab (it turns with the adapter from +Y to +X, clockwise)
    with BuildSketch(Plane.XY.offset(top - mp.SEAL_DEPTH)) as key:
        Circle(SEAL_KEY_R1)
        Circle(SEAL_KEY_R0, mode=Mode.SUBTRACT)
        with Locations((-20 - SEAL_KEY_W / 2, 0)):
            Rectangle(40, 60, mode=Mode.SUBTRACT)        # keep x >= -w/2 (entry at -Y)
        with Locations((0, -20 - SEAL_KEY_W / 2)):
            Rectangle(60, 40, mode=Mode.SUBTRACT)        # keep y >= -w/2 (locked at +X)
    extrude(key.sketch, amount=mp.SEAL_DEPTH, mode=Mode.SUBTRACT)
    with Locations((0, 0, top - lip - mp.UNDERCUT_H)):
        Cylinder(mp.GROOVE_R, mp.UNDERCUT_H, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    cone_h = (mp.LUG_OD / 2 - bore / 2) * math.tan(math.radians(mp.LUG_FLANK_DEG))
    with Locations((0, 0, top - lip)):
        Cone(mp.LUG_OD / 2, bore / 2, cone_h, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)


def main() -> int:
    OUT.mkdir(exist_ok=True)
    part = face()
    bb = part.bounding_box()
    export_stl(part, str(OUT / "face_r6.stl"))
    c = bb.center()
    export_stl(part.translate((-c.X, -c.Y, 0)), str(OUT / "face_r6_centered.stl"))
    print(f"face r6: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
