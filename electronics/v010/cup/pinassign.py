#!/usr/bin/env python3
"""Assign the GPIO signals to HJ-840 GPIO pads by proximity to their other pins (kpy pinassign.py): writes pin_assign.json (read by design/netlist_v4.py)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "design")); sys.path.insert(0, HERE)
import place_cup as PC
import netlist_v4 as N
parts = json.load(open(os.path.join(HERE, "..", "netlist_v4_cup.json")))
pl = json.load(open(os.path.join(HERE, "placement.json")))
geo = PC.geometry(parts)
u1 = pl["U1"]
pads = N.HJ_GPIO_POOL
pos = {pd: PC.pad_pos(geo["U1"], pd, u1) for pd in pads}
cent = {}
for sig in N.HJ_SIGNALS:
    xs = []
    for p in parts:
        if p["ref"] == "U1":
            continue
        for pad, net in p["pins"].items():
            if net == sig and p["ref"] in pl and pad in geo[p["ref"]]["pads"]:
                xs.append(PC.pad_pos(geo[p["ref"]], pad, pl[p["ref"]]))
    cent[sig] = (sum(x for x, _ in xs) / len(xs), sum(y for _, y in xs) / len(xs)) if xs else u1[:2]
cur = {sig: pad for sig, pad in zip(N.HJ_SIGNALS, pads)}
def ring(pad):
    r = "ABCDEFGH".index(pad[0]); c = int(pad[1:])
    return min(r, 7 - r, c - 1, 8 - c)


# LGA escape: with 0.30 x 0.40 mm pads at 0.65 x 0.90 mm pitch only one 0.10 mm track fits per channel, so inner pads are very hard to route:
# perimeter pads (ring 0) cost nothing, ring 1 a little, ring 2/3 a lot (first Freerouting runs failed on exactly these pads)
RING_PEN = {0: 0.0, 1: 1.5, 2: 5.0, 3: 9.0}
cost = lambda a: sum(((pos[a[s]][0] - cent[s][0]) ** 2 + (pos[a[s]][1] - cent[s][1]) ** 2) ** 0.5 + RING_PEN[ring(a[s])] for s in a)
improved = True
free = [p for p in pads if p not in cur.values()]
while improved:
    improved = False
    sigs = list(cur)
    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            a = dict(cur); a[sigs[i]], a[sigs[j]] = a[sigs[j]], a[sigs[i]]
            if cost(a) < cost(cur) - 1e-9:
                cur = a; improved = True
        for f in free:
            a = dict(cur); old = a[sigs[i]]; a[sigs[i]] = f
            if cost(a) < cost(cur) - 1e-9:
                cur = a; free.remove(f); free.append(old); improved = True
print("cost", round(cost(cur), 1))
json.dump(cur, open(os.path.join(HERE, "pin_assign.json"), "w"), indent=1)
