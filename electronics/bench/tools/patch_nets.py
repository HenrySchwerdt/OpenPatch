#!/usr/bin/env python3
"""Finish a few unrouted connections by trying simple routes and keeping the first one that DRC accepts.

patch_nets.py board.kicad_pcb NET x1,y1 x2,y2 [NET x1,y1 x2,y2 ...]      (board coordinates in mm, KiCad python3 + kicad-cli)

Candidates per connection: direct, two L shapes, on F.Cu; then L shapes on B.Cu and In2.Cu through two vias placed 0.9 mm along the route.
A candidate is accepted when the DRC error count does not rise and the unconnected count falls.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pcbnew

pcb = os.path.abspath(sys.argv[1])
K = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
OX, OY = 100.0, 80.0
tmp = tempfile.mkdtemp()
MM = pcbnew.FromMM


def score(path):
    shutil.copy(path, os.path.join(tmp, "s.kicad_pcb"))
    shutil.copy(os.path.splitext(path)[0] + ".kicad_pro", os.path.join(tmp, "s.kicad_pro"))
    subprocess.run([K, "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "-o", os.path.join(tmp, "d.json"),
                    os.path.join(tmp, "s.kicad_pcb")], capture_output=True)
    d = json.load(open(os.path.join(tmp, "d.json")))
    errs = sum(1 for v in d["violations"] if v["severity"] == "error")
    return errs, len(d["unconnected_items"])


def P(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def add_track(b, net, layer, a, c, w=0.15):
    if abs(a[0] - c[0]) < 1e-6 and abs(a[1] - c[1]) < 1e-6:
        return
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetLayer(layer); t.SetWidth(MM(w)); t.SetNet(b.FindNet(net))
    b.Add(t)


def add_via(b, net, p):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(P(*p)); v.SetNet(b.FindNet(net)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetWidth(MM(0.55)); v.SetDrill(MM(0.3))
    b.Add(v)


def candidates(a, c):
    corner1, corner2 = (c[0], a[1]), (a[0], c[1])
    for lay in (pcbnew.F_Cu,):
        yield "F direct", [(lay, a, c)], []
        yield "F L1", [(lay, a, corner1), (lay, corner1, c)], []
        yield "F L2", [(lay, a, corner2), (lay, corner2, c)], []
    for lay in (pcbnew.B_Cu, pcbnew.In2_Cu):
        for name, cor in (("L1", corner1), ("L2", corner2), ("D", None)):
            dx, dy = c[0] - a[0], c[1] - a[1]
            n = (dx * dx + dy * dy) ** 0.5 or 1.0
            va = (a[0] + 0.9 * dx / n, a[1] + 0.9 * dy / n)
            vc = (c[0] - 0.9 * dx / n, c[1] - 0.9 * dy / n)
            segs = [(lay, va, vc)] if cor is None else [(lay, va, cor), (lay, cor, vc)]
            yield f"{pcbnew.LayerName(lay)} {name}", [(pcbnew.F_Cu, a, va)] + segs + [(pcbnew.F_Cu, vc, c)], [va, vc]


args = sys.argv[2:]
for i in range(0, len(args), 3):
    net = args[i]
    a = tuple(float(v) for v in args[i + 1].split(","))
    c = tuple(float(v) for v in args[i + 2].split(","))
    base = score(pcb)
    print(net, "baseline errors/unconnected", base)
    done = False
    for name, segs, vias in candidates(a, c):
        b = pcbnew.LoadBoard(pcb)
        for lay, p, q in segs:
            add_track(b, net, lay, p, q)
        for v in vias:
            add_via(b, net, v)
        trial = os.path.join(tmp, "trial.kicad_pcb")
        pcbnew.SaveBoard(trial, b)
        shutil.copy(os.path.splitext(pcb)[0] + ".kicad_pro", os.path.join(tmp, "trial.kicad_pro"))
        sc = score(trial)
        print("  ", name, sc)
        if sc[0] <= base[0] and sc[1] < base[1]:
            shutil.copy(trial, pcb)
            print("   accepted:", name)
            done = True
            break
    if not done:
        print("   NO CANDIDATE WORKED for", net)
