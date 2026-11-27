#!/usr/bin/env python3
"""kpy gnd_stub_a.py board.kicad_pcb REF:PAD [REF:PAD ...] : give each listed pad its own short track to a new via of the pad's net (maze
search for the nearest via site that clears every layer: finish_route_a.Router, to_via mode), then refill the zones. Used where a GND
pad's pour island is walled in by other nets (gnd_islands_a.py), and to open an escape for a walled-in signal pad before
island_route_a.py. TEST PROJECT, water only."""
import sys

import pcbnew

import finish_route_a as FR


def main() -> None:
    pcb = sys.argv[1]
    b = pcbnew.LoadBoard(pcb)
    R = FR.Router(b)
    want = [a.split(":") for a in sys.argv[2:]]
    for ref, num in want:
        f = [f for f in b.GetFootprints() if f.GetReference() == ref][0]
        p = [q for q in f.Pads() if q.GetNumber() == num][0]
        net = p.GetNetCode()
        path, w = R.route(net, R.cells_of(p), None, to_via=True)
        if path is None:
            print("no via site for", ref, num)
            continue
        R.commit(net, path, w, end_via=True)
        print("stub + via for", ref, num, p.GetNetname(), "items", len(R.last_items))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb, b)


if __name__ == "__main__":
    main()
