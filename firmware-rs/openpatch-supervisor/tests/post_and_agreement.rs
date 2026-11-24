//! Mandatory POST vector, and agreement of the supervisor with the core's phase table and limits.
use openpatch_core::burst::{plan_burst, CellParams, MotorLoad};
use openpatch_core::drive_cal::NFP_608_2645_CUP_MITER_1_1 as CUP;
use openpatch_core::hal::MotorDir;
use openpatch_core::limits::{HOURLY_CAL_MARGIN_PCT, MAX_HOURLY, MAX_PER_MIN};
use openpatch_core::phase_drive::{drive_burst, PhaseLevels, PhasePins, PhaseStepper, StepTimer};
use openpatch_core::MilliUnits;
use openpatch_supervisor::logic::*;

const CFG: Config = Config::CUP_MITER_1_1;

/// Feeds every PHASE edge written by the core's driver into the supervisor, like the EXTI handler would (5 ms per step).
struct Bridge {
    sup: Supervisor,
    now: u64,
    last: (bool, bool),
    permit_log: Vec<bool>,
}
struct BridgePins<'a>(&'a mut Bridge);
impl PhasePins for BridgePins<'_> {
    fn apply(&mut self, l: PhaseLevels) {
        let b = &mut *self.0;
        if (l.aphase, l.bphase) != b.last {
            b.last = (l.aphase, l.bphase);
            b.now += 5;
            let o = b.sup.on_phase(b.now, l.aphase, l.bphase);
            b.permit_log.push(o.permit);
        }
    }
}
struct NoTimer;
impl StepTimer for NoTimer {
    fn delay_us(&mut self, _us: u32) {}
}

fn idle() -> Supervisor {
    let mut s = Supervisor::new(CFG, 0, Inputs::DELIVERING, false, false);
    s.tick(200);
    s
}

fn bridge(inputs: Inputs) -> Bridge {
    let mut sup = idle();
    sup.on_inputs(300, inputs);
    let (o, r) = sup.on_arm_edge(1_000);
    assert!(r.is_ok() && o.permit);
    Bridge { sup, now: 1_000, last: (false, false), permit_log: vec![] }
}

/// MANDATORY POST VECTOR (coordinator 2026-11-20): with the load switch off, the nRF declares REVERSE (`MOT_FWD` = 0) and drives the
/// FORWARD phase order. `SUP_PERMIT` must drop within 1 ms: the decoded direction disagrees with the declared one. (Undocked, so the
/// declaration itself is legal: docked + reverse is the H15 vector.)
#[test]
fn post_declared_reverse_but_forward_phase_order_drops_permit_at_once() {
    let mut s = idle();
    s.on_inputs(300, Inputs { docked: false, fwd_intent: false, ..Inputs::DELIVERING });
    let (o, r) = s.on_arm_edge(1_000);
    assert!(r.is_ok() && o.permit, "armed for reverse");
    let o = s.on_phase(1_005, true, false); // forward order from 00: 10 is the first step
    assert!(!o.permit, "dropped inside the handler of the first wrong edge (well inside 1 ms)");
    assert_eq!((o.state, s.reason()), (State::Fault, FaultReason::DirectionMismatch));
    // the mirror image: declared forward (docked), reverse order
    let mut s = idle();
    assert!(s.on_arm_edge(1_000).1.is_ok());
    let o = s.on_phase(1_005, false, true);
    assert!(!o.permit);
    assert_eq!(s.reason(), FaultReason::DirectionMismatch);
}

#[test]
fn the_post_vector_with_the_core_driver() {
    // core drives the forward table while the inputs declare reverse
    let mut br = bridge(Inputs { docked: false, fwd_intent: false, ..Inputs::DELIVERING });
    let mut st = PhaseStepper::new();
    let (n, _) = drive_burst(&mut st, &mut BridgePins(&mut br), &mut NoTimer, MotorDir::Forward, 10, 5_000, |_| true);
    assert_eq!(n, 10, "the core does not know");
    assert_eq!(br.permit_log.first(), Some(&false), "the very first edge already dropped the permit");
    assert_eq!(br.sup.reason(), FaultReason::DirectionMismatch);
}

#[test]
fn core_driven_bursts_are_counted_exactly_by_the_supervisor() {
    let plan = plan_burst(CellParams::default(), MotorLoad::default(), 3_800, 5_000, CFG.fwd_budget).unwrap();
    assert_eq!(plan.steps, 29);
    let mut br = bridge(Inputs::DELIVERING);
    let mut st = PhaseStepper::new();
    let (n, _) = drive_burst(&mut st, &mut BridgePins(&mut br), &mut NoTimer, MotorDir::Forward, plan.steps, 5_000, |_| true);
    assert_eq!(n, 29);
    assert_eq!(br.permit_log.len(), 29, "one phase edge per step");
    assert!(br.permit_log.iter().all(|p| *p), "permission held for the whole burst");
    assert_eq!(br.sup.fwd_in_window(), 29);
    assert_eq!(br.sup.reason(), FaultReason::None);
}

