# 05 Benefit-risk analysis (Annex I GSPR 1, 8; Annex II section 5) - structure and placeholders

> Test project. **No benefit claim is made and none can be made by this project**: benefit requires clinical evidence of performance and outcomes, which does not exist and which this project will never generate (no use on a person). This file is the structure a manufacturer fills.

## 1. Inputs

| Input | Source | State |
|---|---|---|
| Intended purpose and clinical benefits (measurable, patient-relevant) | manufacturer | **to be defined by the legal manufacturer** |
| State of the art and alternatives (existing patch pumps, tubed pumps, pens) | clinical literature search, MDCG 2020-6 | not performed (`../CLINICAL/01-clinical-evaluation-plan.md`) |
| Residual risk per hazard | `../RISK/02-hazard-analysis.md`, `../RISK/04-residual-risk-and-benefit-risk.md` | hazards identified; estimation placeholder |
| Overall residual risk | ISO 14971 section 8 | manufacturer |
| Post-market data | `07-pms-plan.md` | none (no marketed device) |

## 2. Structure of the analysis (to fill)

1. Clinical benefit statements with outcome parameters (to be defined by the manufacturer).
2. Risks: hazardous situations from `../RISK/`, with probability and severity by the manufacturer.
3. Comparison with state of the art: acceptable benefit-risk only if benefits outweigh residual risks for the intended population; reasoning recorded and reviewed.
4. Sensitivity: which assumptions (accuracy, occlusion detection time, alarm reliability, cybersecurity) most affect the conclusion. Known design-stage facts that would weigh: simulation FAILs for thrust and 1 U accuracy, occlusion detection of 5 to 10 h at 0.5 U/h, no hardware dose bound in Rev A (see `../RISK/04-residual-risk-and-benefit-risk.md`).
5. Conclusion and approval signatures (manufacturer).

## 3. Decision rule

No benefit-risk conclusion is recorded in this repository. Any statement "safe" or "acceptable risk" in project documents refers to engineering test goals for bench work with water.
