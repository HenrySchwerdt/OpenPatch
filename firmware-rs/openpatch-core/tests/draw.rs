//! Draw mode (automatic refill): `Pump::fill_draw` / protocol command 0x0F `FillDraw`.
//! Gates, chunked execution, step-exact volume, stalls, aborts, mandatory priming, notifications.
mod common;
use common::*;
use openpatch_core::drive_cal::{self, PRESETS};
use openpatch_core::limits::*;
use openpatch_core::log::{Event, LOG_CAPACITY};
use openpatch_core::*;
use openpatch_proto::tlv::TlvReader;
use openpatch_proto::{
    self as proto, draw as ds, notify, st, Ccm, CcmError, Command, CommandBody, NoCrypto, Session, CCM_NONCE_LEN,
    CCM_TAG_LEN, FLAG_ENCRYPTED, FLAG_RESPONSE, FRAME_HEADER, FRAME_MAX,
};

// ---- fixtures ---------------------------------------------------------------------------------

/// Fresh RELAXED test pump (suspended, never activated), optionally pre-filled, taken off the
/// cannula adapter: ready to draw.
fn undocked(fill_mu: u32) -> (Pump<MockHal>, MockHal) {
    let (mut p, h) = new_pump();
    if fill_mu > 0 {
        p.fill(MilliUnits(fill_mu)).unwrap();
    }
    h.st().docked = false;
    (p, h)
}

/// Active, resumed pump that was then suspended and undocked (the real refill situation).
fn active_undocked(fill_mu: u32) -> (Pump<MockHal>, MockHal) {
    let (mut p, h) = running(fill_mu, 1000);
    p.suspend().unwrap();
    h.st().docked = false;
    (p, h)
}

fn events(p: &Pump<MockHal>) -> Vec<Event> {
    let mut e = [Event::default(); LOG_CAPACITY];
    let n = p.log().read(0, &mut e);
    e[..n].to_vec()
}

fn find_ev(p: &Pump<MockHal>, k: EventType) -> Option<Event> {
    events(p).into_iter().find(|e| e.kind == k as u8)
}

fn count_ev(p: &Pump<MockHal>, k: EventType) -> usize {
    events(p).iter().filter(|e| e.kind == k as u8).count()
}

fn mu_of(p: &Pump<MockHal>, steps: u32) -> u32 {
    p.pulse_cal().pulses_to_mu(Pulses(steps)).0
}

fn steps_of(p: &Pump<MockHal>, mu: u32) -> u32 {
    p.pulse_cal().mu_to_pulses(MilliUnits(mu)).0
}

fn double_beeps(h: &MockHal) -> usize {
    h.st().buzzer_history.iter().filter(|b| **b == Buzzer::DoubleBeep).count()
}

fn reverse_calls(h: &MockHal) -> Vec<u32> {
    h.st().reverse_calls.clone()
}

fn drain(p: &mut Pump<MockHal>) -> Vec<Notification> {
    let mut v = Vec::new();
    while let Some(n) = p.take_notification() {
        v.push(n);
    }
    v
}

// ---- gates -------------------------------------------------------------------------------------

#[test]
fn docked_pod_never_draws() {
    let (mut p, h) = new_pump();
    p.fill(MilliUnits(10_000)).unwrap();
    assert!(h.st().docked);
    assert_eq!(p.fill_draw(MilliUnits(1_000)), Err(Error::Docked));
    assert_eq!(Error::Docked.code(), 27);
    assert_eq!(p.draw_state(), ds::IDLE);
    run_secs(&mut p, &h, 5);
    assert_eq!(h.st().total_reverse_steps, 0);
}

#[test]
fn delivering_pod_refuses_with_not_suspended_before_anything_else() {
    let (mut p, h) = running(50_000, 1000);
    assert_eq!(p.fill_draw(MilliUnits(1_000)), Err(Error::NotSuspended), "docked and delivering");
    h.st().docked = false;
    assert_eq!(p.fill_draw(MilliUnits(1_000)), Err(Error::NotSuspended), "undocked but not suspended");
    assert_eq!(p.draw_state(), ds::IDLE);
}

#[test]
fn latched_fault_refuses_with_fault() {
    let (mut p, h) = undocked(10_000);
    p.supervisor_mut().latch(Faults::OCCLUSION);
    assert_eq!(p.fill_draw(MilliUnits(1_000)), Err(Error::Fault));
    assert_eq!(p.draw_state(), ds::IDLE);
    assert_eq!(h.st().total_reverse_steps, 0);
    // acknowledged: allowed again
    p.acknowledge(Faults::OCCLUSION).unwrap();
    assert_eq!(p.fill_draw(MilliUnits(1_000)), Ok(()));
}

#[test]
fn second_start_while_running_is_busy_and_keeps_the_first_job() {
    let (mut p, h) = undocked(10_000);
    p.fill_draw(MilliUnits(40_000)).unwrap();
    assert_eq!(p.fill_draw(MilliUnits(1_000)), Err(Error::Busy));
    run_draw(&mut p, &h);
    assert_eq!(p.get_status().draw_requested_mu, 40_000, "the first job was not replaced");
    assert_eq!(count_ev(&p, EventType::DrawStart), 1);
}

#[test]
fn amount_zero_cancels_a_running_draw_and_is_not_found_when_idle() {
    let (mut p, h) = undocked(10_000);
    assert_eq!(p.fill_draw(MilliUnits(0)), Err(Error::NotFound));
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_secs(&mut p, &h, 1);
    assert_eq!(p.fill_draw(MilliUnits(0)), Ok(()));
    assert_eq!(p.draw_state(), ds::ABORTED);
    assert!(!p.draw_running());
    assert_eq!(p.fill_draw(MilliUnits(0)), Err(Error::NotFound), "nothing running any more");
}

