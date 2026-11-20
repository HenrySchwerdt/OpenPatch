//! DRV8835 full-step sequence on APHASE / AENBL / BPHASE / BENBL (`phase_drive`): sequence, direction, de-energise at idle.
use openpatch_core::hal::MotorDir;
use openpatch_core::phase_drive::*;

/// Records every `apply`.
#[derive(Default)]
struct Pins {
    log: Vec<PhaseLevels>,
}
impl PhasePins for Pins {
    fn apply(&mut self, l: PhaseLevels) {
        self.log.push(l);
    }
}
#[derive(Default)]
struct Timer {
    total_us: u64,
    calls: u32,
}
impl StepTimer for Timer {
    fn delay_us(&mut self, us: u32) {
        self.total_us += us as u64;
        self.calls += 1;
    }
}

fn ab(l: PhaseLevels) -> (bool, bool) {
    (l.aphase, l.bphase)
}

#[test]
fn forward_sequence_is_00_10_11_01() {
    let mut s = PhaseStepper::new();
    assert_eq!(ab(s.levels()), (false, false));
    let seq: Vec<_> = (0..8).map(|_| ab(s.step(MotorDir::Forward))).collect();
    let one = [(true, false), (true, true), (false, true), (false, false)];
    assert_eq!(seq[..4], one);
    assert_eq!(seq[4..], one, "the table repeats every four steps");
}

#[test]
fn reverse_is_the_exact_reverse_order() {
    let mut s = PhaseStepper::new();
    let seq: Vec<_> = (0..4).map(|_| ab(s.step(MotorDir::Reverse))).collect();
    assert_eq!(seq, [(false, true), (true, true), (true, false), (false, false)]);
}

#[test]
fn forward_then_reverse_retraces_and_nets_zero() {
    let mut s = PhaseStepper::new();
    let mut f = vec![];
    for _ in 0..7 {
        f.push(ab(s.step(MotorDir::Forward)));
    }
    assert_eq!(s.net_steps(), 7);
    let mut back = vec![];
    for _ in 0..7 {
        back.push(ab(s.step(MotorDir::Reverse)));
    }
    assert_eq!(s.net_steps(), 0);
    // reversing retraces the visited positions: the last forward position is the starting point of the way back
    let mut expect: Vec<_> = f[..6].iter().rev().copied().collect();
    expect.push((false, false));
    assert_eq!(back, expect);
    assert_eq!(s.position(), 0);
}

#[test]
fn exactly_one_phase_line_toggles_per_step_in_both_directions() {
    // The supervisor counts steps from these edges: one step = one edge, and which line toggles alternates A, B, A, B.
    for dir in [MotorDir::Forward, MotorDir::Reverse] {
        let mut s = PhaseStepper::new();
        let mut prev = ab(s.levels());
        for i in 0..64 {
            let now = ab(s.step(dir));
            let toggled = (now.0 != prev.0) as u8 + (now.1 != prev.1) as u8;
            assert_eq!(toggled, 1, "{dir:?} step {i}");
            prev = now;
        }
    }
    assert_eq!(toggling_line_forward(0), Line::A);
    assert_eq!(toggling_line_forward(1), Line::B);
    assert_eq!(toggling_line_forward(2), Line::A);
    assert_eq!(toggling_line_forward(3), Line::B);
}

#[test]
fn table_matches_the_pinmap_text() {
    // FIRMWARE-PINMAP.md: (A, B) (0,0) -> (1,0) -> (1,1) -> (0,1); one toggle per step is the contract
    assert_eq!(FULL_STEP_TABLE, [(false, false), (true, false), (true, true), (false, true)]);
}

#[test]
fn power_up_state_is_de_energised_at_position_zero() {
    let s = PhaseStepper::new();
    assert_eq!(s.levels(), PhaseLevels::RESET);
    assert!(!s.is_energised());
}

#[test]
fn energise_and_de_energise_never_move_the_phase_lines() {
    let mut s = PhaseStepper::new();
    s.step(MotorDir::Forward);
    s.step(MotorDir::Forward); // position 2 = (1,1)
    let before = ab(s.levels());
    let e = s.energise();
    assert_eq!((ab(e), e.aenbl, e.benbl), (before, true, true));
    let d = s.de_energise();
    assert_eq!((ab(d), d.aenbl, d.benbl), (before, false, false), "brake keeps the phase lines (no edge for the supervisor)");
}

