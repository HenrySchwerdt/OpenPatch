> **TEST ONLY - NOT FOR HUMAN USE** (see `../../../../DISCLAIMER.md`). Bench sample, water only, never worn.

# Cup-pod main board: independent sanity review against the housing (2026-11-20)

**Verdict: the board can be fixed with the changes listed below; it is not fundamentally wrong.** The main rectangle sits in the right place: lane 2, above the cell, at a height that leaves room above and below it. But the interface parts were placed against an old or partly wrong picture of the mechanics. There are **3 hard collisions** (USB-C height, lane-2 motor saddle, 5 parts under the board on the dock-pocket roof). There are **4 placement-logic errors** (motor socket, cell pads, button wall, no board support). And the **west end of the board is over-booked**: USB-C, motor wires, cell wires and the TMAG strip all want the same 10 mm. The main fix is to move the USB-C east, which is one parameter in `op_cup.py`. After that, every wire to the board can land at the west end, next to the motor and the cell's lead end.

## Method (what was checked, what was not)
* **Board:** a snapshot of `cup.kicad_pcb` taken 2026-11-20 12:20 (91 footprints, 6 layers, 0.8 mm). It was read with KiCad 10 python (`dump_board.py` -> `board_snapshot.json`). KiCad to pod frame: `x = kx - 100 + 7.45`, `y = 33.5 - (ky - 80)`. This matches `cupgeom.py`, which puts the board at z 5.3-6.1.
* **Housing:** `OP-100.mech.json`, `op_cup.py` and `op_cup_asm.py` (generated 2026-11-19 19:41). Every number that drives a verdict was **probed in `OP-100_bottom.stl` / `OP-100_top.stl` / `OP-100_reservoir.stl`** with a ray-cast inside test (`stl_probe.py`). I did not take it from `FIT-CHECK.md` or the `ko_*` boxes.
* Pod frame: x = 0 at the motor (rear) end, +x toward the dock. y = 0 at the tank-side (-Y) wall. z = 0 at the skin side. Inner walls are at x 0.9 / 47.06 and y 0.9 / 33.7. The lid's inner face is at **z 7.6**.
* Part heights are the placer's table (`place_cup.py HEIGHTS`), not datasheets. Marginal items are marked VERIFY.
* **Not verifiable from the files:**
  * the real lead exit of the NFP-608 (CAD has 4 pins under the can at y ≈ 27; STATUS says "rear");
  * the real 301030 lead end;
  * the mid-mount USB-C part;
  * the sounder sound level through a sealed shell;
  * whether the TMAG flex strip can be routed. No wire, cable or flex path is modelled in CAD.

Images (for non-engineers): `overlay_top.png` (top view, numbered problems) and `overlay_side.png` (A: lane 2 seen from the +Y wall; B: cross-section through the board leg and dock).

## 1. Board outline vs housing (board z 5.3-6.1)

| Edge / neighbour | Board edge | Housing feature (STL) | Clearance | Result |
|---|---|---|---|---|
| West edge vs motor can (y 22.9-32.15) | x 7.45 | Can d6 on axis (4.47, z 4.25): at z 5.3 it reaches x 7.28 | **0.17** (can ±0.1 tolerance leaves 0.07) | marginal |
| West edge vs **lane-2 motor snap saddle** (y 29.95-31.45) | x 7.45 | C-ring lip r 3.37, cut at z 5.85: solid up to x 7.68 at z 5.3. STL shows solid at (7.5, 30.7) for z 4.65-5.7 | **-0.23 (collision)**, z 5.3-5.85 | **FAIL** |
| North edge vs +Y wall | y 33.5 | Inner wall y 33.7 | 0.20 | pass |
| East edge (lane 2) vs end wall | x 43.4 | Inner wall x 47.06 | 3.66 | pass (free space, not used) |
| East edge vs lid post (45.41, 32.05) d2.0 | x 43.4 | Post to z 7.55 | 1.01 | pass |
| South edge (x 7.45-35.4) vs tank | y 22.9 | Tank y ≤ 22.6, full height z 0.9-7.6 | 0.30 | pass |
| Leg west edge vs tank front face | x 35.4 | Tank x ≤ 35.11 | 0.29 | pass |
| Foot east edge vs post (45.41, 2.55) | x 44.2 | Post x ≥ 44.41 | **0.21** | marginal |
| Foot south edge vs -Y wall | y 1.1 | Inner wall y 0.9 | 0.20 | pass |
| Corridor (x 36-42, y 6.35-17.15) vs dock-pocket roof | z 5.3 | Roof solid z **4.45-4.9** at x 35.16-47.07, y 6.45-17.05 | 0.40 below the board | pass for the board, **not for parts** (see 2) |
| Lid, gasket | — | Lid cavity to z 7.6. The gasket sits on the 0.9 mm wall rim (0.15-0.55 from the outer face) and does not reach into the cavity | 1.5 above the board top | pass |
| Rod, gears, plunger, TMAG | — | All in lane 1 at x < 10.2 or inside the tank | not adjacent | pass |
| Cell | — | z 0.9-4.1 (incl. 0.2 swell) | 1.2 below the board | pass |
| **Board support** | z 5.3 | The only board ledges are at (40.57, 24.3) and (40.57, 32.1), d1.8, with **top z 4.15** (made for the old `ko_board` z 4.2). Nothing else touches the board | **1.15 gap: the board floats** | **FAIL** |