#[test]
fn amount_above_the_room_is_a_limit_error_exactly_at_the_room_it_is_fine() {
    let (mut p, _h) = undocked(95_000);
    assert_eq!(p.fill_draw(MilliUnits(5_001)), Err(Error::Limit));
    assert_eq!(p.fill_draw(MilliUnits(200_000)), Err(Error::Limit));
    assert_eq!(p.draw_state(), ds::IDLE);
    assert_eq!(p.fill_draw(MilliUnits(5_000)), Ok(()));
    // an empty reservoir has the whole capacity as room
    let (mut p, _h) = undocked(0);
    assert_eq!(p.fill_draw(MilliUnits(100_001)), Err(Error::Limit));
    assert_eq!(p.fill_draw(MilliUnits(100_000)), Ok(()));
}

#[test]
fn amount_below_one_step_is_bad_arg() {
    let (mut p, _h) = undocked(10_000);
    // one step = 26.1 mU
    assert_eq!(p.fill_draw(MilliUnits(1)), Err(Error::BadArg));
    assert_eq!(p.fill_draw(MilliUnits(26)), Err(Error::BadArg));
    assert_eq!(p.draw_state(), ds::IDLE);
    assert_eq!(p.fill_draw(MilliUnits(27)), Ok(()));
    assert_eq!(p.get_status().draw_requested_mu, 27);
}

#[test]
fn missing_angle_sensor_refuses_to_start() {
    let (mut p, h) = undocked(10_000);
    h.st().angle_missing = true;
    assert_eq!(p.fill_draw(MilliUnits(1_000)), Err(Error::Fault));
    assert_eq!(p.draw_state(), ds::IDLE);
    run_secs(&mut p, &h, 3);
    assert_eq!(h.st().total_reverse_steps, 0);
}

#[test]
fn a_refused_start_leaves_no_trace() {
    let (mut p, h) = new_pump();
    assert_eq!(p.fill_draw(MilliUnits(1_000)), Err(Error::Docked));
    assert_eq!(count_ev(&p, EventType::DrawStart), 0);
    assert!(drain(&mut p).is_empty());
    assert!(reverse_calls(&h).is_empty());
    let s = p.get_status();
    assert_eq!((s.draw_state, s.draw_requested_mu, s.draw_done_mu), (0, 0, 0));
    assert!(s.flags & st::DRAWING == 0);
}

#[test]
fn protocol_command_reports_every_gate() {
    let (mut p, h) = new_pump();
    p.fill(MilliUnits(95_000)).unwrap();
    let cmd = |mu: u32| Command::new(0, CommandBody::FillDraw { amount_mu: mu });
    assert_eq!(proto::cmd::FILL_DRAW, 0x0F);
    assert_eq!(p.execute(&cmd(1_000)).result, Error::Docked.code());
    h.st().docked = false;
    assert_eq!(p.execute(&cmd(0)).result, Error::NotFound.code());
    assert_eq!(p.execute(&cmd(5_001)).result, Error::Limit.code());
    assert_eq!(p.execute(&cmd(10)).result, Error::BadArg.code());
    h.st().angle_missing = true;
    assert_eq!(p.execute(&cmd(1_000)).result, Error::Fault.code());
    h.st().angle_missing = false;
    let ok = p.execute(&cmd(2_000));
    assert_eq!(ok.result, 0);
    assert_eq!(ok.type_, proto::cmd::FILL_DRAW);
    assert_eq!(p.execute(&cmd(1_000)).result, Error::Busy.code());
    assert_eq!(p.execute(&cmd(0)).result, 0, "cancel");
    assert_eq!(p.draw_state(), ds::ABORTED);
}

#[test]
fn protocol_not_suspended() {
    let (mut p, _h) = running(50_000, 1000);
    let rsp = p.execute(&Command::new(0, CommandBody::FillDraw { amount_mu: 1_000 }));
    assert_eq!(rsp.result, Error::NotSuspended.code());
}

// ---- chunked execution -------------------------------------------------------------------------

#[test]
fn draw_runs_in_chunks_of_500_steps_one_per_tick() {
    let (mut p, h) = undocked(0);
    p.fill_draw(MilliUnits(40_000)).unwrap(); // 1532 steps
    let total = steps_of(&p, 40_000);
    assert_eq!(total, 1532);
    assert!(reverse_calls(&h).is_empty(), "starting does not move the motor");
    assert_eq!(h.st().total_reverse_steps, 0);
    let mut expected = Vec::new();
    for want in [500u32, 500, 500, 32] {
        expected.push(want);
        run_secs(&mut p, &h, 1);
        assert_eq!(reverse_calls(&h), expected);
        assert!(!h.st().enabled, "motor off between chunks");
    }
    assert_eq!(DRAW_CHUNK_STEPS, 500);
    assert!(DRAW_CHUNK_STEPS <= DRAW_MAX_PPS, "500 steps per tick never exceed 1000 pps");
    assert_eq!(p.draw_state(), ds::DONE);
    run_secs(&mut p, &h, 5);
    assert_eq!(reverse_calls(&h), expected, "no more calls after DONE");
    assert_eq!(h.st().total_reverse_steps, total);
    assert_eq!(h.st().total_steps, 0, "never a forward step");
    assert!(!h.st().stepped_while_disabled);
}

