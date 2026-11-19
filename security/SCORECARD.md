# Security scorecard

TEST PROJECT, not a medical device. One row per control; **a row is "Done" only if the evidence link runs a test, proof, check or CI job that would fail if the control broke.** Everything else is Partial / Proposed / Open / Rev B. Update this file in the same commit that changes a control. Generated numbers (execs, results) come from the cited run files.

Status: **Done** evidenced; **Partial** some of it evidenced; **Prop** designed in `security/proposals/`, not implemented; **Open** not addressed; **RevB** needs Rev B hardware; **N/A**.
Snapshot 2026-11-19 (73 rows): Done 29, Partial 7, Prop 25, Open 11 (three of them, ID-1, HW-3, K-1, already have a proposal), RevB 1.

## A. Protocol and cryptography
| ID | Control | Status | Evidence |
|---|---|---|---|
| P-1 | Session key secrecy (X25519 + PS in HKDF extract) | Done | Tamarin `session_key_secrecy_ps_only`; ProVerif phase-1 leak query; `security/formal/results/` |
| P-2 | Forward secrecy w.r.t. PS | Done | Tamarin `session_forward_secrecy`; ProVerif `pv_session_spec` |
| P-3 | Injective mutual agreement of sessions (replay resistance of the handshake) | Done | Tamarin `session_agreement_*`; ProVerif S4/S5 |
| P-4 | Key confirmation before keys are installed | Done | `handshake_props.rs::honest_pairing_then_session_agree`; fuzz `handshake_mutate` (45 k structure-aware runs: no installed session after any single-byte tamper) |
| P-5 | Low-order X25519 points rejected | Done | `handshake_props.rs::low_order_public_keys_are_rejected` |
| P-6 | Frame integrity (any bit flip rejected) | Done | `proto_props.rs::sealed_frame_bitflip_rejected`; fuzz `ccm_open` (1.7 M) |
| P-7 | In-session replay/ordering | Done | `proto_props.rs::replay_and_ordering`; Kani `proof_session_replay_monotonic`; fuzz `session_open` |
| P-8 | Direction separation / no reflection, no nonce reuse | **Open** | FINDING-001; proposal 01 s.1 |
| P-9 | Constant-time, audited AEAD on both ends | Prop | proposal 01 s.2 (ChaCha20-Poly1305); Swift CCM is hand-written (FINDING-011) |
| P-10 | Version negotiation with downgrade protection | Prop | proposal 01 s.3 |
| P-11 | RNG: seed health tests, periodic reseed | Prop | proposal 03 s.4 |
| P-12 | Handshake DoS bounds (rate limit, pending slots) | Prop | FINDING-004; proposal 03 s.5 |
| P-13 | Static identifier `PS_ID` removed | Prop | FINDING-005; proposal 03 s.5.4 |

## B. Pairing and identity
| ID | Control | Status | Evidence |
|---|---|---|---|
| ID-1 | Authenticated pairing (no TOFU) | **Open** -> Prop | Tamarin TOFU falsified (`pairing_tofu.tamarin.txt`); proposal 02 |
| ID-2 | High-entropy OOB / QR | Prop | FINDING-002; `oob_offline_guess.py`; proposal 02 s.2.2 |
| ID-3 | PAKE (no offline guessing of a short code) | Prop | ProVerif `pv_pairing_cpace.proverif.txt` (shape verified); proposal 02 s.2.3 |
| ID-4 | Per-device identity key + certificate chain + revocation | Prop | proposal 02 s.2.1/2.4 |
| ID-5 | Pairing only by button, window 60 s | Done | `handshake_props.rs::pairing_refused_outside_window` (logic); button path unverified on hardware |
| ID-6 | Pairing authentication holds with OOB (symbolic) | Done | Tamarin `pairing_oob.tamarin.txt` (4/4 verified) |

