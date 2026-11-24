#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Generate the v0.1.0 "cart" pump (op_cart.py): CAD, STEP/STL exports, renders and mech.json in out/v010-cart/. TEST PROJECT, water only.

  SOLIDCRAFT_CLI=/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli python3 cart_gen.py [--no-snapshots] [--set cart.cartridge.od=11.2]
  python3 cart_check.py          # interference, height, stroke, thrust, rod never wet
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import op_cart
from generate import apply_overrides, run_cli
from op_cmds import Script
from op_layout import HERE, load_params

TAG = "OP-CART"
COLORS = {
    "top": "opacity=0.15,color=#9fb3c8", "bottom": "opacity=0.45,color=#c9d3dd", "lid_gasket": "opacity=0.5,color=#c04040",
    "cartridge": "opacity=0.35,color=#bfe6f2", "stopper": "color=#333333", "cart_cap": "color=#b8b8b8",
    "adapter": "opacity=0.8,color=#3a78c8", "adapter_lug_a": "color=#2a58a0", "adapter_lug_b": "color=#2a58a0", "tubing": "opacity=0.6,color=#e8f4ff",
    "lock_flag": "color=#f0c040", "lock_magnet": "color=#cc2222", "hall_lock": "color=#ff7f00",
    "rod": "color=#a07020", "rod_nut": "color=#d8b040", "gear_rod": "color=#e8b000", "pinion": "color=#f2d020", "washer_r": "color=#888888", "washer_f": "color=#888888",
    "slider": "color=#e0803a", "pusher": "color=#e0803a",
    "motor": "color=#8a8f98", "gearhead": "color=#b9bec6", "motor_boss": "color=#9a9a9a", "motor_shaft": "color=#555555", "motor_rear_boss": "color=#666666",
    "magnet": "color=#cc2222", "hall_tmag": "color=#ffd400", "ko_tmag_board": "opacity=0.5,color=#2e8b57",
    "ko_board": "opacity=0.45,color=#2e8b57", "ko_battery": "opacity=0.5,color=#3a5fcd", "ko_usb": "opacity=0.6,color=#8a3fd0",
}
EXPLODE = {"top": (0, 0, 26), "lid_gasket": (0, 0, 20), "ko_board": (0, 0, 15), "ko_usb": (0, 0, 15), "ko_battery": (0, 0, 9), "ko_tmag_board": (0, 0, 12), "hall_tmag": (0, 0, 12),
           "magnet": (0, 0, 10), "pinion": (0, 0, 10), "motor_shaft": (0, 0, 8), "motor": (0, 0, 8), "gearhead": (0, 0, 8), "motor_boss": (0, 0, 8), "motor_rear_boss": (0, 0, 8),
           "gear_rod": (0, 0, 13), "rod_nut": (0, 0, 13), "washer_r": (0, 0, 11), "washer_f": (0, 0, 11), "rod": (0, 0, 17), "slider": (0, 0, 17), "pusher": (0, 0, 17),
           "cartridge": (8, 0, 22), "stopper": (8, 0, 22), "cart_cap": (8, 0, 22), "adapter": (22, 0, 4), "adapter_lug_a": (22, 0, 4), "adapter_lug_b": (22, 0, 4),
           "tubing": (22, 0, 4), "lock_flag": (22, 0, 4), "lock_magnet": (22, 0, 4), "hall_lock": (0, 0, 6)}


def _cols(created: set) -> list[str]:
    out: list[str] = []
    for k, v in COLORS.items():
        if k in created:
            out += ["--body", f"{k}:{v}"]
    return out


