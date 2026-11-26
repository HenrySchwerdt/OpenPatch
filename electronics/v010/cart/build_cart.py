#!/usr/bin/env python3
"""Build cart/cart.kicad_pcb from netlist_cart.json + placement.json (KiCad python).  usage: kpy build_cart.py [placement.json]

TEST PROJECT, water only. 4 layers (OP_LAYERS=6 for the fallback), 0.8 mm, outline = cartgeom.OUTLINE (57.0 x 10.6, USB-C notch).
Stack (4 L): F.Cu signal / parts, In1 GND plane, In2 signal + power, B.Cu signal / parts; GND pour on every layer after routing.
Rules (JLC 4 L standard, no extra-cost options): track / space 0.10 / 0.10, vias 0.40 / 0.20 (no 0.15 mm drills, pre-order review M8),
4 layers: no via in any pad, HJ-840 ring-2 pads get a dog-bone via at the interstitial point (0.105 mm to the four pads);
6 layers (the routed board): filled + capped vias in the HJ-840 ring >= 1 pads and in the USB D- pads A7 / B7 (POFV), copper to edge 0.20 (0.30 router keep-out band), power nets 0.30 mm (pre-order review M5).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "..", "bench", "tools"))
sys.path.insert(0, os.path.join(ROOT, "cup"))
sys.path.insert(0, HERE)
import pcbnew  # noqa: E402
import benchlib as bl  # noqa: E402
from benchlib import Board, write_project  # noqa: E402
from place_cup import xf  # noqa: E402
import cartgeom as G  # noqa: E402

MM = bl.MM
T = pcbnew.ToMM
V010FP = os.path.join(ROOT, "footprints", "V010.pretty")
_orig = Board.load_fp


def _load(self, lib, nm):
    if lib == "V010":
        return pcbnew.FootprintLoad(V010FP, nm)
    return _orig(self, lib, nm)


Board.load_fp = _load
LAYERS = int(os.environ.get("OP_LAYERS", "4"))
bl.TRACK, bl.CLEAR, bl.VIA_D, bl.VIA_H = 0.10, 0.10, 0.40, 0.20
POWERNETS = ("VCELL", "VBAT", "VMOT", "VMOT_PRE", "BST_SW")           # cell -> boost -> load switch -> drivers: 0.30 mm (review M5)
POWER_W = 0.30
MOTORNETS = ("MOT_A1", "MOT_A2", "MOT_B1", "MOT_B2")                  # coil phases (NFP-608, about 0.1-0.2 A): 0.20 mm
MOTOR_W = 0.20
# 6 layers: JLC fills and caps vias in pads at no extra cost (POFV, pre-order review M8), so the HJ-840 ring >= 1 pads and the two USB D-
# pads (A7 / B7, D+ / D- alternate in the pad row) get a via in the pad, as on the cup board; 4 layers: dog-bones, no via in any pad
POFV = os.environ.get("OP_POFV", "1" if LAYERS == 6 else "0") == "1"
NAME = os.environ.get("OP_NAME", "cart")
PCB = os.path.join(HERE, NAME + ".kicad_pcb")
# HJ-840 dog-bone vias: used ring-2/3 pad -> interstitial point (footprint frame, y down; rows 0.9, columns 0.65)
DOGBONE = {"C3": (-1.30, -1.80), "F3": (-1.30, 0.90), "F4": (-0.65, 1.80), "F5": (0.65, 1.80), "C4": (-0.65, -0.90), "C6": (0.65, -0.90), "D3": (-1.30, -0.90),
           "D6": (1.30, -0.90), "E3": (-1.30, 0.0), "E6": (1.30, 0.0), "F3b": (-1.30, 1.80)}


def via(b, pos, net, d=0.40, h=0.20):
    v = pcbnew.PCB_VIA(b.b); v.SetPosition(pos); v.SetNet(net); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(MM(d)); v.SetDrill(MM(h)); b.b.Add(v)
    return v


def trk(b, a, c, net, w, layer=pcbnew.F_Cu):
    t = pcbnew.PCB_TRACK(b.b); t.SetStart(a); t.SetEnd(c); t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(net); b.b.Add(t)


def ring(pad):
    r = "ABCDEFGH".index(pad[0]); c = int(pad[1:])
    return min(r, 7 - r, c - 1, 8 - c)


def u1_fanout(b, fps):
    """ring 0 / 1 pads escape on F.Cu (router); ring >= 2 pads get a dog-bone; A7-A8 antenna bridge; A1 / H8 GND stubs to a via
    outside the pad field (A1: west, just outside the antenna zone)."""
    u1 = fps["U1"]
    pads = {pd.GetNumber(): pd for pd in u1.Pads()}
    st = (T(u1.GetPosition().x) - bl.OX, T(u1.GetPosition().y) - bl.OY, 270, "F")
    n = 0
    for num, pd in pads.items():
        if not pd.GetNetname() or num in ("A1", "A7", "A8", "H8") or ring(num) < (1 if POFV else 2):
            continue
        if POFV:                    # filled + capped via in the pad (JLC POFV, standard on 6 layers): the inner layers do the escape
            via(b, pd.GetPosition(), pd.GetNet()); n += 1
            continue
        lx, ly = DOGBONE[num]
        dx, dy = xf(lx, ly, st[2], st[3])
        p = pcbnew.VECTOR2I(MM(bl.OX + st[0] + dx), MM(bl.OY + st[1] + dy))
        trk(b, pd.GetPosition(), p, pd.GetNet(), 0.12)
        via(b, p, pd.GetNet()); n += 1
    trk(b, pads["A7"].GetPosition(), pads["A8"].GetPosition(), pads["A7"].GetNet(), 0.25)
    a1 = pads["A1"].GetPosition()
    corner = pcbnew.VECTOR2I(a1.x, a1.y - MM(0.55))
    gv = pcbnew.VECTOR2I(a1.x - MM(1.15), a1.y - MM(0.55))      # bx 53.5: 0.5 mm west of the antenna zone
    trk(b, a1, corner, pads["A1"].GetNet(), 0.2); trk(b, corner, gv, pads["A1"].GetNet(), 0.2)
    via(b, gv, pads["A1"].GetNet())
    h8 = pads["H8"].GetPosition()
    hv = pcbnew.VECTOR2I(h8.x - MM(0.70), h8.y)
    trk(b, h8, hv, pads["H8"].GetNet(), 0.2)
    via(b, hv, pads["H8"].GetNet())
    return n


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
    a = G.ANT
    rule_area(b, "ANT_KEEPOUT", lset(cu[1:]), (a[0], -1.0, a[2] + 0.5, a[3] + 0.5))
    rule_area(b, "ANT_NOPOUR_F", lset([pcbnew.F_Cu]), (a[0], -1.0, a[2] + 0.5, a[3] + 0.5), tracks=False, vias=False)
    for k, (y0, y1) in enumerate(((-1.0, 2.2), (3.3, 6.6), (7.9, a[3] + 0.5))):     # F.Cu corridors: A1 stub (by 2.2..3.3), A7-A8 bridge
        rule_area(b, "ANT_KEEPOUT_F%d" % k, lset([pcbnew.F_Cu]), (a[0], y0, a[2] + 0.5, y1))
    # edge band 0.30 mm on every copper layer (Freerouting does not know the 0.2 mm copper-to-edge rule)
    poly, BAND = G.OUTLINE, 0.30
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
        dx, dy = x1 - x0, y1 - y0
        Ls = math.hypot(dx, dy)
        ux, uy = dx / Ls, dy / Ls
        nx, ny = -uy, ux
        if not G.pip((x0 + x1) / 2 + nx * 0.05, (y0 + y1) / 2 + ny * 0.05, poly):
            nx, ny = -nx, -ny
        e = BAND if Ls > 0.2 else 0.05
        pts = [(x0 - ux * e - nx * 0.2, y0 - uy * e - ny * 0.2), (x1 + ux * e - nx * 0.2, y1 + uy * e - ny * 0.2),
               (x1 + ux * e + nx * BAND, y1 + uy * e + ny * BAND), (x0 - ux * e + nx * BAND, y0 - uy * e + ny * BAND)]
        rule_area(b, "EDGE_KEEPOUT_%d" % i, lset(cu), poly=pts, fills=False)


def gnd_fanout(b, fps, rv=0.2, trk_w=0.12, clr=0.11):
    """short stub + via next to every SMD GND pad (In1 is the GND plane), so the router leaves GND alone"""
    pads = [(f, pd) for f in fps.values() for pd in f.Pads()]
    boxes = []
    for f, pd in pads:
        bb = pd.GetBoundingBox()
        boxes.append((T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom()), pd))
    vias = [(T(v.GetPosition().x), T(v.GetPosition().y)) for v in b.b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]
    tracks = [t for t in b.b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]

    def clear_of_pads(x, y, own, r):
        return not any(q is not own and math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1)) < r for x0, y0, x1, y1, q in boxes)
    n = 0
    for f, pd in pads:
        if pd.GetNetname() != "GND" or pd.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or f.GetReference() in ("U1", "JU1"):
            continue
        if f.GetReference().startswith(("TL", "LK", "TPR", "SP", "MP")):
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
                if G.ANT[0] - 0.3 < bx:
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
    ax, ay, cx, cy = T(a.x), T(a.y), T(c.x), T(c.y)
    return G.seg_dist(x, y, (ax, ay), (cx, cy))


def main():
    plf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "placement.json")
    parts = json.load(open(os.path.join(HERE, "netlist_cart.json")))
    pl = json.load(open(plf))
    b = Board(NAME, G.L, G.W, layers=LAYERS)
    b.b.GetDesignSettings().SetBoardThickness(MM(G.BOARD_T))
    b.poly_outline(G.OUTLINE)
    for p in parts:
        ref = p["ref"]
        x, y, rot, side = pl[ref]
        f = b.add(ref, p["value"], tuple(p["fp"]), x, y, 0, side=side, pins={k: v for k, v in p["pins"].items() if v}, lcsc=p["lcsc"], mpn=p["mpn"],
                  bom=p["bom"], note=p["note"], hide_ref=True)
        f.SetOrientationDegrees(rot if side == "F" else (rot + 180) % 360)
        b.parts[ref].update(dnp=p["dnp"], group=p["group"], board="CART")
    fps = {f.GetReference(): f for f in b.b.GetFootprints()}
    keepouts(b)
    print("U1 fan-out vias:", u1_fanout(b, fps), "(in pad)" if POFV else "(dog-bone)")
    if POFV:
        for pd in fps["JU1"].Pads():
            if pd.GetNumber() in ("A7", "B7"):
                via(b, pd.GetPosition(), pd.GetNet())
    print("gnd fanout vias:", gnd_fanout(b, fps) if os.environ.get("OP_FANOUT", "1") == "1" else "skipped")
    for ref, lab in (("SP1", "+"), ("SP2", "-")):
        c = fps[ref].GetPosition(); b.text(lab, T(c.x) - bl.OX + 1.45, T(c.y) - bl.OY, 1.2, thick=0.2)
    for ref, lab in (("MP1", "A+"), ("MP2", "A-"), ("MP3", "B+"), ("MP4", "B-")):
        c = fps[ref].GetPosition(); b.text(lab, T(c.x) - bl.OX + 1.75, T(c.y) - bl.OY, 0.7, thick=0.12)
    for ref, lab in (("TL1", "T3V3"), ("TL2", "TGND"), ("TL3", "SDA"), ("TL4", "SCL"), ("LK1", "L3V3"), ("LK2", "LGND"), ("LK3", "LOCK")):
        c = fps[ref].GetPosition(); b.text(lab, T(c.x) - bl.OX + 1.75, T(c.y) - bl.OY, 0.6, layer=pcbnew.B_SilkS, mirror=True, thick=0.1)
    b.text("TEST ONLY - NOT FOR HUMAN USE - WATER ONLY", 40.0, 9.9, 0.5, layer=pcbnew.B_SilkS, mirror=True, thick=0.08)
    b.text("OPENPATCH CART v0.1", 23.0, 0.6, 0.5, thick=0.08)
    b.rules(power_nets=POWERNETS, power_w=POWER_W, track=0.10)
    ns = b.b.GetDesignSettings().m_NetSettings
    mc = pcbnew.NETCLASS("Motor")
    mc.SetClearance(MM(0.10)); mc.SetTrackWidth(MM(MOTOR_W)); mc.SetViaDiameter(MM(0.40)); mc.SetViaDrill(MM(0.20))
    ns.SetNetclass("Motor", mc)
    for n in MOTORNETS:
        ns.SetNetclassPatternAssignment(n, "Motor")
    # full (not thermal) zone connection where the spokes starve: USB shield tabs (slots in a narrow web), ESD GND pin
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
        lf = pcbnew.FootprintLoad(V010FP, p["fp"][1]) if p["fp"][0] == "V010" else Board.load_fp(b, *p["fp"])
        lp = [q for q in lf.Pads() if q.GetNumber() == pd.GetNumber()][0]
        ex, ey = xf(T(lp.GetPosition().x), T(lp.GetPosition().y), st[2], st[3])
        ax, ay = T(pd.GetPosition().x) - bl.OX, T(pd.GetPosition().y) - bl.OY
        if abs(ax - (st[0] + ex)) > 0.02 or abs(ay - (st[1] + ey)) > 0.02:
            bad += 1
            print("TRANSFORM MISMATCH", ref, st, (round(ax, 2), round(ay, 2)), (round(st[0] + ex, 2), round(st[1] + ey, 2)))
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
