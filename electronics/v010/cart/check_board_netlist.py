#!/usr/bin/env python3
"""kpy check_board_netlist.py board.kicad_pcb : every pad net of the board equals netlist_cart.json (and the reverse). Exit 1 on a mismatch."""
import json
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
nl = {p["ref"]: {k: v for k, v in p["pins"].items() if v} for p in json.load(open(os.path.join(HERE, "netlist_cart.json")))}
b = pcbnew.LoadBoard(sys.argv[1])
bad = []
seen = set()
for f in b.GetFootprints():
    ref = f.GetReference()
    if ref not in nl:
        if any(p.GetNumber() for p in f.Pads()):
            bad.append("board part %s not in the netlist" % ref)
        continue
    seen.add(ref)
    for p in f.Pads():
        num, net = p.GetNumber(), p.GetNetname()
        if not num:
            continue
        want = nl[ref].get(num, "")
        if net != want:
            bad.append("%s.%s board %r netlist %r" % (ref, num, net, want))
bad += ["netlist part %s missing on the board" % r for r in nl if r not in seen]
print("\n".join(bad) if bad else "board == netlist_cart.json (%d parts)" % len(seen))
sys.exit(1 if bad else 0)
