//! Electrical model of the Rev A bench controller's interlock network (`electronics/bench/INTERLOCK.md`) with fault
//! injection, and [`SimPins`]: the `openpatch_core::bench_ctl::BenchPins` implementation over the shared [`World`]. The
//! core's POST and sequencing (`BenchCtl`) therefore run unchanged against this model, exactly as they run on the target.
//!
//! `MOT_ALLOW = MCU_EN AND LATCH_Q AND OC_OK AND (DOCKED_H XOR DIR_REV)`, `VMOT = USB 5 V` through the P-FET Q4 while
//! `MOT_ALLOW`. The model is analog only where the proofs need it: VMOT ramps up (tau 1 ms) and bleeds down (tau 10 ms,
//! R101), the over-current latch arms 12 ms after `MCU_EN` rises and trips above 450 mA (45 mA with `OC_TEST`), and is
//! cleared only by `MCU_EN` low.
//!
//! The pod battery model of the rest of the simulator is not touched: a bench controller runs from USB, so `VBUS` is a
//! parameter here (`BoardModel::vbus_mv`).

use crate::world::World;
use openpatch_core::bench_ctl::{BenchPins, PinRead};
use openpatch_core::hal::DiagEvent;
use serde::{Deserialize, Serialize};
use std::cell::RefCell;
use std::collections::VecDeque;
use std::rc::Rc;

/// Hardware faults of the interlock board (single-fault injection).
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct BoardFaults {
    /// Q4 (P-FET) drain-source short: the supply can not be cut by the board.
    pub q4_short: bool,
    pub q4_open: bool,
    /// Q8 (MCU_EN leg) shorted: conducts although `MCU_EN` is low.
    pub q8_short: bool,
    /// Q5 (latch leg) shorted.
    pub q5_short: bool,
    /// Q13 (over-current leg) shorted.
    pub q13_short: bool,
    /// Q6 (dock leg) shorted: the `Q6 || Q10` pair always conducts.
    pub q6_short: bool,
    /// Q10 shorted: the pair also conducts for docked + reverse (the XOR of H14 is lost).
    pub q10_short: bool,
    /// The DIR leg keeps conducting after DIR was reverse until `MCU_EN` is cycled low.
    pub dir_leg_sticky: bool,
    pub latch_stuck_high: bool,
    pub latch_stuck_low: bool,
    /// Comparator / over-current latch never trip.
    pub oc_never_trips: bool,
    /// Over-current latch stuck tripped (`OC_OK` low).
    pub oc_stuck_tripped: bool,
    /// `DOCKED_H` stuck high (Q7 off): the gate believes "docked".
    pub docked_h_stuck_high: bool,
    /// `DOCKED_H` forced low always (Q12 on).
    pub docked_h_stuck_low: bool,
    /// `DOCK_TEST` has no effect (Q12 open).
    pub q12_open: bool,
    /// Motor not connected: no holding current.
    pub no_motor: bool,
    /// The `DIR_REV` node does not follow `MOT_DIR` (dead path, stays low).
    pub dir_rev_dead: bool,
    /// The FFC is unplugged: `POD_ID_N` high, `DOCK_N` pulled up (undocked), TMAG does not answer.
    pub ffc_unplugged: bool,
}

impl BoardFaults {
    /// Set a fault by name (scenario action). Names are the field names.
    pub fn set(&mut self, name: &str, on: bool) -> Result<(), String> {
        match name {
            "q4_short" => self.q4_short = on,
            "q4_open" => self.q4_open = on,
            "q8_short" => self.q8_short = on,
            "q5_short" => self.q5_short = on,
            "q13_short" => self.q13_short = on,
            "q6_short" => self.q6_short = on,
            "q10_short" => self.q10_short = on,
            "dir_leg_sticky" => self.dir_leg_sticky = on,
            "latch_stuck_high" => self.latch_stuck_high = on,
            "latch_stuck_low" => self.latch_stuck_low = on,
            "oc_never_trips" => self.oc_never_trips = on,
            "oc_stuck_tripped" => self.oc_stuck_tripped = on,
            "docked_h_stuck_high" => self.docked_h_stuck_high = on,
            "docked_h_stuck_low" => self.docked_h_stuck_low = on,
            "q12_open" => self.q12_open = on,
            "no_motor" => self.no_motor = on,
            "dir_rev_dead" => self.dir_rev_dead = on,
            "ffc_unplugged" => self.ffc_unplugged = on,
            other => return Err(format!("unknown board fault {other:?}")),
        }
        Ok(())
    }
}

