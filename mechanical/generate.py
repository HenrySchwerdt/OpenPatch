#!/usr/bin/env python3
"""OpenPatch Mechanik-Generator.

  python3 generate.py                      # alle drei Größen -> out/
  python3 generate.py --sizes OP-70        # nur eine Größe
  python3 generate.py --coil-d 17.6 --outdir out_coil176
  python3 generate.py --set battery.y=16 --set reservoir.fill_fraction=0.5
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

from op_build import build_model
from op_layout import HERE, load_params, merge

CLI = os.environ.get("SOLIDCRAFT_CLI", "/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli")


def run_cli(*args: str) -> subprocess.CompletedProcess:
    res = subprocess.run([CLI, *args], capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stdout[-2000:] + res.stderr[-3000:])
        raise SystemExit(f"solidcraft-cli {' '.join(args[:2])} fehlgeschlagen")
    return res


def apply_overrides(p: dict, sets: list[str], coil_d: float | None) -> dict:
    over: dict = {}
    for item in sets:
        key, val = item.split("=", 1)
        node = over
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = json.loads(val)
    if coil_d is not None:
        over.setdefault("coil", {})["d"] = coil_d
    return merge(p, over)


def generate_size(p: dict, variant: str, outdir: Path, snapshots: bool) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    s, L = build_model(p, variant)
    tag = variant
    s.export_step(str(outdir / f"{tag}_assembly.step"))
    s.export_stl(str(outdir / f"{tag}_bottom.stl"), ["bottom"])
    s.export_stl(str(outdir / f"{tag}_top.stl"), ["top"])
    script = outdir / f"{tag}.script.json"
    script.write_text(json.dumps(s.dumps(), indent=1), encoding="utf-8")
    sc = outdir / f"{tag}.sc"
    run_cli("run", str(script), "--save", str(sc), "--quiet")
    (outdir / f"{tag}.layout.json").write_text(json.dumps(L, indent=1), encoding="utf-8")
    if snapshots:
        shots(sc, outdir, tag, L)
    return L


def shots(sc: Path, outdir: Path, tag: str, L: dict) -> None:
    shade = ["--body", "top:opacity=0.18,color=#9fb3c8", "--body", "bottom:opacity=0.55,color=#c9d3dd",
             "--body", "reservoir:opacity=0.5,color=#7fd0e0", "--body", "plunger:color=#e0803a",
             "--body", "pcb:color=#2e8b57", "--body", "battery:color=#3a5fcd",
             "--body", "qi_coil:color=#b87333", "--body", "pcb_keepout:opacity=0.15,color=#2e8b57"]
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_iso.png"), "--view", "iso",
            "--width", "1400", "--height", "900", *shade)
    for nm, y in (("section_y7", L["y_p"]), ("section_y22", L["y_s"])):
        cam = {"target": [L["length"] / 2, y, L["height"] / 2], "yaw": 3.14159, "pitch": 0.0,
               "distance": 0.85 * L["length"]}
        run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_{nm}.png"), "--camera", json.dumps(cam),
                "--section", f"y={y:.2f}", "--width", "1600", "--height", "600", "--no-grid", "--no-axes", *shade)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", nargs="*", help="z.B. OP-70 OP-100 OP-200 (Standard: alle)")
    ap.add_argument("--outdir", default=str(HERE / "out"))
    ap.add_argument("--params", help="alternative params.json")
    ap.add_argument("--coil-d", type=float, help="Qi-Spulendurchmesser überschreiben (Spec: 20.0)")
    ap.add_argument("--set", action="append", default=[], metavar="gruppe.schluessel=wert")
    ap.add_argument("--no-snapshots", action="store_true")
    args = ap.parse_args()

    p = apply_overrides(load_params(Path(args.params) if args.params else None), args.set, args.coil_d)
    sizes = args.sizes or list(p["variants"])
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "params.used.json").write_text(json.dumps(p, indent=1), encoding="utf-8")
    for v in sizes:
        L = generate_size(copy.deepcopy(p), v, out, not args.no_snapshots)
        print(f"{v}: L={L['length']:.2f} B={L['width']:.1f}  -> {out}")


if __name__ == "__main__":
    main()
