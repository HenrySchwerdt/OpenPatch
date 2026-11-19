# Regulatory roadmap: what approval needs, per market

> **OpenPatch is a test project and NOT a medical device. It must never be worn or used with insulin on a person** (see `../DISCLAIMER.md`). This folder prepares evidence and structure so that a future **legal manufacturer** could use the repository as the basis of a regulatory submission. It is not regulatory advice, contains no patient labelling and no instructions for use on a human, and nothing in it states or implies that the device is approved, cleared or safe for use on a person.
>
> **WATER ONLY (project decision 2026-11-19):** this project never fills the pump with insulin or any other drug, not even into containers. Everything that needs a drug (drug compatibility, insulin stability, biocompatibility with insulin, E&L with the drug, any test with real insulin) is listed here only as **evidence that a future legal manufacturer must generate under its own responsibility**; this project never plans or runs such tests. Bench evidence here is water-based (viscosity of U100 insulin is water-like, about 1 mPa s, as noted in `../docs/02-safety.md` section 3).
>
> Status: v0.1 (2026-11-19). Facts were checked on the web on 2026-11-19; each is cited in "Sources" (end of this file). Items marked **[VERIFY]** could not be confirmed from a primary source and must be checked by the legal manufacturer's regulatory affairs staff. Money and time figures are **[ESTIMATE]**: rough orders of magnitude from general industry knowledge, not quotes.

## 0. The short version

1. **Classification (expected, to be confirmed with a notified body / FDA Pre-Sub):**

| Market | Pump (pod) | Basis | Pathway |
|---|---|---|---|
| EU | **Class IIb** (active device administering a medicinal product in a potentially hazardous manner) | MDR 2017/745 Annex VIII Rule 12; software that drives the device takes the device class (Annex VIII 3.3) | Notified body, Annex IX (QMS + technical documentation), clinical evaluation consultation procedure (Art. 54) applies to IIb Rule 12 devices **[VERIFY exemptions]** |
| US | **Class II**, 21 CFR 880.5730 *alternate controller enabled (ACE) infusion pump*, product code **QFG** | special controls in the regulation | **510(k)** (ACE pumps are an established type) or De Novo if no suitable predicate; cybersecurity per FD&C Act 524B |
| UK | Class IIb equivalent | UK MDR 2002 as amended | UKCA via UK Approved Body, or CE accepted during the transition (to 30 June 2028 for MDD, 30 June 2030 for MDR certificates; extension is under consultation) **[VERIFY]** |
| Canada | Class III **[VERIFY]** | MDR SOR/98-282 Schedule 1 | Medical Device Licence with an MDSAP certificate |
| Australia | Class IIb **[VERIFY]** | TGA classification rules | ARTG inclusion, Australian sponsor, conformity assessment evidence |
| Japan | Class III **[VERIFY]** | PMD Act | Marketing Authorization Holder, PMDA review, QMS conformity |

   A closed-loop system (pump + CGM + algorithm, for example Trio) is a **different, higher-risk system**: in the EU the integrated closed loop falls under Rule 22 (Class III); in the US the controller is an *interoperable automated glycemic controller* (21 CFR 862.1356) and the CGM an *iCGM* (21 CFR 862.1355). The pump manufacturer proves interoperability; it does not become the controller manufacturer **[VERIFY product codes and class]**.

2. **What the open project can produce now:** design history, requirements, hazard analysis, traceability, SOUP list, software classification and plans, simulation evidence, test procedures, standards mapping, GSPR checklist, figures, templates. About 60 to 70 % of the *documents* of a technical file can be drafted from the repository; they are drafts of **design-stage evidence**, not verified results. See `TECHNICAL-FILE/`, `SOFTWARE/`, `RISK/`.
3. **What cannot be produced by an open project:** a quality management system run by a legal entity (ISO 13485), a notified-body certificate, accredited-lab test reports, human-factors validation, clinical evidence, post-market system, insurance, and the manufacturer's name on the label.
4. **Largest technical gaps before any verification can start** (details in section 6): a *frozen* design (Rev A is a bench split; the integrated Rev B does not exist), simulation FAILs on drive thrust, dose accuracy and occlusion volume (`../mechanical/sim/REPORT.md`), a **reusable fluid path** with no cleaning/reprocessing concept, no air-in-line detection, no audible alarm in the pod, and **no hardware measurements of any safety function**.

## 1. EU: MDR 2017/745

