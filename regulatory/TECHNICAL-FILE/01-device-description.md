# 01 Device description and specification (Annex II section 1)

> Test project. No intended purpose, indication, claim or user group is asserted by this repository.

## 1. Device identification (placeholders)

| Item | Value |
|---|---|
| Trade name | to be defined by the legal manufacturer ("OpenPatch" is a project name, not a trademark; see `../../LICENSE.md`) |
| Manufacturer, SRN, PRRC | to be defined by the legal manufacturer |
| Basic UDI-DI / UDI-DI | to be assigned by the legal manufacturer (Annex VI) |
| Risk class | expected EU IIb (Rule 12), US Class II 880.5730 / QFG; see `../ROADMAP.md` |
| Model variants | OP-70, OP-100, OP-200 (reservoir 0.7 / 1.0 / 2.0 ml; spec §2); the variants differ only in housing and reservoir length |
| Hardware revision in repository | Rev A **bench split** (pod sensor board + bench controller board; spec §4a); Rev B integrated pod planned; v0.1.0 integrated study `../../docs/v010/ARCHITECTURE.md` |
| Software versions | firmware `FW_VERSION 0x0200` (`firmware-rs/openpatch-core/src/limits.rs`), `OpenPatchKit` (iOS), protocol v1 + 1.1 key agreement |

## 2. Intended purpose, indications, users, environment (to be defined by the legal manufacturer)

**Intended purpose: to be defined by the legal manufacturer.** The statements below are not claims; they are facts about the engineering concept that the manufacturer would use when writing the intended purpose.

- Concept: a reusable, detachable pod containing a drug reservoir, a stepper-driven plunger and electronics, connected to a third-party infusion-set cannula head (Insight Flex) and controlled over Bluetooth Low Energy by an external controller application (`OpenPatchKit` in a LoopKit host).
- Intended patient population, indications, contraindications, user profile, use environment: **to be defined by the legal manufacturer.** (Hard rule of this project: no on-body use, no use with insulin on a person, no instructions for use.)
- Project test condition: **water only; no drug is ever used** (DISCLAIMER, 2026-11-19).

## 3. Principle of operation (from the repository)

| Function | Description | Source |
|---|---|---|
| Reservoir | frozen CNC polypropylene stadium bore 16.00 x 5.00 mm, 74.6 mm2; stroke 9.4 / 13.4 / 26.8 mm | spec §3, §3a |
| Drive | NFP-608-26.45 geared stepper (20 steps/rev, ratio 26.45), purchased gear pair, M1.6 x 0.35 leadscrew, nut in carriage, carriage arm pushes the plunger. Resolution about 0.005 U/step (18:18) or 0.00617 U/step (15:12); **gear ratio decision open** | spec §4, `../../docs/STATUS.md`, `../../mechanical/sim/REPORT.md` |
| Fluid path | end cap with fill septum, duckbill check valve, 30G stainless outlet needle that pierces the cannula head septum | spec §3, §3a, §8a |
| Refill | automatic draw mode: pod undocked and suspended, app selects amount, motor retracts and draws through the septum | spec §4, `../../mechanical/REFILL.md` |
| Cannula interface | modular dock insert (snap arms, needle guide, dock magnet); frozen dock interface on the pod | spec §8, §8a |
| Sensing | TMAG5273 angle sensor on the leadscrew magnet (steps vs rotation), dock hall switch, motor current, optional DRV5032 pair | spec §4, §4a |
| Safety supervisor and interlock | software supervisor with hard limits (spec §7) + hardware interlock `MOT_ALLOW = MCU_EN AND watchdog latch AND (DOCKED OR DIR_REVERSE)`, TPL5010 watchdog, over-current cut; optional hardware step budget (HW-A, pending) | spec §7, §7a, `../../docs/02-safety.md`, `../../docs/06-diagnostics.md` |
| Communication | BLE; application-layer X25519 key agreement, AES-128-CCM, replay protection | `../../docs/04-protocol.md` |
| Two-pod system | pods A/B, one delivers; 44/52 h wear timer; explicit release/activate handover | spec §1b |
| Controller application | `OpenPatchKit` (LoopKit PumpManager) managing the pair as one pump; alerts, component health view (planned) | `../../ios/INTEGRATION.md` |
| Power | Rev A bench: USB 5 V; Rev B: Li-Po 17 to 40 mAh, charging pads or Qi | spec §5, v010 architecture |
| Diagnostics | 32-bit diagnostic codes (150 in the catalogue), FRU naming, component health | `../../docs/06-diagnostics.md` |

## 4. Safety limits (spec §7; never relaxed silently)

Max single bolus 10 U (configurable <= 25 U); max basal 5 U/h (<= 30 U/h); max delivery 15 U/h; bolus speed 1.5 U/min; occlusion alarm <= 2 U undelivered; communication loss: temp basal continues max 30 min then reverts to programmed basal; encoder deviation > 10 % over 1 U stops delivery. Implementation: `firmware-rs/openpatch-core/src/limits.rs`.

## 5. Accessories, configurations and compatibility (to be defined by the manufacturer)

- Cannula/infusion set: Accu-Chek Insight Flex (third-party, Roche): compatibility not validated by the maker; manufacturer decision (see `../ROADMAP.md`).
- Dock insert and cannula adapter variants (CERN-OHL-P-2.0 excluded from the commercial licence): each manufacturer approves its own adapter.
- Charger/cradle, programming tools, bench controller: not part of a market product.
- Host application and algorithm: LoopKit / Trio (third-party): interface specification in `../../ios/INTEGRATION.md` and `../../docs/04-protocol.md`.

## 6. Comparison with previous and similar devices

Not performed. No predicate or equivalent device has been named. Required by FDA (substantial equivalence) and MDR (clinical equivalence only with full data access, see `../CLINICAL/02-equivalence.md`). **To be defined by the legal manufacturer.**

## 7. Figures

F01, F02, F03, F04, F13: see `08-figures.md`.
