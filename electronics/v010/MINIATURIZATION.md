> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). Water only. Study for the coordinator / mechanical v010 owner, 2026-11-19.

# v0.1.0 board: how small can it get with the full safety circuit?

Question: bench pod envelope plus only battery + electronics, ideally no 22 mm tail; evaluate smaller radios, 0402/0201, both sides, L-shaped / two-part boards.
Method: real numbers from `netlist.json` (courtyard areas of the actual footprints, `tools/miniaturize.py`) and JLC stock/price lookups (`tools/jlcq.py`, 2026-11-19). **No safety element is removed in any scenario** (series chain + OC leg, two series P-FETs, 2oo2 dock halls, TPL5010 + DONE qualifier + latch, OC comparator + latch, HW-A, readbacks, bleeder).

## 1. Where the area goes (current design, 185 placements)

Sum of courtyards (no DNP) **1499 mm2**; the 102 passives are only **235 mm2**, the 74 other parts **1264 mm2**:

| Part | mm2 | Comment |
|---|---|---|
| E73 module (13 x 18 courtyard) | 282 | 19 % of everything |
| Buzzer MLT-8530 8.5 x 8.5 | 86 | alarm path |
| PicoBlade 4-pin | 83 | 12 x 6.9 courtyard |
| SN74LV4040 TSSOP-16 | 44 | HW-A counter |
| Button TS-1187A | 43 | |
| Tag-Connect pads | 29 | |
| 20 x SOT-23 (2N7002 chain, P-FETs, ...) | about 170 | interlock legs |
| ICs STSPIN220, INA180, TPL5010, MCP73832, 4 x VSSOP FF, 5 x SOT-23-5 gates, ... | about 200 | |
| charge pads, spring contacts, hall, TMAG | about 60 | |

Consequence: **0201 passives alone save only about 85 mm2** (0402 courtyard 2.0, 0201 1.2 mm2). The radio, the connector and the SOT-23 legs matter more. The routed fill target for 4 layers is about 0.6 of both sides (architecture: calibrated on the bench boards; this design was not routable at fill 1.0, see README).

## 2. Radio candidates (JLC, 2026-11-19)

| Module | Size | Antenna | JLC stock / price | Assembly | Firmware impact | Verdict |
|---|---|---|---|---|---|---|
| **Ebyte E73-2G4M08S1C** (C356849) | 13 x 18 x 2.4 | ceramic, integrated | stock **1**, $7.70 | JLC | none (bench-proven map) | current; stock problem (CX C2764963 has 729 pcs but an IPEX connector) |
| **HJSIP HJ-840** (C50052094) | **6.2 x 7.0 x 1.0**, LGA-64, 0.65 mm pad pitch ("suitable for 2-layer boards", 48 GPIO) | `ANT` and `BOARD_ANT` pads: needs a chip antenna / PCB antenna and a pi match on the host board (about 5 x 3 mm + keep-out) | stock **95**, $7.96 | JLC (extended) | **nRF52840: same firmware**, new pin table only; datasheet V1.1.1, no Nordic-partner RF certificate known (VERIFY) | **best candidate**: saves about 200 mm2 |
| Insight SiP ISP1807-LR (C5264268) | 8 x 8 x 1.0 | integrated | stock 0, $12.23 | consigned (PARTS-LOCK) | nRF52840, same | smallest self-contained; consignment lead time; inner pads need via-in-pad |
| Raytac MDBT50Q-1MV2 / -P1MV2 (C5118826 / C5119772) | 15.5 x 10.5 x 2.2 | chip / PCB | stock 0 | consigned | nRF52840 | 155 mm2, no gain over E73 worth the re-spin |
| Fanstel BC840M (C5447804), BT840 family, BM840-V1 (C5211276) | 7.1 x 12.2 (BC840M) | PCB trace | stock 0 | consigned | nRF52840 | out of stock at JLC (BM840/BT840 not offered as listed) |
| Minew MS88SF2 / MS88SF3 | 18.5 x 12.5 / 17.4 x 23.2 | ceramic | stock 0 | consigned | nRF52840 | larger than E73, no gain |
| Bare nRF52840-QIAA aQFN-73 7 x 7 (C190794, 43 301 pcs, $7.59) or WLCSP 3.5 x 3.6 (C3606750, 1762 pcs, $7.32) | 49 mm2 | chip antenna + matching | JLC | JLC | nRF52840, same | smallest, **RF layout + 32 MHz and 32 kHz crystals + DC/DC inductor + VNA tuning**: reject for v0.1.0 (as ARCHITECTURE 3.1) |
| nRF52833 (C2895249 QFN-40 5 x 5, 17 140 pcs) | 25 mm2 | external | JLC | JLC | **different SoC** (192 kB RAM, 512 kB flash, 33 GPIO, no USB-HS? same Embassy family but new HAL/linker/memory map) | not "same firmware"; flash 512 kB must hold MCUboot + core + diag: VERIFY |
| nRF54L15 modules (Raytac AN54LV-15 6.4 x 8.4) | 54 mm2 | chip | not on JLC | consigned | **new firmware port** | v0.2 |

**Recommendation: HJ-840 (nRF52840) + 2.4 GHz chip antenna with pi match on the board edge.** Open items: antenna part (e.g. a 3.2 x 1.6 mm ceramic chip antenna, JLC stock to check), RF keep-out per the HJ-840 reference design (section 3.2 of its datasheet), certification, pad map (29 GPIOs are needed, 48 exist: all of them fit with spares, the analog-capable set must be checked against the pad table), and stock 95 pcs. Fallback if the module is unavailable: E73 as now.

