# 12. Simulation predictions, how to compare, and the test report

> **WARNING: BENCH TEST ONLY.** Test project, not a medical device. Never worn, never used on a person or animal. **Water only: never fill it with insulin or any other drug, not even into a container.** See [DISCLAIMER.md](../../DISCLAIMER.md).

The project predicts the behaviour of the pod with two simulations. **Your measurements are the only way to tell whether the predictions are right.** Compare each measurement with the table below, write down the difference, and send the report. Agreement and disagreement are equally useful.

## 12.1 The two simulations

| Simulation | What it models | Files | Re-run |
|---|---|---|---|
| **Mechanical** (`mechanical/sim/`) | thrust and torque budget of the drive, seal friction, dose resolution and error, tolerance stack-ups (Monte Carlo), structural checks (tongue, arms, buckling), priming volume, bubbles, occlusion stored volume, on the **current CAD** (gear pair 16:20, 0.003951 U/step) | `mechanical/sim/REPORT.md` (2026-11-19: 16 PASS, 10 WARN, 17 FAIL), `common.py` (inputs tagged [DS] datasheet, [LIT] literature, [ASM] assumption) | `python3 mechanical/sim/run_all.py` (4 s) |
| **Virtual pod** (`firmware-rs/openpatch-sim/`) | the real `openpatch-core` firmware on a physics model: delivery, occlusion alarms, dock loss, magnet loss, watchdog, brown-out, flash power loss, 48 h wear; 25 scenarios and Monte Carlo of 1000 pods | `firmware-rs/openpatch-sim/REPORT.md`, `scenarios/*.toml` | `cargo run --release -p openpatch-sim --bin opsim -- report --runs 1000 --out report.md` |

**Caveat:** the virtual-pod report in the repository uses the **15:12 gear pair** of the older concept (0.00617 U/step) and assumes a seal friction of 1.5 N static / 0.8 N dynamic, **four times lower than the 9.6 N the mechanical simulation computes**. Treat the two as bracketing the truth: the mechanical model is the pessimistic one for thrust and friction, the virtual pod the optimistic one. The firmware logic results (alarm latencies, watchdog, interlock) are independent of the pair.

## 12.2 Predicted versus measured (fill the right-hand columns)

Predictions are from the reports named in the "Source" column. "Basis" says what the number rests on: **CAD** (geometry from the model), **[ASM]** (assumption that your bench test replaces), **MC** (Monte Carlo). Put your value and the verdict in `templates/test-report-template.md` section 6.

