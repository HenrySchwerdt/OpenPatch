#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Generate the v0.1.0 "cart" pump (op_cart.py): CAD, STEP/STL exports, renders and mech.json in out/v010-cart/. TEST PROJECT, water only.

  SOLIDCRAFT_CLI=/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli python3 cart_gen.py [--no-snapshots] [--set cart.cartridge.od=11.2]
  python3 cart_check.py          # interference, height, stroke, thrust, rod never wet
"""
from __future__ import annotations

import argparse
import json
import os
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
    "adapter": "opacity=0.8,color=#3a78c8", "b_cap": "opacity=0.85,color=#3a78c8", "needle": "color=#202020", "luer_hub": "color=#f0f0f0", "luer_set": "opacity=0.6,color=#c8e0f0", "adapter_lug_a": "color=#2a58a0", "adapter_lug_b": "color=#2a58a0", "tubing": "opacity=0.6,color=#e8f4ff",
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
           "tubing": (22, 0, 4), "lock_flag": (22, 0, 4), "lock_magnet": (22, 0, 4), "hall_lock": (0, 0, 6),
           "b_cap": (22, 0, 4), "needle": (30, 0, 4), "luer_hub": (34, 0, 4), "luer_set": (40, 0, 4)}


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


PRINT_BODIES = {
    # name: (bodies, orientation, note)   orientation: "asis" = already flat on z 0, "flip" = turned top-down, "up_x" = axis X stood upright, "up_y" = axis Y stood upright
    "print_bottom": (["bottom"], "asis", "tub, floor on the bed"),
    "print_lid": (["top"], "flip", "lid, outer face on the bed (smooth side), bosses up"),
    "print_slider": (["slider"], "up_x", "anti-rotation slider"),
    "print_pusher": (["pusher"], "up_x", "pusher disc, flat face down"),
    "print_lock_flag": (["lock_flag"], "asis", "clip-on flag for the adapter-lock magnet"),
    "print_b_cap": (["b_cap"], "up_x", "variant B needle cap (bayonet nose + needle guide + hub seat), print upright, nose down"),
    "print_button_tpu": (["button"], "up_y", "button cap, print in TPU 95A (or cast silicone)"),
    "dummy_cartridge": (["cartridge", "cart_cap"], "up_x", "cartridge stand-in (ESTIMATE geometry) until the real one arrives"),
    "dummy_board": (["ko_board", "ko_usb"], "asis", "main board + parts envelope with the USB-C receptacle block"),
    "dummy_cell": (["ko_battery"], "asis", "Ampul 301030 envelope"),
    "dummy_motor": (["motor", "gearhead", "motor_boss", "motor_rear_boss"], "up_x", "NFP-608 envelope (shaft not included: use a 2 mm pin)"),
    "dummy_gear": (["gear_rod"], "up_x", "z40 gear tip-circle disc with the nut hex pocket"),
    "dummy_pinion": (["pinion"], "up_x", "z12 pinion tip-circle disc"),
}


def to_origin(path: Path) -> list[float]:
    """Shift an STL so its bounding box starts at (0, 0, 0); rewrite as binary STL. Returns the size."""
    import re
    import struct
    d = path.read_bytes()
    tris = []
    if d[:5] == b"solid" and b"facet" in d[:400]:
        v = [tuple(map(float, m)) for m in re.findall(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", d)]
        tris = [v[i:i + 3] for i in range(0, len(v), 3)]
    else:
        n = struct.unpack("<I", d[80:84])[0]
        for i in range(n):
            o = 84 + i * 50 + 12
            tris.append([struct.unpack("<3f", d[o + 12 * k:o + 12 * k + 12]) for k in range(3)])
    lo = [min(p[i] for tr in tris for p in tr) for i in range(3)]
    hi = [max(p[i] for tr in tris for p in tr) for i in range(3)]
    out = bytearray(b"OpenPatch cart print kit, mm, origin-aligned".ljust(80, b" "))
    out += struct.pack("<I", len(tris))
    for tr in tris:
        q = [[p[i] - lo[i] for i in range(3)] for p in tr]
        a = [q[1][i] - q[0][i] for i in range(3)]
        b = [q[2][i] - q[0][i] for i in range(3)]
        nrm = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
        ln = sum(c * c for c in nrm) ** 0.5 or 1.0
        out += struct.pack("<3f", *[c / ln for c in nrm])
        for p in q:
            out += struct.pack("<3f", *p)
        out += b"\x00\x00"
    path.write_bytes(bytes(out))
    return [round(hi[i] - lo[i], 2) for i in range(3)]


def print_kit(sc: Path, outdir: Path, L: dict, created: set) -> list[dict]:
    """Each printable part / dummy as its own STL, laid flat for FDM (one script run on the saved design, not saved back)."""
    outdir.mkdir(parents=True, exist_ok=True)
    s = Script()
    s.add("parameters.add", name="p_dummy_print", expression="0", comment="print orientation")
    rows = []
    for nm, (bodies, ori, note) in PRINT_BODIES.items():
        bs = [b for b in bodies if b in created]
        if not bs:
            continue
        if ori == "flip":
            s.add("solid.move", bodies=bs, axis=[1, 0, 0], angle="180 deg", origin=[0, L["width"] / 2, L["height"] / 2])
        elif ori == "up_x":
            s.add("solid.move", bodies=bs, axis=[0, 1, 0], angle="-90 deg", origin=[0, 0, 0])
        elif ori == "up_y":
            s.add("solid.move", bodies=bs, axis=[1, 0, 0], angle="-90 deg", origin=[0, 0, 0])      # outer (+Y) face down
        s.add("file.export_stl", path=os.path.relpath(outdir / f"{nm}.stl", HERE), bodies=bs, quality="standard")
        rows.append({"file": f"{nm}.stl", "bodies": bs, "orientation": ori, "note": note})
    pj = outdir / "print.script.json"
    pj.write_text(json.dumps(s.dumps()), encoding="utf-8")
    run_cli("run", str(pj), "--in", str(sc), "--quiet")
    pj.unlink()
    for r in rows:
        r["size_mm"] = to_origin(outdir / r["file"])
    (outdir / "print_kit.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return rows


def coupons(p0: dict, outdir: Path) -> list[str]:
    """Quick fit coupons (minutes to print): cartridge bore ladder and receiver variants (bayonet socket at 3 bores), both with the bore axis vertical."""
    outdir.mkdir(parents=True, exist_ok=True)
    p = op_cart.prepare(p0, "A")
    c = p["cart"]
    s = Script()
    s.add("parameters.add", name="p_coupon", expression="0", comment="fit coupons")
    ds = c["coupons"]["cradle_bores"]
    pitch = max(ds) + 3.0
    s.box("coupon_cradle", (0, pitch * len(ds)), (0, pitch), (0, c["coupons"]["cradle_h"]))
    tools = []
    for k, d in enumerate(ds):
        tools.append(s.cyl(f"t_cc{k}", "Z", (pitch * (k + 0.5), pitch / 2, 0), d, -0.1, 10))
        for j in range(k + 1):                                      # notch count = hole index (1 = smallest)
            tools.append(s.box(f"t_cn{k}_{j}", (pitch * k + 1.0 + 1.2 * j, pitch * k + 1.6 + 1.2 * j), (-0.1, 0.8), (-0.1, 10)))
    s.cut("coupon_cradle", tools)
    s.add("file.export_stl", path=os.path.relpath(outdir / "coupon_cartridge_bore_ladder.stl", HERE), bodies=["coupon_cradle"], quality="standard")
    names = ["coupon_cartridge_bore_ladder.stl"]
    for k, bd in enumerate(c["coupons"]["receiver_bores_A"]):        # variant A: a 6.5 mm slice of the real front end (adapter bed + connector port + bayonet)
        pk = op_cart.prepare(apply_overrides(p0, [f"cart.variants.A.receiver.bore_d={bd}"], None, None), "A")
        Lk = op_cart.geometry(pk)
        nm = f"coupon_front{k}"
        x1 = Lk["length"]
        x0 = x1 - pk["cart"]["receiver"]["collar_len"]
        s.box(nm, (x0, x1), (0, Lk["width"]), (0, Lk["height"]))
        s.cut(nm, op_cart._receiver_cuts(s, pk, Lk, f"f{k}"))
        s.cut(nm, [s.box(f"t_fk{k}_{j}", (x0 - 0.1, x1 + 0.1), (Lk["width"] - 1.6 - 1.2 * j, Lk["width"] - 1.0 - 1.2 * j), (-0.1, 0.7)) for j in range(k + 1)])
        s.add("solid.move", bodies=[nm], axis=[0, 1, 0], angle="-90 deg", origin=[x1, 0, 0])
        s.add("file.export_stl", path=os.path.relpath(outdir / f"coupon_A_front_bore_{bd:.1f}.stl", HERE), bodies=[nm], quality="standard")
        names.append(f"coupon_A_front_bore_{bd:.1f}.stl")
    for k, bd in enumerate(c["coupons"]["receiver_bores"]):          # variant B: round socket only (the B cap has no bed)
        pk = op_cart.prepare(apply_overrides(p0, [f"cart.receiver.bore_d={bd}"], None, None), "B")
        rl = pk["cart"]["receiver"]
        r_g = bd / 2 + pk["cart"]["adapter"]["lug_h"] + rl["lug_clr"]
        half = r_g + 2.0
        Lc = {"y_c": half, "zc": half, "x_front": rl["collar_len"], "x_seat": rl["collar_len"], "collar": [0.0, rl["collar_len"]], "r_groove": r_g}
        nm = f"coupon_rcvb{k}"
        s.box(nm, (0, rl["collar_len"]), (0, 2 * half), (0, 2 * half))
        s.cut(nm, op_cart._receiver_cuts(s, pk, Lc, f"c{k}"))
        s.cut(nm, [s.box(f"t_rk{k}_{j}", (-0.1, rl["collar_len"] + 0.1), (0.8 + 1.2 * j, 1.4 + 1.2 * j), (-0.1, 0.7)) for j in range(k + 1)])
        s.add("solid.move", bodies=[nm], axis=[0, 1, 0], angle="-90 deg", origin=[0, 0, 0])
        s.add("file.export_stl", path=os.path.relpath(outdir / f"coupon_B_receiver_bore_{bd:.1f}.stl", HERE), bodies=[nm], quality="standard")
        names.append(f"coupon_B_receiver_bore_{bd:.1f}.stl")
    pj = outdir / "coupons.script.json"
    pj.write_text(json.dumps(s.dumps()), encoding="utf-8")
    run_cli("run", str(pj), "--quiet")
    pj.unlink()
    for n in names:
        to_origin(outdir / n)
    return names


def p_adapter_lug_x(L: dict) -> float:
    return L["_lug_from_front"]


def generate(p0: dict, variant: str, outroot: Path, snapshots: bool) -> dict:
    global TAG
    TAG = f"OP-CART-{variant}"
    p = op_cart.prepare(p0, variant)
    out = outroot / variant
    out.mkdir(parents=True, exist_ok=True)
    (out / "params.used.json").write_text(json.dumps(p["cart"], indent=1), encoding="utf-8")
    s, L = op_cart.build(p)
    ad = p["cart"]["adapter"]
    L["_lug_from_front"] = ad["lug_from_seat"] + ad["lug_t"] / 2
    L["variant"] = variant
    created = {c["params"].get("body_name") for c in s.dumps() if c["params"].get("body_name")}
    asm = [b for b in op_cart.part_names(p) if b in created]
    s.export_step(str(out / f"{TAG}_assembly.step"), asm)
    for part, bodies in op_cart.mfg_parts(p).items():
        bs = [b for b in bodies if b in created]
        if bs:
            s.export_step(str(out / f"{TAG}_{part}.step"), bs)          # STEP per part; the printable STLs are in print/ (laid flat)
    script = out / f"{TAG}.script.json"
    script.write_text(json.dumps(s.dumps(), indent=1), encoding="utf-8")
    sc = out / f"{TAG}.sc"
    run_cli("run", str(script), "--save", str(sc), "--quiet")
    (out / f"{TAG}.mech.json").write_text(json.dumps(L, indent=1), encoding="utf-8")
    print_kit(sc, out / "print", L, created)
    if snapshots:
        shots(sc, out, L, created)
    e = L["envelope"]
    print(f"{TAG}: body {L['length']:.2f} x {L['width']:.2f} x {L['height']:.2f} mm, with adapter {e['with_adapter_mm'][0]:.2f} mm, {e['bbox_volume_ml']} ml; "
          f"stroke {L['stroke']:.2f} (avail {L['stroke_avail']:.2f}), rod {L['rod_len']:.2f}, U/step {L['u_per_step']:.5f}, front set by {L['front_governed_by']} -> {out}")
    return L


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir")
    ap.add_argument("--variant", action="append", choices=["A", "B"], help="A = original Insight adapter & tubing, B = alternative adapter (default: both)")
    ap.add_argument("--no-snapshots", action="store_true")
    ap.add_argument("--set", action="append", default=[], help="override, e.g. cart.cartridge.od=11.2")
    a = ap.parse_args()
    p0 = apply_overrides(load_params(), a.set, None, None)
    outroot = Path(a.outdir or HERE / "out" / "v010-cart")
    Ls = {v: generate(p0, v, outroot, not a.no_snapshots) for v in (a.variant or ["A", "B"])}
    print("coupons:", ", ".join(coupons(p0, outroot / "coupons")))
    if not a.no_snapshots:
        import cart_compare
        cart_compare.draw(Ls, outroot / "size_comparison.svg")
        if shutil.which("rsvg-convert"):
            subprocess.run(["rsvg-convert", "-b", "white", "-o", str(outroot / "size_comparison.png"), str(outroot / "size_comparison.svg")], check=True)


if __name__ == "__main__":
    main()
