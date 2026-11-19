#!/usr/bin/env python3
"""Scripted placement of the CUP board: simulated annealing on rectangles (KiCad python only to read footprint geometry).

usage: kpy place_cup.py [iterations] [seed]   -> placement_5.json {ref: [bx, by, rot, side]}, prints fill statistics.
Hard rules: parts inside the outline (edge margin), nothing in the antenna keep-out, bottom-side parts <= 1.1 mm high in the low zones,
no overlap (courtyard + margin).  Cost: weighted HPWL + soft anchors + penalties."""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bench", "tools"))
sys.path.insert(0, HERE)
import pcbnew
import benchlib as bl
import cupgeom as G

T = pcbnew.ToMM
V010FP = os.path.join(HERE, "..", "footprints", "V010.pretty")
EDGE, MARGIN = 0.35, 0.10

HEIGHTS = [("ISP1807", 1.0), ("QFN-16", 0.9), ("UFQFPN", 0.6), ("SOT-23-5", 1.45), ("SOT-23-6", 1.45), ("SOT-23", 1.15), ("SOT-353", 1.1), ("SOT-363", 1.1),
           ("VSSOP", 1.1), ("D_SOD-123F", 1.0), ("D_SOD-123", 1.1), ("LED_", 0.7), ("R_0603", 0.55), ("C_0603", 1.0), ("R_0201", 0.3), ("C_0201", 0.3),
           ("R_0402", 0.5), ("C_0402", 0.6), ("X2SON", 0.4), ("Spring", 1.0), ("SW_SKRPACE", 1.4), ("TP_Pad", 0.0), ("FPC_Pad", 0.0), ("USB_C", 3.26)]


def height(fp):
    for k, h in HEIGHTS:
        if k in fp:
            return h
    return 1.0


def load_fp(lib, nm):
    if lib == "V010":
        return pcbnew.FootprintLoad(V010FP, nm)
    path = bl.BENCHFP if lib == "Bench" else os.path.join(bl.KL, lib + ".pretty")
    return pcbnew.FootprintLoad(path, nm)


def geometry(parts):
    geo = {}
    for p in parts:
        f = load_fp(*p["fp"])
        f.BuildCourtyardCaches()
        c = f.GetCourtyard(pcbnew.F_CrtYd)
        bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False, False)
        crt = [T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom())]
        pads = {pd.GetNumber(): (T(pd.GetPosition().x), T(pd.GetPosition().y)) for pd in f.Pads() if pd.GetNumber()}
        if p["ref"] not in ("JU1", "SW1") and not p["fp"][1].startswith("ISP"):
            # placement box = pad envelope + 0.12 (tighter than the library courtyard; body of SOT/QFN lies inside the pad envelope)
            pb = f.GetBoundingBox(False, False)
            x0, y0, x1, y1 = [], [], [], []
            for pd in f.Pads():
                q = pd.GetBoundingBox()
                x0.append(T(q.GetLeft())); y0.append(T(q.GetTop())); x1.append(T(q.GetRight())); y1.append(T(q.GetBottom()))
            crt = [min(x0) - 0.12, min(y0) - 0.12, max(x1) + 0.12, max(y1) + 0.12]
        geo[p["ref"]] = dict(crt=crt, pads=pads, h=height(p["fp"][1]), fp=p["fp"][1])
    return geo


def rot_pt(x, y, rot):
    r = rot % 360
    if r == 0:
        return x, y
    if r == 90:
        return y, -x
    if r == 180:
        return -x, -y
    return -y, x


def xf(x, y, rot, side):
    if side == "B":
        x = -x
    return rot_pt(x, y, rot)


def box_of(g, st):
    cx, cy, rot, side = st
    xs, ys = [], []
    for x, y in ((g["crt"][0], g["crt"][1]), (g["crt"][2], g["crt"][1]), (g["crt"][2], g["crt"][3]), (g["crt"][0], g["crt"][3])):
        a, bq = xf(x, y, rot, side)
        xs.append(cx + a); ys.append(cy + bq)
    return [min(xs), min(ys), max(xs), max(ys)]


def pad_pos(g, num, st):
    cx, cy, rot, side = st
    x, y = g["pads"][num]
    a, bq = xf(x, y, rot, side)
    return cx + a, cy + bq


def pip(x, y, poly):
    ins = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            ins = not ins
    return ins


