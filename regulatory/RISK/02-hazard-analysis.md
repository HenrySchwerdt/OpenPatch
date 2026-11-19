# 02 Hazard analysis

> Test project. Severity values are **proposals for a manufacturer to review**; probabilities are left empty on purpose (no field data, no hardware measurements). Hazards H1 to H10 are from `../../docs/02-safety.md`; H11 to H13 are proposed in `../../docs/06-diagnostics.md` section 1.2 and not yet merged into `02-safety.md`. Controls, diagnostic codes and verifications per hazard are in the generated `TRACE.md`; the diagnostic code catalogue is `../../docs/06-diagnostics.md` section 4 (150 codes) and the per-code matrix will be `../../docs/06-diagnostics-trace.md`.

## 1. Hazards, hazardous situations, harm, controls

| ID | Hazard | Hazardous situation (example) | Harm | Sev (proposal) | Prob | Risk controls (ISO 14971 order) | Diagnostic codes (examples) | Residual risk comment |
|---|---|---|---|---|---|---|---|---|
| H1 | Over-delivery | firmware fault keeps stepping; duplicated or forged bolus; mechanical jump; wrong calibration (gear ratio 25 % error) | severe hypoglycaemia, death | 5 | open | **inherent/protective hardware**: interlock gates, watchdog, over-current cut, optional step budget; **protective software**: supervisor limits (10 U, 15 U/h, 1.7 U/min), encoder cross-check, calibration gating; protocol seq/replay/auth | `1-04-*`, `1-05-*`, `1-06-001`, `1-07-*`, `4-41-002`, `6-60-008`, `7-70-*`, `7-77-*` | Rev A: no hardware dose bound inside the watchdog window (about 2.5 to 4.9 U, upper bound about 25 U); HW-A/HW-B pending decision |
| H2 | Under-delivery / occlusion | kinked cannula, bubbles, stalled motor, seal friction too high (sim: thrust margin FAIL) | hyperglycaemia, ketoacidosis | 4 | open | encoder slip, current rise, 2 U shortfall alarm; dock gate; mechanical redesign | `5-53-*`, `6-60-*`, `4-42-*`, `1-03-*`, `1-08-*` | sim 5.4: alarm after 2.9 to 5.2 U; 5 to 10 h at 0.5 U/h; post-release bolus 0.5 to 3.2 U |
| H3 | Unnoticed delivery stop | battery empty, brown-out, crash, alarm not heard (Rev A pod without buzzer) | as H2 | 4 | open | boot SUSPENDED + alarm; battery thresholds; wear timer; BLE alerts | `1-01-002`, `7-74-*`, `9-90-*`, `A-A0-*`, `1-0C-002` | audible alarm in Rev B required |
| H4 | Air in the reservoir | filling, draw mode vacuum, dead layer 7.5 U (sim 5.2) | under-delivery, delayed start, bolus on pressure change | 3 | open | duckbill valve, priming, instructions (manufacturer) | `5-50-004/005`, `7-73-*` | no air-in-line detection |
| H5 | Wrong concentration | non-U100 insulin filled (a real drug is out of scope for the project, relevant to a manufacturer) | over- or under-dose by a factor | 5 | open | app requires U100 and insulin type; labelling | none (process) | process control only; the pod cannot detect concentration |
| H6 | Loss of communication | BLE gone | stale temp basal continues | 3 | open | temp basal reverts after max 30 min; basal autonomous on pod | `7-71-*`, `8-80-*`, `9-90-*` | |
| H7 | Unauthorised access | attacker commands bolus or changes settings; replay; MITM in pairing window | over-delivery, privacy | 5 | open | button-gated pairing, X25519, AES-CCM, replay protection, pod limits | `8-81-*`, `8-83-*`, `7-75-004` | first pairing is trust-on-first-use without OOB code; flash not read-protected on bench; `security/` owns the threat model |
| H8 | Heat / material degradation of the drug | charging heat, unsuitable materials | loss of insulin effect | 4 | open | charge only undocked; temperature channel; **drug and materials evidence is the manufacturer's (water only here)** | `B-B0-*`, `A-A0-003` | out of scope for the project |
| H9 | Pod not docked / pod left on charger | forward steps while off the cannula | no delivery to patient, fluid leakage | 3 | open | dock hall gate (hardware), alarm and report | `1-07-003/004/006`, `2-21-*` | hall switch about 4 mm early with DRV5032FA |
| H10 | Backflow / siphon / free flow | pressure on housing, head height | uncontrolled delivery | 4 | open | self-locking spindle, duckbill, stadium piston | `6-60-008` | no free-flow test yet (`../STANDARDS-MATRIX.md` s3) |
| H11 | Undetected degradation of a protection element | stuck gate, dead watchdog, dead sensor | H1 or H2 with protection silently lost | 5 | open | POST-S/POST-A proofs, rotating disarm, health = UNKNOWN until proven | all `L` codes of layers 1 and 4 | design only (WP-3) |
| H12 | Diagnostic false positive stops therapy | threshold too tight | needless suspension, hyperglycaemia | 3 | open | thresholds with margin, escalation only on repetition, 72 h nominal soak | W/F codes | tests planned |
| H13 | Diagnostics wrong or lost | log corruption, unknown code | wrong action by user | 3 | open | CRC, unknown = fault, catalogue drift check | `7-7C-*`, `9-95-*` | |

Additional hazards a manufacturer must add (not in the repository today): reusable-path contamination and reprocessing; third-party cannula combination failure (needle length, septum leak); adhesive/skin reactions (patient contact materials); battery thermal runaway; software update failure; data privacy; supply chain (counterfeit components, no component traceability for bench builds).

## 2. Sources of hazard identified in the simulation

`../../mechanical/sim/REPORT.md` findings feed H1/H2/H4/H10: thrust (1.1 to 1.6), carriage tongue (4.4 to 4.6), backlash after draw (2.9), prime volume and dead layer (5.1, 5.2), occlusion stored volume (5.4), duckbill bypass (REPORT change 10), stack-ups (3.6 to 3.8), snap arms (4.1, 4.2).

## 3. Hardware FMEA

The electronics FMEA in the format of `../../docs/06-diagnostics.md` 3.6 (every "protection lost" mode has a code and a test) is work package WP-7 and **not done**. Rev A has six single hardware faults that can still reach a hazard (`../../docs/v010/ARCHITECTURE.md` section 0).
