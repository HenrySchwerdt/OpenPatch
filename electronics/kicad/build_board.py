#!/usr/bin/env python3
"""Build openpatch-op100.kicad_pcb from the fab netlist (run with KiCad's python3).

Frame: mechanical frame (x length, y width) -> KiCad (x, -y), so top view matches the CAD.
Inputs : eco_netlist.build(), ../../mechanical/out/OP-100.layout.json
"""
from __future__ import annotations

import json
import math
import os
import sys

import pcbnew

import eco_netlist

HERE = os.path.dirname(os.path.abspath(__file__))
LAYOUT = os.path.join(HERE, "..", "..", "mechanical", "out", "OP-100.layout.json")
OUT = os.path.join(HERE, "openpatch-op100.kicad_pcb")
KLIB = eco_netlist.KL
FROM = pcbnew.FromMM

lay = json.load(open(LAYOUT))
PCB_X0, PCB_X1 = lay["pcb"]["x"]
PCB_Y0, PCB_Y1 = lay["pcb"]["y"]
CUT = lay["pcb"]["cutouts"]  # name -> [x0,x1,y0,y1]
RF = lay["rf_module"]
COIL = (lay["coil"]["cx"], lay["coil"]["cy"], lay["coil"]["d"] / 2)
BAT_TABS = lay["contacts"]["battery_tabs"]
MOTOR = lay["contacts"]["motor_fpc"]


def P(x: float, y: float) -> "pcbnew.VECTOR2I":
    return pcbnew.VECTOR2I(FROM(x), FROM(-y))


def outline_pts() -> list[tuple[float, float]]:
    t, m, mt = CUT["tower_notch"], CUT["magnet"], CUT["motor_tail"]
    return [(t[1], PCB_Y0), (PCB_X1, PCB_Y0), (PCB_X1, PCB_Y1), (mt[1], PCB_Y1), (mt[1], mt[2]),
            (PCB_X0, mt[2]), (PCB_X0, m[3]), (m[1], m[3]), (m[1], m[2]), (PCB_X0, m[2]),
            (PCB_X0, t[3]), (t[1], t[3])]


def add_line(board, a, b, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a)); s.SetEnd(P(*b))
    s.SetLayer(layer); s.SetWidth(FROM(w))
    board.Add(s)


def add_outline(board):
    pts = outline_pts()
    for i, a in enumerate(pts):
        add_line(board, a, pts[(i + 1) % len(pts)])
    s = CUT["screw_c"]  # interior slot
    r = [(s[0], s[2]), (s[1], s[2]), (s[1], s[3]), (s[0], s[3])]
    for i, a in enumerate(r):
        add_line(board, a, r[(i + 1) % 4])


def add_keepout(board, rect, name, layers_all=True, no_vias=True, no_tracks=True, no_pads=False, no_fp=False):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetZoneName(name)
    z.SetDoNotAllowTracks(no_tracks); z.SetDoNotAllowVias(no_vias)
    z.SetDoNotAllowZoneFills(True); z.SetDoNotAllowPads(no_pads); z.SetDoNotAllowFootprints(no_fp)
    ls = pcbnew.LSET()
    for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    x0, x1, y0, y1 = rect
    ch = z.Outline()
    ch.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        ch.Append(FROM(x), FROM(-y))
    board.Add(z)


