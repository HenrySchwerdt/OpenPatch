#!/usr/bin/env python3
"""Build out/fab/ - the upload folder for JLC3DP / PCBWay 3D printing (and optional CNC).

  python3 fab.py            # after generate.py

Creates out/fab/<SIZE>/<part>.stl|step, out/fab/mould/, out/fab/MANIFEST.csv and out/fab/README.md
(per-file process / material / colour / finish / qty / tolerance notes, vendor notes, cost estimate per iteration).
Price numbers are ESTIMATES (see README) - always confirm with the live instant quote.
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from op_layout import HERE, find_cli, load_params

import argparse
import sys

BENCH = "--variant" in sys.argv and sys.argv[sys.argv.index("--variant") + 1] == "bench"
OUT = HERE / "out" / "bench" if BENCH else HERE / "out"
FAB = OUT / "fab"
CLI = find_cli()

# part -> (process, material, colour, finish, qty per size set, tolerance / notes, upload?)
PARTS = {
    "bottom": ("MJF PA12 (JLC3DP: PA12-HP Nylon; PCBWay: MJF Nylon PA12)", "PA12", "grey (natural, cheapest)",
               "bead-blasted standard; NO dye/vapour smoothing", 1,
               "+-0.2 mm. Post-drill by hand: needle bore dia 0.5, M1.2 pilot dia 1.0 (test-fit), ream hub seat dia 2.0. "
               "Cannula pocket: TODO-MEASURE, order N_clearance 0.10/0.15/0.20 coupons first. Porous: NOT watertight.", True),
    "top": ("MJF PA12", "PA12", "grey (natural)", "bead-blasted standard", 1,
            "+-0.2 mm. 0.5 mm button membrane is at the printable limit - order 2 and keep the better one. "
            "Acoustic port dia 1.2 and screw holes dia 1.4 may need a drill.", True),
    "carriage": ("SLA (JLC3DP: resin 8001 / 9000-type tough; PCBWay: SLA Somos/8000-type)", "tough resin", "any (white/grey)",
                 "support marks on the outside only; do not sand the hex pocket", 2,
                 "+-0.1 mm (hex pocket AF 3.8 = DIN 934 M1.6 AF 3.2 + 0.6 clearance (0.3 mm radial float), closed rear wall + top drop-in slot, dia 1.9 screw bore, rail groove 1.2 x 0.5). Order 2: nut fit is the first test.", True),
    "plunger_core": ("SLA", "tough or clear resin", "any", "no coating", 2,
                     "+-0.1 mm. Seal grooves (0.8 mm wide) + socket for carriage tongue. Water test only.", True),
    "reservoir": ("SLA (clear resin preferred, 'BioMed Clear'-class if offered, else standard clear)", "clear resin",
                  "clear", "wash + UV post-cure; inner bore stays unpolished", 1,
                  "WATER ONLY (SLA copy; the CNC PP part in reservoir-cnc/ is only a material preparation for a future manufacturer) - not sterile, not validated. +-0.1 mm; check bore 16.0 x 5.0 with a "
                  "pin gauge; bore may need light honing. Single piece; open dry end.", True),
    "reservoir_cnc_lower": ("CNC (PCBWay CNC; polypropylene) - OPTIONAL, expensive", "PP natural", "natural", "as machined", 1,
                            "Half of the reservoir (split at bore centre plane). Bond halves after machining. Only for the later "
                            "optional material preparation (never filled with insulin); not part of the cheap monthly loop.", False),
    "reservoir_cnc_upper": ("CNC (PCBWay CNC; polypropylene) - OPTIONAL", "PP natural", "natural", "as machined", 1, "see lower half", False),
    "plunger_seal": ("DO NOT ORDER - cast in the mould (silicone bead seal, Shore A 30, S1/S2/T)", "-", "-", "-", 0,
                     "Reference geometry (assembly state). Cast with mould_lower/upper.", False),
    "gasket": ("DO NOT ORDER - die-cut / laser-cut 0.5 mm silicone sheet, Shore A 40-50, ring 0.4 mm wide, or dispense a 0.5 mm bead", "-", "-", "-", 0,
               "Reference geometry (compressed state 0.45 mm). A 0.4 mm wide ring is fragile: cut it from 0.5 mm sheet with ~0.8 mm webs or use FIPG.", False),
}
# bench pod: same parts minus CNC reservoir halves; plus the dummy cannula head (adapter)
BENCH_PARTS = {k: v for k, v in PARTS.items() if not k.startswith("reservoir_cnc")}
BENCH_PARTS["bottom"] = (PARTS["bottom"][0], "PA12", "grey (natural)", "bead-blasted standard; NO dye/vapour smoothing", 1,
                         "+-0.2 mm. Contains the dock: two snap arms 0.8 mm thick x 9.5 mm free length (hook travel 1.8 mm, ~2.4 % strain). "
                         "ORDER THE DOCK COUPON FIRST. Post-drill by hand: M1.2 pilot dia 1.0 (x5), hub bore dia 2.0 (test-fit), fluid channel dia 0.7. "
                         "FFC exit slot is in the lid. Porous: NOT watertight.", True)
BENCH_PARTS["top"] = ("SLA clear resin (JLC3DP clear, spec 2a)", "clear resin", "clear (polish / clear-coat the outside)", "wash + UV; no window slot: the wall is closed", 1,
                      "+-0.1 mm. CLEAR LID: reservoir, water level and drive are visible through it. Fill scale = 0.15 mm engraving on the inner face (tick / 10 U, long / 50 U). FFC slot 8.0 x 1.1 mm in the +X wall, dome mouth in the lap. Screw holes dia 1.4 may need a drill. WATER ONLY.", True)
BENCH_PARTS["end_cap"] = ("SLA (tough resin; later PP / CNC)", "tough resin", "any", "no coating; clear internal channels d0.7 with a 0.5 mm wire", 2,
                          "+-0.05 mm. End cap pressed onto the d2.0 H7 port of the CNC reservoir (spigot d1.98 x 2.4, locating only; sealed by a face O-ring 2.0 x 0.5 in the cap groove): fill septum bore d3.4 (15 % radial compression on the d4.0 disc, side), duckbill pocket d3.05 with open slot, needle guard tube d3.2 / bore d2.0, "
                          "main channels d0.6 (short), fill branch d0.8; needle hub bore d1.92 (press fit). WATER ONLY in SLA resin.", True)
BENCH_PARTS["coupler"] = ("SLA (tough resin) - or turned brass tube (preferred)", "tough resin / brass", "any", "no coating", 2,
                          "+-0.05 mm. Sleeve coupler d3.0 x 6.0: D-bore d2.04 / flat 1.5 (3.2 deep) for the NFP shaft, M1.6 bore d1.64 (2.8 deep) for the leadscrew; "
                          "retain with one drop of cyanoacrylate / Loctite 638. VERIFY the shaft D-flat on the real motor.", True)
BENCH_PARTS["plunger_nose"] = ("SLA (JLC3DP resin 8001-type)", "tough resin", "any", "no coating", 2,
                               "+-0.1 mm. 0.7 mm stadium disc (14.6 x 3.6) glued (CA) onto the plunger front: dead layer 0.3 mm. WATER ONLY.", True)
BENCH_PARTS["end_cap_lid"] = ("SLA (JLC3DP resin 8001-type)", "tough resin", "any", "no coating", 2,
                              "+-0.05 mm. Upper half of the clamped fluid sandwich: flat underside on the lands, valve / septum ceiling recesses, O-ring half groove, 2 x M1.2 x 6 clamp screws. WATER ONLY.", True)
BENCH_PARTS["thrust_sleeve"] = ("SLA, or brass tube d2.0 x d1.6 x 2.05 (cut + deburr)", "tough resin / brass", "any", "no coating", 2,
                                "+-0.05 mm. Gear carrier and rear thrust shoulder: slides on the rod, rear face on the dry bush, GHW 753020 (bore 2.0) glued on it (Loctite 638). "
                                "Printed d2.0 walls are thin: brass tube recommended.", True)
BENCH_PARTS["thrust_collar"] = ("SLA, or brass tube d2.4 x d1.6 x 1.0", "tough resin / brass", "any", "no coating", 2,
                                "+-0.05 mm. Front thrust shoulder at the rod end: bears on the far bush face; the magnet is glued to the rod end behind it and carries no thrust.", True)
BENCH_PARTS["dock_insert"] = ("SLA (JLC3DP resin 8001-type) or MJF PA12", "tough resin / PA12", "any", "support marks off the arms", 12,
                              "SHARED by all sizes, shipped from dock-inserts/ (12 variants + fixture). +-0.1 mm. Swappable cannula interface (spec 8a): "
                              "frozen interface dock_interface_frozen in params.json.", False)
BENCH_PARTS["cannula_adapter"] = ("SLA (JLC3DP resin 8001-type; PCBWay SLA)", "tough resin", "clear or white", "support marks off the dome sides and the notches",
                                  2, "+-0.1 mm. Dummy cannula head (dome d 10, base plate, side septum recess d 3.6, two latch notches, hose barb d 1.6, magnet "
                                     "pocket d 2.1 x 1.05 in the rear lug). Glue a d2x1 N52 magnet (CA drop) and press a punched d2 silicone plug "
                                     "into the septum bore. Dimensions follow cannula.* placeholders (TODO-MEASURE).", True)
MOULD = ("SLA (high detail, e.g. JLC3DP 8001 / PCBWay SLA)", "tough resin", "any", "print each half standing on its short end (cavity axis vertical), wash + UV cure; clear sprue dia 0.8 / vent dia 0.5", 1,
         "THREE seal variants (S1, S2, T) = 3 sets for ALL sizes (SEAL-AND-DEAD-VOLUME.md). +-0.05 mm. Check the 4 pin/hole fits (pin dia 2.0 / hole 2.2).")

# --- price model (ESTIMATES, USD) ------------------------------------------------------------
MJF_PER_G, MJF_MIN_PART, MJF_BILL_FACTOR, PA12_DENSITY = 0.28, 1.5, 1.6, 1.0
SLA_PER_CM3, SLA_MIN_PART, SLA_BILL_FACTOR = 0.25, 2.0, 1.5
SHIP_EST = (8.0, 18.0)


def volumes(sc: Path, names: list[str]) -> dict[str, float]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump([{"command": "inspect.measure", "params": {}}], fh)
        tmp = fh.name
    r = subprocess.run([CLI, "run", tmp, "--in", str(sc), "--results", "--quiet"], capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    d = json.loads(r.stdout)
    m = next(x for x in d if "bodies" in x)
    return {b["name"]: b.get("volume_mm3", 0.0) / 1000.0 for b in m["bodies"] if b["name"] in names}




def write_bench_readme(p: dict, vols: dict, sizes: list, PARTS: dict) -> None:
    def cost(sz: str, part: str, qty: int) -> float:
        vol = vols[sz].get(part, 0.0)
        if PARTS[part][0].startswith("MJF"):
            return qty * max(MJF_MIN_PART, vol * PA12_DENSITY * MJF_BILL_FACTOR * MJF_PER_G)
        return qty * max(SLA_MIN_PART, vol * SLA_BILL_FACTOR * SLA_PER_CM3 * 4)
    cols = [("bottom", 1), ("top", 1), ("carriage", 2), ("plunger_core", 2), ("plunger_nose", 2), ("reservoir", 1), ("cannula_adapter", 2), ("end_cap", 2), ("end_cap_lid", 2), ("thrust_sleeve", 2), ("thrust_collar", 2)]
    lines = ["| size | " + " | ".join(f"{c} x{q}" for c, q in cols) + " | subtotal |", "|---|" + "---|" * (len(cols) + 1)]
    tot = 0.0
    sub = {}
    for sz in sizes:
        c = [cost(sz, k, q) for k, q in cols]
        sub[sz] = sum(c)
        tot += sub[sz]
        lines.append(f"| {sz} | " + " | ".join(f"${x:.1f}" for x in c) + f" | ${sum(c):.1f} |")
    mould = 6 * max(SLA_MIN_PART, 14.0 * SLA_BILL_FACTOR * SLA_PER_CM3 * 4)
    coupon = SLA_MIN_PART * 12 + MJF_MIN_PART
    single = min(sub.values())
    readme = f"""# OpenPatch bench pod - fabrication folder (`out/bench/fab/`)

