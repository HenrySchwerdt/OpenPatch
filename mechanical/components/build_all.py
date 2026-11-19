#!/usr/bin/env python3
"""Build the OpenPatch vendor-component library: python3 build_all.py [--only id,id] [--force] [--no-boards]

For every part: out/<id>.{step,stl,glb,png} + catalog.json. Parts whose STEP already exists are skipped unless --force
(modelled threads take minutes). Board exports (kicad-cli) go through gen_boards.py.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MODULES = ["gen_motor", "gen_gear", "gen_fasteners", "gen_magnet", "gen_fluid", "gen_ic", "gen_connectors",
           "gen_battery_cannula"]

# fixed part -> project usage notes for the assembly generator (params.json names / PARTS-LOCK rows)
USE = {
    "nfp_608_26_45": "drive motor (PARTS-LOCK #2); params.json drive_presets.nfp_608_26",
    "gear_m03_z15_753015": "motor-side pinion option 15T (PARTS-LOCK #3, firmware preset drive-nfp-608-26-45-g15-12)",
    "gear_m03_z12_753012": "leadscrew-side gear 12T (PARTS-LOCK #3)",
    "gear_m03_z18_390755": "18T:18T 1:1 option used by last CAD snapshot (parts.md 1.0)",
    "rod_m1p6_19": "leadscrew, OP-70 cut length", "rod_m1p6_22": "leadscrew, OP-100 cut length", "rod_m1p6_37": "leadscrew, OP-200 cut length",
    "nut_din934_m1p6_brass": "carriage nut (PARTS-LOCK #5)",
    "screw_iso7045_m1p2x3": "lid/board screw (PARTS-LOCK #20)", "screw_iso7045_m1p2x4": "pod board screw len 4 (params bench.mount.screw_len)",
    "magnet_d2x1_diametric": "superseded spindle magnet option", "magnet_d3x1p5_diametric": "FINAL spindle magnet d3x1.5 diametric", "gear_m03_z16_390754": "FINAL motor gear 16T (centre 5.51 with 20T incl. clearance)", "gear_m03_z20_753020": "FINAL screw gear 20T", "magnet_d2x1_axial": "dock magnet (PARTS-LOCK #8)",
    "needle_30g_efd_14in": "outlet needle (PARTS-LOCK #17)", "duckbill_valve_generic": "outlet check valve (PARTS-LOCK #16)",
    "septum_d4x2": "fill septum (PARTS-LOCK #18)",
    "ebyte_e73_2g4m08s1c": "bench controller MCU module (PARTS-LOCK #11)",
    "ic_tmag5273_sot23_6": "pod angle sensor (PARTS-LOCK #9)", "ic_drv5032_x2son": "pod dock/hall switch (PARTS-LOCK #10)",
    "ic_stspin220_vfqfpn16": "motor driver (PARTS-LOCK #12)", "ic_tpl5010_sot23_6": "watchdog (PARTS-LOCK #13)",
    "hirose_fh12_10s_0p5sh": "pod and controller FFC connector (PARTS-LOCK #15)", "ffc_05mm_10p_same_side": "pod<->controller cable (PARTS-LOCK #15)",
    "molex_picoblade_53261_0471": "controller motor connector (PARTS-LOCK #14)", "lead_picoblade_plug": "NFP motor lead with plug (PARTS-LOCK #14)",
    "battery_lipo_3x12x20": "Rev B battery placeholder", "cannula_head_dummy": "dock fit layout (PARTS-LOCK #1)",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-boards", action="store_true")
    a = ap.parse_args()
    only = {x for x in a.only.split(",") if x}
    from cc import OUT
    cat_path = HERE / "catalog.json"
    catalog = json.loads(cat_path.read_text()) if cat_path.exists() else {}
    for modname in MODULES:
        mod = importlib.import_module(modname)
        for part in mod.build():
            if only and part.pid not in only:
                continue
            meta = mod.META[part.pid]
            print("build", part.pid, flush=True)
            info = part.build(force=a.force)
            catalog[part.pid] = {
                "title": meta["title"],
                "files": info["files"],
                "size_mm": info["size"],
                "bbox_mm": {"min": info["bbox_min"], "max": info["bbox_max"]},
                "mass_g_estimate": info["mass_g"],
                "material": meta["material"],
                "colour": meta["colour"],
                "bodies": {b: part.mat[b] for b in info["bodies"] if b in part.mat},
                "frame": meta["frame"],
                "source": meta["source"],
                "confidence": meta["confidence"],
                "notes": meta["notes"],
                "used_for": USE.get(part.pid, ""),
            }
            cat_path.write_text(json.dumps(dict(sorted(catalog.items())), indent=1))
    if not a.no_boards and not only:
        import gen_boards
        gen_boards.main()
        rep = json.loads((OUT / "boards" / "boards.models.json").read_text())
        for name, r in rep.items():
            catalog[name] = {
                "title": f"{name.replace('_', ' ')} (KiCad STEP export with component models)",
                "files": {k: f"out/boards/{name}.{k}" for k in ("step", "stl", "glb", "png") if (OUT / "boards" / f"{name}.{k}").exists()},
                "material": "FR4 + KiCad stock component models", "colour": "green soldermask, gold pads",
                "frame": "KiCad board coordinates (mm), PCB top at z~1.5, bottom z=0",
                "source": r["pcb"] + " via kicad-cli pcb export step (KiCad 10, stock 3D libraries)",
                "confidence": "datasheet (board geometry from the design) / mixed (stock component models)",
                "footprints_without_3d_model": r["footprints_without_3d_model"],
                "footprints_model_file_not_found": r["footprints_model_file_not_found"],
                "notes": "Replace missing-model parts with the models in this library (e.g. ic_drv5032_x2son, ebyte_e73_2g4m08s1c).",
            }
        cat_path.write_text(json.dumps(dict(sorted(catalog.items())), indent=1))
    import sanitize
    sanitize.main()
    print(f"catalog: {len(catalog)} entries")


if __name__ == "__main__":
    main()