## 3. Area scenarios (courtyard sum / board area at fill 0.6 and 0.7 on both sides)

| Scenario | Changes (cumulative) | Courtyard sum | Board area @0.6 / @0.7 |
|---|---|---|---|
| S0 now (E73, 0402/0603/0805) | built | 1499 | 1250 / 1070 mm2 (46.7 x 29 = 1354 built) |
| S1 + HJ-840 + chip antenna + pi match | -200 | 1300 | 1080 / 930 |
| S2 + 0201 passives | -85 | 1215 | 1010 / 870 |
| S3 + motor spring pads instead of PicoBlade (4 pads 2.6 x 1.8, spec 1c "no cable" as Rev B; needs the motor with a short FPC tail or pads on a 3D-printed carrier) | -58 | 1157 | **965 / 830** |
| S4 + SOT-23 legs -> SOT-523/DFN1006 where JLC stock exists (unchecked) and a 4 x 3 button | about -90 | about 1070 | about 890 / 760 |

For comparison the bench interior to the right of the reservoir is 17.3 x 30.2 = **522 mm2**. Even S4 at fill 0.7 needs about 760 mm2: **a 14 mm tail is the minimum (board about 31 x 29), a 22 mm tail is the comfortable value; a tail-free board is not possible** with the complete safety circuit unless the BLE part is moved off the pod, which the user's goal (all on board) excludes. Dropping elements to gain area is **not** done here (no safety element removed): e.g. the second series P-FET (9 mm2), the second hall (3 mm2) and HW-A (about 130 mm2 incl. decoupling) would save 140 mm2 together, but they are exactly the elements added for the single-fault findings.

## 4. L-shape / two-part board

* The CAD (mechanical/out/bench/OP-100.mech.json) has **no free volume beside the motor lane or behind the reservoir**: the NFP motor axis is at z 4.2 (diameter 6.0, top z 7.2), the reservoir is 6.6 mm high from the floor, the gear pair and leadscrew lane fill y 17 to 31 for x < 28.4. The board bottom plane (z 5.3) cannot pass over them. All usable board volume starts at x_r1 + 2.6 (28.4 for OP-100).
* Beyond x_r1 the usable region is: (a) the leg over the dock channel (only dock halls below, parts up to 1.5 mm above), (b) the battery bay (bottom 0.8 mm), (c) the tail. A two-part split gains **no area** (the sum of the courtyards is unchanged); it only lets a thin second board occupy the 4.4 mm of free air above the floor in the tail (as a stacked daughter board), at the cost of a board-to-board connection that must be solder-free (spring contacts: 2 x 6 pogo/finger contacts, about 6 x 3 mm) and 1.0 mm of stack height. That is a possible way to **fold** the tail (about -40 % length) if the tail height allows a second layer: bottom parts up to 4.2 mm are only the E73 (2.4), buzzer (3.0) and PicoBlade (3.3), so with HJ-840 (1.0 mm) and spring pads a **two-layer tail** is feasible. Quantified: S3/S4 split into a 17.1 x 29 main board (dock leg + battery bay top side parts, TMAG, halls, springs) and a 15 x 29 tail board stacked on the tail floor would fit about 970 mm2 of courtyards at fill 0.6 in **31 x 29 total footprint**.

## 5. Candidate outlines for the mechanical v010 agent

Frame as `board.layout.json` (bx right, by up, origin x_r1 + 2.6, y 1.5; all dimensions parametric in `board/params.json`, set `outline.w`).

| Candidate | Outline (board frame) | Pod length OP-100 | Content |
|---|---|---|---|
| **C1 (recommended next spin)** | rectangle **31.0 x 29.0**, R2.5 (tail 14.3 mm); zones as `params.json` with `tail_free_air` x 17.1..31; antenna chip + keep-out at the +x end, x 27.5..31, y 18..28 | 47.0 + 14.3 = **61.3 x 32 x 8.5 mm** (12.5 cm3) | HJ-840, 0201, spring motor pads, no boost, S3 |
| C2 (aggressive) | rectangle 27.0 x 29.0 | 57.3 mm | S4, fill 0.74: routing risk (4 layers, tight) |
| C3 (folded) | main 17.1 x 29 + tail board 15 x 29 stacked on the floor (z 0.9..4.2) | 47.0 + 11 = 58 mm | S3, spring B2B (6 contacts), assembly of two PCBs |
| built here | rectangle 46.7 x 29.0 | 77 mm | E73 variant, 185 parts, the board in this directory |

The architecture's 22 mm tail (38.7 mm board) is **not enough for the E73 variant** and about right for C1 with E73 swapped for HJ-840 plus fill 0.8 (not recommended). C1 with its 14 mm tail is what the full safety circuit needs; going shorter requires dropping parts or a higher fill than 4-layer 0.8 mm Freerouting reached (`README.md` routing section).

## 6. Not verified / next actions

* HJ-840 stock (95), footprint (LGA-64 0.65 mm, datasheet section 7), pad map and RF reference design; chip antenna selection and certification.
* 0201 assembly acceptance and cost at JLC (setup fee unchanged; 0201 basic parts list not checked).
* SOT-523 / DFN1006 MOSFETs and their JLC stock, a 4 x 3 mm 1.5 mm switch.
* A real routing run of C1 (needs the HJ-840 footprint and the antenna land pattern): not done in this work package.
