//! SafetySupervisor (geared stepper + TMAG5273 angle sensor): command validation, rolling limits,
//! encoder-window occlusion / deviation, per-revolution verification, motor-current occlusion,
//! battery / reservoir / wear, acknowledge semantics, calibrations, plus Pump-level tests driving
//! the mock HAL. Numbers follow the C reference `test_safety.c` (Test26100: 16 counts per step).
mod common;

use common::*;
use openpatch_core::drive_cal::{DriveId, PRESETS};
use openpatch_core::limits::*;
use openpatch_core::*;

const MIN: u64 = 60_000;
const CPS: i64 = 16; // counts per step of the test calibration

/// Host-only test calibration: 26 100 uU/step, 256 steps per turn = 16 counts per step.
fn cal() -> PulseCal {
    PulseCal { uu_num: TEST_UU, uu_den: 1, turn_x100: 25_600 }
}

fn mk() -> SafetySupervisor {
    let mut sv = SafetySupervisor::new(Millis(0), AngleCounts(0), cal());
    sv.set_docked(true);
    sv.set_active(true);
    sv
}

fn sched(pairs: &[(u8, u32)]) -> BasalSchedule {
    BasalSchedule::from_pairs(pairs).unwrap()
}

fn mu(v: u32) -> MilliUnits {
    MilliUnits(v)
}

fn approve(sv: &mut SafetySupervisor, t_ms: u64, steps: u32, res_mu: u32) -> u32 {
    sv.approve_steps(Millis(t_ms), Pulses(steps), mu(res_mu)).0
}

fn observe(sv: &mut SafetySupervisor, t_ms: u64, batt: u16, res_mu: u32, angle: i64) -> Faults {
    sv.observe(
        Millis(t_ms),
        &Observation { battery_mv: batt, reservoir: Some(mu(res_mu)), angle: AngleCounts(angle) },
    )
}

fn bolus(sv: &mut SafetySupervisor, t_ms: u64, amount: u32, res_mu: u32) -> Result<(), Error> {
    sv.check_bolus(Millis(t_ms), mu(amount), mu(res_mu))
}

fn temp(sv: &SafetySupervisor, rate: u32, min: u32) -> Result<(), Error> {
    sv.check_temp_basal(MilliUnitsPerHour(rate), Minutes(min))
}

/// Drive supervisor + a simulated sensor (`pct` % of the commanded travel); returns new faults.
fn drive(sv: &mut SafetySupervisor, iterations: u32, steps_each: u32, pct: i64) -> Faults {
    let mut faults = Faults::NONE;
    let mut enc_x100 = sv.last_angle().0 * 100;
    let mut t = 0u64;
    for _ in 0..iterations {
        let ok = approve(sv, t, steps_each, 1_000_000);
        enc_x100 += ok as i64 * CPS * pct;
        faults |= observe(sv, t, 3900, 1_000_000, enc_x100 / 100);
        t += MIN;
        if !faults.is_empty() {
            break;
        }
    }
    faults
}

// ---- configuration and command validation --------------------------------------------------------

#[test]
fn sv_defaults_and_configure() {
    let mut sv = mk();
    assert_eq!(sv.max_bolus(), mu(10_000));
    assert_eq!(sv.max_basal(), MilliUnitsPerHour(5000));
    let cfg = |sv: &mut SafetySupervisor, b: u32, r: u32| sv.configure(mu(b), MilliUnitsPerHour(r));
    assert_eq!(cfg(&mut sv, 25_000, 30_000), Ok(()));
    assert_eq!(cfg(&mut sv, 25_001, 5000), Err(Error::Limit));
    assert_eq!(cfg(&mut sv, 10_000, 30_001), Err(Error::Limit));
    assert_eq!(cfg(&mut sv, 0, 5000), Err(Error::Limit));
    assert_eq!(cfg(&mut sv, 5000, 0), Err(Error::Limit));
    assert_eq!(sv.max_bolus(), mu(25_000)); // failed calls leave config untouched
}

#[test]
fn sv_check_bolus_rules() {
    let mut sv = mk();
    assert_eq!(bolus(&mut sv, 0, 1000, 50_000), Ok(()));
    assert_eq!(bolus(&mut sv, 0, 10_000, 50_000), Ok(()));
    assert_eq!(bolus(&mut sv, 0, 10_050, 50_000), Err(Error::Limit));
    assert_eq!(bolus(&mut sv, 0, 0, 50_000), Err(Error::BadArg));
    assert_eq!(bolus(&mut sv, 0, 1025, 50_000), Err(Error::BadArg)); // 0.05 U grid
    assert_eq!(bolus(&mut sv, 0, 5000, 4000), Err(Error::Reservoir));
}

