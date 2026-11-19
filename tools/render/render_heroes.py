#!/usr/bin/env python3
"""Hero, exploded, section, detail, size and turntable renders of the OP pods -> docs/renders/ + manifest.json.

TEST PROJECT: bench pod, water only, never worn.  No human body parts appear in any image (scale = coin).

    python3 tools/render/render_heroes.py raw [ids ...]      # path-trace the raw transparent PNGs (slow, resumable)
    python3 tools/render/render_heroes.py compose            # studio composites (light + dark), labels, lineup, manifest

Raw output: tools/render/work/raw/heroes/<id>.png.  Final: docs/renders/<id>[-dark].webp + manifest.json.
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
import oprender as o  # noqa: E402
import parts_model as pm  # noqa: E402
import render_guide as rg  # noqa: E402
import studio as S  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "docs" / "renders"
RAW = o.WORK / "raw" / "heroes"
FOV = 0.22
INSERTS = ROOT / "mechanical" / "out" / "bench" / "fab" / "dock-inserts"


def cam(target, h, yaw, pitch):
    return dict(target=list(target), yaw=yaw, pitch=pitch, distance=h / (2 * math.tan(FOV / 2)), fov=FOV)


def allbodies(info, drop=("water",)):
    g = rg_groups(info)
    return sorted({b for k, v in g.items() if k not in drop for b in v})


def rg_groups(info):
    g = o.groups(info)
    g.update({k: [b for b in v if b in info["all"]] for k, v in rg.EXTRA_GROUPS.items()})
    return g


# explode offsets per group (pod frame, mm): z levels staggered so every part is visible
EXPLODE = {
    "lid": (0, 0, 52), "lidscrews": (0, 0, 66), "gasket": (0, 0, 40), "boardscrew": (0, 0, 46), "ffc": (16, 0, 34), "fh12": (0, 0, 30),
    "board": (0, 0, 30), "head": (34, 0, 6), "dock": (16, 0, 0), "magnet": (10, 0, 22), "collar": (6, 0, 22), "rod": (0, 0, 22),
    "nut": (0, 0, 30), "carriage": (0, 0, 18), "shim": (0, -10, 18), "gearb": (0, 0, 16), "sleeve": (-8, 0, 16), "geara": (-8, 0, 16),
    "motor": (0, 6, 12), "bushes": (0, 0, 10), "reservoir": (0, 0, 12), "plunger_core": (-14, 0, 14), "seals": (-14, 0, 26), "nose": (-4, 0, 26),
    "endcap": (14, 0, 12), "septum": (14, -12, 12), "duckbill": (14, 0, 24), "valve_plug": (14, 0, 34), "needle": (22, 0, 10), "hub": (20, 0, 10),
}
LABELS = {
    "lid": "Lid", "lidscrews": "Lid screws M1.2 x 6", "gasket": "Gasket", "boardscrew": "Board screw M1.2 x 4", "ffc": "FFC cable",
    "fh12": "FFC connector", "board": "Sensor board", "head": "Dummy cannula head", "dock": "Dock insert", "magnet": "Spindle magnet",
    "collar": "Front collar", "rod": "Leadscrew M1.6", "nut": "Brass nut", "carriage": "Carriage", "shim": "Steel shim",
    "gearb": "Gear B, 20 T", "sleeve": "Thrust sleeve", "geara": "Gear A, 16 T", "motor": "Geared stepper", "bushes": "PTFE bushes",
    "reservoir": "Reservoir", "plunger_core": "Plunger core", "seals": "Seal rings", "nose": "Plunger nose", "endcap": "End cap",
    "septum": "Fill septum", "duckbill": "Duckbill valve", "valve_plug": "Valve plug", "needle": "30G needle", "hub": "Needle hub",
    "shell": "Bottom shell",
}


def shots(info):
    g = rg_groups(info)
    allb = allbodies(info)
    bbox = info["bbox"]
    ex = {}
    for name, vec in EXPLODE.items():
        for b in g.get(name, []):
            ex[b] = vec
    hero_q = "hero"
    S_ = {}
    S_["hero_34"] = dict(show=allb, camera=cam((23.5, 16, 3.5), 62, -0.62, 0.42), size=(1500, 940), quality=hero_q)
    S_["hero_34_b"] = dict(show=allb, camera=cam((23.5, 16, 3.5), 56, 0.7, 0.5), size=(1500, 940), quality=hero_q)
    S_["top"] = dict(show=allb, camera=cam((23.5, 16, 3.5), 46, 0.0, 1.45), size=(1500, 1000), quality=hero_q)
    S_["exploded"] = dict(show=allb, explode=ex, camera=cam((26, 14, 26), 132, -0.62, 0.45), size=(1500, 1500), quality=hero_q)
    # section: plan section through the drive axis plane and the reservoir axis, lid off, water in the reservoir
    sec_show = [b for b in allb if b not in g["lid"] + g["lidscrews"] + g["gasket"] + g["board"] + g["fh12"] + g["ffc"] + g["boardscrew"]] + g["water"]
    S_["section_plan"] = dict(show=sec_show, section=dict(axis="z", value=4.2, remove="above"), camera=cam((22, 16, 3), 40, 0.0, 1.45),
                              size=(1500, 1000), quality=hero_q)
    S_["section_34"] = dict(show=sec_show, section=dict(axis="z", value=4.2, remove="above"), camera=cam((20, 16, 3), 42, -0.55, 0.75),
                            size=(1500, 1000), quality=hero_q)
    S_["open_34"] = dict(show=[b for b in allb if b not in g["lid"] + g["lidscrews"] + g["gasket"]], camera=cam((23.5, 16, 3.5), 58, -0.62, 0.62),
                         size=(1500, 940), quality=hero_q)
    # macro details
    S_["detail_gears"] = dict(show=g["geara"] + g["gearb"] + g["sleeve"] + g["bush_dry"] + g["rod"] + g["motor"] + ["bottom"],
                              section=dict(axis="z", value=4.2, remove="above"), camera=cam((3.3, 25.2, 4.2), 13, 0.0, 1.3), size=(1400, 1000), quality=hero_q)
    S_["detail_needle"] = dict(show=g["needle"] + g["hub"] + g["endcap"] + g["duckbill"] + g["valve_plug"] + g["dock"] + g["head"],
                               camera=cam((36, 11, 3), 22, -0.75, 0.35), size=(1400, 1000), quality=hero_q)
    S_["detail_sensor"] = dict(show=g["board"] + g["magnet"] + g["rod"] + g["bush_far"] + g["collar"] + g["fh12"], camera=cam((28.5, 22.5, 4.8), 14, -0.5, 0.45),
                               size=(1400, 1000), quality=hero_q)
    # scale: 2 euro coin next to the pod, top view
    S_["scale_coin"] = dict(show=allb, extras=[dict(key="coin", file="coin_2eur", cols=pm.AX_Z, t=(62.0, 15.0, 0.0), looks={"ring": "coin_ring", "core": "coin_core"})],
                            camera=cam((37, 16, 2), 62, 0.0, 1.45), size=(1500, 940), quality=hero_q)
    # dock inserts: four of the twelve variants side by side (file frame x 4.4..21.1, y 3.6..18.8)
    ex_ins = []
    for i, v in enumerate((1, 4, 8, 12)):
        ex_ins.append(dict(key=f"ins{v}", path=str(INSERTS / f"insert_v{v:02d}.step"), bodies=[f"dock_insert_v{v:02d}"], look="sla",
                           cols=pm.AX_Z, t=(0.0, i * 20.0 - 30.0, 0.0)))
    S_["dock_variants"] = dict(show=[], extras=ex_ins, camera=cam((12, -2, 2), 56, -0.5, 0.75), size=(1500, 940), quality=hero_q)
    # turntable: 24 frames, one scene
    tt = {}
    for i in range(24):
        yaw = -3.14159 + i * 2 * 3.14159 / 24
        tt[f"f{i:02d}"] = ((560, 400), cam((23.5, 16, 3.5), 64, yaw, 0.42))
    S_["turntable"] = dict(show=allb, setups=tt, quality="tt", size=(560, 400), camera=cam((23.5, 16, 3.5), 64, 0, 0.4))
    return S_


def raw(ids):
    RAW.mkdir(parents=True, exist_ok=True)
    base, info = o.build_base("OP-100")
    S_ = shots(info)
    for k, spec in S_.items():
        if ids and k not in ids:
            continue
        if k == "turntable":
            if (RAW / "turntable_f23.png").exists():
                continue
            outs = o.render_shot("hero_turntable", spec, outdir=RAW)
            for n, p in outs.items():
                p.replace(RAW / f"turntable_{n}.png") if n != "main" else p.unlink()
            continue
        if (RAW / f"{k}.png").exists():
            continue
        print("rendering", k, flush=True)
        outs = o.render_shot(f"hero_{k}", spec, outdir=RAW)
        outs["main"].replace(RAW / f"{k}.png")
    # size line-up: the other two sizes, same camera scale
    for size in ("OP-70", "OP-200"):
        if ids and "lineup" not in ids:
            continue
        if (RAW / f"top_{size}.png").exists():
            continue
        b2, i2 = o.build_base(size)
        sp = dict(show=allbodies(i2), camera=cam((23.5, 16, 3.5), 46, 0.0, 1.45), size=(1500, 1000), quality="hero")
        o.render_shot(f"hero_top_{size}", sp, size=size, outdir=RAW)["main"].replace(RAW / f"top_{size}.png")


# ------------------------------------------------------------------ compose
def save(im, name, q=84):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    im.save(p, "WEBP", quality=q, method=6)
    while p.stat().st_size > 400_000 and q > 40:
        q -= 8
        im.save(p, "WEBP", quality=q, method=6)
    return p.stat().st_size


def studio_image(path, variant, size=None, pad=0.06, caption=None, floor=True):
    raw_im = Image.open(path).convert("RGBA")
    w, h = size or raw_im.size
    canvas = S.backdrop(w, h, variant)
    sp = S.trim(raw_im, 4)
    k = min((w * (1 - 2 * pad)) / sp.width, (h * (1 - 2 * pad)) / sp.height)
    sp = sp.resize((int(sp.width * k), int(sp.height * k)), Image.LANCZOS)
    pos = ((w - sp.width) // 2, (h - sp.height) // 2)
    S.with_shadow(canvas, sp, pos, variant)
    return canvas, sp, pos, k


def compose(ids=None):
    base, info = o.build_base("OP-100")
    S_ = shots(info)
    g = rg_groups(info)
    manifest = []

    def add(id_, kind, title, caption, variant, im, name, size_note=None):
        sz = save(im, name)
        manifest.append(dict(id=id_, file=f"renders/{name}", kind=kind, title=title, caption=caption, size=list(im.size), variant=variant, bytes=sz))

    for k, kind, title, cap in [
        ("hero_34", "hero", "OP-100 bench pod, three-quarter view", "The OP-100 bench pod, closed: lid, four screws, FFC cable and dock mouth. Test hardware, water only."),
        ("hero_34_b", "hero", "OP-100, from the dry end", "Same pod seen from the dry end."),
        ("top", "hero", "OP-100, top view", "Top view with the fill window and the 10 U scale."),
        ("open_34", "detail", "OP-100 with the lid removed", "Lid, gasket and screws removed: board, drive and reservoir."),
        ("section_34", "section", "Cutaway through drive and reservoir", "Section at z = 4.2 mm: gear pair, leadscrew and carriage, plunger and water-filled reservoir."),
        ("section_plan", "section", "Plan section at z = 4.2 mm", "Plan section through the drive axis plane."),
        ("detail_gears", "detail", "Gear mesh 16:20", "GHW module 0.3 brass gears: 16 T on the motor shaft, 20 T on the thrust sleeve, centre 5.51 mm."),
        ("detail_needle", "detail", "Needle and dock insert", "30G outlet needle in its hub, end cap with duckbill valve, dock insert and dummy head."),
        ("detail_sensor", "detail", "Sensor board over the spindle magnet", "TMAG5273 board above the diametric spindle magnet on the rod end."),
        ("scale_coin", "detail", "Size next to a 2 euro coin", "OP-100 (47 x 32 x 8.4 mm) beside a 2 euro coin (25.75 mm)."),
        ("dock_variants", "detail", "Dock insert variants", "Dock insert variants v01, v04, v08 and v12 of the twelve-piece fit-test set."),
    ]:
        if ids and k not in ids:
            continue
        p = RAW / f"{k}.png"
        if not p.exists():
            print("missing", k)
            continue
        for var in ("light", "dark"):
            canvas, _, _, _ = studio_image(p, var)
            add(f"{k}", kind, title, cap, var, canvas.convert("RGB"), f"{k}{'-dark' if var == 'dark' else ''}.webp")
    # exploded + labelled
    p = RAW / "exploded.png"
    if p.exists() and (not ids or "exploded" in ids):
        for var in ("light", "dark"):
            canvas, sp, pos, k_ = studio_image(p, var, size=(1800, 1500), pad=0.12)
            add("exploded", "exploded", "OP-100 exploded", "Every real part, spaced out along the assembly axes.", var, canvas.convert("RGB"), f"exploded{'-dark' if var == 'dark' else ''}.webp")
            canvas = canvas.copy()
            d = ImageDraw.Draw(canvas)
            spec = S_["exploded"]
            # recompute the placement of the raw image in the composite: raw is (1500,1500) trimmed
            raw_im = Image.open(p).convert("RGBA")
            bb = raw_im.getchannel("A").getbbox()
            sx = lambda x: pos[0] + (x - max(0, bb[0] - 4)) * k_  # noqa: E731
            sy = lambda y: pos[1] + (y - max(0, bb[1] - 4)) * k_  # noqa: E731
            labs = []
            for name, vec in EXPLODE.items():
                bs = g.get(name, [])
                if not bs:
                    continue
                lo = [min(info["bbox"][b][0][i] for b in bs) for i in range(3)]
                hi = [max(info["bbox"][b][1][i] for b in bs) for i in range(3)]
                c = [(lo[i] + hi[i]) / 2 + vec[i] for i in range(3)]
                x, y = o.project(spec["camera"], [c], 1500, 1500)[0]
                labs.append((sy(y), sx(x), LABELS[name]))
            labs.sort()
            L = [l for l in labs if l[1] < 900]
            R = [l for l in labs if l[1] >= 900]
            ink = S.THEMES[var]["ink"]
            for side, items in (("L", L), ("R", R)):
                n = len(items)
                for i, (y, x, text) in enumerate(items):
                    ty = 120 + i * (1260 / max(1, n))
                    tx = 60 if side == "L" else 1740
                    d.line([(x, y), (tx + (250 if side == "L" else -10), ty + 14)], fill=S.THEMES[var]["mute"], width=2)
                    d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=ink)
                    f = S.font(26, "Medium")
                    tw = d.textlength(text, font=f)
                    d.text((tx if side == "L" else tx - tw, ty), text, font=f, fill=ink)
            add("exploded_labelled", "exploded", "OP-100 exploded, labelled", "Exploded view with part names.", var, canvas.convert("RGB"), f"exploded-labelled{'-dark' if var == 'dark' else ''}.webp")
    # lineup
    parts = [(RAW / "top_OP-70.png", "OP-70"), (RAW / "top.png", "OP-100"), (RAW / "top_OP-200.png", "OP-200")]
    if all(p.exists() for p, _ in parts) and (not ids or "lineup" in ids):
        dims = {"OP-70": "40 x 32", "OP-100": "47 x 32", "OP-200": "58 x 32"}
        for var in ("light", "dark"):
            tw_, th_ = 2000, 760
            canvas = S.backdrop(tw_, th_, var)
            d = ImageDraw.Draw(canvas)
            # same camera scale in all three raw images: crop the same pixel window around the pod centre
            x = 40
            for p, nm in parts:
                im = Image.open(p).convert("RGBA")
                sp = S.trim(im, 4)
                sp = sp.resize((int(sp.width * 0.62), int(sp.height * 0.62)), Image.LANCZOS)
                S.with_shadow(canvas, sp, (x, 150 + (460 - sp.height) // 2), var)
                d.text((x, 80), nm, font=S.font(40, "Bold"), fill=S.THEMES[var]["ink"])
                d.text((x + 170, 92), dims[nm] + " mm", font=S.font(26), fill=S.THEMES[var]["mute"])
                x += sp.width + 60
            add("lineup", "hero", "OP-70, OP-100 and OP-200", "The three bench pod sizes at the same scale; only reservoir and screw length differ.", var, canvas.convert("RGB"), f"lineup{'-dark' if var == 'dark' else ''}.webp")
    # turntable
    frames = sorted(RAW.glob("turntable_f*.png"))
    if len(frames) == 24 and (not ids or "turntable" in ids):
        for i, fp in enumerate(frames):
            canvas, _, _, _ = studio_image(fp, "light", size=(560, 400))
            sz = save(canvas.convert("RGB"), f"turntable/frame-{i:02d}.webp", 78)
            manifest.append(dict(id=f"turntable-{i:02d}", file=f"renders/turntable/frame-{i:02d}.webp", kind="turntable", title=f"OP-100 turntable frame {i + 1} of 24",
                                 caption="Turntable frame, 15 degrees per frame.", size=[560, 400], variant="light", bytes=sz))
    # merge with existing manifest entries of other kinds (guide, components)
    mp = OUT / "manifest.json"
    old = json.loads(mp.read_text()) if mp.exists() else {"images": []}
    keep = [m for m in old.get("images", []) if m["kind"] in ("step", "component")]
    mp.write_text(json.dumps(dict(note="Rendered by tools/render (SolidCraft path tracer) from mechanical/out/bench/OP-*_real.sc. TEST PROJECT: bench pod, water only, never worn.",
                                  images=manifest + keep), indent=1))
    print(len(manifest), "images in manifest")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "raw"
    ids = set(sys.argv[2:])
    raw(ids) if cmd == "raw" else compose(ids or None)
