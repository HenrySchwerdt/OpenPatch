# OpenPatch protocol v1.1: application layer session key agreement (section 5.2)

> **TEST PROJECT. Not a medical device, never to be worn or used with insulin on a person** (see `DISCLAIMER.md`).
> This document closes the open point of protocol v1, section 5.2 / 9.1 ("key agreement and pairing flow"). It is the
> normative text for the key agreement. Everything else (frame format, TLV, commands, error codes, AES-CCM frame
> protection, `seq` rules) stays as in [`firmware/docs/openpatch-protocol.md`](../firmware/docs/openpatch-protocol.md), which is the
> frozen C reference and is deliberately not edited. Where the two documents differ on key material, replay state or
> `SESSION`, **this document wins**.
>
> Implementations: Rust pod side `firmware-rs/openpatch-proto/src/handshake.rs` (+ glue in `firmware-rs/openpatch-bench`), Swift phone
> side `ios/OpenPatchKit/OpenPatchCore/Sources/OpenPatchCore/SessionHandshake.swift`. Both are checked against the shared test
> vectors [`docs/vectors/session-key-agreement.json`](vectors/session-key-agreement.json), which are also re-derived by an independent
> Python script (`docs/vectors/verify.py`).

## 1. Goal and threat model (H7)

Hazard H7 in `docs/02-safety.md`: *unauthorized access, attacker via BLE*. Mitigation required there: pairing with key exchange (X25519),
AES-CCM, no unauthenticated bolus command, pairing only after a button press on the pod.

The BLE link layer (LE Secure Connections, Just Works) is **not** enough: Just Works has no MITM protection, bonds can be created by anybody in
range during the pairing window, and every app on the phone that talks to the bonded pod would be authorised. The application layer therefore
adds its own, independent authentication and encryption.

| Attacker | Capability | What stops them |
|---|---|---|
| Passive eavesdropper | sees all BLE traffic, even if the link layer is broken | session keys derive from an ephemeral X25519 secret **and** the pairing secret; traffic is AES-CCM encrypted. Past sessions stay secret even if `PS` leaks later (ephemeral DH, forward secrecy for sessions). |
| Active attacker in range, never paired | connects, sends commands, replays recorded frames | plaintext is refused (`AUTH`); without `PS` nobody can pass the key confirmation; recorded frames are bound to a session key that no longer exists; handshake frames cannot displace a running session without proving `PS`. |
| Active MITM **during the pairing window** | relays/modifies the unauthenticated pairing exchange | **Not prevented by the key exchange alone**: the first pairing is trust-on-first-use, exactly like Just Works. It is limited by the physical authorisation (button press, 60 s window, one application pairing per press) and, if used, by the optional out-of-band code (section 4.3), which makes the first pairing authenticated. Residual risk is documented in section 8. |
| Attacker with a recorded session | replays commands later or on another connection | per-connection keys + strictly increasing `seq` inside the session (section 6). |
| Attacker who has the phone | uses the app | out of scope of the protocol: `PS` lives in the iOS Keychain (this device only); revoke by pairing the pod again with the button. |
| Attacker with physical access to the pod | reads flash | out of scope: `PS` is stored unencrypted in the pod's flash (nRF52840 APPROTECT must be enabled for anything beyond the bench). |
| Jamming / handshake flooding | denial of service | out of scope (BLE is a best effort radio); a flood cannot replace a running session, only costs the pod CPU time (one X25519 per INIT, in the BLE task, never in the safety task). |

Not a goal: protecting against a compromised phone app or against a person with the pod in their hand who presses the button.

## 2. Primitives

| Purpose | Algorithm |
|---|---|
| Key agreement | X25519 (RFC 7748). A peer public key that yields an all-zero shared secret (low-order point) aborts the handshake. |
| Key derivation | HKDF-SHA256 (RFC 5869) |
| Transcript hash | SHA-256 |
| Key confirmation | HMAC-SHA256, truncated to 16 bytes, compared in constant time |
| Frame protection | AES-128-CCM, M = 8, L = 2 (unchanged from section 5.1 of v1) |

