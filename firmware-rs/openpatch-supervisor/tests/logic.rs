//! Supervisor state machine: arm window, step budget, permit drop and latch, H15, over-current lock-out, lock-up, buckets.
use openpatch_supervisor::logic::*;
use openpatch_supervisor::status::*;

const CFG: Config = Config::CUP_MITER_1_1;

/// Full-step table walker for the test side of the PHASE lines.
struct Walker {
    pos: usize,
}
const TABLE: [(bool, bool); 4] = [(false, false), (true, false), (true, true), (false, true)];
impl Walker {
    fn new() -> Self {
        Walker { pos: 0 }
    }
    fn levels(&self) -> (bool, bool) {
        TABLE[self.pos]
    }
    fn fwd(&mut self) -> (bool, bool) {
        self.pos = (self.pos + 1) % 4;
        TABLE[self.pos]
    }
    fn rev(&mut self) -> (bool, bool) {
        self.pos = (self.pos + 3) % 4;
        TABLE[self.pos]
    }
}

/// A supervisor past its boot check, idle, docked + forward + healthy.
fn idle() -> (Supervisor, Walker, u64) {
    let w = Walker::new();
    let (a, b) = w.levels();
    let mut s = Supervisor::new(CFG, 0, Inputs::DELIVERING, a, b);
    assert_eq!(s.state(), State::Boot);
    s.tick(CFG.boot_check_ms as u64);
    assert_eq!(s.state(), State::Idle);
    (s, w, CFG.boot_check_ms as u64)
}

fn arm(s: &mut Supervisor, t: u64) -> Outputs {
    let (o, r) = s.on_arm_edge(t);
    assert_eq!(r, Ok(()), "arm at {t}");
    o
}

fn fwd_steps(s: &mut Supervisor, w: &mut Walker, t0: u64, n: u32, period: u64) -> (Outputs, u64) {
    let mut t = t0;
    let mut o = s.outputs();
    for _ in 0..n {
        t += period;
        let (a, b) = w.fwd();
        o = s.on_phase(t, a, b);
    }
    (o, t)
}

// ---- boot ---------------------------------------------------------------------------------------------------------

#[test]
fn boot_gives_no_permit_for_200_ms_then_idle() {
    let w = Walker::new();
    let mut s = Supervisor::new(CFG, 1_000, Inputs::DELIVERING, w.levels().0, w.levels().1);
    assert_eq!(s.outputs(), Outputs { permit: false, ok: false, state: State::Boot });
    assert_eq!(s.tick(1_199).state, State::Boot);
    assert_eq!(s.tick(1_200), Outputs { permit: false, ok: true, state: State::Idle });
    // an arm edge during BOOT is refused
    let w = Walker::new();
    let mut s = Supervisor::new(CFG, 0, Inputs::DELIVERING, w.levels().0, w.levels().1);
    assert_eq!(s.on_arm_edge(50).1, Err(ArmReject::State(State::Boot)));
}

#[test]
fn boot_check_fails_with_over_current_or_phase_activity() {
    let w = Walker::new();
    let mut s = Supervisor::new(CFG, 0, Inputs { oc_ok: false, ..Inputs::DELIVERING }, w.levels().0, w.levels().1);
    s.tick(200);
    assert_eq!((s.state(), s.reason()), (State::Fault, FaultReason::BootCheck));
    let mut s = Supervisor::new(CFG, 0, Inputs::DELIVERING, false, false);
    s.on_phase(50, true, false);
    assert_eq!((s.state(), s.reason()), (State::Fault, FaultReason::BootCheck));
}

// ---- arm window and budget ----------------------------------------------------------------------------------------------

#[test]
fn arm_opens_a_window_with_permit() {
    let (mut s, _w, t) = idle();
    let o = arm(&mut s, t + 10);
    assert_eq!(o, Outputs { permit: true, ok: true, state: State::Armed });
}

#[test]
fn a_normal_burst_of_29_steps_stays_inside_the_window_and_ends_with_mcu_en_low() {
    let (mut s, mut w, t) = idle();
    arm(&mut s, t + 10);
    let (o, t_end) = fwd_steps(&mut s, &mut w, t + 10, 29, 5);
    assert!(o.permit && s.fwd_in_window() == 29);
    // the main MCU powers down: MCU_EN low is the normal end, no fault
    let o = s.on_inputs(t_end + 1, Inputs { mcu_en: false, ..Inputs::DELIVERING });
    assert_eq!(o, Outputs { permit: false, ok: true, state: State::Dead });
    assert_eq!(s.reason(), FaultReason::None);
    assert_eq!(s.recent_faults(), 0);
}

