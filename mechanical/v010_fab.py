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
                   "+-0.2 mm. Bench pod shell + v0.1.0: USB-C opening 9.4 x 3.4 mm in the +X wall (0.4 mm web above), battery bay ribs (0.5 mm), motor contact shelf, USB board posts, board posts/pins, M1.2 pilots dia 1.0 (x6). "
                   "Order the dock-insert set (bench `dock-inserts/`, same frozen interface) first. Porous: splash-level only.", True)
PARTS["top"] = ("SLA (JLC3DP clear / transparent resin, spec 2a: clear lid, no fill-window slot)", "clear resin", "clear", "wash + UV cure; no polish on the gasket seat", 1,
                "+-0.1 mm. Board, cell and LEDs are visible: keep the electronics tidy; optional light-blocking black ink / paint mask on the inside over the status LED only if needed. Lid features: piezo port dia 0.8 + membrane recess dia 4.0 x 0.2, button membrane 0.5 mm, "
                "pressure vent dia 0.8 + dia 5.0 x 0.2 recess (ePTFE disc). 0.5 mm membranes are at the printable floor: order 2.", True)
PARTS["usb_gasket"] = ("DO NOT PRINT - die/laser-cut 0.5 mm silicone sheet, Shore A 30-40, frame 0.8 mm wide (DXF in usb-gasket/)", "-", "-", "-", 2,
                        "Reference geometry. Sits between the USB-C receptacle flange and the inside of the +X end wall around the 9.4 x 3.4 mm opening (IPX7 with the receptacle's own seal).", False)
_unused_charge_gasket = ("DO NOT PRINT - die/laser-cut 1.5 mm silicone sheet (or closed-cell silicone foam), Shore A 30-40, ring 1.2 mm wide (DXF in charge-gasket/)", "-", "-", "-", 2,
                          "Reference geometry (compressed 1.4 mm). Sits between the board top and the lid inner face around the charge window.", False)
_unused_cradle = ("MJF PA12 or SLA tough resin", "PA12 / tough resin", "any", "standard; ream pin bores d1.08 if needed", 1,
                "One cradle per size (pad x depends on x_r1). Two P75-E2-class spring test probes pressed into d1.08 bores; M2 x 8 bar screws into d1.6 pilots.")

PURCHASED = [
    ("Radio module <= 1.3 mm on the lid side (ISP1807-class SiP; electronics agent decides)", "on the PCBA", "1 per pod"),
    ("Li-Po cell 301012 class (3.0 x 10 x 12 mm incl. PCM, ~30 mAh) AND 301015/301020 class as spare candidates", "AliExpress / generic", "3 candidates"),
    ("Waterproof USB Type-C receptacle, mid-mount, IPX7 class, ~8.94 x 7.35 x 3.26 mm (vendor drawing VERIFY) + USB board + 2 elastomer/pogo links 2.1 mm", "AliExpress / LCSC", "1 + spare"),
    ("NFP-608 motor with FPC tail (custom, spec 1c) or 4-trace flex jumper; 4 SMD spring contacts 0.9 mm", "group buy / LCSC", "1 + spare"),
    ("SMD spring contacts, 1.0-1.2 mm free height, 2 per pod (MPN VERIFY; fallback M1.2 clamp pads)", "LCSC / DigiKey", "2 + spares"),
    ("Double-sided foam tape 0.6 mm (cell bed)", "generic", "1 strip"),
    ("SMD piezo 9 x 9 x 1.0 (Murata PKMCS0909E4000-R1 class)", "on the PCBA", "1"),
    ("Silicone sheet 0.5 mm Shore A 30-40 (main gasket, USB-C gasket)", "generic", "1 sheet"),
    ("ePTFE adhesive vent / acoustic membrane discs d5 and d4 (PU film for the buzzer port)", "generic", "4+"),
    ("M1.2 x 6 self-tapping screws (lid, x6), M1.2 x 4 (board, x1), M2 x 8 (cradle, x2)", "generic", "1 set"),
]


