//! Cup board v4 motor controller (`openpatch_core::cup_ctl`) against a simulated board: hardware gate
//! `LATCH_Q AND SUP_PERMIT AND MCU_EN AND (docked XOR reverse)`, a supervisor model (arm interval, window, 32-step budget,
//! MCU_EN low closes the window), a cell with a load sag and a VMOT that decays after the cut. Water-only bench project.
use std::cell::RefCell;
use std::rc::Rc;

use openpatch_core::cup_ctl::*;
use openpatch_core::diag::codes;
use openpatch_core::hal::{MotorDir, MotorFault};
use openpatch_core::phase_drive::{PhaseLevels, PhasePins, StepTimer};

#[derive(Debug, Clone, PartialEq, Eq)]
enum Pin {
    MotFwd(bool),
    McuEn(bool),
    Arm,
    Phase(PhaseLevels),
}

struct World {
    now_us: u64,
    log: Vec<Pin>,
    mot_fwd: bool,
    mcu_en: bool,
    latch: bool,
    docked: bool,
    charger: bool,
    // supervisor model
    sup_last_arm_ms: Option<u64>,
    sup_armed_until_ms: u64,
    sup_fwd_steps: u32,
    sup_ok: bool,
    sup_refuses: bool,
    // analog
    rest_mv: u16,
    sag_mv: u16,
    vmot_mv: u16,
    vmot_stuck: bool,
    vmot_dies_after_steps: Option<u32>,
    sup_ok_drops_after_steps: Option<u32>,
    undock_after_steps: Option<u32>,
    vbat_reads: u32,
    // stepping
    last: PhaseLevels,
    steps: u32,
    bad_edges: u32,
    adc_dead: bool,
    /// MCU_EN went low here: the bleeders take VMOT to 0 within 500 ms (model).
    cut_at_us: Option<u64>,
}

impl World {
    fn new() -> Self {
        World {
            now_us: 10_000_000,
            log: vec![],
            mot_fwd: true,
            mcu_en: false,
            latch: false,
            docked: true,
            charger: false,
            sup_last_arm_ms: None,
            sup_armed_until_ms: 0,
            sup_fwd_steps: 0,
            sup_ok: true,
            sup_refuses: false,
            rest_mv: 4_000,
            sag_mv: 300,
            vmot_mv: 0,
            vmot_stuck: false,
            vmot_dies_after_steps: None,
            sup_ok_drops_after_steps: None,
            undock_after_steps: None,
            vbat_reads: 0,
            last: PhaseLevels::RESET,
            steps: 0,
            bad_edges: 0,
            adc_dead: false,
            cut_at_us: None,
        }
    }
    fn now_ms(&self) -> u64 {
        self.now_us / 1000
    }
    fn permit(&self) -> bool {
        self.mcu_en && self.now_ms() < self.sup_armed_until_ms && (self.mot_fwd || self.sup_fwd_steps < 32)
    }
    fn gate(&self) -> bool {
        // XOR of docked and reverse (MOT_FWD high = forward)
        self.latch && self.permit() && self.mcu_en && (self.docked == self.mot_fwd)
    }
    fn update_vmot(&mut self) {
        if self.vmot_stuck {
            self.vmot_mv = 4_960;
        } else if self.gate() {
            self.vmot_mv = 4_960;
        } else if self.vmot_mv > 0 {
            // decays, the test advances time to model the bleeder
        }
    }
    fn energised(&self) -> bool {
        self.last.aenbl || self.last.benbl
    }
}

#[derive(Clone)]
struct H(Rc<RefCell<World>>);