#[test]
fn the_permit_drops_with_the_32nd_forward_step() {
    let (mut s, mut w, t) = idle();
    arm(&mut s, t + 10);
    let (o, t31) = fwd_steps(&mut s, &mut w, t + 10, 31, 2);
    assert!(o.permit, "31 steps: still armed");
    let (a, b) = w.fwd();
    let o = s.on_phase(t31 + 2, a, b);
    assert_eq!(o, Outputs { permit: false, ok: true, state: State::Dead }, "the same call that counted step 32 drops the permit");
    assert_eq!(s.fwd_in_window(), 32);
    assert_eq!(s.reason(), FaultReason::None, "using the full budget is not a fault");
}

#[test]
fn the_33rd_step_is_a_budget_violation_and_latches() {
    let (mut s, mut w, t) = idle();
    arm(&mut s, t + 10);
    let (_, t32) = fwd_steps(&mut s, &mut w, t + 10, 32, 2);
    let (a, b) = w.fwd();
    let o = s.on_phase(t32 + 2, a, b);
    assert_eq!(o, Outputs { permit: false, ok: false, state: State::Fault });
    assert_eq!(s.reason(), FaultReason::BudgetExceeded);
}

#[test]
fn the_window_closes_by_time() {
    let (mut s, mut w, t) = idle();
    arm(&mut s, t + 10);
    assert!(s.tick(t + 10 + CFG.window_ms as u64 - 1).permit);
    assert_eq!(s.tick(t + 10 + CFG.window_ms as u64), Outputs { permit: false, ok: true, state: State::Dead });
    // a step after the window is a stray step
    let (a, b) = w.fwd();
    s.on_phase(t + 700, a, b);
    assert_eq!((s.state(), s.reason()), (State::Fault, FaultReason::StepOutsideWindow));
}

#[test]
fn a_step_event_after_the_window_end_closes_it_first() {
    // the tick did not run yet: the event itself advances time
    let (mut s, mut w, t) = idle();
    arm(&mut s, t + 10);
    let (a, b) = w.fwd();
    s.on_phase(t + 10 + CFG.window_ms as u64 + 5, a, b);
    assert_eq!(s.reason(), FaultReason::StepOutsideWindow);
}

#[test]
fn dead_time_and_minimum_arm_interval() {
    let (mut s, _w, t) = idle();
    arm(&mut s, t);
    // window runs out at +600, DEAD until +1000
    assert_eq!(s.tick(t + 600).state, State::Dead);
    assert_eq!(s.on_arm_edge(t + 700).1, Err(ArmReject::State(State::Dead)));
    assert_eq!(s.tick(t + 999).state, State::Dead);
    assert_eq!(s.tick(t + 1_000).state, State::Idle);
    arm(&mut s, t + 1_000);
}

#[test]
fn an_early_burst_end_still_respects_the_one_second_arm_distance() {
    let (mut s, _w, t) = idle();
    arm(&mut s, t);
    s.on_inputs(t + 150, Inputs { mcu_en: false, ..Inputs::DELIVERING }); // burst over at 150 ms
    // DEAD for 400 ms: idle again at 550, but only 600 ms after the arm
    s.on_inputs(t + 560, Inputs::DELIVERING);
    assert_eq!(s.state(), State::Idle);
    assert_eq!(s.on_arm_edge(t + 600).1, Err(ArmReject::TooSoon));
    assert_eq!(s.on_arm_edge(t + 999).1, Err(ArmReject::TooSoon));
    assert_eq!(s.on_arm_edge(t + 1_000).1, Ok(()));
}

#[test]
fn arm_spam_does_not_extend_the_window_and_is_counted() {
    let (mut s, _w, t) = idle();
    arm(&mut s, t);
    for k in 1..20 {
        assert_eq!(s.on_arm_edge(t + k * 10).1, Err(ArmReject::State(State::Armed)));
    }
    assert_eq!(s.tick(t + 600).state, State::Dead, "the window ended on time");
    assert_eq!(s.arms_rejected(), 19);
    assert_eq!(s.arm_edges(), 20);
}

