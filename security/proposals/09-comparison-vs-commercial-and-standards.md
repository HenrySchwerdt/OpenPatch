# Proposal 09: Comparison with public data on commercial pumps, and mapping to FDA 524B / IEC 81001-5-1 / AAMI TIR57 / SW96

Status: analysis document with an evidence column. **Honesty rule of this table: "exceeds" is claimed only where a test, proof or CI job in this repository demonstrates it; commercial pumps are judged only on what is publicly documented (advisories), never on assumptions about unpublished internals.** OpenPatch is a bench test project, not a medical device; "exceeds" never means "is safe for a person".

## 1. Public record on commercial insulin pumps (what went wrong, as published)

Retrieved 2026-11-19 via web search; primary pages (CISA/NVD) should be re-read before quoting in a regulatory document. Where search results disagreed or were secondary, that is noted.

| Product / year | Public finding | Class of weakness | Source |
|---|---|---|---|
| Animas OneTouch Ping, 2016-10 | CVE-2016-5084 (cleartext data), CVE-2016-5085 (weak random numbers; remote could be spoofed after sniffing a handshake), CVE-2016-5086 (replay: remote controller impersonation); found by Rapid7; ICS-CERT ICSMA-16-279-01 | no encryption, weak RNG, replay | <https://ics-cert.us-cert.gov/advisories/ICSMA-16-279-01>, <https://jvn.jp/vu/JVNVU95089754/> |
| Medtronic MiniMed 508 / Paradigm, 2019-06 | CVE-2019-10964: RF protocol without authentication/authorization; adjacent attacker can inject, replay, modify, intercept; CVSS 7.1 (AV:A/AC:H); Medtronic could not patch these models; FDA safety communication; ICSMA-19-178-01 | no authentication, **no update path** | <https://www.cisa.gov/news-events/ics-medical-advisories/icsma-19-178-01>, <https://threatpost.com/fda-warns-ofpotentially-fatal-flaws-in-medtronicinsulin-pumps/146109> |
| Medtronic MiniMed 600 series, 2022-09 | CVE-2022-32537: an unauthorised user can learn aspects of the pairing protocol; mitigation advised: disable Remote Bolus, pair only in private; ICSMA-22-263-01 (CVSS 4.8) | pairing protocol exposure | <https://cisa.gov/ics/advisories/icsma-22-263-01> |
| Insulet Omnipod (original system), 2020-03 | CVE-2020-10627: wireless RF link lacks proper authentication/authorization (reported by Thirdwayv); CISA ICSMA-20-079-01 states it is not exploitable remotely | RF authentication | <https://nvd.nist.gov/vuln/detail/CVE-2020-10627>, <https://db.gcve.eu/vuln/icsma-20-079-01> |
| Tandem t:slim X2 | vendor statement that SweynTooth is not applicable and proprietary authentication exists; no CVE found in this search | (vendor claim only, unverified) | <https://www.tandemdiabetes.com/community/blog/post/device-and-data-security> |

Pattern: **unauthenticated or replayable RF protocols; no encryption; weak RNG; unpatchable devices; pairing exposed.** The OpenPatch v1.1 session layer addresses each pattern for *sessions* (AEAD, strict seq, ephemeral DH with PS, constant-time confirm tags, DRBG on TRNG, signed DFU), with tests and proofs. It does **not** (yet) address *pairing authentication* (TOFU, FINDING-009) - the same class as CVE-2022-32537 / CVE-2020-10627 in spirit - and that is the first thing proposal 02 fixes.

## 2. Control-by-control comparison

Legend: **Exceeds** = a verifiable property beyond what is publicly documented for the compared pumps; **Meets** = on par with what a modern pump should have; **Gap** = we do not have it / not yet verified. "Public pumps" = the advisories above; their *current* models may do more than is public.

