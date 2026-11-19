//! Bench controller board, Ebyte E73-2G4M08S1CX, `electronics/bench/pin-assignment.md` (Rev A, stepper drive) applied exactly.
//! All 29 GPIOs of the module are used.
//!
//! | Pad | GPIO   | Net          | Used as |
//! |-----|--------|--------------|---------|
//! |  1  | P1.11  | MOT_STBY     | GPIO out (STSPIN220 STBY/RESET, 100k pull-down), low whenever idle |
//! |  2  | P1.10  | DOCK_TEST    | GPIO out, self-test: high forces "undocked" at the interlock gate |
//! |  3  | P0.03  | DOCK_N       | GPIO in, active low (pod dock hall, 100k pull-up) |
//! |  4  | P0.28  | WDT_DONE     | GPIO out through the qualifier: idle LOW, ONE pulse within 20 ms after the WAKE rising edge (`hal::wdt`) |
//! |  6  | P1.13  | POD_ID_N     | GPIO in, low = pod board present (FFC loopback) |
//! |  7  | P0.02  | I_SENSE      | SAADC AIN0, I[mA] = mV / 6.67 |
//! |  8  | P0.29  | BUZ_PWM      | PWM0 ch0 |
//! |  9  | P0.31  | DIR_REV      | GPIO in (diag): the DIR_REVERSE level at the gate, high = reverse |
//! | 10  | P0.30  | DOCKED_H     | GPIO in (diag): the DOCKED level at the gate, high = docked |
//! | 12  | P0.26  | I2C_SDA      | TWIM0 |
//! | 14  | P0.06  | I2C_SCL      | TWIM0 |
//! | 15  | P0.05  | VBUS_SENSE   | SAADC AIN3 (x2 divider) |
//! | 16  | P0.08  | OC_TEST      | GPIO out, self-test: high lowers the over-current reference |
//! | 17  | P1.09  | MOT_EN_FAULT | GPIO in/out (open drain style) |
//! | 18  | P0.04  | VMOT_SENSE   | SAADC AIN2 (x2 divider) |
//! | 20  | P0.12  | MOT_STCK     | PWM1 ch0 |
//! | 22  | P0.07  | MOT_DIR      | GPIO out; also the interlock gate (DIR_REV) |
//! | 26  | P0.18  | NRST         | pin reset (UICR PSELRESET, see `uicr_setup`) |
//! | 28  | P0.15  | BTN_N        | GPIO in, active low |
//! | 30  | P0.17  | WDT_WAKE     | GPIOTE channel 7 (rising) -> PPI ch2 -> EGU3 interrupt |
//! | 32  | P0.20  | ARM_CLK      | GPIO out, rising edge = ARM, idle low |
//! | 33  | P0.13  | LATCH_Q      | GPIO in (diag), firmware name LATCH_Q_MON |
//! | 34  | P0.22  | LATCH_CLR_N  | GPIO open drain (low = clear latch, never driven high) |
//! | 35  | P0.24  | MCU_EN       | GPIO out, read back through the input buffer |
//! | 36  | P1.00  | LED_ST_G     | GPIO out, active high |
//! | 38  | P1.02  | HALL_A       | optional DRV5032 output A (QDEC only for `angle-qdec-fallback` / `coarse-qdec`) |
//! | 40  | P1.04  | HALL_B       | optional DRV5032 output B |
//! | 41  | P0.09  | OC_OK        | GPIO in (diag), NFC pin used as GPIO: high = OK, low = tripped |
//! | 42  | P1.06  | LED_ALM_G    | GPIO out, active high |
//! | 43  | P0.10  | PGATE_MON    | GPIO in (diag), NFC pin used as GPIO: low = MOT_ALLOW true |
//!
//! The STSPIN220 MODE1 / MODE2 are hard-wired low (full step): the firmware has no MODE pins.
//! Peripheral conflicts checked: PWM0 (buzzer) and PWM1 (STCK) are separate instances; QDEC takes P1.02 / P1.04 (optional);
//! TWIM0 takes P0.26 / P0.06; SAADC AIN0, AIN2, AIN3 and VDD are four channels of one scan; P0.02..P0.05 are analog pins.
use super::{take_common, BoardIo, Common, InterlockPins, WatchdogPins};
use embassy_nrf::saadc::Input;
use embassy_nrf::Peripherals;

/// GPIO number of WDT_DONE (P0.28) and WDT_WAKE (P0.17) for the interrupt path in `hal::wdt` (port 0).
pub const WDT_DONE_PIN: u8 = 28;
pub const WDT_WAKE_PIN: u8 = 17;

pub const BOARD_NAME: &str = "bench-e73";
/// LEDs are active high on the bench board.
pub const LED_ACTIVE_HIGH: bool = true;
/// STSPIN220 motor driver fitted (EN/FAULT readiness and fault checks).
pub const HAS_MOTOR_DRIVER: bool = true;
#[allow(dead_code)]
pub const HAS_INTERLOCK: bool = true;
#[allow(dead_code)]
pub const HAS_WATCHDOG: bool = true;
/// I_SENSE (INA180A1 on the 0.333 ohm shunt, 6.67 mV per mA) is fitted.
pub const HAS_CURRENT_SENSE: bool = true;
/// VBUS_SENSE divider present: `Hal::battery_mv` reports VBUS.
pub const HAS_VBUS_SENSE: bool = true;
/// DOCK_N is a real pin (DRV5032FA through the FFC).
#[allow(dead_code)]
pub const DOCK_SIMULATED: bool = false;
/// The hall quadrature signals are real.
pub const ENCODER_SIMULATED: bool = false;
/// No internal pull-ups needed on DOCK_N / BTN_N (100k on the board).
pub const BUTTON_ACTIVE_LOW: bool = true;