Randomness: the pod draws the ephemeral secret (32 bytes) and the nonce (16 bytes) from a ChaCha20 DRBG that is seeded once per boot with 256
bit from the nRF52840 TRNG; the phone uses the system CSPRNG. In that order (secret, then nonce).

Rust (no_std, no alloc, no unsafe): `x25519-dalek 2` (default features off), `hkdf 0.12`, `hmac 0.12`, `sha2 0.10`, `subtle`, `aes`/`ccm`.
Swift: CryptoKit on Apple platforms, swift-crypto (`Crypto`) elsewhere; AES-128-CCM is implemented in OpenPatchCore on top of a small AES block function because neither
library exposes CCM.

## 3. Wire format of the handshake

Handshake messages are ordinary frames (header, TLV payload, CRC-16, section 2 of v1) with `flags = 0` (request) or `flags = RESPONSE`
(response) and **without** the `encrypted` flag. They carry no AES-CCM tag: their integrity comes from the key confirmation tags. `seq` of a
handshake frame is only echoed by the response (the phone uses 0 for INIT and 1 for FINISH) and takes no part in the replay state.

| Type | Name | Direction |
|---|---|---|
| `0x40` | `PAIR_INIT` | phone -> pod; response `0xC0` |
| `0x41` | `PAIR_FINISH` | phone -> pod; response `0xC1` |
| `0x42` | `SESSION_INIT` | phone -> pod; response `0xC2` |
| `0x43` | `SESSION_FINISH` | phone -> pod; response `0xC3` |

(`0x0F` is already taken by the Rust `FillDraw` extension, `0x90` by Alert notifications.)

| Tag | Name | Length | Content |
|---|---|---|---|
| `0x01` | `RESULT` | 1 | as in v1 section 4 |
| `0x30` | `EPH_PUB` | 32 | X25519 public key (RFC 7748 u-coordinate) |
| `0x31` | `NONCE` | 16 | random |
| `0x32` | `CONFIRM` | 16 | key confirmation tag |
| `0x33` | `PS_ID` | 4 | identifier of the pairing secret (`SESSION_INIT` only) |

Messages (A = phone/app, B = pod):

```
INIT request    A -> B   EPH_PUB(pubA)  NONCE(nonceA)  [PS_ID, session only]
INIT response   B -> A   RESULT  EPH_PUB(pubB)  NONCE(nonceB)  CONFIRM(confirm_pod)
FINISH request  A -> B   CONFIRM(confirm_app)
FINISH response B -> A   RESULT
```

`RESULT` codes (numbering of v1 section 4): `OK` 0; `BAD_ARG` 1 (low-order key); `FRAME` 10 (malformed TLV or lengths);
`AUTH` 14 (pairing window closed, or wrong confirmation tag); `SESSION` 18 (FINISH without a matching INIT);
`PAIR` 22 (no pairing secret on the pod, or `PS_ID` mismatch: pair again). Frames with a bad CRC or version, with the `encrypted` flag set, or of another type are dropped silently.

## 4. Key schedule

All strings are ASCII, `||` is concatenation. Labels carry the protocol version (`OPENPATCH/1`).

```
dh          = X25519(ephemeral_secret_self, eph_pub_peer)                (32 bytes, must not be all zero)
ps_id       = HKDF-Expand(prk = PS, info = "OPENPATCH/1 ps-id", L = 4)
th          = SHA-256( "OPENPATCH/1 transcript" || mode || ps_id || pubA || pubB || nonceA || nonceB )
                 mode  = 0x01 pairing, 0x02 session        ps_id = 00 00 00 00 for pairing
```

### 4.1 Pairing (creates the long-term pairing secret `PS`)

```
oob_salt    = 32 x 0x00                                   (no out-of-band code)
            | SHA-256("OPENPATCH/1 oob" || oob)           (with an out-of-band code)
prk         = HKDF-Extract(salt = oob_salt, ikm = dh)
okm         = HKDF-Expand(prk, info = "OPENPATCH/1 pairing" || th, L = 64)
PS          = okm[0..32]            confirm_key = okm[32..64]
```

### 4.2 Session (once per BLE connection)