| Topic | What it requires | Our position |
|---|---|---|
| Classification | Annex VIII Rule 12: active devices that administer/remove medicinal products are IIa, **IIb if potentially hazardous** (substance, body part, mode of application). Insulin delivered subcutaneously by an electronic pump is the textbook IIb case. Software that drives or influences a device takes the device's class (Annex VIII 3.3). MDCG 2021-24 gives the guidance; **Revision 1 was published 2026-04-20** (Rule 12 examples reviewed) | Expect IIb. App `OpenPatchKit` is part of the pump system (accessory/driving software). Algorithm apps are separate manufacturers' devices |
| Conformity route | Annex IX Chapter I+III (full QMS + technical documentation assessment) is the usual route; alternative Annex X (type examination) + Annex XI | Needs a legal manufacturer with ISO 13485 QMS |
| Notified body | Mandatory for IIb. 13 to 18 months for QMS + product certification is the typical reported duration **[ESTIMATE from NB surveys, see Sources]**. Capacity is limited; apply early | Choose an NB with active-infusion experience |
| Clinical evaluation | Art. 61 + Annex XIV. For IIb active devices intended to administer medicinal products, the **clinical evaluation consultation procedure (Art. 54)** by an expert panel normally applies **[VERIFY exemptions]**. Equivalence (Art. 61(4)/(5)) needs full access to the other manufacturer's technical documentation, which is not available for a third-party pump (see `CLINICAL/`) | Needs a clinical investigation plan by the sponsor; none is written here |
| PRRC | Art. 15: a person responsible for regulatory compliance (qualified) | Legal manufacturer |
| Authorised representative | Art. 11 if the manufacturer is outside the EU | Depends on the manufacturer |
| UDI / EUDAMED | Art. 27, Annex VI: Basic UDI-DI, UDI-DI, UDI-PI on label and in the database. EUDAMED is being phased in module by module (Reg. (EU) 2024/1860); the first modules (actor, UDI/device, certificates, market surveillance) are reported as mandatory from 2026 **[VERIFY dates]** | Manufacturer registers, obtains SRN |
| PMS | Art. 83 to 86, Annex III: PMS plan, **PSUR for IIb at least annually [VERIFY]**, PMCF (Annex XIV Part B), trend reporting Art. 88, vigilance Art. 87 (serious incident 15 days, 2 days for serious public health threat, 10 days for death/unanticipated serious deterioration) | Template in `TECHNICAL-FILE/07-pms-plan.md`; the shared fault catalogue (`../docs/06-diagnostics.md`) is a design input |
| SSCP | Art. 32 applies to class III and implantable devices only | Not required for IIb alone |
| Standards | Presumption of conformity via harmonised standards listed under Implementing Decision (EU) 2021/1182 as amended (latest decisions 2025/2078 and 2026/1231 reported; which editions of EN 60601-2-24, EN 62304, EN ISO 10993-1:2025 are cited must be read from the Official Journal) **[VERIFY]** | `STANDARDS-MATRIX.md` |
| GSPR | Annex I general safety and performance requirements | `TECHNICAL-FILE/04-gspr-checklist.md` |
| Technical documentation | Annex II (+ Annex III for PMS) | `TECHNICAL-FILE/` |
| Radio | **RED 2014/53/EU** applies in addition (BLE 2.4 GHz): Art. 3(1)(b) EMC and 3(2) spectrum, harmonised standards EN 300 328, EN 301 489-1/-17, RF exposure EN 62479 (or EN 50663). RED cybersecurity requirements (Delegated Reg. (EU) 2022/30, EN 18031-x, from 1 Aug 2025) are reported **not to apply to MDR devices [VERIFY]** | covered by 60601-1-2 + RED test report from an accredited lab |
| Battery | Li-Po cell: IEC 62133-2, UN 38.3 for transport; EU Battery Regulation 2023/1542 (portable battery obligations: labelling, replaceability, due diligence; **scope and exemptions for batteries inside medical devices to be checked [VERIFY]**) | `STANDARDS-MATRIX.md` |
| WEEE / RoHS / REACH | WEEE 2012/19/EU registration per country; RoHS 2011/65/EU (medical devices in scope; CE declaration covers it); REACH SVHC declaration | Manufacturer |
| Data protection | GDPR for app data (health data); MDR Annex I 17.2/17.4 cybersecurity | `CYBERSECURITY/` |
| Combination aspects | The pump is not an integral drug-device combination (insulin is not supplied with it), so Art. 117 does not apply, but **insulin compatibility and stability claims** (named insulin products, 48 h in the reservoir) must be supported by data | **legal manufacturer only** (drug testing is out of scope of this project, water only) |
| Third-party cannula | The Insight Flex head is Roche's CE-marked device. A pump that pierces it is a combination Roche has not validated; the manufacturer needs its own adapter/infusion-set conformity (see `../COMMERCIAL-LICENSE.md` section 1a) | a decision for the manufacturer: own infusion set, or contract with the cannula maker |

