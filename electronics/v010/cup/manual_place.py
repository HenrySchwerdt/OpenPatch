#!/usr/bin/env python3
"""Hand placement of the CUP board (replaces the simulated-annealing placement of place_cup.py).

usage: kpy manual_place.py [--png out.png]   -> checks every rule, writes placement.json, optionally renders top/bottom views with the ratsnest.

Floorplan (board frame: bx to the right = pod +X, by down = pod -Y; see cupgeom.py):
  * WEST LOBE  (bx 0..11):   motor power chain, everything that carries motor current:
                             boost U8/L1/CB1, load switch U20 (+ILIM R91, C60), driver U7 (+C21, C61, C19), the final AND U34 (MOT_ALLOW) next to U20.
  * BRIDGE     (bx 11..20.4): USB-C receptacle on top; CC resistors under the pad row; only inner layers and the underside carry the
                             ~14 nets between the lobes (VBAT, 3V3, MOT_ALLOW, OC_OK, SUP_PERMIT, 4 driver inputs, I2C, VMOT, VBUS_P, USB pair).
  * EAST LOBE  (bx 20.4..35.6): HJ-840 module (fixed, antenna at the east edge), USB ESD + charger west of it on top,
                             supervisor STM32C011, TPL5010, latch, XOR, AND3 and their pull resistors on the UNDERSIDE west of the module
                             (the module back stays empty: HJ-840 manual).
  * LEG + FINGER: AND U32 (latch clear), RGB LED, sounder BZ1 (underside, 2.0 mm, only here), sounder driver, dock hall at the finger tip,
                  break-off test strip east of the finger.
Every rule of place_cup.py is checked here as a hard rule; boxes are the library courtyards (or the body for parts whose body exceeds the pads).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bench", "tools"))
sys.path.insert(0, HERE)
import pcbnew  # noqa: E402
import cupgeom as G  # noqa: E402
import place_cup as PC  # noqa: E402

T = pcbnew.ToMM
EDGE = 0.30          # part box to board edge
GAP = 0.0            # courtyards may touch, never overlap
TOP_H = 1.5          # lid
# real package heights where the generic table of place_cup.py is too pessimistic (datasheet maximum)
HEIGHT_OVERRIDE = {"U5": 1.1}   # TPL5010DDCR: SOT-23-THIN (DDC), 1.1 mm max

F, B = "F", "B"
# ------------------------------------------------------------------------------------------------ fixed by the mechanics
FIXED = {
    "U1": (31.9, 5.3, 270, F),           # HJ-840, row A (antenna) at the east edge
    "JU1": (15.7, 0.0, 0, F),            # USB-C mid-mount in the notch, pad row at by 8.02
    "SW1": (25.2, 1.85, 0, F),           # side button at the north edge
    "MP1": (2.2, 8.5, 0, F), "MP2": (3.45, 8.5, 0, F), "MP3": (4.7, 8.5, 0, F),
    "MP4": (2.2, 6.3, 0, F), "SP1": (3.45, 6.3, 0, F), "SP2": (4.7, 6.3, 0, F),
    "TL1": (1.4, 9.7, 0, B), "TL2": (2.2, 9.7, 0, B), "TL3": (3.0, 9.7, 0, B), "TL4": (3.8, 9.7, 0, B),
    "BZ1": (33.2, 13.1, 90, B),          # sounder 4 x 4 x 2: only the leg has 2 mm below the board; rotated: pads clear of the east edge
    "U4A": (31.56, 21.75, 0, B),         # dock hall on the magnet axis
}
for k, ref in enumerate(["J10", "J11", "J12", "J13", "J14"] + ["TP%d" % (i + 1) for i in range(6)]):
    FIXED[ref] = (*G.b(*G.STRIP_SLOTS[k]), 0, F)
for k in range(4):
    FIXED["TPR%d" % (k + 1)] = (*G.b(*G.RECOVERY[k]), 0, B)

# ------------------------------------------------------------------------------------------------ hand placement
PLACE = {
    # ---- west lobe, TOP: boost loop L1 -> U8 -> CB1 in one row at the north edge, FB divider under it, VBAT bulk, driver bulk
    "L1": (2.35, 2.3, 0, F),
    "U8": (5.65, 2.3, 0, F),
    "CB1": (8.0, 2.1, 90, F),
    "R55": (3.25, 4.35, 0, F),
    "R56": (5.25, 4.35, 0, F),
    "C5": (7.75, 5.2, 0, F),
    "C21": (7.4, 9.0, 0, F),
    # ---- west lobe, BOTTOM: driver under the motor pads, load switch under CB1, final AND gate, input caps, I2C pull-ups at the REAR pads
    "U7": (7.0, 7.1, 0, B),
    "C61": (9.0, 6.0, 90, B),
    "C19": (9.0, 8.1, 90, B),
    "C71": (3.6, 2.3, 0, B),
    "C60": (5.3, 0.85, 0, B),
    "U20": (7.8, 2.7, 0, B),
    "R91": (7.8, 0.85, 0, B),
    "U34": (3.6, 4.25, 0, B),
    "R90": (5.9, 4.3, 90, B),
    "RI1": (5.2, 9.75, 0, B),
    "RI2": (7.15, 9.75, 0, B),
    "R82": (9.1, 9.75, 0, B),
    # ---- bridge: CC resistors under their pads and the VMOT sense divider (top strip under the receptacle), latch + latch-clear AND (underside)
    "RU1": (16.95, 9.75, 0, F),     # CC1 = A5 at bx 16.95
    "RU2": (13.95, 9.75, 0, F),     # CC2 = B5 at bx 13.95
    "R57": (11.0, 9.7, 0, F),
    "R58": (19.0, 9.7, 0, F),
    "U6": (24.25, 8.9, 0, F),
    "U32": (18.2, 8.6, 0, B),
    # ---- east lobe, TOP (west of the module): charger, 3V3 bulk, USB ESD, VBUS bulk
    "U3": (24.1, 5.8, 0, F),
    "C70": (27.5, 5.6, 90, F),
    "UU1": (13.0, 8.9, 0, B),
    "CU1": (30.2, 1.15, 0, F),
    "R3": (27.5, 9.2, 90, F),
    # ---- east lobe, BOTTOM (supervisor block west of the module; the module back stays empty)
    "U30": (26.35, 2.25, 0, B),
    "U5": (24.0, 6.05, 0, B),
    "C50": (22.45, 1.3, 90, B),
    "U33": (23.45, 9.05, 0, B),
    "R26": (22.45, 3.3, 90, B),
    "U36": (27.4, 5.2, 0, B),
    "RNR": (23.8, 1.3, 90, B),
    "R29": (23.8, 3.3, 90, B),
    "R18": (25.55, 9.0, 90, B),
    "R16": (26.6, 9.0, 90, B),
    "RDK": (27.65, 9.0, 90, B),
    "R92": (21.3, 4.45, 90, B),
    # ---- leg / finger, TOP: sounder driver over the sounder, LED + flyback diode on the finger
    "QBA": (32.95, 12.2, 0, F),
    "RBZ": (33.2, 14.7, 0, F),
    "RDA": (29.4, 11.4, 0, F),
    "R74": (29.5, 15.5, 0, F),
    "LD1": (31.6, 17.6, 0, F),
    "D6": (31.6, 20.6, 90, F),
}


THT = [(9.72, 1.19, 10.52, 3.09), (9.72, 5.79, 10.52, 7.69), (20.88, 1.19, 21.68, 3.09), (20.88, 5.79, 21.68, 7.69),
       (11.65, 6.52, 12.25, 7.12), (19.15, 6.52, 19.75, 7.12)]      # JU1 shield slots (PTH) and pegs (NPTH), board frame


def boxes_and_heights(parts):
    geo = PC.geometry(parts)
    out = {}
    for p in parts:
        lib, nm = p["fp"]
        f = PC.load_fp(lib, nm)
        f.BuildCourtyardCaches()
        c = f.GetCourtyard(pcbnew.F_CrtYd)
        if c.OutlineCount():
            bb = c.BBox()
            crt = [T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom())]
        else:
            crt = geo[p["ref"]]["crt"]
        if nm.startswith(("TP_Pad", "FPC_Pad", "Wire_Pad")):
            crt = geo[p["ref"]]["crt"]
        g = dict(geo[p["ref"]])
        g["crt"] = crt
        g["h"] = HEIGHT_OVERRIDE.get(p["ref"], g["h"])
        out[p["ref"]] = g
    return out


def circle_box_dist(cx, cy, bb):
    dx = max(bb[0] - cx, 0, cx - bb[2])
    dy = max(bb[1] - cy, 0, cy - bb[3])
    return math.hypot(dx, dy)


def check(parts, geo, pl):
    errs = []
    boxes = {r: PC.box_of(geo[r], pl[r]) for r in pl}
    for r, bb in boxes.items():
        side = pl[r][3]
        if r in FIXED:
            continue
        strip = r.startswith(("J1", "TP")) and not r.startswith("TPR")
        if not PC.inside(bb, G.OUTLINE, EDGE if not strip and r not in ("JU1",) else 0.05):
            if r != "JU1":
                errs.append("%s outside the outline / edge margin %s" % (r, [round(v, 2) for v in bb]))
        if not strip:
            k = G.STRIP_KEEP
            sk = G.rect_b(k[0], k[1], k[2], k[3])
            if bb[0] < sk[2] and bb[2] > sk[0] and bb[1] < sk[3] and bb[3] > sk[1] and r not in ("U4A",) and not r.startswith("TPR"):
                errs.append("%s in the strip keep area" % r)
        a = G.ANT
        if r != "U1" and bb[0] < a[2] and bb[2] > a[0] and bb[1] < a[3] and bb[3] > a[1]:
            errs.append("%s in the antenna keep-out" % r)
        for sx, sy in G.SCREWS:
            cx, cy = G.b(sx, sy)
            if circle_box_dist(cx, cy, bb) < G.SCREW_KEEPOUT_D / 2:
                errs.append("%s in the screw ring at %.1f/%.1f" % (r, cx, cy))
        for hx, hy, d in G.HOLD_PADS:
            cx, cy = G.b(hx, hy)
            if circle_box_dist(cx, cy, bb) < d / 2:
                errs.append("%s on the support pad at %.1f/%.1f" % (r, cx, cy))
        for hr in G.HOLD_RECTS:
            q = G.rect_b(*hr)
            if bb[0] < q[2] and bb[2] > q[0] and bb[1] < q[3] and bb[3] > q[1] and not r.startswith("TL"):
                errs.append("%s on the wall shelf" % r)
        h = geo[r]["h"]
        if side == F and h > TOP_H:
            errs.append("%s too tall for the top (%.2f)" % (r, h))
        if side == B:
            wc = G.rect_b(*G.WIRE_CHANNEL)
            if bb[0] < wc[2] and bb[2] > wc[0] and bb[1] < wc[3] and bb[3] > wc[1] and not r.startswith("TL") and h > 0:
                errs.append("%s on the underside wire channel" % r)
            for z, lim in G.LOW_ZONES:
                if bb[0] < z[2] and bb[2] > z[0] and bb[1] < z[3] and bb[3] > z[1] and h > lim + 1e-6 and r not in ("U4A",):
                    errs.append("%s (h %.2f) in a low underside zone (max %.2f)" % (r, h, lim))
            m = boxes["U1"]
            if bb[0] < m[2] and bb[2] > m[0] and bb[1] < m[3] and bb[3] > m[1]:
                errs.append("%s on the back of the module" % r)
    refs = list(pl)
    for i in range(len(refs)):
        for j in range(i + 1, len(refs)):
            a, c = refs[i], refs[j]
            if pl[a][3] != pl[c][3]:
                continue
            A, C = boxes[a], boxes[c]
            w = min(A[2], C[2]) - max(A[0], C[0]) + GAP
            hh = min(A[3], C[3]) - max(A[1], C[1]) + GAP
            if w > 1e-6 and hh > 1e-6:
                errs.append("overlap %s %s (%.2f x %.2f)" % (a, c, w, hh))
    # through-hole shield slots and pegs of the USB receptacle block both sides (board frame boxes from the footprint, + 0.2 mm)
    for t in THT:
        for r, bb in boxes.items():
            if r in ("JU1",):
                continue
            if bb[0] < t[2] + 0.2 and bb[2] > t[0] - 0.2 and bb[1] < t[3] + 0.2 and bb[3] > t[1] - 0.2:
                errs.append("%s on a USB through-hole slot/peg %s" % (r, t))
    return errs, boxes


def pads_of(parts, geo, pl):
    out = {}
    for p in parts:
        r = p["ref"]
        for pad, net in p["pins"].items():
            if net and pad in geo[r]["pads"]:
                out.setdefault(net, []).append((r, pad, PC.pad_pos(geo[r], pad, pl[r])))
    return out


def mst(pts):
    if len(pts) < 2:
        return []
    done = [0]
    edges = []
    rest = set(range(1, len(pts)))
    while rest:
        best = None
        for i in done:
            for j in rest:
                d = math.dist(pts[i], pts[j])
                if best is None or d < best[0]:
                    best = (d, i, j)
        edges.append((pts[best[1]], pts[best[2]]))
        done.append(best[2])
        rest.discard(best[2])
    return edges


def render(parts, geo, pl, boxes, png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Polygon, Circle
    nets = pads_of(parts, geo, pl)
    fig, axs = plt.subplots(2, 1, figsize=(16, 22))
    for ax, side in zip(axs, (F, B)):
        ax.add_patch(Polygon(G.OUTLINE, closed=True, fill=False, lw=1.5, color="k"))
        a = G.ANT
        ax.add_patch(Rectangle((a[0], a[1]), a[2] - a[0], a[3] - a[1], color="orange", alpha=0.25))
        for sx, sy in G.SCREWS:
            cx, cy = G.b(sx, sy)
            ax.add_patch(Circle((cx, cy), G.SCREW_KEEPOUT_D / 2, color="red", alpha=0.2))
        for hx, hy, d in G.HOLD_PADS:
            cx, cy = G.b(hx, hy)
            ax.add_patch(Circle((cx, cy), d / 2, color="purple", alpha=0.2))
        for r, bb in boxes.items():
            s = pl[r][3]
            col = "tab:blue" if s == side else "0.85"
            ax.add_patch(Rectangle((bb[0], bb[1]), bb[2] - bb[0], bb[3] - bb[1], fill=(s == side), alpha=0.25 if s == side else 1, ec=col, fc=col, lw=0.8))
            if s == side:
                ax.text((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, r, ha="center", va="center", fontsize=7, weight="bold")
        for net, lst in nets.items():
            if net == "GND" or len(lst) < 2:
                continue
            for (x0, y0), (x1, y1) in mst([q[2] for q in lst]):
                ax.plot([x0, x1], [y0, y1], lw=0.5, color="g", alpha=0.6)
        for net, lst in nets.items():
            for r, pad, (x, y) in lst:
                if pl[r][3] == side or r in ("U1",):
                    ax.plot(x, y, ".", ms=2, color="r" if net != "GND" else "k")
        ax.set_xlim(-1, 40)
        ax.set_ylim(24, -1)
        ax.set_aspect("equal")
        ax.set_title("TOP (seen from the top)" if side == F else "BOTTOM (also seen from the top, x not mirrored)")
        ax.grid(True, lw=0.3)
    plt.tight_layout()
    plt.savefig(png, dpi=110)


def main():
    parts = json.load(open(os.path.join(HERE, "..", "netlist_v4_cup.json")))
    geo = boxes_and_heights(parts)
    pl = {}
    pl.update({k: list(v) for k, v in FIXED.items()})
    pl.update({k: list(v) for k, v in PLACE.items()})
    missing = [p["ref"] for p in parts if p["ref"] not in pl]
    extra = [r for r in pl if r not in geo]
    errs, boxes = check(parts, geo, {r: pl[r] for r in pl if r in geo})
    for e in errs:
        print("RULE:", e)
    print("missing:", missing, "unknown:", extra)
    print("rule violations:", len(errs))
    if "--png" in sys.argv:
        render(parts, geo, {r: pl[r] for r in pl if r in geo}, boxes, sys.argv[sys.argv.index("--png") + 1])
    if not missing and not extra:
        json.dump({r: pl[r] for r in pl}, open(os.path.join(HERE, "placement.json"), "w"), indent=1)
        print("placement.json written")
    return 1 if (errs or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
