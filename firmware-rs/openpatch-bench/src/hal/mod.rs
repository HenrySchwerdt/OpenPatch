//! `openpatch_core::Hal` per board (bench controller / DK: `bench.rs`; cup pod v4: `cup.rs`). Owned by the `Pump` in the safety task.
//!
//! The core's `motor_step` is a short blocking call: the bench board generates the pulses in hardware (`stepper`) and busy-waits
//! on the hardware counter; the cup board walks the full-step table itself (`openpatch_core::phase_drive`).
pub mod angle;
pub mod tmag;

// E73 bench controller and DK: STSPIN220 step clock, bench interlock, TPL5010 DONE path.
#[cfg(not(feature = "board-cup-v4"))]
pub mod adc;
#[cfg(not(feature = "board-cup-v4"))]
mod bench;
#[cfg(not(feature = "board-cup-v4"))]
pub mod driver;
#[cfg(not(feature = "board-cup-v4"))]
pub mod encoder;
#[cfg(not(feature = "board-cup-v4"))]
pub mod stepper;
#[cfg(not(feature = "board-cup-v4"))]
pub mod wdt;
#[cfg(not(feature = "board-cup-v4"))]
pub use bench::{BenchHal, BoardIoDriver};
/// The HAL type the safety task owns.
#[cfg(not(feature = "board-cup-v4"))]
#[allow(dead_code)]
pub type BoardHal = BenchHal;

// Cup pod v4: phase drive (2 x DRV8838), cup gate, supervisor, nRF watchdog.
#[cfg(feature = "board-cup-v4")]
pub mod cup;
#[cfg(feature = "board-cup-v4")]
pub type BoardHal = cup::CupHal;

/// Read `POWER.RESETREAS` and clear it (write 1 to clear). Must run before anything else touches the peripheral.
pub fn read_and_clear_resetreas() -> u32 {
    let r = embassy_nrf::pac::POWER.resetreas().read().0;
    embassy_nrf::pac::POWER.resetreas().write_value(embassy_nrf::pac::power::regs::Resetreas(0xFFFF_FFFF));
    r
}

/// RESETREAS (nRF52840: RESETPIN bit 0, DOG bit 1, SREQ bit 2, LOCKUP bit 3, OFF bit 16, ... ; a power-on reset reads 0) as
/// the cause the core reports (docs/06-diagnostics.md `7-74-002`). The TPL5010 resets the MCU through the RESET pin
/// (UICR PSELRESET = P0.18), so a RESETPIN reset on the bench board IS the external watchdog; the internal WDT is not used.
/// A soft reset (SREQ) is the commanded one (DFU, service). A cold power-up and a wake from System OFF are `PowerOn`.
pub fn classify_resetreas(bits: u32) -> openpatch_core::hal::ResetCause {
    use openpatch_core::hal::ResetCause;
    const RESETPIN: u32 = 1 << 0;
    const DOG: u32 = 1 << 1;
    const SREQ: u32 = 1 << 2;
    const LOCKUP: u32 = 1 << 3;
    if bits & LOCKUP != 0 {
        ResetCause::Lockup
    } else if bits & DOG != 0 || bits & RESETPIN != 0 {
        ResetCause::Watchdog
    } else if bits & SREQ != 0 {
        ResetCause::Commanded
    } else {
        ResetCause::PowerOn
    }
}

