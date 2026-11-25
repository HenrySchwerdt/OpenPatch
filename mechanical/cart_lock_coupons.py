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
# Round 3 (owner's description + photo crops, 2026-11-25): the adapter cup has 2 OUTWARD hook lugs on its long axis, keyed (5.1 / 3.1 wide, ~0.5 radial,
# ~1.4 tall at the cup tip). Nominal: rim ID 10.7 from the face down to 3.1; 2 keyed windows (5.6 at +Z, 3.6 at -Z) where the lugs drop in with the
# adapter standing at 90 deg; 2 undercut pockets d11.7 from 3.1 to 4.9 deep that run 90 deg clockwise (seen from the face) to a stop face (lugs along
# the 52 face when flush); seal seat 14.6 x 0.5; recess 2.5 outside r 12; ball detent pockets 9.0 / +-4.5. First row (IDs 1-9) = quick first plate.
_R = "receiver"
_C = "cup"
MATRIX = [
    (1, "generous", "everything looser: windows +0.6, undercut 12.5 and 0.6 taller, rim 11.1, recess from r 11.6 and 0.4 deeper",
     {_R: {"lip_clr": 0.55, "bore_d": 12.5, "tab_axial_clr": 0.8, "tab_id": 11.1, "step_clr": 0.7, "recess_r": 11.6}}),
    (2, "nominal", "estimate (header)", {}),
    (3, "windows_+0.2", "windows 0.2 wider (5.8 / 3.8)", {_R: {"lip_clr": 0.35}}),
    (4, "windows_+0.4", "windows 0.4 wider (6.0 / 4.0)", {_R: {"lip_clr": 0.45}}),
    (5, "windows_+0.6", "windows 0.6 wider (6.2 / 4.2)", {_R: {"lip_clr": 0.55}}),
    (6, "windows_-10", "windows turned -10 deg", {_R: {"entry_deg": 80.0}}),
    (7, "windows_+10", "windows turned +10 deg", {_R: {"entry_deg": 100.0}}),
    (8, "undercut_d+0.4", "undercut diameter 12.1 (lug clearance +0.2)", {_R: {"bore_d": 12.1}}),
    (9, "undercut_h+0.3", "undercut 0.3 taller (rim underside 0.3 higher)", {_R: {"tab_axial_clr": 0.5}}),
    (10, "undercut_d+0.8", "undercut diameter 12.5", {_R: {"bore_d": 12.5}}),
    (11, "undercut_h+0.6", "undercut 0.6 taller", {_R: {"tab_axial_clr": 0.8}}),
    (12, "rim_10.5", "rim ID 10.5 (tighter around the cup)", {_R: {"tab_id": 10.5}}),
    (13, "rim_10.9", "rim ID 10.9", {_R: {"tab_id": 10.9}}),
    (14, "rim_11.1", "rim ID 11.1 (cup larger than estimated)", {_R: {"tab_id": 11.1, "bore_d": 12.1}}),
    (15, "stop_80", "end stop after 80 deg instead of 90", {_R: {"travel_deg": 80.0}}),
    (16, "stop_100", "end stop after 100 deg", {_R: {"travel_deg": 100.0}}),
    (17, "snap_bump", "small snap bump (0.25) just before the end stop", {_R: {"snap_bump": 0.25}}),
    (18, "keyed_mirror", "keying mirrored: narrow window at +Z, wide at -Z", {"adapter": {_C: {"lug_w": [3.1, 5.1]}}}),
    (19, "unkeyed_5.6", "both windows wide (5.6), in case the lugs are equal", {"adapter": {_C: {"lug_w": [5.1, 5.1]}}}),
    (20, "lugs_higher", "lugs 0.5 higher (cup proud 4.2): undercut 0.5 higher", {"adapter": {_C: {"proud": 4.2}}}),
    (21, "lugs_lower", "lugs 0.5 lower (cup proud 5.2): undercut 0.5 lower", {"adapter": {_C: {"proud": 5.2}}}),
    (22, "ball_along_-1", "ball pockets 1 closer along (8.0)", {_R: {"ball_y": 8.0}}),
    (23, "ball_along_+1", "ball pockets 1 further along (10.0)", {_R: {"ball_y": 10.0}}),
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
        "**How the original locks (round 3):** the adapter's cup carries **2 outward hook lugs** on the adapter's long axis, one ~5.1 and one ~3.1 wide "
        "(keyed, ~0.5 radial, ~1.4 tall, at the cup tip). The pump rim has **2 matching windows**: with the adapter standing at 90 deg (far half pointing "
        "away from the face, toward the display / label side) the lugs drop through them. Turning the adapter **90 deg clockwise** (seen from the face) down "
        "to flush moves the lugs under the rim in **2 undercut pockets**; each pocket ends in a **stop face** at the flush position. The rim then holds the "
        "adapter axially, the stop + the ball detent hold the angle.",
        "",
        "**Nominal (coupon 2), from photos and the owner's description** (+-0.5-1 mm): rim ID 10.7 from the face down to 3.1; windows 5.6 / 3.6 wide "
        "(lug + 2 x 0.25); undercut pockets d11.7 from 3.1 to 4.9 deep, 90 deg travel to the stop; seal seat d14.6 x 0.5; face recessed 2.5 outside r 12; "
        "2 pockets for a 2 mm steel ball at 9.0 along / +-4.5 across; 2 hook pockets at r 24 / +-7.",
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
        "(no: the cup hits the rim -> rim rows 12-14; the lugs hit -> windows width rows 3-5, angle rows 6-7, keying rows 18-19)",
        "2. **Turns 90 deg clockwise to the stop?** Smooth, stiff, blocked early (undercut too small / too high or low: rows 8-11, 20-21) or does it turn "
        "past flush (stop angle: rows 15-16)? Wrong way only = keying (rows 18-19).",
        "3. **Sits flush?** Locked, the adapter lies flat on the face and lines up with the outline (no gap at the far end, no rocking). "
        "Rocking at the far end -> recess depth / rim radius.",
        "4. **Holds?** Pull gently straight away from the face: it must not come off when locked. Comes off -> tabs too big or undercut too low.",
        "5. **Wobble?** Locked, wiggle it: a little play is fine, rattling is not.",
        "6. **Clicks?** With balls in the pockets (or coupon 17 with the snap bump): does it click into place at flush? (no click -> rows 17, 22-23)",
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
