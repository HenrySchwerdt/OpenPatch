# 01 Risk management plan (ISO 14971:2019, with ISO/TR 24971:2020)

> Test project, not a medical device; never worn; water only. The plan is a **draft the legal manufacturer adopts and approves**. Acceptance criteria below are examples, not decisions.

## 1. Scope

The OpenPatch pump system as a concept: pod (mechanics, electronics, firmware), controller application, interface to a third-party cannula and to a third-party algorithm/CGM. Life-cycle phases: design, manufacture, transport/storage, use, refill (draw), swap of pods, charging, update, decommissioning. Intended use and users: **to be defined by the legal manufacturer** (`../TECHNICAL-FILE/01-device-description.md`).

## 2. Responsibilities

Risk management file owner, reviewers (independent of the designer), approval authority: **legal manufacturer**. In the open project: hazard list owners are the maintainers (`docs/02-safety.md`), changes by pull request (`../LIVING-PROCESS.md`).

## 3. Process as implemented in the repository

| ISO 14971 step | Where |
|---|---|
| Intended use and foreseeable misuse | placeholder; use errors in `../USABILITY/02-known-use-errors.md` |
| Hazard identification | `docs/02-safety.md` H1 to H10; proposed H11 to H13 in `docs/06-diagnostics.md` 1.2; hardware FMEA slot `06-diagnostics.md` 3.6 (not done) |
| Risk estimation | `02-hazard-analysis.md` (severity proposed, probability placeholders) |
| Risk control | spec §7, §7a; hardware interlock; firmware limits; diagnostic codes; labelling by the manufacturer |
| Verification of controls | `TRACE.md` (generated), host tests, simulation, bench plan |
| Residual risk and benefit-risk | `04-residual-risk-and-benefit-risk.md` |
| Risk management review | before release (`../SOFTWARE/07-release-checklist.md`); manufacturer's review |
| Production and post-production | `../TECHNICAL-FILE/07-pms-plan.md`; shared fault catalogue |

## 4. Rules of the project that act as risk policy

1. Safety limits (spec §7) are never relaxed silently; relaxation needs an entry in `docs/STATUS.md`.
2. The hardware interlock stays in every revision (CLAUDE.md); no delivery with a degraded protection layer (spec §7a).
3. Adding a failure mode requires a catalogue row with hazard link and test.
4. No unknown state is "OK": an unproven protection element is UNKNOWN, never green.
5. The project never proceeds to use on a person; risk estimates here concern bench engineering.

## 5. Severity scale (proposal; manufacturer to adopt)

| Level | Name | Description (insulin delivery context) |
|---|---|---|
| 1 | Negligible | inconvenience, no harm |
| 2 | Minor | temporary discomfort or minor hyper/hypoglycaemia needing no medical help |
| 3 | Serious | hypo-/hyperglycaemia requiring assistance of others or medical intervention, hospitalisation |
| 4 | Critical | severe hypoglycaemia with loss of consciousness/seizure, diabetic ketoacidosis, permanent impairment |
| 5 | Catastrophic | death |

## 6. Probability scale (proposal; per year of use, to be quantified by the manufacturer)

1 improbable, 2 remote, 3 occasional, 4 probable, 5 frequent. Software failure probability is not estimated numerically; software-caused hazardous situations are assessed by severity and by the strength and independence of controls (IEC 62304 4.3 / ISO/TR 24971).

## 7. Acceptability matrix

See `03-acceptability-matrix.md`. Overall residual risk and benefit-risk: `04-residual-risk-and-benefit-risk.md`.

## 8. Verification of implementation of controls and of effectiveness

Implementation: `TRACE.md` shows control targets exist and tests exist. Effectiveness: bench and laboratory evidence (water only here), clinical evidence (manufacturer). Without hardware measurements, effectiveness of hardware controls is **unverified**.

## 9. Production and post-production information

Sources, thresholds and feedback loop: `../TECHNICAL-FILE/07-pms-plan.md`.