#[test]
fn every_chunk_is_at_most_500_steps_for_any_size() {
    for amount in [27u32, 13_050, 13_051, 99_999] {
        let (mut p, h) = undocked(0);
        p.fill_draw(MilliUnits(amount)).unwrap();
        run_draw(&mut p, &h);
        let calls = reverse_calls(&h);
        assert!(calls.iter().all(|c| *c >= 1 && *c <= DRAW_CHUNK_STEPS), "{calls:?}");
        assert_eq!(calls.iter().sum::<u32>(), steps_of(&p, amount));
        assert_eq!(calls.len() as u32, steps_of(&p, amount).div_ceil(500));
    }
}

// ---- exact volume ------------------------------------------------------------------------------

/// Counts per step that make the angle sensor confirm every step of any preset (rounded up).
fn counts_for(turn_x100: u32) -> i64 {
    (409_600 + turn_x100 as i64 - 1) / turn_x100 as i64
}

#[test]
fn drawn_volume_is_exactly_steps_times_uu_floor_for_every_preset() {
    for preset in PRESETS {
        for amount in [7_777u32, 33_333, 60_000] {
            let hal = MockHal::new();
            hal.st().counts_per_step = counts_for(preset.cal().turn_x100);
            hal.st().docked = false;
            let cal = DriveCal::from_preset(preset);
            let mut p = Pump::new(hal.clone(), Some(&cal), CAPACITY_100, 1);
            p.set_config(PumpConfig::RELAXED);
            let pc = p.pulse_cal();
            let steps = pc.mu_to_pulses(MilliUnits(amount)).0;
            let want = (steps as u64 * preset.uu_num as u64 / (preset.uu_den as u64 * 1000)) as u32;
            p.fill_draw(MilliUnits(amount)).unwrap();
            run_draw(&mut p, &hal);
            let id = preset.id as u16;
            assert_eq!(p.draw_state(), ds::DONE, "{id:#x} {amount}");
            assert_eq!(p.draw_drawn().0, want, "{id:#x} {amount}");
            assert_eq!(p.get_status().draw_done_mu, want);
            assert_eq!(hal.st().total_reverse_steps, steps);
            assert!(want <= amount && amount - want <= preset_step_mu_ceil(preset), "{id:#x}");
            assert_eq!(p.reservoir().remaining().0, want, "level raised by exactly the drawn steps");
        }
    }
}

fn preset_step_mu_ceil(p: &drive_cal::Preset) -> u32 {
    (p.uu_num as u64).div_ceil(p.uu_den as u64 * 1000) as u32
}

#[test]
fn drawn_never_exceeds_requested_and_is_within_one_step() {
    for amount in [27u32, 100, 5_000, 12_345, 50_000] {
        let (mut p, h) = undocked(0);
        p.fill_draw(MilliUnits(amount)).unwrap();
        run_draw(&mut p, &h);
        let d = p.draw_drawn().0;
        assert!(d <= amount);
        assert!(amount - d < 27, "{amount} -> {d}");
        assert_eq!(d, mu_of(&p, steps_of(&p, amount)));
    }
}

#[test]
fn level_is_existing_plus_drawn_and_unfilled_pumps_become_filled() {
    let (mut p, h) = undocked(20_000);
    p.fill_draw(MilliUnits(10_000)).unwrap();
    run_draw(&mut p, &h);
    let drawn = p.draw_drawn().0;
    assert_eq!(drawn, mu_of(&p, 383));
    assert_eq!(p.reservoir().remaining().0, 20_000 + drawn);
    assert_eq!(p.reservoir().fill_level().0, 20_000 + drawn);
    assert_eq!(p.get_status().reservoir_mu, 20_000 + drawn);

    let (mut p, h) = undocked(0);
    assert!(!p.reservoir().is_filled());
    p.fill_draw(MilliUnits(10_000)).unwrap();
    run_draw(&mut p, &h);
    assert!(p.reservoir().is_filled());
    assert_eq!(p.reservoir().remaining().0, p.draw_drawn().0);
}

#[test]
fn level_never_exceeds_capacity() {
    let (mut p, h) = undocked(99_000);
    p.fill_draw(MilliUnits(1_000)).unwrap();
    run_draw(&mut p, &h);
    assert!(p.reservoir().remaining() <= p.reservoir().capacity());
    // the clamp itself (a draw larger than the room, e.g. a mis-measured chunk)
    p.reservoir_mut().draw_in(Pulses(1_000_000));
    assert_eq!(p.reservoir().remaining(), CAPACITY_100);
    assert_eq!(p.reservoir().fill_level(), CAPACITY_100);
}

#[test]
fn consumed_counter_shrinks_first_then_the_level_rises() {
    let (mut p, h) = running(50_000, 1000);
    p.bolus(MilliUnits(1_000)).unwrap();
    run_secs(&mut p, &h, 60);
    let consumed = p.reservoir().consumed().0;
    assert_eq!(consumed, p.engine().delivered_steps().0);
    assert!(consumed > 30);
    p.suspend().unwrap();
    h.st().docked = false;

    // 10 steps < consumed: only the consumed counter moves
    p.fill_draw(MilliUnits(280)).unwrap();
    run_draw(&mut p, &h);
    assert_eq!(p.draw_state(), ds::DONE);
    assert_eq!(p.reservoir().consumed().0, consumed - 10);
    assert_eq!(p.reservoir().fill_level().0, 50_000);
    let used_uu = (consumed - 10) as u64 * 26_100;
    assert_eq!(p.reservoir().remaining().0 as u64, (50_000_000 - used_uu) / 1000);

    // 76 steps > the remaining consumed: counter to zero, the excess raises the level
    let c = p.reservoir().consumed().0;
    p.fill_draw(MilliUnits(2_000)).unwrap();
    run_draw(&mut p, &h);
    assert_eq!(p.reservoir().consumed().0, 0);
    let extra = 76 - c;
    assert_eq!(p.reservoir().fill_level().0, 50_000 + mu_of(&p, extra));
    assert_eq!(p.reservoir().remaining(), p.reservoir().fill_level());
}

