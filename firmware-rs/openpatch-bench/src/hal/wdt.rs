//! TPL5010 watchdog: WAKE sensing and the DONE pulse, in hardware + one tiny interrupt.
//!
//! The Rev A board qualifies DONE (`electronics/bench/INTERLOCK.md` B): a DONE rising edge counts only while WAKE is high,
//! which is at most 20 ms after the WAKE rising edge. The safety tick (1 s, blocking bursts up to 0.9 s) can not promise
//! that latency, so the response lives here:
//!
//! * `WDT_WAKE` (P0.17) is a GPIOTE channel (7) event, rising edge, linked by PPI channel 2 to EGU3 task `TRIGGER[0]`;
//! * the EGU3 interrupt (above the safety executor) checks the permit [`DONE_PERMIT_UNTIL_MS`] and, only inside it, pulses
//!   `WDT_DONE` (P0.28) high for about 3 us (the qualifier needs >= 2 us) and low again. Idle LOW, ONE pulse per WAKE;
//! * the permit is granted by the safety task only after a verified tick, so a hung or failed safety task lets it lapse:
//!   DONE is withheld, the TPL5010 resets the MCU and its `RSTn` clears the interlock latch independently of the firmware.
//!
//! No other code touches `WDT_DONE`. The pin number is a board constant (`board::WDT_DONE_PIN`, port 0).
use core::sync::atomic::Ordering;
#[cfg(feature = "board-bench-e73")]
use embassy_nrf::pac;
#[cfg(feature = "board-bench-e73")]
use embassy_nrf::pac::interrupt;
use embassy_time::Instant;

#[cfg(feature = "board-bench-e73")]
use crate::shared::{DONE_COUNT, WAKE_COUNT};
use crate::shared::DONE_PERMIT_UNTIL_MS;

#[cfg(feature = "board-bench-e73")]
use crate::board::{WDT_DONE_PIN, WDT_WAKE_PIN};

/// GPIOTE channel and PPI channel used for the WAKE edge (taken as peripherals in `board::Common` so nothing else can claim them).
#[cfg(feature = "board-bench-e73")]
const GPIOTE_CH: usize = 7;
#[cfg(feature = "board-bench-e73")]
const PPI_CH: usize = 2;

/// No TPL5010 on this board (DK): nothing to route.
#[cfg(not(feature = "board-bench-e73"))]
pub fn init() {}

#[allow(dead_code)]
/// Is `now_ms` inside the permit window (wrapping compare)?
#[inline]
pub fn permit_valid(now_ms: u32, until_ms: u32) -> bool {
    (until_ms.wrapping_sub(now_ms) as i32) > 0
}

/// Route the WAKE edge to the EGU3 interrupt. Call once, after `embassy_nrf::init`, before the safety task runs.
#[cfg(feature = "board-bench-e73")]
pub fn init() {
    use embassy_nrf::interrupt::{self, InterruptExt, Priority};
    // GPIOTE CONFIG[ch]: MODE = Event (1), PSEL = pin, PORT = 0, POLARITY = LoToHi (1)
    let cfg = 1u32 | ((WDT_WAKE_PIN as u32) << 8) | (1 << 16);
    pac::GPIOTE.config(GPIOTE_CH).write_value(pac::gpiote::regs::Config(cfg));
    // PPI: GPIOTE.EVENTS_IN[ch] -> EGU3.TASKS_TRIGGER[0]
    let ev = pac::GPIOTE.events_in(GPIOTE_CH).as_ptr() as u32;
    let task = pac::EGU3.tasks_trigger(0).as_ptr() as u32;
    pac::PPI.ch(PPI_CH).eep().write_value(ev);
    pac::PPI.ch(PPI_CH).tep().write_value(task);
    pac::EGU3.intenset().write(|w| w.set_triggered(0, true));
    interrupt::EGU3_SWI3.set_priority(Priority::P3);
    interrupt::EGU3_SWI3.unpend();
    // SAFETY: the interrupt handler below only touches atomics and the DONE pin registers.
    unsafe { interrupt::EGU3_SWI3.enable() };
    pac::PPI.chenset().write_value(pac::ppi::regs::Chen(1 << PPI_CH));
}

/// WAKE seen: answer with ONE DONE pulse if the safety task has granted the permit.
#[cfg(feature = "board-bench-e73")]
#[interrupt]
fn EGU3_SWI3() {
    pac::EGU3.events_triggered(0).write_value(0);
    WAKE_COUNT.fetch_add(1, Ordering::Relaxed);
    let now = Instant::now().as_millis() as u32;
    if permit_valid(now, DONE_PERMIT_UNTIL_MS.load(Ordering::Acquire)) {
        let bit = 1u32 << WDT_DONE_PIN;
        pac::P0.outset().write_value(pac::gpio::regs::Outset(bit));
        cortex_m::asm::delay(64 * 3); // about 3 us at 64 MHz (qualifier: >= 2 us)
        pac::P0.outclr().write_value(pac::gpio::regs::Outclr(bit));
        DONE_COUNT.fetch_add(1, Ordering::Relaxed);
    }
}

/// Grant the DONE permit for `DONE_PERMIT_MS` from now.
pub fn grant_permit() {
    let now = Instant::now().as_millis() as u32;
    DONE_PERMIT_UNTIL_MS.store(now.wrapping_add(crate::config::DONE_PERMIT_MS), Ordering::Release);
}

/// Withdraw the permit at once (the safety task found something wrong).
pub fn revoke_permit() {
    DONE_PERMIT_UNTIL_MS.store(0, Ordering::Release);
}
