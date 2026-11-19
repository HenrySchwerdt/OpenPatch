#!/usr/bin/env python3
"""One command that regenerates every render and the build guide from the CAD.

    python3 tools/render/regenerate.py [--force] [--jobs 3]

Steps: extra components -> base scene (rebuilt automatically when mechanical/out/bench/OP-*_real.sc changed) ->
hero/detail/section/exploded/turntable renders -> parts pages -> every guide step -> composites, manifest.json,
steps.json, booklet -> validation.  --force deletes the raw renders first (needed after a geometry change: the raw
images are cached by name, not by CAD content).
Drive-related steps flagged `pending` in guide_data.py are the ones whose geometry the next CAD revision changes
(central push rod, closed reservoir, longer pod); after the CAD lands run this once and clear the flags.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable


def run(*a):
    print("->", " ".join(a), flush=True)
    subprocess.run([PY, *a], check=True, cwd=HERE.parents[1])


def main():
    force = "--force" in sys.argv
    jobs = "3"
    if "--jobs" in sys.argv:
        jobs = sys.argv[sys.argv.index("--jobs") + 1]
    work = HERE / "work" / "raw"
    if force and work.exists():
        shutil.rmtree(work)
    run("tools/render/components.py")
    run("tools/render/render_heroes.py", "raw")
    run("tools/render/render_parts.py", "raw")
    run("tools/render/render_guide.py", "--jobs", jobs)
    run("tools/render/render_heroes.py", "compose")
    run("tools/render/render_parts.py", "compose")
    run("tools/render/compose_guide.py")
    run("tools/render/validate_guide.py")


if __name__ == "__main__":
    main()
