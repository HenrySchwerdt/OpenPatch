//! Bench controller board, Ebyte E73-2G4M08S1CX (nRF52840), `electronics/bench/pin-assignment.md`.
//!
//! | Pad | GPIO   | Net          | Used as |
//! |-----|--------|--------------|---------|
//! |  1  | P1.11  | MOT_STBY     | GPIO out (STSPIN220 STBY/RESET, 100k pull-down) |
//! |  2  | P1.10  | MOT_MODE2    | GPIO out |
//! |  3  | P0.03  | DOCK_N       | GPIO in, active low (also feeds the hardware interlock) |
//! |  4  | P0.28  | WDT_DONE     | GPIO out (TPL5010 DONE), safety task only |
//! |  6  | P1.13  | MOT_MODE1    | GPIO out |
//! |  7  | P0.02  | I_SENSE      | SAADC AIN0 |
//! |  8  | P0.29  | BUZ_PWM      | PWM0 ch0 |
//! | 12  | P0.26  | I2C_SDA      | TWIM0 |
//! | 14  | P0.06  | I2C_SCL      | TWIM0 |
//! | 15  | P0.05  | VBUS_SENSE   | SAADC AIN3 |
//! | 16  | P0.08  | TMAG_INT     | not used by this firmware (reserved) |
//! | 17  | P1.09  | MOT_EN_FAULT | GPIO in/out (open drain style) |
//! | 18  | P0.04  | VMOT_SENSE   | SAADC AIN2 |
//! | 20  | P0.12  | MOT_STCK     | PWM1 ch0 |
//! | 22  | P0.07  | MOT_DIR      | GPIO out |
//! | 26  | P0.18  | NRST         | pin reset (UICR PSELRESET, see `uicr_setup`) |
//! | 28  | P0.15  | BTN_N        | GPIO in, active low |
//! | 30  | P0.17  | WDT_WAKE     | GPIO in (rising edge) |
//! | 32  | P0.20  | ARM_CLK      | GPIO out |
//! | 33  | P0.13  | LATCH_Q_MON  | GPIO in |
//! | 34  | P0.22  | KILL_N       | GPIO open drain |
//! | 35  | P0.24  | MCU_EN       | GPIO out |
//! | 36  | P1.00  | LED_ST       | GPIO out, active high |
//! | 38  | P1.02  | HALL_A       | QDEC A |
//! | 40  | P1.04  | HALL_B       | QDEC B |
//! | 42  | P1.06  | LED_ALM      | GPIO out, active high |
//!
//! Peripheral conflicts checked: PWM0 (buzzer) and PWM1 (STCK) are separate instances; QDEC takes
//! P1.02/P1.04 (any pins are allowed, no LED pin is connected); TWIM0 takes P0.26/P0.06; SAADC AIN0,
//! AIN2, AIN3 are three channels of one scan. P0.02..P0.05 are analog pins: not used digitally.
//! P0.30/P0.31 (UART test pads), P0.08 (TMAG_INT), P0.09/P0.10 (NFC) are left untouched.
use super::{take_common, BoardIo, Common, InterlockPins, WatchdogPins};
use embassy_nrf::saadc::Input;
use embassy_nrf::Peripherals;

pub const BOARD_NAME: &str = "bench-e73";
/// LEDs are active high on the bench board.
pub const LED_ACTIVE_HIGH: bool = true;
/// STSPIN220 motor driver fitted (EN/FAULT readiness and fault checks).
pub const HAS_MOTOR_DRIVER: bool = true;
#[allow(dead_code)]
pub const HAS_INTERLOCK: bool = true;
#[allow(dead_code)]
pub const HAS_WATCHDOG: bool = true;
/// I_SENSE (INA180A1 across the 1.0 ohm shunt) is fitted.
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
        mot_mode1: p.P1_13.into(),
        mot_mode2: p.P1_10.into(),
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
            kill_n: p.P0_22.into(),
            mcu_en: p.P0_24.into(),
            latch_q_mon: p.P0_13.into(),
        }),
        watchdog: Some(WatchdogPins { done: p.P0_28.into(), wake: p.P0_17.into() }),
    };
    (io, common)
}

/// Make P0.18 the hardware RESET pin (UICR PSELRESET[0] and [1] = P0.18, connected), so that the
/// TPL5010 RSTn pulse resets the MCU. The pin is a plain GPIO otherwise and the watchdog could not
/// reset the controller. Writing the UICR needs a reset to take effect: this resets once on the very
/// first boot of a fresh module. Runs before the radio stack starts.
pub fn uicr_setup() {
    use embassy_nrf::{uicr_write, WriteResult};
    const UICR_PSELRESET0: *mut u32 = 0x1000_1200 as *mut u32;
    const UICR_PSELRESET1: *mut u32 = 0x1000_1204 as *mut u32;
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
    if changed {
        defmt::warn!("UICR PSELRESET written, resetting once");
        cortex_m::peripheral::SCB::sys_reset();
    }
}
