# Board configurations

Exactly one board feature must be enabled (compile error otherwise): `board-bench-e73` (default), `board-nrf52840-dk` or `board-cup-v4` (the v0.1.0 cup pod: pin map, HAL and the open items in `docs/board-cup-v4.md`; `angle-tmag` only).
Everything board specific is in `openpatch-bench/src/board/{e73,dk}.rs` (pins as typed peripherals, polarity / presence consts).
Exactly one drive feature (NO default): `drive-nfp-608-26-45-cup59-miter-1-1` (primary and `scripts/build.sh` default, v0.1.0 cup pod as in the current CAD: miter pair 1:1, stadium bore 20.5 x 5.9 = 113.48 mm^2, 897 624 525 / 119 554 uU = 0.007508 U/step, id 0x27; no check valve, so `FillMode::Draw` is refused and only the assisted pressure fill exists; reservoir capacity stays the nominal 100 / 200 U although the CAD tank holds 132.5 / 239.3 U), `drive-nfp-608-26-45-cup-miter-1-1` (the same cup pod with the PREVIOUS 20.5 x 5.5 tank, 0.00703 U/step, id 0x26: only for pods built with that tank, never on a 5.9 tank; no check valve either), `drive-nfp-608-26-45-g16-20` (bench variant, previous primary: GHW module 0.3 step-down pair 16T->20T, total ratio 33.0625, 0.003949 U/step, id 0x25), `drive-nfp-608-26-45-g15-12` (gear pair 15T->12T, ratio 21.16, id 0x24) and `drive-nfp-608-26-45-g1-1` (coaxial, 0x20), both NOT the current CAD and kept as options only, `drive-syringe-rig-1ml` (bench rig, 0x30), `drive-zwbpd006006-6-43`, `drive-zwbpd006006-4-8`, `drive-faulhaber-adm0620-16`. Exactly one angle feature: `angle-tmag` (default) or `angle-qdec-fallback`; `coarse-qdec` is an optional cross-check log. The e73 pin map below is the Rev A STEPPER map (STSPIN220) of `electronics/bench/pin-assignment.md`.

## `board-bench-e73`: bench controller board (Ebyte E73-2G4M08S1CX), `electronics/bench/pin-assignment.md` (Rev A) applied exactly

Single source of truth: `electronics/bench/pin-assignment.md`; the interlock, its readbacks, the POST and the FMEA: `electronics/bench/INTERLOCK.md`.
All 29 GPIOs of the module are used. Everything pin specific is in `openpatch-bench/src/board/e73.rs`.

