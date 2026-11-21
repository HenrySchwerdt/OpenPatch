#!/usr/bin/env python3
"""3D-printable model of the populated cup board (fit check in the printed housing; NOT an electrical part).

KiCad exports the board body and every part that has a library 3D model; the parts without one (HJ-840 module, USB-C receptacle,
side button, sounder, RGB LED, STM32C011 QFN, AND3, dock hall, DRV8835 whose model file is missing) are added here as boxes with
their datasheet body size and height. Output is in the POD frame of mechanical/out/v010-cup (x from the motor end, y from the
tank-side wall, z from the skin side; board underside at z 5.3), so it drops straight into the printed housing.

usage: python3 print_model.py <placed board .kicad_pcb> <out.stl>
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cupgeom as G  # noqa: E402

# body boxes for parts without a 3D model: (length along the footprint x, along the footprint y, height, centre offset x, y in the footprint frame)
BODIES = {
    "U1": (6.2, 7.0, 1.0, 0.0, 0.0),        # HJ-840 SiP 6.2 x 7.0 x 1.0
    "SW1": (4.7, 3.5, 1.25, 0.0, -0.05),    # ALPS SKSCLAE010 side push
    "BZ1": (4.0, 4.0, 2.0, 0.0, 0.0),       # FUET-4020 sounder
    "LD1": (1.6, 1.5, 0.7, 0.0, 0.0),       # SZYY1615 RGB LED
    "U30": (3.0, 3.0, 0.55, 0.0, 0.0),      # STM32C011 UFQFPN20
    "U36": (1.45, 1.0, 0.5, 0.0, 0.0),      # AND3 UFDFN-6
    "U4A": (1.1, 1.4, 0.4, 0.0, 0.0),       # DRV5032 X2SON
    "U7": (3.0, 2.0, 0.8, 0.0, 0.0),        # DRV8835 WSON-12 (library model file missing)
}
BOARD_T = G.BOARD_T
Z_BOT = G.Z_BOT


def kicad_to_pod(m):
    """KiCad STL frame (x, -y_page, z from the board underside) -> pod frame"""
    v = m.vertices.copy()
    out = np.empty_like(v)
    out[:, 0] = v[:, 0] - 100.0 + G.X0                 # bx = x - 100 (board origin on the page), x_pod = bx + X0
    out[:, 1] = G.Y1 - (-v[:, 1] - 80.0)               # by = y_page - 80, y_pod = Y1 - by
    out[:, 2] = v[:, 2] + Z_BOT
    m.vertices = out
    return m


def box_pod(bx, by, sx, sy, h, side):
    x, y = G.p(bx, by)
    if side == "F":
        z0, z1 = Z_BOT + BOARD_T, Z_BOT + BOARD_T + h
    else:
        z0, z1 = Z_BOT - h, Z_BOT
    b = trimesh.creation.box(extents=(sx, sy, z1 - z0))
    b.apply_translation((x, y, (z0 + z1) / 2))
    return b


def main():
    pcb, out = sys.argv[1], sys.argv[2]
    tmp = tempfile.mktemp(suffix=".stl")
    subprocess.run(["kicad-cli", "pcb", "export", "stl", "--subst-models", "-f", "-o", tmp, pcb], check=True, capture_output=True)
    parts = [kicad_to_pod(trimesh.load(tmp))]
    os.remove(tmp)
    pl = json.load(open(os.path.join(HERE, "placement.json")))
    for ref, (lx, ly, h, ox, oy) in BODIES.items():
        bx, by, rot, side = pl[ref]
        r = rot % 180
        sx, sy = (lx, ly) if r == 0 else (ly, lx)
        parts.append(box_pod(bx + ox, by + oy, sx, sy, h, side))
    # USB-C mid-mount receptacle: body in the board notch, straddling the board (mechanics keep-out z 4.12..7.33), 8.94 wide, 7.35 deep
    k = (19.03, 26.35, 27.97, 33.7)
    usb = trimesh.creation.box(extents=(k[2] - k[0], k[3] - k[1] - 0.2, 7.33 - 4.12))
    usb.apply_translation(((k[0] + k[2]) / 2, (k[1] + k[3]) / 2 - 0.1, (4.12 + 7.33) / 2))
    parts.append(usb)
    m = trimesh.util.concatenate(parts)
    m.export(out)
    lo, hi = m.bounds
    print("written %s: x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f (pod frame), %d triangles" % (out, lo[0], hi[0], lo[1], hi[1], lo[2], hi[2], len(m.faces)))


if __name__ == "__main__":
    main()