STL slab test: a solid sample inside the board volume (z 5.31-6.09) gives 18 hits in lane 2, all in the saddle strip. The corridor and foot give 0 hits against the bottom shell, the lid and the tank.

## 2. Height budget per part (above the board 1.5 mm; below it depends on what lies under it)

| Zone below / above | Allowance | Violations | Marginal (≤ 0.1) |
|---|---|---|---|
| Top side, all of the board | 7.6 - 6.1 = **1.5** | **JU1 USB-C proxy HRO TYPE-C-31-M-12 (top-mount, 3.26): top z 9.36. That is 1.76 above the lid's inner face and 0.86 above the pod's outside.** | U20, U5, UU1 (SOT-23-6), U3 (SOT-23-5) at 1.45 leave 0.05; SW1 at 1.4 leaves 0.10 |
| Bottom side over the **dock-pocket roof** (x 35.16-47.07, y 6.45-17.05) | 5.3 - 4.9 = **0.4** | **C1 (0.6), C50 (0.6), R21 (0.5), R91 (0.5), R92 (0.5)**: each overlaps the roof by 0.1-0.2 | U4A dock hall (0.4) at **0.0** |
| Bottom side over the cell (x 7.87-39.37, y 22.8-33.4) | 5.3 - 4.1 = 1.2 | none (max 1.0: CB1/CB2 0805, L1 1008, U8, DU1, C31) | VERIFY that the real 0805/1008 heights are ≤ 1.1 (some 10 µF 0805 parts are 1.25) |
| Bottom side over the ledges (top 4.15) | 1.15 | none | U31 (SC-70, 1.1) over ledge 1: 0.05 |
| Bottom side in side_b / side_a (floor 0.9) | 4.4 | none (BZ1 2.0, J1 2.8) | — |

Root cause of the pocket hits: `cupgeom.py` sets `LOW_ZONES[1]` = 1.1 mm "over the cannula adapter (z top 4.2)". The adapter is inside the pocket, but the **pocket roof (housing, z 4.45-4.9) lies between the adapter and the board**, so the real limit there is 0.4 mm.

## 3. Interface placement logic (each hand-fixed position in `place_cup.py`)

