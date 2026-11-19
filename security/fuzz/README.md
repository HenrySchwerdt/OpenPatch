# Fuzzing

Crate: `firmware-rs/fuzz/` (cargo-fuzz / libFuzzer, **excluded from the `firmware-rs` workspace**, own lockfile). TEST PROJECT, not a medical device. Built with `overflow-checks` and `debug-assertions` on: an integer overflow counts as a finding.

```sh
rustup toolchain install nightly --profile minimal && cargo install --locked cargo-fuzz --version 0.13.2
cd firmware-rs/fuzz
cargo +nightly fuzz run frame_tlv -- -max_total_time=300      # corpus seeds are picked up from corpus/<target>/
python3 -I ../../security/fuzz-seeds/gen_seeds.py <vectors.json> corpus   # regenerate the committed seeds
```
Default feature `handshake` needs `openpatch-proto` with feature `key-agreement` (`docs/04-protocol.md`; `handshake.rs` was in the shared checkout, not in this branch's base commit). The six non-handshake targets build without it (`--no-default-features`).

| Target | Code under test | Properties asserted |
|---|---|---|
| `frame_tlv` | `decode_frame`, `TlvReader`, `decode_command`, `decode_response` | no panic/overflow; decoded frame re-encodes byte-identically; reader terminates inside its input |
| `session_open` | `Session::open` with real keyed `AesCcm` and with the plaintext (dev) session | production session never accepts a fuzzer-made frame; accepted command seq strictly increasing |
| `ccm_open` | `AesCcm` encrypt/decrypt | round trip; any single bit flip of ct/tag/AAD/nonce rejected; acceptance of arbitrary (ct, tag) implies re-sealing reproduces them |
| `handshake_responder` | `Responder::handle` on frame streams (random PS/OOB/window flag) | no panic; replies are valid frames <= FRAME_MAX; blind bytes never yield a pairing or session |
| `handshake_mutate` | structure-aware: honest phone vs pod, one payload byte of one of four messages changed (CRC fixed) | any modification => pod installs no session; unmodified => equal keys on both sides |
| `dfu_manifest` | manifest parse + Ed25519/SHA-512 verification glue (**mirror** of the bootloader code, see `src/lib.rs`) | parse bounds; honest verifies; image/length/signature/key tampering rejected; format/reserved changes accepted (documents FINDING-006) |
| `storage_records` | `DriveCal::from_bytes/validate/pulse_cal` (real); storage-record length filters (mirror) | no panic; validated record is CRC-consistent, in range, round-trips |

## Run of 2026-11-19 (nightly 1.102.0-nightly 2026-11-18, 4 cores, 300 s per target, seeds from `corpus/`)
`security/fuzz/results/2026-11-19-run1.txt` has the raw libFuzzer statistics.

| Target | Executions | exec/s | Coverage (edges) | Crashes / timeouts / OOM |
|---|---|---|---|---|
| frame_tlv | 6 015 506 | 19 985 | 413 | 0 |
| session_open | 3 223 550 | 10 700 | 125 | 0 |
| ccm_open | 1 680 941 | 5 600 | 403 | 0 |
| dfu_manifest | 219 412 | 730 | 1 131 | 0 |
| storage_records | 12 776 716 | 42 000 | 67 | 0 |
| handshake_responder | 2 574 030 | 8 500 | 224 | 0 |
| handshake_mutate | 45 301 | 150 | 551 | 0 |
| **total** | **26 535 456** | | | **0** |

No crash, so no crash regression files exist; `firmware-rs/fuzz/artifacts/` is empty. The real defects found in this pass (FINDING-001..006) came from **reading the code and writing executable properties**, not from the fuzzers. That is a statement about the fuzzers' reach, not about the absence of bugs.

## Honest limits
- 5 minutes per target is a smoke test. `security-ci.yml` runs 60 s per target per push; real campaigns (hours, continuous) are an open SCORECARD item V-6.
- `storage_records` reaches only 67 edges: a calibration record validates only if it equals one of the eight preset records exactly, which random mutation rarely finds. Add preset-derived seeds when `drive_cal` exposes a seed dump.
- `dfu_manifest` and the storage-record length filters fuzz *mirrors*: the real parsers sit inside `no_std` embassy binaries. Proposal 04 s.4 extracts them into a library so the real code is fuzzed.
- `handshake_mutate` is slow (150 exec/s, X25519 x2 per run); that is why its coverage grows slowly. Run it longer.
- Nothing here fuzzes the BLE stack, the SoftDevice Controller, the Swift implementation, or the hardware interlock.