EXPERIMENTAL bench test sample (Rev A bench split, spec 4a): water only, NEVER on a person. No battery, Qi coil, RF module or
main PCB: the pod carries only the 2-layer pod sensor board (ordered separately as PCBA, see `electronics/`) and an FFC cable
to the bench controller. Folders: `OP-70/`, `OP-100/`, `OP-200/` (upload), `mould/` (three seal-variant sets, valid for all sizes), `dock-inserts/`
(12 swappable dock insert variants + pod-less fixture, order FIRST), `reservoir-sla-water-only/` (print copy of the frozen reservoir, WATER ONLY), `MANIFEST.csv`. Units mm; STEP is master, STL (fine) for the quote tool.

## Order sheet (every size)

| file | process | material | colour | finish | qty / size | tolerance, notes |
|---|---|---|---|---|---|---|
""" + "\n".join(f"| `<SIZE>/{k}.stl` | {v[0]} | {v[1]} | {v[2]} | {v[3]} | {v[4]} | {v[5]} |" for k, v in PARTS.items() if v[6]) + f"""
| `mould/mould*_lower.stl`, `mould*_upper.stl` (3 variants S1, S2, T) | {MOULD[0]} | {MOULD[1]} | {MOULD[2]} | {MOULD[3]} | 3 sets (all sizes) | {MOULD[5]} |
| `dock-inserts/insert_v01..v12.stl` | SLA tough resin (or MJF PA12) | tough resin / PA12 | any | support marks off arms | 12 (shared by all sizes) | swappable dock insert variants (ID on the -Y arm), see `variants.csv` |
| `dock-inserts/dock_fixture.stl` | MJF PA12 or SLA | PA12 / tough resin | any | standard | 1 | pod-less fixture with the frozen dock interface: fit the inserts to a real cannula head without a pod |
| `reservoir-sla-water-only/<SIZE>_reservoir_WATER-ONLY_sla.stl` | SLA clear resin | clear | clear | wash + UV | 1 per size | **WATER ONLY - never insulin or any drug** (printed resin is not validated for any drug). Print copy of the frozen reservoir geometry; the CNC PP part in `reservoir-cnc/` is an optional material preparation, also never filled with insulin |