def add_text(board, txt, x, y, size=0.6, layer=pcbnew.F_SilkS, rot=0.0, mirror=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt); t.SetPosition(P(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(FROM(size), FROM(size)))
    t.SetTextThickness(FROM(0.1))
    t.SetTextAngleDegrees(rot)
    t.SetMirrored(mirror)
    board.Add(t)


def load_fp(lib: str, name: str):
    path = os.path.join(HERE, "OpenPatch.pretty") if lib == "OpenPatch" else os.path.join(KLIB, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit(f"footprint not found {lib}:{name}")
    return fp


# ---------------------------------------------------------------- placement
class Placer:
    def __init__(self):
        self.boxes = {"F": [], "B": []}  # (x0,y0,x1,y1) mech coords

    def free(self, side, x0, y0, x1, y1):
        for b in self.boxes[side]:
            if x0 < b[2] and x1 > b[0] and y0 < b[3] and y1 > b[1]:
                return False
        return True

    def add(self, side, box):
        self.boxes[side].append(box)


def inside_outline(x0, y0, x1, y1, margin=0.3) -> bool:
    if x0 < PCB_X0 + margin or x1 > PCB_X1 - margin or y0 < PCB_Y0 + margin or y1 > PCB_Y1 - margin:
        return False
    for k in ("tower_notch", "magnet", "motor_tail", "screw_c"):
        c = CUT[k]
        if x0 < c[1] + margin and x1 > c[0] - margin and y0 < c[3] + margin and y1 > c[2] - margin:
            return False
    return True


def in_coil(x0, y0, x1, y1) -> bool:
    cx, cy, r = COIL
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        if math.hypot(x - cx, y - cy) > r:
            continue
        return True
    return False


ANT = RF["keepout_xy"]  # x0,x1,y0,y1
MOD = RF["x"] + RF["y"]  # x0,x1,y0,y1 module body
TALL_Y = 18.9


def fp_dims(fp) -> tuple[float, float]:
    """Symmetric (about the footprint origin) pad extents + 0.1 mm, no silk/fab."""
    ex = ey = 0.0
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        c = fp.GetPosition()
        ex = max(ex, abs(bb.GetLeft() - c.x), abs(bb.GetRight() - c.x))
        ey = max(ey, abs(bb.GetTop() - c.y), abs(bb.GetBottom() - c.y))
    return 2 * ex / 1e6 + 0.1, 2 * ey / 1e6 + 0.1


def kind_of(ref: str, fpname: str) -> str:
    if fpname.startswith(("R_0402", "C_0402")):
        return "p0402"
    return "other"


def place_all(board, comps):
    pl = Placer()
    fps = {}
    nets = {}
    for ref, c in comps.items():
        fp = load_fp(c["lib"], c["fp"])
        fp.SetReference(ref); fp.SetValue(c["value"])
        fps[ref] = fp
        for pad, n in c["pads"].items():
            nets.setdefault(n, []).append((ref, pad))
    pos = {}  # ref -> (x,y,side,rot)

    def commit(ref, x, y, side, rot):
        fp = fps[ref]
        fp.SetPosition(P(x, y))
        board.Add(fp)
        if side == "B":
            fp.Flip(P(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot if side == "F" else -rot)
        w, h = fp_dims_cache[ref]
        if rot in (90, 270):
            w, h = h, w
        infl = 0.1 if kind_of(ref, comps[ref]["fp"]) == "p0402" else 0.18
        pl.add(side, (x - w / 2 - infl, y - h / 2 - infl, x + w / 2 + infl, y + h / 2 + infl))
        pos[ref] = (x, y, side, rot)

    fp_dims_cache = {r: fp_dims(f) for r, f in fps.items()}
    # --- fixed anchors (mechanical layout) ---
    fixed = {
        "U1": (sum(RF["x"]) / 2, sum(RF["y"]) / 2, "F", 180),
        "SW1": (lay["button"]["x"] - 0.6, lay["button"]["y"], "F", 0),
        "U8": (26.9, 22.6, "F", 90),
        "U9": (26.6, 21.6, "B", 90),
        "U10": (26.6, 23.5, "B", 90),
        "BT1": (BAT_TABS[0]["x"], (BAT_TABS[0]["y"] + BAT_TABS[1]["y"]) / 2, "B", 0),
        "MP1": (sum(m["x"] for m in MOTOR) / 4, MOTOR[0]["y"], "B", 0),
        "LRX1": (36.6, 18.4, "F", 0),
        "U13": (35.0, 14.6, "B", 0),
        "C20": (29.8, 20.1, "F", 90), "C21": (29.8, 24.7, "F", 90),
    }
    # through-hole/via keep-outs that block the opposite side as well
    pl.add("B", (MOD[0] - 0.2, MOD[2] - 0.2, MOD[1] + 0.2, MOD[2] + 4.2))      # via-in-pad area under ISP1807
    pl.add("F", (30.3, 3.2, 37.6, 6.9)); pl.add("B", (30.3, 3.2, 37.6, 6.9))   # TC2030 pads + NPTH
    for ref, (x, y, s, r) in fixed.items():
        commit(ref, x, y, s, r)
    # FPC connector: put the centroid of pads 1-4 on the motor tail pads of layout.json
    mp = fps["MP1"]; tgt = P(sum(m["x"] for m in MOTOR) / 4, MOTOR[0]["y"])
    pads = [p for p in mp.Pads() if p.GetNumber() in ("1", "2", "3", "4")]
    cx = sum(p.GetPosition().x for p in pads) / 4; cy = sum(p.GetPosition().y for p in pads) / 4
    mp.Move(pcbnew.VECTOR2I(int(tgt.x - cx), int(tgt.y - cy)))
    # --- bottom pads: J1 + test points (no components under the cannula tower) ---
    commit("J1", 33.4, 5.0, "B", 0)
    tp_slots = [(28.6 + 1.6 * (i % 4), 8.4 + 1.8 * (i // 4)) for i in range(13)]
    for i, ref in enumerate(sorted([r for r in comps if r.startswith("TP")], key=lambda s: int(s[2:]))):
        x, y = tp_slots[i]
        commit(ref, x + 4.0, y + 1.0, "B", 0)
    # --- ICs with target hints ---
    ic_targets = [("U2", 37.4, 16.3, 0), ("U4", 31.6, 16.4, 0), ("U3", 36.8, 12.2, 0), ("U12", 31.8, 12.2, 0),
                  ("Q4", 38.4, 8.4, 0), ("Q5", 35.6, 8.4, 0), ("Q6", 32.8, 8.4, 0), ("Q7", 30.0, 8.4, 0),
                  ("U5", 38.0, 4.4, 0), ("U6", 34.2, 4.0, 0), ("Q2", 30.6, 4.4, 0), ("D2", 28.4, 7.5, 0)]
    todo = [r for r in comps if r not in pos]

    def allowed(ref, side, x0, y0, x1, y1):
        if side == "F":
            if not inside_outline(x0, y0, x1, y1):
                return False
            if MOD[0] - 0.3 < x1 and x0 < MOD[1] + 0.3 and MOD[2] - 0.3 < y1 and y0 < MOD[3] + 0.3:
                return False
            if x0 < ANT[1] and x1 > ANT[0] and y0 < ANT[3] and y1 > ANT[2]:
                return False
            tall = comps[ref]["fp"] in ("C_1206_3216Metric",) or ref in ("SW1", "U8")
            if tall and y0 < TALL_Y:
                return False
            return True
        # bottom: only 0.5 mm class parts, over battery y>=13.7 (x>=28.3), keep contact lands/halls clear
        if not comps[ref]["fp"].startswith(("R_0402", "C_0402")):
            return False
        if not inside_outline(x0, y0, x1, y1, 0.4):
            return False
        if y0 < 13.9 or x0 < 28.6 or x1 > PCB_X1 - 0.4 or y1 > 24.5:
            return False
        for bx in ((28.2, 20.0, 30.2, 23.9),):  # battery contact lands + spring swing
            if x0 < bx[2] and x1 > bx[0] and y0 < bx[3] and y1 > bx[1]:
                return False
        return True

    def cost(ref, x, y, side):
        c = 0.0
        for pad, n in comps[ref]["pads"].items():
            if n in ("GND",):
                continue
            others = [pos[r] for r, p in nets[n] if r in pos and r != ref]
            if not others:
                continue
            w = 0.25 if len(nets[n]) > 10 else 1.0
            cx = sum(o[0] for o in others) / len(others); cy = sum(o[1] for o in others) / len(others)
            c += w * (abs(cx - x) + abs(cy - y))
        if side == "B":
            c += 4.0
        return c

    def try_place(ref, tx=None, ty=None, rots=(0, 90)):
        w0, h0 = fp_dims_cache[ref]
        infl = 0.1 if kind_of(ref, comps[ref]["fp"]) == "p0402" else 0.18
        best = None
        sides = ("F", "B") if kind_of(ref, comps[ref]["fp"]) == "p0402" else ("F",)
        for side in sides:
            for rot in rots:
                w, h = (h0, w0) if rot in (90, 270) else (w0, h0)
                x = PCB_X0
                while x < PCB_X1:
                    y = PCB_Y0
                    while y < PCB_Y1:
                        x0, y0, x1, y1 = x - w / 2, y - h / 2, x + w / 2, y + h / 2
                        if allowed(ref, side, x0, y0, x1, y1) and pl.free(side, x0 - infl, y0 - infl, x1 + infl, y1 + infl):
                            c = cost(ref, x, y, side)
                            if tx is not None:
                                c += abs(tx - x) + abs(ty - y)
                            if best is None or c < best[0]:
                                best = (c, x, y, side, rot)
                        y += 0.1
                    x += 0.1
        return best

    for ref, tx, ty, _ in ic_targets:
        b = try_place(ref, tx, ty, (0, 90))
        if b is None:
            raise SystemExit(f"no room for {ref}")
        commit(ref, b[1], b[2], b[3], b[4])
    todo = [r for r in comps if r not in pos]
    # order: more connections to already-placed parts first
    unplaced = set(todo)
    while unplaced:
        def score(r):
            s = 0
            for n in comps[r]["pads"].values():
                s += sum(1 for rr, _ in nets[n] if rr in pos and n != "GND" and len(nets[n]) < 12)
            return -s
        ref = sorted(unplaced, key=score)[0]
        b = try_place(ref)
        if b is None:
            print("NO ROOM:", ref, comps[ref]["fp"]); unplaced.discard(ref); continue
        commit(ref, b[1], b[2], b[3], b[4])
        unplaced.discard(ref)
    return fps, pos, nets


def main():
    comps = eco_netlist.build()
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(FROM(0.8))
    # nets
    netmap = {}
    for c in comps.values():
        for n in c["pads"].values():
            if n not in netmap:
                ni = pcbnew.NETINFO_ITEM(board, n)
                board.Add(ni); netmap[n] = ni
    add_outline(board)
    fps, pos, nets = place_all(board, comps)
    for ref, fp in fps.items():
        for pad in fp.Pads():
            n = comps[ref]["pads"].get(pad.GetNumber())
            if n:
                pad.SetNet(netmap[n])
    # ISP1807 via-in-pad on every connected pad that cannot escape on L1 (datasheet 4.2: 0.2 drill / 0.4 catch pad, filled+capped)
    u1 = fps["U1"]
    for pad in u1.Pads():
        n = comps["U1"]["pads"].get(pad.GetNumber())
        if not n:
            continue
        lp = pad.GetFPRelativePosition()
        x, y = lp.x / 1e6, lp.y / 1e6
        outer = y < -3.5 or x < -3.5 or x > 3.5
        if (outer and n != "GND") or n == "RF_LINK":
            continue
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pad.GetPosition()); v.SetNet(netmap[n])
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetWidth(pcbnew.F_Cu, FROM(0.4)); v.SetDrill(FROM(0.2))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetIsFree(False)
        board.Add(v)
    # RF bridge pads 20-22
    pr = {p.GetNumber(): p for p in u1.Pads()}
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pr["20"].GetPosition()); t.SetEnd(pr["22"].GetPosition())
    t.SetWidth(FROM(0.3)); t.SetLayer(pcbnew.F_Cu); t.SetNet(netmap["RF_LINK"])
    board.Add(t)
    # antenna keep-out (all layers, no copper), allowed LGA pads of module
    add_keepout(board, (ANT[0], ANT[1], ANT[2], PCB_Y1 + 0.6), "ANT_KEEPOUT", no_pads=False)
    # silkscreen
    add_text(board, "TEST ONLY - NOT FOR HUMAN USE", 33.0, 17.1, 0.55)
    add_text(board, "OpenPatch OP-100 Rev A", 33.0, 1.9, 0.5)
    add_text(board, "TEST ONLY - NOT FOR HUMAN USE", 33.6, 6.3, 0.55, layer=pcbnew.B_SilkS, mirror=True)
    pcbnew.SaveBoard(OUT, board)
    json.dump({r: list(v) for r, v in pos.items()}, open(os.path.join(HERE, "placement.json"), "w"), indent=0)
    print("saved", OUT, len(fps), "footprints")


if __name__ == "__main__":
    main()