def shots(sc: Path, outdir: Path, L: dict, created: set) -> None:
    cols = _cols(created)
    common = ["--no-grid", "--no-axes", *cols]
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{TAG}_iso.png"), "--view", "iso", "--width", "1800", "--height", "1000", *common)
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{TAG}_iso_lid_off.png"), "--view", "iso", "--width", "1800", "--height", "1000", *common,
            "--body", "top:opacity=0.02,color=#9fb3c8", "--body", "lid_gasket:opacity=0.02,color=#c04040")
    ex = Script()
    ex.add("parameters.add", name="p_dummy_explode", expression="0", comment="exploded-view helper")
    for b, t in EXPLODE.items():
        if b in created:
            ex.move([b], t)
    exj = outdir / f"{TAG}.explode.json"
    exj.write_text(json.dumps(ex.dumps()), encoding="utf-8")
    run_cli("snapshot", str(exj), "--in", str(sc), "--out", str(outdir / f"{TAG}_exploded.png"), "--view", "iso", "--width", "2200", "--height", "1400", *common)
    exj.unlink()
    zc, yc = L["zc"], L["y_c"]
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{TAG}_section_top_axis.png"), "--view", "top", "--section", f"z={zc:.2f}", "--width", "2400", "--height", "1000", *common)
    cam = {"target": [L["length"] / 2, yc, L["height"] / 2], "yaw": 3.14159, "pitch": 0.0, "distance": 0.95 * L["length"]}
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{TAG}_section_side_axis.png"), "--camera", json.dumps(cam), "--section", f"y={yc:.2f}", "--width", "2600", "--height", "800", *common)
    for nm, x in (("gear", sum(L["gear"]) / 2), ("receiver", L["x_front"] - p_adapter_lug_x(L))):
        cam2 = {"target": [x, L["width"] / 2, L["height"] / 2], "yaw": 1.5708, "pitch": 0.0, "distance": 40.0}
        run_cli("snapshot", str(sc), "--out", str(outdir / f"{TAG}_section_cross_{nm}.png"), "--camera", json.dumps(cam2), "--section", f"x={x:.2f}",
                "--width", "1600", "--height", "1000", *common)


def p_adapter_lug_x(L: dict) -> float:
    return L["_lug_from_front"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir")
    ap.add_argument("--no-snapshots", action="store_true")
    ap.add_argument("--set", action="append", default=[], help="override, e.g. cart.cartridge.od=11.2")
    a = ap.parse_args()
    p = op_cart.prepare(apply_overrides(load_params(), a.set, None, None))
    out = Path(a.outdir or HERE / "out" / "v010-cart")
    out.mkdir(parents=True, exist_ok=True)
    (out / "params.used.json").write_text(json.dumps(p["cart"], indent=1), encoding="utf-8")
    s, L = op_cart.build(p)
    ad = p["cart"]["adapter"]
    L["_lug_from_front"] = ad["lug_from_seat"] + ad["lug_t"] / 2
    created = {c["params"].get("body_name") for c in s.dumps() if c["params"].get("body_name")}
    asm = [b for b in op_cart.PART_NAMES if b in created]
    s.export_step(str(out / f"{TAG}_assembly.step"), asm)
    for part, bodies in op_cart.MFG_PARTS.items():
        s.export_step(str(out / f"{TAG}_{part}.step"), bodies)
        s.export_stl(str(out / f"{TAG}_{part}.stl"), bodies)
    script = out / f"{TAG}.script.json"
    script.write_text(json.dumps(s.dumps(), indent=1), encoding="utf-8")
    sc = out / f"{TAG}.sc"
    run_cli("run", str(script), "--save", str(sc), "--quiet")
    (out / f"{TAG}.mech.json").write_text(json.dumps(L, indent=1), encoding="utf-8")
    if not a.no_snapshots:
        shots(sc, out, L, created)
        import cart_compare
        cart_compare.draw(L, out / "size_comparison.svg")
        if shutil.which("rsvg-convert"):
            subprocess.run(["rsvg-convert", "-b", "white", "-o", str(out / "size_comparison.png"), str(out / "size_comparison.svg")], check=True)
    e = L["envelope"]
    print(f"{TAG}: body {L['length']:.2f} x {L['width']:.2f} x {L['height']:.2f} mm, with adapter {e['with_adapter_mm'][0]:.2f} mm, {e['bbox_volume_ml']} ml; "
          f"stroke {L['stroke']:.2f} (avail {L['stroke_avail']:.2f}), rod {L['rod_len']:.2f}, U/step {L['u_per_step']:.5f}, front set by {L['front_governed_by']} -> {out}")


if __name__ == "__main__":
    main()
