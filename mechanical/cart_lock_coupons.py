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
# Centre values = PHOTO-ESTIMATE of the owner's adapter (2026-11-25): cup OD 10.3 (socket tabs 10.7), cup proud 4.7, rim lip 11.1 x 0.6 over ~80 deg
# across the width, white seal ring 13.5, far half 2.5 proud beyond an arc r 24 around the cup axis, hook ~7 off the long axis at that arc.
MATRIX = [
    (1, "generous", "all clearances +0.4: tabs 11.1, lip ring 12.0, entry gaps +0.4, tab-to-lip axial gap 0.6, arc recess r -0.4 and 0.4 deeper",
     {"receiver": {"tab_id": 11.1, "bore_d": 12.0, "lip_clr": 0.65, "tab_axial_clr": 0.6, "step_clr": 0.7}}),
    (2, "nominal", "photo estimate: tabs 10.7 for the cup 10.3, lip ring 11.6 down to 4.9, entry gaps at +-Y (lips across the width), arc recess r 23.7 x 2.3, catch at r 24 / +-7", {}),
    (3, "tabs_10.4", "socket tabs 10.4 (cup + 0.1, tight)", {"receiver": {"tab_id": 10.4}}),
    (4, "tabs_11.3", "socket tabs 11.3 (cup + 1.0, loose)", {"receiver": {"tab_id": 11.3}}),
    (5, "cup_4.2", "cup 0.5 shorter: tabs end and lip ring 0.5 higher (cup proud 4.2)", {"adapter": {"cup": {"proud": 4.2}}}),
    (6, "cup_5.2", "cup 0.5 longer: tabs end and lip ring 0.5 lower (cup proud 5.2)", {"adapter": {"cup": {"proud": 5.2}}}),
    (7, "lipring_12.2", "lip ring under the tabs 12.2 instead of 11.6 (lip up to ~11.7)", {"receiver": {"bore_d": 12.2}}),
    (8, "entry_90", "entry gaps turned 90 deg (at +-Z): for lips ON the long axis", {"receiver": {"entry_deg": 90.0, "lock_deg": 0.0}}),
    (9, "gaps_wide", "entry gaps for 110 deg lips instead of 80 (narrower tabs)", {"adapter": {"cup": {"lip_arc_deg": 110.0}}}),
    (10, "catch_r22.5", "arc recess + latch catch 1.5 closer to the socket (r 22.5)", {"adapter": {"cup": {"step_r": 22.5, "hook_r": 22.5}}}),
    (11, "catch_r25.5", "arc recess + latch catch 1.5 further out (r 25.5)", {"adapter": {"cup": {"step_r": 25.5, "hook_r": 25.5}}}),
    (12, "recess_deep", "arc recess 0.8 deeper (far-half step 3.3 instead of 2.5)", {"adapter": {"step_h": 3.3}}),
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
        "# Variant A twist-lock fit coupons (`cart_lock_coupons.py`), rebuilt from the owner's adapter photos (2026-11-25)",
        "",
        f"Each coupon is a {DEPTH:.0f} mm slice of the real variant A front end (52 x 19 face) with the cup socket, the two retaining tabs and entry gaps, the lip ring "
        "under the tabs, the flat seal face, the arc recess for the adapter's raised far half and the latch catch notches. Exactly **one** dimension changes per coupon "
        "(PHOTO-ESTIMATE, see below). **ID = number of notches on the base rim** (long edge on the latch side).",
        "",
        "| ID | File | What changed (vs nominal) |",
        "|---|---|---|",
        *[f"| {n} | `A_lock_{n:02d}_{short}.stl` | {what} |" for n, short, what, _ in rows],
        "",
        f"`A_lock_bed.stl`: all {len(rows)} coupons on one {BED[0]:.0f} x {BED[1]:.0f} bed ({sizes['bed'][0]:.0f} x {sizes['bed'][1]:.0f} mm used). Coupon {sizes['one'][0]:.0f} x {sizes['one'][1]:.0f} x {sizes['one'][2]:.0f} mm.",
        "",
        "**Print:** PETG or PLA, 0.4 nozzle, 0.15 layer, 3 perimeters, 15 % infill, face up (as exported), no supports (the tabs overhang the lip ring by ~0.5, they bridge). Brim off.",
        "",
        "## How the adapter locks (what the coupons reproduce)",
        "",
        "1. **Put on at 90 deg:** the adapter sticks out across the pump (long axis across the 19 face). Its dark **cup** (OD ~10.3, ~4.7 proud of its flat underside) "
        "goes into our socket; the two **rim lips** of the cup (outward lip ~11.1, ~0.6 high) pass through the two **entry gaps** between our retaining tabs.",
        "2. **Turn 90 deg down to flush:** the lips slide under the two **retaining tabs** (ID 10.7, from the face down to 3.9) into the **lip ring** (11.6, 3.9 to 4.9 deep). "
        "The tabs hold the adapter axially; the **white seal ring** (OD ~13.5) presses on our flat face around the socket.",
        "3. During the turn the adapter's **raised far half** (~2.5 proud beyond an arc ~24 from the cup axis) sweeps over the face: our face is **recessed** by 2.3 "
        "outside r 23.7 (concentric with the socket).",
        "4. **Flush:** the **hook / spring tongue** at the arc (~7 off the long axis) snaps into a **catch notch** in the recess riser. Notches are on both sides "
        "(which side the hook is on, seen from the pump, is not certain from the photos).",
        "5. The cartridge crimp cap sits 1.0 below our face, inside the cup (cup ID ~8.4, cap 7.8); the needle in the cup bottom meets the septum on the axis.",
        "",
        "**Known conflict:** the cartridge barrel (10.95) does not pass the 10.7 tabs, so with these numbers the cartridge goes in from the top (lid off), not through the "
        "socket. If the real cup OD is >= 11.0, the tabs can open to >= 11.3 and the cartridge passes again (coupon 4 tells).",
        "",
        "## Measure on the real adapter (calipers, in this order)",
        "",
        "1. **Cup OD** just below the lip (across the cup, 2 directions).",
        "2. **Lip OD** at the rim (over the lips, 2 directions: across the width and along the long axis) and **lip height** (rim to the step under the lip).",
        "3. **Lip arcs:** where the lip is interrupted (flats), the angle / width of each lip, relative to the adapter long axis (photo straight on is enough).",
        "4. **Cup protrusion** from the flat underside to the rim (depth gauge of the caliper on the flat face).",
        "5. **Cup ID** and the **depth to the needle base** inside the cup; where the needle tip is relative to the rim.",
        "6. **Seal ring** OD / ID / thickness (proud of the flat face).",
        "7. **Cup centre to the near end** and to both long edges (is it centred across the width?).",
        "8. **Raised far half:** step height over the flat face, and the distance from the cup centre to the arc edge (on the long axis and at both long edges).",
        "9. **Hook:** distance of the hook tip from the cup centre along the long axis and off the axis (which side, seen from the underside with the cup on top), "
        "and which way it springs (in the face plane or toward the pump).",
        "10. **Adapter outline:** length, width, max thickness; tubing exit height above the underside.",
        "",
        "## Sources for these numbers",
        "",
        "Owner's 3 photos of his adapter (underside straight on; 2 side profiles), scaled with the adapter width = 19.0 (pump end face, manual App. A, VERIFIED) "
        "at ~21 px/mm: every value is a **PHOTO-ESTIMATE, +-0.5-1 mm** (perspective, lens). The earlier lug / groove / key-step model from the design patents was wrong "
        "for this part and is replaced.",
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
