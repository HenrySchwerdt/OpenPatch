# 05 SOUP management (IEC 62304 5.3.3, 7.1.3, 8.1.2)

> The inventory is generated: **`SOUP.md`** and `soup.json` (`python3 regulatory/tools/soup.py`). The CycloneDX SBOM for supply-chain security is produced by `../../security/` (planned); this file covers the IEC 62304 process only.

## 1. Inventory

Sources: the three `Cargo.lock` files (host workspace, bench app, bootloader), the Swift `Package.resolved`, and `soup-extra.csv` for items that are not in a lock file (Nordic SoftDevice Controller and MPSL binary libraries, nRF52840 silicon, rustc, iOS frameworks, LoopKit, Trio, design tools). Licences are fetched from the crates.io API and cached in `soup-licences.json` (`--fetch-licences` refreshes; `--check` fails CI when the lock files changed but `soup.json` was not regenerated).

Classification in the table is derived from the dependency graph: *shipped, safety/security path* (reachable from `openpatch-core` or `openpatch-proto` through normal dependencies), *bootloader*, *bench app*, and *test-only*. The graph is a heuristic (feature flags are not resolved); a manufacturer verifies it with `cargo tree -e normal --target thumbv7em-none-eabihf`.

## 2. Evaluation criteria per SOUP item (to apply at selection and at every version change)

1. Function and performance requirements the software places on the SOUP (5.3.3): for crypto crates, correctness against published vectors (RFC 7748, RFC 5869, RFC 3610, already used in `docs/vectors/`).
2. System and hardware needed.
3. **Known anomalies** (8.1.2): check RustSec advisory DB, GitHub security advisories, vendor errata (Nordic release notes for SDC/MPSL), record outcome and date per version in `SOUP.md` (today every entry is "not yet assessed").
4. Maintenance status and release cadence; license compatibility (project: PolyForm Noncommercial software, GPL-3.0-or-later for `ios/`); `non-standard` licences (Nordic blobs) need a legal review.
5. Pinning: exact versions in lock files; toolchain version to be pinned (missing).
6. Risk: is the item reachable from class C code? Then each anomaly is evaluated for hazardous sequences (7.1.3).

## 3. Process at every release

Regenerate (`soup.py`), diff the list against the previous release, evaluate new or changed items, record anomalies, update `../RISK/`, run the full test suites, attach `SOUP.md` and the SBOM to the release record (`07-release-checklist.md`).

## 4. Specific items needing attention

| Item | Why |
|---|---|
| Nordic SoftDevice Controller / MPSL (binary, licence `non-standard`) | closed source in the radio path; no source for review; errata; flash timeslot behaviour affects tick jitter |
| RustCrypto crates (`aes`, `ccm`, `x25519-dalek`, `hkdf`, `hmac`, `sha2`, `subtle`) | class C security path; software AES is not constant time on some targets (`docs/04-protocol.md` s8) |
| `heapless`, `defmt`, `embassy-*` | data structures and runtime in the safety path |
| LoopKit, Trio, iOS | host platform changes outside the manufacturer's control; interface specification required (880.5730 special control) |
| Rust compiler | compiler is SOUP; pin and record |
