//! Occlusion by the angle shortfall only (`occlusion` + `SafetySupervisor` with `OcclusionSource::AngleOnly`, cup v4 board).
mod common;
use common::*;
use openpatch_core::diag::codes;
use openpatch_core::limits::*;
use openpatch_core::occlusion::*;
use openpatch_core::*;

/// Host-only test calibration: 26 100 uU/step, 256 steps per turn = 16 counts per step.
fn cal() -> PulseCal {
    PulseCal { uu_num: TEST_UU, uu_den: 1, turn_x100: 25_600 }
}
fn mu_counts(mu: u32) -> i64 {
    cal().mu_to_angle(MilliUnits(mu)).0
}

#[test]
fn thresholds_are_the_spec_budget_and_half_of_it() {
    assert_eq!(SHORTFALL_FAULT_MU, 2_000);
    assert_eq!(SHORTFALL_FAULT_MU, OCCLUSION.0, "spec section 7: never relaxed");
    assert_eq!(SHORTFALL_WARN_MU, 1_000);
    assert_eq!(SHORTFALL_REARM_MU, 500);
    assert!(SHORTFALL_WARN_MU < SHORTFALL_FAULT_MU && SHORTFALL_REARM_MU < SHORTFALL_WARN_MU);
}

#[test]
fn classification_at_the_boundaries() {
    let c = cal();
    let warn = mu_counts(SHORTFALL_WARN_MU);
    let fault = mu_counts(SHORTFALL_FAULT_MU);
    assert_eq!(classify_shortfall(-100, c), ShortfallLevel::Ok, "over-delivery is deviation, not occlusion");
    assert_eq!(classify_shortfall(0, c), ShortfallLevel::Ok);
    assert_eq!(classify_shortfall(warn, c), ShortfallLevel::Ok, "exactly at the limit is not above it");
    assert_eq!(classify_shortfall(warn + 1, c), ShortfallLevel::Warn);
    assert_eq!(classify_shortfall(fault, c), ShortfallLevel::Warn);
    assert_eq!(classify_shortfall(fault + 1, c), ShortfallLevel::Fault);
    assert_eq!(classify_shortfall(i64::MAX, c), ShortfallLevel::Fault);
    // uncalibrated: any positive shortfall is a fault (fail-safe)
    assert_eq!(classify_shortfall(1, PulseCal::NONE), ShortfallLevel::Fault);
    assert_eq!(classify_shortfall(0, PulseCal::NONE), ShortfallLevel::Ok);
}

#[test]
fn the_cup_drive_numbers() {
    // 1 U = 142 steps = about 1100 angle counts: far above the sensor noise
    let cup = openpatch_core::drive_cal::NFP_608_2645_CUP_MITER_1_1.cal();
    let one_u = cup.mu_to_angle(MilliUnits(1_000)).0;
    assert!((1_080..=1_120).contains(&one_u), "{one_u}");
    assert!(one_u > 100 * 4, "more than 100 x the 4 count noise floor (6-60-004)");
}

#[test]
fn warning_needs_two_consecutive_evaluations_and_is_raised_once() {
    let c = cal();
    let mut m = ShortfallMonitor::new();
    let s = mu_counts(1_200);
    assert_eq!(m.evaluate(s, c), ShortfallEvent::None, "one pass is not enough");
    assert_eq!(m.evaluate(s, c), ShortfallEvent::RaiseWarning);
    assert!(m.warned());
    for _ in 0..10 {
        assert_eq!(m.evaluate(s, c), ShortfallEvent::None, "once per excursion");
    }
}

#[test]
fn a_dip_below_the_warn_level_restarts_the_debounce() {
    let c = cal();
    let mut m = ShortfallMonitor::new();
    assert_eq!(m.evaluate(mu_counts(1_200), c), ShortfallEvent::None);
    assert_eq!(m.evaluate(mu_counts(800), c), ShortfallEvent::None);
    assert_eq!(m.evaluate(mu_counts(1_200), c), ShortfallEvent::None, "not consecutive");
    assert_eq!(m.evaluate(mu_counts(1_200), c), ShortfallEvent::RaiseWarning);
}