impl PhasePins for H {
    fn apply(&mut self, to: PhaseLevels) {
        let mut w = self.0.borrow_mut();
        let from = w.last;
        let edges = (from.aphase != to.aphase) as u32 + (from.bphase != to.bphase) as u32;
        if edges > 1 {
            w.bad_edges += 1;
        }
        if edges == 1 && to.aenbl {
            w.steps += 1;
            if w.mot_fwd {
                w.sup_fwd_steps += 1;
            }
            let s = w.steps;
            if w.vmot_dies_after_steps == Some(s) {
                w.latch = false;
            }
            if w.sup_ok_drops_after_steps == Some(s) {
                w.sup_ok = false;
            }
            if w.undock_after_steps == Some(s) {
                w.docked = false;
            }
        }
        w.last = to;
        w.log.push(Pin::Phase(to));
        if !w.gate() && !w.vmot_stuck {
            w.vmot_mv = 0;
        }
    }
}
impl StepTimer for H {
    fn delay_us(&mut self, us: u32) {
        self.0.borrow_mut().now_us += us as u64;
    }
}
impl CupSense for H {
    fn set_mot_fwd(&mut self, forward: bool) {
        let mut w = self.0.borrow_mut();
        w.mot_fwd = forward;
        w.log.push(Pin::MotFwd(forward));
    }
    fn set_mcu_en(&mut self, high: bool) {
        let mut w = self.0.borrow_mut();
        if w.mcu_en && !high {
            w.cut_at_us = Some(w.now_us);
        }
        w.mcu_en = high;
        w.log.push(Pin::McuEn(high));
        if !high {
            w.sup_armed_until_ms = 0; // MCU_EN low ends the window
        }
    }
    fn arm_edge(&mut self) {
        let mut w = self.0.borrow_mut();
        w.log.push(Pin::Arm);
        w.latch = true;
        let now = w.now_ms();
        let too_soon = w.sup_last_arm_ms.is_some_and(|t| now - t < 1_000);
        let dock_ok = w.docked == w.mot_fwd;
        if !w.sup_refuses && w.mcu_en && !too_soon && dock_ok {
            w.sup_last_arm_ms = Some(now);
            w.sup_armed_until_ms = now + if w.mot_fwd { 600 } else { 1_000 };
            w.sup_fwd_steps = 0;
        }
        w.update_vmot();
    }
    fn read(&mut self) -> CupRead {
        let w = self.0.borrow();
        CupRead { latch_q: w.latch, sup_ok: w.sup_ok, oc_ok: true, docked: w.docked, mcu_en: w.mcu_en }
    }
    fn vmot_mv(&mut self) -> Option<u16> {
        let mut w = self.0.borrow_mut();
        w.update_vmot();
        if !w.gate() && !w.vmot_stuck && w.mcu_en {
            w.vmot_mv = 0; // permit or latch lost while enabled: the switch opens at once (model)
        }
        if !w.gate() && !w.vmot_stuck && w.cut_at_us.is_some_and(|t| w.now_us - t >= 500_000) {
            w.vmot_mv = 0;
        }
        (!w.adc_dead).then_some(w.vmot_mv)
    }
    fn vbat_mv(&mut self) -> Option<u16> {
        let mut w = self.0.borrow_mut();
        w.vbat_reads += 1;
        if w.adc_dead {
            return None;
        }
        Some(if w.energised() { w.rest_mv - w.sag_mv } else { w.rest_mv })
    }
    fn now_ms(&mut self) -> u64 {
        self.0.borrow().now_ms()
    }
    fn charger_present(&mut self) -> bool {
        self.0.borrow().charger
    }
}

struct Board {
    p: H,
    t: H,
    s: H,
}
impl CupBoard for Board {
    type Phase = H;
    type Timer = H;
    type Sense = H;
    fn parts(&mut self) -> (&mut H, &mut H, &mut H) {
        (&mut self.p, &mut self.t, &mut self.s)
    }
}

fn setup() -> (CupCtl<Board>, Rc<RefCell<World>>) {
    let w = Rc::new(RefCell::new(World::new()));
    let h = H(w.clone());
    let ctl = CupCtl::new(Board { p: h.clone(), t: h.clone(), s: h }, CupCfg::DEFAULT);
    w.borrow_mut().log.clear();
    (ctl, w)
}

fn advance(w: &Rc<RefCell<World>>, ms: u64) {
    w.borrow_mut().now_us += ms * 1000;
}

