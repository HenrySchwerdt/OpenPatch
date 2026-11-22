> TEST ONLY - NOT FOR HUMAN USE (see ../../../DISCLAIMER.md). Water only, never worn.

# CUP board: net-by-net hand-routing guide (KiCad 10)

## STATE 2026-11-22: fully routed, DRC 0 (board widened by 2 mm)

**Board:** `cup/cup.kicad_pcb` (routed master), `variants/cup_clean.kicad_pcb` and `variants/cup_dev.kicad_pcb` (the master plus the six DEV interlock test pads on the underside, `variants/TESTPOINTS.md`). 6 layers, 0.8 mm, outline 38.8 x 25.2 mm bounding box (the lane-2 part of the board is 2 mm deeper than before: `cupgeom.py` Y1 = 35.5), 69 footprints, 172 vias (71 of them filled vias in SMD pads, JLC POFV), min track / space 0.10 / 0.10 mm.

**DRC (`drc.json`, `variants/drc_clean.json`, `variants/drc_dev.json`): 0 errors, 0 unconnected items** on all three boards. Remaining warnings (silk only): the USB-C body silk overhangs the board edge (4, connector sits in the notch by design) and the U7 pin-1 mark is clipped by the C61 mask opening on the underside (1).

**How it was routed (reproducible up to the last hand fixes, which live in the committed board):**
1. `build_cup.py` with `OP_BUS=0` (no bus trunks) -> placed board.
2. `nego_route.py placed out 100` (PathFinder negotiation, 100 iterations; knobs `OP_TIGHT=1 OP_VIA_SLACK=0 OP_NEGO=add`). Best score 72, 2 nets left (MOT_FWD, APHASE) and 3 hole-clearance errors.
3. `finish_route.py out drc.json` (A* for the leftovers).
4. `rr_route.py --greedy out placed 8` with `OP_RR_PLATEAU=1 RR_JITTER=0.6`: per-net rip-up trials with rollback; closed the last two nets.
5. Hand fixes (scripted, about 0.05 mm each): 3 hole clearances (one WDT_DELAY bend and one VMOT via moved 0.05 mm); GND stubs with their own via for U3.2 and C70.2; a filled via in U36 pad 2 (GND) after a 0.3 mm detour of OC_OK on In4; solid (not thermal) zone connection for 7 GND pads whose spokes were starved (U3.2, U36.2, C70.2, C5.2, U34.3, U7.13, JU1 shield); 7 duplicate / touching same-net vias and one dangling via removed.
6. `../board/route_v3.py board finish` (GND pours on all layers, island removal, stitching).
7. `silk_labels.py board` (wire / cell pad labels placed free of each other, of pads and of part silk; the `+` of the middle cell pad is a drawn 0.4 mm glyph in the gap under R55).
8. `variants.py board variants/` (now also keeps 0.21 mm from foreign drills), then `../tools/export_cup_jlc.py variants/cup_clean.kicad_pcb jlc` and `... cup_dev.kicad_pcb jlc-dev`.

Run outcomes for reference: without the widening the best was 5 open; with it, 30 to 70 negotiation iterations left 7 to 12 open, 100 iterations left 2.

---

(Older net-by-net table below: written for the 91-part netlist, kept as a routing-order reference.)


Open `cup/cup.kicad_pcb` (placed, critical nets scripted, the rest Freerouting; state of the latest run in `flow.log` / `drc.json`). `cup_after_critical.kicad_pcb` is the board after the scripted critical routing only (everything else unrouted): the best starting point for a manual finish. Netlist and part data: `../design/netlist_v4.py`, `../netlist_v4_cup.json`. Placement is final for this guide (hand moves only to open channels).

## Stack, rules, vias
| Item | Value |
|---|---|
| Layers (6, 0.8 mm, ENIG) | F.Cu signal/parts, **In1 GND plane**, In2 signal, In3 signal, In4 signal / 3V3 pour, B.Cu signal/parts; GND pours on F, In2, In3, In4, B between tracks |
| Rules (JLC 6L) | track >= 0.10 (use 0.12), clearance 0.10, via 0.40 pad / 0.20 drill (**epoxy-filled and capped if placed in a pad**), copper-to-edge >= 0.20, hole-to-hole 0.20 |
| Outline | `cupgeom.py` polygon; antenna band: **no copper on any layer** east of x = 42.0 (pod) at the module end (rule area `ANT_KEEPOUT`) |
| GND | one GND via within 1 mm of every GND pad (via in the pad for 0402 and larger when no other net is on the other side), stitching vias on a 2.5 mm grid but **only inside the outline, 0.7 mm from the edge, 0.45 mm from any other-net copper** (the script version produced shorts at the notches: do it by hand with Edit > Fill all zones, DRC after) |

