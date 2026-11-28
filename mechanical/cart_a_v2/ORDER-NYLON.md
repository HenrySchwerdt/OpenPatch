# OpenTube A v2.3: black nylon parts order (MJF PA12)

> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). Bench only, **water only**: never insulin or any other drug, never on a person.

Files: `../out/cart_a_v2_mjf/print/OpenTube_A_bottom.step` / `_top.step` (exact geometry, preferred: the service meshes it) and
`OpenTube_A_*.stl` (mm, pump coordinates; orientation does not matter for MJF). Every file is gated: STL without holes, STEP imports
into SolidCraft, the outer skin has only the wanted openings.
Built with `OP_MJF=1 ../../.venv/bin/python package.py && OP_MJF=1 ../../.venv/bin/python shells.py`; same checks as the FDM
parts, all pass (`../out/cart_a_v2_mjf/print/mjf_report.json`): no part collisions FULL / EMPTY, closed halves, screws, adapter on the
face, outline at the face = the adapter outline, no hole in a lock feature.

## What to order
| File | Part | Volume | Qty |
|---|---|---|---|
| `OpenTube_A_bottom.stl` | bottom half with the lock face (lower half), tongue, 2 pins, 5 screw holes | 9.20 cm3 | 1 |
| `OpenTube_A_top.stl` | top half with the lock face (upper half), groove, 5 nut pockets, button + LED holes | 8.57 cm3 | 1 |
| `OpenTube_A_yoke.stl` | yoke (lead screw nut + stem) | 0.19 cm3 | 1 |
| `OpenTube_A_pusher.stl` | pusher disc | 0.06 cm3 | 1 |
| `OpenTube_A_button_plunger.stl` | button plunger | 0.07 cm3 | 1 |

Material / process: **MJF (HP Multi Jet Fusion) PA12, dyed black**, standard finish (bead-blasted). SLS PA12 black also works.
A spare pair of halves costs little extra and saves a re-order if a fit needs a touch.

**Not in nylon:** the LED light pipe must be clear (2 mm clear acrylic rod or clear 1.75 filament, 9.06 mm long); the FDM fit dummies
(board, motor, rods, nuts) are not needed.

## Differences to the FDM files (built in)
- Pure rounds on every edge and at the rear end (v2.3: the FDM parts have them too); no 0.15 mm z stretch; no first-layer
  compensation; no groove on the seam (v2.3, owner: the halves butt flush).
- Clearances for MJF (parts mate within about +-0.2 mm): tongue 0.7 in a 1.1 groove (0.2 per side), pin holes d2.45 for d2.0 pins,
  screw holes d2.4, nut pockets AF 4.15 (press fit for AF 4.0 M2 nuts), stem press holes d2.0 for the M2 brass rod (MJF holes come
  out about 0.1 small).

## Hardware per pump (see docs/CART-ORDER.md)
5 x M2 x 12 countersunk (DIN 965 / 963), 6 x M2 nut (5 closing + 1 yoke), 1 x 2 mm steel ball (lock ball), M2 brass rod
(lead screw 31.4 + stem 26.9), pinion / gear / magnet, motor, cell, board.

## Before ordering
1. Print the FDM test coupon `../print/cart_A/TEST5.gcode` (v2.3: FACE4 lock face in both halves) and check with the real
   Accu-Chek adapter: it must sit and lock as on FACE4 (flush all round, no play, does not slip). TEST4 had the 2026-11-27
   outline, 1.16 mm off the bore (loose). Fix `../print/A_lock/make_face.py` first if not - the nylon parts cannot be adjusted
   afterwards.
2. The lock switch reading (adapter locked / free) still needs a bench check with the real board: margins 0.17 / 0.20 mm.
