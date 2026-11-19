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

## 7. Low-profile variant LP (coordinator request after `mechanical/V010.md` section 8): lid-side radio, spring motor contacts, piezo, 301012 cell

Mechanical result to design for: E73 (2.25 mm, bottom) + PicoBlade 3.4 mm = **74.15 mm** pod (OP-100); radio <= 1.3 mm on the lid side = **~55 mm**; plus flat motor contacts instead of the PicoBlade = **~48 mm**. Zones of `mechanical/out/v010/OP-100.layout.json`: dock tunnel y 3.5..15.9 (bottom parts: halls only), strip y 15.2..29, top parts <= 1.3 mm, battery bay x 11.55..25.05.

**Important finding for the E73 board in this directory:** the first version of `board/params.json` (22 mm tail) put the E73 and bottom passives at y 1.7..14.7, i.e. under the dome path. The dock tunnel runs the whole length of the board (to x 44.85), so **all tall and bottom parts must sit in the strip y >= 15.2** (about 560 mm2 including the cell bay). `params.json` now carries the mechanical zones; the E73 variant is placed accordingly (E73 at (35.05, 21.7), PicoBlade at (8.15, 23.9), cell bay as given) and a tail beyond x 44.85 (9.75 mm, board 54 mm) holds the buzzer and overflow.

| Item | LP choice | LCSC / route | Status |
|---|---|---|---|
| Radio, lid side | **Insight SiP ISP1807-LR 8 x 8 x 1.0**, integrated antenna | `C5264268`, stock 0, $12.23; **JLC route = consignment** (PARTS-LOCK: the ISP1807 is sent to JLC for PCBA, extra lead time and handling fee; JLC does not stock it) | needs the ISP1807 land pattern (LGA 62, inner pads: via-in-pad, ENIG, filled vias at extra cost), pin map from the older `electronics/pin-assignment.md`, clear-lid antenna keep-out (about 8 x 3.5 mm at the board edge, no copper on any layer, no metal within about 5 mm): **not built** |
| Alternative <= 1.3 mm radio | **HJSIP HJ-840 6.2 x 7.0 x 1.0** + 2.4 GHz chip antenna | `C50052094`, stock 95, $7.96, JLC assembles | antenna chip (3.2 x 1.6 mm) + pi match, keep-out in a clear lid; nRF52840 firmware unchanged except the pin table; **not built** |
| Motor contact | 4 x SMD spring contact **BWCD-L3.5W2.0H1.0** (3.5 x 2.0 pad, 1.0 mm free height, gold, 8081 pcs, $0.076) on the motor pins | `C2826547`, extended | **Geometry open:** the Rev B motor contacts of the CAD (`contacts.motor_fpc`: pod x 22.6..24.1, y 25.7, z 4.0) and the NFP pins (pod x 15.9) are **left of the board edge** (board starts at pod x 28.4; the notch polygon only removes y < 18.8). The board needs a 6.5 mm tab toward -x at y 24..29, or the motor FPC tail must come to the board: mechanical owner to decide |
| Buzzer | **Murata PKMCS0909E4000-R1** 9 x 9 x 1.0 piezo, top side | `C910763`, stock 1424, $0.86, extended | needs a bridge drive: BUZ_PWM and its inverse (one more 2N7002) each pulling one electrode low against 1 k pull-ups to VBAT = about 4 Vpp at the 4 kHz resonance, about 15 mA, quieter than the MLT-8530 (95 mA); loudness VERIFY. Replaces BZ1/D7/R70 (LP netlist variant **not generated**) |
| Cell | 301012 class, 13.5 x 10.2 x 3.2, about 30 mAh, 2 spring contacts (`C2826547`) | AliExpress cell | 30 mAh x 0.85 x 0.8 = 20 mAh usable vs 10.8 mAh for 72 h: ok; peak 160 mA = 5.3 C: VERIFY R_int; spring gap 0.55 mm vs 1.0 mm free height: thinner spacer or 1.2 mm contact |
| Charge pads | 2 x 3.0 x 3.0 ENIG, 6 mm pitch at (30.05, 19.5) / (30.05, 25.5) | pads only | already at the mechanical positions in `params.json` (footprint still 4 x 3) |
| Button | CAD: 3.0 x 2.6 x 0.55 switch, membrane d5 at (22.85, 23.0); TS-1187A is 5.1 x 5.1 x **1.5 mm > 1.3 mm** top limit | no JLC part found | open |