## 2. US: FDA

| Topic | Facts | Our position |
|---|---|---|
| Regulation / code | **21 CFR 880.5730, alternate controller enabled infusion pump (ACE pump), Class II (special controls), product code QFG** (established by final order 87 FR 6424, 2022-02-04). The regulation says the pump is designed to communicate with external devices (such as automated drug dosing systems) so that delivery commands can be received, executed and confirmed | exactly the OpenPatch concept (pod + external controller) |
| Special controls (880.5730(b), paraphrased) | design verification and validation: delivery accuracy under foreseeable conditions, occlusion and air-in-line detection, drug compatibility and stability, biocompatibility, reliability over use life, electrical safety / EMC / wireless safety; **risk controls and a traceability analysis showing all hazards are controlled**; **validated interface specifications** (secure pairing, secure data transmission, state sharing such as battery and reservoir level, safe operation when out-of-bounds data arrive, process for sharing and validating the protocol); **loss-of-communication measures** (safe pre-programmed rate); **critical event records**; **human factors study**; labelling content (compatible drugs, basal/bolus ranges and increments, accuracy data, occlusion alarm performance, wireless quality of service, reprocessing for multi-patient pumps) | mapping in section 2.1 below |
| Pathway | **510(k)** is expected if a legally marketed ACE pump is a suitable predicate; **De Novo** if the technology (for example a reusable patch pump with detachable fluid path) raises new questions of safety and effectiveness. Pre-Submission (Q-Sub) strongly recommended **[ESTIMATE of fit; FDA decides]** | |
| Interoperability | The pump claims compatibility with named controllers (iAGC, 21 CFR 862.1356) and CGMs (iCGM, 21 CFR 862.1355). Trio is an open-source community project and is **not an FDA-cleared controller**; a manufacturer would partner with a cleared controller or its own **[VERIFY]** | big open decision |
| Format | **eSTAR** electronic submission template (mandatory for 510(k); De Novo eSTAR also required, **VERIFY date**) | `TECHNICAL-FILE/09-estar-map.md` |
| Cybersecurity | FD&C Act **section 524B**: a "cyber device" (software, ability to connect) must have a plan to monitor, identify and address post-market vulnerabilities, processes to provide patches, **SBOM**, and other requirements. FDA guidance *Cybersecurity in Medical Devices: Quality System Considerations and Content of Premarket Submissions* (final June 2025; a revision aligned with QMSR is reported for February 2026 **[VERIFY current version]**) | `CYBERSECURITY/` structure; content owned by `../security/` (planned) |
| Quality system | **QMSR** (amended 21 CFR 820) effective **2026-02-02**; incorporates ISO 13485:2016 by reference; FDA-specific parts remain | ISO 13485 QMS needed in both markets |
| Registration and listing | 21 CFR 807, establishment registration (fee reported FY2027 US$13,785, no small business discount) **[VERIFY]** | manufacturer |
| User fees (FY2027, Oct 2026 to Sep 2027, as reported by third parties **[VERIFY on fda.gov]**) | 510(k) US$28,653 (small business US$7,163); De Novo US$191,020 (small business US$47,755) | |
| UDI | 21 CFR Part 830, GUDID | manufacturer |
| Post-market | MDR reporting 21 CFR 803 (death/serious injury within 30 days, 5 days for events needing remedial action), corrections and removals Part 806, complaint handling | manufacturer; PMS plan template |
| Human factors | FDA human factors guidance; summative validation per user group is a special control | `USABILITY/` |
| Clinical | A 510(k) for an ACE pump is typically supported by bench, software, cybersecurity, human factors and interoperability evidence; a clinical study is **not automatically required** but depends on the predicate and the Pre-Sub outcome. A human study of an insulin pump would be a significant-risk device study under an **IDE (21 CFR 812)** | no protocol written here |

### 2.1 880.5730 special controls: where the repository stands

