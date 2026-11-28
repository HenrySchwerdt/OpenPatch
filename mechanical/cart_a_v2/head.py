#!/usr/bin/env python3
"""Cart pump A v2.2 lock face zone (the former separate head). TEST ONLY - water only, never on a person.

Owner 2026-11-28: the separate head never looked or sat seamless (other print orientation, the halves came out 0.15 lower, a
first-layer notch at its back edge). From v2.2 the front 6.6 mm (x 65.26-71.86) are part of both shell halves: the outer skin runs
through to the face in exactly the Accu-Chek adapter outline, and the tested lock face (make_face.face(): bore, bayonet, windows,
hollow, band, latch groove, lock notch, lock pocket, seal recess) is cut into the halves. The seam (z 8.74) runs through the bore axis.

This module gives the zone in pump coordinates:
- zone_placed(): the solid zone (adapter-outline prism minus every lock-face feature minus the lock ball / pin bore);
- cut_placed(): what the lock face removes from the solid zone (the features + the pin bore).
The shells fuse zone_placed() onto the body (its outline equals the body section at the joint) and split it at the seam.
The lock ball + pin bore lies just under the seam: it becomes a channel open to the seam in the bottom half, closed by the top half.
Run: ../../.venv/bin/python head.py (writes ../out/cart_a_v2/head.stl = the zone, for the renders and the package check)
"""
from __future__ import annotations

import json
import math

from build123d import (Align, BuildPart, BuildSketch, Cylinder, Locations, Mode, Plane, Polygon, Solid, Vector, Wire, Face,
                       export_stl, extrude)

import package as pk

mf = pk.mf
PIN = (26.0, 7.07 - pk.ZC, 2.1, 1.7)                  # lock ball + pin bore: module X, Y, bore d, opening d (KOPF9 values)


def _channel(px: float, py: float, d: float, z0: float, z1: float) -> Solid:
    """Round channel of diameter d along module Z, opened upward to the seam (module Y 0): it lies in the bottom half just under
    the seam, so the top half's flat seam face closes it; prints without a roof. A 2 mm ball cannot pass a 1.7 slot."""
    r = d / 2
    with BuildPart() as c:
        with Locations((px, py, z0)):
            Cylinder(r, z1 - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations((px, (py + 0.02) / 2, z0)):
            from build123d import Box
            Box(d, abs(py) + 0.02, z1 - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return c.part


def face_part() -> Solid:
    """make_face.face() (exact adapter outline, MODULE_DEPTH deep) minus the lock ball / pin bore, in module coordinates."""
    mf.FACE_Z = mf.MODULE_DEPTH
    part = mf.face()
    px, py, bore, opening = PIN
    floor = mf.FACE_Z - mf.RAISE_DEPTH
    part = part - _channel(px, py, bore, -1.0, floor - 0.3)                      # ball + pin channel from the zone's back face
    part = part - _channel(px, py, opening, floor - 0.31, floor + 0.7)           # narrower opening keeps the ball in (cap ~0.47 proud)
    return part


def prism() -> Solid:
    with BuildPart() as p:
        with BuildSketch():
            Polygon(*mf.outline(), align=None)
        extrude(amount=mf.MODULE_DEPTH)
    return p.part


def prism_inset(d: float) -> Solid:
    """The zone's outline inset by d, extruded over the zone depth (+0.2 in front of the face), module coordinates."""
    from build123d import offset
    with BuildPart() as p:
        with BuildSketch():
            Polygon(*mf.outline(), align=None)
            offset(amount=-d, mode=Mode.REPLACE)
        extrude(amount=mf.MODULE_DEPTH + 0.2)
    return p.part


def place(part: Solid) -> Solid:
    """Module -> pump coordinates (keeps the bayonet chirality): module X -> +y, Y -> +z, Z -> +x; back face at the joint."""
    pl = Plane(origin=(pk.X_FACE - mf.MODULE_DEPTH, pk.YC, pk.ZC), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
    return part.moved(pl.location)


def zone_placed() -> Solid:
    return place(face_part())


def cut_placed() -> Solid:
    """Everything the lock face removes from the solid zone (features + pin bore), pump coordinates."""
    return place(prism() - face_part())


def main() -> None:
    z = zone_placed()
    export_stl(z, str(pk.OUT / "head.stl"), tolerance=0.01, angular_tolerance=0.1)
    bb = z.bounding_box()
    rep = {"zone_volume_cm3": round(z.volume / 1000, 3), "valid": z.is_valid, "solids": len(z.solids()),
           "bbox": [[round(bb.min.X, 2), round(bb.min.Y, 2), round(bb.min.Z, 2)], [round(bb.max.X, 2), round(bb.max.Y, 2), round(bb.max.Z, 2)]],
           "pin": {"module": PIN[:2], "bore_d": PIN[2], "opening_d": PIN[3], "shape": "round channel opened up to the seam (bottom half), closed by the top half"}}
    (pk.OUT / "head_report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
