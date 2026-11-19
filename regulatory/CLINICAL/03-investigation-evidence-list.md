# 03 What a pre-market clinical investigation would need: evidence list (to be designed by the sponsor)

> Test project, never used on a person. **No study protocol, no procedure for human use and no inclusion criteria are written here.** This is a list of evidence a sponsor must have ready before a regulator or ethics committee would consider a first-in-human investigation, and which parts this open project can supply (non-clinical only, water only).

## 1. Regulatory framework (for orientation)

EU: MDR Art. 62 and Annex XV (clinical investigation, ISO 14155:2020 good clinical practice), ethics committee, competent authority authorisation, insurance, EUDAMED registration. US: IDE (21 CFR 812) for significant-risk studies, IRB, 21 CFR 50/56. **Sponsor, investigators, sites, CRO: to be defined by the sponsor.**

## 2. Evidence the sponsor needs before human use

| Evidence | Purpose | State in repo | Who produces |
|---|---|---|---|
| Frozen design and device master record | what is being tested | Rev A bench split only | sponsor |
| Risk management file with accepted residual risk for the investigational device | ethics and authority review | `../RISK/` (draft, no acceptance) | sponsor |
| Complete non-clinical verification: electrical safety, EMC, 60601-2-24 essential performance, battery, mechanical, software verification, hazard traceability | safety of the investigational device | design-stage host tests and simulation only | sponsor with accredited labs |
| Biological evaluation (ISO 10993) for all patient-contacting and drug-contacting parts, drug compatibility and stability with the intended drug | safety | **none; never produced by this project (water only)** | sponsor |
| Software documentation (class C) and cybersecurity documentation | safety | `../SOFTWARE/`, `../CYBERSECURITY/` (drafts) | sponsor |
| Usability engineering file: formative results, use-related risk analysis, summative evaluation for the investigational device and labelling | use safety | plan and known use errors only | sponsor |
| Investigator's brochure and instructions for the investigation | | not written (not in this project) | sponsor |
| Interoperability and controller/CGM compatibility evidence | system safety | protocol and tests only | sponsor |
| Quality system evidence (ISO 13485) for manufacture of investigational devices, traceability | | none | sponsor |
| Insurance, ethics approvals, regulatory authorisation | | | sponsor |
| Monitoring, data management, statistical analysis plan, safety reporting plan, stopping rules | GCP | | sponsor / CRO |
| Clinical endpoints and sample size justification | | none | sponsor with clinicians and statisticians |

## 3. What the open project can still supply (non-clinical)

Design history and requirements; hazard analysis and trace; simulation and water-bench evidence; open protocol specification and test vectors; the shared fault catalogue; the pre-built verification procedures (`../../docs/06-diagnostics.md` 6.3, `../../docs/02-safety.md` section 3). All of it is evidence input for the sponsor's decision; none of it supports use on a person by itself.

## 4. Open design questions that change the investigation (sponsor decisions)

Single-patient reuse and reprocessing of the fluid path; refill by user versus pre-filled; which controller and CGM; which cannula; hardware dose limit (HW-A/HW-B); audible alarm; wear time per pod; two-pod handover workflow in the field. Each affects both risk and endpoints.
