# 01 Software safety classification (IEC 62304:2006+A1:2015, clause 4.3)

> Test project, not a medical device. This is a **rationale draft** for a future legal manufacturer; the classification is the manufacturer's decision.

## 1. Method (62304 4.3, Amendment 1)

1. Identify the software system and its software items.
2. For each hazardous situation that a software failure could contribute to, assume the software fails with probability 1 and consider **only risk control measures external to the software system** (hardware, independent devices, procedures).
3. If, after those external controls, the harm could be death or serious injury: **Class C**; non-serious injury: Class B; no injury or damage to health possible: Class A.
4. Software items can be assigned a lower class than the system if they are **segregated** so that a failure in them cannot contribute to the hazardous situation (4.3 d/e, 5.3.5); the segregation must be documented.

## 2. Hazardous situations (from `../../docs/02-safety.md`, `../RISK/`)

| Hazard | Worst credible harm if software fails | External (non-software) control | Residual after external control |
|---|---|---|---|
| H1 over-delivery of the drug | severe hypoglycaemia, death possible | hardware interlock (gates, TPL5010 watchdog, over-current cut); **Rev A does not bound the dose inside the watchdog window in hardware** (2.5 to 25 U, `../../docs/06-diagnostics.md` 1.5); optional HW-A bounds a runaway to about 1.6 U per window; no hardware hourly limit until HW-B | serious injury or death remains possible, **class C** |
| H2 under-delivery / undetected occlusion | hyperglycaemia, ketoacidosis | none beyond dock gate (stops, does not measure) | serious, **class C** |
| H3 unnoticed delivery stop | as H2 | hardware leaves all gates open after reset (safe, but silent) | serious, **class C** |
| H6 loss of communication | autonomous basal continues (design), delivery limits stay in the pod | pod-side limits | non-serious to serious depending on duration, **B or C** |
| H7 unauthorised access | commanded over-delivery | pod limits (10 U bolus, 15 U/h) | serious, **class C** for the security path |
| H9 not docked | no delivery (hardware dock gate) | hardware | A to B for dock handling in software given the hardware gate; keep C for the supervisor that proves the gate |

## 3. Proposed classification per software item

| Software item | Location | Proposed class | Reason |
|---|---|---|---|
| Delivery engine, safety supervisor, reservoir model, pod/wear logic, drive calibration | `firmware-rs/openpatch-core/src` | **C** | decides amount and permission of every step |
| Protocol codec, session, handshake, AES-CCM | `firmware-rs/openpatch-proto/src` | **C** | authenticity and integrity of dose commands (H7, H1) |
| Bench HAL: stepper, interlock sequencing, watchdog service, angle/ADC | `firmware-rs/openpatch-bench/src/hal`, `safety.rs` | **C** | feeds the watchdog, proves the interlock (H1, H11) |
| Persistence (calibration, seq ceiling, reservoir, pod state) | `firmware-rs/openpatch-bench/src/storage.rs` | **C** | corrupted calibration or counters change the dose |
| Bootloader and update path | `firmware-rs/openpatch-bootloader` | **C** (authenticated image) | an unauthenticated image replaces everything |
| BLE host and link layer (trouble-host, SoftDevice Controller, MPSL) | `openpatch-bench` BLE task + SOUP blobs | **B** (proposal) | segregated by ownership rules (`../../firmware-rs/docs/architecture.md`): cannot access motor, interlock or watchdog; frames are authenticated end to end; failure causes loss of communication handled autonomously. **Segregation must be demonstrated by design review and tests (not yet done).** |
| UI task (button, LED, buzzer), `wake_task`, DFU glue | `openpatch-bench` | **B** | alarm audibility is a risk control for H3; if the buzzer is the only alarm path, treat the alarm output as **C** |
| iOS `OpenPatchCore` (wire codec, unit conversion, dose commands, swap coordinator) | `ios/OpenPatchKit/OpenPatchCore` | **C** (proposal) | unit-conversion or swap errors can request wrong doses or leave two pods active; pod-side limits are the external control but a 10 U bolus limit alone does not remove serious harm |
| iOS `OpenPatchKit` (PumpManager, alerts), `OpenPatchKitUI` | `ios/OpenPatchKit/*` | **B** (alerts as risk control for H3: C for the alert path) | |
| Frozen C reference firmware | `firmware/` | not shipped (test oracle) | differential tests only |
| Host tools (generators, trace, SOUP) | `mechanical/`, `electronics/`, `regulatory/tools` | not part of the device software | tool validation per ISO 13485 4.1.6 if output is not verified |

## 4. Can the hardware interlock lower the class?

Short answer: **not for the dosing hazards.** The classification rule credits an external control only if it reduces the *severity-weighted risk* of the hazardous situation to acceptable on its own. The interlock

- does bound motion when the pod is undocked (H9) and bounds runaway time to one watchdog interval, but
- does **not** bound the **amount** in Rev A: a faulty firmware with `STCK` running can deliver about 2.5 to 4.9 U (up to about 25 U if a high step rate is set) before the watchdog trips (`../../docs/06-diagnostics.md` 1.5), more than the 10 U default bolus limit only in the worst case, but still capable of serious harm for a small user. The measurement B11 replaces the estimate.
- With the optional HW-A step budget (about 1.6 U per window) and a future HW-B monitor (15 U/h, 1.7 U/min), the *hourly* hazard could be handled in hardware. Even then the residual severity from repeated windows and from under-delivery hazards stays serious, so **class C remains** for the items in section 3; hardware reduces the **probability** that class C software failure propagates, which is accounted in the risk file, not in the class.

What the hardware does enable is **segregation**: because the BLE/UI parts cannot move the motor or feed the watchdog, they can be assigned a lower class (B) provided the segregation argument in `04-architecture-and-segregation.md` is verified.

## 5. Consequences of class C

All 62304 clauses apply, including 5.4 software detailed design, 5.5.3 unit acceptance criteria, 5.7 system testing with traceability, 7 risk management of software, 8.1.2 SOUP anomaly evaluation, and 9 problem resolution. Statement-coverage evidence from `cargo llvm-cov` is already in the draft CI (`../../firmware-rs/ci/rust.yml`, not active) and should be extended to branch coverage for class C items **[ESTIMATE of expected rigour; confirm with the notified body]**.