// ---- completion bookkeeping --------------------------------------------------------------------

#[test]
fn completed_draw_events_notifications_beep_and_status() {
    let (mut p, h) = undocked(0);
    p.fill_draw(MilliUnits(40_000)).unwrap();
    let start = find_ev(&p, EventType::DrawStart).unwrap();
    assert_eq!((start.a, start.b), (40_000, 1532));
    assert!(p.get_status().flags & st::DRAWING != 0);
    assert_eq!(p.get_status().draw_state, ds::DRAWING);
    run_draw(&mut p, &h);
    let total = mu_of(&p, 1532);
    assert_eq!(
        drain(&mut p),
        vec![
            Notification::DrawProgress(mu_of(&p, 500)),
            Notification::DrawProgress(mu_of(&p, 1000)),
            Notification::DrawProgress(mu_of(&p, 1500)),
            Notification::DrawDone(total),
        ]
    );
    let done = find_ev(&p, EventType::DrawDone).unwrap();
    assert_eq!((done.a, done.b), (total as i32, 40_000));
    assert_eq!(count_ev(&p, EventType::DrawStall), 0);
    assert_eq!(double_beeps(&h), 1);
    let s = p.get_status();
    assert_eq!((s.draw_state, s.draw_requested_mu, s.draw_done_mu), (ds::DONE, 40_000, total));
    assert!(s.flags & st::DRAWING == 0);
    assert!(p.supervisor().faults().is_empty());
}

#[test]
fn a_new_draw_after_a_finished_one_starts_a_fresh_job() {
    let (mut p, h) = undocked(0);
    p.fill_draw(MilliUnits(5_000)).unwrap();
    run_draw(&mut p, &h);
    let first = p.draw_drawn().0;
    p.fill_draw(MilliUnits(3_000)).unwrap();
    assert_eq!(p.get_status().draw_done_mu, 0, "counters restart");
    run_draw(&mut p, &h);
    assert_eq!(p.draw_drawn().0, mu_of(&p, steps_of(&p, 3_000)));
    assert_eq!(p.reservoir().remaining().0, first + p.draw_drawn().0);
}

// ---- stalls ------------------------------------------------------------------------------------

#[test]
fn short_chunk_is_a_stall_with_the_actual_drawn_volume() {
    let (mut p, h) = undocked(10_000);
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_secs(&mut p, &h, 1);
    h.st().reverse_limit = 100; // rear end-stop: the motor cannot move on
    run_secs(&mut p, &h, 1);
    assert_eq!(p.draw_state(), ds::STALLED);
    assert_eq!(reverse_calls(&h), vec![500, 100]);
    let drawn = mu_of(&p, 600);
    assert_eq!(p.draw_drawn().0, drawn);
    assert_eq!(p.reservoir().remaining().0, 10_000 + drawn);
    let ev = find_ev(&p, EventType::DrawStall).unwrap();
    assert_eq!((ev.a, ev.b), (drawn as i32, 40_000));
    assert_eq!(double_beeps(&h), 1);
    assert_eq!(drain(&mut p), vec![Notification::DrawProgress(mu_of(&p, 500)), Notification::DrawStalled(drawn)]);
    let s = p.get_status();
    assert_eq!((s.draw_state, s.draw_done_mu), (ds::STALLED, drawn));
    assert!(s.flags & st::DRAWING == 0);
    run_secs(&mut p, &h, 3);
    assert_eq!(reverse_calls(&h).len(), 2, "no retry after a stall");
    assert!(p.supervisor().faults().is_empty(), "an end-stop is not a fault");
}

#[test]
fn a_stall_with_zero_progress_books_nothing() {
    let (mut p, h) = undocked(10_000);
    h.st().reverse_limit = 0;
    p.fill_draw(MilliUnits(20_000)).unwrap();
    run_secs(&mut p, &h, 1);
    assert_eq!(p.draw_state(), ds::STALLED);
    assert_eq!(p.draw_drawn().0, 0);
    assert_eq!(p.reservoir().remaining().0, 10_000);
    assert!(!p.prime_required());
}

#[test]
fn angle_confirmed_volume_not_commanded_volume_is_booked() {
    // the motor "runs" but the leadscrew only turns 30 %: the angle sensor decides
    let (mut p, h) = undocked(10_000);
    h.st().reverse_pct = 30;
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_secs(&mut p, &h, 1);
    assert_eq!(p.draw_state(), ds::STALLED, "less than 50 % of the commanded travel");
    assert_eq!(h.st().total_reverse_steps, 500, "500 steps were commanded");
    let drawn = mu_of(&p, 150);
    assert_eq!(p.draw_drawn().0, drawn, "only 150 steps are confirmed by the angle");
    assert_eq!(p.reservoir().remaining().0, 10_000 + drawn);
    assert_eq!(drain(&mut p), vec![Notification::DrawStalled(drawn)]);
}

