# Project status & handover

> This file is the **entry point for every new session** (another machine, another Claude subscription, another person).
> It is updated on every push. Last updated: **2026-11-18**.

## Goal

An open-source patch insulin pump ("OpenPatch"). It is detachable, plugs onto an Accu-Chek Insight Flex cannula and is held by Velcro. Further key points:
- Filling by syringe, inductive charging.
- Sizes: 70, 100 and 200 U.
- Build height ≤ 8.5 mm.
- Controlled from Trio, either through a dedicated kit or through DASH emulation.
- Orderable from PCBWay, target budget ≤ 500 €.
- Assembly **without a soldering iron**.
- Goal: smaller than anything on the market.

All dimensions and components are in [spec/design-parameters.md](../spec/design-parameters.md). That is the **single source of truth**.

## Status per subproject

| Area | Status | Verified | Open |
|---|---|---|---|
| Mechanics ([mechanical/](../mechanical/)) | Parametric SolidCraft model for 3 sizes, STEP/STL | `check.py`: all 3 sizes PASS (38/42/55.4 × 32 × 8.5 mm) | Rev A with real parts in progress: motor/spindle purchased parts, bearings, seals, spring contacts, piston seal + casting mold, PCBWay print folder, `ASSEMBLY.md`. The cannula pocket is only a placeholder until the Insight Flex is measured (`mechanical/cannula-measurement.md`). |
| Electronics ([electronics/](../electronics/)) | SKiDL netlist, BOM (51 line items), pin assignment, board outline as DXF | ERC clean, 42 custom rule checks pass | **KiCad layout + autorouting + DRC + PCBWay package in progress.** The ISP1807 pad geometry must be checked against the datasheet, otherwise do NOT order. Cost estimated ~610 €, i.e. over budget. |
| Firmware ([firmware/](../firmware/)) | Portable C core: delivery, safety, reservoir, log, protocol | 129/129 host tests, ~99 % line coverage | Zephyr build for ISP1807 (nRF52840) and nRF52840-DK in progress. Open: crypto (AES-CCM only an interface), DASH mode, `GetStatus` should return the last accepted sequence number. |
| iOS/Trio ([ios/](../ios/)) | `OpenPatchKit` (LoopKit PumpManager) + `OpenPatchCore` | 88 core tests + 36 kit tests green | No encryption; not tested against real hardware; HUD tile missing. Integration: `ios/INTEGRATION.md`. |
| Website ([site/](../site/)) | Vite + three.js, 3D model, sizes, build guide, BOM, costs | Build ok, three.js chunk 158 kB gzip | Workflow `.github/workflows/pages.yml`. Pages must be set to "GitHub Actions" in the repo. |

## Key decisions (with rationale)

1. **No custom ASIC.** Instead the **ISP1807** radio module (nRF52840, 8 × 8 × 1 mm, integrated antenna) for Rev A. An ASIC costs far more than 100 k€, and the antenna layout on the mini board would be the biggest risk. For Rev B the nRF54L15 as a bare chip is planned.
2. **Stadium reservoir 16 × 5 mm** instead of a cylinder, so that a build height of 8.5 mm becomes possible.
3. **Spindle next to the reservoir** with a carriage arm. Inline, the pump would be about twice as long.
4. **Qi coil Ø 17.6 mm.** With Ø 20 it would be 2.4 mm longer.
5. **Drive:** In Rev A a stepper motor (0.0131 U per step, verified with encoder). In Rev B an **SMA ratchet drive** is planned (Omnipod principle, patent US6656159 expired). This makes the pump about 6–7 mm narrower and would be the smallest 200 U patch on the market. Refillability via a releasable pawl; the SMA wire is a wear part.
6. **No pressure-and-valve dosing**, because it flows out freely on a valve failure. Also **no piezo pump**, because it is not validated for insulin.
7. **Omnipod 5 is not emulated.** That would require signed P-256 transcripts and a key manager with App Attest. The DASH mode modeled on nightscout/ESP-Sim (GPL-3.0) is sufficient for Trio.
8. **CAD tools:** SolidCraft for 3D (CLI/MCP: `solidcraft-cli`), CADCraft for 2D (DXF/DWG; CADCraft cannot do 3D).
9. **Basal with 48 half-hour segments**, compatible with DASH.

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
