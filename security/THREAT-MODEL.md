# OpenPatch threat model

> **TEST PROJECT. Not a medical device. Never to be worn or used with insulin on a person** (`DISCLAIMER.md`). The threat model is written as if the design were headed for human use, because that is the standard the security requirement sets ("demonstrably state of the art, every claim verifiable in the repository"). Every status below links to the evidence that backs it; "implemented" means *a test, proof or CI job in this repository checks it*, not that someone believes it.
>
> State: 2026-11-19. Sources read: `docs/02-safety.md`, `spec/design-parameters.md` s.6/7/7a, `docs/04-protocol.md` (v1.1, from the shared checkout), `firmware-rs/{openpatch-proto,openpatch-core,openpatch-bench,openpatch-bootloader,tools/sigtool}`, `firmware-rs/docs/stubs.md`, `electronics/bench/pin-assignment.md`.
> Status legend: **I** implemented and evidenced, **P** proposed (design + test plan in `security/proposals/`), **B** needs Rev B hardware, **O** open / not addressed, **-** not applicable.

## 1. Assets

| # | Asset | Why it matters | Where it lives |
|---|---|---|---|
| A1 | **Dose authority** (ability to cause any delivery or stop) | the safety-critical asset | pod firmware, session keys, PS |
| A2 | **Pairing secret PS** (32 B) | root of all session keys; holder can impersonate the phone to the pod | pod flash (`storage.rs` key 6, plaintext), phone Keychain |
| A3 | **Session keys** (key_c2p, key_p2c, salt) | one connection's dose authority | RAM of pod and phone only |
| A4 | **Firmware signing key** (Ed25519) | whoever holds it controls every pod's code | developer machine `firmware-rs/keys/` today |
| A5 | **Basal schedule, limits, calibration** | integrity = dosing correctness; U/step error is a dosing error | pod flash / RAM; calibration record (`drive_cal.rs`, CRC + preset equality) |
| A6 | **Fault / event log** | evidence, repudiation resistance | pod flash ring (`log.rs`), phone |
| A7 | **User privacy / location** | presence of a pump, health data, movement | BLE adverts, address, `PS_ID`, status data |
| A8 | **Pod availability / integrity of the hardware** (bricking) | a dead pod stops delivery silently if not alarmed | bootloader, flash, DFU |
| A9 | **Build integrity** (toolchain, crates, CI, release artifacts) | upstream of everything above | `Cargo.lock`, GitHub Actions |
| A10 | **BLE bond keys (LTK/IRK)** | link-layer confidentiality, tracking | pod flash plaintext, phone |

## 2. Trust boundaries and interfaces

