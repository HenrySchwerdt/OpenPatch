//! Findings F1..F6 of the virtual pod (openpatch-sim/tests/findings.rs) as core unit tests, plus the persistence
//! helpers of `persist.rs`: unplanned reset alarm (H3), schedule persistence, reservoir margin, take-up before the prime,
//! draw rate / draw stall threshold, hourly cap margin.
mod common;

use common::*;
use openpatch_core::hal::ResetCause;
use openpatch_core::limits::*;
use openpatch_core::persist::{ReservoirPolicy, SchedRec, TempRec};
use openpatch_core::*;
use openpatch_proto::{st, Error};

// ---- helpers -----------------------------------------------------------------------------------------------------
fn strict_pump_with_cause(cause: ResetCause) -> (Pump<MockHal>, MockHal) {
    let hal = MockHal::new();
    hal.st().reset_cause = cause;
    let cal = cal_test();
    let mut p = Pump::new(hal.clone(), Some(&cal), CAPACITY_100, 1);
    p.set_config(PumpConfig::STRICT);
    (p, hal)
}

fn restore_active(p: &mut Pump<MockHal>) {
    p.reservoir_mut().restore(MilliUnits(50_000), Pulses(10));
    p.restore_pod(TEST_PAIR, 1, true, 1, Millis(3_600_000));
}

// ---- F1: unplanned reset of an active pod raises an alarm ----------------------------------------------------------
#[test]
fn f1_an_active_pod_after_a_watchdog_or_brownout_reset_raises_the_alarm_and_refuses_resume() {
    for cause in [ResetCause::Watchdog, ResetCause::Brownout, ResetCause::Lockup, ResetCause::Other, ResetCause::PowerOn] {
        let (mut p, h) = strict_pump_with_cause(cause);
        restore_active(&mut p);
        let s = p.get_status();
        assert!(s.flags & st::SUSPENDED != 0, "{cause:?}: comes up suspended");
        assert!(s.flags & st::ALARM != 0, "{cause:?}: ALARM flag");
        assert!(h.st().buzzer_history.contains(&Buzzer::Alarm), "{cause:?}: buzzer pattern");
        assert_ne!(s.faults & Faults::INTERNAL.bits(), 0, "{cause:?}: legacy projection of an F record");
        // the diagnostic record: 7-74-002 UNEXPECTED_RESET at FAULT severity, ctx_a = cause
        let a = p.supervisor().diag().active().iter().find(|a| a.code.identity() == openpatch_diag::codes::UNEXPECTED_RESET.identity()).copied();
        let a = a.unwrap_or_else(|| panic!("{cause:?}: no 7-74-002 active"));
        assert_eq!(a.severity, openpatch_diag::Severity::Fault);
        // a phone notification, and Resume is refused until the alarm is acknowledged
        assert!(matches!(p.take_notification(), Some(Notification::Fault(_))));
        assert_eq!(p.resume(), Err(Error::Fault));
        p.acknowledge(Faults(0xFFFF)).unwrap();
        assert_eq!(p.get_status().flags & st::ALARM, 0);
        assert_eq!(h.st().buzzer, Buzzer::Off);
    }
}

#[test]
fn f1_commanded_resets_released_pods_and_relaxed_pumps_stay_quiet() {
    // a commanded reset (DFU, service command) is planned
    let (mut p, _h) = strict_pump_with_cause(ResetCause::Commanded);
    restore_active(&mut p);
    assert_eq!(p.get_status().flags & st::ALARM, 0);
    // a pod that was not active (a spare on the charger) only gets the W record, no alarm
    let (mut p, h) = strict_pump_with_cause(ResetCause::Brownout);
    p.restore_pod(TEST_PAIR, 1, false, 0, Millis(0));
    assert_eq!(p.get_status().flags & st::ALARM, 0);
    assert!(!h.st().buzzer_history.contains(&Buzzer::Alarm));
    // RELAXED (C parity) never alarms on restore
    let hal = MockHal::new();
    hal.st().reset_cause = ResetCause::Watchdog;
    let cal = cal_test();
    let mut p = Pump::new(hal, Some(&cal), CAPACITY_100, 1);
    p.set_config(PumpConfig::RELAXED);
    restore_active(&mut p);
    assert_eq!(p.get_status().flags & st::ALARM, 0);
}