#[test]
fn partial_slip_above_half_continues_and_books_only_confirmed_steps() {
    let (mut p, h) = undocked(0);
    h.st().reverse_pct = 60;
    let amount = 39_150; // exactly 1500 steps
    assert_eq!(steps_of(&p, amount), 1500);
    p.fill_draw(MilliUnits(amount)).unwrap();
    run_draw(&mut p, &h);
    assert_eq!(p.draw_state(), ds::DONE);
    assert_eq!(h.st().total_reverse_steps, 1500);
    assert_eq!(p.draw_drawn().0, mu_of(&p, 900), "60 % of every chunk");
    assert!(p.draw_drawn().0 < amount);
    assert_eq!(p.reservoir().remaining().0, p.draw_drawn().0);
}

#[test]
fn three_chunks_of_high_current_are_a_stall() {
    let (mut p, h) = undocked(0);
    h.st().current_ma = Some(OCCLUSION_CURRENT_MA + 60);
    p.fill_draw(MilliUnits(90_000)).unwrap(); // 3448 steps = 7 chunks
    run_secs(&mut p, &h, 2);
    assert!(p.draw_running(), "two bursts are not enough");
    run_secs(&mut p, &h, 1);
    assert_eq!(p.draw_state(), ds::STALLED);
    assert_eq!(OCCLUSION_CURRENT_BURSTS, 3);
    assert_eq!(p.draw_drawn().0, mu_of(&p, 1500), "the three executed chunks are confirmed by the angle");
    assert!(matches!(drain(&mut p).last(), Some(Notification::DrawStalled(_))));
    assert_eq!(double_beeps(&h), 1);
}

#[test]
fn a_low_current_chunk_resets_the_stall_counter() {
    let (mut p, h) = undocked(0);
    p.fill_draw(MilliUnits(90_000)).unwrap();
    let hi = Some(OCCLUSION_CURRENT_MA + 1);
    let lo = Some(OCCLUSION_CURRENT_MA);
    for cur in [hi, hi, lo, hi, hi, lo, lo] {
        h.st().current_ma = cur;
        run_secs(&mut p, &h, 1);
    }
    assert_eq!(p.draw_state(), ds::DONE);
    assert_eq!(p.draw_drawn().0, mu_of(&p, steps_of(&p, 90_000)));
}

#[test]
fn no_current_sensor_never_stalls_on_current() {
    let (mut p, h) = undocked(0);
    h.st().current_ma = None;
    p.fill_draw(MilliUnits(90_000)).unwrap();
    run_draw(&mut p, &h);
    assert_eq!(p.draw_state(), ds::DONE);
}

// ---- aborts ------------------------------------------------------------------------------------

#[test]
fn docking_mid_draw_aborts_and_books_the_partial_volume() {
    let (mut p, h) = undocked(10_000);
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_secs(&mut p, &h, 1);
    h.st().docked = true;
    run_secs(&mut p, &h, 1);
    assert_eq!(p.draw_state(), ds::ABORTED);
    assert!(!p.draw_running());
    assert_eq!(reverse_calls(&h), vec![500], "not a single step after the dock event");
    let drawn = mu_of(&p, 500);
    assert_eq!(p.draw_drawn().0, drawn);
    assert_eq!(p.reservoir().remaining().0, 10_000 + drawn);
    assert!(find_ev(&p, EventType::Docked).is_some());
    let ev = find_ev(&p, EventType::DrawStall).expect("abort is logged");
    assert_eq!((ev.a, ev.b), (drawn as i32, 40_000));
    assert_eq!(double_beeps(&h), 0, "an abort is not announced as done");
    assert_eq!(drain(&mut p), vec![Notification::DrawProgress(drawn)]);
    assert!(!h.st().enabled);
}

#[test]
fn a_fault_latched_before_the_chunk_aborts_without_moving() {
    let (mut p, h) = undocked(10_000);
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_secs(&mut p, &h, 1);
    p.supervisor_mut().latch(Faults::OCCLUSION);
    run_secs(&mut p, &h, 1);
    assert_eq!(p.draw_state(), ds::ABORTED);
    assert_eq!(reverse_calls(&h), vec![500]);
    assert_eq!(p.draw_drawn().0, mu_of(&p, 500));
    assert_eq!(p.reservoir().remaining().0, 10_000 + mu_of(&p, 500));
}

#[test]
fn a_fault_raised_during_the_draw_stops_it_within_one_chunk() {
    let (mut p, h) = undocked(10_000);
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_secs(&mut p, &h, 1);
    h.st().battery_mv = 3_000; // critical: latched at the end of the next tick
    run_secs(&mut p, &h, 1);
    let calls = reverse_calls(&h);
    assert!(calls.len() <= 3);
    run_secs(&mut p, &h, 3);
    assert_eq!(reverse_calls(&h), calls, "no step after the fault was latched");
    assert_eq!(p.draw_state(), ds::ABORTED);
    assert!(p.supervisor().faults().contains(Faults::BATTERY_CRITICAL));
    let drawn = mu_of(&p, calls.iter().sum());
    assert_eq!(p.draw_drawn().0, drawn);
    assert_eq!(p.reservoir().remaining().0, 10_000 + drawn);
    assert_eq!(h.st().buzzer, Buzzer::Alarm);
}

#[test]
fn losing_the_angle_sensor_mid_draw_latches_internal_and_aborts() {
    let (mut p, h) = undocked(10_000);
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_secs(&mut p, &h, 1);
    h.st().angle_missing = true;
    run_secs(&mut p, &h, 1);
    assert_eq!(p.draw_state(), ds::ABORTED);
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
    assert_eq!(reverse_calls(&h), vec![500], "never moves blind");
    assert_eq!(p.draw_drawn().0, mu_of(&p, 500));
}