#[test]
fn sv_check_bolus_respects_rolling_hour() {
    let mut sv = mk();
    let mut t = 0u64;
    let steps = cal().mu_to_pulses(mu(10_000)).0; // 383
    assert_eq!(steps, 383);
    for _ in 0..8 {
        // spread so the per-minute cap is not hit
        assert_eq!(approve(&mut sv, t, steps / 8, 100_000), steps / 8);
        t += MIN;
    }
    assert_eq!(bolus(&mut sv, t, 10_000, 100_000), Err(Error::Hourly)); // 10 + 10 > 15
    assert_eq!(bolus(&mut sv, t, 4000, 100_000), Ok(()));
    assert_eq!(bolus(&mut sv, t + 61 * MIN, 10_000, 100_000), Ok(())); // window slid
}

#[test]
fn sv_check_schedule_and_temp() {
    let sv = mk();
    assert_eq!(sv.check_basal_schedule(&sched(&[(0, 1000), (10, 5000)])), Ok(()));
    assert_eq!(sv.check_basal_schedule(&sched(&[(0, 1000), (10, 5050)])), Err(Error::Limit));
    assert_eq!(sv.check_basal_schedule(&sched(&[(0, 1000), (10, 1025)])), Err(Error::BadArg));
    // structurally invalid (second segment at slot 0)
    assert_eq!(sv.check_basal_schedule(&sched(&[(0, 1000), (0, 1000)])), Err(Error::BadArg));
    assert_eq!(temp(&sv, 5000, 30), Ok(()));
    assert_eq!(temp(&sv, 0, 720), Ok(()));
    assert_eq!(temp(&sv, 5050, 30), Err(Error::Limit));
    assert_eq!(temp(&sv, 1025, 30), Err(Error::BadArg));
    assert_eq!(temp(&sv, 1000, 20), Err(Error::BadArg));
    assert_eq!(temp(&sv, 1000, 750), Err(Error::BadArg));
}

#[test]
fn sv_checks_refuse_while_fault_latched() {
    let mut sv = mk();
    observe(&mut sv, 0, 3000, 50_000, 0); // battery critical
    let s = BasalSchedule::flat(MilliUnitsPerHour(0));
    assert_eq!(bolus(&mut sv, 0, 1000, 50_000), Err(Error::Fault));
    assert_eq!(temp(&sv, 1000, 30), Err(Error::Fault));
    assert_eq!(sv.check_basal_schedule(&s), Err(Error::Fault));
}

#[test]
fn sv_docked_active_released_gates() {
    let mut sv = mk();
    sv.set_docked(false);
    assert_eq!(bolus(&mut sv, 0, 1000, 50_000), Err(Error::NotDocked));
    assert_eq!(approve(&mut sv, 0, 1, 50_000), 0);
    assert_eq!(sv.faults(), Faults::NONE); // a gate is not a fault
    sv.set_docked(true);
    assert_eq!(approve(&mut sv, 1000, 1, 50_000), 1);
    sv.set_active(false);
    assert_eq!(bolus(&mut sv, 0, 1000, 50_000), Err(Error::Released));
    assert_eq!(approve(&mut sv, 2000, 1, 50_000), 0);
    assert_eq!(sv.faults(), Faults::NONE);
    assert!(sv.is_docked() && !sv.is_active());
}

// ---- approve_steps: limits ----------------------------------------------------------------------------

#[test]
fn sv_approves_normal_steps() {
    let mut sv = mk();
    assert_eq!(approve(&mut sv, 0, 5, 50_000), 5);
    assert_eq!(approve(&mut sv, 1000, 0, 50_000), 0);
    assert_eq!(sv.faults(), Faults::NONE);
    assert!(sv.motor_allowed());
}

#[test]
fn sv_hourly_cap_trims_and_latches() {
    let mut sv = mk();
    let mut t = 0u64;
    let mut total = 0;
    // the cap carries the 4 % calibration tolerance margin: 14 423 mU / 26.1 = 552 steps (15 U would be 574)
    let cap = sv.hourly_cap_steps().0;
    assert_eq!(cal().mu_to_pulses(MAX_HOURLY).0, 574);
    assert_eq!(cap, 552);
    for _ in 0..12 {
        // 60 steps/min is under the minute cap (65)
        total += approve(&mut sv, t, 60, 1_000_000);
        t += MIN;
    }
    assert_eq!(total, cap);
    assert!(sv.faults().contains(Faults::LIMIT_EXCEEDED));
    assert!(!sv.motor_allowed());
    assert_eq!(approve(&mut sv, t, 1, 1_000_000), 0); // latched: everything vetoed
}

#[test]
fn sv_rolling_window_slides() {
    let mut sv = mk();
    approve(&mut sv, 0, 60, 1_000_000);
    assert_eq!(sv.hourly_steps(Millis(30 * MIN)), Pulses(60));
    assert_eq!(sv.hourly_steps(Millis(59 * MIN)), Pulses(60));
    // true rolling window: 10 s buckets, a step stays counted for at least 60 minutes (and at most 60 min 10 s)
    assert_eq!(sv.hourly_steps(Millis(60 * MIN)), Pulses(60));
    assert_eq!(sv.hourly_steps(Millis(60 * MIN + 10_000)), Pulses(0));
    assert_eq!(sv.hourly_steps(Millis(500 * MIN)), Pulses(0));
}

