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

from op_layout import HERE, load_params

OUT = HERE / "out"
FAB = OUT / "fab"
CLI = "/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli"

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
                 "+-0.1 mm (hex pocket AF 3.3 for DIN 934 M1.6 nut, dia 1.9 screw bore, rail groove 1.2 x 0.5). Order 2: nut fit is the first test.", True),
    "plunger_core": ("SLA", "tough or clear resin", "any", "no coating", 2,
                     "+-0.1 mm. Seal grooves (0.8 mm wide) + socket for carriage tongue. Water test only.", True),
    "reservoir": ("SLA (clear resin preferred, 'BioMed Clear'-class if offered, else standard clear)", "clear resin",
                  "clear", "wash + UV post-cure; inner bore stays unpolished", 1,
                  "WATER-TEST ONLY - not insulin-contact, not sterile, not validated. +-0.1 mm; check bore 16.0 x 5.0 with a "
                  "pin gauge; bore may need light honing. Single piece; open dry end.", True),
    "reservoir_cnc_lower": ("CNC (PCBWay CNC; polypropylene) - OPTIONAL, expensive", "PP natural", "natural", "as machined", 1,
                            "Half of the reservoir (split at bore centre plane). Bond halves after machining. Only for the later "
                            "insulin-contact candidate; not part of the cheap monthly loop.", False),
    "reservoir_cnc_upper": ("CNC (PCBWay CNC; polypropylene) - OPTIONAL", "PP natural", "natural", "as machined", 1, "see lower half", False),
    "plunger_seal": ("DO NOT ORDER - cast in the mould (silicone, Shore A 40-50)", "-", "-", "-", 0,
                     "Reference geometry (assembly state). Cast with mould_lower/upper.", False),
    "gasket": ("DO NOT ORDER - die-cut / laser-cut 0.5 mm silicone sheet, Shore A 40-50, ring 0.4 mm wide, or dispense a 0.5 mm bead", "-", "-", "-", 0,
               "Reference geometry (compressed state 0.45 mm). A 0.4 mm wide ring is fragile: cut it from 0.5 mm sheet with ~0.8 mm webs or use FIPG.", False),
}
MOULD = ("SLA (high detail, e.g. JLC3DP 8001 / PCBWay SLA)", "tough resin", "any", "wash + UV cure; drill sprue dia 0.7 / vent dia 0.5 clear", 1,
         "One set for ALL sizes. +-0.05..0.1 mm. Check the 4 pin/hole fits (pin dia 2.0 / hole 2.2).")

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




def main() -> None:
    p = load_params(OUT / "params.used.json") if (OUT / "params.used.json").exists() else load_params()
    if FAB.exists():
        shutil.rmtree(FAB)
    FAB.mkdir(parents=True)
    rows, vols = [], {}
    sizes = list(p["variants"])
    for sz in sizes:
        d = FAB / sz
        d.mkdir()
        v = volumes(OUT / f"{sz}.sc", ["bottom", "top", "carriage", "plunger_core", "reservoir"])
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
    for n in ("mould_lower", "mould_upper"):
        for ext in ("stl", "step"):
            shutil.copy(OUT / f"{n}.{ext}", md / f"{n}.{ext}")
        rows.append([f"mould/{n}.stl", *MOULD[:5], MOULD[5], ""])
    with open(FAB / "MANIFEST.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "process", "material", "colour", "finish", "qty", "tolerance_notes", "volume_cm3"])
        w.writerows(rows)

    # ---- cost estimate -------------------------------------------------------------------------
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
    mould = 2 * max(SLA_MIN_PART, 14.0 * SLA_BILL_FACTOR * SLA_PER_CM3 * 4)
    readme = f"""# OpenPatch Rev A - fabrication folder (`out/fab/`)

EXPERIMENTAL DIY device, not a medical device. Everything here is for bench/water testing.
Folders: `OP-70/`, `OP-100/`, `OP-200/` (upload these), `mould/` (one set for all sizes), `MANIFEST.csv`
(machine-readable version of the table below). Units: mm. STEP is the master, STL (fine tessellation) is for the
quote tool; `assembly_reference.step` and `reference_not_ordered/` are NOT to be uploaded.

## Per-file ordering sheet (same for every size)

| file | process | material | colour | finish | qty / size | tolerance, notes |
|---|---|---|---|---|---|---|
""" + "\n".join(f"| `<SIZE>/{k}.stl` | {v[0]} | {v[1]} | {v[2]} | {v[3]} | {v[4]} | {v[5]} |" for k, v in PARTS.items() if v[6]) + f"""
| `mould/mould_lower.stl`, `mould_upper.stl` | {MOULD[0]} | {MOULD[1]} | {MOULD[2]} | {MOULD[3]} | {MOULD[4]} set (all sizes) | {MOULD[5]} |

Not uploaded (reference geometry in `reference_not_ordered/`): `plunger_seal` (cast in the mould) and `gasket`
(die/laser-cut from silicone sheet). CNC reservoir halves (`reservoir_cnc_*`) are in `out/` only; they are the
optional insulin-contact route and are not part of the cheap monthly loop.

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
* Water-test parts (reservoir, plunger core) are NOT biocompatible or sterile. Never put insulin or anything that
  goes to a person through printed Rev A parts.
* Always request the quote for the smallest size (OP-70) first to see per-part minimums before ordering 3 sizes.
"""
    (FAB / "vendor-notes.md").write_text(vendor, encoding="utf-8")
    print(f"fab folder written: {FAB}; per-iteration printed parts about {tot + spare:.0f} USD (estimate)")


if __name__ == "__main__":
    main()