## Routing order (do each step, run DRC, then the next)
| # | Net | Width | Layers | Via strategy | Notes |
|---|---|---|---|---|---|
| 1 | `USB_DP`, `USB_DM` | 0.12, gap 0.12 (about 90 ohm differential on the JLC 6L 0.8 mm stack: check with the JLC impedance calculator, 0.8 mm 6L stack JLC06081H-3313 class, adjust width/gap) | F.Cu next to the In1 GND plane | none, as short as possible from `U1.F1/G1` to `UU1` to `JU1.A6/B6, A7/B7`, equal length (+-0.2 mm) | scripted: done on the board (check) |
| 2 | `VBAT` | 0.30 (0.5 where free) | F/B + In4 | via at both ends | cell pads SP1 to `C5`, `U2`, `U3`, `U8` boost VIN, `L1`, `LD1` anode resistor, `R6`/`R7` |
| 3 | `BST_SW` | 0.40, <= 3 mm | F.Cu only | none | `U8` pin 3 to `L1`: shortest possible, no vias, GND pour below on In1 |
| 4 | `VMOT_PRE` | 0.40 | F.Cu + In2/In4 | 2 vias per layer change | `U8` VOUT, `R55`, `CB1`, `CB2`, `C31`, `DZ1`, `R24`, `C60` and `U20` IN: caps adjacent to U8 and U20 |
| 5 | `VMOT` | 0.30 | F.Cu | 1 via | `U20` OUT to `U7` VS, `C21`, `R25`, `R57` |
| 6 | `MOT_A1`, `MOT_A2`, `MOT_B1`, `MOT_B2` | 0.20 | F.Cu / B.Cu | 1 via max | `U7` to `J1` pins 4, 2, 3, 1: keep the four together, away from the antenna side and from `USB_*` |
| 7 | `SNSA`, `SNSB` | 0.20 | F.Cu | none | `U7` sense pins to `R34`/`R35` (1 ohm) to GND by the shortest path; `SNSA` also goes to the nRF pad `U1.E6` (ADC) with a 0.12 track |
| 8 | `3V3` | 0.20 (pour on In4) | In4 pour + F.Cu stubs | vias at each IC | `U2` out, `C7`, `C1` (U1), `U30`, `U5`, `U6`, `U31` to `U34`, `U11`.. pull-ups; star from `C7` |
| 9 | `MOT_ALLOW`, `DOCK_OR`, `LATCH_Q`, `LATCH_CLR_N`, `OC_OK`, `SUP_NRST`, `ARM_CLK` | 0.12 | F.Cu, In2 | free | hardware cut path: keep short and away from `BST_SW`; `R90` pull-down at `U20` EN |
| 10 | HJ-840 `U1` fan-out | 0.12 | see below | see below | do this before the remaining signals |
| 11 | `I2C_SDA`, `I2C_SCL`, `TL1` to `TL4` pads | 0.12 | In2/F | free | to the REAR strip pads on the bottom (west edge) |
| 12 | rest: `LED_*`, `BTN_N`, `BUZ_A`, `CHG_*`, UART `SUP_TXD`/`SUP_RXD`, `SUP_BOOT0`, `MOT_*` control, `VBUS_P` (0.30) | 0.12 | any | free | |
| 13 | GND: pours, stitching | | all | see table above | fill all zones, then DRC |

## HJ-840 (`U1`, LGA64 6.2 x 7.0) fan-out
* Pads 0.30 x 0.40 on a 0.65 (columns) x 0.9 (rows) grid: between two pad rows there is a 0.5 mm channel, between two columns 0.35 mm (one 0.12 track + 0.10 clearances fits).
* **Outer ring first** (rows A and H, columns 1 and 8): route out on F.Cu in the channels. Inner pads: **dog-bone** via 0.40/0.20 centred in the row channel (0.45 mm from the pad centre), stub 0.12 on F.Cu; or via-in-pad with epoxy fill if the channel is full. Down to In2/In3 and out.
* Fixed pads: `A1`, `H8` GND (via in pad, large pour around), `H2`, `H3`, `H4` 3V3 (one 0.3 track + 100 nF `C1` within 3 mm), `F2` `VBUS_P`, `F1`/`G1` USB pair (route first, F.Cu straight), `E1` NRST (pull-up `R1`), `C2`/`C3` SWD pads (0.12 to the bare pads `J10`/`J11`), `A7`/`A8` antenna: `ANT_A` to `PI2` (0 ohm) to `ANT_B`, **no other net near them**, `PI1`/`PI3` DNP shunt footprints on the GND side, nothing on the board bottom under the module (the board bottom under `U1` is free by construction), copper keep-out at the module end (rule area).
* DCCH `H1`, DEC1 `H6`, DEC5 `C4`, DECUSB `G2`, NFC pads `B4`/`C5`: not connected, leave bare.
* The pad assignment of the GPIO signals is in `pin_assign.json` (swap GPIO pads between signals if it opens a channel: any nRF52840 GPIO works for the digital signals; **keep the analog nets on `G5`, `E6`, `H7`** and fix `FIRMWARE-PINMAP.md` afterwards).

## Hotspots seen in the autorouter runs
* The strip east of the module (x 36 to 43, y 22.9 to 33.5) carries the HJ-840, `U33`, `U34`, `U32`, `U31` and the LED: route its signals on In2/In3 before the west part.
* The dock leg (x 36 to 42, y 6 to 17) is narrow (6 mm): only the hall `U4A` (bottom), `Q7`, `R21` and the traces `3V3`, `GND`, `DOCK_N`/`DOCKED_H` pass; route them on F.Cu / In2 straight, GND via every 5 mm.
* Side block with the motor socket `J1` (bottom) and sounder `BZ1` (bottom): the four motor traces and `PZ_A`/`BUZ_A` pass the corridor on In3/In4.

## Before sending to JLC
Run DRC (all errors fixed, warnings reviewed), Fill all zones, then `tools/export_v3.py cup` style export (Gerber, drill, BOM `C` numbers from `parts.json`, CPL with the rotation table), check the unverified footprints listed in `ORDER.md` (HJ-840, J1, SW1, LD1, BZ1, U8).