#[test]
fn sv_window_allows_full_cap_again_after_ack() {
    let mut sv = mk();
    let mut t = 0u64;
    for _ in 0..12 {
        approve(&mut sv, t, 60, 1_000_000);
        t += MIN;
    }
    t += 61 * MIN;
    assert_eq!(sv.acknowledge(Faults(0xFFFF)), Ok(()));
    assert_eq!(approve(&mut sv, t, 60, 1_000_000), 60);
}

#[test]
fn sv_per_minute_backstop() {
    let mut sv = mk();
    assert_eq!(sv.max_steps_per_min(), Pulses(65));
    assert_eq!(approve(&mut sv, 0, 200, 1_000_000), cal().mu_to_pulses(MAX_PER_MIN).0);
    assert!(sv.faults().contains(Faults::LIMIT_EXCEEDED));
}

#[test]
fn sv_per_minute_backstop_is_per_pulse_single_requests() {
    // the pump asks for one pulse at a time: the 66th pulse inside one wall minute is refused
    let mut sv = mk();
    for i in 0..65 {
        assert_eq!(approve(&mut sv, i * 100, 1, 1_000_000), 1);
    }
    assert_eq!(sv.faults(), Faults::NONE);
    assert_eq!(approve(&mut sv, 6_500, 1, 1_000_000), 0);
    assert!(sv.faults().contains(Faults::LIMIT_EXCEEDED));
}

#[test]
fn sv_reservoir_trim_latches_empty() {
    let mut sv = mk();
    assert_eq!(approve(&mut sv, 0, 10, 100), 3); // floor(100 mU / 26.1 mU)
    assert!(sv.faults().contains(Faults::RESERVOIR_EMPTY));
}

#[test]
fn sv_zero_reservoir_vetoes_everything() {
    let mut sv = mk();
    assert_eq!(approve(&mut sv, 0, 4, 0), 0);
    assert!(sv.faults().contains(Faults::RESERVOIR_EMPTY));
}

#[test]
fn sv_clock_jump_clears_window() {
    let mut sv = mk();
    approve(&mut sv, 0, 60, 1_000_000);
    approve(&mut sv, 10 * MIN, 60, 1_000_000);
    assert_eq!(sv.hourly_steps(Millis(10 * MIN)), Pulses(120));
    assert_eq!(sv.hourly_steps(Millis(1000 * MIN)), Pulses(0));
    // time never goes backwards: older timestamps do not corrupt the window
    assert_eq!(sv.hourly_steps(Millis(5 * MIN)), Pulses(0));
}

// ---- battery / reservoir / wear -------------------------------------------------------------------------

#[test]
fn sv_battery_critical_latches_and_low_flag() {
    let mut sv = mk();
    assert_eq!(observe(&mut sv, 0, 3400, 50_000, 0), Faults::NONE);
    assert!(sv.battery_low());
    assert_eq!(observe(&mut sv, 1000, 3200, 50_000, 0), Faults::BATTERY_CRITICAL);
    assert_eq!(observe(&mut sv, 2000, 3200, 50_000, 0), Faults::NONE); // not reported twice
    assert_eq!(approve(&mut sv, 3000, 5, 50_000), 0);
    // recovery does not clear the latch
    observe(&mut sv, 4000, 3900, 50_000, 0);
    assert!(sv.faults().contains(Faults::BATTERY_CRITICAL));
    assert!(!sv.battery_low());
}

#[test]
fn sv_battery_thresholds_are_exact() {
    let mut sv = mk();
    observe(&mut sv, 0, BATTERY_LOW_MV, 50_000, 0);
    assert!(!sv.battery_low()); // 3500 is not low
    observe(&mut sv, 0, BATTERY_LOW_MV - 1, 50_000, 0);
    assert!(sv.battery_low());
    assert_eq!(observe(&mut sv, 0, BATTERY_CRITICAL_MV, 50_000, 0), Faults::NONE); // 3300 is not critical
    assert_eq!(observe(&mut sv, 0, BATTERY_CRITICAL_MV - 1, 50_000, 0), Faults::BATTERY_CRITICAL);
}

#[test]
fn sv_observe_latches_reservoir_empty() {
    let mut sv = mk();
    assert_eq!(observe(&mut sv, 0, 3900, 0, 0), Faults::RESERVOIR_EMPTY);
}

#[test]
fn sv_unfilled_reservoir_is_not_monitored() {
    let mut sv = mk();
    let f = sv.observe(Millis(0), &Observation { battery_mv: 3900, reservoir: None, angle: AngleCounts(0) });
    assert_eq!(f, Faults::NONE);
}

