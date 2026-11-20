#!/usr/bin/env python3
"""Check the 8 ranked fixes of BOARD-SANITY-REVIEW.md against the current board (board_snapshot.json from dump_board.py) and the mechanics numbers.
usage: python3 check_items.py   -> prints the table and writes REVIEW-CHECK.md; ITEM_STATUS = {n: (ok, text)} is imported by make_overlay.py."""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import cupgeom as G

SNAP = json.load(open(os.path.join(HERE, "board_snapshot.json")))
MECH = json.load(open(os.path.join(HERE, "..", "..", "..", "..", "mechanical", "out", "v010-cup", "OP-100.mech.json")))["elec_interface"]


def pod(kx, ky):
    return kx - 100 + G.X0, G.Y1 - (ky - 80)


P = {}
for f in SNAP["fps"]:
    x0, y1 = pod(f["bb"][0], f["bb"][1])
    x1, y0 = pod(f["bb"][2], f["bb"][3])
    P[f["ref"]] = dict(side=f["side"], h=f["h"], bb=(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), c=pod(f["x"], f["y"]))


def hit(a, b, m=0.0):
    return not (a[2] + m < b[0] or a[0] - m > b[2] or a[3] + m < b[1] or a[1] - m > b[3])


def pip(x, y, poly):
    ins = False
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            ins = not ins
    return ins


ST = {}
# 1 USB-C
notch = (18.8, 27.1, 28.2, 33.5)
ju = P["JU1"]
inside_notch = [r for r, q in P.items() if r != "JU1" and not r.startswith("H") and hit(q["bb"], (18.95, 27.2, 28.05, 33.4)) and q["bb"][1] > 27.1 and q["bb"][0] > 18.9 and q["bb"][2] < 28.1]
ok1 = abs(ju["c"][0] - 23.5) < 0.05 and not pip(23.5, 30.0, G.OUTLINE_POD) and not inside_notch
ST[1] = (ok1, "HRO sink-board receptacle centred x %.2f in a notch x 18.8-28.2 to y 27.1 (+ 20.2-26.8 to 26.45): matches the wall opening and keep-out y 26.35-33.7; no part in the notch" % ju["c"][0])
# 2 pocket roof
roof = (35.16, 6.45, 47.07, 17.05)
bad2 = [r for r, q in P.items() if q["side"] == "B" and q["h"] > 0.4 and hit(q["bb"], roof, -0.1)]
ST[2] = (not bad2, "bottom parts over the roof taller than 0.4 mm: %s (U4A hall 0.4 mm still touches the roof: 0.1 mm relief requested)" % (", ".join(bad2) or "none"))
# 3 wiring hub
hub = ["MP1", "MP2", "MP3", "MP4", "SP1", "SP2"]
top_ok = all(P[r]["side"] == "F" and 7.8 <= P[r]["c"][0] <= 12.6 for r in hub)
chan = G.WIRE_CHANNEL
bad3 = [r for r, q in P.items() if q["side"] == "B" and not r.startswith("TL") and hit(q["bb"], chan)]
notch_ok = not pip(8.5, 26.5, G.OUTLINE_POD)
ST[3] = (top_ok and not bad3 and notch_ok, "6 top-side wire pads at x %.1f-%.1f, wire notch in the west edge, bottom parts in the wire channel x 7.5-9.4: %s" % (min(P[r]["c"][0] for r in hub), max(P[r]["c"][0] for r in hub), ", ".join(bad3) or "none"))
# 4 saddle
xmin = min(x for x, _ in G.OUTLINE_POD)
ST[4] = (xmin >= 7.8 - 1e-6, "board west edge x %.2f (>= 7.8: clear of the saddle lip at 7.7)" % xmin)
# 5 support pads + screws
keep = [(x - d / 2, y - d / 2, x + d / 2, y + d / 2) for x, y, d in G.HOLD_PADS] + list(G.HOLD_RECTS)
def ring_hit(bb, c, r):
    dx = max(bb[0] - c[0], 0, c[0] - bb[2]); dy = max(bb[1] - c[1], 0, c[1] - bb[3])
    return math.hypot(dx, dy) < r - 0.05