#[test]
fn emergency_stop_aborts_immediately() {
    let (mut p, h) = undocked(10_000);
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_secs(&mut p, &h, 1);
    p.emergency_stop();
    assert_eq!(p.draw_state(), ds::ABORTED);
    assert!(!h.st().enabled);
    assert_eq!(p.draw_drawn().0, mu_of(&p, 500));
    run_secs(&mut p, &h, 3);
    assert_eq!(reverse_calls(&h), vec![500]);
}

#[test]
fn cancel_before_the_first_chunk_books_nothing_and_needs_no_prime() {
    let (mut p, h) = undocked(10_000);
    p.set_config(PumpConfig::STRICT);
    p.fill_draw(MilliUnits(40_000)).unwrap();
    p.fill_draw(MilliUnits(0)).unwrap();
    assert_eq!(p.draw_state(), ds::ABORTED);
    assert_eq!(p.draw_drawn().0, 0);
    assert_eq!(p.reservoir().remaining().0, 10_000);
    assert!(!p.prime_required());
    run_secs(&mut p, &h, 3);
    assert!(reverse_calls(&h).is_empty());
}

// ---- mandatory priming -------------------------------------------------------------------------

#[test]
fn strict_draw_requires_a_prime_before_resume() {
    let (mut p, h) = active_undocked(50_000);
    p.set_config(PumpConfig::STRICT);
    p.fill_draw(MilliUnits(5_000)).unwrap();
    assert!(!p.prime_required(), "required once the level changed, not at the start");
    run_draw(&mut p, &h);
    assert!(p.prime_required());
    let s = p.get_status();
    assert!(s.flags & st::PRIME_REQUIRED != 0);
    assert!(s.flags & st::DRAWING == 0);

    h.st().docked = true;
    run_secs(&mut p, &h, 1);
    assert_eq!(p.resume(), Err(Error::PrimeRequired));
    assert_eq!(Error::PrimeRequired.code(), 26);
    prime_all(&mut p, &h, 2);
    assert!(!p.prime_required());
    assert!(p.get_status().flags & st::PRIME_REQUIRED == 0);
    assert_eq!(p.resume(), Ok(()));

    // delivery works normally afterwards: the reverse travel did not fool the supervisor
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 30);
    assert!(p.supervisor().faults().is_empty(), "{:?}", p.supervisor().faults());
    assert!(p.engine().delivered_steps().0 >= 19);
}

#[test]
fn relaxed_draw_needs_no_prime() {
    let (mut p, h) = active_undocked(50_000);
    p.fill_draw(MilliUnits(5_000)).unwrap();
    run_draw(&mut p, &h);
    assert!(!p.prime_required());
    h.st().docked = true;
    assert_eq!(p.resume(), Ok(()));
}

#[test]
fn a_stalled_or_aborted_draw_with_progress_also_requires_a_prime() {
    let (mut p, h) = active_undocked(50_000);
    p.set_config(PumpConfig::STRICT);
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_secs(&mut p, &h, 1);
    p.fill_draw(MilliUnits(0)).unwrap();
    assert!(p.prime_required());
    h.st().docked = true;
    assert_eq!(p.resume(), Err(Error::PrimeRequired));
}

// ---- nothing delivers while drawing ------------------------------------------------------------

#[test]
fn no_delivery_command_is_possible_while_drawing() {
    let (mut p, h) = active_undocked(50_000);
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_secs(&mut p, &h, 1);
    assert_eq!(p.bolus(MilliUnits(500)), Err(Error::NotDocked));
    assert_eq!(p.resume(), Err(Error::NotDocked));
    // docked but the job has not seen it yet: still Busy / refused
    h.st().docked = true;
    assert_eq!(p.resume(), Err(Error::Busy));
    assert!(p.bolus(MilliUnits(500)).is_err());
    assert!(p.set_temp_basal(MilliUnitsPerHour(1000), Minutes(30)).is_err());
    assert_eq!(p.fill(MilliUnits(1_000)), Err(Error::Busy));
    assert_eq!(p.prime(Pulses(2)), Err(Error::Busy));
    assert!(p.engine().is_suspended());
    run_secs(&mut p, &h, 3);
    assert_eq!(h.st().total_steps, 0, "not a single forward step");
    assert_eq!(h.st().total_reverse_steps, 500);
}

#[test]
fn no_forward_steps_for_a_whole_draw_even_with_a_schedule() {
    let (mut p, h) = active_undocked(50_000);
    p.set_schedule(&BasalSchedule::flat(MilliUnitsPerHour(5_000))).unwrap();
    p.fill_draw(MilliUnits(45_000)).unwrap();
    run_draw(&mut p, &h);
    assert_eq!(h.st().total_steps, 0);
    assert!(h.st().total_reverse_steps > 1500);
}

#[test]
fn watchdog_is_serviced_on_every_tick_of_a_draw() {
    let (mut p, h) = undocked(0);
    p.fill_draw(MilliUnits(60_000)).unwrap();
    let before = h.st().kicks;
    let mut ticks = 0;
    while p.draw_running() && ticks < 100 {
        run_secs(&mut p, &h, 1);
        ticks += 1;
    }
    assert!(ticks >= 5);
    assert_eq!(h.st().kicks - before, ticks);
}

// ---- protocol: status, frames, notifications ---------------------------------------------------