#[test]
fn arm_requires_the_inputs() {
    let (mut s, _w, t) = idle();
    s.on_inputs(t + 1, Inputs { mcu_en: false, ..Inputs::DELIVERING });
    assert_eq!(s.on_arm_edge(t + 2).1, Err(ArmReject::McuEnLow));
    s.on_inputs(t + 3, Inputs { link_ok: false, ..Inputs::DELIVERING });
    assert_eq!(s.on_arm_edge(t + 4).1, Err(ArmReject::LinkDown));
    // undocked + forward: nothing to permit (the hardware gate is closed too)
    s.on_inputs(t + 5, Inputs { docked: false, ..Inputs::DELIVERING });
    assert_eq!(s.on_arm_edge(t + 6).1, Err(ArmReject::UndockedForward));
    assert_eq!(s.state(), State::Idle, "refusals are not faults");
}

// ---- direction and dock consistency (H15) -------------------------------------------------------------------------

const UNDOCKED_REV: Inputs = Inputs { docked: false, fwd_intent: false, ..Inputs::DELIVERING };

#[test]
fn positive_controls_docked_forward_and_undocked_reverse_permit() {
    let (mut s, _w, t) = idle();
    assert!(arm(&mut s, t).permit); // docked + forward
    let (mut s, _w, t) = idle();
    s.on_inputs(t + 1, UNDOCKED_REV);
    assert!(arm(&mut s, t + 2).permit, "undocked + reverse (refill) is allowed");
}

#[test]
fn h15_docked_and_reverse_never_permits() {
    // (1) the main MCU asks for the arm with docked + reverse: refused AND latched, permit stays 0
    let (mut s, _w, t) = idle();
    s.on_inputs(t + 1, Inputs { fwd_intent: false, ..Inputs::DELIVERING });
    let (o, r) = s.on_arm_edge(t + 2);
    assert!(r.is_err());
    assert_eq!(o, Outputs { permit: false, ok: false, state: State::Fault });
    assert_eq!(s.reason(), FaultReason::DockedReverse);

    // (2) armed docked + forward, then the direction line goes to reverse: the SAME call drops the permit
    let (mut s, _w, t) = idle();
    arm(&mut s, t);
    let o = s.on_inputs(t + 1, Inputs { fwd_intent: false, ..Inputs::DELIVERING });
    assert_eq!(o, Outputs { permit: false, ok: false, state: State::Fault });
    assert_eq!(s.reason(), FaultReason::DockedReverse);
}

#[test]
fn h15_a_dock_glitch_during_a_reverse_burst_latches_even_after_the_glitch_is_gone() {
    let (mut s, mut w, t) = idle();
    s.on_inputs(t + 1, UNDOCKED_REV);
    arm(&mut s, t + 2);
    for k in 0..5 {
        let (a, b) = w.rev();
        assert!(s.on_phase(t + 3 + k, a, b).permit);
    }
    // 100 us glitch of DOCK_N: two EXTI calls
    let o = s.on_inputs(t + 10, Inputs { docked: true, ..UNDOCKED_REV });
    assert!(!o.permit, "dropped inside the handler of the first edge");
    assert_eq!(s.reason(), FaultReason::DockedReverse);
    let o = s.on_inputs(t + 10, UNDOCKED_REV);
    assert!(!o.permit && o.state == State::Fault, "the glitch is over, the latch is not");
    assert!(!s.tick(t + 1_500).permit);
    assert_eq!(s.tick(t + 10 + CFG.fault_hold_ms as u64 - 1).state, State::Fault);
    // quiet for 2 s with healthy inputs: back to idle
    assert_eq!(s.tick(t + 10 + CFG.fault_hold_ms as u64).state, State::Idle);
}

#[test]
fn fault_does_not_clear_while_h15_is_still_present() {
    let (mut s, _w, t) = idle();
    s.on_inputs(t + 1, Inputs { fwd_intent: false, ..Inputs::DELIVERING });
    let _ = s.on_arm_edge(t + 2);
    assert_eq!(s.tick(t + 10_000).state, State::Fault, "docked + reverse is still there");
    s.on_inputs(t + 10_001, Inputs::DELIVERING); // direction back to forward
    assert_eq!(s.tick(t + 10_001 + CFG.fault_hold_ms as u64).state, State::Idle);
}

#[test]
fn undocked_while_armed_forward_faults() {
    let (mut s, _w, t) = idle();
    arm(&mut s, t);
    let o = s.on_inputs(t + 100, Inputs { docked: false, ..Inputs::DELIVERING });
    assert_eq!(o, Outputs { permit: false, ok: false, state: State::Fault });
    assert_eq!(s.reason(), FaultReason::UndockedForward);
}

