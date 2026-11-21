#!/usr/bin/env python3
"""DEV and CLEAN variants of the routed cup board, from ONE layout (KiCad python).

usage: kpy variants.py routed.kicad_pcb out_dir   ->  out_dir/cup_dev.kicad_pcb, out_dir/cup_clean.kicad_pcb, out_dir/TESTPOINTS.md

* CLEAN: the routed board as it is. The first SWD flash uses the four underside pads TPR1-TPR4 (SWDIO, SWCLK, GND, 3V3).
* DEV:   the same copper plus one bare 0.6 mm test pad on the UNDERSIDE for each interlock net (DEV_NETS), placed centred on an
         existing via of that net (the vias are filled and capped, so a pad on top of one is fine) or, failing that, on one of its
         underside tracks; if the net has no room at all, the pad goes on the nearest free underside spot and finish_route.py
         joins it with a short track (that stub exists only on the DEV board). Nothing is moved or re-routed:
         a via qualifies only if the 0.6 mm pad keeps the board clearance to every other net on B.Cu, stays off every underside
         part body (it may reach 0.2 mm into a courtyard) and keeps 0.5 mm from the board edge. The pads are not assembled (excluded from BOM and placement files).
The two boards therefore differ only by these pads, their solder-mask openings and the GND pour around them.
"""
import math
import os
import subprocess
import sys

import pcbnew

T, MM = pcbnew.ToMM, pcbnew.FromMM
HERE = os.path.dirname(os.path.abspath(__file__))
PAD_D = 0.60
CLR = 0.10
EDGE = 0.50
CRT_IN = 0.20
STUB_MARGIN = 0.15      # a free-spot pad keeps extra room so its joining track can leave it
# net -> short label (test-pad names TPD1.. in this order)
DEV_NETS = [("VMOT", "motor supply after the load switch"),
            ("MOT_ALLOW", "interlock output: motor driver enable"),
            ("LATCH_Q", "fault latch output"),
            ("SUP_PERMIT", "supervisor permit"),
            ("OC_OK", "load-switch over-current flag (low = fault)"),
            ("DOCK_N", "dock hall output (low = docked)")]


def seg_dist(px, py, a, b):
    ax, ay, bx, by = T(a.x), T(a.y), T(b.x), T(b.y)
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def candidate_ok(b, net, x, y, edge_poly, courtyards, margin=0.0):
    r = PAD_D / 2 + margin
    # board edge
    p = pcbnew.VECTOR2I(MM(x), MM(y))
    if not edge_poly.Contains(p):
        return False
    d_edge = T(int(math.sqrt(edge_poly.Outline(0).SquaredDistance(p, True))))
    if d_edge < EDGE + r:
        return False
    # underside parts: the pad may reach into a courtyard by CRT_IN (courtyard = body + 0.25 mm), never onto a body
    for c in courtyards:
        if c.Collide(pcbnew.SHAPE_CIRCLE(p, MM(r - CRT_IN)), 0):
            return False
    # other-net copper on B.Cu (tracks, vias, pads)
    for t in b.GetTracks():
        if t.GetNetCode() == net:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            q = t.GetPosition()
            if math.hypot(T(q.x) - x, T(q.y) - y) < r + T(t.GetWidth(pcbnew.B_Cu)) / 2 + CLR:
                return False
        elif t.GetLayer() == pcbnew.B_Cu and seg_dist(x, y, t.GetStart(), t.GetEnd()) < r + T(t.GetWidth()) / 2 + CLR:
            return False
    circ = pcbnew.SHAPE_CIRCLE(p, MM(r))
    for f in b.GetFootprints():
        for pd in f.Pads():
            if pd.GetNetCode() == net and pd.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                continue
            if not pd.IsOnLayer(pcbnew.B_Cu) and pd.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                continue
            if pd.GetEffectiveShape(pcbnew.B_Cu).Collide(circ, MM(CLR if pd.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH else 0.2)):
                return False
    return True


