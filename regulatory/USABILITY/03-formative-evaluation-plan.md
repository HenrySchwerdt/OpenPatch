# 03 Formative evaluation plan (IEC 62366-1 5.7.2) - bench and simulated environment only

> Test project. **No evaluation on a person, no on-body task, no drug.** The plan covers what the open project can learn with engineers and with water-filled pods on a bench, and states what the legal manufacturer must do later (summative validation with representative users).

## 1. Objectives

Find use errors early in: dock and undock, draw (refill) with water, priming, pod swap in the app against `SimulatedPod`, alarm presentation, error messages and FRU instructions, pairing. Output: a list of use errors and design changes, no performance claim.

## 2. Participants

Engineers and builders (not representative of intended users). Documented as such; results are only usable as formative input.

## 3. Method and materials

| Study | Set-up | Data | Hazard link |
|---|---|---|---|
| F1 Dock fit and release | printed dock coupon and insert variants on a dummy cannula head (`cannula_adapter`), bench pod, no real patient | insertion and pull-off force (sim 4.3 vs measurement), error counts, photos | U1 |
| F2 Draw with water | bench pod, water vial and syringe | steps completed, errors (needle out, air), time | U3, U5 |
| F3 Swap in the app | `SimulatedPod` pair, iOS simulator or test device, scripted failures (lost reply, app restart) | task completion, wrong-order attempts | U6 |
| F4 Alarm perception | bench controller buzzer and phone alerts in lab and noisy conditions | detection rate and delay | U7 |
| F5 Error/FRU message comprehension | screenshots of component health view and alerts | comprehension of the recommended action | U9 |
| F6 Pairing | bench pods, two phones | time, wrong-pod pairings | U8 |

Rules: no participant wears any part; no insulin or other drug (water only, per DISCLAIMER); sessions recorded as short notes (date, version, observed error, severity, change).

## 4. Analysis

Use errors are rated for hazard link (`../RISK/02-hazard-analysis.md`), root cause (UI, device, instructions), and mitigation. Results go into the usability engineering file and update `02-known-use-errors.md`.

## 5. Summative evaluation (legal manufacturer)

Representative users per group (FDA human factors guidance; typical samples of 15 or more per group, to be confirmed), simulated use, critical-task list from the use-related risk analysis, production-equivalent device and labelling. **Entirely the manufacturer's responsibility; not planned or written here.**
