> **TEST ONLY - NOT FOR HUMAN USE** (see `../DISCLAIMER.md`). Bench only, **water only**: the cartridge is never filled with insulin or any other drug; the line ends in a container on a scale, never on a person.

# v0.1.0 "cart" pump: Insight cartridge, variants A and B (`cart_gen.py`, `cart_check.py`)

A small, minimal tubed bench pump. The reservoir is the **Accu-Chek Insight 1.6 ml glass cartridge** (ISO 13926-1 cartridge family). Nothing wet is made by us.
| Variant | On the cartridge | Tubing / site end |
|---|---|---|
| **A** | the **original Accu-Chek Insight Adapter & Tubing** (needle, vent and tubing in one part), locked in our bayonet receiver | Insight tubing -> Insight Flex head set |
| **B** | our **printed bayonet cap**: it centres a standard Luer-lock hypodermic needle (27G, 0.40 x 12 mm) on the septum and presses the crimp cap | needle hub (female Luer) -> Luer tubing set (Accu-Chek FlexLink, Luer pump end) -> head set; Insight Flex compatibility UNVERIFIED (`../docs/insight-research.md` §7) |
The housing, drive and electronics are **identical** for A and B; only the part in the receiver differs.

Research: `../docs/insight-research.md`. Parameters: `params.json -> cart` (+ `cart.variants.A / B`). Code: `op_cart.py` (layout + CAD), `cart_gen.py` (exports, print kit, coupons, renders), `cart_check.py` (checks), `cart_compare.py` (size figure). The cup files are not touched.
```
SOLIDCRAFT_CLI=/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli python3 cart_gen.py      # A + B + coupons, ~20 s with renders
python3 cart_check.py                                                                               # A + B, PASS / FAIL
python3 cart_gen.py --set cart.cartridge.od=11.1 --set cart.receiver.bore_d=13.2                    # after measuring
```

## Size (CAD, both PASS)
| | L x W x H (mm) | box | source |
|---|---|---|---|
| **Cart pump A/B, housing** | **72.8 x 27.25 x 16.1** | 31.9 ml | this CAD (FDM walls 1.2) |
| Cart pump A, with the Insight adapter | 79.3 x 27.55 x 16.1 | 34.8 ml | adapter protrusion 6.5 = ESTIMATE |
| Cart pump B, with the printed cap / with hub + Luer collar | 82.1 / 95.3 x 27.25 x 16.1 | | the 12 mm needle + 11 mm hub sit outside |
| **Accu-Chek Insight, with adapter** | **84 x 52 x 19** | 83 ml | user manual App. A, **VERIFIED** (body without adapter about 72: ESTIMATE) |
| mylife YpsoPump | 78 x 46 x 16 | 57 ml | search excerpt |
| Omnipod DASH / 5 | 52 x 39 x 14.5 | 29 ml | Insulet, VERIFIED |
| OpenPatch cup pod OP-100 | 47.96 x 36.6 x 8.5 | 15 ml | `V010-CUP.md` |
A is smaller than the Insight in every axis (with adapter 79.3 vs 84, 27.25 vs 52, 16.1 vs 19) and is 42 % of its box volume. The 15 mm height goal is missed: the height comes from the receiver bore 12.9 + 2 x (0.15 + 1.2 + 0.5 gasket).

