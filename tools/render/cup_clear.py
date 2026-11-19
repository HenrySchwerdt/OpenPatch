import importlib.util, json, os, sys
from pathlib import Path
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cr", here / "cup_render_lib.py"); cr = importlib.util.module_from_spec(spec); spec.loader.exec_module(cr)
rp = cr.rp
def build(name, cam, w, h, show_fn, quick=False):
    rp.WORK.mkdir(parents=True, exist_ok=True)
    src = rp.WORK / "OP-100.sc"
    import shutil; shutil.copy(rp.OUT / "OP-100.sc", src)
    if quick: w, h = w // 3, h // 3
    names = [b["name"] for b in json.loads(rp.cli("eval", str(src)).stdout)["bodies"]]
    cmds = [{"command": "appearance.assign", "params": {"bodies": ["bottom", "top"], **rp.SHELL}}]
    for b in names:
        if b in ("bottom", "top") or b in rp.HIDDEN: continue
        cmds.append({"command": "appearance.assign", "params": {"bodies": [b], **rp.LOOKS.get(b, rp.METAL)}})
    hide = {b for b in names if not show_fn(b)} | set(rp.HIDDEN)
    for b in sorted(hide & set(names)):
        cmds.append({"command": "browser.visibility", "params": {"visible": False, "items": [b]}})
    cmds.append({"command": "render.settings.set", "params": {"name": "hero", "set": {"backend": "builtin", "mode": "final", "width": w, "height": h,
        "camera": {**cam, "roll": 0, "up": "z"}, "job": {"method": "cpu_raytrace"}}}})
    out = rp.run_script(src, cmds + [{"command": "render.preset.resolve", "params": {"id": "NATIVE-STUDIO-002", "name": "hero"}}], results=True).stdout
    rev = json.loads(out)[-1]["revision"]
    cmds += [{"command": "render.preset.apply", "params": {"id": "NATIVE-STUDIO-002", "name": "hero", "expected_revision": rev, "replace_lighting_and_environment": True, "replace_stage": True}},
             {"command": "render.stage.clear", "params": {"name": "hero"}}]
    staged = rp.WORK / f"{name}.sc"; rp.run_script(src, cmds, dst=staged)
    got = rp.cli("run", "--in", str(staged), str(rp._write(rp.WORK / "get.json", [{"command": "render.settings.get", "params": {"name": "hero"}}])), "--results").stdout
    job = json.loads(got)[-1]["setup"]["job"]; job["transparent_background"] = True
    rp.run_script(staged, [{"command": "render.settings.set", "params": {"name": "hero", "set": {"job": job, "exposure_ev": -0.7}}}], dst=staged)
    png = rp.WORK / f"{name}.png"
    rp.cli("render", str(staged), "--setup", "hero", "--out", str(png), "--overwrite", "--timeout", "3000")
    return png
quick = "--quick" in sys.argv
cams = {"iso": dict(target=[24, 17, 4], yaw=-0.62, pitch=0.5, distance=200, fov=0.22),
        "top": dict(target=[24, 17.3, 4], yaw=0, pitch=1.5707, distance=650, fov=0.075)}
from PIL import Image
for view, cam in cams.items():
    W, H = (2400, 1500) if view == "iso" else (2000, 1500)
    o = build(f"{view}_open", cam, W, H, lambda b: b != "top", quick)
    l = build(f"{view}_lid", cam, W, H, lambda b: b == "top", quick)
    A = Image.open(o).convert("RGBA"); L = Image.open(l).convert("RGBA")
    r, g, b_, a = L.split(); a = a.point(lambda v: int(v * 0.28))
    L = Image.merge("RGBA", (r, g, b_, a))
    bg = Image.new("RGBA", A.size, (238, 238, 236, 255)); bg.alpha_composite(A); bg.alpha_composite(L)
    out = here / f"OP-100_clear_{view}.png"; bg.convert("RGB").save(out); print(out)