Area check: the top side is the only place for the 185 parts when the radio is on the lid side: board 44.25 x 29 is about 1190 mm2, minus notch, keep-outs and pads about 1030 mm2 net; the courtyard sum of the LP content is about 1060 mm2, i.e. **fill above 1.0 on the top side**. **Scenarios B/C of the mechanics (55 / 48 mm pod) are therefore not reachable with the complete safety circuit at 0402 on one side.** Options: (a) a top-side tail of about 10 mm (LP pod about 58 mm); (b) 0201 + SOT-523 parts plus the stacked two-part board of section 4 in the 4.2 mm tall strip; (c) moving HW-A (about 130 mm2) off the pod: **rejected** (it must be in the cut path). The mechanical v010 agent should plan for **LP about 58 mm**, not 48 mm.

## 8. Hard target OP-100 <= 45 mm (spec 2b): what area does the complete safety circuit need?

Boundary conditions from the coordinator: board + parts + cell about 3 mm above the dock tunnel, board 0.6 to 0.8 mm, lid-side parts <= 1.3 mm, bottom <= 0.4 mm over the tunnel (only 0201 passives and the dock halls qualify, 0402 caps are 0.5 mm), spring contacts for motor and cell, cell 301012 (3.0 x 10 x 12 = 120 mm2) possibly beside the board. Inside a 45 mm pod the electronics zone is **x_pod 28.4 .. about 45.5 = 17.1 mm long x 29 wide = about 490 mm2** (tunnel top y 3.5..15.9 about 210 mm2 where the bottom is blocked; strip y 15.2..29 about 240 mm2 where both sides and 4.2 mm of bottom height are free).

**Discrete circuit as built: does not fit.** Courtyard sum of the LP content (HJ-840 or ISP1807 on the lid, piezo, spring pads, 0201) about 1060 mm2 = 2.2 x the whole zone at fill 1.0.

**Compacted circuit (estimate, all safety functions kept).** The only large reduction is to replace the discrete cut-path logic (HW-A window/counter/gates/Schmitt, DONE qualifier, latch, OC comparator + latch, power-up RCs, inverters: about 45 parts and about 330 mm2) by **one mixed-signal matrix IC**, e.g. Renesas **SLG46537V** (STQFN-20 2 x 3 mm, `C5754299`, stock 10, $1.62; comparators, counters, DFFs, LUTs, oscillator, one-time NVM) or SLG46140V (`C6488613`, stock 45). The series 2N7002 gate legs stay discrete (at least the MCU_EN, dock/dir and one matrix leg, independent FETs), the two series P-FETs, TPL5010, INA180, STSPIN220, 2oo2 halls and the readbacks stay. Cost: the matrix IC is a common-cause element for the legs it drives (the MCU_EN leg and the dock/DIR leg remain independent of it), its configuration needs a formal review and a programming step (consigned pre-programmed parts or a jig; not a builder task), and JLC stock is thin.

| Block (compacted) | mm2 |
|---|---|
| HJ-840 + chip antenna + pi match (or ISP1807 + keep-out) | 80 |
| STSPIN220, INA180, TPL5010, MCP73832, LDO, SLG46537, 32 kHz crystal | 82 |
| 2 series P-FETs, 5 gate/utility NFETs, 2 buzzer-bridge NFETs, TVS (SOT-23 / SOT-523 mix) | 75 |
| TMAG5273, 2 dock halls | 18 |
| Piezo 9 x 9 x 1.0 | 81 |
| 6 spring contacts (cell 2 + motor 4), 2 charge pads 3 x 3 (6 mm pitch) | 60 |
| Button (3 x 2.6 class), LED | 14 |
| Tag-Connect pads + 10 test pads (shared) | 40 |
| About 55 passives in 0201 (1.2 mm2 each) | 66 |
| **Total courtyard** | **about 520 mm2** |

Two sides: top for everything >= 0.5 mm, bottom only in the strip (y >= 15.2, up to 4.2 mm, about 240 mm2) plus 0201 / halls over the tunnel. Usable placed area about 490 (top) + 300 (bottom) = 790 mm2 -> **fill about 0.66 (+-0.1)**: borderline for 4 layers, 0.15 mm rules (the fill at which the built E73 design needed a longer board, section 1). Uncertainty of the estimate about +-25 %.