## C. Authorisation and safety separation
| ID | Control | Status | Evidence |
|---|---|---|---|
| Z-1 | Hard limits cannot be raised through any command | Done | `safety_props.rs::p4/p5`; Kani `proof_configure_hard_caps`, `proof_check_bolus_hard_limit` |
| Z-2 | Per-minute and wall-clock-hour caps hold for arbitrary sequences, with a fault-acknowledging adversary | Done | `safety_props.rs::p1/p2`; Kani `proof_approve_steps_*` |
| Z-3 | Exact sliding-hour bound known and tested (16.7 U) | Done (documents FINDING-003) | `safety_props.rs::p3`, `finding_003_*` |
| Z-4 | Sliding hour equals the spec's 15 U | Open | FINDING-003; proposal 07 s.5 |
| Z-5 | Dangerous-command class with fresh/physical confirmation | Prop | proposal 07 s.2-3 |
| Z-6 | Limit-class faults cleared only by physical presence | Prop | proposal 07 s.2.6 |
| Z-7 | Pod behaviour without a session fails safe (refuse everything, basal continues) | Done (logic) | `proto_props.rs::keyless_session_refuses_everything`; core tests |
| Z-8 | Comm-loss fallback cannot be defeated by frame reflection | **Open** | FINDING-001 |
| HW-1 | Hardware interlock (MCU_EN AND watchdog latch AND DOCKED) | Partial (design; board not fabricated/verified) | `docs/02-safety.md` s.2, `spec` s.7a |
| HW-2 | Hardware step budget per arm window (~1.6 U) | Partial (design only) | `spec` s.7a |
| HW-3 | Hardware bound on dose per hour independent of firmware | Open -> Prop | THREAT-MODEL s.4; proposal 07 s.4 |
| HW-4 | Re-arm dead time on `ARM_CLK` (Rev A cheap partial for HW-3) | Prop | THREAT-MODEL s.4 |

## D. Firmware integrity, update and storage
| ID | Control | Status | Evidence |
|---|---|---|---|
| F-1 | Signed firmware (Ed25519 over SHA-512), fail-closed without key | Done (host-checked) | `docs/bootloader.md`; fuzz `dfu_manifest` (219 k execs); hardware unverified |
| F-2 | Power-fail-safe swap with revert of unconfirmed images | Partial (design, embassy-boot; unverified on HW) | `docs/bootloader.md`, `stubs.md` item 8 |
| F-3 | Anti-rollback counter, signed version/product/profile | Prop | FINDING-006; proposal 04 |
| F-4 | Manifest parser is the real code under fuzz/Kani | Prop | proposal 04 s.4 |
| F-5 | Offline release key on a token, rotation, two-person rule | Prop | proposal 04 s.5 |
| F-6 | DFU transport requirements (button start, dangerous class) | Prop | proposal 04 s.6 |
| K-1 | APPROTECT / debug lock + boot assertion | Open -> Prop | FINDING-010; proposal 03 s.2 |
| K-2 | PS and bonds encrypted at rest | Prop | proposal 03 s.3 |
| K-3 | KMU / TrustZone keys | RevB | proposal 03 s.2.3 |
| K-4 | Drive calibration record integrity (CRC + preset equality, mismatch => no delivery) | Done | `drive_cal.rs::validate`; fuzz `storage_records` (12.8 M, coverage limited) |
| L-1 | Tamper-evident hash-chained log | Prop | proposal 05 |

## E. Robustness and verification
| ID | Control | Status | Evidence |
|---|---|---|---|
| V-1 | Formal model of pairing + session (2 tools, cross-checked) | Done | `security/formal/run.sh` (30 expectations) |
| V-2 | CI re-runs the models and fails on drift | Done | `.github/workflows/security-ci.yml` job `formal` (workflow not yet executed on GitHub) |
| V-3 | Frame/TLV/command/response decoders total (no panic) | Done | `proto_props.rs`; Kani `proof_tlv_reader_total`, `proof_decode_frame_total`, `proof_decode_command_total`; fuzz `frame_tlv` (6.0 M) |
| V-4 | Fuzzing of every parser: frame/TLV, handshake x2, session open, CCM, DFU manifest, storage records | Done (smoke) | `firmware-rs/fuzz/`, `security/fuzz/results/2026-11-19-run1.txt`: 26.5 M execs, 0 crashes |
| V-5 | Fuzz corpora seeds committed | Done | `firmware-rs/fuzz/corpus/` (53 files) |
| V-6 | Long-running fuzzing (hours, OSS-Fuzz style) | Open | - |
| V-7 | Storage record codec fuzzed in place (not mirrored) | Prop | `storage_records.rs` header; proposal 03/04 |
| V-8 | Differential tests Rust vs C reference | Done (pre-existing) | `firmware-rs/differential-tests` |
| V-9 | Independent penetration test | Open | - |
| V-10 | Hardware-in-loop security tests (APPROTECT, fault injection) | Open | `stubs.md` (nothing has run on a target) |
| V-11 | Known-issue regression tests flip when a finding is fixed | Done | `finding_001_reflection.rs`, `handshake_props.rs`, `safety_props.rs`; CI step "fixed_* must still fail" |

