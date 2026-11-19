#!/usr/bin/env python3
"""Build v010.kicad_pcb from netlist.json + params.json (run with KiCad's python: /usr/bin/python3).

usage: build_board.py            -> v010.kicad_pcb (placed, nets assigned, not routed), parts.json, v010.kicad_pro
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "..", "bench", "tools"))
import pcbnew
import benchlib as bl
from benchlib import Board, write_project

MM = bl.MM
PRM = json.load(open(os.path.join(HERE, "params.json")))
W, H = PRM["outline"]["w"], PRM["outline"]["h"]
PCB = os.path.join(HERE, "v010.kicad_pcb")
bl.TRACK, bl.CLEAR, bl.VIA_D, bl.VIA_H = 0.15, 0.15, 0.5, 0.25
POWER = ("VBAT", "3V3", "VMOT", "VMOT_RAW", "VMOT_A", "VMOT_PRE", "MOT_A1", "MOT_A2", "MOT_B1", "MOT_B2", "VCHG", "CHG_PAD", "VBAT_SW")
V010FP = os.path.join(ROOT, "footprints", "V010.pretty")

_orig_load = Board.load_fp


def _load(self, lib, name):
    if lib == "V010":
        fp = pcbnew.FootprintLoad(V010FP, name)
        if fp is None:
            raise SystemExit("footprint not found V010:" + name)
        return fp
    return _orig_load(self, lib, name)


Board.load_fp = _load
Y = lambda by: H - by

ANCHOR = {"mcu": (23.0, 12.0), "swd": (18.0, 3.6), "batt": (18.5, 26.0), "pwr": (19.0, 25.0), "chg": (28.0, 25.0), "sense": (27.0, 18.0),
          "sw": (7.0, 12.5), "dock": (12.0, 5.0), "wdt": (6.5, 6.0), "drv": (14.5, 22.5), "oc": (11.0, 16.0), "hwa": (21.0, 17.0),
          "ui": (29.0, 28.0), "tmag": (4.5, 25.5), "boost": (28.0, 4.0), "tp": (10.0, 8.0), "mot": (23.4, 22.0), "dock2": (12, 5), "mech": (1, 1)}
ZONES = PRM["zones"]


def rect_y(r):
    return [r[0], Y(r[3]), r[2], Y(r[1])]      # [x0,y0,x1,y1] in KiCad frame


def main():
    parts = json.load(open(os.path.join(ROOT, "netlist.json")))
    b = Board("v010", W, H, layers=4, corner=PRM["outline"]["corner_r"])
    b.b.GetDesignSettings().SetBoardThickness(MM(PRM["thickness_mm"]))
    b.rounded_outline()
    fixed = PRM["fixed"]
    rots = {"U10T": 90, "J1": 90}
    for p in parts:
        ref = p["ref"]
        fp = tuple(p["fp"])
        if ref in fixed:
            x, y = fixed[ref][0], Y(fixed[ref][1])
        else:
            ax, ay = ANCHOR.get(p["group"], (20, 14))
            x, y = ax, Y(ay)
        rot = rots.get(ref, 0)
        if ref == "U1":
            rot = float(os.environ.get("U1ROT", 90))
        b.add(ref, p["value"], fp, x, y, rot, side=p["side"], pins={k: v for k, v in p["pins"].items() if v}, lcsc=p["lcsc"], mpn=p["mpn"],
              bom=p["bom"], note=p["note"], hide_ref=True)
        b.parts[ref]["dnp"] = p["dnp"]
        b.parts[ref]["group"] = p["group"]
    fps = {f.GetReference(): f for f in b.b.GetFootprints()}
    quad_place(b, fps, parts, set(fixed))
    # antenna keep-out (copper free on all layers, both sides, no parts)
    ak = ZONES["antenna_keepout"]["rect"]
    b.keepout(ak[0], Y(ak[3]), ak[2], Y(ak[1]), "ANT_KEEPOUT")
    # ---- legalize per side
    forbid_b = [rect_y(ZONES["dock_insert_reserve"]["rect"]), rect_y(ZONES["battery_bay"]["rect"]), rect_y(ZONES["spindle_magnet_strip"]["rect"])]
    forbid_both = [rect_y(ak)]
    bottom_allowed = set(("U1", "U4A", "U4B", "U10T", "SP1", "SP2", "J1", "BZ1", "U8", "L1", "D6", "R55", "R56", "C31"))
    legalize2(b, fps, set(fixed), forbid_b, forbid_both, bottom_allowed)
    # silkscreen
    for i, t in enumerate(("TEST ONLY", "NOT FOR", "HUMAN USE")):
        b.text(t, 4.5 + 5.2 * i, Y(0.9), 0.8, thick=0.12)
    b.text("OpenPatch v0.1.0 integrated pod rev A - water only (DISCLAIMER.md)", 20.0, Y(28.2), 0.5, layer=pcbnew.B_SilkS, mirror=True, thick=0.09)
    # pad labels for the charge pads and spring contacts
    b.text("+", 30.5, Y(24.4), 1.0, thick=0.15); b.text("-", 35.5, Y(24.4), 1.0, thick=0.15)
    b.rules(power_nets=POWER, power_w=0.3)
    bds = b.b.GetDesignSettings(); bds.m_CopperEdgeClearance = MM(0.25)
    for f in b.b.GetFootprints():
        f.Reference().SetVisible(False) if f.GetReference()[0] in "RCQ" or f.GetReference().startswith(("TP", "H")) else None
    b.save(PCB)
    json.dump(b.parts, open(os.path.join(HERE, "parts.json"), "w"), indent=1)
    write_project(os.path.join(HERE, "v010.kicad_pro"), POWER, 0.3, edge=0.25)
    print("board written", len(b.parts), "parts")


def quad_place(b, fps, parts, fixed):
    """Quadratic (clique) placement of the movable parts with the fixed parts' pads as anchors; weak pull to the group anchors keeps the clusters spread."""
    import numpy as np
    T = pcbnew.ToMM
    movable = [p["ref"] for p in parts if p["ref"] not in fixed]
    idx = {r: i for i, r in enumerate(movable)}
    n = len(movable)
    A = np.zeros((n, n)); bx = np.zeros(n); by = np.zeros(n)
    netpins = {}
    for p in parts:
        for pad, net in p["pins"].items():
            if net:
                netpins.setdefault(net, []).append((p["ref"], pad))
    padpos = {}
    for r in fixed:
        for pd in fps[r].Pads():
            padpos[(r, pd.GetNumber())] = (T(pd.GetPosition().x) - bl.OX, T(pd.GetPosition().y) - bl.OY)
        c = fps[r].GetPosition()
        padpos[(r, None)] = (T(c.x) - bl.OX, T(c.y) - bl.OY)
    lowweight = {"3V3": 0.01, "VBAT": 0.02, "VMOT": 0.3, "VMOT_RAW": 0.3, "VMOT_PRE": 0.5}
    for net, pl in netpins.items():
        if net == "GND":
            continue
        k = len(pl)
        if k < 2 or k > 40:
            continue
        w = lowweight.get(net, 1.0) / (k - 1)
        for i in range(k):
            for j in range(i + 1, k):
                (ra, pa), (rb, pb) = pl[i], pl[j]
                ia, ib = idx.get(ra), idx.get(rb)
                if ia is not None and ib is not None:
                    A[ia, ia] += w; A[ib, ib] += w; A[ia, ib] -= w; A[ib, ia] -= w
                elif ia is not None and rb in fixed:
                    x, y = padpos.get((rb, pb), padpos[(rb, None)])
                    A[ia, ia] += w; bx[ia] += w * x; by[ia] += w * y
                elif ib is not None and ra in fixed:
                    x, y = padpos.get((ra, pa), padpos[(ra, None)])
                    A[ib, ib] += w; bx[ib] += w * x; by[ib] += w * y
    for p in parts:
        if p["ref"] in idx:
            i = idx[p["ref"]]
            ax, ay = ANCHOR.get(p["group"], (20, 14))
            wa = 0.03
            A[i, i] += wa; bx[i] += wa * ax; by[i] += wa * Y(ay)
    A += np.eye(n) * 1e-6
    xs = np.linalg.solve(A, bx); ys = np.linalg.solve(A, by)
    for r in movable:
        f = fps[r]
        c = f.GetPosition()
        tx = float(min(max(xs[idx[r]], 1.0), W - 1.0)); ty = float(min(max(ys[idx[r]], 1.0), H - 1.0))
        f.Move(pcbnew.VECTOR2I(MM(bl.OX + tx) - c.x, MM(bl.OY + ty) - c.y))


