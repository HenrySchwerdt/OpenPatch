#!/usr/bin/env python3
"""kpy prep_signal_a.py board.kicad_pcb : the "prep" step of ../../board/route_v3.py WITHOUT the In1 GND plane, for the 4-layer lever
"both inner layers signal": In1 stays a signal layer in the DSN and Freerouting routes GND like any other net (no plane to drop vias
into). route_v3.py import / finish are used unchanged afterwards (finish pours GND on every copper layer, so In1 still carries GND copper
wherever no track runs). Kept here instead of an option in the shared route_v3.py so the B and cup flows stay byte-identical.
TEST PROJECT, water only."""
import os
import re
import sys

import pcbnew


def main() -> None:
    pcb = sys.argv[1]
    dsn = os.path.splitext(pcb)[0] + ".dsn"
    b = pcbnew.LoadBoard(pcb)
    left = [z for z in b.Zones() if not z.GetIsRuleArea()]
    if left:        # KiCad 10 python breaks after a BOARD.Remove(): the flow runs ../strip_zones.py first
        raise SystemExit("copper zones left on the board: run ../strip_zones.py first (%d)" % len(left))
    pcbnew.ExportSpecctraDSN(b, dsn)
    t = open(dsn).read()
    if os.environ.get("OP_PROTECT_WIRES", "1") == "1":
        t = t.replace("(type route))", "(type protect))")
    else:
        t = re.sub(r"(\(via [^\n]*)\(type route\)\)", r"\1(type protect))", t)
    t = t.replace("(clearance 100)", "(clearance %d)" % int(float(os.environ.get("OP_CLR", "0.10")) * 1000))
    open(dsn, "w").write(t)
    print("DSN", dsn, "planes [] (In1 signal)")


if __name__ == "__main__":
    main()
