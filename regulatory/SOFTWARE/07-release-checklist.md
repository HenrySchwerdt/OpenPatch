# 07 Release checklist (IEC 62304 5.8)

> Test project. Use for every tagged release of the repository (e.g. 0.1.0 beta). Copy into the release PR and tick. A legal manufacturer extends it. A release of this project is a **bench release**: water only, not for use on a person.

## A. Before tagging

- [ ] `docs/STATUS.md` updated; open decisions listed (gear ratio 15:12 vs 18:18 resolved or flagged)
- [ ] `cargo fmt --check`, `cargo clippy --workspace --all-targets -D warnings`, `cargo test --workspace`, `cargo test -p openpatch-proto --all-features`, differential tests green
- [ ] `swift test` (OpenPatchCore and OpenPatchKit) green
- [ ] `python3 mechanical/generate.py --variant bench && python3 mechanical/check.py --variant bench` green; `python3 mechanical/sim/run_all.py` re-run, FAIL list reviewed
- [ ] KiCad DRC 0 for both bench boards, pin map identical in `electronics/bench/pin-assignment.md`, `firmware-rs/docs/boards.md` and the core
- [ ] `python3 regulatory/tools/trace.py --report regulatory/RISK/TRACE.md` : **0 errors**; gaps reviewed
- [ ] `python3 regulatory/tools/soup.py` and `--check` : list regenerated, new/changed SOUP evaluated (`05-soup-management.md`), anomalies recorded
- [ ] `python3 regulatory/tools/collect_figures.py` : figure index regenerated
- [ ] GSPR checklist status updated (`../TECHNICAL-FILE/04-gspr-checklist.md`), V&V index updated
- [ ] No safety limit relaxed (spec §7, §7a) or each relaxation has a STATUS entry and risk review
- [ ] Known anomalies list written (open FAILs of the simulation, planned-not-built items, stubs from `firmware-rs/docs/stubs.md`)
- [ ] `security/` scorecard and SBOM attached (planned)
- [ ] Toolchain versions recorded (rustc, cargo, Xcode, KiCad, SolidCraft)

## B. Build and sign

- [ ] firmware built with an explicit drive preset (`scripts/build.sh`), drive-guard passed
- [ ] images signed (`scripts/sign-image.sh`); production builds without `dev-plaintext`, without `fault-inject`
- [ ] hashes of binaries recorded in the release notes

## C. Release record

- [ ] tag `vX.Y.Z` (Conventional Commit, release notes), technical-file version `tf-X.Y.Z` (`../LIVING-PROCESS.md`)
- [ ] release notes state: test project, not a medical device, never worn, water only
- [ ] archive of the evidence set (test logs, sim report, trace report, SOUP list, SBOM)

## D. Additional items for a legal manufacturer

- [ ] design review and approval signatures, independent verification of class C items
- [ ] verification on hardware (B01 to B24, accredited lab reports), usability validation
- [ ] labelling and IFU released by the manufacturer
- [ ] UDI assignment, declaration of conformity, registration
- [ ] post-market plan active, vulnerability intake open