| # | Quantity | Prediction | Source | Basis | Test | Your value | Agree? |
|---|---|---|---|---|---|---|---|
| 1 | Plunger thrust at the 105 mA controller limit | **4.0 N** (WARN against 5 N) | mech 1.1 | CAD | 11.1 | | |
| 2 | Plunger thrust at 181 mA rated | **7.0 N** | mech 1.2 | CAD | 11.1 | | |
| 3 | Plunger seal friction, kinetic / breakaway (two rings, 0.13 mm squeeze) | **9.6 N / 14.3 N**; range 3.6 to 21.5 N | mech 1.2 | [ASM] | 03.5 | | |
| 4 | Friction budget at 105 mA / at 181 mA | **1.7 N / about 3.0 N** kinetic | mech 1.2 (derived 03.5) | CAD | 03.5 | | |
| 5 | P(motor cannot break the plunger loose), 105 mA / 181 mA | 100 % / 95 % | mech 1.4 | MC [ASM] | 11.1 | | |
| 6 | Resolution | **0.003951 U/step**, 0.05 U = 12.66 steps (rounding +2.7 %) | mech 2.1, 2.2 | CAD | 11.2 | | |
| 7 | Static error 1 U (area, lead, uncalibrated) | **1.4 %** (95 %) | mech 2.3 | [ASM] | 11.2b | | |
| 8 | 1 U inside +-5 % (95 %) | 73.7 % of doses as drawn (S1); 7.1 % outside with a 1.2 mm tongue and 1.5 N seal friction (S3) | mech 2.4, 2.5 | [ASM] | 11.2b | | |
| 9 | 1 U, virtual pod (1000 pods) | mean -0.11 %, sd 2.47 %, 94.4 % inside +-5 % | opsim 5.1 | MC [ASM] | 11.2b | | |
| 10 | 10 U | mean +0.02 %, sd 0.79 %, 100 % inside +-5 % | opsim 5.1 | MC [ASM] | 11.2c | | |
| 11 | 0.05 U single dose | sd **50.7 %**, only 13.2 % inside +-5 %: judge the 100-dose series, not the single dose | opsim 5.1 | MC [ASM] | 11.2a | | |
| 12 | First 1 U after a draw and prime | **-22 to -60 %** (mech 2.9); mean **-348 mU** (opsim) | mech 2.9, opsim 5.1 | [ASM] | 11.2d | | |
| 13 | Gear backlash/binding at the CAD centre | binds in 35 % of pods at 5.40 mm; built centre 5.51 mm, P(ok) 74 % (MJF) / 88 % (SLA) | mech 3.1 | CAD | 06.3 | | |
| 14 | Pod height | nominal 8.4 mm, worst case 8.60 mm MJF, 8.50 SLA; spec limit 8.5 mm | mech 3.6 | CAD | 08.3 | | |
| 15 | Lid clearance over the reservoir | 0.00 mm nominal, 50 % probability of contact | mech 3.7 | CAD | 08.1 | | |
| 16 | Lid clearance over the tallest board part | +0.20 mm nominal, -0.28 mm worst case | mech 3.8 | CAD | 07.5 | | |
| 17 | Dead layer in front of the plunger | 7.5 U (1.0 mm); about 2.2 U with the 0.7 mm nose | mech 5.2, 03.3 | CAD | 11.2d | | |
| 18 | Priming path volume | **2.21 U** against the firmware prime limit 0.524 U per command | mech 5.1 | CAD | 10.8 | | |
| 19 | Snap-arm peak strain (PA12 / tough resin) | 1.50 % against 3.0 % / 2.0 % allowed | mech 4.1, 4.2 | CAD | 11.6 | | |
| 20 | Dock pull-off / insertion force | **0.6 N / 2.0 N** (WARN: want 1.5 to 10 N) | mech 4.3 | CAD [ASM] | 11.6 | | |
| 21 | Needle landing offset / lead-in | +-0.40 mm against 1.34 mm radius; lead-in 0.40 mm (WARN) | mech 3.3, 3.4 | CAD | 11.6 | | |
| 22 | Dock hall switching distance (face to die) | FA/FB: assert **4.8 to 7.3 mm** (too early); AJ: **3.7 to 5.1 mm**; ZE: 1.6 to 2.2 mm | PARTS-LOCK 10 | datasheet calc | 10.5 | | |
| 23 | TMAG5273 field at the 0.6 mm gap | about 35 mT (fits the +-40 mT range) | `OP-100.layout.json` | CAD | 07.2 | | |
| 24 | Draw suction at 1000 pulses per second, 29G / 27G fill needle | **29 kPa** (limit 30) / about 12 kPa; force margin FAIL (0.26x) | mech 1.7, 1.8, 1.5 | [LIT] | 11.4 | | |
| 25 | Draw of 50 U | core 49.91 U, vial 49.23 U; stall at the rear stop reports the confirmed volume | opsim `refill_draw`, `draw_endstop` | MC [ASM] | 11.4 | | |
| 26 | Occlusion, bolus: undelivered at the alarm | mech sim **3.45 to 3.92 U (FAIL)**; opsim **0.85 U**, mean 0.99 U, 99th percentile 1.93 U; encoder only: 50.8 % above 2 U | mech 5.4, 5.5; opsim 5.2 | [ASM] | 11.3 | | |
| 27 | Occlusion, basal 1 U/h: alarm after | **3019 s** nominal (0.83 U), mean 3642 s, 99th percentile 7147 s | opsim 4, 5.2 | [ASM] | 11.3 | | |
| 28 | Occlusion, basal 3 U/h: alarm after | **961 s**, 0.80 U | opsim 4 | [ASM] | 11.3 | | |
| 29 | Firmware hang with the driver armed: reset after / steps run before the cut | **1.9 s / 389 steps** (about 1.5 U at 0.00395 U/step) | opsim `hang_runaway` | [ASM] | 10.5 step 5 | | |
| 30 | 48 h wear: core / needle | **79.12 U / 78.80 U (-0.4 %)** | opsim `wear_48h` | [ASM] | 11.7 | | |
| 31 | Winding dissipation, both phases | **0.58 W** at 105 mA, **1.74 W** at 181 mA | mech 1.10 | CAD | 11.1 | | |
| 32 | Leadscrew buckling margin OP-100 / OP-200 | 12x / 4x (WARN) | mech 4.8 | CAD | n/a | | |
| 33 | Carriage tongue (steel shim now): thrust-train stiffness | printed tongue 19 N/mm (FAIL, 100 N/mm wanted); allowable thrust 2.0 N | mech 4.4 to 4.6 | CAD | 11.1 | | |

## 12.3 How to compare

1. **Use the same units.** The reports quote U at U100: 1 U = 10 ul = 9.98 mg water. Convert your mass first (`tools/analyze_gravimetric.py`).
2. **Bracket, do not match.** A measurement inside the stated range (for example seal friction 3.6 to 21.5 N) confirms the model's structure; a value outside it means a missing effect. Say which.
3. **Change the assumption, re-run.** If your measured seal friction is 4 N instead of the assumed value, edit the tagged [ASM] constants in `mechanical/sim/common.py` and re-run `run_all.py`; the report shows which verdicts flip. For the virtual pod put your values into a scenario TOML (`[params...]`).
4. **Never adjust the physical pod or the firmware calibration to hide a difference.** Record it.

## 12.4 Reporting your results

1. Copy [templates/test-report-template.md](templates/test-report-template.md) to a new file `my-report-<pod-id>.md` and fill every section; leave a cell empty rather than guessing.
2. Attach the CSV data (`gravimetric_log.csv` etc.), the firmware `bench.csv`, photos of the pod and of any failure, the exact repository commit (`git rev-parse HEAD`) and the firmware features you built.
3. Open an issue on the project repository with the report. Do not include personal details (names, addresses, e-mail, location) in the report or in the photos.
4. State the safety confirmation in the report header: **water only, bench only, no person, no animal, no drug.** A report without it will not be used.

Next: [13-troubleshooting.md](13-troubleshooting.md).
