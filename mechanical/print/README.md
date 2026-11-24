> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). Water only, never worn.

# Fit-check print kit (OP-100 cup pod)

These parts are printed to check, by hand, whether the housing, the board, the motor, the gears and the cell fit together as the
CAD says. They are not functional parts. The printed tank is not a water-tight reservoir, and no printed part is ever used on a body.

All files share the **pod frame** of `mechanical/out/v010-cup`:
- x runs from the motor end;
- y runs from the tank-side wall;
- z runs from the skin side, and the board underside is at z = 5.3.

Every part therefore lands in its place when you load them together in the slicer without moving them. Use that once, for a
virtual check, before you print. For printing, lay each part on its own best face.

## Files

| File | What | Print |
|---|---|---|
| `../out/v010-cup/OP-100_bottom.stl`, `OP-100_top.stl`, `OP-100_end_cap.stl`, `OP-100_end_cap_lid.stl`, `OP-100_dock_insert.stl` | Housing | FDM or resin |
| `../out/v010-cup/OP-100_reservoir.stl`, `OP-100_plunger_core.stl`, `OP-100_thrust_collar.stl` | Tank, plunger core, thrust collar (fit only) | Resin preferred; FDM is fine for fit |
| `OP-100/cup_board_model.stl` | **Populated main board, see below** | Resin, or FDM with 0.2 mm nozzle / fine layers |
| `OP-100/motor_dummy.stl` | NFP-608-26.45 with gearhead, shaft and terminals | FDM |
| `OP-100/gear_a.stl`, `OP-100/gear_b.stl` | Miter pair m0.3 z12, as faced / drilled | **Resin only**, see the gear note |
| `OP-100/rod_nut_collar.stl` | M1.6 rod, plunger nut, thrust collar, bush | Use the real M1.6 rod; print only to check the length |
| `OP-100/magnet.stl` | d2 x 1 angle magnet | Use the real magnet |
| `OP-100/cell_dummy.stl` | Ampul 301030 envelope incl. 0.2 mm swell allowance | FDM |

## The populated board

`cup_board_model.stl` is the routed board of 2026-11-24 (`electronics/v010/cup/variants/cup_clean.kicad_pcb`, regenerated with `print_model.py`), a 6-layer board 0.8 mm thick on the 36.6 mm wide housing (board y 22.9-35.5, USB-C opening and button on the +Y wall). It includes the 3.1 mm leg extension into `side_b` and every part at its position and height.
- KiCad library 3D models are used where they exist.
- Datasheet-size boxes are used for the parts without one: the HJ-840 module (6.2 x 7.0 x 1.0), the USB-C mid-mount body straddling the board in its notch (z 4.12-7.33), the side button, the 4 x 4 x 2 mm sounder under the leg, the RGB LED, the STM32C011, the AND3, the dock hall and the two DRV8838 motor drivers.

What to look at:
1. **Lid clearance.** Top parts may reach 1.5 mm above the board (z 7.6). The KiCad model of the charger U3 is 1.55 mm tall, so the model touches the lid by 0.04 mm. The real MCP73832 SOT-23-5 is 1.45 mm maximum.
2. **Cell clearance.** Under the board, over the cell, parts stay below 1.1 mm, and the cell top is at z 4.1.
3. **The leg.**
   - The sounder (2.0 mm) must sit in the `side_b` pocket.
   - The leg extension (x 43.4-46.5, y 17.15-22.5) lies inside the `side_b` keep-out (x up to 46.76); check that it does not touch a wall.
4. **USB-C.** The receptacle body must align with the opening in the +Y wall (x 18.8-28.2) and the gasket recess.
5. **Button.** The side button sits at x 33.0; the lid flex window is at x 32.4-34.5 (moved on 2026-11-21).
6. **Screws.** The two d1.4 holes must sit on the M1.2 bosses (x 8.9 / y 21.5 and x 37.4 / y 20.0).
7. **Break-off strip.** It hangs east of the hall finger and is cut off at x 40.9 before assembly; print it, then snap it off.

Printing it: put the board on its long edge, or on the bottom face with tree supports under the bottom parts. With a 0.4 mm nozzle, the 0402 parts become small bumps. That is fine for a fit check.

## Gears

The z12 miter gears are module 0.3: tip diameter 4.0 mm, tooth height about 0.66 mm. An FDM printer with a 0.4 mm nozzle cannot form those teeth, so the print is only a space-claim blob. A resin printer (MSLA, 0.05 mm layers) prints them well enough to test the mesh by hand. For the real drive, use the bought brass pair (BUY-LIST §0).

## Printer used: Sovol SV01 Pro (FDM, 0.4 mm nozzle)

| Part | Layer | Orientation / note |
|---|---|---|
| housing bottom / top / end cap | 0.12-0.16 mm, PLA or PETG | outer face down; fits need about 0.2 mm |
| board model | 0.10 mm | on its long edge, brim |
| motor and cell dummies | 0.16 mm | flat face down |
| gears, rod, magnet | - | not printable at 1:1 with a 0.4 mm nozzle: use the real parts |

## 2:1 model (everything scaled by 200 %)