```
prk         = HKDF-Extract(salt = PS, ikm = dh)
okm         = HKDF-Expand(prk, info = "OPENPATCH/1 session" || th, L = 68)
key_c2p     = okm[0..16]      AES-128 key for phone -> pod frames   (nonce direction 0)
key_p2c     = okm[16..32]     AES-128 key for pod -> phone frames   (nonce directions 1 and 2)
salt        = okm[32..36]     nonce prefix of this session
confirm_key = okm[36..68]
```

### 4.3 Key confirmation (both handshakes)

```
confirm_pod = HMAC-SHA256(confirm_key, "OPENPATCH/1 confirm pod" || th)[0..16]
confirm_app = HMAC-SHA256(confirm_key, "OPENPATCH/1 confirm app" || th)[0..16]
```

The transcript hash binds both ephemeral keys, both nonces, the mode and the pairing secret identity into everything that is derived, so a message
spliced from another run yields different keys and tags.

Optional out-of-band code (`oob`): a short secret both sides know before the radio exchange (for example printed on the pod, or a number the app reads from the pod's
bench log). It is mixed into `oob_salt`. If the two sides disagree, the confirmation fails. With an OOB code that an attacker does not know, the first pairing
is authenticated and a MITM in the pairing window cannot succeed. The bench pod defaults to none (`Responder::set_oob`).

## 5. Procedures

### 5.1 Pairing

1. The user presses the button on the pod. The pod opens the BLE pairing window (60 s, bonding) **and** the application layer pairing window (same 60 s, but it is **not** closed when the BLE bond is made, because the bond comes first and the application layer pairing follows on the encrypted link). One application layer pairing per button press.
2. The phone connects, bonds (link layer), sends `PAIR_INIT`.
3. The pod, only if the application window is open, draws `(secret_B, nonce_B)`, answers with `EPH_PUB`, `NONCE`, `confirm_pod`, and keeps the derived `PS` and `confirm_key` as *pending*.
4. The phone verifies `confirm_pod` (a wrong OOB code or an altered exchange fails here), sends `PAIR_FINISH` with `confirm_app`.
5. The pod verifies `confirm_app` in constant time and re-checks the window. Only then it stores `PS` (flash, record 6), closes the application window and answers `OK`. A new pairing replaces the previous `PS`; the old phone has to pair again.
6. The phone stores `PS` after the pod's `OK` (iOS Keychain, `ThisDeviceOnly`).

### 5.2 Session establishment (every connection)

1. A connection starts with **no** session keys on the pod. Every frame that is not a handshake frame is refused with `AUTH` (production). `GetStatus` is not an exception.
2. The phone sends `SESSION_INIT` with `PS_ID`. A pod without `PS`, or with another `PS`, answers `PAIR`.
3. The pod answers with its ephemeral key, nonce and `confirm_pod`, and keeps the derived keys as *pending*. A further INIT replaces the pending handshake, never the running session.
4. The phone verifies `confirm_pod`, sends `SESSION_FINISH` with `confirm_app`.
5. The pod verifies `confirm_app`. **Only now** does it install the new keys (a new `Session`, sequence state reset) and answer `OK`. A wrong tag answers `AUTH`, discards the pending handshake and leaves the running session untouched, so an attacker who only knows the (public) `PS_ID` cannot kick the phone out.
6. The phone installs the same keys on receipt of `OK`. From then on all commands carry `flags.encrypted`.
7. When the link closes, the pod erases the session and half-open handshakes. Session keys never outlive a connection.

## 6. Frame protection and replay state with the new keys

Frame format, AAD (the 7 header bytes) and the 13 byte nonce `salt(4) || dir(1) || seq(2, LE) || 0x00 x 6` are exactly as in v1 section 5.1. What changes:

