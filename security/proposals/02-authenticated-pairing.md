# Proposal 02: Authenticated pairing by default (no TOFU): device identity, OOB/QR, PAKE, certificate chain, revocation

Status: proposed, **not implemented**. Priority **P0**: the formal analysis shows the current pairing has no authentication at all, and the optional OOB variant is weaker than the documentation suggests.
Evidence: `security/formal/results/pairing_tofu.tamarin.txt` (PS secrecy and agreement **falsified**), `pairing_oob.tamarin.txt` (verified for a high-entropy code), `pv_pairing_weak.proverif.txt` (low-entropy code **guessable offline**), `security/poc/oob_offline_guess.py` (recovers the documented example code `123456` from one recorded pairing in 2 s), FINDING-002.

## 1. Problem statement

1. **TOFU (default today)**: PS = f(X25519 DH, transcript) with no authentication. Anybody who completes `PAIR_INIT` while the 60 s window is open becomes the paired peer; an active relay becomes a man in the middle. The pod has no identity the phone can verify. The BLE link layer is LESC Just Works (no MITM protection) so it does not help.
2. **The optional OOB code is mixed in the HKDF *salt* only (`oob_salt`)**. `confirm_pod` in the INIT response is `HMAC(confirm_key(dh, salt, th), ...)`. An attacker who runs one `PAIR_INIT` with its own ephemeral key knows `dh`, `th` and `confirm_pod`, so every candidate code is testable **offline** (FINDING-002). A 6-digit code (as in the test vector) falls in seconds; a 10-character alphanumeric code in minutes on a GPU. The documentation's claim "an attacker that does not know the code cannot succeed" is only true for >= 128-bit codes.
3. **No per-device identity**: a counterfeit pod, a cloned pod or a pod whose PS was extracted cannot be distinguished from the real one; no revocation exists.

## 2. Design

### 2.1 Per-device identity key, provisioned at manufacture
- Each pod gets an **Ed25519 identity key pair generated inside the MCU** (nRF52840: RNG + CC310 or software; nRF54L15 Rev B: KMU, non-exportable) at the **provisioning station**, never outside. The private key never leaves the pod. Only the public key `PK_pod` and a serial number leave.
- The provisioning station (an air-gapped Linux box with a hardware token) signs a **device certificate** `cert = Sig_CA(serial || PK_pod || hw_rev || not_before || not_after || flags)` (Ed25519, 120 bytes) and writes it to the pod (UICR/flash, read-only after lock).
- **Chain**: `Root CA (offline, 2 of 3 split, in a safe)` -> `Provisioning CA (online only on the station, 12 month validity)` -> `device cert`. The phone ships with the Root CA public key *and the next-root key hash* (so a root rollover can be shipped in an app update). Max chain depth 2 keeps the cert a few hundred bytes.

### 2.2 Printed/QR out-of-band secret with enough entropy
- At provisioning the pod generates a **128-bit random pairing code `K_oob`**, stores `SHA-256(K_oob)` only, and exports `K_oob` once to the label printer: QR code (`openpatch://pair?v=2&sn=<serial>&k=<base32 of K_oob>&fp=<first 8 bytes of SHA-256(PK_pod)>`) plus a human-readable Crockford-base32 line for manual entry (26 characters; typing is feasible for a test project, and for a product the QR is the path).
- Scanning the QR gives the phone **both** `K_oob` and a fingerprint of `PK_pod` over a channel the radio attacker cannot see (visual, short range). That is the authentication anchor.
- The code is single-use per factory state: a factory reset (button hold + physical access) generates a new `K_oob` and invalidates the old label; the pod then displays nothing, so after a reset the label must be re-printed or the pod uses the user-visible "pairing display" fallback (7 flashes pattern = 2.3 bits: not enough, so a reset pod **requires re-provisioning**; documented trade-off: no way to convert a stolen pod to a clean one without the station).

### 2.3 Handshake: authenticated, PAKE-shaped, no offline test
Replace "OOB in the salt" by a PAKE-style construction so a captured transcript carries no verifier for low-entropy codes, and still bind the certificate:

