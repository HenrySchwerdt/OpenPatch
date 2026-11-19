# Reference chapters of the OpenPatch bench pod build guide

> **WARNING: BENCH TEST ONLY.** OpenPatch is a test project and **not a medical device**. The pod must **never be worn on, attached to, or used on a person or an animal.** **Fill it with water only. Never put insulin or any other drug into it, not even into a container.** All tests are table-top tests into a beaker, a vial or onto a balance. See [DISCLAIMER.md](../../DISCLAIMER.md), [CLAUDE.md](../../CLAUDE.md) and [docs/02-safety.md](../02-safety.md).

A step-by-step guide to build the **OP-100 bench pod** (spec §4a, Rev A bench split), power it from the bench controller board, and test it **with water** against the predictions of the simulations. The other two sizes (OP-70, OP-200) differ only in the reservoir and screw lengths (table in chapter 00).

State: written 2026-11-19 against the files in this repository. Gaps and values that depend on parts nobody has measured yet are marked **verify on your sample**. Controller-board items are marked **(confirm)** and **to be confirmed when the controller board is final**.

## Chapters

| # | File | Content |
|---|---|---|
| 00 | [00-overview.md](00-overview.md) | what you build, bench-only purpose, sizes, time, skill, safety rules, what the pod can and cannot do, known source gaps |
| 01 | [01-parts-and-tools.md](01-parts-and-tools.md) | bill of materials with part numbers and shop links, printed parts with file names, tools, consumables |
| 02 | [02-print-and-prepare.md](02-print-and-prepare.md) | ordering and post-processing prints, measuring critical dimensions (go / no-go), gear hub turning and sleeve, cutting the M1.6 rod, magnet polarity |
| 03 | [03-plunger-and-seal.md](03-plunger-and-seal.md) | plunger core, cast or cut seal rings, nose, **seal friction pull test** |
| 04 | [04-carriage-nut-shim.md](04-carriage-nut-shim.md) | carriage, M1.6 nut, steel tongue shim |
| 05 | [05-reservoir-end-cap-needle.md](05-reservoir-end-cap-needle.md) | reservoir, end cap, fill septum, duckbill valve, 30G needle and hub |
| 06 | [06-drive-motor-gears-leadscrew.md](06-drive-motor-gears-leadscrew.md) | shell, reservoir in place, leadscrew, gear B and sleeve, carriage, motor, gear A, spindle magnet, needle |
| 07 | [07-pod-sensor-board-ffc.md](07-pod-sensor-board-ffc.md) | TMAG5273 board, dock hall, FFC |
| 08 | [08-closure.md](08-closure.md) | lid contact test, gasket, lid, screws, height check |
| 09 | [09-dock-insert-and-dummy-head.md](09-dock-insert-and-dummy-head.md) | dummy cannula head, insert variant fit test, docking |
| 10 | [10-electronics-first-boot.md](10-electronics-first-boot.md) | controller board, power, probe-rs flashing, first boot, self-test and expected diagnostic codes, pairing, priming |
| 11 | [11-water-bench-tests.md](11-water-bench-tests.md) | gravimetric accuracy, occlusion, draw mode, leak, dock fit, 72 h endurance, with data sheets |
| 12 | [12-sim-predictions-and-report.md](12-sim-predictions-and-report.md) | predictions of the simulations, how to compare, how to report |
| 13 | [13-troubleshooting.md](13-troubleshooting.md) | diagnostic code and symptom to FRU to fix |
| 14 | [14-disassembly-and-cleaning.md](14-disassembly-and-cleaning.md) | disassembly, water-only cleaning, parts life, storage |

## Other files

| Path | Content |
|---|---|
| [templates/](templates/) | CSV data sheets (incoming inspection, gravimetric, occlusion, draw, leak, endurance, dock fit, self-test) and the [test report template](templates/test-report-template.md) |
| [tools/analyze_gravimetric.py](tools/analyze_gravimetric.py) | converts balance readings to delivered units, errors, measured U per step, series uncertainty and +-5 % statistics |
| [tools/render_steps.py](tools/render_steps.py), [tools/compose_steps.py](tools/compose_steps.py) | regenerate the step images in `img/` from `mechanical/out/bench/OP-100.sc` with the SolidCraft CLI |
| [img/](img/) | the step images (CAD renders with exploded insets and numbered callouts) |

## Order of work

1. Read chapter 00, order the **dock insert set** and the prints and parts (01, 02.1).
2. Incoming inspection and preparation (02). **Stop on any no-go.**
3. Plunger and its **seal friction test** (03): if it fails there is no point in building on.
4. Assemble (04 to 09), checking after every step.
5. Electronics and flashing (10): **the 16:20 drive preset must exist in your firmware build** (gap G1, chapter 10.4.1).
6. Water tests in the order of chapter 11, report with the template.

## Key numbers on one page

| Quantity | Value | Source |
|---|---|---|
| 1 U (model) | 10 ul of water = 9.982 mg at 20 degC | U100 convention |
| Reservoir | stadium bore 16.00 x 5.00 mm (+0.05/-0), area 74.63 mm2 | `reservoir_frozen` |
| Leadscrew | M1.6 x 0.35, cut length 25.0 mm (OP-100) | `parts.md` |
| Gear pair | 16 T (motor) : 20 T (screw), centre 5.51 mm built | `params.json` |
| Motor | NFP-608-26.45-SGM, 20 steps/rev, ratio 26.45 | spec §4 |
| Dose per step | **0.003951 U** (0.05 U is 12.66 steps) | spec §4 |
| Safety limits | bolus 10 U, 15 U/h, 1.5 U/min, occlusion 2 U, encoder 10 %/U | spec §7 |
| Acceptance | within +-5 % from 1 U (gravimetric) | docs/02-safety.md 3.1 |
| Pod size OP-100 | 47.0 x 32.0 x 8.4 mm | spec §2 |

## Licences

Documentation: CC BY-NC-SA 4.0 (see [LICENSE.md](../../LICENSE.md)). The dock insert is CERN-OHL-P-2.0. This guide describes a **bench self-build for research and education only**.
