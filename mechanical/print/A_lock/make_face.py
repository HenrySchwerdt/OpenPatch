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
OUT_NEAR = 11.2            # pump end: bore centre to the near end (photo)
BORE_OFFSET_Y = 0.4        # bore centre sits this much towards the silver side (photo)
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
    """Pump end outline, fitted to the owner's pump-end photo (2026-11-26) with its tilt (3.4 deg) and scale
    (14.65 px/mm) taken out. Not a rounded rectangle: the corners on the silver (entry, +Y) side are much rounder
    than on the black front side, and the bore sits ~0.4 mm towards the silver side and 11.2 from the near end.
    Corner radii: bore end/front 2.0, bore end/silver 7.0, far end/silver 5.5, far end/front 2.7."""
    x0, x1 = -OUT_NEAR, 49.0 - OUT_NEAR
    yf, ys = -(WIDTH / 2 + BORE_OFFSET_Y), WIDTH / 2 - BORE_OFFSET_Y
    return rounded_polygon([(x0, yf, 2.0), (x1, yf, 2.7), (x1, ys, 5.5), (x0, ys, 7.0)], seg=16)


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


# Owner 2026-11-26, marked on the pump-end photo: the pump end face is flat; lowered are (1) a round area at the
# far end around the window and (2) a thin strip along the right (entry) edge from about 10 mm below the bore,
# joined by a small square where the strip meets the round area. On the adapter these are its raised parts:
# the hook-shaped boss at the tube end (photo p26 outline, incl. the hook lobe) and the thin wall along the
# silver-side edge (v 0..1.6) that starts with the 45 deg ramp at u 20.6..24.6 (side photo p24).
BAND_W = 1.6               # raised wall along the adapter's entry-side edge (p26: boss top boundary at v 1.6)
# Hook boss (p26 outline, incl. the hook lobe), run past the outline on the right so it merges with the band.
# Owner 2026-11-26: it does not reach the far end on the left (front) side; there the pump face stays at full
# height and the boundary curves gently round (pump photo: the high wall left of the window ring). Smooth curve
# through these pump-photo points (X, Y), converted to (u, v) = (X + CUP_U, W/2 - Y).
FAR_LEFT_CURVE_XY = [(23.6, -5.6), (25.3, -5.6), (30.4, -6.1), (34.5, -5.5), (36.7, -4.2), (38.5, -2.0), (40.0, 0.0)]  # traced on the photo (tilt removed)


def smooth(points: list[tuple[float, float]], per_seg: int = 8) -> list[tuple[float, float]]:
    """Catmull-Rom through the points (end points kept)."""
    p = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for k in range(per_seg):
            t = k / per_seg
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in range(2)))
    out.append(points[-1])
    return out


_curve_uv = [(x + 11.5, 9.5 - y) for x, y in smooth(FAR_LEFT_CURVE_XY)]
BOSS_UV = ([(35.1, 6.5), (33.9, 5.5), (34.3, 2.6), (36.0, 1.2), (36.0, -2.0), (55.0, -2.0), (55.0, 8.0)]
           + _curve_uv[::-1] + [(35.1, 15.1)])
RAISE_DEPTH = 4.3          # raised parts ~3.4 (photo) .. 4 (ruler) high, + clearance
BOSS_SWEEP_DEG, BOSS_SWEEP_STEP = 30.0, 1.0   # boss enters the outline only in the last ~25 deg
HOLLOW_ROUND = 1.5         # rim of the boss hollow rounds over and curves down (owner)
NOTCH_LOCK_X = 35.9        # lock notch at the far end, front side: from here to the far edge (photo)
NOTCH_LOCK_Y = (-6.7, -4.0)
NOTCH_LOCK_DEPTH = 5.0
LOCK_POCKET_X = (24.0, 26.2)   # pocket for the lock at the top of the curved left side of the hollow (photo zoom)
LOCK_POCKET_Y = (-7.7, -5.0)
LATCH_X = (15.0, 20.5)     # latch groove along the strip wall (X from the cup axis), estimated from the owner's mark
LATCH_Z = (0.8, 3.8)       # below the face: 0.8 roof on top, 3.0 tall
LATCH_DEPTH = 1.2          # into the wall (towards -Y)


def band_cut() -> object:
    """Strip for the adapter's thin entry-side wall: one flat 45 deg ramp, then 4.3 deep to the far end."""
    x_s = RAMP_U0 - CUP_U - CLEAR
    y_in = WIDTH / 2 - BAND_W - CLEAR
    prof = [(x_s, FACE_Z + 1), (x_s, FACE_Z), (x_s + RAISE_DEPTH, FACE_Z - RAISE_DEPTH),
            (45, FACE_Z - RAISE_DEPTH), (45, FACE_Z + 1)]
    with BuildPart() as c:
        y_out = WIDTH / 2 + 3
        with BuildSketch(Plane.XZ.offset(-y_out)) as sk:    # Plane.XZ normal is -Y: this sits at Y = y_out
            Polygon(*prof, align=None)
        extrude(sk.sketch, amount=y_out - y_in)             # towards -Y, down to y_in
    return c.part


