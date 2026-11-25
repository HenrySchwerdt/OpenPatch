#!/usr/bin/env python3
"""Scripted hand fixes of the routed cart board (KiCad python).  usage: kpy hand_fix.py board.kicad_pcb fixes.json [--dry]

fixes.json: list of operations in the board frame (mm, cartgeom frame: origin = board top-left on the KiCad page at (100, 80)):
  {"op": "via", "net": N, "at": [x, y]}                                   0.40 / 0.20 through via
  {"op": "track", "net": N, "layer": "In3.Cu", "pts": [[x, y], ...], "w": 0.10}
  {"op": "delete", "near": [x, y], "net": N, "layer": "F.Cu"|"via"}        removes the tracks / vias of net N touching that point
Every fix of the cart board is in cart/hand_fixes.json, so the board can be re-made from the router output."""
import json
import sys

import pcbnew

MM, T = pcbnew.FromMM, pcbnew.ToMM
OX, OY = 100.0, 80.0


def P(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def main() -> None:
    b = pcbnew.LoadBoard(sys.argv[1])
    ops = json.load(open(sys.argv[2]))
    for o in ops:
        net = b.FindNet(o["net"])
        assert net is not None, o
        if o["op"] == "via":
            v = pcbnew.PCB_VIA(b); v.SetPosition(P(*o["at"])); v.SetNet(net); v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetWidth(MM(o.get("d", 0.40))); v.SetDrill(MM(o.get("h", 0.20))); b.Add(v)
        elif o["op"] == "track":
            layer = b.GetLayerID(o["layer"])
            for a, c in zip(o["pts"], o["pts"][1:]):
                t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetLayer(layer); t.SetWidth(MM(o.get("w", 0.10))); t.SetNet(net); b.Add(t)
        elif o["op"] == "delete":
            p = P(*o["near"])
            gone = [t for t in b.GetTracks() if t.GetNetname() == o["net"] and t.HitTest(p, MM(0.02))
                    and (o.get("layer") in (None, "any") or (o["layer"] == "via") == (t.Type() == pcbnew.PCB_VIA_T)
                         and (o["layer"] == "via" or b.GetLayerName(t.GetLayer()) == o["layer"]))]
            for t in gone:
                b.Remove(t)
            print("deleted", len(gone), o)
    if "--dry" not in sys.argv:
        pcbnew.SaveBoard(sys.argv[1], b)
    print("applied", len(ops))


if __name__ == "__main__":
    main()
