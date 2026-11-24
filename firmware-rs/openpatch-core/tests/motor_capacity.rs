//! `Hal::motor_capacity` (cup board v4: one arm per supervisor interval and a cell rest between bursts): the core defers the steps
//! the board cannot take NOW to the next tick instead of reporting a short burst, and never carries them over a suspend, a veto or a
//! fault. Boards without a capacity (`None`, the default) keep the old behaviour exactly (every other test file).
mod common;
use common::*;
use openpatch_core::diag::codes;
use openpatch_core::limits::MAX_DEFERRED_STEPS;
use openpatch_core::*;

fn faults_clean(p: &Pump<MockHal>) -> bool {
    p.supervisor().faults().is_empty()
}

fn short_raised(p: &Pump<MockHal>) -> bool {
    p.supervisor().diag().active().iter().any(|a| a.code.identity() == codes::STEPS_SHORT_OF_APPROVAL.identity())
}

#[test]
fn a_bolus_through_a_board_that_can_step_every_other_tick_is_delivered_exactly() {
    let (mut p, h) = running(50_000, 0);
    h.st().capacity_pattern = vec![0, 29];
    p.bolus(MilliUnits(2_000)).unwrap();
    run_secs(&mut p, &h, 200);
    assert!(!p.engine().bolus_active());
    let want = p.pulse_cal().mu_to_pulses(MilliUnits(2_000)).0;
    assert_eq!(h.st().total_steps, want, "every step delivered, none lost, none extra");
    assert_eq!(p.engine().dropped_steps().0, 0);
    assert!(h.st().step_calls.iter().all(|&n| n <= 29), "{:?}", h.st().step_calls);
    assert!(faults_clean(&p));
    assert!(!short_raised(&p));
}

#[test]
fn no_steps_are_asked_for_while_the_board_says_not_now() {
    let (mut p, h) = running(50_000, 0);
    h.st().capacity_pattern = vec![0];
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 5);
    assert!(h.st().step_calls.is_empty());
    assert!(p.engine().pending_steps().0 > 0, "carried, not dropped");
    assert!(faults_clean(&p));
}

#[test]
fn the_carried_backlog_is_bounded() {
    let (mut p, h) = running(50_000, 0);
    h.st().capacity_pattern = vec![0];
    p.bolus(MilliUnits(5_000)).unwrap();
    run_secs(&mut p, &h, 120);
    assert!(p.engine().pending_steps().0 <= MAX_DEFERRED_STEPS);
    assert!(p.engine().dropped_steps().0 > 0, "the excess is counted as dropped");
}

#[test]
fn a_suspend_drops_the_carried_steps_they_never_run_after_the_resume() {
    let (mut p, h) = running(50_000, 0);
    h.st().capacity_pattern = vec![0];
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 3);
    assert!(p.engine().pending_steps().0 > 0);
    p.suspend().unwrap();
    run_secs(&mut p, &h, 1);
    assert_eq!(p.engine().pending_steps().0, 0);
    h.st().capacity_pattern = vec![29];
    p.resume().unwrap();
    run_secs(&mut p, &h, 3);
    assert_eq!(h.st().total_steps, 0, "basal 0, the cancelled bolus is not delivered late");
}

#[test]
fn a_veto_drops_instead_of_carrying() {
    let (mut p, h) = running(50_000, 0);
    h.st().capacity_pattern = vec![0];
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 3);
    let carried = p.engine().pending_steps().0;
    assert!(carried > 0);
    // undocked: the supervisor approves nothing, so nothing may wait for a later dock
    h.st().docked = false;
    h.st().capacity_pattern = vec![29];
    run_secs(&mut p, &h, 1);
    assert_eq!(p.engine().pending_steps().0, 0);
    assert_eq!(h.st().total_steps, 0);
}

#[test]
fn a_short_burst_is_still_reported_and_nothing_is_carried() {
    let (mut p, h) = running(50_000, 0);
    h.st().capacity_pattern = vec![29];
    h.st().steps_limit = 0;
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 3);
    assert!(short_raised(&p));
    assert_eq!(p.engine().pending_steps().0, 0);
}

#[test]
fn a_draw_waits_for_capacity_and_uses_chunks_no_larger_than_it() {
    let (mut p, h) = running(10_000, 1_000);
    p.suspend().unwrap();
    h.st().docked = false;
    h.st().capacity_pattern = vec![0, 29, 0, 29];
    p.assisted_fill(MilliUnits(1_000)).unwrap();
    run_draw(&mut p, &h);
    assert_eq!(p.draw_state(), draw_state::DONE);
    let calls = h.st().reverse_calls.clone();
    assert!(calls.iter().all(|&n| n <= 29), "{calls:?}");
    assert_eq!(calls.iter().sum::<u32>(), p.pulse_cal().mu_to_pulses(MilliUnits(1_000)).0);
}
