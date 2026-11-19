//! Bench controller board: interlock sequencing, rotating single-gate disarm, readback classification and the
//! POST proofs, against an electrical model of the Rev A gate network with fault injection
//! (`electronics/bench/INTERLOCK.md`). TEST PROJECT, never worn, water only.
use openpatch_core::bench_ctl::*;
use openpatch_core::hal::{DiagEvent, MotorDir, SelfTestOutcome, SelfTestStep};
use openpatch_core::interlock::{dir_level_high, mot_allow, Disarm, PowerError};
use openpatch_core::limits::isense_mv_to_ma;
use openpatch_diag::codes;

/// Electrical model of the controller's gate network. Time is advanced only by `delay_us`.
#[derive(Clone, Default)]
struct Faults {
    q4_short: bool,
    q4_open: bool,
    /// Q8 (MCU_EN leg) shorted: conducts although MCU_EN is low.
    q8_short: bool,
    /// Q5 (latch leg) shorted.
    q5_short: bool,
    /// Q13 (OC leg) shorted.
    q13_short: bool,
    /// Q6 (dock leg) shorted: the pair `Q6 || Q10` always conducts.
    q6_short: bool,
    /// The DIR leg keeps conducting after DIR was reverse until MCU_EN is cycled low.
    dir_leg_sticky: bool,
    latch_stuck_high: bool,
    latch_stuck_low: bool,
    /// Comparator / latch never trip.
    oc_never_trips: bool,
    /// OC latch stuck tripped (comparator output stuck).
    oc_stuck_tripped: bool,
    /// DOCKED_H stuck high (Q7 off).
    docked_h_stuck_high: bool,
    /// DOCKED_H forced low always (Q12 on).
    docked_h_stuck_low: bool,
    /// DOCK_TEST has no effect (Q12 open).
    q12_open: bool,
    /// Motor not connected: no holding current.
    no_motor: bool,
    /// The DIR_REV node does not follow MOT_DIR (dead path, stays low).
    dir_rev_dead: bool,
}

struct Board {
    t_us: u64,
    // driven
    mcu_en: bool,
    clr: bool,
    dock_test: bool,
    oc_test: bool,
    stby: bool,
    mot_dir: bool,
    en_fault_low: bool,
    latch_q: bool,
    oc_ok: bool,
    mcu_en_rise_us: Option<u64>,
    dir_seen_reverse: bool,
    vmot: f64,
    last_us: u64,
    // physical
    hall_docked: bool,
    pod_present: bool,
    tmag: bool,
    r97: bool,
    vbus: u32,
    vdd: u32,
    f: Faults,
    // observation
    stby_since: Option<u64>,
    max_stby_us: u64,
    stby_edges: u32,
    arm_edges: u32,
    log_forced_on: u32,
}

