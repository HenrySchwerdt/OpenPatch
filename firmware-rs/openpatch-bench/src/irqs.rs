//! Interrupt bindings and priorities.
//!
//! Priority plan (nRF52840, 0 = highest): the radio stack owns P0 (RADIO, TIMER0, RTC0) and P4
//! (low priority EGU0_SWI0, CLOCK_POWER). The application never uses P0, P1 or P4:
//! * P2: time driver (RTC1), GPIOTE
//! * P3: SAADC, QDEC, TWIM0, RNG (drivers that are awaited from either executor)
//! * P5: the safety interrupt executor (SWI1) so that BLE host processing in thread mode can never
//!   delay a safety tick; MPSL low priority work (P4) still preempts it, step timing is in hardware.
//! * thread mode: BLE host, UI, persistence, encoder, DFU.
use embassy_nrf::interrupt::{self, InterruptExt, Priority};
use embassy_nrf::{bind_interrupts, peripherals, qdec, rng, saadc, twim};

bind_interrupts!(pub struct Irqs {
    SAADC => saadc::InterruptHandler;
    QDEC => qdec::InterruptHandler<peripherals::QDEC>;
    TWISPI0 => twim::InterruptHandler<peripherals::TWISPI0>;
    RNG => rng::InterruptHandler<peripherals::RNG>;
    EGU0_SWI0 => nrf_sdc::mpsl::LowPrioInterruptHandler;
    CLOCK_POWER => nrf_sdc::mpsl::ClockInterruptHandler;
    RADIO => nrf_sdc::mpsl::HighPrioInterruptHandler;
    TIMER0 => nrf_sdc::mpsl::HighPrioInterruptHandler;
    RTC0 => nrf_sdc::mpsl::HighPrioInterruptHandler;
});

// Cup pod v4: the supervisor UART (status link, and later the ROM bootloader update).
#[cfg(feature = "board-cup-v4")]
bind_interrupts!(pub struct CupIrqs {
    UARTE1 => embassy_nrf::uarte::InterruptHandler<peripherals::UARTE1>;
});

pub const PRIO_DRIVERS: Priority = Priority::P3;
pub const PRIO_SAFETY_EXECUTOR: Priority = Priority::P5;

/// Time driver and GPIOTE priorities for `embassy_nrf::init`.
pub fn embassy_config() -> embassy_nrf::config::Config {
    let mut c = embassy_nrf::config::Config::default();
    c.time_interrupt_priority = Priority::P2;
    c.gpiote_interrupt_priority = Priority::P2;
    // Same source as the MPSL clock configuration in main.rs (`LFCLK_RC`): the 32.768 kHz crystal on P0.00/P0.01 on the bench
    // board and on the DK, the internal RC on the cup pod (the HJ-840 board has no crystal), so MPSL does not switch the clock
    // under RTC1.
    c.lfclk_source = if LFCLK_RC {
        embassy_nrf::config::LfclkSource::InternalRC
    } else {
        embassy_nrf::config::LfclkSource::ExternalXtal
    };
    c
}

/// The low frequency clock is the internal RC oscillator (cup pod v4, no 32 kHz crystal).
pub const LFCLK_RC: bool = cfg!(feature = "board-cup-v4");

/// Driver interrupts the application uses (the radio interrupts are set by MPSL itself).
pub fn set_driver_priorities() {
    interrupt::SAADC.set_priority(PRIO_DRIVERS);
    interrupt::QDEC.set_priority(PRIO_DRIVERS);
    interrupt::TWISPI0.set_priority(PRIO_DRIVERS);
    interrupt::RNG.set_priority(PRIO_DRIVERS);
    #[cfg(feature = "board-cup-v4")]
    interrupt::UARTE1.set_priority(PRIO_DRIVERS);
}
