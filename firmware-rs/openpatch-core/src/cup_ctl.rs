//! Motor control of the cup board v4 (45 parts: 2 x DRV8838 in PHASE/ENABLE, TPS2553 load switch, boost, STM32C011 supervisor).
//! Host tested (`tests/cup_ctl.rs`); `openpatch-bench/src/hal/cup.rs` only binds it to the pins. TEST PROJECT, never worn, water only.
//!
//! Hardware gate (`electronics/v010/INTERLOCK.md` I.8, unchanged here):
//!
//! ```text
//! MOT_ALLOW = LATCH_Q AND SUP_PERMIT AND MCU_EN AND (DOCK_N XOR MOT_FWD)     (forward only docked, reverse only undocked)
//! ```
//!
//! The firmware never bypasses it; this controller only drives the nRF side in the right order and checks the result:
//!
//! * **Power-up** ([`CupCtl::power_up`]), every step refused before any pin moves when it fails: interlock latched failed, direction /
//!   dock combination (`interlock::check_request`: forward needs docked, reverse needs undocked, H15), the supervisor arm interval
//!   (waits up to `max_wait_ms`), the cell at rest (`battery::start_gate`: charger, 3.4 V boost minimum F3, 3.7 V rest threshold F2;
//!   diag `A-A0-004` instance 2), and VMOT already present before the arm (a stuck switch: latched, `1-06-001`). Then `MOT_FWD` FIRST
//!   (it is part of the gate), `MCU_EN` high, ONE `ARM_CLK` edge (the supervisor accepts an arm only with `MCU_EN` high,
//!   `openpatch_supervisor::logic`), settle, and the result is verified: `LATCH_Q`, `SUP_OK`, `OC_OK` and VMOT above the on threshold,
//!   else `MCU_EN` goes low again and the fault is reported.
//! * **Burst** ([`CupCtl::burst`]): `phase_drive::drive_burst` with the plan of `burst::plan_burst` (cell peak current, at most the
//!   supervisor budget of 32 forward steps per window); before EVERY step `SUP_OK`, `LATCH_Q`, `OC_OK`, the dock level (unchanged since
//!   the power-up) and VMOT are read, and `battery::LoadGuard` samples the loaded cell after step 1 (2.8 V) and step 20 (3.0 V). The
//!   first violation brakes the bridges at once. The rest after the burst comes from the plan.
//! * **Power-off** ([`CupCtl::power_off`]): bridges braked, `MCU_EN` low (the supervisor closes the window, its permit and the boost
//!   enable drop). `MOT_FWD` goes back to its reset default (forward) only after VMOT was seen below the off threshold
//!   ([`CupCtl::idle_check`], every tick); VMOT that does not fall within `fall_timeout_ms`, or rises while idle, latches the interlock
//!   failure (`1-06-001`), and an `MCU_EN` that reads back high while idle too (`GATE_INPUT_READBACK_MISMATCH`).
//! * **Capacity** ([`CupCtl::capacity`]): 0 while the supervisor arm interval (1.0 s, plus a margin for the supervisor's LSI clock) or
//!   the cell rest is running, else the planned burst length. The core uses it to defer instead of failing (`Hal::motor_capacity`).
//!   A weak cell or a failed interlock still reports capacity, so the attempt fails LOUDLY instead of deferring forever.
//!
//! Timing values are design values from the netlist and the SPICE report; every one is TODO(verify-on-hardware) (VMOT settle and decay
//! with the real bleeders, the supervisor clock tolerance).

use crate::battery::{rest_refusal_raise, start_gate, LoadGuard};
use crate::burst::{burst_ms_for, plan_burst, rest_for_burst, CellParams, MotorLoad};
use crate::diag::codes;
use crate::hal::{DiagEvent, InterlockReadback, MotorDir, MotorFault};
use crate::interlock::check_request;
use crate::phase_drive::{drive_burst, PhasePins, PhaseStepper, StepTimer};

