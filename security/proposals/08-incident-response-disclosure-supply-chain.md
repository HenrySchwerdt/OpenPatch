# Proposal 08: Incident response, coordinated vulnerability disclosure, bug bounty plan, SBOM publication, patch SLAs, supply-chain controls

Status: proposed (SECURITY.md at the repository root is the *published* part of this proposal: it contains a placeholder contact, no invented address). Priority **P1**.
Evidence: `security/supply-chain/` (deny/audit/SBOM/reproducibility results), FINDING-007, FINDING-008.

## 1. Coordinated vulnerability disclosure (CVD)
- Policy text: `SECURITY.md` (reporting channel placeholder, scope, safe harbour statement drafted for legal review, timelines).
- Channel requirement: GitHub **private vulnerability reporting** (Security Advisories) enabled on the repository *and* a monitored mailbox/PGP key (to be created by the maintainer: **placeholder `<security contact, to be set by the maintainer>`**). A published `security.txt` (RFC 9116) on the project site (`site/public/.well-known/security.txt`) with `Contact:`, `Expires:`, `Policy:`, `Canonical:`; the file must be created by the maintainer with the real contact (not invented here).
- Timelines (adopted from ISO/IEC 29147/30111 practice, ICSA/CISA norms): acknowledge in **3 business days**, triage + severity (CVSS 4.0 + safety impact below) within **7 days**, fix or mitigation within the SLA, public advisory after fix or **90 days** (extendable once by 30 days by agreement), faster if actively exploited.
- Medical-device twist: **safety impact is rated independently of CVSS** with a 4-level scale (None / Bench-only / Could cause incorrect delivery on a bench rig / Could cause harm to a person if the device were used on one). The last class is always treated as Critical even if CVSS is Medium, because the *product intent* is to evolve toward human use; the project must never be used on a person today (DISCLAIMER.md) but the process is exercised as if it could.

## 2. Patch SLAs (calendar days from triage)
| Class | Definition | Mitigation/advisory | Fix in a release |
|---|---|---|---|
| S1 Critical | remote unauthenticated dose-affecting, key disclosure, signing key compromise | 24 h advisory + workaround (disable radio/unpair) | 14 days |
| S2 High | authenticated-state bypass, rollback, replay, privacy leak of identity | 7 days | 30 days |
| S3 Medium | DoS of session establishment, log integrity gaps, dependency advisory with reachable code | 14 days | 60 days |
| S4 Low | hardening, unreachable dependency advisory | next release | 120 days |
Dependency advisories: reviewed **daily** by CI (`security-ci.yml` nightly schedule); every ignore in `firmware-rs/deny.toml` carries a reason and a review date (<= 30 days).

## 3. Incident response
Roles (names TBD by the maintainer): Incident Lead, Crypto/Protocol owner, Firmware owner, iOS owner, Comms.
1. **Detect**: CVD report, CI advisory, fuzzer crash, bench anomaly.
2. **Triage (<= 24 h)**: reproduce, classify S1-S4, decide freeze: S1/S2 => *stop distributing bench firmware images*, keep the site's advisory banner.
3. **Contain**: revoke affected signing key slot / CA (proposal 04, 02), raise `min_security_version`, publish CRL entry if a pod identity is concerned.
4. **Fix** in a private branch/fork (GitHub private advisory fork), review by a second maintainer, run `security-ci` + formal + fuzz regression (a new fuzz artifact or test is *mandatory* with every security fix).
5. **Release**: reproducible build, signed artifacts, SBOM, advisory (GHSA + CVE via GitHub CNA request), changelog with `Security:` section.
6. **Postmortem within 14 days**: root cause, detection gap, new control (SCORECARD row). Blameless; published in `security/incidents/YYYY-MM-DD-title.md` after the embargo.
7. **Exercise** twice a year: tabletop with a synthetic S1 (e.g. "release key leaked") including rotating the key slot on a bench pod.

## 4. Bug bounty plan (staged; no money is promised by this document)
- Phase 0 (now): public CVD, hall-of-fame credit, no cash. Scope: everything in this repository *except* physical attacks needing the bench rig destroyed, social engineering of maintainers, third-party services.
- Phase 1: **targeted challenge on bench pods** shipped to vetted researchers under a signed agreement (water only, DISCLAIMER applies, no human use): scope = pairing/session protocol, DFU, SWD/APPROTECT bypass, BLE privacy. Funding and legal entity TBD by the maintainer.
- Phase 2: platform bounty (HackerOne/Intigriti/YesWeHack) only when a legal entity and a budget exist. Reward bands (proposal, to be validated against budget): S1 and "dose-affecting remote" highest; protocol design flaws proven with a Tamarin/ProVerif counter-example paid as for an implementation bug.
- The **formal models are part of the scope**: a counter-example trace to a lemma that `run.sh` reports as verified is a valid S1/S2 report.

