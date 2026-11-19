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
    if arch == "coax":            # translating screw through a rotating nut on gear_d (op_inline coaxial): the gear/sleeve/bush stack overlaps the screw tail
        return 2 * stroke + 31.7
    raise ValueError(arch)


def thrust(I_mA: float, extra_meshes: int, ratio_mult: float = 1.0) -> float:
    """Plunger thrust [N].  sim/REPORT.md: 4.0 N @105 mA and 7.0 N @181 mA with the 16:20 pair -> 0.0387 N/mA; every extra spur mesh x0.95 (sim pair_eff),
    idler pin friction x0.97 per idler; ratio_mult = screw-side torque multiplier relative to the 16:20 pair."""
    return 0.0387 * I_mA * (0.95 ** extra_meshes) * (0.97 ** extra_meshes) * ratio_mult


def seal(w):                      # S2 seal (sim/seal_model): 0.8 N kinetic / 1.2 N breakaway at the 16x5 perimeter 37.7 mm, scales with perimeter
    k = perim(w) / perim(16.0)
    return 0.8 * k, 1.2 * k


SQUEEZE = {"screw rear clearance 1.2 -> 0.5": 0.7, "rear dry strip 1.0 -> 0.3": 0.7, "dead layer 1.0 -> 0.8 (nose 0.5)": 0.2, "plunger core 3.8 -> 3.2": 0.6,
           "plunger gap 0.2 -> 0.1": 0.1, "closed end wall 2.5 -> 2.0 (port d2.0 needs 2.0)": 0.5}
SQ = sum(SQUEEZE.values())          # 2.8 mm, all inside the (re-ordered) CNC reservoir and the rear stack
W_MAX = 22.4                        # 30.2 cavity - 6.2 motor lane = 24.0 outer - 2 x 0.8 wall
TARGETS = {"OP-100": (45.0, 1000.0), "OP-200": (52.0, 2000.0)}          # spec 2b/2c integrated v0.1.0: hard targets (drive + reservoir + front + dock only)


def coax_len(s: float, f: float, sq: float) -> float:
    """Coaxial translating screw: x_r0 = s + 2.2, reservoir s + 8.3, front + wall 21.2 (20.3 + 0.9); f = front saving, sq = squeezes."""
    return 2 * s + 31.7 - f - sq


def slot_len(s: float, f: float, sq: float) -> float:
    return 4.1 + s + 8.3 + 21.2 - f - sq


def targets(out: dict) -> None:
    print("\n### 2c. Hard targets of the integrated v0.1.0 (OP-100 <= 45, OP-200 <= 52 mm; OP-70 dropped)\n")
    print(f"Squeezes assumed (all inside the re-ordered CNC reservoir and the rear stack): total {SQ:.1f} mm = " + "; ".join(f"{k} (-{v})" for k, v in SQUEEZE.items()) + ".")
    print(f"Widest bore: cavity 30.2 - motor lane 6.2 = 24.0 outer - 2 x 0.8 wall = **{W_MAX} x 5** (area {area(W_MAX):.1f} mm2).  Slot/tongue designs also need a 4.9 mm carriage lane: bore <= 17.5.\n")
    print("| size | architecture | bore | f | squeeze | stroke mm | length mm | vs target | max volume that fits, U |")
    print("|---|---|---|---|---|---|---|---|---|")
    rec = {}
    for size, (tgt, vol) in TARGETS.items():
        for arch, w in (("coax translating screw", W_MAX), ("coax translating screw", 20.0), ("coax translating screw", 16.0), ("slot + tongue (leaks, reference)", 17.5)):
            for f in (3.0, 4.0, 5.0):
                for sq in (0.0, SQ):
                    a = area(w)
                    s = vol / a
                    fn = coax_len if arch.startswith("coax") else slot_len
                    L = fn(s, f, sq)
                    k = 31.7 if arch.startswith("coax") else 33.6
                    smax = (tgt - k + f + sq) / 2 if arch.startswith("coax") else tgt - k + f + sq
                    if w != W_MAX and arch.startswith("coax") and (f != 4.0 or sq == 0.0):
                        continue
                    if not arch.startswith("coax") and (f != 4.0 or sq == 0.0):
                        continue
                    if arch.startswith("coax") and w == W_MAX and sq == 0.0 and f != 4.0:
                        continue
                    print(f"| {size} | {arch} | {w:g} x 5 | {f:g} | {sq:.1f} | {s:.2f} | {L:.1f} | {L - tgt:+.1f} | {smax * a / 10:.0f} |")
                    rec[f"{size}|{arch}|{w}|{f}|{sq}"] = {"stroke": round(s, 2), "length": round(L, 1), "delta": round(L - tgt, 1), "max_U": round(smax * a / 10)}
    out["targets"] = rec
    print("\nReading: OP-100 <= 45 is reachable with the coaxial screw only at the widest bore (22.4 x 5), f >= 3 and all squeezes (43.7 at f = 4, 44.7 at f = 3; 46.5 at f = 4 without squeezes = over);\n"
          "OP-200 <= 52 is not reachable by the coaxial sealed drive (best 62.4 at f = 4 with all squeezes, 10 mm over; it would hold about 144 U in 52 mm).  The leaking slot + tongue design is the only\n"
          "architecture here that reaches 52 for 200 U (51.2 mm with a 17.5 x 5 bore, f = 4 and all squeezes) - a sealed slot or a flexible element would be needed to keep that.\n")


