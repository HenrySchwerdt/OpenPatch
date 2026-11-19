# OpenPatch bench pod test report (template)

> **BENCH TEST ONLY.** Test project, not a medical device. **Water only. Never worn, never used on a person or animal, never filled with insulin or any other drug, not even into a container.** Copy this file to `my-report-<pod-id>.md`, fill every section, leave a cell empty instead of guessing, and attach the CSV files. **Do not put personal details (names, addresses, e-mail, location) into the report or the photos.**

## 0. Safety confirmation (required)

- [ ] Only water was used. No insulin or other drug was ever in the pod, the vials, the syringes or on the bench.
- [ ] The pod was never attached to, worn on, or connected to a person or an animal.
- [ ] The hardware interlock was never bridged and no safety limit was changed.
- [ ] Any deviation from the guide is listed in section 12.

## 1. Identification

| Item | Entry |
|---|---|
| Pod ID (your label, not your name) | |
| Size | OP-70 / **OP-100** / OP-200 |
| Report date | |
| Repository commit (`git rev-parse HEAD`) | |
| Firmware build features (drive preset, board, angle, dev-plaintext) | |
| Controller board revision / ORDER.md version | |
| Pod board variant (dock hall FA / AJ, TMAG5273) | |
| Print materials and vendor (P1 .. P10) | |
| Bought parts: shops and lot notes (motor, gears, magnets, duckbill, needle) | |
| Balance model, resolution, calibration weights used | |

## 2. Parts received and substitutions

| Part ID | As specified? | Substitution or problem |
|---|---|---|
| | | |

## 3. Incoming inspection (attach `incoming-inspection.csv`)

| Item | Result |
|---|---|
| Features outside the go range (list) | |
| Carriage hex pocket across flats (3.3 / 3.8) | |
| Motor shaft free length, plug type, coil resistances | |
| Magnet checks (diametric, polarity) | |
| **Seal friction: route, rings, breakaway N, kinetic N** | |

## 4. Build log (pass / fail per chapter check)

| Chapter | Check | Pass / Fail | Remark |
|---|---|---|---|
| 03 | seal friction <= 3.0 N | | |
| 04 | nut captive, shim straight | | |
| 05 | cap flush, valve direction, needle open | | |
| 06 | carriage full stroke, mesh, end float, needle aligned | | |
| 07 | magnet gap to TMAG (mm), no shorts | | |
| 08 | dye test lid/reservoir, closed height (mm) | | |
| 09 | best insert ID, insertion N, pull-off N | | |

## 5. Electronics and firmware

| Item | Result |
|---|---|
| Controller revision, confirm items C1 to C6 resolved? | |
| Idle current at 5 V, 3V3 | |
| Flash and boot log (calibration line) | |
| TMAG5273 found / field magnitude | |
| Dock hall assert / release distance (mm), variant | |
| VMOT collapse time after a hang (s) | |
| Self-test results (`selftest_log.csv`), diagnostic codes seen | |

## 6. Predicted versus measured (see chapter 12.2)

| # | Quantity | Prediction | Measured | Agree? (yes / within range / no) | Comment |
|---|---|---|---|---|---|
| 1 | thrust at 105 mA / 181 mA (N) | 4.0 / 7.0 | | | |
| 3 | seal friction kinetic / breakaway (N) | 9.6 / 14.3 (3.6 to 21.5) | | | |
| 6 | U per step | 0.003951 | | | |
| 9 | 1 U series: mean error / sd (%) | -0.11 / 2.47 (virtual pod) | | | |
| 10 | 10 U: mean error / sd (%) | +0.02 / 0.79 | | | |
| 11 | 0.05 U x 100: cumulative error (%) | judge the series | | | |
| 12 | first 1 U after a draw (%) | -22 to -60 | | | |
| 13 | gear mesh binds? | 35 % at 5.40 mm; built 5.51 | | | |
| 14 | closed height (mm) | 8.4 (up to 8.6) | | | |
| 15 | lid touches the reservoir? | 50 % | | | |
| 18 | priming commands needed / volume (U) | 2.2 U path, 0.524 U per command | | | |
| 20 | dock pull-off / insertion (N) | 0.6 / 2.0 | | | |
| 22 | dock hall assert distance (mm) | FA 4.8 to 7.3; AJ 3.7 to 5.1 | | | |
| 24 | draw suction / fill needle gauge | 12 kPa (27G), 29 kPa (29G) | | | |
| 26 | bolus occlusion: undelivered at alarm (U), latency (s) | 0.85 U, 34 s (virtual pod); 3.4 to 3.9 U (mechanical sim) | | | |
| 27 | basal 1 U/h occlusion alarm (s) | 3019 | | | |
| 29 | hang: reset after (s) | 1.9 | | | |
| 30 | 48 h delivered vs programmed (%) | -0.4 | | | |

