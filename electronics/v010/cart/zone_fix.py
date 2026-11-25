#!/usr/bin/env python3
"""kpy zone_fix.py board.kicad_pcb REF:PAD [REF:PAD ...] : full (not thermal) zone connection on these pads, then refill every zone.
Used where KiCad reports starved thermal spokes (cart board: C70 pad 2 next to the HJ-840)."""
import sys
import pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
want = {tuple(a.split(":")) for a in sys.argv[2:]}
for f in b.GetFootprints():
    for p in f.Pads():
        if (f.GetReference(), p.GetNumber()) in want:
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[1], b)
print("zone connection FULL:", sorted(want))
