//! DeliveryEngine (SMA pulse actuator; Test26100 calibration, 26 100 uU/pulse).
mod common;

use common::TEST_UU;
use openpatch_core::limits::*;
use openpatch_core::*;

const H: u64 = 3_600_000;
const MIN: u64 = 60_000;

fn flat(rate: u32) -> BasalSchedule {
    BasalSchedule::flat(MilliUnitsPerHour(rate))
}

fn sched(pairs: &[(u8, u32)]) -> BasalSchedule {
    BasalSchedule::from_pairs(pairs).unwrap()
}

fn init() -> DeliveryEngine {
    DeliveryEngine::new(PulseCal { uu_num: TEST_UU, uu_den: 1, turn_x100: 25_600 })
}

fn setup(rate: u32) -> DeliveryEngine {
    let mut de = init();
    assert_eq!(de.set_schedule(&flat(rate)), Ok(()));
    de.comm_heartbeat();
    de.resume();
    de
}

/// Run `ms` in 1 s ticks, committing everything; returns total pulses.
fn run(de: &mut DeliveryEngine, ms: u64) -> u32 {
    let mut total = 0;
    let mut t = 0;
    while t < ms {
        let n = de.tick(Millis(1000));
        de.commit(n);
        total += n.0;
        t += 1000;
    }
    total
}

fn temp(de: &mut DeliveryEngine, rate: u32, min: u32) -> Result<(), Error> {
    de.start_temp_basal(MilliUnitsPerHour(rate), Minutes(min))
}

#[test]
fn de_starts_suspended_and_delivers_nothing() {
    let mut de = init();
    de.set_schedule(&flat(1000)).unwrap();
    assert_eq!(run(&mut de, H), 0);
    assert!(de.is_suspended());
}

#[test]
fn de_zero_dt_returns_zero() {
    let mut de = setup(1000);
    assert_eq!(de.tick(Millis(0)), Pulses(0));
}

#[test]
fn de_flat_basal_one_hour_exact_pulses() {
    let mut de = setup(1000); // 1 U/h = 38.31 pulses
    assert_eq!(run(&mut de, H), 38);
    let r = de.report();
    assert_eq!(r.scheduled, MilliUnits(1000));
    assert_eq!(r.delivered_steps, Pulses(38));
    assert_eq!(r.delivered, MilliUnits(991));
}

#[test]
fn de_fractional_pulses_accumulate_over_a_day() {
    let mut de = setup(5000); // 120 U/day = 4597.7 pulses
    assert_eq!(run(&mut de, 24 * H), 4597);
    let r = de.report();
    assert_eq!(r.scheduled, MilliUnits(120_000));
    assert!(r.scheduled.0 - r.delivered.0 < 27); // < 1 pulse
}

#[test]
fn de_segments_apply_by_time_of_day() {
    let mut de = init();
    let s = sched(&[(0, 1000), (2, 0), (4, 2000)]);
    assert_eq!(de.set_schedule(&s), Ok(()));
    de.resume();
    de.comm_heartbeat();
    // 1 U + 0 U + 2 U = 3 U = 114.9 pulses
    assert_eq!(run(&mut de, 3 * H), 114);
    assert_eq!(de.current_rate(), MilliUnitsPerHour(2000));
}

#[test]
fn de_big_tick_equals_small_ticks_across_boundaries() {
    let s = sched(&[(0, 1000), (2, 0), (4, 2000)]);
    let mut a = init();
    let mut b = init();
    a.set_schedule(&s).unwrap();
    b.set_schedule(&s).unwrap();
    a.resume();
    b.resume();
    let big = a.tick(Millis(3 * H));
    assert_eq!(big.0, run(&mut b, 3 * H));
    assert_eq!(a.accumulator(), b.accumulator());
}

#[test]
fn de_schedule_wraps_at_midnight() {
    let mut de = init();
    de.set_schedule(&sched(&[(0, 1000), (46, 3000)])).unwrap();
    de.resume();
    de.set_time_of_day(Millis(23 * H + 30 * MIN));
    de.comm_heartbeat();
    run(&mut de, H); // 30 min @3 U/h + 30 min @1 U/h = 2 U
    assert_eq!(de.report().scheduled, MilliUnits(2000));
    assert_eq!(de.ms_of_day(), (30 * MIN) as u32);
}

