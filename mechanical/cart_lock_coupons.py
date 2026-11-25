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

# (ID, short name, what changed, overrides on cart.variants.A: {section: {key: value}})
MATRIX = [
    (1, "generous", "all clearances +0.4: bore 13.7, lug notch / groove clearance 0.65, key pocket clearance 0.7", {"receiver": {"bore_d": 13.7, "lug_clr": 0.65}, "adapter": {"bed_clr": 0.7}}),
    (2, "nominal", "current CAD (bore 13.3, lug notches 1.6 + 2 x 0.25 at 90 deg, groove r 7.7, pocket clearance 0.3)", {}),
    (3, "bore_12.9", "nose bore 12.9 (-0.4)", {"receiver": {"bore_d": 12.9}}),
    (4, "bore_13.7", "nose bore 13.7 (+0.4)", {"receiver": {"bore_d": 13.7}}),
    (5, "entry_-10", "lug entry notches rotated -10 deg (80 deg instead of 90)", {"receiver": {"entry_deg": 80.0}}),
    (6, "entry_+10", "lug entry notches rotated +10 deg (100 deg instead of 90)", {"receiver": {"entry_deg": 100.0}}),
    (7, "notch_w+0.4", "lug entry notches 0.4 wider (lug 2.0)", {"receiver": {"entry_w": [2.0, 2.0]}}),
    (8, "keyed_5_1.5", "keyed lugs as in the design patent: one notch for a ~5 wide lug, the opposite one for a ~1.5 wide lug", {"receiver": {"entry_w": [5.0, 1.5]}}),
    (9, "groove_deep", "lug groove 0.4 deeper radially (lugs 1.2 high instead of 0.8) and notches to match", {"adapter": {"lug_h": 1.2}}),
    (10, "cbore_15.9", "counterbore d15.9 x 1.5 at the face (for a ~15.5 flange at the nose base, D720,449 / IFU)", {"receiver": {"cbore_d": 15.9, "cbore_depth": 1.5}}),
    (11, "pocket_+0.4", "key-step pocket 0.4 larger on every side (clearance 0.7) and 0.4 deeper", {"adapter": {"bed_clr": 0.7}}),
]


def variant_params(p0: dict, over: dict) -> dict:
    p1 = copy.deepcopy(p0)
    va = p1["cart"]["variants"]["A"]
    for sec, kv in over.items():
        va.setdefault(sec, {}).update(kv)
    return op_cart.prepare(p1, "A")


def coupon_geometry(p_nom: dict, p: dict) -> dict:
    """Block geometry of the NOMINAL design (the 52 x 19 face stays as built), groove radius from the variant's receiver."""
    L = dict(op_cart.geometry(p_nom))
    rc, ad = p["cart"]["receiver"], p["cart"]["adapter"]
    L["r_groove"] = rc["bore_d"] / 2 + ad["lug_h"] + rc["lug_clr"]
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
    cart_hole = s.cyl(f"t_ch{n}", "X", (0, yc, zc), c["cartridge"]["od"] + 2 * c["cradle_clr"], x0 - 0.1, xs - c["adapter"]["depth"] + 0.01)
    ids = [s.box(f"t_id{n}_{j}", (x0 - 0.1, x0 + 1.0), (W - 2.0 - 1.6 * j, W - 1.2 - 1.6 * j), (-0.1, 1.2)) for j in range(n)]
    s.cut(nm, op_cart._receiver_cuts(s, p, L, f"k{n}") + [cart_hole] + ids)
    s.add("solid.move", bodies=[nm], axis=[0, 1, 0], angle="-90 deg", origin=[xs, 0, 0])   # face up: z' = x - seat in [-DEPTH, 0]
    return nm


