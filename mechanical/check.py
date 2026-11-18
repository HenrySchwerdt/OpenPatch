#!/usr/bin/env python3
"""Maß- und Kollisionsprüfung der erzeugten Baugruppen.

  python3 check.py                       # alle Größen in out/
  python3 check.py --outdir out_coil176
  python3 check.py --ignore-length       # Längenüberschreitung nur als WARN

Exit-Code 1, wenn Höhe > max_height, Länge/Breite > Spec-Ziel (außer --ignore-length)
oder sich interne Teile durchdringen.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from op_build import EXCLUDE_PAIRS
from op_layout import HERE, load_params

CLI = "/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli"
EPS = 1e-6
MIN_OVERLAP_MM3 = 1e-4


def eval_design(sc: Path) -> list:
    script = [{"command": "inspect.measure", "params": {}},
              {"command": "inspect.interference", "params": {"exclude_pairs": EXCLUDE_PAIRS}}]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(script, fh)
        tmp = fh.name
    res = subprocess.run([CLI, "run", tmp, "--in", str(sc), "--results", "--quiet"],
                         capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    if res.returncode != 0:
        raise SystemExit(res.stdout + res.stderr)
    return json.loads(res.stdout)


def envelope(bodies: list) -> tuple[list, list]:
    lo = [min(b["bbox"]["min"][i] for b in bodies) for i in range(3)]
    hi = [max(b["bbox"]["max"][i] for b in bodies) for i in range(3)]
    return lo, hi


def check_size(outdir: Path, variant: str, p: dict, ignore_length: bool) -> dict:
    results = eval_design(outdir / f"{variant}.sc")
    measure = next(r for r in results if "bodies" in r and "body_count" in r)
    interf = next(r for r in results if "interferences" in r)
    bodies = measure["bodies"]
    lo, hi = envelope(bodies)
    dims = [hi[i] - lo[i] for i in range(3)]
    spec = p["spec"]
    tgt_l = spec["length_targets"][variant]
    problems, warns = [], []
    if dims[2] > spec["max_height"] + EPS:
        problems.append(f"Höhe {dims[2]:.3f} > {spec['max_height']}")
    if dims[1] > spec["width_target"] + EPS:
        problems.append(f"Breite {dims[1]:.3f} > {spec['width_target']}")
    if dims[0] > tgt_l + EPS:
        (warns if ignore_length else problems).append(f"Länge {dims[0]:.2f} > Ziel {tgt_l} (+{dims[0]-tgt_l:.2f})")
    bad = [i for i in interf["interferences"] if i.get("volume_mm3", 1) > MIN_OVERLAP_MM3]
    for i in bad:
        problems.append(f"Kollision {i['a']} x {i['b']}: {i['volume_mm3']:.4f} mm3")
    unchecked = [u for u in interf.get("unchecked", [])]
    if unchecked:
        warns.append(f"{len(unchecked)} Paare nicht geprüft")
    not_closed = [b["name"] for b in bodies if not b.get("closed")]
    if not_closed:
        problems.append(f"offene Körper: {not_closed}")
    return {"variant": variant, "dims": dims, "target_l": tgt_l, "problems": problems, "warns": warns,
            "checked": interf.get("checked"), "pairs": interf.get("pairs_candidate"), "bodies": len(bodies)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", default=str(HERE / "out"))
    ap.add_argument("--sizes", nargs="*")
    ap.add_argument("--ignore-length", action="store_true")
    args = ap.parse_args()
    out = Path(args.outdir)
    p = load_params(out / "params.used.json") if (out / "params.used.json").exists() else load_params()
    sizes = args.sizes or list(p["variants"])
    failed = False
    print(f"{'Größe':8} {'L':>7} {'B':>6} {'H':>6}  {'Ziel L':>7}  Status")
    for v in sizes:
        r = check_size(out, v, p, args.ignore_length)
        d = r["dims"]
        status = "PASS" if not r["problems"] else "FAIL"
        failed |= bool(r["problems"])
        print(f"{v:8} {d[0]:7.2f} {d[1]:6.2f} {d[2]:6.2f}  {r['target_l']:7.1f}  {status}"
              f"  ({r['bodies']} Körper)")
        for m in r["problems"]:
            print(f"    FAIL: {m}")
        for m in r["warns"]:
            print(f"    WARN: {m}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
