# 06 Problem resolution (IEC 62304 9) and configuration management (IEC 62304 8)

> Test project. Describes how it works today and what a manufacturer adds.

## 1. Configuration management

| Item | Practice | Addition for a regulated product |
|---|---|---|
| Configuration items | everything in git: source, specs, generated outputs (`mechanical/out`, `electronics/*/fab`), lock files, signing scripts | define the configuration item list per release (software items with versions, SOUP, tools, hardware revision, labelling) |
| Identification | `FW_VERSION` in `limits.rs`; git commit; hardware revision (Rev A bench, Rev B planned); protocol version | one release identifier that ties firmware, app, hardware revision, calibration preset and documents together |
| Change control | Conventional Commits; spec first then propagate; frozen interfaces require a decision in `docs/STATUS.md`; safety limits never relaxed silently | change request with impact analysis (risk, SOUP, verification), approvals |
| Safety-limit change rule | spec §7/§7a; STATUS entry | manufacturer's design-change procedure |
| Builds | `firmware-rs/scripts/build.sh` (explicit drive preset), drive-guard script prevents building without a preset | reproducible build record: toolchain pins, build host, hashes of signed images |
| Release records | none yet | `07-release-checklist.md` |
| Generated figures | `regulatory/tools/collect_figures.py` index | controlled drawings |

## 2. Problem resolution

| Step | Today | Manufacturer addition |
|---|---|---|
| Report | GitHub issues; bench logs in `firmware-rs/docs/bench-testing.md` | complaint handling and anomaly intake linked to ISO 13485 8.2 |
| Evaluate | engineers and AI assistants analyse; hazard link required for new failure modes | formal assessment of safety impact (14971) within a defined time |
| Resolve | test-first fix with a regression test; differential test; STATUS entry | CAPA, change control |
| Verify | `cargo test --workspace`, `swift test`, sim, bench | verification record with traceability |
| Track | issues and commit history | anomaly list per release (known residual anomalies, 5.8.3) |
| Field | catalogue of diagnostic codes with FRU and action; shared fault catalogue obligation in the commercial licence | vigilance and PMS (`../TECHNICAL-FILE/07-pms-plan.md`) |

Rule for new failure modes (spec §7a): **a catalogue row with hazard link and test is required**; relaxing a severity or a threshold requires a STATUS entry.

## 3. Maintenance (62304 6)

Software maintenance plan: security patches (`../CYBERSECURITY/`), SOUP updates (`05-soup-management.md`), host-app (iOS/LoopKit/Trio) compatibility, signed update path (`firmware-rs/docs/bootloader.md`), field-update validation, end-of-support communication. All to be defined by the manufacturer.