| Topic | Public pumps (documented) | OpenPatch today | Assessment | Evidence |
|---|---|---|---|---|
| Link authentication | none (2016, 2019 models), pairing learnable (2022), RF auth lacking (2020) | session: mutual, key-confirmed; pairing: TOFU | **Exceeds** for sessions; **Gap** for pairing | Tamarin/ProVerif results; `pairing_tofu.tamarin.txt` |
| Confidentiality | cleartext (2016) | AEAD, forward secrecy w.r.t. PS | **Exceeds** (provable FS) | `session_forward_secrecy` |
| Replay | possible (2016, 2019) | strict seq + per-session keys; reflection defect | **Meets** with FINDING-001 open | `proto_props.rs`, FINDING-001 |
| RNG | weak (2016) | ChaCha20 DRBG on TRNG, seeded once per boot | **Meets** (reseed/health: proposal 03) | `docs/04-protocol.md` s.2 |
| Formal analysis of the protocol | not public | Tamarin + ProVerif, 30 results reproduced in CI | **Exceeds** | `security/formal/run.sh` |
| Parser robustness | not public | 7 fuzz targets (0 crashes in 26.5 M execs), Kani proofs of decoders | **Exceeds** (public evidence) | `firmware-rs/fuzz`, `kani_proofs.rs` |
| Dose limits vs a malicious authenticated peer | not public | limits proven for arbitrary sequences incl. fault-ack adversary; exact tight bound known (FINDING-003) | **Exceeds** in evidence | `safety_props.rs`, Kani |
| Independent hardware dose bound | not public | design only (HW-A per window, L5 proposed) | **Gap** | THREAT-MODEL s.4 |
| Updatability | unpatchable (508/Paradigm) | signed DFU with revert; transport not written; no rollback protection | **Gap** vs product; design **Meets** | `docs/bootloader.md`, FINDING-006 |
| Secure boot / key storage | not public | no APPROTECT, PS plaintext | **Gap** | FINDING-010 |
| SBOM | not public | CycloneDX generator + CI, cargo-vet bootstrap | **Meets**/in progress | `security/supply-chain/` |
| Vulnerability disclosure | vendor processes exist (CVD with CISA) | SECURITY.md template, no monitored channel yet | **Gap** (needs a real contact) | `SECURITY.md`, proposal 08 |
| Reproducible builds | not public | measured (see results file) | **Exceeds** if reproduces | `repro-build.sh` |
| Privacy (BLE identifiers) | not public | static address + name + `PS_ID` | **Gap** | FINDING-005, proposal 06 |
| Independent pentest / clinical risk file / regulatory submission | exist for cleared devices | none | **Gap** (project-level) | - |

## 3. Mapping to FDA section 524B and standards

Scope note: OpenPatch is not a device under review; the table maps *what a submission would need* to what the repository can evidence. Standards are named from the search results of 2026-11-19 and public descriptions; the exact clause text must be taken from the licensed standards, which this repository does not contain. Sources: <https://bluegoatcyber.com/guides/section-524b-compliance-checklist>, <https://www.emergobyul.com/news/fda-releases-final-guidance-medical-device-cybersecurity> (secondary; **verify against fda.gov**, the searches disagreed on whether the controlling premarket guidance is the June 2025 or a February 2026 version).

| Requirement (as publicly summarised) | Source | OpenPatch evidence | Status |
|---|---|---|---|
| Plan to monitor, identify and address post-market vulnerabilities, including a coordinated vulnerability disclosure process | FD&C Act 524B(b)(1) | `SECURITY.md`, proposal 08 (SLAs, IR) | **Partial** (no monitored contact: placeholder) |
| Processes providing reasonable assurance the device and related systems are cybersecure; make post-market updates and patches available | 524B(b)(2) | signed DFU w/ revert (design), CI advisory scan, patch SLAs | **Partial** (DFU transport and rollback protection open) |
| **SBOM** including commercial, open-source and off-the-shelf software | 524B(b)(3) | `sbom.sh` (CycloneDX 1.5), CI artifact | **Meets** for Rust code; Swift/Trio SBOM not generated here (**Gap**) |
| Security architecture views, threat model, risk assessment (security risk management) | FDA premarket guidance; AAMI TIR57 / SW96 | `THREAT-MODEL.md` (STRIDE per interface, attack trees, safety-security separation) | **Meets** documentation; no independent review (**Gap**) |
| Secure product development framework (SPDF) | IEC 81001-5-1 (named by FDA as the SPDF standard in the secondary sources) | secure-by-design reviews, fuzzing, static/dynamic checks, CI, reproducible build | **Partial**: practices exist, no formal SDLC document set |
| Security testing: fuzzing, static analysis, penetration testing, vulnerability scanning | FDA guidance (secondary summaries) | fuzzing + Kani + proptest + dependency scanning done; **no third-party penetration test** | **Partial** |
| Postmarket: monitoring, triage, patching, disclosure (companion practice) | AAMI TIR97 (secondary) | proposal 08 | **Partial** |
| Interplay with safety risk management (ISO 14971) | AAMI TIR57 | `docs/02-safety.md` hazards H1/H7 linked; `THREAT-MODEL.md` s.4 | **Partial** (no joint risk file) |
| Traceability: requirements -> design -> tests | all | `SCORECARD.md` links each control to evidence | **Meets** (this repo) |

## 4. Where this table could be wrong
- Commercial products evolve; the public record above is 2016-2022 and says nothing about current firmware. "Exceeds" statements are about *evidence in public*, not about ground truth.
- Symbolic proofs use ideal primitives (see `security/formal/README.md`); implementation bugs like FINDING-001 are found by tests, not by the models.
- Hardware claims are unproven until a controller board exists.