## Length stack (lane 1, this is what sets the length)
| Item | mm | Note |
|---|---|---|
| rear wall + clearance | 1.2 + 0.2 | FDM wall |
| anti-rotation slider | 2.5 | printed, bonded on the rod |
| **stroke** (rod tail at FULL) | **23.81** | 1.6 ml / 67.2 mm2 (ID 9.25) |
| travel margin | 0.3 | |
| rear rib + washer + gear nut + washer + front rib | 1.0 + 0.2 + 2.0 + 0.2 + 1.0 | gear m0.3 z40 with the M2 nut |
| pusher clearance + pusher | 0.2 + 1.2 | |
| stopper recess (overlap) | -0.8 | stopper rear face 0.8 inside the barrel |
| **cartridge barrel** | **33.5** | ESTIMATE (stopper 6.5 + stroke + shoulder) |
| neck + crimp cap | 5.3 | ISO h1 5.0 + crimp |
| cap face to housing front (adapter seat) | 1.0 | ESTIMATE |
| **total** | **72.81** | |
What limits it: **cartridge (38.8) + stroke (23.8) = 62.6 mm, 86 % of the length.** The rod must sit behind the stopper at FULL, because the stopper is a plain rubber plug (nothing can key a nut inside the glass), so a non-telescopic drive always has that tail. Already done: motor **beside** the rod (in the tail zone, not in line), board **over** the motor and cell (lane 2 no longer sets the length; it did until today, 76.1), cell **under** the pinion / TMAG strip, 0.2-0.3 mm clearances only. Next step if it must get shorter: a **two-stage telescopic screw** (tube + rod, keyed tube) would cut the tail to about half the stroke plus the nut length: about **-9 to -10 mm** (63 mm housing), at the cost of a custom threaded tube. Not done for the fit print (owner: keep it minimal).

## Dimensions of every part and interface (pod frame: x = 0 rear face, y = 0 cartridge-side wall, z = 0 underside)
| Part / interface | Dimensions (mm) | Status |
|---|---|---|
| Cartridge barrel | OD 10.95, ID 9.25, length to the shoulder 33.5 | OD / ID = ISO 13926-1 1.6 ml row (SCHOTT table, VERIFIED for the ISO row); that the Insight cartridge is that row and the length: **MEASURE** |
| Cartridge neck / crimp cap | neck d5.5, collar d7.15, h1 5.0 (h2 2.9); cap d7.8 x 3.2 | neck / collar VERIFIED (ISO, shared by all rows); cap OD **MEASURE** |
| Stopper | d9.25 x 6.5, rear face 0.8 inside the barrel at FULL | ESTIMATE, **MEASURE** |
| Cartridge seat | 2 U cradles (x +3 / +18 from the cartridge rear), bore 11.55 (+0.3 per side); axis y 7.8, z 7.8; cartridge x 33.0-66.5, neck to 71.8 | FDM fit, coupon 11.0-11.8 |
| Receiver (adapter seat), lane-1 collar | x 66.3-72.8, bore 12.9 x 5.5 deep from the front face, lug groove r 7.5 in +-55 deg sectors around +-Y, entry channels at -45 / 135 deg, lock at 45 / 225 deg (90 deg turn) | ESTIMATE (manual: bayonet, clockwise to the stop, 90 / 120 deg marks); coupons 12.6 / 12.9 / 13.2 |
| Insight adapter (A) | nose d12.4 x 5.5, lugs 2 x (1.6 wide, 0.8 high, 1.2 long, 2.2 behind the seat face), body d14 x 6.5 outside | ESTIMATE, **MEASURE** |
| Needle cap (B, printed) | same nose + lugs as A; cap pocket d8.1 to the crimp cap face; needle hole d0.7; hub seat d4.65 x 0.8; body d14, ends at x 82.1 | ours; hub numbers ESTIMATE |
| Needle + hub (B, bought) | 27G 0.40 x 12 mm (B. Braun Sterican type), tip 2.5 past the cap face; hub nose d4.4 x 3, body d7.6, hub length 11 | ESTIMATE, **MEASURE** |
| Piston rod | M2 x 0.4 DIN 975, x 1.4-32.6 at FULL (31.2 long), travels 23.8 | catalogue |
| Gear nut / pinion | m0.3 z40 (tip d12.6, face 2.0, x 29.2-31.2) with M2 nut AF 4.0 x 1.6 bonded; pinion m0.3 z12 (tip d4.2) on the motor shaft; centre distance 7.8 | catalogue (listings in BUY-LIST §7) |
| Ribs | rear x 28.0-29.0, front x 31.4-32.4, U slots 2.5 wide open to the top (drop-in drive), lid ribs cap them | ours |
| Slider / channel | 3.2 x 3.2 x 2.5 in a 3.6 wide U channel x 1.2-28.0 | ours (FDM +0.2) |
| Pusher | d9.0 x 1.2, rod pocket d2 x 0.9 | ours |
| Motor | NFP-608-26.45: can d6, x 11.5-29.1 (tail, motor, gearhead, boss), axis y 15.6 / z 7.8, two snap saddles | datasheet (VERIFIED in `params.json` drive_presets) |
| Angle sensor | magnet d2 x 1 on the pinion face, TMAG5273 strip x 32.7-34.8 | as cup pod |
| **Board (new outline, same chip set)** | **60.0 x 10.6 x 0.8**, x 6.0-66.0, y 14.55-25.15, pcb z 12.1-12.9, top parts <= 1.45, bottom parts <= 1.2 (over the motor and cell); 3 posts from the floor + 1 lid rib | outline = this CAD; 1.42x the cup board area, so 4 layers may route (VERIFY in KiCad) |
| Cell | Ampul 301030 envelope 31.5 x 10.6 x 3.2, x 28.9-60.4 on the floor, under the pinion / strip and the board | VERIFY on the sample (owner has it) |
| USB-C | mid-mount 8.94 x 7.35 x 3.26 on the board north edge, centre x 50.0, z 12.5; wall opening 9.4 x 3.4 | as cup board part |
| Button | sealed cap in the +Y wall at x 60.5, z 11.45 (side switch on the board underside, actuator +Y): hole d2.5, outside recess d5.3 x 0.8; cap = head d5.0 (+0.3 dome), stem d2.4, barb d3.2 x 0.5 | ours; print TPU 95A or cast silicone A40 |
| Adapter-lock hall | DRV5032 at x 70.4-71.5, y 16.7 (pigtail), magnet d1 x 0.5 on a clip-on flag at r 8.9 | VERIFY |
| Lid screws | 3 x M2 x 8 from the UNDERSIDE (flush counterbores d4.1 x 1.0), into d1.6 pilots of lid bosses d3.6: (3.8, W-3.8), (L-3.8, W-3.8), (14.0, 3.05) | ours |
| Shell | walls 1.2, vertical corners R4.0, top and bottom edges R1.0, flat 0.5 silicone gasket on the split z 14.4, flat lid 1.2 | ours |

