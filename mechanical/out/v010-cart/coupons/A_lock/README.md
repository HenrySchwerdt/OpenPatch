> **TEST ONLY - NOT FOR HUMAN USE.** Bench only, **water only**. These coupons only check how the original Insight Adapter & Tubing fits our printed receiver.

# Variant A twist-lock fit coupons (`cart_lock_coupons.py`)

Each coupon is a 8 mm slice of the real variant A front end (52 x 19 face), face up. Exactly **one** dimension changes per coupon. **ID = number of notches on the base rim.**

**How the original locks (round 3):** the adapter's cup carries **2 outward hook lugs** on the adapter's long axis, one ~5.1 and one ~3.1 wide (keyed, ~0.5 radial, ~1.4 tall, at the cup tip). The pump rim has **2 matching windows**: with the adapter standing at 90 deg (far half pointing away from the face, toward the display / label side) the lugs drop through them. Turning the adapter **90 deg clockwise** (seen from the face) down to flush moves the lugs under the rim in **2 undercut pockets**; each pocket ends in a **stop face** at the flush position. The rim then holds the adapter axially, the stop + the ball detent hold the angle.

**Nominal (coupon 2), from photos and the owner's description** (+-0.5-1 mm): rim ID 10.7 from the face down to 3.1; windows 5.6 / 3.6 wide (lug + 2 x 0.25); undercut pockets d11.7 from 3.1 to 4.9 deep, 90 deg travel to the stop; seal seat d14.6 x 0.5; face recessed 2.5 outside r 12; 2 pockets for a 2 mm steel ball at 9.0 along / +-4.5 across; 2 hook pockets at r 24 / +-7.

| ID | File | What changed (vs nominal) |
|---|---|---|
| 1 | `A_lock_01_generous.stl` | everything looser: windows +0.6, undercut 12.5 and 0.6 taller, rim 11.1, recess from r 11.6 and 0.4 deeper |
| 2 | `A_lock_02_nominal.stl` | estimate (header): keyed windows at 90 deg, stop after a 90 deg turn |
| 3 | `A_lock_03_entry_70.stl` | windows at 70 deg, stop after a 70 deg turn |
| 4 | `A_lock_04_entry_80.stl` | windows at 80 deg, stop after an 80 deg turn |
| 5 | `A_lock_05_entry_105.stl` | windows at 105 deg, stop after a 105 deg turn |
| 6 | `A_lock_06_entry_120.stl` | windows at 120 deg (manual: lift-off ~120), stop after a 120 deg turn |
| 7 | `A_lock_07_windows_+0.2.stl` | windows 0.2 wider (5.8 / 3.8) |
| 8 | `A_lock_08_windows_+0.5.stl` | windows 0.5 wider (6.1 / 4.1) |
| 9 | `A_lock_09_undercut_h-0.3.stl` | undercut 0.3 lower in height (1.5 instead of 1.8: tighter axially) |
| 10 | `A_lock_10_undercut_h+0.3.stl` | undercut 0.3 taller (2.1) |
| 11 | `A_lock_11_windows_+0.8.stl` | windows 0.8 wider (6.4 / 4.4) |
| 12 | `A_lock_12_undercut_d+0.4.stl` | undercut diameter 12.1 |
| 13 | `A_lock_13_undercut_d+0.8.stl` | undercut diameter 12.5 |
| 14 | `A_lock_14_rim_10.5.stl` | rim ID 10.5 (tighter around the cup) |
| 15 | `A_lock_15_rim_10.9.stl` | rim ID 10.9 |
| 16 | `A_lock_16_rim_11.1.stl` | rim ID 11.1 (cup larger than estimated) |
| 17 | `A_lock_17_snap_bump.stl` | small snap bump (0.25) just before the end stop |
| 18 | `A_lock_18_keyed_mirror.stl` | keying mirrored: narrow window on the +Z side, wide on -Z |
| 19 | `A_lock_19_unkeyed_5.6.stl` | both windows wide (5.6), in case the lugs are equal |
| 20 | `A_lock_20_lugs_higher.stl` | lugs 0.5 higher (cup proud 4.2): undercut 0.5 higher |
| 21 | `A_lock_21_lugs_lower.stl` | lugs 0.5 lower (cup proud 5.2): undercut 0.5 lower |
| 22 | `A_lock_22_ball_along_-1.stl` | ball pockets 1 closer along (8.0) |
| 23 | `A_lock_23_ball_along_+1.stl` | ball pockets 1 further along (10.0) |
| 24 | `A_lock_24_rim_r13.stl` | high zone larger: recess from r 13 |
| 25 | `A_lock_25_recess_deep.stl` | recess 0.8 deeper (far half 3.3 proud) |

`A_lock_bed.stl`: all 25 coupons (244 x 168 mm, fits 280 x 240). `A_lock_bed_first.stl`: IDs 1-10 only (quick first plate). Coupon 19 x 52 x 8 mm.

**Print:** PETG or PLA, 0.4 nozzle, 0.15-0.2 layer, 3 perimeters, 15 % infill, as exported (face up), no supports, no brim. Optional: press a 2 mm steel ball into each round pocket on the face (0.5 stands out) to feel the detent click.

## How to judge the fit (per coupon, note the ID)

1. **Goes in?** Adapter sticking out across the face (about 90 deg, the right coupon may want 70-120), cup straight down into the bore: does it drop in to the white ring without force? (no: the cup hits the rim -> rim rows 14-16; the lugs hit -> windows width rows 7-8 and 11, angle rows 3-6, keying rows 18-19)
2. **Turns 90 deg clockwise to the stop?** Smooth, stiff, blocked early (undercut: rows 9-10, 12-13, 20-21) or does it stop before / after flush (entry angle: rows 3-6)? Goes on only the other way = keying (rows 18-19).
3. **Sits flush?** Locked, the adapter lies flat on the face and lines up with the outline (no gap at the far end, no rocking). Rocking at the far end -> recess depth / rim radius.
4. **Holds?** Pull gently straight away from the face: it must not come off when locked. Comes off -> tabs too big or undercut too low.
5. **Wobble?** Locked, wiggle it: a little play is fine, rattling is not.
6. **Clicks?** With balls in the pockets (or coupon 17 with the snap bump): does it click into place at flush? (no click -> rows 17, 22-23)

Report: the best ID and, for it, yes / no for 1-6. If two coupons are both good, report both.
