"""Angle magnet -> TMAG5273 field study for the cup pod (is the rear flex strip droppable?).

Uses hall_model.diametric_field_mT (surface-charge model, +-20 %).  Pod frame: rod axis along X at (y_r, z_c).
Run from mechanical/: python3 studies/cup_magnet_tmag.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hall_model import diametric_field_mT  # noqa: E402

BR = 1.45                        # N52
YR, ZC, XM = 11.65, 4.25, 4.93   # rod axis y, z; magnet centre x (OP-100: gear B front 0.96, magnet d2 x 1)
A1_RANGE, A2_RANGE = 40.0, 133.0  # TMAG5273 x1 / x2 low range, +-mT (datasheet, VERIFY)


def amp(pos, d, t, n=24):
    """(max |B|, min/max |B|) over one rotation at pos relative to the magnet centre."""
    mags = []
    for k in range(n):
        b = diametric_field_mT(pos, 2 * math.pi * k / n, BR, d / 2, t)
        mags.append(math.sqrt(b[0] ** 2 + b[1] ** 2 + b[2] ** 2))
    return max(mags), min(mags) / max(mags)


cases = {
    "current: strip TMAG beside magnet (dx -0.81, dy -2.9)": (-0.81, -2.9, 0.0),
    "board top side, north of magnet (y 24.3, z 6.8)": (0.0, 24.3 - YR, 6.8 - ZC),
    "board bottom side over the cell (x 10.85, z 4.15)": (10.85 - XM, 24.3 - YR, 4.15 - ZC),
    "board west edge top side (x 9.2, z 6.8)": (9.2 - XM, 24.3 - YR, 6.8 - ZC),
}
for d, t in ((2, 1), (3, 1.5), (4, 2), (6, 3)):
    print(f"--- magnet d{d} x {t} N52")
    for name, pos in cases.items():
        a, r = amp(pos, d, t)
        lsb = a / (2 * A1_RANGE / 4096)
        print(f"  {name}: |B| {a:7.2f} mT (min/max {r:.2f}), A1 {a / A1_RANGE * 100:5.1f} % FS ({lsb:5.0f} LSB), A2 {a / A2_RANGE * 100:5.1f} % FS, {a / 0.05:6.0f}x Earth")