def legalize2(b, fps, fixed, forbid_b, forbid_both, bottom_allowed, margin=0.12, edge=0.45, step=0.25, rmax=30):
    side = lambda f: "B" if f.GetSide() == pcbnew.B_Cu else "F"
    placed = {"F": [list(x) for x in forbid_both], "B": [list(x) for x in forbid_both] + [list(x) for x in forbid_b]}
    bl_boxes = bl._box
    ov = lambda a, c: a[0] < c[2] + margin and a[2] > c[0] - margin and a[1] < c[3] + margin and a[3] > c[1] - margin
    for r in fixed:
        f = fps[r]
        bx = bl_boxes(f)
        if r.startswith("H"):
            placed["F"].append(bx); placed["B"].append(bx)
        else:
            placed[side(f)].append(bx)
    area = lambda bb: (bb[2] - bb[0]) * (bb[3] - bb[1])
    todo = sorted((r for r in fps if r not in fixed), key=lambda r: -area(bl_boxes(fps[r])))
    n_moved = 0
    for r in todo:
        f = fps[r]; b0 = bl_boxes(f); sd = side(f)
        cand = [(0.0, 0.0)]
        for k in range(1, int(rmax / step) + 1):
            ring = []
            for i in range(-k, k + 1):
                ring += [(i * step, -k * step), (i * step, k * step), (-k * step, i * step), (k * step, i * step)]
            cand += sorted(set(ring), key=lambda d: d[0] ** 2 + d[1] ** 2)
        for dx, dy in cand:
            b1 = [b0[0] + dx, b0[1] + dy, b0[2] + dx, b0[3] + dy]
            if b1[0] < edge or b1[1] < edge or b1[2] > W - edge or b1[3] > H - edge:
                continue
            if any(ov(b1, p) for p in placed[sd]):
                continue
            if dx or dy:
                f.Move(pcbnew.VECTOR2I(MM(dx), MM(dy))); n_moved += 1
            placed[sd].append(b1)
            break
        else:
            # try the other side (tail only, free air below the board) for small parts
            done = False
            if r not in bottom_allowed:
                c = f.GetPosition()
                f.Flip(c, pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
                f.Move(pcbnew.VECTOR2I(MM(bl.OX + 28.0) - c.x, MM(bl.OY + H / 2) - c.y))
                sd2 = side(f)
                b0 = bl_boxes(f)
                for dx, dy in cand:
                    b1 = [b0[0] + dx, b0[1] + dy, b0[2] + dx, b0[3] + dy]
                    if b1[0] < 17.6 or b1[1] < edge or b1[2] > W - edge or b1[3] > H - edge:
                        continue
                    if any(ov(b1, p) for p in placed[sd2]):
                        continue
                    if dx or dy:
                        f.Move(pcbnew.VECTOR2I(MM(dx), MM(dy)))
                    placed[sd2].append(b1)
                    done = True
                    break
            if not done:
                print("LEGALIZE FAILED", r, sd)
    print("legalize moved", n_moved)


if __name__ == "__main__":
    main()
