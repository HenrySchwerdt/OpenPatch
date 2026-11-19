//! Board configuration: exactly one board feature selects the pin set.
//!
//! * `board-bench-e73` (default): `electronics/bench/pin-assignment.md`, applied exactly.
//! * `board-nrf52840-dk`: Nordic nRF52840-DK, see `firmware-rs/docs/boards.md`.
//!
//! Everything board specific is in this directory; the rest of the firmware only sees [`BoardIo`],
//! [`Common`] and the consts below.
use embassy_nrf::gpio::AnyPin;
use embassy_nrf::peripherals as per;
use embassy_nrf::saadc::AnyInput;
use embassy_nrf::Peri;

#[cfg(all(feature = "board-bench-e73", feature = "board-nrf52840-dk"))]
compile_error!("enable exactly one board feature (board-bench-e73 | board-nrf52840-dk)");
#[cfg(not(any(feature = "board-bench-e73", feature = "board-nrf52840-dk")))]
compile_error!("enable exactly one board feature (board-bench-e73 | board-nrf52840-dk)");

#[cfg(feature = "board-bench-e73")]
mod e73;
#[cfg(feature = "board-bench-e73")]
pub use e73::*;

#[cfg(feature = "board-nrf52840-dk")]
mod dk;
#[cfg(feature = "board-nrf52840-dk")]
pub use dk::*;

/// Hardware interlock pins (E73 bench board only): `VMOT on = latch AND MCU_EN AND DOCKED`.
pub struct InterlockPins {
    /// Latch clock: rising edge = ARM. Idle low.
    pub arm_clk: Peri<'static, AnyPin>,
    /// Open drain, low = clear latch (motor off). Never driven high.
    pub kill_n: Peri<'static, AnyPin>,
    /// Direct MCU enable (second series gate). High = allow.
    pub mcu_en: Peri<'static, AnyPin>,
    /// Read-back of the latch output (MOT_ALLOW).
    pub latch_q_mon: Peri<'static, AnyPin>,
}

/// External TPL5010 watchdog pins.
pub struct WatchdogPins {
    /// DONE: pulse high after each WAKE. Driven ONLY from the safety task.
    pub done: Peri<'static, AnyPin>,
    /// WAKE pulse (rising edge sensed by a small helper task that only sets a flag).
    pub wake: Peri<'static, AnyPin>,
}

/// All board pins by function.
pub struct BoardIo {
    pub mot_stck: Peri<'static, AnyPin>,
    pub mot_dir: Peri<'static, AnyPin>,
    pub mot_mode1: Peri<'static, AnyPin>,
    pub mot_mode2: Peri<'static, AnyPin>,
    pub mot_stby: Peri<'static, AnyPin>,
    pub mot_en_fault: Peri<'static, AnyPin>,
    pub hall_a: Peri<'static, AnyPin>,
    pub hall_b: Peri<'static, AnyPin>,
    /// DOCK_N (active low). `None` on boards that simulate DOCKED with a button.
    pub dock_n: Option<Peri<'static, AnyPin>>,
    /// BUTTON2 on the DK: toggles the simulated DOCKED state.
    pub dock_sim_button: Option<Peri<'static, AnyPin>>,
    pub button: Peri<'static, AnyPin>,
    pub led_status: Peri<'static, AnyPin>,
    pub led_alarm: Peri<'static, AnyPin>,
    pub buzzer: Peri<'static, AnyPin>,
    pub adc_isense: AnyInput<'static>,
    pub adc_vmot: AnyInput<'static>,
    pub adc_vbus: AnyInput<'static>,
    pub i2c_sda: Peri<'static, AnyPin>,
    pub i2c_scl: Peri<'static, AnyPin>,
    pub interlock: Option<InterlockPins>,
    pub watchdog: Option<WatchdogPins>,
}

/// Peripherals that are board independent. Reserved for the radio stack (MPSL / SDC): RTC0, TIMER0,
/// TEMP, PPI channels 17 to 31 and RNG; RTC1 is the embassy time driver. The application owns
/// TIMER1 (step counter), PPI channels 0 and 1, PWM0 (buzzer), PWM1 (STCK), QDEC, SAADC, TWISPI0.
pub struct Common {
    pub rtc0: Peri<'static, per::RTC0>,
    pub timer0: Peri<'static, per::TIMER0>,
    pub temp: Peri<'static, per::TEMP>,
    pub ppi_ch17: Peri<'static, per::PPI_CH17>,
    pub ppi_ch18: Peri<'static, per::PPI_CH18>,
    pub ppi_ch19: Peri<'static, per::PPI_CH19>,
    pub ppi_ch20: Peri<'static, per::PPI_CH20>,
    pub ppi_ch21: Peri<'static, per::PPI_CH21>,
    pub ppi_ch22: Peri<'static, per::PPI_CH22>,
    pub ppi_ch23: Peri<'static, per::PPI_CH23>,
    pub ppi_ch24: Peri<'static, per::PPI_CH24>,
    pub ppi_ch25: Peri<'static, per::PPI_CH25>,
    pub ppi_ch26: Peri<'static, per::PPI_CH26>,
    pub ppi_ch27: Peri<'static, per::PPI_CH27>,
    pub ppi_ch28: Peri<'static, per::PPI_CH28>,
    pub ppi_ch29: Peri<'static, per::PPI_CH29>,
    pub ppi_ch30: Peri<'static, per::PPI_CH30>,
    pub ppi_ch31: Peri<'static, per::PPI_CH31>,
    pub rng: Peri<'static, per::RNG>,
    pub nvmc: Peri<'static, per::NVMC>,
    pub pwm0: Peri<'static, per::PWM0>,
    pub pwm1: Peri<'static, per::PWM1>,
    pub timer1: Peri<'static, per::TIMER1>,
    pub ppi_ch0: Peri<'static, per::PPI_CH0>,
    pub ppi_ch1: Peri<'static, per::PPI_CH1>,
    pub qdec: Peri<'static, per::QDEC>,
    pub saadc: Peri<'static, per::SAADC>,
    pub twispi0: Peri<'static, per::TWISPI0>,
}

/// Moves the board independent peripherals out of `$p` (partial move; `$p` must be owned).
macro_rules! take_common {
    ($p:ident) => {
        $crate::board::Common {
            rtc0: $p.RTC0,
            timer0: $p.TIMER0,
            temp: $p.TEMP,
            ppi_ch17: $p.PPI_CH17,
            ppi_ch18: $p.PPI_CH18,
            ppi_ch19: $p.PPI_CH19,
            ppi_ch20: $p.PPI_CH20,
            ppi_ch21: $p.PPI_CH21,
            ppi_ch22: $p.PPI_CH22,
            ppi_ch23: $p.PPI_CH23,
            ppi_ch24: $p.PPI_CH24,
            ppi_ch25: $p.PPI_CH25,
            ppi_ch26: $p.PPI_CH26,
            ppi_ch27: $p.PPI_CH27,
            ppi_ch28: $p.PPI_CH28,
            ppi_ch29: $p.PPI_CH29,
            ppi_ch30: $p.PPI_CH30,
            ppi_ch31: $p.PPI_CH31,
            rng: $p.RNG,
            nvmc: $p.NVMC,
            pwm0: $p.PWM0,
            pwm1: $p.PWM1,
            timer1: $p.TIMER1,
            ppi_ch0: $p.PPI_CH0,
            ppi_ch1: $p.PPI_CH1,
            qdec: $p.QDEC,
            saadc: $p.SAADC,
            twispi0: $p.TWISPI0,
        }
    };
}
pub(crate) use take_common;