def bore_for_lane(lane: float) -> float:
    """widest bore when a motor lane of width `lane` (motor d + 0.3 clearance) sits beside the reservoir: cavity 30.2 - lane - 2 x 0.8 wall"""
    return 30.2 - lane - 1.6


def motors(out: dict) -> None:
    """Coaxial translating screw with the NFP-608 (d6 x 19.1 stack) or the Zhaowei d3.4 stepper gearbox (13.3 / 14.8 mm, docs/MOTOR-RESEARCH-2026-11-19.md)."""
    print("\n### 2d. Motor variants of the coaxial translating screw (f = 4, all squeezes unless stated; targets OP-100 45 / OP-200 52)\n")
    print("| motor | placement | bore | OP-100 stroke / length | vs 45 | OP-200 stroke / length | vs 52 | max U in 45 / 52 mm | U/step (1:1 chain) |")
    print("|---|---|---|---|---|---|---|---|---|")
    f, sq = 4.0, SQ
    rows = []
    # NFP beside the reservoir (19.1 stack, d6, ratio 26.45 x 20/16)
    rows.append(("NFP-608 d6", "beside the reservoir (as now), gear plane at the nut", bore_for_lane(6.2), "beside", 19.1, 0.35 / (20 * 26.45 * 1.25)))
    # Zhaowei d3.4: beside (lane 3.6) with a gear chain, 36:1 (13.3 mm)
    rows.append(("Zhaowei d3.4 36:1 (13.3 mm)", "beside the reservoir, 3-mesh chain, 1:1", bore_for_lane(3.6), "beside", 13.3, 0.35 / (20 * 36)))
    rows.append(("Zhaowei d3.4 216:1 (14.8 mm)", "beside the reservoir, 3-mesh chain, 1:1", bore_for_lane(3.6), "beside", 14.8, 0.35 / (20 * 216)))
    # Zhaowei in the rear zone parallel to the screw tail (reservoir full width 28.6)
    rows.append(("Zhaowei d3.4 36:1 (13.3 mm)", "in the rear zone beside the screw tail (reservoir full width)", bore_for_lane(0.0) , "rear", 13.3, 0.35 / (20 * 36)))
    for name, place, w, kind, Lm, mm_step in rows:
        a = area(w)
        cells, mx = [], []
        for size, (tgt, vol) in TARGETS.items():
            s = vol / a
            if kind == "beside":
                L = coax_len(s, f, sq)
                if Lm > s + 8.3 - 2.0 + 2.0:                     # motor longer than the reservoir: tail overhang into the front zone (flagged in the study)
                    pass
                smax = (tgt - 31.7 + f + sq) / 2
            else:
                x_r0 = max(s + 2.2, Lm + 2.9)                    # motor behind the gear plane: x_nf = 0.9 + Lm + 0.1 + 2.7, x_r0 = x_nf - 0.8
                L = x_r0 + s + 8.3 + 21.2 - f - sq
                smax = tgt - 21.2 + f + sq - 8.3 - (Lm + 2.9) if (tgt - 21.2 + f + sq - 8.3 - (Lm + 2.9)) < (tgt - 31.7 + f + sq) / 2 else (tgt - 31.7 + f + sq) / 2
            cells.append((s, L, L - tgt))
            mx.append(smax * a / 10)
        ups = mm_step * a / 10
        print(f"| {name} | {place} | {w:.1f} x 5 | {cells[0][0]:.2f} / **{cells[0][1]:.1f}** | {cells[0][2]:+.1f} | {cells[1][0]:.2f} / **{cells[1][1]:.1f}** | {cells[1][2]:+.1f} | {mx[0]:.0f} / {mx[1]:.0f} U | {ups:.4f} |")
        out.setdefault("motors", {})[f"{name}|{place}"] = {"bore": round(w, 1), "op100": [round(cells[0][0], 2), round(cells[0][1], 1)], "op200": [round(cells[1][0], 2), round(cells[1][1], 1)], "u_per_step": round(ups, 5)}
    print("\nCoaxial *direct* drive (motor behind the screw, cup variant, screw rotating) adds the whole motor length in series: OP-100 about "
          f"{0.9 + 13.3 + 2.5 + 1 + 7.27 + 7.27 + 3.6 + 0.2 + 3.3 + 21.2 - 4 - 2.8:.1f} mm (28.6 bore, 13.3 mm motor) - rejected.  The translating-screw variant cannot use a coaxial motor at all (the tail needs the axis).\n"
          "A beside motor of d3.4 only needs a 3.6 mm lane (bore 25.0 vs 22.4), the motor (13-15 mm) is shorter than the reservoir (no overhang), the port is off-centre by up to 3 mm.\n")