/// Configuration of the controller. Nothing here can relax a core limit: the step budget and the arm interval are the supervisor's,
/// the cell limits are `CellParams` (tighten only).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct CupCfg {
    /// Forward step period (200 pps).
    pub fwd_period_us: u32,
    /// Reverse step period until the core sets a rate (assisted fill: 200 pps).
    pub rev_period_us: u32,
    /// VMOT (after the load switch, boost 4.96 V) counts as present above this.
    pub vmot_on_min_mv: u16,
    /// ... and as cut below this.
    pub vmot_off_max_mv: u16,
    /// Load switch soft start + boost start after the arm.
    pub settle_ms: u32,
    /// VMOT must fall below the off threshold within this after `MCU_EN` low (bleeders, about 0.44 s time constant).
    pub fall_timeout_ms: u32,
    /// Distance between two arm edges: the supervisor's 1.0 s plus 10 % for its clock.
    pub arm_spacing_ms: u32,
    /// Longest blocking wait for the arm interval inside one power-up.
    pub max_wait_ms: u32,
    /// Supervisor budget per armed window (forward) and the reverse budget.
    pub fwd_budget: u32,
    pub rev_budget: u32,
    pub cell: CellParams,
    pub load: MotorLoad,
}

impl CupCfg {
    pub const DEFAULT: CupCfg = CupCfg {
        fwd_period_us: 5_000,
        rev_period_us: 5_000,
        vmot_on_min_mv: 4_000,
        vmot_off_max_mv: 300,
        settle_ms: 10,
        fall_timeout_ms: 3_000,
        arm_spacing_ms: 1_100,
        max_wait_ms: 1_500,
        fwd_budget: 32,
        rev_budget: 512,
        cell: CellParams::AMPUL_301030,
        load: MotorLoad::NFP_608_26_45,
    };
}

/// Shortest reverse step period: 1000 pps hard cap (as on every board).
pub const REVERSE_PERIOD_MIN_US: u32 = 1_000;

/// Digital readbacks of the cup board.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct CupRead {
    pub latch_q: bool,
    /// Supervisor healthy (`SUP_OK` high).
    pub sup_ok: bool,
    /// TPS2553 FAULT not asserted (`OC_OK` high).
    pub oc_ok: bool,
    /// Dock hall says docked (`DOCK_N` low).
    pub docked: bool,
    /// Read-back of the `MCU_EN` output.
    pub mcu_en: bool,
}

/// Everything but the bridge and the step delays.
pub trait CupSense {
    /// `MOT_FWD`: `true` = forward intent (the pin level follows the board polarity in the HAL).
    fn set_mot_fwd(&mut self, forward: bool);
    fn set_mcu_en(&mut self, high: bool);
    /// One rising edge on `ARM_CLK`.
    fn arm_edge(&mut self);
    fn read(&mut self) -> CupRead;
    /// `VMOT_SENSE` x 2 in mV, `None` = no valid sample.
    fn vmot_mv(&mut self) -> Option<u16>;
    /// Cell voltage (`VDDHDIV5`) in mV, `None` = no valid sample.
    fn vbat_mv(&mut self) -> Option<u16>;
    fn now_ms(&mut self) -> u64;
    /// USB cable present (`USBDETECTED`): never move on a cable (H8).
    fn charger_present(&mut self) -> bool;
    /// Called before every step of a burst except the first (the HAL polls the angle sensor here).
    fn on_step(&mut self) {}
}

/// The board split into its three independent parts, so the bridge, the delays and the sensing can be borrowed at once.
pub trait CupBoard {
    type Phase: PhasePins;
    type Timer: StepTimer;
    type Sense: CupSense;
    fn parts(&mut self) -> (&mut Self::Phase, &mut Self::Timer, &mut Self::Sense);
}

const EVENTS: usize = 4;