#[test]
fn sv_wear_expiry_latches_and_needs_new_activation() {
    let mut sv = mk();
    sv.observe_wear(Millis(WEAR_MAX.0 - 1));
    assert_eq!(sv.faults(), Faults::NONE);
    sv.observe_wear(WEAR_MAX);
    assert!(sv.wear_expired());
    assert!(sv.faults().contains(Faults::WEAR_EXPIRED));
    assert_eq!(approve(&mut sv, 0, 1, 50_000), 0);
    assert_eq!(sv.acknowledge(Faults::WEAR_EXPIRED), Err(Error::Persists));
    assert!(sv.faults().contains(Faults::WEAR_EXPIRED));
    sv.reset_wear();
    assert!(!sv.wear_expired());
    assert_eq!(sv.faults(), Faults::NONE);
    assert_eq!(approve(&mut sv, 1000, 1, 50_000), 1);
}

// ---- calibration -----------------------------------------------------------------------------------------

#[test]
fn sv_missing_or_invalid_calibration_refuses_and_cannot_be_acknowledged() {
    let bad = [
        PulseCal::NONE,
        PulseCal { uu_num: 999, uu_den: 1, turn_x100: 25_600 },
        PulseCal { uu_num: 60_001, uu_den: 1, turn_x100: 25_600 },
        PulseCal { uu_num: TEST_UU, uu_den: 1, turn_x100: 0 },
    ];
    for c in bad {
        let mut sv = SafetySupervisor::new(Millis(0), AngleCounts(0), c);
        sv.set_docked(true);
        sv.set_active(true);
        assert!(!sv.is_calibrated());
        assert_eq!(sv.faults(), Faults::NO_CALIBRATION);
        assert_eq!(approve(&mut sv, 0, 1, 50_000), 0);
        assert_eq!(bolus(&mut sv, 0, 1000, 50_000), Err(Error::Fault));
        assert_eq!(sv.acknowledge(Faults(0xFFFF)), Err(Error::Persists));
        assert_eq!(sv.faults(), Faults::NO_CALIBRATION);
        assert!(!sv.motor_allowed());
    }
}

#[test]
fn sv_calibration_range_boundaries_are_accepted() {
    for uu in [CAL_UU_MIN, CAL_UU_MAX] {
        let sv = SafetySupervisor::new(Millis(0), AngleCounts(0), PulseCal { uu_num: uu, uu_den: 1, turn_x100: 25_600 });
        assert!(sv.is_calibrated());
        assert_eq!(sv.faults(), Faults::NONE);
    }
    let sv = mk();
    assert_eq!(sv.calibration(), cal());
}

// ---- acknowledge ---------------------------------------------------------------------------------------------

#[test]
fn sv_ack_refused_while_cause_persists() {
    let mut sv = mk();
    observe(&mut sv, 0, 3200, 0, 0);
    let both = Faults::BATTERY_CRITICAL | Faults::RESERVOIR_EMPTY;
    assert_eq!(sv.faults(), both);
    // battery still low, reservoir still empty
    assert_eq!(sv.acknowledge(Faults(0xFFFF)), Err(Error::Persists));
    assert_eq!(sv.faults(), both);
    // reservoir refilled, battery charged above hysteresis
    observe(&mut sv, 1000, 3350, 50_000, 0); // 3350 < 3300 + 100: not yet
    assert_eq!(sv.acknowledge(Faults::BATTERY_CRITICAL), Err(Error::Persists));
    observe(&mut sv, 2000, 3500, 50_000, 0);
    assert_eq!(sv.acknowledge(Faults(0xFFFF)), Ok(()));
    assert_eq!(sv.faults(), Faults::NONE);
}

#[test]
fn sv_ack_battery_hysteresis_boundary() {
    let mut sv = mk();
    observe(&mut sv, 0, 3200, 50_000, 0);
    observe(&mut sv, 1000, BATTERY_CRITICAL_MV + BATTERY_HYSTERESIS_MV - 1, 50_000, 0);
    assert_eq!(sv.acknowledge(Faults::BATTERY_CRITICAL), Err(Error::Persists));
    observe(&mut sv, 2000, BATTERY_CRITICAL_MV + BATTERY_HYSTERESIS_MV, 50_000, 0);
    assert_eq!(sv.acknowledge(Faults::BATTERY_CRITICAL), Ok(()));
}

#[test]
fn sv_ack_mask_is_selective_and_empty_ack_is_ok() {
    let mut sv = mk();
    assert_eq!(sv.acknowledge(Faults(0xFFFF)), Ok(())); // nothing latched
    approve(&mut sv, 0, 200, 1_000_000); // LIMIT_EXCEEDED, trimmed to 65 steps
    observe(&mut sv, 0, 3900, 0, 65 * CPS); // RESERVOIR_EMPTY, encoder consistent
    assert_eq!(sv.acknowledge(Faults::LIMIT_EXCEEDED), Ok(()));
    assert_eq!(sv.faults(), Faults::RESERVOIR_EMPTY);
}

