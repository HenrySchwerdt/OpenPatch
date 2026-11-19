//! Nordic nRF52840-DK (PCA10056). Mapping table: `firmware-rs/docs/boards.md`.
//!
//! The DK has no motor driver, no interlock and no TPL5010: the STCK pin simply toggles, the
//! hardware interlock is compiled out, DOCKED is simulated with BUTTON2 (a press toggles, the
//! default at boot is DOCKED so headless bench runs work), and the encoder is simulated (the
//! executed steps are mirrored into the encoder value). The hall pins are wired to QDEC anyway so
//! the decoder can be exercised with jumper wires.
//!
//! | Function | DK pin | Notes |
//! |---|---|---|
//! | LED_ST (status) | P0.13 (LED1) | active LOW |
//! | LED_ALM (alarm) | P0.14 (LED2) | active LOW |
//! | button (pod) | P0.11 (BUTTON1) | active low, external pull-up |
//! | DOCKED toggle | P0.12 (BUTTON2) | pressing toggles simulated DOCKED |
//! | MOT_STCK | P1.05 (D4) | PWM1 |
//! | MOT_DIR | P1.06 (D5) | |
//! | MOT_MODE1 | P1.07 (D6) | |
//! | MOT_MODE2 | P1.08 (D7) | |
//! | MOT_STBY | P1.10 (D8) | |
//! | MOT_EN_FAULT | P1.11 (D9) | |
//! | HALL_A / HALL_B | P1.01 (D0) / P1.02 (D1) | QDEC (internal pull-ups) |
//! | BUZ_PWM | P1.12 (D10) | PWM0 |
//! | I_SENSE (AIN1) | P0.03 (A0) | analog input, not a real shunt |
//! | VMOT_SENSE (AIN2) | P0.04 (A1) | |
//! | VBUS_SENSE (AIN4) | P0.28 (A2) | not used (battery_mv is a fixed value) |
//! | I2C SDA / SCL | P0.26 / P0.27 | optional TMAG5273 |
use super::{take_common, BoardIo, Common};
use embassy_nrf::saadc::Input;
use embassy_nrf::Peripherals;

pub const BOARD_NAME: &str = "nrf52840-dk";
/// DK LEDs are active LOW.
pub const LED_ACTIVE_HIGH: bool = false;
/// STSPIN220 motor driver fitted (EN/FAULT readiness and fault checks).
pub const HAS_MOTOR_DRIVER: bool = false;
#[allow(dead_code)]
pub const HAS_INTERLOCK: bool = false;
#[allow(dead_code)]
pub const HAS_WATCHDOG: bool = false;
pub const HAS_CURRENT_SENSE: bool = false;
pub const HAS_VBUS_SENSE: bool = false;
#[allow(dead_code)]
pub const DOCK_SIMULATED: bool = true;
pub const ENCODER_SIMULATED: bool = true;
pub const BUTTON_ACTIVE_LOW: bool = true;

pub fn take(p: Peripherals) -> (BoardIo, Common) {
    let common = take_common!(p);
    let io = BoardIo {
        mot_stck: p.P1_05.into(),
        mot_dir: p.P1_06.into(),
        mot_mode1: p.P1_07.into(),
        mot_mode2: p.P1_08.into(),
        mot_stby: p.P1_10.into(),
        mot_en_fault: p.P1_11.into(),
        hall_a: p.P1_01.into(),
        hall_b: p.P1_02.into(),
        dock_n: None,
        dock_sim_button: Some(p.P0_12.into()),
        button: p.P0_11.into(),
        led_status: p.P0_13.into(),
        led_alarm: p.P0_14.into(),
        buzzer: p.P1_12.into(),
        adc_isense: p.P0_03.degrade_saadc(),
        adc_vmot: p.P0_04.degrade_saadc(),
        adc_vbus: p.P0_28.degrade_saadc(),
        i2c_sda: p.P0_26.into(),
        i2c_scl: p.P0_27.into(),
        interlock: None,
        watchdog: None,
    };
    (io, common)
}

/// Nothing to do on the DK (P0.18 already is the reset pin).
pub fn uicr_setup() {}
