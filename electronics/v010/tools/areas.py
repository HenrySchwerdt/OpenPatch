#!/usr/bin/env python3
"""Courtyard area per side and group (KiCad python)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bench", "tools"))
import pcbnew
import benchlib as bl

b = pcbnew.LoadBoard(os.path.join(HERE, "..", "board", "v010.kicad_pcb"))
parts = json.load(open(os.path.join(HERE, "..", "board", "parts.json")))
tot = {"F": 0, "B": 0}
byg = {}
for f in b.GetFootprints():
    bx = bl._box(f)
    a = (bx[2] - bx[0]) * (bx[3] - bx[1])
    s = "B" if f.GetSide() == pcbnew.B_Cu else "F"
    tot[s] += a
    g = parts[f.GetReference()]["group"]
    byg[(s, g)] = byg.get((s, g), 0) + a
print({k: round(v) for k, v in tot.items()}, "board", 38.7 * 29)
for k, v in sorted(byg.items(), key=lambda kv: -kv[1])[:16]:
    print(k, round(v))
