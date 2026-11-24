> **TEST ONLY - NOT FOR HUMAN USE** (see `../DISCLAIMER.md`). Bench only, **water only**: the cartridge is never filled with insulin or any other drug, and the tubing ends in a container on a scale, never on a person.

# v0.1.0 "cart" pump: Insight-class cartridge + original Insight adapter (`cart_gen.py`, `cart_check.py`)

A second, simpler OpenPatch variant next to the cup pod (`V010-CUP.md`). It is a small **tubed** bench pump: a bought Accu-Chek Insight-class 1.6 ml glass cartridge, the **original Accu-Chek Insight Adapter & Tubing** locked into a bayonet receiver, our NFP-608-26.45 geared stepper, the Ampul 301030 cell, USB-C, and the **cup-pod main board unchanged**.
Research and sources: `../docs/insight-research.md`. **No cartridge or adapter drawing is public: every cartridge / adapter number below is an ESTIMATE until measured on a sample** (list at the end).

Files: `op_cart.py` (layout + CAD), `cart_gen.py` (driver, exports, renders), `cart_check.py` (checks), `cart_compare.py` (size figure); parameters in `params.json -> cart`. Output: `out/v010-cart/` (`OP-CART.sc`, assembly STEP, per-part STEP + STL for bottom, top, slider, pusher, lock flag, lid gasket, `OP-CART.mech.json`, `check.json`, renders).
Separate scripts on purpose: the cup files (`generate.py`, `check.py`, `op_cup*.py`, `cup_*.py`) are not touched.

```
SOLIDCRAFT_CLI=/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli python3 cart_gen.py      # ~10 s incl. renders
python3 cart_check.py                                                                               # PASS / FAIL, writes check.json
python3 cart_gen.py --set cart.cartridge.od=11.2 --set cart.receiver.bore_d=12.4                    # after measuring a sample
```

## What is simpler than the cup pod
| Cup pod | Cart pump |
|---|---|
| custom stadium tank (CNC), cast cup plunger + 2 lip seals, fill septum, pressure-fill procedure | **bought glass cartridge with its own stopper and septum**; nothing wet is made by us |
| dock pocket, U-clip, spring needle guard, 30G needle + hub, cannula fit coupon | **original Insight adapter** (needle, vent, tubing) in a two-lug bayonet socket |
| miter pair, magnet clash, sealed rod-in-plunger nut | one spur pair, one nut bonded in the gear, one translating rod |
| patch on the body (8.5 mm) | tubed bench unit (15.2 mm); no on-body use in any case |
| new PCB per housing change | **same main board** (`electronics/v010/cup`, routed, DRC 0), same firmware hardware |

## Layout (top view, +X toward the adapter, +Y toward the USB-C wall; z = 0 underside)
**Lane 1 (cartridge axis, y 7.35, z 7.35):** rear wall -> U channel with the printed anti-rotation **slider** bonded on the rod end (x 1.1-4.1 at FULL, travels the stroke) -> rear rib (x 26.05) -> washer -> **gear nut** = brass spur gear m0.3 z40 (tip d12.6, x 27.25-29.25) with an M2 brass nut bonded in a hex pocket -> washer -> front rib (x 29.45-30.45) -> printed **pusher disc** d9.0 on the rod front end -> **stopper** -> **cartridge** (x 31.05-67.05, neck to 71.55) in two U cradles -> **receiver collar** (x 69.3-75.8) with the adapter bayonet -> **adapter** outside (to x 82.3) + tubing.
**Lane 2:** motor NFP-608-26.45 **parallel to the rod** in the tail zone (x 9.55-27.15, axis y 15.15), pinion m0.3 z12 on the D-shaft flush with the gear, diametric d2 x 1 magnet on the pinion face, TMAG5273 strip in front of it (x 30.75-32.8; same sensor and strip as the cup pod) -> the **cup main board** 35.6 x 12.6 x 0.8 (x 33.4-69.0, y 13.95-26.55, z 5.3-6.1, parts 4.12-7.55) with the **Ampul 301030** under it (x 35.1-66.6, z 0.9-4.1) and the USB-C mid-mount in the +Y wall (opening x 44.4-53.8, z 4.0-7.4; board-relative position as in the cup pod) -> adapter-lock hall at the front wall.
Motor and cell wires reach the board's west-end pads exactly as in the cup pod (spec §1a soldering exception).

Renders: `out/v010-cart/OP-CART_iso.png`, `_iso_lid_off.png`, `_exploded.png`, `_section_side_axis.png` (rod / gear / cartridge stack), `_section_top_axis.png`, `_section_cross_gear.png`, `_section_cross_receiver.png`, `size_comparison.png`.