Not uploaded (`reference_not_ordered/`): `plunger_seal` (cast in the mould) and `gasket` (cut from 0.5 mm silicone sheet).
The reservoir is an SLA clear part (water test only), same as the integrated variant. CNC reservoir halves are not part of the bench loop.

## Process recommendation
* Housing (bottom/top): MJF PA12 grey - the snap arms are designed for PA12 (E about 1.7 GPa, 2.4 % strain at 1.8 mm hook travel).
  If JLC3DP flags the 0.8 mm arms or 0.4 mm lap tongue, re-order the same files in SLA tough resin (stiffer: arm force rises, retest with the insert set).
* Carriage, plunger core, cannula adapter, mould: SLA tough resin. Reservoir: SLA clear.
* Vendor: JLC3DP default (one order, one shipment with the PCBA); PCBWay as fallback. See `../../fab/vendor-notes.md` for notes.

## Estimated cost per iteration (ESTIMATE - confirm with the instant quote)

Price model identical to the integrated variant (MJF {MJF_PER_G:.2f} USD/g x {MJF_BILL_FACTOR}, min {MJF_MIN_PART:.1f} USD/part; SLA min {SLA_MIN_PART:.1f} USD/part). Shipping {SHIP_EST[0]:.0f}-{SHIP_EST[1]:.0f} USD (one order).

