# Project status & handover

> This file is the **entry point for every new session** (another machine, another Claude subscription, another person).
> It is updated on every push. Last updated: **2026-11-24 (firmware drive preset 0x27 for the 20.5 x 5.9 cup bore)**.

## Cart A adapter lock: round-5 puck coupons from hand measurements (2026-11-25, mechanics)
Round 4 coupons (`LOCK3.gcode`) did not fit: the photo-derived adapter cup (d10.3, lugs 0.5) was too small. Owner measured the real Insight adapter with a ruler: cup d11-11.5, d13 over the lugs, cup 5 mm above the face (incl. ~1 mm seal), lugs at the cup tip 1-1.5 thick with chord widths 4.5 and 6.5, adapter 49 x 19, cup centre 11-11.5 from the near end, far half raised 4 mm with a ramp from 21 to 25 mm. So the pump side is a round lock boss of about d19 with the rest of the end face recessed 4 mm. `mechanical/print/A_lock/make_pucks.py` builds that boss alone (6 variants: bore 11.7/12.0 x lip 2.4/2.9/3.4, keyed windows, 360 deg undercut, lip underside bevelled 45 deg because the lug hook flank is bevelled). The lugs have a straight outer edge in top view, so the windows are flat-ended slots and the groove is d15.2 (the lug corners sweep r 7.27). Single best puck (bore 12.0, lip 2.9) as `A_lock/PUCK6.gcode` (15 min) for fast iteration). PUCK6 fitted (lug lock OK, a bit catchy). `A_lock/PUCK7.gcode` adds a d15.6 x 0.8 seal recess so the adapter sits flush, bore 12.2, lip 3.5, windows +0.3, groove 2.1 high). Owner printed the 6-variant plate: puck 4 (bore 12.0, lip 2.4, no seal recess) fitted best. Its seal held the adapter ~0.8 mm high, so with the 0.8 mm seal recess the lip grows by the same amount: `A_lock/PUCK8.gcode` = bore 12.4 (owner: a little easier in and out), lip 3.2, seal recess d15.6 x 0.8), sliced as `A_lock/PUCK5.gcode` (face up, no supports, Z -0.15). PUCK8 fitted; owner: seal recess a touch deeper, then the lock is done. Final lock in `make_pucks.py` (FINAL_BORE 12.4, FINAL_LIP 3.5, seal recess d15.6 x 1.1). Pump end face coupon: `A_lock/make_face.py` -> `A_lock/FACE1.gcode` (34 min, face up). Owner 2026-11-26 marked the lowered areas on a pump-end photo: the end face is flat except a round area at the far end around the window and a thin strip along the right (entry) edge from ~10 mm below the bore, joined by a small square. These take the adapter's raised parts: the hook-shaped boss at the tube end (traced from photo p26, incl. the hook lobe) and the thin wall along its entry-side edge (1.6 wide, 45 deg ramp at u 20.6..24.6). Lowered 4.3 deep, swept over the clockwise 90 deg turn (adapter goes on from the right). Final lock in the bore, windows across the width. Round 2 (owner): the far-end left (front) side stays at full height with a gentle curve, outline measured from two pump-end photos (corner radii 3.0 / 7.5 / 5.5 / 2.5, rounder on the silver side), and a rectangular latch groove (X 15..20.5, 3 tall, 1.2 deep, closed on top) in the side wall of the entry-edge strip where the adapter's wall snaps in. Round 3 (owner): no turning sweep (the strip ramp is one flat 45 deg face, nothing grows towards the bore), outline refitted to the photo with its tilt removed, hollow rim rounds over and curves down (r 2), its left boundary retraced from the photo, a pocket for the lock at the top of the curved left side (X 24..26.2, Y -7.7..-5) and the notch where it meets the far edge. FACE1 printed and tested by the owner: the adapter stuck ~15 deg before the end of the turn (boss inner wall against the face beside the hollow). `A_lock/FACE2.gcode` (36 min): the boss footprint is now swept over the last 30 deg of the clockwise turn, the hollow rim rounds outwards (r 1.5) so the floor keeps the boss's full footprint, left boundary retraced on the photo. FACE2 still caught at C (front); owner: move the hollow's near edge 1-2 mm towards the bore. `A_lock/FACE3.gcode` (HOLLOW_UP 1.5, lock pocket kept as a 5.8 deep pocket inside the hollow).

## Firmware drive preset 0x27 for the 20.5 x 5.9 cup bore (2026-11-24, firmware-rs + ios)
- Follows mechanics 7879e22 (bore 20.5 x 5.5 -> 5.9). **New preset id, not an in-place change:** `0x27` `nfp-608-26-45-cup59-miter-1-1` (`drive_cal::NFP_608_2645_CUP59_MITER_1_1`): stadium area 86.14 + (355/113)(3481/400) = 5 129 283 / 45 200 mm^2 = 113.4797 mm^2 (`bore_area_x100` 11348), exact **897 624 525 / 119 554 uU = 0.0075081 U/step** (was 0x26: 840 503 125 / 119 554 = 0.0070303 U/step, +6.8 %); 133 steps per U, take-up 0.33 mm = 3.74 U = 499 steps (same lead, same steps). 0x26 stays unchanged for pods with the old 5.5 tank; a record with one id and the other's numbers is refused. No suction draw on either (`allows_draw` false for 0x26 and 0x27).
- `scripts/build.sh` default and the drive guard: `drive-nfp-608-26-45-cup59-miter-1-1` (0x26 via `DRIVE=drive-nfp-608-26-45-cup-miter-1-1`). Supervisor `Config::CUP59_MITER_1_1`: hour cap 1920 steps (14.42 U), minute cap 226 steps (1.7 U), recomputed from the core (the 0x26 caps 2051 / 241 would pass 6.8 % more volume on a 5.9 pod). Reservoir capacity stays the nominal 100 / 200 U (CAD tank 132.5 / 239.3 U) until the bigger tank is confirmed on the bench.
- Golden wire vectors (`docs/vectors/wire-v1-scenarios.json`) regenerated on 0x27 (DRIVE_CAL 7508 uU/step, prime 67 steps = 0.5 U rounded like the app). iOS: 0x27 accepted (first in `firmwarePresets`), 0x26 still accepted, simulator pod = 0x27.
- Tests: `cargo test --workspace` 960 passed, 0 failed, 2 ignored (+16 new: `preset_cup59.rs` 14, supervisor agreement 1, cup59 checks in the wire vectors); thumbv7em builds (bench-e73, nrf52840-dk, cup-v4) with the new drive OK; `swift test` (OpenPatchCore) 258 passed (+1). The OpenPatchKit Xcode target was not test-run (LoopKit package not resolved on this Mac).
- **Open:** `mechanical/cup_check.py` still compares the CAD bore with preset 0x26 (regex on `Nfp608_26_45CupMiter1_1`), so its TARGET line stays until it points at `Nfp608_26_45Cup59Miter1_1` (mechanics agent). Bench-verify U/step on the 5.9 tank (balance) before any dosing run.