def nfp_chain(out: dict) -> None:
    """Recompute the NFP-608-26.45 thrust chain from the datasheet point (pull-out 1.6 gf*cm @ 500 pps at rated 181 mA) - reconciles the '1.6 gf*cm -> ~6 N' question."""
    print("\n### 2e. NFP thrust chain recomputed (datasheet 1.6 gf*cm pull-out @ 500 pps, 4.8 V / 26.5 ohm = 181 mA rated)\n")
    T_m = 1.6 * 0.0980665                      # N*mm  (1 gf*cm = 0.0980665 N*mm)
    d, pit = 1.6, 0.35
    d2 = d - 0.6495 * pit
    lam = math.atan(pit / (math.pi * d2))
    ca = math.cos(math.radians(30))
    mu_t, mu_c, rm = 0.22, 0.18, 1.205
    thread = d2 / 2 * (math.tan(lam) + mu_t / ca) / (1 - mu_t * math.tan(lam) / ca)
    collar = mu_c * rm
    rows = []
    T1 = T_m * 26.45
    T2, T3 = T1 * 0.64, T1 * 0.64 * 1.25 * 0.95
    print("| step | value |")
    print("|---|---|")
    print(f"| motor pull-out torque 1.6 gf*cm | {T_m:.3f} N*mm (0.157 mN*m) |")
    print(f"| x 26.45 planetary (ideal) | {T1:.2f} N*mm |")
    print(f"| x 0.64 gearhead efficiency (sim, 2-stage planetary) | {T2:.2f} N*mm |")
    print(f"| x 1.25 (z16 -> z20) x 0.95 pair efficiency | {T3:.2f} N*mm at the screw |")
    print(f"| thread torque per N: d2 = {d2:.3f} mm, lead angle {math.degrees(lam):.2f} deg, mu 0.22 | {thread:.3f} N*mm/N (thread efficiency {pit / (2 * math.pi) / thread * 100:.0f} %) |")
    print(f"| thrust-collar / bush-face friction: mu 0.18 x r_m {rm} mm | {collar:.3f} N*mm/N |")
    tot = thread + collar
    print(f"| total | {tot:.3f} N*mm/N -> overall screw efficiency {pit / (2 * math.pi) / tot * 100:.0f} % |")
    for I in (105, 160, 181):
        F = T3 * I / 181 / tot
        rows.append((I, round(F, 2)))
        print(f"| thrust at {I} mA (torque proportional to current) | **{F:.1f} N** |")
    ideal = 2 * math.pi * 0.25 * (T_m * 26.45 * 1.25) / pit
    print(f"\nReconciliation: with only a thread efficiency of 0.25 and ideal gears the chain gives {ideal:.0f} N ('more than 6 N' as the motor research notes); the sim chain adds the gearhead efficiency 0.64, the pair 0.95 and,"
          f" above all, the thrust-collar friction (about as large as the thread friction: overall screw efficiency {pit / (2 * math.pi) / tot * 100:.0f} % instead of 25 %).  Result {rows[2][1]} N at 181 mA, {rows[1][1]} N at 160 mA,"
          f" {rows[0][1]} N at 105 mA = the sim values (7.0 / ~6.4 / 4.0): **the '6 N' is a 160 mA figure of the full chain, not of the ideal one; the 1.6 gf*cm datasheet point does reconcile.**"
          " Direct drive with the Zhaowei gearbox: required output torque = 7 N x 0.452 = 3.2 N*mm = 3.2 mN*m (gearbox limit 13.7 mN*m: ok) -> motor torque 0.12 mN*m (1.2 gf*cm) at 36:1 (eta 0.73) or 0.023 mN*m (0.23 gf*cm) at 216:1 (eta 0.65): unverified for a d3.4 motor.\n")
    out["nfp_chain"] = {"thread": round(thread, 3), "collar": round(collar, 3), "F": dict(rows)}


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
            ("push screw, tail NOT overlapped by the gear stack (old estimate)", "pushscrew", 16, 4.1, 0.0),
            ("**coaxial translating screw, as built in CAD** (rear zone s + 2.2)", "coax", 16, 0.0, 0.0),
            ("coaxial translating screw, bore 22.4 x 5", "coax", 22.4, 0.0, 0.0),
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
    targets(out)
    motors(out)
    nfp_chain(out)
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