{chr(10).join(lines)}

* Printed parts for ONE pod size: about **${single:.0f}** (+ shipping); all three sizes: about **${tot:.0f}**.
* Dock insert set (12 SLA inserts + 1 fixture): about ${coupon:.0f} - order it with the first pod batch, it decides the cannula.* values; later iterations only need the inserts that changed.
* Mould (once, reusable): about ${mould:.0f}.
* Per iteration (1 size + coupon + shipping, no mould): about **${single + coupon + SHIP_EST[0]:.0f} - ${single + coupon + SHIP_EST[1]:.0f}**; repeat iterations without coupon about ${single + SHIP_EST[0]:.0f} - ${single + SHIP_EST[1]:.0f}.
* Not included: pod sensor board PCBA (see electronics), motor (reusable), spring contacts, FFC cable, magnets, needle hubs: see `../ASSEMBLY.md`.
"""
    (FAB / "README.md").write_text(readme, encoding="utf-8")
    (FAB / "vendor-notes.md").write_text("See ../../fab/vendor-notes.md (same vendors and process names).\n", encoding="utf-8")
    print(f"bench fab folder written: {FAB}; one size about {single:.0f} USD printed parts (estimate)")


def write_shim(p: dict, out: Path, fab: Path, rows: list) -> None:
    """Stainless tongue shim (purchased/laser-cut): DXF + SVG drawing, 0.5 x 1.4 mm strip."""
    import ezdxf
    sh, sl, dr = p["bench"]["shim"], p["seal"], p["drive"]
    L = json.loads((out / "OP-100.mech.json").read_text())
    y_end = L["y_r"] + (p["reservoir"]["w_in"] - 2 * p["reservoir"]["plunger_clr"]) / 2
    y_face = L["y_s"] - dr["carriage_bw"] / 2
    length = (y_face + sh["pocket_depth"] - 0.1) - (y_end - sl["socket_depth"] + 0.1)
    d = fab / "tongue-shim"
    d.mkdir(exist_ok=True)
    h, c = sh["h"], 0.15
    pts = [(c, 0), (length - c, 0), (length, c), (length, h - c), (length - c, h), (c, h), (0, h - c), (0, c)]
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    msp.add_lwpolyline(pts, close=True)
    msp.add_text(f"OpenPatch tongue shim, stainless 1.4301 (304), t = {sh['t']} mm, laser cut or hand cut from 0.5 mm strip", height=0.5, dxfattribs={"insert": (0, -2.0)})
    msp.add_text(f"{length:.2f} x {h:.2f} mm, corners C0.15, burr-free. Glued (CA) into the carriage pocket. WATER ONLY bench pump.", height=0.5, dxfattribs={"insert": (0, -3.0)})
    doc.saveas(d / "tongue_shim.dxf")
    s = 20.0
    poly = " ".join(f"{20 + x * s:.1f},{60 - y * s:.1f}" for x, y in pts)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(length * s + 80)}" height="130" viewBox="0 0 {int(length * s + 80)} 130">'
           f'<rect width="100%" height="100%" fill="white"/><polygon points="{poly}" fill="#dddddd" stroke="#222" stroke-width="1.2"/>'
           f'<text x="20" y="20" font-size="12" font-family="sans-serif">Tongue shim, stainless 1.4301, thickness {sh["t"]} mm (purchase / laser cut)</text>'
           f'<text x="20" y="100" font-size="12" font-family="sans-serif">length {length:.2f}   width {h:.2f}   (to scale x20)   corners C0.15</text>'
           f'<text x="20" y="116" font-size="11" font-family="sans-serif">Glued (CA) into the carriage pocket; free end enters the plunger socket. Water-only bench pump.</text></svg>')
    (d / "tongue_shim.svg").write_text(svg, encoding="utf-8")
    (d / "README.md").write_text(f"# Tongue shim (stainless 0.5 x {h} x {length:.2f} mm)\n\nLaser-cut or hand-cut from 0.5 mm stainless strip (feeler gauge stock works). `tongue_shim.dxf` / `.svg`. "
                                 f"Replaces the printed carriage tongue (sim 4.4-4.6). Water-only bench pump, never on a person.\n", encoding="utf-8")
    rows.append(["tongue-shim/tongue_shim.dxf", "laser cut / hand cut (stainless 1.4301 strip, 0.5 mm)", "stainless 304", "-", "deburr", 2,
                 f"{length:.2f} x {h:.2f} x {sh['t']} mm, +-0.05; glued into the carriage pocket", ""])


def main() -> None:
    p = load_params(OUT / "params.used.json") if (OUT / "params.used.json").exists() else load_params()
    PARTS = BENCH_PARTS if BENCH else globals()["PARTS"]
    if FAB.exists():
        for child in FAB.iterdir():          # keep dock-coupon/ (built by generate.py --coupon)
            if child.name not in ("dock-coupon", "dock-inserts", "stencil", "reservoir-cnc", "reservoir-sla-water-only", "tongue-shim"):
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    FAB.mkdir(parents=True, exist_ok=True)
    rows, vols = [], {}
    sizes = list(p["variants"])
    for sz in sizes:
        d = FAB / sz
        d.mkdir()
        v = volumes(OUT / f"{sz}.sc", ["bottom", "top", "carriage", "plunger_core", "plunger_nose", "reservoir", "cannula_adapter", "end_cap", "end_cap_lid", "thrust_sleeve", "thrust_collar"])
        vols[sz] = v
        for part, (proc, mat, col, fin, qty, tol, upload) in PARTS.items():
            if not upload:
                continue
            for ext in ("stl", "step"):
                src = OUT / f"{sz}_{part}.{ext}"
                if src.exists():
                    shutil.copy(src, d / f"{part}.{ext}")
            rows.append([f"{sz}/{part}.stl", proc, mat, col, fin, qty, tol, round(v.get(part, 0), 3)])
        for ext in ("stl", "step"):          # reference-only geometry kept out of the upload folders
            for part in ("plunger_seal", "gasket"):
                src = OUT / f"{sz}_{part}.{ext}"
                if src.exists():
                    (d / "reference_not_ordered").mkdir(exist_ok=True)
                    shutil.copy(src, d / "reference_not_ordered" / f"{part}.{ext}")
        shutil.copy(OUT / f"{sz}_assembly.step", d / "assembly_reference.step")
    md = FAB / "mould"
    md.mkdir()
    for n in ("mould_lower", "mould_upper", "mould_s2_lower", "mould_s2_upper", "mould_t_lower", "mould_t_upper"):
        for ext in ("stl", "step"):
            shutil.copy(OUT / f"{n}.{ext}", md / f"{n}.{ext}")
        rows.append([f"mould/{n}.stl", *MOULD[:5], MOULD[5], ""])
    if BENCH:
        ins = FAB / "dock-inserts"
        if (ins / "variants.csv").exists():
            note = ("Swappable dock insert variants 1..12 (embossed ID on the -Y arm), parameter sweep cannula.A_dome_d x N_hook_h, see variants.csv; "
                    "fit-test on a real cannula head with dock_fixture (same frozen interface as the pod), then enter the winner in params.json.")
            rows.append(["dock-inserts/insert_v01..v12.stl", "SLA tough resin (JLC3DP 8001-type) - or MJF PA12 (arms behave differently)", "tough resin / PA12", "any",
                         "support marks off the arms", 12, note, ""])
            rows.append(["dock-inserts/dock_fixture.stl", "MJF PA12 or SLA", "PA12 / tough resin", "any", "standard", 1,
                         "Pod-less fixture carrying the frozen dock interface (window, ledge, detent bumps, rear stop).", ""])
        write_shim(p, OUT, FAB, rows)
        wo = FAB / "reservoir-sla-water-only"
        wo.mkdir(exist_ok=True)
        for sz in sizes:
            for ext in ("stl", "step"):
                src = OUT / f"{sz}_reservoir.{ext}"
                if src.exists():
                    shutil.copy(src, wo / f"{sz}_reservoir_WATER-ONLY_sla.{ext}")
            rows.append([f"reservoir-sla-water-only/{sz}_reservoir_WATER-ONLY_sla.stl", "SLA clear resin (JLC3DP)", "clear resin", "clear",
                         "wash + UV post-cure, bore not polished", 1,
                         "WATER ONLY - NEVER INSULIN OR ANY OTHER DRUG. Print copy of the frozen CNC reservoir geometry (reservoir_frozen unchanged). "
                         "SLA: bore 16.0 x 5.0 and the d2.0 port may need +0.05..0.1 mm / a reamer; do not change reservoir_frozen, document the deviation.", ""])
        (wo / "README.md").write_text(
            "# Reservoir, SLA print copy - WATER ONLY\n\n"
            "These files are print-ready copies of the **frozen** CNC reservoir geometry (`params.json` -> `reservoir_frozen`) for the first,\n"
            "water-only bench builds (SLA resin, e.g. JLC3DP). **They must never be filled with insulin or any other drug (water only)**: printed resin is not validated for any drug,\n"
            "not sterile. The CNC polypropylene part in\n"
            "`../reservoir-cnc/`.\n\n"
            "* Geometry identical to `../reservoir-cnc/` (same bore 16.00 x 5.00, port d2.0 at the closed end); nothing in `reservoir_frozen` was changed.\n"
            "* SLA tolerance is about +-0.1 mm: check the bore with the plunger, ream the port to d2.0 if the cap spigot does not enter. If SLA needs a\n"
            "  different wall or clearance, document it here - do not edit `reservoir_frozen`.\n"
            "* Print standing on the open end, support the outside only; wash and UV-cure, do not sand the bore.\n", encoding="utf-8")
    with open(FAB / "MANIFEST.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "process", "material", "colour", "finish", "qty", "tolerance_notes", "volume_cm3"])
        w.writerows(rows)

    if BENCH:      # BOM check: every manufactured part of the model has a fab file (or is a documented reference/cast part)
        from op_build import BENCH_MFG_PARTS
        reference = {"plunger_seal": "cast in the mould/", "gasket": "cut from silicone sheet", "dock_insert": "dock-inserts/ (12 variants)"}
        missing = []
        for part in BENCH_MFG_PARTS:
            if part in reference:
                continue
            for sz in sizes:
                if not (FAB / sz / f"{part}.stl").exists():
                    missing.append(f"{sz}/{part}.stl")
        print("BOM check:", "all manufactured parts have fab files" if not missing else f"MISSING {missing}")
    # ---- cost estimate -------------------------------------------------------------------------
    if BENCH:
        write_bench_readme(p, vols, sizes, PARTS)
        return

    def part_cost(sz: str, part: str, qty: int) -> float:
        vol = vols[sz].get(part, 0.0)
        proc = PARTS[part][0]
        if proc.startswith("MJF"):
            return qty * max(MJF_MIN_PART, vol * PA12_DENSITY * MJF_BILL_FACTOR * MJF_PER_G)
        return qty * max(SLA_MIN_PART, vol * SLA_BILL_FACTOR * SLA_PER_CM3 * 4)
    lines = ["| size | bottom | top | carriage x2 | plunger_core x2 | reservoir | subtotal |", "|---|---|---|---|---|---|---|"]
    tot = 0.0
    for sz in sizes:
        c = [part_cost(sz, "bottom", 1), part_cost(sz, "top", 1), part_cost(sz, "carriage", 2),
             part_cost(sz, "plunger_core", 2), part_cost(sz, "reservoir", 1)]
        tot += sum(c)
        lines.append(f"| {sz} (vol cm3: " + "/".join(f"{vols[sz].get(k,0):.2f}" for k in ("bottom", "top", "carriage", "plunger_core", "reservoir"))
                     + ") | " + " | ".join(f"${x:.1f}" for x in c) + f" | ${sum(c):.1f} |")
    spare = part_cost("OP-100", "bottom", 1) + part_cost("OP-100", "top", 1)
    mould = 6 * max(SLA_MIN_PART, 14.0 * SLA_BILL_FACTOR * SLA_PER_CM3 * 4)
    readme = f"""# OpenPatch Rev A - fabrication folder (`out/fab/`)

