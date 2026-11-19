# Proposal 01: AEAD replacement, direction-safe session layer, version negotiation and downgrade protection

Status: proposed, reviewed by the security owner, **not implemented** (this pass changes no protocol/crypto source). Hand to the owner of `firmware-rs/openpatch-proto` and `ios/OpenPatchKit/OpenPatchCore`.
Priority: **P0 for the session-layer defect (section 1), P1 for the AEAD swap (section 2).**
Evidence base: FINDING-001, FINDING-005 (`security/THREAT-MODEL.md section 9`), `security/verify/tests/finding_001_reflection.rs`, `security/formal/proverif/openpatch_session.pv.in`.

## 1. Fix first, independent of the cipher: the session layer reflects responses (FINDING-001)

`Session::open` (`openpatch-proto/src/session.rs`) takes `is_response` from the header flag, chooses the nonce direction and (in `AesCcm::cipher`) the AES key from it, and skips the replay check for responses. On the pod this means a pod->phone frame replayed to the pod authenticates, refreshes `comm_heartbeat()` and is answered with a *second* message under the *same* (`key_p2c`, nonce). Demonstrated on the real code.

Required change (cipher independent):

1. **Direction is a property of the receiver, not of the frame.** `Session` gets a `Role::{Pod, Phone}` at construction. A pod `open()` only ever decrypts with `key_c2p` and nonce direction 0; a phone `open()` only with `key_p2c` and directions 1/2. A frame whose RESPONSE flag does not match the role is rejected *before* any crypto (`Error::Frame`) and without side effects (no heartbeat, no response).
2. **The nonce direction is not taken from the wire at all.** Nonce = `salt(4) || dir(1, derived from role+type of counter) || counter(2 or 8)`. The header stays in the AAD, so tampering with the flag fails the tag.
3. **Counter separation**: pod->phone responses use the *pod's own* strictly increasing counter (echoing the command `seq` stays in the payload, not in the nonce). Then no function of attacker input can make the pod encrypt twice under one nonce. Add a hard invariant in `seal`: the encrypt counter must be strictly greater than the last one used for that key, else `Err` (a debug_assert is not enough: make it a latching fault).
4. `comm_heartbeat()` is called only after a frame passed role check, AEAD and replay check.

Test plan:
- Flip `security/verify/tests/finding_001_reflection.rs`: the three `known_issue_*` tests start failing (expected), un-ignore `fixed_*` and invert the others into regression tests.
- Re-run `security/formal/run.sh`: change the ProVerif `-DREFLECT` expectation (`pv_session_reflect`, query 7) from `false` to `true`; CI job `formal` enforces it.
- New proptest: for any interleaving of `seal`/`open` on both roles, no (key, nonce) pair is ever used for two different plaintexts (record nonces in a test `Ccm` wrapper, as in `finding_001_reflection.rs::Recording`).
- Fuzz: `firmware-rs/fuzz` target `session_open` gains a pod-role session and asserts the heartbeat counter is unchanged for every input that is not a valid command.
- Kani: harness `Session::open` role check (`security/verify/src/kani_proofs.rs`): `role == Pod && flags & RESPONSE != 0 => Err`.

## 2. Replace AES-CCM with an AEAD that has audited constant-time implementations on both ends

### Why change at all

| Concern | AES-128-CCM today | Impact |
|---|---|---|
| iOS side is **our own** CCM on a table-based AES (`SessionCrypto.swift`; CryptoKit has no CCM) | Cache-timing side channel on the *phone*: other apps on the same device can mount Flush+Reload/Prime+Probe class attacks on T-tables. The key protects dose authority. | Unaudited, non-constant-time, hand-written crypto on the dose-authority path. This is the single weakest crypto component. |
| 64-bit tag (M = 8) | 2^-64 forgery probability per attempt; fine for a link that needs ~2^20 attempts to matter, but below the 128-bit margin used everywhere else in the protocol | Acceptable, but free to improve |
| CCM needs two AES passes, no hardware offload in the Rust stack | Pod CPU/energy | Minor |
| 13-byte nonce / 2-byte counter in the frame | Rekey every 65 534 commands (acceptable) | Minor |
| Pod side `aes` 0.8 soft backend on Cortex-M4 is the bit-sliced *fixslice* implementation (constant time) | OK | Pod is not the problem |

### Candidates evaluated