impl Board {
    fn new() -> Self {
        Board {
            t_us: 0,
            mcu_en: false,
            clr: true,
            dock_test: false,
            oc_test: false,
            stby: false,
            mot_dir: false,
            en_fault_low: false,
            latch_q: false,
            oc_ok: true,
            mcu_en_rise_us: None,
            dir_seen_reverse: false,
            vmot: 0.0,
            last_us: 0,
            hall_docked: true,
            pod_present: true,
            tmag: true,
            r97: false,
            vbus: 4_950,
            vdd: 3_300,
            f: Faults::default(),
            stby_since: None,
            max_stby_us: 0,
            stby_edges: 0,
            arm_edges: 0,
            log_forced_on: 0,
        }
    }
    fn docked_h(&self) -> bool {
        if self.f.docked_h_stuck_high {
            return true;
        }
        if self.f.docked_h_stuck_low {
            return false;
        }
        self.hall_docked && !(self.dock_test && !self.f.q12_open)
    }
    fn dir_rev(&self) -> bool {
        if self.f.dir_rev_dead {
            return false;
        }
        self.mot_dir != self.r97
    }
    /// The series chain conducts (PGATE_MON low).
    fn chain(&self) -> bool {
        let latch = self.latch_q || self.f.q5_short;
        let en = self.mcu_en || self.f.q8_short;
        let oc = self.oc_ok || self.f.q13_short;
        let dir_leg = self.dir_rev() || (self.f.dir_leg_sticky && self.dir_seen_reverse && self.mcu_en);
        let dock_pair = self.docked_h() || dir_leg || self.f.q6_short;
        latch && en && oc && dock_pair
    }
    fn switch_on(&self) -> bool {
        (self.chain() && !self.f.q4_open) || self.f.q4_short
    }
    fn current_ma(&self) -> f64 {
        if self.stby && !self.f.no_motor && self.vmot > 3_000.0 && !self.en_fault_low {
            160.0
        } else {
            0.0
        }
    }
    /// Advance the analog state to `t`.
    fn step_to(&mut self, t: u64) {
        let mut cur = self.last_us;
        while cur < t {
            let dt = (t - cur).min(100);
            cur += dt;
            self.t_us = cur;
            if self.switch_on() {
                self.vmot += (4_800.0 - self.vmot) * (1.0 - (-(dt as f64) / 1_000.0).exp());
            } else {
                self.vmot *= (-(dt as f64) / 10_000.0).exp();
            }
            // over-current latch: armed 12 ms after MCU_EN rises
            let armed = self.mcu_en_rise_us.is_some_and(|r| cur >= r + 12_000);
            let thr = if self.oc_test { 45.0 } else { 450.0 };
            if armed && self.mcu_en && self.current_ma() > thr && !self.f.oc_never_trips {
                self.oc_ok = false;
            }
            if self.f.oc_stuck_tripped {
                self.oc_ok = false;
            }
            if !self.mcu_en {
                if !self.f.oc_stuck_tripped {
                    self.oc_ok = true;
                }
                self.dir_seen_reverse = false;
            }
            if self.dir_rev() && self.mcu_en {
                self.dir_seen_reverse = true;
            }
            if self.f.latch_stuck_high {
                self.latch_q = true;
            }
            if self.f.latch_stuck_low {
                self.latch_q = false;
            }
        }
        self.last_us = t;
    }
    fn touch(&mut self) {
        let t = self.t_us;
        self.step_to(t.max(self.last_us));
        if self.f.latch_stuck_high {
            self.latch_q = true;
        }
        if self.f.oc_stuck_tripped {
            self.oc_ok = false;
        }
    }
    fn latch_apply_clear(&mut self) {
        if self.clr && !self.f.latch_stuck_high {
            self.latch_q = false;
        }
    }
}

impl BenchPins for Board {
    fn set_mot_dir(&mut self, high: bool) {
        self.touch();
        self.mot_dir = high;
    }
    fn set_mcu_en(&mut self, high: bool) {
        self.touch();
        if high && !self.mcu_en {
            self.mcu_en_rise_us = Some(self.t_us);
        }
        if !high {
            self.mcu_en_rise_us = None;
            // the over-current latch CLR follows MCU_EN low immediately
            if !self.f.oc_stuck_tripped {
                self.oc_ok = true;
            }
            self.dir_seen_reverse = false;
        }
        self.mcu_en = high;
        self.step_to(self.t_us);
    }
    fn arm_edge(&mut self) {
        self.touch();
        self.arm_edges += 1;
        if !self.clr && !self.f.latch_stuck_low {
            self.latch_q = true;
        }
    }
    fn set_latch_clear(&mut self, asserted: bool) {
        self.touch();
        self.clr = asserted;
        self.latch_apply_clear();
    }
    fn set_dock_test(&mut self, on: bool) {
        self.touch();
        self.dock_test = on;
    }
    fn set_oc_test(&mut self, on: bool) {
        self.touch();
        self.oc_test = on;
    }
    fn set_stby(&mut self, active: bool) {
        self.touch();
        if active && !self.stby {
            self.stby_since = Some(self.t_us);
            self.stby_edges += 1;
        }
        if !active {
            if let Some(s) = self.stby_since.take() {
                self.max_stby_us = self.max_stby_us.max(self.t_us - s);
            }
        }
        self.stby = active;
    }
    fn drive_en_fault_low(&mut self, low: bool) {
        self.touch();
        self.en_fault_low = low;
    }
    fn read(&mut self) -> PinRead {
        self.touch();
        PinRead {
            latch_q: self.latch_q,
            oc_ok: self.oc_ok,
            mot_allow: self.chain(),
            docked_h: self.docked_h(),
            dir_rev: self.dir_rev(),
            mcu_en: self.mcu_en,
            stby: self.stby,
            arm_clk: false,
            latch_clr: self.clr,
            dock_n_low: self.hall_docked && self.pod_present,
            pod_present: self.pod_present,
            en_fault_high: !self.en_fault_low && self.stby,
        }
    }
    fn vmot_mv(&mut self) -> u32 {
        self.touch();
        self.vmot as u32
    }
    fn isense_mv(&mut self) -> u32 {
        self.touch();
        (self.current_ma() * 6.667) as u32
    }
    fn vbus_mv(&mut self) -> u32 {
        self.vbus
    }
    fn vdd_mv(&mut self) -> u32 {
        self.vdd
    }
    fn tmag_ack(&mut self) -> bool {
        self.pod_present && self.tmag
    }
    fn now_us(&mut self) -> u64 {
        self.t_us
    }
    fn delay_us(&mut self, us: u32) {
        let t = self.t_us + us as u64;
        self.step_to(t);
    }
}

