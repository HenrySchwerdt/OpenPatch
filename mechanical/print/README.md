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

`cup_board_model.stl` is the board as placed on 2026-11-21, a 6-layer board 0.8 mm thick. It includes the 3.1 mm leg extension into `side_b`, every part at its position and height, and the break-off test strip.
- KiCad library 3D models are used where they exist.
- Datasheet-size boxes are used for the parts without one: the HJ-840 module (6.2 x 7.0 x 1.0), the USB-C mid-mount body straddling the board in its notch (z 4.12-7.33), the side button, the 4 x 4 x 2 mm sounder under the leg, the RGB LED, the STM32C011, the AND3, the dock hall and the DRV8835.

What to look at:
1. **Lid clearance.** Top parts may reach 1.5 mm above the board (z 7.6). The KiCad model of the charger U3 is 1.55 mm tall, so the model touches the lid by 0.04 mm. The real MCP73832 SOT-23-5 is 1.45 mm maximum.
2. **Cell clearance.** Under the board, over the cell, parts stay below 1.1 mm, and the cell top is at z 4.1.
3. **The leg.**
   - The sounder (2.0 mm) must sit in the `side_b` pocket.
   - The leg extension (x 43.4-46.5, y 17.15-22.5) must not hit a wall. The mechanics must still open `side_b` for it.
4. **USB-C.** The receptacle body must align with the opening in the +Y wall (x 18.8-28.2) and the gasket recess.
5. **Button.** The side button sits at x 33.0. The mechanics flex window is still at x 30.0 (`elec_interface.button`) and must move +3.0 mm.
6. **Screws.** The two d1.4 holes must sit on the M1.2 bosses (x 8.9 / y 21.5 and x 37.4 / y 20.0).
7. **Break-off strip.** It hangs east of the hall finger and is cut off at x 40.9 before assembly; print it, then snap it off.

Printing it: put the board on its long edge, or on the bottom face with tree supports under the bottom parts. With a 0.4 mm nozzle, the 0402 parts become small bumps. That is fine for a fit check.

## Gears

The z12 miter gears are module 0.3: tip diameter 4.0 mm, tooth height about 0.66 mm. An FDM printer with a 0.4 mm nozzle cannot form those teeth, so the print is only a space-claim blob. A resin printer (MSLA, 0.05 mm layers) prints them well enough to test the mesh by hand. For the real drive, use the bought brass pair (BUY-LIST §0).

## Tolerances

- **FDM:** sliding and press fits need about 0.2-0.3 mm extra clearance. The housing CAD already carries the gaps the moulded/printed parts need. If a lid is tight, scale the part by 100.5 % in x/y before you change the CAD, and note the printer and the setting.
- **Resin:** expect less than 0.1 mm. Cure fully before you measure.

Record what you measure in `docs/STATUS.md`: printer, nozzle / layer height, which fit was tight or loose and by how much.

Regenerate: `python3 make_print_kit.py <placed board .kicad_pcb>` (needs `solidcraft-cli` and KiCad 10).