```
  user ──button/LED/buzzer──► [ POD / bench controller ]                    [ cloud / Nightscout ]
                                 │  MCU nRF52840  (safety task | delivery | BLE task)   ▲
   BLE radio  ◄── TB1 ──────────►│  ── hardware interlock (TPL5010 + latch + DOCKED) ─► motor supply
   (any device in range)         │  ── FFC (TB5) ──► pod sensor board (TMAG, dock hall) / motor
                                 │  ── SWD (TB3) ──► debug probe (physical)
   phone (iOS: Trio + OpenPatchKit) ◄── TB2 (app boundary: other apps, OS) ; ── TB6 ──► Trio ◄── cloud (TB7)
   DFU image source ── TB4 ──► pod (not implemented yet)           build/CI/crates.io ── TB8 ──► firmware
```
Boundaries: **TB1** radio (untrusted), **TB2** phone OS/app boundary, **TB3** debug port / flash (physical), **TB4** firmware update channel, **TB5** pod sensors/FFC (physical wires inside the enclosure), **TB6** Trio <-> OpenPatchKit, **TB7** Trio <-> cloud/Nightscout (out of this repository's control), **TB8** supply chain.

## 3. Attackers

| ID | Attacker | Capability | In scope |
|---|---|---|---|
| T1 | **Proximity radio attacker** | sniff/inject/relay BLE in range, incl. long-range receiver (hundreds of metres, directional antenna) and a laptop with BLE; no physical access | yes |
| T2 | **Malicious app on the phone** | runs on the same iPhone, no PS; can scan BLE, use CoreBluetooth, side channels (cache timing on the Swift AES) | yes |
| T3 | **Compromised phone / compromised Trio / malicious algorithm** | holds PS and session keys, issues arbitrary authenticated commands | yes: pod must still bound harm (L1-L5 of proposal 07) |
| T4 | **Supply-chain attacker** | malicious or vulnerable crate, compromised CI action, poisoned toolchain, tampered release artifact | yes |
| T5 | **Malicious firmware update** | validly signed (stolen key) or rolled-back image delivered over TB4 | yes |
| T6 | **Physical attacker (SWD, glitching, probing)** | has the pod for minutes to days; SWD probe, fault injection | partly (Rev A bench: APPROTECT only; Rev B: KMU) |
| T7 | **Insider at a manufacturer / provisioning** | can implant keys, skip provisioning steps, sign images | yes (process controls, proposals 02/04/08) |
| T8 | **Curious bystander / tracker** | passive BLE scanning over time | yes (privacy) |

## 4. The key argument: safety-security separation

**Claim.** The *safety case* must not depend on the security of the firmware. Concretely: what is the worst dose an attacker can cause with **fully attacker-controlled firmware** (T5 with a stolen key, T6 with flash write, or a malicious dependency T4), what bounds it, and what is the *evidence*?

| Layer | Bounds attacker-controlled firmware? | What it guarantees | What it does **not** | Evidence |
|---|---|---|---|---|
| L0 Physics | yes | motor speed and stroke limit the dose *rate*; reservoir limits the *total* (100/200 U) | nothing below ~370 U/min (at 1000 pps x 6.17 mU/step; mechanical stall limit unmeasured) | spec s.4, `limits.rs DRAW_MAX_PPS` |
| L1 Hardware interlock `VMOT = latch AND MCU_EN AND (DOCKED OR DIR_REV)` + TPL5010 | yes | hung/crashed firmware cannot hold the motor on beyond one watchdog interval (2 s); no forward delivery when undocked; supply is off at power-up | firmware that **feeds** the watchdog and sets the enables keeps the supply on. The gates are *cooperative*, not an authority | `docs/02-safety.md` s.2, `spec` s.7a; **hardware not yet fabricated/verified** (`docs/STATUS.md`: controller board interrupted) |
| L2 Hardware step budget "HW-A" (arm window + pulse budget in discrete logic, ~1.6 U per window) | yes, per arm | a runaway *inside one watchdog window* is bounded to about 1.6 U | **re-arming**: a toggling MCU can re-arm after each window (the same limit is stated for the SMA one-shot in `pin-assignment.md`); per-hour dose is not bounded | `spec` s.7a; **design only, not built** |
| L3 Hardware over-current cut that clears the latch | yes | stall/short produces a hardware cut | says nothing about dose delivered at normal current | `spec` s.7a; **design only** |
| L4 Firmware supervisor (`approve_steps`, `check_*`) | **no** (it is the thing the attacker replaces) | bounds an authenticated-but-malicious *phone* (T3): 1.7 U/min, 15 U per wall-clock hour (16.7 U sliding, FINDING-003), 10/25 U bolus, 5/30 U/h basal | firmware compromise | `security/verify/tests/safety_props.rs`, Kani proofs, differential tests vs C |
| L5 **Independent hardware dose monitor (proposed)**: second die or discrete leaky bucket on STCK/DIR, own clock, read-only limits, latch until power cycle + button | **yes, with margin** | worst case fully malicious firmware: <= 15 U/h and <= 1.7 U/min (leaky bucket, no bucket boundary effect) | dose *inside* the budget; physical attacks on the monitor itself | `proposals/07` s.4 (Rev B per spec s.7a; Rev A discrete-logic variant: re-arm dead time) |

**Result.** With **today's** design, fully attacker-controlled firmware is bounded by L0 and, once built and verified, L1-L3: *no forward delivery while undocked, no unattended runaway longer than one window (~1.6 U)*. It is **not** bounded per hour, because nothing in hardware limits how often the window is re-armed. The only per-hour bound is firmware (L4), i.e. exactly the component a firmware-level attacker replaces. Closing this needs L5; on Rev A the cheapest partial step is an **arm dead-time one-shot** in front of `ARM_CLK` (one re-arm per minute: caps the worst case at ~1.6 U/min ~ 96 U/h, still a gap but a bounded and *measurable* one on the bench) plus the leaky-bucket monitor on Rev B. This is the single most important residual risk of the architecture and is tracked as SCORECARD row HW-3.

**What the model deliberately separates.**
1. *Authentication* (who may command) never replaces *authorisation limits* (what a commanded pod may do): `proposals/07`.
2. *Anything reachable from the radio never runs in the safety task*: handshake and CPU-expensive crypto are in the BLE task (`docs/04-protocol.md` s.1); a DoS of the handshake degrades availability of sessions, not the autonomous basal delivery.
3. *Loss of authentication or comms must fail safe*: no session => no commands, basal continues autonomously, temp basal falls back after 30 min (H6). Evidence: `proto_props.rs::keyless_session_refuses_everything`; **comm-loss fallback can be defeated by the reflected-frame heartbeat (FINDING-001) for an attacker inside the live connection.**
4. *Security faults are safety-visible*: proposal 05 puts security events into the same hash-chained log as faults.

## 5. STRIDE per interface

Threat IDs `S1..`, `T1..` are local to each table. "Mit." = mitigation, "Status" per legend, with evidence.

### 5.1 BLE GATT / application protocol (TB1, TB2)
| STRIDE | Threat | Mit. | Status | Evidence |
|---|---|---|---|---|
| S | Unpaired device issues commands | App-layer session; production refuses every non-handshake frame | **I** | `proto_props.rs::keyless_session_refuses_everything`, fuzz `session_open` (no unauthenticated frame accepted, 3.2 M execs) |
| S | Attacker becomes paired peer (TOFU / MITM in window) | OOB code, button, 60 s window | **O** (TOFU **falsified** formally); OOB guessable offline | `security/formal/results/pairing_tofu.tamarin.txt`, FINDING-002, FINDING-009; fix `proposals/02` |
| S | Fake pod to the phone | Pod proves PS via confirm tag in sessions; no identity in pairing | session **I**, pairing **O** | Tamarin `session_agreement_app`; `proposals/02` |
| T | Modify frames in flight | AES-CCM tag + CRC; keys per connection | **I** | `proto_props.rs::sealed_frame_bitflip_rejected`; fuzz `ccm_open` (1.7 M execs) |
| T | Reflect pod responses back (nonce reuse, heartbeat refresh) | none | **O** | FINDING-001; `proposals/01` s.1 |
| R | Pod or phone denies a dose command | event log with ids; no integrity | **O** | `proposals/05` |
| I | Eavesdrop dose/status data | AEAD in session; ephemeral DH => forward secrecy | **I** | Tamarin `session_forward_secrecy`, ProVerif phase-1 leak |
| I | Track a user by `PS_ID` / static address / name | none | **O** | FINDING-005, `proposals/06` |
| D | Flood handshakes; displace pending | single pending slot; handshake in BLE task (not safety task) | **O**/partial | FINDING-004, `proposals/03` s.5 |
| E | Dangerous command without confirmation | none (any session can `Release`, `SetPairing`, `FillPrime`) | **O** | `proposals/07` s.3 |
| E | Raise limits above hard caps | `configure()` rejects; hard caps `const` | **I** | `safety_props.rs::p4/p5`, Kani `proof_configure_hard_caps` |
| E | Replay old command in the same session | strict seq | **I** | `proto_props.rs::replay_and_ordering`, fuzz `session_open` |

### 5.2 Pairing (button + app-layer handshake)
| STRIDE | Threat | Mit. | Status | Evidence |
|---|---|---|---|---|
| S/E | First-come attacker during the 60 s window replaces PS | button, one pairing/press | **O** | Tamarin TOFU traces; `proposals/02` |
| S | Offline guess of a short OOB code | none (code only in salt) | **O** | `oob_offline_guess.py` (recovers `123456` in 2 s), ProVerif weak secret |
| T | Pairing without button | window closed => `AUTH` | **I** | `handshake_props.rs::pairing_refused_outside_window` |
| I | PS leak from flash | none (plaintext; APPROTECT off) | **O** | FINDING-010, `proposals/03` |
| D | Keep the window pending to block the user | window/pending slot | partial | FINDING-004 |

### 5.3 DFU / bootloader (TB4) - transport not implemented
| STRIDE | Threat | Mit. | Status | Evidence |
|---|---|---|---|---|
| T/E | Unsigned image installed | Ed25519 over SHA-512, verified in app and bootloader, fail-closed without key | **I** (logic host-checked; hardware unverified) | `docs/bootloader.md`, fuzz `dfu_manifest` (219 k execs) |
| T/E | Rollback to a vulnerable/dev/DK image | none | **O** | FINDING-006, `proposals/04` |
| T | Manifest metadata tampering | fields ignored, not signed | **O** (harmless today) | FINDING-006 |
| D | Brick via interrupted/failed update | embassy-boot power-fail-safe swap, revert on unconfirmed trial | **I** (design, unverified on hardware) | `docs/bootloader.md`, stubs.md item 8 |
| E | Compromised phone pushes firmware | none yet (no transport) | **P** (button + dangerous-command class) | `proposals/04` s.6, `07` |
| S | Signing key theft | key file on developer machine, 0600 | **O** | `proposals/04` s.5, `08` |
| D | Release key rotation requires re-flashing the bootloader | none | **O** | `proposals/04` s.5 |

### 5.4 SWD / debug / flash (TB3), physical
| STRIDE | Threat | Mit. | Status | Evidence |
|---|---|---|---|---|
| I | Read flash (PS, bonds) via SWD | none: APPROTECT not enabled | **O** | FINDING-010, `proposals/03` s.2 |
| T/E | Reflash arbitrary code | none until APPROTECT; bootloader does not re-verify ACTIVE | **O** | `proposals/04` s.1.6 |
| T | Voltage/EM glitch of the APPROTECT check or of the signature verification | none | **B** (KMU, TrustZone, nRF54L15) | `proposals/03` s.2.3 |
| D | Erase | n/a | - | - |
| Safety | Attacker firmware runs the motor | interlock L1-L3 (design), monitor L5 (proposed) | **P**/design | section 4 |

### 5.5 Flash storage records
| STRIDE | Threat | Mit. | Status | Evidence |
|---|---|---|---|---|
| T | Wrong drive calibration written (U/step error = dosing error) | CRC + equality with a known preset; mismatch => no delivery, record never overwritten | **I** | `drive_cal.rs::validate`, fuzz `storage_records` (12.8 M execs, coverage limited, see fuzz README) |
| T | Seq ceiling / reservoir record rolled back | write-ahead ceiling | partial | `stubs.md` "Deliberate deviations" |
| I | PS/LTK plaintext | none | **O** | FINDING-010 |
| T | Log record rewriting | none | **O** | `proposals/05` |

### 5.6 FFC / pod sensors (TB5)
| STRIDE | Threat | Mit. | Status | Evidence |
|---|---|---|---|---|
| T | Spoofed angle sensor (TMAG5273) masks over-/under-delivery | 3 %/rev check, 10 % window check, occlusion; sensor missing => refuse to deliver | **I** (logic) / sensor **unverified on hardware** | core tests, `stubs.md` |
| T | Fake DOCKED (magnet) enables forward delivery undocked | DOCKED in hardware gate and firmware | design, hardware unverified | `pin-assignment.md`; firmware `dock-simulated` is compile_error with `board-bench-e73` unless `unsafe-bench-override` |
| T | I2C bus tampering | physical access inside the enclosure | out of scope (physical, T6) | - |

### 5.7 Cloud / Nightscout via Trio (TB6, TB7)
| STRIDE | Threat | Mit. | Status |
|---|---|---|---|
| T | Compromised Nightscout / cloud pushes remote commands via Trio | Trio's own remote command security (out of repo); pod limits L4/L5 bound any command | partial (limits **I**, Trio **-**) |
| I | Dose and glucose data leave the phone | Trio/Nightscout configuration | - |
| E | OpenPatchKit exposes more than needed to Trio | review of `ios/INTEGRATION.md`; commands gated per class | **P** (`proposals/07`) |

## 6. Attack trees

### 6.1 Goal: deliver unintended insulin (over-delivery)
```
G1 over-delivery
├─ A. Issue dosing commands the owner did not intend
│   ├─ A1 become the paired peer ................... TOFU/first-come (O: FINDING-009), weak OOB (O: FINDING-002)  -> proposal 02
│   ├─ A2 steal PS ................................. flash read (O: FINDING-010), phone compromise (T3)          -> 02, 03, 07
│   ├─ A3 hijack a live session .................... needs session keys: Tamarin secrecy/agreement (I); reflection only refreshes heartbeat (O: FINDING-001)
│   └─ A4 abuse authority of a malicious phone/algorithm (T3)  -> bounded by L4: <=16.7 U/h, 10 U bolus (I, FINDING-003); L5 proposed
├─ B. Change what the pod believes
│   ├─ B1 wrong U/step (calibration rewrite) ........ CRC+preset equality => no delivery (I); gear-ratio mismatch between CAD and firmware default is a *non-attack* dosing error flagged in STATUS.md
│   ├─ B2 spoof the angle sensor / dock ............. physical (T6); firmware cross-checks (I), hardware gate (design)
│   └─ B3 raise limits ............................... hard caps const (I)
├─ C. Run attacker firmware (T5/T6/T4)
│   ├─ C1 forge or steal signing key ................. offline key + token (P: proposal 04/08)
│   ├─ C2 rollback to a vulnerable image ............. (O: FINDING-006) -> 04
│   ├─ C3 flash via SWD ............................. APPROTECT (O: FINDING-010) -> 03; glitching (B)
│   └─ C4 malicious dependency ....................... deny/vet/reproducible builds (partial I/P: section 7)
│        └─ then dose is bounded only by L0..L3 (section 4): re-arm gap -> L5 (P)
└─ D. Make the safety monitoring blind: replay/reflect heartbeats so comm-loss fallback never triggers (O: FINDING-001)
```

### 6.2 Goal: stop delivery silently
```
G2 silent stop
├─ A. Command suspend/Release/SetPairing without owner knowledge  (authenticated only: O dangerous-command class -> 07)
├─ B. Starve the pod: battery drain by connection/handshake floods (O: rate limits, 03), brown-out (H3: restarts SUSPENDED + alarm, I by design)
├─ C. Trigger latching faults by feeding false sensor data (physical T6) -> alarm is raised (fault => alarm) so not silent (I)
├─ D. Block the alarm path: jam BLE so Trio never shows the alarm  -> on-pod buzzer/LED (Rev B buzzer; bench has buzzer) ; comm-loss alert in Trio (out of repo)
├─ E. Brick: bad update (04), flash erase (T6), bootloader state corruption; recovery is physical re-flash (B)
└─ F. Log erase to hide a stop (O: 05)
```

### 6.3 Goal: exfiltrate data
```
G3 exfiltration
├─ Radio: eavesdrop app layer (AEAD, forward secrecy: I) ; link-layer Just-Works eavesdrop: unprotected but app layer covers; identifiers: PS_ID, static address, name (O: 06, FINDING-005)
├─ Phone: other app reads Keychain (iOS sandbox, ThisDeviceOnly: -) ; Swift AES cache timing (O: FINDING-011) -> 01
├─ Pod flash: PS, LTK, IRK, log (O: FINDING-010) -> 03
├─ Cloud: Nightscout/Trio (-)
└─ Supply chain: telemetry in a dependency (T4) -> deny.toml bans/sources, SBOM review (partial)
```

### 6.4 Goal: brick the pod
```
G4 brick
├─ Install a bad but validly signed image (stolen key / honest bug): revert if not confirmed (30 good ticks) (I by design, unverified on HW)
├─ Corrupt bootloader state/manifest page: power-fail-safe swap (I by design); bootloader cancels invalid pending update (I)
├─ Erase flash via SWD (T6): unrecoverable without re-flash; APPROTECT blocks (O) 
├─ Set a bad UICR (reset pin) : build-time only
└─ Fill the log/storage to wear flash: rate limits and eviction accounting (O: 05, 07)
```

## 7. Supply chain (T4/T8) - status
| Control | Status | Evidence |
|---|---|---|
| Advisory scanning in CI incl. nightly | **I** (config + workflow) | `.github/workflows/security-ci.yml`, `firmware-rs/deny.toml`, `security/supply-chain/results/` |
| Licence policy incl. copyleft denial and PolyForm exceptions | **I** | `deny.toml` |
| Source pinning (crates.io only, no git deps) | **I** | `deny.toml [sources]` |
| Lockfiles + `--locked` | **I** | workflow |
| cargo-vet | bootstrap (92 exemptions, no real audits yet) | `firmware-rs/supply-chain/` |
| Reproducible build | **Partial**: identical from a fixed source path; differs across paths (cargo metadata of out-of-workspace path deps); bootloader reproducible anywhere | `repro-build.sh`, `supply-chain/results/repro-build.txt` |
| SBOM | **I** (generator, CycloneDX) | `sbom.sh` |
| Actions pinned by SHA | **O** (could not be resolved without API access; checker job fails until done) | `check-action-pins.sh`, FINDING-012 |
| Pinned toolchain | **P** (file text in proposal 08; not created to avoid disturbing other agents) | `proposals/08` |
| Signed releases (sigstore + minisign) | **P** | `proposals/08` s.5 |

## 8. Residual risks that this repository does *not* close (state plainly)
1. L1-L3 hardware is a design; none of it has been fabricated or measured. The claim "fully attacker-controlled firmware is bounded by hardware" is **not yet true** and becomes true only with L5.
2. No code has run on a target (`stubs.md`): timing, TPL5010 handshake, MPSL flash timeslots are unverified, and a security argument that depends on them is conditional.
3. Closed-source BLE controller (FINDING-013) and the Apple platform are trusted.
4. The symbolic models assume ideal primitives, no low-order points, perfect RNG; computational issues (nonce reuse, timing) are covered by tests/proposals, not by the proofs.
5. Link-layer pairing is Just Works; privacy and DoS at the radio level are only partially mitigated (`proposals/06`).

## 9. Weakness register (the findings; reproductions run in this repository)

(A standalone `security/THREAT-MODEL.md section 9` was requested but the authoring tool refused to create files with that name in this pass, so the register lives here and in the hand-over message; the CI and test comments refer to it by ID.)

| ID | Title | Severity | Status | Reproduction | Fix |
|---|---|---|---|---|---|
| FINDING-001 | Reflected pod->phone responses authenticate, bypass replay, refresh the comm heartbeat, and cause AES-CCM nonce reuse under `key_p2c` | Medium (bench) | Open | `security/verify/tests/finding_001_reflection.rs`; ProVerif `-DREFLECT` reachable | proposal 01 s.1 |
| FINDING-002 | OOB pairing code is guessable offline (only in HKDF salt, confirm tag visible); the test-vector code `123456` falls in 2 s | High for the documented OOB mitigation | Open | `security/poc/oob_offline_guess.py`; ProVerif weak secret false | proposal 02 |
| FINDING-003 | "15 U per rolling hour" is 60 wall-clock buckets; a real 59-minute window can contain 16.7 U | Low | Open | `safety_props.rs::finding_003_*` (tight bound proven by `p3`) | proposal 07 s.5 |
| FINDING-004 | One pending handshake: anyone knowing the cleartext `PS_ID` can displace the phone's handshake | Low-Medium | Open | `handshake_props.rs::known_issue_pending_slot_*` | proposal 03 s.5 |
| FINDING-005 | `PS_ID` static 4-byte identifier in cleartext in every `SESSION_INIT` | Low (privacy) | Open | `handshake_props.rs::known_issue_ps_id_*` | proposal 03 s.5.4, 06 |
| FINDING-006 | DFU manifest: no version/rollback, no product/profile binding; `format`/`reserved` unsigned; parser not directly fuzzable | Medium | Open | fuzz `dfu_manifest`; `bootloader/src/main.rs::check_pending` | proposal 04 |
| FINDING-007 | `heapless 0.8.0`: 9 RustSec advisories (2026-11-18/19, fixed >= 0.9.4), none reachable | Low | Triaged | `cargo deny` / `cargo audit` | proposal 08 SC-3 |
| FINDING-008 | `trouble-host` -> `p256 0.13.2` -> `crypto-bigint 0.5.5`: RUSTSEC-2026-0387 timing in LESC ECDH | Medium (link layer) | Open, upstream | `cargo deny --manifest-path firmware-rs/openpatch-bench/Cargo.toml check advisories` | proposal 03 s.6 |
| FINDING-009 | TOFU pairing: PS secrecy/agreement falsified formally | High (bench) | Open by design | `security/formal/results/pairing_tofu.tamarin.txt` | proposal 02 |
| FINDING-010 | PS and bond keys plaintext in flash; APPROTECT never enabled | Medium bench / High product | Open | `docs/04-protocol.md` s.8.3 | proposal 03 |
| FINDING-011 | Swift AES-CCM: table based, hand written, not constant time | Medium | Open | `SessionCrypto.swift` | proposal 01 s.2 |
| FINDING-012 | `pages.yml`: actions on mutable tags, workflow-level `pages: write`/`id-token: write` | Low | Open (file not ours) | file | proposal 08 SC-6 |
| FINDING-013 | Closed-source BLE controller blobs reported unlicensed by cargo-deny | Info | Accepted | `cargo deny` | proposal 08 s.7 |
| FINDING-014 | Hardware: no per-hour dose bound independent of firmware; HW-A budget is per arm window and re-armable | High (architecture) | Open | section 4 | proposal 07 s.4 |

Fuzzing outcome: 7 targets, 300 s each, **0 crashes / timeouts / property violations in 26.5 M executions** (`security/fuzz/results/2026-11-19-run1.txt`).
Not findings (checked): low-order DH keys rejected; wrong `PS_ID` yields no verifier; keys installed only after confirmation; forward secrecy; frame bit-flip rejection; limits hold for arbitrary sequences (even with an adversary acknowledging every fault).
