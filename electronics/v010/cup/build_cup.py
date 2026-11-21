#!/usr/bin/env python3
"""Build cup/cup.kicad_pcb from netlist_v4_cup.json + placement.json (KiCad python).  usage: kpy build_cup.py [placement.json]

6 layers, 0.8 mm, outline = L/U shape (cupgeom.OUTLINE), HJ-840 via-in-pad fan-out, antenna keep-out, parts.json for the fab export."""
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
bl.TRACK, bl.CLEAR, bl.VIA_D, bl.VIA_H = 0.10, 0.10, 0.40, 0.20     # JLC 6-layer: 0.09 / 0.09 mm minimum
POWERNETS = ("VBAT", "VMOT", "VMOT_PRE", "BST_SW", "MOT_A1", "MOT_A2", "MOT_B1", "MOT_B2", "VBUS_P")      # 3V3 carries about 8 mA: default width
NAME = "cup"
PCB = os.path.join(HERE, NAME + ".kicad_pcb")


U1_VIA_D, U1_VIA_H = 0.35, 0.15       # filled + capped via in pad (JLC POFV, free on 6-layer boards); 0.35 copper keeps 0.2 mm hole-to-track with 0.1 copper clearance


RING0_OPEN = os.environ.get("OP_RING0_VIA", "0") != "1"


def _ring(pad):
    r = "ABCDEFGH".index(pad[0]); c = int(pad[1:])
    return min(r, 7 - r, c - 1, 8 - c)


def u1_fanout(b, fps):
    """HJ-840: a filled via in every used pad of the inner rings (inner layers do their escape); perimeter (ring 0) signal pads have no via,
    they escape outward on F.Cu (a via in every pad walled off all six layers at 0.65 mm pitch: the routers could not enter the module).
    Also excepted: the antenna-strip pads A1 / A7 / A8:
    A7 (ANT) and A8 (BOARD_ANT) are bridged on F.Cu (the former 0 ohm + 2 x DNP pi network), A1 (GND) gets a short F.Cu stub to a via just west of the keep-out."""
    u1 = fps["U1"]
    pads = {pd.GetNumber(): pd for pd in u1.Pads()}
    n = 0

    def via(pos, net, d=U1_VIA_D, h=U1_VIA_H):
        v = pcbnew.PCB_VIA(b.b); v.SetPosition(pos); v.SetNet(net); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetWidth(MM(d)); v.SetDrill(MM(h)); b.b.Add(v)

    def trk(a, c, net, w):
        t = pcbnew.PCB_TRACK(b.b); t.SetStart(a); t.SetEnd(c); t.SetLayer(pcbnew.F_Cu); t.SetWidth(MM(w)); t.SetNet(net); b.b.Add(t)

    for num, pd in pads.items():
        if not pd.GetNetname() or num in ("A1", "A7", "A8"):
            continue
        if RING0_OPEN and _ring(num) == 0 and pd.GetNetname() != "GND":
            continue          # perimeter signal pad: escapes outward on F.Cu, so the inner layers under the module rim stay open
        via(pd.GetPosition(), pd.GetNet()); n += 1
    trk(pads["A7"].GetPosition(), pads["A8"].GetPosition(), pads["A7"].GetNet(), 0.25)
    a1 = pads["A1"].GetPosition()
    corner = pcbnew.VECTOR2I(a1.x, a1.y - MM(0.55))          # board frame: -y = north, out of the pad row toward the module edge
    gv = pcbnew.VECTOR2I(a1.x - MM(1.15), a1.y - MM(0.55))   # west, 0.15 mm outside the antenna keep-out (bx < 34.2)
    trk(a1, corner, pads["A1"].GetNet(), 0.2); trk(corner, gv, pads["A1"].GetNet(), 0.2)
    via(gv, pads["A1"].GetNet(), 0.4, 0.2)
    return n


