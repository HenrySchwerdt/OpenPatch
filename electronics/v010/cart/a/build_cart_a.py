#!/usr/bin/env python3
"""Build cart/a/<OP_NAME>.kicad_pcb from netlist_cart_a.json + placement.json (KiCad python).  usage: kpy build_cart_a.py [placement.json]

TEST PROJECT, water only. Copy of ../build_cart.py (B) for the A outline (cartgeom_a.OUTLINE) and the A antenna wing; same rules as B:
4 layers (OP_LAYERS=6 for the fallback), 0.8 mm, F.Cu signal / parts, In1 GND plane, In2 signal + power, B.Cu signal / parts, GND pour on
every layer after routing; track / space 0.10 / 0.10, vias 0.40 / 0.20, cell -> boost -> load switch -> drivers 0.30 mm (pre-order review
M5), motor phases 0.20 mm, copper to edge 0.20 (0.30 router band). 4 layers: no via in any pad, HJ-840 ring-2 pads get a dog-bone via at
the interstitial point; 6 layers: filled + capped vias in the HJ-840 ring >= 1 pads (POFV) as on B.
Antenna (cartgeom_a.ANT): module x range, from 1.0 mm inside the A end to the wing edge: no copper on In1 / In2 / B.Cu, no pour on F.Cu,
F.Cu tracks only in the A1 GND stub corridor and the A7-A8 bridge corridor (as B).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "..", "bench", "tools"))
sys.path.insert(0, os.path.join(ROOT, "cup"))
sys.path.insert(0, HERE)
import pcbnew  # noqa: E402
import benchlib as bl  # noqa: E402
from benchlib import Board, write_project  # noqa: E402
from place_cup import xf  # noqa: E402
import cartgeom_a as G  # noqa: E402

MM = bl.MM
T = pcbnew.ToMM
V010FP = os.path.join(ROOT, "footprints", "V010.pretty")
CARTA = os.path.join(HERE, "CARTA.pretty")
_orig = Board.load_fp


def _load(self, lib, nm):
    if lib == "V010":
        return pcbnew.FootprintLoad(V010FP, nm)
    if lib == "CARTA":
        return pcbnew.FootprintLoad(CARTA, nm)
    return _orig(self, lib, nm)


Board.load_fp = _load
LAYERS = int(os.environ.get("OP_LAYERS", "4"))
bl.TRACK, bl.CLEAR, bl.VIA_D, bl.VIA_H = 0.10, 0.10, 0.40, 0.20
POWERNETS = ("VCELL", "VBAT", "VMOT", "VMOT_PRE", "BST_SW")
POWER_W = 0.30
MOTORNETS = ("MOT_A1", "MOT_A2", "MOT_B1", "MOT_B2")
MOTOR_W = 0.20
POFV = os.environ.get("OP_POFV", "1" if LAYERS == 6 else "0") == "1"
NAME = os.environ.get("OP_NAME", "cart_a")
PCB = os.path.join(HERE, NAME + ".kicad_pcb")
# HJ-840 dog-bone vias: used ring-2/3 pad -> interstitial point (footprint frame, y down; rows 0.9, columns 0.65); as B
DOGBONE = {"C3": (-1.30, -1.80), "F3": (-1.30, 0.90), "F4": (-0.65, 1.80), "F5": (0.65, 1.80), "C4": (-0.65, -0.90), "C6": (0.65, -0.90),
           "D3": (-1.30, -0.90), "D6": (1.30, -0.90), "E3": (-1.30, 0.0), "E6": (1.30, 0.0), "D4": (-0.65, -0.90), "E4": (-0.65, 0.90),
           "D5": (0.65, -0.90), "E5": (0.65, 0.90), "C5": (0.65, -1.80), "F6": (1.30, 0.90)}
# A1 GND stub: west out of the module to a via 0.05 mm outside the antenna keep-out; H8: east to a via outside the module
A1_PATH = [(54.20, 38.41), (53.95, 38.16), (53.95, 37.60)]     # stays >= 0.3 from the wing edge (router band)
A1_VIA = A1_PATH[-1]
H8_VIA = (60.25, 32.11)


def via(b, pos, net, d=0.40, h=0.20):
    v = pcbnew.PCB_VIA(b.b); v.SetPosition(pos); v.SetNet(net); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(MM(d)); v.SetDrill(MM(h)); b.b.Add(v)
    return v


def trk(b, a, c, net, w, layer=pcbnew.F_Cu):
    t = pcbnew.PCB_TRACK(b.b); t.SetStart(a); t.SetEnd(c); t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(net); b.b.Add(t)


def pv(x, y):
    """pump coordinates -> KiCad VECTOR2I"""
    bx, by = G.b(x, y)
    return pcbnew.VECTOR2I(MM(bl.OX + bx), MM(bl.OY + by))


def ring(pad):
    r = "ABCDEFGH".index(pad[0]); c = int(pad[1:])
    return min(r, 7 - r, c - 1, 8 - c)


def u1_fanout(b, fps, st):
    """ring 0 / 1 pads escape on F.Cu (router); ring >= 2 pads get a dog-bone; A7-A8 antenna bridge; A1 / H8 GND stubs to vias outside
    the module (A1: just outside the antenna keep-out)"""
    u1 = fps["U1"]
    pads = {pd.GetNumber(): pd for pd in u1.Pads()}
    n = 0
    for num, pd in pads.items():
        if not pd.GetNetname() or num in ("A1", "A7", "A8", "H8") or ring(num) < (1 if POFV else 2):
            continue
        if POFV:
            via(b, pd.GetPosition(), pd.GetNet()); n += 1
            continue
        lx, ly = DOGBONE[num]
        dx, dy = xf(lx, ly, st[2], st[3])
        p = pcbnew.VECTOR2I(MM(bl.OX + st[0] + dx), MM(bl.OY + st[1] + dy))
        trk(b, pd.GetPosition(), p, pd.GetNet(), 0.12)
        via(b, p, pd.GetNet()); n += 1
    trk(b, pads["A7"].GetPosition(), pads["A8"].GetPosition(), pads["A7"].GetNet(), 0.25)
    pts = [pads["A1"].GetPosition()] + [pv(*q) for q in A1_PATH]
    for p0, p1 in zip(pts, pts[1:]):
        trk(b, p0, p1, pads["A1"].GetNet(), 0.2)
    via(b, pv(*A1_VIA), pads["A1"].GetNet())
    trk(b, pads["H8"].GetPosition(), pv(*H8_VIA), pads["H8"].GetNet(), 0.2)
    via(b, pv(*H8_VIA), pads["H8"].GetNet())
    return n


def usb_fanout(b, fps):
    """4 layers (no via in pad): the USB-C data pads alternate D+ / D- at 0.5 mm pitch (B6 D+, A7 D-, A6 D+, B7 D-); D+ is joined on
    F.Cu 1.78 mm below the pad row, D- drops into a via under each pad and is joined on B.Cu between the two vias (fixed copper)."""
    pads = {pd.GetNumber(): pd for pd in fps["JU1"].Pads()}
    yp = G.USB_MOUTH_Y - 8.02                   # pad row centre (pump y)
    yj, yv = yp - 1.78, yp - 1.18               # D+ join line, D- via row
    xs = {n: G.USB_X + dx for n, dx in (("B6", -0.75), ("A7", -0.25), ("A6", 0.25), ("B7", 0.75))}
    dp, dm = pads["A6"].GetNet(), pads["A7"].GetNet()
    for n in ("B6", "A6"):
        trk(b, pv(xs[n], yp), pv(xs[n], yj), dp, 0.12)
    trk(b, pv(xs["B6"], yj), pv(xs["A6"], yj), dp, 0.12)
    for n in ("A7", "B7"):
        trk(b, pv(xs[n], yp), pv(xs[n], yv), dm, 0.12)
        via(b, pv(xs[n], yv), dm)
    trk(b, pv(xs["A7"], yv), pv(xs["B7"], yv), dm, 0.12, pcbnew.B_Cu)


def mot_fanout(b, fps):
    """motor header J2 (bottom): its signal pads sit at 1.25 mm pitch with 0.45 mm gaps (no via fits between them), so each phase gets a
    via 0.35 mm west of its pad (under the J2 housing) and a 0.20 mm B.Cu stub; the drivers on the top reach the vias (router)."""
    vias = {}
    for pd in fps["J2"].Pads():
        if pd.GetNumber() not in ("1", "2", "3", "4"):
            continue
        x, y = T(pd.GetPosition().x), T(pd.GetPosition().y)
        bb = pd.GetBoundingBox()
        if POFV:                                                  # filled + capped via in the pad, 0.25 from its -x end
            xv = min(T(bb.GetLeft()), T(bb.GetRight())) + 0.25
        else:
            xv = min(T(bb.GetLeft()), T(bb.GetRight())) - 0.55  # pad edge toward -x (the opening side) minus via radius + 0.35
        pv_ = pcbnew.VECTOR2I(MM(xv), MM(y))
        via(b, pv_, pd.GetNet())
        if not POFV:
            trk(b, pv_, pd.GetPosition(), pd.GetNet(), MOTOR_W, pcbnew.B_Cu)
        vias[pd.GetNetname()] = G.p(xv - bl.OX, y - bl.OY)
    if POFV:
        drv_fanout(b, fps, vias)


def drv_fanout(b, fps, jv):
    """POFV boards: the two DRV8838 (rot 0, outputs on their -x column) reach the J2 vias on F.Cu along fixed, non-crossing paths:
    the output nearer the J2 via row turns first (inner path), VMOT (pin 1) and GND (pin 4) drop into filled vias in their pads so
    nothing else leaves that column. U7A: J2 vias above (+y), U7B: below (-y)."""
    for ref, s, inner, outer in (("U7A", 1, "2", "3"), ("U7B", -1, "3", "2")):
        pads = {pd.GetNumber(): pd for pd in fps[ref].Pads()}
        pp = {n: G.p(T(pd.GetPosition().x) - bl.OX, T(pd.GetPosition().y) - bl.OY) for n, pd in pads.items() if n}
        for n in ("1", "4"):                                    # VMOT, GND: via in the pad, at its outer end
            if ref == "U7B" and n == "1":
                continue                                        # under J2's mounting tab (bottom): VMOT leaves on F.Cu, below
            via(b, pv(pp[n][0] - 0.15, pp[n][1]), pads[n].GetNet())
        if ref == "U7B":                                        # VMOT: straight up 0.45, east over the driver to a via beyond J2's tab
            x1, y1 = pp["1"]                                    # (keeps the strip under the supervisor's south pin row free)
            xv = x1 + 0.8
            pts = [(x1, y1), (x1, y1 + 0.45), (xv, y1 + 0.45)]
            for a, c in zip(pts, pts[1:]):
                trk(b, pv(*a), pv(*c), pads["1"].GetNet(), POWER_W)
            via(b, pv(xv, y1 + 0.45), pads["1"].GetNet())
        for n, dx in ((inner, 0.6), (outer, 1.0)):
            net = pads[n].GetNet()
            xv, yv = jv[pads[n].GetNetname()]
            x0, y0 = pp[n]
            pts = [(x0, y0), (x0 - dx, y0), (x0 - dx, yv - s * 0.28), (x0 - dx + 0.28, yv), (xv, yv)]
            for a, c in zip(pts, pts[1:]):
                trk(b, pv(*a), pv(*c), net, MOTOR_W)


# POFV boards: middle pins of the fine-pitch parts (a signal pad with a neighbour pad on both sides) are walled in once their neighbours
# are routed; each gets a filled via at the outer end of its pad (routing runs showed U8.2 / U34.2 left open on 4 and 6 layers)
MID_PADS = [("U8", "2"), ("U34", "2"), ("U33", "2"), ("U32", "2"), ("U36", "5"), ("U5", "5"), ("U6", "2"), ("U6", "6"), ("U6", "7"),
            ("UU1", "5"), ("U20", "2")]


def pad_vias(b, fps, targets=MID_PADS, rv=0.2, clr=0.1):
    """filled via at the outer end of each listed pad, if it keeps clr to every other-net pad (any layer) and hole clearance"""
    allpads = [(f, pd) for f in fps.values() for pd in f.Pads()]
    vias = [(T(v.GetPosition().x), T(v.GetPosition().y), v.GetNetCode()) for v in b.b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]
    done, skipped = 0, []
    for ref, num in targets:
        f = fps[ref]
        pd = [p for p in f.Pads() if p.GetNumber() == num][0]
        cx, cy = T(f.GetPosition().x), T(f.GetPosition().y)
        px, py = T(pd.GetPosition().x), T(pd.GetPosition().y)
        sx, sy = T(pd.GetBoundingBox().GetWidth()), T(pd.GetBoundingBox().GetHeight())
        ux, uy = px - cx, py - cy
        if abs(ux) >= abs(uy):                          # pad row along y: outward is +-x
            x, y = px + math.copysign(max(sx / 2 - rv, 0.0), ux), py
        else:
            x, y = px, py + math.copysign(max(sy / 2 - rv, 0.0), uy)
        def free(x, y, r, layers=(pcbnew.F_Cu, pcbnew.B_Cu), hole=True):
            c = pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(MM(x), MM(y)), MM(r))
            for g, q in allpads:
                if q.GetNetCode() == pd.GetNetCode() and q.GetNetCode() > 0:
                    continue
                for lay in layers:
                    if q.IsOnLayer(lay) and q.GetEffectiveShape(lay).Collide(c, MM(clr)):
                        return False
                if hole and q.GetDrillSizeX() > 0 and math.hypot(T(q.GetPosition().x) - x, T(q.GetPosition().y) - y) < T(q.GetDrillSizeX()) / 2 + 0.1 + 0.25:
                    return False
            if hole and any(math.hypot(vx - x, vy - y) < 2 * rv + clr and vn != pd.GetNetCode() for vx, vy, vn in vias):
                return False
            bx, by = x - bl.OX, y - bl.OY
            return G.inside([bx - r, by - r, bx + r, by + r], G.OUTLINE, 0.32) and not in_ant(bx, by)
        layer = pcbnew.B_Cu if f.GetSide() == pcbnew.B_Cu else pcbnew.F_Cu
        if free(x, y, rv):
            via(b, pcbnew.VECTOR2I(MM(x), MM(y)), pd.GetNet())
            vias.append((x, y, pd.GetNetCode())); done += 1
            continue
        # no room in the pad (the other face has a part there): short stub outward to a via
        n = math.hypot(ux, uy) or 1.0
        ox, oy = (math.copysign(1.0, ux), 0.0) if abs(ux) >= abs(uy) else (0.0, math.copysign(1.0, uy))
        hit = None
        for d in (0.6, 0.75, 0.9, 1.1, 1.3):
            for ang in (0, 25, -25, 45, -45):
                ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                dx, dy = ox * ca - oy * sa, ox * sa + oy * ca
                L = (sx / 2 if ox else sy / 2) + d - 0.2          # via centre beyond the pad's outer end
                x2, y2 = px + dx * L, py + dy * L
                if not free(x2, y2, rv):
                    continue
                if all(free(px + t * (x2 - px), py + t * (y2 - py), 0.06, (layer,), hole=False) for t in (0.4, 0.6, 0.8)):
                    hit = (x2, y2)
                    break
            if hit:
                break
        if not hit:
            skipped.append("%s.%s" % (ref, num))
            continue
        q2 = pcbnew.VECTOR2I(MM(hit[0]), MM(hit[1]))
        trk(b, pd.GetPosition(), q2, pd.GetNet(), 0.12, layer)
        via(b, q2, pd.GetNet())
        vias.append((hit[0], hit[1], pd.GetNetCode())); done += 1
    print("pad vias / stubs:", done, "skipped (no room):", skipped)


def rule_area(b, name, layers, rect=None, poly=None, tracks=True, vias=True, fills=True):
    z = pcbnew.ZONE(b.b); z.SetIsRuleArea(True); z.SetZoneName(name)
    z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(vias); z.SetDoNotAllowZoneFills(fills); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    z.SetLayerSet(layers)
    ch = z.Outline(); ch.NewOutline()
    pts = poly or ((rect[0], rect[1]), (rect[2], rect[1]), (rect[2], rect[3]), (rect[0], rect[3]))
    for x, y in pts:
        ch.Append(MM(bl.OX + x), MM(bl.OY + y))
    b.b.Add(z)


def lset(layers):
    s = pcbnew.LSET()
    for l in layers:
        s.AddLayer(l)
    return s


def copper(b):
    return [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu] + ([pcbnew.In3_Cu, pcbnew.In4_Cu] if LAYERS == 6 else []) + [pcbnew.B_Cu]


def keepouts(b):
    cu = copper(b)
    a = G.ANT                                     # board frame [x0, y0 (beyond the edge), x1, y1 (1.0 mm inside the module)]
    rule_area(b, "ANT_KEEPOUT", lset(cu[1:]), a)
    rule_area(b, "ANT_NOPOUR_F", lset([pcbnew.F_Cu]), a, tracks=False, vias=False)
    ya = G.Y1 - 38.41                             # row A pad centres (board frame)
    x_a1 = G.b(55.4, 0)[0]; x_a7 = G.b(58.7, 0)[0]; x_a8 = G.b(59.8, 0)[0]
    for k, r in enumerate(((a[0], a[1], a[2], ya - 0.42), (a[0], ya + 0.42, a[2], a[3]), (x_a1, ya - 0.42, x_a7, ya + 0.42),
                           (x_a8, ya - 0.42, a[2], ya + 0.42))):
        rule_area(b, "ANT_KEEPOUT_F%d" % k, lset([pcbnew.F_Cu]), r)
    # edge band 0.30 mm on every copper layer (Freerouting does not know the 0.2 mm copper-to-edge rule)
    poly, BAND = G.OUTLINE, 0.30
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
        dx, dy = x1 - x0, y1 - y0
        Ls = math.hypot(dx, dy)
        if Ls < 1e-6:
            continue
        ux, uy = dx / Ls, dy / Ls
        nx, ny = -uy, ux
        if not G.pip((x0 + x1) / 2 + nx * 0.05, (y0 + y1) / 2 + ny * 0.05, poly):
            nx, ny = -nx, -ny
        e = BAND if Ls > 0.2 else 0.05
        pts = [(x0 - ux * e - nx * 0.2, y0 - uy * e - ny * 0.2), (x1 + ux * e - nx * 0.2, y1 + uy * e - ny * 0.2),
               (x1 + ux * e + nx * BAND, y1 + uy * e + ny * BAND), (x0 - ux * e + nx * BAND, y0 - uy * e + ny * BAND)]
        rule_area(b, "EDGE_KEEPOUT_%d" % i, lset(cu), poly=pts, fills=False)


def in_ant(bx, by, m=0.3):
    a = G.ANT
    return a[0] - m < bx < a[2] + m and a[1] - m < by < a[3] + m


def gnd_fanout(b, fps, rv=0.2, trk_w=0.12, clr=0.11):
    """short stub + via next to every SMD GND pad (In1 is the GND plane), so the router leaves GND alone"""
    pads = [(f, pd) for f in fps.values() for pd in f.Pads()]
    boxes = []
    for f, pd in pads:
        bb = pd.GetBoundingBox()
        boxes.append((T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom()), pd))
    for f in fps.values():                         # NPTH holes too (SW2 location lugs, USB pegs)
        for pd in f.Pads():
            if pd.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                bb = pd.GetBoundingBox()
                boxes.append((T(bb.GetLeft()) - 0.1, T(bb.GetTop()) - 0.1, T(bb.GetRight()) + 0.1, T(bb.GetBottom()) + 0.1, None))
    vias = [(T(v.GetPosition().x), T(v.GetPosition().y)) for v in b.b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]
    tracks = [t for t in b.b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]

    def clear_of_pads(x, y, own, r):
        return not any(q is not own and math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1)) < r for x0, y0, x1, y1, q in boxes)
    n = 0
    for f, pd in pads:
        if pd.GetNetname() != "GND" or pd.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or f.GetReference() in ("U1", "JU1"):
            continue
        if f.GetReference().startswith(("TPR",)):
            continue
        px, py = T(pd.GetPosition().x), T(pd.GetPosition().y)
        if any(math.hypot(vx - px, vy - py) < 0.9 for vx, vy in vias):
            continue
        layer = pcbnew.B_Cu if f.GetSide() == pcbnew.B_Cu else pcbnew.F_Cu
        done = False
        for d in (0.45, 0.55, 0.7, 0.9, 1.1, 1.4):
            for k in range(16):
                a = k * math.pi / 8
                x, y = px + d * math.cos(a), py + d * math.sin(a)
                if not clear_of_pads(x, y, pd, rv + clr):
                    continue
                if any(math.hypot(vx - x, vy - y) < 2 * rv + clr + 0.1 for vx, vy in vias):
                    continue
                if not all(clear_of_pads(px + t * (x - px), py + t * (y - py), pd, trk_w / 2 + clr) for t in (0.25, 0.5, 0.75)):
                    continue
                bx, by = x - bl.OX, y - bl.OY
                if not G.inside([bx - rv, by - rv, bx + rv, by + rv], G.OUTLINE, 0.32):
                    continue
                if in_ant(bx, by):
                    continue
                if any(t.GetNetname() != "GND" and _seg_d(x, y, t) < rv + clr + T(t.GetWidth()) / 2 for t in tracks):
                    continue
                p = pcbnew.VECTOR2I(MM(x), MM(y))
                via(b, p, pd.GetNet())
                trk(b, pd.GetPosition(), p, pd.GetNet(), trk_w, layer)
                vias.append((x, y)); n += 1; done = True
                break
            if done:
                break
    return n


def _seg_d(x, y, t):
    a, c = t.GetStart(), t.GetEnd()
    return G.seg_dist(x, y, (T(a.x), T(a.y)), (T(c.x), T(c.y)))


def silk(b):
    def t(txt, x, y, size, layer=pcbnew.F_SilkS, rot=0.0, thick=0.08):
        bx, by = G.b(x, y)
        b.text(txt, bx, by, size, layer=layer, rot=rot, mirror=(layer == pcbnew.B_SilkS), thick=thick)
    # underside, in the free motor-plug zone (x 41.6-48.2, y 22.6-29.2): the safety marking and the motor pin order
    for k, line in enumerate(("TEST ONLY", "NOT FOR HUMAN USE", "WATER ONLY", "OPENPATCH CART-A")):
        t(line, 44.9, 28.4 - 0.75 * k, 0.45, pcbnew.B_SilkS)
    t("J2 1A+ 2A- 3B+ 4B-", 44.9, 23.4, 0.4, pcbnew.B_SilkS)
    t("CART-A TEST ONLY", 36.0, 28.55, 0.4)
    j3 = G.p(*json.load(open(os.path.join(HERE, "placement.json")))["J3"][:2])
    t("+", j3[0], j3[1] + 3.35, 1.0, pcbnew.B_SilkS, thick=0.18)     # contact 1 (VCELL) is the +y one, see place_cart_a.py
    t("-", j3[0], j3[1] - 3.35, 1.0, pcbnew.B_SilkS, thick=0.18)
    t("CELL", j3[0] - 2.35, j3[1], 0.5, pcbnew.B_SilkS, rot=90)


def main():
    plf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "placement.json")
    parts = json.load(open(os.path.join(HERE, "netlist_cart_a.json")))
    pl = json.load(open(plf))
    xs = [q[0] for q in G.OUTLINE]; ys = [q[1] for q in G.OUTLINE]
    b = Board(NAME, max(xs), max(ys), layers=LAYERS)
    b.b.GetDesignSettings().SetBoardThickness(MM(G.BOARD_T))
    b.poly_outline(G.OUTLINE)
    for p in parts:
        ref = p["ref"]
        x, y, rot, side = pl[ref]
        f = b.add(ref, p["value"], tuple(p["fp"]), x, y, 0, side=side, pins={k: v for k, v in p["pins"].items() if v}, lcsc=p["lcsc"], mpn=p["mpn"],
                  bom=p["bom"], note=p["note"], hide_ref=True)
        f.SetOrientationDegrees(rot if side == "F" else (rot + 180) % 360)
        b.parts[ref].update(dnp=p["dnp"], group=p["group"], board="CART_A")
    fps = {f.GetReference(): f for f in b.b.GetFootprints()}
    keepouts(b)
    print("U1 fan-out vias:", u1_fanout(b, fps, pl["U1"]), "(in pad)" if POFV else "(dog-bone)")
    if POFV:
        for pd in fps["JU1"].Pads():
            if pd.GetNumber() in ("A7", "B7"):
                via(b, pd.GetPosition(), pd.GetNet())
    else:
        usb_fanout(b, fps)
    mot_fanout(b, fps)
    if POFV:
        pad_vias(b, fps)
    print("gnd fanout vias:", gnd_fanout(b, fps) if os.environ.get("OP_FANOUT", "1") == "1" else "skipped")
    silk(b)
    b.rules(power_nets=POWERNETS, power_w=POWER_W, track=0.10)
    ns = b.b.GetDesignSettings().m_NetSettings
    mc = pcbnew.NETCLASS("Motor")
    mc.SetClearance(MM(0.10)); mc.SetTrackWidth(MM(MOTOR_W)); mc.SetViaDiameter(MM(0.40)); mc.SetViaDrill(MM(0.20))
    ns.SetNetclass("Motor", mc)
    for n in MOTORNETS:
        ns.SetNetclassPatternAssignment(n, "Motor")
    for ref, num in (("JU1", "S"), ("UU1", "2")):
        for pd in fps[ref].Pads():
            if pd.GetNumber() == num:
                pd.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    d = b.b.GetDesignSettings()
    d.m_CopperEdgeClearance = MM(0.2); d.m_MinThroughDrill = MM(0.2); d.m_ViasMinSize = MM(0.4); d.m_HoleToHoleMin = MM(0.25); d.m_TrackMinWidth = MM(0.1)
    bad = 0
    for p in parts:
        ref = p["ref"]; st = pl[ref]; f = fps[ref]
        pads = [pd for pd in f.Pads() if pd.GetNumber()]
        if not pads:
            continue
        pd = pads[0]
        lf = Board.load_fp(b, *p["fp"])
        lp = [q for q in lf.Pads() if q.GetNumber() == pd.GetNumber()]
        lp = min(lp, key=lambda q: 0)
        cands = [q for q in lf.Pads() if q.GetNumber() == pd.GetNumber()]
        ax, ay = T(pd.GetPosition().x) - bl.OX, T(pd.GetPosition().y) - bl.OY
        ok = False
        for q in cands:
            ex, ey = xf(T(q.GetPosition().x), T(q.GetPosition().y), st[2], st[3])
            if abs(ax - (st[0] + ex)) <= 0.02 and abs(ay - (st[1] + ey)) <= 0.02:
                ok = True
        if not ok:
            bad += 1
            print("TRANSFORM MISMATCH", ref, st, (round(ax, 2), round(ay, 2)))
    print("transform mismatches:", bad)
    b.save(PCB)
    json.dump(b.parts, open(os.path.join(HERE, "parts.json"), "w"), indent=1)
    write_project(os.path.join(HERE, NAME + ".kicad_pro"), POWERNETS, POWER_W, track=0.10, edge=0.2, clear=0.10)
    pj = os.path.join(HERE, NAME + ".kicad_pro"); dd = json.load(open(pj)); r = dd["board"]["design_settings"]["rules"]
    r.update(min_through_hole_diameter=0.2, min_via_diameter=0.4, min_track_width=0.1, min_hole_to_hole=0.25, min_hole_clearance=0.2, min_via_annular_width=0.1)
    cl = dd["net_settings"]["classes"]
    cl.append(dict(cl[0], name="Motor", track_width=MOTOR_W, priority=1))
    dd["net_settings"]["netclass_patterns"] += [{"netclass": "Motor", "pattern": n} for n in MOTORNETS]
    json.dump(dd, open(pj, "w"), indent=2)
    print(NAME, "written", len(b.parts), "parts,", LAYERS, "layers")


main()
