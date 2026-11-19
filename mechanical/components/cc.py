"""Shared helpers for the OpenPatch vendor-component library (mechanical/components).

A component generator builds a `Part` (wraps mechanical/op_cmds.py `Script`), assigns looks to bodies and
calls `Part.build()`. That writes <id>.script.json and runs SolidCraft to produce STEP + STL + glTF (.glb)
and a PNG iso render into out/. Local frame conventions are documented per part in README.md / catalog.json.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # reuse mechanical/op_cmds.py unmodified
from op_cmds import Script  # noqa: E402

CLI = os.environ.get("SOLIDCRAFT_CLI", "/usr/local/bin/solidcraft-cli")
OUT = HERE / "out"

# ---- palette (hex, metallic, roughness) -----------------------------------------------------------
PAL = {
    "brass": ("#c9a24a", 1.0, 0.30),
    "steel": ("#c5c8cc", 1.0, 0.28),           # stainless / zinc plated steel
    "dark_steel": ("#7d8288", 1.0, 0.40),
    "nickel": ("#b9bcc0", 1.0, 0.25),
    "tin": ("#d4d6d9", 1.0, 0.30),             # tinned terminals
    "gold": ("#d9b43c", 1.0, 0.22),            # ENIG
    "copper": ("#b87333", 1.0, 0.30),
    "black_pa": ("#1c1c1e", 0.0, 0.55),        # black PA / epoxy mould compound
    "black_ic": ("#1a1a1c", 0.0, 0.45),
    "fr4_green": ("#1f6b3a", 0.0, 0.40),
    "fr4_black": ("#16181a", 0.0, 0.40),
    "silicone": ("#d9ecef", 0.0, 0.35),        # translucent silicone (opaque stand-in in glTF/STEP)
    "ndfeb": ("#a9adb3", 0.9, 0.35),           # nickel-copper-nickel coated NdFeB
    "mag_n": ("#d23a3a", 0.0, 0.45),           # north-pole marker
    "mag_s": ("#3a6bd2", 0.0, 0.45),           # south-pole marker
    "lavender": ("#b79be0", 0.0, 0.45),        # EFD 30G hub colour code
    "ceramic": ("#d8d2c4", 0.0, 0.55),
    "cap_brown": ("#8a6d4a", 0.0, 0.5),
    "res_black": ("#232323", 0.0, 0.5),
    "kapton": ("#d8903a", 0.0, 0.5),           # polyimide / FFC film
    "white_pa": ("#ece9e1", 0.0, 0.5),         # PicoBlade housing is natural/white nylon
    "pouch": ("#c9ccd1", 0.6, 0.35),
    "wire_red": ("#c92a2a", 0.0, 0.5),
    "wire_blk": ("#222222", 0.0, 0.5),
    "wire_ylw": ("#d8c12a", 0.0, 0.5),
    "wire_wht": ("#e6e6e6", 0.0, 0.5),
    "dome": ("#cfe3ea", 0.0, 0.2),
    "grey_pc": ("#9aa0a6", 0.0, 0.5),
}

DENSITY = {  # g/cm3 for mass estimates
    "brass": 8.5, "steel": 7.9, "dark_steel": 7.8, "nickel": 8.9, "tin": 7.3, "gold": 19.3, "copper": 8.9,
    "black_pa": 1.3, "black_ic": 1.8, "fr4_green": 1.85, "fr4_black": 1.85, "silicone": 1.15, "ndfeb": 7.5,
    "mag_n": 7.5, "mag_s": 7.5, "lavender": 0.91, "ceramic": 3.5, "cap_brown": 5.0, "res_black": 3.0,
    "kapton": 1.4, "white_pa": 1.14, "pouch": 2.0, "wire_red": 1.5, "wire_blk": 1.5, "wire_ylw": 1.5, "wire_wht": 1.5,
    "dome": 1.2, "grey_pc": 1.2,
}


def run(*args: str) -> subprocess.CompletedProcess:
    r = subprocess.run([CLI, *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(f"solidcraft-cli {' '.join(args)}\n{r.stdout}\n{r.stderr}\n")
        raise SystemExit(f"solidcraft-cli failed ({r.returncode})")
    return r


class Part:
    def __init__(self, pid: str, title: str) -> None:
        self.pid = pid
        self.title = title
        self.s = Script()
        self.mat: dict[str, str] = {}        # body -> palette key
        self.opacity: dict[str, float] = {}  # body -> opacity (render only)
        self.cfg = {"snapshot_view": "iso", "camera": None, "width": 1000, "height": 1000}

    # ---- looks ---------------------------------------------------------------------------------
    def look(self, bodies, key: str, opacity: float = 1.0) -> None:
        if isinstance(bodies, str):
            bodies = [bodies]
        for b in bodies:
            self.mat[b] = key
            if opacity < 1.0:
                self.opacity[b] = opacity

    def _look_cmds(self, with_opacity: bool) -> list[dict]:
        cmds = []
        for b, key in self.mat.items():
            col, met, rough = PAL[key]
            p = {"bodies": [b], "color": col, "pbr": {"metallic": met, "roughness": rough, "dielectric_ior": 1.5}}
            if with_opacity and b in self.opacity:
                p = {"bodies": [b], "color": col, "opacity": self.opacity[b]}
            cmds.append({"command": "appearance.assign", "params": p})
        return cmds

    # ---- build ---------------------------------------------------------------------------------
    def build(self, outdir: Path = OUT, render: bool = True, force: bool = False) -> dict:
        outdir.mkdir(parents=True, exist_ok=True)
        bodies = list(self.mat)
        geo = list(self.s.cmds)
        pid = self.pid
        base = str(outdir / pid)
        exp = [
            {"command": "file.export_step", "params": {"path": f"{pid}.step", "bodies": bodies}},
            {"command": "file.export_stl", "params": {"path": f"{pid}.stl", "bodies": bodies, "quality": "standard"}},
            {"command": "file.export", "params": {"path": f"{pid}.glb", "bodies": bodies, "quality": "standard"}},
        ]
        full = geo + self._look_cmds(False) + exp
        sp = outdir / f"{pid}.script.json"
        newtxt = json.dumps(full, indent=0)
        if (not force and sp.exists() and sp.read_text() == newtxt
                and all((outdir / f"{pid}.{e}").exists() for e in ("step", "stl", "glb", "png"))):
            # identical script and all outputs present: only re-measure (from the STEP, fast)
            info = measure(outdir / f"{pid}.step", bodies)
            info["mass_g"] = round(mass_g(info["volumes_mm3"], self.mat), 4)
            info["materials"] = sorted(set(self.mat.values()))
            info["files"] = {k: f"out/{pid}.{k}" for k in ("step", "stl", "glb", "png")}
            return info
        sp.write_text(newtxt)
        run("run", str(sp), "--quiet", "--script-relative")
        # render script (with translucency) and measurements
        rs = outdir / f".{pid}.render.json"
        rs.write_text(json.dumps(geo + self._look_cmds(True)))
        info = {}
        info = measure(rs, bodies)
        if render:
            cam = self.cfg["camera"] or auto_camera(info, self.cfg.get("yaw", -0.7), self.cfg.get("pitch", 0.5),
                                                    self.cfg.get("zoom", 1.0))
            args = ["snapshot", str(rs), "--out", f"{base}.png", "--width", str(self.cfg["width"]),
                    "--height", str(self.cfg["height"]), "--no-grid", "--no-axes", "--quality", "fine",
                    "--camera", json.dumps(cam)]
            run(*args)
        info["mass_g"] = round(mass_g(info["volumes_mm3"], self.mat), 4)
        info["materials"] = sorted(set(self.mat.values()))
        rs.unlink(missing_ok=True)
        info["files"] = {k: f"out/{pid}.{k}" for k in ("step", "stl", "glb", "png")}
        return info


def measure(script_path: Path, bodies: list[str]) -> dict:
    """Overall bbox and volume per body from the CLI's measurement output."""
    r = run("eval", str(script_path))
    d = json.loads(r.stdout)
    vols = {b["name"]: b["volume_mm3"] for b in d["bodies"]}
    lo = [min(b["bbox"]["min"][i] for b in d["bodies"]) for i in range(3)]
    hi = [max(b["bbox"]["max"][i] for b in d["bodies"]) for i in range(3)]
    return {"bbox_min": [round(x, 3) for x in lo], "bbox_max": [round(x, 3) for x in hi],
            "size": [round(h - l, 3) for h, l in zip(hi, lo)], "volumes_mm3": vols,
            "bodies": [b["name"] for b in d["bodies"]]}


