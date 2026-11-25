#!/usr/bin/env python3
"""Round-5 fit coupons for the Insight adapter twist-lock: the pump's round lock boss only ("pucks").

TEST ONLY - NOT FOR HUMAN USE (see ../../../DISCLAIMER.md). Bench fit test with an empty adapter, never worn.

Adapter dimensions measured by hand (ruler, 2026-11-25):
  cup OD 11.0-11.5, over the lugs 13.0, cup height above the adapter face 5 (incl. ~1 mm seal ring),
  lugs at the cup tip, 1-1.5 thick, chord widths 4.5 and 6.5 (opposite each other, on the adapter long axis),
  adapter 49 x 19, cup centre 11-11.5 from the near end, far half raised 4 mm with a ramp from 21 to 25 mm.
  => the raised far half starts ~10 mm from the cup axis, so the pump side is a round boss of about d19
     around the bore with everything outside recessed 4 mm. These pucks are that boss alone, so the
     adapter body cannot collide with anything and only the lock itself is tested.

Puck: d19 x 9, printed mating face UP (no bridges). Through bore, two keyed lug windows from the face down
to the lip, a full 360 deg undercut ring below the lip (no rotation stop, so the entry angle does not matter
for this test). A small tab at the bottom carries the variant number.
Variants: bore d 11.7 / 12.0  x  lip 2.4 / 2.9 / 3.4 (face to the outer edge of the lug hook flank).
Round 5b (2026-11-25): the lug hook flank is bevelled (~45 deg, owner photos), so the lip underside is a 45 deg cone.
"""
from __future__ import annotations

import sys
from pathlib import Path

from build123d import (Align, Axis, Box, BuildPart, BuildSketch, Cone, Cylinder, Locations, Mode, Plane, Text, export_stl,
                       extrude, Compound)

HERE = Path(__file__).resolve().parent
OUT = HERE / "pucks"
PUCK_D, PUCK_H = 19.0, 9.0
LUG_OD = 13.0 + 0.8          # bevel cone outer diameter (13 across the lug flats + clearance)
WIN_X = 6.5 + 0.4            # window flat, from the axis (lug flat at 6.5 + clearance)
GROOVE_R = 7.6               # undercut radius: the big lug's corners (6.5 out, 3.25 to the side) sweep r 7.27
WIN_SMALL, WIN_BIG = 4.5 + 1.3, 6.5 + 1.3   # window widths (lug chord + clearance; lugs are ~174 deg apart, not 180)
UNDERCUT_H = 2.1             # lug 1-1.5 thick + clearance (1.9 was a bit catchy)
TAB_W, TAB_L, TAB_H = 7.0, 6.0, 3.0
BORES = (11.7, 12.0)
LIPS = (2.4, 2.9, 3.4)
SEAL_D, SEAL_DEPTH = 15.6, 0.8   # recess for the adapter's d15 x 1 seal ring so the adapter sits flush
LUG_FLANK_DEG = 45.0       # lug hook flank is bevelled (owner photos 2026-11-25), lip underside matches
PITCH = 30.0


def puck(bore: float, lip: float, label: str):
    top = PUCK_H
    with BuildPart() as p:
        Cylinder(PUCK_D / 2, PUCK_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations((PUCK_D / 2 + TAB_L / 2 - 1.0, 0, 0)):
            Box(TAB_L + 2.0, TAB_W, TAB_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # through bore
        Cylinder(bore / 2, PUCK_H, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # keyed windows (big lug +X, small lug -X), face down to the lip. Top view of the lugs (owner photo
        # 2026-11-25): straight outer edge at 6.5 from the cup axis with blunt ends, not an arc, so the
        # windows are flat-ended slots out to WIN_X instead of thin crescents
        for sx, w in ((1, WIN_BIG), (-1, WIN_SMALL)):
            with Locations((sx * WIN_X / 2, 0, top - lip)):
                Box(WIN_X, w, lip, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # seal recess in the face (owner 2026-11-25: original has a groove for the seal, adapter sits flush)
        if SEAL_DEPTH > 0:
            with Locations((0, 0, top - SEAL_DEPTH)):
                Cylinder(SEAL_D / 2, SEAL_DEPTH, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # undercut ring below the lip (full turn)
        with Locations((0, 0, top - lip - UNDERCUT_H)):
            Cylinder(GROOVE_R, UNDERCUT_H, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # bevelled lip underside: the lugs' hook flank is sloped, a square lip corner would block the turn
        import math
        cone_h = (LUG_OD / 2 - bore / 2) * math.tan(math.radians(LUG_FLANK_DEG))
        with Locations((0, 0, top - lip)):
            Cone(LUG_OD / 2, bore / 2, cone_h, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # variant number engraved into the tab
        with BuildSketch(Plane.XY.offset(TAB_H - 0.6)) as sk:
            with Locations((PUCK_D / 2 + TAB_L / 2 + 0.3, 0)):
                Text(label, font_size=4.0, align=(Align.CENTER, Align.CENTER))
        extrude(sk.sketch, amount=0.8, mode=Mode.SUBTRACT)
    return p.part


def main() -> int:
    OUT.mkdir(exist_ok=True)
    parts = []
    n = 0
    for bore in BORES:
        for lip in LIPS:
            n += 1
            part = puck(bore, lip, str(n))
            export_stl(part, str(OUT / f"puck_{n}_bore{bore}_lip{lip}.stl"))
            col, row = (n - 1) % 3, (n - 1) // 3  # row = bore, col = lip
            parts.append(part.translate((-PITCH + col * PITCH - 3, PITCH / 2 - row * PITCH, 0)))
            print(f"puck {n}: bore d{bore}  lip {lip}  undercut {lip:.1f}..{lip + UNDERCUT_H:.1f} below face")
    export_stl(Compound(parts), str(OUT / "pucks_bed.stl"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
