#!/usr/bin/env python3
"""Scripted placement of the CUP board: simulated annealing on rectangles (KiCad python only to read footprint geometry).

usage: kpy place_cup.py [iterations] [seed]   -> placement.json {ref: [bx, by, rot, side]}, prints fill statistics.
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
EDGE, MARGIN = 0.30, 0.08

HEIGHTS = [("HJ840", 1.0), ("ISP1807", 1.0), ("QFN-16", 0.9), ("UFQFPN", 0.6), ("SOT-23-5", 1.45), ("SOT-23-6", 1.45), ("SOT-23", 1.15), ("SOT-353", 1.1), ("SOT-363", 1.1),
           ("VSSOP", 1.1), ("D_SOD-123F", 1.0), ("D_SOD-123", 1.1), ("LED_", 0.7), ("R_0603", 0.55), ("C_0603", 1.0), ("R_0201", 0.3), ("C_0201", 0.3),
           ("R_0402", 0.5), ("C_0402", 0.6), ("X2SON", 0.4), ("Spring", 1.0), ("A1251WR", 2.8), ("Wire_Pad", 0.0), ("C_0805", 1.25), ("L_1008", 1.25), ("USB_C_Mid", 1.0), ("BZ_4020", 2.0), ("SW_SKSCLAE", 1.25), ("USB_C_HRO", 1.0), ("UFDFN", 0.5), ("TP_Pad", 0.0), ("FPC_Pad", 0.0), ("USB_C", 3.26)]


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
        if p["ref"] not in ("JU1", "SW1") and not p["fp"][1].startswith(("ISP", "HJ")):
            # placement box = pad envelope + 0.12 (tighter than the library courtyard; body of SOT/QFN lies inside the pad envelope)
            pb = f.GetBoundingBox(False, False)
            x0, y0, x1, y1 = [], [], [], []
            for pd in f.Pads():
                q = pd.GetBoundingBox()
                x0.append(T(q.GetLeft())); y0.append(T(q.GetTop())); x1.append(T(q.GetRight())); y1.append(T(q.GetBottom()))
            crt = [min(x0) - 0.07, min(y0) - 0.07, max(x1) + 0.07, max(y1) + 0.07]
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

    fix("U1", 39.7, 28.2, 270)                       # HJ-840: row A (antenna pads A7/A8) toward +X at the board edge
    fix("JU1", 23.5, 33.5, 0)                   # receptacle mouth at the +Y edge (origin = mouth centre), pad row 8.0 mm inside
    for i in range(4):                              # REAR strip pad row (TMAG only), bottom side, 0.8 pitch
        fix(["TL1", "TL2", "TL3", "TL4"][i], 9.2 + 0.8 * i, 23.8, 0, "B")
    fix("SW1", 33.0, 31.65, 0)                      # side button at the north edge, actuator toward +Y; x 30.0 -> 33.0 (SKSCLAE010 is 4.85 wide: at x 30 it hits the USB notch and the shield slot): mechanics request
    for ref, hx, hy in G.HUB_PADS:                 # west-end wiring hub: motor A+ A- B+ B-, cell + -, top side
        fix(ref, hx, hy, 0)
    fix("BZ1", 41.0, 20.4, 0, "B")                 # sounder: side_b block, bottom side, farthest corner from the dock hall (8.9 mm)
    fix("U4A", 39.36, 11.75, 0, "B")
    strip_refs = ["J10", "J11", "J12", "J13", "J14"] + ["TP%d" % (k + 1) for k in range(6)]     # SWD pads + bare test pads on the break-off strip (owner decision), top side
    for k, ref in enumerate(strip_refs):
        fix(ref, G.STRIP_SLOTS[k][0], G.STRIP_SLOTS[k][1], 0)
    for k in range(4):                              # recovery pads on the underside of the hall finger
        fix("TPR%d" % (k + 1), G.RECOVERY[k][0], G.RECOVERY[k][1], 0, "B")
    movable = [p["ref"] for p in parts if p["ref"] not in fixed]
    # side rules
    top_only = {p["ref"] for p in parts if p["group"] in ("swd", "tp", "tpx") or p["ref"] in ("PZ1", "PZ2", "LD1", "SP1", "SP2", "MP1", "MP2", "MP3", "MP4")}
    bot_only = {"BZ1"}
    anchors = {"PZ1": (21.0, 30.0), "PZ2": (21.0, 27.0), "SP1": (37.0, 24.6), "SP2": (37.0, 27.6), "BZ1": (41.0, 20.4)}
    for p in parts:
        if p["group"] in ("swd", "tp"):
            anchors[p["ref"]] = (39.0, 13.0)
        elif p["group"] == "tpx":                   # bare test pads: gather them on the leg (x 35.4..42, y 17.15..22.9) and hall finger, top side
            anchors[p["ref"]] = (39.5, 20.5)
    anchor_b = {k: G.b(*v) for k, v in anchors.items()}
    tpset = {p['ref'] for p in parts if p['group'] in ('swd', 'tp', 'tpx')}

    # ---- nets
    nets = {}
    for p in parts:
        for pad, n in p["pins"].items():
            if n and n != "GND" and pad in geo[p["ref"]]["pads"]:
                nets.setdefault(n, []).append((p["ref"], pad))
    nets = {n: l for n, l in nets.items() if len(l) >= 2}
    gw = {}
    # cohesion of functional blocks (router friendliness): virtual nets over the first pad of each member
    for gname, members, w in (("_boost", ("U8", "L1", "C71", "C5", "CB1", "R55", "R56"), 2.0), ("_drive", ("U7", "C21", "C61", "MP1", "MP2", "MP3", "MP4"), 1.5),
                              ("_v3v3", ("U32", "U34", "U36", "U33", "U5", "U30", "U6", "R18", "R90", "R92", "R16", "RDK", "RNR", "C50"), 0.8)):
        lst = [(r, sorted(geo[r]["pads"])[0]) for r in members if r in geo and geo[r]["pads"]]
        if len(lst) >= 2:
            nets[gname] = lst
            gw[gname] = w
    wnet = {n: (0.15 if len(l) > 14 else 1.0) for n, l in nets.items()}
    wnet.update(gw)
    for n in ("USB_DP", "USB_DM"):
        wnet[n] = 1.5
    for n in ("VMOT", "VBAT", "MOT_A1", "MOT_A2", "MOT_B1", "MOT_B2"):
        if n in wnet:
            wnet[n] = 0.6
    # routability: the power stage nets must stay short (the first Freerouting runs left BST_SW, MOT_* and VMOT_PRE open when U8-L1 and U7-motor pads were far apart)
    for n, w in (("BST_SW", 6.0), ("VMOT_PRE", 3.0), ("VMOT", 2.5), ("MOT_A1", 2.5), ("MOT_A2", 2.5), ("MOT_B1", 2.5), ("MOT_B2", 2.5), ("BST_FB", 3.0), ("ILIM", 3.0),
                 ("PZ_C", 2.0), ("PZ_A", 2.0), ("ANT_A", 3.0), ("ANT_B", 3.0), ("LATCH_CLR_N", 2.0), ("PERM_L", 2.0), ("DOCK_XOR", 2.0), ("MOT_ALLOW", 2.0), ("WDT_DELAY", 2.0)):
        if n in wnet:
            wnet[n] = w
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

    # keep-outs from the mechanics (OP-100.mech.json elec_interface): screw rings d2.8, support pads d1.6 / shelf rectangle (both faces), wire channel (bottom side)
    keep_boxes = []
    for hx, hy in G.SCREWS:
        a, c = G.b(hx - G.SCREW_KEEPOUT_D / 2, hy - G.SCREW_KEEPOUT_D / 2), G.b(hx + G.SCREW_KEEPOUT_D / 2, hy + G.SCREW_KEEPOUT_D / 2)
        keep_boxes.append((min(a[0], c[0]), min(a[1], c[1]), max(a[0], c[0]), max(a[1], c[1])))
    for hx, hy, d in G.HOLD_PADS:
        a, c = G.b(hx - d / 2, hy - d / 2), G.b(hx + d / 2, hy + d / 2)
        keep_boxes.append((min(a[0], c[0]), min(a[1], c[1]), max(a[0], c[0]), max(a[1], c[1])))
    for x0, y0, x1, y1 in G.HOLD_RECTS:
        keep_boxes.append(tuple(G.rect_b(x0, y0, x1, y1)))
    wc = tuple(G.rect_b(*G.WIRE_CHANNEL))
    keep_boxes.append(tuple(G.rect_b(*G.STRIP_KEEP)))

    def keep_ok(r, bb, st):
        if r in fixed:
            return True
        for k in keep_boxes:
            if not (bb[2] < k[0] or bb[0] > k[2] or bb[3] < k[1] or bb[1] > k[3]):
                return False
        if st[3] == "B" and not (bb[2] < wc[0] or bb[0] > wc[2] or bb[3] < wc[1] or bb[1] > wc[3]):
            return False
        return True

    def legal(r, st):
        g = geo[r]
        bb = box_of(g, st)
        if not inside(bb, poly):
            return False
        if r != "U1" and bb[2] > G.ANT[0] and bb[3] > G.ANT[1] and bb[1] < G.ANT[3]:
            return False
        if st[3] == "B":
            for z, lim in G.LOW_ZONES:
                if g["h"] > lim and not (bb[2] < z[0] or bb[0] > z[2] or bb[3] < z[1] or bb[1] > z[3]):
                    return False
        if r == "BZ1":     # magnetic sounder: keep >= 8.8 mm from the dock hall (stray field < 10 % of the hall threshold, dipole estimate)
            hx, hy = G.b(39.36, 11.75)
            if math.hypot((bb[0] + bb[2]) / 2 - hx, (bb[1] + bb[3]) / 2 - hy) < 8.8:
                return False
        if not keep_ok(r, bb, st):
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
                s += ov_area(bb, qb, 0.0 if (r in tpset or q in tpset) else MARGIN)
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
        return 0.0 if not a else (0.7 if r in tpset else 0.15) * math.hypot(st[0] - a[0], st[1] - a[1])

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
        d = dh + (40 + 600 * (it / N) ** 2) * do + da          # overlap penalty ramps up so the last part of the schedule legalises the layout
        if d <= 0 or rnd.random() < math.exp(-d / t):
            state[r] = new; boxes[r] = nb; netlen.update(nl); cur += d; ovtot += 2 * do; acc += 1
        if it % 50000 == 0:
            print("it", it, "T %.3f" % t, "cost %.1f" % cur, "hpwl %.1f" % total(), "overlap %.2f" % (ovtot / 2), flush=True)
    # ---- legalisation: exhaustive local search for every part that still overlaps (grid 0.1 mm, radius 5 mm, all rotations / allowed sides)
    for sweep in range(10):
        bad = [r for r in movable if overlap_of(r, boxes[r], state[r]) > 1e-6]
        if not bad:
            break
        rnd.shuffle(bad)
        for r in bad:
            old = state[r]; oo = overlap_of(r, boxes[r], old)
            best_c = (oo * 1000 + 0.0, old)
            sides = ("B",) if r in bot_only else (("F",) if r in top_only else ("F", "B"))
            for side in sides:
                for rot in (0, 90, 180, 270):
                    for ix in range(-50, 51, 2):
                        for iy in range(-50, 51, 2):
                            new = [old[0] + ix * 0.1, old[1] + iy * 0.1, rot, side]
                            if not legal(r, new):
                                continue
                            nb = box_of(geo[r], new)
                            o = overlap_of(r, nb, new)
                            if o >= best_c[0] / 1000:
                                continue
                            nl2 = {n: hp(n, {r: new}) for n in nets_of.get(r, ())}
                            dh = sum(wnet[n] * (nl2[n] - netlen[n]) for n in nl2)
                            c = o * 1000 + dh + anchor_cost(r, new)
                            if c < best_c[0]:
                                best_c = (c, new)
            if best_c[1] is not old:
                new = best_c[1]
                state[r] = new; boxes[r] = box_of(geo[r], new)
                for n in nets_of.get(r, ()):
                    netlen[n] = hp(n)
        print("legalise sweep", sweep, "overlapping parts", len(bad), flush=True)
    ov = sum(overlap_of(r, boxes[r], state[r]) for r in movable) / 2
    print("final hpwl %.1f overlap %.3f accepted %d" % (total(), ov, acc))
    out = {r: [round(v[0], 3), round(v[1], 3), v[2], v[3]] for r, v in state.items()}
    json.dump(out, open(os.path.join(HERE, "placement.json"), "w"), indent=0)
    # fill statistics
    area = {"F": 0.0, "B": 0.0}
    for r, bb in boxes.items():
        area[state[r][3]] += (bb[2] - bb[0]) * (bb[3] - bb[1])
    print("courtyard area F %.0f B %.0f" % (area["F"], area["B"]))


if __name__ == "__main__":
    main()