| Pad | GPIO | Net | Used as |
|---|---|---|---|
| 1 | P1.11 | MOT_STBY | GPIO out (also read back), STSPIN220 STBY/RESET, 100k pull-down. **Low whenever the driver is idle** (both phases at 160 mA are about 1.4 W) |
| 2 | P1.10 | DOCK_TEST | GPIO out, self-test: high pulls `DOCKED_H` low (forces "undocked" at the gate). Can never force docked |
| 3 | P0.03 | DOCK_N | GPIO in, active low (pod dock hall, 100k pull-up: an unplugged FFC reads "not docked") |
| 4 | P0.28 | WDT_DONE | GPIO out through the qualifier. **Idle LOW, ONE pulse within 20 ms after the WAKE rising edge**, issued by the EGU3 interrupt (`hal/wdt.rs`) |
| 6 | P1.13 | POD_ID_N | GPIO in, low = pod board present (FFC loopback, 10 k on the pod) |
| 7 | P0.02 / AIN0 | I_SENSE | SAADC AIN0 (gain 1/6, 0.6 V ref, 20 us). **I [mA] = mV / 6.67** (INA180A1 on 0.333 ohm). Saturates at about 3.25 V = 490 mA |
| 8 | P0.29 | BUZ_PWM | PWM0 ch0, 2.7 kHz 50 % |
| 9 | P0.31 | DIR_REV | GPIO in (diag): the DIR_REVERSE level as seen at the interlock gate (Q10), high = reverse |
| 10 | P0.30 | DOCKED_H | GPIO in (diag): the DOCKED level as seen at the gate (Q6), high = docked |
| 12 / 14 | P0.26 / P0.06 | I2C SDA / SCL | TWIM0 (TMAG5273, 0x35) |
| 15 | P0.05 / AIN3 | VBUS_SENSE | SAADC AIN3 (x2 divider, 40 us) |
| 16 | P0.08 | OC_TEST | GPIO out, self-test: high lowers the over-current reference to about 45 mA. Can only make the trip easier |
| 17 | P1.09 | MOT_EN_FAULT | in (fault, low) / driven low to disable the stage |
| 18 | P0.04 / AIN2 | VMOT_SENSE | SAADC AIN2 (x2 divider, 40 us) |
| 20 | P0.12 | MOT_STCK | PWM1 ch0 |
| 22 | P0.07 | MOT_DIR | GPIO out; **also the interlock gate** (same net as DIR_REV through R96). Set first in every power-up |
| 26 | P0.18 | NRST | reset pin (UICR PSELRESET) |
| 28 | P0.15 | BTN_N | GPIO in, active low |
| 30 | P0.17 | WDT_WAKE | GPIOTE channel 7 (rising) -> PPI ch2 -> EGU3 interrupt |
| 32 | P0.20 | ARM_CLK | GPIO out (also read back), rising edge = ARM, idle low |
| 33 | P0.13 | LATCH_Q | GPIO in (diag), firmware name `LATCH_Q_MON` |
| 34 | P0.22 | LATCH_CLR_N | GPIO open drain (low = clear latch, never driven high; also read back). **Held low at idle** |
| 35 | P0.24 | MCU_EN | GPIO out **and read back** (input buffer connected while driven): the level seen by the gate Q8 and the over-current latch clear |
| 36 | P1.00 | LED_ST_G | GPIO out, active high |
| 38 / 40 | P1.02 / P1.04 | HALL_A / HALL_B | optional DRV5032 pair, QDEC only for `angle-qdec-fallback` / `coarse-qdec` |
| 41 | P0.09 | OC_OK | GPIO in (diag), NFC pin as GPIO: high = OK, low = over-current latch tripped (supply cut) |
| 42 | P1.06 | LED_ALM_G | GPIO out, active high |
| 43 | P0.10 | PGATE_MON | GPIO in (diag), NFC pin as GPIO: **low = MOT_ALLOW true** (supply switch on), high = off |

Removed since the previous revision: `MOT_MODE1` / `MOT_MODE2` (the STSPIN220 MODE pins are hard-wired low: **full step is forced** whatever STCK / DIR do at the STBY edge, DS11633 6.2 / Table 8, so there is
no sequencing requirement), the UART pads, `TMAG_INT`, `SMA_*`. The old `KILL_N` is now `LATCH_CLR_N`.

### The interlock and what the firmware checks (`openpatch_core::bench_ctl`, host tested; `openpatch-bench/src/hal/driver.rs` only binds it to the pins)

`MOT_ALLOW = MCU_EN AND LATCH_Q AND OC_OK AND (DOCKED_H XOR DIR_REV)`, `VMOT = VBUS` through the P-FET Q4 while `MOT_ALLOW`. The over-current latch (comparator U8 + latch U9, trip about 450 mA total supply current) is
cleared **only** by cycling `MCU_EN` low. The firmware can only remove permission; the self-test pins `DOCK_TEST` and `OC_TEST` are pull-down paths that make a leg block / trip more easily.

Readbacks (`Hal::interlock_state`, RB1..RB10): `PGATE_MON` (RB1), `DOCKED_H`, `DIR_REV`, `LATCH_Q`, `OC_OK`, `VMOT_SENSE`, `I_SENSE`, own-pin readback of `MCU_EN` / `ARM_CLK` / `LATCH_CLR_N` / `STBY`, `EN/FAULT`, `POD_ID_N`; plus `VBUS_SENSE`, the
SAADC `VDD` channel (3V3 rail), TMAG ACK + DEVICE_ID. Rev A has **no** mid-chain readbacks (RB2 / RB3 are `None`), so a stuck-pass Q6 / Q10 pair is reported as one finding.

Power-up (`interlock::power_up_plan`): DIR to the burst direction (**first**), release `LATCH_CLR_N`, `MCU_EN` high, one `ARM_CLK` edge, `LATCH_Q` must read high, `PGATE_MON` must show `MOT_ALLOW` **and** `VMOT_SENSE` the supply,
`OC_OK` must still be high, then STBY high and EN/FAULT must release. Power-down: STBY low, EN/FAULT driven low, then **one gate cuts, rotating** (burst k: `MCU_EN` only, k+1: `LATCH_CLR_N` only, k+2: both); the collapse
(`PGATE_MON` high and `VMOT_SENSE` below the cut level) is verified; if it does not happen the second gate follows at once and the stuck leg is named (`1-07-001` / `1-07-002`). A supply that stays up while `PGATE_MON`
is high is **Q4 shorted**: nothing on the board can cut it, so the controller is QUARANTINED (`1-06-001`, STBY low for good, no power-up, MCU kept alive for the alarm "replace the controller board", DONE not withheld because a reset can not help).

