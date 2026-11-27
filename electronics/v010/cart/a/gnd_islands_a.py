#!/usr/bin/env python3
"""kpy gnd_islands_a.py board.kicad_pcb : GND connectivity clusters (zone-fill islands, pads, vias, tracks) -> prints every cluster except
the largest with its members (pump coordinates), to find what a DRC "zone to zone" unconnected item means. TEST PROJECT, water only."""
import sys

import pcbnew

T = pcbnew.ToMM


def P(v):
    return (round(T(v.x) - 100 + 32.6, 2), round(41 - (T(v.y) - 80), 2))


def main() -> None:
    b = pcbnew.LoadBoard(sys.argv[1])
    net = b.FindNet("GND").GetNetCode()
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, c):
        parent[find(a)] = find(c)
    islands = []          # (key, layer, SHAPE_LINE_CHAIN outline poly set)
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetCode() != net:
            continue
        for lay in z.GetLayerSet().Seq():
            ps = z.GetFilledPolysList(lay)
            for k in range(ps.OutlineCount()):
                one = pcbnew.SHAPE_POLY_SET()
                one.AddOutline(ps.Outline(k))
                for h in range(ps.HoleCount(k)):
                    one.AddHole(ps.Hole(k, h))
                islands.append((("Z", z.GetZoneName(), k), lay, one))
    items = []
    for t in b.GetTracks():
        if t.GetNetCode() != net:
            continue
        key = ("V" if t.Type() == pcbnew.PCB_VIA_T else "T", P(t.GetPosition() if t.Type() == pcbnew.PCB_VIA_T else t.GetStart()), id(t))
        items.append((key, t))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() == net:
                items.append((("P", f.GetReference() + "." + p.GetNumber(), id(p)), p))
    for key, it in items:
        find(key)
        for ikey, lay, poly in islands:
            if not it.IsOnLayer(lay):
                continue
            pts = [it.GetPosition()] if it.Type() != pcbnew.PCB_TRACE_T else [it.GetStart(), it.GetEnd()]
            if any(poly.Contains(q) for q in pts):
                union(key, ikey)
    # tracks join the pads / vias at their ends
    for key, it in items:
        if it.Type() != pcbnew.PCB_TRACE_T:
            continue
        for k2, other in items:
            if other is it or not other.IsOnLayer(it.GetLayer()):
                continue
            if other.HitTest(it.GetStart(), 1000) or other.HitTest(it.GetEnd(), 1000):
                union(key, k2)
    for ikey, lay, poly in islands:
        find(ikey)
    groups = {}
    for k in list(parent):
        groups.setdefault(find(k), []).append(k)
    gs = sorted(groups.values(), key=len, reverse=True)
    print("GND clusters:", [len(g) for g in gs])
    for g in gs[1:]:
        print(" cluster:", [k[1] if k[0] in ("P", "V", "T") else (k[1], k[2]) for k in g][:30])


if __name__ == "__main__":
    main()