## Drive (unchanged principle)
Gear nut fixed axially between two ribs, M2 rod translating, anti-rotation slider; the rod stays behind the stopper (never wet). U/step 0.4 / (20 x 26.45 x 40/12) x 67.2 = **0.00152 U**. Thrust estimate 33 N vs need 18.1 N (8 N stopper ESTIMATE + 150 kPa) = 1.83x; stall about 490 kPa (Insight max 350), so firmware occlusion detection (angle shortfall) must act well before stall.
**Motor choice (owner: free choice, cheap):** the comparison is in BUY-LIST §7b. Summary: the NFP-608 + 3.33:1 spur stage has the lowest and most bounded stall force; a 10 mm geared stepper (GM12-10BY, 1:20-1:30, about 9 EUR delivered) is cheaper and would drive the M2 rod almost directly, but its holding torque is about 4x its pull-out torque (90-140 N on the rod when blocked) and it needs firmware stall detection and a reduced coil voltage; DC gearmotors with encoders are rejected (stall force unbounded with the DRV8838). Kept: NFP-608 in the fit print (dummy).

## Interlock / electronics
Same chip set and interlock as the cup board: motor supply = MCU_EN AND watchdog latch (TPL5010) AND supervisor permit AND (ADAPTER LOCKED XOR DIR_REVERSE); the cup board's dock hall becomes the adapter-lock hall on a pigtail; TPS2553 over-current clears the latch. New board outline only (`electronics/` follow-up: route a 60 x 10.6 board, 4 layers if possible).

