# Proposal 05: Tamper-evident, hash-chained fault and delivery log

Status: proposed, **not implemented**. Priority **P1**. Another agent is concurrently changing the diagnostic records of `firmware-rs` core (`docs/06-diagnostics.md`, new tags 0x27-0x2F, commands 0x10-0x12): this proposal is written as an **additive layer** on top of whatever record format lands there, and must be reconciled with that owner before implementation.
Evidence: `firmware-rs/openpatch-core/src/log.rs` (event log, ids, `GetHistory`), threat model repudiation/tampering rows (`security/THREAT-MODEL.md`).

## 1. Why
A pod that delivered something unintended must leave evidence the attacker cannot rewrite silently, and a *compromised phone* must not be able to hide or forge history. Today the log is a ring buffer served over `GetHistory` with sequence ids; nothing proves it is complete or unmodified (a phone that is the only reader can show the clinician anything; an attacker with flash write can edit it). Required by the product intent ("every claim verifiable") and by AAMI TIR57 / FDA 524B expectations on logging and audit.

## 2. Design
### 2.1 Hash chain over event records
For event `i` with canonical bytes `rec_i` (id, uptime, type, argument fields as defined by the diagnostics owner, fixed-width little endian):
```
h_0 = HMAC-SHA256(K_log, "OPENPATCH/LOG/1 genesis" || pod_serial || boot_epoch)      (K_log = HKDF(device secret, "log"); device-local)
h_i = SHA-256( "OPENPATCH/LOG/1 link" || h_{i-1} || rec_i )                             (16-byte truncation stored per record, full 32 in checkpoints)
```
Each stored record carries `h_i[..8]`. Truncation to 64 bits is enough *per link* because the chain, not any single tag, gives integrity; checkpoints use the full hash.
- **Checkpoint record** every 32 events and at every state change that matters (suspend/resume, fault latch, pairing, DFU, reset): `CHK{ id, full h_i, counter_monotonic, uptime }`.
- **Signed checkpoints for off-pod verification**: the pod can MAC checkpoints with `K_log`, but a verifier needs the *pod identity key* of proposal 02 to check authenticity without a shared secret: `sig = Ed25519(sk_pod, "OPENPATCH/LOG/1 chk" || serial || id || h_i || counter)`. Signing costs ~ms; sign only every 256 events and on fault. Before proposal 02 exists, the MAC with `K_log` (verifiable only with the pod, e.g. on the bench via a `VerifyLog` command) is the stage-1 deliverable.
- **Gap detection**: ids are consecutive; a missing id or a hash mismatch is `LOG_BROKEN` and is itself logged in the next chain (the break is visible forever).
### 2.2 Ring buffer without losing evidence
The log is a ring; overwriting the oldest events is allowed, but the **chain anchor moves forward**: when events `0..k` are evicted the pod stores `(k, h_k)` in the anchor record; verification starts from the anchor. Eviction is logged. Verification property: from any anchor and the following records, a verifier recomputes the chain and checks every checkpoint signature.
### 2.3 What is logged (minimum set for security)
Pairing opened/closed/succeeded/refused, session established/failed (reason code, counts: not PS_ID), replay/auth failures (rate-limited summary records so a flood cannot evict real history: aggregate counters per minute), every dose command accepted (type, amount, source session id counter), every limit trip (`LIMIT_EXCEEDED`, hourly), fault latch/ack, suspend/resume, DFU events (version before/after, security_version), debug-port-open detection, boot reason (watchdog/brownout/power-on), RNG health failure, time set.
### 2.4 Reading
`GetHistory` gains `FROM_ID` chain proofs: response carries `prev_hash` for the first returned event so the phone can verify continuity without trusting the pod's framing; the phone verifies the chain and **stores checkpoints in its own database** (and Nightscout via Trio as `Pump event` notes): a second independent copy detects pod-side rewrites since the last sync (the pod cannot produce a different chain consistent with a checkpoint the phone already holds).
### 2.5 Flash write endurance and power loss
Append-only records written with the existing sequential-storage pattern; the chain value of the last record is recomputed at boot from the last checkpoint + trailing records, so a torn write is detected (CRC) and dropped, and the next record chains from the last intact one with a `TORN` marker.

## 3. Limits (state them in the doc)
A hash chain proves *internal consistency*, not that nothing was deleted at the *end* (tail truncation) unless an independent party saw a later checkpoint: hence the phone-side checkpoint copy and monotonic counter. An attacker with full flash write can rebuild the chain only if they hold `K_log` / `sk_pod`; with APPROTECT on and keys in KMU (Rev B) they do not.

## 4. Test plan
- Unit/proptest in `openpatch-core`: append N events with arbitrary eviction, verify from the anchor: always valid; flipping any bit / deleting any record in the middle / reordering / duplicating: verification fails at the first affected record.
- Torn-write fuzz: truncate the byte stream at every position; recovery yields a valid chain prefix.
- Fuzz target `log_chain_verify` (new): arbitrary bytes into the verifier never panic.
- Kani: `verify_chain` loop invariants for a bounded N (e.g. 8 records): `valid => each h_i equals the recomputation`.
- Integration: phone-side verification test vectors shared Rust/Swift (`docs/vectors/log-chain.json`).
- Flash budget: measure the record size growth (+8 bytes/record, +40 per checkpoint) against the STORAGE page budget; the owner of `storage.rs` signs off.