def add_testpad(b, ref, net, x, y):
    f = pcbnew.FOOTPRINT(b)
    f.SetReference(ref)
    f.SetValue(net.GetNetname())
    f.SetFPID(pcbnew.LIB_ID("openpatch", "TestPad_D0.6_Bottom"))
    f.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    f.Reference().SetVisible(False)
    f.Value().SetVisible(False)
    b.Add(f)
    pd = pcbnew.PAD(f)
    pd.SetNumber("1")
    pd.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pd.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    pd.SetSize(pcbnew.VECTOR2I(MM(PAD_D), MM(PAD_D)))
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Cu)
    ls.AddLayer(pcbnew.F_Mask)
    pd.SetLayerSet(ls)
    f.Add(pd)
    f.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    for p in f.Pads():
        p.SetNet(net)
    return f


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    b = pcbnew.LoadBoard(src)
    pcbnew.SaveBoard(os.path.join(out, "cup_clean.kicad_pcb"), b)
    edge = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(edge, True)
    courtyards = []
    for f in b.GetFootprints():
        if f.GetLayer() == pcbnew.B_Cu:
            f.BuildCourtyardCaches()
            c = f.GetCourtyard(pcbnew.B_CrtYd)
            if c.OutlineCount():
                courtyards.append(c)
    rows, missing = [], []
    for k, (name, what) in enumerate(DEV_NETS):
        ni = b.FindNet(name)
        if ni is None:
            missing.append(name)
            continue
        code = ni.GetNetCode()
        # candidates: the net's vias first, then points every 0.1 mm along its B.Cu tracks (the pad then sits on its own track)
        cands = []
        for t in b.GetTracks():
            if t.GetNetCode() != code:
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                cands.append((0, T(t.GetPosition().x), T(t.GetPosition().y)))
            elif t.GetLayer() == pcbnew.B_Cu:
                x0, y0, x1, y1 = T(t.GetStart().x), T(t.GetStart().y), T(t.GetEnd().x), T(t.GetEnd().y)
                n = max(1, int(math.hypot(x1 - x0, y1 - y0) / 0.1))
                cands += [(1, x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n + 1)]
        cands.sort()
        hit = None
        for _, x, y in cands:
            if candidate_ok(b, code, x, y, edge, courtyards):
                hit = (x, y)
                break
        stub = False
        if hit is None:
            # no room on the net's own copper: the nearest free underside spot, joined by a short track (finish_route.py, below)
            own = [(x, y) for _, x, y in cands] + [(T(p.GetPosition().x), T(p.GetPosition().y)) for f in b.GetFootprints()
                                                    for p in f.Pads() if p.GetNetCode() == code]
            bb = b.GetBoardEdgesBoundingBox()
            pts = [(T(bb.GetLeft()) + 0.2 * i, T(bb.GetTop()) + 0.2 * j) for i in range(int(T(bb.GetWidth()) / 0.2) + 1)
                   for j in range(int(T(bb.GetHeight()) / 0.2) + 1)]
            pts.sort(key=lambda q: min(math.hypot(q[0] - a, q[1] - c) for a, c in own))
            for x, y in pts[:4000]:
                if candidate_ok(b, code, x, y, edge, courtyards, margin=STUB_MARGIN):
                    hit, stub = (x, y), True
                    break
        if hit is None:
            missing.append(name)
            continue
        ref = "TPD%d" % (k + 1)
        add_testpad(b, ref, ni, *hit)
        rows.append((ref, name, what, hit[0] - 100.0, hit[1] - 80.0, stub))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    dev = os.path.join(out, "cup_dev.kicad_pcb")
    pcbnew.SaveBoard(dev, b)
    if any(r[5] for r in rows):
        # join the free-spot pads (separate processes: KiCad's python wrapper does not survive a second board in one process)
        drcj = os.path.join(out, "_dev_drc.json")
        subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "-o", drcj, dev], capture_output=True)
        kpy = os.path.join(HERE, "..", "board", "kpy")
        subprocess.run([kpy, os.path.join(HERE, "finish_route.py"), dev, drcj], capture_output=True)
        subprocess.run([kpy, os.path.join(HERE, "..", "board", "route_v3.py"), dev, "finish"], capture_output=True)
        os.remove(drcj)
    with open(os.path.join(out, "TESTPOINTS.md"), "w") as fh:
        fh.write("# Cup board DEV variant: underside test pads\n\n")
        fh.write("Bare 0.6 mm pads on the underside, on existing vias or joined by a short track. Board frame (mm, origin top-left of the board outline, y down, seen from the top).\n")
        fh.write("Bench use only, with water (see DISCLAIMER.md). Probe with a sprung pin; do not solder wires to them.\n\n")
        fh.write("| Pad | Net | What | x | y |\n|---|---|---|---|---|\n")
        for ref, name, what, x, y, stub in rows:
            fh.write("| %s | %s | %s%s | %.2f | %.2f |\n" % (ref, name, what, " (own short track)" if stub else "", x, y))
        if missing:
            fh.write("\nNo free via found for: %s\n" % ", ".join(missing))
    print("DEV test pads:", [(r[0], r[1]) for r in rows], "missing:", missing)


if __name__ == "__main__":
    main()
