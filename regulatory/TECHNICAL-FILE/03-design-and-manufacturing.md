# 03 Design and manufacturing information (Annex II section 3)

> Test project. Rev A is a bench split; the information below is the design history as it exists, not controlled manufacturing documentation.

## 1. Design stages (design history)

| Stage | Records | Notes |
|---|---|---|
| Concept and decisions | `../../docs/STATUS.md` (decision log), `../../spec/design-parameters.md` (single source of truth), `../../docs/01-architecture.md` | every decision is dated; spec changes first, then propagate |
| Safety concept | `../../docs/02-safety.md`, `../../docs/06-diagnostics.md` | hazards H1 to H13 |
| Parts selection | `../../docs/PARTS-LOCK.md`, `../../mechanical/parts.md`, `motor-selection.md`, `gear-selection.md`, `linear-actuator-selection.md`, `../../electronics/bom.csv` | LOCKED / LOCK-AFTER-SAMPLE / CANDIDATE status per part; sample order pending |
| Mechanical design | `../../mechanical/*.py` generators, `params.json`, `out/` (STEP, STL, renders), `check.py` (interference, height <= 8.5 mm) | generated from parameters; frozen interfaces `reservoir_frozen`, `dock_interface_frozen` |
| Design verification by simulation | `../../mechanical/sim/REPORT.md` (`run_all.py`) | 14 PASS / 9 WARN / 20 FAIL at the last run; recommended changes listed there |
| Electronics | `../../electronics/bench/` (controller, pod), `pin-assignment.md`, `bom.csv`, KiCad projects, JLCPCB fab packages | DRC and routing state in `../../electronics/fab/STATUS.md`; interlock design |
| Firmware | `../../firmware-rs/` (Rust, Embassy, no_std core with `forbid(unsafe_code)`), frozen C reference `../../firmware/` for differential tests | see `../SOFTWARE/` |
| iOS kit | `../../ios/OpenPatchKit/` | `../../ios/INTEGRATION.md` |
| Integrated pod study | `../../docs/v010/ARCHITECTURE.md` | feasibility, 66.9 x 32 x 8.5 mm OP-100 with electronics tail |

## 2. Design inputs and outputs

- **Inputs**: user need (project statement, `../../docs/STATUS.md` Goal), spec sections 1 to 8a, safety limits §7, diagnostics requirement §7a.
- **Outputs**: drawings and models (`mechanical/out`), BOMs, fab packages, firmware source, protocol documents, test vectors (`../../docs/vectors/`).
- Review points today: STATUS.md entries and independent reviews recorded there (DFM review of reservoir drawing and PCB layout are listed as pending). **No formal design review by a manufacturer exists.**

## 3. Manufacturing and suppliers (as planned for bench iterations)

| Item | Process | Supplier (candidate) | Records |
|---|---|---|---|
| Housing and dock inserts | MJF PA12 / SLA | JLC3DP | `../../mechanical/out/bench/fab/`, `ASSEMBLY.md` |
| Reservoir | CNC polypropylene, frozen drawing, qty 2 per size | PCBWay CNC | `out/bench/fab/reservoir-cnc/` drawings (F05) |
| Plunger seal, septum, duckbill | cast silicone (printed mould), punched, purchased | various (CANDIDATE) | `../../docs/PARTS-LOCK.md` rows 16, 18, 19 |
| PCBs and assembly | JLCPCB PCBA | JLCPCB | `../../electronics/bench/fab/jlcpcb/`, `ORDER` documents |
| Motor, gears, leadscrew | purchased | nfpshop, GHW-Modellbau, fastener shops | PARTS-LOCK |
| Assembly | manual, no soldering iron (spec §1a) | builder | `../../mechanical/ASSEMBLY.md` |
| Firmware programming | SWD, signed images (`firmware-rs/scripts/sign-image.sh`) | | `../../firmware-rs/docs/bootloader.md` |

**Not available** (legal manufacturer + QMS): supplier qualification, incoming inspection, process validation (IQ/OQ/PQ), cleanliness and packaging, device master record, lot traceability, UDI assignment.

## 4. Critical interfaces and frozen parameters

| Interface | Source | Change rule |
|---|---|---|
| Reservoir envelope, datum faces, port | `params.json: reservoir_frozen`, spec §3a | decision in STATUS.md |
| Dock interface (mount, needle exit, hall, magnet) | `params.json: dock_interface_frozen`, spec §8a | decision in STATUS.md; dock insert and adapter are CERN-OHL-P-2.0 and approved by each manufacturer |
| Pin map firmware / electronics | `../../electronics/bench/pin-assignment.md` vs `../../firmware-rs/docs/boards.md` | must be identical; check in review |
| Drive calibration (U/step) | `firmware-rs` feature `drive-*`, spec §4 | **open: 15:12 vs 18:18 (25 % dose error if mismatched)**; stored per-pod calibration blocks delivery when missing or corrupt |
| Wire protocol | `../../docs/04-protocol.md`, `../../firmware/docs/openpatch-protocol.md`, `firmware-rs/docs/protocol-extensions.md` | additive tags only (old parsers skip new tags) |

## 5. Materials and wetted path (drug contact: manufacturer only)

Wetted-path material choice is recorded as design preparation (spec §3a: PP reservoir, platinum-cure silicone seals/septum/duckbill, stainless needle, no printed resin). **No drug is used in this project**; biological evaluation, extractables/leachables and drug compatibility belong to the legal manufacturer (`../STANDARDS-MATRIX.md`).

## 6. Figures

F05, F06, F07 to F11, F17: see `08-figures.md`.
