//! F2 / F3 of the SPICE report (`electronics/v010/cup/sim/REPORT.md`): resting start threshold, loaded abort after the first step,
//! boost enable, and the diag code `A-A0-004` (`battery::{MotorSupplyLimits, start_gate, LoadGuard}`).
use openpatch_core::battery::*;
use openpatch_core::diag::{codes, Action, DiagState, Fru, Severity};
use openpatch_core::hal::MotorDir;
use openpatch_core::phase_drive::*;

#[test]
fn defaults_and_existing_limits_are_not_relaxed() {
    assert_eq!((MOTOR_REST_MIN_MV, MOTOR_LOAD_ABORT_MV, BOOST_ENABLE_MIN_MV), (3_700, 2_800, 3_400));
    assert_eq!(MotorSupplyLimits::default(), MotorSupplyLimits { rest_min_mv: 3_700, load_abort_mv: 2_800 });
    // existing limits unchanged
    assert_eq!((MOTOR_MIN_VBAT_MV, MOTOR_LOAD_FLOOR_MV, MOTOR_LOAD_CHECK_STEPS), (3_400, 3_000, 20));
    assert!(MOTOR_REST_MIN_MV >= MOTOR_MIN_VBAT_MV, "the new start threshold only tightens");
}

#[test]
fn constructor_checks_ranges_and_a_hand_built_value_is_clamped() {
    assert_eq!(MotorSupplyLimits::new(3_700, 2_800), Ok(MotorSupplyLimits::DEFAULT));
    assert_eq!(MotorSupplyLimits::new(3_399, 2_800), Err(LimitsError::RestMinOutOfRange));
    assert_eq!(MotorSupplyLimits::new(4_151, 2_800), Err(LimitsError::RestMinOutOfRange));
    assert_eq!(MotorSupplyLimits::new(3_400, 2_599), Err(LimitsError::LoadAbortOutOfRange));
    assert_eq!(MotorSupplyLimits::new(3_400, 3_001), Err(LimitsError::LoadAbortOutOfRange));
    assert!(MotorSupplyLimits::new(3_400, 2_600).is_ok());
    assert!(MotorSupplyLimits::new(4_150, 3_000).is_ok());
    let h = MotorSupplyLimits { rest_min_mv: 0, load_abort_mv: 0 };
    assert_eq!((h.effective_rest_min_mv(), h.effective_load_abort_mv()), (BOOST_ENABLE_MIN_MV, 2_600));
}

// ---- F3: boost enable ----------------------------------------------------------------------------------------------------------

#[test]
fn boost_enable_needs_3v4_at_rest() {
    assert!(!boost_enable_allowed(0));
    assert!(!boost_enable_allowed(3_399));
    assert!(boost_enable_allowed(3_400));
}

#[test]
fn start_gate_order_and_reasons() {
    let d = MotorSupplyLimits::DEFAULT;
    assert_eq!(start_gate(d, 4_200, true), Err(StartRefusal::Charger));
    assert_eq!(start_gate(d, 3_399, false), Err(StartRefusal::BoostBelowMinimum));
    assert_eq!(start_gate(d, 3_400, false), Err(StartRefusal::RestBelowThreshold));
    assert_eq!(start_gate(d, 3_699, false), Err(StartRefusal::RestBelowThreshold));
    assert_eq!(start_gate(d, 3_700, false), Ok(()));
    assert!(!motor_start_allowed(3_699, false) && motor_start_allowed(3_700, false) && !motor_start_allowed(4_200, true));
}

#[test]
fn a_passed_start_gate_implies_the_boost_minimum_for_every_configuration() {
    // the F3 dependency made explicit: whatever the configuration (valid or hand built), no start without the boost minimum
    let mut configs = vec![MotorSupplyLimits::DEFAULT, MotorSupplyLimits { rest_min_mv: 0, load_abort_mv: 0 }];
    for rest in (3_400..=4_150).step_by(50) {
        configs.push(MotorSupplyLimits::new(rest, 2_800).unwrap());
    }
    for cfg in configs {
        for mv in 0..=5_000u16 {
            for charger in [false, true] {
                let gate = start_gate(cfg, mv, charger);
                if gate.is_ok() {
                    assert!(boost_enable_allowed(mv), "{cfg:?} {mv} mV");
                    assert!(mv >= BOOST_ENABLE_MIN_MV && mv >= cfg.effective_rest_min_mv() && !charger);
                }
                if !boost_enable_allowed(mv) && !charger {
                    assert_eq!(gate, Err(StartRefusal::BoostBelowMinimum), "{cfg:?} {mv} mV");
                }
            }
        }
    }
}

#[test]
fn the_default_rest_threshold_subsumes_the_boost_minimum() {
    for mv in 0..=5_000u16 {
        if start_gate(MotorSupplyLimits::DEFAULT, mv, false).is_ok() {
            assert!(boost_enable_allowed(mv));
        }
    }
}

// ---- F2: loaded abort ----------------------------------------------------------------------------------------------------------

#[test]
fn no_sample_before_the_first_step() {
    let mut g = LoadGuard::new(MotorSupplyLimits::DEFAULT);
    assert!(g.keep_going(0, || panic!("not loaded yet, no sample")));
    assert_eq!(g.abort(), None);
}

#[test]
fn loaded_vbat_below_2v8_after_the_first_step_stops_the_move() {
    let mut g = LoadGuard::new(MotorSupplyLimits::DEFAULT);
    assert!(g.keep_going(0, || 0));
    assert!(!g.keep_going(1, || 2_799));
    assert_eq!(g.abort(), Some(SagAbort { loaded_mv: 2_799, floor_mv: 2_800, steps_made: 1 }));
    // tripped for good: no sample, no further step
    assert!(!g.keep_going(2, || panic!("no sampling after the abort")));
    assert!(!g.keep_going(0, || 4_200));
}