A complete 2:1 print (pod about 96 x 69 x 17 mm, fits the 280 x 240 mm bed) is the easiest way to see the mechanism work. At that size the gears are m0.6 with about 1.3 mm teeth, which a 0.4 mm nozzle prints well enough to turn by hand. The plunger, rod path, dock, board outline and part positions are all readable.

Limits of the 2:1 model:
- **Print every part scaled**, including motor, cell, rod and magnet. Real bought parts do not fit a 2:1 housing.
- **Clearances do not scale with the printer error.** A gap of 0.1 mm in the CAD becomes 0.2 mm at 2:1, while the printer error stays about 0.2 mm. A 2:1 print shows collisions and the layout, but not whether the 1:1 parts will be tight.
- Real fits (lid, USB-C, button window, board screws, cell pocket) are checked afterwards with a 1:1 housing and the real parts.

## Tolerances

- **FDM:** sliding and press fits need about 0.2-0.3 mm extra clearance. The housing CAD already carries the gaps the moulded/printed parts need. If a lid is tight, scale the part by 100.5 % in x/y before you change the CAD, and note the printer and the setting.
- **Resin:** expect less than 0.1 mm. Cure fully before you measure.

Record what you measure in `docs/STATUS.md`: printer, nozzle / layer height, which fit was tight or loose and by how much.

Regenerate: `python3 make_print_kit.py <placed board .kicad_pcb>` (needs `solidcraft-cli` and KiCad 10).

## Functional 2:1 parts (`OP-100_2to1_demo/`, `demo_2to1.py`)

The CAD gears are envelopes and the rod and nut have no thread, so a scaled print of them does not move. For the hand-turned 2:1 model, `demo_2to1.py` generates three parts:
- **Miter gears:** m0.6 z12, involute, 0.15 mm backlash. Gear A has a d4.2 bore for the motor shaft dummy; gear B has a d3.4 bore and is glued on the plain end of the rod.
- **Lead screw:** d3.2 x 32.8 mm, **1.0 mm pitch**. This is printable; the real M1.6 x 0.35 is not. The first 7 mm are plain.
- **Plunger nut:** AF 7.0 x 2.6 with 0.2 mm radial thread clearance; it goes into the plunger core's hex pocket.

Print the screw upright in PETG and make two, because it is thin. Print the gears back face down at 0.1 mm layers. Scale the other kit parts by 200 %, or use the zip of the session.

## 2:1 housing, sliced for the Sovol SV01 Pro (`OP-100_x2/`)

The final OP-100 housing (bottom shell + lid, from `../out/v010-cup/`, state of 2026-11-24) is scaled to 200 %. Both parts are printed together in one job. The lid is flipped so its outer face is down.

- `make_x2_housing.py` writes `OP-100_bottom_x2.stl` (95.9 x 73.2 x 15.1 mm), `OP-100_top_x2.stl` (95.9 x 73.2 x 6.2 mm, flipped) and the bed layout `OP-100_housing_x2_bed.stl`.
- `slice_sv01pro.sh <stl> <gcode>` slices with the CuraEngine inside UltiMaker Cura (5.11, SV01 Pro definition, Titan extruder, 0.4 nozzle).
  - CuraEngine alone ignores Cura's formula settings, so `cura_resolve.py` evaluates all 724 settings the way the Cura app does.
  - Our overrides are in `sv01pro_pla_firstlayer.json`.
- Result: **`OP-100_x2/OP-100_housing_x2_SV01PRO.gcode`**. PLA, 0.16 mm layers, 20 % grid infill, tree supports (for the dock-pocket roof and the motor saddles), 6 mm brim. About 1 h 50 min and about 38 g of filament (CuraEngine estimate).

**First-layer fixes in that profile:**
1. **A fresh bed mesh on every print.** The stock Sovol start code only runs `M420 S1`, which loads a saved mesh. If `G29` + `M500` was never run on the printer, that does nothing, and a tilted or warped bed ruins the first layer.
   - The new start code heats the bed to 65 °C first, then homes and runs `G29`. This adds about 2 min.
   - It then applies the mesh with a 10 mm fade (`M420 S1 Z10`).
2. **Thick, wide, slow first layer:** 0.28 mm height, 120 % line width, 15 mm/s, part fan off. The fan ramps up over layers 1-4.
3. **First-layer temperatures** 5 °C hotter: nozzle 210 °C, bed 65 °C. After that, 205 °C and 60 °C.
4. **6 mm brim** against lifting corners.

**If the first layer is still bad, check these on the printer (a slicer cannot fix them):**
- **Z offset (probe offset):** set `M851 Z-…` from a paper test and save it with `M500`.
  - Lines too thin or scratchy: the nozzle is too close. Raise it by 0.05 mm.
  - Lines round and not sticking: the nozzle is too far. Lower it by 0.05 mm.
- **Clean the bed:** isopropyl alcohol, no fingerprints.
- **Tram the bed screws** roughly before `G29`: the probe can only compensate a few tenths of a millimetre.
- **Slow or tight filament path:** check the Titan tension; a skipping extruder looks like poor adhesion.

**Other materials:** for PETG, change the temperatures in `sv01pro_pla_firstlayer.json` and `BED0` / `NOZ0` in `slice_sv01pro.sh` (e.g. 235/240 °C nozzle, 75/80 °C bed), then re-run the slice.
