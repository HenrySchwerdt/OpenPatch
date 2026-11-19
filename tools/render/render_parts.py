#!/usr/bin/env python3
"""'Parts on the table' pages of the build guide: every loose part laid out and labelled with its BOM id, like IKEA.

    python3 tools/render/render_parts.py raw        # path-trace parts_large + parts_small (transparent PNG)
    python3 tools/render/render_parts.py compose    # label pages -> docs/build-guide/steps/parts-1.webp, parts-2.webp, tools.webp

Large page: housing and fluidic parts.  Small page: drive, fasteners, needle, magnets, cables.  Tools page: icons.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guide_data as gd  # noqa: E402
import icons  # noqa: E402
import oprender as o  # noqa: E402
import parts_model as pm  # noqa: E402
import render_guide as rg  # noqa: E402
import studio as S  # noqa: E402

ROOT = HERE.parents[1]
IMG = ROOT / "docs" / "build-guide" / "steps"
RAW = o.WORK / "raw" / "parts"
FOV = 0.22

# page -> list of (label, bom id, qty, groups | extra spec, (x, y))
LARGE = [
    ("P1", ["shell"], (-52, 26)), ("P2", ["lid"], (4, 26)), ("M2", ["gasket"], (58, 26)),
    ("P6", ["reservoir"], (-52, -8)), ("P7", ["endcap"], (-18, -8)), ("P9", ["dock"], (14, -8)), ("P8", ["head_body"], (46, -8)),
    ("E1", ["board"], (-52, -38)), ("B1", ["motor"], (-18, -38)),
    ("P4", ["plunger_core"], (14, -38)), ("P3", ["carriage"], (40, -38)), ("P5", ["nose"], (56, -38)),
]
SMALL = [
    ("B5", ["rod"], (-34, 22)), ("B4", ["sleeve"], (-10, 22)), ("B4c", ["collar"], (2, 22)), ("B6", ["nut"], (14, 22)), ("B7", ["bush_dry"], (24, 22)),
    ("B8", ["magnet"], (34, 22)), ("B9", ["dockmag"], (44, 22)),
    ("B10", ["shim"], (-34, 8)), ("B11", ["needle"], (-14, 8)), ("B12", ["hub"], (2, 8)), ("B13", ["duckbill"], (14, 8)), ("M3", ["valve_plug"], (26, 8)),
    ("B14", ["septum"], (38, 8)), ("M1", ["seals"], (50, 8)),
]
EXTRAS_SMALL = [
    ("B2", dict(key="ga", file="gear_m03_z16_390754", look="brass"), (-34, -8)),
    ("B3", dict(key="gb", file="gear_m03_z20_753020", look="brass"), (-18, -8)),
    ("B16a", dict(key="s6", file="screw_iso7045_m1p2x6", look="steel"), (-2, -8)),
    ("B16b", dict(key="s4", file="screw_iso7045_m1p2x4", look="steel"), (10, -8)),
    ("B17", dict(key="ffc2", file="ffc_05mm_10p_same_side", look="kapton"), (26, -8)),
    ("B18", dict(key="tube", file="tube_silicone_1p6", look="ptfe"), (44, -8)),
    ("SC", dict(key="coin", file="coin_2eur", looks={"ring": "coin_ring", "core": "coin_core"}), (30, -34)),
]


def cam(target, h, yaw, pitch):
    return dict(target=list(target), yaw=yaw, pitch=pitch, distance=h / (2 * math.tan(FOV / 2)), fov=FOV)


def layout(info, items, extras):
    g = rg.step_specs.__globals__["o"].groups(info)
    g.update({k: [b for b in v if b in info["all"]] for k, v in rg.EXTRA_GROUPS.items()})
    bbox = info["bbox"]
    shift, show, placed = {}, [], []
    for label, groups, (tx, ty) in items:
        bs = [b for name in groups for b in g[name]]
        lo = [min(bbox[b][0][i] for b in bs) for i in range(3)]
        hi = [max(bbox[b][1][i] for b in bs) for i in range(3)]
        c = [(lo[i] + hi[i]) / 2 for i in range(3)]
        for b in bs:
            shift[b] = (tx - c[0], ty - c[1], -lo[2])
        show += bs
        placed.append((label, (tx, ty, hi[2] - lo[2])))
    ex = []
    for label, spec, (tx, ty) in extras:
        # extras are inserted lying flat; z axis parts (screws, coin, gears) are placed so their local origin sits at (tx, ty)
        spec = dict(spec)
        spec["cols"] = pm.AX_Z if spec["file"] not in ("rod", "ffc_05mm_10p_same_side", "tube_silicone_1p6") else pm.AX_Z
        spec["t"] = (tx, ty, 2.0 if "screw" in spec["file"] else 0.0)
        if spec["file"] == "tube_silicone_1p6":
            spec["cols"] = ((1, 0, 0), (0, 0, 1), (0, -1, 0))     # lying along Y
            spec["t"] = (tx, ty - 12, 1.6)
        if spec["file"] == "screw_iso7045_m1p2x6" or spec["file"] == "screw_iso7045_m1p2x4":
            spec["cols"] = ((1, 0, 0), (0, 0, 1), (0, -1, 0))
            spec["t"] = (tx, ty + 3, 1.2)
        if spec["file"].startswith("gear"):
            spec["cols"] = pm.AX_Z
            spec["t"] = (tx, ty, 2.5 if "z20" in spec["file"] else 0.0)
        if spec["file"].startswith("ffc"):
            spec["cols"] = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
            spec["t"] = (tx, ty - 12, 0.0)
        ex.append(spec)
        placed.append((label, (tx, ty, 3)))
    return show, shift, ex, placed


def raw():
    RAW.mkdir(parents=True, exist_ok=True)
    base, info = o.build_base("OP-100")
    show, shift, _, _ = layout(info, LARGE, [])
    spec = dict(show=show, explode=shift, camera=cam((0, 0, 0), 150, 0.0, 1.1), size=(1800, 1200), quality="hero")
    if not (RAW / "parts_large.png").exists():
        o.render_shot("parts_large", spec, outdir=RAW)["main"].replace(RAW / "parts_large.png")
    show, shift, ex, _ = layout(info, SMALL, EXTRAS_SMALL)
    spec = dict(show=show, explode=shift, extras=ex, camera=cam((8, -4, 0), 92, 0.0, 1.1), size=(1800, 1200), quality="hero")
    if not (RAW / "parts_small.png").exists():
        o.render_shot("parts_small", spec, outdir=RAW)["main"].replace(RAW / "parts_small.png")


def compose():
    base, info = o.build_base("OP-100")
    pages = [("parts-1", "Parts on the table: housing and fluid parts", RAW / "parts_large.png", LARGE, [], cam((0, 0, 0), 150, 0.0, 1.1)),
             ("parts-2", "Parts on the table: drive, fasteners and small parts", RAW / "parts_small.png", SMALL, EXTRAS_SMALL, cam((8, -4, 0), 92, 0.0, 1.1))]
    for pid, title, path, items, extras, cm in pages:
        if not path.exists():
            print("missing", path)
            continue
        _, _, _, placed = layout(info, items, extras)
        W, H = 1800, 1200
        canvas = S.backdrop(W, H, "light")
        im = Image.open(path).convert("RGBA")
        S.with_shadow(canvas, im, (0, 0), "light", drop=0.01)
        d = ImageDraw.Draw(canvas)
        d.text((40, 30), title, font=S.font(46, "Bold"), fill=S.THEMES["light"]["ink"])
        d.text((40, 90), "Check every part against the list before step 1. Bench only, water only.", font=S.font(26), fill=S.THEMES["light"]["mute"])
        for label, (x, y, zh) in placed:
            if label == "SC":
                continue
            px, py = o.project(cm, [(x, y, 0)], W, H)[0]
            q = gd.BOM[label][2]
            tag = f"{q}x {label}" if q > 1 else label
            f = S.font(28, "Bold")
            tw = d.textlength(tag, font=f)
            bx, by = px - tw / 2 - 12, py + 30
            S.rounded(d, (bx, by, bx + tw + 24, by + 44), 12, fill=(24, 26, 30))
            d.text((bx + 12, by + 5), tag, font=f, fill=(255, 255, 255))
        canvas.convert("RGB").save(IMG / f"{pid}.webp", "WEBP", quality=84, method=6)
    # tools page
    W, H = 1800, 1100
    canvas = S.backdrop(W, H, "light")
    d = ImageDraw.Draw(canvas)
    d.text((40, 30), "Tools and consumables", font=S.font(46, "Bold"), fill=S.THEMES["light"]["ink"])
    x0, y0, cw, ch = 40, 130, 330, 190
    for i, (tid, name) in enumerate(gd.TOOLS.items()):
        cx, cy = x0 + (i % 5) * (cw + 20), y0 + (i // 5) * (ch + 20)
        S.rounded(d, (cx, cy, cx + cw, cy + ch), 22, fill=(255, 255, 255), outline=S.THEMES["light"]["line"], width=3)
        canvas.alpha_composite(icons.tool(tid, 100), (cx + 24, cy + 24))
        for j, ln in enumerate(S.wrap(name, S.font(24, "Medium"), cw - 40, d)[:3]):
            d.text((cx + 24, cy + 132 + j * 0) if False else (cx + 140, cy + 40 + j * 30), ln, font=S.font(24, "Medium"), fill=S.THEMES["light"]["ink"])
    y = y0 + 4 * (ch + 20) - 10
    cons = [f"{k}  {v[0]} ({v[1]})" for k, v in gd.BOM.items() if k.startswith("C")]
    d.text((40, y), "Consumables:  " + "   |   ".join(cons), font=S.font(22), fill=S.THEMES["light"]["mute"])
    canvas.convert("RGB").save(IMG / "tools.webp", "WEBP", quality=84, method=6)
    print("parts/tools pages written")


if __name__ == "__main__":
    raw() if (sys.argv[1] if len(sys.argv) > 1 else "raw") == "raw" else compose()
