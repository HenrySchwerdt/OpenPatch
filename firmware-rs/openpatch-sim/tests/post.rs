//! POST scenarios on the bench controller's interlock board model (`openpatch_sim::board`): the core's
//! `BenchCtl` POST runs unchanged against the electrical model, a fault is injected, and the diagnostic code that
//! the pod raises is asserted. A proof that can not be made (UNKNOWN) never counts as passed.
//! TEST PROJECT, never worn, water only.

mod common;
use common::*;
use openpatch_core::bench_ctl::{BenchCtl, CtlCfg};
use openpatch_core::hal::{Hal, MotorDir, SelfTestOutcome, SelfTestStep};
use openpatch_sim::board::SimPins;
use openpatch_sim::params::Params;
use openpatch_sim::world::{SimHal, World};
use std::cell::RefCell;
use std::rc::Rc;

fn codes(o: &openpatch_sim::runner::RunOutput, sub_op: u8) -> Vec<String> {
    o.verdict.selftests.iter().find(|s| s.sub_op == sub_op).unwrap_or_else(|| panic!("no self-test {sub_op}: {:?}", o.verdict.selftests)).codes.clone()
}

fn st(o: &openpatch_sim::runner::RunOutput, sub_op: u8) -> (u16, u16) {
    let s = o.verdict.selftests.iter().find(|s| s.sub_op == sub_op).expect("self-test ran");
    assert_eq!(s.result, 0, "RunSelfTest accepted");
    (s.steps_passed, s.steps_failed)
}

#[test]
fn a_healthy_board_passes_every_proof_and_raises_no_code() {
    let o = run("post_clean");
    assert_eq!(st(&o, 1), (0b1, 0), "POST-S: the passive checks passed");
    assert_eq!(st(&o, 2), (0b111, 0), "POST-A: gate cut, dock/DIR block, over-current leg");
    assert!(o.verdict.selftests.iter().all(|s| s.codes.is_empty()), "{:?}", o.verdict.selftests);
    assert!(o.verdict.notes.is_empty(), "{:?}", o.verdict.notes);
}

#[test]
fn a_stuck_latch_is_named_by_post_s() {
    let o = run("post_stuck_latch");
    let (_, failed) = st(&o, 1);
    assert_eq!(failed, 0b1);
    assert!(codes(&o, 1).contains(&"1-05-003".to_string()), "{:?}", codes(&o, 1));
    // POST-A: nothing is reported as passed on a board whose latch can not be cleared
    let (passed, failed) = st(&o, 2);
    assert_eq!(passed & failed, 0);
    assert!(failed != 0, "POST-A fails too");
}

#[test]
fn a_shorted_p_fet_q4_latches_replace_controller_and_never_resets_in_a_loop() {
    let o = run("post_stuck_q4");
    assert!(codes(&o, 1).contains(&"1-06-001".to_string()), "{:?}", codes(&o, 1));
    // quarantined: the later proofs are UNKNOWN (neither passed nor failed)
    let (passed, failed) = st(&o, 2);
    assert_eq!((passed, failed), (0, 0), "no proof is made on a board whose supply can not be cut");
    // the code is a latched L code: FRU controller, REPLACE
    let id = openpatch_core::diag::codes::VMOT_STUCK_ON.identity();
    let info = openpatch_core::diag::CATALOGUE.iter().find(|c| c.code.identity() == id).unwrap();
    assert_eq!(info.severity, openpatch_core::diag::Severity::Latched);
    assert_eq!(info.fru, openpatch_core::diag::Fru::Ctrl);
    assert_eq!(info.action, openpatch_core::diag::Action::Replace);
    // a reset can not help, so the TPL5010 is not starved: no watchdog reset in the run
    assert!(o.verdict.resets.is_empty(), "{:?}", o.verdict.resets);
    assert!(has_fault(&o.verdict, "INTERNAL"), "the legacy fault bits show a stopped pod: {:?}", o.verdict.faults);
}

#[test]
fn a_dock_gate_input_that_disagrees_with_the_hall_is_named() {
    let o = run("post_dock_gate_stuck");
    assert!(codes(&o, 1).contains(&"1-07-003".to_string()), "{:?}", codes(&o, 1));
}

#[test]
fn an_unplugged_ffc_is_named_and_stops_the_pod() {
    let o = run("post_ffc_unplugged");
    assert!(codes(&o, 1).contains(&"3-30-001".to_string()), "{:?}", codes(&o, 1));
    assert!(has_fault(&o.verdict, "INTERNAL"), "{:?}", o.verdict.faults);
}

