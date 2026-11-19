# 09 FDA eSTAR section order mapped to this repository

> eSTAR is the FDA electronic submission template (PDF form). The section list below is the commonly used order for a 510(k)/De Novo; **[VERIFY]** the exact current template version when preparing a submission. Content = what a legal manufacturer would paste or attach; nothing here is a submission.

| eSTAR section | Content | Repository source | Status |
|---|---|---|---|
| Administrative: submitter, contacts, user fee, registration | manufacturer | n/a | LM |
| Classification: product code QFG, 21 CFR 880.5730 | `../ROADMAP.md` section 2 | have | |
| Predicate / reference devices; substantial equivalence discussion (510(k)) | to be defined | none | LM |
| Device description | `01-device-description.md`, figures F01 to F04 | HAVE | |
| Indications for use | **to be defined by the legal manufacturer** | none | LM |
| Labeling (including 880.5730(b)(7) content) | `02-labelling-and-ifu.md` | **placeholder** | LM |
| Reprocessing, sterility, shelf life | decisions open | none | LM |
| Biocompatibility | ISO 10993 programme | none (drug-contact is manufacturer only) | LAB, LM |
| Software / firmware documentation (FDA software guidance, IEC 62304) | `../SOFTWARE/` | HAVE (draft) | |
| Cybersecurity (524B: threat model, SBOM, architecture views, vulnerability plan, testing) | `../CYBERSECURITY/` + `../../security/` | structure; content by `security/` | |
| Interoperability (controller, CGM, protocol specification) | `../../docs/04-protocol.md`, `../../ios/INTEGRATION.md` | HAVE (partly) | |
| EMC, wireless coexistence, electrical, mechanical safety | `../STANDARDS-MATRIX.md` | LAB | |
| Performance testing, bench (accuracy, occlusion, air, free flow, battery, endurance) | `06-verification-validation-index.md`, `../../mechanical/sim/REPORT.md` | SIM; BENCH; LAB | |
| Human factors | `../USABILITY/` | plan | |
| Clinical (if needed) | `../CLINICAL/` | structure | |
| Risk management file, hazard traceability (880.5730(b)(2)) | `../RISK/TRACE.md` | HAVE (draft) | |
| Quality system (QMSR, ISO 13485) | n/a | LM | |
| Truthful and accurate statement, 510(k) summary or De Novo statement | manufacturer | LM | |
