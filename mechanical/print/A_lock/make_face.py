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
  lock: bore, windows, undercut groove, 45 deg lip underside, seal recess (no key slot)
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


FAR_END_CORNER_R = 5.0      # both far-end corners (traced bottom-right corner ~5)


def outline() -> list[tuple[float, float]]:
    """Pump end outline = the adapter's outer contour, traced on the owner's top-down adapter photo (2026-11-26):
    both long edges fitted as lines and made parallel (photo rotation and keystone removed), scaled to 49 x 19,
    mirrored (the adapter face lies face to face on the pump). Owner: the far end is one straight line, the
    bump seen there is perspective (that side is raised), so beyond X 30 the traced points are replaced by the two
    long edges, a straight far edge and two equal corner arcs.
    Points in adapter_outline.json (pump X, Y in mm), clipped to the 19 mm width."""
    import json
    pts = json.loads((HERE / "adapter_outline.json").read_text())
    ys, yf = WIDTH / 2 - BORE_OFFSET_Y, -(WIDTH / 2 + BORE_OFFSET_Y)
    pts = [(x, min(ys, max(yf, y))) for x, y in pts]
    x_cut, x_end, r = 30.0, 49.0 - OUT_NEAR, FAR_END_CORNER_R
    keep = [x <= x_cut for x, _ in pts]
    n = len(pts)
    start = next(i for i in range(n) if keep[i] and not keep[i - 1])      # first kept point after the gap
    chain = []
    i = start
    while keep[i % n] and len(chain) < n:
        chain.append(pts[i % n]); i += 1
    # chain runs from one long edge round the near end to the other; close it over the far end
    y_last = chain[-1][1]
    side_a, side_b = chain[-1][1], chain[0][1]          # continue the traced long edges without a jog
    bottom = [(x_cut, side_a), (x_end - r, side_a)]
    sa = 1 if side_a > 0 else -1
    for k in range(1, 12):
        t = k / 12 * math.pi / 2
        bottom.append((x_end - r + r * math.sin(t), side_a - sa * r + sa * r * math.cos(t)))
    bottom += [(x_end, side_a - sa * r), (x_end, side_b + sa * r)]
    for k in range(1, 12):
        t = k / 12 * math.pi / 2
        bottom.append((x_end - r + r * math.cos(t), side_b + sa * r - sa * r * math.sin(t)))
    bottom += [(x_end - r, side_b), (x_cut, side_b)]
    return chain + bottom


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
BAND_EXTRA = -2.2          # FACE3 test (owner, C = 2.5): the adapter's ramp starts 2.5 later than the slope; slope top moved 2.2 towards the far end (0.3 play)
BAND_W = 1.6               # raised wall along the adapter's entry-side edge (p26: boss top boundary at v 1.6)
# Hook boss (p26 outline, incl. the hook lobe), run past the outline on the right so it merges with the band.
# Owner 2026-11-26: it does not reach the far end on the left (front) side; there the pump face stays at full
# height and the boundary curves gently round (pump photo: the high wall left of the window ring). Smooth curve
# through these pump-photo points (X, Y), converted to (u, v) = (X + CUP_U, W/2 - Y).
FAR_LEFT_CURVE_XY = [(22.1, -5.6), (23.6, -5.6), (25.3, -5.6), (30.4, -6.1), (34.5, -5.5), (36.7, -4.2), (38.5, -2.0), (40.0, 0.0)]  # traced on the photo (tilt removed)


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
HOLLOW_UP = 1.5            # FACE2 test: still caught at C, owner: move the hollow's near edge 1-2 mm towards the bore
BOSS_UV = ([(35.1 - HOLLOW_UP, 6.5), (33.9 - HOLLOW_UP, 5.5), (34.3 - HOLLOW_UP, 2.6), (36.0 - HOLLOW_UP, 1.2),
            (36.0 - HOLLOW_UP, -2.0), (55.0, -2.0), (55.0, 8.0)]
           + _curve_uv[::-1] + [(35.1 - HOLLOW_UP, 15.1)])
