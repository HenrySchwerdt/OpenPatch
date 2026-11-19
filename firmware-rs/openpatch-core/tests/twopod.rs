//! Two-pod system (spec/design-parameters.md section 1b): dock input, wear timer, pairing,
//! Activate / Release, charger. Port of `firmware/tests/test_twopod.c`.
mod common;
use common::*;
use openpatch_core::limits::*;
use openpatch_core::log::LOG_CAPACITY;
use openpatch_core::*;
use openpatch_proto::{cmd, st, tag};
use openpatch_proto::{Command, CommandBody};

const HOUR_MS: u64 = 3_600_000;
const ROLE_A: u8 = 1;
const ROLE_B: u8 = 2;

type P = Pump<MockHal>;

/// Big jumps for the wear timer: one tick per hour.
fn advance_hours(p: &mut P, h: &MockHal, hours: u32) {
    for _ in 0..hours {
        h.advance_ms(HOUR_MS);
        p.tick();
    }
}

fn log_count(p: &P, kind: EventType) -> usize {
    let mut e = [Event::default(); LOG_CAPACITY];
    let n = p.log().read(0, &mut e);
    e[..n].iter().filter(|x| x.kind == kind as u8).count()
}

fn log_has(p: &P, kind: EventType) -> bool {
    log_count(p, kind) > 0
}

fn status(p: &mut P) -> openpatch_proto::Status {
    p.get_status()
}

fn total_steps(h: &MockHal) -> u32 {
    h.st().total_steps
}

fn set_docked(h: &MockHal, d: bool) {
    h.st().docked = d;
}

/// Filled, paired, unactivated.
fn ready() -> (P, MockHal) {
    let (mut p, h) = new_pump();
    p.fill(MilliUnits(100_000)).unwrap();
    p.set_pairing(TEST_PAIR, ROLE_A).unwrap();
    (p, h)
}

fn act_args(activation_id: u32) -> ActivateArgs {
    ActivateArgs {
        pair_id: TEST_PAIR,
        activation_id,
        schedule: BasalSchedule::flat(MilliUnitsPerHour(1000)),
        temp: None,
    }
}

// ---- dock input -----------------------------------------------------------------------------
#[test]
fn dock_undocked_pod_never_steps_and_reports_paused() {
    let (mut p, h) = running(100_000, 3000);
    run_secs(&mut p, &h, 600);
    let before = total_steps(&h);
    assert!(before > 0);
    set_docked(&h, false);
    run_secs(&mut p, &h, 3600);
    assert_eq!(total_steps(&h), before); // not a single step
    let s = status(&mut p);
    assert_eq!(s.delivery_state, DeliveryState::PausedUndocked as u8);
    assert_eq!(s.flags & st::DOCKED, 0);
    assert_ne!(s.flags & st::ACTIVE, 0);
    assert_eq!(s.faults, 0); // a pause, not a latched fault
    assert_eq!(log_count(&p, EventType::Undocked), 1);
}

#[test]
fn dock_resumes_basal_without_catch_up_when_redocked() {
    let (mut p, h) = running(100_000, 3000);
    set_docked(&h, false);
    run_secs(&mut p, &h, 1800);
    assert_eq!(total_steps(&h), 0);
    set_docked(&h, true);
    run_secs(&mut p, &h, 1);
    assert_eq!(log_count(&p, EventType::Docked), 1);
    assert_eq!(status(&mut p).delivery_state, DeliveryState::Active as u8);
    run_secs(&mut p, &h, 3600);
    // one hour of 3 U/h = 114.9 steps; the missed half hour is NOT made up
    let n = total_steps(&h);
    assert!((114..=116).contains(&n), "{n}");
}

#[test]
fn dock_loss_cancels_running_bolus_and_blocks_new_ones() {
    let (mut p, h) = running(100_000, 0);
    assert_eq!(p.bolus(MilliUnits(5000)), Ok(()));
    run_secs(&mut p, &h, 10);
    let mid = total_steps(&h);
    assert!(mid > 0);
    set_docked(&h, false);
    run_secs(&mut p, &h, 1);
    assert_eq!(total_steps(&h), mid);
    assert!(!p.engine().bolus_active());
    assert!(log_has(&p, EventType::BolusCancel));
    assert_eq!(p.bolus(MilliUnits(50)), Err(Error::NotDocked));
    set_docked(&h, true);
    run_secs(&mut p, &h, 60);
    assert_eq!(total_steps(&h), mid); // the cancelled bolus does not come back
}

