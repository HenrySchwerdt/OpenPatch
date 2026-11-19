#!/usr/bin/env python3
"""Compose the IKEA-style step pages from the raw renders, write docs/build-guide/steps.json and the booklet.

    python3 tools/render/compose_guide.py [--only A01 ...]

Needs the raw renders of render_guide.py.  Steps without a raw image are skipped (reported at the end).
Output: docs/build-guide/steps/<id>.webp (+ <id>_check.webp, <id>_wrong.webp), steps.json, booklet.html, booklet.pdf
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guide_data as gd  # noqa: E402
import icons  # noqa: E402
import oprender as o  # noqa: E402
import render_guide as rg  # noqa: E402
import studio as st_  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "docs" / "build-guide"
IMG = OUT / "steps"
RAW = rg.RAW
W, H = 1400, 1000
MAIN_BOX = (320, 20, 1380, 830)
CHAPTERS = {"A": "Prepare the parts", "B": "Build the sub-assemblies", "C": "Shell, drive and needle", "D": "Sensor board and cable",
            "E": "Close the pod", "F": "Dock and dummy head", "G": "Finish"}


def symbol(d, c, r, kind, color):
    x, y = c
    d.ellipse([x - r, y - r, x + r, y + r], fill=color)
    k = r * 0.5
    if kind == "ok":
        d.line([(x - k, y), (x - k * 0.25, y + k * 0.8), (x + k, y - k * 0.7)], fill=(255, 255, 255), width=int(r * 0.28), joint="curve")
    else:
        d.line([(x - k * 0.8, y - k * 0.8), (x + k * 0.8, y + k * 0.8)], fill=(255, 255, 255), width=int(r * 0.28))
        d.line([(x - k * 0.8, y + k * 0.8), (x + k * 0.8, y - k * 0.8)], fill=(255, 255, 255), width=int(r * 0.28))


def inset(canvas, path, box, color, kind, caption, variant="light"):
    t = st_.THEMES[variant]
    img = Image.open(path).convert("RGBA")
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    d = ImageDraw.Draw(canvas)
    st_.rounded(d, (x0 - 6, y0 - 6, x1 + 6, y1 + 66), 18, fill=t["panel"], outline=color, width=5)
    bg = st_.backdrop(w, h, variant)
    img = st_.trim(img, 8)
    img.thumbnail((w - 20, h - 20), Image.LANCZOS)
    st_.with_shadow(bg, img, ((w - img.width) // 2, (h - img.height) // 2), variant)
    canvas.alpha_composite(bg, (x0, y0))
    d = ImageDraw.Draw(canvas)
    symbol(d, (x0 + 6, y0 + 6), 28, kind, color)
    f = st_.font(21, "Medium")
    y = y1 + 10
    for ln in st_.wrap(caption, f, w, d)[:2]:
        d.text((x0 + 4, y), ln, font=f, fill=t["ink"])
        y += 26


def build_page(step, meta, variant="light"):
    t = st_.THEMES[variant]
    canvas = st_.backdrop(W, H, variant)
    d = ImageDraw.Draw(canvas)
    main = Image.open(RAW / f"{step['id']}.png").convert("RGBA")
    cam, size = meta["camera"], meta["size"]
    bb = main.getchannel("A").getbbox() or (0, 0, size[0], size[1])
    pad = 14
    bb = (max(0, bb[0] - pad), max(0, bb[1] - pad), min(size[0], bb[2] + pad), min(size[1], bb[3] + pad))
    crop = main.crop(bb)
    bw, bh = MAIN_BOX[2] - MAIN_BOX[0], MAIN_BOX[3] - MAIN_BOX[1]
    scale = min(bw / crop.width, bh / crop.height, 2.2)
    sprite = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)
    ox = MAIN_BOX[0] + (bw - sprite.width) // 2
    oy = MAIN_BOX[1] + (bh - sprite.height) // 2 - 10
    st_.with_shadow(canvas, sprite, (ox, oy), variant)

    def P(pt):
        x, y = o.project(cam, [pt], *size)[0]
        return (ox + (x - bb[0]) * scale, oy + (y - bb[1]) * scale)

    for a in meta["arrows"]:
        st_.arrow(canvas, P(a["a"]), P(a["b"]), color=t["ink"] if variant == "light" else (255, 255, 255), halo=(255, 255, 255) if variant == "light" else (20, 20, 24))
    if step.get("turn"):
        c = P(step["turn"][0])
        st_.curved_arrow(canvas, c, 46, 210, 520, color=t["ink"])
    d = ImageDraw.Draw(canvas)
    for label, pt in step.get("mark") or []:
        c = P(pt)
        st_.badge(d, c, 17, label, fill=(232, 163, 23), fg=(24, 26, 30), size=22)
    # action icon (non-3D actions)
    ic = icons.action(step["icon"]) if step.get("icon") else None
    if ic:
        st_.rounded(d, (W - 220, 30, W - 30, 220), 28, fill=t["panel"], outline=t["line"], width=3)
        canvas.alpha_composite(ic.resize((140, 140), Image.LANCZOS), (W - 195, 55))
    # step number
    d = ImageDraw.Draw(canvas)
    st_.rounded(d, (28, 24, 300, 150), 22, fill=(24, 26, 30) if variant == "light" else (240, 242, 245))
    d.text((52, 30), str(step["n"]), font=st_.font(96, "ExtraBold"), fill=(255, 255, 255) if variant == "light" else (20, 20, 24))
    d.text((180, 44), step["id"], font=st_.font(30, "SemiBold"), fill=(170, 176, 184))
    d.text((180, 84), CHAPTERS[step["ch"]].split()[0].upper(), font=st_.font(17, "SemiBold"), fill=(170, 176, 184))
    # parts panel
    y = 176
    if step.get("parts"):
        n = len(step["parts"])
        st_.rounded(d, (28, y, 300, y + 22 + n * 52), 18, fill=t["panel"], outline=t["line"], width=2)
        for i, (pid, q) in enumerate(step["parts"]):
            yy = y + 14 + i * 52
            st_.badge(d, (56, yy + 22), 20, f"{q}x", fill=(24, 26, 30) if variant == "light" else (240, 242, 245),
                      fg=(255, 255, 255) if variant == "light" else (20, 20, 24), size=20)
            d.text((88, yy + 2), pid, font=st_.font(24, "Bold"), fill=t["ink"])
            nm = gd.BOM[pid][0]
            d.text((88, yy + 28), nm if len(nm) < 24 else nm[:23] + ".", font=st_.font(14), fill=t["mute"])
        y += 36 + n * 52
    # tools
    if step.get("tools"):
        n = len(step["tools"])
        st_.rounded(d, (28, y, 300, y + 24 + n * 74), 18, fill=t["panel"], outline=t["line"], width=2)
        for i, tid in enumerate(step["tools"]):
            yy = y + 12 + i * 74
            canvas.alpha_composite(icons.tool(tid, 56), (40, yy))
            nm = gd.TOOLS[tid]
            for j, ln in enumerate(st_.wrap(nm, st_.font(15), 150, d)[:2]):
                d.text((106, yy + 10 + j * 19), ln, font=st_.font(15), fill=t["ink"])
        y += 36 + n * 74
    # check / wrong insets (bottom right, over the empty corner of the main image)
    cx = W - 30
    chk = step.get("check")
    wr = step.get("wrong")
    cp, wp = RAW / f"{step['id']}_check.png", RAW / f"{step['id']}_wrong.png"
    both = bool(chk and cp.exists() and wr and wp.exists())
    iw, ih = (250, 188) if both else (300, 225)
    if chk and cp.exists():
        box = (cx - iw, 250, cx, 250 + ih) if both else (cx - iw, 560, cx, 560 + ih)
        inset(canvas, cp, box, st_.GREEN, "ok", chk[0], variant)
    if wr and wp.exists():
        box = (cx - iw, 540, cx, 540 + ih) if both else (cx - iw, 560, cx, 560 + ih)
        inset(canvas, wp, box, st_.RED, "no", wr[0], variant)
    # text band
    d = ImageDraw.Draw(canvas)
    d.text((30, 836), step["title"], font=st_.font(36, "Bold"), fill=t["ink"])
    yy = 888
    for ln in step["lines"][:3]:
        d.text((30, yy), ln, font=st_.font(24), fill=t["mute"] if variant == "light" else (200, 205, 212))
        yy += 32
    if step.get("warn"):
        x0 = 760
        st_.rounded(d, (x0, 878, W - 30, 978), 16, fill=(255, 244, 214), outline=st_.AMBER, width=3)
        d.polygon([(x0 + 24, 892), (x0 + 62, 958), (x0 - 14, 958)], fill=st_.AMBER)
        d.text((x0 + 15, 920), "!", font=st_.font(34, "ExtraBold"), fill=(24, 26, 30))
        wl = st_.wrap(step["warn"], st_.font(20, "Medium"), W - 30 - x0 - 90, d)[:3]
        for i, ln in enumerate(wl):
            d.text((x0 + 76, 886 + i * 27), ln, font=st_.font(20, "Medium"), fill=(70, 50, 0))
    return canvas.convert("RGB")


def save_webp(im, path, q=84):
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "WEBP", quality=q, method=6)
    while path.stat().st_size > 400_000 and q > 50:
        q -= 8
        im.save(path, "WEBP", quality=q, method=6)


def write_booklet(steps):
    """booklet.html (print-ready, one page per step) and booklet.pdf (the same pages, 1400 x 1000)."""
    pages = [("parts-1", "Parts on the table 1"), ("parts-2", "Parts on the table 2"), ("tools", "Tools")]
    files = [(t, IMG / f"{i}.webp") for i, t in pages if (IMG / f"{i}.webp").exists()]
    files += [(f"{s['id']} {s['title']}", OUT / s["image"]) for s in steps if (OUT / s["image"]).exists()]
    html = ["<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>OpenPatch OP-100 build guide (booklet)</title>",
            "<style>@page{size:A4 landscape;margin:0}body{margin:0;background:#fff;font-family:Inter,Arial,sans-serif}",
            "section{page-break-after:always;width:297mm;height:210mm;display:flex;align-items:center;justify-content:center;background:#f4f5f6}",
            "img{width:297mm;height:auto;max-height:210mm;object-fit:contain}.cover{flex-direction:column;text-align:center;background:#fff}",
            "h1{font-size:34pt;margin:0 0 8pt}p{font-size:13pt;max-width:200mm}</style></head><body>",
            "<section class=\"cover\"><div><h1>OpenPatch OP-100 bench pod: build guide</h1>",
            "<p><b>BENCH TEST ONLY.</b> Not a medical device. Never worn on, attached to or used on a person or an animal. Water only: never insulin or any other drug.</p>",
            "<p>Follow the steps in order. One action per step. Compare your work with the green check image before you go on.</p></div></section>"]
    for title, f in files:
        html.append(f"<section><img src=\"{f.relative_to(OUT).as_posix()}\" alt=\"{title}\"></section>")
    html.append("</body></html>")
    (OUT / "booklet.html").write_text("\n".join(html), encoding="utf-8")
    ims = [Image.open(f).convert("RGB") for _, f in files]
    if ims:
        ims[0].save(OUT / "booklet.pdf", save_all=True, append_images=ims[1:], resolution=120.0)


def write_readme(steps):
    rows = []
    cur = None
    for s in steps:
        if s["chapter"] != cur:
            cur = s["chapter"]
            rows.append(f"\n### {cur}. {CHAPTERS[cur]}\n\n| Step | Action | Parts | Tools |\n|---|---|---|---|")
        parts = ", ".join(f"{p['qty']}x {p['id']}" for p in s["parts"]) or "-"
        tools = ", ".join(t["name"] for t in s["tools"]) or "-"
        rows.append(f"| [{s['n']}]({s['image']}) | {s['title']} | {parts} | {tools} |")
    txt = f"""# OpenPatch OP-100 bench pod: build guide (step by step)