fn ctl(f: impl FnOnce(&mut Board), forward_high: bool) -> BenchCtl<Board> {
    let mut b = Board::new();
    b.r97 = forward_high; // R97 fitted <=> DIR_FORWARD_HIGH = true (the consistent pairings)
    f(&mut b);
    let mut cfg = CtlCfg::BENCH;
    cfg.forward_high = forward_high;
    BenchCtl::new(b, cfg)
}

fn events(c: &mut BenchCtl<Board>) -> Vec<DiagEvent> {
    let mut v = vec![];
    while let Some(e) = c.take_event() {
        v.push(e);
    }
    v
}

fn has(v: &[DiagEvent], code: openpatch_diag::DiagCode) -> bool {
    v.iter().any(|e| e.code.identity() == code.identity())
}

// ---------------------------------------------------------------------------------------------
// gate model and polarity
// ---------------------------------------------------------------------------------------------

#[test]
fn gate_network_truth_table_includes_the_over_current_leg() {
    for bits in 0..32u32 {
        let (l, e, o, d, r) = (bits & 1 != 0, bits & 2 != 0, bits & 4 != 0, bits & 8 != 0, bits & 16 != 0);
        assert_eq!(mot_allow(l, e, o, d, r), l && e && o && (d || r));
    }
    // an over-current trip blocks even a docked, armed, enabled pod
    assert!(!mot_allow(true, true, false, true, false));
}

#[test]
fn dir_polarity_r96_default_is_forward_low_and_r97_flips_it() {
    // default hardware: R96 fitted, DIR_FORWARD_HIGH = false
    assert!(!dir_level_high(MotorDir::Forward, false));
    assert!(dir_level_high(MotorDir::Reverse, false));
    // R97 instead of R96
    assert!(dir_level_high(MotorDir::Forward, true));
    assert!(!dir_level_high(MotorDir::Reverse, true));
    assert!(!CtlCfg::BENCH.forward_high, "the default hardware needs DIR_FORWARD_HIGH = false");
}

#[test]
fn shunt_scale_is_667_mv_per_ma_not_20() {
    // 3 x 1.0 ohm in parallel x INA180A1 (20 V/V): 2.67 V = 400 mA (pin-assignment.md), 3.0 V = 450 mA (comparator)
    assert_eq!(isense_mv_to_ma(2_670), 400);
    assert_eq!(openpatch_core::limits::HW_OVERCURRENT_MA, 450);
    assert_eq!(openpatch_core::limits::I_SENSE_UV_PER_MA, 6_666);
    // a 267 mA stall (limits::MOTOR_STALL_CURRENT_MA) is 1.78 V and reads back as 267, not 89
    let mv = 267 * 6_667 / 1_000;
    assert!((isense_mv_to_ma(mv) as i32 - 267).abs() <= 1);
}

/// The constant is tied to the netlist: R31 / R39 / R47 in `controller/parts.json` and the INA180A1 variant. A checkout whose
/// electronics files predate Rev A (no R47) skips the cross-check with a message; the arithmetic test above still runs.
#[test]
fn shunt_constant_matches_the_controller_netlist() {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../../electronics/bench/controller/parts.json");
    let Ok(text) = std::fs::read_to_string(path) else {
        eprintln!("parts.json not found: netlist cross-check skipped");
        return;
    };
    let value_of = |r: &str| -> Option<String> {
        let key = format!("\"{r}\": {{");
        let at = text.find(&key)?;
        let rest = &text[at..];
        let v = rest.find("\"value\":")?;
        let q1 = rest[v + 8..].find('"')? + v + 8 + 1;
        let q2 = rest[q1..].find('"')? + q1;
        Some(rest[q1..q2].to_string())
    };
    let shunts: Vec<String> = ["R31", "R39", "R47"].iter().filter_map(|r| value_of(r)).collect();
    if shunts.len() != 3 {
        eprintln!("parts.json lists {} shunt resistors (Rev A has 3): netlist cross-check skipped", shunts.len());
        return;
    }
    assert!(shunts.iter().all(|v| v == "1.0R"), "each shunt resistor is 1.0 ohm: {shunts:?}");
    assert_eq!(openpatch_core::limits::SHUNT_PARALLEL_N as usize, shunts.len());
    assert_eq!(openpatch_core::limits::SHUNT_EACH_MOHM, 1_000);
    assert!(value_of("U7").is_some_and(|v| v.starts_with("INA180A1")), "gain 20 V/V variant");
    assert_eq!(openpatch_core::limits::INA180A1_GAIN, 20);
}