pub fn take(p: Peripherals) -> (BoardIo, Common) {
    let common = take_common!(p);
    let io = BoardIo {
        mot_stck: p.P0_12.into(),
        mot_dir: p.P0_07.into(),
        mot_stby: p.P1_11.into(),
        mot_en_fault: p.P1_09.into(),
        hall_a: p.P1_02.into(),
        hall_b: p.P1_04.into(),
        dock_n: Some(p.P0_03.into()),
        dock_sim_button: None,
        button: p.P0_15.into(),
        led_status: p.P1_00.into(),
        led_alarm: p.P1_06.into(),
        buzzer: p.P0_29.into(),
        adc_isense: p.P0_02.degrade_saadc(),
        adc_vmot: p.P0_04.degrade_saadc(),
        adc_vbus: p.P0_05.degrade_saadc(),
        i2c_sda: p.P0_26.into(),
        i2c_scl: p.P0_06.into(),
        interlock: Some(InterlockPins {
            arm_clk: p.P0_20.into(),
            latch_clr_n: p.P0_22.into(),
            mcu_en: p.P0_24.into(),
            latch_q_mon: p.P0_13.into(),
            oc_ok: p.P0_09.into(),
            pgate_mon: p.P0_10.into(),
            dir_rev: p.P0_31.into(),
            docked_h: p.P0_30.into(),
            dock_test: p.P1_10.into(),
            oc_test: p.P0_08.into(),
            pod_id_n: p.P1_13.into(),
        }),
        watchdog: Some(WatchdogPins { done: p.P0_28.into(), wake: p.P0_17.into() }),
    };
    (io, common)
}

/// One-time UICR handling of the bench controller (runs before the radio stack starts).
///
/// * `UICR.NFCPINS` bit 0 = 0 (`PROTECT` disabled = GPIO): P0.09 (`OC_OK`) and P0.10 (`PGATE_MON`) are plain inputs. With the
///   erased value (NFC) both pads are the NFC antenna pins and the over-current and gate readbacks would read garbage.
///   This is done by `embassy_nrf::init` through the cargo feature `embassy-nrf/nfc-pins-as-gpio`, which the
///   `board-bench-e73` feature enables: a MASKED write of bit 0 only (it only ever clears a bit, so it can not fail on a fresh
///   module), followed by one system reset. It is also what makes `p.P0_09` / `p.P0_10` exist in the pin set.
/// * `UICR.PSELRESET[0]` and `[1]` = P0.18 (connected): the TPL5010 `RSTn` (net `NRST`) must be a hardware reset, or the
///   watchdog could not reset the MCU. `embassy_nrf::init` already programs this unless `reset-pin-as-gpio` is enabled; the
///   explicit write below keeps the check independent of that default and of the embassy version.
///
/// A fresh module therefore resets once or twice on its first boot (UICR writes need a reset). Nothing safety relevant depends on
/// the order: the interlock outputs are driven low by the first `new_driver`, `OC_OK` / `PGATE_MON` are read-backs only (the gate
/// itself is discrete logic), and the readbacks are not trusted before the reset because `uicr_setup` logs an error and the POST
/// (`1-01-003`) would flag a wrong UICR. If a UICR word holds another value it logs an error: erase the UICR once
/// (`probe-rs erase`). The bootloader needs no change: it reads neither pin, and the application programs the UICR the first time
/// it runs.
pub fn uicr_setup() {
    use embassy_nrf::{uicr_write, WriteResult};
    const UICR_PSELRESET0: *mut u32 = 0x1000_1200 as *mut u32;
    const UICR_PSELRESET1: *mut u32 = 0x1000_1204 as *mut u32;
    const UICR_NFCPINS: *const u32 = 0x1000_120C as *const u32;
    /// pin 18, port 0, CONNECT = 0 (connected).
    const P0_18_CONNECTED: u32 = 18;
    let mut changed = false;
    for reg in [UICR_PSELRESET0, UICR_PSELRESET1] {
        // SAFETY: both addresses are valid UICR registers of the nRF52840 (PSELRESET[0..1]).
        match unsafe { uicr_write(reg, P0_18_CONNECTED) } {
            WriteResult::Written => changed = true,
            WriteResult::Noop => {}
            WriteResult::Failed => defmt::error!("UICR PSELRESET holds another value; erase UICR (ERASEALL) once"),
        }
    }
    // SAFETY: 0x1000_120C is UICR.NFCPINS of the nRF52840 (read only here).
    let nfc = unsafe { UICR_NFCPINS.read_volatile() };
    if nfc & 1 != 0 {
        defmt::error!("UICR NFCPINS still selects NFC: P0.09 (OC_OK) / P0.10 (PGATE_MON) readbacks are not valid; erase UICR (ERASEALL) once");
    }
    if changed {
        defmt::warn!("UICR PSELRESET written, resetting once");
        cortex_m::peripheral::SCB::sys_reset();
    }
}
