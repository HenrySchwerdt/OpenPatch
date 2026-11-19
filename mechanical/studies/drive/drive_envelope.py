#!/usr/bin/env python3
"""Envelope / force / lost-motion numbers for sealed (closed-reservoir) plunger drives of the OpenPatch bench pod.

Run:  python3 mechanical/studies/drive/drive_envelope.py      (prints markdown tables, writes drive_envelope.json next to it)

Closed-form from mechanical/params.json plus the constants quoted below.  No CAD.  The CAD of the chosen design is op_inline.py
(`generate.py --variant bench --drive inline`); the 'cup drive, built in CAD' row reproduces its pod lengths (checked against out/bench-inline).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = json.loads((HERE.parent.parent / "params.json").read_text())

H_IN = P["reservoir"]["h_in"]                     # 5.0 bore height (cavity height 6.6 is already full)
A16 = H_IN * (16.0 - H_IN) + math.pi * (H_IN / 2) ** 2
STROKE16 = {v: d["stroke"] for v, d in P["variants"].items()}
VOL = {v: STROKE16[v] * A16 for v in STROKE16}    # mm3: OP-70 ~701, OP-100 1000, OP-200 2000
POD_NOW = {"OP-70": 43.0, "OP-100": 47.0, "OP-200": 60.4}      # side_gears bench pod (out/bench/*.mech.json)
TAIL = P["bench"]["tail_len"]                      # 20.3 mm behind x_r1 (end cap 4.4 + dock / dome)
WALL = P["shell"]["wall"]
END_WALL = P["reservoir_frozen"]["end_wall"]
DEAD, GAP, RWALL = P["reservoir"]["dead"], P["reservoir"]["plunger_gap"], P["reservoir"]["wall"]
PLUNGER = P["reservoir"]["plunger_len"]
CUP_EXTRA = 3.6                                    # = op_inline.CUP_EXTRA
PLUG_SAVING = 4.0                                  # front saving f [mm]: decision spec 3c (no check valve; clamp ring + septum + needle) shrinks the 4.4 mm end cap; the
                                                   # seal/end-cap agent reports the exact number -> 4.0 is an ASSUMPTION, see the sensitivity table (3 / 4 / 5)
GH = P["drive_presets"]["nfp_608_26"]["gh_ratio"]


def area(w): return H_IN * (w - H_IN) + math.pi * (H_IN / 2) ** 2
def perim(w): return 2 * (w - H_IN) + math.pi * H_IN


def length_model(arch: str, stroke: float, x_r0: float) -> float:
    """Pod length [mm]; x_r0 = start of the reservoir behind the gear plane."""
    if arch == "slot":            # current carriage + tongue (leaks)
        return x_r0 + DEAD + stroke + PLUNGER + GAP + RWALL + END_WALL + TAIL + WALL
    if arch == "cup":             # driven screw on the axis, dry cup (nut at the rear plate): the bore is one stroke longer
        return x_r0 + DEAD + stroke + (stroke + CUP_EXTRA) + GAP + RWALL + END_WALL + TAIL + WALL
    if arch == "pushscrew":       # rotating nut at the rear gear plane, translating screw tail behind it, tip pushes a normal plunger
        return WALL + (stroke + 2.6 + 0.5) + 1.4 + 0.2 + DEAD + stroke + PLUNGER + GAP + RWALL + END_WALL + TAIL + WALL
    raise ValueError(arch)


def thrust(I_mA: float, extra_meshes: int, ratio_mult: float = 1.0) -> float:
    """Plunger thrust [N].  sim/REPORT.md: 4.0 N @105 mA and 7.0 N @181 mA with the 16:20 pair -> 0.0387 N/mA; every extra spur mesh x0.95 (sim pair_eff),
    idler pin friction x0.97 per idler; ratio_mult = screw-side torque multiplier relative to the 16:20 pair."""
    return 0.0387 * I_mA * (0.95 ** extra_meshes) * (0.97 ** extra_meshes) * ratio_mult


def seal(w):                      # S2 seal (sim/seal_model): 0.8 N kinetic / 1.2 N breakaway at the 16x5 perimeter 37.7 mm, scales with perimeter
    k = perim(w) / perim(16.0)
    return 0.8 * k, 1.2 * k


def run():
    out = {"sizes": {}, "widths": {}}
    print("## 1. Bore width: stroke, dose per step, seal force (height 5.0 fixed)\n")
    print("| bore W x 5 | area mm2 | stroke OP-70/100/200 mm | perimeter mm | S2 seal kin/break N | U/step @16:20 | volume of 0.1 mm lost motion, U |")
    print("|---|---|---|---|---|---|---|")
    for w in (16, 18, 20, 22, 24):
        a, pm = area(w), perim(w)
        st = {v: VOL[v] / a for v in VOL}
        k, b = seal(w)
        ups = 0.35 / (20 * GH * 1.25) * a / 10.0
        out["widths"][w] = {"area": round(a, 1), "stroke": {v: round(x, 2) for v, x in st.items()}, "perimeter": round(pm, 1), "seal_kin": round(k, 2),
                            "seal_break": round(b, 2), "u_per_step": round(ups, 5)}
        print(f"| {w} x 5 | {a:.1f} | {st['OP-70']:.1f} / {st['OP-100']:.1f} / {st['OP-200']:.1f} | {pm:.1f} | {k:.2f} / {b:.2f} | {ups:.5f} | {0.1 * a / 10:.2f} |")
    print("\n## 2. Pod length by architecture (mm)\n")
    print("| architecture | bore | OP-70 | OP-100 | OP-200 | delta vs 43.0 / 47.0 / 60.4 |")
    print("|---|---|---|---|---|---|")
    rows = [("slot + tongue (current, LEAKS)", "slot", 16, 4.1, 0.0),
            ("cup drive, as built in CAD (gear plane 4.0..5.4)", "cup", 16, 5.5, 0.0),
            ("cup drive, gear plane 2.6..4.0 (lid screws moved)", "cup", 16, 4.1, 0.0),
            ("push screw (rotating nut + translating screw tail)", "pushscrew", 16, 4.1, 0.0),
            ("cup, bore 22 x 5", "cup", 22, 4.1, 0.0), ("cup, bore 24 x 5", "cup", 24, 4.1, 0.0),
            ("cup, bore 16, front saving f", "cup", 16, 4.1, PLUG_SAVING),
            ("cup, bore 22, front saving f", "cup", 22, 4.1, PLUG_SAVING), ("cup, bore 24, front saving f", "cup", 24, 4.1, PLUG_SAVING)]
    for name, arch, w, x0, sav in rows:
        a = area(w)
        L = {v: length_model(arch, VOL[v] / a, x0) - sav for v in VOL}
        d = {v: L[v] - POD_NOW[v] for v in VOL}
        out["sizes"][name] = {"length": {v: round(L[v], 1) for v in L}, "delta": {v: round(d[v], 1) for v in d}}
        print(f"| {name} | {w} x 5 | {L['OP-70']:.1f} | {L['OP-100']:.1f} | {L['OP-200']:.1f} | {d['OP-70']:+.1f} / {d['OP-100']:+.1f} / {d['OP-200']:+.1f} |")
    print(f"\n(f = {PLUG_SAVING} mm front saving assumed in the last three rows; gear plane 2.6..4.0 so x_r0 = 4.1)\n")
    print("### 2b. Sensitivity to the front saving f (delta length vs 43.0 / 47.0 / 60.4, mm)\n")
    print("| bore | f = 0 | f = 3 | f = 4 | f = 5 |")
    print("|---|---|---|---|---|")
    for w in (16, 20, 22, 24):
        cells = []
        for f in (0.0, 3.0, 4.0, 5.0):
            d = {v: length_model("cup", VOL[v] / area(w), 4.1) - f - POD_NOW[v] for v in VOL}
            cells.append(f"{d['OP-70']:+.1f} / {d['OP-100']:+.1f} / {d['OP-200']:+.1f}")
        print(f"| {w} x 5 | " + " | ".join(cells) + " |")
    out["sensitivity"] = {w: {f: {v: round(length_model("cup", VOL[v] / area(w), 4.1) - f - POD_NOW[v], 1) for v in VOL} for f in (0.0, 3.0, 4.0, 5.0)} for w in (16, 20, 22, 24)}
    print("\n## 3. Thrust margin of the cup drive (chain z16 -> z20 -> z17 -> z20 = 3 meshes, 1 idler)\n")
    print("Requirement = S2 breakaway + duckbill 3 kPa + P_occ x A with P_occ = 40 kPa (a detectable occlusion).  margin = thrust / requirement.  "
          "ratio_mult 1.33: z12 motor gear instead of z16 (screw-side torque x1.33, U/step drops by the same factor).\n")
    print("| bore | I mA | ratio_mult | thrust N | requirement N | margin | margin vs breakaway+duckbill only | P_occ reachable kPa | U/step |")
    print("|---|---|---|---|---|---|---|---|---|")
    res = []
    for w in (16, 22, 24):
        a = area(w)
        k, b = seal(w)
        req = b + 0.003 * a + 0.040 * a
        for I in (105, 160, 181):
            for rm in (1.0, 20 / 12 / 1.25):
                F = thrust(I, 2, rm)
                pocc = (F - k - 0.003 * a) / a * 1000
                ups = 0.35 / (20 * GH * 1.25 * rm) * a / 10.0
                res.append({"w": w, "I": I, "ratio_mult": round(rm, 3), "F": round(F, 2), "req": round(req, 2), "margin": round(F / req, 2), "margin_breakaway": round(F / (b + 0.003 * a), 2),
                            "pocc_kPa": round(pocc), "u_per_step": round(ups, 5)})
                print(f"| {w} x 5 | {I} | {rm:.2f} | {F:.2f} | {req:.2f} | {F / req:.2f} | {F / (b + 0.003 * a):.2f} | {pocc:.0f} | {ups:.5f} |")
    out["thrust"] = res
    print("\n## 4. Lost motion and compliance of the cup drive\n")
    print("| item | axial mm | volume at 16x5, U | at 22x5, U |")
    print("|---|---|---|---|")
    for name, mm in (("thread backlash M1.6 x 0.35 nut (assumed)", 0.08), ("thread backlash, worst case", 0.15),
                     ("train compliance at 7 N (tube 0.25 um + screw 0.5 um + nut thread ~5 um + PA12 plate ~10 um)", 0.016)):
        print(f"| {name} | {mm} | {mm * area(16) / 10:.2f} | {mm * area(22) / 10:.2f} |")
    print("\nOld tongue train: 0.10 U per 3 N wind-up (sim 4.2) plus socket/nut play ~2.2 U at every reversal.  The cup drive has no socket and no tongue.")
    (HERE / "drive_envelope.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    run()