## F. Supply chain and build
| ID | Control | Status | Evidence |
|---|---|---|---|
| SC-1 | cargo-vet in repo | Partial (bootstrap: 92 exemptions, 0 own audits) | `firmware-rs/supply-chain/` |
| SC-2 | cargo-deny: advisories, licences (copyleft denied, PolyForm exceptions), bans, sources | Done | `firmware-rs/deny.toml`, `security/supply-chain/results/deny-*.txt` |
| SC-3 | `heapless` >= 0.9.4 | Open (triaged, 9 ignores with reasons) | FINDING-007 |
| SC-4 | p256/crypto-bigint timing advisory resolved | Open (upstream) | FINDING-008 |
| SC-5 | Toolchain pinned | Prop | proposal 08 s.6 |
| SC-6 | Actions pinned by SHA, least privilege | Partial (permissions/no secrets done; SHAs need API access; `pages.yml` not ours) | `check-action-pins.sh` fails until pinned |
| SC-7 | `--locked` builds, lockfiles committed | Done | workflow, `Cargo.lock` files |
| SC-8 | CycloneDX SBOM per lockfile | Done | `security/supply-chain/sbom.sh`, `results/sbom/` |
| SC-9 | Reproducible bench firmware and bootloader | Partial: identical from a fixed source path (3 builds), differs across source paths (cargo `-C metadata` of out-of-workspace path deps); bootloader reproducible from any path | `security/supply-chain/repro-build.sh`, `results/repro-build.txt` |
| SC-10 | Signed releases (sigstore + minisign), provenance | Prop | proposal 08 s.5 |
| SC-11 | Nightly advisory scan | Done (config) | workflow `schedule` |

## G. Privacy
| ID | Control | Status | Evidence |
|---|---|---|---|
| PR-1 | RPA rotation, no static address | Prop | proposal 06 s.2.1 |
| PR-2 | No name/UUID/serial in adverts; no pairing beacon | Prop | proposal 06 s.2.2-4 |
| PR-3 | Minimal TX power, no Coded PHY advertising | Prop | proposal 06 s.2.5 |
| PR-4 | App-layer data only inside the session | Done | production refuses non-handshake frames (`proto_props.rs`) |

## H. Process
| ID | Control | Status | Evidence |
|---|---|---|---|
| PC-1 | SECURITY.md with CVD policy | Partial (no real contact: placeholder by design) | `SECURITY.md` |
| PC-2 | Incident response, patch SLAs, bounty plan | Prop | proposal 08 |
| PC-3 | Threat model (assets, attackers, STRIDE, attack trees, safety-security separation) | Done (doc), no independent review | `security/THREAT-MODEL.md` |
| PC-4 | Comparison with public data and standards, evidence column | Done (doc) | proposal 09 |
| PC-5 | Security events logged and reviewed | Prop | proposal 05 |

## Priorities (impact / effort)
1. P-8 reflection fix (small, P0) 2. ID-1..3 authenticated pairing (P0) 3. HW-3/HW-4 hardware dose bound 4. K-1 APPROTECT 5. F-3 anti-rollback before any DFU transport 6. P-9 AEAD swap 7. Z-5/Z-6 authorisation classes 8. SC-3/SC-4/SC-6 housekeeping 9. L-1, PR-1..3.
