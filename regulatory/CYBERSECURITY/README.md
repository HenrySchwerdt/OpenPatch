# Cybersecurity submission structure (FD&C Act 524B, IEC 81001-5-1, MDR Annex I 17.2/17.4)

> Test project, not a medical device. **Ownership:** a dedicated security agent owns `security/` (threat model, formal verification of the handshake, fuzzing, supply chain including the CycloneDX SBOM and cargo-deny, SECURITY.md, SCORECARD.md). **This folder contains no threat model and no SBOM generator**; it defines where those artifacts go in a submission and references them. Paths marked *(planned)* may not exist in every checkout yet. The IEC 62304 SOUP list stays in `../SOFTWARE/SOUP.md`.

## 1. Artifact map

| Required content | FDA premarket cybersecurity guidance / 524B | IEC 81001-5-1 | MDR Annex I | Where it lives |
|---|---|---|---|---|
| Threat model and security risk assessment | yes (architecture views, threat model) | 5.2 threat modelling | 17.2, 17.4 | `../../security/THREAT-MODEL.md` *(planned)*; protocol threat table `../../docs/04-protocol.md` section 1 |
| Security architecture views (global system, multi-patient/updates, security use case views) | yes | 5.3 | | diagrams to be drawn from `../../firmware-rs/docs/architecture.md`; figures F13/F15 in `../figures/INDEX.md` |
| Security risk management linked to safety risk (14971) | yes, with TIR57-style method | 4.2 | | hazard H7 in `../RISK/TRACE.md`; security-specific risk table in `security/` *(planned)* |
| Security requirements and verification | yes | 5.4 to 5.7 | | `../SOFTWARE/03-requirements.md` SRS-021 to SRS-024; vectors `../../docs/vectors/` |
| **SBOM** (NTIA minimum elements, machine readable; support and end-of-support info) | yes, 524B(b)(3) | 5.1.x, 8 | | CycloneDX file produced by `../../security/` *(planned)*; IEC 62304 view `../SOFTWARE/SOUP.md` |
| Security testing: static analysis, fuzzing, vulnerability scan, penetration test | yes | 5.7 | | fuzzing and formal verification by `security/` *(planned)*; penetration test by an independent party (manufacturer, LAB) |
| Scorecard / supply-chain posture | supporting | | | `../../security/SCORECARD.md` *(planned)* |
| Plan to monitor, identify, address post-market vulnerabilities (524B(b)(1)) | yes | 6 maintenance, 8 | | policy `../../security/SECURITY.md` *(planned)* + section 3 below |
| Process to provide patches and updates in a reasonably justified, timely manner (524B(b)(2)) | yes | 6.3 | | signed updates: `../../firmware-rs/docs/bootloader.md`; release process `../SOFTWARE/07-release-checklist.md` |
| Cybersecurity labelling (user-facing security info) | yes | | 23.4 | manufacturer (no IFU here) |
| Interoperability security (secure pairing, secure data transmission) | 880.5730(b) special control | | | `../../docs/04-protocol.md` |

## 2. Statement of cyber device status

The pod contains software and a BLE radio; the controller app is internet-connected. The device is therefore expected to be a **cyber device** under section 524B and in scope of MDR Annex I 17.2/17.4 **[VERIFY with FDA on the definition of "ability to connect to the internet" for BLE-only pods]**. Treat it as in scope.

## 3. Vulnerability management structure (to be run by the manufacturer; policy text owned by `security/`)

| Element | Content to define |
|---|---|
| Intake | coordinated disclosure address and policy (`SECURITY.md` *(planned)*), CVE/GHSA handling |
| Triage | link to safety risk: each vulnerability is assessed for safety impact with `../RISK/` |
| SOUP/SBOM monitoring | `soup.py` and the SBOM are regenerated per release; advisory feeds (RustSec, GitHub, vendor errata for Nordic blobs) monitored; results recorded in `../SOFTWARE/SOUP.md` known-anomalies column |
| Remediation | signed update path, timelines per severity, field communication |
| Support period and end of support | to be defined; shown in the SBOM metadata |
| Coordinated disclosure with the shared fault catalogue | security findings that are safety relevant go into the post-market fault reporting (`../../COMMERCIAL-LICENSE.md` section 4) |

## 4. Known design-stage security gaps from the repository (see `security/` for the authoritative list)

First pairing is trust-on-first-use without an out-of-band code; pairing secret stored unencrypted in pod flash and phone Keychain; APPROTECT must be enabled beyond the bench; pod RNG seeded once per boot; Swift AES is not constant-time; no hardware testing (`../../docs/04-protocol.md` section 8, `../../firmware-rs/docs/stubs.md`).