> **WARNING: BENCH TEST ONLY.** OpenPatch is a test project and **not a medical device**. The pod must **never be worn on, attached to, or used on a person or an animal.** **Fill it with water only. Never put insulin or any other drug into it, not even into a container.** See [DISCLAIMER.md](../../DISCLAIMER.md) and [docs/02-safety.md](../02-safety.md).

This guide works like an IKEA or LEGO manual: **one physical action per step**, one large picture, only the parts and the tool of that step, a **green check picture** ("it must look like this") and, where people go wrong, a **red picture** ("not like this"). Arrows show where a part goes. At most three short lines of text per step.

1. Start with [Parts on the table 1](steps/parts-1.webp) and [2](steps/parts-2.webp) and check that you have everything, then look at the [tools](steps/tools.webp).
2. Do the steps in order. Do not go on if the green picture does not match your work.
3. Print the whole guide: [booklet.pdf](booklet.pdf) (or open [booklet.html](booklet.html)). The same steps as data: [steps.json](steps.json) (id, title, image, parts, tools, check, warnings).

Pictures are rendered from the bench CAD (`mechanical/out/bench/OP-100_real.sc`) with the pipeline in [`tools/render/`](../../tools/render/README.md); regenerate them after a CAD change. The long reference chapters (bill of materials with shop links, measurements and go/no-go limits, electronics, water tests, troubleshooting) are kept in [reference-chapters.md](reference-chapters.md) and the numbered chapter files next to it.