#[test]
fn sv_ack_occlusion_and_internal_are_allowed() {
    let mut sv = mk();
    sv.latch(Faults::OCCLUSION);
    sv.latch(Faults::INTERNAL);
    assert_eq!(sv.faults(), Faults::OCCLUSION | Faults::INTERNAL);
    assert_eq!(sv.acknowledge(Faults(0xFFFF)), Ok(()));
    assert_eq!(sv.faults(), Faults::NONE);
}

// ---- encoder window: occlusion / deviation (C reference numbers) -------------------------------------

#[test]
fn sv_healthy_encoder_never_faults() {
    let mut sv = mk();
    assert_eq!(drive(&mut sv, 200, 8, 100), Faults::NONE); // 8 steps/min stays under the hourly cap
    assert!(sv.motor_allowed());
}

#[test]
fn sv_small_encoder_noise_is_tolerated() {
    let mut sv = mk();
    assert_eq!(drive(&mut sv, 100, 8, 98), Faults::NONE); // 2 % slip: inside window (10 %) and revolution (3 %) limits
    assert!(sv.motor_allowed());
}

#[test]
fn sv_encoder_deviation_over_10_percent_stops() {
    let mut sv = mk();
    let f = drive(&mut sv, 100, 10, 85);
    assert!(f.contains(Faults::ENCODER_DEVIATION));
    assert!(!f.contains(Faults::OCCLUSION)); // 85 % travel is deviation, not occlusion
    // caught right after the first 1 U window
    assert!(sv.commanded_counts() < cal().mu_to_angle(mu(1400)));
}

#[test]
fn sv_full_stall_is_occlusion_and_deviation() {
    let mut sv = mk();
    let f = drive(&mut sv, 100, 10, 0);
    assert!(f.contains(Faults::OCCLUSION));
    assert!(f.contains(Faults::ENCODER_DEVIATION));
    // before 2 U went undelivered
    assert!(sv.commanded_counts() < cal().mu_to_angle(OCCLUSION));
}

#[test]
fn sv_over_delivery_is_deviation_not_occlusion() {
    let mut sv = mk();
    let f = drive(&mut sv, 100, 10, 130);
    assert!(f.contains(Faults::ENCODER_DEVIATION));
    assert!(!f.contains(Faults::OCCLUSION));
}

#[test]
fn sv_slow_leak_below_deviation_still_trips_occlusion_at_2u() {
    let mut sv = mk();
    let f = drive(&mut sv, 800, 8, 98); // 2 % each window and revolution, running balance grows
    assert!(f.contains(Faults::OCCLUSION));
    assert!(!f.contains(Faults::ENCODER_DEVIATION));
    let undelivered = sv.commanded_counts().0 - (sv.last_angle().0 - sv.encoder_baseline().0);
    assert!(undelivered > cal().mu_to_angle(OCCLUSION).0);
}

#[test]
fn sv_ack_clears_latched_encoder_faults_and_rebaselines() {
    let mut sv = mk();
    drive(&mut sv, 100, 10, 0);
    assert!(!sv.motor_allowed());
    assert_eq!(sv.acknowledge(Faults::OCCLUSION | Faults::ENCODER_DEVIATION), Ok(()));
    assert!(sv.motor_allowed());
    assert_eq!(sv.commanded_steps(), Pulses(0));
    assert_eq!(drive(&mut sv, 50, 10, 100), Faults::NONE); // clean again, old balance forgotten
}

#[test]
fn sv_rebaseline_after_prime_resets_bookkeeping() {
    let mut sv = mk();
    approve(&mut sv, 0, 10, 1_000_000);
    sv.rebaseline(AngleCounts(5000));
    assert_eq!(sv.last_angle(), AngleCounts(5000));
    assert_eq!(sv.encoder_baseline(), AngleCounts(5000));
    assert_eq!(sv.commanded_counts(), AngleCounts(0));
    assert_eq!(sv.commanded_steps(), Pulses(0));
    assert_eq!(observe(&mut sv, 0, 3900, 1000, 5000), Faults::NONE);
}

#[test]
fn sv_approve_tracks_commanded_counts_exactly() {
    let mut sv = mk();
    assert_eq!(approve(&mut sv, 0, 10, 1_000_000), 10);
    assert_eq!(sv.commanded_counts(), AngleCounts(10 * CPS));
    assert_eq!(sv.commanded_steps(), Pulses(10));
}

// ---- per-revolution TMAG verification ----------------------------------------------------------------

