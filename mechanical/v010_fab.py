# SPDX-License-Identifier: LicenseRef-OpenPatch
"""`fab.py --variant v010` -> out/v010/fab/ : print-ready files for the v0.1.0 integrated pod, cradle, charge-window gasket. TEST PROJECT, water only."""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import fab as F
from op_layout import HERE, load_params

OUT = HERE / "out" / "v010"
FAB = OUT / "fab"

PARTS = dict(F.BENCH_PARTS)
PARTS["bottom"] = (F.PARTS["bottom"][0], "PA12", "grey (natural)", "bead-blasted standard; NO dye/vapour smoothing", 1,
                   "+-0.2 mm. Bench pod shell + v0.1.0 tail: battery bay ribs (0.5 mm, printable floor 0.4), board posts/pins on the floor, extended dock tunnel window, M1.2 pilots dia 1.0 (x7). "
                   "Order the dock-insert set (bench `dock-inserts/`, same frozen interface) first. Porous: splash-level only.", True)
PARTS["top"] = ("SLA (JLC3DP clear / transparent resin, spec 2a: clear lid, no fill-window slot)", "clear resin", "clear", "wash + UV cure; no polish on the gasket seat", 1,
                "+-0.1 mm. Board, cell and LEDs are visible: keep the tail tidy; optional light-blocking black ink / paint mask on the inside over the status LED only if needed. Lid features: charge window 4.4 x 10.4 mm (+ gasket seat), piezo port dia 0.8 + membrane recess dia 4.0 x 0.2, button membrane 0.5 mm, "
                "pressure vent dia 0.8 + dia 5.0 x 0.2 recess (ePTFE disc). 0.5 mm membranes are at the printable floor: order 2.", True)
PARTS["charge_gasket"] = ("DO NOT PRINT - die/laser-cut 1.5 mm silicone sheet (or closed-cell silicone foam), Shore A 30-40, ring 1.2 mm wide (DXF in charge-gasket/)", "-", "-", "-", 2,
                          "Reference geometry (compressed 1.4 mm). Sits between the board top and the lid inner face around the charge window.", False)
PARTS_CRADLE = ("MJF PA12 or SLA tough resin", "PA12 / tough resin", "any", "standard; ream pin bores d1.08 if needed", 1,
                "One cradle per size (pad x depends on x_r1). Two P75-E2-class spring test probes pressed into d1.08 bores; M2 x 8 bar screws into d1.6 pilots.")

PURCHASED = [
    ("Ebyte E73-2G4M08S1C module (LCSC C356849)", "on the PCBA", "1 per pod"),
    ("Molex PicoBlade 53261-0471 on the PCBA + NFP motor lead plug (4 pos 1.25 mm)", "on the PCBA / on the lead", "1"),
    ("Li-Po cell 301012 class (3.0 x 10 x 12 mm incl. PCM, ~30 mAh) AND 301015/301020 class as spare candidates", "AliExpress / generic", "3 candidates"),
    ("SMD spring contacts, 1.0-1.2 mm free height, 2 per pod (MPN VERIFY; fallback M1.2 clamp pads)", "LCSC / DigiKey", "2 + spares"),
    ("Double-sided foam tape 0.6 mm (cell bed)", "generic", "1 strip"),
    ("SMD piezo 9 x 9 x 1.0 (Murata PKMCS0909E4000-R1 class)", "on the PCBA", "1"),
    ("Silicone sheet 1.5 mm Shore A 30-40 (charge gasket) and 0.5 mm (main gasket)", "generic", "1 sheet"),
    ("ePTFE adhesive vent / acoustic membrane discs d5 and d4 (PU film for the buzzer port)", "generic", "4+"),
    ("Spring test probes P75-E2 class, tube d1.02, length 16.5 (cradle)", "AliExpress / LCSC", "2 per cradle + spares"),
    ("M1.2 x 6 self-tapping screws (lid, x6), M1.2 x 4 (board, x1), M2 x 8 (cradle, x2)", "generic", "1 set"),
]