| Special control (summary) | Repository evidence | Status |
|---|---|---|
| Delivery accuracy under foreseeable conditions | `../docs/02-safety.md` s3 step 1; `../mechanical/sim/REPORT.md` section 2 (Monte Carlo, FAILs for 1 U) | simulation only; needs bench + accredited lab |
| Occlusion and air-in-line detection | encoder/current occlusion in `firmware-rs/openpatch-core/src/safety.rs`; sim 5.4 FAIL (2.9 to 5.2 U undelivered at alarm); **no air-in-line sensing** | gap |
| Drug compatibility and stability | none, and none will be produced here (water only) | **legal manufacturer only** |
| Biocompatibility of patient-contacting parts | wetted-path material choice kept as design preparation (spec 3a); no tests | needs accredited lab, legal manufacturer only |
| Reliability over use life | 72 h endurance plan (`02-safety` s3 step 3) | needs bench |
| Electrical safety, EMC, wireless | none yet | needs accredited lab; Rev B pod must exist |
| Traceability of hazards | `RISK/TRACE.md` (generated by `tools/trace.py`) | have (design stage) |
| Validated interface spec (secure pairing, state sharing) | `../docs/04-protocol.md`, test vectors, host tests in Rust and Swift | have (design stage); security review by `security/` |
| Loss of communication | spec 7, tests `de_temp_basal_falls_back_30min_after_comm_loss` | have (host tests) |
| Critical event records | event log (`firmware-rs/openpatch-core/src/log.rs`), planned fault log (`docs/06-diagnostics.md`) | partly |
| Human factors | `USABILITY/` plan | plan only |
| Labelling | placeholder (`TECHNICAL-FILE/02-labelling-and-ifu.md`) | manufacturer |

## 3. United Kingdom (MHRA)

- Regulated under the Medical Devices Regulations 2002 (as amended). **UKCA** marking via a UK Approved Body; a **UK Responsible Person** is required for manufacturers outside the UK; devices must be registered with MHRA.
- CE-marked devices remain accepted in Great Britain for a transition period: reported **until 30 June 2028 (MDD) or 30 June 2030 (MDR)**; MHRA has announced a consultation on indefinite CE recognition and on international reliance (using FDA, Health Canada, TGA decisions). Treat as **[VERIFY]**.
- **Post-market surveillance regulations took effect on 16 June 2025** (apply to UKCA and CE-marked devices on the GB market).
- Practical route for a first manufacturer: EU MDR certificate first, then use the CE recognition or reliance route.

## 4. Canada, Australia, Japan (brief)

| Market | Authority / law | Class (expected) | Requirements to remember |
|---|---|---|---|
| Canada | Health Canada, Medical Devices Regulations SOR/98-282 | Class III **[VERIFY]** | Medical Device Licence (Class II to IV) needs an **MDSAP** certificate (ISO 13485 + MDSAP); English/French labelling; Health Canada treats **insulin-product/pump compatibility claims as part of indications for use** (regulatory notice) |
| Australia | TGA, Therapeutic Goods (Medical Devices) Regulations 2002 | IIb **[VERIFY]** | ARTG inclusion by an Australian sponsor; conformity assessment evidence (MDSAP or EU MDR certificate accepted to a degree **[VERIFY]**); essential principles; UDI roll-out |
| Japan | MHLW/PMDA, PMD Act | Class III **[VERIFY]** | Marketing Authorization Holder in Japan (or a designated MAH), foreign manufacturer accreditation, QMS ordinance (ISO 13485-aligned), PMDA review or registered certification body, Japanese labelling; local clinical data may be requested |

## 5. Phased plan

Cost and time are **[ESTIMATE]**: orders of magnitude for a first-of-kind small manufacturer, EU+US, not quotes. Costs exclude internal staff and the Rev B redesign.

