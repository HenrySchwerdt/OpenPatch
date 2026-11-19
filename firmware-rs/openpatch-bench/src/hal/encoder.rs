//! Optional QDEC on the two DRV5032FA hall switches: accumulates edge counts into `ENC_COUNTS`.
//! Used as the angle source of `angle-qdec-fallback` and as a coarse cross-check log of feature
//! `coarse-qdec` (never the primary angle channel).
use core::sync::atomic::Ordering;
use embassy_nrf::gpio::AnyPin;
use embassy_nrf::peripherals::QDEC;
use embassy_nrf::qdec::{self, Qdec};
use embassy_nrf::Peri;
use embassy_time::Timer;

use crate::config::*;
use crate::irqs::Irqs;
use crate::shared::ENC_COUNTS;

pub fn new_qdec(q: Peri<'static, QDEC>, a: Peri<'static, AnyPin>, b: Peri<'static, AnyPin>) -> Qdec<'static> {
    let mut cfg = qdec::Config::default();
    cfg.period = qdec::SamplePeriod::_256us;
    cfg.debounce = true;
    Qdec::new(q, Irqs, a, b, cfg)
}

#[embassy_executor::task]
pub async fn qdec_task(mut q: Qdec<'static>) -> ! {
    loop {
        let d = q.read().await;
        ENC_COUNTS.fetch_add(d as i32, Ordering::Relaxed);
        Timer::after_millis(ENC_POLL_MS).await;
    }
}
