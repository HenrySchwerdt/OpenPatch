#!/usr/bin/env python3
"""Render the raw (transparent) images of the IKEA-style build guide: one main image per step, plus the check
("must look like this") and wrong ("common mistake") images where the step defines them.

    python3 tools/render/render_guide.py [--only A01 B05 ...] [--jobs 3] [--quality step] [--size OP-100]

Output: tools/render/work/raw/steps/<id>.png, <id>_check.png, <id>_wrong.png (RGBA, transparent background).
Existing files are kept (use --force).  compose_guide.py then builds the final pages.
"""
from __future__ import annotations

import argparse
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guide_data as gd  # noqa: E402
import oprender as o  # noqa: E402
import parts_model as pm  # noqa: E402

FOV = 0.22
RAW = o.WORK / "raw" / "steps"

ROOT_INS = o.ROOT / "mechanical" / "out" / "bench" / "fab" / "dock-inserts"
EXTRA_GROUPS = {"seals_a": ["seal_a"], "seals_b": ["seal_b"], "head_body": ["cannula_adapter"]}


def view(v, aspect=None):
    (t, h, yaw, pitch) = v
    return dict(target=list(t), yaw=yaw, pitch=pitch, distance=h / (2 * math.tan(FOV / 2)), fov=FOV)


def step_specs(info, size_main=(900, 675), size_check=(560, 420), quality="step"):
    """Yield (step, kind, spec) for every image of every step, with the cumulative context resolved."""
    g = o.groups(info)
    g.update({k: [b for b in v if b in info["all"]] for k, v in EXTRA_GROUPS.items()})
    bbox = info["bbox"]

    def bodies(groups):
        return [b for name in groups for b in g[name]]

    def center(bs):
        lo = [min(bbox[b][0][i] for b in bs) for i in range(3)]
        hi = [max(bbox[b][1][i] for b in bs) for i in range(3)]
        return [(lo[i] + hi[i]) / 2 for i in range(3)], lo, hi

    acc = set()
    out = []
    for st in gd.STEPS:
        new = bodies(st["new"])
        ctx_groups = list(st.get("ctx") or [])
        ctx = set(bodies(ctx_groups))
        if st.get("acc"):
            ctx |= acc
        ctx -= set(new)
        base = dict(show=new, ctx=sorted(ctx), quality=quality)
        extras = []
        if st.get("loose_gear"):
            f, hub = ("gear_m03_z16_390754", None) if st["loose_gear"] == "a" else ("gear_m03_z20_753020", None)
            y = 28.0 if st["loose_gear"] == "a" else 22.5
            extras.append(dict(key=f"raw{st['loose_gear']}", file=f, cols=pm.AX_X, t=(2.6, y, 4.2), look="brass"))
            base["show"] = []
        explode = {}
        shift = {}
        if st["id"] == "F04":       # fit test on the pod-less dock fixture (same frozen interface, file frame = pod frame - 25.8 in X)
            ins = ROOT_INS / "insert_v01.step"
            extras += [dict(key="fixture", path=str(ROOT_INS / "dock_fixture.step"), bodies=["dock_fixture"], look="housing", cols=pm.AX_Z, t=(0, 0, 0)),
                       dict(key="insv01", path=str(ins), bodies=["dock_insert_v01"], look="sla", cols=pm.AX_Z, t=(0, 0, 0))]
            base["show"] = bodies(["head"])
            for b in bodies(["head"]):
                shift[b] = (-25.8 + 14, 0, 0)
        if st.get("loose") and len(new) > 1:
            # lay the loose parts out in a row on the table (centres on x, y = 0, resting on z = 0)
            x = 0.0
            placed = []
            for name in st["new"]:
                bs = g[name]
                if not bs:
                    continue
                c, lo, hi = center(bs)
                w = hi[0] - lo[0]
                dx = x + w / 2 - c[0]
                dy = -c[1] if name not in ("reservoir",) else -c[1]
                dz = -lo[2]
                for b in bs:
                    shift[b] = (dx, dy, dz)
                x += w + 5
                placed.append(name)
            tot = x - 5
            for b in shift:
                shift[b] = (shift[b][0] - tot / 2, shift[b][1], shift[b][2])
        lift = {}
        for name, vec in (st.get("lift") or {}).items():
            for b in g.get(name, []):
                lift[b] = vec
        arrows = []
        for name, vec in (st.get("lift") or {}).items():
            bs = g.get(name, [])
            if bs:
                c, _, _ = center(bs)
                arrows.append(dict(a=[c[i] + vec[i] for i in range(3)], b=c, group=name))
        spec = dict(base)
        spec["extras"] = extras
        spec["explode"] = {**shift, **lift}
        # auto-fit the main view to everything that is drawn (parts, context, lifted parts)
        shown = list(new) + sorted(ctx)
        pts_lo, pts_hi = [1e9] * 3, [-1e9] * 3
        for b in shown:
            sh = spec["explode"].get(b, (0, 0, 0))
            for i in range(3):
                pts_lo[i] = min(pts_lo[i], bbox[b][0][i] + sh[i])
                pts_hi[i] = max(pts_hi[i], bbox[b][1][i] + sh[i])
        cam_v = st["cam"]
        if shown and not st.get("loose_gear") and not st.get("fixed_cam"):
            ctr = [(pts_lo[i] + pts_hi[i]) / 2 for i in range(3)]
            diag = math.sqrt(sum((pts_hi[i] - pts_lo[i]) ** 2 for i in range(3)))
            cam_v = (tuple(ctr), max(14.0, diag * 0.82 + 3), st["cam"][2], st["cam"][3])
        spec["camera"] = view(cam_v)
        spec["size"] = size_main
        out.append((st, "main", spec, arrows))
        chk = st.get("check")
        if chk:
            cv = chk[1] or st["cam"]
            if chk[1] is None:
                cv = (st["cam"][0], st["cam"][1] * 0.8, st["cam"][2], st["cam"][3])
            s2 = dict(base)
            # check image: parts in their final place
            s2["extras"] = []
            if st.get("loose_gear"):
                s2["show"] = new
            s2["explode"] = dict(shift)
            s2["camera"] = view(cv)
            s2["size"] = size_check
            out.append((st, "check", s2, []))
        wr = st.get("wrong")
        if wr and wr[1]:
            cv = (chk[1] if chk and chk[1] else st["cam"])
            s3 = dict(base)
            s3["extras"] = []
            sh = {}
            for name, vec in wr[1].items():
                for b in g.get(name, []):
                    sh[b] = vec
            s3["explode"] = {**shift, **sh}
            s3["camera"] = view(cv)
            s3["size"] = size_check
            out.append((st, "wrong", s3, []))
        if st.get("acc") and not st.get("noacc"):
            acc |= set(new) | ctx
        elif st.get("acc") is None:
            pass
    return out


def render_all(only=None, jobs=2, quality="step", force=False, size="OP-100"):
    base, info = o.build_base(size)
    RAW.mkdir(parents=True, exist_ok=True)
    items = step_specs(info, quality=quality)
    todo = []
    for st, kind, spec, arrows in items:
        if only and st["id"] not in only:
            continue
        name = st["id"] if kind == "main" else f"{st['id']}_{kind}"
        if (RAW / f"{name}.png").exists() and not force:
            continue
        todo.append((name, spec))

    def work(it):
        name, spec = it
        try:
            outs = o.render_shot(f"g_{name}", spec, size=size, outdir=RAW)
            src = outs["main"]
            final = RAW / f"{name}.png"
            src.replace(final)
            print("done", name, flush=True)
        except SystemExit as e:  # keep going on a failed step
            print("FAILED", name, str(e)[:300], flush=True)

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        list(ex.map(work, todo))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--quality", default="step")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--size", default="OP-100")
    a = ap.parse_args()
    render_all(set(a.only) if a.only else None, a.jobs, a.quality, a.force, a.size)
