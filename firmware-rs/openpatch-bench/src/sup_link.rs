//! Supervisor link of the cup pod v4, receive side: the STM32C011 sends a 13-byte status frame every 500 ms and on every state change
//! (`openpatch_supervisor::status`, INTERLOCK.md H) on `SUP_TXD` (nRF RX, 115200 8N1). This task decodes it into atomics for the
//! diagnostics and the log. It also owns the two strap lines so nothing else can move them: `SUP_BOOT0` driven LOW (normal boot) and
//! `SUP_NRST` released (open drain, never driven high).
//!
//! NOT implemented (documented in `docs/board-cup-v4.md`): the challenge/response answer the supervisor expects (INTERLOCK.md H:
//! `[0x5A, seq, crc16(ch XOR K[seq mod 16])]` within 20 ms); its frame format and the table `K` exist only in the document, not in
//! `openpatch-supervisor`, and the STM32 platform shell that would send the challenge is not written. A supervisor that insists on the
//! link stays in `LINK_WAIT` and never permits: the motor stays cut (fail safe). The supervisor update (`openpatch-supflash`) would
//! take this UART and both strap pins over from this task (integration point).
use core::sync::atomic::Ordering;
use embassy_nrf::gpio::{AnyPin, Level, Output, OutputDrive};
use embassy_nrf::peripherals::UARTE1;
use embassy_nrf::uarte::{self, Uarte};
use embassy_nrf::Peri;
use embassy_time::Instant;
use openpatch_supervisor::status::{StatusFrame, FRAME_LEN, SYNC};

use crate::shared::{SUP_LAST_RX_MS, SUP_STATE};

#[embassy_executor::task]
pub async fn sup_link_task(
    uarte: Peri<'static, UARTE1>,
    rx: Peri<'static, AnyPin>,
    tx: Peri<'static, AnyPin>,
    boot0: Peri<'static, AnyPin>,
    nrst: Peri<'static, AnyPin>,
) -> ! {
    let _boot0 = Output::new(boot0, Level::Low, OutputDrive::Standard);
    let _nrst = Output::new(nrst, Level::High, OutputDrive::Standard0Disconnect1); // released, open drain
    let cfg = uarte::Config::default(); // 115200 8N1
    let mut u = Uarte::new(uarte, rx, tx, crate::irqs::CupIrqs, cfg);
    let mut frame = [0u8; FRAME_LEN];
    let mut n = 0usize;
    let mut last_state: Option<u8> = None;
    loop {
        let mut b = [0u8; 1];
        if u.read(&mut b).await.is_err() {
            n = 0;
            continue;
        }
        if n == 0 && b[0] != SYNC {
            continue; // resync on the sync byte
        }
        frame[n] = b[0];
        n += 1;
        if n < FRAME_LEN {
            continue;
        }
        n = 0;
        match StatusFrame::decode(&frame) {
            Ok(f) => {
                let s = f.state as u8;
                SUP_STATE.store(s, Ordering::Relaxed);
                SUP_LAST_RX_MS.store(Instant::now().as_millis() as u32, Ordering::Relaxed);
                if last_state != Some(s) {
                    last_state = Some(s);
                    defmt::info!("supervisor state {} reason {} hour {} min {}", s, f.reason as u8, f.hour_level, f.minute_level);
                }
            }
            Err(_) => defmt::warn!("supervisor status frame rejected"),
        }
    }
}
