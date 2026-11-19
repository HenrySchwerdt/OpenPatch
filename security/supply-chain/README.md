# Supply-chain controls

TEST PROJECT, not a medical device. Config: `firmware-rs/deny.toml` (cargo-deny), `firmware-rs/supply-chain/` (cargo-vet), scripts here, CI: `.github/workflows/security-ci.yml`. Tools used 2026-11-19: cargo-deny 0.21.0, cargo-audit 0.23.0, cargo-vet 0.10.3, cargo-cyclonedx 0.5.10, rustc 1.97.0 stable / 1.102.0-nightly.

```sh
cd firmware-rs && cargo deny --exclude differential-tests check          # host workspace
cd firmware-rs/openpatch-bench && cargo deny --config ../deny.toml check # embedded app (own lockfile); same for openpatch-bootloader, tools/sigtool, fuzz, ../../security/verify
cargo audit                                                              # RustSec on the current Cargo.lock
cargo vet                                                                # firmware-rs workspace
security/supply-chain/sbom.sh [outdir]                                   # CycloneDX 1.5 per lockfile
security/supply-chain/repro-build.sh [firmware-rs] [workdir]             # build the bench firmware + bootloader twice from two paths, compare SHA-256
security/supply-chain/check-action-pins.sh                               # every workflow `uses:` must be a 40-hex SHA
```

## Results (2026-11-19)

| Check | Result | Detail |
|---|---|---|
| cargo-deny host workspace (`firmware-rs`) | advisories ok, bans ok, licences ok, sources ok | after triage; **9 `heapless 0.8.0` advisories** (RUSTSEC-2026-0574..0582, published 2026-11-18/19, patched >= 0.9.4) are ignored with a per-advisory reachability reason (only `Vec` and `Deque::push/pop` are used). FINDING-007 |
| cargo-deny `openpatch-bench` | **crypto-bigint 0.5.5 RUSTSEC-2026-0387** (secret-dependent branches in constant-time ops; path `trouble-host -> p256 -> elliptic-curve -> crypto-bigint`, i.e. BLE LE Secure Connections ECDH); `bare-metal 0.2.5` deprecated (RUSTSEC-2026-0110); `nrf-mpsl-sys`, `nrf-sdc-sys` "unlicensed" (Nordic proprietary binaries) | raw output before triage: `results/deny-openpatch-bench.txt`, `results/audit-bench.txt`. After the dated ignore entries in `deny.toml` the advisories pass; the licence finding is accepted and tracked (FINDING-013). FINDING-008 stays **open** (SCORECARD SC-4) |
| cargo-deny bootloader, sigtool | advisories: `bare-metal` only (triaged) | `results/deny-openpatch-bootloader.txt`, `results/deny-tools_sigtool.txt` |
| cargo-audit | same advisories as above (`results/audit-*.txt`) | |
| cargo-vet | bootstrap only: **92 exemptions, 0 own audits** | `firmware-rs/supply-chain/`; importing Google/Mozilla/Bytecode-Alliance audit sets (not done here: fetching them needs the raw GitHub host, blocked in the authoring sandbox) will shrink the list |
| SBOM | generator + CI artifact | `sbom.sh` |
| Reproducible build | bench app (`app.bin` SHA-256 `3a0d94521734dad3d72c3a5a3b7960be4887a9a7c0735b47bac2bf2c73d33409`, 294 768 bytes) is **identical across fresh target dirs from the same source path**, three builds. **Not identical when the source path differs** (second path: 294 784 bytes, different hash): cargo derives the `-C metadata` hash of path dependencies outside the workspace root from their absolute path, `--remap-path-prefix` does not cover it. The bootloader is reproducible even from different paths (SHA-256 of `boot.bin` `1652152f5468707d38453dfbedee31a1cd01488b35c0ba39009e5927805bae8b`). Consequence: release builds run in a fixed directory (container `/build/firmware-rs`); the SBOM/provenance records that path | `results/repro-build.txt` |
| Actions pinning | **fails by design until SHAs are resolved** | the authoring sandbox had no GitHub API access; no SHA was invented. `pin-actions.sh` resolves them on a maintainer machine |

## Policy summary (`deny.toml`)
- **Licences**: allow MIT, Apache-2.0 (+LLVM exception), BSD-2/3, ISC, Unicode, Zlib, CC0, 0BSD, MPL-2.0 (reviewed). **Strong copyleft (GPL/AGPL/LGPL/SSPL/EUPL) is denied by omission** in firmware crates: `LICENSE.md` makes `firmware-rs` PolyForm-Noncommercial with a commercial licence, which a copyleft dependency would make impossible. `ios/` is GPL-3.0-or-later by decision (Trio is AGPL) and is outside cargo-deny. Workspace crates `openpatch-core/-proto` carry an explicit PolyForm exception.
- **Sources**: crates.io only, no git dependencies (`allow-git = []`).
- **Bans**: `openssl`, `native-tls`, `ring`, `chrono` (rationale in the file); wildcards warn (workspace crates lack `publish = false`).
- **Advisories**: unmaintained and unsound count as errors; every ignore has a reason and a review date.

## Other repository findings from this review
- `.github/workflows/pages.yml` (not ours): actions on mutable tags (`@v4`, `@v3`, `@v5`), workflow-level `pages: write` and `id-token: write`. Fix: SHA pins, move permissions to the deploy job. (FINDING-012)
- `firmware-rs/ci/rust.yml` (draft, not active) installs tools with `cargo install --locked` without versions and uses `dtolnay/rust-toolchain@stable` and `Swatinem/rust-cache@v2` on mutable refs: do not activate as is.
- `differential-tests` links the frozen C core through FFI (`unsafe` allowed there only): keep it out of the release path; it has no licence field (excluded in deny runs).

Signing and release plan: `security/proposals/08-incident-response-disclosure-supply-chain.md` section 5.
