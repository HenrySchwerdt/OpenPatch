#!/usr/bin/env python3
"""Cart pump A v2: everything for one assembly test on one print bed. TEST ONLY - water only, never on a person.

Owner 2026-11-27: all parts on one print, no brim, plus printed stand-ins for the board, the motor and the bought metal parts so the
whole pump can be put together once. Stand-ins (fit only, not functional):
- board: 0.8 plate + tongue, USB-C receptacle, SW1, LED, TMAG, lock switch; 6 feet under it (bottom parts zone) so it prints flat;
- motor: body + gearhead d6, rear boss, shaft, pinion d4.2, magnet, lying with a flat;
- gear: d12.6 x 2 disc; screw rod d2 x 31.4, stem d2 x 26.9, lock pin d2 x 3.3, light pipe d2 x 9.06 (lying, flat bottom);
  2 hex nuts M2 size (AF 4.0 x 1.6). M2 x 0.4 cannot be printed as a thread with a 0.4 nozzle: plain d2 rods test the fit.
Real parts from shells.py (bottom, top, yoke, plunger, pusher) and the head KOPF9. Writes ../out/cart_a_v2/print/v2_all_bed.stl.
Run after shells.py: ../../.venv/bin/python bed_all.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np
from build123d import Plane, Pos, Solid, export_stl

import package as pk

sys.path.insert(0, str(pk.MECH / "print"))
from make_x2_housing import read_stl  # noqa: E402

P = pk.OUT / "print"
B, C = pk.box, pk.cyl_x
GAP = 5.0          # between parts on the bed
BED = (250.0, 220.0)


def flat_rod(segments: list[tuple[float, float]], flat: float = 0.35) -> Solid:
    """Coaxial cylinders along x (length, diameter), lying on the bed with the bottom flattened by `flat` (prints without a brim)."""
    r = max(d for _l, d in segments) / 2
    x, s = 0.0, None
    for ln, d in segments:
        c = C(x, x + ln, 0.0, r, d)
        s = c if s is None else s + c
        x += ln
    s = s - B((-1, x + 1), (-10, 10), (-1, flat))
    return Pos(0, 0, -flat) * s


def hex_nut(af: float = 4.0, t: float = 1.6, hole: float = 2.2) -> Solid:
    from build123d import Face, Vector, Wire
    import math
    rc = af / 2 / math.cos(math.radians(30))
    pts = [Vector(rc * math.cos(math.radians(60 * i)), rc * math.sin(math.radians(60 * i)), 0) for i in range(6)]
    return Solid.extrude(Face(Wire.make_polygon(pts, close=True)), Vector(0, 0, t)) - Solid.make_cylinder(hole / 2, t + 1, Plane(origin=(0, 0, -0.5)))


def board_dummy() -> Solid:
    pz0, pz1 = pk.BOARD["pcb_z"]
    z_bed = pz0 - 1.6
    s = B(pk.BOARD["x"], pk.BOARD["y"], (pz0, pz1)) + B(pk.TONGUE["x"], pk.TONGUE["y"], (pz0, pz1))
    s = s + B((pk.USB_X - 4.47, pk.USB_X + 4.47), (36.8 - 7.35, 36.8), (z_bed, pk.USB_Z + 1.63))       # mid-mount receptacle
    bx, by = pk.BUTTON_XY
    lx, ly = pk.LED_XY
    s = s + B((bx - 1.75, bx + 1.75), (by - 1.75, by + 1.75), (pz1, pz1 + 1.5))                       # SW1
    s = s + B((lx - 0.8, lx + 0.8), (ly - 0.8, ly + 0.8), (pz1, pz1 + 0.6))                           # LED
    s = s + B((32.8, 34.8), (pk.YM - 1.0, pk.YM + 1.0), (pz1, pz1 + 0.75))                            # TMAG5273
    s = s + B((59.76 + pk.XS, 63.26 + pk.XS), (37.46 - 1.75, 37.46 + 1.75), (z_bed, pz0))             # lock switch (underside)
    for x in (34.5, 47.0, 59.0):                                                                       # print feet in the bottom parts zone
        for y in (21.5, 33.0):
            s = s + B((x - 1.0, x + 1.0), (y - 1.0, y + 1.0), (z_bed, pz0))
    return Pos(0, 0, -z_bed) * s


def stand_ins() -> dict[str, Solid]:
    return {
        "board_dummy": board_dummy(),
        "motor_dummy": flat_rod([(0.7, 3.0), (16.1, 6.0), (0.9, 1.5), (2.0, 4.2), (1.0, 2.0)]),
        "gear_dummy": Solid.make_cylinder(6.3, 2.0) - Solid.make_cylinder(1.1, 3.0, Plane(origin=(0, 0, -0.5))),
        "screw_rod": flat_rod([(31.4, 2.0)]),
        "stem_rod": flat_rod([(26.9, 2.0)]),
        "lock_pin": flat_rod([(3.3, 2.0)]),
        "light_pipe_rod": flat_rod([(9.06, 2.0)]),
        "nut_a": hex_nut(), "nut_b": hex_nut(),
    }


def load(path: Path) -> np.ndarray:
    t = read_stl(path).reshape(-1, 3, 3).astype(float)
    mn, mx = t.reshape(-1, 3).min(0), t.reshape(-1, 3).max(0)
    return t - np.array([(mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, mn[2]])


def rot90(t: np.ndarray) -> np.ndarray:
    r = t.copy()
    r[..., 0], r[..., 1] = -t[..., 1], t[..., 0]
    return r


def shelf(items: list[tuple[str, float, float]], width: float) -> tuple[float, dict]:
    """Shelf packing of (name, w, h) rectangles into a strip of `width`; returns the used height and the lower-left corners."""
    x, y, row_h, pos = 0.0, 0.0, 0.0, {}
    for n, w, h in sorted(items, key=lambda it: -it[2]):
        if x + w > width + 1e-6:
            x, y, row_h = 0.0, y + row_h + GAP, 0.0
        pos[n] = (x, y)
        x, row_h = x + w + GAP, max(row_h, h)
    return y + row_h, pos


def pack(meshes: dict[str, np.ndarray]) -> list[np.ndarray]:
    """Compact layout around the bed centre (owner: short travel): each part lies with its long side along x or y, strip widths
    from 90 to 200 mm are tried, the smallest square-ish footprint wins."""
    best = None
    for rot_long in (False, True):                       # long side along x, or along y
        oriented = {}
        for n, t in meshes.items():
            ext = np.ptp(t.reshape(-1, 3), axis=0)
            oriented[n] = rot90(t) if (ext[0] >= ext[1]) == rot_long else t
        items = [(n, *np.ptp(t.reshape(-1, 3), axis=0)[:2]) for n, t in oriented.items()]
        for width in np.arange(90.0, 201.0, 2.0):
            if any(w > width for _n, w, _h in items):
                continue
            h, pos = shelf(items, width)
            used_w = max(pos[n][0] + w for n, w, _h in items)
            score = max(used_w, h) ** 2 + used_w * h          # small and square
            if h <= BED[1] and (best is None or score < best[0]):
                best = (score, oriented, pos)
    _s, oriented, pos = best
    out = []
    for n, t in oriented.items():
        ext = np.ptp(t.reshape(-1, 3), axis=0)
        x0, y0 = pos[n]
        out.append(t + np.array([x0 + ext[0] / 2, y0 + ext[1] / 2, 0]))
    return out


def main() -> None:
    for k, s in stand_ins().items():
        export_stl(s, str(P / f"fit_{k}.stl"), tolerance=0.01, angular_tolerance=0.1)
    names = ["v2_bottom", "v2_top", "kopf9", "fit_board_dummy", "v2_yoke", "v2_pusher", "v2_button_plunger", "fit_motor_dummy",
             "fit_gear_dummy", "fit_screw_rod", "fit_stem_rod", "fit_light_pipe_rod", "fit_lock_pin", "fit_nut_a", "fit_nut_b"]
    paths = {n: (pk.MECH / "print" / "cart_A" / "kopf9_centered.stl" if n == "kopf9" else P / f"{n}.stl") for n in names}
    meshes = {n: load(p) for n, p in paths.items()}
    placed = pack(meshes)
    tris = np.concatenate(placed)
    c = tris.reshape(-1, 3)
    tris = tris - np.array([(c[:, 0].min() + c[:, 0].max()) / 2, (c[:, 1].min() + c[:, 1].max()) / 2, 0])
    span = np.ptp(tris.reshape(-1, 3), axis=0)
    assert span[0] <= BED[0] and span[1] <= BED[1], span
    with open(P / "v2_all_bed.stl", "wb") as f:
        f.write(b"cart_a_v2 all parts".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for a, b, cc in tris:
            nrm = np.cross(b - a, cc - a)
            nrm = nrm / (np.linalg.norm(nrm) or 1.0)
            f.write(struct.pack("<12fH", *nrm, *a, *b, *cc, 0))
    print("bed", np.round(span, 1), "parts", len(names))


if __name__ == "__main__":
    main()
