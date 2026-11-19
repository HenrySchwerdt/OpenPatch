//! Battery, TPL5010 watchdog timer and the angle sensor (TMAG5273) models.

use crate::params::{ElectricalParams, SensorParams};
use crate::rng::Rng;
use std::f64::consts::PI;

/// Single Li-Po cell with PCM: open-circuit voltage from state of charge, internal resistance,
/// coulomb counting. `dip_mv` is a scenario-injected extra drop (contact bounce, cold, ageing).
#[derive(Clone, Debug)]
pub struct Battery {
    pub soc: f64,
    cap_mah: f64,
    r_int: f64,
    bench: bool,
    pub dip_mv: f64,
    /// Scenario override of the open-circuit voltage (mV).
    pub ocv_override: Option<f64>,
}

const OCV: [(f64, f64); 7] = [(0.0, 3000.0), (0.05, 3450.0), (0.2, 3680.0), (0.5, 3820.0), (0.8, 4000.0), (0.95, 4120.0), (1.0, 4180.0)];

impl Battery {
    pub fn new(p: &ElectricalParams) -> Self {
        Battery { soc: p.soc_start, cap_mah: p.battery_capacity_mah, r_int: p.r_int_ohm, bench: p.bench_supply, dip_mv: 0.0, ocv_override: None }
    }

    pub fn ocv_mv(&self) -> f64 {
        if let Some(v) = self.ocv_override {
            return v;
        }
        let s = self.soc.clamp(0.0, 1.0);
        for w in OCV.windows(2) {
            let ((s0, v0), (s1, v1)) = (w[0], w[1]);
            if s <= s1 {
                return v0 + (v1 - v0) * (s - s0) / (s1 - s0);
            }
        }
        OCV[OCV.len() - 1].1
    }

    /// Terminal voltage with `i_ma` drawn.
    pub fn terminal_mv(&self, i_ma: f64) -> f64 {
        if self.bench {
            return 4000.0 - self.dip_mv;
        }
        self.ocv_mv() - i_ma * self.r_int - self.dip_mv
    }

    pub fn drain(&mut self, i_ma: f64, dt_s: f64) {
        if self.bench {
            return;
        }
        self.soc = (self.soc - i_ma * dt_s / 3600.0 / self.cap_mah).max(0.0);
    }
}

/// 12-bit unwrap of the TMAG5273 angle, a copy of `openpatch-bench/src/hal/angle.rs::Tracker`
/// (valid while the shaft moves less than half a turn between two samples).
#[derive(Clone, Debug, Default)]
pub struct Tracker {
    last: Option<u16>,
    pub cum: i64,
}

impl Tracker {
    pub fn update(&mut self, raw: u16) -> i64 {
        if let Some(l) = self.last {
            let mut d = raw as i32 - l as i32;
            if d >= 2048 {
                d -= 4096;
            } else if d < -2048 {
                d += 4096;
            }
            self.cum += d as i64;
        }
        self.last = Some(raw);
        self.cum
    }
}

/// Physical angle -> raw 12-bit reading (after the 13-bit conversion is decimated by the HAL).
pub fn sample_angle(sp: &SensorParams, theta_s: f64, strength: f64, rng: &mut Rng) -> u16 {
    let theta = if strength < sp.lost_threshold {
        // magnet gone: the sensor sees the stray field only; direction is arbitrary and noisy
        sp.angle_offset_deg.to_radians() + sp.garbage_noise_deg.to_radians() * rng.gauss()
    } else {
        let sigma = if strength < sp.weak_threshold { sp.angle_noise_deg / strength.max(1e-3) } else { sp.angle_noise_deg };
        theta_s + sp.angle_inl_deg.to_radians() * theta_s.sin() + sp.angle_offset_deg.to_radians() + sigma.to_radians() * rng.gauss()
    };
    let frac = (theta / (2.0 * PI)).rem_euclid(1.0);
    let levels = (1u64 << sp.angle_bits) as f64;
    let raw = ((frac * levels).floor() as u64).min((1u64 << sp.angle_bits) - 1);
    (raw >> sp.angle_bits.saturating_sub(12)) as u16
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tracker_unwraps_forward_and_backward() {
        let mut t = Tracker::default();
        for k in 0..20u32 {
            t.update(((k * 500) % 4096) as u16);
        }
        assert_eq!(t.cum, 19 * 500);
        let mut t = Tracker::default();
        t.update(100);
        t.update(4000); // -196 counts, not +3900
        assert_eq!(t.cum, -196);
    }

    #[test]
    fn sensor_quantises_to_12_bit_and_is_monotonic() {
        let sp = SensorParams { angle_noise_deg: 0.0, angle_inl_deg: 0.0, angle_offset_deg: 0.0, ..Default::default() };
        let mut rng = Rng::new(1);
        let a = sample_angle(&sp, 0.0, 1.0, &mut rng);
        let b = sample_angle(&sp, 2.0 * PI * 0.25, 1.0, &mut rng);
        assert_eq!(a, 0);
        assert_eq!(b, 1024);
    }

    #[test]
    fn battery_curve() {
        let b = Battery::new(&ElectricalParams::default());
        assert!((b.ocv_mv() - 4180.0).abs() < 1.0);
        assert!(b.terminal_mv(180.0) < b.ocv_mv() - 200.0);
    }
}
