# 04 GSPR checklist (MDR Annex I), per requirement: evidence and gap

> Test project, not a medical device. "Evidence" means design-stage evidence in this repository (host tests, simulation, documents); **no hardware measurement of any safety function exists**. Status codes: HAVE, SIM, BENCH, LAB, CLIN, LM (see `README.md`). Requirement text is paraphrased; the manufacturer works from the regulation. Update this table in every PR that changes evidence (`../LIVING-PROCESS.md`).

## Chapter I General requirements

| GSPR | Requirement (short) | Applicable | Evidence in repo | Status | Gap / next step |
|---|---|---|---|---|---|
| 1 | Performs as intended by the manufacturer, safe, acceptable benefit-risk | yes | `../RISK/`, spec §7 | SIM | intended purpose and performance claims are the manufacturer's; clinical evidence missing (`../CLINICAL/`) |
| 2 | Reduce risks as far as possible | yes | hazard table `../../docs/02-safety.md`, `../RISK/TRACE.md` | HAVE (draft) | risk acceptance criteria to be set by the manufacturer |
| 3 | Risk management system (plan, hazard identification, estimation, control, residual risk, production feedback) | yes | `../RISK/01-risk-management-plan.md` | HAVE (draft) | probabilities and acceptability by the manufacturer |
| 4 | Risk control: inherent safety first, protection measures, information | yes | hardware interlock (inherent), software limits, diagnostics, `../RISK/` | HAVE (draft) | hierarchy evidence per control in `../RISK/02-hazard-analysis.md` |
| 5 | Reduce use-error risk (ergonomics, user knowledge, environment) | yes | `../USABILITY/` | HAVE (plan) | formative/summative by the manufacturer |
| 6 | Lifetime: safe during the lifetime specified | yes | 48 h wear / 52 h stop (`limits.rs`), endurance plan s3 step 3 | SIM, BENCH | lifetime and reuse count (refill cycles) must be defined and validated |
| 7 | Transport and storage do not impair characteristics | yes | none | LAB, LM | transport/storage tests, packaging |
| 8 | Benefit-risk ratio acceptable | yes | `05-benefit-risk.md` | placeholder | needs clinical data; manufacturer |
| 9 | Devices without intended medical purpose | no | n/a | n/a | |

## Chapter II Requirements regarding design and manufacture

