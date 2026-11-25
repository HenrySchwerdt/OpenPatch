#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Variant A twist-lock fit coupons: 10 mm slices of the real A front end (52 x 19 face, connector bore, lug entry notches, lug groove,
key-step pocket) with ONE uncertain dimension changed per coupon, to find which receiver fits the real Accu-Chek Insight Adapter & Tubing.
TEST PROJECT: bench only, water only, never worn.

  SOLIDCRAFT_CLI=... python3 cart_lock_coupons.py
Writes out/v010-cart/coupons/A_lock/: A_lock_<ID>.stl (face up, flat base, at the origin), A_lock_bed.stl (all coupons on a 280 x 240 bed), A_lock_bed_first.stl (IDs 1-9),
README.md (ID -> what changed, how to test). ID = number of notches on the base rim (+Y long edge), 1..N.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import op_cart
from cart_gen import to_origin
from generate import run_cli
from op_cmds import Script
from op_layout import HERE, load_params

DEPTH = 8.0             # slice depth (mm) behind the seat plane (small, fast coupons)
FACE_KEEP = 6.0         # solid material behind the face; deeper than the undercut (<= 5.4) and the recess + hook pockets (<= 4.3)
SKIRT_WALL = 1.6        # base skirt wall and the ring around the cartridge hole (lightening, print time)
RING_OD = 15.0
GAP = 6.0               # spacing on the bed
BED = (280.0, 240.0)

# (ID, short name, what changed, overrides on cart.variants.A: {section: {key: value}}, nested dicts merged)
# Nominal = photo estimate (no measuring tools; scaled from the 52 x 19 end face, the 19 adapter width, the 10.95 cartridge; 7 pump + 3 adapter photos):
# seal seat 14.6 x 0.5, 2 windows at +-Y for 80 deg lips, tabs 11.3, undercut 12.5 from 3.9 to 4.9, recess 2.5 outside r 12, ball pockets 9.0 / +-4.5.
# The first row (IDs 1-9) is the quick first plate; the rest widen the search.
_R = "receiver"
MATRIX = [
    (1, "generous", "all clearances +0.4: tabs 11.7, undercut 12.9, windows +0.8 wide, tab-to-lip gap 0.6, recess from r 11.6 and 0.4 deeper",
     {_R: {"tab_id": 11.7, "bore_d": 12.9, "lip_clr": 0.65, "tab_axial_clr": 0.6, "step_clr": 0.7, "recess_r": 11.6}}),
    (2, "nominal", "photo estimate (header)", {}),
    (3, "tabs_-0.4", "tabs 10.9", {_R: {"tab_id": 10.9}}),
    (4, "tabs_+0.4", "tabs 11.7", {_R: {"tab_id": 11.7}}),
    (5, "undercut_-0.4", "undercut 12.1", {_R: {"bore_d": 12.1}}),
    (6, "undercut_+0.4", "undercut 12.9", {_R: {"bore_d": 12.9}}),
    (7, "windows_-10", "windows turned -10 deg", {_R: {"entry_deg": -10.0, "lock_deg": 80.0}}),
    (8, "windows_+10", "windows turned +10 deg", {_R: {"entry_deg": 10.0, "lock_deg": 100.0}}),
    (9, "windows_+0.5", "windows 0.5 wider", {_R: {"lip_clr": 0.5}}),
    (10, "tabs_-0.8", "tabs 10.5", {_R: {"tab_id": 10.5}}),
    (11, "tabs_+0.8", "tabs 12.1", {_R: {"tab_id": 12.1}}),
    (12, "undercut_-0.8", "undercut 11.7", {_R: {"bore_d": 11.7}}),
    (13, "undercut_+0.8", "undercut 13.3", {_R: {"bore_d": 13.3}}),
    (14, "undercut_high", "undercut 0.5 higher (cup proud 4.2)", {"adapter": {"cup": {"proud": 4.2}}}),
    (15, "undercut_low", "undercut 0.5 lower (cup proud 5.2)", {"adapter": {"cup": {"proud": 5.2}}}),
    (16, "windows_-20", "windows turned -20 deg", {_R: {"entry_deg": -20.0, "lock_deg": 70.0}}),
    (17, "windows_+20", "windows turned +20 deg", {_R: {"entry_deg": 20.0, "lock_deg": 110.0}}),
    (18, "windows_keyed", "one wide (110 deg, toward the far half) and one narrow (50 deg) window", {"adapter": {"cup": {"lip_arc_deg": [110.0, 50.0]}}}),
    (19, "ball_along_-1", "ball pockets 1 closer along (8.0)", {_R: {"ball_y": 8.0}}),
    (20, "ball_along_+1", "ball pockets 1 further along (10.0)", {_R: {"ball_y": 10.0}}),
    (21, "ball_across_-1", "ball pockets 1 closer to the axis (3.5 across)", {_R: {"ball_off": 3.5}}),
    (22, "ball_across_+1", "ball pockets 1 further across (5.5)", {_R: {"ball_off": 5.5}}),
    (23, "rim_r11", "high zone smaller: recess from r 11", {_R: {"recess_r": 11.0}}),
    (24, "rim_r13", "high zone larger: recess from r 13", {_R: {"recess_r": 13.0}}),
    (25, "recess_deep", "recess 0.8 deeper (far half 3.3 proud)", {"adapter": {"step_h": 3.3}}),
]


