# SPDX-License-Identifier: CERN-OHL-P-2.0
"""Fab files of the cup pod: U-clip stencil DXF + data, dock fit-test coupon (clip design), tank CNC data package.  TEST PROJECT, water only."""
from __future__ import annotations

import copy
import csv
import json
import shutil
from pathlib import Path

import op_cup_dock as dock
from generate import run_cli
from op_cmds import Script
from op_coupon import A_STEPS, N_STEPS


def run(p: dict, out: Path, L: dict) -> dict:
    K = L["dock"]
    fab = out / "fab"
    (fab / "stencil").mkdir(parents=True, exist_ok=True)
    dxf = dock.dxf_u_clip(p, K, fab / "stencil" / "u_clip_301FH_0p10.dxf")
    st, hw = dock.clip_stress(p, K), dock.hall_window(p)
    c = p["cup"]["dock"]
    (fab / "stencil" / "u_clip_data.json").write_text(json.dumps({
        "status": "ALL DOCK VALUES TODO-MEASURE (Insight Flex not measured; head estimated from photos).  Order: laser-cut stainless stencil sheet, flat pattern in the DXF (layer CUT = outline, BEND = bend lines; "
                  "two clips), then bend over a 0.15 mm radius.  JLCPCB/PCBWay stencil service cuts 0.1 / 0.12 / 0.15 mm sheets; the SMT-stencil steel is usually 304 or 316L (spring temper NOT guaranteed): "
                  "order the 301 FH foil (or full-hard 1.4310) as a custom cut / or use 304 stencil steel for the first fit test and expect a lower allowable stress (VERIFY).",
        "material": c["clip"]["material"], "thickness_mm": c["clip"]["t"], "dxf": dxf, "stress": st, "hall": hw,
        "latch_force": {"engage_N_per_clip": round(st["F_need_N"], 3), "note": "vertical tooth faces lock the head; release by lifting both teeth with a 0.5 mm pick; retention limited by the notch (placeholder), not by the clip"},
        "allowable": f"{c['clip']['allow_MPa']} MPa = 0.65 x Rp0.2 ({c['clip']['yield_MPa']} MPa, 301 FH) for a few hundred snaps (fatigue not analysed)"}, indent=1), encoding="utf-8")
    # ---- dock fit-test coupon: pocket + window + needle stop wall, head variants (dome d x notch depth), same clip
    cp = fab / "dock-coupon"
    cp.mkdir(exist_ok=True)
    s = Script()
    half, z_roof0 = K["half"], p["cup"]["dock"]["head"]["B_dome_h"] + c["clr"]
    lx = K["pocket_len"] + 1.2
    s.box("dock_fixture", (-1.0, lx), (-half - c["pocket_wall"], half + c["pocket_wall"]), (0, z_roof0 + c["roof"]))
    s.cut("dock_fixture", [s.box("t_in", (0.0, K["pocket_len"]), (-half, half), (-0.1, z_roof0)),
                           s.cyl("t_hub", "X", (0, 0, K["z_n"]), p["cup"]["dock"]["hub"]["d"] - p["cup"]["dock"]["hub"]["press"], -1.1, 0.1)])
    rows = []
    vi = 0
    for dn in N_STEPS:
        for da in A_STEPS:
            vi += 1
            q = copy.deepcopy(p)
            hh = q["cup"]["dock"]["head"]
            hh["A_dome_d"] = round(hh["A_dome_d"] + da, 3)
            hh["notch_depth"] = round(hh["notch_depth"] + dn, 3)
            Kq = dock.layout(q, -0.05, 0.0)
            dock.build_head(s, q, Kq, name=f"head_v{vi:02d}", mag=f"head_mag_v{vi:02d}")
            sq = dock.clip_stress(q, Kq)
            rows.append([vi, hh["A_dome_d"], hh["notch_depth"], round(sq["need_travel"], 2), round(sq["sigma_need"]), round(sq["F_need_N"], 3)])
    names = [f"head_v{i:02d}" for i in range(1, vi + 1)]
    s.export_step(str(cp / "dock_fixture.step"), ["dock_fixture"])
    s.export_stl(str(cp / "dock_fixture.stl"), ["dock_fixture"])
    for n in names:
        s.export_stl(str(cp / f"{n}.stl"), [n])
    sj = cp / "_c.script.json"
    sj.write_text(json.dumps(s.dumps()), encoding="utf-8")
    run_cli("run", str(sj), "--quiet")
    sj.unlink()
    with open(cp / "variants.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["id", "head_dome_d_mm (TODO-MEASURE)", "notch_depth_mm", "clip_travel_mm", "clip_stress_MPa", "clip_force_N"])
        wr.writerows(rows)
    # ---- tank CNC data package
    rc = out / "reservoir-cnc"
    rc.mkdir(exist_ok=True)
    for ext in ("step", "stl"):
        src = out / f"{L['variant']}_reservoir.{ext}"
        if src.exists():
            shutil.copy(src, rc / src.name)
    fz, fl = p["reservoir_frozen"], p["cup"]["fill"]
    pkg = {"_status": "NOT frozen / NOT ordered (user 2026-11-19): cup-pod tank, replaces reservoir_frozen for the cup variant only. Material PP-H, water only.",
           "bore": {"w": fz["bore_w"], "h": fz["bore_h"], "corner_r": fz["bore_h"] / 2, "tol": "+0.05/0", "Ra_um": 0.8, "depth_from_dry_rim": round(L["x_in"] - L["x_dry"], 2)},
           "outer": {"w": fz["outer_w"], "h": fz["outer_h"], "tol": "+-0.1", "length": round(L["tank_len"], 2), "wall": fz["wall"], "front_wall": fz["end_wall"]},
           "outlet": {"bore": f"d{fl['out_d']} straight along +X through the front wall at y={L['y_r']:.2f}, z={K['z_n']}",
                      "hub_seat": f"d{p['cup']['dock']['hub']['d'] - p['cup']['dock']['hub']['press']:.2f} H7 (press 0.08) from x={K['x_hub'][0]:.2f} to the front face, 30G needle hub d{p['cup']['dock']['hub']['d']}"},
           "fill_septum": {"pocket": f"d{fl['pocket_d']} x {fl['pocket_top'] - 0.85:.2f} from the underside (z 0.85..{fl['pocket_top']}) at x={L['x_s']:.2f}, y={L['y_s']:.2f}",
                           "channel": f"d{fl['chan_d']} along X at z={fl['chan_z']} into the bore front lower corner", "septum": f"silicone disc d{fl['septum_d']} x {fl['septum_h']}",
                           "note": "angled (tilted) fill bore NOT modelled: SolidCraft script cylinders are axis-aligned; vertical pocket + short horizontal channel is the CAD equivalent. VERIFY with the CNC shop (3-axis tilt vs 3+2)."},
           "dead_volume": "plunger front face reaches the front wall (gap 0.02 mm); remaining dead volume = outlet legs + gap ~0.4 U (about 4 mm3)"}
    (rc / "reservoir_cnc.json").write_text(json.dumps(pkg, indent=1), encoding="utf-8")
    return {"stencil": dxf, "coupon_variants": len(rows)}