/// Command exactly one revolution (256 steps, 64 per minute: under the minute cap) and observe the
/// sensor at `enc_end` once at the end. Returns the faults latched by that observation.
fn one_rev(sv: &mut SafetySupervisor, t0: u64, enc_start: i64, enc_end: i64) -> Faults {
    for i in 0..4 {
        assert_eq!(approve(sv, t0 + i * MIN, 64, 1_000_000), 64);
    }
    observe(sv, t0 + 3 * MIN, 3900, 1_000_000, enc_start + enc_end)
}

#[test]
fn rev_exact_revolution_is_no_false_positive() {
    let mut sv = mk();
    assert_eq!(one_rev(&mut sv, 0, 0, 4096), Faults::NONE);
    assert!(sv.motor_allowed());
}

#[test]
fn rev_tolerance_boundary_high_side() {
    // 3 % of 4096 = 122.88 counts
    let mut sv = mk();
    assert_eq!(one_rev(&mut sv, 0, 0, 4096 + 122), Faults::NONE);
    let mut sv = mk();
    assert_eq!(one_rev(&mut sv, 0, 0, 4096 + 123), Faults::ENCODER_DEVIATION);
}

#[test]
fn rev_tolerance_boundary_low_side() {
    let mut sv = mk();
    assert_eq!(one_rev(&mut sv, 0, 0, 4096 - 122), Faults::NONE);
    let mut sv = mk();
    let f = one_rev(&mut sv, 0, 0, 4096 - 123);
    assert_eq!(f, Faults::ENCODER_DEVIATION); // only the revolution check: window (10 %) and occlusion (2 U) stay quiet
}

#[test]
fn rev_check_waits_for_a_full_revolution() {
    let mut sv = mk();
    for i in 0..3 {
        approve(&mut sv, i * MIN, 64, 1_000_000); // 192 steps: no revolution yet
    }
    // 5 % off, but neither a full revolution nor a 10 % window error
    assert_eq!(observe(&mut sv, 3 * MIN, 3900, 1_000_000, 3072 - 150), Faults::NONE);
}

#[test]
fn rev_counters_rebase_after_acknowledge() {
    let mut sv = mk();
    assert_eq!(one_rev(&mut sv, 0, 0, 4096 + 300), Faults::ENCODER_DEVIATION);
    assert_eq!(sv.acknowledge(Faults::ENCODER_DEVIATION), Ok(()));
    // baseline is now the last seen angle: an exact revolution from there is clean
    let start = sv.last_angle().0;
    assert_eq!(start, 4096 + 300);
    assert_eq!(one_rev(&mut sv, 10 * MIN, start, 4096), Faults::NONE);
}

#[test]
fn rev_counters_rebase_after_explicit_rebaseline() {
    let mut sv = mk();
    approve(&mut sv, 0, 64, 1_000_000);
    approve(&mut sv, MIN, 64, 1_000_000);
    sv.rebaseline(AngleCounts(9000)); // e.g. after a draw: half a revolution of history is forgotten
    assert_eq!(one_rev(&mut sv, 10 * MIN, 9000, 4096), Faults::NONE);
}

#[test]
fn rev_second_revolution_is_checked_independently() {
    let mut sv = mk();
    assert_eq!(one_rev(&mut sv, 0, 0, 4096), Faults::NONE);
    assert_eq!(one_rev(&mut sv, 10 * MIN, 4096, 4096 + 200), Faults::ENCODER_DEVIATION); // 2nd rev 4.9 % off
}

// ---- motor-current occlusion ---------------------------------------------------------------------------------

const BURST: Pulses = Pulses(10);
const ABOVE: u16 = OCCLUSION_CURRENT_MA + 1;
const BELOW: u16 = OCCLUSION_CURRENT_MA;

#[test]
fn motor_current_below_threshold_never_latches() {
    let mut sv = mk();
    for _ in 0..100 {
        assert!(!sv.observe_motor_burst(BURST, Some(BELOW))); // exactly at the threshold is not above it
    }
    assert_eq!(sv.faults(), Faults::NONE);
}

#[test]
fn motor_current_consecutive_high_bursts_latch_occlusion() {
    let mut sv = mk();
    assert_eq!(OCCLUSION_CURRENT_BURSTS, 3);
    for _ in 0..OCCLUSION_CURRENT_BURSTS - 1 {
        assert!(!sv.observe_motor_burst(BURST, Some(ABOVE)));
        assert_eq!(sv.faults(), Faults::NONE);
    }
    assert!(sv.observe_motor_burst(BURST, Some(ABOVE)));
    assert_eq!(sv.faults(), Faults::OCCLUSION);
    assert!(!sv.motor_allowed());
    assert_eq!(approve(&mut sv, 0, 5, 50_000), 0);
    assert!(!sv.observe_motor_burst(BURST, Some(ABOVE))); // already latched: not new again
}