## After step G02: commissioning facts (firmware)

Use these when you follow chapters 10 and 11 (they supersede older numbers there):

| Item | Value |
|---|---|
| Drive feature / preset | `drive-nfp-608-26-45-g16-20` (id 0x25, default), 0.003949 U per step (exact rational) |
| Diagnostics commands | GetFaultLog 0x20, RunSelfTest 0x21, ClearDiag 0x22; result code 31 = NoSchedule |
| STSPIN220 run current | 160 mA; thresholds 213 mA (forward occlusion), 253 mA (draw stall) |
| Unplanned reset of an active pod | raises fault 7-74-002: acknowledge it, then resume |
| Prime after a refill | automatic take-up (160 steps, not counted as delivery), wait one minute (1.7 U/min backstop), then 5 prime commands (prime path about 2.21 U, may shrink after the seal and dead-volume study) |
| Draw rate | capped by the fill needle gauge (29G: 841 pps) |

## Steps ({len(steps)})
{chr(10).join(rows)}

## Licence

Documentation: CC BY-NC-SA 4.0 (see [LICENSE.md](../../LICENSE.md)). Bench self-build for research and education only.
"""
    (OUT / "README.md").write_text(txt, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    base, info = o.build_base("OP-100")
    items = rg.step_specs(info)
    meta = {}
    for st, kind, spec, arrows in items:
        if kind == "main":
            meta[st["id"]] = dict(camera=spec["camera"], size=spec["size"], arrows=arrows)
    done, skipped, steps_json = [], [], []
    n = 0
    for st in gd.STEPS:
        n += 1
        st = dict(st, n=n)
        sid = st["id"]
        if not (RAW / f"{sid}.png").exists():
            skipped.append(sid)
            continue
        if not a.only or sid in a.only:
            page = build_page(st, meta[sid])
            save_webp(page, IMG / f"{sid}.webp")
        done.append(sid)
        rec = dict(id=sid, n=n, chapter=st["ch"], chapter_title=CHAPTERS[st["ch"]], title=st["title"], lines=st["lines"], image=f"steps/{sid}.webp",
                   parts=[dict(id=p, qty=q, name=gd.BOM[p][0], spec=gd.BOM[p][1]) for p, q in st.get("parts", [])], tools=[dict(id=t, name=gd.TOOLS[t]) for t in st.get("tools", [])],
                   check=(st["check"][0] if st.get("check") else None), wrong=(st["wrong"][0] if st.get("wrong") else None),
                   warnings=([st["warn"]] if st.get("warn") else []) + [gd.WARN_WATER])
        steps_json.append(rec)
    (OUT / "steps.json").write_text(json.dumps(dict(
        title="OpenPatch OP-100 bench pod build guide", note="BENCH TEST ONLY. Water only. Never worn on a person or animal.",
        chapters=CHAPTERS, bom={k: dict(name=v[0], spec=v[1], qty=v[2]) for k, v in gd.BOM.items()}, tools=gd.TOOLS, steps=steps_json), indent=1))
    write_booklet(steps_json)
    write_readme(steps_json)
    print("composed", len(done), "steps; skipped (no raw image):", skipped)


if __name__ == "__main__":
    main()
