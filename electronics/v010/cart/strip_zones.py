#!/usr/bin/env python3
"""kpy strip_zones.py board.kicad_pcb : remove every copper zone (keeps rule areas), so the grid routers see only tracks / pads / vias."""
import sys
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
for z in [z for z in b.Zones() if not z.GetIsRuleArea()]:
    b.Remove(z)
pcbnew.SaveBoard(sys.argv[1], b)
print("zones removed")