#[test]
fn hysteresis_rearms_only_below_half_the_warn_level() {
    let c = cal();
    let mut m = ShortfallMonitor::new();
    m.evaluate(mu_counts(1_200), c);
    assert_eq!(m.evaluate(mu_counts(1_200), c), ShortfallEvent::RaiseWarning);
    // hovering around 1 U does not raise again
    for _ in 0..3 {
        assert_eq!(m.evaluate(mu_counts(900), c), ShortfallEvent::None);
        assert_eq!(m.evaluate(mu_counts(1_100), c), ShortfallEvent::None);
    }
    assert!(m.warned());
    // a clear drop (below 0.5 U) re-arms and clears the record
    assert_eq!(m.evaluate(mu_counts(400), c), ShortfallEvent::ClearWarning);
    assert!(!m.warned());
    assert_eq!(m.evaluate(mu_counts(400), c), ShortfallEvent::None, "only once");
    m.evaluate(mu_counts(1_200), c);
    assert_eq!(m.evaluate(mu_counts(1_300), c), ShortfallEvent::RaiseWarning);
    m.reset();
    assert!(!m.warned());
}

#[test]
fn fault_is_immediate_and_not_debounced() {
    let c = cal();
    let mut m = ShortfallMonitor::new();
    assert_eq!(m.evaluate(mu_counts(2_100), c), ShortfallEvent::RaiseFault);
    assert_eq!(m.evaluate(mu_counts(2_100), c), ShortfallEvent::RaiseFault);
}

// ---- in the supervisor ------------------------------------------------------------------------------------------

const CPS: i64 = 16;

fn mk(source: OcclusionSource) -> SafetySupervisor {
    let mut sv = SafetySupervisor::new(Millis(0), AngleCounts(0), cal());
    sv.set_docked(true);
    sv.set_active(true);
    sv.set_occlusion_source(source);
    sv
}

fn obs(angle: i64) -> Observation {
    Observation { battery_mv: 3_900, reservoir: Some(MilliUnits(1_000_000)), angle: AngleCounts(angle) }
}

fn active_ids(sv: &SafetySupervisor) -> Vec<u32> {
    sv.diag().active().iter().map(|a| a.code.identity().0).collect()
}

fn undelivered_mu(sv: &SafetySupervisor) -> f64 {
    let un = sv.commanded_counts().0 - (sv.last_angle().0 - sv.encoder_baseline().0);
    un as f64 * 1_000.0 / mu_counts(1_000) as f64
}

#[test]
fn slow_blockage_warns_at_1u_then_faults_at_2u() {
    let mut sv = mk(OcclusionSource::AngleOnly);
    // 2 % shortfall: the 10 % window and the 3 % revolution checks stay quiet, the balance grows by about 4 mU per minute
    let (mut warned_at, mut faulted_at) = (None, None);
    let mut enc = 0i64;
    for i in 0..2_000u64 {
        let ok = sv.approve_steps(Millis(i * 60_000), Pulses(8), MilliUnits(1_000_000)).0;
        enc += ok as i64 * CPS * 98;
        let f = sv.observe(Millis(i * 60_000), &obs(enc / 100));
        if warned_at.is_none() && active_ids(&sv).contains(&codes::OCCLUSION_SHORTFALL_WARNING.0) {
            warned_at = Some(undelivered_mu(&sv));
            assert!(!f.contains(Faults::OCCLUSION), "the warning comes first");
            assert!(sv.motor_allowed(), "a warning does not stop delivery");
        }
        if f.contains(Faults::OCCLUSION) {
            faulted_at = Some(undelivered_mu(&sv));
            break;
        }
    }
    let w = warned_at.expect("warning raised");
    assert!((1_000.0..1_100.0).contains(&w), "warned at {w} mU");
    let f = faulted_at.expect("fault raised");
    assert!(f > 2_000.0 && f < 2_100.0, "faulted at {f} mU (spec limit 2 U)");
    assert!(!sv.motor_allowed());
}