## 5. SBOM and artifact publication
- Every release publishes: firmware `.bin`/`.elf` hashes, **CycloneDX 1.5 SBOMs** for every lockfile (`security/supply-chain/sbom.sh`), VEX statements for dependency advisories judged non-exploitable (CycloneDX VEX `analysis.state = not_affected` with justification mirrors the `deny.toml` reasons), the reproducible-build log (`repro-build.sh` output), SLSA provenance attestation, and `SHA256SUMS` signed.
- **Signing plan**: (a) **sigstore/cosign keyless** (GitHub OIDC) for CI-built artifacts and attestations: proves *which workflow at which commit* produced a file; (b) **minisign** (Ed25519, offline key on a hardware token, two maintainers) for the *release decision*: a human signs `SHA256SUMS`; the firmware signature of proposal 04 is a third, separate key (device trust anchor). Users verify with `cosign verify-blob` and `minisign -V`; instructions in `SECURITY.md`. Release tags are signed (`git tag -s`), `main` requires signed commits + 1 review + green `security-ci`.
- SBOM *consumption*: a nightly job diffs the new SBOM against the previous release and fails on any new dependency without a cargo-vet audit entry.

## 6. Supply-chain controls (concrete task list, tracked in SCORECARD)
| ID | Task | State |
|---|---|---|
| SC-1 | `cargo vet` in `firmware-rs/supply-chain/` with imports of Google/Mozilla/Bytecode Alliance audits, own audits for `embassy-*`, `trouble-host`, RustCrypto crates (`aes`, `ccm`, `x25519-dalek`, `hkdf`, `hmac`, `sha2`, `subtle`, `ed25519-dalek`/`salty`) | exemptions bootstrap committed; real audits: open |
| SC-2 | `cargo deny` (`firmware-rs/deny.toml`) in CI, all workspaces | done (config + CI) |
| SC-3 | Upgrade `heapless 0.8.0 -> >= 0.9.4` (9 advisories, FINDING-007); then delete the `ignore` entries | open |
| SC-4 | `trouble-host`/`p256`/`crypto-bigint >= 0.7.6` (FINDING-008) | open (upstream) |
| SC-5 | Pin toolchain: `rust-toolchain.toml` (channel `1.97.0`, components, `thumbv7em-none-eabihf`) in `firmware-rs/` | proposed file text below; **not created** (would change every developer's toolchain, other agents are building) |
| SC-6 | GitHub Actions pinned by SHA, least-privilege tokens, no `pull_request_target`, `persist-credentials: false`; existing `pages.yml` uses mutable tags and a workflow-level `pages: write` + `id-token: write` (finding) | new workflow compliant except SHA resolution (needs API access); existing workflow: open |
| SC-7 | `Cargo.lock` committed and `--locked` in every CI build | done for new CI |
| SC-8 | Crate `publish = false` on every workspace member (enables `wildcards = "deny"`) | open |
| SC-9 | `differential-tests` links the C reference core: keep it out of the release path; it is the only crate allowed `unsafe` FFI | note |
| SC-10 | Dependabot/Renovate for Cargo + Actions with grouped weekly PRs and mandatory `security-ci` | proposed |
| SC-11 | Secret scanning + push protection on the repository; `.gitignore` already blocks `keys/`, `*.pem`, `*.key`, `**/ed25519-secret*` | partly done |
| SC-12 | Reproducible bench firmware | see `security/supply-chain/results/` for the measured outcome |

Proposed `firmware-rs/rust-toolchain.toml` (to be added by the build owner):
```toml
[toolchain]
channel = "1.97.0"
components = ["rustfmt", "clippy", "llvm-tools"]
targets = ["thumbv7em-none-eabihf"]
profile = "minimal"
```

## 7. Third-party binary blobs and licences (note for the licensing owner)
`openpatch-bench` depends on `nrf-mpsl-sys 0.3.0` and `nrf-sdc-sys 0.3.0` (Nordic MPSL/SoftDevice Controller binaries): cargo-deny reports them as *unlicensed* (Nordic proprietary licence, redistribution only for use with Nordic SoCs). They are the BLE controller: **closed-source code on the radio path**, outside our audit reach. Controls: keep them pinned (`=0.4.0` in Cargo.toml), record their hashes in the SBOM, track Nordic security bulletins in the nightly job (manual feed until automated), and state the licence in LICENSE.md third-party list. For a product this blob also needs a documented exception in the deny config (`[[licenses.clarify]]` with the vendor licence text hash).
