"""OpenPatch render core: realistic scene from the bench CAD, shots, camera projection, studio compositing.

TEST PROJECT: bench pod, water only, never worn.  Everything here is deterministic: the same CAD file and the same
shot description give the same image (fixed seed, fixed sample count).

Pipeline
  build_base(size)   OP-xxx.sc  ->  work/base_OP-xxx.sc   real component models inserted at the frames of
                                    mechanical/components/catalog.json, envelope bodies hidden, realistic
                                    materials assigned, studio lighting preset applied.  Cached by content hash.
  render_shot(...)   base + per-shot script (visibility, grey context, explode offsets, camera, quality)
                     -> raw RGBA PNG (transparent background)
  compose.py         raw PNG -> studio image (light / dark), arrows, badges, labels, check images.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import components as comp  # noqa: E402
import parts_model as pm  # noqa: E402

BASE_VERSION = "2"   # bump when build_base() changes what the base scene contains
CLI = os.environ.get("SOLIDCRAFT_CLI") or shutil.which("solidcraft-cli") or "/usr/local/bin/solidcraft-cli"
CAD = Path(os.environ.get("OP_CAD_DIR", ROOT / "mechanical" / "out" / "bench"))
WORK = Path(os.environ.get("OP_RENDER_WORK", HERE / "work"))
CATALOG = json.loads((ROOT / "mechanical" / "components" / "catalog.json").read_text())

# ------------------------------------------------------------------ materials
GREY = {"color": "#c9ced3", "pbr": {"metallic": 0.0, "roughness": 0.85, "dielectric_ior": 1.45}}
GREY_GHOST = {"color": "#e3e6e9", "pbr": {"metallic": 0.0, "roughness": 0.9, "dielectric_ior": 1.45}}


def dielectric(color, rough=0.5, opacity=None):
    # The CPU ray tracer accepts opaque bodies only (InvalidScene otherwise), so "translucent" materials are
    # rendered as opaque pale colours; `opacity` is kept in the signature for the day glass becomes available.
    return {"color": color, "pbr": {"metallic": 0.0, "roughness": rough, "dielectric_ior": 1.5}}


def metal(color, rough=0.3):
    return {"color": color, "pbr": {"metallic": 1.0, "roughness": rough, "dielectric_ior": 1.5}}


LOOKS = {
    "housing": dielectric("#efece6", 0.66),                 # matte MJF PA12 / SLA white, slightly warm
    "lid": dielectric("#f1eee8", 0.62),
    "sla": dielectric("#d9dee3", 0.42),                      # SLA tough resin, pale grey
    "sla_warm": dielectric("#e8dfcc", 0.40),
    "pp_clear": dielectric("#d3e3ec", 0.22, 0.34),           # clear PP / SLA reservoir
    "water": dielectric("#8fc8ee", 0.05, 0.55),              # water, slightly blue
    "silicone": dielectric("#e9f1f3", 0.38, 0.72),           # translucent platinum silicone
    "gasket": dielectric("#d6dbde", 0.45, 0.85),
    "steel": metal("#c9ccd0", 0.28),
    "ndfeb": metal("#aeb2b8", 0.33),
    "brass": metal("#cfa653", 0.30),
    "brass_dark": metal("#b8923f", 0.38),
    "nickel": metal("#bfc2c6", 0.28),
    "tin": metal("#d6d8db", 0.3),
    "gold": metal("#dcb842", 0.22),
    "black_pa": dielectric("#1d1d20", 0.55),
    "black_ic": dielectric("#18181a", 0.45),
    "mask": dielectric("#1f6b3a", 0.38),                     # green soldermask
    "mask_black": dielectric("#17191b", 0.40),
    "kapton": dielectric("#d99a45", 0.42, 0.92),
    "beige": dielectric("#e3d9c3", 0.5),
    "ptfe": dielectric("#f4f4f1", 0.6),
    "white_pa": dielectric("#f4f2ec", 0.55),
    "lavender": dielectric("#b79be0", 0.45),
    "coin_ring": metal("#d8c07a", 0.3),
    "coin_core": metal("#c9ccd0", 0.3),
    "mag_n": dielectric("#d23a3a", 0.45),
    "mag_s": dielectric("#3a6bd2", 0.45),
}

# CAD body -> look key (envelope bodies that stay in the scene)
ENV_LOOK = {
    "bottom": "housing", "top": "lid", "gasket": "gasket", "reservoir": "pp_clear",
    "plunger_core": "sla_warm", "plunger_nose": "sla_warm", "seal_a": "silicone", "seal_b": "silicone",
    "carriage": "sla", "tongue_shim": "steel", "pod_board": "mask", "hall_tmag": "black_ic", "hall_drv0": "black_ic",
    "hall_drv1": "black_ic", "hall_dock": "black_ic", "cannula_adapter": "white_pa", "end_cap": "sla",
    "needle_hub": "ptfe", "dock_insert": "sla", "bush_dry": "ptfe", "bush_far": "ptfe",
    "gear": "brass", "gear (2)": "brass", "thrust_sleeve": "brass_dark", "thrust_collar": "brass_dark",
    "rod": "steel", "nut": "brass", "S_half": "ndfeb", "N_half": "ndfeb", "needle": "steel",
    "sleeve": "silicone", "valve_plug": "silicone", "septum": "silicone", "dock_magnet": "ndfeb",
    "gearbox": "nickel", "motor_can": "nickel", "front_boss": "brass", "shaft": "steel", "rear_boss": "brass",
    "term_block": "black_pa", "pin1": "tin", "pin2": "tin", "pin3": "tin", "pin4": "tin",
}
# inserted component bodies -> look key  (<instance key>__<solid name>)
PART_LOOK = {
    "motor__gearbox": "nickel", "motor__motor_can": "nickel", "motor__front_boss": "brass", "motor__shaft": "steel",
    "motor__rear_boss": "brass", "motor__term_block": "black_pa", "motor__pin1": "tin", "motor__pin2": "tin",
    "motor__pin3": "tin", "motor__pin4": "tin",
    "needle__needle": "steel", "fh12__housing": "beige", "fh12__lock": "beige",
    "ffc__film": "kapton",
    "dockmag__S_half": "ndfeb", "dockmag__N_half": "ndfeb", "magnet__S_half": "ndfeb", "magnet__N_half": "ndfeb",
}
for _k in range(1, 15):
    PART_LOOK[f"fh12__tail{_k}"] = "gold"
    PART_LOOK[f"fh12__tab_{'l' if _k == 1 else 'r'}"] = "gold"
for _k in range(1, 11):
    PART_LOOK[f"ffc__c0_{_k}"] = "tin"
    PART_LOOK[f"ffc__c1_{_k}"] = "tin"


def cli(*args, check=True):
    r = subprocess.run([CLI, *args], capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f"solidcraft-cli {' '.join(map(str, args[:4]))} failed:\n{r.stderr[-2000:]}{r.stdout[-500:]}")
    return r


def run_cmds(src, cmds, dst=None, results=False, tag="x"):
    WORK.mkdir(parents=True, exist_ok=True)
    p = WORK / f"cmd_{tag}.json"
    p.write_text(json.dumps(cmds))
    a = ["run", "--in", str(src), str(p)]
    if dst:
        a += ["--save", str(dst)]
    if results:
        a += ["--results"]
    r = cli(*a)
    p.unlink(missing_ok=True)
    if results:
        t = r.stdout
        return json.loads(t[t.find("["):])
    return None


def inspect(src):
    r = cli("inspect", str(src))
    return json.loads(r.stdout)


# ------------------------------------------------------------------ base scene
def _unique(name, existing):
    if name not in existing:
        return name
    n = 2
    while f"{name} ({n})" in existing:
        n += 1
    return f"{name} ({n})"


def _catalog_bodies(file_id):
    if file_id in CATALOG:
        return list(CATALOG[file_id]["bodies"])
    c = {p.pid: p for p in comp.parts()}[file_id]
    return list(c.mat)


def _insert_list():
    """[(instance key, file id, matrix, hide-after?)] of everything that is inserted into the base scene."""
    items = []
    items.append(("fh12", pm.FH12["file"], pm.mat(pm.FH12["cols"], pm.FH12["t"])))
    items.append(("ffc", pm.FFC["file"], pm.mat(pm.FFC["cols"], pm.FFC["t"])))
    for i, (x, y) in enumerate([(2.0, 4.2), (2.0, 11.7), (2.0, 17.0), (28.8, 18.8)]):
        items.append((f"lidscrew{i + 1}", "screw_iso7045_m1p2x6", pm.mat(pm.AX_Z, (x, y, 7.4))))
    items.append(("boardscrew", "screw_iso7045_m1p2x4", pm.mat(pm.AX_Z, (36.4, 19.4, 5.9 + 0.0))))
    return items


def _cad_file(size):
    """Round-2 CAD: OP-xx_real.sc already carries the vendor-accurate library models; fall back to the envelope design."""
    f = CAD / f"{size}_real.sc"
    return f if f.exists() else CAD / f"{size}.sc"


def _src_hash(size):
    h = hashlib.sha256()
    h.update(_cad_file(size).read_bytes())
    h.update(BASE_VERSION.encode())
    for f in ("parts_model.py", "components.py"):
        h.update((HERE / f).read_bytes())
    for k in sorted(CATALOG):
        h.update(k.encode())
    return h.hexdigest()[:16]


def build_base(size="OP-100", force=False):
    """Return (base .sc path, info dict)."""
    WORK.mkdir(parents=True, exist_ok=True)
    comp.ensure()
    base = WORK / f"base_{size}.sc"
    meta = WORK / f"base_{size}.json"
    hsh = _src_hash(size)
    if not force and base.exists() and meta.exists() and json.loads(meta.read_text()).get("hash") == hsh:
        return base, json.loads(meta.read_text())
    src = WORK / f"{size}.src.sc"
    shutil.copy(_cad_file(size), src)
    envelope_names = [b["name"] for b in inspect(src)["bodies"]]
    existing = set(envelope_names)
    cmds, bodies_of, looks, hidden = [], {}, {}, []
    expect = []
    for key, fid, matrix in _insert_list():
        cmds.append({"command": "file.insert_step", "params": {"path": str(comp.path(fid)), "name": f"r_{key}", "matrix": matrix}})
        ins_idx = len(cmds) - 1
        raw = _catalog_bodies(fid)
        names, pred = [], []
        for b in raw:
            n = _unique(b, existing)
            existing.add(n)
            new = f"{key}__{b}"
            cmds.append({"command": "body.rename", "params": {"bodies": [n], "name": new}})
            existing.discard(n)
            existing.add(new)
            names.append(new)
            pred.append(n)
        expect.append((ins_idx, sorted(pred)))
        bodies_of[key] = names
    hidden += ["ffc_conn", "ffc_cable"]
    hidden = [h for h in hidden if h in envelope_names]
    # reservoir water (hidden unless a shot shows it)
    cmds.append({"command": "sketch.create", "params": {"plane": "YZ", "offset": 9.7}})
    cmds.append({"command": "sketch.slot.center_to_center", "params": {"p0": [11.2 - 5.45, 4.2], "p1": [11.2 + 5.45, 4.2], "width": 4.9}})
    cmds.append({"command": "sketch.finish", "params": {}})
    cmds.append({"command": "solid.extrude", "params": {"distance": 13.5, "body_name": "water", "name": "water"}})
    hidden.append("water")
    # looks
    allb = envelope_names + [b for v in bodies_of.values() for b in v] + ["water"]
    for b in allb:
        if b in hidden:
            continue
        k = ENV_LOOK.get(b)
        if b in PART_LOOK:
            k = PART_LOOK[b]
        if b == "water":
            k = "water"
        if k is None:
            inst = b.partition("__")[0]
            k = "steel" if inst.startswith(("lidscrew", "boardscrew")) else (pm.REAL.get(inst) or {}).get("look")
        if k is None:
            k = "sla"
        looks[b] = k
        cmds.append({"command": "appearance.assign", "params": {"bodies": [b], **LOOKS[k]}})
    for h in hidden:
        cmds.append({"command": "browser.visibility", "params": {"visible": False, "items": [h]}})
    cmds.append({"command": "render.settings.set", "params": {"name": "main", "set": {
        "backend": "builtin", "mode": "final", "width": 1200, "height": 800,
        "camera": {"target": [23.5, 16.0, 3.5], "yaw": -0.62, "pitch": 0.46, "distance": 190, "fov": 0.22, "roll": 0, "up": "z"},
        "job": {"method": "cpu_raytrace"}}}})
    res = run_cmds(src, cmds + [{"command": "render.preset.resolve", "params": {"id": "NATIVE-STUDIO-002", "name": "main"}}], results=True, tag="base1")
    # self-check of the predicted body names
    for idx, names in expect:
        got = sorted(res[idx].get("created_bodies") or res[idx].get("bodies") or [])
        if got != names:
            raise SystemExit(f"body-name prediction failed at command {idx}: expected {names}, got {got}")
    rev = res[-1]["revision"]
    run_cmds(src, cmds + [
        {"command": "render.preset.apply", "params": {"id": "NATIVE-STUDIO-002", "name": "main", "expected_revision": rev,
                                                       "replace_lighting_and_environment": True, "replace_stage": True}},
        {"command": "render.stage.clear", "params": {"name": "main"}}], dst=base, tag="base2")
    got = run_cmds(base, [{"command": "render.settings.get", "params": {"name": "main"}}], results=True, tag="get")
    setup = got[-1]["setup"]
    bbox = {b["name"]: [b["bbox"]["min"], b["bbox"]["max"]] for b in inspect(base)["bodies"]}
    info = {"bbox": bbox, "hash": hsh, "bodies_of": bodies_of, "looks": looks, "hidden": hidden, "envelope": envelope_names,
            "setup": setup, "all": allb}
    meta.write_text(json.dumps(info, indent=1))
    return base, info


# ------------------------------------------------------------------ camera + projection
def project(cam, pts, w, h):
    """Project pod-space points to pixel coordinates for a SolidCraft camera dict (calibrated, see calibrate())."""
    t = cam["target"]
    yaw, pitch, dist = cam["yaw"], cam["pitch"], cam["distance"]
    fov = cam.get("fov", 0.5)
    cp, sp, cy, sy = math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    # camera position direction (from target toward the eye), z up
    eye_dir = (cp * sy * CAL["sx"], -cp * cy * CAL["sy"], sp)
    n = math.sqrt(sum(c * c for c in eye_dir))
    f = tuple(-c / n for c in eye_dir)                      # forward
    up0 = (0, 0, 1)
    rx = (f[1] * up0[2] - f[2] * up0[1], f[2] * up0[0] - f[0] * up0[2], f[0] * up0[1] - f[1] * up0[0])
    rn = math.sqrt(sum(c * c for c in rx))
    r = tuple(c / rn for c in rx)
    u = (r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0])
    eye = tuple(t[i] - f[i] * dist for i in range(3))
    focal = (h / 2) / math.tan(fov / 2) if CAL["fov_vertical"] else (w / 2) / math.tan(fov / 2)
    out = []
    for p in pts:
        d = tuple(p[i] - eye[i] for i in range(3))
        x = sum(d[i] * r[i] for i in range(3))
        y = sum(d[i] * u[i] for i in range(3))
        z = sum(d[i] * f[i] for i in range(3))
        out.append((w / 2 + focal * x / z, h / 2 - focal * y / z))
    return out


CAL = {"sx": 1.0, "sy": 1.0, "fov_vertical": True}
_cal = HERE / "camera_calibration.json"
if _cal.exists():
    CAL.update(json.loads(_cal.read_text()))


# ------------------------------------------------------------------ shots
QUALITY = {
    "draft": dict(spp=8, depth=3, denoise=True),
    "step": dict(spp=6, depth=2, denoise=True),
    "tt": dict(spp=3, depth=2, denoise=True),
    "hero": dict(spp=14, depth=3, denoise=True),
}


def job_for(setup, quality):
    q = QUALITY[quality]
    job = json.loads(json.dumps(setup["job"]))
    job["transparent_background"] = True
    opt = job.setdefault("options", {})
    opt["budget"] = "studio"
    opt["progressive"] = {"samples_per_pixel": q["spp"], "seed": 7}
    opt["path"] = {"max_depth": q["depth"]}
    opt["denoise"] = q["denoise"]
    return job


def _extras_cmds(info, extras):
    """Insert extra component models (loose parts, tools-free) into a shot scene. Returns (cmds, bodies, expect)."""
    cmds, bodies, expect = [], [], []
    existing = set(info["all"])
    for ex in extras:
        fid = ex.get("file")
        cmds.append({"command": "file.insert_step", "params": {"path": str(ex.get("path") or comp.path(fid)), "name": f"x_{ex['key']}",
                                                                 "matrix": pm.mat(ex.get("cols", pm.AX_Z), ex["t"])}})
        ins = len(cmds) - 1
        pred, names = [], []
        for b in (ex.get("bodies") or _catalog_bodies(fid)):
            n = _unique(b, existing)
            existing.add(n)
            new = f"x_{ex['key']}__{b}"
            cmds.append({"command": "body.rename", "params": {"bodies": [n], "name": new}})
            existing.discard(n)
            existing.add(new)
            pred.append(n)
            names.append(new)
            lk = (ex.get("looks") or {}).get(b) or ex.get("look") or PART_LOOK.get(f"{ex.get('lib', ex['key'])}__{b}") or "steel"
            cmds.append({"command": "appearance.assign", "params": {"bodies": [new], **LOOKS[lk]}})
        expect.append((ins, sorted(pred)))
        bodies += names
        ex["_bodies"] = names
    return cmds, bodies, expect


def shot_commands(info, spec):
    """Commands that turn the base scene into one shot.

    spec: dict(show=[bodies in realistic look], ctx=[bodies as grey context], hide_rest=True,
               explode={body:(dx,dy,dz)}, camera=cam, size=(w,h), quality='step', ev=-0.35, look={body:lookkey},
               extras=[loose component models], check=dict(camera=..., size=...) second saved setup)
    """
    ex_cmds, ex_bodies, expect = _extras_cmds(info, spec.get("extras", []))
    allb = list(info["all"]) + ex_bodies
    show = set(spec.get("show", [])) | set(ex_bodies)
    ctx = set(spec.get("ctx", []))
    keep = show | ctx
    cmds = list(ex_cmds)
    for b in allb:
        cmds.append({"command": "browser.visibility", "params": {"visible": b in keep, "items": [b]}})
    for b in ctx:
        cmds.append({"command": "appearance.assign", "params": {"bodies": [b], **GREY}})
    for b, k in (spec.get("look") or {}).items():
        cmds.append({"command": "appearance.assign", "params": {"bodies": [b], **(LOOKS[k] if isinstance(k, str) else k)}})
    sec = spec.get("section")
    if sec:     # remove everything on one side of a plane: dict(axis='z', value=4.2, remove='above')
        ax = "xyz".index(sec["axis"])
        for i, b in enumerate(sorted(keep)):
            bb = info["bbox"].get(b)
            if not bb or not (bb[0][ax] < sec["value"] < bb[1][ax]):
                continue
            corner = [-30.0, -30.0, -30.0]
            dims = [160.0, 160.0, 160.0]
            if sec.get("remove", "above") == "above":
                corner[ax] = sec["value"]
            else:
                corner[ax] = sec["value"] - dims[ax]
            cmds.append({"command": "solid.box", "params": {"length": dims[0], "width": dims[1], "height": dims[2], "corner": corner,
                                                            "body_name": f"sec_{i}", "name": f"sec_{i}"}})
            cmds.append({"command": "solid.combine", "params": {"target": b, "tools": [f"sec_{i}"], "operation": "cut", "name": f"section {b}"}})
    for b, t in (spec.get("explode") or {}).items():
        if any(t) and b in keep:
            cmds.append({"command": "solid.move", "params": {"bodies": [b], "translate": list(t)}})
    q = spec.get("quality", "step")
    base_set = json.loads(json.dumps(info["setup"]))
    base_set["job"] = job_for(info["setup"], q)
    base_set["exposure_ev"] = spec.get("ev", -0.35)
    setups = {"main": (spec.get("size", (1200, 800)), spec["camera"])}
    if spec.get("setups"):
        setups = {k: (tuple(v[0]), v[1]) for k, v in spec["setups"].items()}
    if spec.get("check"):
        setups["check"] = (spec["check"].get("size", (700, 500)), spec["check"]["camera"])
    for name, (size, cam) in setups.items():
        cam = dict(cam)
        cam.setdefault("fov", 0.22)
        cam.update(roll=0, up="z")
        s = json.loads(json.dumps(base_set))
        s.update(width=size[0], height=size[1], camera=cam)
        cmds.append({"command": "render.settings.set", "params": {"name": name, "set": s}})
    return cmds, expect, list(setups)


def render_shot(name, spec, size="OP-100", outdir=None, keep_scene=False):
    """Render one shot (and its optional check setup) to transparent PNGs; returns {setup: path}."""
    base, info = build_base(size)
    outdir = Path(outdir or WORK / "raw")
    outdir.mkdir(parents=True, exist_ok=True)
    stage = WORK / f"shot_{name}.sc"
    cmds, expect, setups = shot_commands(info, spec)
    res = run_cmds(base, cmds, dst=stage, results=True, tag=f"s_{name}")
    for idx, names in expect:
        got = sorted(res[idx].get("created_bodies") or res[idx].get("bodies") or [])
        if got != names:
            raise SystemExit(f"{name}: extra body-name prediction failed: expected {names}, got {got}")
    outs = {}
    for s in setups:
        out = outdir / (f"{name}.png" if s == "main" else f"{name}_{s}.png")
        if spec.get("only_setup") and s != spec["only_setup"]:
            continue
        cli("render", str(stage), "--setup", s, "--out", str(out), "--overwrite", "--timeout", "3000", "--legacy-memory-admission")
        outs[s] = out
    if not keep_scene:
        stage.unlink(missing_ok=True)
        Path(str(stage) + ".bak").unlink(missing_ok=True)
    return outs


def groups(info):
    """Convenience groups of body names used by shots and guide steps (names of OP-xx_real.sc plus the inserted extras)."""
    b = info["bodies_of"]
    g = {
        "shell": ["bottom"], "lid": ["top"], "gasket": ["gasket"],
        "plunger": ["plunger_core", "plunger_nose", "seal_a", "seal_b"],
        "plunger_core": ["plunger_core"], "nose": ["plunger_nose"], "seals": ["seal_a", "seal_b"],
        "reservoir": ["reservoir"], "endcap": ["end_cap"],
        "septum": ["septum"], "duckbill": ["sleeve"], "valve_plug": ["valve_plug"],
        "needle": ["needle"], "hub": ["needle_hub"],
        "motor": ["gearbox", "motor_can", "front_boss", "shaft", "rear_boss", "term_block", "pin1", "pin2", "pin3", "pin4"],
        "geara": ["gear"], "gearb": ["gear (2)"], "sleeve": ["thrust_sleeve"], "collar": ["thrust_collar"],
        "rod": ["rod"], "nut": ["nut"], "magnet": ["S_half", "N_half"],
        "bushes": ["bush_dry", "bush_far"], "bush_dry": ["bush_dry"], "bush_far": ["bush_far"],
        "carriage": ["carriage"], "shim": ["tongue_shim"],
        "board": ["pod_board", "hall_tmag", "hall_drv0", "hall_drv1", "hall_dock"], "fh12": b["fh12"], "ffc": b["ffc"],
        "boardscrew": b["boardscrew"], "lidscrews": sum([b[f"lidscrew{i}"] for i in range(1, 5)], []),
        "dock": ["dock_insert"], "head": ["cannula_adapter", "dock_magnet"], "dockmag": ["dock_magnet"],
        "water": ["water"],
    }
    hid = set(info["hidden"]) - {"water"}
    return {k: [x for x in v if x in set(info["all"]) and x not in hid] for k, v in g.items()}