### POST (`BenchCtl::selftest`, run by `Pump::run_self_test`; the pod must be SUSPENDED)

| Step | `SelfTestStep` | Proves | Failure -> code |
|---|---|---|---|
| POST-S | `PassiveChecks` (every boot via `BenchHal::boot_post_s`, and `RunSelfTest` sub-op 1) | supply absent (`VMOT_SENSE` < 0.3 V, `PGATE_MON` high), `LATCH_Q` low, `OC_OK` high, own pins as driven (STBY low), `DIR_REV` low at the forward level, VBUS 4.5 to 5.5 V, 3V3 3.0 to 3.6 V, `I_SENSE` idle offset, FFC / pod (`POD_ID_N`, TMAG ACK), `DOCKED_H` = NOT `DOCK_N` | `1-06-001` (Q4), `1-05-003`, `1-07-003` / `1-07-006` (dock path), `1-07-007` (own pin / OC), `4-40-003`, `A-A2-001/002`, `1-09-001`, `1-02-001/002`, `1-08-001/002`, `3-30-001` (FFC), `3-30-004` (docked without the pod) |
| A01 | `GateCut` | latch sets (`MCU_EN` low: supply stays off, Q8 leg blocks); supply up via DOCK_TEST + reverse level; **cut with `LATCH_CLR_N` only**, then re-arm and **cut with `MCU_EN` only**, each verified on `PGATE_MON` and `VMOT_SENSE` | `1-05-002`, `1-05-001`, `1-07-002`, `1-07-001`, `1-06-001`, `1-06-002` |
| A02 | `DockGateBlock` | with DOCK_TEST (undocked at the gate, works docked too) forward must stay off for 50 ms; reverse must conduct and `DIR_REV` follow; forward again must cut | `1-07-003` (Q6 / Q10 pair), `1-07-004`, `1-07-007` inst 6 (dead DIR path), `4-40-003` (inverted polarity), `1-06-001` |
| A13 | `ReverseDockedBlock` | H14 (DOCKED XOR DIR_REV): with the pod really docked, docked + forward conducts, then DIR reverse must cut (`DOCK_TEST` can only force undocked, so the proof is UNKNOWN when undocked; A02 proves the other wrong combination, undocked + forward) | `1-07-008` |
| A12 | `OverCurrentCut` | with the coils holding (STBY high, no step, at most 100 ms, needs `I_SENSE` >= 60 mA) `OC_TEST` must trip the latch (`OC_OK` low) and cut the supply; the latch clears only by cycling `MCU_EN` | `1-07-007` inst 7 (comparator / latch / Q13), `1-07-005` (latch stuck tripped), UNKNOWN when the motor draws no holding current |

Every proof ends in the safe state (STBY low, `MCU_EN` low, latch held clear, test pins low, DIR forward level), also when it fails. The proofs never drive the motor (STBY stays low) except the bounded coil hold of A12. A proof that can not be made (DK, motor not
connected, `DOCK_TEST` without effect, quarantined board) stays UNKNOWN: `SelfTestOutcome::Unsupported`, never "passed". `1-07-007` instances: 1 `MCU_EN`, 2 `ARM_CLK`, 3 `LATCH_CLR_N`, 4 `STBY`, 5 `WDT_DONE`, 6 `MOT_DIR`, 7 over-current leg.
The catalogue has no dedicated code for the over-current leg; it is mapped to `1-07-007` (instance 7) until the catalogue owner adds `GATE_OC_STUCK_PASS` (see docs/stubs.md).

### DIR polarity (R96 / R97)

`DIR_FORWARD_HIGH = false` for the default hardware (R96 fitted: `DIR_REV` = `MOT_DIR`, DIR high = reverse = retract); cargo feature `dir-forward-high` for R97 instead of R96. `openpatch_core::interlock::dir_level_high` maps direction to the pin level and is tested for both
polarities; the controller refuses nothing on its own but **POST detects a mismatch**: with the wrong pairing `DIR_REV` reads reverse at the forward level (`4-40-003`). Which level physically retracts depends on lead order, gear pair and thread hand:
confirm in bench test T5 (docs/bench-testing.md); the core's own check (a reverse burst whose angle moves forward) raises the same code.

