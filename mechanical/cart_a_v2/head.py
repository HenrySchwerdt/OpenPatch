#!/usr/bin/env python3
"""Cart pump A v2.1 head KOPF10. TEST ONLY - water only, never on a person.

KOPF9 (make_face.py --module, tested lock face: bore, bayonet, lock pocket, latch groove, seal recess) with only these changes
(owner print 2026-11-27: the head did not go onto the shells, one screw hole sat behind the joint ring):
- outline = the adapter outline with the same 45 deg facets at the top / bottom faces as the shells (package.section_yz), so head
  and shells stay flush at the joint (the facets add at most 0.96 mm, at the far-bottom sweep);
- rear groove 0.85..2.55 x 2.0 (KOPF9 0.95..2.45) with a 0.3 mouth step: 0.3 mm play per side for the 1.1 mm joint ring instead of
  0.2, and the mouth stays open although it prints on the bed (first-layer squish);
- lower screw at module Y -4.5 (KOPF9 -5.5): 1.0 mm clear of the ring instead of 0.01; the pair is now symmetric about the bore.
The lock face itself (everything make_face.face() cuts) is untouched.

Writes ../out/cart_a_v2/print/v2_head.stl (print orientation: face up, back on the bed, like KOPF9) and ../out/cart_a_v2/head.stl
(placed, pump coordinates). Run: ../../.venv/bin/python head.py
"""
from __future__ import annotations

import json

from build123d import (Align, BuildPart, BuildSketch, Cone, Cylinder, Locations, Mode, Plane, Polygon, Rot, Solid, export_stl,
                       extrude, offset)

import package as pk

mf = pk.mf
SCREWS = [(10.0, 4.5), (10.0, -4.5)]                 # module X (along y from the bore), Y (up): pump (21.46, 13.24) / (21.46, 4.24)
PIN = (26.0, 7.07 - pk.ZC, 2.1, 1.7)                  # lock ball + pin bore: X, Y, bore d, opening d (KOPF9 values)
GROOVE = {"in0": 0.85, "in1": 2.55, "depth": 2.0, "mouth": 0.3}
RING = {"in0": 1.15, "in1": 2.25}                     # the shells' joint ring (shells.py), for the report


def outline_faceted() -> list[tuple[float, float]]:
    """Adapter outline + 45 deg facets, in module coordinates (X = y - YC, Y = z - ZC)."""
    return [(y - pk.YC, z - pk.ZC) for y, z in pk.section_yz(pk.HEAD_L, pk.HEAD_W, 0.0, w=1.0, facet=True)]


def _ring(d0: float, d1: float, z0: float, z1: float) -> Solid:
    with BuildPart() as r:
        with BuildSketch(Plane.XY.offset(z0)):
            Polygon(*mf.outline(), align=None)
            offset(amount=-d0, mode=Mode.REPLACE)
            with BuildSketch(mode=Mode.PRIVATE) as inner:
                Polygon(*mf.outline(), align=None)
                offset(amount=-d1, mode=Mode.REPLACE)
            from build123d import add
            add(inner.sketch, mode=Mode.SUBTRACT)
        extrude(amount=z1 - z0)
    return r.part


def build() -> Solid:
    """KOPF10 in module coordinates (back face z 0, lock face z MODULE_DEPTH)."""
    mf.FACE_Z = mf.MODULE_DEPTH
    keep = mf.outline
    mf.outline = outline_faceted
    try:
        part = mf.face()
        fz = mf.FACE_Z
        with BuildPart() as hs:                                    # countersunk M2 (DIN 965) from the face into the shell bosses
            for hx, hy in SCREWS:
                with Locations((hx, hy, -1.0)):
                    Cylinder(1.15, fz + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
                with Locations((hx, hy, fz - 1.0)):
                    Cone(1.15, 2.15, 1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
                with Locations((hx, hy, fz - 0.01)):
                    Cylinder(2.15, 0.5, align=(Align.CENTER, Align.CENTER, Align.MIN))
        part = part - hs.part
        px, py, bore, opening = PIN                                # 2 mm steel ball in the hollow floor, pin behind it to the switch
        floor = fz - mf.RAISE_DEPTH
        with BuildPart() as pb:
            with Locations((px, py, -1.0)):
                Cylinder(bore / 2, floor - 0.3 + 1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
            with Locations((px, py, floor - 0.31)):
                Cylinder(opening / 2, 1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
        part = part - pb.part
        g = GROOVE
        part = part - _ring(g["in0"], g["in1"], -0.01, g["depth"])
        part = part - _ring(g["in0"] - g["mouth"], g["in1"] + g["mouth"], -0.01, g["mouth"])     # mouth step
    finally:
        mf.outline = keep
    return part


def place(part: Solid) -> Solid:
    """Module -> pump coordinates (keeps the bayonet chirality): module X -> +y, Y -> +z, Z -> +x; back face at the joint."""
    pl = Plane(origin=(pk.X_FACE - mf.MODULE_DEPTH, pk.YC, pk.ZC), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
    return part.moved(pl.location)


def main() -> None:
    part = build()
    bb = part.bounding_box()
    c = bb.center()
    (pk.OUT / "print").mkdir(parents=True, exist_ok=True)
    # print: face up like KOPF9; turned so the near end (module -X) faces the bed's back, where the slicer's "back" seam goes
    export_stl(Rot(0, 0, -90) * part.translate((-c.X, -c.Y, 0)), str(pk.OUT / "print" / "v2_head.stl"), tolerance=0.01, angular_tolerance=0.1)
    placed = place(part)
    export_stl(placed, str(pk.OUT / "head.stl"), tolerance=0.01, angular_tolerance=0.1)
    pb = placed.bounding_box()
    rep = {"volume_cm3": round(part.volume / 1000, 3), "valid": part.is_valid, "solids": len(part.solids()),
           "placed_bbox": [[round(pb.min.X, 2), round(pb.min.Y, 2), round(pb.min.Z, 2)], [round(pb.max.X, 2), round(pb.max.Y, 2), round(pb.max.Z, 2)]],
           "groove": GROOVE, "ring": RING, "play_per_side_mm": round(min(RING["in0"] - GROOVE["in0"], GROOVE["in1"] - RING["in1"]), 2),
           "screws_pump_yz": [[round(pk.YC + x, 2), round(pk.ZC + y, 2)] for x, y in SCREWS]}
    (pk.OUT / "head_report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
