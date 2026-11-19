#!/usr/bin/env python3
"""OpenPatch mechanical generator (Rev A).

  python3 generate.py                      # all three sizes -> out/
  python3 generate.py --sizes OP-70        # one size
  python3 generate.py --set drive.active_preset=faulhaber_adm0620_16   (see --preset)
  python3 generate.py --preset faulhaber_adm0620_16
  python3 generate.py --set battery.y=10 --no-snapshots

Writes per size: .sc design, assembly STEP, per-part STEP+STL, layout.json (for electronics),
snapshots (iso, exploded, sections).  Then run `python3 fab.py` to build out/fab/.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

from op_build import build_model, part_sets
from op_cmds import Script
from op_drive import build_reservoir
from op_layout import HERE, find_cli, load_params, merge, stadium_area
from op_mould import build_mould

CLI = find_cli()

# exploded view: translation per body group (z up, mm)
EXPLODE = {
    "top": (0, 0, 22), "qi_coil": (0, 0, 17), "gasket": (0, 0, 12), "rf_module": (0, 0, 9), "buzzer": (0, 0, 9),
    "switch": (0, 0, 9), "pcb": (0, 0, 7), "hall_tmag": (0, 0, 7), "hall_drv0": (0, 0, 7), "hall_drv1": (0, 0, 7),
    "carriage": (0, 0, 14), "nut": (0, 0, 14), "plunger_core": (0, 0, 10), "seal_a": (0, 0, 10), "seal_b": (0, 0, 10),
    "leadscrew": (0, 0, 8), "magnet": (0, 0, 8), "bush_dry": (0, 0, 8), "bush_far": (0, 0, 8),
    "reservoir": (0, 0, 4), "septum": (0, -8, 4), "needle": (0, 0, -6), "needle_hub": (0, 0, -3),
    "motor": (0, 0, 4), "gearhead": (0, 0, 4), "gear_a": (0, 0, 8), "gear_b": (0, 0, 12),
    "battery": (0, 0, -4), "bottom": (0, 0, -10),
}
COLORS = ["--body", "top:opacity=0.18,color=#9fb3c8", "--body", "bottom:opacity=0.55,color=#c9d3dd",
          "--body", "reservoir:opacity=0.5,color=#7fd0e0", "--body", "plunger_core:color=#e0803a",
          "--body", "seal_a:color=#dd3333", "--body", "seal_b:color=#dd3333", "--body", "carriage:color=#f0c040",
          "--body", "pcb:color=#2e8b57", "--body", "battery:color=#3a5fcd", "--body", "qi_coil:color=#b87333",
          "--body", "pcb_keepout:opacity=0.05", "--body", "rf_module:color=#222222", "--body", "gasket:color=#111111"]


BENCH_EXPLODE = {
    "top": (0, 0, 22), "ffc_cable": (14, 0, 16), "ffc_conn": (0, 0, 14), "hall_drv0": (0, 0, 12), "hall_drv1": (0, 0, 12),
    "pod_board": (0, 0, 8), "hall_tmag": (0, 0, 6), "hall_dock": (0, 0, 6), "gasket": (0, 0, 12),
    "carriage": (0, 0, 14), "nut": (0, 0, 14), "plunger_core": (0, 0, 10), "seal_a": (0, 0, 10), "seal_b": (0, 0, 10),
    "leadscrew": (0, 0, 8), "magnet": (0, 0, 8), "bush_far": (0, 0, 8), "reservoir": (0, 0, 4),
    "motor": (0, 0, 10), "gearhead": (0, 0, 10), "motor_boss": (0, 0, 10), "motor_shaft": (0, 0, 10), "motor_rear_boss": (0, 0, 10),
    "motor_term": (0, 6, 10), "motor_pins": (0, 6, 10), "coupler": (0, 0, 14), "duckbill_valve": (0, 0, 12),
    "septum": (0, -8, 4), "needle": (0, 0, -6), "needle_hub": (0, 0, -3), "dock_magnet": (0, 0, -16),
    "cannula_adapter": (0, 0, -12), "dock_insert": (0, 0, -9), "bottom": (0, 0, -6),
}
BENCH_COLORS = ["--body", "top:opacity=0.18,color=#9fb3c8", "--body", "bottom:opacity=0.55,color=#c9d3dd",
                "--body", "reservoir:opacity=0.5,color=#7fd0e0", "--body", "plunger_core:color=#e0803a",
                "--body", "carriage:color=#f0c040", "--body", "pod_board:color=#2e8b57", "--body", "cannula_adapter:color=#7a5cc7", "--body", "dock_insert:color=#e07ac0",
                "--body", "ffc_cable:color=#e8c36a", "--body", "ffc_conn:color=#222222", "--body", "motor:color=#888888", "--body", "gearhead:color=#aaaaaa", "--body", "coupler:color=#d4a017", "--body", "duckbill_valve:color=#5ec8e8",
                "--body", "dock_magnet:color=#cc2222", "--body", "magnet:color=#cc2222", "--body", "gasket:color=#111111"]


def run_cli(*args: str) -> subprocess.CompletedProcess:
    res = subprocess.run([CLI, *args], capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stdout[-2000:] + res.stderr[-3000:])
        raise SystemExit(f"solidcraft-cli {' '.join(args[:2])} failed")
    return res


def apply_overrides(p: dict, sets: list[str], coil_d: float | None, preset: str | None) -> dict:
    over: dict = {}
    for item in sets:
        key, val = item.split("=", 1)
        node = over
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = json.loads(val)
    if coil_d is not None:
        over.setdefault("coil", {})["d"] = coil_d
    p = merge(p, over)
    preset = preset or p["drive"].get("active_preset")
    if preset:
        p = merge(p, {"drive": {**p["drive_presets"][preset], "active_preset": preset}})
        p = merge(p, over)
    return p


def envelope_info(p: dict, L: dict) -> dict:
    r = p["shell"]["corner_r"]
    area = L["length"] * L["width"] - (4 - math.pi) * r * r
    bbox_ml = L["length"] * L["width"] * L["height"] / 1000.0
    return {"bbox_mm": [round(L["length"], 2), L["width"], L["height"]], "bbox_volume_ml": round(bbox_ml, 2),
            "footprint_mm2": round(area, 1),
            "outer_solid_volume_ml_approx": round(area * L["height"] / 1000.0, 2),
            "note": "outer_solid_volume ignores the 1.0 mm top edge fillet (conservative, <2 % high)"}


def reservoir_cnc_script(p: dict, L: dict, tag: str, outdir: Path) -> Script:
    """Two CNC halves of the reservoir (split at the bore centre plane) - bonded after machining."""
    s = Script()
    zc = L["z_axis"]
    for nm, z in (("reservoir_cnc_lower", (-1.0, zc)), ("reservoir_cnc_upper", (zc, 12.0))):
        build_reservoir(s, p, L, name=nm)
        box = s.box(f"t_half_{nm}", (L["x_r0"] - 1, L["x_r1"] + 1), (0, 32), z)
        s.add("solid.combine", target=nm, tools=[box], operation="intersect", name=f"half {nm}")
        s.export_step(str(outdir / f"{tag}_{nm}.step"), [nm])
        s.export_stl(str(outdir / f"{tag}_{nm}.stl"), [nm])
    return s


def generate_size(p: dict, variant: str, outdir: Path, snapshots: bool) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    s, L = build_model(p, variant)
    bench = L["mode"] == "bench"
    MFG_PARTS, PART_NAMES, _ = part_sets(L["mode"])
    tag = variant
    from op_build import NFP_PARTS
    created = {c["params"].get("body_name") for c in s.dumps() if c["params"].get("body_name")}
    asm = [b for b in PART_NAMES if b != "pcb_keepout" and b in created]
    MFG_PARTS = {k: [b for b in v if b in created] for k, v in MFG_PARTS.items() if any(b in created for b in v)}
    s.export_step(str(outdir / f"{tag}_assembly.step"), asm)
    for part, bodies in MFG_PARTS.items():
        s.export_step(str(outdir / f"{tag}_{part}.step"), bodies)
        s.export_stl(str(outdir / f"{tag}_{part}.stl"), bodies)
    script = outdir / f"{tag}.script.json"
    script.write_text(json.dumps(s.dumps(), indent=1), encoding="utf-8")
    sc = outdir / f"{tag}.sc"
    run_cli("run", str(script), "--save", str(sc), "--quiet")
    L["envelope"] = envelope_info(p, L)
    if bench:
        from op_bench import layout_json
        (outdir / f"{tag}.mech.json").write_text(json.dumps(L, indent=1), encoding="utf-8")
        (outdir / f"{tag}.layout.json").write_text(json.dumps(layout_json(p, L, L["bench"]), indent=1), encoding="utf-8")
    else:
        (outdir / f"{tag}.layout.json").write_text(json.dumps(L, indent=1), encoding="utf-8")
    # CNC reservoir halves
    if not bench:
        cs = reservoir_cnc_script(p, L, tag, outdir)
        cj = outdir / f"{tag}.cnc.script.json"
        cj.write_text(json.dumps(cs.dumps()), encoding="utf-8")
        run_cli("run", str(cj), "--quiet")
        cj.unlink()
    # mould files (size independent) copied per size
    for f in ("mould_lower.step", "mould_upper.step", "mould_lower.stl", "mould_upper.stl"):
        shutil.copy(outdir / f, outdir / f"{tag}_{f}")
    if snapshots:
        shots(sc, outdir, tag, L, created)
    return L


def shots(sc: Path, outdir: Path, tag: str, L: dict, created: set | None = None) -> None:
    bench = L["mode"] == "bench"
    COLORS = BENCH_COLORS if bench else globals()["COLORS"]
    EXPLODE = BENCH_EXPLODE if bench else globals()["EXPLODE"]
    if created is not None:        # drop colour entries of bodies that do not exist in this variant (solidcraft-cli errors on them)
        COLORS = [x for k, x in enumerate(COLORS) if x == "--body" and k + 1 < len(COLORS) and COLORS[k + 1].split(":")[0] in created
                  or (k > 0 and COLORS[k - 1] == "--body" and x.split(":")[0] in created)]
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_iso.png"), "--view", "iso",
            "--width", "1400", "--height", "900", *COLORS)
    ex = Script()
    ex.add("parameters.add", name="p_dummy_explode", expression="0", comment="exploded-view helper")
    for b, t in EXPLODE.items():
        if created is None or b in created:
            ex.move([b], t)
    exj = outdir / f"{tag}.explode.json"
    exj.write_text(json.dumps(ex.dumps()), encoding="utf-8")
    run_cli("snapshot", str(exj), "--in", str(sc), "--out", str(outdir / f"{tag}_exploded.png"), "--view", "iso",
            "--width", "1800", "--height", "1300", "--no-grid", "--no-axes", *COLORS)
    exj.unlink()
    secs = [("section_y_cannula", L["y_p"]), ("section_y_reservoir", L["y_r"]), ("section_y_screw", L["y_s"]),
            ("section_y_motor", L["y_m"])]
    for nm, y in secs:
        cam = {"target": [L["length"] / 2, y, L["height"] / 2], "yaw": 3.14159, "pitch": 0.0,
               "distance": 0.85 * L["length"]}
        run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_{nm}.png"), "--camera", json.dumps(cam),
                "--section", f"y={y:.2f}", "--width", "1600", "--height", "600", "--no-grid", "--no-axes", *COLORS)
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_section_plan_z4.2.png"), "--view", "top",
            "--section", f"z={L['z_axis']:.2f}", "--width", "1800", "--height", "800", "--no-grid", "--no-axes", *COLORS)


def generate_coupon(p: dict) -> None:
    """Dock insert variant set (12 variants, embossed IDs) + pod-less fit-test fixture -> out/bench/fab/dock-inserts/."""
    from op_coupon import add_variant_inserts, build_fixture, variants
    p = copy.deepcopy(p)
    p["mode"] = "bench"
    d = HERE / "out" / "bench" / "fab" / "dock-inserts"
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("*"):
        old.unlink()
    s = Script()
    vs = variants(p)
    geo = add_variant_inserts(s, p, vs)
    build_fixture(s, p)
    for v in vs:
        nm = f"dock_insert_v{v['id']:02d}"
        s.export_step(str(d / f"insert_v{v['id']:02d}.step"), [nm])
        s.export_stl(str(d / f"insert_v{v['id']:02d}.stl"), [nm])
    s.export_step(str(d / "dock_fixture.step"), ["dock_fixture"])
    s.export_stl(str(d / "dock_fixture.stl"), ["dock_fixture"])
    sj = d / "_inserts.script.json"
    sj.write_text(json.dumps(s.dumps()), encoding="utf-8")
    run_cli("run", str(sj), "--save", str(d / "dock_inserts.sc"), "--quiet")
    sj.unlink()
    (d / "dock_inserts.sc").unlink()
    (d / "LICENSE.md").write_text(
        "# Licence of this folder\n\n"
        "SPDX-License-Identifier: CERN-OHL-P-2.0\n\n"
        "The dock inserts, the dock fixture, the variants table and their generators (`mechanical/op_dock.py`, `mechanical/op_coupon.py`,\n"
        "`mechanical/cannula-measurement.md`) are released under the permissive CERN Open Hardware Licence Version 2 - Permissive\n"
        "(CERN-OHL-P-2.0). The rest of the repository is under the project's non-commercial dual licence. Test project, not a medical\n"
        "device; never for use on a person.\n", encoding="utf-8")
    with open(d / "variants.csv", "w", encoding="utf-8") as fh:
        fh.write("id,file,cannula.A_dome_d,cannula.N_hook_h,hook_gap_mm,arm_strain_pct,arm_tip_travel_mm,arm_force_N\n")
        for v in vs:
            g = geo[v["id"]]
            fh.write(f"{v['id']},insert_v{v['id']:02d}.stl,{v['A_dome_d']},{v['N_hook_h']},{2 * g['hook_in']:.3f},"
                     f"{g['arm_strain'] * 100:.2f},{g['travel']:.3f},{g['arm_tip_force_N']:.2f}\n")
    print(f"dock inserts + fixture written: {d}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", nargs="*")
    ap.add_argument("--variant", choices=["integrated", "bench"], default="integrated",
                    help="bench = bench pod (sensor board + FFC, no battery/coil/RF), writes to out/bench/")
    ap.add_argument("--outdir")
    ap.add_argument("--params")
    ap.add_argument("--preset", help="drive preset from params.json drive_presets")
    ap.add_argument("--coil-d", type=float)
    ap.add_argument("--set", action="append", default=[], metavar="group.key=value")
    ap.add_argument("--no-snapshots", action="store_true")
    ap.add_argument("--coupon", action="store_true", help="only build the dock insert variant set + fit-test fixture (out/bench/fab/dock-inserts/)")
    args = ap.parse_args()

    p = apply_overrides(load_params(Path(args.params) if args.params else None), args.set, args.coil_d, args.preset)
    p["mode"] = args.variant
    if args.variant == "bench":
        p["shell"]["width"] = p["bench"]["width_by_layout"][p["bench"]["drive_layout"]]
    if args.coupon:
        generate_coupon(p)
        return

    sizes = args.sizes or list(p["variants"])
    out = Path(args.outdir or (HERE / "out" / "bench" if args.variant == "bench" else HERE / "out"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "params.used.json").write_text(json.dumps(p, indent=1), encoding="utf-8")
    ms, _ = build_mould(p)
    mj = out / "mould.script.json"
    mj.write_text(json.dumps(ms.dumps()).replace("__OUT__", str(out)), encoding="utf-8")
    run_cli("run", str(mj), "--save", str(out / "mould.sc"), "--quiet")
    for v in sizes:
        L = generate_size(copy.deepcopy(p), v, out, not args.no_snapshots)
        extra = "" if args.variant == "bench" else f" battery={L['bat_x']:.1f}x{p['battery']['y']}x{p['battery']['t']}"
        print(f"{v}: L={L['length']:.2f} W={L['width']:.1f} H={L['height']:.1f}{extra} "
              f"U/step={L['drive']['u_per_step']:.5f} env={L['envelope']['bbox_volume_ml']} ml -> {out}")
    if args.variant == "bench" and not args.sizes:
        generate_coupon(p)


if __name__ == "__main__":
    main()
