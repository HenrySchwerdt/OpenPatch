#!/usr/bin/env python3
"""Extra component models the render pipeline needs on top of mechanical/components (read-only import).

Everything is built into tools/render/cache/components/ (git-ignored) with the generators of the component library:
  rod_m1p6_25         project cut length of the OP-100 leadscrew (library only has 19/22/37), modelled thread (about 3 min)
  gear_z20_turned     GHW 753020 with the hub turned off (as built)
  gear_z16_skimmed    GHW 390754 skimmed from 5.0 to 1.4 mm (as built)
  sleeve_d2x1p6       brass tube d2.0 x d1.6, 2.1 long (gear B carrier)
  bush_ptfe           PTFE bush d3.0 x d1.7 x 1.0
  coin_2eur           2 euro coin, scale reference (d25.75 x 2.20), plain faces
Run:  python3 tools/render/components.py [id ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LIB = ROOT / "mechanical" / "components"
CACHE = HERE / "cache" / "components"
sys.path.insert(0, str(LIB))
import cc  # noqa: E402

cc.PAL.setdefault("ptfe", ("#f4f4f2", 0.0, 0.6))
cc.PAL.setdefault("coin_ring", ("#d8c07a", 1.0, 0.3))
cc.PAL.setdefault("coin_core", ("#c9ccd0", 1.0, 0.3))
for _k in ("ptfe", "coin_ring", "coin_core"):
    cc.DENSITY.setdefault(_k, 2.0)
from gen_fasteners import rod, screw  # noqa: E402
from gen_gear import spur_gear  # noqa: E402


def parts():
    out = [rod(25.0), screw(6.0)]
    out.append(spur_gear("gear_z20_turned", "GHW 753020 z20, hub turned off, width 1.4", 0.3, 20, 2.0, 1.4))
    out.append(spur_gear("gear_z16_skimmed", "GHW 390754 z16 skimmed to 1.4", 0.3, 16, 2.0, 1.4))
    p = cc.Part("sleeve_d2x1p6", "brass sleeve d2.0 x d1.6 x 2.1")
    p.s.cyl("sleeve", "Z", (0, 0, 0), 2.0, 0.0, 2.1)
    p.s.cyl("bore", "Z", (0, 0, 0), 1.6, -0.1, 2.2)
    p.s.cut("sleeve", ["bore"])
    p.look("sleeve", "brass")
    out.append(p)
    p = cc.Part("bush_ptfe", "PTFE bush d3.0 x d1.7 x 1.0")
    p.s.cyl("bush", "Z", (0, 0, 0), 3.0, 0.0, 1.0)
    p.s.cyl("bore", "Z", (0, 0, 0), 1.7, -0.1, 1.1)
    p.s.cut("bush", ["bore"])
    p.look("bush", "ptfe")
    out.append(p)
    p = cc.Part("tube_silicone_1p6", "silicone tubing 1/16 in ID (1.6) x OD 3.2, 24 mm piece")
    p.s.cyl("tube", "Z", (0, 0, 0), 3.2, 0.0, 24.0)
    p.s.cyl("bore", "Z", (0, 0, 0), 1.6, -0.1, 24.1)
    p.s.cut("tube", ["bore"])
    p.look("tube", "ptfe")
    out.append(p)
    p = cc.Part("coin_2eur", "2 euro coin d25.75 x 2.2 (scale reference, plain)")
    p.s.cyl("ring", "Z", (0, 0, 0), 25.75, 0.0, 2.2)
    p.s.cyl("core_tool", "Z", (0, 0, 0), 18.5, -0.1, 2.3)
    p.s.cut("ring", ["core_tool"])
    p.s.cyl("core", "Z", (0, 0, 0), 18.45, 0.0, 2.2)
    p.look("ring", "coin_ring")
    p.look("core", "coin_core")
    out.append(p)
    return out


def ensure(only=None):
    CACHE.mkdir(parents=True, exist_ok=True)
    for p in parts():
        if only and p.pid not in only:
            continue
        if (CACHE / f"{p.pid}.step").exists():
            continue
        print("building", p.pid, flush=True)
        p.build(outdir=CACHE, render=False)


def path(pid: str) -> Path:
    f = CACHE / f"{pid}.step"
    if not f.exists():
        f = LIB / "out" / f"{pid}.step"
    return f


if __name__ == "__main__":
    ensure(set(sys.argv[1:]) or None)
