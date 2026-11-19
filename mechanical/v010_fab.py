# SPDX-License-Identifier: LicenseRef-OpenPatch
"""`fab.py --variant v010` -> out/v010/fab/: print/CNC-ready files of the integrated v0.1.0 pod with a README per part.  TEST PROJECT, water only, never on a person."""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import fab as F
from op_layout import HERE, load_params

OUT = HERE / "out" / "v010"
FAB = OUT / "fab"
SIZES = ("OP-100", "OP-200")
SIZE_INDEPENDENT = ("end_cap", "end_cap_lid", "plunger_core")

# part -> (process, material, colour, finish, qty per pod, tolerance, post-processing, notes, upload?)
VT = "JLC3DP vendor tolerances: SLA +-0.2 mm (holes shrink, +-0.3), MJF +-0.3 mm (holes shrink, +-0.3); the CAD clearances already assume them (dfm_rules.json)."
PARTS = {
    "bottom": ("MJF PA12 (JLC3DP Nylon / PA12-HP)", "PA12", "grey (natural)", "bead-blasted standard; no dye, no vapour smoothing", 1,
               "+-0.3 mm (vendor). Bearing-block bore d3.05 for the bush, M1.2 pilots d1.0, USB-C opening 9.4 x 3.4 mm with a 0.4 mm web, spine channel 0.3 deep (floor 0.6 left), crush ribs printed 0.4 mm proud.",
               "REAM the bush bore d3.05 with a 3.05 mm drill by hand (printed holes shrink 0.1-0.2); drill the M1.2 pilots d1.0; test-fit the bush before gluing (ASSEMBLY.md step B1). Porous: splash level only, never claimed watertight.",
               "Shell wall 0.9 mm (MJF vendor minimum 1.0-1.5: accepted, hard floor 0.5). Everything printed has 0.2-0.4 mm clearance for the vendor tolerance.", True),
    "top": ("SLA (JLC3DP clear / transparent resin; spec 2a: CLEAR LID)", "clear resin", "clear (polish / clear-coat the outside)", "wash + UV cure; clear-coat the outside; do not polish the gasket seat or the engraving", 1,
            "+-0.2 mm (vendor). Lid wall 0.9 mm, 0.75 mm over the reservoir recess, 0.6 mm under the scale engraving (0.15 deep), button membrane 0.5 mm, vent d0.8 + d5.0 x 0.2 recess, piezo port d1.2 + d4.0 x 0.2 recess.",
            "Drill the lid screw clearance holes d1.4 by hand if they print under d1.3 (holes shrink). Order 2: the 0.5 mm membrane is at the printable floor. Optional black ink on the inside over the status LED only.",
            "No fill-window slot (spec 2a); the fill scale is an engraving (tick / 10 U, long / 50 U). Everything inside is visible: tidy interconnect.", True),
    "end_cap": ("SLA (JLC3DP 8001/9000-type tough resin)", "tough resin", "any", "no coating; clear channels with a 0.5 mm wire", 2,
                "+-0.2 mm (vendor). Lower half of the fluid sandwich: spigot d1.98 x 1.8 (locating only), O-ring face groove, gasket recess 0.4, septum pocket axis Z (underside fill, inside the footprint), fill-needle hole d2.0 through the pod floor, via d0.6, needle bore, guard tube d3.2.",
                "Ream the spigot-to-port fit only if it does not enter the port d2.0 H7 by hand (spigot d1.98 prints 2.0-2.2: sand to 1.95 with 1500 grit). Hub seat d2.0: ream with a 2.0 drill. Channels d0.5-0.6 are at the SLA hole minimum: clear them with a 0.5 mm wire; water test only.",
                "Module retention against the reservoir: two printed crush ribs in the bottom shell push the reservoir against the cap, O-ring land contact guaranteed (check.py).", True),
    "end_cap_lid": ("SLA (JLC3DP 8001/9000-type tough resin)", "tough resin", "any", "no coating", 2,
                    "+-0.2 mm (vendor). Upper half of the clamped sandwich: flat underside on the lands, septum chamber recess, spur groove, O-ring half groove, spigot half pin, 2 x M1.2 x 6 clamp screws (clearance d1.4).",
                    "Drill the screw clearance d1.4 if undersize. Septum compression 15 % is set by the lands (hard stop), not by the screws.", "", True),
    "plunger_core": ("SLA (JLC3DP 8001/9000-type tough resin)", "tough resin", "any", "no coating", 2,
                     "+-0.2 mm (vendor) on a 4.5 x 25.5 mm stadium (core clearance 0.1 per side in the CAD: the vendor +-0.2 is absorbed by the seal bead (squeeze 0.03 mm) and the PTFE-tape recess).",
                     "Sand or hone the core flanges to the bore (wrapped dowel, 1500 grit) so that it slides without the seal; optional 0.1 mm PTFE tape wrap (tape recess is designed in). Screw socket d2.5 x 2.0 and the 0.3 mm tab: do not sand the tab.",
                     "Pushed only (pressure fill, spec 3c); anti-rotation of the screw = hacksaw slot 0.4 on the screw tip engaging the tab. WATER ONLY.", True),
    "reservoir_cnc": ("CNC (PCBWay / JLCCNC CNC; polypropylene PP-H)", "PP natural", "natural", "as machined; bore Ra 0.8", 2,
                      "+-0.1 mm; bore 25.7 x 4.7 +0.05/-0 (corner R2.35 = D4.7 end mill), wall 1.0 (JLCCNC absolute plastic minimum), end wall 2.0, port d2.0 H7 offset 5.95 mm from the bore centre, outer 27.7 x 6.7. Inspection report requested for bore height and port.",
                      "None. Deburr the rear edge. The deep pocket (OP-200: depth 23 mm = 4.9 x tool) needs a long-reach tool: ask the vendor; OP-100 depth 15 mm is standard.",
                      "RE-FROZEN interface (params.json reservoir_frozen_v010, replaces reservoir_frozen of the bench pod): order once per size AFTER the independent DFM review. Water only.", True),
    "dock_insert": ("SLA (JLC3DP tough resin) or MJF PA12", "tough resin / PA12", "any", "support marks off the arms", 12,
                    "+-0.2 mm (vendor). SHARED with the bench pod (frozen dock interface, shipped from dock-inserts/): 12 variants, labelled by embossed ID.",
                    "Support marks off the snap arms; arm strain 1.9-2.1 % (SLA allow 2 %: use the tough resin, order MJF as the second set).", "", False),
    "cannula_adapter": ("SLA (JLC3DP tough resin)", "tough resin", "clear or white", "support marks off the dome and the notches", 2,
                        "+-0.2 mm (vendor). Dummy cannula head for the dock fit test (TODO-MEASURE dimensions); magnet pocket d2.1 x 1.05.",
                        "Glue the d2 x 1 N52 magnet with a CA drop; punch a d2 silicone plug into the septum bore.", "Test fixture, not part of the pod (not ordered from this folder: use the bench fab set).", False),
    "plunger_seal": ("DO NOT ORDER - cast in the mould (platinum-cure silicone bead seal, Shore A 30)", "-", "-", "-", 0, "see SEAL-AND-DEAD-VOLUME.md", "", "Reference geometry (assembly state).", False),
    "gasket": ("DO NOT ORDER - die/laser-cut 0.5 mm silicone sheet, Shore A 40-50 (DXF in gasket/) or dispensed bead", "-", "-", "-", 1, "cut ring 0.4 mm wide is fragile: webs of 0.8 mm", "", "Reference geometry (compressed 0.45 mm).", False),
    "cap_gasket": ("DO NOT ORDER - die/laser-cut 0.5 mm silicone sheet (DXF in cap-gasket/)", "-", "-", "-", 1, "0.5 mm sheet in a 0.4 mm recess = 20 % squeeze on hard lands", "", "The port path is one slot in the sheet.", False),
    "usb_gasket": ("DO NOT ORDER - die/laser-cut 0.5 mm silicone sheet (DXF in usb-gasket/)", "-", "-", "-", 1, "frame 0.8 mm wide around the 9.4 x 3.4 mm opening", "", "Compressed between the receptacle flange and the rear wall inside.", False),
}

