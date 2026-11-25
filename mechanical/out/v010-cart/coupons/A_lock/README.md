> **TEST ONLY - NOT FOR HUMAN USE.** Bench only, **water only**. These coupons only check how the original Insight Adapter & Tubing fits our printed receiver.

# Variant A twist-lock fit coupons (`cart_lock_coupons.py`)

Each coupon is a 10 mm slice of the real variant A front end: the full 52 x 19 face with the connector bore, the two lug entry notches, the lug groove (bayonet undercut) and the key-step pocket. Exactly **one** uncertain dimension is changed per coupon (all ESTIMATE from unscaled patent drawings and manual figures, `../../../../docs/insight-research.md` §7.6). **ID = number of notches on the base rim** (long edge on the tubing side).

| ID | File | What changed (vs nominal) |
|---|---|---|
| 1 | `A_lock_01_generous.stl` | all clearances +0.4: bore 13.7, lug notch / groove clearance 0.65, key pocket clearance 0.7 |
| 2 | `A_lock_02_nominal.stl` | current CAD (bore 13.3, lug notches 1.6 + 2 x 0.25 at 90 deg, groove r 7.7, pocket clearance 0.3) |
| 3 | `A_lock_03_bore_12.9.stl` | nose bore 12.9 (-0.4) |
| 4 | `A_lock_04_bore_13.7.stl` | nose bore 13.7 (+0.4) |
| 5 | `A_lock_05_entry_-10.stl` | lug entry notches rotated -10 deg (80 deg instead of 90) |
| 6 | `A_lock_06_entry_+10.stl` | lug entry notches rotated +10 deg (100 deg instead of 90) |
| 7 | `A_lock_07_notch_w+0.4.stl` | lug entry notches 0.4 wider (lug 2.0) |
| 8 | `A_lock_08_keyed_5_1.5.stl` | keyed lugs as in the design patent: one notch for a ~5 wide lug, the opposite one for a ~1.5 wide lug |
| 9 | `A_lock_09_groove_deep.stl` | lug groove 0.4 deeper radially (lugs 1.2 high instead of 0.8) and notches to match |
| 10 | `A_lock_10_cbore_15.9.stl` | counterbore d15.9 x 1.5 at the face (for a ~15.5 flange at the nose base, D720,449 / IFU) |
| 11 | `A_lock_11_pocket_+0.4.stl` | key-step pocket 0.4 larger on every side (clearance 0.7) and 0.4 deeper |

`A_lock_bed.stl`: all 11 coupons on one 280 x 240 bed (bed size 119 x 168 mm used). Coupon 19 x 52 x 10 mm.

**Print:** PETG or PLA, 0.4 nozzle, 0.15-0.2 layer, 3 perimeters, 15 % infill, face up (as exported), no supports (the groove ceiling is a ~1 mm overhang ring, it bridges). Brim off.

**Test order:** 1 (generous) first: if the adapter does not enter or turn even there, measure the adapter before printing more. Then 2 (nominal), then only the rows that address what misfits:
- nose does not enter / wobbles: 3 / 4 (bore);
- nose enters but the lugs hit the face: 7 (wider notches), 8 (keyed wide + narrow notch), 5 / 6 (notch angle);
- lugs drop in but do not turn / turn too freely: 9 (deeper groove) vs 2;
- the adapter does not sit flat: 10 (counterbore for a flange at the nose base), 11 (bigger key-step pocket).

**What to note per coupon:** enters at 90 deg (yes / no), turns clockwise to flush (yes / no / force), axial play when locked (mm, feeler), the adapter flush with both side faces and top / bottom, any rubbing (where). Then set `cart.receiver.*` / `cart.adapter.*` in `params.json` and regenerate.

## How the receiver works (variant A, nominal values)

