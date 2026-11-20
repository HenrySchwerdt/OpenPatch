#!/usr/bin/env python3
"""Derive the CLEAN variant (no break-off strip) from the routed DEV board, from ONE layout (KiCad python).

usage: python3 make_clean.py   ->  cup_clean.kicad_pcb
* Edge.Cuts redrawn as the mechanical outline (cupgeom.OUTLINE_POD_BOARD, finger edge x 40.9 straight)
* strip footprints (J10-J14, TP1-TP6) deleted
* tracks / vias that lay in the strip or crossed the neck, and every dead-end branch that is left, deleted (no stub reaches the board edge: the pruning keeps
  0.3 mm from the finger edge; dangling copper is removed iteratively), zones refilled
The first SWD flash of the clean board uses the four underside pads TPR1-TPR4 (SWDIO, SWCLK, GND, 3V3, 1.27 mm pitch) on the hall finger."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bench", "tools"))
sys.path.insert(0, HERE)
import pcbnew
import benchlib as bl
import cupgeom as G

MM = pcbnew.FromMM
T = pcbnew.ToMM
b = pcbnew.LoadBoard(os.path.join(HERE, "cup.kicad_pcb"))
# 1. outline
for d in list(b.GetDrawings()):
    if d.GetLayer() == pcbnew.Edge_Cuts:
        b.Remove(d)
poly = [(bl.OX + x, bl.OY + y) for x, y in G.OUTLINE_BOARD]
for i in range(len(poly)):
    (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
    s = pcbnew.PCB_SHAPE(b)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
    s.SetStart(pcbnew.VECTOR2I(MM(x0), MM(y0))); s.SetEnd(pcbnew.VECTOR2I(MM(x1), MM(y1)))
    b.Add(s)
# 2. strip footprints
STRIP = {"J10", "J11", "J12", "J13", "J14"} | {"TP%d" % k for k in range(1, 7)}
for f in list(b.GetFootprints()):
    if f.GetReference() in STRIP:
        b.Remove(f)
# 3. copper in the strip / across the neck: x beyond (finger edge - 0.3)
XCUT = bl.OX + (40.9 - 0.3 - G.X0)           # board frame x of the cut line (finger east edge 40.9 pod)
removed = 0
for t in list(b.GetTracks()):
    pts = [t.GetPosition()] if t.Type() == pcbnew.PCB_VIA_T else [t.GetStart(), t.GetEnd()]
    if any(T(p.x) > XCUT for p in pts):
        b.Remove(t); removed += 1
print("removed strip / neck copper:", removed)


def key(p):
    return (round(T(p.x), 3), round(T(p.y), 3))


# 4. iterative dead-end pruning (a track end that touches nothing else and is not on a pad of its net)
pads = {}
for f in b.GetFootprints():
    for pd in f.Pads():
        pads.setdefault(key(pd.GetPosition()), set()).add(pd.GetNetname())
import math


def seg_d(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def on_other(t, p):
    """does the end p of t touch the interior of another track of the same net on the same layer, or a via of that net"""
    px, py = T(p.x), T(p.y)
    for o in b.GetTracks():
        if o is t or o.GetNetCode() != t.GetNetCode():
            continue
        if o.Type() == pcbnew.PCB_VIA_T:
            if math.hypot(T(o.GetPosition().x) - px, T(o.GetPosition().y) - py) < 0.25:
                return True
        elif o.GetLayer() == t.GetLayer() and seg_d(px, py, T(o.GetStart().x), T(o.GetStart().y), T(o.GetEnd().x), T(o.GetEnd().y)) < 0.01:
            return True
    return False


pruned = 0
for _ in range(60):
    ends = {}
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            ends.setdefault(key(t.GetPosition()), []).append(t)
        else:
            for p in (t.GetStart(), t.GetEnd()):
                ends.setdefault(key(p), []).append(t)
    dead = []
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            n = [o for o in ends.get(key(t.GetPosition()), []) if o is not t]
            if len(n) == 0 and key(t.GetPosition()) not in pads and not t.GetNetname() == "GND":
                dead.append(t)
            continue
        for p in (t.GetStart(), t.GetEnd()):
            k = key(p)
            n = [o for o in ends.get(k, []) if o is not t]
            if not n and k not in pads and not on_other(t, p):
                dead.append(t); break
    if not dead:
        break
    for t in dead:
        b.Remove(t); pruned += 1
print("pruned dead-end items:", pruned)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(os.path.join(HERE, "cup_clean.kicad_pcb"), b)
print("cup_clean.kicad_pcb written")
