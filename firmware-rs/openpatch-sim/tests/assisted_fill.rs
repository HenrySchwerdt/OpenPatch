//! Assisted (pressure) fill, spec 3c (decision 2026-11-19): the pod is undocked and suspended, the user pushes WATER through the
//! septum with a syringe while the motor retracts the plunger at a fixed, rate-limited speed. The fill volume is booked from
//! the plunger travel, the reservoir stays at positive pressure (no air through the outlet needle), the excess leaves as
//! drops at the needle tip, a prime follows before docking, and the interlock lets the motor reverse only while undocked.
//!
//! What the simulator can and can not show (read before trusting a number): the plant's syringe is a pressure source on the
//! septum (`Plant::fill_push_kpa`); its water accounting under pressure (compression of the lumped compliance, through-flow at the
//! needle tip) is NOT calibrated, so these tests assert the pod's behaviour (state, booking, interlock, faults, rate), not
//! gravimetric volumes. The case "the user does not push" is a documented gap: see `tests/findings.rs`.
//! TEST PROJECT, never worn, water only.

mod common;
use common::*;
use openpatch_core::limits::{draw_pps, FillNeedle, ASSISTED_FILL_PPS};
use openpatch_sim::scenario::Action;

#[test]
fn the_retraction_rate_is_fixed_and_rate_limited() {
    let cal = openpatch_core::drive_cal::NFP_608_2645_G16_20.cal();
    assert_eq!(ASSISTED_FILL_PPS, 200, "a hand pushing a syringe through a small septum: 0.8 U/s");
    for n in [FillNeedle::G27, FillNeedle::G29, FillNeedle::G31] {
        assert!(draw_pps(n, cal) <= ASSISTED_FILL_PPS, "{n:?}");
    }
    // the motor of the pod never retracts faster than the fixed rate in a run
    let o = run("assisted_fill_user_pushes");
    let w = o.dev.world.borrow();
    assert!(w.params.motor.reverse_rate_hz <= ASSISTED_FILL_PPS as f64, "{}", w.params.motor.reverse_rate_hz);
}

#[test]
fn a_user_who_pushes_gets_the_fill_booked_from_the_travel_under_the_interlock() {
    let o = run("assisted_fill_user_pushes");
    let v = &o.verdict;
    assert_eq!(v.draws.len(), 1);
    let d = &v.draws[0];
    assert_eq!(d.core_state, openpatch_proto::draw::DONE);
    assert!((d.core_drawn_mu as f64 - 20_000.0).abs() < 500.0, "booked from the travel: core says {}", d.core_drawn_mu);
    // interlock: reverse only when undocked (DIR_REV leg), nothing moved forward undocked, no fault, no refused burst
    assert_eq!(v.interlock.bursts_blocked_total, 0);
    assert!(!v.interlock.violated);
    assert!(v.faults.is_empty(), "{:?}", v.faults);
}

#[test]
fn a_prime_is_required_before_docking_resume() {
    let mut sc = scenario("assisted_fill_user_pushes");
    sc.events.retain(|e| !matches!(e.action, Action::Prime { .. }));
    let o = run_sc(sc);
    assert!(o.verdict.notes.iter().any(|n| n.contains("resume -> result 26")), "{:?}", o.verdict.notes);
    // ... and with the primes (the take-up needs two prime commands) the resume works
    let o = run("assisted_fill_user_pushes");
    assert!(!o.verdict.notes.iter().any(|n| n.contains("resume -> result")), "{:?}", o.verdict.notes);
}

#[test]
fn a_user_who_pushes_too_hard_does_not_over_book_the_fill_and_never_runs_forward() {
    // 150 kPa on the septum: the pressure assists the retraction instead of loading it. The pod must not book more than it
    // was asked for, must not move forward undocked and must not book anything as delivery; the excess pressure leaves as
    // drops at the needle tip (no check valve, undocked, water only).
    let o = run("assisted_fill_user_pushes_hard");
    let v = &o.verdict;
    let d = &v.draws[0];
    assert!(d.core_drawn_mu <= 20_000 + 500, "never over-booked: {}", d.core_drawn_mu);
    assert!(d.core_state == openpatch_proto::draw::DONE || d.core_state == openpatch_proto::draw::STALLED, "{d:?}");
    assert!(!v.interlock.violated);
    assert!(v.core_delivered_mu <= v.scheduled_mu + 15, "nothing was booked as delivery");
    let w = o.dev.world.borrow();
    assert!(w.plant.peak_pressure_kpa <= 200.0, "{} kPa", w.plant.peak_pressure_kpa);
    assert!(w.plant.out_ul > 0.0, "the excess leaves at the needle: {} ul", w.plant.out_ul);
}

#[test]
fn a_user_who_does_not_push_is_a_documented_gap_not_a_silent_pass() {
    // The retracting plunger makes a vacuum and draws AIR through the open outlet needle (no check valve). Current and angle do
    // not separate this from a healthy fill (peak 134 mA against 136 mA), so the pod books the travel. The gap is recorded
    // as an ignored finding (tests/findings.rs); here the observable fact is asserted so a future detector flips this test.
    let o = run("assisted_fill_user_does_not_push");
    let d = &o.verdict.draws[0];
    assert_eq!(d.core_state, openpatch_proto::draw::DONE, "no detector exists today: {d:?}");
    let w = o.dev.world.borrow();
    assert!(w.plant.line_air_ul > 20.0 || w.plant.bubble_ul > 20.0, "the travel was booked but air came in: line {} bubble {}", w.plant.line_air_ul, w.plant.bubble_ul);
    assert!(!o.verdict.interlock.violated);
}