def seg_dist(px, py, a, c):
    ax, ay = a; cx, cy = c
    dx, dy = cx - ax, cy - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def inside(bb, poly, m=EDGE):
    cs = [(bb[0], bb[1]), (bb[2], bb[1]), (bb[2], bb[3]), (bb[0], bb[3])]
    for x, y in cs:
        if not pip(x, y, poly):
            return False
        for i in range(len(poly)):
            if seg_dist(x, y, poly[i], poly[(i + 1) % len(poly)]) < m:
                return False
    # concave outline: no polygon vertex inside the (inflated) rectangle
    for x, y in poly:
        if bb[0] - m < x < bb[2] + m and bb[1] - m < y < bb[3] + m:
            return False
    return True


def ov_area(a, c, m=MARGIN):
    w = min(a[2], c[2]) - max(a[0], c[0]) + m
    h = min(a[3], c[3]) - max(a[1], c[1]) + m
    return w * h if w > 0 and h > 0 else 0.0


def in_rect(x, y, r):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    rnd = random.Random(seed)
    parts = json.load(open(os.path.join(HERE, "..", "netlist_v4_cup.json")))
    geo = geometry(parts)
    ref_of = {p["ref"]: p for p in parts}
    poly = G.OUTLINE
    # ---- fixed placements (pod coordinates -> board)
    fixed = {}

    def fix(ref, x, y, rot, side="F"):
        bx, by = G.b(x, y)
        fixed[ref] = [bx, by, rot, side]

    fix("U1", 42.4, 28.2, 90)                       # antenna half (local +Y) toward +X, overhanging the board edge
    fix("JU1", 12.5, 29.75, 180)                   # receptacle opening toward the +Y long wall
    for i in range(8):                              # REAR strip pad row, bottom side, 0.8 pitch
        fix(["MP1", "MP2", "MP3", "MP4", "TL1", "TL2", "TL3", "TL4"][i], 9.2 + 0.8 * i, 23.8, 0, "B")
    fix("SW1", 39.8, 3.0, 180)
    fix("LD1", 32.0, 31.2, 0)                      # RGB LED, top side, clear view through the lid (no tall part within 2 mm, piezo disc is at x < 28)
    fix("U4A", 39.36, 11.75, 0, "B")
    movable = [p["ref"] for p in parts if p["ref"] not in fixed]
    # side rules
    top_only = {p["ref"] for p in parts if p["group"] in ("swd", "tp") or p["ref"] in ("PZ1", "PZ2", "LD1")}
    bot_only = {"SP1", "SP2"}
    anchors = {"PZ1": (21.0, 30.0), "PZ2": (21.0, 27.0), "SP1": (38.2, 25.0), "SP2": (38.2, 31.0)}
    for p in parts:
        if p["group"] in ("swd", "tp"):
            anchors[p["ref"]] = (39.5, 20.0)
    anchor_b = {k: G.b(*v) for k, v in anchors.items()}

    # ---- nets
    nets = {}
    for p in parts:
        for pad, n in p["pins"].items():
            if n and n != "GND" and pad in geo[p["ref"]]["pads"]:
                nets.setdefault(n, []).append((p["ref"], pad))
    nets = {n: l for n, l in nets.items() if len(l) >= 2}
    wnet = {n: (0.15 if len(l) > 14 else 1.0) for n, l in nets.items()}
    for n in ("USB_DP", "USB_DM"):
        wnet[n] = 1.5
    for n in ("VMOT", "VBAT", "MOT_A1", "MOT_A2", "MOT_B1", "MOT_B2"):
        if n in wnet:
            wnet[n] = 0.6
    nets_of = {}
    for n, l in nets.items():
        for r, _ in l:
            nets_of.setdefault(r, set()).add(n)

    state = {r: list(fixed[r]) for r in fixed}
    # initial positions: spread over the body
    def rand_state(r):
        for _ in range(500):
            bx = rnd.uniform(0.5, 34.0); by = rnd.uniform(0.5, 10.0)
            side = "B" if r in bot_only else ("F" if r in top_only else rnd.choice("FB"))
            st = [bx, by, rnd.choice((0, 90, 180, 270)), side]
            if r in anchor_b:
                st[0], st[1] = anchor_b[r]
            if legal(r, st):
                return st
        return [10.0, 5.0, 0, "F"]

    def legal(r, st):
        g = geo[r]
        bb = box_of(g, st)
        if not inside(bb, poly):
            return False
        if r != "U1" and bb[2] > G.ANT[0] and bb[3] > G.ANT[1] and bb[1] < G.ANT[3]:
            return False
        if st[3] == "B" and g["h"] > G.BOT_LIMIT:
            for z in G.LOW_ZONES:
                if not (bb[2] < z[0] or bb[0] > z[2] or bb[3] < z[1] or bb[1] > z[3]):
                    return False
        if r in top_only and st[3] != "F":
            return False
        if r in bot_only and st[3] != "B":
            return False
        return True

    for r in movable:
        state[r] = rand_state(r)
    boxes = {r: box_of(geo[r], state[r]) for r in state}
    both = {"JU1", "U1"}

    def overlap_of(r, bb, st):
        s = 0.0
        for q, qb in boxes.items():
            if q == r:
                continue
            if state[q][3] == st[3] or q in both or r in both:
                s += ov_area(bb, qb)
        return s

    def hp(n, over=None):
        xs, ys = [], []
        for r, pad in nets[n]:
            st = over[r] if over and r in over else state[r]
            x, y = pad_pos(geo[r], pad, st)
            xs.append(x); ys.append(y)
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    def anchor_cost(r, st):
        a = anchor_b.get(r)
        return 0.0 if not a else 0.15 * math.hypot(st[0] - a[0], st[1] - a[1])

    netlen = {n: hp(n) for n in nets}
    total = lambda: sum(wnet[n] * netlen[n] for n in nets)
    ovtot = sum(overlap_of(r, boxes[r], state[r]) for r in movable)
    cur = total() + 40 * ovtot + sum(anchor_cost(r, state[r]) for r in movable)
    best = None
    T0, T1 = 2.0, 0.02
    acc = 0
    for it in range(N):
        t = T0 * (T1 / T0) ** (it / N)
        r = rnd.choice(movable)
        old = state[r]
        new = list(old)
        m = rnd.random()
        sig = 0.3 + 5.0 * t
        if m < 0.55:
            new[0] += rnd.gauss(0, sig); new[1] += rnd.gauss(0, sig)
        elif m < 0.70:
            new[2] = (new[2] + rnd.choice((90, 180, 270))) % 360
        elif m < 0.78 and r not in top_only and r not in bot_only:
            new[3] = "B" if old[3] == "F" else "F"
        elif m < 0.90:
            # jump next to a random net neighbour
            ns = list(nets_of.get(r, ()))
            if not ns:
                continue
            n = rnd.choice(ns)
            q = rnd.choice([x for x, _ in nets[n] if x != r] or [r])
            if q == r:
                continue
            new[0] = state[q][0] + rnd.gauss(0, 1.2); new[1] = state[q][1] + rnd.gauss(0, 1.2)
        else:
            new[0] += rnd.gauss(0, 0.15); new[1] += rnd.gauss(0, 0.15)
        if not legal(r, new):
            continue
        nb = box_of(geo[r], new)
        affected = nets_of.get(r, ())
        nl = {n: hp(n, {r: new}) for n in affected}
        dh = sum(wnet[n] * (nl[n] - netlen[n]) for n in affected)
        do = overlap_of(r, nb, new) - overlap_of(r, boxes[r], old)
        da = anchor_cost(r, new) - anchor_cost(r, old)
        d = dh + 40 * do + da
        if d <= 0 or rnd.random() < math.exp(-d / t):
            state[r] = new; boxes[r] = nb; netlen.update(nl); cur += d; ovtot += 2 * do; acc += 1
        if it % 50000 == 0:
            print("it", it, "T %.3f" % t, "cost %.1f" % cur, "hpwl %.1f" % total(), "overlap %.2f" % (ovtot / 2), flush=True)
    ov = sum(overlap_of(r, boxes[r], state[r]) for r in movable) / 2
    print("final hpwl %.1f overlap %.3f accepted %d" % (total(), ov, acc))
    out = {r: [round(v[0], 3), round(v[1], 3), v[2], v[3]] for r, v in state.items()}
    json.dump(out, open(os.path.join(HERE, "placement_5.json"), "w"), indent=0)
    # fill statistics
    area = {"F": 0.0, "B": 0.0}
    for r, bb in boxes.items():
        area[state[r][3]] += (bb[2] - bb[0]) * (bb[3] - bb[1])
    print("courtyard area F %.0f B %.0f" % (area["F"], area["B"]))


if __name__ == "__main__":
    main()
