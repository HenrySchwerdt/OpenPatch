# Project status & handover

> This file is the **entry point for every new session** (another machine, another Claude subscription, another person).
> It is updated on every push. Last updated: **2026-11-19 (cloud session, v0.1.0 integrated model merged)**.

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
