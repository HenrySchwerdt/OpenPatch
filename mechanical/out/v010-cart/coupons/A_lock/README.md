> **TEST ONLY - NOT FOR HUMAN USE.** Bench only, **water only**. These coupons only check how the original Insight Adapter & Tubing fits our printed receiver.

# Variant A twist-lock fit coupons (`cart_lock_coupons.py`)

Each coupon is a 8 mm slice of the real variant A front end (52 x 19 face), face up. Exactly **one** dimension changes per coupon. **ID = number of notches on the base rim.**

**Nominal (coupon 2), all from photos** (no measuring tools; scaled from the pump end face 52 x 19 VERIFIED, the 19 adapter width and the ISO cartridge 10.95 / cap 7.8, cross-checked between 7 photos of the original pump and 3 of the adapter, +-0.5-1 mm): seal seat d14.6 x 0.5 for the white ring; 2 bore windows at +-Y (along the end face) for the cup's 2 rim lips (~80 deg each); 2 retaining tabs between them, ID 11.3 (the cartridge passes); undercut d12.5 from 3.9 to 4.9 below the face; face recessed 2.5 outside r 12 (the original's curved rim; the adapter's raised far half lies there); 2 pockets for a 2 mm steel ball detent at 9.0 along / +-4.5 across; 2 hook pockets at r 24 / +-7. The adapter pivots on the bore and swings down over the battery side; the tubing leaves its far end.

| ID | File | What changed (vs nominal) |
|---|---|---|
| 1 | `A_lock_01_generous.stl` | all clearances +0.4: tabs 11.7, undercut 12.9, windows +0.8 wide, tab-to-lip gap 0.6, recess from r 11.6 and 0.4 deeper |
| 2 | `A_lock_02_nominal.stl` | photo estimate (header) |
| 3 | `A_lock_03_tabs_-0.4.stl` | tabs 10.9 |
| 4 | `A_lock_04_tabs_+0.4.stl` | tabs 11.7 |
| 5 | `A_lock_05_undercut_-0.4.stl` | undercut 12.1 |
| 6 | `A_lock_06_undercut_+0.4.stl` | undercut 12.9 |
| 7 | `A_lock_07_windows_-10.stl` | windows turned -10 deg |
| 8 | `A_lock_08_windows_+10.stl` | windows turned +10 deg |
| 9 | `A_lock_09_windows_+0.5.stl` | windows 0.5 wider |
| 10 | `A_lock_10_tabs_-0.8.stl` | tabs 10.5 |
| 11 | `A_lock_11_tabs_+0.8.stl` | tabs 12.1 |
| 12 | `A_lock_12_undercut_-0.8.stl` | undercut 11.7 |
| 13 | `A_lock_13_undercut_+0.8.stl` | undercut 13.3 |
| 14 | `A_lock_14_undercut_high.stl` | undercut 0.5 higher (cup proud 4.2) |
| 15 | `A_lock_15_undercut_low.stl` | undercut 0.5 lower (cup proud 5.2) |
| 16 | `A_lock_16_windows_-20.stl` | windows turned -20 deg |
| 17 | `A_lock_17_windows_+20.stl` | windows turned +20 deg |
| 18 | `A_lock_18_windows_keyed.stl` | one wide (110 deg, toward the far half) and one narrow (50 deg) window |
| 19 | `A_lock_19_ball_along_-1.stl` | ball pockets 1 closer along (8.0) |
| 20 | `A_lock_20_ball_along_+1.stl` | ball pockets 1 further along (10.0) |
| 21 | `A_lock_21_ball_across_-1.stl` | ball pockets 1 closer to the axis (3.5 across) |
| 22 | `A_lock_22_ball_across_+1.stl` | ball pockets 1 further across (5.5) |
| 23 | `A_lock_23_rim_r11.stl` | high zone smaller: recess from r 11 |
| 24 | `A_lock_24_rim_r13.stl` | high zone larger: recess from r 13 |
| 25 | `A_lock_25_recess_deep.stl` | recess 0.8 deeper (far half 3.3 proud) |

`A_lock_bed.stl`: all 25 coupons (219 x 168 mm, fits 280 x 240). `A_lock_bed_first.stl`: IDs 1-9 only (quick first plate). Coupon 19 x 52 x 8 mm.

**Print:** PETG or PLA, 0.4 nozzle, 0.15-0.2 layer, 3 perimeters, 15 % infill, as exported (face up), no supports, no brim. Optional: press a 2 mm steel ball into each round pocket on the face (0.5 stands out) to feel the detent click.

## How to judge the fit (per coupon, note the ID)

1. **Goes in at 90 deg?** Adapter sticking out across the face, cup straight down into the bore: does it drop in to the white ring without force? (no: tabs too tight -> try a higher tabs value; lips hit -> windows angle / width)
2. **Turns 90 deg?** Turn it down toward the long side until flush: smooth, stiff or blocked? Blocked early -> undercut too small or too high/low.
3. **Sits flush?** Locked, the adapter lies flat on the face and lines up with the outline (no gap at the far end, no rocking). Rocking at the far end -> recess depth / rim radius.
4. **Holds?** Pull gently straight away from the face: it must not come off when locked. Comes off -> tabs too big or undercut too low.
5. **Wobble?** Locked, wiggle it: a little play is fine, rattling is not.
6. **Clicks?** With balls in the pockets: does it click into place at flush? (no click -> ball position rows 19-22)

Report: the best ID and, for it, yes / no for 1-6. If two coupons are both good, report both.
