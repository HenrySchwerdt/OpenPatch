# Proposal 03: Key storage at rest, debug lock, RNG, handshake rate limiting and pending-slot hardening

Status: proposed, **not implemented**. Priority: P0 for APPROTECT/debug lock and the pending slot, P1 for encrypted PS, P2 for KMU (Rev B).
Evidence: `docs/04-protocol.md` section 8 items 3, 4, 6; `firmware-rs/openpatch-bench/src/storage.rs` (PS record 33 bytes plaintext, BLE bond LTK/IRK plaintext); FINDING-004, FINDING-005, FINDING-008.

## 1. Assets in flash today (plaintext)
| Record | Content | Impact if read out |
|---|---|---|
| key 6 `PS` | 32-byte pairing secret | impersonate the phone *for the pod* (full dose authority within pod limits); old recorded sessions stay safe (ephemeral DH) |
| keys 16..19 | BLE bond: LTK, IRK | link-layer impersonation, tracking of the phone's RPA |
| key 4 | drive calibration | integrity only (CRC + preset equality) |
| bootloader pubkey | public | none |
| *(future)* identity private key (proposal 02) | Ed25519 seed | clone the pod |

## 2. Debug and read-out protection (P0, small)
1. **Enable APPROTECT** (UICR) on every non-bench-debug build. The exact register encoding and the extra *soft-APPROTECT* handling the firmware must perform at boot differ by nRF52840 silicon revision: follow Nordic's current errata / migration note for the revision actually used (to be recorded in `docs/boards.md`); this proposal deliberately does not hard-code values. Without it the whole flash, including PS, is readable via SWD in seconds with a cheap probe.
2. Add a **build profile `production`** that: sets APPROTECT, disables the `dev-plaintext` feature (compile_error if both), asserts at boot that APPROTECT is active (`FICR`/`UICR` read) and **refuses to deliver** otherwise (`Fault::DEBUG_OPEN`, logged in the tamper-evident log of proposal 05).
3. The nRF52840 has **no secure key storage**; APPROTECT + (optionally) `ERASEALL`-only recovery is the best available. Be explicit in documentation: a physical attacker with *glitching equipment* (voltage/EM fault injection on the APPROTECT check, a published class of attacks on nRF52 devices) can still extract flash. Rev A is a bench device; Rev B (nRF54L15) must use the **KMU** (Key Management Unit) + TrustZone-M so keys are never in readable flash, and CRACEN for crypto.
4. Test: `scripts/check-approtect.sh` reads UICR through probe-rs, expects `APPROTECT` set and `probe-rs read` of flash to fail; run in the release checklist and as a hardware-in-loop step when one exists. Until then the SCORECARD marks this "proposed".

## 3. PS encrypted at rest (P1)
Goal: a *flash dump without the MCU running* (cold-boot chip-off, partial glitch) does not yield PS.
- Derive a **device-unique storage key** `K_store = HKDF(FICR.DEVICEID(8 B) || UICR.customer[0..16] random 128-bit written once at provisioning, label)`. On nRF52840 FICR.DEVICEID is not secret, so the secret part is the provisioning-time random in UICR (also readable without APPROTECT, but it is in a different region than the PS record and chip-off needs both: this raises the bar from *one* record to *two* regions + the HKDF design, it is **not** a strong barrier, state so in the doc).
- Better on nRF52840: **CC310 key store** (`nrf_cc3xx` "hw unique key", HUK) if the vendor library is accepted (binary blob, `unsafe` FFI, consider only if the threat model for Rev A includes chip-off; bench pods do not).
- Rev B: store PS (and identity key) as **KMU keys**; the firmware never sees them, only a key slot id.
- Record format v2: `version(1) | nonce(12) | AEAD(ChaCha20-Poly1305, key=K_store, aad=record_key||version)(PS) | tag(16)`; nonce = monotonic write counter (stored in the same record) so a rollback of the flash record to an older PS is **detected as stale** only together with proposal 04's counter.
- Honest scope statement: for Rev A this is defence in depth against casual flash dumps and *accidental* leakage (backups of flash images, factory images); it does not stop a motivated physical attacker.

