> **TEST ONLY - NOT FOR HUMAN USE.** Bench only, **water only**. These coupons only check how the original Insight Adapter & Tubing fits our printed receiver.

# Variant A twist-lock fit coupons (`cart_lock_coupons.py`), rebuilt from the owner's adapter photos (2026-11-25)

Each coupon is a 10 mm slice of the real variant A front end (52 x 19 face) with the cup socket, the two retaining tabs and entry gaps, the lip ring under the tabs, the flat seal face, the arc recess for the adapter's raised far half and the latch catch notches. Exactly **one** dimension changes per coupon (PHOTO-ESTIMATE, see below). **ID = number of notches on the base rim** (long edge on the latch side).

| ID | File | What changed (vs nominal) |
|---|---|---|
| 1 | `A_lock_01_generous.stl` | all clearances +0.4: tabs 11.1, lip ring 12.0, entry gaps +0.4, tab-to-lip axial gap 0.6, arc recess r -0.4 and 0.4 deeper |
| 2 | `A_lock_02_nominal.stl` | photo estimate: tabs 10.7 for the cup 10.3, lip ring 11.6 down to 4.9, entry gaps at +-Y (lips across the width), arc recess r 23.7 x 2.3, catch at r 24 / +-7 |
| 3 | `A_lock_03_tabs_10.4.stl` | socket tabs 10.4 (cup + 0.1, tight) |
| 4 | `A_lock_04_tabs_11.3.stl` | socket tabs 11.3 (cup + 1.0, loose) |
| 5 | `A_lock_05_cup_4.2.stl` | cup 0.5 shorter: tabs end and lip ring 0.5 higher (cup proud 4.2) |
| 6 | `A_lock_06_cup_5.2.stl` | cup 0.5 longer: tabs end and lip ring 0.5 lower (cup proud 5.2) |
| 7 | `A_lock_07_lipring_12.2.stl` | lip ring under the tabs 12.2 instead of 11.6 (lip up to ~11.7) |
| 8 | `A_lock_08_entry_90.stl` | entry gaps turned 90 deg (at +-Z): for lips ON the long axis |
| 9 | `A_lock_09_gaps_wide.stl` | entry gaps for 110 deg lips instead of 80 (narrower tabs) |
| 10 | `A_lock_10_catch_r22.5.stl` | arc recess + latch catch 1.5 closer to the socket (r 22.5) |
| 11 | `A_lock_11_catch_r25.5.stl` | arc recess + latch catch 1.5 further out (r 25.5) |
| 12 | `A_lock_12_recess_deep.stl` | arc recess 0.8 deeper (far-half step 3.3 instead of 2.5) |

`A_lock_bed.stl`: all 12 coupons on one 280 x 240 bed (119 x 168 mm used). Coupon 19 x 52 x 10 mm.

**Print:** PETG or PLA, 0.4 nozzle, 0.15 layer, 3 perimeters, 15 % infill, face up (as exported), no supports (the tabs overhang the lip ring by ~0.5, they bridge). Brim off.

## How the adapter locks (what the coupons reproduce)

1. **Put on at 90 deg:** the adapter sticks out across the pump (long axis across the 19 face). Its dark **cup** (OD ~10.3, ~4.7 proud of its flat underside) goes into our socket; the two **rim lips** of the cup (outward lip ~11.1, ~0.6 high) pass through the two **entry gaps** between our retaining tabs.
2. **Turn 90 deg down to flush:** the lips slide under the two **retaining tabs** (ID 10.7, from the face down to 3.9) into the **lip ring** (11.6, 3.9 to 4.9 deep). The tabs hold the adapter axially; the **white seal ring** (OD ~13.5) presses on our flat face around the socket.
3. During the turn the adapter's **raised far half** (~2.5 proud beyond an arc ~24 from the cup axis) sweeps over the face: our face is **recessed** by 2.3 outside r 23.7 (concentric with the socket).
4. **Flush:** the **hook / spring tongue** at the arc (~7 off the long axis) snaps into a **catch notch** in the recess riser. Notches are on both sides (which side the hook is on, seen from the pump, is not certain from the photos).
5. The cartridge crimp cap sits 1.0 below our face, inside the cup (cup ID ~8.4, cap 7.8); the needle in the cup bottom meets the septum on the axis.

**Known conflict:** the cartridge barrel (10.95) does not pass the 10.7 tabs, so with these numbers the cartridge goes in from the top (lid off), not through the socket. If the real cup OD is >= 11.0, the tabs can open to >= 11.3 and the cartridge passes again (coupon 4 tells).

## Measure on the real adapter (calipers, in this order)

1. **Cup OD** just below the lip (across the cup, 2 directions).
2. **Lip OD** at the rim (over the lips, 2 directions: across the width and along the long axis) and **lip height** (rim to the step under the lip).
3. **Lip arcs:** where the lip is interrupted (flats), the angle / width of each lip, relative to the adapter long axis (photo straight on is enough).
4. **Cup protrusion** from the flat underside to the rim (depth gauge of the caliper on the flat face).
5. **Cup ID** and the **depth to the needle base** inside the cup; where the needle tip is relative to the rim.
6. **Seal ring** OD / ID / thickness (proud of the flat face).
7. **Cup centre to the near end** and to both long edges (is it centred across the width?).
8. **Raised far half:** step height over the flat face, and the distance from the cup centre to the arc edge (on the long axis and at both long edges).
9. **Hook:** distance of the hook tip from the cup centre along the long axis and off the axis (which side, seen from the underside with the cup on top), and which way it springs (in the face plane or toward the pump).
10. **Adapter outline:** length, width, max thickness; tubing exit height above the underside.

## Sources for these numbers

Owner's 3 photos of his adapter (underside straight on; 2 side profiles), scaled with the adapter width = 19.0 (pump end face, manual App. A, VERIFIED) at ~21 px/mm: every value is a **PHOTO-ESTIMATE, +-0.5-1 mm** (perspective, lens). The earlier lug / groove / key-step model from the design patents was wrong for this part and is replaced.