1. Phone -> pod `PAIR_INIT`: `EPH_PUB(A)` with `A = X25519(a, G_oob)` where **`G_oob = HashToCurve(K_oob)` (CPace, draft-irtf-cfrg-cpace, Ristretto255 or X25519 variant)**. For a 128-bit `K_oob` plain salt mixing would also be safe; CPace is chosen because it keeps the scheme safe if a future product shortens the code. ProVerif shape check: `pv_pairing_cpace.proverif.txt` (weak secret **not** guessable offline, PS secrecy and injective agreement verified; equation restricted to generator-derived bases).
2. Pod -> phone: `B`, `nonce`, `cert`, `sig = Ed25519(sk_pod, "OPENPATCH/2 pair-id" || th)`, then `confirm_pod`. The phone verifies `cert` against the pinned root (chain, validity, revocation list version, `hw_rev`), **checks `SHA-256(PK_pod)` equals the fingerprint from the QR**, verifies `sig` over the transcript. Only then it sends `confirm_app`.
3. PS = HKDF(dh, th, K_oob-derived salt) as today. PS is bound to `PK_pod` (included in `th`), so the phone's stored pairing is `(PS, PK_pod, serial)`; a different pod cannot satisfy a later session (`PS_ID` check plus identity in the transcript).
4. **Which party authenticates whom**: the pod authenticates the phone through possession of `K_oob` (physical access to the label); the phone authenticates the pod through the CA chain + fingerprint. That is **mutual** authentication; neither relies on the radio channel.
5. The physical button window stays (defence in depth, one pairing per press), as does link-layer bonding. The channel binding to the BLE bond is still absent (trouble-host does not export it); the app layer does not rely on the link layer.

### 2.4 Revocation
- **Pod certificates are short-lived relative to the device life**: `not_after = manufacture + 18 months` (pods live 48 h in the field; a bench pod is a fixed device); an expired cert is a warning on a bench pod, a refusal for a pod with `flags.production`.
- **Revocation list (CRL) signed by the provisioning CA**: `{version, serial ranges, not_after}` shipped inside the iOS app (updated through the normal app update channel and a signed `crl.json` fetched at pairing time from the project's static site; the phone caches it and refuses to **pair** (not to continue an existing session) with a revoked serial). A stale CRL (> 90 days) produces a pairing warning, not a hard failure (offline phones).
- **Compromised provisioning CA**: root signs a new provisioning CA, revokes the old by serial range; phones accept only certs of CAs in the current root-signed `ca-set` (version monotonic, stored in Keychain: anti-rollback).
- **Pod-side**: the pod stores the highest accepted `crl_version` the phone presented (monotonic) and refuses a phone that proves possession of an older one only in `production` mode (a lost-phone scenario is covered by factory reset + re-pairing, not CRL).

### 2.5 Phone-side key protection (cross-reference)
PS lives in the Keychain with `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` and Secure Enclave wrapping (the 256-bit PS is wrapped with an SE P-256 key via ECIES; the SE key is non-exportable and requires device unlock; optionally `.biometryCurrentSet` for *pairing* operations only, not for every session).

## 3. Threat coverage
| Attack | Today | After |
|---|---|---|
| Radio MITM in pairing window | succeeds | fails (needs `K_oob` or the pod private key) |
| Offline dictionary on OOB | succeeds (FINDING-002) | n/a (128-bit code, PAKE) |
| Counterfeit/cloned pod | undetectable | fails (no valid cert / fingerprint mismatch) |
| Stolen pod re-sold | possible | needs the provisioning station |
| Lost-label attacker with physical access | n/a | can pair if they hold label + press the button; same as owning the device |
| Compromised phone app | out of scope | PS in Keychain/SE; see proposal 07 for dose limits |

## 4. Test plan
1. Tamarin: new `openpatch_pairing_v2.spthy.in` (identity key, cert verification, QR secret as `Fr` revealed only by explicit rule). Lemmas: `pairing_agreement_injective` (both sides), `ps_secrecy`, `pod_identity_binding` (a phone accepts only a pod whose `PK_pod` it scanned), `no_unknown_key_share`. Must verify with `-DOOB`-equivalent.
2. ProVerif: keep `pv_pairing_cpace` (weak secret true) and add `pv_pairing_v2` with weak `K_oob` + certificate signature; expectation `weaksecret true`.
3. Regression: `security/poc/oob_offline_guess.py` must exit **1** ("code NOT recovered") against v2 vectors; CI inverts its expectation once v2 is default.
4. Fuzz: new targets `cert_parse` (device cert + CRL parsers) and `pair_v2_responder`.
5. Hardware test: provisioning station script + `tools/provision` with a signed-cert golden file; pod boot refuses to enter pairing with no/invalid cert.
6. Counterfeit test on the bench: flash an unprovisioned pod, assert the app refuses.

## 5. Open points (need a decision, not invented here)
- Who runs the Root CA and where it is stored (offline; custodians). The project has no entity for this yet.
- Whether CPace or SPAKE2+ (RFC 9383) is used: CPace is smaller; SPAKE2+ is an RFC with published test vectors. Either way **use an audited library; do not implement the group arithmetic by hand** (`ristretto255` via `curve25519-dalek` is already a transitive dependency of the signing tool).
- Label/QR supply for 3D-printed/hand-assembled bench builds: a `tools/provision` script that prints the label on a thermal printer on the same station.