| Phase | Who | What | Output | Cost | Time |
|---|---|---|---|---|---|
| **0. Open project, now** | maintainers and contributors | requirements, risk file, trace, SOUP, software classification, simulation, bench procedures, standards mapping, GSPR and technical-file skeleton, figure index, this roadmap | `regulatory/`, evidence in git | near zero cash | continuous, see `LIVING-PROCESS.md` |
| **1. Design closure** | open project + first company | fix the simulation FAILs, freeze Rev B (integrated pod, audible alarm, hardware dose limit decision, reusable-path concept), run the bench plan on real hardware (water first), gravimetric accuracy, occlusion, endurance, fault injection B01 to B24 | measured design verification (pre-formal) | EUR 30k to 150k | 6 to 12 months |
| **2. Legal manufacturer + QMS** | a company | ISO 13485 QMS, design controls on top of the repository history, PRRC, supplier controls (PCBA, CNC, printing), regulatory strategy, Pre-Sub with FDA, NB selection | QMS, regulatory plan | EUR 80k to 300k to set up | 6 to 12 months (parallel to 1) |
| **3. Accredited labs** | test houses | IEC 60601-1, -1-2, -1-6, -1-8, -1-11, **-2-24**, RED radio and EMC, IEC 62133-2 and UN 38.3, ISO 10993 set and extractables/leachables for the fluid path, drug (insulin) compatibility and stability **(manufacturer only, never in this project)**, IP rating, drop and mechanical, ageing/shelf life, sterilisation validation if the cannula interface must be sterile, penetration test | test reports | EUR 250k to 800k | 9 to 15 months |
| **4. Human factors** | manufacturer + HF lab | formative then summative validation per user group; *no part of this repository writes on-body tasks* | HF report (62366-1, FDA HF guidance) | EUR 100k to 300k | 6 to 9 months |
| **5. Clinical** | sponsor with clinical CRO | clinical evaluation, probably a clinical investigation (EU: Art. 62; US: IDE if a study is needed), interoperability studies with a controller and CGM | clinical evaluation report | EUR 1M to 5M | 2 to 4 years |
| **6. Submission and review** | manufacturer | EU: NB audit and technical documentation review (13 to 18 months typical), US: 510(k) 90 FDA review days nominal, often 4 to 8 months elapsed **[ESTIMATE]**; fees: NB EUR 50k to 200k, FDA see section 2 | CE certificate, 510(k) clearance | included in section 0 totals below | 12 to 24 months |
| **7. Market and PMS** | manufacturer | PMS plan, PSUR, PMCF, vigilance, annual audits, cybersecurity monitoring | ongoing | EUR 150k to 500k per year | continuous |

Rough total for a first EU + US approval: **EUR 3M to 10M and 4 to 6 years [ESTIMATE]**, dominated by phase 5 and by the redesign needed to close phase 1. This is why the commercial licence (`../COMMERCIAL-LICENSE.md` section 3a) lets the first funding company recoup its investment from later licensees (verified, audited, with a capped return), and why the 5 % levy funds shared evidence.

## 6. Top gaps ranked by cost and time

| # | Gap | Why it matters | Cost / time [ESTIMATE] | Who |
|---|---|---|---|---|
| 1 | **Clinical evidence** (no equivalence route for a new open device) | MDR Art. 61, Art. 54; FDA interoperability and possibly IDE | EUR 1M to 5M, 2 to 4 y | sponsor |
| 2 | **Frozen, verified design**: sim FAILs for thrust (1.1 to 1.6), dose accuracy at 1 U (2.4), occlusion volume (5.4), dead layer air (5.2), stack-ups (3.6 to 3.8); gear ratio mismatch open (`../docs/STATUS.md`); no measurement of any safety function on hardware | all lab testing needs a frozen design | EUR 30k to 150k, 6 to 12 months | open project + company |
| 3 | **Reusable fluid path / reprocessing and drug-contact biocompatibility** (pod is refilled for 48 h cycles; ISO 10993-1:2025 set, E&L, cleaning validation, insulin stability; **all manufacturer-generated, no drug is ever used in this project**) | not covered anywhere in the repository; likely the hardest non-clinical item | EUR 100k to 400k, 9 to 15 months | lab + manufacturer |
| 4 | **Legal manufacturer + ISO 13485 QMS + notified body** | no submission without them | EUR 80k to 300k + NB, 12 to 24 months | company |
| 5 | **IEC 60601-1 / -1-2 / -1-11 / -2-24 / -1-8 testing** (needs a Rev B pod with battery, audible alarm, sealed housing) | basic safety and essential performance | EUR 150k to 500k, 6 to 12 months | accredited lab |
| 6 | **Human factors** (dock, refill draw mode, two-pod swap, alarms) | FDA special control, IEC 62366-1 | EUR 100k to 300k, 6 to 9 months | manufacturer + HF lab |
| 7 | **Controller and CGM interoperability / third-party cannula** | Trio is not cleared; Insight Flex is Roche's device | partnership or own infusion set; EUR 100k+ | company |
| 8 | **Software class C evidence**: SOUP anomaly review (Nordic binary libraries), independent verification, tool pins | IEC 62304 | EUR 50k to 150k | company |
| 9 | **Hardware dose bound** (HW-A/HW-B) and **air-in-line detection** | 880.5730 special control; 60601-2-24 | design effort in Rev B | open project |
| 10 | **Cybersecurity** pen test, vulnerability process, SBOM, threat model reviews | FD&C 524B, MDR Annex I 17 | EUR 20k to 60k + process | `security/` + manufacturer |

