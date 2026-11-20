# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Driver of `generate.py --variant v010 --drive cup` (op_cup.py): CAD + exports + renders in out/v010-cup/. TEST PROJECT, water only."""
from __future__ import annotations

import json
from pathlib import Path

import cup_annotate
import op_cup
from generate import run_cli
from op_cmds import Script
from op_layout import HERE

COLORS = {
    "top": "opacity=0.16,color=#9fb3c8", "bottom": "opacity=0.5,color=#c9d3dd",
    "reservoir": "opacity=0.45,color=#7fd0e0", "plunger_core": "color=#e0803a", "seal_a": "color=#dd2222", "seal_b": "color=#dd2222", "nut": "color=#f0c040",
    "rod": "color=#111111", "thrust_sleeve": "color=#d4a017", "bush_rod": "color=#b0701c", "gear_a": "color=#e8b000", "gear_b": "color=#f2d020",
    "motor": "color=#8a8f98", "gearhead": "color=#b9bec6", "motor_boss": "color=#9a9a9a", "motor_shaft": "color=#555555", "motor_rear_boss": "color=#666666", "motor_term": "color=#c06020",
    "magnet": "color=#cc2222", "hall_tmag": "color=#ffd400", "end_cap": "color=#d8dde3", "end_cap_lid": "opacity=0.6,color=#e6eaee", "cap_gasket": "color=#222222", "cap_oring": "color=#aa3333",
    "septum": "color=#f2a0c0", "needle": "color=#000000", "needle_hub": "color=#5ec8e8", "cannula_adapter": "opacity=0.55,color=#7a5cc7",
    "dock_magnet": "color=#cc2222", "hall_dock": "color=#ff7f00",
    "ko_dock_board": "opacity=0.45,color=#2e8b57", "dock_clip": "color=#b8c0c8", "needle_guard": "opacity=0.6,color=#5ec8e8", "ko_side_a": "opacity=0.45,color=#c0a060", "ko_side_b": "opacity=0.45,color=#c0a060", "ko_io": "opacity=0.45,color=#d09020", "ko_aux": "opacity=0.35,color=#7fbf7f", "ko_board": "opacity=0.35,color=#2e8b57", "ko_board_tab": "opacity=0.35,color=#2e8b57", "ko_battery": "opacity=0.4,color=#3a5fcd", "ko_usb": "opacity=0.45,color=#8a3fd0", "ko_tmag_board": "opacity=0.45,color=#2e8b57",
}
EXPLODE = {"top": (0, 0, 24), "ko_board": (0, 0, 16), "ko_board_tab": (0, 0, 16), "ko_battery": (0, 0, 16), "ko_tmag_board": (0, 0, 11), "end_cap_lid": (0, 0, 17), "cap_gasket": (0, 0, 12), "septum": (0, 0, 9),
           "plunger_core": (0, 0, 13), "seal_a": (0, 0, 13), "seal_b": (0, 0, 13), "nut": (0, 0, 19), "rod": (0, 0, 21), "thrust_sleeve": (0, 0, 15), "gear_b": (0, 0, 15),
           "gear_a": (0, 0, 15), "bush_rod": (0, 0, 9), "magnet": (0, 0, 15), "hall_tmag": (0, 0, 12), "reservoir": (0, 0, 7), "motor": (0, 0, 9), "gearhead": (0, 0, 9),
           "motor_boss": (0, 0, 9), "motor_shaft": (0, 0, 12), "motor_rear_boss": (0, 0, 9), "motor_term": (0, 0, -5), "needle": (0, 0, -7), "needle_hub": (0, 0, -7),
           "cap_oring": (0, 0, 5), "dock_clip": (0, 0, 10), "needle_guard": (0, 0, -7), "ko_dock_board": (0, 0, 16), "cannula_adapter": (0, 0, -15), "dock_magnet": (0, 0, -19), "hall_dock": (0, 0, 13), "ko_usb": (0, 0, -3), "ko_io": (0, 0, 14), "ko_side_a": (0, 0, 14), "ko_side_b": (0, 0, 14), "ko_aux": (0, 0, 16)}


def _cols(created: set) -> list[str]:
    out: list[str] = []
    for k, v in COLORS.items():
        if k in created:
            out += ["--body", f"{k}:{v}"]
    return out


def generate_size(p: dict, variant: str, outdir: Path, snapshots: bool) -> dict:
    s, L = op_cup.build(p, variant)
    created = {c["params"].get("body_name") for c in s.dumps() if c["params"].get("body_name")}
    asm = [b for b in op_cup.PART_NAMES if b in created]
    mfg = {k: [b for b in v if b in created] for k, v in op_cup.MFG_PARTS.items()}
    tag = variant
    s.export_step(str(outdir / f"{tag}_assembly.step"), asm)
    for part, bodies in mfg.items():
        s.export_step(str(outdir / f"{tag}_{part}.step"), bodies)
        s.export_stl(str(outdir / f"{tag}_{part}.stl"), bodies)
    script = outdir / f"{tag}.script.json"
    script.write_text(json.dumps(s.dumps(), indent=1), encoding="utf-8")
    sc = outdir / f"{tag}.sc"
    run_cli("run", str(script), "--save", str(sc), "--quiet")
    (outdir / f"{tag}.mech.json").write_text(json.dumps(L, indent=1), encoding="utf-8")
    if snapshots:
        shots(sc, outdir, tag, L, created)
        asm_shots(sc, outdir, tag, L, created)
        cup_annotate.draw(p, L, outdir / f"{tag}_top_annotated.svg")
        import cup_fab
        cup_fab.run(p, outdir, L)
    return L