def _merge(d: dict, over: dict) -> None:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            _merge(d[k], v)
        else:
            d[k] = v


def variant_params(p0: dict, over: dict) -> dict:
    p1 = copy.deepcopy(p0)
    va = p1["cart"]["variants"]["A"]
    _merge(va, over)
    return op_cart.prepare(p1, "A")


def coupon_geometry(p_nom: dict, p: dict) -> dict:
    """Block geometry of the NOMINAL design (the 52 x 19 face stays as built), groove radius from the variant's receiver."""
    L = dict(op_cart.geometry(p_nom))
    rc, ad = p["cart"]["receiver"], p["cart"]["adapter"]
    L["r_groove"] = rc["bore_d"] / 2 if rc.get("type") == "cup_bayonet" else rc["bore_d"] / 2 + ad["lug_h"] + rc["lug_clr"]
    return L


def build_coupon(s: Script, p_nom: dict, p: dict, n: int) -> str:
    """Front-end slice x in [seat - DEPTH, seat] of the A block, face (+X) turned up; the base skirt is hollow except a ring around the cartridge hole."""
    L = coupon_geometry(p_nom, p)
    c = p["cart"]
    W, H, xs, yc, zc = L["width"], L["height"], L["x_seat"], L["y_c"], L["zc"]
    x0 = xs - DEPTH
    nm = f"lock{n}"
    s.box(nm, (x0, xs), (0, W), (0, H))
    s.cut(nm, [s.box(f"t_lt{n}", (x0 - 0.1, xs - FACE_KEEP), (SKIRT_WALL, W - SKIRT_WALL), (SKIRT_WALL, H - SKIRT_WALL))])
    s.join(nm, [s.cyl(f"t_ring{n}", "X", (0, yc, zc), RING_OD, x0, xs - FACE_KEEP + 0.01)])
    cart_hole = s.cyl(f"t_ch{n}", "X", (0, yc, zc), c["cartridge"]["od"] + 2 * c["cradle_clr"], x0 - 0.1, xs - 5.0)
    ids = [s.box(f"t_id{n}_{j}", (x0 - 0.1, x0 + 1.0), (W - 2.0 - 1.6 * j, W - 1.2 - 1.6 * j), (-0.1, 1.2)) for j in range(n)]
    s.cut(nm, op_cart._receiver_cuts(s, p, L, f"k{n}") + [cart_hole] + ids)
    s.add("solid.move", bodies=[nm], axis=[0, 1, 0], angle="-90 deg", origin=[xs, 0, 0])   # face up: z' = x - seat in [-DEPTH, 0]
    return nm


