#!/usr/bin/env python3
"""HJ-840 GPIO assignment for the cart placement (kpy pinassign_cart.py) -> cart/pin_assign.json (read by netlist_cart.py).

4-layer board without filled vias in pads, so the ring of the pad matters a lot: ring 0 pads escape outward on F.Cu, ring 1 pads escape
between two ring-0 pads (one 0.10 track per 0.35 mm gap), ring 2 / 3 pads need a dog-bone via at the interstitial point.
Not used: row A (antenna zone), F6 / G6 (32 kHz crystal pins P0.00 / P0.01), B4 / C5 (NFC). Row B is outside the zone (bx 53.75) but next
to it: only its two ring-0 pads B1 / B8 (escape north / south, not toward the zone), at a small extra cost. Analog: VMOT_SENSE stays on H7 (AIN, fixed); every assigned signal is digital."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bench", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "cup"))
sys.path.insert(0, os.path.join(HERE, "..", "design"))
import place_cup as PC  # noqa: E402
import netlist_v4 as N  # noqa: E402
from netlist_cart import HJ_SIGNALS  # noqa: E402

RING_PEN = {0: 0.0, 1: 0.6, 2: 4.0, 3: 6.0}
ROW_B_PEN = 1.0


def ring(pad: str) -> int:
    r = "ABCDEFGH".index(pad[0]); c = int(pad[1:])
    return min(r, 7 - r, c - 1, 8 - c)


def main() -> None:
    parts = json.load(open(os.path.join(HERE, "netlist_cart.json")))
    pl = json.load(open(os.path.join(HERE, "placement.json")))
    geo = PC.geometry(parts)
    pads = [q for q in N.HJ_GPIO_POOL if q[0] != "A" and q not in ("F6", "G6", "B4", "C5") and not (q[0] == "B" and ring(q) > 0)]
    pos = {pd: PC.pad_pos(geo["U1"], pd, pl["U1"]) for pd in pads}
    cent = {}
    for sig in HJ_SIGNALS:
        xs = [PC.pad_pos(geo[p["ref"]], pad, pl[p["ref"]]) for p in parts if p["ref"] != "U1" for pad, net in p["pins"].items() if net == sig]
        cent[sig] = (sum(x for x, _ in xs) / len(xs), sum(y for _, y in xs) / len(xs))

    def pen(pad: str) -> float:
        return RING_PEN[ring(pad)] + (ROW_B_PEN if pad[0] == "B" else 0.0)

    def cost(a: dict) -> float:
        return sum(((pos[a[s]][0] - cent[s][0]) ** 2 + (pos[a[s]][1] - cent[s][1]) ** 2) ** 0.5 * 0.2 + pen(a[s]) for s in a)
    cur = dict(zip(HJ_SIGNALS, sorted(pads, key=pen)))
    free = [p for p in pads if p not in cur.values()]
    improved = True
    while improved:
        improved = False
        sigs = list(cur)
        for i in range(len(sigs)):
            for j in range(i + 1, len(sigs)):
                a = dict(cur); a[sigs[i]], a[sigs[j]] = a[sigs[j]], a[sigs[i]]
                if cost(a) < cost(cur) - 1e-9:
                    cur, improved = a, True
            for f in list(free):
                a = dict(cur); old = a[sigs[i]]; a[sigs[i]] = f
                if cost(a) < cost(cur) - 1e-9:
                    cur, improved = a, True
                    free.remove(f); free.append(old)
    rings = {}
    for s, p in cur.items():
        rings.setdefault(ring(p), []).append(p)
    print("cost %.1f" % cost(cur), {k: sorted(v) for k, v in sorted(rings.items())})
    json.dump(dict(sorted(cur.items())), open(os.path.join(HERE, "pin_assign.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