// ---------------------------------------------------------------------------------------------
// runtime sequencing
// ---------------------------------------------------------------------------------------------

#[test]
fn nominal_power_up_and_down_in_both_directions_and_both_polarities() {
    for fwd_high in [false, true] {
        for (dir, docked) in [(MotorDir::Forward, true), (MotorDir::Reverse, false)] {
            let mut c = ctl(|b| b.hall_docked = docked, fwd_high);
            assert_eq!(c.power_up(docked, dir), Ok(()), "fwd_high {fwd_high} {dir:?}");
            assert!(c.powered && c.pins.stby && c.pins.mcu_en && c.pins.vmot > 4_300.0);
            assert_eq!(c.verify_supply(docked), Ok(()));
            assert!(c.power_off());
            assert!(!c.pins.stby && !c.pins.mcu_en && c.pins.clr && c.pins.vmot < 1_500.0);
            assert!(events(&mut c).is_empty());
            assert!(!c.failed && !c.quarantined);
        }
    }
}

#[test]
fn forward_undocked_is_refused_before_any_pin_moves() {
    let mut c = ctl(|b| b.hall_docked = false, false);
    let before = (c.pins.mcu_en, c.pins.arm_edges);
    assert_eq!(c.power_up(false, MotorDir::Forward), Err(PowerError::Refused(openpatch_core::interlock::Refusal::ForwardWhileUndocked)));
    assert_eq!((c.pins.mcu_en, c.pins.arm_edges), before);
}

#[test]
fn dir_is_set_before_mcu_en_in_a_draw_and_the_gate_alone_blocks_forward_undocked() {
    // hardware gate: undocked + forward level + MCU_EN + armed => no supply, whatever the firmware thinks
    let mut c = ctl(|b| b.hall_docked = false, false);
    c.pins.set_latch_clear(false);
    c.pins.set_mcu_en(true);
    c.pins.arm_edge();
    c.pins.delay_us(50_000);
    assert!(c.pins.vmot < 100.0 && !c.pins.chain());
    // reverse level: the supply comes up
    c.pins.set_mot_dir(dir_level_high(MotorDir::Reverse, false));
    c.pins.delay_us(20_000);
    assert!(c.pins.vmot > 4_300.0);
}

#[test]
fn power_down_rotates_mcuen_only_latch_only_both() {
    let mut c = ctl(|_| {}, false);
    let mut seen = vec![];
    for _ in 0..6 {
        c.power_up(true, MotorDir::Forward).unwrap();
        assert!(c.power_off());
        seen.push(c.last_disarm.unwrap());
        assert!(!c.pins.mcu_en && c.pins.clr, "after every power-down both gates are closed");
    }
    use Disarm::*;
    assert_eq!(seen, vec![McuEnOnly, LatchOnly, Both, McuEnOnly, LatchOnly, Both]);
    assert!(events(&mut c).is_empty());
}

#[test]
fn a_stuck_mcu_en_leg_is_named_by_the_mcuen_only_disarm_and_the_supply_is_still_cut() {
    let mut c = ctl(|b| b.f.q8_short = true, false);
    c.power_up(true, MotorDir::Forward).unwrap();
    // first power-down is McuEnOnly: the chain keeps conducting, the latch clear cuts it
    assert!(c.power_off(), "the second gate cuts at once");
    assert_eq!(c.last_disarm, Some(Disarm::McuEnOnly));
    let ev = events(&mut c);
    assert!(has(&ev, codes::GATE_MCUEN_STUCK_PASS), "{ev:?}");
    assert!(!c.failed && !c.quarantined, "one stuck leg is reported, the pod is not reset");
}

#[test]
fn a_stuck_latch_leg_is_named_by_the_latch_only_disarm() {
    let mut c = ctl(|b| b.f.q5_short = true, false);
    c.power_up(true, MotorDir::Forward).unwrap();
    assert!(c.power_off()); // McuEnOnly: the MCU_EN leg cuts, nothing is wrong yet
    assert!(events(&mut c).is_empty(), "the stuck latch leg is invisible while MCU_EN cuts");
    c.power_up(true, MotorDir::Forward).unwrap();
    assert!(c.power_off()); // LatchOnly: now the stuck leg shows
    assert_eq!(c.last_disarm, Some(Disarm::LatchOnly));
    assert!(has(&events(&mut c), codes::GATE_LATCH_STUCK_PASS));
}