* `salt` is the session's `salt` from the key schedule, no longer a constant.
* The AES key is selected by `dir`: `dir = 0` (commands) uses `key_c2p`, `dir = 1` (responses, echo of the command `seq`) and `dir = 2` (unsolicited notifications on the Alert characteristic, frame type `0x90`, the pod's own counter) use `key_p2c`. A frame cannot be reflected into the other direction (different key and nonce).
* **Nonce uniqueness**: a key is used for exactly one session; within a session `(dir, seq)` never repeats because command `seq` is strictly increasing and capped at `0xFFFE`.
* **Replay rules inside a session are unchanged**: command `seq` must increase strictly (gaps allowed), equal or lower -> `REPLAY` (dropped); state advances only after successful authentication; `seq = 0xFFFF` is reserved.
* **The sequence space is per session.** A new session starts with a fresh counter (the phone uses 1, the pod accepts anything above 0). The persisted `LAST_SEQ` ceiling (v1 section 5.2, 6.1) stays in the pod and in `GetStatus`, but it is no longer what protects against replays across connections or reboots: a frame of an older session fails authentication outright because the key differs. The v1 advice "start at last known + 16" is therefore only needed with the development key. Reaching `0xFFFE` is no longer terminal: the phone runs `SESSION_INIT` again (`SESSION` error handling).
* `GetStatus.LAST_SEQ` reports the highest `seq` accepted in the current session.
* Plaintext frames are never accepted in production. `dev-plaintext` builds still accept them and still start with the fixed, public development key; a phone that never runs the handshake sees the old behaviour, a phone that does gets negotiated keys for that connection.

## 7. How this addresses H7

| H7 requirement (`docs/02-safety.md`) | Where |
|---|---|
| Pairing with key exchange (X25519) | section 4.1 |
| AES-CCM | section 6, keys from section 4.2 |
| No unauthenticated bolus command | production pods accept no plaintext and no frame before a session exists; a session needs `PS` |
| Pairing only after a button press on the pod | the application pairing window (section 5.1) is opened only by the button; the pod refuses `PAIR_INIT` / `PAIR_FINISH` outside it |

## 8. Known limits and open risks

1. **First pairing is trust-on-first-use** unless the OOB code is used (section 4.3). An attacker who relays the first pairing during the 60 s window becomes the paired peer. Mitigations: button, short window, one pairing per press, link layer bonding (also Just Works), and the user sees that the real phone can no longer connect. A bench pod does not use an OOB code yet.
2. **No channel binding to the BLE bond.** `PS` is established inside the same button window as the bond, but it is not cryptographically tied to the link layer key (trouble-host and CoreBluetooth do not expose it). Compromise of the link layer alone never yields a session, because the application layer needs `PS`; the reverse is also true.
3. **`PS` at rest**: plaintext in the pod's flash and the phone's Keychain. Pod side needs APPROTECT / encrypted storage before anything but a bench pod. A flash read-out reveals `PS` and allows impersonation of the phone, but still not decryption of recorded sessions (ephemeral DH).
4. **Pod RNG**: a ChaCha20 DRBG seeded once per boot from the TRNG (no reseed during a boot). A boot-time seed failure is not detectable in software.
5. **Swift AES** is a table based software implementation (no constant-time guarantee); it runs on the phone only. The pod uses the RustCrypto `aes` crate (software, table or fixslice depending on the target).
6. **DoS**: a nearby attacker can make the pod burn CPU with INIT frames (one X25519 each, in the BLE task) and, while the pairing window is open, can occupy the pending slot. A running session is never affected.
7. No hardware testing yet (nothing here has run on an nRF52840 or an iPhone).

## 9. Test vectors

`docs/vectors/session-key-agreement.json` (hex strings) contains: RFC 7748 X25519, RFC 5869 HKDF and RFC 3610 AES-CCM known answers (to guard the primitives on both sides), two complete pairing runs (without and with OOB code, all four frames), one complete session run that uses the `PS` of the first pairing, four encrypted frames (command, command, response, notification, with `dir` 0/0/1/2), and the low-order public keys that must be rejected.

* Generated by `firmware-rs/openpatch-proto/tests/handshake.rs` (`OPENPATCH_WRITE_VECTORS=1 cargo test -p openpatch-proto --features key-agreement --test handshake`); the test fails if the committed file is stale.
* Consumed by the Swift suite (`SessionHandshakeTests`): the Swift initiator, fed with the same secrets, must produce the same requests, keys and encrypted frames byte for byte, and must decrypt the Rust pod's responses and notification.
* Re-derived independently by `python3 -I docs/vectors/verify.py` (`cryptography` package).