## Cup pod: challenge-review mechanics pass, bigger tank at the same size (2026-11-24, mechanics)
- Research (2026-11-24): Asian Luer infusion sets (bench/water only) and cheap CGMs vs. iOS/Trio BLE access: `docs/research-asia-sets-cgm.md`.
- Owner: "couldn't the tank be bigger?" Outer size kept (OP-100 **47.96 x 36.6 x 8.5**, OP-200 66.78 x 36.6 x 8.5); the stroke now fills the length (`cup.outer_length`). **OP-100 132.5 U (was 100), OP-200 239.3 U (was 200)**, bore 20.5 x 5.9, U/step 0.007508. Both sizes PASS `check.py --variant v010 --drive cup --assembly`, H 8.5. Details: `mechanical/V010-CUP.md` (challenge-review pass), `mechanical/challenge-review/CHALLENGE.md`.
- Applied: #1 fill channel now opens into the bore (probed on the exported STL; the old STL is reported blocked at x 32.70); #2 3.5 mm in-pod slide reserve removed (pocket 8.4, L-springs 0.05 mm, dock + hall + screw E +3.5); #3 micro-margins (collar kept 1.0, the west board tab sets the dry rim); #4 thrust model with collar friction, PTFE shim + greased thread: **1.68x** (9.1 / 5.4 N; dry 1.05x, so grease + shim are mandatory); #5 pocket-mouth seal plate + hidden ePTFE vent; #6 single seal bead (S2); review #9 floor/roof 0.7 over the tank, bore 5.9 (moulds regenerated); #8 motor offset removed, empty keep-outs deleted, honest packing with named voids; flush button key (pad 35.37); USB-C outer counterbore (overmold 0.5 from the mouth, frame in the board gap); 23G centring hub (needle-to-septum stack 0.56 vs 0.8 capture). BUY-LIST Z13-Z15 added (PTFE shim, ePTFE vent, grease), G8 dropped; PARTS-LOCK rows 4, 7, 12, 18 corrected, 23-25 added.
- **Board revision (electronics agent, with the H8 SW1 move):** west tab x 7.33-9.53 (was 7.8-10.0), screw W (8.43, 21.5); side_b leg west end x 38.9 (was 35.4); hall finger x 41.36-44.36; dock hall U4A (42.86, 11.75); screw E (40.90, 20.0); main body, north edge, USB-C notch, east tab, NE corner unchanged. Parts to move: finger parts +3.5, R74 off the cut leg, BZ1 / U6 / RBZ out of the new screw-E ring. `mech.json -> elec_interface.board_outline_changes_2026_11_24`.
- **Open / required before dosing:** ~~firmware preset 0x26 still has the 20.5 x 5.5 area~~ done: new preset 0x27 (see above; `cup_check` must be pointed at it). Measure the Insight Flex head (A, B, C, J/K, latch): every dock number is still a photo estimate. Source the 0.05 mm 301 FH foil, PTFE film, ePTFE vent disc. Check a real USB-C plug and the mouth plate on the 1:1 print. Skipped: tank wall 0.5 (#10), front wall 2.0 (#11), guard spring -> silicone sleeve, Rev B dock in lane 2 (#14), ko_side_b shrink; 2:1 print files in `mechanical/print/` are from the old geometry.

## Every part in JLC stock: 2 x DRV8838 instead of the DRV8835 (2026-11-24, owner decision, electronics)
- Owner: everything we use must be in JLC stock. Live check of all 34 BOM lines: only DRV8835DSSR (C129328) was at 0. Replaced by **2 x DRV8838DSGR (C86667, stock 1457)**: same PHASE/ENABLE truth table (TI SLVSBA4F rev F), so nets, firmware pin map, phase sequence and supervisor counting are unchanged (firmware: comments only, tests green). U7A coil A, U7B coil B, nSLEEP and VCC on 3V3, C20 / C62 added (`electronics/v010/INTERLOCK.md` I.6b, FMEA FM6-U7-3).
- Board re-routed around the drivers: **0 DRC errors, 0 unconnected** on master and both variants; JLC packages `jlc/` and `jlc-dev/` regenerated (56 placements, 34 lines, 22 extended); `COST.md` from a new live snapshot: parts 17.2 USD per board, order of 5 about 300 EUR delivered. SPICE re-run: case 4 still PASS (0.184 A per coil).
- Leftovers done: print-kit board model regenerated from the routed board (`mechanical/print/OP-100/cup_board_model.stl`, north edge 35.5); button coordinates in `ASSEMBLY-CUP.md` (window x 32.4-34.5, nub x 32.6-33.4 at SW1 x 33.0); `check.py` without arguments no longer crashes (KeyError 'purge': the stale `out/` params of the superseded `integrated` variant predate the purge groove). It now reports that old design honestly: FAIL wall `plunger_groove_to_socket_wall` 0.05 mm in its stale CAD output (regenerating needs SolidCraft on the Mac; the cup pod check `--variant v010 --drive cup` passes).
- Order blockers: none in the design. Low stock: STM32C011 35, HJ-840 85 (order spares). Still to check on the quote page: fees for filled vias in pads and 0.15 mm drills; bottom-side rotations in the 3D preview (U4A, BZ1, U7A, U7B).

## Cup board fully routed, DRC 0 (2026-11-22, electronics)
- `electronics/v010/cup/cup.kicad_pcb` is routed on the 2 mm deeper outline (`cupgeom.py` Y1 = 35.5, placement shifted +2.0 for every part north of by 8.55): **0 DRC errors, 0 unconnected** on the master and on both variants (`variants/cup_clean.kicad_pcb`, `variants/cup_dev.kicad_pcb`). Flow and the hand fixes: `cup/ROUTING-GUIDE.md` (negotiation 100 iterations, greedy rip-up with rollback in `rr_route.py --greedy`, then 0.05 mm hand fixes, a filled via in U36 pad 2, solid zone connection for 7 starved GND pads).
- Pad labels A+ / A- / B+ / B- / + / - no longer overlap (`silk_labels.py`); the DEV test pads keep 0.21 mm from foreign drills (`variants.py`).
- JLC packages regenerated: `jlc/` (CLEAN) and `jlc-dev/` (DEV); `ORDER.md`, `COST.md` updated. (The DRV8835 stock blocker was resolved on 2026-11-24, see above.) The board uses filled vias in pads (POFV, 71) and 0.15 mm via drills: check the JLC quote page for fees.
- Open: print-kit board model (`print_model.py`), stale button x values in `ASSEMBLY-CUP.md`, two mechanics PNGs.

## Cup pod 2 mm wider for board routing (2026-11-22, owner decision, mechanics)
- `cup.lane2_extra` = 2.0: lane 2 = cell + 0.4 + 2.0 = 13.0 mm (y 22.8-35.6), pod width 34.6 -> **36.6** (OP-100 47.96 x 36.6 x 8.5, OP-200 66.78 x 36.6 x 8.5). Tank (bore 20.5 x 5.5), strokes and all x positions unchanged; cell stays on the south side of lane 2. Moved +2.0 in y: board north edge (pcb_y 22.9-35.5), USB-C receptacle y 28.35-35.7 / opening in the wall at y 35.7, button nub face y 35.4, north ledge (41.5, 34.1), wall shelf / lid wall rib from y 34.9, NE lid corner post. Both sizes PASS `check.py --variant v010 --drive cup`. Open: the board outline in `electronics/` (owner) and the print-kit board model still use the old 33.5 north edge.

## Cup v4 firmware: bootloader ACL, supervisor flashing, pump app port (2026-11-24, firmware-rs)
- **Done, host tested** (`cargo test --workspace`: 937 passed, 2 ignored; +63 tests): (1) the bootloader write/erase-protects its own code with the nRF52840 ACL before the jump (`openpatch_boot_policy::acl`, `docs/bootloader-v2.md`; the state page and the UICR rollback counter cannot be ACL-protected, documented); (2) new crate `openpatch-supflash`: nRF-side STM32C011 flashing through the ROM bootloader (signed + not downgraded image via boot-policy, flash-guard preconditions, entry/autobaud retries, Get ID 0x443, RDP probe + one unprotect, erase, 256-byte writes, read-back + digest check, exit to normal boot on every path), tested against a simulated bootloader; embedded driver left as an integration point; (3) the pump application builds for `board-cup-v4` (`openpatch_core::cup_ctl` + `hal/cup.rs`, new `Hal::motor_capacity` deferral, nRF WDT, RGB UI, supervisor status link). `scripts/build.sh` builds the cup bootloader and app.
- **Needs hardware** (all `TODO(verify-on-hardware)`, list in `firmware-rs/docs/stubs.md` items 9-11): ACL PERM read-back / BusFault, ST AN2606/AN3155 facts (not readable here) and all flasher timeouts, every `CupCfg` timing, WDT vs. the DFU soft reset, RC LF clock with BLE. **Open:** supervisor challenge/response (a supervisor that needs it never permits), cup POST proofs (`Unsupported`), stuck dock hall check, supervisor image storage / minimum version. The bring-up binary now arms after `MCU_EN` (the supervisor refuses an arm with `MCU_EN` low).

## Cup pod housing vs main board (2026-11-20, electronics worktree, mechanics)
- Board review fixes applied in `op_cup.py` / `op_cup_asm.py` (both sizes PASS `check.py --variant v010 --drive cup --assembly`, H 8.5): USB-C opening moved east (x 18.8-28.2, centred x 23.5 / z 5.7 on the board mid-plane); cell shifted 1.5 mm east (x 9.37-40.87, lead end WEST, VERIFY on sample) for a wire channel x 7.5-9.4; board 3-point support at z 5.3 (2 ledges + west wall shelf) with 3 lid hold-down ribs; **board screwed down with 2 x M1.2 x 4 brass** (W 8.9/21.5 on a board tab, E 37.40/20.0 in the side_b leg); lane-2 motor saddle lip cut to z 5.2 (230 degree wrap kept); side button moved to the +Y lid wall (flex window, VERIFY stiffness). Spec §1a records the soldered motor + cell exception. All coordinates: `mechanical/V010-CUP.md` (board interface table) and `mech.json -> elec_interface`. `cup_packing.py` no longer counts the rim gaskets as contents (it reported 0 free area before).

## Take-up is a travel, converted per preset (2026-11-19, electronics worktree, firmware-rs)
- Fixed bug: `plunger_um_to_mu` used a global 74.63 mm^2 area, so the 0.33 mm take-up after a reversal was 350 steps on the cup pod instead of 499. Each `Preset` now carries `bore_area_x100` (cup 106.26 mm^2); `LOST_MOTION_TOTAL_UM` / `TAKEUP_UM_AFTER_REVERSAL` is a travel, `Preset::travel_um_to_steps` converts it exactly (rounded up), `PumpConfig::takeup_um` replaces `takeup_mu`. Applied after every assisted fill / draw. Golden vector `docs/vectors/wire-v1-scenarios.json` regenerated (one more cup prime retry); Swift golden count 40 -> 41. Open: the real cup backlash is still unmeasured.

## iOS / Trio kit drives the cup pod (2026-11-19, ios worktree)
- `OpenPatchKit` now runs the v0.1.0 cup pod end to end from Trio on the bench (water only): wire parity with `firmware-rs` by golden frames of a real cup pod (`docs/vectors/wire-v1-scenarios.json`) and a source-parsing parity suite, encrypted session wired with keychain-stored pairing secret, `LAST_SEQ` resync, DRIVE_CAL `0x26` accepted / unknown refused / preset shown, assisted pressure fill only (no draw), prime take-up retry, uncertain-delivery recovery from status + history, new alerts; 257 core + 80 kit tests green; loop + balance compare: `ios/BENCH-LOOP.md`, `ios/tools/bench_compare.py`. Not run against a real pod; open: firmware take-up volume uses the 74.6 mm^2 bore area (cup bore 106 mm^2), Trio has no pump-history export.

## v0.1.0 cup pod, layout A (2026-11-19, mechanical worktree)
- `generate.py --variant v010 --drive cup` / `check.py --variant v010 --drive cup`: transverse motor at the rear spanning both lanes, miter pair z16:z16 (2 gears), rod ends at gear B, cup plunger, tank (un-frozen for this variant: bore 20.5 x 5.5, fill septum underside + outlet in the front wall), dock at the right end of lane 1 (pocket 11.9 x 9.8, 3.5 mm slide, 301 FH U-clip, spring needle guard), reserved volumes for battery/board/USB-C. OP-100 47.96 x 34.6 x 8.5, OP-200 66.78 x 34.6 x 8.5 (bore 20.5 x 5.5; 45 / 52 mm and 32 mm width targets missed; cell = Ampul 301030, see mechanical/battery-selection.md). Details: `mechanical/V010-CUP.md`. Decision needed: re-freeze the CNC tank (`out/v010-cup/reservoir-cnc`), clip material (301 FH foil), Insight Flex measurements (all dock values TODO-MEASURE).

## MILESTONE 1 (2026-11-19, cloud session) — what changed since the handoff below

Done and verified (merged to `main`):
- **Parts & cost:** `docs/PARTS-LOCK.md` rows verified against live listings (nothing promoted to LOCKED), `docs/SHOPPING.md` (AliExpress-first ≤ 200 € build + detailed iteration list), `docs/05-cost-model.md`. Verdict: first bench pump (pod + controller) ≈ 230–300 € with all cuts, marginal pump 65–95 €; the integrated v0.1.0 pod removes the second board.
- **Spec:** §1d cost target, §7a diagnostics & hardware independence (incl. HW step budget HW-A, no service override for latched codes), §8a modular dock insert on a frozen pod interface, §6 DASH mode = clean-room only.
- **firmware-rs:** 371 host tests green (+28). TMAG5273 verified against TI SLYS045C — **real angle-decode bug fixed**, CRC/torn-read/ID checks. Draw mode on `board-bench-e73` with the new gate `VMOT = MCU_EN AND LATCH AND (DOCKED OR DIR_REVERSE)`; forward-while-undocked refused. Drive-feature guard. Occlusion setter (lower only), `Hal::motor_fault`, peak-current CSV column. Open: STSPIN220 MODE/DIR latch at STBY rise (electronics to confirm).
- **Protocol v1.1 §5.2 session key agreement** (`docs/04-protocol.md`): X25519 pairing secret + per-connection ephemeral X25519/HKDF, key confirmation; Rust (feature `key-agreement`, 364 tests) + Swift (167 tests, runs on Linux with Swift 6.0.3), shared vectors `docs/vectors/`. Kit/UI wiring still open.
- **Diagnostics design** `docs/06-diagnostics.md`: 150 codes, 32-bit structure, FRU + action, propagation, protocol additions, work packages WP-0…WP-8 (implementation in progress).
- **v0.1.0 integrated pod architecture** `docs/v010/ARCHITECTURE.md` (+ calc scripts): E73 module, 4-layer 0.8 mm board in a 22 mm tail, charge pads instead of Qi, 40 mAh cell, buzzer fits; OP-100 ≈ 66.9 × 32 × 8.5 mm. Spec changes proposed there are **not yet applied**.
- **Mechanical simulation suite** `mechanical/sim/` (`python3 mechanical/sim/run_all.py` → REPORT.md): 14 PASS / 9 WARN / 20 FAIL on the current CAD — thrust 3.2 N at 105 mA (< 5 N), carriage tongue too thin, lid touches reservoir, gear centre without backlash, dead volume 2.2 U, duckbill bypass, occlusion undelivered 2.5–5.2 U. Fixes handed to the mechanical owner; **gear ratio decision: drop 15:12, use 16:20 step-down if orderable, else 18:18**.
- **Licensing:** dual licence (`LICENSE.md`): CC BY-NC-SA 4.0 hardware/docs, PolyForm Noncommercial software, ios/ GPL-3.0, dock insert CERN-OHL-P-2.0; draft commercial Fair-Price licence (`COMMERCIAL-LICENSE.md`: price ≤ cost + 30 %, 5 % trial levy, sponsor recoupment + 20 % capped return), `CLA.md`, `CONTRIBUTING.md`. Needs legal review.
- **Tooling on Linux:** SolidCraft 0.44.1 (AppImage, `solidcraft-cli`), KiCad 10.0.8, Swift 6.0.3 all work in the cloud container (see `docs/SETUP.md`).

In progress (next milestones, each merged separately when green): mechanics (parallel-motor layout, sim fixes, modular dock insert, `check.py`), bench controller board (interlock incl. readbacks, over-current cut, DRC 0), diagnostics implementation (WP-0/1/4/5), virtual-pod simulator (`firmware-rs/openpatch-sim`), vendor-accurate component models (`mechanical/components/`), website redesign (engineering-notebook style, licence page, fault-code explorer), regulatory technical file (`regulatory/`), security programme (`security/`: threat model, formal handshake proof, fuzzing, supply chain).

## HANDOFF (2026-11-19) — previous handoff (partly superseded by milestone 1)

**Setup:** see `docs/SETUP.md` (all tools, macOS/Linux/Windows).

**Current architecture (decided):** Rev A = bench split (pod with mechanics + small pod sensor board, FFC to a ~40 × 50 mm bench controller board with nRF52840 module). Drive = **NFP-608-26.45 geared stepper + sleeve coupler + M1.6 leadscrew**, refill = **automatic draw mode** (motor reverses, duckbill check valve in the outlet). Reservoir = **frozen CNC polypropylene part** (spec §3a), septum/valve/needle in a separate end cap. Cannula = Accu-Chek Insight Flex, horizontal slide-on dock (dimensions not public → dock fit-test coupon). Firmware = **Rust** (`firmware-rs/`, Embassy). Two-pod system (48 h per pod). Tests with **water only** (never insulin or any drug; decision 2026-11-19), never a person.

**State at handoff (2026-11-19, agents stopped mid-task; everything is on `main`):**

> ⚠️ **Gear-ratio mismatch (being resolved in milestone 2: 16:20 or 18:18, firmware preset follows):** the last (unverified) CAD snapshot `mechanical/out/bench/OP-100_layout_annotated.png` uses a **z18 : z18** gear pair (1:1, centre 5.40, envelope 44.9 × 32.0 × 8.5 mm), while spec §4 and the firmware default feature `drive-nfp-608-26-45-g15-12` assume **15 : 12**. Pick one, update spec §4, `mechanical/parts.md` and the firmware build default (`drive-nfp-608-26-45-g1-1` for 18:18) together — a mismatch means a 25 % dosing error.


| Area | State | Verified | What the next agent must do |
|---|---|---|---|
| `firmware-rs/` | **Done** | 343 host tests incl. 32 differential tests vs C pass; builds for bench (E73), DK, syringe rig | Open items in `firmware-rs/docs/stubs.md`: session key agreement, TMAG5273 register map vs datasheet, DFU transport. Default drive feature: `drive-nfp-608-26-45-g15-12`. |
| `ios/`, `site/`, docs | Done | Swift 143 + 49 tests; site live on Pages | Update site numbers once mechanics/electronics are final. |
| `mechanical/` | **Interrupted** while switching from the coaxial layout (committed earlier in `1d2ebf5`, OP-100 69.2 × 27) back to **motor beside the reservoir + GHW 15:12 gear pair** (spec §4). The working-tree changes of that switch are committed as WIP, the last pipeline run did not finish. | Not verified (`check.py --variant bench` must be re-run) | Finish the parallel-motor layout (target OP-100 ≈ 42 × 27 × 8.5), run `python3 generate.py --variant bench && python3 check.py --variant bench`, regenerate `out/bench/fab/`, annotated top view, and report the new pod-board fields in `out/bench/OP-*.layout.json`. Frozen CNC reservoir (`reservoir_frozen`, `out/bench/fab/reservoir-cnc/`) must not change. |
| `electronics/bench/` | **Interrupted.** Controller board routed earlier (render in `fab/jlcpcb/controller/`), but **pending changes not applied/verified**: STSPIN220 current limit for the NFP motor, PicoBlade 4-pin motor header, SMA parts removed, silkscreen overlap cleanup, and the **new interlock MOT_ALLOW = MCU_EN AND TPL5010_LATCH AND (DOCKED OR DIR_REVERSE)**. Pod sensor board not built yet (waits for the final mechanical layout). | No DRC report for the current state | Apply the changes above, DRC 0 on the controller, build the pod sensor board from the final layout.json (TMAG5273 mandatory, dock hall, optional DRV5032 pair, FFC), export JLCPCB packages, `pin-assignment.md`, `ORDER.md`, `COST.md`; then an **independent layout review** (antenna keep-out on all layers, motor current loop, shunt Kelvin, decoupling, unbroken GND) and fix findings. Keep `firmware-rs` pin map in sync. |

**Next steps (in order):**
0. **Parts lock** (`docs/PARTS-LOCK.md`): place the sample order for all LOCK-AFTER-SAMPLE / CANDIDATE parts, measure, update the table + spec, then freeze CAD/PCB around them. Resolve the gear ratio (15:12 recommended) first.
1. Finish mechanics and electronics as described in the table above; get everything green: `check.py --variant bench`, KiCad DRC 0 for both bench boards, `cargo test --workspace`, `npm run build`.
2. Independent DFM review of the CNC reservoir drawings; independent PCB layout review; fix findings.
3. Write `SHOPPING.md`: one complete bench iteration (JLCPCB boards, JLC3DP prints, PCBWay CNC reservoir ×2 per size, NFP motors, M1.6 rod/nuts, magnets, duckbill valves, 30G needles, silicone, FFC, programmer) with links, qty, prices.
4. User: print the dock fit-test coupon first, test against a real Insight Flex head, enter the winning variant.
5. First order, bench tests per `docs/02-safety.md` §3; log real prices in `docs/05-cost-model.md`.
6. **CAD detailing pass** (only after the layout/dimensions are final): vendor-accurate motor model from the NFP drawing (pins, bosses, D-shaft), KiCad STEP of both boards with components, involute gear teeth from module/tooth count, cosmetic threads, fillets/chamfers/draft, properly shaped snap arms, lid lettering + fill-window scale, then photoreal SolidCraft path-traced renders (iso, exploded, section) for the website and docs. Current models are deliberately simplified envelopes for fit/interference checks.
7. Rev B: integrated pod (bare nRF54L15, HDI), motor with FPC tail (group buy), battery + Qi, no cables inside the pod (spec §1c).

## Goal

An open-source patch insulin pump ("OpenPatch"). It is detachable, plugs onto an Accu-Chek Insight Flex cannula and is held by Velcro. Further key points:
- Filling by syringe, inductive charging.
- Sizes: 70, 100 and 200 U.
- Build height ≤ 8.5 mm.
- Controlled from Trio, either through a dedicated kit or through DASH emulation.
- Cheap to build: **at least one working iteration ordered every month** (JLCPCB/JLC3DP primary, PCBWay secondary).
- Assembly **without a soldering iron**.
- Goal: smaller than anything on the market.

All dimensions and components are in [spec/design-parameters.md](../spec/design-parameters.md). That is the **single source of truth**.

## Status per subproject

| Area | Status | Verified | Open |
|---|---|---|---|
| Mechanics ([mechanical/](../mechanical/)) | **Bench pod (Rev A) done**: `generate.py --variant bench`, horizontal slide-on Insight Flex dock (needle at z 3.0, 2 PA12 snap arms), pod sensor board 15.5 × 25.9 mm (same for all sizes), FFC exit, fab package `out/bench/fab/` (~$31–41/iteration incl. dock fit-test coupon `out/fab/dock-coupon/`, 6 needle-free variants) | `check.py --variant bench`: OP-70/100/200 PASS, 35 bodies interference-checked | Insight Flex dimensions are not public (researched twice): fit-test coupon + mm-paper photos. Squeeze release not implemented (pull-off). Dock hall switches ~4 mm early with DRV5032FA → higher threshold part. **Integrated variant is parked until Rev B** (new dock collides with battery/PCB/RF keep-out; `check.py` default variant fails). |
| Electronics ([electronics/](../electronics/)) | KiCad 10 board generated from netlist + mechanical layout; ISP1807 footprint verified (vendor lib + DS1807 R19); WCSP parts swapped (BQ51013B VQFN, MCP73832 + LDO); dock Hall in interlock; TPL5010 2 s | DRC: **63 errors, routing ~81 %** | **NOT ORDERABLE**: 17.1 × 29 mm board does not route (see `electronics/fab/STATUS.md`); TMAG5273 only SOT-23-6; no real spring contact fits; 4L min 0.8 mm at JLC; ISP1807 consigned; ~$420/iteration. Firmware must follow the charger swap (no I2C charger) and the final dock pin. |
| Firmware ([firmware/](../firmware/)) | Portable C core + Zephyr/NCS v3.4.2 app for `openpatch_reva` and `nrf52840dk/nrf52840` (MCUboot, signed BLE DFU, NVS). Per-drive calibration (0.0261 U/step for 5:1, Kconfig, CRC-checked, reported in `GetStatus`). Two-pod: dock detection, 44/52 h wear timer, `SetPairing`/`Activate`/`Release`. | 173/173 host tests; `scripts/build.sh all` builds both targets | Open: app-layer AES-CCM, DASH mode, BQ25120A config, TMAG5273/STSPIN220 registers vs datasheet, Rev A `dock-gpios` pin placeholder, delivered-since-activation resets on reboot. Untested on hardware. |
| iOS/Trio ([ios/](../ios/)) | `OpenPatchKit` (LoopKit PumpManager) managing a pod pair A/B as one pump, swap flow (`PairSwapCoordinator`), wear/spare alerts; calibration read from the pod (refuses to dose if unknown) | 143 core tests + 49 kit tests (iOS simulator, LoopKit `f974241`) | No encryption; not tested against real hardware; HUD tile missing. Integration: `ios/INTEGRATION.md`. |
| Website ([site/](../site/)) | **Apple-style redesign live**: https://henryschwerdt.github.io/ai-insulin-pump/ — path-traced SolidCraft renders, scroll story, size comparison, disclaimer | Build ok, initial JS 2.2 kB gzip, viewer 144 kB on demand, screenshots 375/768/1440 light+dark | STL per size ~11 MB for the viewer (decimate later); exploded render has transparency artifacts; re-render via `site/scripts/render-product.sh` (~12 min). |

## Key decisions (with rationale)

1. **No custom ASIC.** Instead the **ISP1807** radio module (nRF52840, 8 × 8 × 1 mm, integrated antenna) for Rev A. An ASIC costs far more than 100 k€, and the antenna layout on the mini board would be the biggest risk. For Rev B the nRF54L15 as a bare chip is planned.
2. **Stadium reservoir 16 × 5 mm** instead of a cylinder, so that a build height of 8.5 mm becomes possible.
3. **Spindle next to the reservoir** with a carriage arm. Inline, the pump would be about twice as long.
4. **Qi coil Ø 17.6 mm.** With Ø 20 it would be 2.4 mm longer.
5. **Drive:** In Rev A a 5:1 geared stepper (0.0261 U per step, verified with encoder). In Rev B an **SMA ratchet drive** is planned (Omnipod principle, patent US6656159 expired). This makes the pump about 6–7 mm narrower and would be the smallest 200 U patch on the market. Refillability via a releasable pawl; the SMA wire is a wear part.
6. **No pressure-and-valve dosing**, because it flows out freely on a valve failure. Also **no piezo pump**, because it is not validated for insulin.
7. **Omnipod 5 is not emulated.** That would require signed P-256 transcripts and a key manager with App Attest. The DASH mode modeled on nightscout/ESP-Sim (GPL-3.0) is sufficient for Trio.
8. **CAD tools:** SolidCraft for 3D (CLI/MCP: `solidcraft-cli`), CADCraft for 2D (DXF/DWG; CADCraft cannot do 3D).
9. **Basal with 48 half-hour segments**, compatible with DASH.

## Decision log (user)

- 2026-11-19 (coordinator, cloud session): **Coaxial comparison model** (`generate.py/check.py --variant v010`, `mechanical/V010.md`). **Superseded for v0.1.0 by the owner's cup pod, layout A (`--drive cup`)**; it is kept only as a measured comparison. It has one coaxial rod, a closed wide bore of 25.7 × 4.7 mm with a 1.0 mm wall, the motor in the rear zone, no idler, a ring magnet with TMAG, USB-C in the rear wall, a clear lid on a flat gasket joint with 6 screws, and the fill septum on the underside (d3.2).
  - **Verified from a clean checkout:** `check.py --variant v010` PASS for both sizes. That covers fluid boundary, H14, one-rod, 54 bodies with no interference and 12 dock inserts. `--assembly` reports 0 blocking findings.
  - **Length targets missed:** OP-100 is **58.2 mm** against 45, OP-200 is **66.9 mm** against 54. The cause is the dry tail of the translating screw. All levers together reach about 49 / 58 mm. Compared with the cup pod (OP-100 47.96 / OP-200 66.78 × 34.6 mm), the coaxial model is 10 mm longer at OP-100, about equal at OP-200, but 2.6 mm narrower. The length-closure study was stopped in favour of the cup pod.
  - **Other open findings:** thrust margin 1.14 (target ≥ 2); the U/step firmware constant must be rescaled for the 116 mm² bore; the POWER board (572 mm²) does not fit the ~190 mm² pocket; the ring magnet is a custom part; the TMAG needs the A2 range plus a lookup calibration; the v010 dock inserts are not interchangeable with the bench inserts (z interface changed); cannula dome height still unmeasured.
- 2026-11-19: **v0.1.0 radio = Insight SiP ISP1807** (8 × 8 × 1, integrated certified antenna, consigned to JLC) on a MAIN board ≤ 400 mm²; button = small side-actuated tact switch on the POWER board edge (coordinator choice; a magnet tap near the TMAG would disturb the angle sensor). Partition per electronics/v010/MINIATURIZATION.md §11.
- 2026-11-19: **New hazards H14/H15** (docs/02-safety.md): manual septum injection while docked would bypass all limits → septum must be unreachable when docked (spec §3e); reverse while docked → interlock becomes `DOCKED XOR DIR_REVERSE`.
- 2026-11-19: **Only the integrated v0.1.0 pod is built** (spec §4c); the bench controller board is parked as a fallback/debug fixture (not ordered).
- 2026-11-19: **Drive = coaxial translating leadscrew + closed reservoir** (spec §3d); **OP-200 keeps 200 U at ≈ 54 mm** (user), OP-100 ≤ 45 mm via wider bore + compact front.
- 2026-11-19: **v0.1.0 safety chain uses a tiny independent supervisor MCU** (+ hardware over-current cut + two series switches; spec §7a) to reach ~300 mm² board area. Motor candidates for v0.1.0 in spec §4b (Zhaowei Ø3.4 geared stepper, samples first). The first v0.1.0 board (185 parts, 54 × 29 mm) did not route.
- 2026-11-19: **USB-C (waterproof) for charging + flashing; split boards allowed** (spec §2d); charge pads and cradle dropped.
- 2026-11-19: **v0.1.0 sizes: OP-100 and OP-200 only** (OP-70 dropped; spec §2c).
- 2026-11-19: **Size targets v0.1.0: OP-100 ≤ 45 mm, OP-200 ≤ 52 mm** incl. battery + electronics (spec §2b); first v0.1.0 CAD was 74 mm (OP-100) — rejected.
- 2026-11-19: **No check valve; Omnipod-style pressure fill** (spec §3c): syringe pushes through the septum while the motor retracts at a fixed rate; self-locking leadscrew prevents free flow; fluid module = clamp ring + septum + needle. Supersedes the automatic suction draw mode.
- 2026-11-19: **Transparent lid, no fill-window slot** (spec §2a): clear SLA lid with an engraved scale.
- 2026-11-19: **Independent design review** (`docs/REVIEW-2026-11-19.md`): top problems = seal friction budget, off-axis push lever, end cap not sealed to the reservoir, uncontrolled air path in draw mode, ~2.2 U lost motion at reversals, stick-slip basal accuracy, firmware current-sense scaling 3× wrong, TMAG angle plane, push-rod length, manufacturability/doc conflicts. All dispatched to the owners. **Before ordering the full pod: a ~20 € seal/leak/septum/lost-motion test-coupon order** settles the biggest unknowns.
- 2026-11-19: **Plunger coupling = central push rod, closed reservoir** (spec §3b). The side-slot coupling leaked (slot in front of the seal at a full reservoir). The user preferred unchanged dimensions via magnetic coupling, but the magnet simulation gives ~1.2 N vs ~7 N needed, so it was rejected; the user then left the choice open. Then the user required the same form factor: a same-envelope sealed drive (push band around the open end etc.) is being studied; push rod = fallback only. An independent full design review (docs/REVIEW-2026-11-19.md) checks every subsystem for whether it works as a pump.
- 2026-11-19: **Water only.** The pump must never be filled with insulin or any other drug, not even for bench tests into containers. Supersedes the earlier decision that allowed insulin bench tests into containers (commit 7c95570). Website gets a non-dismissable top banner on every page.
- 2026-11-19: **Goal v0.1.0 beta = integrated pod without the bench controller board**, parts ~98 % final before ordering, as much verification as possible in simulation (virtual pod, mechanical calcs, SPICE), then one order and bench tests only (still a test sample, never worn). The bench controller board stays as an optional test fixture.
- 2026-11-19: **Cost target ≤ 200 € all-in per complete pump, AliExpress-first** (spec §1d).
- 2026-11-19: **Hardware safety independent of software + component-level diagnostics**: discrete interlock, over-current cut, readbacks for every safety element, structured fault codes forwarded through every layer, Trio shows the faulty component and asks to replace it (`docs/06-diagnostics.md`, in progress).
- 2026-11-19: **Drive = geared stepper NFP-608-26.45 + sleeve coupler + leadscrew, refill = automatic draw mode** (app selects amount, motor retracts and draws insulin through the septum; duckbill check valve in the outlet). SMA ratchet and half-nut dropped for buildability.

- 2026-11-19: **Buildability beats minimal size**: builders are not watchmakers. If an off-the-shelf micro linear stepper actuator (motor + gearhead + leadscrew + slider, ideally FPC/ZIF) with a full drawing, ≥ 5 N and ≤ 0.03 U/step is found, it replaces the SMA ratchet (SMA stays a later option for minimal size). Research: `mechanical/linear-actuator-selection.md`.

- 2026-11-19: **Rev A = bench split** (pod sensor board + separate bench controller board, see spec §4a), because the integrated 17 × 29 mm board does not route.
- 2026-11-19: **Embedded firmware moves to Rust now** (Embassy on nRF52840, `firmware-rs/`). The C/Zephyr code in `firmware/` stays as the tested reference (173 tests) for differential testing until the Rust firmware passes the same bench tests; then it is retired. Unfinished C bench-target work is kept in `git stash` ("wip: stopped C bench-target agent").

- 2026-11-18: **Rev A = bench test sample only** (water tests, never on the body). Keep the size; battery ~17–26 mAh; no piezo (alarms via BLE/Trio only). Real buzzer + larger battery come in Rev B (SMA drive frees space).

## Next steps (in order)

1. Finish the KiCad layout: verify the ISP1807 footprint, routing, DRC 0 errors, Gerber/CPL/BOM in `electronics/pcbway/`, `ORDER.md`.
2. Finish mechanics Rev A: spring contacts, pressure ribs, `out/pcbway/`, `ASSEMBLY.md`.
3. Compile the firmware for `openpatch_reva` and `nrf52840dk/nrf52840` and test it on the DK.
4. **User:** measure the cannula with calipers (measurement sheet), then adapt the cannula pocket.
5. Bring costs to ≤ 500 € (3 instead of 5 boards, cheaper housings or motors) and then order.
6. Test bench: gravimetric delivery accuracy with water (see `docs/02-safety.md` §3).
7. Rev B: SMA ratchet drive, nRF54L15 as a bare chip, target 55 × 25 × 8.5 mm.

## How to continue (for a new Claude session)

- Read `CLAUDE.md` first, then this file, then `spec/design-parameters.md`.
- Run tests:
  - Firmware: `cmake -S firmware -B /tmp/fw && cmake --build /tmp/fw && ctest --test-dir /tmp/fw`
  - iOS: `cd ios/OpenPatchKit/OpenPatchCore && swift test`
  - Mechanics: `cd mechanical && python3 generate.py && python3 check.py`
  - Website: `cd site && npm ci && npm run build`
- After every unit of work, update this file and push.

- 2026-11-19 (user, design review): **v0.1.0 layout = two lanes.** Lane 1 in one row rear→front: transverse motor + right-angle gear → one rotating rod + cup plunger (concept B) → closed CNC tank → end cap (fill septum on the underside) → dock directly after the end cap (place-down pocket + 3–4 mm slide, 12 × 10 mm, U-clip like the original Insight connector, spring-steel clips). Lane 2 (+Y): battery, board, USB-C, piezo, button. Superseded: slot/carriage drive, second shaft, full-length dock tunnel, frozen dock interface.
- 2026-11-19 (user): size levers for the two-lane layout: **dock in lane 2 beside the end cap** (lane 1 ends at the end cap) and **wider/taller tank bore ≈ 22 × 5.5** (un-freezes the not-yet-ordered CNC reservoir) to hit OP-100 ≤ 45 mm / OP-200 ≤ 52 mm.
- 2026-11-19 (user): **no separate end cap** — fill septum (angled, from below) and side outlet + needle hub are integrated in the CNC tank front wall; plunger travels to the front wall (near-zero dead volume); dock = place-down pocket + 2 spring-steel clips. Lane 1 as wide as possible (tank bore ~24 × 5.5), lane 2 narrow. Target OP-100 ≈ 30–40 mm long.
- 2026-11-19 (user, confirmed sketch A — supersedes "dock in lane 2"): top view +X right, +Y up: **motor transverse at the far LEFT spanning both lanes** (nothing left of it); lane 1 (bottom) left→right: bevel pair (rod ends at gear B, magnet in gear B) → cup plunger → tank (septum under the front wall, outlet through the front wall) → **dock at the RIGHT END of lane 1 (bottom right)**; lane 2 (top, narrow): battery, board, piezo, button, USB-C.
- 2026-11-19 (firmware-rs): drive preset `nfp-608-26-45-cup-miter-1-1` (id 0x26, 840503125/119554 uU = 0.00703 U/step, bore 20.5 x 5.5 per CAD json) is the build.sh default for the cup pod; older presets kept for bench. `FillMode::Draw` (suction) is refused on it (no check valve), assisted pressure fill kept; tests in `openpatch-core/tests/preset_cup.rs`.
- 2026-11-19 (user): **motor locked = NFP-608-26.45-SGM** for the prototype (fits, 0.00703 U/step, ~8.6 N computed). Motor supply via 5 V boost + bulk cap (cell peak current), undervoltage lockout ~3.4 V; first bench test = thrust at 3.4 V and 5 V. Shorter Ø5 motor deferred.
- 2026-11-20 (user): **side-pressable button** with the case closed: side-actuated SMD tact switch at an outer board edge + thin flexing zone (≈ 0.4 mm, cut-out hinge) in the side wall, no hole; critical actions need a long press (emergency stop 3 s). Also: all electronics on the main board (SMD sounder on the board instead of the lid piezo); try to drop the TMAG rear strip by relocating the angle magnet; route on 6 layers, then shrink the board.
- 2026-11-20 (user): electronics path = **reduce the part count (≤ ~90), then hand/scripted routing**; fallback: routing guide for a manual KiCad finish (user or freelancer). The 132-part v4 board does not place/route at 528 mm² (see electronics/v010/cup/FIT-CHECK.md).
- 2026-11-20 (user): **dock hall sensor stays** (DRV5032FA, part of the HW cut path latch AND DOCKED; blocks motor reverse while docked). Main MCU → **HJSIP HJ-840** SiP (nRF52840, 6.2×7×1.0 mm, LCSC C50052094, JLC-stocked) replacing the consigned ISP1807; no consigned parts at all; sounder fitted (4×4×2 mm, board underside); no debug connector (bare SWD pads, USB DFU).
- 2026-11-20 (user): motor socket J1 dropped; motor lead plug cut, 4 wires soldered to pads at the board's west edge next to the motor (like the cell leads). Motor driver to be swapped STSPIN220 → DRV8835 (26.5 Ω coil, full steps, no chopper needed); part audit (PART-AUDIT.md) to remove legacy parts.
- 2026-11-20: **Buy list for the cup pod hardware** (2 pods + spares, carts AliExpress / GHW-Modellbau / Amazon.de / nfpshop): `docs/BUY-LIST.md`. Key finding: no m0.3 z16 miter pair exists; m0.3 z12 (OD 4.02, drawing read) or m0.4 z12 instead, CAD `cup.gears` must change; 12 further spec mismatches listed there (§6).
- 2026-11-20: handoff written: docs/HANDOFF-2026-11-20.md (current design + ordered open work). Branch merged into main.
- 2026-11-20 (cloud coordinator): **Independent netlist review of the 45-part cup board.** Verdict: the architecture is sound, but these fixes are needed before ordering. They have been passed to the board agent.
  - **C1:** R26 10 k → 6.8 k. The TPL5010 interval was 7.6 s instead of 2 s.
  - **C2:** U33 NAND → 74AUP1G86 XOR, so the hardware gate becomes `DOCKED XOR DIR_REVERSE` (spec §7, H15; the board implemented OR).
  - **C3:** add 4.7 µF on the HJ-840 REG0 3V3 rail and verify the load on the bench.
  - **M1:** U36 → 3-input AND including `MCU_EN`, plus a pull-down. This restores the CLAUDE.md rule "motor only with MCU enable AND watchdog" in hardware.
  - **M4/M5:** supervisor recovery pads and interlock test pads.
  - **M6:** capacitors rated 10 V.
  - **Minor:** I2C pull-ups, cell and motor polarity silkscreen, regenerated pin map, part audit and FMEA.
  - **Bench item:** measure the dock-hall margin at pre-slide and undocked positions.
- 2026-11-20: **Cup CAD on real BUY-LIST parts.**
  - m0.3 z12:z12 miter, so U/step is unchanged.
  - Nut AF 3.5 DIN 934, no thrust sleeve (gear B tapped on the rod), bonded bush, tube collar/bush/hub, flat silicone ring.
  - `elec_interface` unchanged.
  - OP-200 target in `cup_check` aligned to 54 mm.
  - Dropping the TMAG rear strip is not feasible: about 0.3 mT at the board (`mechanical/studies/cup_magnet_tmag.py`).
  - Clean checkout PASS. OP-100 47.96 / OP-200 66.78 × 34.6 × 8.5 mm.
  - Open: thrust margin 1.65 (< 2); steel rod behind the angle magnet (compare with brass on the bench); head washers do not fit (silicone dab); guard spring is not a catalogue part.
- 2026-11-20: **firmware-rs for the cup v4 board.** 845 host tests green; diag catalogue 154 codes, schema 3; Swift core 257 green.
  - DRV8835 full-step phase driver.
  - `board-cup-v4` pin map from `netlist_v4.py`.
  - VDDHDIV5 battery reading and REGOUT0 3.3 V.
  - Burst stepping; cell limits are placeholders until measured on the bench.
  - Occlusion by angle shortfall only (new warning 5-53-004).
  - New crate `openpatch-supervisor`: phase-edge step budget, permit/latch, mandatory POST vector (declared reverse with forward phases → permit drop), ROM-bootloader flashing only with the motor supply cut.
  - New crate `openpatch-boot-policy`: Ed25519 signed manifest v2, rollback counter in UICR.
  - LED state machine.
  - Open: port the pump application to the cup board, the STM32C0 platform shell, USB DFU glue.
- 2026-11-20: **SPICE of the corrected cup board** (`electronics/v010/cup/sim/REPORT.md`, `run_all.sh`).
  - **Passed:** enable logic 32/32 (docked XOR reverse now blocks docked + reverse in hardware), TPS2553 limit 0.552 A, FAULT → latch clear → cut in < 1 µs, TPL5010 timeout cut, 3V3 collapse cut, DRV8835 full step 0.18 A per coil.
  - **Model note:** the TI TPS61023 model is not physical in ngspice, so a labelled behavioural model is used.
  - **Hardware findings passed to the board agent:**
    - F1: 100 k pull-up on `DOCK_N`. Without it, an open hall joint enables forward motion undocked.
    - F3: second 10 µF on VBAT.
    - F5: 100 k pull-up on `SUP_NRST`.
    - F6: 100 nF at the DRV8835 VM pin.
    - F4: ILIM doc range 0.50–0.62 A.
  - **Firmware follow-ups:**
    - F2: loaded-VBAT abort below 2.8 V, and a 3.7 V rest threshold until the cell ESR is measured.
    - F7: STM32C011 BOR at its highest level, `SUP_PERMIT` held low for 10 ms after any reset.
- 2026-11-20: **Firmware SPICE follow-ups (F2/F3/F7).** 874 Rust tests, diag catalogue 155 codes / schema 4, Swift 257. New safety limits are tightenings only (spec §7):
  - no motor start below 3.7 V resting VBAT (interim until the cell ESR is measured);
  - stop a move when the loaded VBAT after the first step is below 2.8 V (new code `A-A0-004` CELL_SAG_UNDER_LOAD);
  - boost enable needs ≥ 3.4 V;
  - `SUP_PERMIT` is held low for ≥ 10 ms after any reset or brown-out;
  - BOR = highest is part of supervisor provisioning.
- 2026-11-20: **Remaining German translated and a language check added to CI.**
  - Translated: electronics README, cost doc, schematic and layout scripts with their regenerated BOM, netlist and reports; mechanical op_* comments and generated JSON.
  - New check `tools/check_language.py` with `tools/language-allowlist.txt`, run as the `language` job in security-ci.
  - Kept on purpose: iOS de.lproj, proper nouns, and the verbatim shop titles in BUY-LIST.
  - Temporary allowlist for `electronics/v010/**` and `firmware-rs/**` while the board work runs; no German was found there.
  - Known pre-existing issues: `mechanical/check.py` with default arguments raises `KeyError: 'purge'` (the cup and v010 variants are fine); `electronics/schematic/check_netlist.py` messages quote stale pins.
- 2026-11-20: **Cup board: hand placement and routing state (not orderable yet).** Owner decisions:
  - test pads on a break-off strip: SWD J10-J14 plus 6 interlock test points;
  - 4 SWD recovery pads under the finger;
  - two export variants, "dev" with the strip and "clean" without it;
  - stay with the nRF52840 and flash it once over SWD; JLC programming service as an option.
  - **Placement:** `electronics/v010/cup/manual_place.py` replaces the annealing placement. Every mechanical rule is checked on the library courtyards, including the USB through-hole slots. Pre-route DRC: 0 errors.
  - **Fixes:**
    - The antenna keep-out covered the HJ-840 feed pads. A7 and A8 are now bridged on F.Cu, which replaces the 0 ohm + 2 DNP pi network, so the circuit is unchanged.
    - Filled via in every used module pad (0.35/0.15, JLC POFV). Rows A/B and P0.00/P0.01 are not used. GPIOs are reassigned and `firmware-rs/openpatch-bench/src/board/cup_v4.rs` is updated; the cup bring-up firmware builds for thumbv7em.
    - Underside-capable packages, all in JLC stock: TPS2553DRVR (WSON-6; pinout checked in the TI datasheet: 1 OUT, 2 ILIM, 3 FAULT, 4 EN, 5 GND, 6 IN, pad GND), 2 x SN74AUP1G08DCKR, USBLC6-2P6, 2N7002W, 1N4148WS.
  - **Routing (Freerouting):**
    - 37 connections open, copper DRC clean.
    - Freerouting plateaus at 36-48 open and leaves the inner layers of the bridge unused.
    - An In4 3V3 plane made it worse (63 open).
    - A pre-routed D+ loop makes Freerouting hang.
  - **Open items:**
    - Route the 37 remaining connections: by hand in KiCad, or by a scripted bus of the 14 bridge nets on In2-In4.
    - DRV8835 has JLC stock 0: use JLC global sourcing, or HT8835A after a check.
    - Confirm the JLC via-in-pad and 0.15 mm drill pricing.
    - Regenerate the JLC dev/clean packages after routing.
    - Update FIRMWARE-PINMAP.md.
- 2026-11-24 (owner, after the 2:1 test print of the cup housing): **stadium USB-C opening, open-end dock, button cap, shell joint without a gap.** Mechanics only; `elec_interface` board outline, screws, supports and the SW1 position are unchanged. Both sizes PASS `check.py --variant v010 --drive cup --assembly` (OP-100 47.96 / OP-200 66.78 x 36.6 x 8.5).
  - **USB-C:** stadium opening 9.0 x 3.4 (R1.7 ends, x 19.0-28.0, z 4.0-7.4) with a 0.3 x 45 deg outer chamfer; stadium gasket recess and stadium silicone frame (inner 8.5 x 2.8, outer 10.6 x 5.0, 0.4 thick).
  - **Dock:** pocket open to the underside AND the +X end face (U-slot 9.8 x 4.4), the head slides in from the end like on the Insight pump; lintel above the opening, lead-in chamfers at the end and 0.4 mm chamfers on the bottom edges. The U-clip (its bridge blocked the end) became two 301 FH L-springs whose tabs sit in slots of two anchor blocks at the open end (arm 7.55 unchanged, 350 MPa). Slide 3.5, slide stop, needle + guard, dock hall (39.36, 11.75), roof z 4.4-4.9 under the board unchanged. Stencil DXF renamed `fab/stencil/dock_springs_301FH_0p10.dxf`; dock coupon rebuilt open-ended.
  - **Side button:** flex window + nub removed; printed button cap (new STL `OP-100_button_cap.stl`, stem d1.6, key recessed 0.2, flange bar inside) in a hole through the +Y LID wall at x 33.0 / z 6.35, O-ring 1.5 x 0.5 silicone in a d2.4 x 0.5 counterbore (20 % squeeze, BUY-LIST Z12, not yet sourced), stroke 0.30 to actuate. A d3.0 cap / ID 2.0 O-ring does not fit between the shell joint, the lid roof and the R1.8 top fillet.
  - **Shell joint (gap in the print):** cause = lid face designed 0.4 above the rim for the flat sheet gasket, and the lid roof resting on the corner posts (0.05 below the roof), so even without the gasket the lid stood 0.35 mm proud (0.7 mm at 2:1). Now the lid sits on the rim (hard stop, flush seam), seal = cast silicone ring 0.32 x 0.4 (Z4, STL `OP-xxx_lid_gasket.stl`) in a 0.45 x 0.45 rim groove, pressed by a 0.30 x 0.13 lid tongue: 20 % squeeze, 78 % fill. Post tops 0.1 below the roof, hold-down ribs 0.05 above the board. A bought 0.8-1.0 mm cord would need +2 mm width and length (no inside clearance at the walls): not taken.
  - Pre-order review inputs: (H8) the routed board puts the SW1 tip at y 35.65-35.77 / z ~6.7 against the agreed tip <= 35.35: the cap pad was extended to z 6.35-7.05 (cap axis 6.35, offset below the actuator), but **SW1 must move back 0.45 mm on the board (board y 82.30)**, the 0.9 mm wall has no room left for it (passed to the electronics side, OPEN); (M7) USB-C keep-out widened to x 18.8-28.2, y 26.6-35.7.
  - Open / VERIFY: SW1 move on the board (H8), SW1 body front face < y 35.2, thin spots (groove walls 0.225 / 0.175, 0.15 under the groove over the dock opening, 0.19 under the fillet behind the button counterbore: SLA only), seal-ring mould not designed, O-ring Z12 to source. The 2:1 print files in `mechanical/print/OP-100_x2/` are from the old geometry and were not regenerated.