#[test]
fn step_direction_must_agree_with_the_intent_line() {
    // reverse steps while the intent says forward
    let (mut s, mut w, t) = idle();
    arm(&mut s, t);
    let (a, b) = w.rev();
    let o = s.on_phase(t + 5, a, b);
    assert!(!o.permit);
    assert_eq!(s.reason(), FaultReason::DirectionMismatch);
    // forward steps while the intent says reverse (undocked)
    let (mut s, mut w, t) = idle();
    s.on_inputs(t + 1, UNDOCKED_REV);
    arm(&mut s, t + 2);
    let (a, b) = w.fwd();
    s.on_phase(t + 5, a, b);
    assert_eq!(s.reason(), FaultReason::DirectionMismatch);
}

#[test]
fn reverse_window_is_longer_and_reverse_steps_are_not_counted_in_the_buckets() {
    let (mut s, mut w, t) = idle();
    s.on_inputs(t + 1, UNDOCKED_REV);
    arm(&mut s, t + 2);
    for k in 0..300u64 {
        let (a, b) = w.rev();
        assert!(s.on_phase(t + 3 + k * 3, a, b).permit, "reverse step {k}");
    }
    assert_eq!(s.rev_in_window(), 300);
    assert_eq!((s.hour_level_steps(), s.minute_level_steps()), (0, 0), "draw steps never reach the dose buckets");
    // a reverse window is 1 s long
    assert!(s.tick(t + 2 + 999).permit);
    assert!(!s.tick(t + 2 + 1_000).permit);
}

#[test]
fn reverse_budget_is_enforced_too() {
    let (mut s, mut w, t) = idle();
    s.on_inputs(t + 1, UNDOCKED_REV);
    arm(&mut s, t + 2);
    let mut last = s.outputs();
    for k in 0..CFG.rev_budget as u64 {
        let (a, b) = w.rev();
        last = s.on_phase(t + 3 + k, a, b);
    }
    assert!(!last.permit && last.state == State::Dead, "the permit drops with the last budgeted reverse step");
    let (a, b) = w.rev();
    s.on_phase(t + 3 + 600, a, b);
    assert_eq!(s.reason(), FaultReason::BudgetExceeded);
}

// ---- stray motion, sequence errors ----------------------------------------------------------------------------------------

#[test]
fn stepping_without_a_window_is_a_fault() {
    let (mut s, mut w, t) = idle();
    let (a, b) = w.fwd();
    let o = s.on_phase(t + 5, a, b);
    assert_eq!(o, Outputs { permit: false, ok: false, state: State::Fault });
    assert_eq!(s.reason(), FaultReason::StepOutsideWindow);
}

#[test]
fn both_lines_toggling_at_once_is_a_sequence_fault() {
    let (mut s, _w, t) = idle();
    arm(&mut s, t);
    let o = s.on_phase(t + 5, true, true); // 00 -> 11
    assert!(!o.permit);
    assert_eq!(s.reason(), FaultReason::PhaseSequence);
}

#[test]
fn the_main_mcu_reset_mid_burst_is_not_a_phase_fault() {
    let (mut s, mut w, t) = idle();
    arm(&mut s, t);
    fwd_steps(&mut s, &mut w, t, 3, 5); // the burst leaves the lines at 11
    // the nRF resets: its pins float low (both lines drop at once)
    let o = s.on_main_reset(t + 40, false, false);
    assert_eq!(o, Outputs { permit: false, ok: true, state: State::Dead });
    assert_eq!(s.reason(), FaultReason::None);
    s.tick(t + 1_000);
    assert_eq!(s.state(), State::Idle);
    // the new burst starts from 00 again and counts normally
    let mut w2 = Walker::new();
    arm(&mut s, t + 1_000);
    let (a, b) = w2.fwd();
    assert!(s.on_phase(t + 1_010, a, b).permit);
    assert_eq!(s.fwd_in_window(), 1);
}

#[test]
fn a_reset_does_not_clear_a_fault() {
    let (mut s, mut w, t) = idle();
    let (a, b) = w.fwd();
    s.on_phase(t + 5, a, b);
    assert_eq!(s.state(), State::Fault);
    s.on_main_reset(t + 10, false, false);
    assert_eq!(s.state(), State::Fault);
}

// ---- over-current ------------------------------------------------------------------------------------------------------------

