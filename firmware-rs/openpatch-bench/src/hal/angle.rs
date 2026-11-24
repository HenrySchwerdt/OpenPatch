//! Cumulative, unwrapped leadscrew angle for `Hal::angle_read`.
//!
//! * `Tmag`: absolute 12 bit angle over I2C, unwrapped here. The unwrap is only valid if the shaft
//!   moves less than half a turn between two samples: the HAL samples every `ANGLE_POLL_MS`
//!   during every burst (see `config.rs` for the margin), and the shaft is at rest between bursts.
//!   A missing sensor yields `None` (the core refuses to deliver).
//! * `Qdec` (`angle-qdec-fallback`): the two DRV5032 hall switches as quadrature, 1024 counts per
//!   edge, 1 pole pair placeholder. NOT sufficient for the 3 % per revolution check.
//! * `Simulated` (DK): exact from the executed pulses (`TURN_X100`), so the core's checks see an
//!   ideal leadscrew.
use core::sync::atomic::Ordering;

use super::tmag::Tmag;
use crate::config::*;
use crate::shared::ENC_COUNTS;

#[cfg_attr(feature = "board-cup-v4", allow(dead_code))] // Qdec / Simulated: bench board and DK only
pub enum AngleSource {
    Tmag { sensor: Tmag, tracker: Tracker },
    Qdec,
    /// TMAG5273 absent at boot: `read` is always `None`.
    Missing,
    Simulated { num: i64 },
}

/// Unwraps a 12 bit angle into a cumulative count.
#[derive(Default)]
pub struct Tracker {
    last: Option<u16>,
    cum: i64,
}

impl Tracker {
    pub fn update(&mut self, raw: u16) -> i64 {
        if let Some(l) = self.last {
            let mut d = raw as i32 - l as i32;
            let half = ANGLE_COUNTS_PER_TURN / 2;
            if d >= half {
                d -= ANGLE_COUNTS_PER_TURN;
            } else if d < -half {
                d += ANGLE_COUNTS_PER_TURN;
            }
            self.cum += d as i64;
        }
        self.last = Some(raw);
        self.cum
    }
}

#[cfg_attr(feature = "board-cup-v4", allow(dead_code))]
impl AngleSource {
    /// Current cumulative angle in counts, `None` if the sensor is missing.
    pub fn read(&mut self) -> Option<i64> {
        match self {
            AngleSource::Tmag { sensor, tracker } => {
                if sensor.missing() {
                    return None;
                }
                sensor.read_raw().ok().map(|r| tracker.update(r))
            }
            AngleSource::Missing => None,
            AngleSource::Qdec => Some(ENC_COUNTS.load(Ordering::Relaxed) as i64 * ENC_DIRECTION as i64 * QDEC_ANGLE_COUNTS_PER_EDGE),
            AngleSource::Simulated { num } => Some(*num / TURN_X100 as i64),
        }
    }

    /// Called from the burst loop to keep the unwrap valid.
    pub fn poll(&mut self) {
        if let AngleSource::Tmag { .. } = self {
            let _ = self.read();
        }
    }

    /// DK: account for executed pulses (+ forward, - reverse).
    pub fn simulate_pulses(&mut self, pulses: i64) {
        if let AngleSource::Simulated { num } = self {
            // pulses x 4096 x 100 / TURN_X100 counts, kept as numerator over TURN_X100
            *num += pulses * ANGLE_COUNTS_PER_TURN as i64 * 100;
        }
    }
}