#[test]
fn motor_current_low_burst_resets_the_count() {
    let mut sv = mk();
    for _ in 0..OCCLUSION_CURRENT_BURSTS - 1 {
        sv.observe_motor_burst(BURST, Some(ABOVE));
    }
    assert!(!sv.observe_motor_burst(BURST, Some(BELOW)));
    for _ in 0..OCCLUSION_CURRENT_BURSTS - 1 {
        assert!(!sv.observe_motor_burst(BURST, Some(ABOVE)));
    }
    assert_eq!(sv.faults(), Faults::NONE);
    assert!(sv.observe_motor_burst(BURST, Some(ABOVE)));
}

#[test]
fn motor_current_none_changes_nothing() {
    let mut sv = mk();
    for _ in 0..OCCLUSION_CURRENT_BURSTS - 1 {
        sv.observe_motor_burst(BURST, Some(ABOVE));
    }
    for _ in 0..10 {
        assert!(!sv.observe_motor_burst(BURST, None)); // neither latches nor resets
    }
    assert_eq!(sv.faults(), Faults::NONE);
    assert!(sv.observe_motor_burst(BURST, Some(ABOVE)));
}

#[test]
fn motor_current_zero_step_burst_is_ignored() {
    let mut sv = mk();
    for _ in 0..10 {
        assert!(!sv.observe_motor_burst(Pulses(0), Some(ABOVE)));
    }
    assert_eq!(sv.faults(), Faults::NONE);
    // and it does not count towards (or reset) a running series either
    sv.observe_motor_burst(BURST, Some(ABOVE));
    sv.observe_motor_burst(BURST, Some(ABOVE));
    assert!(!sv.observe_motor_burst(Pulses(0), Some(BELOW)));
    assert!(sv.observe_motor_burst(BURST, Some(ABOVE)));
}

#[test]
fn motor_current_count_is_cleared_by_rebaseline_and_ack() {
    let mut sv = mk();
    sv.observe_motor_burst(BURST, Some(ABOVE));
    sv.observe_motor_burst(BURST, Some(ABOVE));
    sv.rebaseline(AngleCounts(0));
    assert!(!sv.observe_motor_burst(BURST, Some(ABOVE))); // count restarted
}

// ---- production calibration NFP-608-26.45 -------------------------------------------------------------------

fn nfp() -> PulseCal {
    DriveCal::preset(DriveId::Nfp608_26_45G1_1 as u16).unwrap().pulse_cal().unwrap()
}

#[test]
fn nfp_calibration_numbers() {
    let c = nfp();
    assert_eq!((c.uu_num, c.uu_den, c.turn_x100), (2_611_000, 529, 52_900));
    assert_eq!(c.micro_u_floor(), 4_935);
    assert_eq!(c.angle_per_pulse_x1000(), 7_742); // non-integer: 7.742 counts per step (floor)
    assert_eq!(c.expected_angle(Pulses(529)), AngleCounts(4096)); // exactly one revolution
    assert!(cal_in_range(c));
}

#[test]
fn nfp_expected_angle_never_drifts_more_than_one_count() {
    let c = nfp();
    for p in 0..=100_000u32 {
        let got = c.expected_angle(Pulses(p)).0;
        // exact = p * 4096 / 529
        let diff = (got * 529 - p as i64 * 4096).abs();
        assert!(diff < 529, "p={p} got={got}");
    }
}

#[test]
fn nfp_ideal_sensor_over_100_revolutions_gives_no_false_alarm() {
    let c = nfp();
    let mut sv = SafetySupervisor::new(Millis(0), AngleCounts(0), c);
    sv.set_docked(true);
    sv.set_active(true);
    let mut t = 0u64;
    let mut worst = 0i64;
    while sv.commanded_steps().0 < 100_000 {
        assert_eq!(approve(&mut sv, t, 30, 1_000_000), 30); // 30 steps/min = 148 mU/min
        let steps = sv.commanded_steps().0;
        let cc = sv.commanded_counts().0;
        worst = worst.max((cc * 529 - steps as i64 * 4096).abs());
        // ideal sensor: floor of the exact angle
        let enc = steps as i64 * 4096 / 529;
        assert_eq!(observe(&mut sv, t, 3900, 1_000_000, enc), Faults::NONE, "steps {steps}");
        t += MIN;
    }
    assert!(worst < 529); // < 1 count
    assert!(sv.commanded_steps().0 / 529 >= 100);
    assert_eq!(sv.faults(), Faults::NONE);
}

#[test]
fn nfp_real_deviation_is_still_caught() {
    let c = nfp();
    let mut sv = SafetySupervisor::new(Millis(0), AngleCounts(0), c);
    sv.set_docked(true);
    sv.set_active(true);
    let mut t = 0u64;
    let mut faults = Faults::NONE;
    while faults.is_empty() && sv.commanded_steps().0 < 5_000 {
        approve(&mut sv, t, 30, 1_000_000);
        let enc = sv.commanded_steps().0 as i64 * 4096 / 529 * 90 / 100; // 90 % travel
        faults |= observe(&mut sv, t, 3900, 1_000_000, enc);
        t += MIN;
    }
    assert!(faults.contains(Faults::ENCODER_DEVIATION));
}