/// The analog and fault state of the interlock board. The digital state shared with the rest of the simulator
/// (`mcu_en`, `latch_q`, `dir_reverse`, the dock hall) stays in [`World`].
#[derive(Clone, Debug)]
pub struct BoardModel {
    pub f: BoardFaults,
    pub dock_test: bool,
    pub oc_test: bool,
    pub stby: bool,
    pub en_fault_low: bool,
    /// `LATCH_CLR_N` is held low (latch cleared). Idle state.
    pub clr_asserted: bool,
    /// `MOT_DIR` pin level (the gate level `World::dir_reverse` follows it through the R96 / R97 option).
    pub mot_dir_high: bool,
    /// R97 fitted instead of R96 (DIR_REV is the inverse of MOT_DIR).
    pub r97_fitted: bool,
    pub oc_ok: bool,
    mcu_en_prev: bool,
    mcu_en_rise_us: Option<u64>,
    dir_seen_reverse: bool,
    pub vmot_mv: f64,
    last_us: u64,
    /// USB 5 V (`VBUS_SENSE` x 2 divider reading) and the 3V3 rail.
    pub vbus_mv: u32,
    pub vdd_mv: u32,
    /// Motor holding current with both phases at the chopper limit (mA).
    pub hold_ma: f64,
    /// Controller state that survives between self-tests (the controller itself is rebuilt per call).
    pub quarantined: bool,
    pub failed: bool,
    pub events: VecDeque<DiagEvent>,
}

impl Default for BoardModel {
    fn default() -> Self {
        BoardModel {
            f: BoardFaults::default(),
            dock_test: false,
            oc_test: false,
            stby: false,
            en_fault_low: true,
            clr_asserted: true,
            mot_dir_high: false,
            r97_fitted: false,
            oc_ok: true,
            mcu_en_prev: false,
            mcu_en_rise_us: None,
            dir_seen_reverse: false,
            vmot_mv: 0.0,
            last_us: 0,
            vbus_mv: 4_950,
            vdd_mv: 3_300,
            hold_ma: openpatch_core::limits::MOTOR_RUN_CURRENT_MA as f64,
            quarantined: false,
            failed: false,
            events: VecDeque::new(),
        }
    }
}

impl World {
    /// The dock hall as the interlock gate sees it (`DOCKED_H`): Q7 inverts `DOCK_N`, Q12 (`DOCK_TEST`) pulls it low.
    pub fn docked_h(&self) -> bool {
        let b = &self.board;
        if b.f.docked_h_stuck_high {
            return true;
        }
        if b.f.docked_h_stuck_low {
            return false;
        }
        self.docked_hw() && !(b.dock_test && !b.f.q12_open)
    }

    /// The reverse-direction leg input (`DIR_REV`): `MOT_DIR` through R96, or its inverse through Q11 / R97.
    pub fn dir_rev_gate(&self) -> bool {
        if self.board.f.dir_rev_dead {
            return false;
        }
        self.dir_reverse
    }

    /// The latch output as the gate sees it.
    pub fn latch_eff(&self) -> bool {
        self.latch_q || self.board.f.latch_stuck_high
    }

    /// The series chain conducts (`PGATE_MON` low), faults included.
    pub fn chain(&self) -> bool {
        let b = &self.board;
        let latch = self.latch_eff() && !b.f.latch_stuck_low || b.f.q5_short;
        let en = self.mcu_en || b.f.q8_short;
        let oc = b.oc_ok || b.f.q13_short;
        let dir_leg = self.dir_rev_gate() || (b.f.dir_leg_sticky && b.dir_seen_reverse && self.mcu_en);
        let pair = (self.docked_h() != dir_leg) || b.f.q6_short || b.f.q10_short;
        self.power_on && latch && en && oc && pair
    }

    /// The P-FET is on.
    pub fn switch_on(&self) -> bool {
        self.power_on && ((self.chain() && !self.board.f.q4_open) || self.board.f.q4_short)
    }

    /// Supply current seen by `I_SENSE` (mA): coil holding current while the driver is awake with the supply up.
    pub fn board_current_ma(&self) -> f64 {
        let b = &self.board;
        if b.stby && !b.f.no_motor && !b.en_fault_low && b.vmot_mv > 3_000.0 {
            b.hold_ma
        } else {
            0.0
        }
    }

