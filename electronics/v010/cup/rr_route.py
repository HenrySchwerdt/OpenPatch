#!/usr/bin/env python3
"""Rip-up and re-route clean-up for the cup board (KiCad python).

Input: a routed board (nego_route.py + finish_route.py) and the placed, unrouted board it came from (its copper = the fixed
fan-out: module vias in pad, wire/USB pad vias, A7-A8 bridge, A1 stub). Every round:
  1. KiCad DRC; routed items in a clearance / hole-clearance / short / rule-area error are deleted,
  2. every open non-GND connection is routed against all copper; if that fails, it is searched again with routed foreign
     copper passable at a price, the routed items it runs through are ripped up, and it is routed for real,
  3. ripped nets come back as open connections in the next round.
usage: kpy rr_route.py routed.kicad_pcb placed.kicad_pcb [rounds]   (writes routed.kicad_pcb in place)
"""
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np

import pcbnew
import finish_route as FR

T, MM = pcbnew.ToMM, pcbnew.FromMM
SOFT_COST = 40.0


def sig(t):
    if t.Type() == pcbnew.PCB_VIA_T:
        return ("v", round(T(t.GetPosition().x), 3), round(T(t.GetPosition().y), 3))
    return ("t", t.GetLayer(), round(T(t.GetStart().x), 3), round(T(t.GetStart().y), 3), round(T(t.GetEnd().x), 3), round(T(t.GetEnd().y), 3))


def drc(pcb):
    out = tempfile.mktemp(suffix=".json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "-o", out, pcb], capture_output=True)
    d = json.load(open(out))
    os.remove(out)
    return d


def item_at(b, desc, pos, routed):
    a, _ = FR.find_item(b, desc, pos)
    return a


def soft_route(R, net, starts, goals, soft_mask):
    """A* where cells blocked only by routed foreign copper are passable at SOFT_COST; returns path or None"""
    import heapq
    w = FR.width_of(R.b.GetNetInfo().GetNetItem(net).GetNetname())
    own = R.own[w]
    hard = (own == 0) | (own == net)
    pas = hard | soft_mask[w]
    goals = [q for q in goals if pas[q]]
    if not goals:
        return None
    goalset = set(goals)
    gx = np.array([g[1] for g in goals]); gy = np.array([g[2] for g in goals])
    tx, ty = gx.mean(), gy.mean()
    trad = float(np.hypot(gx - tx, gy - ty).max())
    rv = int(math.ceil((FR.VIA_D / 2 + FR.CLR - (FR.CLR + w / 2 + 0.01)) / FR.G)) + 1
    from scipy import ndimage
    via_ok = ~R.viablock.copy()
    for li in range(len(FR.LAYERS)):
        via_ok &= ndimage.binary_erosion(pas[li], structure=FR.disk(rv), border_value=0)
    best, came, pq = {}, {}, []
    for s in starts:
        if pas[s]:
            best[s] = 0.0
            heapq.heappush(pq, (0.0, 0.0, s))
    dirs = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]
    n = 0
    while pq:
        f, gc, s = heapq.heappop(pq)
        if gc > best.get(s, 1e18) + 1e-9:
            continue
        if s in goalset:
            path = [s]
            while path[-1] in came:
                path.append(came[path[-1]])
            return path[::-1]
        n += 1
        if n > 1_500_000:
            return None
        l, i, j = s
        for di, dj, c in dirs:
            ni, nj = i + di, j + dj
            if not (0 <= ni < R.g.nx and 0 <= nj < R.g.ny) or not pas[l, ni, nj]:
                continue
            t = (l, ni, nj)
            ng = gc + c * (1.0 if hard[l, ni, nj] else SOFT_COST)
            if ng < best.get(t, 1e18):
                best[t] = ng; came[t] = s
                heapq.heappush(pq, (ng + max(math.hypot(ni - tx, nj - ty) - trad, 0.0), ng, t))
        if via_ok[i, j]:
            for l2 in range(len(FR.LAYERS)):
                if l2 != l:
                    t = (l2, i, j)
                    ng = gc + FR.VIA_COST + (0 if all(hard[q, i, j] for q in range(len(FR.LAYERS))) else 4 * SOFT_COST)
                    if ng < best.get(t, 1e18):
                        best[t] = ng; came[t] = s
                        heapq.heappush(pq, (ng + max(math.hypot(i - tx, j - ty) - trad, 0.0), ng, t))
    return None


