"""Cast silicone seal bead (shared by the plunger assembly state in op_drive.py and the moulds in op_mould.py).

Seal design (see SEAL-AND-DEAD-VOLUME.md): the plunger core carries up to two grooves (ring_a rear, ring_b front).  Each groove is filled with a
cast silicone ring whose outer profile is a thin trapezoidal BEAD: flat land `land` (the only sliding contact, 0.2-0.3 mm) on two flanks of width
(width (groove - land)/2, 36-40 deg), standing `free_oversize/2` (+ core clearance) proud of the core.  One mould family, three variants (params.json -> seal.variants):

  S1  single front bead, land 0.20, cast oversize 0.15 mm  (primary)
  S2  single front bead, land 0.15, cast oversize 0.12 mm  (low friction; thinner leak margin)
  T   twin beads (front + rear), land 0.20, cast oversize 0.14 mm (redundant seal + longer guide, about 1.7x friction of S1)

All three fit the same plunger core.
"""
from __future__ import annotations

import math

from op_cmds import Script


def variant(p: dict, key: str | None = None) -> dict:
    sl = p["seal"]
    key = key or sl["active_variant"]
    v = dict(sl["variants"][key])
    v["key"] = key
    v.setdefault("land", sl["land"])
    return v


def ring_range(p: dict, which: str) -> tuple[float, float]:
    sl = p["seal"]
    return tuple(sl["ring_a"] if which == "a" else sl["ring_b"])


def bead_bodies(s: Script, name: str, a: float, b: float, yc: float, zc: float,
                w_base: float, h_base: float, w_tip: float, h_tip: float, land: float) -> list[str]:
    """Solid (not hollow) bead between x = a and b: rear flank (draft +), land (constant), front flank (draft -).
    Returns the body names [rear (= name), land, front]; the caller joins or cuts with them."""
    f = (b - a - land) / 2.0
    if f <= 0:
        raise ValueError("bead land wider than the ring")
    grow = (w_tip - w_base) / 2.0
    ang = math.degrees(math.atan2(grow, f))
    n1 = s.stadium_taper(name, (a, a + f), yc, zc, w_base, h_base, ang)
    n2 = s.stadium(f"{name}_l", (a + f, a + f + land), yc, zc, w_tip, h_tip)
    n3 = s.stadium_taper(f"{name}_f", (a + f + land, b), yc, zc, w_tip, h_tip, -ang)
    return [n1, n2, n3]