#[test]
fn de_schedule_validation() {
    let s = flat(1000);
    assert_eq!(s.validate(), Ok(()));
    // count == 0
    assert_eq!(BasalSchedule::new().validate(), Err(Error::BadArg));
    // must start at slot 0
    assert_eq!(sched(&[(1, 1000)]).validate(), Err(Error::BadArg));
    // not ascending
    assert_eq!(sched(&[(0, 1000), (0, 5)]).validate(), Err(Error::BadArg));
    // out of range
    assert_eq!(sched(&[(0, 1000), (48, 5)]).validate(), Err(Error::BadArg));
    // count 25 is unrepresentable (heapless capacity 24): construction itself is refused
    let too_many: Vec<(u8, u32)> = (0..25).map(|i| (i as u8, 1000)).collect();
    assert!(BasalSchedule::from_pairs(&too_many).is_none());
    // C also checked a NULL schedule: not representable in Rust (references are never null)
    let mut de = init();
    assert_eq!(de.set_schedule(&BasalSchedule::new()), Err(Error::BadArg));
    assert!(!de.has_schedule());
}

#[test]
fn de_temp_basal_overrides_then_returns_to_basal() {
    let mut de = setup(1000);
    assert_eq!(temp(&mut de, 2000, 30), Ok(()));
    assert_eq!(de.current_rate(), MilliUnitsPerHour(2000));
    assert_eq!(de.temp_remaining(), Minutes(30));
    run(&mut de, 30 * MIN); // 1000 mU
    assert!(!de.temp_active());
    assert!(de.take_events().has(EngineEvents::TEMP_DONE));
    assert_eq!(de.take_events(), EngineEvents(0));
    assert_eq!(de.current_rate(), MilliUnitsPerHour(1000));
    de.comm_heartbeat();
    run(&mut de, 30 * MIN); // + 500 mU
    assert_eq!(de.report().scheduled, MilliUnits(1500));
}

#[test]
fn de_temp_basal_zero_rate_is_allowed() {
    let mut de = setup(1000);
    assert_eq!(temp(&mut de, 0, 60), Ok(()));
    assert_eq!(run(&mut de, 25 * MIN), 0); // before the 30 min comm-loss fallback
}

#[test]
fn de_temp_basal_validation() {
    let mut de = setup(1000);
    assert_eq!(temp(&mut de, 1000, 0), Err(Error::BadArg));
    assert_eq!(temp(&mut de, 1000, 45), Err(Error::BadArg));
    assert_eq!(temp(&mut de, 1000, 750), Err(Error::BadArg));
    assert_eq!(temp(&mut de, 1000, 720), Ok(()));
    de.suspend();
    assert_eq!(temp(&mut de, 1000, 30), Err(Error::Suspended));
}

#[test]
fn de_cancel_temp_basal() {
    let mut de = setup(1000);
    assert!(!de.cancel_temp_basal());
    temp(&mut de, 3000, 60).unwrap();
    assert!(de.cancel_temp_basal());
    assert_eq!(de.current_rate(), MilliUnitsPerHour(1000));
    assert_eq!(de.temp_remaining(), Minutes(0));
}

#[test]
fn de_temp_basal_falls_back_30min_after_comm_loss() {
    let mut de = setup(1000);
    temp(&mut de, 4000, 120).unwrap();
    run(&mut de, 29 * MIN);
    assert!(de.temp_active());
    run(&mut de, 2 * MIN); // crosses the 30 min mark
    assert!(!de.temp_active());
    assert!(de.take_events().has(EngineEvents::TEMP_COMM_FALLBACK));
    assert_eq!(de.current_rate(), MilliUnitsPerHour(1000));
    // 30 min @4 U/h = 2000 mU, then 1 min @1 U/h = 16.67 mU
    assert_eq!(de.report().scheduled, MilliUnits(2016));
}

#[test]
fn de_heartbeat_extends_temp_basal() {
    let mut de = setup(1000);
    temp(&mut de, 4000, 120).unwrap();
    run(&mut de, 20 * MIN);
    de.comm_heartbeat();
    run(&mut de, 29 * MIN);
    assert!(de.temp_active());
    assert!(!de.take_events().has(EngineEvents::TEMP_COMM_FALLBACK));
}

#[test]
fn de_bolus_runs_at_1_5_u_per_min() {
    let mut de = setup(0);
    assert_eq!(de.start_bolus(MilliUnits(1000)), Ok(()));
    assert_eq!(de.bolus_remaining(), MilliUnits(1000));
    let mut pulses = run(&mut de, 10_000); // 10 s = 250 mU = 9.58 pulses
    assert_eq!(pulses, 9);
    assert_eq!(de.bolus_remaining(), MilliUnits(750));
    pulses += run(&mut de, 30_000);
    assert_eq!(pulses, 38); // 1000 mU = 38.31 pulses
    assert!(!de.bolus_active());
    assert!(de.take_events().has(EngineEvents::BOLUS_DONE));
}

