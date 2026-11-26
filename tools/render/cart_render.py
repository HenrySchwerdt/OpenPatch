#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Photoreal renders of the cart pump variant A (SolidCraft path tracer, studio preset NATIVE-STUDIO-002), same pipeline as the cup pod
(site/scripts/render-product.py). TEST PROJECT: bench only, water only, never worn.

  SOLIDCRAFT_CLI=... python3 tools/render/cart_render.py [--quick] [iso top exploded]
Writes transparent PNGs to tools/render/work/cart/ and composites them on a light studio backdrop into docs/renders/cart/ (needs Pillow;
the macOS system /usr/bin/python3 has it: the compositing step runs there when the current interpreter lacks Pillow).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CLI = os.environ.get("SOLIDCRAFT_CLI", "/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli")
SRC = ROOT / "mechanical" / "out" / "v010-cart" / "A" / "OP-CART-A.sc"
WORK = HERE / "work" / "cart"
OUT = ROOT / "docs" / "renders" / "cart"

SHELL = {"color": "#ecebe7", "pbr": {"metallic": 0.0, "roughness": 0.55, "dielectric_ior": 1.45}}      # warm white satin
ADAPTER = {"appearance": "starter.plastic.pc-graphite-opaque"}                                              # dark, as the real Insight adapter
LOOKS = {
    "adapter": ADAPTER, "adapter_lug_a": ADAPTER, "adapter_lug_b": ADAPTER,
    "tubing": {"appearance": "starter.plastic.hdpe-natural-opaque"},
    "button": {"color": "#d9d7d2", "pbr": {"metallic": 0.0, "roughness": 0.8, "dielectric_ior": 1.4}},
    "lid_gasket": {"appearance": "starter.plastic.tpu-matte-black"},
    "cartridge": {"appearance": "starter.plastic.hdpe-natural-opaque"}, "stopper": {"appearance": "starter.plastic.tpu-matte-black"},
    "cart_cap": {"appearance": "starter.metal.silver-cool"},
    "adapter_seal": {"color": "#f2f2ef", "pbr": {"metallic": 0.0, "roughness": 0.6, "dielectric_ior": 1.4}},
}
SHOWN_CLOSED = {"bottom", "top", "lid_gasket", "adapter", "adapter_lug_a", "adapter_lug_b", "adapter_seal", "tubing", "button"}
SHOTS = {
    "iso": dict(w=2400, h=1500, cam=dict(target=[40, 26, 8], yaw=-0.62, pitch=0.48, distance=330, fov=0.22), explode={}),
    "iso_usb": dict(w=2400, h=1500, cam=dict(target=[40, 26, 8], yaw=2.52, pitch=0.42, distance=330, fov=0.22), explode={}),
    "top": dict(w=2000, h=1500, cam=dict(target=[40, 26, 8], yaw=0.0, pitch=1.5707, distance=900, fov=0.1), explode={}),
    "exploded": dict(w=2600, h=1500, cam=dict(target=[52, 26, 8], yaw=-0.62, pitch=0.42, distance=400, fov=0.22),
                     explode={"adapter": (26, 0, 0), "adapter_lug_a": (26, 0, 0), "adapter_lug_b": (26, 0, 0), "tubing": (26, 0, 0),
                              "lock_magnet": (26, 0, 0), "adapter_seal": (26, 0, 0), "cartridge": (13, 0, 0), "stopper": (13, 0, 0), "cart_cap": (13, 0, 0)},
                     extra_show={"cartridge", "stopper", "cart_cap"}),
}


def cli(*args: str) -> subprocess.CompletedProcess:
    r = subprocess.run([CLI, *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"solidcraft-cli {' '.join(args[:3])} failed:\n{r.stdout[-800:]}{r.stderr[-1500:]}")
    return r


def run_script(src: Path, cmds: list, dst: Path | None = None, results: bool = False) -> subprocess.CompletedProcess:
    p = WORK / "script.json"
    p.write_text(json.dumps(cmds))
    a = ["run", "--in", str(src), str(p)]
    if dst:
        a += ["--save", str(dst)]
    if results:
        a += ["--results"]
    return cli(*a)


def build(name: str, quick: bool) -> Path:
    s = SHOTS[name]
    WORK.mkdir(parents=True, exist_ok=True)
    src = WORK / "OP-CART-A.sc"
    shutil.copy(SRC, src)
    w, h = (s["w"] // 3, s["h"] // 3) if quick else (s["w"], s["h"])
    names = [b["name"] for b in json.loads(cli("eval", str(src)).stdout)["bodies"]]
    show = SHOWN_CLOSED | s.get("extra_show", set())
    cmds = [{"command": "appearance.assign", "params": {"bodies": ["bottom", "top"], **SHELL}}]
    for b in names:
        if b in LOOKS:
            cmds.append({"command": "appearance.assign", "params": {"bodies": [b], **LOOKS[b]}})
    for b, t in s["explode"].items():
        if b in names:
            cmds.append({"command": "solid.move", "params": {"bodies": [b], "translate": list(t)}})
    for b in sorted(set(names) - show):
        cmds.append({"command": "browser.visibility", "params": {"visible": False, "items": [b]}})
    cmds.append({"command": "render.settings.set", "params": {"name": "hero", "set": {
        "backend": "builtin", "mode": "final", "width": w, "height": h, "camera": {**s["cam"], "roll": 0, "up": "z"}, "job": {"method": "cpu_raytrace"}}}})
    rev = json.loads(run_script(src, cmds + [{"command": "render.preset.resolve", "params": {"id": "NATIVE-STUDIO-002", "name": "hero"}}], results=True).stdout)[-1]["revision"]
    cmds += [{"command": "render.preset.apply", "params": {"id": "NATIVE-STUDIO-002", "name": "hero", "expected_revision": rev,
                                                         "replace_lighting_and_environment": True, "replace_stage": True}},
             {"command": "render.stage.clear", "params": {"name": "hero"}}]
    staged = WORK / f"{name}.sc"
    run_script(src, cmds, dst=staged)
    (WORK / "get.json").write_text(json.dumps([{"command": "render.settings.get", "params": {"name": "hero"}}]))
    job = json.loads(cli("run", "--in", str(staged), str(WORK / "get.json"), "--results").stdout)[-1]["setup"]["job"]
    job["transparent_background"] = True
    run_script(staged, [{"command": "render.settings.set", "params": {"name": "hero", "set": {"job": job, "exposure_ev": -0.6}}}], dst=staged)
    png = WORK / f"{name}.png"
    cli("render", str(staged), "--setup", "hero", "--out", str(png), "--overwrite", "--timeout", "3000")
    return png


COMPOSE = r'''
import sys
from PIL import Image, ImageFilter
src, dst = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGBA")
bg = Image.new("RGBA", im.size, (236, 236, 233, 255))
a = im.split()[3]
sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
sh.putalpha(a.point(lambda v: int(v * 0.22)).filter(ImageFilter.GaussianBlur(18)))
bg.alpha_composite(sh, (12, 22))
bg.alpha_composite(im)
bg.convert("RGB").save(dst, quality=92)
'''


def compose(png: Path, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"cart_A_{name}.png"
    py = sys.executable
    try:
        import PIL  # noqa: F401
    except ImportError:
        py = "/usr/bin/python3"
    subprocess.run([py, "-c", COMPOSE, str(png), str(dst)], check=True)
    return dst


def main() -> None:
    quick = "--quick" in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or list(SHOTS)
    for n in names:
        print(f"rendering {n} ...", flush=True)
        print("  ->", compose(build(n, quick), n), flush=True)


if __name__ == "__main__":
    main()