**Minimum board / candidate outline (estimate):** **17.7 x 29.0 mm rectangle (about 510 mm2), x_pod 28.4 .. 46.1**, R2.5, tunnel zone and strip zone as in `mechanical/out/v010/OP-100.layout.json`, cell bay (12 x 10, bottom, springs only) in the strip y 18..28.2, lid-side radio at the right edge with the antenna keep-out (8 x 3.5, clear lid) and the piezo on the strip top; pod length **47.0 + about 1 mm = 48 mm for OP-100**, i.e. **the 45 mm target is not reachable (3 mm short)** because the bench body itself is 47.0 mm; any <= 45 mm pod needs the dome/tunnel and the reservoir end re-arranged (V010.md section 8 front-compaction study), not a smaller board. Without the matrix IC (discrete interlock + HW-A) the minimum is about 1060 mm2 of courtyards, i.e. a **board of about 38 x 29 mm (1100 mm2 at 0.6 two-sided) and a pod of about 70 mm**, as built here.
**Not verified:** all areas are courtyard sums from KiCad footprints and datasheet outlines (tools/miniaturize.py), not a routed result; SOT-523/0201 stock and the SLG46537 stock (10 pcs) and design verification are open.

## 9. Target board <= 300 mm2 (about 15 x 20 mm), total height <= 3 mm, cell beside: evaluation and recommendation

**Verdict: reachable on paper at about 270 to 300 mm2 only with a tiny independent supervisor MCU (variant S) and the rules below; the discrete multi-gate variant (D) needs about 380 mm2. Nothing was routed or built for this section: areas are courtyard estimates (+-25 %).**

### 9.1 Safety chain: tiny supervisor MCU (S) versus compact discrete (D)

| | D: discrete, multi-gate packages | **S: supervisor MCU (recommended)** |
|---|---|---|
| Content | 3 x SOT-363 dual 2N7002 (`C83571`, 97 k pcs) for the 5-leg chain, dual P-FET, TPL5010, 4 FF + 4040 counter + 5 gates + Schmitt + RCs, INA180 + TLV7011 + latch | one MCU (e.g. **MSP430FR2000** QFN 3 x 3 `C2053947` stock 135 or **STM32C011J4M6** SO-8 `C5456172` stock 1101, $1.0; no WLCSP 2 x 2 part is stocked at JLC) with own RC clock, own supply pin from the same LDO but its own decoupling, 1 to 2 kB of firmware |
| Functions | fixed hardware, verified by SPICE and truth tables | watchdog **challenge/response** (replaces TPL5010 + DONE qualifier + latch: it closes the "toggling DONE" gap of the bench), arm window + counts `STCK` pulses itself with a timer and gates `STCK_DRV` through one AND gate, OC latch timing, **leaky bucket 15 U/h and 1.7 U/min = HW-B of security proposal 07 for free** (Rev B item pulled into v0.1.0), drives its own series leg |
| Kept discrete in both | series P-FET pair, **MCU_EN leg and dock/DIR leg as independent NFETs** (not through the supervisor), 2oo2 halls, INA180 + hardware OC comparator (TLV7011) clearing the gate, bleeder | same |
| Area (courtyards) | about 230 mm2 | **about 90 mm2** (MCU 15, AND gate 5, 2 dual NFET 14, P-FET pair 7, INA 12, comparator 5, about 30 0201 passives 30, misc 2) |
| Independence | physically independent legs, no software | **diverse**: different core (Cortex-M0+ or MSP430 vs Cortex-M4), own clock and flash, firmware reviewed and formally checked separately (Kani on about 100 lines, `security/proposals/07` section 4), read-out protected, provisioned only by wire (SWD pads); it **can only remove permission** (it is one more AND leg and the STCK gate): a failing supervisor cannot cause delivery, the MCU_EN leg, dock/DIR leg and OC comparator remain independent of it. Residual: a supervisor that wrongly stays "permitting" leaves the other legs; a hung supervisor starves its own watchdog window (it is itself reset by an on-chip watchdog and its outputs default to no permission) |
| Cost / risk | none new | software item (IEC 62304 class C unit) in the cut path; needs its own test and a second programming step at production; JLC stock 135 / 1101 |