PURCHASED = [
    ("Drive screw M1.6 x 0.35 A2 stainless threaded rod, cut to 14.5 mm (OP-100) / 23.0 mm (OP-200) + hacksaw slot 0.4 x 1.0 across the tip", "hardware / AliExpress", "1 + spare"),
    ("DIN 934 M1.6 brass nut AF 3.2, glued (Loctite 638) on the front face of the nut gear", "hardware", "2"),
    ("NFP-608-26.45-SGM stepper gearmotor, FPC / pin version (motor pins face +Y toward the contact card)", "nfpshop.com", "1 + spare"),
    ("GHW module 0.3 brass gears 390754 (z16, motor) and 753020 (z20, nut gear, hub turned off)", "GHW-Modellbau", "1 + spare"),
    ("Thrust sleeve: brass tube d2.0 x d1.64 x 3.1 mm (cut + deburr); dry bush d3.0 x d1.7 x 1.0 (PTFE/brass)", "hardware", "1 each + spare"),
    ("Diametric RING magnet N45/N52 d5 x d2 x 1.5 mm (custom order; VERIFY availability) glued on the sleeve", "magnet vendor", "2"),
    ("30G needle + printed hub, O-ring 2.0 x 0.7 (NBR/silicone), silicone septum disc d3.2 x 2, 0.5 mm silicone sheet", "generic", "1 set"),
    ("ISP1807 radio SiP 8 x 8 x 1.0 (on the MAIN PCBA, consigned) + MAIN / POWER / SENSOR boards (electronics/v010)", "JLCPCB PCBA", "1 set"),
    ("Li-Po cell 301012 class (3.0 x 10 x 12 mm incl. PCM, ~30 mAh) + 0.6 mm foam tape", "AliExpress", "3 candidates"),
    ("Waterproof USB-C 16P mid-mount receptacle (IPX7 class, 8.94 x 7.35 x 3.26 mm, drawing VERIFY) + USB board", "AliExpress / LCSC", "1 + spare"),
    ("SMD spring contacts (1.0-1.2 mm free height): 2 on MAIN for the cell, 4 on the motor contact card, 8 on the MAIN tongue for the FPC spine", "LCSC", "14 + spares"),
    ("FPC spine (flex, 0.1 mm, ~4 mm wide x 45 mm) between the motor card, SENSOR board and the MAIN tongue", "JLCPCB / PCBWay flex", "1 + spare"),
    ("SMD piezo 9 x 9 x 1.0 on the lid inner face, ePTFE vent disc d5, PU film d4, M1.2 x 6 self-tapping screws (x9) + M1.2 x 6 (cap clamp x2)", "generic", "1 set"),
]