def readme(rows: list[tuple], sizes: dict) -> str:
    lines = [
        "> **TEST ONLY - NOT FOR HUMAN USE.** Bench only, **water only**. These coupons only check how the original Insight Adapter & Tubing fits our printed receiver.",
        "",
        "# Variant A twist-lock fit coupons (`cart_lock_coupons.py`)",
        "",
        f"Each coupon is a {DEPTH:.0f} mm slice of the real variant A front end: the full 52 x 19 face with the connector bore, the two lug entry notches, the lug groove (bayonet undercut) and the key-step pocket. "
        "Exactly **one** uncertain dimension is changed per coupon (all ESTIMATE from unscaled patent drawings and manual figures, `../../../../docs/insight-research.md` §7.6). "
        "**ID = number of notches on the base rim** (long edge on the tubing side).",
        "",
        "| ID | File | What changed (vs nominal) |",
        "|---|---|---|",
    ]
    for n, short, what, _ in rows:
        lines.append(f"| {n} | `A_lock_{n:02d}_{short}.stl` | {what} |")
    lines += [
        "",
        f"`A_lock_bed.stl`: all {len(rows)} coupons on one {BED[0]:.0f} x {BED[1]:.0f} bed (bed size {sizes['bed'][0]:.0f} x {sizes['bed'][1]:.0f} mm used). Coupon {sizes['one'][0]:.0f} x {sizes['one'][1]:.0f} x {sizes['one'][2]:.0f} mm.",
        "",
        "**Print:** PETG or PLA, 0.4 nozzle, 0.15-0.2 layer, 3 perimeters, 15 % infill, face up (as exported), no supports (the groove ceiling is a ~1 mm overhang ring, it bridges). Brim off.",
        "",
        "**Test order:** 1 (generous) first: if the adapter does not enter or turn even there, measure the adapter before printing more. Then 2 (nominal), then only the rows that address what misfits:",
        "- nose does not enter / wobbles: 3 / 4 (bore);",
        "- nose enters but the lugs hit the face: 7 (wider notches), 8 (keyed wide + narrow notch), 5 / 6 (notch angle);",
        "- lugs drop in but do not turn / turn too freely: 9 (deeper groove) vs 2;",
        "- the adapter does not sit flat: 10 (counterbore for a flange at the nose base), 11 (bigger key-step pocket).",
        "",
        "**What to note per coupon:** enters at 90 deg (yes / no), turns clockwise to flush (yes / no / force), axial play when locked (mm, feeler), the adapter flush with both side faces and top / bottom, any rubbing (where). Then set `cart.receiver.*` / `cart.adapter.*` in `params.json` and regenerate.",
        "",
        "## How the receiver works (variant A, nominal values)",
        "",
        "1. **Bore:** the adapter's round nose (needle in its centre) drops into a d13.3 bore, 5.5 deep, on the cartridge axis (12.5 from the -Y end, centred in the 19). Below the bore the cartridge passes (d11.55); its crimp cap sits 1.0 below the seat plane, so the needle meets the septum on the axis.",
        "2. **Entry notches:** two axial slots in the bore wall, 180 deg apart, at 90 deg (the adapter's long axis vertical, i.e. across the 19 face): the two lugs on the nose rim slide down them.",
        "3. **Lug groove (bayonet undercut):** a ring groove r 7.7 from 1.95 to 3.65 below the seat plane (lug 1.2 thick at 2.2 below the seat, + 0.25 clearance each side). Turned clockwise by 90 deg, the lugs move under the groove's front wall: that is what holds the adapter **axially**.",
        "4. **Lock angle / rotation stop:** at 0 deg (long axis along the 52 face) the adapter's key step (raised underside of its tubing half, 2.8 high) drops into the pocket in the face (y 21.2-50.1, z 1.9-17.1, 3.1 deep): it stops the turn and keeps the adapter from turning back; the adapter body then lies flush with the housing outline.",
        "5. **Counterbore:** none in the nominal design (coupon 10 tests one for a flange at the nose base).",
        "6. **Seal:** none. Water only, open bench; the original adapter has a vent and is not watertight either (manual p.36). The patent's pump has an O-ring on the housing face (US9554967B2 Fig. 4b, part 235), we do not.",
        "",
        "## Which references set which dimension (all read as images, none committed; links in `docs/insight-research.md` §7.6)",
        "",
        "| Dimension | Value used | References (distinct views) |",
        "|---|---|---|",
        "| Pump end face 52 x 19, length 84 | 52 x 19 x 84 | user manual App. A (text, VERIFIED) |",
        "| Adapter = flush end cap, put on at 90 deg, clockwise to the stop | 90 deg entry, 0 deg lock | manual p.28 step 8, p.29 step 9, p.27 and p.36 removal (4 figures); US D689,523 Fig. 6 (1) |",
        "| Nose OD | 13.0 (bore 13.3) | US D720,449 Figs 3, 5, 7 (3); Adapter & Tubing IFU figure (1) |",
        "| Nose axis from the adapter end | 12.5 | US D720,449 Figs 3, 5 (2); manual p.29 underside view (1) |",
        "| Lugs: count, position | 2, on the long axis when locked | US D720,449 Fig. 5 (1 view only) |",
        "| Lug widths | CAD 1.6 both; patent reads ~5 and ~1.5 (keyed) -> coupon 8 | US D720,449 Fig. 5 (1) |",
        "| Lug height 0.8, thickness 1.2, depth below the seat 2.2 | guesses | **no source** (not visible in any view) |",
        "| Pump bore / counterbore / notch arc | patent reads ~11.7-12.4 / ~15-17 / 60-80 deg; CAD uses 13.3 / none / slots | US D689,523 Fig. 6 (1 view only) |",
        "| Key step height and extent | 2.8, tubing half | US D720,449 Fig. 3 (1); manual p.29 side view (1); IFU (1) |",
        "| Tubing exit | far end, 2 above the underside | US D720,449 Figs 1, 2, 5, 6, 8 (5) |",
        "| Vent / seal | none in our receiver | US9554967B2 Figs 3, 4b (2); manual App. A + p.36 (text) |",
        "| Overall look | | owner's product photo (1) |",
        "",
        "In all: US D720,449 = 8 views on 4 sheets, US D689,523 = 1 figure, US9554967B2 = 2 figures, manual = 7 figures (p.2, p.27, p.28, p.29 x 3, p.36) + text, Adapter & Tubing IFU = its figures (count not recorded), 1 owner photo. "
        "The design patents are **unscaled**: every value was scaled from them with the VERIFIED 84 x 52 x 19 and is an ESTIMATE (+-1 mm). The biggest open conflict: nose ~13 vs pump bore ~12 in the patents.",
        "",
        "There is **no seal** in this receiver (the original adapter is not watertight either, manual p.36; the pump end of the patent has an O-ring on the housing face). Axial hold = the lugs under the groove's front wall; rotation stop = the key step in its pocket.",
    ]
    return "\n".join(lines) + "\n"


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