### Watchdog (TPL5010 behind the qualifier U10)

A DONE rising edge counts only while WAKE is high (<= 20 ms after the WAKE edge): stuck, early and late edges are rejected in hardware. `hal/wdt.rs`: `WDT_WAKE` is a GPIOTE channel event, PPI ch2 links it to the EGU3 task, the EGU3 interrupt (above the safety executor) pulses
`WDT_DONE` for about 3 us **only inside the permit** `DONE_PERMIT_UNTIL_MS`, which the safety task renews after every verified tick (`DONE_PERMIT_MS` = 1.5 s) and the POST renews while it runs. A hung or failed safety task lets the permit lapse and the TPL5010 resets the MCU (RSTn clears the latch).
The bootloader answers WAKE in pure hardware during a DFU swap (`openpatch-bootloader`, `done_path`). Not rejected by the board (honest limit, INTERLOCK.md B): a peripheral that toggles DONE faster than the window.

### UICR

`UICR.NFCPINS` = GPIO (P0.09 / P0.10 are `OC_OK` / `PGATE_MON`): `embassy_nrf::init` does it (masked write of bit 0, then a reset) because `board-bench-e73` enables the `embassy-nrf/nfc-pins-as-gpio` feature, which also makes `P0_09` / `P0_10` exist as pins. `uicr_setup()` writes `UICR.PSELRESET[0,1]` = P0.18 (hardware reset
for the TPL5010 `RSTn`), checks that NFCPINS really is GPIO (logs an error otherwise) and resets once. A fresh module therefore resets once or twice on the first boot. The readbacks do not matter for those resets (the gate is discrete logic) and the bootloader reads neither pin. If a UICR word holds another value: `probe-rs erase` once.

### Peripheral allocation and conflicts

