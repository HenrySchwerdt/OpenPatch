# 02 Software development plan (IEC 62304 clause 5.1), as the repository actually works

> Test project. This plan describes the **practice found in the repository**; it is a draft starting point, not a controlled QMS procedure.

## 1. Scope and classification

Items and classes: `01-safety-classification.md`. Standards: IEC 62304:2006+A1:2015, IEC 81001-5-1 for security (`../CYBERSECURITY/`), ISO 14971 for software risk (`../RISK/`).

## 2. Life-cycle model as practiced

| Aspect | Practice in repository | Source |
|---|---|---|
| Source of truth | `spec/design-parameters.md` first, then propagate to subprojects | `../../CLAUDE.md` |
| Languages | firmware Rust (Embassy, `no_std` core, `forbid(unsafe_code)`); C/Zephyr firmware kept as frozen reference; Swift for iOS | `../../CLAUDE.md`, `../../firmware-rs/README.md` |
| Test-first | firmware core and Swift core are developed test-first; **all tests green before committing** | `../../CLAUDE.md` |
| Differential testing | Rust core compared with the C reference after every operation (proptest, 325 000 ops, scripted scenarios, documented differences) | `../../firmware-rs/docs/differential-testing.md` |
| Simulation | mechanics/drive/dose/fluidics models, 43 rows | `../../mechanical/sim/` |
| Simulated hardware | host-tested interlock model (`interlock.rs`), planned simulated board for HAL (WP-3) | `../../docs/06-diagnostics.md` section 6 |
| Fault injection | planned `fault-inject` feature (never in production builds) | `../../docs/06-diagnostics.md` 6.2 |
| Static checks | `cargo fmt`, `cargo clippy -D warnings`, `forbid(unsafe_code)` in the core, drive-guard script | `../../firmware-rs/ci/rust.yml`, `scripts/check-drive-guard.sh` |
| CI | draft workflow for firmware-rs exists but is **not active** (copy to `.github/workflows/`); site pages workflow active | `../../firmware-rs/ci/rust.yml`, `.github/workflows/` |
| Version control and review | git, Conventional Commits, update `docs/STATUS.md` and commit after each unit of work; contributor licence agreement | `../../CLAUDE.md`, `../../CONTRIBUTING.md`, `../../CLA.md` |
| AI-assisted development | much of the code and documentation is written with AI coding assistants under human direction (commit trailers). **The manufacturer must treat this as normal development output that needs the same human review, verification and independent assessment; AI use does not substitute for reviews** | git history |
| Releases | version in `FW_VERSION`, signed images (MCUboot-style, `firmware-rs/scripts/sign-image.sh`), release checklist in `07-release-checklist.md` | `../../firmware-rs/docs/bootloader.md` |

## 3. Activities and outputs per clause (class C)

| 62304 clause | Activity | Output in repo | Gap |
|---|---|---|---|
| 5.1 Planning | this plan | `02-development-plan.md` | no schedule, no resource plan (manufacturer) |
| 5.2 Requirements | SRS derived from spec, protocol, diagnostics | `03-requirements.md` | requirement IDs are not yet in the code comments |
| 5.3 Architecture | architecture documents with ownership rules and segregation | `04-architecture-and-segregation.md`, `../../firmware-rs/docs/architecture.md` | interfaces between items not formally specified |
| 5.4 Detailed design | module docs and code | `../../firmware-rs/docs/*.md`, rustdoc | detailed design per unit not separate |
| 5.5 Unit implementation and verification | unit tests, property tests, clippy | `openpatch-core/tests`, `openpatch-proto/tests` | acceptance criteria not written per unit; branch coverage not measured |
| 5.6 Integration testing | core + HAL on host with mock HAL; protocol over frames | `tests/pump.rs`, `tests/twopod.rs`, `tests/draw.rs`, vectors | HAL integration on hardware not run (`stubs.md`) |
| 5.7 System testing | bench procedures with water | `../../docs/02-safety.md` s3, `../../docs/06-diagnostics.md` 6.3 | not executed |
| 5.8 Release | checklist | `07-release-checklist.md` | no release has been made under the checklist |
| 6 Maintenance | problem and change process | `06-problem-resolution-and-configuration.md` | |
| 7 Risk management | hazard trace, software contribution analysis | `../RISK/` | |
| 8 Configuration management | git, lock files, SOUP list | `06-...`, `SOUP.md` | toolchain not pinned (no rust-toolchain file); no bill of tools |
| 9 Problem resolution | GitHub issues + diagnostics catalogue | `06-...` | |

## 4. Development environment and tools

Rust stable (pin needed), `cargo`, Embassy, nrfutil/NCS for the frozen C target, Xcode/Swift, KiCad 10, SolidCraft. Tool pins to record: `../../docs/SETUP.md`; tool qualification needed where tool output is not verified (e.g. image signing tool).
