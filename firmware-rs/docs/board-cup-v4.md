# `board-cup-v4`: cup pod v4, 45 fitted parts (HJ-840 SiP, DRV8835, STM32C011 supervisor)

> TEST PROJECT, never worn. Water only.

Pins: `openpatch-bench/src/board/cup_v4.rs` is the single place (table in its header); the source of truth is `electronics/v010/design/netlist_v4.py` / `netlist_v4_cup.json` (the HJ-840 table in `FIRMWARE-PINMAP.md` is stale). Only the bring-up binary `src/bin/cup_bringup.rs` uses it so far:

```sh
cd firmware-rs/openpatch-bench
cargo build --release --target thumbv7em-none-eabihf --no-default-features --features board-cup-v4 --bin cup_bringup
```

The pump application (`main.rs`) is still the E73 / DK application and is NOT ported.

## Host tested pieces (`openpatch-core`, the bring-up binary only binds them to pins)

* `phase_drive`: DRV8835 full steps on `APHASE/AENBL/BPHASE/BENBL`. `(A,B)` = 00, 10, 11, 01 forward, reverse order for reverse, exactly one PHASE toggle per step (the supervisor counts these edges), brake (`AENBL = BENBL = 0`) at idle, PHASE lines untouched when de-energising, enables raised after and lowered before the phase lines.
* `burst`: bursts with rest gaps for the cell's peak current. `CellParams` (default Ampul 301030: 60 mAh realistic, 700 mA pulse limit, 150 ms, 90 mA average, 250 ms minimum rest) and `MotorLoad` (1.74 W, 88 %) are configurable PLACEHOLDERS: the vendor page gives no discharge rate. Default plan: 29 steps per burst at 200 pps, rest about 0.7 s at 3.8 V.
* `battery`: `vddhdiv5_to_mv` (SAADC `VDDHDIV5`, 12 bit, 0.6 V reference, gain 1/6: `mV = raw x 18000 / 4096`), the cell supply policy (next section), `regout0_action` (`UICR.REGOUT0` = 3.3 V, HV mode: the HJ-840 has no LDO).
* `led`: charging pulse (red, 1 Hz), full = green, low = red (single flash, double below 3.4 V), fault 4 Hz, button shows the battery colour. `charger_state(usb_detected, stat_low)`: MCP73832 STAT cannot tell "done" from "no cable", so the cable comes from `USBDETECTED` (`VBUS_P`).
* `occlusion`: angle shortfall only (`SafetySupervisor::set_occlusion_source(AngleOnly)`): warning `5-53-004` above 1 U (two consecutive passes, hysteresis, auto clear on a new baseline), fault `5-53-001` above 2 U (spec 7, unchanged). The current-rise detector (`5-53-002/003`) is off on this board (no shunt).

## Cell supply policy (SPICE findings F2, F3; `electronics/v010/cup/sim/REPORT.md`)

The simulation showed that the droop margin depends on the unmeasured cell resistance (at 1.2 ohm or more the old 3.4 V resting lockout still lets VBAT fall below the nRF VDDH minimum of 2.5 V; at 1.6 ohm the supply collapses) and that the boost pre-charge draws about 1 A. All thresholds below are NEW limits that only tighten (spec section 7); nothing existing was relaxed. They live in `battery::MotorSupplyLimits`, which is `CellParams::supply` (`CellParams::AMPUL_301030` uses the defaults), so they are configuration data, not constants of the logic.

| Rule | Default | Configurable | Where |
|---|---|---|---|
| Boost enable (F3): resting VBAT at least | 3.4 V `BOOST_ENABLE_MIN_MV` | no | `battery::boost_enable_allowed`, first check of `start_gate` |
| No move starts (F2): resting VBAT below | 3.7 V `MOTOR_REST_MIN_MV`, INTERIM until the cell ESR is measured | 3.4 to 4.15 V (`MotorSupplyLimits::new` rejects the rest; a hand built lower value is clamped to 3.4 V on use) | `battery::start_gate`, `burst::plan_burst` (refusal `BatteryLow`) |
| Move stops (F2): VBAT under load, sampled after the first step of the burst, below | 2.8 V `MOTOR_LOAD_ABORT_MV` | 2.6 to 3.0 V (clamped to 2.6 V on use, so the check cannot be switched off) | `battery::LoadGuard` |
| Move stops: VBAT under load after 20 steps below | 3.0 V `MOTOR_LOAD_FLOOR_MV`, unchanged | no | `LoadGuard` (second check point) |