#[test]
fn dock_is_sampled_before_every_motor_action_not_once_a_second() {
    let (mut p, h) = running(100_000, 0);
    set_docked(&h, false); // no tick since
    assert_eq!(p.bolus(MilliUnits(50)), Err(Error::NotDocked));
    let _ = p.suspend();
    assert_eq!(p.resume(), Err(Error::NotDocked));
    assert_eq!(p.prime(Pulses(5)), Err(Error::NotDocked));
    assert_eq!(total_steps(&h), 0);
}

#[test]
fn dock_supervisor_is_the_hard_gate() {
    let mut sv = SafetySupervisor::new(Millis(0), AngleCounts(0), cal_test().pulse_cal().unwrap());
    let res = MilliUnits(100_000);
    // starts closed: neither docked nor active
    assert_eq!(sv.approve_steps(Millis(0), Pulses(5), res), Pulses(0));
    sv.set_active(true);
    assert_eq!(sv.approve_steps(Millis(0), Pulses(5), res), Pulses(0));
    sv.set_docked(true);
    assert_eq!(sv.approve_steps(Millis(0), Pulses(5), res), Pulses(5));
    sv.set_docked(false);
    assert_eq!(sv.approve_steps(Millis(0), Pulses(5), res), Pulses(0));
    assert!(sv.faults().is_empty()); // gating is not a fault
    sv.set_docked(true);
    sv.set_active(false);
    assert_eq!(sv.approve_steps(Millis(0), Pulses(5), res), Pulses(0));
}

/// Hal with only the required methods: `docked` / `charger_present` use the trait defaults.
struct NoHooksHal(MockHal);

impl Hal for NoHooksHal {
    fn motor_step(&mut self, steps: Pulses) -> Pulses {
        self.0.motor_step(steps)
    }
    fn motor_enable(&mut self, e: bool) {
        self.0.motor_enable(e)
    }
    fn angle_read(&mut self) -> Option<AngleCounts> {
        self.0.angle_read()
    }
    fn watchdog_kick(&mut self) {
        self.0.watchdog_kick()
    }
    fn buzzer(&mut self, p: Buzzer) {
        self.0.buzzer(p)
    }
    fn battery_mv(&mut self) -> u16 {
        self.0.battery_mv()
    }
    fn time_ms(&mut self) -> Millis {
        self.0.time_ms()
    }
}

#[test]
fn dock_missing_hal_hooks_mean_not_docked() {
    let cal = cal_test();
    let mut p = Pump::new(NoHooksHal(MockHal::new()), Some(&cal), CAPACITY_100, 1);
    assert_eq!(p.fill(MilliUnits(100_000)), Ok(()));
    assert_eq!(p.set_pairing(TEST_PAIR, ROLE_A), Ok(()));
    let a = ActivateArgs {
        pair_id: TEST_PAIR,
        activation_id: 1,
        schedule: BasalSchedule::flat(MilliUnitsPerHour(0)),
        temp: None,
    };
    assert_eq!(p.activate(&a), Err(Error::NotDocked));
}