fn idx(log: &[Pin], p: &Pin) -> usize {
    log.iter().position(|x| x == p).unwrap_or_else(|| panic!("{p:?} not in {log:?}"))
}

// ---- reset state -----------------------------------------------------------------------------------------------------------

#[test]
fn new_drives_the_safe_state() {
    let w = Rc::new(RefCell::new(World::new()));
    w.borrow_mut().mcu_en = true;
    w.borrow_mut().mot_fwd = false;
    let h = H(w.clone());
    let _ = CupCtl::new(Board { p: h.clone(), t: h.clone(), s: h }, CupCfg::DEFAULT);
    let w = w.borrow();
    assert!(!w.mcu_en && w.mot_fwd, "MCU_EN low, MOT_FWD at its reset default (forward)");
    assert!(!w.last.aenbl && !w.last.benbl, "bridges braked");
}

// ---- power-up ordering and refusals ------------------------------------------------------------------------------------------

#[test]
fn forward_docked_power_up_sets_direction_then_mcu_en_then_arms_and_verifies_the_supply() {
    let (mut c, w) = setup();
    c.power_up(true, MotorDir::Forward).unwrap();
    let log = w.borrow().log.clone();
    assert!(idx(&log, &Pin::MotFwd(true)) < idx(&log, &Pin::McuEn(true)));
    assert!(idx(&log, &Pin::McuEn(true)) < idx(&log, &Pin::Arm), "the supervisor accepts an arm only with MCU_EN high");
    assert!(c.is_powered());
    assert_eq!(c.readback().vmot_mv, Some(4_960));
}

#[test]
fn forward_undocked_and_reverse_docked_are_refused_before_any_pin_moves() {
    let (mut c, w) = setup();
    assert_eq!(c.power_up(false, MotorDir::Forward), Err(MotorFault::ForwardWhileUndocked));
    assert_eq!(c.power_up(true, MotorDir::Reverse), Err(MotorFault::ReverseWhileDocked));
    assert!(w.borrow().log.is_empty(), "{:?}", w.borrow().log);
}

#[test]
fn a_weak_resting_cell_or_a_charger_refuses_the_start_before_mcu_en() {
    let (mut c, w) = setup();
    w.borrow_mut().rest_mv = 3_650; // below the 3.7 V interim rest threshold
    assert_eq!(c.power_up(true, MotorDir::Forward), Err(MotorFault::CellSupply));
    let e = c.take_event().unwrap();
    assert_eq!(e.code, codes::CELL_SAG_UNDER_LOAD.with_inst(2));
    assert_eq!((e.ctx_a, e.ctx_b), (3_650, 3_700));
    assert!(!w.borrow().log.contains(&Pin::McuEn(true)));
    w.borrow_mut().rest_mv = 4_000;
    w.borrow_mut().charger = true;
    assert_eq!(c.power_up(true, MotorDir::Forward), Err(MotorFault::CellSupply));
    assert!(!w.borrow().log.contains(&Pin::McuEn(true)));
    // an ADC that cannot read the cell refuses too (0 mV)
    w.borrow_mut().charger = false;
    w.borrow_mut().adc_dead = true;
    assert_eq!(c.power_up(true, MotorDir::Forward), Err(MotorFault::CellSupply));
}

#[test]
fn a_supply_that_is_already_on_before_the_arm_latches_the_interlock_failure() {
    let (mut c, w) = setup();
    w.borrow_mut().vmot_stuck = true;
    assert_eq!(c.power_up(true, MotorDir::Forward), Err(MotorFault::SupplyUnexpected));
    assert!(c.failed());
    assert_eq!(c.take_event().unwrap().code, codes::VMOT_STUCK_ON);
    assert!(!w.borrow().log.contains(&Pin::Arm));
    w.borrow_mut().vmot_stuck = false;
    assert_eq!(c.power_up(true, MotorDir::Forward), Err(MotorFault::InterlockFailed), "latched until reset");
}

