#!/usr/bin/env python3
"""route.py <board.kicad_pcb> prep|route|import|finish   (KiCad python3)

prep   : drop zones except rule areas, add In1 GND plane, export Specctra DSN
route  : run Freerouting
import : import the SES result
finish : add GND pours (F, B, In2), fill zones, save
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchlib as bl

pcb = sys.argv[1]
base = os.path.splitext(pcb)[0]
dsn, ses = base + ".dsn", base + ".ses"
step = sys.argv[2]
four = True


def pour(b, name, layer, net="GND"):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer); z.SetNet(b.FindNet(net)); z.SetZoneName(name)
    z.SetMinThickness(bl.MM(0.15)); z.SetLocalClearance(bl.MM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(bl.MM(0.25)); z.SetThermalReliefSpokeWidth(bl.MM(0.3))
    bb = b.GetBoardEdgesBoundingBox()
    ins = bl.MM(0.35)
    ch = z.Outline(); ch.NewOutline()
    for x, y in ((bb.GetLeft() + ins, bb.GetTop() + ins), (bb.GetRight() - ins, bb.GetTop() + ins),
                 (bb.GetRight() - ins, bb.GetBottom() - ins), (bb.GetLeft() + ins, bb.GetBottom() - ins)):
        ch.Append(x, y)
    b.Add(z)


if step == "prep":
    b = pcbnew.LoadBoard(pcb)
    for z in list(b.Zones()):
        if not z.GetIsRuleArea():
            b.Remove(z)
    for t in list(b.GetTracks()):
        b.Remove(t)
    layers = [pcbnew.In1_Cu] if b.GetCopperLayerCount() == 4 else []
    for l in layers:
        pour(b, "GND_plane", l)
    pcbnew.SaveBoard(pcb, b)
    pcbnew.ExportSpecctraDSN(b, dsn)
    print("DSN", dsn)
elif step == "route":
    print("freerouting rc", bl.freeroute(dsn, ses, passes=int(sys.argv[3]) if len(sys.argv) > 3 else 40))
elif step == "import":
    print("SES import", bl.import_ses(pcb, ses))
elif step == "finish":
    b = pcbnew.LoadBoard(pcb)
    for z in list(b.Zones()):
        if not z.GetIsRuleArea():
            b.Remove(z)
    if b.GetCopperLayerCount() == 4:
        pour(b, "GND_In1", pcbnew.In1_Cu); pour(b, "GND_In2", pcbnew.In2_Cu)
    pour(b, "GND_F", pcbnew.F_Cu); pour(b, "GND_B", pcbnew.B_Cu)
    for f in b.GetFootprints():
        if f.GetReference().startswith("J"):
            for pd in f.Pads():
                if pd.GetNetname() == "GND":
                    pd.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb, b)
    print("zones filled")