| Ref (pod position) | What the mechanics says | Verdict | Where it should go |
|---|---|---|---|
| **U1** HJ-840 (39.7, 28.2) rot 270 | Row A, including the antenna pads A7/A8, is at x 42.85, and the board edge is x 43.4. The rule area covers x 42.0-43.3 on all 6 layers, with no tracks, vias or pour (fill sampled: 0 hits). In front of it is 3.7 mm of air to the end wall. The cell lies under the non-antenna half only (cell ends at x 39.37). | **Correct** | Keep it. Minor: the steel M1.2 lid screw (45.41, 32.05) is about 2.3 mm from the module corner. Use an A2 (non-magnetic) or brass screw, or accept some detuning (VERIFY with the RSSI test). |
| **JU1** USB-C (12.5, 29.75), mouth toward +Y | In plan it matches the wall opening (STL opening x 7.70-17.00, centre 12.35; z 4.15-7.5, centre about 5.83). In height it is wrong: the top-mount proxy puts its centre at about z 7.7. The outline has **no notch** for the mid-mount part that FIT-CHECK requests. | **Wrong (height); plan position OK but bad for the wiring** | Use a real mid-mount / sink receptacle in a board-edge notch. Its centre on the board mid-plane (z 5.7) is 0.13 from the opening centre. Its bottom is at about z 4.07, which touches the 4.1 cell top: VERIFY with the real part. **Recommended:** move the opening and receptacle east to about x 19-28 (one change to `L["usb"]` in `op_cup.py`). That frees the west end for the wires. |
| **TL1-4** TMAG strip pads (9.2-11.6, 23.8), bottom | The TMAG sits in lane 1 at x 2.67-5.57, y 7.25-10.45, z ≈ 5.0. A strip must cross the gears (tips up to z 6.95; lid 7.6) and then run in the only free channel, x 7.5-10.1, y 15-22.8, between the motor and the tank. It ends under the board in the 1.2 mm gap above the cell. | **Plausible** (nearest board point to that channel) | Keep it, but the strip path is not modelled (VERIFY). It is moot if the planned magnet relocation removes the strip. |
| **J1** motor socket (39.8, 4.7), bottom | The motor is at x 1.47-7.47. The 4 pins are under the can at y 25.35-28.75 (`motor_term`), with the floor pin pocket and FPC groove ending at x 7.77. J1 is about **32 mm away**, on the other side of the tank. | **Wrong** (removal already decided) | 4 solder pads at the west end, **top side** (solderable with the lid off), at about x 7.9-10.5, y 24.6-26.3. See fix 3 for the wire path. |
| **SP1/SP2** cell pads (anchors 37.0, 24.6 / 27.6; **actually placed** 34.71, 31.13 / 28.39, 27.93), top | ASSEMBLY-CUP step 4 says the **PCM / lead end faces the motor (west, x ≈ 7.9)**. FIT-CHECK says east: the docs disagree. Top-side pads in the middle of the board cannot be reached from below at all. The south edge is 0.3 from the full-height tank and the north edge is 0.2 from the wall, so there is no gap for a wire to wrap around. The placer also moved SP2 6.6 mm off its anchor. | **Wrong** | Fix the lead end to WEST and put SP1/SP2 at the west end next to the motor pads, top side, with the wires coming up through a wire notch (fix 3). If the lead end is east instead, the wires would come up at x 39.4-43.4, right next to the antenna. Avoid that. |
| **SW1** side tact (39.8, 3.0), actuator -Y | The actuator is 0.16 from the inner -Y wall. **The STL wall at x 39.8 is solid** (bottom z 0-4.95, lid z 5.45-7.8): there is no flex zone. The requested zone (x 38.3-41.3, z 6-7.5) would be in the clear SLA **lid** wall and partly in the R1.8 top fillet (z > 6.7). | **Position OK, housing feature missing** | Either add the flex zone to `op_cup_asm.py` (lid side wall, flat area below the fillet, z 5.6-6.7), or move SW1 to the north edge of the main body (y 33.5, 0.2 from the +Y wall). That also lets you delete the foot (see 4). |
| **BZ1** sounder (39.0, 20.2), bottom | side_b, floor at 0.9: 2.4 mm spare. | **Fits** | The acoustic path is not designed: the shell is sealed (gasket, no port). Expect heavy damping (VERIFY on the bench). It is a **magnetic** sounder 8.5 mm from the dock hall U4A: VERIFY its stray field against the DRV5032FA threshold, and keep it ≥ 10 mm from the hall if possible. |
| **LD1** RGB LED (32.0, 31.2), top | Under the flat part of the clear lid (the top fillet starts at y ≈ 32.8). The nearest tall part (U3, 1.45) is 2 mm away. | **Correct** | — |
| **U4A** dock hall (39.36, 11.75), bottom | Mechanics `x_d` = 39.363, `y_c` = 11.75 is the magnet position when **docked** (`x_d0` 42.86 is the pre-slide position). Package z 4.9-5.3 sits on the roof (4.45-4.9) with 0.0 mm. | **Correct in plan, zero z margin** | Keep x/y. Treat the roof as the board's support and specify a 0.05 relief, or let the hall touch by design. Move C1/C50/R21/R91/R92 off the pocket area or to the top side. |
| **SWD** J10 SWDIO (39.9, 32.2), J11 SWDCLK (41.3, 32.2), J12 NRST (32.7, 29.4), J13 GND (38.0, 13.5), J14 3V3 (38.05, 12.1) | All top side, flat, reachable with the lid off. | **Pass** | They are spread over 19 mm, so flashing needs 5 loose probes. Group them in one row (e.g. along the north edge, x 33-38). |