def auto_camera(info: dict, yaw: float, pitch: float, zoom: float) -> dict:
    lo, hi = info["bbox_min"], info["bbox_max"]
    c = [(a + b) / 2 for a, b in zip(lo, hi)]
    r = 0.5 * math.sqrt(sum((b - a) ** 2 for a, b in zip(lo, hi)))
    fov = 0.5
    return {"target": c, "yaw": yaw, "pitch": pitch, "distance": r / math.sin(fov / 2) * 1.05 / zoom, "fov": fov}


def mass_g(vol_by_body_mm3: dict[str, float], mat: dict[str, str]) -> float:
    return sum(v / 1000.0 * DENSITY[mat[b]] for b, v in vol_by_body_mm3.items() if b in mat)


# ---- geometry helpers ---------------------------------------------------------------------------
def involute_pts(rb: float, ra: float, n: int = 6) -> list[tuple[float, float]]:
    """Involute of base circle rb from rb up to ra (polar angle form), n samples."""
    pts = []
    t_max = math.sqrt(max((ra / rb) ** 2 - 1.0, 0.0))
    for i in range(n):
        t = t_max * i / (n - 1) if n > 1 else 0
        pts.append((rb * (math.cos(t) + t * math.sin(t)), rb * (math.sin(t) - t * math.cos(t))))
    return pts


def inv(a: float) -> float:
    return math.tan(a) - a