pub struct CupCtl<B: CupBoard> {
    board: B,
    cfg: CupCfg,
    st: PhaseStepper,
    /// Direction and dock level of the running power-up.
    powered: Option<(MotorDir, bool)>,
    resting_mv: u16,
    rev_period_us: u32,
    failed: bool,
    fault: Option<MotorFault>,
    events: [Option<DiagEvent>; EVENTS],
    last_arm_ms: Option<u64>,
    rest_until_ms: u64,
    /// `MCU_EN` went low at this time and VMOT was not yet seen below the off threshold.
    off_since_ms: Option<u64>,
    mot_fwd: bool,
}

impl<B: CupBoard> CupCtl<B> {
    /// Drives the safe state: bridges braked, `MCU_EN` low, `MOT_FWD` at its reset default (forward).
    pub fn new(mut board: B, cfg: CupCfg) -> Self {
        let mut st = PhaseStepper::new();
        {
            let (phase, _, sense) = board.parts();
            phase.apply(st.de_energise());
            sense.set_mcu_en(false);
            sense.set_mot_fwd(true);
        }
        Self {
            board,
            rev_period_us: cfg.rev_period_us.max(REVERSE_PERIOD_MIN_US),
            cfg,
            st,
            powered: None,
            resting_mv: 0,
            failed: false,
            fault: None,
            events: [None; EVENTS],
            last_arm_ms: None,
            rest_until_ms: 0,
            off_since_ms: None,
            mot_fwd: true,
        }
    }

    pub fn board_mut(&mut self) -> &mut B {
        &mut self.board
    }
    pub fn cfg(&self) -> &CupCfg {
        &self.cfg
    }
    pub fn is_powered(&self) -> bool {
        self.powered.is_some()
    }
    /// The interlock failure is latched (until reset).
    pub fn failed(&self) -> bool {
        self.failed
    }
    pub fn take_fault(&mut self) -> Option<MotorFault> {
        self.fault.take()
    }
    pub fn take_event(&mut self) -> Option<DiagEvent> {
        let e = self.events[0].take();
        self.events.rotate_left(1);
        e
    }
    fn push(&mut self, e: DiagEvent) {
        if let Some(slot) = self.events.iter_mut().find(|s| s.is_none()) {
            *slot = Some(e);
        }
    }
    fn latch_failed(&mut self, code: crate::diag::DiagCode, a: i32) {
        self.failed = true;
        self.push(DiagEvent { code, ctx_a: a, ctx_b: 0, ctx_c: 0 });
    }

    /// Reverse rate from the core (fill needle): clamped to 1000 pps.
    pub fn set_reverse_pps(&mut self, pps: u32) {
        let pps = pps.clamp(1, 1_000_000 / REVERSE_PERIOD_MIN_US);
        self.rev_period_us = 1_000_000 / pps;
    }
    pub fn reverse_period_us(&self) -> u32 {
        self.rev_period_us
    }
    fn period(&self, dir: MotorDir) -> u32 {
        match dir {
            MotorDir::Forward => self.cfg.fwd_period_us,
            MotorDir::Reverse => self.rev_period_us,
        }
    }
    fn budget(&self, dir: MotorDir) -> u32 {
        match dir {
            MotorDir::Forward => self.cfg.fwd_budget,
            MotorDir::Reverse => self.cfg.rev_budget,
        }
    }

    /// Steps of one planned burst in `dir` (at the resting voltage of the running power-up, or a fresh sample).
    pub fn plan_steps(&mut self, dir: MotorDir) -> Option<u32> {
        let mv = if self.powered.is_some() { self.resting_mv } else { self.board.parts().2.vbat_mv().unwrap_or(0) };
        plan_burst(self.cfg.cell, self.cfg.load, mv, self.period(dir), self.budget(dir)).ok().map(|p| p.steps)
    }

    fn next_start_ms(&self) -> u64 {
        let arm = self.last_arm_ms.map_or(0, |t| t + self.cfg.arm_spacing_ms as u64);
        arm.max(self.rest_until_ms)
    }

