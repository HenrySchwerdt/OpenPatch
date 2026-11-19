# Project status & handover

> This file is the **entry point for every new session** (another machine, another Claude subscription, another person).
> It is updated on every push. Last updated: **2026-11-18**.

## HANDOFF (2026-11-19) — read this first

**Setup:** see `docs/SETUP.md` (all tools, macOS/Linux/Windows).

**Current architecture (decided):** Rev A = bench split (pod with mechanics + small pod sensor board, FFC to a ~40 × 50 mm bench controller board with nRF52840 module). Drive = **NFP-608-26.45 geared stepper + sleeve coupler + M1.6 leadscrew**, refill = **automatic draw mode** (motor reverses, duckbill check valve in the outlet). Reservoir = **frozen CNC polypropylene part** (spec §3a), septum/valve/needle in a separate end cap. Cannula = Accu-Chek Insight Flex, horizontal slide-on dock (dimensions not public → dock fit-test coupon). Firmware = **Rust** (`firmware-rs/`, Embassy). Two-pod system (48 h per pod). Tests with water or insulin **into containers only, never a person**.

**Work in progress at handoff (merged to main on user request as WIP snapshots `a2913ac`/`b2afa23`; branch `wip/2026-11-19-handoff` kept):** three agents were mid-task when the session ended — tests and checks of this snapshot are NOT verified:
1. `mechanical/`: stepper/coaxial redesign, envelope shrink (target width ~25–27 mm), annotated top view, CNC-PP reservoir drawings + PCBWay order README (`out/bench/fab/reservoir-cnc/`), end cap with septum + duckbill. `check.py --variant bench` must pass.
2. `electronics/bench/`: controller board (STSPIN220 + current sense, interlock incl. DOCKED, TPL5010 2 s, PicoBlade 4-pin motor header) and pod sensor board (TMAG5273 mandatory, dock hall, FFC) → DRC 0, JLCPCB packages, `pin-assignment.md`, `ORDER.md`, `COST.md`. Then an **independent layout review** (antenna keep-out all layers, motor loop, shunt Kelvin, decoupling, unbroken GND).
3. `firmware-rs/`: port of the C core (all 173 behaviours) + property + differential tests, stepper preset NFP_608_2645 (exact rational, no default), FillDraw refill mode, Embassy app for bench + nRF52840-DK. At snapshot `b2afa23` the workspace compiles (`cargo build --workspace`); `cargo test` was not re-run.

**Next steps (in order):**
1. Finish the three areas above on main and get everything green: `cargo test --workspace`, `check.py --variant bench`, KiCad DRC 0 for both bench boards, `npm run build`.
2. Independent DFM review of the CNC reservoir drawings; independent PCB layout review; fix findings.
3. Write `SHOPPING.md`: one complete bench iteration (JLCPCB boards, JLC3DP prints, PCBWay CNC reservoir ×2 per size, NFP motors, M1.6 rod/nuts, magnets, duckbill valves, 30G needles, silicone, FFC, programmer) with links, qty, prices.
4. User: print the dock fit-test coupon first, test against a real Insight Flex head, enter the winning variant.
5. First order, bench tests per `docs/02-safety.md` §3; log real prices in `docs/05-cost-model.md`.
6. Rev B: integrated pod (bare nRF54L15, HDI), motor with FPC tail (group buy), battery + Qi, no cables inside the pod (spec §1c).

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