#[test]
fn burst_energises_after_phases_are_set_and_brakes_at_the_end() {
    let mut s = PhaseStepper::new();
    let mut p = Pins::default();
    let mut t = Timer::default();
    let (n, why) = drive_burst(&mut s, &mut p, &mut t, MotorDir::Forward, 5, 5_000, |_| true);
    assert_eq!((n, why), (5, BurstStop::Done));
    // energise, 5 steps, brake
    assert_eq!(p.log.len(), 7);
    assert_eq!(p.log[0], PhaseLevels { aphase: false, bphase: false, aenbl: true, benbl: true });
    assert!(p.log[1..6].iter().all(|l| l.aenbl && l.benbl), "energised for every step");
    let last = *p.log.last().unwrap();
    assert!(!last.aenbl && !last.benbl, "idle = both bridges braked");
    // 5 steps from position 0 end at position 1
    assert_eq!(ab(last), (true, false));
    assert_eq!(s.position(), 1);
    // alignment period + one period per step
    assert_eq!((t.calls, t.total_us), (6, 6 * 5_000));
    assert!(!s.is_energised());
}

#[test]
fn bursts_continue_the_sequence_with_no_phase_edge_in_between() {
    let mut s = PhaseStepper::new();
    let mut p = Pins::default();
    let mut t = Timer::default();
    drive_burst(&mut s, &mut p, &mut t, MotorDir::Forward, 3, 5_000, |_| true);
    let idle = *p.log.last().unwrap();
    let n1 = p.log.len();
    drive_burst(&mut s, &mut p, &mut t, MotorDir::Forward, 3, 5_000, |_| true);
    assert_eq!(ab(p.log[n1]), ab(idle), "no phase edge between the burst and the next energise");
    assert_eq!(s.position(), 2, "3 + 3 steps continue the sequence");
}

#[test]
fn empty_burst_energises_nothing() {
    let mut s = PhaseStepper::new();
    let mut p = Pins::default();
    let mut t = Timer::default();
    assert_eq!(drive_burst(&mut s, &mut p, &mut t, MotorDir::Forward, 0, 5_000, |_| true), (0, BurstStop::Done));
    assert!(p.log.iter().all(|l| !l.aenbl && !l.benbl));
    assert_eq!(t.calls, 0);
}

#[test]
fn abort_brakes_at_once() {
    let mut s = PhaseStepper::new();
    let mut p = Pins::default();
    let mut t = Timer::default();
    let (n, why) = drive_burst(&mut s, &mut p, &mut t, MotorDir::Forward, 10, 5_000, |made| made < 3);
    assert_eq!((n, why), (3, BurstStop::Aborted));
    let last = *p.log.last().unwrap();
    assert!(!last.aenbl && !last.benbl);
    assert_eq!(s.net_steps(), 3);
}

#[test]
fn reverse_burst_walks_the_table_backwards() {
    let mut s = PhaseStepper::new();
    let mut p = Pins::default();
    let mut t = Timer::default();
    drive_burst(&mut s, &mut p, &mut t, MotorDir::Reverse, 4, 2_000, |_| true);
    let phases: Vec<_> = p.log[1..5].iter().map(|l| ab(*l)).collect();
    assert_eq!(phases, [(false, true), (true, true), (true, false), (false, false)]);
    assert_eq!(s.net_steps(), -4);
}

#[test]
fn safe_write_order_energise_phases_first_de_energise_enables_first() {
    let off = PhaseLevels { aphase: true, bphase: false, aenbl: false, benbl: false };
    let on = PhaseLevels { aenbl: true, benbl: true, ..off };
    let order_cell = std::cell::RefCell::new(Vec::<&str>::new());
    apply_in_safe_order(off, on, |_, _| order_cell.borrow_mut().push("phase"), |_, _| order_cell.borrow_mut().push("enable"));
    assert_eq!(*order_cell.borrow(), ["phase", "enable"], "phase lines settle before the bridge is driven");
    order_cell.borrow_mut().clear();
    apply_in_safe_order(on, off, |_, _| order_cell.borrow_mut().push("phase"), |_, _| order_cell.borrow_mut().push("enable"));
    assert_eq!(*order_cell.borrow(), ["enable", "phase"], "the bridge goes off before anything else changes");
    order_cell.borrow_mut().clear();
    let stepped = PhaseLevels { aphase: true, bphase: true, ..on };
    apply_in_safe_order(on, stepped, |_, _| order_cell.borrow_mut().push("phase"), |_, _| order_cell.borrow_mut().push("enable"));
    assert_eq!(*order_cell.borrow(), ["enable", "phase"]);
}