#[test]
fn an_over_current_leg_that_never_trips_is_named_by_the_over_current_proof() {
    let o = run("post_oc_leg_stuck");
    let (passed, failed) = st(&o, 2);
    assert_eq!(failed & 0b100, 0b100, "step 3 (over-current) failed");
    assert_eq!(passed & 0b011, 0b011, "the gate proofs still pass");
    assert!(codes(&o, 2).contains(&"1-07-007".to_string()), "{:?}", codes(&o, 2));
}

#[test]
fn a_wrong_dir_polarity_option_is_named_4_40_003() {
    let o = run("post_dir_polarity");
    assert!(codes(&o, 1).contains(&"4-40-003".to_string()), "{:?}", codes(&o, 1));
    let (passed, _failed) = st(&o, 2);
    assert_eq!(passed, 0, "no proof passes with an inverted DIR gate input");
}

// ---- model level -----------------------------------------------------------------------------------------------

fn world() -> Rc<RefCell<World>> {
    Rc::new(RefCell::new(World::new(Params::default(), 1)))
}

#[test]
fn the_controller_runs_the_real_sequence_on_the_world_model() {
    let w = world();
    let mut c = BenchCtl::new(SimPins(w.clone()), CtlCfg::BENCH);
    assert!(c.power_up(true, MotorDir::Forward).is_ok());
    assert!(w.borrow().vmot_on());
    assert!(w.borrow().board.vmot_mv > 4_300.0);
    assert!(c.power_off());
    assert!(!w.borrow().vmot_on());
    // draw: undocked, reverse only
    w.borrow_mut().docked_phys = false;
    assert!(c.power_up(false, MotorDir::Reverse).is_ok());
    assert!(w.borrow().vmot_on());
    assert!(c.power_off());
}

#[test]
fn the_over_current_latch_cuts_the_world_supply_and_clears_only_with_mcu_en() {
    let w = world();
    let mut c = BenchCtl::new(SimPins(w.clone()), CtlCfg::BENCH);
    c.power_up(true, MotorDir::Forward).unwrap();
    w.borrow_mut().board.oc_test = true; // 45 mA reference, 160 mA holding
    let t = w.borrow().t_us + 30_000;
    w.borrow_mut().advance_to(t);
    assert!(!w.borrow().board.oc_ok);
    assert!(!w.borrow().vmot_on(), "the over-current latch opened the supply switch");
    w.borrow_mut().board.oc_test = false;
    let t = w.borrow().t_us + 30_000;
    w.borrow_mut().advance_to(t);
    assert!(!w.borrow().board.oc_ok, "stays tripped until MCU_EN is cycled");
    c.power_off();
    assert!(c.power_up(true, MotorDir::Forward).is_ok());
}

#[test]
fn sim_hal_selftest_goes_through_the_core_proofs_and_reports_readbacks() {
    let w = world();
    let mut h = SimHal(w.clone());
    for s in [SelfTestStep::PassiveChecks, SelfTestStep::GateCut, SelfTestStep::DockGateBlock, SelfTestStep::OverCurrentCut] {
        assert_eq!(h.selftest(s), SelfTestOutcome::Passed, "{s:?}");
    }
    let rb = h.interlock_state().expect("bench board has readbacks");
    assert_eq!(rb.mot_allow, Some(false));
    assert_eq!(rb.oc_ok, Some(true));
    assert_eq!(rb.pod_present, Some(true));
    assert!(h.take_diag().is_none());
}

#[test]
fn the_pod_stays_serviced_by_the_watchdog_during_post_a() {
    // POST-A takes simulated time: the proofs service the TPL5010 themselves (BenchPins::kick)
    let w = world();
    let mut h = SimHal(w.clone());
    let t0 = w.borrow().t_us;
    h.watchdog_kick();
    for s in [SelfTestStep::GateCut, SelfTestStep::DockGateBlock, SelfTestStep::OverCurrentCut] {
        assert_eq!(h.selftest(s), SelfTestOutcome::Passed);
    }
    assert!(w.borrow().reset_pending.is_none(), "no watchdog reset during the proofs");
    assert!(w.borrow().t_us - t0 < 1_900_000, "POST-A proofs are short: {} us", w.borrow().t_us - t0);
}