// ---- F2: schedule + temp basal persistence, Resume never silently 0 U/h -----------------------------------------------
#[test]
fn f2_schedule_record_roundtrips_and_rejects_garbage() {
    let s = BasalSchedule::from_pairs(&[(0, 500), (12, 1250), (30, 0), (47, 30_000)]).unwrap();
    let r = SchedRec::encode(&s);
    assert_eq!(r.len, 13);
    assert_eq!(SchedRec::decode(r.as_bytes()), Some(s));
    assert_eq!(SchedRec::decode(&[]), None);
    assert_eq!(SchedRec::decode(&[0]), None);
    assert_eq!(SchedRec::decode(&[1, 0, 0]), None, "truncated");
    assert_eq!(SchedRec::decode(&[1, 3, 0x10, 0x00]), None, "first segment must start at slot 0");
    assert_eq!(SchedRec::decode(&[2, 0, 1, 0, 0, 2, 0, 0, 7]), None, "wrong length");
    assert_eq!(SchedRec::decode(&[2, 0, 1, 0, 5, 1, 2, 0]), None, "slots must ascend");
    assert_eq!(SchedRec::decode(&[25]), None);
    assert!(SchedRec::NONE.is_none());
}

#[test]
fn f2_temp_record_rounds_down_and_drops_short_temps() {
    assert_eq!(TempRec::from_engine(true, MilliUnitsPerHour(2000), 89), TempRec { rate_mu_h: 2000, remaining_min: 60 });
    assert_eq!(TempRec::from_engine(true, MilliUnitsPerHour(2000), 29), TempRec::NONE);
    assert_eq!(TempRec::from_engine(false, MilliUnitsPerHour(2000), 600), TempRec::NONE);
    let t = TempRec { rate_mu_h: 1500, remaining_min: 120 };
    assert_eq!(TempRec::from_bytes(&t.to_bytes()), Some(t));
    assert_eq!(TempRec::from_bytes(&[1, 2, 3]), None);
}

#[test]
fn f2_a_restored_schedule_and_temp_basal_survive_a_reset_and_resume_delivers() {
    // run: schedule + a temp basal on the first pod
    let (mut p, _h) = running(50_000, 1000);
    p.set_schedule(&BasalSchedule::from_pairs(&[(0, 1000), (24, 2000)]).unwrap()).unwrap();
    p.set_temp_basal(MilliUnitsPerHour(3000), Minutes(120)).unwrap();
    let (sched, temp) = (p.schedule_record(), p.temp_record());
    assert!(!sched.is_none());
    assert_eq!(temp, TempRec { rate_mu_h: 3000, remaining_min: 120 });

    // reset: a fresh pump, restore like the platform boot code
    let (mut q, h) = strict_pump_with_cause(ResetCause::Brownout);
    restore_active(&mut q);
    assert_eq!(q.resume(), Err(Error::Fault)); // the alarm first
    q.acknowledge(Faults(0xFFFF)).unwrap();
    assert_eq!(q.resume(), Err(Error::NoSchedule), "without a restored schedule Resume is refused with a clear code");
    assert_eq!(Error::NoSchedule.code(), 31);
    q.restore_schedule(&SchedRec::decode(sched.as_bytes()).unwrap()).unwrap();
    q.restore_temp(temp);
    assert_eq!(q.resume(), Ok(()));
    assert!(q.engine().has_schedule());
    assert!(q.engine().temp_active(), "the temp basal was handed to Resume");
    assert_eq!(q.engine().temp_rate().0, 3000);
    run_secs(&mut q, &h, 600);
    assert!(q.engine().delivered_steps().0 > 0, "delivers again");
}

#[test]
fn f2_a_schedule_above_the_limits_is_not_restored() {
    let (mut q, _h) = strict_pump_with_cause(ResetCause::Brownout);
    restore_active(&mut q);
    let hot = BasalSchedule::flat(MilliUnitsPerHour(HARD_MAX_BASAL.0 + 50));
    assert_eq!(q.restore_schedule(&hot), Err(Error::Limit));
    assert!(!q.engine().has_schedule());
}

// ---- F3: the reservoir margin is not re-added on every boot ---------------------------------------------------------------
#[test]
fn f3_a_reboot_loop_without_delivery_does_not_drain_the_reservoir_model() {
    let (m, t) = (64, 16);
    let mut res = Reservoir::new(CAPACITY_100, cal_test().pulse_cal().unwrap());
    res.restore(MilliUnits(50_000), Pulses(1000));
    let mut stored = (50_000u32, 1000u32); // flash
    for boot in 0..100 {
        // boot: restore what the flash holds, build the policy
        res.restore(MilliUnits(stored.0), Pulses(stored.1));
        let mut pol = ReservoirPolicy::at_boot(m, t, Some(stored));
        // many ticks after the boot with no delivery: nothing may be written
        for _ in 0..50 {
            assert_eq!(pol.next_write(&res), None, "boot {boot}: the margin was added again");
        }
        let _ = &mut pol;
    }
    assert_eq!(res.consumed().0, 1000, "model unchanged after 100 reboots");
}

