> TEST ONLY - NOT FOR HUMAN USE (see ../../../../DISCLAIMER.md). Bench only, **water only**: never insulin or any other drug, never on a person.

# Cart pump A v2 main board (30.2 x 16.95 + tongue + antenna wing): routed on 4 layers, DRC 0 / 0; 6-layer fallback also routed

Same chip set and the same hardware interlock as the cup board and the routed B board (`../README.md`, `../../INTERLOCK.md`): HJ-840
nRF52840 SiP, STM32C011 supervisor, TPL5010 + latch + AND / XOR gates (motor supply only with MCU enable AND watchdog latch AND supervisor
permit AND (ADAPTER LOCKED XOR DIR_REVERSE)), TPS2553 load switch, TPS61023 boost, 2 x DRV8838, MCP73832 charger, USB-C, RGB LED, sounder.
Nothing in the interlock chain is removed or relaxed: the lock detector switch only replaces B's adapter-lock hall as the source of `DOCK_N`
(same polarity, same pull-up to "not locked").
Mechanical interface: `../../../../mechanical/out/cart_a_v2/board_A_interface.json` + the coordinator's 4 mm-pinion changes of 2026-11-27
(`cartgeom_a.OVERRIDE`: notch x 32.6-33.0 / y 31.0-36.3, TMAG x 33.2-35.2, far strip from x 33.0), brief `../../../../mechanical/CART-A-V2-BRIEF.md` 6-9.