#[test]
fn all_production_presets_are_accepted_by_the_supervisor() {
    for p in PRESETS {
        let sv = SafetySupervisor::new(Millis(0), AngleCounts(0), p.cal());
        assert!(sv.is_calibrated(), "{:?}", p.id);
        assert_eq!(sv.faults(), Faults::NONE);
    }
}

// =====================================================================================================
// Pump level: the supervisor driven through the mock HAL
// =====================================================================================================

/// Running pump with a bolus (25 mU per 1 s tick = just under one step per tick; the first tick
/// executes nothing).
fn pump_with_bolus(mu_amount: u32) -> (Pump<MockHal>, MockHal) {
    let (mut p, h) = running(50_000, 0);
    p.bolus(MilliUnits(mu_amount)).unwrap();
    (p, h)
}

#[test]
fn pump_healthy_run_has_no_fault_and_crosses_a_revolution() {
    let (mut p, h) = pump_with_bolus(10_000);
    run_secs(&mut p, &h, 420);
    assert_eq!(p.supervisor().faults(), Faults::NONE);
    assert!(h.st().total_steps >= 383 - 1); // 10 U, more than one 256-step revolution
    assert!(!h.st().stepped_while_disabled);
    assert_eq!(h.st().buzzer, Buzzer::Off);
}

#[test]
fn pump_total_stall_latches_occlusion_alarm_and_suspends() {
    let (mut p, h) = pump_with_bolus(5_000);
    h.st().delivered_pct = 0;
    run_secs(&mut p, &h, 60);
    assert!(p.supervisor().faults().contains(Faults::OCCLUSION));
    assert_eq!(h.st().buzzer, Buzzer::Alarm);
    assert!(p.engine().is_suspended());
    let steps = h.st().total_steps;
    run_secs(&mut p, &h, 30);
    assert_eq!(h.st().total_steps, steps); // nothing more is stepped
    assert!(!h.st().enabled);
}

#[test]
fn pump_half_delivery_latches_encoder_deviation_without_occlusion() {
    let (mut p, h) = pump_with_bolus(5_000);
    h.st().delivered_pct = 50;
    run_secs(&mut p, &h, 60);
    let f = p.supervisor().faults();
    assert!(f.contains(Faults::ENCODER_DEVIATION));
    assert!(!f.contains(Faults::OCCLUSION));
    assert_eq!(h.st().buzzer, Buzzer::Alarm);
    assert!(p.engine().is_suspended());
}

#[test]
fn pump_high_motor_current_for_3_bursts_latches_occlusion() {
    let (mut p, h) = pump_with_bolus(5_000);
    h.st().current_ma = Some(OCCLUSION_CURRENT_MA + 1);
    run_secs(&mut p, &h, 2); // tick 1 steps nothing, tick 2 one burst
    assert_eq!(p.supervisor().faults(), Faults::NONE);
    run_secs(&mut p, &h, 4);
    assert_eq!(p.supervisor().faults(), Faults::OCCLUSION);
    assert_eq!(h.st().buzzer, Buzzer::Alarm);
    assert!(p.engine().is_suspended());
}

#[test]
fn pump_current_at_threshold_never_latches() {
    let (mut p, h) = pump_with_bolus(5_000);
    h.st().current_ma = Some(OCCLUSION_CURRENT_MA);
    run_secs(&mut p, &h, 30);
    assert_eq!(p.supervisor().faults(), Faults::NONE);
}

#[test]
fn pump_missing_angle_sensor_latches_internal_and_delivers_nothing() {
    let (mut p, h) = pump_with_bolus(5_000);
    h.st().angle_missing = true;
    run_secs(&mut p, &h, 10);
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
    assert_eq!(h.st().total_steps, 0);
    assert!(p.engine().is_suspended());
}

#[test]
fn pump_short_motor_execution_latches_internal() {
    let (mut p, h) = pump_with_bolus(5_000);
    h.st().steps_limit = 0; // the motor executes nothing of what was approved
    run_secs(&mut p, &h, 5);
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
    assert_eq!(h.st().total_steps, 0);
    assert!(p.engine().is_suspended());
}

#[test]
fn pump_acknowledged_occlusion_resumes_cleanly() {
    let (mut p, h) = pump_with_bolus(5_000);
    h.st().delivered_pct = 0;
    run_secs(&mut p, &h, 60);
    assert!(p.supervisor().faults().contains(Faults::OCCLUSION));
    h.st().delivered_pct = 100;
    p.acknowledge(Faults(0xFFFF)).unwrap();
    assert_eq!(p.supervisor().faults(), Faults::NONE);
}
