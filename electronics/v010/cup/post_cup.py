#!/usr/bin/env python3
"""Post-route clean-up of cup.kicad_pcb (KiCad python): remove routed/fan-out copper that lies inside the screw keep-out rings, refill zones, save.
usage: python3 post_cup.py   (run after flow_cup.sh)"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bench", "tools"))
sys.path.insert(0, HERE)
import pcbnew
import benchlib as bl
import cupgeom as G

T = pcbnew.ToMM
PCB = os.path.join(HERE, "cup.kicad_pcb")
b = pcbnew.LoadBoard(PCB)
rings = [(bl.OX + G.b(*s)[0], bl.OY + G.b(*s)[1]) for s in G.SCREWS]
rm = []
for t in list(b.GetTracks()):
    pts = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
    if any(math.hypot(T(p.x) - cx, T(p.y) - cy) < G.SCREW_KEEPOUT_D / 2 + 0.05 for p in pts for cx, cy in rings):
        rm.append(t)
for t in rm:
    b.Remove(t)
print("removed items inside the screw keep-out rings:", len(rm))
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(PCB, b)
