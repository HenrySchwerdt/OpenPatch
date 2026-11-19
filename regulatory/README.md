# regulatory/: evidence and structure for a future legal manufacturer

> **OpenPatch is a test project, not a medical device. Never wear it, never connect it to a person, never fill it with insulin or any other drug (water only).** This folder contains **no instructions for use, no patient labelling and no intended-use claim**; those are written by the legal manufacturer in the regulated phase. Facts about regulations were checked on 2026-11-19 and carry **[VERIFY]** where not confirmed from primary sources; money and time figures are estimates. See `../DISCLAIMER.md`.

Purpose: a company (legal manufacturer) could take this repository as the basis of a regulatory submission, and the commercial licence (`../COMMERCIAL-LICENSE.md`) rewards the first company that funds approval. We write what can be delivered while building and keep it traceable and current.

| Path | Contents |
|---|---|
| `ROADMAP.md` | what approval needs per market (EU MDR, US FDA ACE pump 880.5730, UK, Canada, Australia, Japan), phased plan with cost/time estimates, ranked gaps |
| `STANDARDS-MATRIX.md` | every applicable standard with clauses, evidence, status, gap; IEC 60601-2-24 essential performance mapped to our scenarios and tests |
| `TECHNICAL-FILE/` | MDR Annex II/III and FDA eSTAR skeleton, GSPR checklist, V&V index, PMS template, figure list |
| `SOFTWARE/` | IEC 62304: classification, plan, SRS, architecture and segregation, generated SOUP list, release checklist |
| `RISK/` | ISO 14971: plan, hazard analysis, acceptability matrix, residual-risk placeholder, generated `TRACE.md` |
| `CYBERSECURITY/` | 524B / IEC 81001-5-1 submission structure (content owned by `../security/`) |
| `USABILITY/` | IEC 62366-1: use specification placeholder, use errors from the design, formative plan (bench only) |
| `CLINICAL/` | clinical evaluation structure, why equivalence is unavailable, evidence list for a sponsor (no protocol) |
| `LIVING-PROCESS.md` | how it is kept current: per-PR rules, definition of done, versioning (tf-0.1.0-beta) |
| `tools/` | `trace.py`, `soup.py`, `collect_figures.py`, draft CI workflow |
| `figures/` | generated figure index (paths into the repository, nothing copied) |

## Commands

```sh
python3 regulatory/tools/trace.py --report regulatory/RISK/TRACE.md --json regulatory/RISK/trace.json   # exit 1 on broken links
python3 regulatory/tools/soup.py            # SOUP.md + soup.json from the lock files (--fetch-licences, --check)
python3 regulatory/tools/collect_figures.py # figures/INDEX.md
```

Status vocabulary: HAVE, SIM (simulation/host test), BENCH (water bench), LAB (accredited lab), CLIN (human evidence, never this project), LM (legal manufacturer; includes every drug-related test).