| | ChaCha20-Poly1305 (RFC 8439) | AES-128-GCM | AES-CCM on nRF52840 CryptoCell-310 |
|---|---|---|---|
| iOS | **CryptoKit `ChaChaPoly`** (first-party, Apple-maintained, no custom code), swift-crypto elsewhere | CryptoKit `AES.GCM` (hardware AES on A-series) | not applicable (iOS side would still need CCM) |
| Pod, Rust | RustCrypto `chacha20poly1305` 0.10: pure Rust ARX, constant time by construction, no tables, `no_std`, no alloc, `forbid(unsafe)` compatible | RustCrypto `aes-gcm`: GHASH soft implementation is constant time (CLMUL-less `polyval` soft) but ~3x slower; needs the AES soft backend | Nordic `nrf_cc310` library: binary blob, hardware speed, but a closed component and a new `unsafe` FFI boundary in a `forbid(unsafe_code)` core; does not help the iOS side |
| Tag | 128-bit | 128-bit | 8-bit..128-bit configurable |
| Nonce misuse | catastrophic on reuse (as GCM, as CCM): handled by section 1 counters | catastrophic | same |
| Side channels | none inherent | GHASH soft ok | hardware, ok |
| Cost on Cortex-M4F @ 64 MHz | ~25-35 cycles/byte (no AES hardware) - frames are <= 244 bytes: well under 1 ms | ~60-90 cycles/byte soft | negligible |

**Recommendation: ChaCha20-Poly1305 end to end** (CryptoKit `ChaChaPoly` on the phone, RustCrypto `chacha20poly1305` on the pod). Rationale: it removes the only hand-written crypto in the system (the Swift CCM), both ends use maintained, constant-time-by-design implementations, the tag grows to 128 bit, and no binary blob or `unsafe` enters the pod. CryptoCell-310 stays an *optimisation* for later (key storage / RNG use of CC310 are separate, see proposal 03), not the AEAD choice.

Do **not** keep both AEADs long term: two ciphers double the audit surface. Keep AES-CCM only inside a bounded migration window (below).

### Frame/nonce layout (v2)

```
version=2 | type | flags | counter u64 LE (pod and phone each have their own, per key) | len u16 | ciphertext | tag(16) | crc16
nonce(12) = salt(4, from key schedule) || counter(8)        # direction is separated by KEY (key_c2p vs key_p2c), never by a nonce byte
AAD       = the 7+ header bytes incl. version, type, flags, counter, len
```
CRC16 stays outside the AEAD (link-level corruption check, as now). With 64-bit counters the 0xFFFE rekey cliff disappears; the phone still re-handshakes at 2^32.

## 3. Version negotiation and downgrade protection

Goal: introduce v2 without letting an attacker force v1 (AES-CCM, weaker, historical bugs) on a pod and phone that both speak v2.

1. `SESSION_INIT` (phone) carries `VERSIONS` (TLV 0x34): a bitmask of supported suites, e.g. `0x03` = {1: AES-CCM v1.1, 2: ChaChaPoly v2}. `SESSION_INIT` response carries `CHOSEN` (TLV 0x35): the highest common suite.
2. **Both lists and the chosen value are part of the transcript hash** (`th = SHA-256(label || mode || ps_id || pubA || pubB || nonceA || nonceB || versions_offered || versions_supported_by_pod || chosen)`). An attacker who strips v2 from the offer changes `th`, both confirmation tags fail, and the handshake aborts: downgrade is detected, not negotiated. (Tamarin lemma to add: `no_downgrade`: `AppUp(chosen = 1) ==> not (Ex v2 offered by both)`.)
3. Policy: a pod with `MIN_SUITE = 2` (the default from the day the iOS release ships v2) answers `PAIR`/`VERSION` to v1-only phones. The *pod's stored* `MIN_SUITE` is monotonic (can only be raised, stored with the anti-rollback counter of proposal 04), so a firmware downgrade cannot re-enable v1 silently.
4. Labels: `OPENPATCH/2 ...` for every HKDF/HMAC label of v2, so key material of v1 and v2 can never be confused (cross-protocol separation).
5. Pairing secret PS is unchanged across v1/v2 only if proposal 02 has not replaced it; if proposal 02 lands first, v2 is defined directly on top of the authenticated pairing and v1 is never offered to a new pod.

## 4. Migration plan

1. Land section 1 on v1.1 (small diff, P0).
2. Implement v2 behind a cargo feature `suite-chacha` in `openpatch-proto`, plus Swift `SessionHandshake`/`SessionCrypto` on CryptoKit. Shared vectors: extend `docs/vectors/session-key-agreement.json` with RFC 8439 known-answer vectors and two complete v2 sessions; `verify.py` re-derives them with `cryptography.hazmat...ChaCha20Poly1305`.
3. Differential test: Rust encrypt -> Swift decrypt and back for 10^5 random frames in CI (a Swift test reading a Rust-generated JSON file).
4. Bench pods flash `MIN_SUITE = 1` for one release, then `2`; delete `SessionCrypto.swift`'s CCM and the `aes`/`ccm` dependencies after one release (supply chain shrinks: `aes`, `ccm`, `cipher`).

## 5. Effort / risk
Section 1: 1-2 days incl. tests. Section 2-4: ~1 week incl. Swift, vectors, fuzz targets (`ccm_open` becomes `aead_open`). Risk: the `chacha20poly1305` crate must be pinned and added to the cargo-vet audits (proposal 08, SC-1).
