#!/usr/bin/env python3
"""Photoreal product renders of OpenPatch via the SolidCraft path tracer.

Usage: render-product.py <shot> [--quick]   shots: hero | exploded | top70 | top100 | top200 | all
Writes transparent PNGs to a work dir (default: $OP_RENDER_WORK or ./.render-work).
render-product.sh then converts them to AVIF/WebP/PNG in public/renders/.
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

CLI = os.environ.get("SOLIDCRAFT_CLI", "/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli")
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("OP_CAD_DIR", ROOT / "mechanical" / "out"))
WORK = Path(os.environ.get("OP_RENDER_WORK", Path(__file__).resolve().parents[1] / ".render-work"))

SHELL = {"color": "#ecebe7", "pbr": {"metallic": 0.0, "roughness": 0.62, "dielectric_ior": 1.45}}
METAL = {"appearance": "starter.metal.stainless-soft-satin"}
LOOKS = {  # restrained, believable materials for the cut-away parts; unlisted bodies get METAL
    "gasket": {"appearance": "starter.plastic.tpu-matte-black"},
    "reservoir": {"appearance": "starter.plastic.hdpe-natural-opaque"},
    "plunger_core": {"appearance": "starter.plastic.abs-warm-white"},
    "seal_a": {"appearance": "starter.plastic.tpu-matte-black"},
    "seal_b": {"appearance": "starter.plastic.tpu-matte-black"},
    "carriage": {"appearance": "starter.plastic.nylon-ivory"},
    "nut": {"appearance": "starter.metal.brass-champagne"},
    "gearhead": {"appearance": "starter.metal.titanium-matte"},
    "motor": {"appearance": "starter.metal.aluminum-bead-blast"},
    "gear_a": {"appearance": "starter.metal.brass-champagne"},
    "gear_b": {"appearance": "starter.metal.brass-champagne"},
    "battery": {"appearance": "starter.plastic.pc-graphite-opaque"},
    "pcb": {"color": "#20362e", "pbr": {"metallic": 0.1, "roughness": 0.35, "dielectric_ior": 1.5}},
    "qi_coil": {"appearance": "starter.metal.copper-aged-warm"},
    "rf_module": {"appearance": "starter.metal.silver-cool"},
    "buzzer": {"appearance": "starter.plastic.pom-black"},
    "switch": {"appearance": "starter.plastic.pom-black"},
    "septum": {"appearance": "starter.plastic.tpu-matte-black"},
    "magnet": {"appearance": "starter.metal.carbon-steel-polished"},
}
HIDDEN = {"pcb_keepout"}
SHELL_BODIES = {"bottom", "top"}
# exploded lift along Z (mm), applied per body; unlisted bodies stay put
LIFT = {"top": 36, "gasket": 30, "qi_coil": 24, "rf_module": 21, "buzzer": 18, "switch": 18, "pcb": 12,
        "hall_tmag": 12, "hall_drv0": 12, "hall_drv1": 12, "battery": 4,
        "reservoir": 14, "plunger_core": 14, "seal_a": 14, "seal_b": 14, "carriage": 16, "nut": 16,
        "leadscrew": 21, "bush_dry": 21, "bush_far": 21, "magnet": 21,
        "gearhead": 21, "motor": 21, "gear_a": 21, "gear_b": 21, "septum": 7, "needle": 3, "needle_hub": 3}

SHOTS = {
    # name: design, w, h, camera, exploded, shell_hidden_keepout
    "hero_graphite": dict(d="OP-100", w=2400, h=1500, cam=dict(target=[21, 16, 3.5], yaw=-0.62, pitch=0.46, distance=190, fov=0.22), expl=False, graphite=True),
    "hero":     dict(d="OP-100", w=2400, h=1500, cam=dict(target=[21, 16, 3.5], yaw=-0.62, pitch=0.46, distance=190, fov=0.22), expl=False),
    "exploded": dict(d="OP-100", w=2000, h=1600, cam=dict(target=[21, 16, 19], yaw=-0.62, pitch=0.42, distance=340, fov=0.22), expl=True),
    "top70":    dict(d="OP-70",  w=1000, h=800, cam=dict(target=[19, 16, 4], yaw=0, pitch=1.5707, distance=650, fov=0.1), expl=False, scale=True),
    "top100":   dict(d="OP-100", w=1000, h=800, cam=dict(target=[21, 16, 4], yaw=0, pitch=1.5707, distance=650, fov=0.1), expl=False, scale=True),
    "top200":   dict(d="OP-200", w=1000, h=800, cam=dict(target=[27.7, 16, 4], yaw=0, pitch=1.5707, distance=650, fov=0.1), expl=False, scale=True),
}

def cli(*args, check=True):
    r = subprocess.run([CLI, *args], capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"solidcraft-cli {' '.join(args[:3])} failed:\n{r.stderr[-1500:]}")
    return r

def run_script(src, cmds, dst=None, results=False):
    p = WORK / "script.json"; p.write_text(json.dumps(cmds))
    a = ["run", "--in", str(src), str(p)]
    if dst: a += ["--save", str(dst)]
    if results: a += ["--results"]
    return cli(*a)

def build(name, quick):
    s = SHOTS[name]
    WORK.mkdir(parents=True, exist_ok=True)
    src = WORK / f"{s['d']}.sc"
    shutil.copy(OUT / f"{s['d']}.sc", src)  # copy: CAD output may be regenerated meanwhile
    w, h = (s["w"] // 3, s["h"] // 3) if quick else (s["w"], s["h"])
    names = [b["name"] for b in json.loads(cli("eval", str(src)).stdout)["bodies"]]
    shell = {"appearance": "starter.plastic.pc-graphite-opaque"} if s.get("graphite") else SHELL
    cmds = [{"command": "appearance.assign", "params": {"bodies": ["bottom", "top"], **shell}}]
    for b in names:
        if b in SHELL_BODIES or b in HIDDEN:
            continue
        look = LOOKS.get(b, METAL)
        cmds.append({"command": "appearance.assign", "params": {"bodies": [b], **look}})
    hide = set(HIDDEN)
    if s["expl"]:
        for b, z in LIFT.items():
            if b in names:
                cmds.append({"command": "solid.move", "params": {"bodies": [b], "translate": [0, 0, z]}})
    else:
        hide |= {b for b in names if b not in SHELL_BODIES and b != "gasket"}
    for b in sorted(hide & set(names)):
        cmds.append({"command": "browser.visibility", "params": {"visible": False, "items": [b]}})
    cmds.append({"command": "render.settings.set", "params": {"name": "hero", "set": {
        "backend": "builtin", "mode": "final", "width": w, "height": h, "camera": {**s["cam"], "roll": 0, "up": "z"},
        "job": {"method": "cpu_raytrace"}}}})
    resolve = cmds + [{"command": "render.preset.resolve", "params": {"id": "NATIVE-STUDIO-002", "name": "hero"}}]
    out = run_script(src, resolve, results=True).stdout
    rev = json.loads(out)[-1]["revision"]
    cmds.append({"command": "render.preset.apply", "params": {"id": "NATIVE-STUDIO-002", "name": "hero", "expected_revision": rev,
        "replace_lighting_and_environment": True, "replace_stage": True}})
    cmds.append({"command": "render.stage.clear", "params": {"name": "hero"}})
    staged = WORK / f"{name}.sc"
    run_script(src, cmds, dst=staged)
    got = cli("run", "--in", str(staged), str(_write(WORK / "get.json", [{"command": "render.settings.get", "params": {"name": "hero"}}])), "--results").stdout
    setup = json.loads(got)[-1]["setup"]
    job = setup["job"]; job["transparent_background"] = True
    ev = float(os.environ.get("OP_EV", "-0.7"))
    fix = [{"command": "render.settings.set", "params": {"name": "hero", "set": {"job": job, "exposure_ev": ev}}}]
    run_script(staged, fix, dst=staged)
    return staged

def _write(p, data):
    p.write_text(json.dumps(data)); return p

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    quick = "--quick" in sys.argv
    names = list(SHOTS) if not args or args[0] == "all" else args
    for n in names:
        staged = build(n, quick)
        png = WORK / f"{n}.png"
        print(f"rendering {n} …", flush=True)
        cli("render", str(staged), "--setup", "hero", "--out", str(png), "--overwrite", "--timeout", "3000")
        print("  ->", png)

if __name__ == "__main__":
    main()
