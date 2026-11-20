> **TEST ONLY - NOT FOR HUMAN USE** (see `../DISCLAIMER.md`). Water only, never worn.

# v0.1.0 "cup" pod (`generate.py --variant v010 --drive cup`, `check.py --variant v010 --drive cup`)

Files: `op_cup.py` (layout + CAD), `op_cup_dock.py` (dock, U-clip, hall), `cup_gen.py` (driver + renders), `cup_annotate.py`, `cup_check.py`, `cup_packing.py`, `cup_fab.py`; params in `params.json -> cup`.
Output: `out/v010-cup/` (iso with clear lid, exploded, top section at the tank axis, side section along lane 1, cross section through the dock, annotated top view, `fab/stencil/*.dxf`, `fab/dock-coupon/`, `reservoir-cnc/`).

## Layout A (user sketch, final)
Top view, +X right, +Y up. **Motor NFP-608-26.45 transverse (axis Y) is the last element at the rear and spans both lanes**; nothing behind it.
Lane 1 (bottom): miter gear B on the rod (rod ENDS at gear B; magnet on gear B's rear face, TMAG5273 beside it with 0.5 mm gap) -> bush + collar (thrust bearing) -> cup plunger -> tank (closed walls) -> front wall (fill septum on the UNDERSIDE, outlet straight through the wall into the needle hub) -> dock at the right end (needle +X into the cannula side septum).
Lane 2 (top): wire channel x 7.5-9.4, cell x 9.37-40.87 (lead end west), main board above it (z 5.3-6.1) with the USB-C mid-mount in a north-edge notch (opening x 18.8-28.2 in the +Y long wall), side button at x 30 on the +Y wall, antenna clearance east of the board; a keep-out in the rear corner of lane 1 (button, LED, buzzer, charger strip).
Exactly two gears (z16 / z16 miter, 1:1), one rod, no carriage, tongue, idler, end cap. The only moving seals are the two lip rings of the plunger.

| size | L x W x H (mm) | envelope | stroke | plunger | tank | bore | U/step |
|---|---|---|---|---|---|---|---|
| OP-100 | **47.96 x 34.6 x 8.5** | 14.1 ml | 9.4 mm | 12.6 mm | 24.9 mm | 20.5 x 5.5 | 0.00703 |
| OP-200 | **66.78 x 34.6 x 8.5** | 19.6 ml | 18.8 mm | 22.0 mm | 43.8 mm | 20.5 x 5.5 | 0.00703 |

Both PASS `check.py`; the 45 / 52 mm length and 32 mm width targets are MISSED (TARGET lines). Width 34.6: the transverse motor reaches 21.1 mm from the tank axis (gear stage + NFP body), so a 23 mm lane 1 forces W >= 34.6; lane 2 is cell width + 0.4 (11.0 mm with the placeholder cell) and the tank gets the rest (outer 21.5, bore 20.5 x 5.5; aspect 3.7). W = 32 would cap the bore at 16.7 (OP-100 50.2 mm earlier). Lane 2 can not be 6 mm: no real orderable cell is narrower than 10 mm (see battery below).

## Motor beside the tank / transverse options (analysis)
* Motor beside the tank with exactly two spur gears is impossible: the gear centre distance is limited to about 5.5 mm by the 6.7 mm cavity height (gear tip radius <= 3.3), the motor axis would lie inside the tank footprint.
* Worm + wheel: infeasible, the worm axis must be tangent to the wheel pitch circle, i.e. >= 4.2 mm above or below the rod axis (z > 8.5), and a self-locking worm (eta 0.3-0.4) gives about 3.3 N < 5 N.
* Miter / bevel pair 90 deg (built): 1:1, eta ~0.9, only height-neutral option. Catalogue candidates (all VERIFY, no link fetched in this session): GHW-Modellbau and Maedler miter/bevel gears module 0.3-0.5, KHK SMA/SM-series miter gears (module 0.5), AliExpress "mini miter gear 16T bore 2 mm". Module 0.3 z16 miter is NOT confirmed to exist as a catalogue item; fallback module 0.5 z10.

## Thrust (19 x 5.5 class plunger, estimate, VERIFY on the bench)
NFP-608-26.45: 1.6 gf cm x 26.45 x 0.64 = 2.65 N mm at the gearhead; miter 1:1 eta 0.9 -> 2.39 N mm at the rod; M1.6 x 0.35 screw eta 0.2 -> **8.6 N** at the plunger. Needed (bore 20.5 x 5.5, 106 mm2): seal breakaway 2.0 N (bench 1.6 N scaled by perimeter 48.6/37.7) + 30 kPa occlusion 3.2 N = **5.2 N**; available 8.6 N = **1.65x** (>= 1.5x rule met, requirement >= 5 N met, SF 2 = 10.4 N not met). Fix if short: miter pair z16 (motor) : z20 (rod) = ratio 0.8 -> 10.7 N (+25 %), U/step 0.0045, plunger 25 % slower; firmware preset g16-20 exists.
Plunger aspect 20.1 / 5.3 = 3.7 (limit 4.5); lip seals sit on the long flat sides as before (the stadium ring contacts the whole perimeter, oversize 0.15); anti-tilt: cup body 12.6 mm (OP-100) / 22 mm (OP-200) on a 20.5 mm width (L/W 0.62 / 1.08, check >= 0.5) plus two rings 3.25 mm apart; add guide fins if the bench shows yaw jamming.
Battery (`mechanical/battery-selection.md`): **Ampul 301030**, 3.0 x 10 x 30 mm, 90 mAh listed (60 mAh realistic per the Liter table), integrated protection chip, two wires, 4.00 EUR, https://ampul.eu/en/battery/6782-li-pol-battery-90mah-37v-301030 (page read; shipping to DE and the real size to be measured). Days per charge at 3.4 mAh/day (0.15 mA) with 0.85 x 0.8 derating: **about 12 days (60 mAh) to 18 days (90 mAh)**, far above 48 h + reserve; width, not capacity, is the limit. Backup: Soldered 350824 (40 mAh, JST-PH, BerryBase.de, about 8 days, dimensions to measure). Lane 2 stack (z): floor 0.9, cell 3.0 + 0.2 swell allowance (z 0.9-4.1), USB-C receptacle 3.26 mm stacked ABOVE the front end of the cell (z 4.2-7.46, opening in the +Y long wall, lid inner 7.6), main board 0.8 + parts <= 1.3 above the rest of the cell (z 4.2-6.4); the receptacle is soldered to the board by the PCBA, the cell wires run to the board edge (a PCM end of the cell needs a 1.5 mm tail, inside the 31.5 mm envelope). Lane 2 is then as long as the cell, so OP-100 returns to the lane-1 length.

## Board interface (board review 2026-11-20, `electronics/v010/cup/review/BOARD-SANITY-REVIEW.md`; all values in `mech.json -> elec_interface`)
Pod frame (x = 0 motor end, y = 0 tank-side wall, z = 0 skin side). Both sizes use the same lane-2 numbers; only screw E follows the dock.
| Item | Geometry |
|---|---|
| Main board | west edge x >= 7.8, east edge 43.4, y 22.9-33.5, z 5.3-6.1; top parts <= 7.55 (lid inner 7.6); bottom parts >= 4.12 over the cell, none over the wire channel (x < 9.4) |
| USB-C | mid-mount 8.94 x 7.35 x 3.26 centred x 23.5, z 5.7 (board mid-plane), receptacle y 26.35-33.7; wall opening x 18.8-28.2, z 4.0-7.4 (bottom + lid wall), gasket recess x 17.9-29.1, 0.4 deep. Keep-out bottom clipped to z 4.12 (cell envelope 4.1 incl. 0.2 swell): VERIFY the real receptacle underside |
| Cell | Ampul 301030 envelope x 9.37-40.87, y 22.8-33.4, z 0.9-4.1, lead end WEST (VERIFY-ON-SAMPLE) |
| Wire channel | x 7.5-9.37, full lane-2 width, floor to board underside: motor 4 + cell 2 wires (soldered, spec §1a exception) + TMAG strip |
| Supports (top z 5.3) | ledges d1.0 at (41.5, 24.3), (41.5, 32.1); wall shelf x 8.0-9.2, y 32.9-wall; part-free d1.6 pads (shelf: x 7.7-9.5, y 32.6-33.5) on BOTH board faces |
| Lid hold-down ribs | d1.0 at the two ledge points + wall rib x 8.0-9.2, y 32.9-wall, all from the lid roof down to z 6.1 (1.5 mm) |
| Board screws | 2 x M1.2 x 4 brass cheese head (ISO 1207 / DIN 84, head d2.0 x 0.8, top z 6.9), board hole d1.4 NPTH, part-free ring d2.8 both faces; boss d1.8 from the floor to z 5.3, thread-forming pilot d0.95 x 3.6 (z 1.7-5.3). **W (8.9, 21.5)** on a board tab x 7.8-10.0, y 20.1-22.9 between gearhead and tank; **E (37.40, 20.0)** in the side_b leg (OP-200: 56.22, 20.0 = dock front face + 2.24). No boss fits under the main body (cell = full lane width; east of the cell is < 3 mm from the HJ-840 antenna band x 42.85-43.4, y 24-32); screw distance to that band: W 34 mm, E 6.8 mm |
| Side button | SW1 actuator x 30.0 toward +Y; lid flex window x 29.4-31.5, z 5.6-6.7, 0.45 wall left, inner nub x 29.6-30.4, z 6.15-6.65, contact face y 33.4 (actuator tip must end at y <= 33.35). Probably too stiff, see ASSEMBLY-CUP |
| Lane-2 motor saddle | y 29.95-31.45, outer x <= 7.84, +X lip cut at z 5.2 (x 7.71 there), 230 degree wrap |
Not changed: the dock-pocket roof (z 4.45-4.9) stays 0.4 below the board; it is not used as a support (no boss added).

## Dock (all values TODO-MEASURE; head estimated from the photos by proportion: dome d8.0 x 4.2, base 9 x 9)
Bottom-open pocket 11.9 x 9.8 (head + 0.2 clearance + 3.5 slide), roof 0.5; the pod is lowered over the head and slid 3.5 mm (= needle insertion) until two U-clip teeth drop into the dome side notches. Footprint before (frozen insert + full-length tunnel): 21.2 x 15.2 insert/flange pocket and a 12.4 mm wide path along the whole pod; after: 11.9 x 9.8 (base-plate window 12.9 mm: a 9 mm base plate + slide; <= 12 needs a plate <= 8.1 mm; width 10 would need dome and plate <= 9.6).
U-clip: 301 FH 0.1 mm, b 2.4, arm 7.5 mm, DXF flat pattern in `fab/stencil/` (stencil sheets are usually 304/316L: order 301 FH foil or accept lower allowable). Allowable 650 MPa (0.65 Rp0.2); needed travel 0.7 mm -> 350 MPa, 0.185 N/clip; 1.8 mm travel would give 900 MPa (a 3.5 mm arm allows 0.28 mm; 1.8 mm needs >= 8.9 mm). Vertical tooth faces lock; release by lifting the teeth.
Needle: spring guard (0.3 N) covers the tip whenever no head is present (tip recessed 0.4 mm), tip z 2.6 above the underside. Dock hall: magnet d1 x 0.5 in the head, hall on the roof; dipole model: asserts only within 0.74 mm of the final position (the teeth drop 0.3 mm before the end).
The frozen dock interface keys in `params.json` are untouched (bench pod); the cup pod does not use the sliding insert; the coupon (`fab/dock-coupon/`) is rebuilt for the pocket + clip with 12 head variants (dome d x notch depth, `variants.csv` incl. clip stress).

## Tank (un-frozen for the cup variant, NOT ordered)
Bore 20.5 x 5.5 (stroke 9.4 mm for 100 U), wall 0.6, outer 21.5 x 6.7, front wall 2.5. Fill septum: d1.6 x 1.0 silicone in a d1.7 pocket from the underside at the lower front edge, d1.0 channel into the bore (a tilted bore is not modelled: SolidCraft cylinders are axis aligned; VERIFY with the CNC shop). Outlet: d0.8 straight through the front wall into the hub seat (d1.42 H7, press 0.08, 30G hub d1.5). Plunger reaches the front wall (gap 0.02): dead volume about 0.3 U (1 mm of plunger = 10.6 U). Data: `out/v010-cup/reservoir-cnc/reservoir_cnc.json`. The seal ring grooves are the S2 geometry of the bench plunger moved to the front of the cup; the moulds (`mould*.step`, 20.5 x 5.5 cavity) are regenerated per run in `out/v010-cup/`.
Refill (pressure fill, spec 3c): remove the pod, turn it over, push water with a syringe through the underside septum while the firmware retracts the plunger at a fixed rate; the fill hole is inside the Velcro footprint and outside the dock window (check H14); the pocket roof and the docked head cover nothing else.

## Checks (`check.py --variant v010 --drive cup`)
No interference, no open bodies, height <= 8.5; rod never inside the wet volume (analytic + CAD wet volumes at full / empty), plunger reaches the front wall, tip stays 0.4 mm off the cup bottom, tank volume = closed-bore model (no slot), septum not reachable when docked, needle recessed in the extended guard, dome path free, exactly two gears, nothing behind the motor column, thrust >= 5 N, packing (`cup_packing.py`): no empty full-height rectangle >= 4 x 4 mm (largest 23 mm2; free plan area lane 1 88 / lane 2 38 mm2 of 1007 / 508); the strips beside the dock pocket hold piezo / button / ICs.
Open: vent d0.8 + ePTFE in the lid, wire / TMAG strip paths (not modelled), button flex stiffness, dock hall threshold, CNC review.