Recommendation: **S**, with the two discrete independent legs and the discrete OC comparator kept (they are exactly the elements the single-fault analysis needs), and the supervisor firmware limited to counters and comparisons (no radio, no parsing, no dynamic memory). If the project insists on "no software in the cut path", use D and accept about 380 mm2.

### 9.2 Area per function block (variant S, 0201, both sides)

| Block | mm2 | How |
|---|---|---|
| Radio | 74 | ISP1807 8 x 8 x 1.0 (integrated antenna, **internal 32 kHz crystal: no crystal parts**, consigned) or HJ-840 + chip antenna (about 85, JLC stock 95) |
| Driver + sense | 40 | STSPIN220 3 x 3, 2 x 1 ohm (0402), 22 uF 0805 + 10 uF 0603, VREF divider fed from STBY, 0.22 ohm shunt |
| TMAG5273 + decoupling | 17 | fixed position under the spindle magnet |
| Dock halls (2) | 6 | X2SON, bottom, 0.4 mm |
| Charger | 12 | **BQ25100A DSBGA-6 0.9 x 1.4** (`C2871910`, stock 25, $2.2, 0.4 mm pitch) + 3 x 0201; fallback MCP73832 SOT-23-5 (+10 mm2) |
| LDO | 9 | XC6206 SOT-23 or a DSBGA LDO (about 5) |
| Battery sense + NTC | 8 | switched divider, 1 x SOT-523, 0201 |
| Safety chain (S) | 90 | see 9.1 |
| SWD | 6 | 4 pads 0.8 x 0.8 (SWDIO, SWDCLK, RESET, GND) at 1.27 mm, spring probe jig; **no Tag-Connect field** |
| LED 0402 + R | 3 | |
| Button | 10 | small side-actuated tact (no JLC part verified); **keep it**: physical confirmation of dangerous commands (security proposal 07 section 3) and pairing; an alternative trigger without a switch would be a magnet tap on a hall, which the dock/spindle fields make unreliable: not recommended |
| Off-board spring pads | 12 | piezo (glued to the lid, 2 pads), charge pads in the lid (2 pads), the sources of the lid contacts |
| Cell + motor spring pads, bottom | 48 | 6 x BWCD-L3.5W2.0H1.0 (`C2826547`) pads: bottom side only |
| Decoupling and misc | 15 | |
| **Total courtyard** | **about 350** | top about 265, bottom about 88 (0201 passives and spring pads) |

Both sides at fill 0.6 to 0.65 -> **about 270 to 300 mm2**: candidate outline **15.6 x 19.5 mm (304 mm2), x_pod 28.4 .. 44.0, y_pod about 5 .. 24.5**, which covers both fixed sensor positions (TMAG pod (30.2, 22.5), dock hall pod (43.8, 11.2) at the right edge), R1.5 corners, the antenna edge at the top, cell beside (301012: 12 x 10 x 3.0) in the strip beside it. Without S (D): about 450 mm2 courtyard -> about 380 mm2 board. With E73 (not low-profile) none of this applies.
Layers: 4 layers is the limit for Freerouting at this density; plan **6 layers 0.8 mm with via-in-pad** (ISP1807 inner pads and the BQ25100 DSBGA need it) for a real attempt; the fill of 0.6 is an estimate from the built board, not a promise.

### 9.3 BOM cost delta per board (list prices, 2026-11-19) and JLC assembly

| Change | Delta USD |
|---|---|
| E73 7.70 -> ISP1807 12.23 (consigned) | +4.5 |
| MCP73832 0.96 -> BQ25100A 2.21 | +1.2 |
| remove 4 FF, 4040, 5 gates, Schmitt, TPL5010, TLV latch (about 8.6) | -8.6 |
| add supervisor MCU (1.0 to 1.3), AND gate, 2 dual NFET (0.2), dual P-FET | +1.6 |
| piezo 9 x 9 (`C910763`) replaces MLT-8530 | +0.7 |
| 0201 passives instead of 0402 | about 0 |
| **Parts per board** | **about 22 -> about 22 (+-3)** |
| Extended-part fee: 21 lines -> about 16 lines | -15 per order (the supervisor and the consigned part keep it from dropping further) |
| Consignment handling for the ISP1807 (JLC fee, extra lead time) | + about 20 to 40 per order (unknown, ask JLC) |