// ---- wear timer -----------------------------------------------------------------------------
#[test]
fn wear_warning_at_44h_stop_and_alarm_at_52h() {
    let (mut p, h) = running(100_000, 0);
    advance_hours(&mut p, &h, 43);
    let s = status(&mut p);
    assert_eq!(s.flags & st::WEAR_WARNING, 0);
    assert_eq!(s.wear_s, 43 * 3600);
    advance_hours(&mut p, &h, 1); // 44 h
    let s = status(&mut p);
    assert_ne!(s.flags & st::WEAR_WARNING, 0);
    assert_eq!(s.faults, 0);
    assert_eq!(s.delivery_state, DeliveryState::Active as u8);
    assert_eq!(log_count(&p, EventType::WearWarning), 1);
    advance_hours(&mut p, &h, 7); // 51 h: still delivering, warned only once
    assert_eq!(log_count(&p, EventType::WearWarning), 1);
    assert_eq!(status(&mut p).delivery_state, DeliveryState::Active as u8);
    assert_eq!(status(&mut p).faults, 0);
    advance_hours(&mut p, &h, 1); // 52 h
    let s = status(&mut p);
    assert_ne!(s.faults & Faults::WEAR_EXPIRED.bits(), 0);
    assert_eq!(s.delivery_state, DeliveryState::StoppedWear as u8);
    assert_ne!(s.flags & st::ALARM, 0);
    assert_ne!(s.flags & st::SUSPENDED, 0);
    assert_eq!(h.st().buzzer, Buzzer::Alarm);
    assert_eq!(log_count(&p, EventType::WearExpired), 1);
}

#[test]
fn wear_expired_pod_delivers_nothing_and_cannot_be_resumed_or_acknowledged() {
    let (mut p, h) = running(100_000, 3000);
    advance_hours(&mut p, &h, 52);
    let steps = total_steps(&h);
    run_secs(&mut p, &h, 3600);
    assert_eq!(total_steps(&h), steps);
    assert_eq!(p.resume(), Err(Error::Fault));
    assert_eq!(p.bolus(MilliUnits(50)), Err(Error::Fault));
    assert_eq!(p.acknowledge(Faults(0xFFFF)), Err(Error::Persists));
    assert_ne!(status(&mut p).faults & Faults::WEAR_EXPIRED.bits(), 0);
}

#[test]
fn wear_counts_a_stalled_loop_in_full() {
    let (mut p, h) = running(100_000, 0);
    h.advance_ms(52 * HOUR_MS); // one single tick after a 52 h stall
    p.tick();
    assert_ne!(status(&mut p).faults & Faults::WEAR_EXPIRED.bits(), 0);
}

#[test]
fn wear_timer_restarts_with_a_new_activation_and_is_frozen_while_released() {
    let (mut p, h) = running(100_000, 0);
    advance_hours(&mut p, &h, 52);
    assert!(p.release(TEST_PAIR).is_ok());
    let frozen = status(&mut p).wear_s;
    advance_hours(&mut p, &h, 10);
    assert_eq!(status(&mut p).wear_s, frozen);
    assert_eq!(p.activate(&act_args(2)), Ok(()));
    let s = status(&mut p);
    assert_eq!(s.wear_s, 0);
    assert_eq!(s.faults & Faults::WEAR_EXPIRED.bits(), 0);
    assert_eq!(s.flags & st::WEAR_WARNING, 0);
    assert_eq!(p.resume(), Ok(()));
    run_secs(&mut p, &h, 3600);
    assert!(total_steps(&h) > 0);
}

// ---- pairing --------------------------------------------------------------------------------
#[test]
fn pairing_validation() {
    let (mut p, _h) = new_pump();
    assert_eq!(p.set_pairing(0, ROLE_A), Err(Error::BadArg));
    assert_eq!(p.set_pairing(5, 0), Err(Error::BadArg)); // OP_ROLE_NONE
    assert_eq!(p.set_pairing(5, 3), Err(Error::BadArg));
    assert_eq!(p.set_pairing(5, ROLE_B), Ok(()));
    let s = status(&mut p);
    assert_eq!(s.pair_id, 5);
    assert_eq!(s.role, ROLE_B);
    assert!(log_has(&p, EventType::Paired));
}

#[test]
fn pairing_refused_while_active() {
    let (mut p, _h) = running(100_000, 0);
    assert_eq!(p.set_pairing(77, ROLE_B), Err(Error::AlreadyActive));
    assert_eq!(status(&mut p).pair_id, TEST_PAIR);
}

// ---- Activate -------------------------------------------------------------------------------
#[test]
fn activate_refuses_unpaired_and_wrong_pair() {
    let (mut p, _h) = new_pump();
    let _ = p.fill(MilliUnits(100_000));
    let mut a = act_args(1);
    assert_eq!(p.activate(&a), Err(Error::Pair)); // not paired
    let _ = p.set_pairing(TEST_PAIR, ROLE_A);
    a.pair_id = TEST_PAIR + 1;
    assert_eq!(p.activate(&a), Err(Error::Pair));
    assert!(!p.pod().active);
}