1. **Bore:** the adapter's round nose (needle in its centre) drops into a d13.3 bore, 5.5 deep, on the cartridge axis (12.5 from the -Y end, centred in the 19). Below the bore the cartridge passes (d11.55); its crimp cap sits 1.0 below the seat plane, so the needle meets the septum on the axis.
2. **Entry notches:** two axial slots in the bore wall, 180 deg apart, at 90 deg (the adapter's long axis vertical, i.e. across the 19 face): the two lugs on the nose rim slide down them.
3. **Lug groove (bayonet undercut):** a ring groove r 7.7 from 1.95 to 3.65 below the seat plane (lug 1.2 thick at 2.2 below the seat, + 0.25 clearance each side). Turned clockwise by 90 deg, the lugs move under the groove's front wall: that is what holds the adapter **axially**.
4. **Lock angle / rotation stop:** at 0 deg (long axis along the 52 face) the adapter's key step (raised underside of its tubing half, 2.8 high) drops into the pocket in the face (y 21.2-50.1, z 1.9-17.1, 3.1 deep): it stops the turn and keeps the adapter from turning back; the adapter body then lies flush with the housing outline.
5. **Counterbore:** none in the nominal design (coupon 10 tests one for a flange at the nose base).
6. **Seal:** none. Water only, open bench; the original adapter has a vent and is not watertight either (manual p.36). The patent's pump has an O-ring on the housing face (US9554967B2 Fig. 4b, part 235), we do not.

## Which references set which dimension (all read as images, none committed; links in `docs/insight-research.md` §7.6)

| Dimension | Value used | References (distinct views) |
|---|---|---|
| Pump end face 52 x 19, length 84 | 52 x 19 x 84 | user manual App. A (text, VERIFIED) |
| Adapter = flush end cap, put on at 90 deg, clockwise to the stop | 90 deg entry, 0 deg lock | manual p.28 step 8, p.29 step 9, p.27 and p.36 removal (4 figures); US D689,523 Fig. 6 (1) |
| Nose OD | 13.0 (bore 13.3) | US D720,449 Figs 3, 5, 7 (3); Adapter & Tubing IFU figure (1) |
| Nose axis from the adapter end | 12.5 | US D720,449 Figs 3, 5 (2); manual p.29 underside view (1) |
| Lugs: count, position | 2, on the long axis when locked | US D720,449 Fig. 5 (1 view only) |
| Lug widths | CAD 1.6 both; patent reads ~5 and ~1.5 (keyed) -> coupon 8 | US D720,449 Fig. 5 (1) |
| Lug height 0.8, thickness 1.2, depth below the seat 2.2 | guesses | **no source** (not visible in any view) |
| Pump bore / counterbore / notch arc | patent reads ~11.7-12.4 / ~15-17 / 60-80 deg; CAD uses 13.3 / none / slots | US D689,523 Fig. 6 (1 view only) |
| Key step height and extent | 2.8, tubing half | US D720,449 Fig. 3 (1); manual p.29 side view (1); IFU (1) |
| Tubing exit | far end, 2 above the underside | US D720,449 Figs 1, 2, 5, 6, 8 (5) |
| Vent / seal | none in our receiver | US9554967B2 Figs 3, 4b (2); manual App. A + p.36 (text) |
| Overall look | | owner's product photo (1) |

In all: US D720,449 = 8 views on 4 sheets, US D689,523 = 1 figure, US9554967B2 = 2 figures, manual = 7 figures (p.2, p.27, p.28, p.29 x 3, p.36) + text, Adapter & Tubing IFU = its figures (count not recorded), 1 owner photo. The design patents are **unscaled**: every value was scaled from them with the VERIFIED 84 x 52 x 19 and is an ESTIMATE (+-1 mm). The biggest open conflict: nose ~13 vs pump bore ~12 in the patents.

There is **no seal** in this receiver (the original adapter is not watertight either, manual p.36; the pump end of the patent has an O-ring on the housing face). Axial hold = the lugs under the groove's front wall; rotation stop = the key step in its pocket.