RAISE_DEPTH = 2.4          # FACE3 test (owner, A = B = 2 mm gap at 4.3): raised parts ~2.3 high, 0.1 play
BOSS_SWEEP_DEG, BOSS_SWEEP_STEP = 45.0, 1.0   # front end of the boss near wall leaves the outline only after ~38 deg
HOLLOW_ROUND = 2.0         # convex round-over of the edge into the hollow (owner: rounded, side photo of the original shows both top corners of the front wall rounded)
OUTER_ROUND, OUTER_ROUND_X0 = 0.0, 20.0   # owner: the outer front edge is sharp ("ganz links aussen eckig"), only the inner edge is rounded
NOTCH_LOCK_X = 35.9        # lock notch at the far end, front side: from here to the far edge (photo)
NOTCH_LOCK_Y = (-6.7, -2.5)   # runs into the hollow so no thin pillar is left between them (owner)
NOTCH_LOCK_DEPTH = 5.0
LOCK_POCKET_X = (23.2, 27.4)   # lock pocket in the curved left side of the hollow; widened (owner, FACE3: 'noch breiter')
LOCK_POCKET_Y = (-7.7, -5.0)
LOCK_POCKET_DEPTH = 5.8      # deeper than the hollow so it stays a pocket now the hollow reaches over it
LATCH_X = (13.6, 21.0)     # latch groove along the strip wall: from the foot of the slope back into the hollow (owner: bigger, so the adapter's catch fits for sure)
LATCH_Z = (0.7, 3.0)       # below the face: 0.7 roof; runs a little below the shallower strip floor
LATCH_DEPTH = 1.6          # into the wall (towards -Y)


def band_cut() -> object:
    """Strip for the adapter's thin entry-side wall: one flat 45 deg ramp, then 4.3 deep to the far end."""
    x_s = RAMP_U0 - CUP_U - CLEAR - BAND_EXTRA
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
    """(top depth, bottom depth, grow) slices of the boss hollow. Owner 2026-11-26: the edge from the face into
    the hollow is a convex quarter circle bulging upwards (bull-nose), "genau andersrum" than the concave scoop of
    the first try. grow = how far the opening is widened beyond the boss outline at that depth."""
    D, R, n = RAISE_DEPTH, min(HOLLOW_ROUND, RAISE_DEPTH), 12
    if R <= 0:
        return [(0.0, D, 0.0)]
    out = []
    for j in range(n):
        d0, d1 = R * j / n, R * (j + 1) / n
        dm = (d0 + d1) / 2
        out.append((d0, d1, R - math.sqrt(max(0.0, R * R - (R - dm) ** 2))))
    if D > R:
        out.append((R, D, 0.0))
    return out


def face() -> object:
    """Pump end face: flat, lock in the bore, the lowered strip and hollow for the adapter's raised parts,
    the latch groove and the lock notch."""
    with BuildPart() as p:
        with BuildSketch():
            Polygon(*outline(), align=None)
        extrude(amount=FACE_Z)
        add(band_cut(), mode=Mode.SUBTRACT)
        # owner's photo of the original pump end (side view, 2026-11-26): at the far end the front side stays at
        # full height and its OUTER edge (end face to the black front) is rounded, the drop into the hollow is
        # straight. Quarter-round cutter along the front edge from OUTER_ROUND_X0 to the far end.
        y_e = -(WIDTH / 2 + BORE_OFFSET_Y)
        if OUTER_ROUND <= 0:
            y_e = None
        prof = [] if y_e is None else [(y_e - 1, FACE_Z + 1), (y_e - 1, FACE_Z - OUTER_ROUND)]
        if y_e is not None:
            prof += [(y_e + OUTER_ROUND - OUTER_ROUND * math.cos(a * math.pi / 32),
                      FACE_Z - OUTER_ROUND + OUTER_ROUND * math.sin(a * math.pi / 32)) for a in range(17)]
            prof += [(y_e + OUTER_ROUND, FACE_Z + 1)]
        if y_e is not None:
            with BuildSketch(Plane.YZ.offset(OUTER_ROUND_X0)) as rs:
                Polygon(*prof, align=None)
            extrude(rs.sketch, amount=49.0 - OUT_NEAR - OUTER_ROUND_X0 + 1, mode=Mode.SUBTRACT)
        # hollow for the hook boss: the opening matches the owner's red circle, the rim curves down into it
        for d0, d1, inset in hollow_slices():
            with BuildSketch(Plane.XY.offset(FACE_Z - d1)) as hs:
                Polygon(*uv(BOSS_UV), align=None)
                # bull-nose edge: the top slices are a little wider, the floor keeps the boss outline + clearance
                offset(amount=CLEAR + inset, mode=Mode.REPLACE)
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
        # (no notch at the far end any more: owner 2026-11-26, the corner stays at full height and rounds down)
        # pocket for the lock where the curved left side of the hollow starts (pump photo, bottom left)
        with Locations((sum(LOCK_POCKET_X) / 2, sum(LOCK_POCKET_Y) / 2, FACE_Z - LOCK_POCKET_DEPTH)):
            Box(LOCK_POCKET_X[1] - LOCK_POCKET_X[0], LOCK_POCKET_Y[1] - LOCK_POCKET_Y[0], LOCK_POCKET_DEPTH + 1,
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
    # (no arc slot for the seal's key tab: owner 2026-11-26, not needed, face stays closed there)
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