#[test]
fn a_supervisor_that_withholds_the_permit_gives_no_supply_and_mcu_en_goes_low_again() {
    let (mut c, w) = setup();
    w.borrow_mut().sup_refuses = true;
    assert_eq!(c.power_up(true, MotorDir::Forward), Err(MotorFault::SupplyMissing));
    assert!(!w.borrow().mcu_en);
    assert!(!c.is_powered());
}

// ---- the burst -----------------------------------------------------------------------------------------------------------------

#[test]
fn a_forward_burst_makes_exactly_the_steps_one_phase_edge_each_and_brakes() {
    let (mut c, w) = setup();
    c.power_up(true, MotorDir::Forward).unwrap();
    assert_eq!(c.burst(20), 20);
    c.power_off();
    let w = w.borrow();
    assert_eq!(w.steps, 20);
    assert_eq!(w.bad_edges, 0);
    assert!(!w.last.aenbl && !w.last.benbl);
    assert!(!w.mcu_en);
    assert_eq!(c.take_fault(), None);
}

#[test]
fn a_burst_without_power_up_or_above_the_plan_is_refused() {
    let (mut c, w) = setup();
    assert_eq!(c.burst(5), 0);
    assert_eq!(c.take_fault(), Some(MotorFault::SupplyMissing));
    c.power_up(true, MotorDir::Forward).unwrap();
    let max = c.plan_steps(MotorDir::Forward).unwrap();
    assert!(max <= CupCfg::DEFAULT.fwd_budget, "never more than the supervisor budget");
    assert_eq!(c.burst(max + 1), 0);
    assert_eq!(c.take_fault(), Some(MotorFault::Timeout));
    assert_eq!(w.borrow().steps, 0);
}

#[test]
fn a_cell_that_sags_under_load_stops_the_burst_after_the_first_step() {
    let (mut c, w) = setup();
    w.borrow_mut().sag_mv = 1_300; // 4.0 V at rest, 2.7 V loaded < 2.8 V
    c.power_up(true, MotorDir::Forward).unwrap();
    assert_eq!(c.burst(20), 1);
    assert_eq!(c.take_fault(), Some(MotorFault::CellSupply));
    let e = c.take_event().unwrap();
    assert_eq!(e.code, codes::CELL_SAG_UNDER_LOAD.with_inst(1));
    assert_eq!((e.ctx_a, e.ctx_b, e.ctx_c), (2_700, 2_800, 1));
    assert!(!w.borrow().last.aenbl, "braked at once");
}

#[test]
fn the_supply_or_the_supervisor_going_away_mid_burst_stops_it() {
    let (mut c, w) = setup();
    w.borrow_mut().vmot_dies_after_steps = Some(4);
    c.power_up(true, MotorDir::Forward).unwrap();
    assert_eq!(c.burst(20), 4);
    assert_eq!(c.take_fault(), Some(MotorFault::SupplyMissing));
    c.power_off();

    let (mut c, w) = setup();
    w.borrow_mut().sup_ok_drops_after_steps = Some(6);
    c.power_up(true, MotorDir::Forward).unwrap();
    assert_eq!(c.burst(20), 6);
    assert_eq!(c.take_fault(), Some(MotorFault::SupplyMissing));
}

#[test]
fn losing_the_dock_during_a_forward_burst_stops_it() {
    let (mut c, w) = setup();
    w.borrow_mut().undock_after_steps = Some(3);
    c.power_up(true, MotorDir::Forward).unwrap();
    assert_eq!(c.burst(20), 3);
    assert_eq!(c.take_fault(), Some(MotorFault::ForwardWhileUndocked));
}

#[test]
fn a_reverse_burst_undocked_sets_mot_fwd_low_first_and_respects_the_rate_cap() {
    let (mut c, w) = setup();
    w.borrow_mut().docked = false;
    c.set_reverse_pps(5_000); // clamped to 1000 pps
    assert_eq!(c.reverse_period_us(), 1_000);
    c.set_reverse_pps(200);
    assert_eq!(c.reverse_period_us(), 5_000);
    c.power_up(false, MotorDir::Reverse).unwrap();
    let log = w.borrow().log.clone();
    assert!(idx(&log, &Pin::MotFwd(false)) < idx(&log, &Pin::McuEn(true)));
    let n = c.plan_steps(MotorDir::Reverse).unwrap();
    assert_eq!(c.burst(n), n);
    c.power_off();
}