EXPERIMENTAL DIY device, not a medical device. Everything here is for bench/water testing.
Folders: `OP-70/`, `OP-100/`, `OP-200/` (upload these), `mould/` (three seal-variant sets, valid for all sizes), `MANIFEST.csv`
(machine-readable version of the table below). Units: mm. STEP is the master, STL (fine tessellation) is for the
quote tool; `assembly_reference.step` and `reference_not_ordered/` are NOT to be uploaded.

## Per-file ordering sheet (same for every size)

| file | process | material | colour | finish | qty / size | tolerance, notes |
|---|---|---|---|---|---|---|
""" + "\n".join(f"| `<SIZE>/{k}.stl` | {v[0]} | {v[1]} | {v[2]} | {v[3]} | {v[4]} | {v[5]} |" for k, v in PARTS.items() if v[6]) + f"""
| `mould/mould*_lower.stl`, `mould*_upper.stl` (3 variants S1, S2, T) | {MOULD[0]} | {MOULD[1]} | {MOULD[2]} | {MOULD[3]} | 3 sets (all sizes) | {MOULD[5]} |

Not uploaded (reference geometry in `reference_not_ordered/`): `plunger_seal` (cast in the mould) and `gasket`
(die/laser-cut from silicone sheet). CNC reservoir halves (`reservoir_cnc_*`) are in `out/` only; they are the
optional material preparation for a future manufacturer (never filled with insulin) and are not part of the cheap monthly loop.