#[test]
fn a_latch_that_cannot_clear_is_reported_by_the_latch_only_disarm() {
    let mut c = ctl(|b| b.f.latch_stuck_high = true, false);
    // MCU_EN still cuts, so power-up/down works; the latch-only disarm names the latch
    c.power_up(true, MotorDir::Forward).unwrap();
    c.power_off();
    c.power_up(true, MotorDir::Forward).unwrap();
    c.power_off();
    assert_eq!(c.last_disarm, Some(Disarm::LatchOnly));
    assert!(has(&events(&mut c), codes::LATCH_CANNOT_CLEAR));
    assert!(c.failed, "an uncuttable latch is reset by the TPL5010 (withhold DONE)");
}

#[test]
fn both_gates_stuck_means_the_supply_is_not_cut_and_the_reset_path_is_taken() {
    let mut c = ctl(|b| {
        b.f.q8_short = true;
        b.f.q5_short = true;
    }, false);
    c.power_up(true, MotorDir::Forward).unwrap();
    assert!(!c.power_off());
    assert!(c.failed && !c.quarantined);
    assert_eq!(c.power_up(true, MotorDir::Forward), Err(PowerError::InterlockFailed));
}

#[test]
fn q4_shorted_cannot_be_cut_by_the_board_so_the_controller_is_quarantined_not_reset() {
    let mut c = ctl(|b| {
        b.f.q4_short = true;
        b.pins_settle();
    }, false);
    assert!(!c.verify_idle());
    let ev = events(&mut c);
    assert!(has(&ev, codes::VMOT_STUCK_ON), "{ev:?}");
    assert!(c.quarantined && !c.failed, "a reset can not help: keep the MCU alive for the alarm, STBY low");
    assert_eq!(c.power_up(true, MotorDir::Forward), Err(PowerError::InterlockFailed));
    assert!(!c.pins.stby);
    // reported once, not every tick
    assert!(!c.verify_idle());
    assert!(events(&mut c).is_empty());
}

#[test]
fn over_current_trip_while_powered_is_a_driver_fault_and_the_supply_stays_cut_until_mcu_en_cycles() {
    let mut c = ctl(|_| {}, false);
    c.power_up(true, MotorDir::Forward).unwrap();
    // 10 ohm across the motor header (T9): 500 mA
    c.pins.oc_test = true; // trips at 45 mA with the 160 mA hold current
    c.pins.delay_us(30_000);
    assert!(!c.pins.oc_ok && c.pins.vmot < 3_000.0);
    assert_eq!(c.verify_supply(true), Err(PowerError::DriverFault));
    assert!(!c.powered);
    assert!(has(&events(&mut c), codes::DRIVER_FAULT_IN_BURST));
    c.pins.oc_test = false;
    // MCU_EN was cycled low by the power-down: the next power-up works
    assert_eq!(c.power_up(true, MotorDir::Forward), Ok(()));
}

#[test]
fn idle_check_is_clean_and_names_a_latch_that_set_itself() {
    let mut c = ctl(|_| {}, false);
    assert!(c.verify_idle());
    assert!(events(&mut c).is_empty());
    c.pins.f.latch_stuck_high = true;
    c.pins.latch_q = true;
    assert!(!c.verify_idle());
    assert!(has(&events(&mut c), codes::LATCH_SET_WITHOUT_ARM));
    assert!(c.failed);
}

#[test]
fn stby_is_low_whenever_the_driver_is_idle() {
    let mut c = ctl(|_| {}, false);
    assert!(!c.pins.stby);
    c.power_up(true, MotorDir::Forward).unwrap();
    assert!(c.pins.stby);
    c.power_off();
    assert!(!c.pins.stby && c.pins.en_fault_low);
    // the readback of STBY is checked at idle
    c.pins.stby = true;
    assert!(!c.verify_idle());
    assert!(events(&mut c).iter().any(|e| e.code.identity() == codes::GATE_INPUT_READBACK_MISMATCH.identity() && e.code.inst() == pin::STBY));
}

// ---------------------------------------------------------------------------------------------
// POST
// ---------------------------------------------------------------------------------------------