## 4. RNG
Today: ChaCha20 DRBG seeded **once per boot** from the TRNG (`firmware-rs/openpatch-bench/src/main.rs`); no reseed; boot-time seed failure undetectable.
1. **Reseed** the DRBG from the TRNG every `min(1 hour, 2^20 outputs)` and mix `Instant::now()` + battery ADC LSBs + BLE RSSI jitter as *additional* (never sole) input. Document that the RNG feeds: ephemeral X25519 secret, nonces, (proposal 02) the K_oob and identity key generation.
2. **Health tests on the TRNG seed** (SP 800-90B style): repetition-count and adaptive-proportion test on the first 4 KiB of raw TRNG output at boot; on failure do not start the BLE stack for pairing/sessions and latch `Fault::RNG`. nRF52840's TRNG has its own bias correction; the tests catch stuck-at after damage/glitch.
3. **Fork-resistant**: draw the ephemeral secret via `rng.fill_bytes` *after* mixing in the connection counter (the DRBG state is advanced by every call anyway; a test pins that two consecutive handshakes never reuse an ephemeral).
4. **Provisioning keys are generated on the station's HSM**, not on the pod, when the pod RNG health cannot be attested (decision for proposal 02).
5. Tests: unit test with a stuck TRNG mock (all zeros, repeating) asserts refusal; proptest asserts reseeding never reduces entropy input; the existing handshake tests keep a deterministic RNG only in `#[cfg(test)]`.

## 5. Handshake DoS, pending slot, rate limiting (P0)
Findings: FINDING-004 (any in-range peer that knows the cleartext `PS_ID` can displace the phone's pending handshake) and the X25519-per-INIT CPU cost.
1. **Per-connection pending slots + owner binding**: a `Pending` belongs to the *BLE connection handle* that created it; INIT on connection X cannot replace pending on connection Y. Since one peer connects at a time, the practical effect is: a *second* central cannot interfere with the first (the pod accepts one connection at a time, so also enforce `max_connections = 1` at the BLE layer and reject others before the application sees data).
2. **INIT rate limit** (token bucket in the BLE task): at most 4 INITs/10 s per connection and 20/min globally; excess is dropped without a response (no oracle). After 8 failed FINISH (bad confirm) in 5 min: exponential backoff 1 s .. 5 min on session handshakes and a log entry (proposal 05). In the pairing window the pairing path is already single-shot per button press.
3. **Cheap checks first**: verify `PS_ID` (4 bytes, no EC) before X25519 (already so for sessions); add an HMAC-based **stateless cookie** (QUIC retry / DTLS HelloVerify style) *only if* measurements show the X25519 cost matters: per INIT ~ 0.3-0.5 s on soft X25519 on a 64 MHz M4 (measure; the nRF52840 CC310 can do it in ms but is a blob). Until measured, rate limiting is sufficient.
4. **Hide `PS_ID`** (FINDING-005): replace the static 4-byte identifier by an **epoch-keyed tag**: `PS_ID_t = HMAC(PS, "ps-id" || connection_counter_hint)[..4]` where the phone and pod both know a monotonically stored `session_counter` (pod stores it with the seq ceiling). A pod checks the current and next 8 counters. Static identifier removed; tests: two sessions never show the same `PS_ID`.
5. **Handshake and safety separation**: handshake work stays in the BLE task, never in the safety task (already so); add a CI assertion in `openpatch-bench` build.rs that the handshake module is not referenced from the safety task (compile-time `mod` visibility test).

## 6. Dependency finding to fix here (FINDING-008)
`trouble-host 0.8.0` pulls `p256 0.13.2` -> `crypto-bigint 0.5.5`, which carries **RUSTSEC-2026-0387** (secret-dependent branches in constant-time operations) in the LE Secure Connections ECDH path of the pod. Mitigations, in order: bump `trouble-host`/`p256`/`crypto-bigint >= 0.7.6` when released; until then record the exposure (link layer only, the application layer does not use P-256) and keep the advisory in the deny.toml *triage list with a review date* once decided. Because the application layer does not depend on the LESC secret, this does not break the session keys, but it weakens link-layer confidentiality against a *local* observer of power/EM or timing.

## 7. Test plan summary
- Unit/proptest: record AEAD round trip, wrong key/aad fail, flash-rollback detection (with proposal 04).
- Fuzz: `storage_records` target is extended to the encrypted record parser once it exists (and the codec moves to a library crate).
- Property: rate limiter never produces a response beyond the budget (proptest on token bucket with arbitrary time sequences, Kani for the arithmetic).
- Hardware: APPROTECT check script; TRNG stuck-at injection with a mock.