## Size (CAD, check PASS)
| | L x W x H (mm) | box volume | note |
|---|---|---|---|
| **OpenPatch cart pump, body** | **75.8 x 27.65 x 15.2** | 31.9 ml | front set by the board east edge + collar (cartridge alone would allow 72.55) |
| **OpenPatch cart pump, with adapter** | **82.3 x 27.65 x 15.2** | 34.6 ml | adapter body estimate 14.0 x 6.5 outside |
| Accu-Chek Insight, with adapter | 84 x 52 x 19 | 83 ml | user manual App. A, VERIFIED |
| mylife YpsoPump (same cartridge class) | 78 x 46 x 16 | 57 ml | ESTIMATE (search excerpt) |
| Omnipod DASH / 5 pod | 52 x 39 x 14.5 | 29 ml | Insulet chart, VERIFIED (patch, 200 U) |
| OpenPatch cup pod OP-100 | 47.96 x 36.6 x 8.5 | 14.9 ml | `V010-CUP.md` (patch, 100 U) |

The cart pump is smaller than the Insight in every axis: -1.7 mm long (with adapter), **-24 mm narrow**, **-3.8 mm thin**, **42 % of its box volume**. Length is set by the glass cartridge (36 mm barrel + neck, ESTIMATE) plus the stroke behind it (21.65 mm) - the price of a non-telescopic rod. Height is set by the receiver bore 12.6 (adapter nose estimate 12.4) and the z40 gear tip circle 12.6; the bayonet groove lies only in the +-Y flank sectors (+-55 deg) so the lugs do not add height. The 15.0 mm height goal is missed by 0.2 (TARGET line in `cart_check.py`).

## Drive
* **Principle:** gear nut fixed axially, threaded rod translating (anti-rotation slider in a U channel). The rod is behind the stopper at all times, so it is never wet. A rotating rod with a translating nut would need the rod to pass through the stopper at FULL; that is why the rod translates.
* **Parts:** pinion m0.3 z12 (bore 2.0 on the NFP D-shaft, Loctite 648), gear m0.3 z40 (centre distance 7.8 = m (z1 + z2) / 2), DIN 975 M2 x 0.4 rod 29.55 mm long, DIN 934 M2 brass nut (AF 4.0, h 1.6) bonded in the gear, two 0.2 mm washers (PTFE or brass) against the ribs. Both ribs have U slots open to the top: the rod + gear + nut subassembly drops in from above and the lid ribs cap the slots (no press fits, no tools).
* **Axial load path:** stopper -> pusher -> rod -> thread -> nut -> gear -> rear washer -> rear rib -> tub. Reverse (retract): gear -> front washer -> front rib. The cartridge is held forward by the adapter (bayonet lugs -> collar) and backward by the front rib (0.2 mm gap behind it).
* **Resolution:** 0.4 mm / (20 x 26.45 x 40/12) x 73.9 mm2 = **0.00168 U per full step** (0.0168 ul; 1 U = 596 steps). Firmware needs a new drive preset (bore area 73.9, ratio 12:40, pitch 0.4): follow-up, not part of this change.
* **Thrust (`cart_check.thrust`, estimates):** NFP pull-out 2.65 N mm x 40/12 x 0.95 = 8.4 N mm at the nut; M2 x 0.4 at eta 0.25 -> **33.0 N**. Need: stopper breakaway 8 N (ESTIMATE, measure) + 150 kPa occlusion design point on 73.9 mm2 (11.1 N) = 19.1 N -> **1.73x** (rule >= 1.5x met). The stall force corresponds to **447 kPa** on the cartridge, above the Insight's 350 kPa maximum: occlusion must be detected by the firmware (TMAG angle shortfall, as in the cup pod) long before stall; the bench rig adds a pressure gauge.
* **Stroke:** 1.6 ml / 73.9 mm2 = 21.65 mm; available in the estimated barrel 28.0 mm. At EMPTY the rod rear end is still 4.5 mm behind the nut and the slider 0.3 mm off the rear rib (`cart_check` moves rod, slider, pusher and stopper to EMPTY and re-runs the interference check).