def main() -> None:
    p = json.loads((OUT / "params.used.json").read_text()) if (OUT / "params.used.json").exists() else load_params()
    if FAB.exists():
        shutil.rmtree(FAB)
    FAB.mkdir(parents=True)
    rows, vols = [], {}
    sizes = list(p["v010"]["sizes"])
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
        for part in ("plunger_seal", "gasket", "usb_gasket"):
            for ext in ("stl", "step"):
                src = OUT / f"{sz}_{part}.{ext}"
                if src.exists():
                    shutil.copy(src, ref / f"{part}.{ext}")
        shutil.copy(OUT / f"{sz}_assembly.step", d / "assembly_reference.step")
    md = FAB / "mould"
    md.mkdir()
    for n in ("mould_lower", "mould_upper"):
        for ext in ("stl", "step"):
            shutil.copy(OUT / f"{n}.{ext}", md / f"{n}.{ext}")
        rows.append([f"mould/{n}.stl", *F.MOULD[:5], F.MOULD[5], ""])
    # USB-C gasket DXF (die/laser cut) from the generated geometry
    import ezdxf
    L = json.loads((OUT / "OP-100.mech.json").read_text())
    ug = L["v010"]["usb"]["gasket"]
    op = L["v010"]
    g = FAB / "usb-gasket"
    g.mkdir()
    oy, oz = ug["outer_y"], ug["outer_z"]
    ow, oh = oy[1] - oy[0], oz[1] - oz[0]
    ya, yb = L["v010"]["usb"]["open_y"]
    za, zb = L["v010"]["usb"]["open_z"]
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (ow, 0), (ow, oh), (0, oh)], close=True)
    msp.add_lwpolyline([(ya - oy[0], za - oz[0]), (yb - oy[0], za - oz[0]), (yb - oy[0], zb - oz[0]), (ya - oy[0], zb - oz[0])], close=True)
    msp.add_text("OpenPatch v0.1.0 USB-C gasket, silicone 0.5 mm, TEST PROJECT water only", height=0.6, dxfattribs={"insert": (0, -2.0)})
    doc.saveas(g / "usb_gasket.dxf")
    rows.append(["usb-gasket/usb_gasket.dxf", PARTS["usb_gasket"][0], "silicone 0.5 mm", "-", "-", 2, PARTS["usb_gasket"][5], ""])
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
        cr = 0.0
        sub[sz] = sum(c) + cr
        lines.append(f"| {sz} | " + " | ".join(f"${x:.1f}" for x in c) + f" | ${cr:.1f} | ${sub[sz]:.1f} |")
    coupon = F.SLA_MIN_PART * 12 + F.MJF_MIN_PART
    mould = 2 * max(F.SLA_MIN_PART, 14.0 * F.SLA_BILL_FACTOR * F.SLA_PER_CM3 * 4)
    single = sub["OP-100"]
    readme = f"""# OpenPatch v0.1.0 integrated pod - fabrication folder (`out/v010/fab/`)

EXPERIMENTAL TEST sample, **water only, never on a person or animal**. The pod is the bench pod (frozen CNC/SLA reservoir, dock interface, drive) plus the
electronics (main board over the dock tunnel, ~30 mAh Li-Po in the strip beside it, waterproof USB-C at the +X end, piezo, button, pressure vent; charge pads and cradle dropped, spec 2d). Folders: `OP-70/`, `OP-100/`, `OP-200/`
(upload), `usb-gasket/` (DXF, die/laser cut), `mould/` (all sizes), `dock-inserts/` (shared with the bench pod), `MANIFEST.csv`. Units mm; STEP is master.

## Order sheet (every size)

| file | process | material | colour | finish | qty / size | tolerance, notes |
|---|---|---|---|---|---|---|
""" + "\n".join(f"| `<SIZE>/{k}.stl` | {v[0]} | {v[1]} | {v[2]} | {v[3]} | {v[4]} | {v[5]} |" for k, v in PARTS.items() if v[6]) + f"""
| `mould/mould_lower.stl`, `mould_upper.stl` | {F.MOULD[0]} | {F.MOULD[1]} | {F.MOULD[2]} | {F.MOULD[3]} | {F.MOULD[4]} set | {F.MOULD[5]} |
| `usb-gasket/usb_gasket.dxf` | {PARTS['usb_gasket'][0]} | silicone | - | - | 2 | frame 0.8 mm, 0.5 mm sheet |

Not uploaded: `plunger_seal` (cast in the mould), `gasket` (0.5 mm silicone sheet), `usb_gasket` (cut from 0.5 mm silicone).

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