## Vendor choice (low cost first)

* **Default: JLC3DP** for everything (MJF PA12 housing, SLA small parts). Cheapest per set in the public price pages
  I could read (PA12 about 0.275-0.35 USD/g after the recent price cuts; from 0.30 USD/part for small parts).
* **PCBWay** only if (a) you want one order with PCBs + prints (shared shipping), (b) JLC3DP rejects thin walls
  (0.4 mm tongue, 0.5 mm membrane) - PCBWay engineers review files by hand - or (c) you need the CNC PP reservoir
  (CNC quotes start around 25 USD per part). Upload the same files; processes have the same names (MJF Nylon PA12, SLA).
* Details: `vendor-notes.md`.

## Estimated cost per monthly iteration (ESTIMATE - confirm with the instant quote)

Assumptions (edit in `fab.py`): MJF PA12 {MJF_PER_G:.2f} USD/g x density {PA12_DENSITY} x billing factor {MJF_BILL_FACTOR}
(MJF bills offset volume), min {MJF_MIN_PART:.1f} USD/part; SLA resin min {SLA_MIN_PART:.1f} USD/part, volume term
~{SLA_PER_CM3*4:.1f} USD/cm3 x {SLA_BILL_FACTOR}. Shipping {SHIP_EST[0]:.0f}-{SHIP_EST[1]:.0f} USD per order (one order).