BUS_NETS = ["VBAT", "3V3", "VMOT", "SUP_PERMIT", "OC_OK", "MOT_ALLOW", "PERM_L", "DOCK_XOR", "APHASE", "BPHASE", "AENBL", "BENBL", "I2C_SCL", "I2C_SDA"]
BUS_XA = tuple(float(v) for v in os.environ.get("OP_BUS_XA", "5.5/10.4").split("/"))   # clamp of the trunk ends (board frame x)
BUS_XB = tuple(float(v) for v in os.environ.get("OP_BUS_XB", "21.5/31.5").split("/"))
BUS_LANES = [8.45, 8.75, 9.05, 9.35, 9.65, 9.95, 10.2]      # board-frame y of the lanes (below the D- pad vias at y 8.02, above the edge band at 10.3)


def bridge_bus(b, fps):
    """Pre-route the nets that join the west and east lobes as straight trunks on In2 / In3 across the USB bridge (Freerouting leaves the
    bridge inner layers unused and then fails on exactly these long nets). Each trunk runs from the mean x of its west pins (>= 5.5) to the
    mean x of its east pins (<= 31.5) on its own lane; the router then only connects the short ends."""
    pins = {}
    for f in fps.values():
        for pd in f.Pads():
            n = pd.GetNetname()
            if n in BUS_NETS:
                pins.setdefault(n, []).append((T(pd.GetPosition().x) - bl.OX, T(pd.GetPosition().y) - bl.OY))
    # only nets with pins in both lobes; per layer the lanes are filled in the order of the nets' east pin y (north-most on the top lane)
    nets = [nt for nt in BUS_NETS if any(x < 11.0 for x, _ in pins.get(nt, [])) and any(x > 20.4 for x, _ in pins.get(nt, []))]
    ey = lambda nt: sum(y for x, y in pins[nt] if x > 20.4) / len([1 for x, _ in pins[nt] if x > 20.4])
    half = (len(nets) + 1) // 2
    pairs = []
    for layer, grp in ((pcbnew.In2_Cu, nets[:half]), (pcbnew.In3_Cu, nets[half:])):
        pairs += [(nt, (layer, y)) for nt, y in zip(sorted(grp, key=ey), BUS_LANES)]
    n = 0
    for net, (layer, y) in pairs:
        west = [x for x, _ in pins[net] if x < 11.0]
        east = [x for x, _ in pins[net] if x > 20.4]
        xa = min(max(sum(west) / len(west), BUS_XA[0]), BUS_XA[1])
        xb = min(max(sum(east) / len(east), BUS_XB[0]), BUS_XB[1])
        t = pcbnew.PCB_TRACK(b.b)
        t.SetStart(pcbnew.VECTOR2I(MM(bl.OX + xa), MM(bl.OY + y))); t.SetEnd(pcbnew.VECTOR2I(MM(bl.OX + xb), MM(bl.OY + y)))
        t.SetLayer(layer); t.SetWidth(MM(0.16 if net in POWERNETS or net == "3V3" else 0.10)); t.SetNet(b.net(net)); b.b.Add(t); n += 1
    return n


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
                if any(math.hypot(bx - G.b(*sc)[0], by - G.b(*sc)[1]) < G.SCREW_KEEPOUT_D / 2 + rv + 0.05 for sc in G.SCREWS):
                    continue
                if any(math.hypot(bx - pt[0], by - pt[1]) < G.SCREW_KEEPOUT_D / 2 + 0.2 for sc in G.SCREWS for pt in [G.b(*sc)]) or \
                        any(math.hypot(px - bl.OX - G.b(*sc)[0], py - bl.OY - G.b(*sc)[1]) < G.SCREW_KEEPOUT_D / 2 + 0.6 and
                            math.hypot(bx - G.b(*sc)[0], by - G.b(*sc)[1]) < math.hypot(px - bl.OX - G.b(*sc)[0], py - bl.OY - G.b(*sc)[1]) for sc in G.SCREWS):
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
    # antenna keep-out (layout review 2026-11-20): no copper on In1..B.Cu over the whole antenna strip; on F.Cu no tracks / vias except the two
    # corridors that the module itself needs (A1 GND stub at by 2.2..3.4, A7-A8 bridge at by 6.6..7.9); no pour on any layer
    a = G.ANT
    ls = pcbnew.LSET()
    for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu):
        ls.AddLayer(l)

    def rule_area(name, layers, rect, tracks=True, vias=True, fills=True):
        z = pcbnew.ZONE(b.b); z.SetIsRuleArea(True); z.SetZoneName(name)
        z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(vias); z.SetDoNotAllowZoneFills(fills); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        z.SetLayerSet(layers)
        ch = z.Outline(); ch.NewOutline()
        for x, y in ((rect[0], rect[1]), (rect[2], rect[1]), (rect[2], rect[3]), (rect[0], rect[3])):
            ch.Append(MM(bl.OX + x), MM(bl.OY + y))
        b.b.Add(z)

    inner = pcbnew.LSET()
    for l in (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu):
        inner.AddLayer(l)
    fcu = pcbnew.LSET(); fcu.AddLayer(pcbnew.F_Cu)
    rule_area("ANT_KEEPOUT", inner, a)
    rule_area("ANT_NOPOUR_F", fcu, a, tracks=False, vias=False)
    for k, (y0, y1) in enumerate(((a[1], 2.2), (3.4, 6.6), (7.9, a[3]))):
        rule_area("ANT_KEEPOUT_F%d" % k, fcu, (a[0], y0, a[2], y1))
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
    # board-edge keep-out band 0.25 mm (no tracks / vias / pour on any copper layer): Freerouting does not know the 0.2 mm copper-to-edge rule of the fab
    poly = G.OUTLINE
    area2 = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    sg = 1.0 if area2 > 0 else -1.0                 # +1: counter-clockwise in this frame (y down: the interior is to the right of the travel direction when sg < 0)
    BAND = 0.30
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        nx, ny = -uy * sg, ux * sg                   # inward normal (checked below)
        mx, my = (x0 + x1) / 2 + nx * 0.05, (y0 + y1) / 2 + ny * 0.05
        from place_cup import pip
        if not pip(mx, my, poly):
            nx, ny = -nx, -ny
        pts = [(x0 - ux * BAND, y0 - uy * BAND), (x1 + ux * BAND, y1 + uy * BAND), (x1 + ux * BAND + nx * BAND, y1 + uy * BAND + ny * BAND), (x0 - ux * BAND + nx * BAND, y0 - uy * BAND + ny * BAND)]
        ez = pcbnew.ZONE(b.b); ez.SetIsRuleArea(True); ez.SetZoneName("EDGE_KEEPOUT_%d" % i)
        ez.SetDoNotAllowTracks(True); ez.SetDoNotAllowVias(True); ez.SetDoNotAllowZoneFills(False); ez.SetDoNotAllowPads(False); ez.SetDoNotAllowFootprints(False)
        ez.SetLayerSet(ls)
        ech = ez.Outline(); ech.NewOutline()
        for px, py in pts:
            ech.Append(MM(bl.OX + px), MM(bl.OY + py))
        b.b.Add(ez)
    print("U1 vias in pad:", u1_fanout(b, fps))
    # filled vias in the wire pads (motor + cell leads sit straight above the driver on the underside) and in the four USB data pads
    # (D+ / D- alternate in the receptacle pad row, A6-B6 and A7-B7 are joined on an inner layer)
    nvp = 0
    for ref, pads_, d, h in (("MP1", ("1",), 0.45, 0.2), ("MP2", ("1",), 0.45, 0.2), ("MP3", ("1",), 0.45, 0.2), ("MP4", ("1",), 0.45, 0.2),
                             ("SP1", ("1",), 0.45, 0.2), ("SP2", ("1",), 0.45, 0.2), ("JU1", ("A7", "B7"), U1_VIA_D, U1_VIA_H)):
        for pd in fps[ref].Pads():
            if pd.GetNumber() in pads_:
                v = pcbnew.PCB_VIA(b.b); v.SetPosition(pd.GetPosition()); v.SetNet(pd.GetNet()); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetWidth(MM(d)); v.SetDrill(MM(h)); b.b.Add(v); nvp += 1
    print("vias in wire / USB pads:", nvp)
    if os.environ.get("OP_BUS", "1") == "1":
        print("bridge bus trunks:", bridge_bus(b, fps))
    # USB D+: B6 and A6 joined on F.Cu by a U-loop just south of the pad row (D- uses the two pad vias above, joined on an inner layer)
    up = {pd.GetNumber(): pd.GetPosition() for pd in fps["JU1"].Pads()}
    dp = fps["JU1"].Pads()[0].GetBoard().FindNet("USB_DP") if False else b.b.FindNet("USB_DP")
    yl = up["B6"].y + MM(0.98)
    pts = [up["B6"], pcbnew.VECTOR2I(up["B6"].x, yl), pcbnew.VECTOR2I(up["A6"].x, yl), up["A6"]]
    for k in range(3 if os.environ.get("OP_DPLOOP", "0") == "1" else 0):      # off by default: Freerouting 2.2.4 hangs in PolylineTrace.normalize on this pre-route
        t = pcbnew.PCB_TRACK(b.b); t.SetStart(pts[k]); t.SetEnd(pts[k + 1]); t.SetLayer(pcbnew.F_Cu); t.SetWidth(MM(0.15)); t.SetNet(dp); b.b.Add(t)
    print("gnd fanout vias:", gnd_fanout(b, fps) if os.environ.get("OP_FANOUT", "1") == "1" else "skipped (OP_FANOUT=0: Freerouting places the GND vias itself)")
    for ref, lab in (("SP1", "+"), ("SP2", "-")):
        c = fps[ref].GetPosition(); b.text(lab, T(c.x) - bl.OX, T(c.y) - bl.OY - 2.1, 1.3, thick=0.2)       # large + / - at the cell pads (review m5)
    for ref, lab, dy in (("MP1", "A+", 1.6), ("MP2", "A-", 1.6), ("MP3", "B+", 1.6), ("MP4", "B-", -1.7)):      # bottom row labels below, MP4 above; 0.9 mm text, inside the outline
        c = fps[ref].GetPosition(); b.text(lab, T(c.x) - bl.OX, T(c.y) - bl.OY + dy, 0.9, thick=0.15)
    b.text("TEST ONLY - NOT FOR HUMAN USE", 14.0, 13.5, 0.5, layer=pcbnew.B_SilkS, mirror=True, thick=0.08)
    b.rules(power_nets=POWERNETS, power_w=0.16, track=0.10)
    d = b.b.GetDesignSettings()
    d.m_CopperEdgeClearance = MM(0.2); d.m_MinThroughDrill = MM(0.15); d.m_ViasMinSize = MM(0.3); d.m_HoleToHoleMin = MM(0.2); d.m_TrackMinWidth = MM(0.1)
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
    write_project(os.path.join(HERE, NAME + ".kicad_pro"), POWERNETS, 0.16, track=0.10, edge=0.2, clear=0.10)
    pj = os.path.join(HERE, NAME + ".kicad_pro"); dd = json.load(open(pj)); r = dd["board"]["design_settings"]["rules"]
    r.update(min_through_hole_diameter=0.15, min_via_diameter=0.3, min_track_width=0.1, min_hole_to_hole=0.2, min_hole_clearance=0.2, min_via_annular_width=0.075)
    json.dump(dd, open(pj, "w"), indent=2)
    print(NAME, "written", len(b.parts), "parts")


main()