#[test]
fn activate_refuses_when_not_docked() {
    let (mut p, h) = ready();
    set_docked(&h, false);
    let a = act_args(1);
    assert_eq!(p.activate(&a), Err(Error::NotDocked));
    assert!(!p.pod().active);
    assert_eq!(status(&mut p).delivery_state, DeliveryState::Released as u8);
    set_docked(&h, true);
    assert_eq!(p.activate(&a), Ok(()));
}

#[test]
fn activate_refuses_unfilled_charging_and_faulted_pods() {
    let (mut p, h) = new_pump();
    let _ = p.set_pairing(TEST_PAIR, ROLE_A);
    let a = act_args(1);
    assert_eq!(p.activate(&a), Err(Error::Reservoir));
    let _ = p.fill(MilliUnits(100_000));
    h.st().charger = true;
    assert_eq!(p.activate(&a), Err(Error::Charging));
    h.st().charger = false;
    h.st().battery_mv = 3000; // critical battery
    run_secs(&mut p, &h, 2);
    assert_eq!(p.activate(&a), Err(Error::Fault));
    assert!(!p.pod().active);
}

#[test]
fn activate_is_all_or_nothing() {
    let (mut p, _h) = ready();
    let mut a = act_args(1);
    a.schedule = BasalSchedule::flat(MilliUnitsPerHour(5050)); // above the configured max basal
    assert_eq!(p.activate(&a), Err(Error::Limit));
    assert!(!p.pod().active);
    assert!(!p.engine().has_schedule());
    a = act_args(1);
    a.temp = Some((MilliUnitsPerHour(1000), Minutes(20))); // not a multiple of 30
    assert_eq!(p.activate(&a), Err(Error::BadArg));
    a.temp = Some((MilliUnitsPerHour(9000), Minutes(30))); // above max basal
    assert_eq!(p.activate(&a), Err(Error::Limit));
    a = act_args(0); // activation id 0 is reserved
    assert_eq!(p.activate(&a), Err(Error::BadArg));
    assert!(!p.pod().active);
    assert!(!p.engine().has_schedule());
    assert!(!log_has(&p, EventType::Activate));
}

#[test]
fn activate_carries_schedule_and_leaves_delivery_suspended_until_resume() {
    let (mut p, h) = ready();
    let mut a = act_args(7);
    a.schedule = BasalSchedule::from_pairs(&[(0, 1000), (4, 2000)]).unwrap();
    a.temp = Some((MilliUnitsPerHour(2500), Minutes(90)));
    assert_eq!(p.activate(&a), Ok(()));
    let s = status(&mut p);
    assert_eq!(s.delivery_state, DeliveryState::Active as u8);
    assert_ne!(s.flags & st::ACTIVE, 0);
    assert_ne!(s.flags & st::SUSPENDED, 0);
    assert_ne!(s.flags & st::HAS_SCHEDULE, 0);
    assert_eq!(s.wear_s, 0);
    run_secs(&mut p, &h, 120);
    assert_eq!(total_steps(&h), 0); // nothing before Resume
    assert_eq!(p.prime(Pulses(10)), Ok(())); // connector prime works while suspended
    assert_eq!(total_steps(&h), 10);
    assert_eq!(p.resume(), Ok(()));
    let s = status(&mut p);
    assert_ne!(s.flags & st::TEMP_ACTIVE, 0);
    assert_eq!(s.temp_rate_mu_h, 2500);
    assert_eq!(s.temp_remaining_min, 90);
    assert_eq!(s.current_rate_mu_h, 2500);
    assert!(log_has(&p, EventType::Activate));
    run_secs(&mut p, &h, 1800);
    assert!(total_steps(&h) > 10 + 40); // 2.5 U/h for 30 min = 47 steps
}