def build_inserts(p: dict, d: Path) -> None:
    """The 12 dock insert variants (frozen interface, spec 8a) for the v0.1.0 DFM rules (embossed ID strokes 0.5 mm); no fit-test fixture here (bench tool)."""
    import copy
    from generate import run_cli
    from op_cmds import Script
    from op_coupon import add_variant_inserts, variants
    p = copy.deepcopy(p)
    p["mode"] = "bench"
    d.mkdir(parents=True, exist_ok=True)
    s = Script()
    vs = variants(p)
    geo = add_variant_inserts(s, p, vs)
    for v in vs:
        nm = f"dock_insert_v{v['id']:02d}"
        s.export_step(str(d / f"insert_v{v['id']:02d}.step"), [nm])
        s.export_stl(str(d / f"insert_v{v['id']:02d}.stl"), [nm])
    sj = d / "_inserts.script.json"
    sj.write_text(json.dumps(s.dumps()), encoding="utf-8")
    run_cli("run", str(sj), "--quiet")
    sj.unlink()
    (d / "LICENSE.md").write_text("# Licence of this folder\n\nSPDX-License-Identifier: CERN-OHL-P-2.0\n\nThe dock inserts and their generators (`mechanical/op_dock.py`, `mechanical/op_coupon.py`) are released under CERN-OHL-P-2.0. "
                                  "Test project, not a medical device; never for use on a person.\n", encoding="utf-8")
    with open(d / "variants.csv", "w", encoding="utf-8") as fh:
        fh.write("id,file,cannula.A_dome_d,cannula.N_hook_h,hook_gap_mm,arm_strain_pct,arm_tip_travel_mm,arm_force_N\n")
        for v in vs:
            g = geo[v["id"]]
            fh.write(f"{v['id']},insert_v{v['id']:02d}.stl,{v['A_dome_d']},{v['N_hook_h']},{2 * g['hook_in']:.3f},{g['arm_strain'] * 100:.2f},{g['travel']:.3f},{g['arm_tip_force_N']:.2f}\n")


