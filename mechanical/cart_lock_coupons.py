#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Variant A twist-lock fit coupons: 10 mm slices of the real A front end (52 x 19 face, connector bore, lug entry notches, lug groove,
key-step pocket) with ONE uncertain dimension changed per coupon, to find which receiver fits the real Accu-Chek Insight Adapter & Tubing.
TEST PROJECT: bench only, water only, never worn.

  SOLIDCRAFT_CLI=... python3 cart_lock_coupons.py
Writes out/v010-cart/coupons/A_lock/: A_lock_<ID>.stl (face up, flat base, at the origin), A_lock_bed.stl (all coupons on a 280 x 240 bed),
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

DEPTH = 10.0            # slice depth (mm) behind the seat plane
FACE_KEEP = 6.2         # solid material behind the face; deeper than the bore (5.5), groove (3.65) and key pocket (3.1)
SKIRT_WALL = 1.6        # base skirt wall and the ring around the cartridge hole (lightening, print time)
RING_OD = 15.0
GAP = 6.0               # spacing on the bed
BED = (280.0, 240.0)

# (ID, short name, what changed, overrides on cart.variants.A: {section: {key: value}}, nested dicts merged)
# Centre values = ESTIMATE from the owner's photos of the ORIGINAL Insight pump end face + his adapter (2026-11-25): seal seat 14.6 x 0.5,
# 2 bore windows at +-Y (along the end face) for 80 deg lips, retaining tabs 11.3 (the cartridge passes), lip ring 12.5 down to 4.9,
# face recessed 2.5 outside r 12 (the pump's curved rim), detent ball pockets (2 mm ball) at 8.5 along / +-5.5 across, hook pockets at r 24 / +-7.
MATRIX = [
    (1, "generous", "all clearances +0.4: tabs 11.7, lip ring 12.9, windows +0.4, tab-to-lip gap 0.6, recess from r 11.6 and 0.4 deeper",
     {"receiver": {"tab_id": 11.7, "bore_d": 12.9, "lip_clr": 0.65, "tab_axial_clr": 0.6, "step_clr": 0.7, "recess_r": 11.6}}),
    (2, "nominal", "estimate from the original pump + adapter photos (values in the header of this README)", {}),
    (3, "tabs_11.0", "retaining tabs 11.0 (tight; the cartridge 10.95 just passes)", {"receiver": {"tab_id": 11.0}}),
    (4, "tabs_11.6", "retaining tabs 11.6 (loose)", {"receiver": {"tab_id": 11.6}}),
    (5, "lipring_12.0", "undercut (lip ring) 12.0 instead of 12.5", {"receiver": {"bore_d": 12.0}}),
    (6, "lipring_13.0", "undercut (lip ring) 13.0", {"receiver": {"bore_d": 13.0}}),
    (7, "undercut_high", "cup 0.5 shorter: tabs end and undercut 0.5 higher (cup proud 4.2)", {"adapter": {"cup": {"proud": 4.2}}}),
    (8, "undercut_low", "cup 0.5 longer: tabs end and undercut 0.5 lower (cup proud 5.2)", {"adapter": {"cup": {"proud": 5.2}}}),
    (9, "windows_+20", "windows turned +20 deg", {"receiver": {"entry_deg": 20.0, "lock_deg": 110.0}}),
    (10, "windows_-20", "windows turned -20 deg", {"receiver": {"entry_deg": -20.0, "lock_deg": 70.0}}),
    (11, "windows_keyed", "asymmetric windows (patent / photo: one wide, one narrow): 110 deg toward +Y (far half), 50 deg toward -Y", {"adapter": {"cup": {"lip_arc_deg": [110.0, 50.0]}}}),
    (12, "ball_far", "detent ball pockets 1.5 further out (10.0 along)", {"receiver": {"ball_y": 10.0}}),
    (13, "ball_near", "detent ball pockets 1.5 closer (7.0 along) and 4.5 across", {"receiver": {"ball_y": 7.0, "ball_off": 4.5}}),
    (14, "rim_r13", "high zone around the socket larger: recess from r 13.0", {"receiver": {"recess_r": 13.0}}),
    (15, "recess_deep", "recess 0.8 deeper (far half 3.3 proud)", {"adapter": {"step_h": 3.3}}),
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
        "# Variant A twist-lock fit coupons (`cart_lock_coupons.py`), built on the ORIGINAL pump's end face (2026-11-25)",
        "",
        f"Each coupon is a {DEPTH:.0f} mm slice of the real variant A front end (52 x 19 face). Exactly **one** dimension changes per coupon. "
        "**ID = number of notches on the base rim.** Nominal (coupon 2), all ESTIMATE from the owner's photos of the original pump end face and of his adapter, "
        "scaled with the 19 mm end-face width (+-0.5-1 mm):",
        "",
        "- seal seat (shallow counterbore) d14.6 x 0.5 for the adapter's white ring (OD ~13.5);",
        "- bore wall with **2 windows** at +-Y (along the end face), each for an ~80 deg cup lip, and **2 retaining tabs** between them, ID 11.3 "
        "(the cartridge, 10.95, passes, as on the original);",
        "- **undercut** (lip ring) d12.5 under the tabs, from 3.9 to 4.9 below the face (adapter cup ~4.7 proud, lip ~0.6 high);",
        "- the face is **recessed 2.5 outside r 12** around the socket (the original's curved rim; the adapter's raised far half lies there);",
        "- **detent**: 2 pockets for a 2 mm steel ball (press in, 0.5 proud) at 8.5 along +Y and +-5.5 across (the original has one polished ball there; "
        "the adapter has 2 holes ~11 from its cup at +-5). Print without balls first; add a ball (e.g. 2 mm bearing ball) to feel the click;",
        "- hook pockets 3 x 2.3, 1 deep in the recess floor at r 24, +-7 across (for the adapter's curved hook; what it catches on the original is not "
        "clear from the photos).",
        "",
        "| ID | File | What changed (vs nominal) |",
        "|---|---|---|",
        *[f"| {n} | `A_lock_{n:02d}_{short}.stl` | {what} |" for n, short, what, _ in rows],
        "",
        f"`A_lock_bed.stl`: all {len(rows)} coupons on one {BED[0]:.0f} x {BED[1]:.0f} bed ({sizes['bed'][0]:.0f} x {sizes['bed'][1]:.0f} mm used). Coupon {sizes['one'][0]:.0f} x {sizes['one'][1]:.0f} x {sizes['one'][2]:.0f} mm.",
        "",
        "**Print:** PETG or PLA, 0.4 nozzle, 0.15 layer, 3 perimeters, 15 % infill, face up (as exported), no supports (the tabs overhang the undercut by ~0.6 and bridge). Brim off.",
        "",
        "**Test:** put the adapter on at 90 deg (sticking out across the face), push the cup in, turn 90 deg down to flush. Note: enters (y/n), turns (y/n/force), "
        "axial play when flush, flush with the outline (y/n), clicks (with ball). Start with 1 (generous) and 2 (nominal), then the rows for what misfits.",
        "",
        "## Measure on the ORIGINAL pump end face (calipers; adapter off)",
        "",
        "1. **Bore at the face** (smallest diameter through the tabs) and **seal seat** diameter + depth (the shallow step around the bore).",
        "2. **Undercut**: largest diameter under the tabs (inside calipers or a feeler) and its depth: face to the underside of the tabs, face to the undercut floor.",
        "3. **Windows**: width of each window (chord at the bore) and the angle of each window centre against the pump's long side (photo straight on is enough). Are they equal?",
        "4. **Cartridge seat**: depth from the face to the inner ledge / cartridge cap.",
        "5. **Detent ball**: distance from the bore centre along the end face and across, ball diameter, how far it stands out, does it spring?",
        "6. **Curved rim**: radius from the bore centre to the curved step around the battery side, and the step height down to the battery-side face.",
        "7. **Bore centre** to the near end of the face and to both long sides.",
        "8. **Battery side**: where the adapter's hook catches when flush (which edge), its distance from the bore centre.",
        "9. On the **adapter**: lip OD over the lips (2 directions), lip height, lip arcs; cup OD; cup protrusion.",
        "10. On the **adapter**: the 2 underside holes (distance from the cup centre, spacing, diameter) and the height of the raised far half.",
        "",
        "**Photo wanted:** one straight top-down photo of the pump end face (adapter off) with a ruler in mm lying on the face plane, camera square to the face, "
        "and the same for the adapter underside.",
        "",
        "The earlier models (lug groove from the patents; cup socket from the adapter photo alone) are replaced.",
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
    cols = 5
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
    pj = out / "lock.script.json"
    pj.write_text(json.dumps(s.dumps()), encoding="utf-8")
    run_cli("run", str(pj), "--quiet")
    pj.unlink()
    one = to_origin(out / names[0])
    for f in names[1:]:
        to_origin(out / f)
    bed = to_origin(out / "A_lock_bed.stl")
    if bed[0] > BED[0] or bed[1] > BED[1]:
        raise SystemExit(f"bed layout {bed} exceeds {BED}")
    (out / "README.md").write_text(readme(MATRIX, {"one": one, "bed": bed}), encoding="utf-8")
    print(f"{len(names)} coupons {one[0]:.1f} x {one[1]:.1f} x {one[2]:.1f}, bed {bed[0]:.1f} x {bed[1]:.1f} -> {out}")


if __name__ == "__main__":
    main()
