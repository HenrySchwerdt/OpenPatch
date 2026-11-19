# Technical file skeleton (MDR Annex II + III, FDA eSTAR order)

> **Test project, not a medical device; never worn, never filled with insulin or any drug (water only).** This skeleton is filled with what the repository provides. Every statement of intended purpose, claim, labelling or clinical performance is **"to be defined by the legal manufacturer"**. Version of this file set: **tf-0.1.0-beta** (see `../LIVING-PROCESS.md` for versioning).

| MDR Annex II section | File | eSTAR section (FDA, 510(k) / De Novo) | Filled from |
|---|---|---|---|
| 1 Device description and specification, variants, accessories | `01-device-description.md` | Device description; Indications for use (placeholder) | spec, docs, mechanical, electronics |
| 1.1(c) Intended purpose, claims | `01-device-description.md` section 2 | Indications for use / 510(k) summary | placeholder |
| Information supplied by the manufacturer (label, IFU) | `02-labelling-and-ifu.md` | Labeling | **placeholder only** |
| 3 Design and manufacturing information | `03-design-and-manufacturing.md` | Device description, Sterility/Reprocessing, Manufacturing | mechanical, electronics, firmware-rs |
| 4 GSPR (Annex I) | `04-gspr-checklist.md` | Performance testing, Standards, Software, Cybersecurity, Human factors | all |
| 5 Benefit-risk and risk management | `05-benefit-risk.md`, `../RISK/` | Risk management | RISK |
| 6 Product verification and validation | `06-verification-validation-index.md` | Performance testing (bench, EMC, electrical safety, software, human factors, clinical) | tests, sim, bench plan |
| Annex III Post-market surveillance | `07-pms-plan.md` | Post-market (not part of eSTAR; MDR reporting plan) | template |
| Figures | `08-figures.md` (index `../figures/INDEX.md`) | all | `../tools/collect_figures.py` |
| eSTAR order | `09-estar-map.md` | | |
| Software documentation (IEC 62304) | `../SOFTWARE/` | Software/Firmware | |
| Cybersecurity documentation | `../CYBERSECURITY/` | Cybersecurity | `../security/` (planned) |
| Usability engineering file | `../USABILITY/` | Human factors | |
| Clinical evaluation | `../CLINICAL/` | Clinical | |

Status vocabulary used in this folder: **HAVE** (draft evidence exists), **SIM** (simulation or host test only), **BENCH** (needs bench work, water only), **LAB** (accredited laboratory), **CLIN** (human evidence, never this project), **LM** (legal manufacturer, incl. everything needing a drug).