* **F3 dependency.** `start_gate` checks, in this order: charger, boost enable (3.4 V, independent of the configuration), rest threshold. With the defaults the 3.7 V rule subsumes the 3.4 V rule; the test `a_passed_start_gate_implies_the_boost_minimum_for_every_configuration` sweeps 0 to 5 V against every valid and a hand built configuration, so the boost can never be enabled below 3.4 V even if the rest threshold is lowered to the floor. Measure the resting voltage before `MCU_EN` goes high.
* **Loaded abort.** `LoadGuard::keep_going(steps_made, sample)` is the `keep_going` callback of `phase_drive::drive_burst` (asked before every step with the steps already made): it samples VBAT through the closure at `steps_made == 1` and `== 20` only, stops the burst on the first violation and stays tripped. A failed ADC sample must be reported as 0 mV (aborts). Burst rests are unchanged; a retry starts with the resting check again.
* **Diagnostics.** New code `A-A0-004` `CELL_SAG_UNDER_LOAD` (fault, FRU = cell `BATT`, action charge = `CHECK_POWER` in the generated tables, text "Battery too weak for the motor. Charge or replace the cell."; legacy fault bit 3 like `BATTERY_CRITICAL`, so resume needs an acknowledge after charging). Instance 1 = move stopped under load (`SagAbort::raise`: ctx_a = loaded mV, ctx_b = threshold, ctx_c = steps made); instance 2 = move refused at rest (`rest_refusal_raise`: ctx_a = resting mV, ctx_b = threshold). Catalogue schema 4, 155 codes.
* **Not changed / open.** The pin map is untouched. The bring-up binary (`cup_bringup`) plans with the defaults through `plan_burst`, so the 3.7 V rule applies there; it does not yet call `LoadGuard` (the ADC read is async, the burst callback is not): wiring that is part of porting the pump application. The status LED still shows "critical" below 3.4 V only, so between 3.4 and 3.7 V a refused start is reported by the `A-A0-004` fault, not by the LED colour. Replace the 3.7 V interim value after the cell ESR measurement and record it in spec section 7.

## Supervisor (`openpatch-supervisor`)

Platform independent logic of the STM32C011: PHASE-edge step counting, arm window (600 ms, 1 s reverse), 32-step forward budget (permit drops with the 32nd step, the 33rd latches), dead time, H15 and direction consistency, over-current lock-out (2 s), 3 faults in 10 minutes lock until a power cycle, leaky buckets, status frame. Mandatory POST vector: declared reverse (`MOT_FWD` = 0) with forward phase order drops `SUP_PERMIT` in the handler of the first edge. Flashing through the ST ROM bootloader (8E1 UART, AN3155 framing) is only possible through a `FlashSession`, which needs VMOT below 0.3 V for 50 ms, undocked, no delivery, a verified image, and re-checks the supply before every frame.

**Reset / brown-out hold-off (F7).** After ANY reset or brown-out `SUP_PERMIT` stays low for at least 10 ms (`MIN_RESET_HOLDOFF_MS`, `Config::reset_holdoff_ms`, cannot be configured below 10): `Supervisor::new` (the supervisor's own power-up or reset) starts it, `on_main_reset` and the new `on_brown_out` restart it, and `on_arm_edge` answers `ArmReject::ResetHoldoff` until it is over. It runs in parallel to the dead time and never shortens it. Tests: `openpatch-supervisor/tests/reset_holdoff.rs`.

Provisioning option bytes (`openpatch-supervisor/src/provisioning.rs`, `PROVISIONING_OPTION_BYTES`): option byte nBOOT_SEL = 0 and BOR level = highest (F7: a short 3V3 dip must reset the supervisor instead of leaving the motor enable latch set), both set in the same provisioning step. Read-out protection level 1 and the independent watchdog are set in that step as well (INTERLOCK.md H). The register bits are not hard-coded: the platform shell maps the table to FLASH_OPTR and verifies the read-back.

Other platform shell requirements (not in the repository): Stop mode with LPTIM / LSI (no 1 kHz sleep tick), `SUP_NRST` driven open drain only by the nRF.

## Hardware facts followed (review 2026-11-20)

The gate is `docked XOR reverse` (docked + reverse is cut in hardware; the core refuses it before a pin moves, the supervisor is a second line). `MCU_EN` is a hardware leg: direction first, then `ARM_CLK`, then `MCU_EN`; `MCU_EN` low before the direction returns to forward. The TPL5010 interval is about 2.0 s (`TPL5010_INTERVAL_MS`). I2C at 100 kHz, TMAG to sleep after boot. No 32 kHz crystal (`LfclkSource::InternalRC`).

## Not done

Porting the pump application to this board (replace the STSPIN220 `BenchCtl` / `Stepper` by `phase_drive` and the burst plan, `VMOT_SENSE` only), `USBDETECTED`, TMAG sleep, the TPL5010 kick path, the UART challenge/response, the nRF side of the supervisor update, the STM32C0 platform shell, USB DFU glue.