def shots(sc: Path, outdir: Path, tag: str, L: dict, created: set) -> None:
    cols = _cols(created)
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_iso.png"), "--view", "iso", "--width", "1800", "--height", "1000", "--no-grid", "--no-axes", *cols)
    ex = Script()
    ex.add("parameters.add", name="p_dummy_explode", expression="0", comment="exploded-view helper")
    for b, t in EXPLODE.items():
        if b in created:
            ex.move([b], t)
    exj = outdir / f"{tag}.explode.json"
    exj.write_text(json.dumps(ex.dumps()), encoding="utf-8")
    run_cli("snapshot", str(exj), "--in", str(sc), "--out", str(outdir / f"{tag}_exploded.png"), "--view", "iso", "--width", "2200", "--height", "1400", "--no-grid", "--no-axes", *cols)
    exj.unlink()
    zc = L["zc"]
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_section_top_axis.png"), "--view", "top", "--section", f"z={zc:.2f}", "--width", "2400", "--height", "1000", "--no-grid", "--no-axes", *cols)
    cam = {"target": [L["length"] / 2, L["y_r"], L["height"] / 2], "yaw": 3.14159, "pitch": 0.0, "distance": 0.85 * L["length"]}
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_section_side_axis.png"), "--camera", json.dumps(cam), "--section", f"y={L['y_r']:.2f}", "--width", "2600", "--height", "800",
            "--no-grid", "--no-axes", *cols)
    xs = L["dock"]["x_d"]
    cam2 = {"target": [xs, L["width"] / 2, L["height"] / 2], "yaw": 1.5708, "pitch": 0.0, "distance": 30.0}
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_section_cross_dock.png"), "--camera", json.dumps(cam2), "--section", f"x={xs:.2f}", "--width", "1800", "--height", "900",
            "--no-grid", "--no-axes", *cols)


def asm_shots(sc: Path, outdir: Path, tag: str, L: dict, created: set) -> None:
    import op_cup_asm
    cols = _cols(created) + ["--body", "lid_gasket:color=#c04040", "--body", "usb_gasket:color=#c04040", "--body", "hub_oring:color=#c04040"]
    offs = [0, 9, 18, 26, 34, 44, -12]
    ex = Script()
    ex.add("parameters.add", name="p_dummy_explode2", expression="0", comment="assembly exploded view")
    for gi, (gname, names) in enumerate(op_cup_asm.ORDER):
        for n in names:
            if n in created:
                ex.move([n], (0, 0, offs[gi]))
    for n in ("cannula_adapter", "dock_magnet"):
        if n in created:
            ex.move([n], (0, 0, -22))
    exj = outdir / f"{tag}.asm.json"
    exj.write_text(json.dumps(ex.dumps()), encoding="utf-8")
    run_cli("snapshot", str(exj), "--in", str(sc), "--out", str(outdir / f"{tag}_assembly_exploded.png"), "--view", "iso", "--width", "2200", "--height", "1500", "--no-grid", "--no-axes", *cols)
    exj.unlink()
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_iso_lid_off.png"), "--view", "iso", "--width", "1800", "--height", "1000", "--no-grid", "--no-axes", *cols, "--body", "top:opacity=0.02,color=#9fb3c8")
    rows = [f'<text x="40" y="{1560 + 26 * k}" font-size="20" font-family="Helvetica,Arial,sans-serif"><tspan fill="#c00" font-weight="bold">{g}</tspan>   lifts {offs[k]:+d} mm in the picture</text>' for k, (g, _n) in enumerate(op_cup_asm.ORDER)]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="2200" height="{1580 + 26 * len(rows)}"><rect width="100%" height="100%" fill="#fff"/>'
           f'<image x="0" y="0" width="2200" height="1500" xlink:href="{outdir / (tag + "_assembly_exploded.png")}"/>'
           f'<text x="40" y="40" font-size="26" font-family="Helvetica,Arial,sans-serif" font-weight="bold">{tag} assembly order (exploded, step 1 at the bottom, lid and gaskets last; dock parts from below)</text>' + "".join(rows) + '</svg>')
    sp = outdir / f"{tag}_assembly_labeled.svg"
    sp.write_text(svg, encoding="utf-8")
    import shutil, subprocess
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", "-b", "white", "-o", str(sp.with_suffix(".png")), str(sp)], check=True)


def main(p0: dict, sizes: list[str] | None, outdir: str | None, no_snapshots: bool, snapshot_sizes: list[str]) -> None:
    import copy
    p = op_cup.prepare(p0)
    sizes = sizes or list(p["cup"]["sizes"])
    out = Path(outdir or (HERE / "out" / "v010-cup"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "params.used.json").write_text(json.dumps(p, indent=1), encoding="utf-8")
    from op_mould import build_mould
    import os
    ms, _ = build_mould(p)
    mj = out / "mould.script.json"
    mj.write_text(json.dumps(ms.dumps()).replace("__OUT__", os.path.relpath(out, HERE)), encoding="utf-8")
    run_cli("run", str(mj), "--save", str(out / "mould.sc"), "--quiet")
    for v in sizes:
        L = generate_size(copy.deepcopy(p), v, out, (not no_snapshots) and v in snapshot_sizes)
        e = L["envelope"]
        print(f"{v}: L={L['length']:.2f} W={L['width']:.2f} H={L['height']:.1f} U/step={L['u_per_step']:.5f} env={e['bbox_volume_ml']} ml  tank {L['tank_len']:.1f}  plunger {L['L_pl']:.1f}  rod {L['rod_len']:.1f} -> {out}")
