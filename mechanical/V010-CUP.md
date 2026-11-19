> **TEST ONLY - NOT FOR HUMAN USE** (see `../DISCLAIMER.md`). Water only, never worn.

# v0.1.0 "cup" pod (`generate.py --variant v010 --drive cup`, `check.py --variant v010 --drive cup`)

Files: `op_cup.py` (layout + CAD), `op_cup_dock.py` (dock, U-clip, hall), `cup_gen.py` (driver + renders), `cup_annotate.py`, `cup_check.py`, `cup_packing.py`, `cup_fab.py`; params in `params.json -> cup`.
Output: `out/v010-cup/` (iso with clear lid, exploded, top section at the tank axis, side section along lane 1, cross section through the dock, annotated top view, `fab/stencil/*.dxf`, `fab/dock-coupon/`, `reservoir-cnc/`).

## Layout A (user sketch, final)
Top view, +X right, +Y up. **Motor NFP-608-26.45 transverse (axis Y) is the last element at the rear and spans both lanes**; nothing behind it.
Lane 1 (bottom): miter gear B on the rod (rod ENDS at gear B; magnet on gear B's rear face, TMAG5273 beside it with 0.5 mm gap) -> bush + collar (thrust bearing) -> cup plunger -> tank (closed walls) -> front wall (fill septum on the UNDERSIDE, outlet straight through the wall into the needle hub) -> dock at the right end (needle +X into the cannula side septum).
Lane 2 (top): cell (4 mm thick class), main board above it, USB-C in the +Y long wall, piezo / button / aux, length-matched; a keep-out in the rear corner of lane 1 (button, LED, buzzer, charger strip).
Exactly two gears (z16 / z16 miter, 1:1), one rod, no carriage, tongue, idler, end cap. The only moving seals are the two lip rings of the plunger.

| size | L x W x H (mm) | envelope | stroke | plunger | tank | bore | U/step |
|---|---|---|---|---|---|---|---|
| OP-100 | **47.96 x 34.6 x 8.5** | 14.1 ml | 9.4 mm | 12.6 mm | 24.9 mm | 20.3 x 5.5 | 0.00703 |
| OP-200 | **66.78 x 34.6 x 8.5** | 19.6 ml | 18.8 mm | 22.0 mm | 43.8 mm | 20.3 x 5.5 | 0.00703 |

Both PASS `check.py`; the 45 / 52 mm length and 32 mm width targets are MISSED (TARGET lines). Width 34.6: the transverse motor reaches 21.1 mm from the tank axis (gear stage + NFP body), so a 23 mm lane 1 forces W >= 34.6; lane 2 is cell width + 0.4 (11.0 mm with the placeholder cell) and the tank gets the rest (outer 21.5, bore 20.3 x 5.5; aspect 3.7). W = 32 would cap the bore at 16.7 (OP-100 50.2 mm earlier). Lane 2 can not be 6 mm: no real orderable cell is narrower than 10 mm (see battery below).

## Motor beside the tank / transverse options (analysis)
* Motor beside the tank with exactly two spur gears is impossible: the gear centre distance is limited to about 5.5 mm by the 6.7 mm cavity height (gear tip radius <= 3.3), the motor axis would lie inside the tank footprint.
* Worm + wheel: infeasible, the worm axis must be tangent to the wheel pitch circle, i.e. >= 4.2 mm above or below the rod axis (z > 8.5), and a self-locking worm (eta 0.3-0.4) gives about 3.3 N < 5 N.
* Miter / bevel pair 90 deg (built): 1:1, eta ~0.9, only height-neutral option. Catalogue candidates (all VERIFY, no link fetched in this session): GHW-Modellbau and Maedler miter/bevel gears module 0.3-0.5, KHK SMA/SM-series miter gears (module 0.5), AliExpress "mini miter gear 16T bore 2 mm". Module 0.3 z16 miter is NOT confirmed to exist as a catalogue item; fallback module 0.5 z10.

## Thrust (19 x 5.5 class plunger, estimate, VERIFY on the bench)
NFP-608-26.45: 1.6 gf cm x 26.45 x 0.64 = 2.65 N mm at the gearhead; miter 1:1 eta 0.9 -> 2.39 N mm at the rod; M1.6 x 0.35 screw eta 0.2 -> **8.6 N** at the plunger. Needed (bore 20.3 x 5.5, 106 mm2): seal breakaway 2.0 N (bench 1.6 N scaled by perimeter 48.6/37.7) + 30 kPa occlusion 3.2 N = **5.2 N**; available 8.6 N = **1.65x** (>= 1.5x rule met, requirement >= 5 N met, SF 2 = 10.4 N not met). Fix if short: miter pair z16 (motor) : z20 (rod) = ratio 0.8 -> 10.7 N (+25 %), U/step 0.0045, plunger 25 % slower; firmware preset g16-20 exists.
Plunger aspect 20.1 / 5.3 = 3.7 (limit 4.5); lip seals sit on the long flat sides as before (the stadium ring contacts the whole perimeter, oversize 0.15); anti-tilt: cup body 12.6 mm (OP-100) / 22 mm (OP-200) on a 20.3 mm width (L/W 0.62 / 1.08, check >= 0.5) plus two rings 3.25 mm apart; add guide fins if the bench shows yaw jamming.
Battery: placeholder 401012 class (4.0 x 10 x 12 mm, 40 mAh, integrated PCM, ampul.eu listing 3.23 EUR, VERIFY) = about 8 days per charge at 3.4 mAh/day with 0.85 x 0.8 derating; 401030 (80 mAh, AS-Power listing, VERIFY) about 16 days but 32 mm long (+6 mm pod). The final cell comes from `mechanical/battery-selection.md` (separate research); only `cup.battery` in `params.json` changes, lane 2 and the tank follow automatically.

## Dock (all values TODO-MEASURE; head estimated from the photos by proportion: dome d8.0 x 4.2, base 9 x 9)
Bottom-open pocket 11.9 x 9.8 (head + 0.2 clearance + 3.5 slide), roof 0.5; the pod is lowered over the head and slid 3.5 mm (= needle insertion) until two U-clip teeth drop into the dome side notches. Footprint before (frozen insert + full-length tunnel): 21.2 x 15.2 insert/flange pocket and a 12.4 mm wide path along the whole pod; after: 11.9 x 9.8 (base-plate window 12.9 mm: a 9 mm base plate + slide; <= 12 needs a plate <= 8.1 mm; width 10 would need dome and plate <= 9.6).
U-clip: 301 FH 0.1 mm, b 2.4, arm 7.5 mm, DXF flat pattern in `fab/stencil/` (stencil sheets are usually 304/316L: order 301 FH foil or accept lower allowable). Allowable 650 MPa (0.65 Rp0.2); needed travel 0.7 mm -> 350 MPa, 0.185 N/clip; 1.8 mm travel would give 900 MPa (a 3.5 mm arm allows 0.28 mm; 1.8 mm needs >= 8.9 mm). Vertical tooth faces lock; release by lifting the teeth.
Needle: spring guard (0.3 N) covers the tip whenever no head is present (tip recessed 0.4 mm), tip z 2.6 above the underside. Dock hall: magnet d1 x 0.5 in the head, hall on the roof; dipole model: asserts only within 0.74 mm of the final position (the teeth drop 0.3 mm before the end).
The frozen dock interface keys in `params.json` are untouched (bench pod); the cup pod does not use the sliding insert; the coupon (`fab/dock-coupon/`) is rebuilt for the pocket + clip with 12 head variants (dome d x notch depth, `variants.csv` incl. clip stress).

## Tank (un-frozen for the cup variant, NOT ordered)
Bore 20.3 x 5.5 (stroke 9.4 mm for 100 U), wall 0.6, outer 21.5 x 6.7, front wall 2.5. Fill septum: d1.6 x 1.0 silicone in a d1.7 pocket from the underside at the lower front edge, d1.0 channel into the bore (a tilted bore is not modelled: SolidCraft cylinders are axis aligned; VERIFY with the CNC shop). Outlet: d0.8 straight through the front wall into the hub seat (d1.42 H7, press 0.08, 30G hub d1.5). Plunger reaches the front wall (gap 0.02): dead volume about 0.3 U (1 mm of plunger = 10.6 U). Data: `out/v010-cup/reservoir-cnc/reservoir_cnc.json`. The seal ring grooves are the S2 geometry of the bench plunger moved to the front of the cup; the moulds (`mould*.step`, 20.3 x 5.5 cavity) are regenerated per run in `out/v010-cup/`.
Refill (pressure fill, spec 3c): remove the pod, turn it over, push water with a syringe through the underside septum while the firmware retracts the plunger at a fixed rate; the fill hole is inside the Velcro footprint and outside the dock window (check H14); the pocket roof and the docked head cover nothing else.

## Checks (`check.py --variant v010 --drive cup`)
No interference, no open bodies, height <= 8.5; rod never inside the wet volume (analytic + CAD wet volumes at full / empty), plunger reaches the front wall, tip stays 0.4 mm off the cup bottom, tank volume = closed-bore model (no slot), septum not reachable when docked, needle recessed in the extended guard, dome path free, exactly two gears, nothing behind the motor column, thrust >= 5 N, packing (`cup_packing.py`): no empty full-height rectangle >= 4 x 4 mm (largest 23 mm2; free plan area lane 1 88 / lane 2 40 mm2 of 1007 / 508); the strips beside the dock pocket hold piezo / button / ICs.
Open: closure screws / gasket are not detailed (no free bosses beside the full-width tank), vent d0.8 + ePTFE in the lid, FPC/solderless links between the keep-outs, dock hall threshold, CNC review.