// ---- power-off, idle verification, spacing ------------------------------------------------------------------------------------

#[test]
fn the_direction_returns_to_forward_only_after_the_supply_is_verified_cut() {
    let (mut c, w) = setup();
    w.borrow_mut().docked = false;
    c.power_up(false, MotorDir::Reverse).unwrap();
    c.burst(10);
    w.borrow_mut().vmot_mv = 3_000; // still decaying when MCU_EN goes low
    c.power_off();
    assert!(!w.borrow().mot_fwd, "not yet: VMOT still high");
    assert!(c.idle_check());
    assert!(!w.borrow().mot_fwd);
    w.borrow_mut().vmot_mv = 100;
    advance(&w, 300);
    assert!(c.idle_check());
    assert!(w.borrow().mot_fwd, "verified cut: back to the reset default");
}

#[test]
fn a_supply_that_does_not_fall_after_the_cut_latches_the_failure() {
    let (mut c, w) = setup();
    c.power_up(true, MotorDir::Forward).unwrap();
    c.burst(5);
    c.power_off();
    w.borrow_mut().vmot_stuck = true;
    advance(&w, CupCfg::DEFAULT.fall_timeout_ms as u64 + 1);
    assert!(!c.idle_check());
    assert!(c.failed());
    assert_eq!(c.take_event().unwrap().code, codes::VMOT_STUCK_ON);
}

#[test]
fn mcu_en_that_reads_back_high_while_idle_is_a_failure() {
    let (mut c, w) = setup();
    w.borrow_mut().mcu_en = true; // a short to the rail
    assert!(!c.idle_check());
    assert!(c.failed());
}

#[test]
fn capacity_is_zero_until_the_supervisor_arm_interval_and_the_cell_rest_are_over() {
    let (mut c, w) = setup();
    let full = c.capacity(MotorDir::Forward);
    assert!(full > 0 && full <= 32);
    c.power_up(true, MotorDir::Forward).unwrap();
    c.burst(full);
    c.power_off();
    assert_eq!(c.capacity(MotorDir::Forward), 0);
    advance(&w, 500);
    assert_eq!(c.capacity(MotorDir::Forward), 0, "1.1 s arm spacing (supervisor 1.0 s + clock tolerance)");
    advance(&w, 700);
    assert_eq!(c.capacity(MotorDir::Forward), full);
    // a weak cell still offers capacity (the budget): the attempt must fail loudly, not defer forever
    w.borrow_mut().rest_mv = 3_000;
    assert_eq!(c.capacity(MotorDir::Forward), CupCfg::DEFAULT.fwd_budget);
}

#[test]
fn a_power_up_inside_the_arm_interval_waits_for_it_bounded() {
    let (mut c, w) = setup();
    c.power_up(true, MotorDir::Forward).unwrap();
    let t0 = w.borrow().sup_last_arm_ms.unwrap();
    c.burst(5);
    c.power_off();
    c.power_up(true, MotorDir::Forward).unwrap();
    let arm_times: Vec<u64> = vec![t0, w.borrow().sup_last_arm_ms.unwrap()];
    assert!(arm_times[1] - arm_times[0] >= CupCfg::DEFAULT.arm_spacing_ms as u64);
    assert_eq!(c.burst(5), 5);
}

#[test]
fn the_readback_reports_the_cup_signals_and_unknown_for_the_rest() {
    let (mut c, _w) = setup();
    let r = c.readback();
    assert_eq!(r.latch_q, Some(false));
    assert_eq!(r.docked_h, Some(true));
    assert_eq!(r.dir_rev, Some(false));
    assert_eq!(r.oc_ok, Some(true));
    assert_eq!(r.vmot_mv, Some(0));
    assert_eq!(r.pgate, None);
    assert_eq!(r.i_sense_mv, None, "no shunt on this board");
}
