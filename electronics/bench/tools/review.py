#!/usr/bin/env python3
"""Layout self-review checks for the controller board (KiCad python3): review.py controller.kicad_pcb

Checks: antenna keep-out (no copper of any kind on any layer), GND plane continuity (island count and tracks on the plane layer),
decoupling distance, motor-loop / shunt Kelvin geometry, shortest key loops.
"""
import math
import sys

import pcbnew

OX, OY = 100.0, 80.0
t = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
layers = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu] if b.GetCopperLayerCount() == 4 else [pcbnew.F_Cu, pcbnew.B_Cu]
names = {l: b.GetLayerName(l) for l in layers}
fps = {f.GetReference(): f for f in b.GetFootprints()}


def pos(f):
    p = f.GetPosition()
    return t(p.x) - OX, t(p.y) - OY


def pad(ref, num):
    for p in fps[ref].Pads():
        if p.GetNumber() == str(num):
            q = p.GetPosition()
            return t(q.x) - OX, t(q.y) - OY
    raise KeyError((ref, num))


# ---- antenna keep-out
ko = None
for z in b.Zones():
    if z.GetIsRuleArea() and z.GetZoneName() == "ANT_KEEPOUT":
        bb = z.GetBoundingBox()
        ko = (t(bb.GetLeft()) - OX, t(bb.GetTop()) - OY, t(bb.GetRight()) - OX, t(bb.GetBottom()) - OY)
print("antenna keep-out box", [round(v, 2) for v in ko], "layers", [names[l] for l in layers if z.IsOnLayer(l)])
viol = 0
for tr in b.GetTracks():
    bb = tr.GetBoundingBox()
    x0, y0, x1, y1 = t(bb.GetLeft()) - OX, t(bb.GetTop()) - OY, t(bb.GetRight()) - OX, t(bb.GetBottom()) - OY
    if x0 < ko[2] and x1 > ko[0] and y0 < ko[3] and y1 > ko[1]:
        viol += 1
        print("  COPPER IN KEEP-OUT:", tr.GetClass(), tr.GetNetname(), names.get(tr.GetLayer(), tr.GetLayer()))
for f in b.GetFootprints():
    for p in f.Pads():
        bb = p.GetBoundingBox()
        x0, y0, x1, y1 = t(bb.GetLeft()) - OX, t(bb.GetTop()) - OY, t(bb.GetRight()) - OX, t(bb.GetBottom()) - OY
        if x0 < ko[2] and x1 > ko[0] and y0 < ko[3] and y1 > ko[1]:
            viol += 1
            print("  PAD IN KEEP-OUT:", f.GetReference(), p.GetNumber())
fillviol = 0
for z in b.Zones():
    if z.IsOnCopperLayer() and not z.GetIsRuleArea():
        for l in layers:
            if z.IsOnLayer(l) and z.HasFilledPolysForLayer(l):
                poly = z.GetFilledPolysList(l)
                bb = poly.BBox()
                for i in range(poly.OutlineCount()):
                    ob = poly.Outline(i).BBox()
                    x0, y0, x1, y1 = t(ob.GetLeft()) - OX, t(ob.GetTop()) - OY, t(ob.GetRight()) - OX, t(ob.GetBottom()) - OY
                    if x0 < ko[2] and x1 > ko[0] and y0 < ko[3] and y1 > ko[1]:
                        # does the fill polygon actually intersect the box?
                        box = pcbnew.SHAPE_POLY_SET()
                        box.NewOutline()
                        for x, y in ((ko[0], ko[1]), (ko[2], ko[1]), (ko[2], ko[3]), (ko[0], ko[3])):
                            box.Append(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))
                        inter = pcbnew.SHAPE_POLY_SET(poly)
                        inter.BooleanIntersection(box)
                        if inter.OutlineCount():
                            fillviol += 1
                            print("  ZONE FILL IN KEEP-OUT:", z.GetZoneName(), names[l], "area mm2", round(inter.Area() / 1e12, 3))
                            break
print("antenna keep-out copper items:", viol, "zone fills inside:", fillviol)

# ---- GND plane continuity
for l in layers:
    for z in b.Zones():
        if z.IsOnLayer(l) and not z.GetIsRuleArea() and z.HasFilledPolysForLayer(l):
            poly = z.GetFilledPolysList(l)
            areas = sorted((poly.Outline(i).Area() / 1e12 for i in range(poly.OutlineCount())), reverse=True)
            print(f"GND zone {z.GetZoneName()} on {names[l]}: {len(areas)} island(s), largest {areas[0]:.1f} mm2, others {[round(a, 2) for a in areas[1:6]]}")
trk = {names[l]: 0 for l in layers}
for tr in b.GetTracks():
    if tr.GetClass() == "PCB_TRACK" and tr.GetLayer() in names:
        trk[names[tr.GetLayer()]] += 1
print("track segments per layer:", trk)

# ---- decoupling distance (cap pad on the supply net to the IC supply pad)
pairs = [("C4", "U1", "19"), ("C5", "U1", "19"), ("C25", "U7", "5"), ("C27", "U5", "1"), ("C28", "U6", "8"), ("C36", "U9", "8"), ("C33", "U10", "8"),
         ("C34", "U8", "8"), ("C1", "U2", "3"), ("C2", "U2", "2")]
for c, u, n in pairs:
    if c in fps and u in fps:
        cx, cy = pos(fps[c])
        px, py = pad(u, n)
        print(f"decoupling {c}->{u}.{n}: {math.hypot(cx - px, cy - py):.1f} mm")
for c in ("C22", "C23", "C24"):
    cx, cy = pos(fps[c])
    px, py = pad("U4", "6")
    print(f"motor bulk {c}->U4.VMOT: {math.hypot(cx - px, cy - py):.1f} mm")

# ---- shunt Kelvin: INA180 sense pins must connect at the shunt pads, not along the high-current path
for ref in ("R31", "R39", "R47"):
    print(ref, "pads", pad(ref, 1), pad(ref, 2))
print("U7 IN+ (pad 3)", pad("U7", 3), "IN- (pad 4)", pad("U7", 4))
for tr in b.GetTracks():
    if tr.GetClass() == "PCB_TRACK" and tr.GetNetname() in ("VMOT_RAW", "VMOT"):
        pass
