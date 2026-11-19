# security/verify: executable properties, bounded proofs and regression demonstrators

Standalone crate (own `[workspace]`, not part of `firmware-rs/`), path dependencies on `firmware-rs/openpatch-core` and `openpatch-proto`. TEST PROJECT, not a medical device. **It changes no existing source.**

```sh
cd security/verify
cargo test --release                                  # safety_props, proto_props, finding_001 demonstrators
cargo test --release --features handshake             # + handshake_props (needs openpatch-proto feature key-agreement)
cargo test --release --features handshake --test finding_001_reflection -- --ignored   # the fixed_* test: FAILS while FINDING-001 is open
cargo kani                                            # 8 Kani harnesses (cargo install --locked kani-verifier && cargo kani setup)
```
Results of the run on 2026-11-19: `results/cargo-test-2026-11-19.txt` (23 tests passing, the one `fixed_*` test failing as intended), `results/kani-2026-11-19.txt` (Kani 0.68.0: **8 of 8 harnesses verified**).

| File | What it establishes | Method |
|---|---|---|
| `tests/safety_props.rs` | For arbitrary command/time sequences (2000 cases x up to 200 ops, all production drive presets, adversary acknowledging every fault): never > 1.7 U per wall minute; never > 15 U in 60 wall minutes; in any *sliding* real hour never > 16.7 U (`cap + per-minute cap`, the tight bound); bolus/rate checks respect configured and hard limits. `finding_003_*` reproduces the 16.7 U case. | proptest |
| `tests/proto_props.rs` | decoders total (no panic), frame codec canonical, any single bit flip of a sealed frame rejected, replay/ordering, keyless session refuses everything | proptest, 20 000 cases each |
| `tests/handshake_props.rs` (feature `handshake`) | responder total on garbage, honest pairing + session agree, window enforcement, wrong PS gets `PAIR`, low-order keys rejected; FINDING-004/005 demonstrators | proptest + unit |
| `tests/finding_001_reflection.rs` | FINDING-001 on the real `Pump::handle_frame` with real AES-CCM: reflected response accepted twice, nonce reuse recorded, 3 keystream bytes leaked; `fixed_*` is the acceptance test of the fix | unit (uses the core's own MockHal via `#[path]`) |
| `src/kani_proofs.rs` | TLV reader, frame decoder, command decoder total for all inputs up to the stated sizes; replay monotonic; `approve_steps` bounds (reservoir, per-minute, hourly) for any time/request; two approvals in one minute <= per-minute cap; `check_bolus` never above the hard max; `configure` never stores above hard caps | Kani bounded model checking (CBMC), bounds in each harness comment |

Limits of the evidence: proptest samples; Kani proofs are for the bounds stated (e.g. 12 payload bytes), not for all lengths: the unbounded argument is the code's structure plus the fuzzers. The supervisor proofs fix one drive preset (NFP 15:12); proptest covers all production presets. Time is a `u64` ms input; clock tampering is out of scope (the supervisor ignores time going backwards).

When a finding is fixed: flip the `known_issue_*` tests, un-ignore `fixed_*`, and update `THREAT-MODEL.md` section 9 + `SCORECARD.md`; the CI step "fixed_* must still FAIL while the findings are open" reminds the owner.