def hollow_slices() -> list[tuple[float, float, float]]:
    """(top depth, bottom depth, inset) slices of the boss hollow: its rim rounds over and curves down
    (owner 2026-11-26), a quarter circle of HOLLOW_ROUND, vertical below."""
    out, n = [], 12
    for j in range(n):
        d0, d1 = HOLLOW_ROUND * j / n, HOLLOW_ROUND * (j + 1) / n
        dm = (d0 + d1) / 2
        inset = HOLLOW_ROUND - math.sqrt(max(0.0, HOLLOW_ROUND ** 2 - dm ** 2))
        out.append((d0, d1, inset))
    out.append((HOLLOW_ROUND, RAISE_DEPTH, HOLLOW_ROUND))
    return out


def face() -> object:
    """Pump end face: flat, lock in the bore, the lowered strip and hollow for the adapter's raised parts,
    the latch groove and the lock notch."""
    with BuildPart() as p:
        with BuildSketch():
            Polygon(*outline(), align=None)
        extrude(amount=FACE_Z)
        add(band_cut(), mode=Mode.SUBTRACT)
        # hollow for the hook boss: the opening matches the owner's red circle, the rim curves down into it
        for d0, d1, inset in hollow_slices():
            with BuildSketch(Plane.XY.offset(FACE_Z - d1)) as hs:
                Polygon(*uv(BOSS_UV), align=None)
                # the rounding grows the opening outwards, so the floor keeps the boss's full footprint
                offset(amount=CLEAR + (HOLLOW_ROUND - inset), mode=Mode.REPLACE)
            extrude(hs.sketch, amount=d1 - d0 + (1.0 if d0 == 0 else 0.0), mode=Mode.SUBTRACT)
        # FACE1 test 2026-11-26: the adapter stuck ~15 deg before the end, the boss's inner wall ran into the
        # face next to the hollow. Clear what the boss sweeps over the last part of the clockwise turn (before
        # that it is outside the pump outline).
        with BuildPart(mode=Mode.PRIVATE) as bp:
            with BuildSketch(Plane.XY.offset(FACE_Z - RAISE_DEPTH)) as bsk:
                Polygon(*uv(BOSS_UV), align=None)
                offset(amount=CLEAR, mode=Mode.REPLACE)
            extrude(bsk.sketch, amount=RAISE_DEPTH + 1)
        for k in range(1, int(BOSS_SWEEP_DEG / BOSS_SWEEP_STEP) + 1):
            add(bp.part.rotate(Axis.Z, k * BOSS_SWEEP_STEP), mode=Mode.SUBTRACT)
        # rectangular groove going into the side wall of the entry-edge strip (owner 2026-11-26, marked on the
        # render): the adapter's wall latches into it at the end of the turn. Closed on top (real undercut).
        wall_y = WIDTH / 2 - BAND_W - CLEAR
        with Locations(((LATCH_X[0] + LATCH_X[1]) / 2, wall_y - LATCH_DEPTH / 2 + 0.2, FACE_Z - LATCH_Z[1])):
            Box(LATCH_X[1] - LATCH_X[0], LATCH_DEPTH + 0.4, LATCH_Z[1] - LATCH_Z[0],
                align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # notch for the lock at the far end, front side (owner: "Aussparung fuer einen Lock links unten";
        # pump photo: where the curved high wall meets the far edge)
        with Locations(((NOTCH_LOCK_X + 49.0 - OUT_NEAR) / 2 + 1.0, sum(NOTCH_LOCK_Y) / 2, FACE_Z - NOTCH_LOCK_DEPTH)):
            Box(49.0 - OUT_NEAR - NOTCH_LOCK_X + 2.0, NOTCH_LOCK_Y[1] - NOTCH_LOCK_Y[0], NOTCH_LOCK_DEPTH + 1,
                align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # pocket for the lock where the curved left side of the hollow starts (pump photo, bottom left)
        with Locations((sum(LOCK_POCKET_X) / 2, sum(LOCK_POCKET_Y) / 2, FACE_Z - RAISE_DEPTH)):
            Box(LOCK_POCKET_X[1] - LOCK_POCKET_X[0], LOCK_POCKET_Y[1] - LOCK_POCKET_Y[0], RAISE_DEPTH + 1,
                align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
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