## 4. Shape sanity (L-shape / leg)
* Area: main body 381 mm². Leg 149 mm² (28 %), made of the corridor 65, the side_b block 38 and the **foot 46**.
* The **corridor** carries the dock hall and its circuit (U4A, Q7, R21, C1), plus parts that do not need to be there (U2 LDO, U20 TPS2553 load switch, U5 TPL5010, test pads). It is an area overflow. Only the hall is tied to this position. Below it there are just 0.4 mm, so it is effectively a **one-sided** board.
* The **side_b block** has 4.4 mm free below it. It is the only good place for tall bottom parts (BZ1). It is justified.
* The **foot** (x 35.4-44.2, y 1.1-6.35) holds only SW1 and J1. Once J1 is removed it exists for **one button**, and the wall feature that button needs does not exist. This part is wasted.
* The east end of lane 2 (x 43.4-47.06, 3.7 × 10.6 mm, full height free) is unused. It should stay free in front of the antenna, so leaving it unused is the right call.
* **Simpler outline proposal:**
  * main body x 7.8-43.4, y 22.9-33.5, with a USB-C notch at its new east-shifted position;
  * side_b block x 35.4-42.0, y 17.2-22.9 (unchanged);
  * a hall finger only (x 37.9-40.9, y 10.4-17.15; top-side parts only, plus the hall);
  * **delete the foot**: SW1 goes to the north edge of the main body with the flex zone in the +Y lid wall.

  This keeps every position-bound part, removes about 46 mm² of board that only holds the button, and leaves one clean edge for the button and the USB-C. A separate spring-contact board for the hall is **not** simpler: it needs 3 contacts or wires, and assembly must stay iron-free.

## 5. Ranked fixes

| # | Fix | Owner | Effect |
|---|---|---|---|
| 1 | **USB-C:** replace the top-mount proxy with a real mid-mount receptacle in an outline notch. **Move the receptacle and the wall opening east** (about x 19-28). Mechanics: `L["usb"]["x"]` in `op_cup.py`, then re-run `check.py --variant v010 --drive cup`. | elec + mech | Removes the 1.76 mm lid collision and frees the west end for wires. |
| 2 | **Pocket roof zone:** set `cupgeom.LOW_ZONES[1]` to 0.4 mm (roof z 4.9, not adapter 4.2). Move C1, C50, R21, R91, R92 to the top side or off x 35.2-47, y 6.45-17.05. | elec | Removes 5 collisions. |
| 3 | **West-end wiring hub:** use top-side pads for the motor (4) and the cell (2) at x ≈ 7.9-12, y 24-27, next to the TL pads. Shift the **cell 1.5 mm east** (x 9.4-40.9; lane 2 has 7.7 mm spare at the east end) to open a wire channel x 7.5-9.4 for the motor, cell and TMAG wires. Add a 1.5 × 2.5 mm wire notch in the board's west edge so the wires can come up to the top-side pads. Fix the cell's lead end to WEST in ASSEMBLY-CUP and FIT-CHECK. Remove J1 and the SP anchors at x 37. | mech + elec | Short wires, pads solderable with the lid off, no wires near the antenna. |
| 4 | **Saddle collision:** pull the board's west edge to x ≥ 7.8, which also gives 0.5 to the can. Or cut the +X lip of the lane-2 saddle to z ≤ 5.2. | elec (or mech) | Removes the collision and the 0.17 can clearance. |
| 5 | **Board support:** raise the two ledges to z 5.3, keep a 1.0 mm part-free pad above each, and move U31 off ledge 1. Use the pocket roof as the third support under the hall finger (add 2 small 0.05-relief pads around U4A). Hold the board down with lid ribs, since there are 1.5 mm above it. | mech + elec | The board stops floating. |
| 6 | **Button:** either add the flex zone to the CAD (lid wall, flat area z 5.6-6.7, not into the R1.8 fillet), or move SW1 to the north edge and delete the foot (section 4). | mech (+ elec) | The button can actually be pressed. |
| 7 | **Sounder:** check its stray field against the dock hall and its sound level in the sealed shell. If it is too quiet, add a vent/port with a membrane (`params.json` already has an ePTFE vent spec). | elec + bench | Avoids a false DOCKED reading and an inaudible alarm. |
| 8 | Group the SWD pads (5 in one row), check the real heights of SOT-23-6 / 0805 / 1008 parts (0.05 margins), and use a non-magnetic lid screw near the antenna. | elec | Minor. |

Also noted as a rule conflict for the owner: soldering the motor and cell wires to pads contradicts CLAUDE.md "Assembly without a soldering iron (spec §1a)". The user decided on 2026-11-20 to solder them, so spec §1a should record this exception.

## Files
* `overlay_top.png`, `overlay_side.png`: images (`make_overlay.py`, Pillow from the main repo `.venv`).
* `board_snapshot.json`: the footprint dump the images are built from (`dump_board.py`, run with `../../board/kpy`).
* `stl_probe.py`: ray-cast inside test of the housing STLs used for the clearances above.
