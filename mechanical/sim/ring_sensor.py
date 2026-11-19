#!/usr/bin/env python3
"""Angle-sensor model of the v0.1.0 drive: diametric RING magnet on the nut-gear sleeve, TMAG5273 beside it (side-shaft, YZ angle).

  python3 mechanical/sim/ring_sensor.py [OP-100]

magpylib (6.x) model of the ring (N45, Br = 1.30 T assumed), sensor at the position of out/v010/<size>.mech.json (geo.sensor.tmag).  For every rotation angle of the
magnet the field vector in the sensor's YZ plane is computed; reported: |B_yz| min / max, the angle error of atan2(Bz, By) against the magnet angle (peak-to-peak after removing
the mean offset), and the sensitivity to a +-0.3 mm sensor placement error.  Estimates (+-20 %): measure on the bench, calibrate in firmware (a 4-point or lookup calibration removes
the systematic part; the angle only has to be monotonic for per-revolution verification and stall detection).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent


def model(od: float, idn: float, t: float, rel: tuple[float, float, float], br_mt: float = 1300.0, n: int = 72, dxyz=(0, 0, 0)) -> dict:
    """rel = sensor position relative to the ring centre in POD axes (dx along the ring axis, dy, dz).  Returns the field statistics over one magnet turn."""
    import magpylib as mp
    ang, bmag, bx = [], [], []
    for k in range(n):
        th = 2 * math.pi * k / n
        # local axes of the magnet: local x = pod Y, local y = pod Z, local z = pod X (cyclic permutation, handedness kept); diametric magnetisation rotating in the local x-y plane
        m = mp.magnet.CylinderSegment(dimension=(idn / 2, od / 2, t, 0, 360), polarization=(br_mt * math.cos(th), br_mt * math.sin(th), 0))
        pos = (rel[1] + dxyz[1], rel[2] + dxyz[2], rel[0] + dxyz[0])
        b = m.getB(pos)                     # local (x, y, z) = pod (Y, Z, X) in mT
        by, bz, bxx = float(b[0]), float(b[1]), float(b[2])
        ang.append(math.atan2(bz, by))
        bmag.append(math.hypot(by, bz))
        bx.append(bxx)
    ang = np.unwrap(np.array(ang))
    ideal = np.array([2 * math.pi * k / n for k in range(n)])
    c = np.polyfit(ideal, ang, 1)
    slope = float(c[0])
    err = ang - np.polyval(c, ideal)           # residual after the best linear fit (gain error is calibrated out in firmware; direction is a sign convention)
    return {"B_yz_min_mT": round(min(bmag), 2), "B_yz_max_mT": round(max(bmag), 2), "B_x_pk_mT": round(max(abs(v) for v in bx), 2),
            "angle_err_pp_deg": round(math.degrees(err.max() - err.min()), 2), "angle_slope": round(slope, 3)}


def main() -> None:
    size = sys.argv[1] if len(sys.argv) > 1 else "OP-100"
    L = json.loads((HERE / "out" / "v010" / f"{size}.mech.json").read_text())
    p = json.loads((HERE / "out" / "v010" / "params.used.json").read_text())
    rg = p["pod"]["ring"]
    tm = L["geo"]["sensor"]["tmag"]
    rx = (L["ring"][0] + L["ring"][1]) / 2
    rel = (tm["c"][0] - rx, tm["c"][1] - L["y_r"], (tm["z"][0] + tm["z"][1]) / 2 - L["z_axis"])
    base = model(rg["od"], rg["id"], rg["t"], rel)
    print(f"{size}: sensor at ring-relative (dx {rel[0]:+.2f}, dy {rel[1]:+.2f}, dz {rel[2]:+.2f}) mm")
    print("  nominal:", base)
    worst = {"angle_err_pp_deg": base["angle_err_pp_deg"], "B_yz_min_mT": base["B_yz_min_mT"], "B_yz_max_mT": base["B_yz_max_mT"]}
    for d in ((0.3, 0, 0), (-0.3, 0, 0), (0, 0.3, 0), (0, -0.3, 0), (0, 0, 0.3), (0, 0, -0.3)):
        r = model(rg["od"], rg["id"], rg["t"], rel, dxyz=d)
        worst["angle_err_pp_deg"] = max(worst["angle_err_pp_deg"], r["angle_err_pp_deg"])
        worst["B_yz_min_mT"] = min(worst["B_yz_min_mT"], r["B_yz_min_mT"])
        worst["B_yz_max_mT"] = max(worst["B_yz_max_mT"], r["B_yz_max_mT"])
    print("  worst case over +-0.3 mm placement:", worst)
    out = {"size": size, "rel_mm": [round(v, 3) for v in rel], "nominal": base, "worst_0p3mm": worst, "magnet": "diametric ring d5 x d2 x 1.5, N45 Br 1.30 T assumed",
           "tmag_variant_note": "TMAG5273A1 (+-40 / +-80 mT) if B_yz_max < 40 mT, else A2 (+-133 / +-266 mT)"}
    (HERE / "out" / "v010" / f"{size}.ring_sensor.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