| | **4 layers** `cart_a.kicad_pcb` (preferred) | **6 layers** `cart_a6.kicad_pcb` (fallback) |
|---|---|---|
| Stack (0.8 mm) | F / In1 / In2 / B: **all four carry signals**, GND pour on all four | F / In1 GND plane / In2 / In3 / In4 / B (as B), GND pour on all six |
| KiCad 10 DRC, master + CLEAN + DEV | **0 errors, 0 unconnected**. Warnings: 29 courtyard overlaps (see "Deviations"), silkscreen (10 edge, 20 overlap, 25 over copper, 7 text height), 1 In1 track end + 1 in-pad via flagged "dangling" that carry a connection (removing either opens it) | **0 errors, 0 unconnected**. Warnings: the same 29 courtyard overlaps and silkscreen only |
| Netlist check (`check_board_netlist_a.py`) | board == `netlist_cart_a.json`, 72 parts, 59 nets | same |
| Copper | 165 vias 0.40 / 0.20, tracks 0.10 / 0.10, power 0.30, motor 0.20 (B's rules); track F 348 / In1 402 / In2 313 / B 334 mm | 155 vias, same rules; F 338 / In2 248 / In3 198 / In4 261 / B 170 mm |
| Filled + capped vias in pads (POFV) | HJ-840 ring >= 1, U30 pad 6, USB D-, J2, driver VMOT / GND, middle pins: **4-layer option, not free** | same pads, free on 6 layers |
| JLC package (CLEAN / DEV) | `jlc/`, `jlc-dev/`: gerbers zip, BOM (38 lines), CPL (65 placements, bottom = 180 - KiCad - delta), NOT-ASSEMBLED (7 bare pads), CPL-CHECK, **CPL-VERIFY 65 / 65 OK** (worst 0.425 mm = FUET-4020 land difference) | `jlc-a6/`, `jlc-a6-dev/`: the same, 65 / 65 OK |
| DEV test pads (`variants_cart_a*/TESTPOINTS.md`) | 5 of 6: no underside spot for VMOT that a stub reaches (probe VMOT at the driver caps) | 6 of 6 |
| Cost, 5 boards incl. PCBA, shipping, VAT (`COST.md`, E) | **366 EUR** (PCB 56.09 E: re-quote, POFV not priced) | 392 EUR (PCB 77.85) |

## Interface: what was met, what was not (pump coordinates, mm)
| Item | Interface | Board | Status |
|---|---|---|---|
| Outline | main rect x 32.6-62.8, y 19.35-36.3; tongue x 59.0-63.96, y 34.5-39.96; wing <= `antenna_wing_max` (x 52-59); r <= 0.5 | as given + rear-far notch x 32.6-33.0 / y 31.0-36.3 (pinion) + the USB-C notch (B geometry); wing = `antenna_wing_max` clipped at y 40.76 (2.0 beyond the HJ-840 A end); corners r 0.5 (0.3 wing, 0.2 at the far-front tongue corner: SW2 frame pad, 0.2 at the pinion notch) | met |
| USB-C (fixed) | centre x 40.0, front face y 36.8 | **x 42.0**, front face y 36.8, mid-mount in its notch (main cut +-4.57 to y 30.58, sub-notch +-3.15 to y 29.80) | **NOT met: +2.0 mm**. At x 40.0 the receptacle's front shield-tab slots (+-5.58, 2.14 behind the mouth: x 34.02-34.82, y 33.71-35.61) and its notch (x >= 35.43) leave 2.03 mm of board between the pinion notch (x 33.0) and the USB notch for the TMAG5273, whose SOT-23-6 land needs 2.5 mm (plus 0.2 copper-to-edge). With the TMAG moved away instead it would sit 6.3 mm from the magnet (about 1.5-3 mT instead of about 40 mT): the angle sensor is a safety sensor, so the USB-C moved. **Housing: move the USB-C stadium opening +2.0 mm in x** (x 37.28-46.72; still on the flat far wall, the flare starts at x 48). |
| TMAG5273 (top) | x 33.2-35.2, y 32.4-34.4 | U10 centre (34.47, 33.38), rot 90: body x 33.67-35.27, pads x 33.22-35.72 (0.22 from the notch edge) | met within 0.27 mm in x (land pattern + copper-to-edge), 0.055 mm in y |
| SW1 (top) | (46.5, 22.05), <= 3.5 x 3.5 x 1.5, d4.4 free | Alps SKSGACE010 3.0 x 2.7 x 1.4 at (46.5, 22.05); no other top part in d4.4 | met |
| LED (top) | (39.0, 22.05), d2.4 free | SZYY1615RGB-B at (39.0, 22.05) | met |
| Sounder (bottom) | (57.0, 26.0), <= 2.5 | FUET-4020 2.5 at (57.0, 26.0) | met |
| Lock switch (tongue underside) | body x 60.76-64.26, y 35.71-39.21; actuator toward +x on y 37.46; operating <= 0.25 mm from free, travel >= 0.8, low force | **Alps SPVS410100** (C160857, JLC stock 7711), lever toward +x, body x 60.64-63.94 / y 35.58-39.08, **lever tip on y 37.46**: free x 65.72, ON x 64.68, total travel x 64.18; the lever lies within the switch's 1.0 mm body height under the board (0.4-0.87 mm below the board face, z 7.47-7.94), inside the face of the d2 lock pin (centre z 7.07: z 6.07-8.07); 0.35 N max | **operating position NOT met**: 1.05 mm head-on (no JLC-stocked side-actuated detector reaches 0.25: Alps SPVS / SPVR / SPVM / SSCQ, Panasonic ESE16 / ESE11 checked). Over-travel after ON 0.5 mm, total travel 1.55 mm. **Pin**: preload the lever about 0.87 mm with the ball free (pin face at x 64.85, 0.17 before ON), locked 0.37 further = x 64.48 (0.20 past ON, 0.30 before total travel): the CAD pin tip (64.63 / 64.26) becomes 0.22 mm shorter; tune on the bench as BOARD-A-PLAN 2 says |
| Motor connector (bottom) | JST-SH 4 near (34.0, 33.5); then: 4-pin 1.25 mm header for the NFP "JST 1.25" lead | **J2 Molex PicoBlade 53261-0471** (C696092, right angle, 3.4 high) at x 48.2-54.4, y 20.4-31.4, opening toward -x at x 48.2; the plug lies under the board in a part-free zone x 41.6-48.2 / y 22.6-29.2 | **position NOT met**: the rear-far corner holds the USB-C tab slots and notch, the gear (x 29-32.6, y 19.6-31.6) blocks a plug behind the rear edge; leads run on the floor from the rear-far corner to the plug (200 mm leads: slack under the board). Family **assumed** PicoBlade-compatible (NFP states only "JST 1.25 pitch") |
| Cell connector (bottom) | near (61.5, 29.0), no soldering | **J3 Kyocera AVX 9175 2-way IDC** (C7434809, JLC stock 94) at (61.0, 28.5), wires along x from the front edge, + / - on the bottom silkscreen | met; 26-28 AWG with 0.7-1.0 mm insulation only (the 702 code is probably the 26 AWG cap: check the cell lead; 28 AWG cap 009175002701106 has the same land) |
| Part-free strips | y 19.35-20.35 all x; y 35.3-36.3 for x 33.0-35.0 and 45.0-59.0, both faces | no part in them, except **the HJ-840 on top over x 54.2-59.0** and the **USB-C right front tab slot** (x 47.18-47.98, y up to 35.61) | **NOT met at two places**: the module must cross y 35.3-36.3 (it is 7.0 long and its antenna end has to reach y 38.76): **interrupt the top clamp over x 53.9-59.0** (the bottom ledge may stay: nothing on the bottom under the module); the USB-C tab slot reaches 0.31 into the strip: **ledge / clamp to spare x 47.0-48.2** (also true at x 40.0: x 45.18-45.98) |
| Heights | top 1.46, bottom 6.84 (2.8 in the boss zone x >= 62.86) | top max 1.45 (U3, U10), bottom max J3 about 4.6 (AVX 3.45 + cap, ESTIMATE), J2 3.4, BZ1 2.5; nothing in the boss zone | met (J3 cap height to confirm) |
| HJ-840 antenna | antenna end >= 3 mm from the pouch (y <= 34.9, z >= 11.1), away from water and motor | U1 x 54.2-60.4, y 31.76-38.76, row A toward +y; antenna (last 1.0 mm of the module, y 37.76-38.76, z <= 10.14): **3.02 mm** to the pouch edge (2.86 in y, 0.96 in z); 20 mm from the water (y 17), 26 mm from the motor (x 27.9); keep-out = module x range from y 37.76 to the wing edge: no copper on In1 / In2 / B.Cu, no pour on F.Cu, F.Cu only the A1 GND stub (to a via at (53.95, 37.60), outside the keep-out) and the A7-A8 bridge; nothing on the bottom under the module | met (just: 3.02) |

## Netlist A (`netlist_cart_a.py` -> `netlist_cart_a.json`, 72 parts)
B netlist recipe (cup snapshot minus the dock hall U4A / C80) with these changes, nothing else:
| Change | Parts | Why |
|---|---|---|
| removed | TMAG strip pads TL1-4, motor wire pads MP1-4, cell wire pads SP1 / SP2 (B's pigtail LK1-3 never existed here) | sensor on the board; no soldering iron (spec 1a) |
| TMAG5273A1QDBVR on the board | U10 (top, C3716049) + C41 100 nF; pull-ups RI1 / RI2 as on B | pins from the EasyEDA symbol: 1 SCL, 2 GND, 3 GND(TEST), 4 VCC, 5 INT# n.c., 6 SDA; I2C 0x35 |
| lock detector switch on `DOCK_N` | SW2 Alps SPVS410100 (C160857, bottom, tongue) from `LOCK_SW` to GND; RLK 10 k `LOCK_SW` -> `DOCK_N`; CLK 100 nF `DOCK_N` -> **3V3**; RDK 100 k pull-up kept | closed = locked = `DOCK_N` 0.3 V; open switch, broken joint or open RLK = high = not locked = forward blocked; a shorted CLK also reads not locked (it goes to 3V3, not GND); debounce: falls in 0.9 ms (RLK \|\| RDK), rises in 10 ms (8 ms to VIH 2.0 V). The cup board has no debounce RC on `DOCK_N` (BOARD-A-PLAN asked "as on the cup board"): this one is new |
| motor connector | J2 Molex PicoBlade 53261-0471 (C696092, bottom), pins 1-4 = `MOT_A1`, `MOT_A2`, `MOT_B1`, `MOT_B2` (A+, A-, B+, B-), mounting tabs MP on GND | NFP-608-26.45-SGM leads end in "JST 1.25 pitch" (NFP datasheet; family not stated): **PicoBlade-compatible ASSUMED**; check the lead order on the motor (NFP: phase sequence A+, A-, B+, B-) |
| cell connector | J3 Kyocera AVX 9175 2-way IDC (C7434809 = 009175002702996, 9175-700 capped type, bottom), 1 = `VCELL` (+), 2 = GND (-) | owner's cell has bare leads; IDC, no soldering, no crimp |
| button | SW1 Alps SKSGACE010 (C127465) top-push tact on the TOP face, 3.0 x 2.7 x 1.4, 1.6 N (B: side tact on the bottom) | pressed by the printed plunger at (46.5, 22.05) |
| HJ-840 GPIO pads | `pin_assign.json` (`pinassign_cart_a.py`), map for the firmware: `PINMAP-A.md` / `cart_a_pins.json` | escape with filled vias in the pads |

## Routing, layer decision
Both boards come from the same placement (`place_table.json`, pump coordinates -> `placement.json` by `place_cart_a.py`: 0 rule
violations) and pin assignment (`pin_assign.json`, `OP_POFV=1 kpy pinassign_cart_a.py`).
* **4 layers with an In1 GND plane** (B's scheme on 4 layers) did not close: 12 placement passes (try1-try12: drivers, supervisor,
  pull-up rows, J2, U36 / U33 / U34 moved; In1 short pieces allowed in the finishing A*), Freerouting stopped at 20-30 open connections and
  the finishing tools (A*, greedy rip-up, PathFinder, island routing) at **7 opens at best** (try11: VBAT x2, BST_FB around the boost,
  USB_DP, I2C_SCL, MCU_EN, BPHASE across the middle).
* **Lever "both inner layers signal"** (`prep_signal_a.py`, `OP_IN1_SIGNAL=1 ./flow_cart_a.sh`): Freerouting routes on all four layers
  and GND like any net; the GND pours on all layers come afterwards. try12 placement: **5 opens after Freerouting**, closed by island
  routing and a short list of rips / vias (`hand_fixes_a.json`) -> 0 / 0. Price: In1 is no longer a solid reference plane (402 mm of
  signal track on it, 19 mm of it under the HJ-840 body: DOCK_N, SUP_BOOT0, SUP_NRST, SWDCLK, LED_G / LED_B, OC_OK, BPHASE, BTN_N); every
  layer has a GND pour and 165 vias stitch them. The antenna keep-out (no copper on In1 / In2 / B.Cu, no pour on F.Cu) is unchanged.
  The same lever on try10 / try11 left 7 / 14 opens after Freerouting.
* **6 layers** (run in parallel as asked): In1 GND plane as on B, Freerouting 15 unrouted, finishing + island routing -> 1 open, closed by
  hand (`hand_fixes_a6.json`).
* Tools added for the last opens: `island_route_a.py` (A* from any copper of one island to any copper of the other; `OP_FIRST`),
  `island_fix_a.py` (rip only the pieces in the way, not whole nets), `gnd_stub_a.py` (pad -> own via), `gnd_islands_a.py`,
  `turn_part_a.py`, `prune_dangling_a.py` (each removal DRC-checked), `prep_signal_a.py`.

## Deviations from B's rules
* **In1 carries signals on the 4-layer board** (B: solid GND plane on In1). Not on the 6-layer board.
* **29 courtyard overlaps** (B: none), the same on both boards (same placement): worst C41 0.85 mm into the USB-C courtyard beside its
  rear shield tab (pad gap 0.56, the shell wall is 1 mm away), JU1 / U3 0.59, U5 / R74 0.40; smallest pad-to-pad gap between two parts
  **0.18 mm** (C71-L1, RU2-C82, R57-R58, C19-R56). No body collides; JLC's DFM may ask for a confirmation.
* 7 silkscreen texts below the 0.8 mm height check (B: 2).
* Everything else as B: 0.10 / 0.10, vias 0.40 / 0.20, power 0.30, POFV pads, CPL rule (bottom origin shift now fitted for both sides,
  with the mounting tabs: `lcsc_origin_a.py`).

## Rebuild (KiCad 10, Freerouting 2.2.4 jar not committed: set FREEROUTING_JAR)
```sh
cd electronics/v010/cart/a
python3 netlist_cart_a.py && python3 pinmap_cart_a.py      # netlist (applies the committed pin_assign.json), PINMAP-A.md
python3 gen_footprints_a.py                                                                # CARTA.pretty (SW2, SW1, J3)
../../board/kpy place_cart_a.py                                                            # rule check of place_table.json
OP_LAYERS=4 OP_POFV=1 OP_NAME=cart_a ../../board/kpy build_cart_a.py                       # placed board + fan-out (6 L: OP_LAYERS=6 OP_NAME=cart_a6)
OP_IN1_SIGNAL=1 OP_BOARD=cart_a.kicad_pcb ./flow_cart_a.sh 60                              # Freerouting (6 L: without OP_IN1_SIGNAL)
OP_LAYERS=4 OP_IN1=1 ./finish_cart_a.sh cart_a.kicad_pcb cart_a_placed.kicad_pcb cart_a_f1.kicad_pcb 10
#   then island_route_a.py / island_fix_a.py / hand fixes as in hand_fixes_a.json (hand_fixes_a6.json), route_v3 finish, prune_dangling_a.py
./post_a.sh <routed>.kicad_pcb cart_a                                                      # DRC, netlist check, variants, jlc/ + jlc-dev/, CPL verify
python3 live_stock_a.py && python3 cost_cart_a.py 4 && python3 cost_cart_a.py 6           # COST.md tables
```
Freerouting is not deterministic: the committed `cart_a.kicad_pcb` / `cart_a6.kicad_pcb` are the routed sources; `post_a.sh` rebuilds
everything after them.

## Open before ordering
* **STM32C011F4U6TR (supervisor) is out of stock at JLC** (0 on 2026-11-27): wait or consign; no change of part without a netlist review.
* **Housing**: USB-C opening +2.0 mm in x (x 37.28-46.72); top clamp interrupted over x 53.9-59.0; ledge / clamp to spare x 47.0-48.2.
* **Lock switch**: operating position 1.05 mm instead of <= 0.25 (no stocked part reaches it): set the pin preload as in the table, bench-tune.
* **Motor connector**: J2 position (x 48.2-54.4 instead of near (34, 33.5)); PicoBlade family assumed for the NFP "JST 1.25" lead: check
  the plug and the phase order before ordering.
* **J3**: check the cell lead gauge (26 AWG cap) and the cap height (4.6 mm, E).
* **4-layer PCB price**: re-quote at JLC with the gerbers, incl. "via in pad, filled and capped" (needed: HJ-840 ring >= 1 and the other
  POFV pads) - the 4-layer estimate does not include it.
* **4-layer board**: In1 is not a solid plane under the HJ-840; compare RSSI with the 6-layer board / B on the bench if radio range matters.
* Courtyard overlaps / 0.18 mm pad gaps: confirm in JLC's DFM check.
* Firmware: board file `cart_a_v1.rs` (feature `board-cart-a-v1`) from `cart_a_pins.json` not generated (firmware out of scope here).