#[test]
fn over_current_falling_edge_faults_and_locks_out_re_arming_for_two_seconds() {
    let (mut s, _w, t) = idle();
    arm(&mut s, t);
    let o = s.on_inputs(t + 100, Inputs { oc_ok: false, ..Inputs::DELIVERING });
    assert_eq!(o, Outputs { permit: false, ok: false, state: State::Fault });
    assert_eq!(s.reason(), FaultReason::OverCurrent);
    // with the permit low the switch recovers: OC_OK high again, but the fault holds for 2 s
    s.on_inputs(t + 150, Inputs::DELIVERING);
    assert_eq!(s.on_arm_edge(t + 1_000).1, Err(ArmReject::State(State::Fault)));
    assert_eq!(s.tick(t + 150 + CFG.fault_hold_ms as u64 - 1).state, State::Fault);
    assert_eq!(s.tick(t + 150 + CFG.fault_hold_ms as u64).state, State::Idle);
    assert!(s.on_arm_edge(t + 150 + CFG.fault_hold_ms as u64 + 1).1.is_ok());
}

#[test]
fn over_current_that_stays_asserted_keeps_the_fault() {
    let (mut s, _w, t) = idle();
    arm(&mut s, t);
    s.on_inputs(t + 100, Inputs { oc_ok: false, ..Inputs::DELIVERING });
    assert_eq!(s.tick(t + 60_000).state, State::Fault);
}

#[test]
fn over_current_in_idle_also_faults() {
    let (mut s, _w, t) = idle();
    s.on_inputs(t + 5, Inputs { oc_ok: false, ..Inputs::DELIVERING });
    assert_eq!((s.state(), s.reason()), (State::Fault, FaultReason::OverCurrent));
}

#[test]
fn link_loss_while_armed_faults() {
    let (mut s, _w, t) = idle();
    arm(&mut s, t);
    let o = s.on_inputs(t + 5, Inputs { link_ok: false, ..Inputs::DELIVERING });
    assert!(!o.permit);
    assert_eq!(s.reason(), FaultReason::LinkLost);
}

// ---- lock-up ------------------------------------------------------------------------------------------------------------------

fn provoke_fault(s: &mut Supervisor, w: &mut Walker, t: u64) {
    let (a, b) = w.fwd();
    s.on_phase(t, a, b); // stray step in IDLE
}

#[test]
fn three_faults_in_ten_minutes_lock_until_power_cycle() {
    let (mut s, mut w, mut t) = idle();
    for k in 0..3 {
        t += 5_000;
        s.tick(t); // out of the previous FAULT
        provoke_fault(&mut s, &mut w, t);
        assert!(s.state() == State::Fault || s.state() == State::Locked, "fault {k}");
    }
    assert_eq!(s.state(), State::Locked);
    assert_eq!(s.reason(), FaultReason::TooManyFaults);
    assert_eq!(s.outputs(), Outputs { permit: false, ok: false, state: State::Locked });
    // nothing leaves LOCKED: no time, no inputs, no arm
    for dt in [10_000u64, 3_600_000, 86_400_000] {
        s.on_inputs(t + dt, Inputs::DELIVERING);
        assert_eq!(s.tick(t + dt).state, State::Locked);
        assert_eq!(s.on_arm_edge(t + dt).1, Err(ArmReject::State(State::Locked)));
    }
}

#[test]
fn faults_further_apart_than_ten_minutes_do_not_lock() {
    let (mut s, mut w, mut t) = idle();
    for k in 0..6 {
        t += 400_000; // 6.7 minutes apart: never three inside 10 minutes... but two do
        s.tick(t);
        provoke_fault(&mut s, &mut w, t);
        // three consecutive faults span 800 s, more than the 600 s window: never locked
        assert_eq!(s.state(), State::Fault, "fault {k}");
    }
}

// ---- buckets ------------------------------------------------------------------------------------------------------------------

#[test]
fn arm_is_refused_when_a_bucket_has_less_room_than_one_budget() {
    let (mut s, mut w, mut t) = idle();
    let mut windows = 0;
    // arm every 1.0 s and use the full budget each time: the per-minute bucket (241 steps) fills
    loop {
        t += 1_000;
        let (o, r) = s.on_arm_edge(t);
        if r.is_err() {
            assert_eq!(r, Err(ArmReject::BucketFull));
            assert!(!o.permit);
            break;
        }
        let (_, tt) = fwd_steps(&mut s, &mut w, t, 32, 2);
        t = tt;
        windows += 1;
        assert!(windows < 20, "the bucket must fill within 20 windows");
    }
    assert!(windows >= 7 && windows <= 9, "{windows} full windows fit in one minute (241 steps)");
    assert_eq!(s.state(), State::Idle, "a full bucket is a refusal, not a fault");
    // it leaks: after a while the arm works again
    t += 10_000;
    assert!(s.on_arm_edge(t).1.is_ok());
}