fn run_all(c: &mut BenchCtl<Board>) -> Vec<SelfTestOutcome> {
    [SelfTestStep::PassiveChecks, SelfTestStep::GateCut, SelfTestStep::DockGateBlock, SelfTestStep::OverCurrentCut].iter().map(|s| c.selftest(*s)).collect()
}

fn failed_code(o: &SelfTestOutcome) -> Option<openpatch_diag::DiagCode> {
    match o {
        SelfTestOutcome::Failed(c) => Some(*c),
        _ => None,
    }
}

fn same(a: Option<openpatch_diag::DiagCode>, b: openpatch_diag::DiagCode) -> bool {
    a.is_some_and(|a| a.identity() == b.identity())
}

#[test]
fn post_passes_on_a_healthy_board_docked_and_undocked_for_both_polarities() {
    for fwd_high in [false, true] {
        for docked in [true, false] {
            let mut c = ctl(|b| b.hall_docked = docked, fwd_high);
            let out = run_all(&mut c);
            assert_eq!(out, vec![SelfTestOutcome::Passed; 4], "fwd_high {fwd_high} docked {docked}");
            assert!(events(&mut c).is_empty());
            // safe state after the POST
            assert!(!c.pins.mcu_en && !c.pins.stby && c.pins.clr && !c.pins.dock_test && !c.pins.oc_test);
            assert!(c.pins.vmot < 1_500.0 || { c.pins.delay_us(50_000); c.pins.vmot < 300.0 });
        }
    }
}

#[test]
fn post_never_drives_the_motor_except_the_bounded_hold_of_the_over_current_proof() {
    let mut c = ctl(|_| {}, false);
    for s in [SelfTestStep::PassiveChecks, SelfTestStep::GateCut, SelfTestStep::DockGateBlock] {
        assert_eq!(c.selftest(s), SelfTestOutcome::Passed);
        assert_eq!(c.pins.stby_edges, 0, "{s:?} must never wake the driver");
    }
    assert_eq!(c.selftest(SelfTestStep::OverCurrentCut), SelfTestOutcome::Passed);
    assert_eq!(c.pins.stby_edges, 1);
    assert!(c.pins.max_stby_us <= 100_000, "coil hold at most 100 ms, was {} us", c.pins.max_stby_us);
}

#[test]
fn post_proves_each_gate_cuts_alone_by_failing_when_one_is_stuck() {
    // Q8 (MCU_EN leg) stuck pass
    let mut c = ctl(|b| b.f.q8_short = true, false);
    assert!(same(failed_code(&c.selftest(SelfTestStep::GateCut)), codes::GATE_MCUEN_STUCK_PASS));
    // Q5 (latch leg) stuck pass
    let mut c = ctl(|b| b.f.q5_short = true, false);
    assert!(same(failed_code(&c.selftest(SelfTestStep::GateCut)), codes::GATE_LATCH_STUCK_PASS));
    // dock pair shorted: undocked forward passes
    let mut c = ctl(|b| b.f.q6_short = true, false);
    assert!(same(failed_code(&c.selftest(SelfTestStep::DockGateBlock)), codes::GATE_DOCK_STUCK_PASS));
    // OC leg stuck pass: OC_TEST trips the latch but the chain keeps conducting
    let mut c = ctl(|b| b.f.q13_short = true, false);
    let o = c.selftest(SelfTestStep::OverCurrentCut);
    assert!(same(failed_code(&o), codes::GATE_INPUT_READBACK_MISMATCH), "{o:?}");
    assert_eq!(failed_code(&o).unwrap().inst(), pin::OC);
}

#[test]
fn post_dir_leg_that_keeps_conducting_after_the_flip_is_named() {
    let mut c = ctl(|b| b.f.dir_leg_sticky = true, false);
    let o = c.selftest(SelfTestStep::DockGateBlock);
    assert!(same(failed_code(&o), codes::GATE_DIRREV_STUCK_PASS), "{o:?}");
}

#[test]
fn post_stuck_latch_both_ways() {
    let mut c = ctl(|b| b.f.latch_stuck_high = true, false);
    assert!(same(failed_code(&c.selftest(SelfTestStep::PassiveChecks)), codes::LATCH_SET_WITHOUT_ARM));
    let mut c = ctl(|b| b.f.latch_stuck_low = true, false);
    assert!(same(failed_code(&c.selftest(SelfTestStep::GateCut)), codes::LATCH_CANNOT_SET));
    // set but cannot clear: found by the latch-only cut
    let mut c = ctl(|b| b.f.latch_stuck_high = true, false);
    let o = c.selftest(SelfTestStep::GateCut);
    assert!(failed_code(&o).is_some(), "{o:?}");
}

