> **TEST ONLY - NOT FOR HUMAN USE.** Bench only, **water only**. These coupons only check how the original Insight Adapter & Tubing fits our printed receiver.

# Variant A twist-lock fit coupons (`cart_lock_coupons.py`), built on the ORIGINAL pump's end face (2026-11-25)

Each coupon is a 10 mm slice of the real variant A front end (52 x 19 face). Exactly **one** dimension changes per coupon. **ID = number of notches on the base rim.** Nominal (coupon 2), all ESTIMATE from the owner's photos of the original pump end face and of his adapter, scaled with the 19 mm end-face width (+-0.5-1 mm):

- seal seat (shallow counterbore) d14.6 x 0.5 for the adapter's white ring (OD ~13.5);
- bore wall with **2 windows** at +-Y (along the end face), each for an ~80 deg cup lip, and **2 retaining tabs** between them, ID 11.3 (the cartridge, 10.95, passes, as on the original);
- **undercut** (lip ring) d12.5 under the tabs, from 3.9 to 4.9 below the face (adapter cup ~4.7 proud, lip ~0.6 high);
- the face is **recessed 2.5 outside r 12** around the socket (the original's curved rim; the adapter's raised far half lies there);
- **detent**: 2 pockets for a 2 mm steel ball (press in, 0.5 proud) at 8.5 along +Y and +-5.5 across (the original has one polished ball there; the adapter has 2 holes ~11 from its cup at +-5). Print without balls first; add a ball (e.g. 2 mm bearing ball) to feel the click;
- hook pockets 3 x 2.3, 1 deep in the recess floor at r 24, +-7 across (for the adapter's curved hook; what it catches on the original is not clear from the photos).

| ID | File | What changed (vs nominal) |
|---|---|---|
| 1 | `A_lock_01_generous.stl` | all clearances +0.4: tabs 11.7, lip ring 12.9, windows +0.4, tab-to-lip gap 0.6, recess from r 11.6 and 0.4 deeper |
| 2 | `A_lock_02_nominal.stl` | estimate from the original pump + adapter photos (values in the header of this README) |
| 3 | `A_lock_03_tabs_11.0.stl` | retaining tabs 11.0 (tight; the cartridge 10.95 just passes) |
| 4 | `A_lock_04_tabs_11.6.stl` | retaining tabs 11.6 (loose) |
| 5 | `A_lock_05_lipring_12.0.stl` | undercut (lip ring) 12.0 instead of 12.5 |
| 6 | `A_lock_06_lipring_13.0.stl` | undercut (lip ring) 13.0 |
| 7 | `A_lock_07_undercut_high.stl` | cup 0.5 shorter: tabs end and undercut 0.5 higher (cup proud 4.2) |
| 8 | `A_lock_08_undercut_low.stl` | cup 0.5 longer: tabs end and undercut 0.5 lower (cup proud 5.2) |
| 9 | `A_lock_09_windows_+20.stl` | windows turned +20 deg |
| 10 | `A_lock_10_windows_-20.stl` | windows turned -20 deg |
| 11 | `A_lock_11_windows_keyed.stl` | asymmetric windows (patent / photo: one wide, one narrow): 110 deg toward +Y (far half), 50 deg toward -Y |
| 12 | `A_lock_12_ball_far.stl` | detent ball pockets 1.5 further out (10.0 along) |
| 13 | `A_lock_13_ball_near.stl` | detent ball pockets 1.5 closer (7.0 along) and 4.5 across |
| 14 | `A_lock_14_rim_r13.stl` | high zone around the socket larger: recess from r 13.0 |
| 15 | `A_lock_15_recess_deep.stl` | recess 0.8 deeper (far half 3.3 proud) |

`A_lock_bed.stl`: all 15 coupons on one 280 x 240 bed (119 x 168 mm used). Coupon 19 x 52 x 10 mm.

**Print:** PETG or PLA, 0.4 nozzle, 0.15 layer, 3 perimeters, 15 % infill, face up (as exported), no supports (the tabs overhang the undercut by ~0.6 and bridge). Brim off.

**Test:** put the adapter on at 90 deg (sticking out across the face), push the cup in, turn 90 deg down to flush. Note: enters (y/n), turns (y/n/force), axial play when flush, flush with the outline (y/n), clicks (with ball). Start with 1 (generous) and 2 (nominal), then the rows for what misfits.

## Measure on the ORIGINAL pump end face (calipers; adapter off)

1. **Bore at the face** (smallest diameter through the tabs) and **seal seat** diameter + depth (the shallow step around the bore).
2. **Undercut**: largest diameter under the tabs (inside calipers or a feeler) and its depth: face to the underside of the tabs, face to the undercut floor.
3. **Windows**: width of each window (chord at the bore) and the angle of each window centre against the pump's long side (photo straight on is enough). Are they equal?
4. **Cartridge seat**: depth from the face to the inner ledge / cartridge cap.
5. **Detent ball**: distance from the bore centre along the end face and across, ball diameter, how far it stands out, does it spring?
6. **Curved rim**: radius from the bore centre to the curved step around the battery side, and the step height down to the battery-side face.
7. **Bore centre** to the near end of the face and to both long sides.
8. **Battery side**: where the adapter's hook catches when flush (which edge), its distance from the bore centre.
9. On the **adapter**: lip OD over the lips (2 directions), lip height, lip arcs; cup OD; cup protrusion.
10. On the **adapter**: the 2 underside holes (distance from the cup centre, spacing, diameter) and the height of the raised far half.

**Photo wanted:** one straight top-down photo of the pump end face (adapter off) with a ruler in mm lying on the face plane, camera square to the face, and the same for the adapter underside.

The earlier models (lug groove from the patents; cup socket from the adapter photo alone) are replaced.
