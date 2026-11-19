# 07 Post-market surveillance plan template (MDR Art. 83 to 86, Annex III; FDA 21 CFR 803/806/820)

> Template for a **future legal manufacturer**. This project has no marketed device, no users and no post-market data; the pump is never used on a person.

## 1. Scope and responsibilities

| Item | Content |
|---|---|
| Devices covered | all variants and software versions placed on the market (to be defined) |
| Responsible person (PRRC), PMS owner | to be defined by the legal manufacturer |
| Classes and reports | EU IIb: PMS plan, **PSUR (annual for IIb, to verify)**, PMCF plan and evaluation report; US: MDR reports, complaint files |

## 2. Data sources (Annex III 1.1)

Complaints and service returns; **device fault logs and diagnostic codes** (pod fault log, `GetFaultLog`; catalogue `../../docs/06-diagnostics.md`), with the shared fault catalogue obligation from `../../COMMERCIAL-LICENSE.md` §4 (post-market fault reporting into the shared catalogue); vigilance and field safety notices of similar devices; literature; registries; cybersecurity vulnerability reports (`../CYBERSECURITY/`); controller/CGM interoperability field data; user feedback; PMCF studies.

## 3. Methods and indicators

| Indicator | Source | Threshold (set by manufacturer) |
|---|---|---|
| Over/under-delivery events | complaints, `7-70-*` and `5-53-*` codes | to be defined |
| Occlusion alarms and time to alarm | fault log | |
| Interlock/proof failures (latched codes L) | fault log | any occurrence reviewed |
| Unexpected resets (`7-74-002`) | fault log | |
| Wear-limit and swap failures | app and pod logs | |
| Alert acknowledgement and alarm-not-heard reports (`1-0C-002`) | app | |
| Security events | vulnerability intake | per policy |

Trend reporting (Art. 88): statistically significant increase of non-serious incidents or expected undesirable side-effects.

## 4. Vigilance and field actions

Serious incident reporting timelines (EU Art. 87; US 21 CFR 803), FSCA, corrections and removals (Part 806), recall decision tree: manufacturer procedures, not defined here.

## 5. Feedback into design

PMS results update: hazard analysis (`../RISK/`), catalogue rows (rule: "adding a failure mode requires a catalogue row with hazard link and test", spec §7a), SOUP anomaly list (`../SOFTWARE/SOUP.md`), usability file, clinical evaluation, benefit-risk (`05-benefit-risk.md`).

## 6. PMCF plan (Annex XIV Part B)

Structure only; methods and objectives to be defined by the manufacturer (`../CLINICAL/`).
