# Board configurations

Exactly one board feature must be enabled (`compile_error!` otherwise): `board-bench-e73` (default) or `board-nrf52840-dk`.
Everything board specific is in `openpatch-bench/src/board/{e73,dk}.rs` (pins as typed peripherals, polarity / presence consts).
Exactly one drive feature (NO default): `drive-nfp-608-26-45` (primary), `drive-zwbpd006006-6-43`, `drive-zwbpd006006-4-8`, `drive-faulhaber-adm0620-16`. Exactly one angle feature: `angle-tmag` (default) or `angle-qdec-fallback`; `coarse-qdec` is an optional cross-check log. The pin map below is the STEPPER map (STSPIN220); the board documentation currently in the repository differs, see docs/stubs.md.

## `board-bench-e73`: bench controller board (Ebyte E73-2G4M08S1CX), `electronics/bench/pin-assignment.md` applied exactly

| Pad | GPIO | Net | Used as |
|---|---|---|---|
| 1 | P1.11 | MOT_STBY | GPIO out, STSPIN220 STBY/RESET (100k pull-down) |
| 2 | P1.10 | MOT_MODE2 | GPIO out (latched at STBY rising edge) |
| 3 | P0.03 | DOCK_N | GPIO in, active low (also feeds the interlock) |
| 4 | P0.28 | WDT_DONE | GPIO out, TPL5010 DONE, safety task only |
| 6 | P1.13 | MOT_MODE1 | GPIO out |
| 7 | P0.02 / AIN0 | I_SENSE | SAADC ch0 (gain 1/6, 0.6 V ref, 20 us) |
| 8 | P0.29 | BUZ_PWM | PWM0 ch0, 2.7 kHz 50 % |
| 9 / 10 | P0.31 / P0.30 | UART TX / RX | not used (test pads) |
| 12 / 14 | P0.26 / P0.06 | I2C SDA / SCL | TWIM0 (TMAG5273 probe, 0x35) |
| 15 | P0.05 / AIN3 | VBUS_SENSE | SAADC ch2 (x2 divider, 40 us) |
| 16 | P0.08 | TMAG_INT | unused (reserved) |
| 17 | P1.09 | MOT_EN_FAULT | in (fault, low) / driven low to disable the stage |
| 18 | P0.04 / AIN2 | VMOT_SENSE | SAADC ch1 (x2 divider, 40 us) |
| 20 | P0.12 | MOT_STCK | PWM1 ch0 |
| 22 | P0.07 | MOT_DIR | GPIO out |
| 26 | P0.18 | NRST | reset pin: UICR PSELRESET[0,1] written at first boot |
| 28 | P0.15 | BTN_N | GPIO in, active low |
| 30 | P0.17 | WDT_WAKE | GPIO in, rising edge (flag only) |
| 32 | P0.20 | ARM_CLK | GPIO out, rising edge = ARM |
| 33 | P0.13 | LATCH_Q_MON | GPIO in |
| 34 | P0.22 | KILL_N | GPIO open drain (low = kill, never driven high) |
| 35 | P0.24 | MCU_EN | GPIO out |
| 36 | P1.00 | LED_ST | GPIO out, active high |
| 38 / 40 | P1.02 / P1.04 | HALL_A / HALL_B | QDEC, only for `angle-qdec-fallback` / `coarse-qdec` (internal pull-ups, no LED pin) |
| 42 | P1.06 | LED_ALM | GPIO out, active high |

Peripheral allocation and conflicts: PWM0 buzzer, PWM1 STCK (separate instances); QDEC accepts any pins (P1.02 / P1.04 are fine, the LED
pin stays disconnected); TWIM0 on P0.26 / P0.06; one SAADC scan of AIN0 / AIN2 / AIN3 (analog pins P0.02 to P0.05 are not used
digitally); TIMER1 counts steps; PPI ch0 / ch1 are the application's; RTC1 time driver; RTC0, TIMER0, TEMP, PPI ch17 to 31 and RNG
belong to the radio stack. 32.768 kHz crystal on P0.00 / P0.01 is used as LF clock source (MPSL and embassy both configured for it).

STSPIN220 mode: MODE1 = MODE2 = low latched at the STBY edge = **full step** (one core step = one full motor step, 20 steps/rev).
STCK idles low (it is MODE3), DIR is set to the forward level before STBY goes high (`config::DIR_FORWARD_HIGH`).

UICR: P0.18 must be the hardware reset pin or the TPL5010 RSTn cannot reset the MCU. `board::uicr_setup()` writes
`UICR.PSELRESET[0]` and `[1]` (= P0.18) before the radio starts and does one system reset the first time on a fresh module.
If the UICR already holds another value it logs an error: erase the UICR once (`probe-rs erase`).

Analog scaling (`config.rs`, `hal/adc.rs`): counts to mV = raw x 3600 / 4096; I_SENSE: mA = mV / 20 (20 V/V x 1.0 ohm: 3.3 V = 165 mA,
full scale 3.6 V = 180 mA); VBUS and VMOT: x 2. `Hal::battery_mv` reports VBUS (about 5000 mV). A USB sag below 3500 / 3300 mV raises
LOW_BATTERY / BATTERY_CRITICAL on purpose.

Angle: primary = TMAG5273 over TWIM0 (0x35, P0.26 / P0.06, `hal/tmag.rs`), `Hal::angle_read` returns the cumulative unwrapped 12 bit angle (4096 counts per leadscrew turn),
`None` when it does not answer. The DRV5032FA quadrature on P1.02 / P1.04 is only used by `angle-qdec-fallback` (1024 counts per edge, 1 pole pair placeholder, NOT
sufficient for the 3 %/turn check) and by `coarse-qdec` (log only). The DRV5032 output is sampled at 20 Hz: valid for <= about 5 edges/s only.
Draw mode needs the pump undocked, which the DOCKED interlock gate prevents on this board (docs/stubs.md).

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
| MOT_MODE1 / MOT_MODE2 | P1.07 (D6) / P1.08 (D7) | |
| MOT_STBY | P1.10 (D8) | |
| MOT_EN_FAULT | P1.11 (D9) | pulled up |
| HALL_A / HALL_B | P1.01 (D0) / P1.02 (D1) | QDEC, internal pull-ups |
| BUZ_PWM | P1.12 (D10) | PWM0, 2.7 kHz |
| I_SENSE / VMOT_SENSE / VBUS_SENSE | P0.03 (A0) / P0.04 (A1) / P0.28 (A2) | sampled, values meaningless without hardware |
| I2C SDA / SCL | P0.26 / P0.27 | optional TMAG5273 |

DK pins are taken from the nRF52840-DK Arduino header numbering (A0 = P0.03, A1 = P0.04, A2 = P0.28, D0 to D13 = P1.01 to P1.15 without
P1.09, SDA/SCL = P0.26/P0.27); check against the board documentation if something does not respond. P0.05 to P0.08 (UART bridge),
P0.09/P0.10 (NFC), P0.17 to P0.23 (QSPI flash) and P0.18 (reset) are avoided.
Run on the DK: `cargo run --release --no-default-features --features board-nrf52840-dk,angle-tmag,drive-nfp-608-26-45,dev-plaintext`.
