#!/usr/bin/env python3
"""kpy dedup_vias.py board.kicad_pcb : removes the second of two same-net vias closer than 0.45 mm (router leftovers; JLC hole-to-hole), keeps the one
with more track ends, re-points the other one's track ends to it, refills the zones."""
import sys, pcbnew, math
T=pcbnew.ToMM
b=pcbnew.LoadBoard(sys.argv[1])
vias=[t for t in b.GetTracks() if t.Type()==pcbnew.PCB_VIA_T]
gone=set()
for i,a in enumerate(vias):
    for c in vias[i+1:]:
        if a.GetNetCode()!=c.GetNetCode() or id(a) in gone or id(c) in gone: continue
        d=math.hypot(T(a.GetPosition().x-c.GetPosition().x),T(a.GetPosition().y-c.GetPosition().y))
        if d < 0.45:
            # keep the via on which more track ends land
            def ends(v):
                p=v.GetPosition(); return sum(1 for t in b.GetTracks() if t.Type()!=pcbnew.PCB_VIA_T and t.GetNetCode()==v.GetNetCode() and (t.GetStart()==p or t.GetEnd()==p))
            drop = a if ends(a) < ends(c) else c
            keep = c if drop is a else a
            # re-point the dropped via's track ends to the kept via
            for t in list(b.GetTracks()):
                if t.Type()!=pcbnew.PCB_VIA_T and t.GetNetCode()==drop.GetNetCode():
                    if t.GetStart()==drop.GetPosition(): t.SetStart(keep.GetPosition())
                    if t.GetEnd()==drop.GetPosition(): t.SetEnd(keep.GetPosition())
            print('drop via',drop.GetNetname(),round(T(drop.GetPosition().x)-100,3),round(T(drop.GetPosition().y)-80,3))
            gone.add(id(drop)); b.Remove(drop)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[1], b)
