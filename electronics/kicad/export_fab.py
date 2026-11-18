#!/usr/bin/env python3
"""Export JLCPCB + PCBWay packages from openpatch-op100.kicad_pcb (plain python3; calls kicad-cli).

Outputs: ../fab/jlcpcb/{gerbers zip, BOM, CPL}, ../fab/pcbway/{gerbers zip, BOM, CPL}, ../fab/step, ../fab/render
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
FAB = os.path.join(HERE, "..", "fab")
PCB = os.path.join(HERE, "openpatch-op100.kicad_pcb")
K = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
NET = json.load(open(os.path.join(HERE, "netlist-fab.json")))["components"]

# value -> (LCSC, MPN, manufacturer, JLC type) ; sources: fab/research.md (JLC/LCSC API 2026-11-18) + JLC parts API
LCSC = {
    ("R", "0R"): ("C17168", "0402WGF0000TCE", "Uniroyal", "Basic"),
    ("R", "1k"): ("C11702", "0402WGF1001TCE", "Uniroyal", "Basic"),
    ("R", "3.16k"): ("C11462", "0402WGF3161TCE", "Uniroyal", "Extended"),
    ("R", "4.7k"): ("C25900", "0402WGF4701TCE", "Uniroyal", "Basic"),
    ("R", "10k"): ("C25744", "0402WGF1002TCE", "Uniroyal", "Basic"),
    ("R", "100k"): ("C25741", "0402WGF1003TCE", "Uniroyal", "Basic"),
    ("R", "1M"): ("C26083", "0402WGF1004TCE", "Uniroyal", "Basic"),
    ("R", "1.5M"): ("C22276", "0402WGF1504TCE", "Uniroyal", "Extended"),
    ("R", "200R"): ("C25087", "0402WGF2000TCE", "Uniroyal", "Basic"),
    ("R", "47k"): ("C25792", "0402WGF4702TCE", "Uniroyal", "Basic"),
    ("R", "10R"): ("C25077", "0402WGF100JTCE", "Uniroyal", "Basic"),
    ("R", "6.8k"): ("C25917", "0402WGF6801TCE", "Uniroyal", "Extended"),
    ("R", "3.3k"): ("C25890", "0402WGF3301TCE", "Uniroyal", "Basic"),
    ("R", "1R0"): ("C140193", "RC-02U1R00FT", "Ralec", "Extended"),
    ("C0402", "100nF"): ("C1525", "CL05B104KO5NNNC", "Samsung", "Basic"),
    ("C0402", "1uF"): ("C52923", "CL05A105KA5NQNC", "Samsung", "Basic"),
    ("C0402", "4.7uF"): ("C23733", "CL05A475MP5NRNC", "Samsung", "Basic"),
    ("C0402", "10nF 25V"): ("C15195", "CL05B103KB5NNNC", "Samsung", "Basic"),
    ("C0402", "22nF 25V"): ("C1532", "0402B223K500NT", "FH", "Basic"),
    ("C0402", "1nF C0G"): ("C307441", "CL05C102JB5NNNC", "Samsung", "Extended"),
    ("C0603", "10uF"): ("C19702", "CL10A106KP8NNNC", "Samsung", "Basic"),
    ("C0603", "10uF 25V"): ("C96446", "CL10A106MA8NRNC", "Samsung", "Basic"),
    ("C0603", "470nF 25V"): ("C1623", "CL10B474KA8NNNC", "Samsung", "Basic"),
    ("C1206", "100nF C0G 25V"): ("C170182", "1206N104J500CT", "Walsin/Fenghua", "Extended"),
    ("U2", ""): ("C55663", "BQ51013BRHLR", "Texas Instruments", "Extended"),
    ("U3", ""): ("C38066", "MCP73832T-2ACI/OT", "Microchip", "Extended"),
    ("U4", ""): ("C2150516", "STSPIN220", "STMicroelectronics", "Extended"),
    ("U5", ""): ("C473912", "TPL5010DDCR", "Texas Instruments", "Extended"),
    ("U6", ""): ("C2677745", "SN74AUP1G74DQER", "Texas Instruments", "Extended"),
    ("U8", ""): ("C3716049", "TMAG5273A1QDBVR", "Texas Instruments", "Extended"),
    ("U9", ""): ("C2152496", "DRV5032FADMRR", "Texas Instruments", "Extended"),
    ("U12", ""): ("C5446", "XC6206P332MR-G", "Torex", "Basic"),
    ("D1", ""): ("C48260", "TPD1E10B06DPYR", "Texas Instruments", "Extended"),
    ("D2", ""): ("C896535", "RB521S30T5G", "onsemi", "Extended"),
    ("Q4", ""): ("C15127", "AO3401A", "AOS", "Basic"),
    ("Q", "2N7002"): ("C8545", "2N7002", "Changjiang", "Basic"),
    ("Q2", ""): ("C3040603", "DMG1013UW", "TECH PUBLIC", "Extended"),
    ("SW1", ""): ("C231329", "B3U-1000P", "Omron", "Extended"),
}
NOT_FAB = {"U1": "ISP1807-LR-RS (LCSC C5264268, stock 0): consigned / sourced by user",
           "MP1": "Hirose FH12-4S-0.5SH(55) FPC connector: not at JLC, consigned or substitute",
           "BT1": "battery spring contacts: provisional, not selected",
           "LRX1": "coil spring contacts: provisional, not selected",
           "J1": "Tag-Connect pads only (no part)"}


def lcsc_for(ref: str, value: str, fp: str):
    pre = "".join(ch for ch in ref if ch.isalpha())
    if ref in NOT_FAB or pre == "TP":
        return None
    if pre == "R":
        return LCSC[("R", value)]
    if pre == "C":
        k = "C1206" if "1206" in fp else "C0603" if "0603" in fp else "C0402"
        return LCSC[(k, value)]
    for key in ((ref, ""), (pre, value), ("U9" if ref in ("U10", "U13") else ref, "")):
        if key in LCSC:
            return LCSC[key]
    return LCSC[(ref, "")]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode not in (0,):
        print("WARN", " ".join(cmd[:4]), r.returncode, r.stderr[-300:])
    return r


def gerbers(outdir: str, name: str):
    os.makedirs(outdir, exist_ok=True)
    tmp = os.path.join(outdir, "_g")
    shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    layers = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
    run([K, "pcb", "export", "gerbers", "--layers", layers, "--no-protel-ext", "--use-drill-file-origin" if False else "--subtract-soldermask", "-o", tmp + "/", PCB])
    run([K, "pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm", "--excellon-separate-th", "-o", tmp + "/", PCB])
    z = os.path.join(outdir, name)
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(tmp)):
            if not f.endswith((".gbrjob", ".rpt")):
                zf.write(os.path.join(tmp, f), f)
    shutil.rmtree(tmp)
    return z


def positions():
    tmp = os.path.join(FAB, "_pos.csv")
    run([K, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", tmp, PCB])
    rows = list(csv.DictReader(open(tmp)))
    os.remove(tmp)
    return rows


def main():
    rows = positions()
    jl = os.path.join(FAB, "jlcpcb"); pw = os.path.join(FAB, "pcbway")
    gerbers(jl, "openpatch-reva-gerbers-jlcpcb.zip")
    gerbers(pw, "openpatch-reva-gerbers.zip")
    bom, cpl_j, cpl_p, notfab = {}, [], [], []
    for r in rows:
        ref = r["Ref"]
        c = NET[ref]
        info = lcsc_for(ref, c["value"], c["fp"])
        if info is None:
            notfab.append((ref, c["value"], NOT_FAB.get(ref, "no part (pad/test point)")))
            continue
        key = (c["value"], c["fp"], info[0])
        bom.setdefault(key, []).append(ref)
        layer = "Top" if r["Side"] == "top" else "Bottom"
        cpl_j.append([ref, r["PosX"], r["PosY"], layer, r["Rot"]])
        cpl_p.append([ref, r["PosX"], r["PosY"], layer, r["Rot"]])
    with open(os.path.join(jl, "BOM-jlcpcb.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (v, fp, lc), refs in sorted(bom.items(), key=lambda x: x[1][0]):
            w.writerow([v, ",".join(sorted(refs)), fp, lc])
    with open(os.path.join(jl, "CPL-jlcpcb.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]); w.writerows(cpl_j)
    with open(os.path.join(pw, "CPL-pcbway.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]); w.writerows(cpl_p)
    with open(os.path.join(pw, "BOM-pcbway.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Quantity", "Manufacturer", "MPN", "Description", "Package", "Type", "LCSC"])
        for (v, fp, lc), refs in sorted(bom.items(), key=lambda x: x[1][0]):
            ref0 = refs[0]
            info = lcsc_for(ref0, v, fp)
            w.writerow([",".join(sorted(refs)), len(refs), info[2], info[1], v, fp, "SMD", lc])
    with open(os.path.join(FAB, "NOT-ASSEMBLED.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["Designator", "Value", "Reason"]); w.writerows(notfab)
    print("exported; BOM lines:", len(bom), "placed parts:", len(cpl_j), "not assembled:", len(notfab))


def extras():
    os.makedirs(os.path.join(FAB, "step"), exist_ok=True)
    os.makedirs(os.path.join(FAB, "render"), exist_ok=True)
    run([K, "pcb", "export", "step", "--force", "--subst-models", "-o",
         os.path.join(FAB, "step", "openpatch-op100.step"), PCB])
    for side in ("top", "bottom"):
        run([K, "pcb", "render", "--side", side, "--width", "1600", "--height", "1000", "--quality", "basic",
             "--background", "opaque", "-o", os.path.join(FAB, "render", f"openpatch-op100-{side}.png"), PCB])


if __name__ == "__main__":
    main()
    extras()