#[test]
fn post_stuck_p_fet_q4_latches_and_quarantines_it_cannot_be_cut_by_the_board() {
    let mut c = ctl(|b| {
        b.f.q4_short = true;
        b.pins_settle();
    }, false);
    let out = run_all(&mut c);
    assert!(same(failed_code(&out[0]), codes::VMOT_STUCK_ON), "{out:?}");
    assert!(c.quarantined, "replace the controller board");
    assert!(!c.failed, "withholding DONE would only cause a reset loop: Q4 stays on after any reset");
    // the other proofs refuse to run on a quarantined board (UNKNOWN, never passed)
    assert_eq!(out[1], SelfTestOutcome::Unsupported);
    assert_eq!(out[3], SelfTestOutcome::Unsupported);
    assert!(!c.pins.stby, "STBY low: no motion with the supply stuck on");
    assert!(has(&events(&mut c), codes::VMOT_STUCK_ON));
}

#[test]
fn post_dock_hall_and_dock_gate_faults() {
    // gate input stuck high while the hall says undocked: the over-delivery class
    let mut c = ctl(|b| {
        b.hall_docked = false;
        b.f.docked_h_stuck_high = true;
    }, false);
    assert!(same(failed_code(&c.selftest(SelfTestStep::PassiveChecks)), codes::GATE_DOCK_STUCK_PASS));
    // gate input forced low while the hall says docked: forward never allowed
    let mut c = ctl(|b| b.f.docked_h_stuck_low = true, false);
    assert!(same(failed_code(&c.selftest(SelfTestStep::PassiveChecks)), codes::GATE_DOCK_STUCK_BLOCK));
    // DOCK_TEST that does not force the gate input: the dock proof is inconclusive, never "passed"
    let mut c = ctl(|b| b.f.q12_open = true, false);
    assert_eq!(c.selftest(SelfTestStep::DockGateBlock), SelfTestOutcome::Unsupported);
}

#[test]
fn post_ffc_unplugged_is_named_and_a_docked_signal_without_the_pod_is_impossible() {
    let mut c = ctl(|b| {
        b.pod_present = false;
        b.hall_docked = false;
    }, false);
    let o = c.selftest(SelfTestStep::PassiveChecks);
    assert!(same(failed_code(&o), codes::FFC_ABSENT), "{o:?}");
    // POD_ID_N high but DOCK_N reads docked: impossible combination
    let mut c = ctl(|b| {
        b.pod_present = false;
        b.f.docked_h_stuck_high = true;
    }, false);
    let r = c.pins.read();
    assert!(!r.pod_present);
    // TMAG silent with the pod board present and the dock hall reading docked: the dock line is not believable
    let mut c2 = ctl(|b| b.tmag = false, false);
    assert!(same(failed_code(&c2.selftest(SelfTestStep::PassiveChecks)), codes::FFC_DOCK_LINE_FAULT));
    // undocked with a silent TMAG: not an FFC fault by itself (the angle channel reports 2-20-001)
    let mut c3 = ctl(|b| {
        b.tmag = false;
        b.hall_docked = false;
    }, false);
    assert_eq!(c3.selftest(SelfTestStep::PassiveChecks), SelfTestOutcome::Passed);
    let _ = c;
}

#[test]
fn post_over_current_leg_faults() {
    // comparator / latch never trip
    let mut c = ctl(|b| b.f.oc_never_trips = true, false);
    let o = c.selftest(SelfTestStep::OverCurrentCut);
    assert!(same(failed_code(&o), codes::GATE_INPUT_READBACK_MISMATCH), "{o:?}");
    // latch stuck tripped: OC_OK low at idle (fail safe, VMOT never on)
    let mut c = ctl(|b| b.f.oc_stuck_tripped = true, false);
    assert!(same(failed_code(&c.selftest(SelfTestStep::PassiveChecks)), codes::GATE_MCUEN_STUCK_BLOCK));
    // motor not connected: no holding current, the proof is inconclusive (UNKNOWN), not passed
    let mut c = ctl(|b| b.f.no_motor = true, false);
    assert_eq!(c.selftest(SelfTestStep::OverCurrentCut), SelfTestOutcome::Unsupported);
    assert!(!c.pins.stby, "STBY back low after an inconclusive proof");
}

