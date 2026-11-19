#!/usr/bin/env python3
"""Silkscreen cleanup: silkfix.py board.kicad_pcb  (KiCad python3 + kicad-cli)

Runs a DRC with the silk rules enabled, hides the reference designator of every footprint whose reference text overlaps other silk or
copper (and deletes loose text labels that overlap), repeats until nothing is left or no progress is made. Writes the board in place.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pcbnew

pcb = os.path.abspath(sys.argv[1])
K = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
tmp = tempfile.mkdtemp()
KEEP = ("U1", "U4", "J1", "J2", "J4", "J5", "SW1", "BZ1")


def drc(path):
    shutil.copy(path, os.path.join(tmp, "s.kicad_pcb"))
    pro = json.load(open(os.path.splitext(path)[0] + ".kicad_pro"))
    for k in ("silk_over_copper", "silk_overlap", "silk_edge_clearance"):
        pro["board"]["design_settings"]["rule_severities"][k] = "warning"
    json.dump(pro, open(os.path.join(tmp, "s.kicad_pro"), "w"))
    subprocess.run([K, "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "-o", os.path.join(tmp, "d.json"),
                    os.path.join(tmp, "s.kicad_pcb")], capture_output=True)
    return json.load(open(os.path.join(tmp, "d.json")))["violations"]


# one-off geometry clean-ups: module outline silk crosses its own castellated pads (JLC clips it anyway), motor label sits on the connector
b = pcbnew.LoadBoard(pcb)
tb = b.GetTitleBlock()
tb.SetTitle("OpenPatch bench controller rev A")
tb.SetCompany("OpenPatch project")
tb.SetComment(0, "TEST ONLY - NOT FOR HUMAN USE (DISCLAIMER.md)")
b.SetTitleBlock(tb)
for f in b.GetFootprints():
    if f.GetReference() == "U1":
        for g in list(f.GraphicalItems()):
            if g.GetLayer() == pcbnew.F_SilkS and not isinstance(g, pcbnew.PCB_TEXT):
                g.SetLayer(pcbnew.Cmts_User)
for f in b.GetFootprints():
    if f.GetReference() in ("BZ1", "J4", "J1"):
        for g in list(f.GraphicalItems()):
            if g.GetLayer() == pcbnew.F_SilkS:
                g.SetLayer(pcbnew.Cmts_User)
for d in b.GetDrawings():
    if isinstance(d, pcbnew.PCB_TEXT) and d.GetLayer() == pcbnew.B_SilkS:
        if d.GetText() in ("PGATE", "VMOT", "MOT_DIR"):
            d.SetLayer(pcbnew.Cmts_User)
        elif d.GetText().startswith("TEST ONLY - NOT FOR"):
            d.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.0), pcbnew.FromMM(1.0)))
            d.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(100 + 19.0), d.GetPosition().y))
for d in b.GetDrawings():
    if isinstance(d, pcbnew.PCB_TEXT) and d.GetText().startswith("MOTOR") and d.GetLayer() == pcbnew.F_SilkS:
        j5 = [f for f in b.GetFootprints() if f.GetReference() == "J5"][0]
        d.SetLayer(pcbnew.B_SilkS); d.SetMirrored(True)
        d.SetPosition(pcbnew.VECTOR2I(j5.GetPosition().x + pcbnew.FromMM(1.0), j5.GetPosition().y))
        d.SetTextAngleDegrees(90)
pcbnew.SaveBoard(pcb, b)
for it in range(6):
    v = [x for x in drc(pcb) if x["type"].startswith("silk")]
    print("iteration", it, "silk violations", len(v))
    if not v:
        break
    b = pcbnew.LoadBoard(pcb)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    hide, texts = set(), []
    for x in v:
        for item in x["items"]:
            m = re.match(r"Reference field of (\S+)", item["description"])
            mt = re.match(r"PCB text '(.+)' on [FB]\.Silkscreen", item["description"])
            if mt:
                texts.append(mt.group(1))
            if m:
                hide.add(m.group(1))
            elif item["description"].startswith("Text") or "PCB_TEXT" in item["description"]:
                texts.append((item["pos"]["x"], item["pos"]["y"]))
    n = 0
    for d in b.GetDrawings():
        if isinstance(d, pcbnew.PCB_TEXT) and d.GetText() in texts and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            d.SetLayer(pcbnew.Cmts_User); n += 1     # test-point label with no free spot: not printed
    for r in hide:
        if r in fps and fps[r].Reference().IsVisible():
            fps[r].Reference().SetVisible(False); n += 1
    print("  hidden references:", n, "text items flagged:", len(texts))
    pcbnew.SaveBoard(pcb, b)
    if not n:
        break
rest = [x for x in drc(pcb) if x["type"].startswith("silk")]
print("remaining silk warnings:", len(rest))
for x in rest[:20]:
    print("  ", x["type"], [i["description"][:48] for i in x["items"]])
