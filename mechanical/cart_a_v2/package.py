#!/usr/bin/env python3
"""Cart pump A v2 package study (../CART-A-V2-BRIEF.md). TEST ONLY - water only, never on a person.

Builds the v2 body form (a slim body section that flares into the head's adapter outline), places every part of the brief
(section 1) as simple solids in pump coordinates, checks that each part fits the inner cavity (wall + clearance) at FULL and
EMPTY and that no two parts collide, and writes meshes for the renders plus a JSON report.

Pump coordinates (mm): x = length (0 rear, 64.26 head joint, 70.86 head face), y = width (0 = near / cartridge side),
z = height (0 = underside). Run: ../../.venv/bin/python package.py
"""
from __future__ import annotations

import json
import math
import struct
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
from build123d import Face, Plane, Pos, Solid, Vector, Wire, export_stl, import_step

HERE = Path(__file__).resolve().parent
MECH = HERE.parent
sys.path.insert(0, str(MECH / "print" / "A_lock"))
import make_face as mf  # noqa: E402  (head outline = single source of truth)

OUT = MECH / "out" / "cart_a_v2"
V1 = MECH / "out" / "v010-cart" / "A" / "print"

# ---- form ---------------------------------------------------------------------------------------------------------
XS = 1.0                   # rear stop ring behind the barrel (owner 2026-11-27): everything from the cartridge forward moves +1.0
X_JOINT = 64.26 + XS       # head module back face (head 6.6 deep)
X_FACE = 70.86 + XS
GAP = 0.15                 # visible joint line body | head
HEAD_L, HEAD_W = 49.0, 19.0  # head section (width y, height z) = adapter outline
BODY_L, BODY_W = 38.0, 19.0  # body section: motor edge 36.4 + wall; flat top = head height (top shell printed face-down, no supports)
FLARE_X0 = 48.0 + XS       # body flares into the head from here (smoothstep, tangent at both ends); top flat before it
REAR_R = 5.0               # rear end rounded with this profile radius
WALL, CLR = 1.2, 0.2
SEAM_Z = 8.74              # parting line = cartridge axis height

# ---- package (v1 A drive, screw lane moved +2.0 in y for the chamber partition) -------------------------------------
YC, ZC = 11.46, 8.74       # cartridge axis (fixed by the adapter cup position in the head)
YS, YM = 25.635, 33.435    # screw lane, motor lane (a = 7.8)
STROKE = 23.66
PART_Y = (17.25, 18.85)    # chamber partition (cartridge chamber | drive + electronics)
BOARD = {"x": (32.6, 61.8 + XS), "y": (19.35, 36.3), "pcb_z": (8.34, 9.14), "top": 1.45, "bottom": 1.2}   # pcb centre on the seam (USB-C)
TONGUE = {"x": (58.0 + XS, 62.96 + XS), "y": (34.5, 39.96)}
CELL = {"x": (32.3 + XS, 63.8 + XS), "y": (24.3, 34.9), "z": (11.1, 14.3)}       # above the board, clear of head boss + button plunger
PINION_X1 = 32.66          # front face of the 4 mm pinion (motor boss face 28.66 + 4.0)
BOARD_NOTCH = {"x": (32.6, 33.0), "y": (31.0, 36.31)}   # board absent here: clears the pinion end
TMAG_X = (33.67, 35.27)    # TMAG5273 body on the routed board (U10 at 34.47 / 33.38), beside the magnet in the pinion front bore
USB_X, USB_Z = 42.0, 8.74  # mid-mount, centred ON the seam; x 42.0 on the routed board (40.0 left no room for the TMAG5273)
BUTTON_XY, LED_XY = (46.5, 22.05), (39.0, 22.05)   # beside the cell, clear of the board clamp strip; 3.6 mm wall between the holes
HEAD_SCREWS: list[tuple[float, float]] = []      # v2.2: no separate head any more (lock face zone is part of the halves); was KOPF10 [10,-4.5] / [10,4.5];
                                                # KOPF9's lower screw (z 3.24) ran 0.01 past the joint ring (owner print 2026-11-27)