#[test]
fn a_core_reverse_burst_is_counted_as_reverse() {
    let mut br = bridge(Inputs { docked: false, fwd_intent: false, ..Inputs::DELIVERING });
    let mut st = PhaseStepper::new();
    let (n, _) = drive_burst(&mut st, &mut BridgePins(&mut br), &mut NoTimer, MotorDir::Reverse, 100, 5_000, |_| true);
    assert_eq!(n, 100);
    assert_eq!((br.sup.rev_in_window(), br.sup.fwd_in_window()), (100, 0));
    assert!(br.permit_log.iter().all(|p| *p));
}

#[test]
fn a_burst_longer_than_the_budget_is_cut_by_the_supervisor() {
    // a runaway core asking for 40 steps: the permit drops with step 32, step 33 latches
    let mut br = bridge(Inputs::DELIVERING);
    let mut st = PhaseStepper::new();
    drive_burst(&mut st, &mut BridgePins(&mut br), &mut NoTimer, MotorDir::Forward, 40, 5_000, |_| true);
    assert_eq!(br.permit_log.iter().position(|p| !*p), Some(31), "permit gone after the 32nd step edge");
    assert_eq!(br.sup.reason(), FaultReason::BudgetExceeded);
}

#[test]
fn bursts_from_the_plan_fit_the_window_and_the_budget() {
    for mv in [3_700u16, 3_800, 4_200] {
        let plan = plan_burst(CellParams::default(), MotorLoad::default(), mv, 5_000, CFG.fwd_budget).unwrap();
        assert!(plan.steps <= CFG.fwd_budget);
        assert!(plan.burst_ms <= CFG.window_ms, "the burst fits the armed window");
        assert!(plan.burst_ms + plan.rest_ms <= 2 * CFG.min_arm_interval_ms, "at most two ticks per cycle");
    }
}

#[test]
fn bucket_caps_equal_the_cores_limits_for_the_cup_drive() {
    let cal = CUP.cal();
    let hourly_mu = MAX_HOURLY.0 as u64 * 100 / (100 + HOURLY_CAL_MARGIN_PCT as u64);
    assert_eq!(CFG.hour_cap_steps, cal.mu_to_pulses(MilliUnits(hourly_mu as u32)).0, "15 U/h with the calibration margin, in steps");
    assert_eq!(CFG.minute_cap_steps, cal.mu_to_pulses(MAX_PER_MIN).0, "1.7 U/min in steps");
}

/// The 20.5 x 5.9 cup bore (preset 0x27, current CAD) doses 6.8 % more per step: its supervisor caps are recomputed from the core,
/// and they are TIGHTER in steps than the 0x26 caps (running the 0x26 caps on a 5.9 pod would let 6.8 % more volume through).
#[test]
fn bucket_caps_equal_the_cores_limits_for_the_cup59_drive() {
    use openpatch_core::drive_cal::NFP_608_2645_CUP59_MITER_1_1 as CUP59;
    let c59 = Config::CUP59_MITER_1_1;
    let cal = CUP59.cal();
    let hourly_mu = MAX_HOURLY.0 as u64 * 100 / (100 + HOURLY_CAL_MARGIN_PCT as u64);
    assert_eq!(c59.hour_cap_steps, cal.mu_to_pulses(MilliUnits(hourly_mu as u32)).0, "15 U/h with the calibration margin, in steps");
    assert_eq!(c59.minute_cap_steps, cal.mu_to_pulses(MAX_PER_MIN).0, "1.7 U/min in steps");
    assert_eq!((c59.hour_cap_steps, c59.minute_cap_steps), (1_920, 226));
    assert!(c59.hour_cap_steps < CFG.hour_cap_steps && c59.minute_cap_steps < CFG.minute_cap_steps);
    // in volume both caps stay at or below the core limits
    assert!(cal.pulses_to_mu(openpatch_core::Pulses(c59.hour_cap_steps)).0 as u64 <= hourly_mu);
    assert!(cal.pulses_to_mu(openpatch_core::Pulses(c59.minute_cap_steps)).0 <= MAX_PER_MIN.0);
    // everything that is not a volume is the same as on 0x26
    assert_eq!(Config { hour_cap_steps: CFG.hour_cap_steps, minute_cap_steps: CFG.minute_cap_steps, ..c59 }, CFG);
}