    /// Steps the board can make in ONE call now: 0 = not now (arm interval or cell rest running, ask again next tick).
    pub fn capacity(&mut self, dir: MotorDir) -> u32 {
        let now = self.board.parts().2.now_ms();
        if now < self.next_start_ms() {
            return 0;
        }
        self.plan_steps(dir).unwrap_or(self.budget(dir))
    }

    fn wait_until(&mut self, t_ms: u64) -> bool {
        let (_, timer, sense) = self.board.parts();
        let start = sense.now_ms();
        if t_ms > start + self.cfg.max_wait_ms as u64 {
            return false;
        }
        while sense.now_ms() < t_ms {
            timer.delay_us(1_000);
        }
        true
    }

    /// Request the motor supply for motion in `dir` (see the module documentation for the order and every check).
    pub fn power_up(&mut self, docked: bool, dir: MotorDir) -> Result<(), MotorFault> {
        if self.failed {
            return Err(MotorFault::InterlockFailed);
        }
        check_request(dir, docked).map_err(MotorFault::from)?;
        if self.powered.is_some() {
            self.power_off();
        }
        if !self.wait_until(self.next_start_ms()) {
            return Err(MotorFault::Timeout);
        }
        let (_, timer, sense) = self.board.parts();
        let resting = sense.vbat_mv().unwrap_or(0);
        let charger = sense.charger_present();
        if let Err(why) = start_gate(self.cfg.cell.supply, resting, charger) {
            if let Some(r) = rest_refusal_raise(self.cfg.cell.supply, resting, why) {
                self.push(DiagEvent { code: r.code, ctx_a: r.ctx_a, ctx_b: r.ctx_b, ctx_c: r.ctx_c });
            }
            return Err(MotorFault::CellSupply);
        }
        // the gate must be closed before we ask for it: a supply that is already there is a stuck switch
        match sense.vmot_mv() {
            None => return Err(MotorFault::SupplyMissing),
            Some(v) if v >= self.cfg.vmot_on_min_mv => {
                self.latch_failed(codes::VMOT_STUCK_ON, v as i32);
                return Err(MotorFault::SupplyUnexpected);
            }
            Some(_) => {}
        }
        let forward = matches!(dir, MotorDir::Forward);
        sense.set_mot_fwd(forward);
        timer.delay_us(100);
        sense.set_mcu_en(true);
        timer.delay_us(100);
        sense.arm_edge();
        let now = sense.now_ms();
        self.last_arm_ms = Some(now);
        self.mot_fwd = forward;
        self.off_since_ms = None;
        timer.delay_us(self.cfg.settle_ms * 1_000);
        let r = sense.read();
        let v = sense.vmot_mv();
        let ok = r.latch_q && r.sup_ok && r.oc_ok && v.is_some_and(|v| v >= self.cfg.vmot_on_min_mv);
        self.powered = Some((dir, docked));
        self.resting_mv = resting;
        if !ok {
            self.power_off();
            return Err(if r.oc_ok { MotorFault::SupplyMissing } else { MotorFault::Driver });
        }
        Ok(())
    }

