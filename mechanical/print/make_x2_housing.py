#!/usr/bin/env python3
"""Scale the final OP-100 cup housing (bottom shell + lid) by 2 and lay it out for the Sovol SV01 Pro bed.

TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). Fit/visual model, never worn.

Output (mechanical/print/OP-100_x2/):
  OP-100_bottom_x2.stl  outer (skin) face down, as modelled
  OP-100_top_x2.stl     lid flipped (outer face down)
  OP-100_housing_x2_bed.stl  both parts placed side by side, centred on the origin (CuraEngine adds the bed centre)
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "out" / "v010-cup"
OUT = HERE / "OP-100_x2"
SCALE = 2.0
BED_W, BED_D = 280.0, 240.0
GAP = 12.0  # mm between the two parts on the bed


def read_stl(path: Path) -> np.ndarray:
    """Return triangles as (n, 3, 3) float array (binary or ASCII STL)."""
    data = path.read_bytes()
    if data[:5] == b"solid" and b"facet" in data[:400]:
        verts = [list(map(float, ln.split()[1:4])) for ln in data.decode().splitlines() if ln.strip().startswith("vertex")]
        return np.asarray(verts, dtype=np.float64).reshape(-1, 3, 3)
    (n,) = struct.unpack_from("<I", data, 80)
    rec = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n, offset=84)
    return rec["v"].astype(np.float64)


def write_stl(path: Path, tris: np.ndarray, name: str) -> None:
    v1, v2, v3 = tris[:, 0], tris[:, 1], tris[:, 2]
    nrm = np.cross(v2 - v1, v3 - v1)
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.divide(nrm, ln, out=np.zeros_like(nrm), where=ln > 0)
    rec = np.zeros(len(tris), dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    rec["n"], rec["v"] = nrm, tris
    header = (name.encode()[:80]).ljust(80, b" ")
    path.write_bytes(header + struct.pack("<I", len(tris)) + rec.tobytes())


def to_floor(t: np.ndarray) -> np.ndarray:
    """Translate so min z = 0 and min x/y = 0."""
    return t - t.reshape(-1, 3).min(axis=0)


def flip_x180(t: np.ndarray) -> np.ndarray:
    """Rotate 180 deg about X (y -> -y, z -> -z); keeps the triangle winding (proper rotation)."""
    return t * np.array([1.0, -1.0, -1.0])


def main() -> int:
    OUT.mkdir(exist_ok=True)
    bottom = to_floor(read_stl(SRC / "OP-100_bottom.stl") * SCALE)
    lid = to_floor(flip_x180(read_stl(SRC / "OP-100_top.stl") * SCALE))
    write_stl(OUT / "OP-100_bottom_x2.stl", bottom, "OP-100 bottom x2")
    write_stl(OUT / "OP-100_top_x2.stl", lid, "OP-100 lid x2 flipped")

    sb, sl = bottom.reshape(-1, 3).max(axis=0), lid.reshape(-1, 3).max(axis=0)
    total_w = sb[0] + GAP + sl[0]
    if total_w > BED_W - 20 or max(sb[1], sl[1]) > BED_D - 20:
        print(f"does not fit the bed side by side: {total_w:.1f} x {max(sb[1], sl[1]):.1f}", file=sys.stderr)
        return 1
    # CuraEngine adds the bed centre (machine_center_is_zero = false), so the layout is centred on the origin
    x0 = -total_w / 2
    b = bottom + np.array([x0, -sb[1] / 2, 0])
    l = lid + np.array([x0 + sb[0] + GAP, -sl[1] / 2, 0])
    parts = [b, l]
    cap_src = SRC / "OP-100_button_cap.stl"
    if cap_src.exists():  # button cap (added 2026-11-24), printed beside the shells
        cap = to_floor(read_stl(cap_src) * SCALE)
        write_stl(OUT / "OP-100_button_cap_x2.stl", cap, "OP-100 button cap x2")
        sc = cap.reshape(-1, 3).max(axis=0)
        parts.append(cap + np.array([-sc[0] / 2, -max(sb[1], sl[1]) / 2 - GAP - sc[1], 0]))
    write_stl(OUT / "OP-100_housing_x2_bed.stl", np.concatenate(parts), "OP-100 housing x2 bed layout")
    print(f"bottom x2: {sb[0]:.2f} x {sb[1]:.2f} x {sb[2]:.2f} mm")
    print(f"lid    x2: {sl[0]:.2f} x {sl[1]:.2f} x {sl[2]:.2f} mm (flipped)")
    print(f"bed layout x {x0 + BED_W / 2:.1f}..{x0 + total_w + BED_W / 2:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
