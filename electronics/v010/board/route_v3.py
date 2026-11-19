#!/usr/bin/env python3
"""route_v3.py <board.kicad_pcb> prep|route|import|finish  (KiCad python).  6-layer flow: In1 (and In4 if OP_P4=1) are GND planes.

prep   : drop non-keepout zones, add GND plane zones (exported to the DSN as Freerouting planes), protect the manual fan-out vias, export DSN
route  : Freerouting (OP_PASSES, default 40)
import : import the SES
finish : GND pours on all copper layers, island removal, stitching vias, fill, save
"""
import os
import re
import sys

import pcbnew

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bench", "tools"))
import benchlib as bl

pcb = sys.argv[1]
base = os.path.splitext(pcb)[0]
dsn, ses = base + ".dsn", base + ".ses"
step = sys.argv[2]
MM = pcbnew.FromMM
P4 = os.environ.get("OP_P4", "0") == "1"
FREEROUTING = os.environ.get("FREEROUTING_JAR") or bl.FREEROUTING


def zone(b, name, layer, net="GND", inset=0.25):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer); z.SetNet(b.FindNet(net)); z.SetZoneName(name)
    z.SetMinThickness(MM(0.1)); z.SetLocalClearance(MM(0.15))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(MM(0.15)); z.SetThermalReliefSpokeWidth(MM(0.2))
    bb = b.GetBoardEdgesBoundingBox(); i = MM(inset)
    ch = z.Outline(); ch.NewOutline()
    for x, y in ((bb.GetLeft() + i, bb.GetTop() + i), (bb.GetRight() - i, bb.GetTop() + i), (bb.GetRight() - i, bb.GetBottom() - i), (bb.GetLeft() + i, bb.GetBottom() - i)):
        ch.Append(x, y)
    b.Add(z)
    return z


def stitch(b, pitch=2.5, clear=0.45):
    gnd = b.FindNet("GND").GetNetCode()
    items = list(b.GetTracks()) + [p for f in b.GetFootprints() for p in f.Pads()]
    bb = b.GetBoardEdgesBoundingBox(); n = 0
    x = bb.GetLeft() + MM(1.0)
    rules = [z for z in b.Zones() if z.GetIsRuleArea()]
    while x < bb.GetRight() - MM(0.8):
        y = bb.GetTop() + MM(1.0)
        while y < bb.GetBottom() - MM(0.8):
            p = pcbnew.VECTOR2I(int(x), int(y)); ok = True
            for it in items:
                if it.GetNetCode() == gnd:
                    if it.HitTest(p, MM(0.8)):
                        ok = False; break
                elif it.HitTest(p, MM(clear)):
                    ok = False; break
            if ok:
                for z in rules:
                    if z.GetBoundingBox().Contains(p):
                        ok = False
            if ok:
                v = pcbnew.PCB_VIA(b); v.SetPosition(p); v.SetNet(b.FindNet("GND")); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetWidth(MM(bl.VIA_D)); v.SetDrill(MM(bl.VIA_H)); b.Add(v); items.append(v); n += 1
            y += MM(pitch)
        x += MM(pitch)
    print("stitching vias:", n)


if step == "prep":
    b = pcbnew.LoadBoard(pcb)
    for z in list(b.Zones()):
        if not z.GetIsRuleArea():
            b.Remove(z)
    zone(b, "GND_In1", pcbnew.In1_Cu)
    if P4:
        zone(b, "GND_In4", pcbnew.In4_Cu)
    pcbnew.SaveBoard(pcb, b)
    pcbnew.ExportSpecctraDSN(b, dsn)
    t = open(dsn).read()
    t = t.replace("(type route))", "(type protect))")
    t = t.replace("(clearance 100)", "(clearance %d)" % int(float(os.environ.get("OP_CLR", "0.10")) * 1000))
    layers = ["In1.Cu"] + (["In4.Cu"] if P4 else [])
    for l in layers:
        t = t.replace("(layer %s\n      (type signal)" % l, "(layer %s\n      (type power)" % l)
    open(dsn, "w").write(t)
    print("DSN", dsn, "planes", layers)
elif step == "route":
    import subprocess
    cmd = [bl.JAVA, "-jar", FREEROUTING, "-de", dsn, "-do", ses, "-mp", os.environ.get("OP_PASSES", "40")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    open(ses + ".log", "w").write(r.stdout + r.stderr)
    print("freerouting rc", r.returncode)
elif step == "import":
    b = pcbnew.LoadBoard(pcb)
    print("SES import", pcbnew.ImportSpecctraSES(b, ses))
    pcbnew.SaveBoard(pcb, b)
elif step == "finish":
    b = pcbnew.LoadBoard(pcb)
    for z in list(b.Zones()):
        if not z.GetIsRuleArea():
            b.Remove(z)
    ls = [("GND_F", pcbnew.F_Cu), ("GND_In1", pcbnew.In1_Cu), ("GND_In2", pcbnew.In2_Cu)]
    if b.GetCopperLayerCount() == 6:
        ls += [("GND_In3", pcbnew.In3_Cu), ("GND_In4", pcbnew.In4_Cu)]
    ls.append(("GND_B", pcbnew.B_Cu))
    for nm, l in ls:
        zone(b, nm, l)
    for z in b.Zones():
        if not z.GetIsRuleArea():
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    stitch(b)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb, b)
    print("zones filled")
