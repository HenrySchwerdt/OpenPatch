#!/usr/bin/env python3
"""Build the three v0.1.0 boards (KiCad python): build_multi.py main|sensor|usb  -> boards/<name>/<name>.kicad_pcb + parts.json + .kicad_pro"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "..", "bench", "tools"))
import pcbnew
import benchlib as bl
from benchlib import Board, write_project

MM = bl.MM
name = sys.argv[1]
bl.TRACK, bl.CLEAR, bl.VIA_D, bl.VIA_H = 0.15, 0.15, 0.5, 0.25
V010FP = os.path.join(ROOT, "footprints", "V010.pretty")
_orig = Board.load_fp


def _load(self, lib, nm):
    if lib == "V010":
        return pcbnew.FootprintLoad(V010FP, nm)
    return _orig(self, lib, nm)


Board.load_fp = _load

CFG = {
    "sensor": dict(w=15.0, h=13.0, layers=2, corner=1.0, fixed={"U10T": (3.2, 10.0, 90, "B"), "U4A": (3.6, 3.0, 0, "B"), "U4B": (6.6, 3.0, 0, "B"), "J3S": (11.2, 6.5, 90, "F")},
                   anchors={"sensor": (7, 7)}, antenna=None),
    "usb": dict(w=22.0, h=26.0, layers=2, corner=1.0, fixed={"JU1": (11.0, 5.0, 0, "F"), "J3U": (11.0, 21.0, 0, "F")}, anchors={"usb": (11, 13)}, antenna=None),
    "main": dict(w=52.0, h=38.0, layers=4, corner=2.0,
                 fixed={"U1": (39.0, 21.0, None, "B"), "J1": (6.0, 28.0, 90, "B"), "BZ1": (12.0, 9.0, 0, "B"), "SP1": (3.0, 12.0, 0, "B"), "SP2": (3.0, 17.0, 0, "B"),
                        "SW1": (30.0, 4.0, 0, "F"), "J3": (18.0, 34.0, 0, "F"), "J7": (32.0, 34.0, 0, "F"),
                        "H1": (1.5, 1.5, 0, "F"), "H2": (50.5, 1.5, 0, "F"), "H3": (1.5, 36.5, 0, "F")},
                 anchors={"mcu": (28, 18), "swd": (14, 4), "batt": (10, 14), "pwr": (15, 14), "chg": (8, 6), "sense": (20, 10), "sw": (8, 18), "dock": (13, 11),
                          "drv": (14, 22), "oc": (18, 16), "sup": (22, 22), "ui": (24, 8), "boost": (6, 26), "tp": (20, 6), "mot": (6, 23), "ffc": (20, 28), "mech": (1, 1)},
                 antenna=(42.5, 12.0, 52.0, 30.0)),
}[name]
W, H = CFG["w"], CFG["h"]
Y = lambda by: H - by
POWER = ("VBAT", "3V3", "VMOT", "VMOT_RAW", "VMOT_A", "VMOT_PRE", "MOT_A1", "MOT_A2", "MOT_B1", "MOT_B2", "VBUS_P", "VBUS_R", "BST_SW")
OUTDIR = os.path.join(HERE, name)
os.makedirs(OUTDIR, exist_ok=True)
PCB = os.path.join(OUTDIR, name + ".kicad_pcb")
exec(open(os.path.join(HERE, "placelib.py")).read())


def main():
    parts = json.load(open(os.path.join(ROOT, "netlist_%s.json" % name)))
    b = Board(name, W, H, layers=CFG["layers"], corner=CFG["corner"])
    b.b.GetDesignSettings().SetBoardThickness(MM(0.8))
    b.rounded_outline()
    fixed = CFG["fixed"]
    for p in parts:
        ref = p["ref"]
        side = p["side"]
        if ref in fixed:
            x, y, rot, side = fixed[ref]
            y = Y(y)
            if rot is None:
                rot = float(os.environ.get("U1ROT", 90))
        else:
            x, y = CFG["anchors"].get(p["group"], (W / 2, H / 2)); y = Y(y); rot = 0
        b.add(ref, p["value"], tuple(p["fp"]), x, y, rot, side=side, pins={k: v for k, v in p["pins"].items() if v}, lcsc=p["lcsc"], mpn=p["mpn"], bom=p["bom"], note=p["note"], hide_ref=True)
        b.parts[ref]["dnp"] = p["dnp"]; b.parts[ref]["group"] = p["group"]; b.parts[ref]["board"] = p.get("board", name)
    fps = {f.GetReference(): f for f in b.b.GetFootprints()}
    forb = []
    if CFG["antenna"]:
        a = CFG["antenna"]
        b.keepout(a[0], Y(a[3]), a[2], Y(a[1]), "ANT_KEEPOUT")
        forb.append([a[0], Y(a[3]), a[2], Y(a[1])])
    quad_place(b, fps, parts, set(fixed))
    legalize2(b, fps, set(fixed), forb)
    T = pcbnew.ToMM
    lab = []
    for f in b.b.GetFootprints():
        r = f.GetReference()
        if (r.startswith("TP") or r in ("J4", "J5", "J6")) and f.GetSide() == pcbnew.F_Cu:
            lab.append((b.parts[r]["value"], T(f.GetPosition().x) - bl.OX, T(f.GetPosition().y) - bl.OY))
    if lab:
        print("labels dropped:", bl.place_labels(b, lab, 0.6))
    b.text("TEST ONLY - NOT FOR HUMAN USE", 1.0, Y(0.8), 0.6, thick=0.1)
    b.rules(power_nets=POWER, power_w=0.3)
    b.b.GetDesignSettings().m_CopperEdgeClearance = MM(0.25)
    b.b.GetDesignSettings().m_MinThroughDrill = MM(0.2)
    for f in b.b.GetFootprints():
        f.Reference().SetVisible(False)
    b.save(PCB)
    json.dump(b.parts, open(os.path.join(OUTDIR, "parts.json"), "w"), indent=1)
    write_project(os.path.join(OUTDIR, name + ".kicad_pro"), POWER, 0.3, edge=0.25)
    pj = os.path.join(OUTDIR, name + ".kicad_pro"); d = json.load(open(pj)); d["board"]["design_settings"]["rules"]["min_through_hole_diameter"] = 0.2; json.dump(d, open(pj, "w"), indent=2)
    print(name, "written", len(b.parts), "parts", W, "x", H)


main()