#[test]
fn activate_is_idempotent_for_the_same_activation_id() {
    let (mut p, h) = ready();
    let a = act_args(7);
    assert_eq!(p.activate(&a), Ok(()));
    assert_eq!(p.resume(), Ok(()));
    run_secs(&mut p, &h, 600);
    let steps = total_steps(&h);
    assert_eq!(p.activate(&a), Ok(())); // lost response, app retries
    assert_eq!(log_count(&p, EventType::Activate), 1);
    assert_eq!(status(&mut p).flags & st::SUSPENDED, 0); // untouched: still delivering
    run_secs(&mut p, &h, 60);
    assert!(total_steps(&h) >= steps);
    let b = act_args(8);
    assert_eq!(p.activate(&b), Err(Error::AlreadyActive));
}

// ---- Release --------------------------------------------------------------------------------
#[test]
fn release_stops_delivery_reports_totals_and_is_idempotent() {
    let (mut p, h) = running(100_000, 0);
    assert_eq!(p.bolus(MilliUnits(2000)), Ok(()));
    run_secs(&mut p, &h, 90);
    assert_eq!(p.release(TEST_PAIR), Ok(MilliUnits(1983))); // 76 steps * 26.1 mU
    let s = status(&mut p);
    assert_eq!(s.delivery_state, DeliveryState::Released as u8);
    assert_eq!(s.flags & st::ACTIVE, 0);
    assert_ne!(s.flags & st::SUSPENDED, 0);
    assert_eq!(s.delivered_mu, 1983);
    assert_eq!(s.reservoir_mu, 98016); // 100000 - 1983.6
    assert!(!h.st().enabled);
    let steps = total_steps(&h);
    run_secs(&mut p, &h, 3600);
    assert_eq!(total_steps(&h), steps);
    assert_eq!(p.release(TEST_PAIR), Ok(MilliUnits(1983))); // retry after BLE loss
    assert_eq!(log_count(&p, EventType::Release), 1);
    assert_eq!(p.release(TEST_PAIR + 1), Err(Error::Pair));
}

#[test]
fn release_works_while_undocked_and_cancels_bolus_and_temp() {
    let (mut p, h) = running(100_000, 1000);
    assert_eq!(p.set_temp_basal(MilliUnitsPerHour(2000), Minutes(60)), Ok(()));
    assert_eq!(p.bolus(MilliUnits(1000)), Ok(()));
    set_docked(&h, false);
    assert!(p.release(TEST_PAIR).is_ok());
    assert!(!p.engine().bolus_active());
    assert!(!p.engine().temp_active());
}

#[test]
fn released_pod_refuses_every_delivery_command() {
    let (mut p, h) = running(100_000, 1000);
    assert!(p.release(TEST_PAIR).is_ok());
    let s = BasalSchedule::flat(MilliUnitsPerHour(1000));
    assert_eq!(p.set_schedule(&s), Err(Error::Released));
    assert_eq!(p.set_temp_basal(MilliUnitsPerHour(1000), Minutes(30)), Err(Error::Released));
    assert_eq!(p.bolus(MilliUnits(50)), Err(Error::Released));
    assert_eq!(p.resume(), Err(Error::Released));
    assert_eq!(p.prime(Pulses(5)), Err(Error::Released));
    run_secs(&mut p, &h, 3600);
    let steps = total_steps(&h);
    run_secs(&mut p, &h, 3600);
    assert_eq!(total_steps(&h), steps);
    // the spare can still be filled (it is refilled while parked on the charger)
    assert_eq!(p.fill(MilliUnits(90_000)), Ok(()));
}

// ---- charger --------------------------------------------------------------------------------
#[test]
fn charger_forces_release() {
    let (mut p, h) = running(100_000, 3000);
    run_secs(&mut p, &h, 120);
    h.st().charger = true;
    run_secs(&mut p, &h, 1);
    let s = status(&mut p);
    assert_eq!(s.delivery_state, DeliveryState::Released as u8);
    assert_eq!(s.flags & st::ACTIVE, 0);
    assert!(log_has(&p, EventType::Release));
    let steps = total_steps(&h);
    h.st().charger = false;
    run_secs(&mut p, &h, 600);
    assert_eq!(total_steps(&h), steps); // leaving the charger does NOT re-activate
    assert_eq!(p.resume(), Err(Error::Released));
}