fn rpc(p: &mut Pump<MockHal>, s: &mut Session<NoCrypto>, seq: u16, body: CommandBody) -> proto::Response {
    let cmd = Command::new(seq, body);
    let mut payload = [0u8; 64];
    let pl = proto::encode_command_payload(&cmd, &mut payload).unwrap();
    let mut frame = [0u8; FRAME_MAX];
    let n = s.seal(false, cmd.body.type_id(), seq, false, &payload[..pl], &mut frame).unwrap();
    let mut out = [0u8; FRAME_MAX];
    let m = p.handle_frame(s, &frame[..n], &mut out).unwrap();
    let f = proto::decode_frame(&out[..m]).unwrap();
    assert!(f.flags & FLAG_RESPONSE != 0);
    assert_eq!(f.type_, cmd.body.type_id() | proto::RSP_BIT);
    proto::decode_response(cmd.body.type_id(), f.seq, f.payload).unwrap()
}

#[test]
fn fill_draw_over_frames_and_status_tags() {
    let (mut p, h) = undocked(10_000);
    let mut s = Session::new(NoCrypto, false, [9, 9, 9, 9], true);
    let r = rpc(&mut p, &mut s, 1, CommandBody::FillDraw { amount_mu: 40_000 });
    assert_eq!(r.result, 0);
    let st0 = rpc(&mut p, &mut s, 2, CommandBody::GetStatus).status.unwrap();
    assert_eq!((st0.draw_state, st0.draw_requested_mu, st0.draw_done_mu), (ds::DRAWING, 40_000, 0));
    assert!(st0.flags & st::DRAWING != 0);
    run_secs(&mut p, &h, 1);
    let st1 = rpc(&mut p, &mut s, 3, CommandBody::GetStatus).status.unwrap();
    assert_eq!(st1.draw_done_mu, mu_of(&p, 500));
    run_draw(&mut p, &h);
    let st2 = rpc(&mut p, &mut s, 4, CommandBody::GetStatus).status.unwrap();
    assert_eq!((st2.draw_state, st2.draw_done_mu), (ds::DONE, mu_of(&p, 1532)));
    assert_eq!(st2.reservoir_mu, 10_000 + mu_of(&p, 1532));
    assert_eq!(proto::tag::DRAW_STATE, 0x21);
    assert_eq!(proto::tag::DRAW_REQUESTED_MU, 0x22);
    assert_eq!(proto::tag::DRAW_DONE_MU, 0x23);
    // gates over frames
    let bad = rpc(&mut p, &mut s, 5, CommandBody::FillDraw { amount_mu: 0 });
    assert_eq!(bad.result, Error::NotFound.code());
}

#[test]
fn strict_prime_required_flag_over_frames() {
    let (mut p, h) = active_undocked(50_000);
    p.set_config(PumpConfig::STRICT);
    let mut s = Session::new(NoCrypto, false, [9, 9, 9, 9], true);
    assert_eq!(rpc(&mut p, &mut s, 1, CommandBody::FillDraw { amount_mu: 2_000 }).result, 0);
    run_draw(&mut p, &h);
    h.st().docked = true;
    run_secs(&mut p, &h, 1);
    let r = rpc(&mut p, &mut s, 2, CommandBody::Resume);
    assert_eq!(r.result, Error::PrimeRequired.code());
    let flags = rpc(&mut p, &mut s, 3, CommandBody::GetStatus).status.unwrap().flags;
    assert!(flags & st::PRIME_REQUIRED != 0);
    // the take-up after the draw is recovered over several prime commands (per-minute cap): repeat like a phone
    let mut seq = 4;
    loop {
        let pr = rpc(&mut p, &mut s, seq, CommandBody::FillPrime { sub_op: proto::SUBOP_PRIME, fill_mu: 0, prime_steps: 2 });
        seq += 1;
        if pr.result == 0 {
            break;
        }
        assert_eq!(pr.result, Error::Hourly.code(), "only the cap may refuse");
        assert!(seq < 12);
        run_secs(&mut p, &h, 61);
    }
    assert_eq!(rpc(&mut p, &mut s, seq, CommandBody::Resume).result, 0);
}

fn parse_notification(payload: &[u8]) -> (u8, u32) {
    let (mut kind, mut arg) = (None, None);
    for item in TlvReader::new(payload) {
        let (t, v) = item.expect("well-formed TLV");
        match t {
            proto::tag::NOTIFY_KIND => kind = Some(v[0]),
            proto::tag::NOTIFY_ARG => arg = Some(u32::from_le_bytes([v[0], v[1], v[2], v[3]])),
            _ => {}
        }
    }
    (kind.expect("kind"), arg.expect("arg"))
}

#[test]
fn notification_frames_are_type_0x90_and_decode() {
    let (mut p, h) = undocked(0);
    let mut s = Session::new(NoCrypto, false, [1, 2, 3, 4], true);
    let mut out = [0u8; FRAME_MAX];
    assert!(p.notification_frame(&mut s, false, &mut out).is_none());
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_draw(&mut p, &h);
    let expect = [
        (notify::DRAW_PROGRESS, mu_of(&p, 500)),
        (notify::DRAW_PROGRESS, mu_of(&p, 1000)),
        (notify::DRAW_PROGRESS, mu_of(&p, 1500)),
        (notify::DRAW_DONE, mu_of(&p, 1532)),
    ];
    for (i, want) in expect.iter().enumerate() {
        let n = p.notification_frame(&mut s, false, &mut out).expect("pending").expect("sealed");
        let f = proto::decode_frame(&out[..n]).expect("valid frame + CRC");
        assert_eq!(f.type_, 0x90);
        assert_eq!(f.type_, notify::FRAME_TYPE);
        assert!(f.flags & FLAG_RESPONSE != 0);
        assert_eq!(f.flags & FLAG_ENCRYPTED, 0);
        assert_eq!(f.seq, i as u16, "the pump's own notification counter");
        assert_eq!(parse_notification(f.payload), *want);
    }
    assert!(p.notification_frame(&mut s, false, &mut out).is_none());
}