PWM0 buzzer, PWM1 STCK (separate instances); QDEC (optional) accepts any pins; TWIM0 on P0.26 / P0.06; one SAADC scan of AIN0 / AIN2 / AIN3 and `VDD` (analog pins P0.02 to P0.05 are not used digitally); TIMER1 counts steps; PPI ch0 / ch1 are the step counter's, **ch2 the WAKE link**; GPIOTE channel 7 and EGU3 are the
WAKE path; RTC1 time driver; RTC0, TIMER0, TEMP, PPI ch17 to 31 and RNG belong to the radio stack. EGU3 (SWI3) is not documented as used by MPSL / SDC (EGU0 and the SDC's own are): UNVERIFIED on hardware. 32.768 kHz crystal on P0.00 / P0.01 is the LF clock source (MPSL and embassy both configured for it).

Analog scaling (`config.rs`, `hal/adc.rs`, `openpatch_core::limits`): counts to mV = raw x 3600 / 4096; **I_SENSE: mA = mV x 3 / 20 (20 V/V x 0.333 ohm = 6.67 mV per mA: 3.3 V = 495 mA, hardware over-current at 3.0 V = 450 mA)**, derived in one place (`limits::I_SENSE_UV_PER_MA`) and tied to
`controller/parts.json` by a host test (R31 / R39 / R47 = 3 x 1.0 ohm, INA180A1); VBUS and VMOT: x 2; VDD: direct. `Hal::battery_mv` reports VBUS (about 5000 mV). A USB sag below 3500 / 3300 mV raises LOW_BATTERY / BATTERY_CRITICAL on purpose.

Angle: primary = TMAG5273 over TWIM0 (0x35, P0.26 / P0.06, `hal/tmag.rs`), `Hal::angle_read` returns the cumulative unwrapped 12 bit angle (4096 counts per leadscrew turn), `None` when it does not answer.
**Sensor plane**: the spindle magnet (axis along the leadscrew = pod X) rotates its field in the pod **Y-Z** plane, so the angle is computed from the Y and Z channels (`tmag5273::AnglePlane::YZ`, default; features `tmag-plane-xy` / `tmag-plane-xz` after the hand-turned-rod check T12), range **+-80 mT** on both axes
(the field is estimated at 34 to 41 mT: marginal for +-40 mT; `tmag-range-40mt` restores it). The package-axis to pod-axis mapping is taken from the review and the layout drawing, NOT verified against the datasheet figure: UNVERIFIED until T12.
The DRV5032FA quadrature on P1.02 / P1.04 is only used by `angle-qdec-fallback` (1024 counts per edge, 1 pole pair placeholder, NOT sufficient for the 3 %/turn check) and by `coarse-qdec` (log only).
Draw mode needs the pump undocked: with the gate `MOT_ALLOW = MCU_EN AND LATCH_Q AND OC_OK AND (DOCKED_H XOR DIR_REV)` the firmware sets MOT_DIR to the reverse level BEFORE `MCU_EN` / ARM (docs/stubs.md item 2).

## `board-nrf52840-dk`: Nordic nRF52840-DK (PCA10056)

No motor driver, interlock, TPL5010 or current shunt. The STCK pin simply toggles; the interlock and watchdog are absent
(`interlock: None`, `watchdog: None`); STSPIN220 readiness / fault checks are skipped; `motor_current_peak_ma` is `None`;
`battery_mv` is fixed at 4000 mV; DOCKED is simulated; the angle is simulated exactly from the executed pulses (forward and reverse, so draw works). The hall pins can be wired to QDEC for `angle-qdec-fallback` / `coarse-qdec` experiments (the simulated value is still what the core sees). LEDs are active LOW.

| Function | DK pin | Notes |
|---|---|---|
| LED_ST (status) | P0.13 (LED1) | active low |
| LED_ALM (alarm) | P0.14 (LED2) | active low |
| pod button | P0.11 (BUTTON1) | short = pairing window + silence, hold 3 s = emergency stop |
| DOCKED simulation | P0.12 (BUTTON2) | each press toggles; **docked at boot** (`DOCK_SIM_INITIAL`) so headless runs work |
| MOT_STCK | P1.05 (Arduino D4) | PWM1, toggles at 200 Hz during a burst |
| MOT_DIR | P1.06 (D5) | |
| MOT_STBY | P1.10 (D8) | |
| MOT_EN_FAULT | P1.11 (D9) | pulled up |
| HALL_A / HALL_B | P1.01 (D0) / P1.02 (D1) | QDEC, internal pull-ups |
| BUZ_PWM | P1.12 (D10) | PWM0, 2.7 kHz |
| I_SENSE / VMOT_SENSE / VBUS_SENSE | P0.03 (A0) / P0.04 (A1) / P0.28 (A2) | sampled, values meaningless without hardware |
| I2C SDA / SCL | P0.26 / P0.27 | optional TMAG5273 |

DK pins are taken from the nRF52840-DK Arduino header numbering (A0 = P0.03, A1 = P0.04, A2 = P0.28, D0 to D13 = P1.01 to P1.15 without
P1.09, SDA/SCL = P0.26/P0.27); check against the board documentation if something does not respond. P0.05 to P0.08 (UART bridge),
P0.09/P0.10 (NFC), P0.17 to P0.23 (QSPI flash) and P0.18 (reset) are avoided.
Run on the DK: `cargo run --release --no-default-features --features board-nrf52840-dk,angle-tmag,drive-nfp-608-26-45-g16-20,dev-plaintext`.

## Software DOCKED (`dock-simulated`) and the interlock board

`dock-simulated` reports DOCKED from software (initial docked; on the DK BUTTON2 toggles it, which is also how a draw is made possible). It is always the case on the DK. On
`board-bench-e73` it is `compile_error!` unless `unsafe-bench-override` is also given, because the hardware interlock gate (`MOT_ALLOW = MCU_EN AND LATCH_Q AND OC_OK AND (DOCKED_H XOR DIR_REV)`) must
not be undermined by a firmware flag; even with the override the supply gate still needs the real DOCKED signal (only the firmware's own checks are fooled), and without a toggle
button the pump can never be undocked for a draw. Draw on the bench controller board goes through DIR_REVERSE (docs/stubs.md), not through a software DOCKED.

### H14 / H15 (spec 7a): DOCKED XOR DIR_REVERSE and the pressure anomaly

The gate is now `DOCKED_H XOR DIR_REV`: forward only docked, reverse only undocked, both wrong combinations are cut in hardware. Firmware refuses a reverse request while docked before any pin moves (`interlock::check_request`, `MotorFault::ReverseWhileDocked`, raised as `7-70-008`).
POST: A02 proves undocked + forward is cut and undocked + reverse conducts, A13 proves docked + reverse is cut (needs the real dock). `5-54-001 PRESSURE_ANOMALY_WHILE_DOCKED` (latched): docked, motor not driven since the last tick, leadscrew angle moved by more than `PRESSURE_ANOMALY_ANGLE_COUNTS` (300 counts, 0.19 U): the self-locking drive was back-driven (possible manual injection). Catalogue schema is now 2 (153 codes).