JLC assembly: **yes for everything except the radio route**: 0201, SOT-363/SOT-523, QFN-24, STSPIN220, DSBGA-6 (stock 25, ask JLC about 0.4 mm WLCSP placement) are standard; the ISP1807 must be **consigned** (stock 0, LGA 62 with inner pads, X-ray check recommended); the alternative HJ-840 is JLC-assemblable (stock 95) but needs its antenna design. Spring contacts BWCD (8081 pcs) and piezo (1424 pcs) are in stock. Risks: DSBGA and ISP1807 stock, via-in-pad cost and lead time, supervisor firmware programming (no JLC programming service for custom firmware: pre-programmed parts or a jig), and everything in 9.2 being estimates.

## 10. Waterproof USB-C (spec 2d) and the three-board split (MAIN / USB-CHARGE / SENSOR)

Charge pads are dropped; USB-C (charge + flash + CDC log) replaces them. Estimates, nothing routed.

### 10.1 IPX7 USB-C receptacle: what JLC can give

I could **not verify an IPX7 rating for any JLC-library USB-C part** (the JLC parts API carries no ingress rating; searches for IPX7/IP67/IP68 return only a 3.5 mm audio jack, `C3151741` PJ-825 IPX7, which is not USB). Candidates to verify with the vendor datasheet before ordering (all extended parts, JLC-assemblable, 16 P power+USB2.0, none claims a rating in the library): **XKB U262-161N-4BVC11** `C319148` (stock 33 592, $0.41, 7.3 mm deep, right-angle SMD), **G-Switch GT-USB-7010x** (`C2843967`, `C2837092`, `C3001293`, stock 789 to 7455), **Korean Hropart TYPE-C-31-M-12** `C165948` (bench part, 501 900 pcs, **not waterproof**), GCT USB4105-GF-A `C3020560` (not waterproof). Typical dimensions (VERIFY): body 8.9 x 7.3 (to 10 mm incl. shell) x **3.2 mm** high for a top-mount; a mid-mount/sink-type (board notch, receptacle half below the board) is about 2.6 mm above the board. Waterproof types are sold by Korean Hropart / Shou Han / G-Switch as "TYPE-C waterproof 16P / 6P" with a silicone gasket: **action: the mechanical/purchasing owner asks the vendor for the IPX7 drawing and LCSC code; this study cannot supply one.** The 3.2 mm height does not fit the 3 mm stack: the receptacle must sit at the pod **edge** on its own board (10.2) with a lid cut-out, as the coordinator proposes.

### 10.2 USB on the radio module

| Module | USB pins | Note |
|---|---|---|
| E73-2G4M08S1C | **VBUS (pad 27), D- (29), D+ (31)** exposed (bench pin table: unconnected there) | usable |
| ISP1807 | VBUS, D+, D- exposed per the Insight datasheet (**VERIFY the land pattern**; the older `electronics/pin-assignment.md` ISP1807 map lists the USB pads) | usable |
| HJ-840 | pad grid excerpt shows no D+/D- (only P0/P1 GPIO, SWD, DEC5, ANT); **VERIFY**, if absent USB cannot be used and the module is out | likely not suitable |
| nRF52833 / nRF54L15 | USB FS on nRF52833, none on nRF54L15 (no USB) | different SoC |

USB side circuit (on the USB-CHARGE board): CC1/CC2 5.1 k pull-downs (sink), TVS on VBUS (SMF5.0A `C193402`), P-FET ideal-diode/reverse + OVP (6 V) stage, **USBLC6-2SC6** (`C7519`, bench part) on D+/D-, 10 uF + 1 uF, VBUS sense divider (the module needs VBUS on its VBUS pin to enable USB). Charger IC stays on MAIN (VBUS_PROT in).

### 10.3 Boards, areas, interconnect (OP-100, all estimates)

