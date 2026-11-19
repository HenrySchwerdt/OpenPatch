# OpenPatch security

TEST PROJECT, not a medical device; never to be worn or used with insulin on a person (`../DISCLAIMER.md`). This directory holds the security work that makes the claim "state of the art, every claim verifiable" checkable. Rule: **no claim without a test, proof or CI job**; unproven things are listed as proposals or open.

| Where | What |
|---|---|
| [`THREAT-MODEL.md`](THREAT-MODEL.md) | assets, trust boundaries, attackers, STRIDE per interface with status, attack trees, **safety-security separation argument**, weakness register (sec. 9) |
| [`SCORECARD.md`](SCORECARD.md) | every control: status + evidence link |
| [`formal/`](formal/README.md) | Tamarin + ProVerif models and results (`formal/run.sh`) |
| [`verify/`](verify/README.md) | proptest + Kani harnesses, regression demonstrators for each finding |
| [`fuzz/README.md`](fuzz/README.md), `../firmware-rs/fuzz/` | cargo-fuzz targets for every parser, seeds, run results |
| [`supply-chain/`](supply-chain/README.md) | deny/audit/vet, SBOM, reproducible build, action pinning |
| [`poc/oob_offline_guess.py`](poc/oob_offline_guess.py) | FINDING-002 demonstrator (stdlib only, runs against the shared test vectors) |
| [`proposals/`](proposals/) | 01 AEAD + session-layer fix + version negotiation, 02 authenticated pairing, 03 key storage / RNG / DoS, 04 anti-rollback + signed manifest, 05 tamper-evident log, 06 BLE privacy, 07 authorisation + hardware dose limiter, 08 IR / CVD / bounty / SBOM / supply chain, 09 comparison with commercial pumps and standards |
| [`../SECURITY.md`](../SECURITY.md) | disclosure policy (contact is a placeholder) |
| `../.github/workflows/security-ci.yml` | audit/deny, verify, fuzz smoke, formal, reproducible build, SBOM, pin check |

## Reproduce everything (about 25 minutes on 4 cores, plus tool installs)
```sh
security/formal/run.sh                              # 30 expected results, ~15 s (Tamarin 1.10.0, ProVerif 2.05)
(cd security/verify && cargo test --release --features handshake && cargo kani)
python3 -I security/poc/oob_offline_guess.py docs/vectors/session-key-agreement.json   # exit 0 = attack reproduced
(cd firmware-rs/fuzz && cargo +nightly fuzz run frame_tlv -- -max_total_time=60)
security/supply-chain/repro-build.sh firmware-rs /tmp/repro
```

## Headline results (2026-11-19)
- **Session handshake**: secrecy, forward secrecy (w.r.t. PS), injective mutual agreement **proved** in two tools. **Pairing is not authenticated (TOFU): falsified**, and the documented OOB mitigation falls to an offline guess for short codes (2 s for the test-vector code). Fix designed (proposal 02), formally shape-checked.
- **Implementation defects found by executable properties** on the real code: reflected responses authenticate and cause AES-CCM nonce reuse (FINDING-001); "15 U/hour" is 16.7 U in a real hour (FINDING-003); DFU has no rollback protection (FINDING-006); handshake slot DoS (FINDING-004); static identifier (FINDING-005).
- **Parsers**: 7 fuzz targets, 26.5 M executions, 0 crashes; 8 Kani proofs, all verified.
- **Supply chain**: 9 reachable-by-nobody `heapless` advisories triaged; a real timing advisory in the BLE pairing crypto path (`crypto-bigint`); closed Nordic radio blobs.
- **Architecture**: fully attacker-controlled firmware is bounded only per arm window by the hardware design (and the hardware does not exist yet): the per-hour bound needs an independent monitor (proposal 07).

## Scope of this pass
New files only. No existing protocol, crypto or core source was changed; recommended changes are in `proposals/`. Another agent owns `regulatory/` (including a cybersecurity folder): coordinate cross-references before merging; `docs/STATUS.md` was not edited.