def smooth(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def extents(x: float) -> tuple[float, float]:
    s = smooth((x - FLARE_X0) / (X_JOINT - FLARE_X0))
    return BODY_L + (HEAD_L - BODY_L) * s, BODY_W + (HEAD_W - BODY_W) * s


def dome_stations(e: float = 0.0, n: int = 6) -> list[tuple[float, float]]:
    """Rear end profile (x, inset) of the skin offset by e: quarter circle from the rear face down to 45 deg, then a straight
    45 deg facet to the full section (owner 2026-11-27 print: the rounded rear edge sagged where it meets the bed)."""
    r = REAR_R - e
    st = [(REAR_R - r * math.cos(th), REAR_R - r * math.sin(th)) for th in np.linspace(0.0, math.pi / 4, n + 1)]
    x45, d45 = st[-1]
    return st + [(x45 + (d45 - e), e)]


def dome_inset(x: float) -> float:
    st = dome_stations()
    if x >= st[-1][0]:
        return 0.0
    x45, d45 = st[-2]
    if x >= x45:
        return d45 - (x - x45)
    return REAR_R - math.sqrt(max(REAR_R ** 2 - (REAR_R - x) ** 2, 0.0))


def exact_inset(pts: list[tuple[float, float]], d: float, n: int = 240) -> list[tuple[float, float]]:
    """Exact 2D offset (inward by d) of a closed polygon, sampled at n points (same method as make_face's head groove)."""
    from build123d import BuildSketch, Mode, Polygon, offset
    with BuildSketch() as sk:
        Polygon(*pts, align=None)
        offset(amount=-d, mode=Mode.REPLACE)
    w = sk.sketch.faces()[0].outer_wire()
    return [(q.X, q.Y) for q in (w.position_at(i / n) for i in range(n))]


# owner 2026-11-27 (v2 print): the halves looked different left and right. The body is now mirror-symmetric (same corners near
# and far) and only blends into the adapter's own outline over the flare (x 49 -> joint), so the head (adapter outline) still sits
# flush. Every corner meets its top / bottom face with a 45 deg facet: the halves print bed-side down without a sagging overhang.
SYM_SHAPE = {"near_left": (5.0, 6.0), "near_right": (2.8, 3.8), "far_left": (5.0, 6.0, 2.0), "far_right": (2.8, 3.8), "near_slant": 0.0}
FACET_SLOPE = 1.0          # |dz/dy| below which a corner is replaced by a straight 45 deg line to its face


def shape_at(w: float) -> dict:
    """Corner set between the symmetric body (w = 0) and the adapter outline (w = 1)."""
    a, b = SYM_SHAPE, mf.ADAPTER_SHAPE
    lerp = lambda p, q: tuple(p[i] + (q[i] - p[i]) * w for i in range(len(p)))  # noqa: E731
    return {"near_left": lerp(a["near_left"], b["near_left"]), "near_right": lerp(a["near_right"], b["near_right"]),
            "far_left": lerp(a["far_left"], b["far_left"]), "far_right": lerp(a["far_right"], b["far_right"]),
            "near_slant": a["near_slant"] + (b["near_slant"] - a["near_slant"]) * w}


def _facet(q: list[tuple[float, float]], face_first: bool) -> list[tuple[float, float]]:
    """q: corner polyline in (u = z, v = y). Replace the part flatter than 45 deg next to the horizontal face (u = const) by a
    straight 45 deg line from the tangent point to the face; same point count."""
    pts = list(q if face_first else q[::-1])                 # pts[0] on the face, pts[-1] on the side wall
    u_face = pts[0][0]
    j = None
    for i in range(len(pts) - 1, 0, -1):                     # walk from the side wall toward the face
        du, dv = pts[i - 1][0] - pts[i][0], pts[i - 1][1] - pts[i][1]
        if abs(du) < FACET_SLOPE * abs(dv):
            j = i
            break
    if j is None or j == 0:
        return q
    u45, v45 = pts[j]
    h = abs(u_face - u45)
    sv = 1.0 if (pts[0][1] - pts[j][1]) > 0 else -1.0
    line = [(u45 + (u_face - u45) * s, v45 + sv * h * s) for s in [1 - i / j for i in range(j + 1)]]   # index 0 = face end
    out = line[:j] + pts[j:]
    return out if face_first else out[::-1]


def section_yz(L: float, W: float, d: float = 0.0, k: int = 16, m: int = 6, w: float = 1.0, facet: float = 1.0) -> list[tuple[float, float]]:
    """Section at width L (y) and height W (z), inset by d. w = 1: the head's adapter outline (make_face.ADAPTER_SHAPE),
    w = 0: the symmetric body; facet: 45 deg facets where the corners meet the top and bottom faces. Fixed point count."""
    sh = shape_at(w)
    nlu, nlv = sh["near_left"]
    nru, nrv = sh["near_right"]
    flu, flv, fln = sh["far_left"]
    fru, frv = sh["far_right"]
    sl = sh["near_slant"]

    def rr(r: float) -> float:
        return max(r - d, 0.3)

    quads = [mf._quad(d + rr(nlu), sl + d + rr(nlv), rr(nlu), rr(nlv), 180, 270, 2.0, k),     # bottom face -> near side
             mf._quad(W - d - rr(nru), d + rr(nrv), rr(nru), rr(nrv), 270, 360, 2.0, k),       # near side -> top face
             mf._quad(W - d - rr(fru), L - d - rr(frv), rr(fru), rr(frv), 0, 90, 2.0, k),      # top face -> far side
             mf._quad(d + rr(flu), L - d - rr(flv), rr(flu), rr(flv), 90, 180, fln, k)]        # far side -> bottom face
    if facet > 0:                                            # 0..1: blend between the plain and the faceted corners (same point count)
        fq = [_facet(quads[0], True), _facet(quads[1], False), _facet(quads[2], True), _facet(quads[3], False)]
        quads = [[(a[0] + (b[0] - a[0]) * facet, a[1] + (b[1] - a[1]) * facet) for a, b in zip(q, f)] for q, f in zip(quads, fq)]
    uv = []
    for i, q in enumerate(quads):
        uv += q
        a, b = q[-1], quads[(i + 1) % 4][0]
        uv += [(a[0] + (b[0] - a[0]) * j / (m + 1), a[1] + (b[1] - a[1]) * j / (m + 1)) for j in range(1, m + 1)]
    return [(v, u) for u, v in uv]          # (y, z)


def morph_w(x: float) -> float:
    """Blend weight of the adapter outline along the body: 0 behind the flare, 1 at the head joint (same curve as extents)."""
    return smooth((x - FLARE_X0) / (X_JOINT - FLARE_X0))


FACET_FADE = 4.0           # v2.2 (owner: seamless with the Accu-Chek adapter): the print facets fade out over the last 4 mm before the
                           # lock face zone, so from the joint to the face the outline is exactly the adapter outline


def facet_at(x: float) -> float:
    return 1.0 - smooth((x - (X_JOINT - FACET_FADE)) / FACET_FADE)


def section_at(x: float, d: float = 0.0) -> list[tuple[float, float]]:
    L, W = extents(x)
    return section_yz(L, W, d, w=morph_w(x), facet=facet_at(x))


def inner_poly(x: float, extra: float = 0.0) -> np.ndarray:
    L, W = extents(x)
    return np.array(section_at(x, dome_inset(x) + WALL + extra))


def inside(poly: np.ndarray, y: float, z: float) -> bool:
    yy, zz = poly[:, 0], poly[:, 1]
    y2, z2 = np.roll(yy, -1), np.roll(zz, -1)
    cross = ((zz > z) != (z2 > z)) & (y < (y2 - yy) * (z - zz) / np.where(z2 - zz == 0, 1e-12, z2 - zz) + yy)
    return bool(np.count_nonzero(cross) % 2)


# ---- body mesh ------------------------------------------------------------------------------------------------------
def body_rings(e: float = 0.0, x_end: float = X_JOINT - GAP, n_dome: int = 12) -> list[np.ndarray]:
    """Rings of the outer surface offset inward by e (e = 0: outer skin)."""
    stations = []
    stations += dome_stations(e, n_dome // 2)
    stations += [(x, e) for x in np.linspace(REAR_R, FLARE_X0, 8)[1:]]
    stations += [(x, e) for x in np.arange(FLARE_X0 + 0.8, x_end, 0.8)]
    stations.append((x_end, e))
    rings = []
    for x, d in stations:
        rings.append(np.array([(x, y, z) for y, z in section_at(x, d)]))
    return rings


def rings_to_tris(rings: list[np.ndarray]) -> np.ndarray:
    tris = []
    n = len(rings[0])
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            tris += [(a[i], b[i], b[j]), (a[i], b[j], a[j])]
    yz = rings[0][:, 1:]
    ccw = (np.roll(yz[:, 0], -1) * yz[:, 1] - yz[:, 0] * np.roll(yz[:, 1], -1)).sum() < 0   # ring sense seen from +x
    for ring, outward_minus_x in ((rings[0], True), (rings[-1], False)):
        c = ring.mean(axis=0)
        for i in range(n):
            t = (c, ring[i], ring[(i + 1) % n])             # normal +x when the ring is CCW
            tris.append(t[::-1] if outward_minus_x == ccw else t)
    t = np.array(tris)
    vol = np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6
    return t if vol > 0 else t[:, ::-1]


def mesh_volume(t: np.ndarray) -> float:
    return float(abs(np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6))


def write_stl(path: Path, t: np.ndarray) -> None:
    with open(path, "wb") as f:
        f.write(b"cart_a_v2".ljust(80, b" "))
        f.write(struct.pack("<I", len(t)))
        for a, b, c in t:
            nrm = np.cross(b - a, c - a)
            nrm = nrm / (np.linalg.norm(nrm) or 1.0)
            f.write(struct.pack("<12fH", *nrm, *a, *b, *c, 0))


# ---- parts ----------------------------------------------------------------------------------------------------------
def cyl_x(x0: float, x1: float, y: float, z: float, d: float) -> Solid:
    return Solid.make_cylinder(d / 2, x1 - x0, Plane(origin=(x0, y, z), x_dir=(0, 1, 0), z_dir=(1, 0, 0)))


def cone_x(x0: float, x1: float, y: float, z: float, d0: float, d1: float) -> Solid:
    return Solid.make_cone(d0 / 2, d1 / 2, x1 - x0, Plane(origin=(x0, y, z), x_dir=(0, 1, 0), z_dir=(1, 0, 0)))


def cyl_z(x: float, y: float, z0: float, z1: float, d: float) -> Solid:
    return Solid.make_cylinder(d / 2, z1 - z0, Plane(origin=(x, y, z0)))


def box(x: tuple, y: tuple, z: tuple) -> Solid:
    return Solid.make_box(x[1] - x[0], y[1] - y[0], z[1] - z[0], Plane(origin=(x[0], y[0], z[0])))


def parts(state: str = "full") -> dict[str, tuple[Solid, str, bool]]:
    """name -> (solid, material, moves_with_the_stopper). state 'empty' shifts the moving parts by the stroke."""
    dx = STROKE if state == "empty" else 0.0
    pz0, pz1 = BOARD["pcb_z"]
    P: dict[str, tuple[Solid, str, bool]] = {}
    c0 = 27.56 + XS                                   # barrel rear end face, sits on the rear stop ring
    glass = cyl_x(c0, c0 + 32, YC, ZC, 10.95) - cyl_x(c0 - 0.16, c0 + 32.14, YC, ZC, 9.25)
    glass = glass + (cone_x(c0 + 32, c0 + 36, YC, ZC, 10.95, 5.6) - cone_x(c0 + 32, c0 + 35.44, YC, ZC, 9.25, 3.2))
    P["cartridge_glass"] = (glass + cyl_x(c0 + 36, c0 + 38.1, YC, ZC, 5.6), "glass", False)
    P["cartridge_cap"] = (cyl_x(c0 + 38.1, c0 + 43.0, YC, ZC, 7.5), "alu", False)
    if not dx:
        P["water"] = (cyl_x(c0 + 8.3, c0 + 31.84, YC, ZC, 9.2), "water", True)   # EMPTY: no water left
    P["stopper"] = (cyl_x(c0 + 0.3 + dx, c0 + 8.3 + dx, YC, ZC, 9.25), "rubber", True)
    P["pusher"] = (cyl_x(c0 - 0.5 + dx, c0 + 0.3 + dx, YC, ZC, 8.4), "plastic_dark", True)   # passes the d8.9 stop ring
    P["stem"] = (cyl_x(3.6 + dx, c0 - 0.5 + dx, YC, ZC, 2.0), "steel", True)                 # 1.0 longer than v1
    yoke = box((1.6 + dx, 3.6 + dx), (YC - 3.0, YS + 3.0), (ZC - 2.75, ZC + 2.75))
    P["yoke"] = (yoke, "plastic_dark", True)
    P["screw"] = (cyl_x(0.6, 32.0, YS, ZC, 2.0), "steel", False)          # front end inside rib_f (v1: 32.46)
    P["gear"] = (cyl_x(28.76, 30.76, YS, ZC, 12.6), "brass", False)
    P["washer_r"] = (cyl_x(28.56, 28.76, YS, ZC, 5.0), "steel", False)
    P["washer_f"] = (cyl_x(30.76, 30.96, YS, ZC, 5.0), "steel", False)
    P["motor"] = (cyl_x(11.76, 19.76, YM, ZC, 6.0), "motor", False)
    P["gearhead"] = (cyl_x(19.76, 27.86, YM, ZC, 6.0), "motor_head", False)
    P["motor_rear"] = (cyl_x(11.06, 11.76, YM, ZC, 3.0), "plastic_dark", False)
    P["shaft"] = (cyl_x(27.86, 28.66, YM, ZC, 3.5), "steel", False)              # gearhead front boss d3.5 x 0.8 (NFP drawing)
    # market m0.3 z12 pinions are 4 mm long (AliExpress / GHW): pinion on the d2 D-shaft against the boss, x 28.66-32.66;
    # the d2 x 1 angle magnet sits in its free front bore (x 31.66-32.66)
    P["pinion"] = (cyl_x(28.66, PINION_X1, YM, ZC, 4.2) - cyl_x(PINION_X1 - 1.0, PINION_X1 + 0.1, YM, ZC, 2.0), "brass", False)
    P["magnet"] = (cyl_x(PINION_X1 - 1.0, PINION_X1, YM, ZC, 2.0), "magnet", False)
    ol = json.loads((HERE / "board_outline_a.json").read_text())["outline_xy"]                 # routed board (notches, tongue, wing)
    P["board"] = (Solid.extrude(Face(Wire.make_polygon([Vector(x, y, pz0) for x, y in ol], close=True)), Vector(0, 0, pz1 - pz0)), "pcb", False)
    notch = box((BOARD["x"][0] - 0.1, BOARD_NOTCH["x"][1]), BOARD_NOTCH["y"], (pz0 - 3.0, pz1 + 3.0))
    P["ko_board_top"] = (box((BOARD["x"][0], BOARD["x"][1]), BOARD["y"], (pz1, pz1 + BOARD["top"])) - notch, "ko", False)
    P["ko_board_bottom"] = (box((BOARD["x"][0], 60.5), BOARD["y"], (pz0 - BOARD["bottom"], pz0)) - notch, "ko", False)
    P["usb_c"] = (box((USB_X - 4.47, USB_X + 4.47), (36.8 - 7.35, 36.8), (USB_Z - 1.63, USB_Z + 1.63)), "steel", False)
    # routed board (cart_a6.kicad_pcb): Alps SPVS410100 lock switch on the tongue underside, lever toward +x on y 37.46 (free 65.72,
    # ON 64.68, end 64.18); the pin preloads it: tip 64.85 with the ball free, 64.48 locked (board README, bench-tune)
    P["lock_switch"] = (box((60.64, 63.94), (35.58, 39.08), (pz0 - 1.0, pz0)), "black", False)
    P["lock_pin"] = (cyl_x(64.48, 66.56 + XS, 37.46, 7.07, 2.0), "steel", False)
    P["hj840"] = (box((54.2, 60.4), (31.76, 38.76), (pz1, pz1 + 1.45)), "black", False)                 # radio module, antenna end toward +y
    P["j2_motor"] = (box((48.2, 54.4), (20.4, 31.4), (pz0 - 3.4, pz0)), "black", False)                # PicoBlade 4 pin, opening toward -x
    P["j2_plug"] = (box((41.6, 48.2), (22.6, 29.2), (pz0 - 3.4, pz0 - 0.1)), "black", False)           # the motor plug lies under the board
    P["j3_cell"] = (box((59.46, 62.54), (25.6, 31.4), (pz0 - 4.6, pz0)), "black", False)               # AVX 9175 IDC + cap (height estimate)
    P["tmag"] = (box(TMAG_X, (YM - 1.0, YM + 1.0), (pz1, pz1 + 0.75)), "black", False)
    P["sw1"] = (box((BUTTON_XY[0] - 1.75, BUTTON_XY[0] + 1.75), (BUTTON_XY[1] - 1.75, BUTTON_XY[1] + 1.75), (pz1, pz1 + 1.5)), "black", False)
    P["led"] = (box((LED_XY[0] - 0.8, LED_XY[0] + 0.8), (LED_XY[1] - 0.8, LED_XY[1] + 0.8), (pz1, pz1 + 0.6)), "led", False)
    P["sounder"] = (box((55.0, 59.0), (24.0, 28.0), (pz0 - 2.5, pz0)), "black", False)            # FUET-4020 (BZ1 at 57.0 / 26.0)
    P["cell"] = (box(CELL["x"], CELL["y"], CELL["z"]), "cell", False)
    return P


def top_z(x: float, y: float) -> float:
    """Outer top surface height at (x, y) (flat part of the roof)."""
    return extents(x)[1]


def housing_features() -> dict[str, tuple[Solid, str]]:
    """Internal walls that matter for the package (not the whole shell): chamber partition + rear seal ring, head screw bosses,
    button plunger and LED light pipe (they cross the cavity)."""
    H: dict[str, tuple[Solid, str]] = {}
    # rear stop ring = chamber rear wall: the barrel's rear end face (OD 10.95 / ID 9.25) rests on it; only d8.9 stays open for the
    # pusher (d8.4) and the stem. A 0.5 TPU washer on it takes up the cartridge length tolerance and seals (detail CAD).
    sec = [(min(y, PART_Y[1]), z) for y, z in inner_poly(28.06)]   # the cavity section, cut at the partition
    face = Face(Wire.make_polygon([Vector(27.56, y, z) for y, z in sec], close=True))
    H["rear_stop"] = (Solid.extrude(face, Vector(XS, 0, 0)) - cyl_x(27.4, 28.7, YC, ZC, 8.9), "shell")
    H["partition"] = (box((27.56, X_JOINT - GAP), PART_Y, (WALL, 15.4)), "shell")
    bx, by = BUTTON_XY
    H["button_plunger"] = (cyl_z(bx, by, BOARD["pcb_z"][1] + 1.6, top_z(bx, by) - 0.05, 3.0), "accent")
    lx, ly = LED_XY
    H["light_pipe"] = (cyl_z(lx, ly, BOARD["pcb_z"][1] + 0.7, top_z(lx, ly) - 0.05, 2.0), "clear")
    return H


EXCLUDE = {frozenset(p) for p in [("cartridge_glass", "stopper"), ("cartridge_glass", "water"), ("stopper", "water"), ("stopper", "pusher"),
                                   ("pusher", "stem"), ("stem", "yoke"), ("yoke", "screw"), ("screw", "gear"), ("screw", "washer_r"),
                                   ("screw", "washer_f"), ("gear", "washer_r"), ("gear", "washer_f"), ("gear", "pinion"), ("motor", "gearhead"),
                                   ("motor", "motor_rear"), ("gearhead", "shaft"), ("shaft", "pinion"), ("pinion", "magnet"),
                                   ("cartridge_glass", "cartridge_cap"), ("cartridge_glass", "pusher"), ("cartridge_glass", "rear_stop"),
                                   ("board", "ko_board_top"), ("board", "ko_board_bottom"), ("board", "usb_c"), ("board", "lock_switch"),
                                   ("board", "tmag"), ("board", "sw1"), ("board", "hj840"), ("board", "j2_motor"), ("board", "j3_cell"), ("ko_board_top", "hj840"), ("ko_board_bottom", "j2_motor"), ("ko_board_bottom", "j3_cell"), ("j2_motor", "j2_plug"), ("ko_board_bottom", "j2_plug"), ("board", "led"), ("board", "sounder"), ("ko_board_top", "usb_c"),
                                   ("ko_board_bottom", "usb_c"), ("ko_board_top", "lock_switch"), ("ko_board_top", "tmag"), ("ko_board_top", "sw1"),
                                   ("ko_board_top", "led"), ("ko_board_bottom", "sounder"), ("lock_switch", "lock_pin"), ("ko_board_bottom", "lock_switch"), ("sw1", "button_plunger"),
                                   ("led", "light_pipe"), ("ko_board_top", "button_plunger"), ("ko_board_top", "light_pipe"),
                                   ("washer_f", "pinion"), ("washer_r", "pinion"), ("magnet", "pinion"), ("shaft", "pinion")]}


INTO_WALL = {"screw": 0.6}      # rear end in a pocket of the rear wall (v1 screw_in_wall)
ON_WALL = {"usb_c"}             # front face sits on the inner wall by design


def fit_check(name: str, solid: Solid) -> dict:
    pts = []
    for e in solid.edges():                                # extremes of primitives lie on their edges
        try:
            pts += [e.position_at(t) for t in np.linspace(0, 1, 25)]
        except Exception:                                  # degenerate edge (cone apex, seam)
            continue
    worst, bad = None, 0
    for v in pts:
        x, y, z = v.X, v.Y, v.Z
        if x >= X_JOINT - GAP:
            continue                       # inside the head (checked by make_face / v1 cart_check)
        if x < WALL and x < INTO_WALL.get(name, WALL) - 1e-6:
            bad += 1
            continue
        if x < WALL:
            continue
        if not inside(inner_poly(x, -0.02 if name in ON_WALL else CLR), y, z):
            bad += 1
            worst = (round(x, 2), round(y, 2), round(z, 2))
    return {"part": name, "outside_points": bad, "example": worst}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"form": {"body_section_mm": [BODY_L, BODY_W], "head_section_mm": [HEAD_L, HEAD_W], "flare_from_x": FLARE_X0,
                             "rear_radius": REAR_R, "seam_z": SEAM_Z}}
    outer = rings_to_tris(body_rings())
    write_stl(OUT / "body_outer.stl", outer)
    write_stl(OUT / "body_inset_seam.stl", rings_to_tris(body_rings(e=0.35)))
    body_vol = mesh_volume(outer)

    import head as hd                                                                   # v2.2: the lock face zone of the shells
    head = hd.zone_placed()                                                             # (x 65.26-71.86), as a real solid
    adapter = Pos(XS, 0, 0) * import_step(str(V1 / "cart_A_adapter_dummy_placed.step"))
    needle = Pos(XS, 0, 0) * import_step(str(V1 / "cart_A_needle_placed.step"))
    for nm, shp in (("head", head), ("adapter", adapter), ("needle", needle)):
        export_stl(shp, str(OUT / f"{nm}.stl"), tolerance=0.01, angular_tolerance=0.1)
    hb, ab = head.bounding_box(), adapter.bounding_box()

    results = {"fit": [], "collisions": {}}
    H = housing_features() | {"head": (head, "shell")}                                  # the head is checked against every part
    for state in ("full", "empty"):
        P = parts(state)
        allp = {k: v[0] for k, v in P.items()} | {k: v[0] for k, v in H.items()}
        if state == "full":
            for nm, (sol, mat, _mv) in P.items():
                export_stl(sol, str(OUT / f"part__{nm}__{mat}.stl"), tolerance=0.01, angular_tolerance=0.1)
            for nm, (sol, mat) in H.items():
                export_stl(sol, str(OUT / f"feat__{nm}__{mat}.stl"), tolerance=0.01, angular_tolerance=0.1)
        for nm, (sol, _mat, mv) in P.items():
            if state == "full" or mv:
                r = fit_check(nm, sol)
                if r["outside_points"]:
                    results["fit"].append(r | {"state": state})
        hits = []
        for a, b in combinations(allp, 2):
            if frozenset((a, b)) in EXCLUDE or (a.startswith("ko_") and b.startswith("ko_")) or (a in H and b in H):
                continue
            if state == "empty" and not (P.get(a, (0, 0, False))[2] or P.get(b, (0, 0, False))[2]):
                continue
            sa, sb = allp[a], allp[b]
            if not sa.bounding_box().overlaps(sb.bounding_box()):
                continue
            inter = sa & sb
            v = inter.volume if inter is not None else 0.0
            if v > 0.01:
                hits.append([a, b, round(v, 3)])
        results["collisions"][state] = hits

    L_total = ab.max.X - 0.0
    report["size"] = {
        "body_with_head_mm": [round(X_FACE, 2), round(HEAD_L, 2), round(HEAD_W, 2)],
        "with_adapter_mm": [round(L_total, 2), round(max(HEAD_L, ab.max.Y - ab.min.Y), 2), round(HEAD_W, 2)],
        "body_volume_ml": round(body_vol / 1000, 2),
        "head_volume_ml": round(head.volume / 1000, 2),
        "adapter_box_ml": round((ab.max.X - ab.min.X) * (ab.max.Y - ab.min.Y) * (ab.max.Z - ab.min.Z) / 1000, 2),
        "insight_box_ml": 83.0, "insight_mm": [84, 52, 19],
        "head_bbox": [[round(hb.min.X, 2), round(hb.min.Y, 2), round(hb.min.Z, 2)], [round(hb.max.X, 2), round(hb.max.Y, 2), round(hb.max.Z, 2)]],
    }
    yz = np.array(section_yz(HEAD_L, HEAD_W))
    area = 0.5 * abs(np.dot(yz[:, 0], np.roll(yz[:, 1], -1)) - np.dot(yz[:, 1], np.roll(yz[:, 0], -1)))
    head_env, adapter_env = area * (X_FACE - X_JOINT) / 1000, area * 9.5 / 1000
    report["size"]["head_envelope_ml"] = round(head_env, 2)
    report["size"]["adapter_envelope_ml"] = round(adapter_env, 2)
    report["size"]["total_envelope_ml"] = round(body_vol / 1000 + head_env + adapter_env, 1)
    report["size"]["vs_insight_box"] = f"{(body_vol / 1000 + head_env + adapter_env) / 83.0 - 1:+.0%}"
    report["check"] = results
    report["pass"] = not results["fit"] and not any(results["collisions"].values())
    (OUT / "package_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
