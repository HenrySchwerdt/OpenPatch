#!/usr/bin/env python3
"""Build cup/cup.kicad_pcb from netlist_v4_cup.json + placement.json (KiCad python).  usage: kpy build_cup.py [placement.json]

6 layers, 0.8 mm, outline = L/U shape (cupgeom.OUTLINE), ISP1807 via-in-pad fan-out, antenna keep-out, parts.json for the fab export."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "..", "bench", "tools"))
sys.path.insert(0, HERE)
import pcbnew
import benchlib as bl
from benchlib import Board, write_project
import cupgeom as G
from place_cup import xf

MM = bl.MM
T = pcbnew.ToMM
V010FP = os.path.join(ROOT, "footprints", "V010.pretty")
_orig = Board.load_fp


def _load(self, lib, nm):
    if lib == "V010":
        return pcbnew.FootprintLoad(V010FP, nm)
    return _orig(self, lib, nm)


Board.load_fp = _load
bl.TRACK, bl.CLEAR, bl.VIA_D, bl.VIA_H = 0.12, 0.10, 0.40, 0.20
POWERNETS = ("VBAT", "3V3", "VMOT", "VMOT_PRE", "BST_SW", "MOT_A1", "MOT_A2", "MOT_B1", "MOT_B2", "VBUS_P")
NAME = "cup"
PCB = os.path.join(HERE, NAME + ".kicad_pcb")


def isp_fanout(b, fps):
    u1 = fps["U1"]; n = 0
    outer = {1, 7, 25, 31, 2, 4, 6, 26, 28, 30} | set(range(32, 49, 2))
    for pd in u1.Pads():
        num = int(pd.GetNumber())
        net = pd.GetNet()
        if not net or net.GetNetname() in ("", "RF_BRIDGE") or num in outer or num > 64:
            continue
        v = pcbnew.PCB_VIA(b.b)
        v.SetPosition(pd.GetPosition()); v.SetNet(net); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(MM(0.40)); v.SetDrill(MM(0.20))
        b.b.Add(v); n += 1
    return n


def rf_bridge(b, fps):
    p = {pd.GetNumber(): pd for pd in fps["U1"].Pads()}
    t = pcbnew.PCB_TRACK(b.b)
    t.SetStart(p["20"].GetPosition()); t.SetEnd(p["22"].GetPosition()); t.SetLayer(pcbnew.F_Cu); t.SetWidth(MM(0.30)); t.SetNet(b.net("RF_BRIDGE"))
    b.b.Add(t)


def gnd_fanout(b, fps, net="GND", rv=0.2, trk=0.12, clr=0.12):
    """short stub + via next to every SMD pad of `net` (GND plane on In1): keeps the router off the ground nets (fan-out before Freerouting)"""
    import math
    from place_cup import inside
    pads = [(f, pd) for f in fps.values() for pd in f.Pads()]
    boxes = []
    for f, pd in pads:
        bb = pd.GetBoundingBox()
        boxes.append((T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom()), pd))
    vias = [(T(v.GetPosition().x), T(v.GetPosition().y)) for v in b.b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]
    n = 0
    for f, pd in pads:
        if pd.GetNetname() != net or pd.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or f.GetReference() == "U1":
            continue
        px, py = T(pd.GetPosition().x), T(pd.GetPosition().y)
        if any(math.hypot(vx - px, vy - py) < 0.9 for vx, vy in vias):
            continue
        bbp = pd.GetBoundingBox()
        if min(T(bbp.GetWidth()), T(bbp.GetHeight())) >= 0.38 and f.GetReference() != "J1" and not any(math.hypot(vx - px, vy - py) < 0.6 for vx, vy in vias) and not any(q is not pd and math.hypot(max(x0 - px, 0, px - x1), max(y0 - py, 0, py - y1)) < rv + clr for x0, y0, x1, y1, q in boxes):
            v = pcbnew.PCB_VIA(b.b); v.SetPosition(pd.GetPosition()); v.SetNet(pd.GetNet()); v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetWidth(MM(2 * rv)); v.SetDrill(MM(0.2)); b.b.Add(v); vias.append((px, py)); n += 1
            continue
        done = False
        for d in (0.45, 0.55, 0.7, 0.9, 1.1, 1.4):
            for k in range(16):
                a = k * math.pi / 8
                x, y = px + d * math.cos(a), py + d * math.sin(a)
                if any(q is not pd and math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1)) < rv + clr for x0, y0, x1, y1, q in boxes):
                    continue
                if any(math.hypot(vx - x, vy - y) < 2 * rv + clr + 0.1 for vx, vy in vias):
                    continue
                if any(q is not pd and math.hypot(max(x0 - (px + t * (x - px)), 0, (px + t * (x - px)) - x1), max(y0 - (py + t * (y - py)), 0, (py + t * (y - py)) - y1)) < trk / 2 + clr for x0, y0, x1, y1, q in boxes for t in (0.25, 0.5, 0.75)):
                    continue
                bx, by = x - bl.OX, y - bl.OY
                if not inside([bx - rv, by - rv, bx + rv, by + rv], G.OUTLINE, 0.3):
                    continue
                if G.ANT[0] - 0.3 < bx < G.ANT[2] + 0.3 and G.ANT[1] < by < G.ANT[3]:
                    continue
                v = pcbnew.PCB_VIA(b.b); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetNet(pd.GetNet()); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetWidth(MM(2 * rv)); v.SetDrill(MM(0.2)); b.b.Add(v)
                t = pcbnew.PCB_TRACK(b.b); t.SetStart(pd.GetPosition()); t.SetEnd(pcbnew.VECTOR2I(MM(x), MM(y)))
                t.SetLayer(pcbnew.B_Cu if f.GetSide() == pcbnew.B_Cu else pcbnew.F_Cu); t.SetWidth(MM(trk)); t.SetNet(pd.GetNet()); b.b.Add(t)
                vias.append((x, y)); n += 1; done = True
                break
            if done:
                break
    return n


def main():
    plf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "placement.json")
    parts = json.load(open(os.path.join(ROOT, "netlist_v4_cup.json")))
    pl = json.load(open(plf))
    b = Board(NAME, 36.6, 32.4, layers=6)
    b.b.GetDesignSettings().SetBoardThickness(MM(G.BOARD_T))
    b.poly_outline(G.OUTLINE)
    for p in parts:
        ref = p["ref"]
        x, y, rot, side = pl[ref]
        f = b.add(ref, p["value"], tuple(p["fp"]), x, y, 0, side=side, pins={k: v for k, v in p["pins"].items() if v}, lcsc=p["lcsc"], mpn=p["mpn"],
                  bom=p["bom"], note=p["note"], hide_ref=True)
        f.SetOrientationDegrees(rot if side == "F" else (rot + 180) % 360)

        b.parts[ref]["dnp"] = p["dnp"]; b.parts[ref]["group"] = p["group"]; b.parts[ref]["board"] = "CUP"
    fps = {f.GetReference(): f for f in b.b.GetFootprints()}
    # antenna keep-out (all copper layers)
    a = G.ANT
    z = pcbnew.ZONE(b.b); z.SetIsRuleArea(True); z.SetZoneName("ANT_KEEPOUT")
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowZoneFills(True); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu):
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    ch = z.Outline(); ch.NewOutline()
    for x, y in ((a[0], a[1]), (a[2], a[1]), (a[2], a[3]), (a[0], a[3])):
        ch.Append(MM(bl.OX + x), MM(bl.OY + y))
    b.b.Add(z)
    # board screws (mechanics elec_interface): d1.4 NPTH + d2.8 keep-out (no tracks, vias or pour) on all copper layers
    import math
    for k, (hx, hy) in enumerate(G.SCREWS):
        bx, by = G.b(hx, hy)
        c = pcbnew.VECTOR2I(MM(bl.OX + bx), MM(bl.OY + by))
        hf = pcbnew.FOOTPRINT(b.b); hf.SetReference("H%d" % (k + 1)); hf.SetValue("screw hole d1.4"); hf.SetPosition(c)
        pd = pcbnew.PAD(hf); pd.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); pd.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pd.SetSize(pcbnew.VECTOR2I(MM(G.SCREW_HOLE_D), MM(G.SCREW_HOLE_D))); pd.SetDrillSize(pcbnew.VECTOR2I(MM(G.SCREW_HOLE_D), MM(G.SCREW_HOLE_D)))
        pd.SetPosition(c); pd.SetLayerSet(pcbnew.PAD.UnplatedHoleMask()); hf.Add(pd); hf.Reference().SetVisible(False); b.b.Add(hf)
        kz = pcbnew.ZONE(b.b); kz.SetIsRuleArea(True); kz.SetZoneName("SCREW_KEEPOUT_%d" % (k + 1))
        kz.SetDoNotAllowTracks(True); kz.SetDoNotAllowVias(True); kz.SetDoNotAllowZoneFills(True); kz.SetDoNotAllowPads(False); kz.SetDoNotAllowFootprints(False)
        kz.SetLayerSet(ls)
        kch = kz.Outline(); kch.NewOutline()
        for a in range(24):
            ang = 2 * math.pi * a / 24
            kch.Append(MM(bl.OX + bx + G.SCREW_KEEPOUT_D / 2 * math.cos(ang)), MM(bl.OY + by + G.SCREW_KEEPOUT_D / 2 * math.sin(ang)))
        b.b.Add(kz)
    print("gnd fanout vias:", gnd_fanout(b, fps))
    for ref, lab in (("SP1", "+"), ("SP2", "-")):
        c = fps[ref].GetPosition(); b.text(lab, T(c.x) - bl.OX, T(c.y) - bl.OY - 2.1, 1.0, thick=0.15)
    b.text("TEST ONLY - NOT FOR HUMAN USE", 14.0, 13.5, 0.5, layer=pcbnew.B_SilkS, mirror=True, thick=0.08)
    b.rules(power_nets=POWERNETS, power_w=0.25, track=0.12)
    d = b.b.GetDesignSettings()
    d.m_CopperEdgeClearance = MM(0.2); d.m_MinThroughDrill = MM(0.2); d.m_ViasMinSize = MM(0.4); d.m_HoleToHoleMin = MM(0.2); d.m_TrackMinWidth = MM(0.1)
    for f in b.b.GetFootprints():
        f.Reference().SetVisible(False)
    # verify the SA transform against KiCad's pad positions
    bad = 0
    for p in parts:
        ref = p["ref"]; st = pl[ref]
        f = fps[ref]
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
            if bad < 6:
                print("TRANSFORM MISMATCH", ref, st, (round(ax, 2), round(ay, 2)), (round(st[0] + ex, 2), round(st[1] + ey, 2)))
    print("transform mismatches:", bad)
    b.save(PCB)
    json.dump(b.parts, open(os.path.join(HERE, "parts.json"), "w"), indent=1)
    write_project(os.path.join(HERE, NAME + ".kicad_pro"), POWERNETS, 0.25, track=0.12, edge=0.2, clear=0.10)
    pj = os.path.join(HERE, NAME + ".kicad_pro"); dd = json.load(open(pj)); r = dd["board"]["design_settings"]["rules"]
    r.update(min_through_hole_diameter=0.2, min_via_diameter=0.4, min_track_width=0.1, min_hole_to_hole=0.2, min_hole_clearance=0.2, min_via_annular_width=0.1)
    json.dump(dd, open(pj, "w"), indent=2)
    print(NAME, "written", len(b.parts), "parts")


main()
