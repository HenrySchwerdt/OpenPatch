# Formal verification of the OpenPatch v1.1 handshake

TEST PROJECT, not a medical device. Models of `docs/04-protocol.md` (key agreement v1.1: X25519 + HKDF-SHA256 + key-confirmation HMAC, then AES-CCM frames).

## Run

Tools used (pinned): **Tamarin 1.10.0** (release binary, sha256 `538fe055b65f419aac4710015948f0e6a2253d2f61958c136e2d2bd67981028c`) with **Maude 3.2** (works, Tamarin prints a warning that 3.2.1+ is its tested list), **ProVerif 2.05** (source tarball sha256 `4871f53c32ab4a04669a060c4886ba5d9080496963fb980a9a62d2c429ceabc4`, built with `./build`, needs `ocaml-nox`).

```sh
export LC_ALL=C.UTF-8          # Tamarin prints unicode quantifiers
security/formal/run.sh         # regenerates variants, runs everything (~15 s), compares each result with its EXPECTED value
```
`run.sh` exits non-zero if any result differs from the expectation (attack expected, or property expected), so protocol, model or tool drift fails CI (`security-ci.yml`, job `formal`). Outputs (generated models, raw tool output) are in `results/`.
Templates are `*.in` with `#ifdef` variants expanded by `preprocess.py` (Tamarin's own preprocessor rejects `#ifdef` inside rule bodies).

## Models and results (2026-11-19, all reproduced by `run.sh`)

| Model | Variant | Property | Result |
|---|---|---|---|
| `tamarin/openpatch_pairing.spthy.in` | TOFU (current default) | executable (sanity) | verified |
| | | PS secrecy | **falsified** (attack trace) |
| | | agreement (phone view) | **falsified** |
| | | injective agreement (pod view) | **falsified** |
| | `-DOOB` high-entropy out-of-band secret | executable, PS secrecy, agreement, injective agreement | **all verified** (unless the OOB secret is revealed) |
| `tamarin/openpatch_session.spthy.in` | session handshake | executable | verified |
| | | session-key secrecy (even if every ephemeral is revealed, PS never revealed) | verified |
| | | **forward secrecy**: PS revealed after the session, ephemerals intact | verified |
| | | injective agreement, pod side (**replay resistance of the handshake**) | verified |
| | | agreement, phone side | verified |
| `proverif/openpatch_pairing.pv.in` | `-DTOFU` | PS secrecy, agreement | false (attack), as Tamarin |
| | `-DOOB` | oob secret, PS secrecy, injective agreement both ways | true, as Tamarin |
| | `-DWEAK` (6-digit code, current key schedule) | **weak secret** | **false: guessable offline** (FINDING-002; concrete attack: `security/poc/oob_offline_guess.py`) |
| | `-DCPACE` (code only derives the DH generator, PAKE shape of proposal 02) | weak secret, PS secrecy, injective agreement | **true** |
| `proverif/openpatch_session.pv.in` | spec | secrecy of data under session keys with PS leaked in phase 1 (forward secrecy), both directions | true |
| | | injective agreement pod->phone and phone->pod | true |
| | | command / response authenticity | true |
| | | pod never accepts a pod->phone frame as input | true |
| | `-DREFLECT` (behaviour of the current `Session::open`) | same query | **false: reachable** (FINDING-001) |
| | `-DLEAK0` (PS known from the start) | sanity: every property must fail | fails as required (proofs not vacuous) |

Tamarin and ProVerif agree on every shared question (TOFU broken; OOB with a strong secret fine), which is the cross-check of the two tools and of the two independent encodings.

## What the models do and do not cover (read before quoting a result)

Covered: Dolev-Yao network attacker controlling all messages; unbounded sessions in parallel; explicit compromise rules (PS reveal, ephemeral reveal, OOB reveal); injective correspondence (agreement with replay protection).

Abstractions (each can hide a real attack):
1. **Ideal primitives.** HKDF/SHA-256/HMAC are independent random oracles with the specified labels and inputs; AES-CCM is ideal authenticated encryption (`senc` unforgeable). **AES-CCM nonce reuse is therefore invisible to the models**; it is covered by `security/verify/tests/finding_001_reflection.rs`.
2. **X25519 as an abstract DH group.** Low-order points, twist/cofactor issues and non-canonical encodings are not modelled; the implementation rejects an all-zero shared secret (`handshake_props.rs::low_order_public_keys_are_rejected`).
3. **Randomness is perfect and fresh.** A weak or repeated RNG is out of the model (proposal 03).
4. **Single pending slot** is over-approximated by unbounded pending handshakes (the attacker has more power than in reality).
5. **The pod's strictly increasing `seq` filter** cannot be expressed in ProVerif (`table` else-branches are over-approximated), so data-channel agreement is stated **non-injectively** there; replay rejection is discharged by `security/verify/tests/proto_props.rs::replay_and_ordering` and the Kani proof `proof_session_replay_monotonic`. (The earlier Tamarin draft with the `SeqOnce` restriction and the data channel did not terminate in reasonable memory and was cut; the session theory here is the handshake only.)
6. **OOB secret entropy** is a modelling choice: `-DOOB` assumes it unguessable; `-DWEAK` assumes guessable. CPace is checked in ProVerif with an equation restricted to generator-derived bases (`exp(exp(gen(w),x),y)`): a sound abstraction of "password-derived generator" but not a computational PAKE proof; it relies on the published CPace analysis. Use an audited library for the real thing.
7. Timing, power and fault side channels, the link layer (LESC), and the physical button are not modelled (the button is the linear fact `Window`).
8. The models are *hand-written from the specification and the code*, not extracted from it. Conformance between model and code is checked through the shared test vectors (`docs/vectors/`) and the executable tests in `security/verify`, not by a proof.

## Next models (proposal 02 / 01)
`openpatch_pairing_v2.spthy.in` (device certificate, QR secret, PAKE), `no_downgrade` lemma for suite negotiation, log-chain consistency (proposal 05).
