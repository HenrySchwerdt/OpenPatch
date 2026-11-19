# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Packing check of the cup pod: free plan area per lane and empty full-height rectangles (z 0.9 .. 7.6) inside the shell.  FAIL if a >= 4 x 4 mm empty rectangle remains."""
from __future__ import annotations

import json
import math
from pathlib import Path

CELL = 0.2
MIN_SIDE = 4.0


def run(outdir: Path, variant: str) -> dict:
    p = json.loads((outdir / "params.used.json").read_text())
    L = json.loads((outdir / f"{variant}.mech.json").read_text())
    import check as C
    res = C.eval_design(outdir / f"{variant}.sc", [])
    bodies = next(r for r in res if "bodies" in r and "body_count" in r)["bodies"]
    w, Lp, W, H = L["wall"], L["length"], L["width"], L["height"]
    z0, z1 = w, H - w
    K = L["dock"]
    nx, ny = int(round((Lp - 2 * w) / CELL)), int(round((W - 2 * w) / CELL))
    occ = [[False] * nx for _ in range(ny)]
    r_in = p["shell"]["corner_r"] - w

    def mark(x0, x1, y0, y1):
        for j in range(max(0, int((y0 - w) / CELL)), min(ny, int(math.ceil((y1 - w) / CELL)))):
            for i in range(max(0, int((x0 - w) / CELL)), min(nx, int(math.ceil((x1 - w) / CELL)))):
                occ[j][i] = True
    for b in bodies:
        if b["name"] in ("bottom", "top"):
            continue
        mn, mx = b["bbox"]["min"], b["bbox"]["max"]
        if mx[2] <= z0 + 1e-6 or mn[2] >= z1 - 1e-6:
            continue
        mark(mn[0], mx[0], mn[1], mx[1])
    mark(K["x_bf"], Lp - w, L["y_r"] - K["half"] - p["cup"]["dock"]["pocket_wall"], L["y_r"] + K["half"] + p["cup"]["dock"]["pocket_wall"])        # dock pocket (printed walls + volume)
    for j in range(ny):                                           # outside the rounded inner corners = not cavity
        for i in range(nx):
            x, y = w + (i + 0.5) * CELL, w + (j + 0.5) * CELL
            for cx, cy in ((w + r_in, w + r_in), (Lp - w - r_in, w + r_in), (w + r_in, W - w - r_in), (Lp - w - r_in, W - w - r_in)):
                if (x < w + r_in or x > Lp - w - r_in) and (y < w + r_in or y > W - w - r_in) and abs(x - cx) < r_in and abs(y - cy) < r_in and math.hypot(x - cx, y - cy) > r_in:
                    occ[j][i] = True
    ps = [[0] * (nx + 1) for _ in range(ny + 1)]
    for j in range(ny):
        for i in range(nx):
            ps[j + 1][i + 1] = ps[j][i + 1] + ps[j + 1][i] - ps[j][i] + (1 if occ[j][i] else 0)
    cnt = lambda i0, j0, i1, j1: ps[j1][i1] - ps[j0][i1] - ps[j1][i0] + ps[j0][i0]
    k = int(round(MIN_SIDE / CELL))
    hits = [(w + i * CELL, w + j * CELL) for j in range(ny - k + 1) for i in range(nx - k + 1) if cnt(i, j, i + k, j + k) == 0]
    # largest empty rectangle (histogram method)
    best = (0.0, None)
    h = [0] * nx
    for j in range(ny):
        for i in range(nx):
            h[i] = 0 if occ[j][i] else h[i] + 1
        st: list[int] = []
        for i in range(nx + 1):
            cur = h[i] if i < nx else 0
            while st and h[st[-1]] >= cur:
                hh = h[st.pop()]
                left = st[-1] + 1 if st else 0
                area = hh * (i - left) * CELL * CELL
                if area > best[0]:
                    best = (area, (w + left * CELL, w + (j - hh + 1) * CELL, w + i * CELL, w + (j + 1) * CELL))
            st.append(i)
    ylim = L["lane2_y"][0] - 0.1
    lane = {"lane 1 (y < %.1f)" % ylim: [0, 0], "lane 2 (y >= %.1f)" % ylim: [0, 0]}
    keys = list(lane)
    for j in range(ny):
        y = w + (j + 0.5) * CELL
        for i in range(nx):
            inside = not (occ[j][i] and False)
            lane[keys[0] if y < ylim else keys[1]][1] += CELL * CELL
            if not occ[j][i]:
                lane[keys[0] if y < ylim else keys[1]][0] += CELL * CELL
    return {"variant": variant, "free_mm2": {k_: round(v[0], 1) for k_, v in lane.items()}, "plan_mm2": {k_: round(v[1], 1) for k_, v in lane.items()},
            "largest_empty_rect": {"area_mm2": round(best[0], 1), "x0y0x1y1": [round(v, 2) for v in best[1]] if best[1] else None},
            "rect_4x4_found": bool(hits), "rect_4x4_first": [round(v, 1) for v in hits[0]] if hits else None, "n_4x4_cells": len(hits)}


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "out" / "v010-cup"
    for v in (sys.argv[2:] or ["OP-100", "OP-200"]):
        print(json.dumps(run(out, v), indent=1))