def main() -> None:
    p = json.loads((OUT / "params.used.json").read_text()) if (OUT / "params.used.json").exists() else load_params()
    if FAB.exists():
        shutil.rmtree(FAB)
    FAB.mkdir(parents=True)
    rows, vols = [], {}
    sizes = list(p["variants"])
    for sz in sizes:
        d = FAB / sz
        d.mkdir()
        v = F.volumes(OUT / f"{sz}.sc", ["bottom", "top", "carriage", "plunger_core", "plunger_nose", "reservoir", "cannula_adapter", "end_cap", "valve_plug", "thrust_sleeve", "thrust_collar"])
        vols[sz] = v
        for part, (proc, mat, col, fin, qty, tol, upload) in PARTS.items():
            if not upload:
                continue
            for ext in ("stl", "step"):
                src = OUT / f"{sz}_{part}.{ext}"
                if src.exists():
                    shutil.copy(src, d / f"{part}.{ext}")
            rows.append([f"{sz}/{part}.stl", proc, mat, col, fin, qty, tol, round(v.get(part, 0), 3)])
        ref = d / "reference_not_ordered"
        ref.mkdir()
        for part in ("plunger_seal", "gasket", "charge_gasket"):
            for ext in ("stl", "step"):
                src = OUT / f"{sz}_{part}.{ext}"
                if src.exists():
                    shutil.copy(src, ref / f"{part}.{ext}")
        shutil.copy(OUT / f"{sz}_assembly.step", d / "assembly_reference.step")
        cd = FAB / "cradle"
        cd.mkdir(exist_ok=True)
        for part in ("cradle_base", "cradle_bar"):
            for ext in ("stl", "step"):
                src = OUT / "cradle" / f"cradle_{sz}_{part}.{ext}"
                if src.exists():
                    shutil.copy(src, cd / f"{sz}_{part}.{ext}")
        rows.append([f"cradle/{sz}_cradle_base.stl", *PARTS_CRADLE[:5], PARTS_CRADLE[5], ""])
        rows.append([f"cradle/{sz}_cradle_bar.stl", PARTS_CRADLE[0], PARTS_CRADLE[1], "any", "standard", 1, "Hold-down bar, 2 mm thick, M2 holes d2.2", ""])
    md = FAB / "mould"
    md.mkdir()
    for n in ("mould_lower", "mould_upper"):
        for ext in ("stl", "step"):
            shutil.copy(OUT / f"{n}.{ext}", md / f"{n}.{ext}")
        rows.append([f"mould/{n}.stl", *F.MOULD[:5], F.MOULD[5], ""])
    # charge-window gasket DXF (die/laser cut) -- from the generated geometry
    import ezdxf
    L = json.loads((OUT / "OP-100.mech.json").read_text())
    G = L["v010"]
    g = FAB / "charge-gasket"
    g.mkdir()
    ox, oy, w = G["gasket"]["outer_x"], G["gasket"]["outer_y"], G["window"]
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (ox[1] - ox[0], 0), (ox[1] - ox[0], oy[1] - oy[0]), (0, oy[1] - oy[0])], close=True)
    ix0, iy0 = w["x"][0] - ox[0], w["y"][0] - oy[0]
    msp.add_lwpolyline([(ix0, iy0), (ix0 + w["x"][1] - w["x"][0], iy0), (ix0 + w["x"][1] - w["x"][0], iy0 + w["y"][1] - w["y"][0]), (ix0, iy0 + w["y"][1] - w["y"][0])], close=True)
    msp.add_text("OpenPatch v0.1.0 charge-window gasket, silicone 1.5 mm, ring %.1f mm, TEST PROJECT water only" % p["v010"]["charge"]["gasket_w"], height=0.6, dxfattribs={"insert": (0, -2.0)})
    doc.saveas(g / "charge_gasket.dxf")
    rows.append(["charge-gasket/charge_gasket.dxf", PARTS["charge_gasket"][0], "silicone 1.5 mm", "-", "-", 2, PARTS["charge_gasket"][5], ""])
    bench_ins = HERE / "out" / "bench" / "fab" / "dock-inserts"
    if bench_ins.exists():
        shutil.copytree(bench_ins, FAB / "dock-inserts")
        rows.append(["dock-inserts/insert_v01..v12.stl", "SLA tough resin (or MJF PA12)", "tough resin / PA12", "any", "support marks off the arms", 12,
                     "SAME files as the bench pod (frozen dock interface): one set serves bench and v0.1.0 pods", ""])
    with open(FAB / "MANIFEST.csv", "w", newline="", encoding="utf-8") as fh:
        w_ = csv.writer(fh)
        w_.writerow(["file", "process", "material", "colour", "finish", "qty", "tolerance_notes", "volume_cm3"])
        w_.writerows(rows)

    def cost(sz: str, part: str, qty: int) -> float:
        vol = vols[sz].get(part, 0.0)
        if PARTS[part][0].startswith("MJF"):
            return qty * max(F.MJF_MIN_PART, vol * F.PA12_DENSITY * F.MJF_BILL_FACTOR * F.MJF_PER_G)
        return qty * max(F.SLA_MIN_PART, vol * F.SLA_BILL_FACTOR * F.SLA_PER_CM3 * 4)

    cols = [("bottom", 1), ("top", 1), ("carriage", 2), ("plunger_core", 2), ("plunger_nose", 2), ("reservoir", 1), ("cannula_adapter", 2), ("end_cap", 2), ("valve_plug", 2), ("thrust_sleeve", 2), ("thrust_collar", 2)]
    lines = ["| size | " + " | ".join(f"{c} x{q}" for c, q in cols) + " | cradle | subtotal |", "|---|" + "---|" * (len(cols) + 2)]
    sub = {}
    for sz in sizes:
        c = [cost(sz, k, q) for k, q in cols]
        cr = max(F.MJF_MIN_PART, 40.0 * 1.0 * F.MJF_BILL_FACTOR * F.MJF_PER_G) + 1.5
        sub[sz] = sum(c) + cr
        lines.append(f"| {sz} | " + " | ".join(f"${x:.1f}" for x in c) + f" | ${cr:.1f} | ${sub[sz]:.1f} |")
    coupon = F.SLA_MIN_PART * 12 + F.MJF_MIN_PART
    mould = 2 * max(F.SLA_MIN_PART, 14.0 * F.SLA_BILL_FACTOR * F.SLA_PER_CM3 * 4)
    single = sub["OP-100"]
    readme = f"""# OpenPatch v0.1.0 integrated pod - fabrication folder (`out/v010/fab/`)

EXPERIMENTAL TEST sample, **water only, never on a person or animal**. The pod is the bench pod (frozen CNC/SLA reservoir, dock interface, drive) plus the
electronics strip (integrated PCBA, ~30 mAh Li-Po, buzzer, button, two charge pads behind a gasketed lid window, pressure vent). Folders: `OP-70/`, `OP-100/`, `OP-200/`
(upload), `cradle/` (one per size), `charge-gasket/` (DXF, die/laser cut), `mould/` (all sizes), `dock-inserts/` (shared with the bench pod), `MANIFEST.csv`. Units mm; STEP is master.

## Order sheet (every size)

| file | process | material | colour | finish | qty / size | tolerance, notes |
|---|---|---|---|---|---|---|
""" + "\n".join(f"| `<SIZE>/{k}.stl` | {v[0]} | {v[1]} | {v[2]} | {v[3]} | {v[4]} | {v[5]} |" for k, v in PARTS.items() if v[6]) + f"""
| `cradle/<SIZE>_cradle_base.stl`, `<SIZE>_cradle_bar.stl` | {PARTS_CRADLE[0]} | {PARTS_CRADLE[1]} | any | standard | 1 per size | {PARTS_CRADLE[5]} |
| `mould/mould_lower.stl`, `mould_upper.stl` | {F.MOULD[0]} | {F.MOULD[1]} | {F.MOULD[2]} | {F.MOULD[3]} | {F.MOULD[4]} set | {F.MOULD[5]} |
| `charge-gasket/charge_gasket.dxf` | {PARTS['charge_gasket'][0]} | silicone | - | - | 2 | ring 1.2 mm, 1.5 mm sheet |

Not uploaded: `plunger_seal` (cast in the mould), `gasket` (0.5 mm silicone sheet), `charge_gasket` (cut from 1.5 mm silicone).

## Purchased items specific to v0.1.0 (not printed)

| item | source | qty |
|---|---|---|
""" + "\n".join(f"| {a} | {b} | {c} |" for a, b, c in PURCHASED) + f"""

## Estimated printed-part cost (ESTIMATE, same price model as the bench pod; confirm with the instant quote)

{chr(10).join(lines)}

* One OP-100 set about **${single:.0f}** (+ shipping {F.SHIP_EST[0]:.0f}-{F.SHIP_EST[1]:.0f} USD, + dock-insert set about ${coupon:.0f} if not already ordered for the bench pod, + mould about ${mould:.0f} once).
* The PCBA (board outline from `OP-xx.layout.json`) is ordered separately; see `../V010.md` for the open items.
"""
    (FAB / "README.md").write_text(readme, encoding="utf-8")
    print(f"v010 fab folder written: {FAB}; one OP-100 set about {single:.0f} USD printed parts (estimate)")