| GSPR | Requirement (short) | Applicable | Evidence in repo | Status | Gap / next step |
|---|---|---|---|---|---|
| 10.1 | Chemical, physical properties: toxicity, flammability, compatibility with materials, tissues, body fluids and **substances** the device is exposed to | yes | material rule spec §3a; mechanical design | LM, LAB | **drug compatibility is manufacturer-only (water only here)**; physical compatibility with water only |
| 10.2 | Minimise risk from contaminants and residues | yes | none | LM, LAB | cleanliness of fluid path, cleaning validation |
| 10.3 | Minimise risk from substances leaking from device | yes | duckbill valve, seals; REPORT recommended change 10 (valve bypass) | SIM | leak tests (water) as bench; E&L is manufacturer-only |
| 10.4 | CMR / endocrine disruptors above 0.1 % w/w | yes | none (BOM review pending) | LM | BOM substance declaration |
| 10.5 | Minimise particles / leachables risk | yes | none | LM, LAB | |
| 10.6 | Intended ingress/egress of substances | yes | outlet needle, septum | SIM | accuracy tests (water) |
| 10.7 | Biocompatibility (ISO 10993) | yes | none | LAB, LM | see `../STANDARDS-MATRIX.md` |
| 10.8 | Ageing, wear, packaging | yes | none | LAB | shelf life, ageing of silicone and printed parts |
| 11.1 to 11.8 | Infection and microbial contamination; sterility; reprocessing | yes | none; reusable pod concept | LM | decide sterility of fluid path and reprocessing; ISO 11135/17665/17664-1 |
| 12 | Devices incorporating a medicinal substance | no | pump does not incorporate insulin | n/a | document the rationale (Art. 117 not triggered) |
| 13 | Materials of biological origin | no | none | n/a | silicone and PP only |
| 14.1 | Compatibility with other devices and equipment (combination) | yes | cannula dock (Insight Flex), controller app (LoopKit/Trio), CGM via controller | SIM | **third-party cannula and controller are unvalidated combinations**; interface specification `../../docs/04-protocol.md`; manufacturer decision |
| 14.2 | Design to remove or reduce: injury (ergonomic), use error, environment (EMI, humidity), contact hazards | yes | `../../mechanical/check.py`, sim REPORT sections 3 and 4 | SIM | tolerance and structural FAILs open (REPORT 3.6 to 3.8, 4.4 to 4.6) |
| 14.3 | Minimise risks of fire/explosion, flammable substances | yes | Li-Po cell protection (PCM) | LAB | IEC 62133-2, UN 38.3, 60601-1 clause 11 |
| 14.4 | Adjustment, calibration, maintenance safe | yes | per-pod calibration, `drive_cal.rs`; no calibration means no delivery (`cal_missing_blocks_delivery`) | HAVE, SIM | service procedures by the manufacturer |
| 14.5 | Interoperability with other devices | yes | protocol spec, test vectors, `PairSwapCoordinator` | HAVE, SIM | validated interface per 880.5730 |
| 14.6 | Protection against unauthorised use | yes | pairing button window, X25519, AES-CCM, replay (`../../docs/04-protocol.md`) | HAVE, SIM | `../../security/` review; production APPROTECT |
| 14.7 | Waste disposal, safe decommissioning | yes | none | LM | |
| 15.1, 15.2 | Measuring function accuracy | yes (delivered volume is a measured/controlled quantity) | sim section 2, safety plan s3 | SIM, BENCH | accuracy claims by the manufacturer |
| 16 | Radiation protection (non-ionising) | yes (2.4 GHz BLE) | none | LAB | RF exposure EN 62479 / EN 50663 |
| 17.1 | Repeatability, reliability, performance of programmable electronic systems; single-fault conditions | yes | hardware interlock, watchdog, redundant dose limits, fault codes, 343 core tests + 32 differential | HAVE (draft), SIM | single-fault verification on hardware (B07 to B12); FMEA (WP-7) |
| 17.2 | Software developed per state of the art (life cycle, risk, verification) | yes | `../SOFTWARE/`, tests, CI | HAVE (draft) | class C completion; independent review |
| 17.3 | Software running on mobile platforms: minimum IT requirements | yes | `../../ios/INTEGRATION.md` | HAVE (partly) | minimum iOS version and device list by the manufacturer |
| 17.4 | IT security: minimum requirements incl. protection against unauthorised access | yes | `../CYBERSECURITY/`, `../../docs/04-protocol.md` | HAVE (partly), LAB | pen test, SBOM, vulnerability process |
| 18.1 | Single-fault safe | yes | interlock design, `../../docs/06-diagnostics.md` section 1.2 | SIM | hardware-alone coverage is partial (H1 dose inside watchdog window not bounded in Rev A) |
| 18.2 | Power supply, internal power state, alarm when low | yes | battery thresholds, wear timer, `pump_critical_battery_blocks_delivery` | SIM | measurements, Rev B battery |
| 18.3 | External power supply | partly (USB bench power; charger) | bench controller | LAB | |
| 18.4 | Alarm system for conditions that may cause harm | yes | alarm catalogue (`../../docs/06-diagnostics.md`), alerts in `OpenPatchKit` | SIM, LAB | Rev A pod has no buzzer; 60601-1-8 |
| 18.5 | Minimise EMI | yes | none | LAB | 60601-1-2 |
| 18.6 | Protection from electric shock | yes | low voltage battery device | LAB | 60601-1 |
| 18.7 | Protection from mechanical and thermal risks incl. vibration, noise | yes | motor heat (REPORT 1.10); noise unmeasured | SIM, BENCH | temperature of applied part |
| 18.8 | Protection against inadvertent substance leakage into patient | yes | hardware interlock, duckbill, self-locking screw, H1, H10 | SIM | free-flow test missing (`../STANDARDS-MATRIX.md` section 3) |
| 19 | Active implantable devices | no | n/a | n/a | not implanted |
| 20.1 | Mechanical risks: stability, moving parts, vibration | yes | REPORT sections 3 and 4 | SIM | FAILs: tongue stress 4.4, stiffness 4.6, stack-ups 3.6 to 3.8 |
| 20.2 | Risks from vibration | yes | none | LAB | |
| 20.3 | Noise | yes | none | BENCH | |
| 20.4 | Terminals and connectors | yes | FFC/ZIF, JST and PicoBlade plugs (bench only) | SIM | Rev B has no cables |
| 20.5 | Heat and temperature of surfaces (applied part limits) | yes | winding dissipation (REPORT 1.7), no measurement | BENCH, LAB | |
| 21.1 | Energy or substance supply to patient: accuracy and stability of output; protection against inadvertent hazardous output | yes | safety supervisor limits, encoder cross-check, hardware interlock | SIM | accuracy 1 U FAIL in sim; trumpet curves, occlusion and post-occlusion bolus missing |
| 21.2 | Means to prevent/indicate inadequate output where it could be hazardous | yes | occlusion (sim 5.4 FAIL), encoder deviation, under-delivery codes | SIM | alarm volume criterion vs standard; air-in-line missing |
| 22.1 to 22.4 | Lay-person devices: usability, verification by lay users, information | yes | `../USABILITY/` | HAVE (plan) | no lay-user evaluation; manufacturer |

## Chapter III Information supplied with the device

| GSPR | Requirement (short) | Applicable | Evidence | Status | Gap |
|---|---|---|---|---|---|
| 23.1 | General: label and IFU, language, electronic form | yes | placeholder `02-labelling-and-ifu.md` | LM | written by the legal manufacturer |
| 23.2 | Label content (name, manufacturer, UDI, storage, single use / reuse, IP, symbols) | yes | placeholder | LM | |
| 23.3 | Sterile packaging information | depends | none | LM | |
| 23.4 | IFU content (purpose, performance, contraindications, residual risks, warnings, compatible devices, installation, maintenance, reprocessing, alarm information, symbols) | yes | **none by design** | LM | the IFU is the legal manufacturer's; no on-body instructions are written in this project |

## Totals (as of 2026-11-19, tf-0.1.0-beta)

Applicable GSPRs without any evidence: 7, 10.x (drug/chem), 11.x, 16, 18.5, 18.6, 20.2 to 20.5, 23.x. GSPRs with simulation/host-test evidence but no hardware measurement: 1, 14.x, 15, 17.x, 18.1, 18.2, 18.4, 18.8, 20.1, 21.x. See `../RISK/TRACE.md` for the hazard chain.
