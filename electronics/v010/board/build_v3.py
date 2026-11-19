#!/usr/bin/env python3
"""Build a v3 board with a scripted manual placement + fan-out vias (KiCad python):  build_v3.py main|power

main : ISP1807 module top-left, antenna half toward the top edge, 6 layers 0.8 mm, 0201 passives, via-in-pad on every connected inner module pad.
Environment: OP_W, OP_H override the outline (mm).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "..", "bench", "tools"))
import pcbnew
import benchlib as bl
from benchlib import Board, write_project

MM = bl.MM
T = pcbnew.ToMM
name = sys.argv[1]
V010FP = os.path.join(ROOT, "footprints", "V010.pretty")
_orig = Board.load_fp


def _load(self, lib, nm):
    if lib == "V010":
        return pcbnew.FootprintLoad(V010FP, nm)
    return _orig(self, lib, nm)


Board.load_fp = _load
# JLC 6-layer rules (3.5/3.5 mil capable); via 0.4/0.2 (via-in-pad is filled + capped)
bl.TRACK, bl.CLEAR, bl.VIA_D, bl.VIA_H = 0.12, 0.10, 0.40, 0.20

exec(open(os.path.join(HERE, "layout_%s.py" % name)).read())
