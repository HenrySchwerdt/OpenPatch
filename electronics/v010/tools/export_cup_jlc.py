#!/usr/bin/env python3
"""JLCPCB package of the CUP board (plain python3 + kicad-cli): cup/jlc/ gerbers + drill zip, BOM, CPL (rotation corrected), NOT-ASSEMBLED.

usage: python3 export_cup_jlc.py [board.kicad_pcb]   (default cup/cup.kicad_pcb)
CPL rotation = KiCad rotation - delta, delta = orientation of the official LCSC/EasyEDA footprint relative to ours (cup/jlc_rot_offsets.json, computed by
comparing pad positions per pad number).  Bottom side: JLC mirrors, rotation = (360 - rot) mod 360 is applied by JLC's own convention for the bottom layer as
exported by KiCad ("--side both" reports the rotation in the board frame), so bottom parts are listed in ORDER.md for a 3D-preview check."""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
CUP = os.path.join(ROOT, "cup")
K = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli")
PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(CUP, "cup.kicad_pcb")
PARTS = json.load(open(os.path.join(CUP, "parts.json")))
OFF = json.load(open(os.path.join(CUP, "jlc_rot_offsets.json")))
OUT = os.path.join(CUP, "jlc")
LAYERS = "F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print("WARN", cmd[:5], r.stderr[-300:])
    return r


os.makedirs(OUT, exist_ok=True)
tmp = os.path.join(OUT, "_g")
shutil.rmtree(tmp, ignore_errors=True)
os.makedirs(tmp)
run([K, "pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask", "-o", tmp + "/", PCB])
run([K, "pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm", "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", "-o", tmp + "/", PCB])
with zipfile.ZipFile(os.path.join(OUT, "openpatch-cup-gerbers.zip"), "w", zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(os.listdir(tmp)):
        if not f.endswith((".gbrjob", ".rpt")) and "-drl_map" not in f:
            zf.write(os.path.join(tmp, f), f)
shutil.rmtree(tmp)

pos = os.path.join(OUT, "_pos.csv")
run([K, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", pos, PCB])
rows = {r["Ref"]: r for r in csv.DictReader(open(pos))}
os.remove(pos)
bom, cpl, notasm, VAL = {}, [], [], {}
for ref, p in PARTS.items():
    if ref not in rows:
        continue
    r = rows[ref]
    if p.get("dnp"):
        notasm.append((ref, p["value"], "DNP match part: " + (p.get("note") or "")))
        continue
    if not p.get("bom"):
        notasm.append((ref, p["value"], "bare pad / not assembled"))
        continue
    if not p.get("lcsc"):
        notasm.append((ref, p["value"], p.get("note") or "no LCSC part"))
        continue
    rot = float(r["Rot"])
    off = OFF.get(p["fp"], {}).get("delta_ccw", 0)
    rot = (rot - off) % 360
    cpl.append([ref, r["PosX"], r["PosY"], "Top" if r["Side"] == "top" else "Bottom", f"{rot:g}"])
    bom.setdefault((p["lcsc"], p["fp"]), []).append(ref)
    VAL.setdefault((p["lcsc"], p["fp"]), p["value"])
key = lambda s: (re.sub(r"\d", "", s), int(re.sub(r"\D", "", s) or 0))
with open(os.path.join(OUT, "BOM-jlcpcb.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (lc, fp), refs in sorted(bom.items(), key=lambda x: key(sorted(x[1], key=key)[0])):
        w.writerow([VAL[(lc, fp)], ",".join(sorted(refs, key=key)), fp, lc])
with open(os.path.join(OUT, "CPL-jlcpcb.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    w.writerows(cpl)
with open(os.path.join(OUT, "NOT-ASSEMBLED.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Value", "Reason"])
    w.writerows(notasm)
print("JLC package:", len(cpl), "placements,", len(bom), "BOM lines,", len(notasm), "not assembled ->", OUT)