def write_part_readmes(p: dict, vols: dict) -> None:
    d = FAB / "parts"
    d.mkdir(exist_ok=True)
    for name, v in PARTS.items():
        proc, mat, col, fin, qty, tol, post, note, up = v
        txt = (f"# {name}\n\n> TEST PROJECT: not a medical device. WATER ONLY, never on a person.\n\n"
               f"| item | value |\n|---|---|\n| process | {proc} |\n| material | {mat} |\n| colour | {col} |\n| finish | {fin} |\n| quantity per pod | {qty} |\n"
               f"| uploaded to the vendor | {'yes' if up else 'no'} |\n| volume OP-100 / OP-200 (cm3) | {vols['OP-100'].get(name if name != 'reservoir_cnc' else 'reservoir', 0):.2f} / {vols['OP-200'].get(name if name != 'reservoir_cnc' else 'reservoir', 0):.2f} |\n\n"
               f"**Tolerances / features:** {tol}\n\n**Post-processing:** {post or 'none'}\n\n**Notes:** {note}\n\n{VT}\n")
        (d / f"{name}.md").write_text(txt, encoding="utf-8")


def main() -> None:
    p = json.loads((OUT / "params.used.json").read_text()) if (OUT / "params.used.json").exists() else load_params()
    if FAB.exists():
        shutil.rmtree(FAB)
    FAB.mkdir(parents=True)
    rows, vols = [], {}
    names = ["bottom", "top", "end_cap", "end_cap_lid", "plunger_core", "reservoir", "cannula_adapter", "dock_insert"]
    for sz in SIZES:
        d = FAB / sz
        d.mkdir()
        vols[sz] = F.volumes(OUT / f"{sz}.sc", names)
        for part, v in PARTS.items():
            if not v[8] or part in ("reservoir_cnc", "dock_insert"):
                continue
            for ext in ("stl", "step"):
                # size-independent parts (fluid sandwich, plunger core: same shape, only their position in the pod differs) are shipped from the OP-100 export for both sizes
                src = OUT / f"{'OP-100' if part in SIZE_INDEPENDENT else sz}_{part}.{ext}"
                if src.exists():
                    shutil.copy(src, d / f"{part}.{ext}")
            rows.append([f"{sz}/{part}.stl", v[0], v[1], v[2], v[3], v[4], v[5], round(vols[sz].get(part, 0), 3)])
        shutil.copy(OUT / f"{sz}_assembly.step", d / "assembly_reference.step")
    cnc = FAB / "reservoir-cnc"
    cnc.mkdir()
    for sz in SIZES:
        shutil.copy(OUT / f"{sz}_reservoir.step", cnc / f"{sz}_reservoir_cnc.step")
        shutil.copy(OUT / f"{sz}_reservoir.stl", cnc / f"{sz}_reservoir_cnc.stl")
        rows.append([f"reservoir-cnc/{sz}_reservoir_cnc.step", PARTS["reservoir_cnc"][0], PARTS["reservoir_cnc"][1], "natural", "as machined", 2, PARTS["reservoir_cnc"][5], round(vols[sz].get("reservoir", 0), 3)])
    md = FAB / "mould"
    md.mkdir()
    for n in ("mould_lower", "mould_upper"):
        for ext in ("stl", "step"):
            shutil.copy(OUT / f"{n}.{ext}", md / f"{n}.{ext}")
        rows.append([f"mould/{n}.stl", *F.MOULD[:5], F.MOULD[5], ""])
    # silicone gasket DXFs from the generated geometry
    import ezdxf
    L = json.loads((OUT / "OP-100.mech.json").read_text())
    G = L["geo"]
    sh = p["shell"]

    def dxf(path: Path, outer: list, holes: list[list], label: str) -> None:
        doc = ezdxf.new("R2010", setup=True)
        doc.units = ezdxf.units.MM
        msp = doc.modelspace()
        msp.add_lwpolyline(outer, close=True)
        for h in holes:
            msp.add_lwpolyline(h, close=True)
        msp.add_text(f"OpenPatch v0.1.0 {label}, silicone 0.5 mm, TEST PROJECT water only", height=0.6, dxfattribs={"insert": (0, -2.0)})
        path.parent.mkdir(exist_ok=True)
        doc.saveas(path)

    u = G["usb"]
    oy, oz = u["gasket"]["y"], u["gasket"]["z"]
    ya, yb = u["open_y"]
    za, zb = u["open_z"]
    dxf(FAB / "usb-gasket" / "usb_gasket.dxf", [(0, 0), (oy[1] - oy[0], 0), (oy[1] - oy[0], oz[1] - oz[0]), (0, oz[1] - oz[0])],
        [[(ya - oy[0], za - oz[0]), (yb - oy[0], za - oz[0]), (yb - oy[0], zb - oz[0]), (ya - oy[0], zb - oz[0])]], "USB-C gasket")
    cg = p["dock"]["cap"]["sandwich"]["gasket"]
    gx = cg["x"][1] - cg["x"][0]
    gy = 0.9 + 0.3 + 5.9 - 0.3 + 0.0
    dxf(FAB / "cap-gasket" / "cap_gasket.dxf", [(0, 0), (gx, 0), (gx, 9.6), (0, 9.6)], [], "fluid sandwich gasket (cut the port slot 0.6 mm + septum opening d4.1 per cap_gasket.step)")
    ri = sh["rim_inset"]
    wl = L["length"]
    dxf(FAB / "gasket" / "gasket_OP-100.dxf", [(ri, ri), (wl - ri, ri), (wl - ri, 32 - ri), (ri, 32 - ri)],
        [[(sh["wall"], sh["wall"]), (wl - sh["wall"], sh["wall"]), (wl - sh["wall"], 32 - sh["wall"]), (sh["wall"], 32 - sh["wall"])]], "main gasket (rounded corners R3.5/3.1 per STEP)")
    for nm, rr in (("usb-gasket/usb_gasket.dxf", PARTS["usb_gasket"]), ("cap-gasket/cap_gasket.dxf", PARTS["cap_gasket"]), ("gasket/gasket_OP-100.dxf", PARTS["gasket"])):
        rows.append([nm, rr[0], "silicone 0.5 mm", "-", "-", rr[4], rr[5], ""])
    build_inserts(p, FAB / "dock-inserts")
    if True:
        rows.append(["dock-inserts/insert_v01..v12.stl", PARTS["dock_insert"][0], PARTS["dock_insert"][1], "any", PARTS["dock_insert"][3], 12, PARTS["dock_insert"][5], ""])
    with open(FAB / "MANIFEST.csv", "w", newline="", encoding="utf-8") as fh:
        w_ = csv.writer(fh)
        w_.writerow(["file", "process", "material", "colour", "finish", "qty", "tolerance_notes", "volume_cm3"])
        w_.writerows(rows)
    write_part_readmes(p, vols)

    def cost(sz: str, part: str, qty: int) -> float:
        vol = vols[sz].get(part, 0.0)
        if PARTS[part][0].startswith("MJF"):
            return qty * max(F.MJF_MIN_PART, vol * F.PA12_DENSITY * F.MJF_BILL_FACTOR * F.MJF_PER_G)
        return qty * max(F.SLA_MIN_PART, vol * F.SLA_BILL_FACTOR * F.SLA_PER_CM3 * 4)

    cols = [("bottom", 1), ("top", 2), ("end_cap", 2), ("end_cap_lid", 2), ("plunger_core", 2), ("cannula_adapter", 2)]
    lines = ["| size | " + " | ".join(f"{c} x{q}" for c, q in cols) + " | subtotal (printed) |", "|---|" + "---|" * (len(cols) + 1)]
    sub = {}
    for sz in SIZES:
        c = [cost(sz, k, q) for k, q in cols]
        sub[sz] = sum(c)
        lines.append(f"| {sz} | " + " | ".join(f"${x:.1f}" for x in c) + f" | ${sub[sz]:.1f} |")
    readme = f"""# OpenPatch v0.1.0 integrated pod - fabrication folder (`out/v010/fab/`)

EXPERIMENTAL TEST sample, **water only, never on a person or animal, never insulin or any drug**. One coherent model (`generate.py --variant v010`, `V010.md`): coaxial one-rod drive, motor in the rear zone,
closed CNC reservoir (re-frozen interface), minimal fluid module, dock insert on the frozen interface, MAIN / POWER / SENSOR boards, waterproof USB-C in the rear wall, clear lid.
Folders: `OP-100/`, `OP-200/` (upload), `reservoir-cnc/` (STEP for the CNC order), `mould/`, `dock-inserts/` (shared with the bench pod), `gasket/`, `cap-gasket/`, `usb-gasket/` (DXF for die/laser cutting),
`parts/` (one README per part: process, material, tolerances, post-processing), `MANIFEST.csv`. Units mm; STEP is master.

{VT}

## Order sheet (every size)

| file | process | material | colour | finish | qty | tolerance / features |
|---|---|---|---|---|---|---|
""" + "\n".join(f"| `<SIZE>/{k}.stl` | {v[0]} | {v[1]} | {v[2]} | {v[3]} | {v[4]} | {v[5]} |" for k, v in PARTS.items() if v[8] and k not in ("reservoir_cnc", "dock_insert")) + f"""
| `reservoir-cnc/<SIZE>_reservoir_cnc.step` | {PARTS['reservoir_cnc'][0]} | PP | natural | as machined | 2 | {PARTS['reservoir_cnc'][5]} |
| `mould/mould_lower.stl`, `mould_upper.stl` | {F.MOULD[0]} | {F.MOULD[1]} | {F.MOULD[2]} | {F.MOULD[3]} | {F.MOULD[4]} set | {F.MOULD[5]} |
| `dock-inserts/` | {PARTS['dock_insert'][0]} | | | | 12 | shared with the bench pod |

Not uploaded: `plunger_seal` (cast), `gasket`, `cap_gasket`, `usb_gasket` (silicone sheet cut from the DXFs).

## Purchased items (not printed)

| item | source | qty |
|---|---|---|
""" + "\n".join(f"| {a} | {b} | {c} |" for a, b, c in PURCHASED) + f"""

## Estimated printed-part cost (ESTIMATE, same price model as the bench pod)

{chr(10).join(lines)}

* + shipping {F.SHIP_EST[0]:.0f}-{F.SHIP_EST[1]:.0f} USD; the CNC reservoir quote comes from the vendor (qty 2 per size).
* The PCBAs (outlines in `OP-xx.layout.json`) are ordered separately (`electronics/v010`).
"""
    (FAB / "README.md").write_text(readme, encoding="utf-8")
    print(f"v010 fab folder written: {FAB}")