## Adapter receiver and lock detection
* Bore d12.6 for the adapter nose (5.5 deep), two axial entry channels at -45 / 135 deg, lug groove over the 90 deg turn to the lock position 45 / 225 deg, all ESTIMATE (`cart.receiver`, `cart.adapter`). The manual describes a clockwise turn to a stop, flush with the housing, with 90 and 120 deg marks: measure and set `entry_deg` / `lock_deg`. Expect to print a **receiver fit coupon** first (only the collar, 4-6 variants of bore and groove), like the dock coupon of the cup pod: follow-up.
* The adapter carries the forward thrust of the cartridge and presses the cap against its own nose; we do not modify the adapter. Its needle pierces the septum when it is seated; the alignment comes from the nose in the bore (manual: the needle must meet the septum centrally and perpendicularly).
* **Adapter locked = the existing DOCKED input.** A printed clip-on flag on the adapter body carries a d1 x 0.5 magnet; a DRV5032 just inside the front wall (x 73.7-74.8, y 15.95, on a 3-wire pigtail to the board's dock-hall pads, VERIFY whether the board's own DRV5032 can see it instead) reads it in the locked position only. The interlock stays as it is: **motor supply = MCU_EN AND watchdog latch AND supervisor permit AND (LOCKED XOR DIR_REVERSE)**: forward only with the adapter locked, rod retraction (cartridge change) only with the adapter off, TPS2553 over-current clears the latch (`electronics/v010/INTERLOCK.md`).

## Electronics reuse
Same board, same parts and nets: HJ-840 nRF52840, STM32C011 supervisor, TPL5010 watchdog latch, TPS2553 load switch, TPS61023 boost, 2 x DRV8838, MCP73832 charger, USB-C (DFU + charging), RGB LED, side button (lid flex window at x 58.6 on the +Y wall: not modelled yet), sounder, TMAG5273 on its strip. Only the housing interface differs: board supported by 3 floor ledges (part-free d1.6 pads) and 1 lid rib; the two M1.2 board screws of the cup pod are not modelled yet (open item). Antenna end (east) faces the plastic collar, no metal within 0.3 mm.

## Assembly (bench)
1. Bond the M2 brass nut into the z40 gear hex pocket (CA); press the z12 pinion on the NFP shaft (Loctite 648); bond the angle magnet on the pinion face.
2. Screw the M2 rod through the gear nut, bond the slider on its rear end and the pusher disc on its front end.
3. Snap the motor into its two saddles, drop the rod / gear subassembly with both washers into the rib slots (slider into the U channel); check the mesh by hand.
4. Fit the cell, solder motor and cell wires to the board pads (spec §1a exception), lay the board on its ledges, TMAG strip and lock hall in place, lid with gasket, screws.
5. Cartridge change (water only): adapter off -> firmware retracts the rod (reverse allowed only without the adapter) -> empty cartridge out of the front bore -> new cartridge filled with water, stopper first -> adapter on, turn to the stop -> firmware advances until the pusher touches the stopper (current / angle shortfall) -> prime into the container.

## Checks (`cart_check.py`, all PASS 2026-11-24)
No interference at FULL and at EMPTY (moving parts copied at the end of stroke; a negative test with `--set cart.travel_margin=-1.0` fails as it should), housing closed, height below the Insight (19) and length / width below it, stroke <= available travel, rod engaged in the nut over the whole stroke, slider inside its channel, rod / pusher never in the wet volume, gear centre distance = m (z1 + z2) / 2, pinion tip clear of the rod, gear tip clear of the floor, thrust >= 1.5x need, board envelope identical to `cup.board`, all exports present.
Not checked / not modelled: gear teeth (envelopes only, the pair is an EXCLUDE pair), board screws, button window, vent, wire paths, tolerance stack of the bayonet.

## Open items
1. **Measure a sample** (see `../docs/insight-research.md`): cartridge OD / ID / length / neck / cap / stopper; adapter nose, lugs, rotation angle, needle; stopper breakaway and glide force with water. Update `params.json -> cart`, regenerate, re-check.
2. Confirm that an empty YpsoPump Reservoir fits and seals with the Insight adapter (1 bar water hold); otherwise find an empty Insight-format cartridge.
3. Receiver fit coupon (collar only, variant set), then freeze `cart.receiver`.
4. Board screws (2 x M1.2 as in the cup pod) and the side-button flex window in the +Y lid wall; vent with ePTFE.
5. Firmware drive preset for the cart (U/step 0.00168, bore 73.9 mm2), "find the stopper" routine after each cartridge change, occlusion threshold well below the 447 kPa stall pressure.
6. Patent: US9205190B2 (Roche, active to about 2029) describes a gear wheel threaded on a piston rod; read claim 1 before any publication of hardware beyond this bench study (`../docs/insight-research.md` §6).
7. Optional size reduction: a telescopic rod would cut about 15 mm of length; a new board outline over the tail zone could cut the width to about 19 mm. Both cost the "reuse unchanged" simplicity and are not pursued now.
