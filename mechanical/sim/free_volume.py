#!/usr/bin/env python3
"""Free-volume map of a pod design from body bounding boxes (conservative: round parts count as boxes).

  python3 sim/free_volume.py out/bench/OP-100.sc            # bench pod
  python3 sim/free_volume.py out/v010/OP-100.sc --skip-v010  # v0.1.0 pod without its electronics

Prints the largest free rectangles for several pocket heights and an ASCII map of the largest free vertical gap per 0.5 mm cell (floor z 0.9 .. lid inner).
Used for mechanical/V010.md section 8 (where could the electronics go without a tail). Run from mechanical/."""
import json, subprocess, sys
from pathlib import Path
sc = sys.argv[1]
import tempfile
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
    json.dump([{"command": "inspect.measure", "params": {}}], fh)
r = subprocess.run(["solidcraft-cli", "run", fh.name, "--in", sc, "--results", "--quiet"], capture_output=True, text=True)
Path(fh.name).unlink(missing_ok=True)
meas = json.loads(r.stdout)
bodies = next(x for x in meas if "bodies" in x and "body_count" in x)["bodies"]
SKIP = {"bottom", "top", "gasket", "pod_board", "ffc_conn", "ffc_cable", "hall_drv0", "hall_drv1"}
if "--skip-v010" in sys.argv:
    SKIP |= {"e73", "pico_conn", "pico_plug", "battery", "bat_foam", "bat_pad_p", "bat_pad_n", "spring_p", "spring_n", "piezo", "switch", "chg_pad_1", "chg_pad_2", "charge_gasket"}
ZF = 0.9
ZL = max(b["bbox"]["max"][2] for b in bodies if b["name"] == "top") - 0.9
X1 = max(b["bbox"]["max"][0] for b in bodies if b["name"] == "bottom") - 0.9
X0, Y0, Y1 = 0.9, 0.9, 31.1
occ = [(b["name"], b["bbox"]["min"], b["bbox"]["max"]) for b in bodies if b["name"] not in SKIP]

D = 0.5
nx, ny = int((X1 - X0) / D), int((Y1 - Y0) / D)


def gaps(x, y):
    iv = []
    for n, mn, mx in occ:
        if mn[0] < x + D and mx[0] > x and mn[1] < y + D and mx[1] > y:
            iv.append((max(mn[2], ZF), min(mx[2], ZL)))
    iv.sort()
    g, cur = [], ZF
    for a, b in iv:
        if a > cur + 1e-6:
            g.append((cur, a))
        cur = max(cur, b)
    if ZL > cur + 1e-6:
        g.append((cur, ZL))
    return g


G = [[gaps(X0 + i * D, Y0 + j * D) for j in range(ny)] for i in range(nx)]


def rects(h):
    """maximal rectangles (x,y) where a free z gap >= h exists; z-range = intersection of gap windows (approx: lowest top / highest bottom)."""
    ok = [[any(b - a >= h - 1e-9 for a, b in G[i][j]) for j in range(ny)] for i in range(nx)]
    out, used = [], [[False] * ny for _ in range(nx)]
    for _ in range(6):
        best = None
        hist = [0] * ny
        # brute force over x ranges (small grid)
        for i0 in range(nx):
            col = [True] * ny
            for i1 in range(i0, nx):
                for j in range(ny):
                    col[j] = col[j] and ok[i1][j] and not used[i1][j]
                j = 0
                while j < ny:
                    if col[j]:
                        k = j
                        while k < ny and col[k]:
                            k += 1
                        area = (i1 - i0 + 1) * (k - j)
                        if best is None or area > best[0]:
                            best = (area, i0, i1, j, k - 1)
                        j = k
                    else:
                        j += 1
        if not best or best[0] < 8:
            break
        _, i0, i1, j0, j1 = best
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                used[i][j] = True
        zlo, zhi = 0, 99
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                c = [g for g in G[i][j] if g[1] - g[0] >= h - 1e-9]
                g = max(c, key=lambda t: t[1] - t[0])
                zlo, zhi = max(zlo, g[0]), min(zhi, g[1])
        out.append(dict(x=(round(X0 + i0 * D, 1), round(X0 + (i1 + 1) * D, 1)), y=(round(Y0 + j0 * D, 1), round(Y0 + (j1 + 1) * D, 1)),
                        dx=(i1 - i0 + 1) * D, dy=(j1 - j0 + 1) * D, z=(round(zlo, 2), round(zhi, 2)), free_h=round(zhi - zlo, 2)))
    return out


for h in (3.4, 2.5, 1.6, 0.8):
    print(f"--- free pocket height >= {h} mm")
    for r in rects(h):
        print("  ", r)
# ascii map of the max free gap
print("max free gap per cell (digits = mm, '.' <0.5, '#' occupied); x right 0.9..46.1, y down 31.1..0.9")
for j in range(ny - 1, -1, -1):
    row = ""
    for i in range(nx):
        m = max((b - a for a, b in G[i][j]), default=0)
        row += "." if m < 0.5 else (str(min(9, int(m))))
    print(f"{Y0 + j * D:5.1f} {row}")