## 7. What the open project can still do for free (ordered by leverage)

1. Close the simulation FAILs in `../mechanical/sim/REPORT.md` (tongue thickness, seal friction, dead layer, backlash take-up) and re-run `python3 mechanical/sim/run_all.py`.
2. Run the bench procedures B01 to B24 and `docs/02-safety.md` section 3 on the bench controller with water; record results in `../firmware-rs/docs/bench-testing.md`. Every executed procedure turns a `plan` row in `RISK/trace-links.csv` into evidence.
3. Write the missing IEC 60601-2-24 style bench tests listed in `STANDARDS-MATRIX.md` section 3 (free flow, air, bolus after occlusion release, trumpet curves).
4. Keep `tools/trace.py`, `tools/soup.py` and `tools/collect_figures.py` green in CI (`LIVING-PROCESS.md`).
5. Prepare the Pre-Sub question list for FDA and the NB briefing (what we know, what we do not).

## Sources (retrieved 2026-11-19)

- 21 CFR 880.5730 text (Cornell LII): https://www.law.cornell.edu/cfr/text/21/880.5730 ; final order 87 FR 6424: https://www.govinfo.gov/content/pkg/FR-2022-02-04/pdf/2022-02369.pdf ; product code QFG listing (third party): https://fda.innolitics.com/productcode/QFG
- MDCG 2021-24 and Rev. 1 (published 2026-04-20, per secondary source): https://openregulatory.com/mdcg/mdcg-2021-24 , https://mdxcro.com/?p=11509 . Rule 12 and Rule 22 wording is from MDR Annex VIII (not re-fetched; **[VERIFY]**).
- FDA QMSR effective 2026-02-02, ISO 13485:2016 incorporated: https://www.fda.gov/quality-systems-regulation
- FDA premarket cybersecurity guidance (June 2025; revision reported February 2026): https://www.hhs.gov/guidance/sites/default/files/hhs-guidance-documents/FDA/GUI00001825-final-PremarketCybersecurity-2025.pdf , https://www.dlapiper.com/en-jp/insights/publications/2026/02/fda-issues-revised-cybersecurity-premarket-submission-guidance
- FDA user fees FY2026/FY2027 (third-party summaries): https://www.raps.org/resource/fda-unveils-fy-2026-user-fee-rates.html , https://www.pureglobal.com/news/fda-fy-2027-medical-device-user-fees
- UK MHRA PMS regulations 2025-06-16 and CE recognition: https://www.gov.uk/government/news/first-major-overhaul-of-medical-device-regulation-comes-into-force-across-great-britain , https://www.gov.uk/government/publications/implementation-of-the-future-regulation-of-medical-devices
- IEC 60601-2-24:2012 table of contents and scope (VDE preview): https://assets.vde-verlag.de/iec-normen/preview-pdf/info_iec60601-2-24%7Bed2.0%7Db.pdf
- EU harmonised standards decisions: https://www.pureglobal.com/news/eu-commission-implementing-decision-eu-2025-2078-on-harmonised-standards , https://medenvoyglobal.com/?p=27306
- RED delegated regulation 2022/30 and MDR exclusion: https://www.gov.uk/government/publications/radio-equipment-regulations-2017/regulation-eu-202230-factsheet
- ISO 10993-1:2025 (edition 6, November 2025): https://www.iso.org/standard/10993-1
- Notified body timelines: https://meddeviceguide.com/blog/eu-mdr-notified-body-capacity-crisis-2026-2027-guide , https://www.gmp-compliance.org/gmp-news/survey-results-from-team-notified-body-on-the-mdr-and-ivdr
- Health Canada insulin-pump compatibility claims notice: https://www.canada.ca/en/health-canada/services/drugs-health-products/medical-devices/activities/announcements/notice-insulin-product-pump-compatibility-claims.html
- Not confirmed from primary sources (all **[VERIFY]**): Canada, Australia and Japan classes; EUDAMED module dates; PSUR interval; Battery Regulation scope for medical devices; De Novo eSTAR date; current guidance version for FDA cybersecurity.
