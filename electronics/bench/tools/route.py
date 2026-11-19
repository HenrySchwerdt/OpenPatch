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


def stitch(b, pitch=4.0, clear=0.7):
    """GND stitching vias on a regular grid wherever no foreign copper is within `clear` mm (ties the GND pours of all layers together)."""
    gnd = b.FindNet("GND")
    items = [t for t in b.GetTracks()] + [p for f in b.GetFootprints() for p in f.Pads()]
    bb = b.GetBoardEdgesBoundingBox()
    n = 0
    x = bb.GetLeft() + bl.MM(2.0)
    while x < bb.GetRight() - bl.MM(1.5):
        y = bb.GetTop() + bl.MM(2.0)
        while y < bb.GetBottom() - bl.MM(1.5):
            p = pcbnew.VECTOR2I(int(x), int(y))
            ok = True
            for it in items:
                if it.GetNetCode() != gnd.GetNetCode() and it.HitTest(p, bl.MM(clear)):
                    ok = False
                    break
                if it.GetNetCode() == gnd.GetNetCode() and it.HitTest(p, bl.MM(0.7)):
                    ok = False        # do not stack on existing GND copper
                    break
            for z in b.Zones():
                if z.GetIsRuleArea() and z.HitTestFilledArea(pcbnew.F_Cu, p, 0) or (z.GetIsRuleArea() and z.GetBoundingBox().Contains(p)):
                    ok = False
            if ok:
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(p); v.SetNet(gnd); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetWidth(bl.MM(bl.VIA_D)); v.SetDrill(bl.MM(bl.VIA_H))
                b.Add(v); items.append(v); n += 1
            y += bl.MM(pitch)
        x += bl.MM(pitch)
    print("stitching vias:", n)


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
    # route with a slightly larger clearance than the DRC rule (0.15 mm) so imported tracks never end up at the limit
    txt = open(dsn).read().replace("(clearance 150)", "(clearance %d)" % int(float(os.environ.get("OP_CLR", "0.17")) * 1000))
    # optional: keep signals off In1 (the GND plane)
    if os.environ.get("OP_PLANE") == "1":   # experimental: gave 60+ unrouted nets on the controller, so off by default
        txt = txt.replace("(layer In1.Cu\n      (type signal)", "(layer In1.Cu\n      (type power)")
    open(dsn, "w").write(txt)
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
    for z in b.Zones():
        if not z.GetIsRuleArea():
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)    # no floating copper islands
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    stitch(b)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb, b)
    print("zones filled")
elif step == "fix":
    # pads whose thermal relief is starved get a solid connection to the pour, then refill
    import json, re, subprocess, shutil
    K = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
    out = "/tmp/_fix_drc.json"
    subprocess.run([K, "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "-o", out, pcb], capture_output=True)
    d = json.load(open(out))
    b = pcbnew.LoadBoard(pcb)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    n = 0
    for v in d["violations"]:
        if v["type"] != "starved_thermal":
            continue
        for it in v["items"]:
            m = re.match(r"Pad (\S+) \[GND\] of (\S+)", it["description"])
            if m and m.group(2) in fps:
                for pd in fps[m.group(2)].Pads():
                    if pd.GetNumber() == m.group(1):
                        pd.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL); n += 1
    # tracks that violate the copper-to-edge rule are narrowed to 0.15 mm (power tracks carry only milliamps there)
    m = 0
    for v in d["violations"]:
        if v["type"] != "copper_edge_clearance":
            continue
        for it in v["items"]:
            mm = re.match(r"Track \[(\S+)\] on (\S+)", it["description"])
            if not mm:
                continue
            px, py = it["pos"]["x"], it["pos"]["y"]
            for tr in b.GetTracks():
                if tr.GetClass() == "PCB_TRACK" and tr.GetNetname() == mm.group(1) and tr.GetBoundingBox().Contains(
                        pcbnew.VECTOR2I(pcbnew.FromMM(px), pcbnew.FromMM(py))):
                    tr.SetWidth(pcbnew.FromMM(0.15)); m += 1
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(pcb, b)
    print("starved pads set to full connection:", n, " edge tracks narrowed:", m)
