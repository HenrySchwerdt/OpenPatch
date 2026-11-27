#!/usr/bin/env python3
"""kpy turn_part_a.py board.kicad_pcb REF DEG [X Y] : rotate one placed part in place (about its origin) by DEG and, with X Y (pump
coordinates, cartgeom_a.py), also move it there, on a routed board; prints the uuids of the tracks / vias that touched its pads (callers
delete them with rr_route_a.remove_uuids and re-route with island_route_a.py).
Used for the last hand fixes of the routed boards (README "Routing"). TEST PROJECT, water only."""
import json
import sys

import pcbnew

import cartgeom_a as G


def main() -> None:
    pcb, ref, deg = sys.argv[1], sys.argv[2], float(sys.argv[3])
    b = pcbnew.LoadBoard(pcb)
    f = [f for f in b.GetFootprints() if f.GetReference() == ref][0]
    pads = list(f.Pads())
    uu = []
    for t in b.GetTracks():
        for p in pads:
            if p.GetNetCode() and t.GetNetCode() == p.GetNetCode() and (p.HitTest(t.GetStart()) or (t.Type() != pcbnew.PCB_VIA_T and p.HitTest(t.GetEnd()))):
                uu.append(t.m_Uuid.AsString())
                break
    f.SetOrientationDegrees((f.GetOrientationDegrees() + deg) % 360)
    if len(sys.argv) > 5:
        bx, by = G.b(float(sys.argv[4]), float(sys.argv[5]))
        f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(100.0 + bx), pcbnew.FromMM(80.0 + by)))
    pcbnew.SaveBoard(pcb, b)
    print("@@" + json.dumps(sorted(set(uu))))


if __name__ == "__main__":
    main()
