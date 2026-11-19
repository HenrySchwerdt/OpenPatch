//! Reservoir model (Test26100 calibration).
mod common;

use common::TEST_UU;
use openpatch_core::limits::*;
use openpatch_core::*;

fn res(capacity: MilliUnits) -> Reservoir {
    Reservoir::new(capacity, PulseCal { uu_num: TEST_UU, uu_den: 1, turn_x100: 25_600 })
}

#[test]
fn res_unfilled_is_neither_empty_nor_low() {
    let r = res(CAPACITY_200);
    assert_eq!(r.remaining(), MilliUnits(0));
    assert!(!r.is_empty());
    assert!(!r.is_low());
}

#[test]
fn res_fill_validation() {
    let mut r = res(CAPACITY_100);
    assert_eq!(r.fill(MilliUnits(0)), Err(Error::BadArg));
    assert_eq!(r.fill(MilliUnits(CAPACITY_100.0 + 1)), Err(Error::Limit));
    assert_eq!(r.fill(CAPACITY_100), Ok(()));
    assert_eq!(r.remaining(), MilliUnits(100_000));
}

#[test]
fn res_consume_reduces_remaining_exactly() {
    let mut r = res(CAPACITY_200);
    r.fill(MilliUnits(100_000)).unwrap();
    r.consume(Pulses(1000)); // 26.1 U
    assert_eq!(r.remaining(), MilliUnits(73_900));
    r.consume(Pulses(1)); // 100000 - 26126.1 mU -> floor
    assert_eq!(r.remaining(), MilliUnits(73_873));
}

#[test]
fn res_low_alarm_threshold() {
    let mut r = res(CAPACITY_100);
    r.fill(MilliUnits(20_000)).unwrap();
    assert!(!r.is_low());
    r.consume(Pulses(383)); // 9996.3 mU -> remaining 10003 -> not yet
    assert!(!r.is_low());
    r.consume(Pulses(1)); // 10022.4 mU -> remaining 9977
    assert!(r.is_low());
    assert!(!r.is_empty());
    assert_eq!(r.set_low_threshold(MilliUnits(5000)), Ok(()));
    assert!(!r.is_low());
    assert_eq!(r.set_low_threshold(MilliUnits(CAPACITY_100.0 + 1)), Err(Error::BadArg));
}

#[test]
fn res_empty_and_saturating_consume() {
    let mut r = res(CAPACITY_70);
    r.fill(MilliUnits(1000)).unwrap();
    r.consume(Pulses(100_000));
    assert_eq!(r.remaining(), MilliUnits(0));
    assert!(r.is_empty());
    assert!(r.is_low());
}

#[test]
fn res_refill_resets_consumption() {
    let mut r = res(CAPACITY_70);
    r.fill(MilliUnits(5000)).unwrap();
    r.consume(Pulses(100));
    r.fill(MilliUnits(60_000)).unwrap();
    assert_eq!(r.remaining(), MilliUnits(60_000));
    assert_eq!(r.consumed(), Pulses(0));
}

#[test]
fn res_default_low_threshold_is_10_units() {
    let r = res(CAPACITY_70);
    assert_eq!(r.low_threshold(), MilliUnits(10_000));
}

// ---- draw_in (refill by reversing the plunger) ---------------------------------------------
#[test]
fn res_draw_in_shrinks_consumed_counter_first() {
    let mut r = res(CAPACITY_200);
    r.fill(MilliUnits(10_000)).unwrap();
    r.consume(Pulses(100));
    let before = r.remaining();
    r.draw_in(Pulses(40));
    assert_eq!(r.consumed(), Pulses(60));
    assert_eq!(r.fill_level(), MilliUnits(10_000)); // level untouched while consumed > 0
    assert!(r.remaining() > before);
    r.draw_in(Pulses(60)); // exactly the rest
    assert_eq!(r.consumed(), Pulses(0));
    assert_eq!(r.remaining(), MilliUnits(10_000));
}

#[test]
fn res_draw_in_is_exact_in_steps_not_in_floored_mu() {
    let mut r = res(CAPACITY_200);
    r.fill(MilliUnits(50_000)).unwrap();
    r.consume(Pulses(1000));
    for _ in 0..1000 {
        r.draw_in(Pulses(1)); // one step at a time: no per-call rounding loss
    }
    assert_eq!(r.consumed(), Pulses(0));
    assert_eq!(r.remaining(), MilliUnits(50_000));
}

#[test]
fn res_draw_in_beyond_consumed_raises_fill_level() {
    let mut r = res(CAPACITY_200);
    r.fill(MilliUnits(10_000)).unwrap();
    r.consume(Pulses(100));
    r.draw_in(Pulses(150)); // 100 back into the counter, 50 steps = 1305 mU on top
    assert_eq!(r.consumed(), Pulses(0));
    assert_eq!(r.fill_level(), MilliUnits(11_305));
    assert_eq!(r.remaining(), MilliUnits(11_305));
}

#[test]
fn res_draw_in_clamps_at_capacity() {
    let mut r = res(CAPACITY_100);
    r.fill(MilliUnits(99_000)).unwrap();
    r.draw_in(Pulses(1000)); // 26 100 mU would overflow
    assert_eq!(r.fill_level(), CAPACITY_100);
    assert_eq!(r.remaining(), CAPACITY_100);
    assert_eq!(r.consumed(), Pulses(0));
}

#[test]
fn res_draw_in_from_unfilled_start() {
    let mut r = res(CAPACITY_100);
    r.draw_in(Pulses(0));
    assert!(!r.is_filled());
    r.draw_in(Pulses(100)); // 2610 mU
    assert!(r.is_filled());
    assert_eq!(r.fill_level(), MilliUnits(2_610));
    assert_eq!(r.remaining(), MilliUnits(2_610));
    assert_eq!(r.consumed(), Pulses(0));
    let mut c = res(CAPACITY_100);
    c.draw_in(Pulses(1_000_000)); // clamps
    assert_eq!(c.fill_level(), CAPACITY_100);
}

#[test]
fn res_draw_in_inverts_consume_for_every_preset() {
    for pr in drive_cal::PRESETS {
        let mut r = Reservoir::new(CAPACITY_200, pr.cal());
        r.fill(MilliUnits(80_000)).unwrap();
        let rem = r.remaining();
        for n in [1u32, 7, 202, 5000] {
            r.consume(Pulses(n));
            r.draw_in(Pulses(n));
            assert_eq!(r.remaining(), rem, "{:?} {n}", pr.id);
            assert_eq!(r.consumed(), Pulses(0));
        }
    }
}
