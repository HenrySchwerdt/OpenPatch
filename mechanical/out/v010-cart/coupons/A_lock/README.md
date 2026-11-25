> **TEST ONLY - NOT FOR HUMAN USE.** Bench only, **water only**. These coupons only check how the original Insight Adapter & Tubing fits our printed receiver.

# Variant A twist-lock fit coupons (`cart_lock_coupons.py`)

Each coupon is a 8 mm slice of the real variant A front end (52 x 19 face), face up. Exactly **one** dimension changes per coupon. **ID = number of notches on the base rim.**

**How the original locks (round 3):** the adapter's cup carries **2 outward hook lugs** on the adapter's long axis, one ~5.1 and one ~3.1 wide (keyed, ~0.5 radial, ~1.4 tall, at the cup tip). The pump rim has **2 matching windows**: with the adapter standing at 90 deg (far half pointing away from the face, toward the display / label side) the lugs drop through them. Turning the adapter **90 deg clockwise** (seen from the face) down to flush moves the lugs under the rim in **2 undercut pockets**; each pocket ends in a **stop face** at the flush position. The rim then holds the adapter axially, the stop + the ball detent hold the angle.

**Nominal (coupon 2), from photos and the owner's description** (+-0.5-1 mm): rim ID 10.7 from the face down to 3.1; windows 5.6 / 3.6 wide (lug + 2 x 0.25); undercut pockets d11.7 from 3.1 to 4.9 deep, 90 deg travel to the stop; seal seat d14.6 x 0.5; face recessed 2.5 outside r 12; 2 pockets for a 2 mm steel ball at 9.0 along / +-4.5 across; 2 hook pockets at r 24 / +-7.

| ID | File | What changed (vs nominal) |
|---|---|---|
| 1 | `A_lock_01_generous.stl` | everything looser: windows +0.6, undercut 12.5 and 0.6 taller, rim 11.1, recess from r 11.6 and 0.4 deeper |
| 2 | `A_lock_02_nominal.stl` | estimate (header) |
| 3 | `A_lock_03_windows_+0.2.stl` | windows 0.2 wider (5.8 / 3.8) |
| 4 | `A_lock_04_windows_+0.4.stl` | windows 0.4 wider (6.0 / 4.0) |
| 5 | `A_lock_05_windows_+0.6.stl` | windows 0.6 wider (6.2 / 4.2) |
| 6 | `A_lock_06_windows_-10.stl` | windows turned -10 deg |
| 7 | `A_lock_07_windows_+10.stl` | windows turned +10 deg |
| 8 | `A_lock_08_undercut_d+0.4.stl` | undercut diameter 12.1 (lug clearance +0.2) |
| 9 | `A_lock_09_undercut_h+0.3.stl` | undercut 0.3 taller (rim underside 0.3 higher) |
| 10 | `A_lock_10_undercut_d+0.8.stl` | undercut diameter 12.5 |
| 11 | `A_lock_11_undercut_h+0.6.stl` | undercut 0.6 taller |
| 12 | `A_lock_12_rim_10.5.stl` | rim ID 10.5 (tighter around the cup) |
| 13 | `A_lock_13_rim_10.9.stl` | rim ID 10.9 |
| 14 | `A_lock_14_rim_11.1.stl` | rim ID 11.1 (cup larger than estimated) |
| 15 | `A_lock_15_stop_80.stl` | end stop after 80 deg instead of 90 |
| 16 | `A_lock_16_stop_100.stl` | end stop after 100 deg |
| 17 | `A_lock_17_snap_bump.stl` | small snap bump (0.25) just before the end stop |
| 18 | `A_lock_18_keyed_mirror.stl` | keying mirrored: narrow window at +Z, wide at -Z |
| 19 | `A_lock_19_unkeyed_5.6.stl` | both windows wide (5.6), in case the lugs are equal |
| 20 | `A_lock_20_lugs_higher.stl` | lugs 0.5 higher (cup proud 4.2): undercut 0.5 higher |
| 21 | `A_lock_21_lugs_lower.stl` | lugs 0.5 lower (cup proud 5.2): undercut 0.5 lower |
| 22 | `A_lock_22_ball_along_-1.stl` | ball pockets 1 closer along (8.0) |
| 23 | `A_lock_23_ball_along_+1.stl` | ball pockets 1 further along (10.0) |
| 24 | `A_lock_24_rim_r13.stl` | high zone larger: recess from r 13 |
| 25 | `A_lock_25_recess_deep.stl` | recess 0.8 deeper (far half 3.3 proud) |

`A_lock_bed.stl`: all 25 coupons (219 x 168 mm, fits 280 x 240). `A_lock_bed_first.stl`: IDs 1-9 only (quick first plate). Coupon 19 x 52 x 8 mm.

**Print:** PETG or PLA, 0.4 nozzle, 0.15-0.2 layer, 3 perimeters, 15 % infill, as exported (face up), no supports, no brim. Optional: press a 2 mm steel ball into each round pocket on the face (0.5 stands out) to feel the detent click.

## How to judge the fit (per coupon, note the ID)

1. **Goes in at 90 deg?** Adapter sticking out across the face, cup straight down into the bore: does it drop in to the white ring without force? (no: the cup hits the rim -> rim rows 12-14; the lugs hit -> windows width rows 3-5, angle rows 6-7, keying rows 18-19)
2. **Turns 90 deg clockwise to the stop?** Smooth, stiff, blocked early (undercut too small / too high or low: rows 8-11, 20-21) or does it turn past flush (stop angle: rows 15-16)? Wrong way only = keying (rows 18-19).
3. **Sits flush?** Locked, the adapter lies flat on the face and lines up with the outline (no gap at the far end, no rocking). Rocking at the far end -> recess depth / rim radius.
4. **Holds?** Pull gently straight away from the face: it must not come off when locked. Comes off -> tabs too big or undercut too low.
5. **Wobble?** Locked, wiggle it: a little play is fine, rattling is not.
6. **Clicks?** With balls in the pockets (or coupon 17 with the snap bump): does it click into place at flush? (no click -> rows 17, 22-23)

Report: the best ID and, for it, yes / no for 1-6. If two coupons are both good, report both.