#[test]
fn de_bolus_pauses_basal_without_catch_up() {
    let mut de = setup(5000);
    de.start_bolus(MilliUnits(1000)).unwrap();
    let during = run(&mut de, 40_000); // bolus only: 38.31 pulses
    assert_eq!(during, 38);
    assert_eq!(de.report().scheduled, MilliUnits(1000)); // basal not scheduled while bolus ran
}

#[test]
fn de_bolus_validation() {
    let mut de = setup(0);
    assert_eq!(de.start_bolus(MilliUnits(0)), Err(Error::BadArg));
    assert_eq!(de.start_bolus(MilliUnits(500)), Ok(()));
    assert_eq!(de.start_bolus(MilliUnits(500)), Err(Error::Busy));
    de.suspend();
    assert_eq!(de.start_bolus(MilliUnits(500)), Err(Error::Suspended));
}

#[test]
fn de_cancel_bolus_reports_undelivered() {
    let mut de = setup(0);
    assert_eq!(de.cancel_bolus(), MilliUnits(0));
    de.start_bolus(MilliUnits(1000)).unwrap();
    run(&mut de, 10_000);
    assert_eq!(de.cancel_bolus(), MilliUnits(750));
    assert!(!de.bolus_active());
    assert_eq!(run(&mut de, 60_000), 0);
}

#[test]
fn de_many_small_boluses_do_not_lose_fractions() {
    let mut de = setup(0);
    let mut total = 0;
    for _ in 0..100 {
        assert_eq!(de.start_bolus(MilliUnits(50)), Ok(())); // 1.92 pulses each
        total += run(&mut de, 5000);
        assert!(!de.bolus_active());
    }
    assert_eq!(total, 191); // floor(5000 / 26.1)
}

#[test]
fn de_suspend_cancels_bolus_and_temp_and_shows_deficit() {
    let mut de = setup(1000);
    temp(&mut de, 2000, 120).unwrap();
    de.start_bolus(MilliUnits(5000)).unwrap();
    de.suspend();
    assert!(!de.bolus_active());
    assert!(!de.temp_active());
    assert_eq!(run(&mut de, 30 * MIN), 0);
    de.comm_heartbeat();
    de.resume();
    run(&mut de, 30 * MIN);
    let r = de.report();
    assert_eq!(r.scheduled, MilliUnits(1000)); // 2 x 30 min @ 1 U/h
    assert!(r.delivered.0 < 520); // only the resumed half-hour
    assert!(r.delivered.0 > 480);
}

#[test]
fn de_commit_tracks_dropped_steps() {
    let mut de = setup(5000);
    let n = de.tick(Millis(60_000));
    assert!(n.0 > 0);
    de.commit(Pulses(0)); // supervisor vetoed everything
    let r = de.report();
    assert_eq!(r.delivered_steps, Pulses(0));
    assert_eq!(r.dropped_steps, n);
    let m = de.tick(Millis(60_000));
    de.commit(Pulses(m.0 + 99)); // over-commit is clamped
    assert_eq!(de.report().delivered_steps, m);
}

#[test]
fn de_uncommitted_pending_accumulates() {
    let mut de = setup(5000);
    let a = de.tick(Millis(60_000));
    let b = de.tick(Millis(60_000));
    assert_eq!(de.pending_steps(), Pulses(a.0 + b.0));
    de.commit(Pulses(a.0 + b.0));
    assert_eq!(de.pending_steps(), Pulses(0));
}

#[test]
fn de_events_for_bolus_done_not_reported_twice() {
    let mut de = setup(0);
    de.start_bolus(MilliUnits(100)).unwrap();
    run(&mut de, 10_000);
    assert!(de.take_events().has(EngineEvents::BOLUS_DONE));
    assert_eq!(de.take_events(), EngineEvents(0));
}

#[test]
fn de_no_schedule_means_zero_rate() {
    let mut de = init();
    de.resume();
    assert_eq!(de.current_rate(), MilliUnitsPerHour(0));
    assert_eq!(run(&mut de, H), 0);
}

#[test]
fn de_time_of_day_is_normalised() {
    let mut de = init();
    de.set_time_of_day(Millis(DAY_MS as u64 + 5));
    assert_eq!(de.ms_of_day(), 5);
}