| Board | Content | Outline x height | Area | Layers |
|---|---|---|---|---|
| **SENSOR** | TMAG5273 (SOT-23-6, bottom, 1.45 mm) + 2 dock halls (X2SON, bottom 0.4 mm) + 4 x 0201 + 2 pull-ups, 8-pin FFC contact | **about 9 x 12 mm**, 0.6 mm, top <= 1.3 | about 110 mm2 | 2 |
| **USB-CHARGE** | receptacle (mid-mount) + TVS, ESD, 2 x CC resistor, ideal-diode P-FET, OVP, caps, 6-pin FFC contact | **about 12 x 10 mm** at a pod edge, height of the receptacle 2.6 to 3.2 mm | about 120 mm2 | 2 |
| **MAIN** | radio (ISP1807 or E73) + STSPIN220 + supervisor-MCU safety chain (9.1 S) or the discrete chain, charger, LDO, sense, LED, button, SWD pads, 2 FFC ZIF connectors (8 + 6 pin, 0.5 mm, 1.0 mm high class) | about **15 x 19 mm** (S), about 20 x 20 mm (D) | about 285 mm2 (S), about 400 mm2 (D) | 4 to 6 |
| Total | | | **about 515 mm2 (S)** vs about 300 mm2 for the single board of 9.1 | |

The split costs about +215 mm2 (two ZIF connectors 2 x 15, board edges and keep-outs of three outlines, the receptacle footprint 65 mm2 instead of the removed charge pads) but lets each board sit where its height allows: SENSOR at the spindle magnet (TMAG pod (30.2, 22.5)) and the dock tunnel end (hall pod (43.8, 11.2)) as one FFC-linked strip, USB at the edge with the receptacle height, MAIN above the tunnel.
Interconnect (solder-free for the builder: FFC + ZIF connectors assembled by JLC, the cable is only inserted; spring contacts are the alternative): **MAIN-SENSOR** 8 pins: 3V3, GND x2, SDA, SCL, DOCK_N, DOCK_NB, TMAG_INT (reserve); **MAIN-USB** 6 pins: VBUS_PROT, GND x2, D+, D-, VBUS_SENSE/CC (reserve). Parts: 2 ZIF connectors per cable end pair = 4 connectors (JLC: e.g. Hirose FH12-8S-0.5SH `C...` / the FH12-10S `C506791` of the bench; these are 2.0 mm tall (CAD note): **a <= 1.0 mm FFC connector is still an open point**, or use spring contacts (2 x 8 BWCD-class `C2826547`, 1.0 mm) between stacked boards) and 2 FFC cables (0.5 mm pitch, 30 to 50 mm, $0.5 to 1).
Panel: the three boards in **one JLC panel / one PCBA project** (tab-routed with mouse bites, the SENSOR and USB boards 2-layer 0.6 mm is not possible in one 4-layer panel: JLC allows one stackup per order, so all three are 4-layer 0.8 mm or the SENSOR/USB boards are ordered as a second, cheap 2-layer order).

### 10.4 Cost delta (list prices; fees estimated)

| Item | Delta per pod USD |
|---|---|
| IPX7 USB-C receptacle (assume $1 to 2) replaces 2 charge pads (0) and adds USBLC6 0.2, TVS (already), 2 CC resistors, P-FET 0.1 | +1.5 to +2.5 |
| 2 FFC cables + 4 ZIF connectors | +2 to +4 |
| two small extra boards (PCB share) and handling | +3 to +6 |
| **Total per pod** | **about +7 to +12 USD**; one-time: second panel or stackup order about +10 to +20, vendor IPX7 sample cost unknown |

### 10.5 Firmware and safety notes (USB must not bypass authorisation)

* USB is a **second transport for the same authenticated session layer**, not a privileged channel: CDC carries only the diagnostic/log stream (read-only `GetFaultLog`, `GetDiagSummary`, RTT-style text) and the **same signed, AEAD-protected commands as BLE after pairing**; no unauthenticated command, no dosing command without an authorised session, no limit change (`security/proposals/07`: dangerous commands need the physical button within 30 s).
* DFU over USB: MCUboot **signed images only**, anti-rollback, started only with the button pressed; no raw flash write, no `nrfutil` open bootloader.
* `VBUS_SENSE` high = pod is on a cable: firmware pauses delivery (H8, as with the removed charge pads), `MCU_EN` low, the dock gate already blocks forward motion undocked; USB and SWD never enable the motor path (the hardware chain has no input from VBUS).
* SWD stays on pads (4 pads, RESET included) for provisioning; APPROTECT must be enabled in production firmware. A USB-connected host cannot reach the supervisor MCU (9.1 S) at all.
* Safety elements are unchanged by the split: series P-FET pair, gate chain legs or supervisor + two discrete legs, OC comparator, 2oo2 halls, bleeder, readbacks all live on MAIN except the halls on SENSOR (FFC loss reads "not docked": fail safe).