    /// Advance the analog state of the board to the current time. Cheap: called from the world clock.
    pub fn board_step(&mut self) {
        let now = self.t_us;
        let dt = now.saturating_sub(self.board.last_us) as f64;
        // MCU_EN edges: low clears the over-current latch at once, a rise arms it 12 ms later
        let en = self.mcu_en;
        if en && !self.board.mcu_en_prev {
            self.board.mcu_en_rise_us = Some(now);
        }
        if !en {
            self.board.mcu_en_rise_us = None;
            if !self.board.f.oc_stuck_tripped {
                self.board.oc_ok = true;
            }
            self.board.dir_seen_reverse = false;
        }
        self.board.mcu_en_prev = en;
        if self.board.f.oc_stuck_tripped {
            self.board.oc_ok = false;
        }
        if dt > 0.0 {
            let target = if self.switch_on() { self.board.vbus_mv as f64 } else { 0.0 };
            if target > self.board.vmot_mv {
                self.board.vmot_mv = target - (target - self.board.vmot_mv) * (-dt / 1_000.0).exp();
            } else if target < self.board.vmot_mv {
                // bleeder R101 and the motor: tau about 10 ms
                self.board.vmot_mv = target + (self.board.vmot_mv - target) * (-dt / 10_000.0).exp();
            }
        }
        // over-current comparator + latch
        let armed = self.board.mcu_en_rise_us.is_some_and(|r| now >= r + 12_000);
        let thr = if self.board.oc_test { 45.0 } else { 450.0 };
        if armed && en && self.board_current_ma() > thr && !self.board.f.oc_never_trips {
            self.board.oc_ok = false;
        }
        if en && self.dir_rev_gate() {
            self.board.dir_seen_reverse = true;
        }
        self.board.last_us = now;
    }
}

/// `BenchPins` over the shared world. Every call first brings the analog state up to date.
pub struct SimPins(pub Rc<RefCell<World>>);

impl SimPins {
    fn with<R>(&self, f: impl FnOnce(&mut World) -> R) -> R {
        let mut w = self.0.borrow_mut();
        w.board_step();
        let r = f(&mut w);
        w.board_step();
        r
    }
}

impl BenchPins for SimPins {
    fn set_mot_dir(&mut self, high: bool) {
        self.with(|w| {
            w.board.mot_dir_high = high;
            w.dir_reverse = high != w.board.r97_fitted;
        });
    }
    fn set_mcu_en(&mut self, high: bool) {
        self.with(|w| w.mcu_en = high && w.power_on);
    }
    fn arm_edge(&mut self) {
        self.with(|w| {
            if !w.board.clr_asserted && !w.board.f.latch_stuck_low && w.power_on {
                w.latch_q = true;
            }
        });
    }
    fn set_latch_clear(&mut self, asserted: bool) {
        self.with(|w| {
            w.board.clr_asserted = asserted;
            if asserted && !w.board.f.latch_stuck_high {
                w.latch_q = false;
            }
        });
    }
    fn set_dock_test(&mut self, on: bool) {
        self.with(|w| w.board.dock_test = on);
    }
    fn set_oc_test(&mut self, on: bool) {
        self.with(|w| w.board.oc_test = on);
    }
    fn set_stby(&mut self, active: bool) {
        self.with(|w| w.board.stby = active);
    }
    fn drive_en_fault_low(&mut self, low: bool) {
        self.with(|w| w.board.en_fault_low = low);
    }
    fn read(&mut self) -> PinRead {
        self.with(|w| {
            let ffc = w.board.f.ffc_unplugged;
            PinRead {
                latch_q: w.latch_eff() && !w.board.f.latch_stuck_low,
                oc_ok: w.board.oc_ok,
                mot_allow: w.chain(),
                docked_h: w.docked_h(),
                dir_rev: w.dir_rev_gate(),
                mcu_en: w.mcu_en,
                stby: w.board.stby,
                arm_clk: false,
                latch_clr: w.board.clr_asserted,
                dock_n_low: w.docked_hw() && !ffc,
                pod_present: !ffc,
                en_fault_high: !w.board.en_fault_low && w.board.stby,
            }
        })
    }
    fn vmot_mv(&mut self) -> u32 {
        self.with(|w| w.board.vmot_mv.max(0.0) as u32)
    }
    fn isense_mv(&mut self) -> u32 {
        // I = mV / 6.67 (INA180A1 on the 0.333 ohm shunt)
        self.with(|w| (w.board_current_ma() * 6.667) as u32)
    }
    fn vbus_mv(&mut self) -> u32 {
        self.with(|w| w.board.vbus_mv)
    }
    fn vdd_mv(&mut self) -> u32 {
        self.with(|w| w.board.vdd_mv)
    }
    fn tmag_ack(&mut self) -> bool {
        self.with(|w| w.power_on && !w.angle_nack && !w.board.f.ffc_unplugged)
    }
    fn now_us(&mut self) -> u64 {
        self.0.borrow().t_us
    }
    fn delay_us(&mut self, us: u32) {
        let mut w = self.0.borrow_mut();
        let t = w.t_us + us as u64;
        w.advance_to(t);
    }
    fn kick(&mut self) {
        self.0.borrow_mut().kick();
    }
}
