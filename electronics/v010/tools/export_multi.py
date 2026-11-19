#!/usr/bin/env python3
"""JLCPCB package for the v0.1.0 board (plain python3 + kicad-cli): fab/jlcpcb/ gerbers+drill zip, BOM, CPL, NOT-ASSEMBLED, renders, STEP."""
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
K = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli")
NAME = sys.argv[1]
PCB = os.path.join(ROOT, "board", NAME, NAME + ".kicad_pcb")
PARTS = json.load(open(os.path.join(ROOT, "board", NAME, "parts.json")))
OUT = os.path.join(ROOT, "fab", "jlcpcb", NAME)
LAYERS = ("F.Cu,In1.Cu,In2.Cu,B.Cu," if NAME == "main" else "F.Cu,B.Cu,") + "F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
ROT = [(r"^SOT-23", 180), (r"^QFN-", 270), (r"^VSSOP-", 270), (r"^LED_", 180), (r"^D_SOD-123", 180), (r"^SOT-353", 180), (r"^TSSOP", 0)]


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
with zipfile.ZipFile(os.path.join(OUT, "openpatch-v010-%s-gerbers.zip" % NAME), "w", zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(os.listdir(tmp)):
        if not f.endswith((".gbrjob", ".rpt")) and "-drl_map" not in f:
            zf.write(os.path.join(tmp, f), f)
shutil.rmtree(tmp)

pos = os.path.join(OUT, "_pos.csv")
run([K, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", pos, PCB])
rows = {r["Ref"]: r for r in csv.DictReader(open(pos))}
os.remove(pos)
bom, cpl, notasm = {}, [], []
for ref, p in PARTS.items():
    if ref not in rows:
        continue
    r = rows[ref]
    if p.get("dnp"):
        notasm.append((ref, p["value"], "DNP variant part: " + (p.get("note") or "")))
        continue
    if not p.get("bom"):
        if p.get("note"):
            notasm.append((ref, p["value"], p["note"]))
        continue
    if not p.get("lcsc"):
        notasm.append((ref, p["value"], p.get("note") or "no LCSC part"))
        continue
    rot = float(r["Rot"])
    for pat, off in ROT:
        if re.search(pat, p["fp"]):
            rot = (rot + off) % 360
            break
    cpl.append([ref, r["PosX"], r["PosY"], "Top" if r["Side"] == "top" else "Bottom", f"{rot:g}"])
    bom.setdefault((p["value"], p["fp"], p["lcsc"], p.get("mpn", "")), []).append(ref)
key = lambda s: (re.sub(r"\d", "", s), int(re.sub(r"\D", "", s) or 0))
with open(os.path.join(OUT, "BOM-jlcpcb.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (v, fp, lc, mpn), refs in sorted(bom.items(), key=lambda x: key(sorted(x[1], key=key)[0])):
        w.writerow([v, ",".join(sorted(refs, key=key)), fp, lc])
with open(os.path.join(OUT, "CPL-jlcpcb.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    w.writerows(cpl)
with open(os.path.join(OUT, "NOT-ASSEMBLED.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Value", "Reason"])
    w.writerows(notasm)
for side in ("top", "bottom"):
    run([K, "pcb", "render", "--side", side, "--width", "2000", "--height", "1400", "--quality", "basic", "--background", "opaque",
         "-o", os.path.join(OUT, f"openpatch-v010-{NAME}-{side}.png"), PCB])
run([K, "pcb", "export", "step", "--force", "--subst-models", "-o", os.path.join(OUT, "openpatch-v010-%s.step" % NAME), PCB])
print("BOM lines", len(bom), "placed", len(cpl), "not assembled", len(notasm), "->", OUT)