// ---- persistence hook -----------------------------------------------------------------------
#[test]
fn restore_active_pod_comes_up_suspended_with_wear_and_pairing() {
    let (mut p, _h) = new_pump();
    p.restore_pod(TEST_PAIR, ROLE_B, true, 42, Millis(45 * HOUR_MS));
    let s = status(&mut p);
    assert_eq!(s.pair_id, TEST_PAIR);
    assert_eq!(s.role, ROLE_B);
    assert_ne!(s.flags & st::ACTIVE, 0);
    assert_ne!(s.flags & st::SUSPENDED, 0);
    assert_ne!(s.flags & st::WEAR_WARNING, 0);
    assert_eq!(s.wear_s, 45 * 3600);
}

#[test]
fn restore_beyond_wear_limit_latches_the_fault_at_boot() {
    let (mut p, _h) = new_pump();
    p.restore_pod(TEST_PAIR, ROLE_A, true, 42, Millis(53 * HOUR_MS));
    assert_ne!(status(&mut p).faults & Faults::WEAR_EXPIRED.bits(), 0);
    assert_eq!(status(&mut p).delivery_state, DeliveryState::StoppedWear as u8);
}

// ---- two pods, one pair: only one delivers --------------------------------------------------
#[test]
fn two_pods_only_the_activated_one_delivers() {
    let (mut a, ha) = new_pump();
    let (mut b, hb) = new_pump();
    let _ = a.fill(MilliUnits(100_000));
    let _ = b.fill(MilliUnits(100_000));
    assert_eq!(a.set_pairing(TEST_PAIR, ROLE_A), Ok(()));
    assert_eq!(b.set_pairing(TEST_PAIR, ROLE_B), Ok(()));
    let act = act_args(1);
    assert_eq!(a.activate(&act), Ok(()));
    assert_eq!(a.resume(), Ok(()));
    set_docked(&hb, false); // B sits on the charger, not on the cannula
    assert_eq!(b.activate(&act), Err(Error::NotDocked));
    for _ in 0..600 {
        ha.advance_ms(1000);
        hb.advance_ms(1000);
        a.tick();
        b.tick();
    }
    assert!(total_steps(&ha) > 0);
    assert_eq!(total_steps(&hb), 0);
    // handover: A released, B docked and activated
    assert!(a.release(TEST_PAIR).is_ok());
    set_docked(&hb, true);
    let act = act_args(2);
    assert_eq!(b.activate(&act), Ok(()));
    assert_eq!(b.resume(), Ok(()));
    let a_steps = total_steps(&ha);
    for _ in 0..600 {
        ha.advance_ms(1000);
        hb.advance_ms(1000);
        a.tick();
        b.tick();
    }
    assert_eq!(total_steps(&ha), a_steps);
    assert!(total_steps(&hb) > 0);
}

// ---- wire format ----------------------------------------------------------------------------
fn roundtrip_cmd(c: &Command) -> Command {
    let mut buf = [0u8; 200];
    let n = openpatch_proto::encode_command_payload(c, &mut buf).unwrap();
    assert!(n > 0);
    openpatch_proto::decode_command(c.body.type_id(), 3, &buf[..n]).unwrap()
}

fn segs(pairs: &[(u8, u16)]) -> openpatch_proto::BasalSegs {
    let mut v = openpatch_proto::BasalSegs::new();
    for &(start_slot, rate_mu_h) in pairs {
        v.push(openpatch_proto::BasalSeg { start_slot, rate_mu_h }).unwrap();
    }
    v
}