#[test]
fn sustained_forward_steps_are_bounded_by_the_buckets_over_two_hours() {
    // Worst case: the main MCU arms every second and steps the full budget. The buckets bound the TOTAL forward steps to
    // capacity + leak x time (a leaky bucket admits one full capacity burst on top of the sustained rate): a backstop of twice the
    // hourly limit, not the limit itself (the limit is the core's rolling window).
    let (mut s, mut w, mut t) = idle();
    let end = 2 * 3_600_000u64;
    let mut total = 0u32;
    while t < end {
        t += 1_000;
        let (_o, r) = s.on_arm_edge(t);
        if r.is_ok() {
            let (_, tt) = fwd_steps(&mut s, &mut w, t, 32, 1);
            t = tt;
            total += 32;
            // leave through the normal end: MCU_EN low then high again for the next burst
            s.on_inputs(t + 1, Inputs { mcu_en: false, ..Inputs::DELIVERING });
            s.on_inputs(t + 2, Inputs::DELIVERING);
        }
    }
    let cap = CFG.hour_cap_steps;
    assert!(total <= cap + cap * 2 + 32, "total {total} steps in 2 h vs bucket bound {}", 3 * cap + 32);
    assert!(total >= cap, "the bucket does admit the sustained rate: {total}");
}

// ---- misc -------------------------------------------------------------------------------------------------------------------

#[test]
fn time_never_runs_backwards() {
    let (mut s, _w, t) = idle();
    arm(&mut s, t + 100);
    // an out-of-order timestamp must not reopen or extend anything
    assert!(s.tick(t + 50).permit);
    assert_eq!(s.tick(t + 100 + 600).state, State::Dead);
    assert_eq!(s.tick(t + 10).state, State::Dead);
}

#[test]
fn outputs_are_safe_in_every_state_but_armed() {
    let (mut s, mut w, t) = idle();
    assert!(!s.outputs().permit);
    arm(&mut s, t);
    assert!(s.outputs().permit);
    s.tick(t + 600);
    assert!(!s.outputs().permit); // dead
    let (a, b) = w.fwd();
    s.on_phase(t + 700, a, b);
    assert!(!s.outputs().permit); // fault
}

#[test]
fn status_frame_roundtrip_and_errors() {
    let (mut s, mut w, t) = idle();
    arm(&mut s, t);
    fwd_steps(&mut s, &mut w, t, 5, 2);
    let f = s.snapshot();
    assert_eq!((f.state, f.fwd_in_window, f.arm_edges), (State::Armed, 5, 1));
    let bytes = f.encode();
    assert_eq!(bytes.len(), FRAME_LEN);
    assert_eq!(bytes[0], SYNC);
    assert_eq!(StatusFrame::decode(&bytes), Ok(f));
    let mut bad = bytes;
    bad[3] ^= 1;
    assert_eq!(StatusFrame::decode(&bad), Err(DecodeError::Crc));
    let mut bad = bytes;
    bad[0] = 0;
    assert_eq!(StatusFrame::decode(&bad), Err(DecodeError::Sync));
    assert_eq!(StatusFrame::decode(&bytes[..12]), Err(DecodeError::Length));
    let mut bad = bytes;
    bad[1] = 9;
    bad[12] = crc8(&bad[..12]);
    assert_eq!(StatusFrame::decode(&bad), Err(DecodeError::BadState));
    let mut bad = bytes;
    bad[2] = 8; // the reserved reason
    bad[12] = crc8(&bad[..12]);
    assert_eq!(StatusFrame::decode(&bad), Err(DecodeError::BadReason));
    // every reason and state round trips
    for st in [State::Boot, State::Idle, State::Armed, State::Dead, State::Fault, State::Locked] {
        for r in [FaultReason::None, FaultReason::OverCurrent, FaultReason::DockedReverse, FaultReason::TooManyFaults, FaultReason::BucketOverflow, FaultReason::LinkLost] {
            let f = StatusFrame { state: st, reason: r, fwd_in_window: 32, rev_in_window: 500, hour_level: 2000, minute_level: 240, arm_edges: 65_535 };
            assert_eq!(StatusFrame::decode(&f.encode()), Ok(f));
        }
    }
}