{chr(10).join(lines)}

* One set per size (OP-70/100/200): about **${tot:.0f}**; spares (1 extra bottom + top of OP-100): about ${spare:.0f};
  mould (once, reusable for a few casts): about ${mould:.0f}.
* Printed parts per iteration (3 sizes + spares): about **${tot + spare + SHIP_EST[0]:.0f} - ${tot + spare + SHIP_EST[1]:.0f}** incl. shipping
  (without the mould). Realistic expectation: 40-60 USD for a 3-size iteration (about 20-25 USD for a single size); the per-part minimums dominate, not the volume.
* Purchased mechanical parts per iteration: see `../../parts.md` (AliExpress geared stepper, M1.6 rod/nuts, gears, magnet,
  needles): about 25-45 USD per pump, much of it reusable (motors, gears, screws are not consumed).
"""
    (FAB / "README.md").write_text(readme, encoding="utf-8")
    vendor = """# Vendor notes

## JLC3DP (jlc3dp.com) - default
* Upload STL (or STEP) per part; choose process per the table in README.md. MJF: "PA12-HP Nylon" (grey).
  Pick standard finishing only. SLA: choose a tough resin (8001-type) for carriage/plunger/mould, clear for the reservoir.
* Minimum wall for MJF is about 0.5-0.8 mm depending on the tool; our 0.4 mm tongue and 0.45 mm skirt may be flagged
  or break in depowdering. If rejected: re-order the housing in SLA (0.4 mm is fine there) - the lid/bottom STEP is the same.
* Order everything in one order (shared shipping). Add a note: "dimensions critical on bores; no support marks inside bores".

## PCBWay (pcbway.com) - alternative
* 3D Printing -> MJF Nylon PA12 / SLA; CNC Machining -> PP (optional reservoir halves).
* Upload STEP for CNC (STL for printing). Notes field: "prototype, +-0.1 mm on marked bores, deburr, no coating".
* Good for hand-reviewed thin features and for combining with PCB/PCBA orders.

## Both
* Water-test parts (reservoir, plunger core) are NOT biocompatible or sterile. The pump is never filled with insulin or any other drug (water only) and is never connected to a person.
* Always request the quote for the smallest size (OP-70) first to see per-part minimums before ordering 3 sizes.
"""
    (FAB / "vendor-notes.md").write_text(vendor, encoding="utf-8")
    print(f"fab folder written: {FAB}; per-iteration printed parts about {tot + spare:.0f} USD (estimate)")


if __name__ == "__main__":
    main()