#[test]
fn wire_pairing_activate_release_roundtrip() {
    let c = Command::new(0, CommandBody::SetPairing { pair_id: 0x1122_3344, role: ROLE_B });
    match roundtrip_cmd(&c).body {
        CommandBody::SetPairing { pair_id, role } => {
            assert_eq!(pair_id, 0x1122_3344);
            assert_eq!(role, ROLE_B);
        }
        other => panic!("{other:?}"),
    }

    let c = Command::new(0, CommandBody::Release { pair_id: 0x5566_7788 });
    match roundtrip_cmd(&c).body {
        CommandBody::Release { pair_id } => assert_eq!(pair_id, 0x5566_7788),
        other => panic!("{other:?}"),
    }

    let mut body = CommandBody::Activate {
        pair_id: 9,
        activation_id: 77,
        schedule: segs(&[(0, 800), (30, 1200)]),
        temp: Some((2100, 150)),
    };
    match roundtrip_cmd(&Command::new(0, body.clone())).body {
        CommandBody::Activate { pair_id, activation_id, schedule, temp } => {
            assert_eq!(pair_id, 9);
            assert_eq!(activation_id, 77);
            assert_eq!(schedule.len(), 2);
            assert_eq!(schedule[1].rate_mu_h, 1200);
            assert_eq!(temp, Some((2100, 150)));
        }
        other => panic!("{other:?}"),
    }
    if let CommandBody::Activate { temp, .. } = &mut body {
        *temp = None;
    }
    match roundtrip_cmd(&Command::new(0, body)).body {
        CommandBody::Activate { temp, .. } => assert_eq!(temp, None),
        other => panic!("{other:?}"),
    }
}

#[test]
fn wire_malformed_pairing_activate_release_are_rejected() {
    assert!(openpatch_proto::decode_command(cmd::SET_PAIRING, 1, &[]).is_err());
    assert!(openpatch_proto::decode_command(cmd::RELEASE, 1, &[]).is_err());
    assert!(openpatch_proto::decode_command(cmd::ACTIVATE, 1, &[]).is_err());
    // Activate without a schedule
    let p = [tag::PAIR_ID, 4, 1, 0, 0, 0, tag::ACTIVATION_ID, 4, 1, 0, 0, 0];
    assert!(openpatch_proto::decode_command(cmd::ACTIVATE, 1, &p).is_err());
    // temp rate without duration
    let q = [
        tag::PAIR_ID, 4, 1, 0, 0, 0, tag::ACTIVATION_ID, 4, 1, 0, 0, 0, tag::BASAL_SEG, 3, 0,
        0x10, 0x00, tag::RATE_MU_H, 2, 0xE8, 0x03,
    ];
    assert!(openpatch_proto::decode_command(cmd::ACTIVATE, 1, &q).is_err());
}

#[test]
fn protocol_release_response_carries_totals_and_status() {
    let (mut p, h) = running(100_000, 0);
    assert_eq!(p.bolus(MilliUnits(1000)), Ok(()));
    run_secs(&mut p, &h, 60);
    let c = Command::new(5, CommandBody::Release { pair_id: TEST_PAIR });
    let rsp = p.execute(&c);
    assert_eq!(rsp.result, 0);
    assert!(rsp.status.is_some());
    assert_eq!(rsp.act_delivered_mu, Some(991));
    let mut buf = [0u8; 200];
    let n = openpatch_proto::encode_response_payload(&rsp, &mut buf).unwrap();
    assert!(n > 0);
    let d = openpatch_proto::decode_response(cmd::RELEASE, 5, &buf[..n]).unwrap();
    assert_eq!(d.act_delivered_mu, Some(991));
    let s = d.status.unwrap();
    assert_eq!(s.delivery_state, DeliveryState::Released as u8);
    assert_eq!(s.reservoir_mu, 99008);
    assert_eq!(s.delivered_mu, 991);
    assert_eq!(s.pair_id, TEST_PAIR);
    assert_eq!(s.role, ROLE_A);
}

#[test]
fn protocol_status_reports_docked_role_and_wear() {
    let (mut p, h) = running(100_000, 0);
    advance_hours(&mut p, &h, 2);
    let rsp = p.execute(&Command::new(0, CommandBody::GetStatus));
    let mut buf = [0u8; 220];
    let n = openpatch_proto::encode_response_payload(&rsp, &mut buf).unwrap();
    assert!(n > 0);
    let d = openpatch_proto::decode_response(cmd::GET_STATUS, 0, &buf[..n]).unwrap();
    let s = d.status.unwrap();
    assert_ne!(s.flags & st::DOCKED, 0);
    assert_ne!(s.flags & st::ACTIVE, 0);
    assert_eq!(s.role, ROLE_A);
    assert_eq!(s.pair_id, TEST_PAIR);
    assert_eq!(s.wear_s, 2 * 3600);
    assert_eq!(s.delivery_state, DeliveryState::Active as u8);
}
