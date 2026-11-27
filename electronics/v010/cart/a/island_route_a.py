#!/usr/bin/env python3
"""Island-to-island maze routing for the open connections of the cart A board (KiCad python; TEST PROJECT, water only).

finish_route_a.py routes only the pair of items KiCad's DRC names for an open connection; when that pad is walled in the route fails
although the rest of its island may be reachable. Here every open (non-GND) connection is routed from ANY copper of the first island
(all items connected to the first item: pads, tracks, vias) to ANY copper of the second island, with the same A*, grid, rules and layers
as finish_route_a.py (OP_LAYERS, OP_IN1). Opens are taken in order of distance; each success updates the grid.

usage: kpy island_route_a.py board.kicad_pcb drc.json   (writes the board in place; OP_FIRST=NET1,NET2 routes those nets first)"""
import json
import math
import os
import sys

import pcbnew

import finish_route_a as FR

T = pcbnew.ToMM


def island(b, item):
    con = b.GetConnectivity()
    out = list(con.GetConnectedItems(item))
    return [item] + [i for i in out if i is not item]


def main() -> None:
    pcb, drc = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(pcb)
    b.BuildConnectivity()
    d = json.load(open(drc))
    R = FR.Router(b)
    jobs = []
    for u in d["unconnected_items"]:
        if len(u["items"]) != 2 or "[GND]" in u["items"][0]["description"]:
            continue
        a, na = FR.find_item(b, u["items"][0]["description"], u["items"][0]["pos"])
        c, _ = FR.find_item(b, u["items"][1]["description"], u["items"][1]["pos"])
        if a is None or c is None:
            continue
        dist = math.hypot(u["items"][0]["pos"]["x"] - u["items"][1]["pos"]["x"], u["items"][0]["pos"]["y"] - u["items"][1]["pos"]["y"])
        jobs.append((dist, na, a, c))
    first = [n for n in os.environ.get("OP_FIRST", "").split(",") if n]    # nets to route before the rest (hand fixes: the net a rip was made for)
    jobs.sort(key=lambda j: (j[1] not in first, j[0]))
    ok, fail = 0, []
    for dist, net, a, c in jobs:
        b.BuildConnectivity()
        ia, ic = island(b, a), island(b, c)
        if set(id(x) for x in ia) & set(id(x) for x in ic):
            continue                                      # joined by an earlier route
        code = a.GetNetCode()
        starts = [q for it in ia for q in R.cells_of(it)]
        goals = [q for it in ic for q in R.cells_of(it)]
        path, w = R.route(code, starts, goals)
        if path is None:
            path, w = R.route(code, goals, starts)
        if path is None:
            fail.append((net, round(dist, 1)))
            print("FAIL", net, round(dist, 1), flush=True)
            continue
        if not R.commit(code, path, w):
            # an empty path (the islands share a grid cell on different layers without a via): nothing was added
            fail.append((net, round(dist, 1)))
            print("FAIL", net, round(dist, 1), "(empty path)", flush=True)
            continue
        ok += 1
        print("ok  ", net, round(dist, 1), flush=True)
    pcbnew.SaveBoard(pcb, b)
    print("routed", ok, "failed", len(fail), fail)


if __name__ == "__main__":
    main()