    /// One planned burst of `steps` in the powered direction. Returns the steps made; a short burst leaves its cause in
    /// [`CupCtl::take_fault`] (and a diagnostic in [`CupCtl::take_event`] where the catalogue has one).
    pub fn burst(&mut self, steps: u32) -> u32 {
        let Some((dir, docked)) = self.powered else {
            self.fault.get_or_insert(MotorFault::SupplyMissing);
            return 0;
        };
        let period = self.period(dir);
        let plan = match plan_burst(self.cfg.cell, self.cfg.load, self.resting_mv, period, self.budget(dir)) {
            Ok(p) => p,
            Err(_) => {
                self.fault = Some(MotorFault::CellSupply);
                return 0;
            }
        };
        if steps == 0 || steps > plan.steps {
            self.fault = Some(MotorFault::Timeout);
            return 0;
        }
        let on_min = self.cfg.vmot_on_min_mv;
        let mut guard = LoadGuard::new(self.cfg.cell.supply);
        let mut stop: Option<MotorFault> = None;
        let (phase, timer, sense) = self.board.parts();
        let (made, _) = drive_burst(&mut self.st, phase, timer, dir, steps, period, |made| {
            if made > 0 {
                sense.on_step();
            }
            let r = sense.read();
            let why = if !r.sup_ok || !r.latch_q {
                Some(MotorFault::SupplyMissing)
            } else if !r.oc_ok {
                Some(MotorFault::Driver)
            } else if r.docked != docked {
                Some(if docked { MotorFault::ForwardWhileUndocked } else { MotorFault::ReverseWhileDocked })
            } else if !sense.vmot_mv().is_some_and(|v| v >= on_min) {
                Some(MotorFault::SupplyMissing)
            } else if !guard.keep_going(made, || sense.vbat_mv().unwrap_or(0)) {
                Some(MotorFault::CellSupply)
            } else {
                None
            };
            stop = why;
            why.is_none()
        });
        let now = sense.now_ms();
        self.rest_until_ms = now + rest_for_burst(self.cfg.cell, plan.cell_ma, burst_ms_for(made, period)) as u64;
        if let Some(a) = guard.abort() {
            let r = a.raise();
            self.push(DiagEvent { code: r.code, ctx_a: r.ctx_a, ctx_b: r.ctx_b, ctx_c: r.ctx_c });
        }
        if stop.is_some() {
            self.fault = stop;
        }
        made
    }

    /// Bridges braked, `MCU_EN` low. The direction stays until [`CupCtl::idle_check`] has seen the supply cut.
    pub fn power_off(&mut self) {
        let (phase, _, sense) = self.board.parts();
        phase.apply(self.st.de_energise());
        sense.set_mcu_en(false);
        let now = sense.now_ms();
        if self.powered.take().is_some() || self.off_since_ms.is_none() {
            self.off_since_ms = Some(now);
        }
    }

    /// Idle verification (every tick, never while powered). `false` = something is wrong (the watchdog permit is withheld).
    pub fn idle_check(&mut self) -> bool {
        if self.failed {
            return false;
        }
        if self.powered.is_some() {
            return true;
        }
        let (fall, off_max) = (self.cfg.fall_timeout_ms as u64, self.cfg.vmot_off_max_mv);
        let (_, _, sense) = self.board.parts();
        let r = sense.read();
        let now = sense.now_ms();
        let v = sense.vmot_mv();
        if r.mcu_en {
            self.latch_failed(codes::GATE_INPUT_READBACK_MISMATCH, 1);
            return false;
        }
        let Some(v) = v else {
            self.push(DiagEvent { code: codes::ADC_FAULT, ctx_a: 0, ctx_b: 0, ctx_c: 0 });
            return false;
        };
        match self.off_since_ms {
            Some(t) if v > off_max => {
                if now.saturating_sub(t) > fall {
                    self.latch_failed(codes::VMOT_STUCK_ON, v as i32);
                    return false;
                }
                true // still decaying
            }
            Some(_) => {
                self.off_since_ms = None;
                if !self.mot_fwd {
                    let (_, _, sense) = self.board.parts();
                    sense.set_mot_fwd(true);
                    self.mot_fwd = true;
                }
                true
            }
            None if v > off_max => {
                self.latch_failed(codes::VMOT_STUCK_ON, v as i32);
                false
            }
            None => true,
        }
    }

    /// Readbacks for the core (`Hal::interlock_state`); signals this board does not have stay `None` (UNKNOWN, never OK).
    pub fn readback(&mut self) -> InterlockReadback {
        let mot_fwd = self.mot_fwd;
        let (_, _, sense) = self.board.parts();
        let r = sense.read();
        InterlockReadback {
            latch_q: Some(r.latch_q),
            docked_h: Some(r.docked),
            dir_rev: Some(!mot_fwd),
            oc_ok: Some(r.oc_ok),
            vmot_mv: sense.vmot_mv(),
            ..InterlockReadback::default()
        }
    }
}