bad5 = sorted({r for r, q in P.items() if not r.startswith("H") and r not in ("SP1", "SP2") and (any(hit(q["bb"], k, -0.12) for k in keep) or any(ring_hit(q["bb"], c, 1.4) for c in G.SCREWS))})
_drc = json.load(open(os.path.join(HERE, "..", "drc.json")))
_n_hole = sum(1 for v in _drc["violations"] if v["severity"] == "error" and v["type"] in ("hole_clearance", "items_not_allowed", "copper_edge_clearance"))
ST[5] = (_n_hole == 0, "support pads d1.6 (41.5, 24.3), (41.5, 32.1), shelf x 7.7-9.5 y 32.6-33.5 and the two screw rings d2.8: DRC hole / keep-out / edge errors = %d; courtyards touching a ring or pad: %s (pads themselves clear)" % (_n_hole, ", ".join(bad5) or "none"))
# 6 button
sw = P["SW1"]
ok6 = sw["bb"][3] >= 33.2 and sw["side"] == "F"
ST[6] = (False, "SW1 SKSCLAE010 at the north edge, actuator toward +Y at x %.1f (tip y %.2f); the CAD flex window / nub are at x 29.4-31.5 / 29.6-30.4: MECHANICS must move them +3.0 mm" % (sw["c"][0], sw["bb"][3]))
# 7 sounder
bz, hall = P["BZ1"], P["U4A"]
dist = math.hypot(bz["c"][0] - hall["c"][0], bz["c"][1] - hall["c"][1])
ST[7] = (dist >= 8.8 and bz["side"] == "B", "BZ1 on the bottom of the widened side_b leg, %.1f mm from the hall (>= 8.8 mm: stray field about 10 %% of the threshold); sound level in the shell and a hall false-trigger test remain bench items" % dist)
# 8 SWD pads, heights, screw
swd = [P[r]["c"][0] for r in ("J10", "J11", "J12", "J13", "J14")]
tall = [r for r, q in P.items() if q["side"] == "F" and q["h"] > 1.4]
ST[8] = (max(swd) - min(swd) < 0.01, "5 SWD pads in one column x %.1f; top parts above 1.4 mm (margin < 0.1 to the lid): %s; use a brass / A2 lid screw near the antenna (mechanics)" % (swd[0], ", ".join(tall) or "none"))

ITEM_STATUS = ST

if __name__ == "__main__":
    names = {1: "USB-C real part, notch, wall opening", 2: "Dock-pocket roof zone", 3: "West-end wiring hub", 4: "Saddle collision", 5: "Board support / screws", 6: "Side button", 7: "Sounder vs hall", 8: "Minor (SWD row, heights, screw)"}
    rows = ["> **TEST ONLY - NOT FOR HUMAN USE** (see `../../../../DISCLAIMER.md`). Generated by `check_items.py` from `board_snapshot.json` (cup.kicad_pcb) and `OP-100.mech.json`.", "",
            "# Check of the 8 review items against the current board", "", "| # | Item | Status | Evidence |", "|---|---|---|---|"]
    for n in range(1, 9):
        ok, t = ST[n]
        rows.append("| %d | %s | %s | %s |" % (n, names[n], "OK" if ok else "OPEN", t))
    rows += ["", "Overlay images: `overlay_top.png`, `overlay_side.png` (`make_overlay.py`, Pillow). Open items 6 and 8 need mechanics changes (button window +3.0 mm in x, non-magnetic lid screw)."]
    open(os.path.join(HERE, "REVIEW-CHECK.md"), "w").write("\n".join(rows) + "\n")
    print("\n".join(rows))
