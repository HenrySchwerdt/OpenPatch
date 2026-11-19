#!/usr/bin/env python3
"""Consistency checks of the build guide: every BOM part (with a physical part) appears in at least one step, every
step part/tool exists in the BOM/tool list, every image exists, size limits hold.  Exit code 1 on a problem."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guide_data as gd  # noqa: E402

ROOT = HERE.parents[1]
GUIDE = ROOT / "docs" / "build-guide"
REN = ROOT / "docs" / "renders"


def main():
    bad = []
    used = {p for s in gd.STEPS for p, _ in s.get("parts", [])}
    for pid in gd.BOM:
        if pid not in used:
            bad.append(f"BOM part {pid} ({gd.BOM[pid][0]}) is not used in any step")
    for s in gd.STEPS:
        for p, q in s.get("parts", []):
            if p not in gd.BOM:
                bad.append(f"step {s['id']}: part {p} not in BOM")
        for t in s.get("tools", []):
            if t not in gd.TOOLS:
                bad.append(f"step {s['id']}: tool {t} unknown")
        if len(s["lines"]) > 3:
            bad.append(f"step {s['id']}: more than 3 text lines")
    ids = [s["id"] for s in gd.STEPS]
    if len(ids) != len(set(ids)):
        bad.append("duplicate step ids")
    sj = GUIDE / "steps.json"
    if sj.exists():
        d = json.loads(sj.read_text())
        for s in d["steps"]:
            if not (GUIDE / s["image"]).exists():
                bad.append(f"missing image {s['image']}")
        missing = set(ids) - {s["id"] for s in d["steps"]}
        if missing:
            bad.append(f"steps without image: {sorted(missing)}")
    mf = REN / "manifest.json"
    total = 0
    for base in (GUIDE / "steps", REN):
        for f in base.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
                if f.suffix in (".webp", ".jpg", ".png") and f.stat().st_size > 400_000:
                    bad.append(f"{f} larger than 400 kB")
    if mf.exists():
        for m in json.loads(mf.read_text())["images"]:
            if m["kind"] != "step" and not (ROOT / "docs" / m["file"]).exists():
                bad.append(f"manifest file missing: {m['file']}")
    print(f"steps: {len(ids)}, BOM entries: {len(gd.BOM)}, image bytes: {total / 1e6:.1f} MB")
    for b in bad:
        print("PROBLEM:", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