## 7. Gravimetric accuracy (11.2; attach `gravimetric_log.csv` and the analysis output)

| Series | Runs | Mean error % | sd % | Inside +-5 % | Measured U per step | Uncertainty % | Verdict |
|---|---|---|---|---|---|---|---|
| 0.05 U x 100 | | | | | | | |
| 1 U x 10 | | | | | | | |
| 10 U | | | | | | | |
| first 1 U after a draw | | | | | | | |

## 8. Occlusion (11.3; attach `occlusion_log.csv`)

| Test | Alarm time (s) | Undelivered (U) | Alarm source | Release volume (ul) | Pass (<= 2 U) |
|---|---|---|---|---|---|
| bolus 8 U, clamp at 60 s | | | | | |
| basal 3 U/h | | | | | |
| basal 1 U/h (optional) | | | | | |
| Free-run peak current (median / max mA), blocked peak (mA) | | | | | |

## 9. Draw mode (11.4; attach `draw_log.csv`)

Controller revision with the DIR_REVERSE gate? yes / no (if no: not possible, state so).

| Requested U | Needle | Drawn by firmware (U) | Drawn by mass (U) | Diff % | Bubble (mm3) | Stalled at the rear stop | First 1 U after (%) |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## 10. Leak tests (11.5; attach `leak_log.csv`)

Item 3.5 of `docs/02-safety.md` (30 min at 1 m depth) was **not applicable** to the Rev A bench housing and was not done: yes / no.

| Test | Gain (mg) | Wet? | Location | Pass |
|---|---|---|---|---|
| static, clamped outlet | | | | |
| septum re-seal | | | | |
| anti-siphon (200 mm below / above, 30 min) | | | | |
| vacuum hold after a draw | | | | |

## 11. Dock insert fit and endurance (11.6, 11.7)

| Item | Result |
|---|---|
| Best insert ID and values (A, N) | |
| Insertion / pull-off force (N), cycles 1 / 10 / 25 / 50 | |
| Arm whitening, creep, cracks after 50 cycles | |
| `DOCKED` correct in every cycle? needle landed every time? | |
| 72 h endurance: achieved hours, wear-timer behaviour (Activate), delivered vs programmed (%), resets, comms-loss fallback, leaks | |

## 12. Deviations from the guide, modifications, firmware changes

| What | Why | Effect |
|---|---|---|
| | | |

## 13. Faults, codes and troubleshooting

| Time | Symptom or code | Part (FRU) | Fix | Result |
|---|---|---|---|---|
| | | | | |

## 14. Conclusions

- What worked:
- What failed or is out of the predicted range:
- Biggest finding (one sentence):
- Suggested change to CAD, firmware or the guide:

## 15. Attachments

- [ ] `incoming-inspection.csv`  - [ ] `gravimetric_log.csv` and the analysis output  - [ ] `occlusion_log.csv`  - [ ] `draw_log.csv`  - [ ] `leak_log.csv`  - [ ] `dock_fit_log.csv`  - [ ] `endurance_log.csv`  - [ ] `selftest_log.csv`  - [ ] firmware `bench.csv` and `run.log`  - [ ] photos of the open pod, failures and the test set-up (no people, no personal details)