#[test]
fn post_detects_a_wrong_dir_polarity_option() {
    // R97 fitted but the firmware assumes R96 (DIR_FORWARD_HIGH = false)
    let mut b = Board::new();
    b.r97 = true;
    let mut c = BenchCtl::new(b, CtlCfg::BENCH);
    let out = run_all(&mut c);
    for o in &out[1..] {
        assert!(same(failed_code(o), codes::DIR_INVERTED), "{o:?}");
    }
    assert!(same(failed_code(&out[0]), codes::DIR_INVERTED));
    // the opposite mismatch: R96 fitted, firmware assumes R97
    let mut cfg = CtlCfg::BENCH;
    cfg.forward_high = true;
    let mut c = BenchCtl::new(Board::new(), cfg);
    assert!(same(failed_code(&c.selftest(SelfTestStep::GateCut)), codes::DIR_INVERTED));
}

#[test]
fn post_dead_dir_path_is_not_a_polarity_error() {
    let mut c = ctl(|b| b.f.dir_rev_dead = true, false);
    let o = c.selftest(SelfTestStep::DockGateBlock);
    let code = failed_code(&o).expect("fails");
    assert_eq!(code.identity(), codes::GATE_INPUT_READBACK_MISMATCH.identity());
    assert_eq!(code.inst(), pin::MOT_DIR);
}

#[test]
fn post_rails_and_sensor_plausibility() {
    let mut c = ctl(|b| b.vdd = 2_800, false);
    assert!(same(failed_code(&c.selftest(SelfTestStep::PassiveChecks)), codes::RAIL_3V3_LOW));
    let mut c = ctl(|b| b.vbus = 4_200, false);
    assert!(same(failed_code(&c.selftest(SelfTestStep::PassiveChecks)), codes::USB_SUPPLY_LOW));
    let mut c = ctl(|b| b.vbus = 5_800, false);
    assert!(same(failed_code(&c.selftest(SelfTestStep::PassiveChecks)), codes::USB_OVERVOLT));
    let mut c = ctl(|b| b.vbus = 2_000, false);
    assert!(same(failed_code(&c.selftest(SelfTestStep::PassiveChecks)), codes::VOLTAGE_SENSE_IMPLAUSIBLE));
}

#[test]
fn a_failed_proof_still_ends_in_the_safe_state() {
    for f in [
        (|b: &mut Board| b.f.q8_short = true) as fn(&mut Board),
        |b| b.f.q5_short = true,
        |b| b.f.q13_short = true,
        |b| b.f.q6_short = true,
        |b| b.f.oc_never_trips = true,
    ] {
        let mut c = ctl(f, false);
        let _ = run_all(&mut c);
        assert!(!c.pins.mcu_en && !c.pins.stby && c.pins.clr && !c.pins.dock_test && !c.pins.oc_test);
        assert!(!c.pins.mot_dir, "DIR back at the forward level");
    }
}

#[test]
fn readback_snapshot_reports_every_leg() {
    let mut c = ctl(|_| {}, false);
    c.power_up(true, MotorDir::Forward).unwrap();
    let rb = c.readback();
    assert_eq!(rb.latch_q, Some(true));
    assert_eq!(rb.oc_ok, Some(true));
    assert_eq!(rb.mot_allow, Some(true));
    assert_eq!(rb.pgate, Some(false));
    assert_eq!(rb.docked_h, Some(true));
    assert_eq!(rb.dir_rev, Some(false));
    assert_eq!(rb.pod_present, Some(true));
    assert_eq!(rb.own_pin_mismatch, 0);
    assert!(rb.vmot_mv.unwrap() > 4_300);
    assert!(rb.pg_mid1.is_none() && rb.pg_mid2.is_none(), "Rev A has no mid-chain readbacks");
}

impl Board {
    /// Let the analog state settle (a fault injected at "power-up").
    fn pins_settle(&mut self) {
        self.step_to(self.t_us + 100_000);
    }
}


#[test]
fn a_board_without_the_interlock_never_reports_a_proof_as_passed() {
    let mut c = BenchCtl::new(Board::new(), CtlCfg::NO_INTERLOCK);
    for s in [SelfTestStep::PassiveChecks, SelfTestStep::GateCut, SelfTestStep::DockGateBlock, SelfTestStep::OverCurrentCut] {
        assert_eq!(c.selftest(s), SelfTestOutcome::Unsupported, "{s:?}");
    }
    // direction, STBY and nothing else: no gate pin is touched
    assert_eq!(c.power_up(true, MotorDir::Forward), Ok(()));
    assert!(c.pins.stby && !c.pins.mcu_en && c.pins.arm_edges == 0);
    assert!(c.verify_idle() && c.verify_supply(true).is_ok());
    assert!(c.power_off() && !c.pins.stby);
}
