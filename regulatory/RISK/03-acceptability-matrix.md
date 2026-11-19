# 03 Risk acceptability matrix (example, to be adopted or replaced by the legal manufacturer)

> Test project. The criteria below are **illustrative**, derived from the scales in `01-risk-management-plan.md`. ISO 14971 requires the manufacturer to define criteria in the plan; none is approved here.

|  | Sev 1 Negligible | Sev 2 Minor | Sev 3 Serious | Sev 4 Critical | Sev 5 Catastrophic |
|---|---|---|---|---|---|
| **Prob 5 Frequent** | ALARP review | Unacceptable | Unacceptable | Unacceptable | Unacceptable |
| **Prob 4 Probable** | Acceptable | ALARP review | Unacceptable | Unacceptable | Unacceptable |
| **Prob 3 Occasional** | Acceptable | ALARP review | ALARP review | Unacceptable | Unacceptable |
| **Prob 2 Remote** | Acceptable | Acceptable | ALARP review | ALARP review | Unacceptable |
| **Prob 1 Improbable** | Acceptable | Acceptable | Acceptable | ALARP review | ALARP review |

- *Acceptable*: no further reduction required.
- *ALARP review*: reduce as far as possible; document whether further reduction is practicable (MDR Annex I GSPR 2 requires risks reduced **as far as possible** without adversely affecting the benefit-risk ratio, stricter than "ALARP"); benefit-risk analysis for the residual risk.
- *Unacceptable*: redesign or additional controls; no release.

Notes specific to this device:

1. For software-contributed causes, probability is not used to lower the class or the required rigour (IEC 62304); estimate severity and the strength of independent controls instead.
2. Hazards at severity 5 (H1, H5, H7, H11) cannot be accepted by probability alone: they need an independent hardware or procedural control with verified effectiveness. The current state for H1 is documented in `04-residual-risk-and-benefit-risk.md`.
3. No probabilities have been estimated: the matrix is **not yet applied**.
