> TEST ONLY - NOT FOR HUMAN USE (see ../../../DISCLAIMER.md). Water only, never worn.

# CUP board: net-by-net hand-routing guide (KiCad 10)

## STATE 2026-11-20 (54 fitted parts + 19 bare pads, outline with USB notch): what is routed, what is left

**Board:** `cup/cup.kicad_pcb`, 6 layers 0.8 mm, 35.6 x 23.1 mm, 85 footprints. Flow: `place_cup.py` (SA + legaliser, seed 6, overlap 0.25 mm2 courtyard level) -> `pinassign.py` -> `design/netlist_v4.py` -> `build_cup.py` -> `flow_cup.sh` (Freerouting 2.2.4, rules 0.10 / 0.10, power class 0.16 on VBAT, VMOT, VMOT_PRE, BST_SW, MOT_*, VBUS_P; edge keep-out band 0.3 mm; screw keep-outs) -> `post_cup.py`.

**DRC (`drc.json`): copper errors 0 except 7 `starved_thermal` (GND pads whose zone connection is cut: they are part of the open list), 73 connections unconnected.** Warnings: courtyards overlap 85 (placement margin 0.08 mm), silk over copper 68 (silk only).

Freerouting plateaued at 66 to 73 open connections in three runs (900 s: 81, 1500 s: 66, 6 minutes / 12 passes: 72); more time did not help. The board is **not orderable**. Open connections by net (full list with pads and positions: `open_connections.txt`):

| Net | Open | Net | Open | Net | Open |
|---|---|---|---|---|---|
| `3V3` | 13 | `SUP_NRST` | 5 | `GND` | 4 (pours) |
| `DOCK_N` | 4 | `LATCH_Q`, `SUP_PERMIT`, `VBAT` | 3 each | `USB_DP`, `BPHASE`, `APHASE` | 2 each |
| 24 other nets (`ANT_A/B`, `BUZ_A`, `SUP_TXD/RXD/BOOT0/OK/DONE/WAKE`, `PZ_C`, `MOT_ALLOW/PERM_L/DOCK_XOR`, `OC_OK`, `USB_DM`, `LATCH_CLR_N`, `MOT_A1/A2/B2`, `MCU_EN`, `I2C_SCL/SDA`, `CHG_STAT`, `LED_R/G/A`, `AENBL`, `VMOT/VMOT_SENSE`, `WDT_DELAY`, `ILIM`, `BST_SW`) | 1 each | | | | |

**Why it stalls (diagnosis from the open list):**
1. The placement optimiser minimises wire length of rectangles and does not know the router. Result: the boost loop is split (`U8` at x 16.5 but `L1` at x 41.9 on the leg: `BST_SW` is open), the motor driver `U7` sits at x 30-32 while the motor pads `MP1-MP4` are at x 10-12.5 (`MOT_A1/A2/B2` open), and the 3V3 rail has 13 open stubs because the gates, TPL5010, supervisor and hall are spread over the leg and the module neighbourhood.
2. The module side is dense: HJ-840 0.9 x 0.65 mm LGA with 0.30 x 0.40 mm pads leaves one track per channel (0.35 mm gap), and 14 of its pads are used by the supervisor, the gates and the LED / motor GPIOs next to it.
3. The 19 bare pads (TP1-TP14 + 5 SWD) take about 25 mm2 of the 250 mm2 of usable top copper.

**What to do next (in this order):**
1. **Hand-route in KiCad** (fastest): the 73 open items are mostly 1 to 5 mm stubs between neighbouring parts. Use the order below (USB, VBAT, BST_SW, VMOT_PRE, VMOT, MOT_*, then 3V3 and the signals); the net names of the table further down are partly from the old netlist, the current names are in `netlist_v4_cup.json`. Re-run `post_cup.py`, DRC, `../tools/export_cup_jlc.py`.
2. **Or re-place**: weight the power nets in `place_cup.py` (`BST_SW`, `VMOT_PRE`, `MOT_*` x4, group cohesion of the boost block: `U8 L1 C71 C5 CB1 R55 R56` within 6 mm; `U7 C21 C61` within 8 mm of `MP1-MP4`), keep `L1` on the lane-2 top side, and give the test pads the leg and the hall finger only. Then run `flow_cup.sh` again (about 25 minutes).
3. **Or relax the board**: moving the test pads TP1-TP14 to a separate break-off strip of the JLC panel would free 25 mm2 and 14 nets of routing; the owner decides because the pads were requested (review M4, M5).

**Verified on this board:** all 8 review items (`review/REVIEW-CHECK.md`, `review/overlay_top.png`, `overlay_side.png`), screw holes d1.4 NPTH with d2.8 keep-out, USB-C notch and the real HRO pad row, SW1 near the north edge (mechanics must move the flex window +3.0 mm), BZ1 on the widened leg 8.8 mm from the hall.

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