def main():
    pcb, placed = sys.argv[1], sys.argv[2]
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    fixed = {sig(t) for t in pcbnew.LoadBoard(placed).GetTracks()}
    for rd in range(rounds):
        b = pcbnew.LoadBoard(pcb)
        routed = [t for t in b.GetTracks() if sig(t) not in fixed]
        d = drc(pcb)
        errs = [v for v in d["violations"] if v["severity"] == "error" and v["type"] in ("clearance", "hole_clearance", "shorting_items", "items_not_allowed", "tracks_crossing", "copper_edge_clearance")]
        rip = {}
        for v in errs:
            for it in v["items"]:
                a = item_at(b, it["description"], it["pos"], routed)
                if a is not None and a.Type() in (pcbnew.PCB_TRACE_T, pcbnew.PCB_VIA_T) and sig(a) not in fixed:
                    rip[a.m_Uuid.AsString()] = a
        for a in rip.values():
            b.Remove(a)
        pcbnew.SaveBoard(pcb, b)
        b = pcbnew.LoadBoard(pcb)          # KiCad 10 python: the track container is unusable after Remove(); reload
        opens = [u for u in d["unconnected_items"] if len(u["items"]) == 2 and "[GND]" not in u["items"][0]["description"]]
        print("round %d: %d DRC errors (ripped %d items), %d open non-GND connections" % (rd, len(errs), len(rip), len(opens)), flush=True)
        if not errs and not opens:
            break
        R = FR.Router(b)
        # cells covered by routed foreign copper only (soft) = blocked now but free on the fixed-only grid
        bf = pcbnew.LoadBoard(placed)
        Rf = FR.Router(bf)
        jobs = []
        for u in opens:
            a, na = FR.find_item(b, u["items"][0]["description"], u["items"][0]["pos"])
            c, nc = FR.find_item(b, u["items"][1]["description"], u["items"][1]["pos"])
            if a is None or c is None:
                continue
            dist = math.hypot(u["items"][0]["pos"]["x"] - u["items"][1]["pos"]["x"], u["items"][0]["pos"]["y"] - u["items"][1]["pos"]["y"])
            jobs.append((dist, na, u["items"][0], u["items"][1]))
        jobs.sort(key=lambda j: j[0])
        done = 0
        for dist, net, ua, uc in jobs:
            a, _ = FR.find_item(b, ua["description"], ua["pos"])
            c, _ = FR.find_item(b, uc["description"], uc["pos"])
            if a is None or c is None:
                continue
            code = a.GetNetCode()
            st, go = R.cells_of(a), R.cells_of(c)
            path, w = R.route(code, st, go)
            if path is None:
                soft = {wk: ((Rf.own[wk] == 0) | (Rf.own[wk] == code)) & ~((R.own[wk] == 0) | (R.own[wk] == code)) for wk in R.own}
                sp = soft_route(R, code, st, go, soft)
                if sp is None:
                    print("   no path even with rip-up:", net, round(dist, 1), flush=True)
                    continue
                # rip routed items of other nets near the soft path
                cells = [(FR.LAYERS[l], *R.g.xy(i, j)) for (l, i, j) in sp]
                victims = {}
                for t in list(b.GetTracks()):
                    if sig(t) in fixed or t.GetNetCode() == code:
                        continue
                    for lay, x, y in cells[::2]:
                        if t.Type() == pcbnew.PCB_VIA_T or t.GetLayer() == lay:
                            p = t.GetPosition() if t.Type() == pcbnew.PCB_VIA_T else None
                            if p is not None:
                                dd = math.hypot(T(p.x) - x, T(p.y) - y)
                            else:
                                dd = FR.seg_dist(x, y, t.GetStart(), t.GetEnd())
                            if dd < 0.45:
                                victims[t.m_Uuid.AsString()] = t
                                break
                for t in victims.values():
                    b.Remove(t)
                pcbnew.SaveBoard(pcb, b)
                b = pcbnew.LoadBoard(pcb)
                a, _ = FR.find_item(b, ua["description"], ua["pos"])
                c, _ = FR.find_item(b, uc["description"], uc["pos"])
                if a is None or c is None:
                    continue
                R = FR.Router(b)
                path, w = R.route(code, R.cells_of(a), R.cells_of(c))
                print("   ripped %d items for %s %.1f -> %s" % (len(victims), net, dist, "routed" if path else "still blocked"), flush=True)
                if path is None:
                    continue
            R.commit(code, path, w)
            done += 1
        pcbnew.SaveBoard(pcb, b)
        print("   routed %d of %d" % (done, len(jobs)), flush=True)
    d = drc(pcb)
    errs = [v for v in d["violations"] if v["severity"] == "error"]
    opens = [u for u in d["unconnected_items"] if "[GND]" not in u["items"][0]["description"]]
    print("final: %d DRC errors, %d open non-GND, %d open GND" % (len(errs), len(opens), len(d["unconnected_items"]) - len(opens)))


if __name__ == "__main__":
    main()