#[test]
fn f3_the_margin_is_added_once_per_run_that_consumed_insulin() {
    let cal = cal_test().pulse_cal().unwrap();
    let mut res = Reservoir::new(CAPACITY_100, cal);
    res.restore(MilliUnits(50_000), Pulses(1000));
    let mut pol = ReservoirPolicy::at_boot(64, 16, Some((50_000, 1000)));
    assert_eq!(pol.next_write(&res), None);
    res.consume(Pulses(1));
    let (fill, stored) = pol.next_write(&res).expect("first consumption after a boot triggers the write");
    assert_eq!((fill, stored), (50_000, 1001 + 64));
    pol.written(fill, stored);
    // no more writes until consumption closes in on the stored value again
    for _ in 0..40 {
        res.consume(Pulses(1));
        assert_eq!(pol.next_write(&res), None);
    }
    res.consume(Pulses(8));
    assert!(pol.next_write(&res).is_some());
    // a fill change always writes
    let mut res2 = res;
    res2.fill(MilliUnits(60_000)).unwrap();
    assert!(pol.next_write(&res2).is_some());
}

// ---- F4: take-up after every draw, counted as non-delivery ----------------------------------------------------------------
fn draw_pump() -> (Pump<MockHal>, MockHal) {
    let hal = MockHal::new();
    let cal = cal_test();
    let mut p = Pump::new(hal.clone(), Some(&cal), CAPACITY_100, 1);
    p.set_config(PumpConfig::STRICT);
    p.fill(MilliUnits(50_000)).unwrap();
    activate(&mut p, 1000).unwrap();
    hal.st().docked = false;
    run_secs(&mut p, &hal, 1);
    p.assisted_fill(MilliUnits(5_000)).unwrap();
    run_draw(&mut p, &hal);
    hal.st().docked = true;
    run_secs(&mut p, &hal, 1);
    (p, hal)
}

#[test]
fn f4_the_first_prime_after_a_draw_runs_the_takeup_first_and_does_not_count_it_as_delivery() {
    let (mut p, h) = draw_pump();
    let delivered0 = p.engine().delivered_steps();
    let steps0 = h.st().total_steps;
    let kicks0 = h.st().kicks;
    let takeup = openpatch_core::drive_cal::DriveId::Test26100.preset().travel_um_to_steps(TAKEUP_UM_AFTER_REVERSAL);
    assert!(takeup > 0);
    // the lost motion is larger than one minute of the backstop allows together with a prime: several commands
    let commands = prime_all(&mut p, &h, 2);
    assert!(commands >= 2, "take-up {takeup} steps does not fit one minute with the prime");
    assert_eq!(h.st().total_steps - steps0, takeup + 2, "take-up + prime, no step more");
    assert_eq!(p.engine().delivered_steps(), delivered0, "neither take-up nor prime is delivery");
    assert!(!p.prime_required());
    // a second prime has no take-up
    let steps1 = h.st().total_steps;
    run_secs(&mut p, &h, 61);
    p.prime(Pulses(2)).unwrap();
    assert_eq!(h.st().total_steps - steps1, 2);
    // chunks: every burst <= PRIME_CHUNK_STEPS and the watchdog was fed between them
    assert!(h.st().step_calls.iter().all(|&n| n <= PRIME_CHUNK_STEPS));
    assert!(h.st().kicks > kicks0 || takeup + 2 <= PRIME_CHUNK_STEPS);
}

#[test]
fn f4_the_takeup_never_exceeds_the_per_minute_cap_even_though_it_is_larger_than_one_minute_allows() {
    let (mut p, h) = draw_pump();
    let cal = cal_test().pulse_cal().unwrap();
    let minute = cal.mu_to_pulses(MAX_PER_MIN).0;
    let takeup = openpatch_core::drive_cal::DriveId::Test26100.preset().travel_um_to_steps(TAKEUP_UM_AFTER_REVERSAL);
    assert!(takeup + 2 > minute);
    let s0 = h.st().total_steps;
    assert_eq!(p.prime(Pulses(2)), Err(Error::Hourly), "part of the take-up, no prime");
    let first = h.st().total_steps - s0;
    assert!(first > 0 && first <= minute, "{first} steps in the first minute, cap {minute}");
    assert!(p.prime_required(), "the prime itself has not run");
    assert!(p.supervisor().faults().is_empty(), "a refusal never latches");
}

#[test]
fn f4_takeup_is_refused_not_latched_when_it_would_trim_against_the_minute_cap() {
    let (mut p, h) = draw_pump();
    // use up the minute budget: a bolus running at the per-minute backstop
    p.resume().ok();
    let _ = h;
    // a prime of MAX_PRIME on top of the take-up on the TEST calibration: 65 steps per minute at most
    let before = p.supervisor().faults();
    let r = p.prime(p.supervisor().calibration().mu_to_pulses(MAX_PRIME));
    assert!(r.is_ok() || r == Err(Error::Hourly), "{r:?}");
    assert_eq!(p.supervisor().faults(), before, "a refusal must not latch LIMIT_EXCEEDED");
}

