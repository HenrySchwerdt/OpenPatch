# 04 Software architecture and segregation argument (IEC 62304 5.3)

> Test project. Describes the architecture in `../../firmware-rs/docs/architecture.md`, `../../docs/01-architecture.md`, `../../docs/v010/ARCHITECTURE.md` and adds the segregation argument a manufacturer needs for class assignment. **Not verified on hardware.**

## 1. Software items and interfaces

| Item | Responsibility | Owns | Interfaces |
|---|---|---|---|
| `openpatch-core` (`no_std`, `forbid(unsafe_code)`) | delivery engine, safety supervisor, reservoir, pod/wear, draw, diagnostics (planned), event log | no hardware | `Hal` trait (motor, angle, watchdog, battery, dock, time, buzzer) |
| `openpatch-proto` | frame, TLV, session, AES-CCM, handshake | no hardware | byte buffers, `SessionKeySource` seam |
| `openpatch-bench` HAL (stepper, driver/interlock, angle, ADC) | physical motor, interlock sequencing, TPL5010 DONE, STCK PWM + PPI counter | **safety task only**: `Pump`, motor and interlock pins, PWM, SAADC, DONE pin | `Hal` implementation |
| Safety task (interrupt executor P5) | 1 s tick, frame handling, persistence snapshots | `Pump<BenchHal>` | channels from BLE and UI tasks |
| BLE host task (trouble-host + SoftDevice Controller + MPSL) | link, GATT, pairing window, handshake | radio | `FRAME_IN` / `FRAME_OUT`, `BENCH_CMD`, `SESSION_EVT` (keys to the safety task) |
| UI task | button, LED, buzzer | UI pins | atomics (`ALARM_ON`, `BEEP_REQ`, ...) and `UI_CMD` |
| Persistence task | sole flash writer | flash | `PERSIST` snapshots from the safety task |
| Bootloader | image verification and swap | flash partitions | signed image trailer |
| iOS `OpenPatchCore`, `OpenPatchKit` | protocol client, dosing commands, swap, alerts | phone BLE | `Transport` protocol |

## 2. Segregation argument (to be verified)

Goal: show that failures of the BLE stack, UI and (partly) persistence cannot cause the class C hazardous situations, so they can carry a lower class.

| # | Claim | Basis in the design | Evidence now | Evidence needed |
|---|---|---|---|---|
| S1 | The BLE task cannot move the motor, change the interlock, or service the watchdog | ownership rules: `Pump`, motor/interlock pins, PWM, SAADC, DONE belong to the safety task only; Rust ownership makes this a compile-time property | `architecture.md` "Ownership rules"; type system | code review of `main.rs`/HAL; test that BLE task has no handle (compile-fail test or module visibility check) |
| S2 | The safety task preempts the BLE task | interrupt executor P5 above radio low priority; link layer timing in P0/P4 | `irqs.rs` table | timing measurement on hardware (tick jitter during flash writes, BLE bursts) |
| S3 | A hung BLE host cannot hold the motor on or feed the watchdog | DONE is pulsed only if the wake flag is set and the interlock verification passed, from `Pump::tick()` | `architecture.md` | fault-injection test B23 (tick stall) |
| S4 | Frames from BLE cannot cause harm without authentication | AES-CCM, replay protection, handshake; limits enforced after decoding in the supervisor | proto tests, vectors | security review (`../../security/`) |
| S5 | Shared memory between tasks is limited to channels and atomics | `shared.rs` | `architecture.md` | static review; no `unsafe` outside HAL/FFI |
| S6 | Flash writes cannot stall the safety task beyond the watchdog interval | MPSL timeslot flash, sole writer, coalesced writes, 2 s watchdog >> stall | `architecture.md` flash section | worst-case tick jitter measurement ("not done yet" in the document) |
| S7 | A faulty SOUP blob (SDC/MPSL) cannot write to safety state | separate task, no shared mutable state except channels | design only | review of linker/memory layout; MPU use (not enabled today) |

Consequence: if S1 to S7 are verified, BLE host and UI may be Class B; otherwise they inherit Class C.

## 3. Hardware interlock as risk control and segregation boundary

The hardware interlock (`MOT_ALLOW = MCU_EN AND latch AND (DOCKED OR DIR_REVERSE)`, TPL5010, over-current cut) is **independent of software**: with arbitrary firmware behaviour, an undocked pod cannot step forward and a hung MCU loses the latch within one TPL5010 interval (about 2 to 4 s, to be measured, B11). It is a risk control in the ISO 14971 sense and a boundary for the argument above. It does **not** lower the class of the dosing software (see `01-safety-classification.md` section 4) because the amount delivered inside a watchdog window is not bounded in Rev A.

## 4. Open architecture items

- Interface specifications between items (`Hal`, channels) are only in code and `architecture.md`; a formal interface list is needed for class C (5.3.2).
- MPU/stack-overflow protection for the safety task (`flip-link` is used in the build script; no MPU).
- Dynamic behaviour: worst-case execution time of the tick and of a draw chunk (0.85 s blocking) vs the 1 s tick and 2 s watchdog; measure.
- The planned diagnostics module (WP-1) adds a persistent fault log and a `Pins` abstraction for host testing of the interlock logic (WP-3).
