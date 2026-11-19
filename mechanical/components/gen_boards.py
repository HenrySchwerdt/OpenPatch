"""Export both bench boards to STEP (with component 3D models) via kicad-cli and report which footprints lack a 3D model.

Needs KiCad 10 and its stock 3D libraries (apt: kicad-packages3d, or the KiCad.app bundle on the Mac).
Outputs: out/boards/<name>.step (+ .stl/.glb/.png via SolidCraft import) and out/boards/<name>.models.json
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from cc import HERE, OUT, run

ROOT = HERE.parent.parent
BOARDS = {   # name -> (pcb, extra kicad-cli flags)
    "bench_pod_board": (ROOT / "electronics/bench/pod/pod.kicad_pcb", ["--include-silkscreen"]),
    # controller: no silkscreen (600+ extra faces, +8 MB STEP)
    "bench_controller_board": (ROOT / "electronics/bench/controller/controller.kicad_pcb", []),
}
KICAD_CLI = os.environ.get("KICAD_CLI", "kicad-cli")
MODEL_DIR = os.environ.get("KICAD10_3DMODEL_DIR", "/usr/share/kicad/3dmodels")


def footprint_models(pcb: Path) -> list[dict]:
    """Top-level (footprint ...) blocks -> {ref, fp, models:[path,...], exists:[bool]}."""
    txt = pcb.read_text()
    out = []
    for m in re.finditer(r'^\t\(footprint "([^"]+)"', txt, re.M):
        start = m.start()
        nxt = re.search(r'^\t\(footprint "', txt[m.end():], re.M)
        blk = txt[start: m.end() + nxt.start()] if nxt else txt[start:]
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk)
        models = re.findall(r'\(model "([^"]+)"', blk)
        ex = []
        for mp in models:
            q = mp.replace("${KICAD10_3DMODEL_DIR}", MODEL_DIR).replace("${KIPRJMOD}", str(pcb.parent))
            ex.append(Path(q).exists())
        out.append({"ref": ref.group(1) if ref else "?", "fp": m.group(1).split(":")[-1], "models": models, "exists": ex})
    return out


def main() -> None:
    d = OUT / "boards"
    d.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, KICAD10_3DMODEL_DIR=MODEL_DIR)
    report = {}
    for name, (pcb, extra) in BOARDS.items():
        step = d / f"{name}.step"
        cmd = [KICAD_CLI, "pcb", "export", "step", "--force", "--subst-models", "--include-tracks", "--include-pads",
               "--include-soldermask", *extra, "-o", str(step), str(pcb)]
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        missing_msgs = [l for l in (r.stdout + r.stderr).splitlines() if "File not found" in l or "Could not" in l]
        fps = footprint_models(pcb)
        no_model = sorted({f["fp"] for f in fps if not f["models"]})
        not_found = sorted({f["fp"] for f in fps if f["models"] and not all(f["exists"])})
        report[name] = {
            "pcb": str(pcb.relative_to(ROOT)), "footprints": len(fps),
            "with_model": sum(1 for f in fps if f["models"] and all(f["exists"])),
            "footprints_without_3d_model": no_model, "footprints_model_file_not_found": not_found,
            "kicad_warnings": missing_msgs,
        }
        # convert for the website / assemblies: soldermask faces come in translucent, glTF needs opaque bodies
        ev = json.loads(run("eval", str(step)).stdout)
        mask = [b["name"] for b in ev["bodies"] if "soldermask" in b["name"]]
        silk = [b["name"] for b in ev["bodies"] if "silkscreen" in b["name"]]
        cmds = [{"command": "appearance.assign", "params": {"bodies": mask, "color": "#1f6b3a"}}] if mask else []
        cmds += [{"command": "appearance.assign", "params": {"bodies": silk, "color": "#f2f2f2"}}] if silk else []
        cmds += [{"command": "file.export", "params": {"path": str(d / f"{name}.glb")}},
                 ]
        if name != "bench_controller_board":      # controller STL would be ~180 MB: glb/step only
            cmds.append({"command": "file.export", "params": {"path": str(d / f"{name}.stl"), "quality": "standard"}})
        sp = d / f".{name}.post.json"
        sp.write_text(json.dumps(cmds))
        run("run", str(sp), "--in", str(step), "--quiet")
        run("snapshot", str(sp), "--in", str(step), "--out", str(d / f"{name}.png"), "--view", "iso", "--width", "1400",
            "--height", "1000", "--no-grid", "--no-axes", "--quality", "fine")
        sp.unlink()
    (d / "boards.models.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    sys.exit(main())
