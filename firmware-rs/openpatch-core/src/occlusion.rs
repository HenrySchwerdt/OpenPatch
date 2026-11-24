//! Occlusion detection by the TMAG5273 angle shortfall ONLY (cup board v4).
//!
//! The 45-part board has no motor current sense: the shunt + INA180 of the earlier boards are gone (`INTERLOCK.md` I.5 / I.6: a
//! single shunt would need more than two parts, the DRV8838 has no sense pins), so the **current-rise warning is dropped on this
//! board** (`SafetySupervisor::set_occlusion_current_enabled(false)`, [`OcclusionSource::AngleOnly`]). What remains is the angle
//! channel, which is a separate sensor on the rear flex strip and was always the primary detector:
//!
//! `shortfall = commanded angle - measured angle` (since the last baseline), in angle counts, compared in insulin volume.
//!
//! | Level | Threshold | Reaction |
//! |---|---|---|
//! | Warn | shortfall above [`SHORTFALL_WARN_MU`] (1 U, half the budget) on [`SHORTFALL_WARN_EVALS`] consecutive evaluations | `5-53-004` WARNING, delivery continues |
//! | Fault | shortfall above [`SHORTFALL_FAULT_MU`] (2 U, `limits::OCCLUSION`, **spec section 7: never relaxed**) | `5-53-001` FAULT, latched like before |
//!
//! The fault threshold is the unchanged spec limit and is NOT debounced (as before). The warning is debounced so one noisy sample
//! cannot raise it, and it has hysteresis (re-arms when the shortfall falls below [`SHORTFALL_REARM_MU`] = half the warn level) so a
//! shortfall that hovers around 1 U raises ONE record. On the cup drive 1 U is 142 steps = about 1100 angle counts, far above the
//! sensor noise (a few counts, `6-60-004`).
//!
//! Without the current channel a blockage is seen one stroke later (the stored volume of the compliance is not measured), so the
//! 2 U budget of the spec is spent on the shortfall alone; the stored-volume allowance of the current-based detector
//! (`limits::OCC_*`) does not apply and nothing here relaxes the 2 U limit.

use crate::limits::OCCLUSION;
use crate::units::{MilliUnits, PulseCal};

/// Warning threshold: half of the spec budget, in mU.
pub const SHORTFALL_WARN_MU: u32 = OCCLUSION.0 / 2;
/// Fault threshold: the spec limit, in mU (`limits::OCCLUSION`).
pub const SHORTFALL_FAULT_MU: u32 = OCCLUSION.0;
/// The warning re-arms below this shortfall, in mU.
pub const SHORTFALL_REARM_MU: u32 = SHORTFALL_WARN_MU / 2;
/// Consecutive evaluations above the warn threshold before the warning is raised.
pub const SHORTFALL_WARN_EVALS: u8 = 2;

/// Which channels feed the occlusion detector.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum OcclusionSource {
    /// Angle shortfall and motor current (boards with a current sense: bench).
    AngleAndCurrent,
    /// Angle shortfall only (cup board v4).
    AngleOnly,
}

/// Level of one evaluation (no debounce).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum ShortfallLevel {
    Ok,
    Warn,
    Fault,
}

/// Classify a shortfall in angle counts (`commanded - measured`, may be negative) against the thresholds, for the drive `cal`.
/// An uncalibrated drive (`PulseCal::NONE`) cannot convert: the fault level is returned for ANY positive shortfall (fail-safe;
/// the supervisor refuses to run without calibration anyway).
pub fn classify_shortfall(shortfall_counts: i64, cal: PulseCal) -> ShortfallLevel {
    if shortfall_counts <= 0 {
        return ShortfallLevel::Ok;
    }
    if cal.is_none() {
        return ShortfallLevel::Fault;
    }
    if shortfall_counts > cal.mu_to_angle(MilliUnits(SHORTFALL_FAULT_MU)).0 {
        ShortfallLevel::Fault
    } else if shortfall_counts > cal.mu_to_angle(MilliUnits(SHORTFALL_WARN_MU)).0 {
        ShortfallLevel::Warn
    } else {
        ShortfallLevel::Ok
    }
}

/// What the monitor tells the supervisor after an evaluation.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum ShortfallEvent {
    None,
    /// Raise `5-53-004` (once per excursion).
    RaiseWarning,
    /// The shortfall fell below the re-arm level: the warning's condition is gone, clear its record (auto clear of a W record).
    ClearWarning,
    /// Raise `5-53-001`.
    RaiseFault,
}

/// Debounce and hysteresis of the warning.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct ShortfallMonitor {
    above: u8,
    warned: bool,
}

impl ShortfallMonitor {
    pub const fn new() -> Self {
        Self { above: 0, warned: false }
    }

    /// New baseline (fill, prime, draw, acknowledge): forget the excursion.
    pub fn reset(&mut self) {
        *self = Self::new();
    }

    pub fn warned(&self) -> bool {
        self.warned
    }

    /// Evaluate one monitor pass.
    pub fn evaluate(&mut self, shortfall_counts: i64, cal: PulseCal) -> ShortfallEvent {
        match classify_shortfall(shortfall_counts, cal) {
            ShortfallLevel::Fault => {
                self.above = self.above.saturating_add(1);
                ShortfallEvent::RaiseFault
            }
            ShortfallLevel::Warn => {
                self.above = self.above.saturating_add(1);
                if self.above >= SHORTFALL_WARN_EVALS && !self.warned {
                    self.warned = true;
                    ShortfallEvent::RaiseWarning
                } else {
                    ShortfallEvent::None
                }
            }
            ShortfallLevel::Ok => {
                // consecutive means consecutive: any evaluation at or below the warn level restarts the debounce; only a clear
                // drop (below the re-arm level) re-arms the warning itself
                self.above = 0;
                if self.warned && !cal.is_none() && shortfall_counts <= cal.mu_to_angle(MilliUnits(SHORTFALL_REARM_MU)).0 {
                    self.warned = false;
                    ShortfallEvent::ClearWarning
                } else {
                    ShortfallEvent::None
                }
            }
        }
    }
}