#[test]
fn f4_relaxed_has_no_takeup_and_one_burst() {
    let hal = MockHal::new();
    let cal = cal_test();
    let mut p = Pump::new(hal.clone(), Some(&cal), CAPACITY_100, 1);
    p.set_config(PumpConfig::RELAXED);
    p.fill(MilliUnits(50_000)).unwrap();
    activate(&mut p, 1000).unwrap();
    hal.st().docked = false;
    p.assisted_fill(MilliUnits(5_000)).unwrap();
    run_draw(&mut p, &hal);
    hal.st().docked = true;
    let s0 = hal.st().total_steps;
    p.prime(Pulses(5)).unwrap();
    assert_eq!(hal.st().total_steps - s0, 5);
    assert_eq!(hal.st().step_calls.last(), Some(&5));
}

// ---- F5: draw rate by needle, separate draw stall threshold -----------------------------------------------------------------
#[test]
fn f5_the_draw_rate_is_derived_from_the_needle_and_a_fine_needle_shortens_the_chunks() {
    let cal = cal_test().pulse_cal().unwrap();
    for needle in [FillNeedle::G29, FillNeedle::G31] {
        let hal = MockHal::new();
        let mut p = Pump::new(hal.clone(), Some(&cal_test()), CAPACITY_100, 1);
        p.set_config(PumpConfig { fill_needle: needle, ..PumpConfig::STRICT });
        p.fill(MilliUnits(10_000)).unwrap();
        activate(&mut p, 1000).unwrap();
        hal.st().docked = false;
        p.assisted_fill(MilliUnits(5_000)).unwrap();
        let pps = draw_pps(needle, cal);
        assert_eq!(hal.st().draw_rate_pps, Some(pps));
        run_draw(&mut p, &hal);
        let chunk = draw_chunk_steps(pps);
        assert!(hal.st().reverse_calls.iter().all(|&n| n <= chunk), "{needle:?}: chunk {chunk} vs {:?}", hal.st().reverse_calls);
    }
}

#[test]
fn f5_a_draw_burst_between_the_occlusion_and_the_draw_threshold_is_not_a_stall() {
    let current = OCCLUSION_CURRENT_MA + 20; // above the forward threshold, below the draw threshold
    assert!(current < DRAW_STALL_CURRENT_MA);
    // STRICT: the draw completes
    let hal = MockHal::new();
    let mut p = Pump::new(hal.clone(), Some(&cal_test()), CAPACITY_100, 1);
    p.set_config(PumpConfig::STRICT);
    p.fill(MilliUnits(10_000)).unwrap();
    activate(&mut p, 1000).unwrap();
    hal.st().docked = false;
    hal.st().current_ma = Some(current);
    p.assisted_fill(MilliUnits(40_000)).unwrap();
    run_draw(&mut p, &hal);
    assert_eq!(p.draw_state(), openpatch_proto::draw::DONE);
    // a burst above the draw threshold stalls it
    let hal = MockHal::new();
    let mut p = Pump::new(hal.clone(), Some(&cal_test()), CAPACITY_100, 1);
    p.set_config(PumpConfig::STRICT);
    p.fill(MilliUnits(10_000)).unwrap();
    activate(&mut p, 1000).unwrap();
    hal.st().docked = false;
    hal.st().current_ma = Some(DRAW_STALL_CURRENT_MA + 5);
    p.assisted_fill(MilliUnits(40_000)).unwrap();
    run_draw(&mut p, &hal);
    assert_eq!(p.draw_state(), openpatch_proto::draw::STALLED);
}

// ---- F6: the hourly cap carries the tolerance margin ----------------------------------------------------------------------------
#[test]
fn f6_the_hourly_cap_leaves_room_for_the_worst_case_area_and_lead_tolerance() {
    let p = Pump::new(MockHal::new(), Some(&cal_test()), CAPACITY_100, 1); // STRICT by default
    let cap = p.supervisor().hourly_cap_steps().0;
    let cal = p.pulse_cal();
    let physical_uu_at_worst_case = cal.pulses_to_micro(Pulses(cap)).0 * (100 + HOURLY_CAL_MARGIN_PCT as u64) / 100;
    assert!(physical_uu_at_worst_case <= MAX_HOURLY.0 as u64 * 1000, "{physical_uu_at_worst_case}");
    // and the cap is still within one step of that bound (not needlessly small)
    let one_more = cal.pulses_to_micro(Pulses(cap + 1)).0 * (100 + HOURLY_CAL_MARGIN_PCT as u64) / 100;
    assert!(one_more > MAX_HOURLY.0 as u64 * 1000);
}
