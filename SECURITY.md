# Security policy

OpenPatch is a **test project, not a medical device**. It must never be worn or used with insulin on a person (see [DISCLAIMER.md](DISCLAIMER.md)). We still treat security reports with the seriousness of a safety-relevant product, because the engineering goal is to be demonstrably better than what the medical market documents today. Every security claim in this repository is meant to be checkable: see [`security/SCORECARD.md`](security/SCORECARD.md).

## Reporting a vulnerability

> **Contact: `<security contact, to be set by the maintainer>`**
> This is a placeholder. No email address, PGP key or reporting form has been published yet and none is invented here. Until the maintainer fills this in, use GitHub **private vulnerability reporting** on the repository if it is enabled (Security tab -> "Report a vulnerability"); do **not** open a public issue for a vulnerability.

Please include: affected component and commit, a reproduction (a failing test, a trace, a captured frame, or a model counter-example is ideal), and your assessment of the impact. For protocol issues a Tamarin/ProVerif counter-example against `security/formal/` is a valid report on its own.

## What to expect (targets, not guarantees)

| Step | Target |
|---|---|
| Acknowledgement | 3 business days |
| Triage and severity (CVSS 4.0 + safety impact class) | 7 days |
| Fix or mitigation | S1 14 days, S2 30 days, S3 60 days, S4 120 days (details: `security/proposals/08-incident-response-disclosure-supply-chain.md`) |
| Public advisory | after the fix, or 90 days after the report (one 30 day extension by agreement); sooner if exploited |

Reporters are credited in the advisory unless they prefer otherwise. A safe-harbour statement and bounty terms are **drafts for legal review** in the proposal above and are **not** in force until the maintainer publishes them here.

## Scope

In scope: everything in this repository: `firmware-rs/`, `firmware/` (frozen C reference), `ios/`, protocol documents, bootloader/signing tools, CI workflows, the formal models, and the website build. Out of scope: Trio, LoopKit, Nightscout and Apple/Nordic platform code (report to their owners; tell us if our integration makes it worse), physical attacks that require destroying the hardware, social engineering of maintainers, denial of service by radio jamming.

## Known issues

Open weaknesses are tracked, with reproductions, in [`security/THREAT-MODEL.md`](security/THREAT-MODEL.md) (section 9, "Weakness register") and the status of every control in [`security/SCORECARD.md`](security/SCORECARD.md). Reporting something already listed there is welcome if you can improve the reproduction or the impact assessment.

## Verifying releases (planned)

Releases will ship `SHA256SUMS` signed with minisign (offline maintainer key), CI build provenance via sigstore, CycloneDX SBOMs and a reproducible-build log (plan: `security/proposals/08...`, tools: `security/supply-chain/`). Until the first signed release exists, build from source with `--locked` and compare with `security/supply-chain/repro-build.sh`.
