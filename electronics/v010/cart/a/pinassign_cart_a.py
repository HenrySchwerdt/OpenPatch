#!/usr/bin/env python3
"""HJ-840 GPIO assignment for the cart A placement (kpy pinassign_cart_a.py) -> cart/a/pin_assign.json (read by netlist_cart_a.py).

Same method as ../pinassign_cart.py (B): 4 layers without filled vias in pads, so the ring of the pad matters: ring 0 pads escape outward
on F.Cu, ring 1 pads escape between two ring-0 pads, ring 2 / 3 pads need a dog-bone via at the interstitial point (build_cart_a.py).
Not used: row A (antenna zone), F6 / G6 (32 kHz crystal pins P0.00 / P0.01), B4 / C5 (NFC); of row B (0.05 mm outside the zone) only the
ring-0 pads B1 / B8. VMOT_SENSE stays on H7 (AIN, fixed); every assigned signal is digital. Fixed pads (power, USB, SWD, NRST, GND, ANT)
are those of the cup / B board. OVERRIDE: decisions taken after a routing run (none yet for A)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "bench", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "cup"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "design"))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import place_cart_a as PA  # noqa: E402  (CARTA footprint loader patched into place_cup)
import place_cup as PC  # noqa: E402
import netlist_v4 as N  # noqa: E402
from netlist_cart import HJ_SIGNALS  # noqa: E402

RING_PEN = {0: 0.0, 1: 0.2, 2: 0.4, 3: 0.6} if os.environ.get("OP_POFV") == "1" else {0: 0.0, 1: 0.6, 2: 4.0, 3: 6.0}   # POFV: every ring >= 1 pad has its own filled via
OVERRIDE = json.loads(os.environ.get("OP_PIN_OVERRIDE", "{}"))
ROW_B_PEN = 1.0


def ring(pad: str) -> int:
    r = "ABCDEFGH".index(pad[0]); c = int(pad[1:])
    return min(r, 7 - r, c - 1, 8 - c)


def main() -> None:
    parts = json.load(open(os.path.join(HERE, "netlist_cart_a.json")))
    pl = json.load(open(os.path.join(HERE, "placement.json")))
    geo = PA.geometry(parts)
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
    for sig, pad in OVERRIDE.items():
        other = [s_ for s_, p_ in cur.items() if p_ == pad and s_ != sig]
        if other:                                   # swap with the signal that had the pad
            cur[other[0]] = cur[sig]
        cur[sig] = pad
    rings = {}
    for s, p in cur.items():
        rings.setdefault(ring(p), []).append(p)
    print("cost %.1f" % cost(cur), {k: sorted(v) for k, v in sorted(rings.items())})
    json.dump(dict(sorted(cur.items())), open(os.path.join(HERE, "pin_assign.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