#[test]
fn stalled_and_fault_notifications_are_framed() {
    let (mut p, h) = undocked(10_000);
    h.st().reverse_limit = 0;
    p.fill_draw(MilliUnits(20_000)).unwrap();
    run_secs(&mut p, &h, 1);
    h.st().battery_mv = 3_000;
    run_secs(&mut p, &h, 1);
    let mut s = Session::new(NoCrypto, false, [1, 2, 3, 4], true);
    let mut out = [0u8; FRAME_MAX];
    let mut got = Vec::new();
    while let Some(r) = p.notification_frame(&mut s, false, &mut out) {
        let n = r.unwrap();
        got.push(parse_notification(proto::decode_frame(&out[..n]).unwrap().payload));
    }
    assert!(got.contains(&(notify::DRAW_STALLED, 0)));
    assert!(got.contains(&(notify::FAULT, Faults::BATTERY_CRITICAL.bits() as u32)));
}

// A fake CCM (keystream + hash tag) good enough to prove which nonce was used.
#[derive(Default)]
struct FakeCcm;

fn keystream_xor(nonce: &[u8; CCM_NONCE_LEN], input: &[u8], out: &mut [u8]) {
    for (i, b) in input.iter().enumerate() {
        out[i] = b ^ nonce[i % 13].wrapping_add(0x5A).wrapping_add(i as u8);
    }
}

fn tag_of(nonce: &[u8; CCM_NONCE_LEN], aad: &[u8], ct: &[u8]) -> [u8; CCM_TAG_LEN] {
    let mut h: u64 = 1_469_598_103_934_665_603;
    for b in nonce.iter().chain(aad).chain(ct) {
        h = (h ^ *b as u64).wrapping_mul(1_099_511_628_211);
    }
    let mut tag = [0u8; CCM_TAG_LEN];
    for (i, t) in tag.iter_mut().enumerate() {
        *t = (h >> (8 * i)) as u8;
    }
    tag
}

impl Ccm for FakeCcm {
    fn encrypt(&mut self, nonce: &[u8; CCM_NONCE_LEN], aad: &[u8], pt: &[u8], ct: &mut [u8], tag: &mut [u8; CCM_TAG_LEN]) -> Result<(), CcmError> {
        keystream_xor(nonce, pt, ct);
        *tag = tag_of(nonce, aad, ct);
        Ok(())
    }
    fn decrypt(&mut self, nonce: &[u8; CCM_NONCE_LEN], aad: &[u8], ct: &[u8], tag: &[u8; CCM_TAG_LEN], pt: &mut [u8]) -> Result<(), CcmError> {
        if tag_of(nonce, aad, ct) != *tag {
            return Err(CcmError);
        }
        keystream_xor(nonce, ct, pt);
        Ok(())
    }
}

#[test]
fn encrypted_notification_uses_nonce_direction_two() {
    let salt = [5u8, 6, 7, 8];
    let (mut p, h) = undocked(0);
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_secs(&mut p, &h, 1);
    let mut s = Session::new(FakeCcm, true, salt, false);
    let mut out = [0u8; FRAME_MAX];
    let n = p.notification_frame(&mut s, true, &mut out).unwrap().unwrap();
    let f = proto::decode_frame(&out[..n]).unwrap();
    assert_eq!(f.type_, 0x90);
    assert!(f.flags & FLAG_ENCRYPTED != 0 && f.flags & FLAG_RESPONSE != 0);
    let ct_len = f.payload.len() - CCM_TAG_LEN;
    let mut tag = [0u8; CCM_TAG_LEN];
    tag.copy_from_slice(&f.payload[ct_len..]);
    let aad = &out[..FRAME_HEADER];
    let mut plain = [0u8; 32];
    let mut nonce = [0u8; CCM_NONCE_LEN];
    nonce[..4].copy_from_slice(&salt);
    nonce[4] = 2;
    nonce[5..7].copy_from_slice(&f.seq.to_le_bytes());
    s.ccm_mut().decrypt(&nonce, aad, &f.payload[..ct_len], &tag, &mut plain[..ct_len]).expect("direction 2");
    assert_eq!(parse_notification(&plain[..ct_len]), (notify::DRAW_PROGRESS, mu_of(&p, 500)));
    for resp in [false, true] {
        let wrong = s.nonce(resp, f.seq);
        assert_ne!(wrong, nonce, "command/response nonces differ from the notification nonce");
        assert!(s.ccm_mut().decrypt(&wrong, aad, &f.payload[..ct_len], &tag, &mut plain[..ct_len]).is_err());
    }
}

#[test]
fn encrypting_without_a_session_key_fails_but_consumes_the_notification() {
    let (mut p, h) = undocked(0);
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_secs(&mut p, &h, 1);
    let mut s = Session::new(NoCrypto, false, [0; 4], true);
    let mut out = [0u8; FRAME_MAX];
    assert_eq!(p.notification_frame(&mut s, true, &mut out), Some(Err(Error::Auth)));
    assert!(p.notification_frame(&mut s, false, &mut out).is_none());
}

// ---- regression: never step blind --------------------------------------------------------------

#[test]
fn a_lost_angle_sensor_stops_delivery_on_the_very_first_tick() {
    let (mut p, h) = running(50_000, 1000);
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 2);
    let steps = h.st().total_steps;
    assert!(steps > 0);
    h.st().angle_missing = true;
    run_secs(&mut p, &h, 3);
    assert_eq!(h.st().total_steps, steps, "no forward step without the angle sensor");
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
}
