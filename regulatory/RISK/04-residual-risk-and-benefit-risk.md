# 04 Residual risk and benefit-risk (placeholder with known design-stage facts)

> Test project. **No residual risk is accepted and no benefit-risk conclusion is made here.** Both are decisions of the legal manufacturer after verification and clinical evaluation. This file lists the facts that such a decision would have to weigh, taken from the repository on 2026-11-19.

## 1. Known open residual risks (design stage)

| # | Residual risk | Hazard | Evidence | What would reduce it |
|---|---|---|---|---|
| 1 | Dose inside a watchdog window is not bounded by hardware in Rev A | H1 | `docs/06-diagnostics.md` 1.5; measurement B11 pending | HW-A step budget, HW-B hourly monitor (Rev B) |
| 2 | Occlusion detection: alarm after 5 to 10 h at 0.5 U/h basal; total undelivered at alarm 2.5 to 5.2 U; post-release bolus up to about 3 U | H2 | sim 5.4 to 5.7 | pressure/current criterion before stall, lower threshold by stored volume, time criterion at basal |
| 3 | Drive thrust does not break loose the plunger seal in the model (FAIL) | H2 | sim 1.1 to 1.6 | seal redesign, current, gear pair, thrust-end change |
| 4 | Dose accuracy at 1 U does not meet +-5 % in the model as drawn | H1/H2 | sim 2.4 to 2.7, 2.9 | stiffer tongue, seal friction, backlash take-up, per-pod calibration |
| 5 | Air: 7.5 U dead layer, no air detection | H4 | sim 5.1, 5.2 | front stop, prime outlet-up, sensing |
| 6 | Gear-ratio mismatch between CAD snapshot and firmware default | H1 | `docs/STATUS.md` handoff | decide, align spec, CAD, firmware preset; `4-41-002` latches a wrong build |
| 7 | No audible alarm in Rev A pod; alarm priority mapping missing | H3 | spec §5 | Rev B buzzer, IEC 60601-1-8 table |
| 8 | No hardware measurements for any safety function | all | `firmware-rs/docs/stubs.md` | bench B01 to B24 (water) |
| 9 | First pairing trust-on-first-use; pod flash not protected on bench | H7 | `docs/04-protocol.md` s8 | OOB code, APPROTECT, `security/` review |
| 10 | Reusable fluid path, third-party cannula, drug-related risks (compatibility, stability, concentration) | new | not analysed | manufacturer programme (drug evidence is never produced in this project: water only) |

## 2. Benefit side

No clinical benefit is claimed. Benefit and clinical performance require a clinical evaluation (`../CLINICAL/`) by the manufacturer.

## 3. Placeholder for the conclusion (manufacturer)

| Item | Value |
|---|---|
| Overall residual risk acceptable? | to be decided by the legal manufacturer |
| Benefit-risk conclusion | to be decided by the legal manufacturer |
| Approved by / date | |