#[test]
fn loaded_vbat_at_2v8_passes_and_other_steps_take_no_sample() {
    let mut g = LoadGuard::new(MotorSupplyLimits::DEFAULT);
    assert!(g.keep_going(1, || 2_800));
    for n in 2..MOTOR_LOAD_CHECK_STEPS {
        assert!(g.keep_going(n, || panic!("step {n} is not a check point")));
    }
    assert_eq!(g.abort(), None);
}

#[test]
fn the_existing_3v0_check_after_20_steps_still_applies() {
    let mut g = LoadGuard::new(MotorSupplyLimits::DEFAULT);
    assert!(g.keep_going(1, || 2_900));
    assert!(g.keep_going(20, || 3_000));
    let mut g = LoadGuard::new(MotorSupplyLimits::DEFAULT);
    assert!(g.keep_going(1, || 2_900));
    assert!(!g.keep_going(20, || 2_999));
    assert_eq!(g.abort(), Some(SagAbort { loaded_mv: 2_999, floor_mv: MOTOR_LOAD_FLOOR_MV, steps_made: 20 }));
}

#[test]
fn the_abort_threshold_is_configurable_and_cannot_be_disabled() {
    let mut g = LoadGuard::new(MotorSupplyLimits::new(3_700, 3_000).unwrap());
    assert!(!g.keep_going(1, || 2_950));
    assert_eq!(g.abort().unwrap().floor_mv, 3_000);
    // a hand-built zero does not switch the check off
    let mut g = LoadGuard::new(MotorSupplyLimits { rest_min_mv: 3_700, load_abort_mv: 0 });
    assert!(!g.keep_going(1, || 2_599));
    let mut g = LoadGuard::new(MotorSupplyLimits { rest_min_mv: 3_700, load_abort_mv: 0 });
    assert!(g.keep_going(1, || 2_600));
    // a failed ADC sample reported as 0 mV aborts
    let mut g = LoadGuard::new(MotorSupplyLimits::DEFAULT);
    assert!(!g.keep_going(1, || 0));
}

struct Pins;
impl PhasePins for Pins {
    fn apply(&mut self, _l: PhaseLevels) {}
}
struct Timer;
impl StepTimer for Timer {
    fn delay_us(&mut self, _us: u32) {}
}

#[test]
fn the_guard_stops_a_real_burst_after_the_first_step() {
    let (mut st, mut pins, mut timer) = (PhaseStepper::new(), Pins, Timer);
    let mut g = LoadGuard::new(MotorSupplyLimits::DEFAULT);
    let mut samples = 0;
    let (made, why) = drive_burst(&mut st, &mut pins, &mut timer, MotorDir::Forward, 29, 5_000, |made| {
        g.keep_going(made, || {
            samples += 1;
            2_700 // the cell sags under the first step
        })
    });
    assert_eq!((made, why, samples), (1, BurstStop::Aborted, 1));
    assert_eq!(g.abort().map(|a| a.steps_made), Some(1));
}

#[test]
fn a_healthy_cell_runs_the_whole_burst_with_two_samples() {
    let (mut st, mut pins, mut timer) = (PhaseStepper::new(), Pins, Timer);
    let mut g = LoadGuard::new(MotorSupplyLimits::DEFAULT);
    let mut samples = 0;
    let (made, why) = drive_burst(&mut st, &mut pins, &mut timer, MotorDir::Forward, 29, 5_000, |made| {
        g.keep_going(made, || {
            samples += 1;
            3_300
        })
    });
    assert_eq!((made, why, samples), (29, BurstStop::Done, 2));
    assert_eq!(g.abort(), None);
}

// ---- diag A-A0-004 -------------------------------------------------------------------------------------------------------------

#[test]
fn diag_records_for_the_abort_and_the_refused_start() {
    let a = SagAbort { loaded_mv: 2_750, floor_mv: 2_800, steps_made: 1 }.raise();
    assert_eq!((a.code.identity(), a.code.inst(), a.ctx_a, a.ctx_b, a.ctx_c), (codes::CELL_SAG_UNDER_LOAD, 1, 2_750, 2_800, 1));
    let r = rest_refusal_raise(MotorSupplyLimits::DEFAULT, 3_650, StartRefusal::RestBelowThreshold).unwrap();
    assert_eq!((r.code.identity(), r.code.inst(), r.ctx_a, r.ctx_b), (codes::CELL_SAG_UNDER_LOAD, 2, 3_650, 3_700));
    let r = rest_refusal_raise(MotorSupplyLimits::DEFAULT, 3_300, StartRefusal::BoostBelowMinimum).unwrap();
    assert_eq!((r.code.inst(), r.ctx_b), (2, 3_400));
    assert!(rest_refusal_raise(MotorSupplyLimits::DEFAULT, 4_200, StartRefusal::Charger).is_none());
}

#[test]
fn the_catalogue_entry_names_the_cell_and_the_charge_action() {
    assert_eq!(codes::CELL_SAG_UNDER_LOAD.0, 0xAA00_0400, "A-A0-004");
    let mut d = DiagState::new();
    let id = d.raise(SagAbort { loaded_mv: 2_750, floor_mv: 2_800, steps_made: 1 }.raise());
    let rec = d.record(id).unwrap();
    assert_eq!(rec.severity(), Severity::Fault);
    assert_eq!(rec.fru(), Some(Fru::Batt));
    assert_eq!(rec.action(), Some(Action::CheckPower), "CHARGE in the catalogue doc");
    // the legacy fault projection carries the battery bit, so resume is blocked until acknowledged
    assert!(d.legacy_faults().contains(openpatch_core::faults::Faults::BATTERY_CRITICAL));
}