#[test]
fn the_warning_record_is_a_warning_in_the_catalogue() {
    use openpatch_diag::{Severity, CATALOGUE};
    let e = CATALOGUE.iter().find(|c| c.code == codes::OCCLUSION_SHORTFALL_WARNING).unwrap();
    assert_eq!(e.severity, Severity::Warning);
    assert_eq!(codes::OCCLUSION_SHORTFALL_WARNING.0, 0x5530_0400);
}

#[test]
fn full_stall_still_faults_before_2u_without_any_current_input() {
    let mut sv = mk(OcclusionSource::AngleOnly);
    let mut faults = Faults::NONE;
    for i in 0..100u64 {
        sv.approve_steps(Millis(i * 60_000), Pulses(10), MilliUnits(1_000_000));
        faults |= sv.observe(Millis(i * 60_000), &obs(0));
        if !faults.is_empty() {
            break;
        }
    }
    assert!(faults.contains(Faults::OCCLUSION));
    assert!(sv.commanded_counts() < cal().mu_to_angle(OCCLUSION));
}

#[test]
fn angle_only_ignores_the_current_channel_completely() {
    let mut sv = mk(OcclusionSource::AngleOnly);
    assert_eq!(sv.occlusion_source(), OcclusionSource::AngleOnly);
    for _ in 0..50 {
        assert!(!sv.observe_motor_burst(Pulses(10), Some(u16::MAX)), "no current-rise detection on this board");
    }
    assert_eq!(sv.faults(), Faults::NONE);
    assert!(!active_ids(&sv).contains(&codes::OCCLUSION_CURRENT_RISE.0));
    assert!(sv.motor_allowed());
}

#[test]
fn both_channels_remain_the_default_on_other_boards() {
    let mut sv = SafetySupervisor::new(Millis(0), AngleCounts(0), cal());
    sv.set_docked(true);
    sv.set_active(true);
    assert_eq!(sv.occlusion_source(), OcclusionSource::AngleAndCurrent);
    let above = OCCLUSION_CURRENT_MA + 1;
    assert!(!sv.observe_motor_burst(Pulses(10), Some(above)));
    assert!(!sv.observe_motor_burst(Pulses(10), Some(above)));
    assert!(sv.observe_motor_burst(Pulses(10), Some(above)));
}

#[test]
fn rebaseline_restarts_the_warning_debounce() {
    let mut sv = mk(OcclusionSource::AngleOnly);
    // 1.3 U commanded, nothing moves: past 1 U, below 2 U
    let steps = cal().mu_to_pulses(MilliUnits(1_300)).0;
    sv.approve_steps(Millis(0), Pulses(steps), MilliUnits(1_000_000));
    sv.observe(Millis(1_000), &obs(0));
    assert!(!active_ids(&sv).contains(&codes::OCCLUSION_SHORTFALL_WARNING.0), "one pass is not enough");
    sv.observe(Millis(2_000), &obs(0));
    assert!(active_ids(&sv).contains(&codes::OCCLUSION_SHORTFALL_WARNING.0));
    // new baseline (refill / prime): the monitor starts again, two new passes are needed
    // (a 1.3 U stall also trips the 10 % window check: acknowledge it, as the user would)
    let f = sv.faults();
    let _ = sv.acknowledge(f);
    sv.rebaseline(AngleCounts(0));
    assert!(!active_ids(&sv).contains(&codes::OCCLUSION_SHORTFALL_WARNING.0), "the new baseline clears the old warning");
    assert!(sv.motor_allowed());
    sv.approve_steps(Millis(70_000), Pulses(steps), MilliUnits(1_000_000));
    sv.observe(Millis(71_000), &obs(0));
    assert!(!active_ids(&sv).contains(&codes::OCCLUSION_SHORTFALL_WARNING.0), "debounce restarted");
    sv.observe(Millis(72_000), &obs(0));
    assert!(active_ids(&sv).contains(&codes::OCCLUSION_SHORTFALL_WARNING.0));
}