## Fit print (tomorrow): what to print and how
Files: `out/v010-cart/coupons/`, `out/v010-cart/A/print/`, `out/v010-cart/B/print/` (every STL laid flat and moved to the origin; sizes in `print_kit.json`).
1. **Coupons first** (PLA/PETG, 0.2 layer, 15 min): `coupon_cartridge_bore_ladder.stl` (holes 11.0 / 11.2 / 11.4 / 11.6 / 11.8, notch count 1-5 from small to large): the cartridge must slide in with a light touch; `coupon_receiver_bore_12.6/12.9/13.2.stl` (notches 1-3): the Insight adapter nose must enter, turn about 90 deg clockwise to the stop and sit firm. Enter the winners: `cart.cradle_clr = (hole - OD) / 2`, `cart.receiver.bore_d`, then regenerate.
2. **Housing** (PETG preferred, 0.4 nozzle, 0.15-0.2 layer, 3 perimeters, 20 % infill): `print_bottom.stl` floor on the bed (supports only under the USB-C / button openings if your slicer asks); `print_lid.stl` outer face on the bed, bosses up.
3. **Small parts**: `print_slider`, `print_pusher` (0.1 layer), `print_lock_flag`, `print_button_tpu` (TPU 95A, head down), variant B `print_b_cap` (nose down, 0.1 layer, PETG).
4. **Dummies** (any material): `dummy_board` (60.0 x 10.6 board + part envelope + USB-C block), `dummy_cell`, `dummy_motor`, `dummy_gear`, `dummy_pinion`, `dummy_cartridge` (use the real cartridge if you have it).
Tolerances built in: +0.3 per side on the cartridge cradle, +0.25 on the lug groove and entry channels, +0.2 on the slider channel, +0.05 on the motor saddles (snap), +0.3 on the button recess, 0.2 gap on the lid bosses. If your printer runs tight, scale nothing: change `cart.cradle_clr` / `cart.receiver.lug_clr` and regenerate.
**Fit checklist:** cartridge slides into the cradles and out through the front bore; adapter (A) or B cap enters, turns to the stop, holds the cartridge without axial play and the needle meets the septum centrally (look through the bore before turning); Insight Flex / Luer set connects at the tubing end; rod + gear + washers drop into the rib slots and the slider runs in its channel over the full stroke; motor dummy snaps into its saddles; cell dummy fits under the TMAG strip; board dummy lies on its 3 posts with the USB-C block in the wall opening; button cap snaps in flush; lid closes on the gasket with 3 screws from below and nothing on top. Note every misfit with the part name and a caliper value.

## Checks (`cart_check.py`, A and B PASS 2026-11-24)
No interference at FULL and EMPTY (moving parts copied to the end of stroke; a negative test fails as it should), housing closed, height / length / width below the Insight (B: with its cap; the hub + Luer collar is reported), stroke <= available travel, rod engaged over the whole stroke, slider in its channel, rod never wet, gear centre distance and clearances, thrust >= 1.5x, board outline >= the cup board area, all exports present.

## Open items
1. Measure cartridge, stopper, adapter and needle hub (list in `../docs/insight-research.md`), enter in `params.json -> cart`, regenerate.
2. B: check the FlexLink Luer gender against the needle hub (female) and whether a FlexLink head can be replaced by an Insight Flex head (the owner wants an Insight Flex cannula at the site end for both variants).
3. Route the new 60 x 10.6 board (same chip set, 4 layers if possible), then the order package (BUY-LIST §7, JLC files, cost per pump).
4. Motor decision (BUY-LIST §7b), firmware drive preset (U/step 0.00152).
5. Telescopic screw if the length must drop below about 70 mm.
6. Patent: US9205190B2 (gear wheel threaded on a piston rod, Roche, active to about 2029): read claim 1 before publishing hardware.