def readme(rows: list[tuple], sizes: dict) -> str:
    return "\n".join([
        "> **TEST ONLY - NOT FOR HUMAN USE.** Bench only, **water only**. These coupons only check how the original Insight Adapter & Tubing fits our printed receiver.",
        "",
        "# Variant A twist-lock fit coupons (`cart_lock_coupons.py`)",
        "",
        f"Each coupon is a {DEPTH:.0f} mm slice of the real variant A front end (52 x 19 face), face up. Exactly **one** dimension changes per coupon. "
        "**ID = number of notches on the base rim.**",
        "",
        "**Nominal (coupon 2), all from photos** (no measuring tools; scaled from the pump end face 52 x 19 VERIFIED, the 19 adapter width and the ISO cartridge "
        "10.95 / cap 7.8, cross-checked between 7 photos of the original pump and 3 of the adapter, +-0.5-1 mm): seal seat d14.6 x 0.5 for the white ring; "
        "2 bore windows at +-Y (along the end face) for the cup's 2 rim lips (~80 deg each); 2 retaining tabs between them, ID 11.3 (the cartridge passes); "
        "undercut d12.5 from 3.9 to 4.9 below the face; face recessed 2.5 outside r 12 (the original's curved rim; the adapter's raised far half lies there); "
        "2 pockets for a 2 mm steel ball detent at 9.0 along / +-4.5 across; 2 hook pockets at r 24 / +-7. The adapter pivots on the bore and swings down over the "
        "battery side; the tubing leaves its far end.",
        "",
        "| ID | File | What changed (vs nominal) |",
        "|---|---|---|",
        *[f"| {n} | `A_lock_{n:02d}_{short}.stl` | {what} |" for n, short, what, _ in rows],
        "",
        f"`A_lock_bed.stl`: all {len(rows)} coupons ({sizes['bed'][0]:.0f} x {sizes['bed'][1]:.0f} mm, fits {BED[0]:.0f} x {BED[1]:.0f}). "
        f"`A_lock_bed_first.stl`: IDs 1-9 only (quick first plate). Coupon {sizes['one'][0]:.0f} x {sizes['one'][1]:.0f} x {sizes['one'][2]:.0f} mm.",
        "",
        "**Print:** PETG or PLA, 0.4 nozzle, 0.15-0.2 layer, 3 perimeters, 15 % infill, as exported (face up), no supports, no brim. "
        "Optional: press a 2 mm steel ball into each round pocket on the face (0.5 stands out) to feel the detent click.",
        "",
        "## How to judge the fit (per coupon, note the ID)",
        "",
        "1. **Goes in at 90 deg?** Adapter sticking out across the face, cup straight down into the bore: does it drop in to the white ring without force? "
        "(no: tabs too tight -> try a higher tabs value; lips hit -> windows angle / width)",
        "2. **Turns 90 deg?** Turn it down toward the long side until flush: smooth, stiff or blocked? Blocked early -> undercut too small or too high/low.",
        "3. **Sits flush?** Locked, the adapter lies flat on the face and lines up with the outline (no gap at the far end, no rocking). "
        "Rocking at the far end -> recess depth / rim radius.",
        "4. **Holds?** Pull gently straight away from the face: it must not come off when locked. Comes off -> tabs too big or undercut too low.",
        "5. **Wobble?** Locked, wiggle it: a little play is fine, rattling is not.",
        "6. **Clicks?** With balls in the pockets: does it click into place at flush? (no click -> ball position rows 19-22)",
        "",
        "Report: the best ID and, for it, yes / no for 1-6. If two coupons are both good, report both.",
    ]) + "\n"


def main() -> None:
    p0 = load_params()
    out = HERE / "out" / "v010-cart" / "coupons" / "A_lock"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.stl"):
        old.unlink()
    s = Script()
    s.add("parameters.add", name="p_lock_coupons", expression="0", comment="A twist-lock coupons")
    names, bodies = [], []
    cols = 9
    p_nom = op_cart.prepare(p0, "A")
    for k, (n, short, _, over) in enumerate(MATRIX):
        p = variant_params(p0, over)
        nm = build_coupon(s, p_nom, p, n)
        f = f"A_lock_{n:02d}_{short}.stl"
        s.add("file.export_stl", path=os.path.relpath(out / f, HERE), bodies=[nm], quality="standard")
        L = op_cart.geometry(p_nom)
        col, row = k % cols, k // cols
        dx = -(L["x_seat"] - L["height"]) + col * (L["height"] + GAP)                     # x' starts at seat - H after the turn
        dy = row * (L["width"] + GAP)
        s.add("solid.move", bodies=[nm], translate=[dx, dy, DEPTH])
        names.append(f)
        bodies.append(nm)
    s.add("file.export_stl", path=os.path.relpath(out / "A_lock_bed.stl", HERE), bodies=bodies, quality="standard")
    s.add("file.export_stl", path=os.path.relpath(out / "A_lock_bed_first.stl", HERE), bodies=bodies[:cols], quality="standard")
    pj = out / "lock.script.json"
    pj.write_text(json.dumps(s.dumps()), encoding="utf-8")
    run_cli("run", str(pj), "--quiet")
    pj.unlink()
    one = to_origin(out / names[0])
    for f in names[1:]:
        to_origin(out / f)
    bed = to_origin(out / "A_lock_bed.stl")
    to_origin(out / "A_lock_bed_first.stl")
    if bed[0] > BED[0] or bed[1] > BED[1]:
        raise SystemExit(f"bed layout {bed} exceeds {BED}")
    (out / "README.md").write_text(readme(MATRIX, {"one": one, "bed": bed}), encoding="utf-8")
    print(f"{len(names)} coupons {one[0]:.1f} x {one[1]:.1f} x {one[2]:.1f}, bed {bed[0]:.1f} x {bed[1]:.1f} -> {out}")


if __name__ == "__main__":
    main()
