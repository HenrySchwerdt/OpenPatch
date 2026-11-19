//! Bench controller board: the interlock sequencing, the readback classification and the power-on
//! self-test (POST), hardware independent and host-tested.
//!
//! Source of truth: `electronics/bench/INTERLOCK.md` and `pin-assignment.md` (Rev A).
//! `MOT_ALLOW = MCU_EN AND LATCH_Q AND OC_OK AND (DOCKED_H OR DIR_REV)`, `VMOT = VBUS` through the P-FET Q4
//! while `MOT_ALLOW`. The board implements [`BenchPins`] (embassy pins on the target, an electrical model in the
//! simulator), this module owns every decision. Rules it keeps:
//!
//! * the firmware can only REMOVE permission: no step of the self-test forces the supply on. The test pins
//!   (`DOCK_TEST`, `OC_TEST`) are pull-down paths that make a leg block / trip more easily;
//! * DIR is part of the gate: it is set first in every power-up and returns to forward only after the supply
//!   is verified cut;
//! * every power-down cuts with a different single gate in rotation (`MCU_EN` only, `LATCH_CLR_N` only, both),
//!   verifies the collapse and names the stuck gate if it does not;
//! * a supply that stays on although the P-FET gate is off (`PGATE_MON` high) is Q4 shorted: the board can not
//!   cut it, so the controller is QUARANTINED (STBY low for good, no power-up, alarm "replace controller board"),
//!   it does NOT withhold the watchdog (a reset can not help);
//! * every finding is a [`DiagEvent`] with a catalogue code; the HAL never decides policy, the core does.
//!
//! No alloc, no unsafe.

use crate::hal::{DiagEvent, InterlockReadback, MotorDir, MotorFault, SelfTestOutcome, SelfTestStep};
use crate::interlock::{self, check_request, mot_allow, power_up_plan, Disarm, PowerError, Step};
use heapless::Deque;
use crate::limits;
use openpatch_diag::{codes, DiagCode};

/// Thresholds of the POST (docs: INTERLOCK.md section F) and of the idle checks. One place, calibrate on the bench.
pub mod th {
    /// "VMOT off" in the POST and at idle (INTERLOCK.md: < 0.3 V).
    pub const VMOT_OFF_MV: u32 = 300;
    /// "VMOT on" in the POST (INTERLOCK.md: > 4.3 V; USB 5 V minus the P-FET and the shunt).
    pub const VMOT_UP_MV: u32 = 4_300;
    /// "VMOT cut" after a disarm (INTERLOCK.md: < 1.8 V, the STSPIN220 minimum VS).
    pub const VMOT_CUT_MV: u32 = 1_800;
    /// Time allowed for the supply to come up / collapse in the POST.
    pub const VMOT_MOVE_MS: u32 = 30;
    /// A blocked leg must keep the supply below `VMOT_OFF_MV` for this long.
    pub const BLOCK_HOLD_MS: u32 = 50;
    /// LATCH_Q must follow LATCH_CLR_N / ARM_CLK within this time.
    pub const LATCH_MS: u32 = 1;
    /// VBUS window of POST step 1 (USB 5 V).
    pub const VBUS_MIN_MV: u32 = 4_500;
    pub const VBUS_MAX_MV: u32 = 5_500;
    /// Below this the MCU can not really run from USB (`1-09-001` inst 2).
    pub const VBUS_IMPLAUSIBLE_MV: u32 = 3_000;
    /// 3V3 rail window.
    pub const VDD_MIN_MV: u32 = 3_000;
    pub const VDD_MAX_MV: u32 = 3_600;
    /// `I_SENSE` with the driver in standby: offset above this is a fault (INA180A1, 6.67 mV per mA => 12 mA).
    pub const ISENSE_IDLE_MAX_MV: u32 = 80;
    /// INA180A1 output saturates at about 3.25 V (490 mA).
    pub const ISENSE_SAT_MV: u32 = 3_200;
    /// The over-current proof needs at least this holding current (OC_TEST trips above about 45 mA = 300 mV):
    /// 400 mV = 60 mA. Below it the proof is inconclusive (motor not connected), never "passed".
    pub const OC_PROOF_MIN_MV: u32 = 400;
    /// Time for the over-current comparator and latch to trip after `OC_TEST` (RC 0.1 ms, LM393).
    pub const OC_TRIP_MS: u32 = 10;
    /// STBY stays high at most this long in the over-current proof (coil holding current, about 1.4 W).
    pub const OC_HOLD_MAX_MS: u32 = 100;
    /// Release of the over-current latch CLR is delayed about 12 ms after `MCU_EN` rises (hardware blanking).
    pub const OC_CLEAR_MS: u32 = 20;
}

/// `I_SENSE` in mA from mV: INA180A1 (20 V/V) on the 0.333 ohm shunt = 6.67 mV per mA (`config::I_SENSE_MV_X100_PER_MA`).
pub const fn isense_ma(mv: u32) -> u32 {
    limits::isense_mv_to_ma(mv)
}

/// Leg identifiers carried in `ctx_a` of the findings.
pub mod leg {
    pub const MCU_EN: i32 = 1;
    pub const LATCH: i32 = 2;
    pub const DOCK: i32 = 3;
    pub const DIR: i32 = 4;
    pub const OC: i32 = 5;
    /// A leg of the series chain is open but the readbacks can not tell which one.
    pub const UNKNOWN: i32 = 0;
}

/// Own-pin readback instances (`1-07-007` inst = pin).
pub mod pin {
    pub const MCU_EN: u8 = 1;
    pub const ARM_CLK: u8 = 2;
    pub const LATCH_CLR_N: u8 = 3;
    pub const STBY: u8 = 4;
    pub const WDT_DONE: u8 = 5;
    pub const MOT_DIR: u8 = 6;
    /// The over-current leg (`OC_OK` readback against the comparator test).
    pub const OC: u8 = 7;
}

/// Everything the board can read back, one snapshot. All values are LOGICAL (the pin polarity is the board's
/// business): `true` means the named condition holds.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct PinRead {
    /// `LATCH_Q` (latch output) is high.
    pub latch_q: bool,
    /// `OC_OK` is high (over-current latch has not tripped).
    pub oc_ok: bool,
    /// `PGATE_MON` is LOW: the composite `MOT_ALLOW` is true, the supply switch is on.
    pub mot_allow: bool,
    /// `DOCKED_H`: docked as the gate sees it.
    pub docked_h: bool,
    /// `DIR_REV`: reverse as the gate sees it.
    pub dir_rev: bool,
    /// Own-pin readback of `MCU_EN` (high).
    pub mcu_en: bool,
    /// Own-pin readback of `STBY` (high).
    pub stby: bool,
    /// Own-pin readback of `ARM_CLK` (high).
    pub arm_clk: bool,
    /// Own-pin readback of `LATCH_CLR_N`: `true` = line is LOW (clear asserted).
    pub latch_clr: bool,
    /// `DOCK_N` is low (the pod hall says docked).
    pub dock_n_low: bool,
    /// `POD_ID_N` is low (pod board present, FFC intact).
    pub pod_present: bool,
    /// `EN/FAULT` reads high (driver ready, no fault).
    pub en_fault_high: bool,
}

/// The board under the controller. Outputs are logical, the implementation applies polarity and drive modes.
pub trait BenchPins {
    /// `MOT_DIR` pin level (the same net as the STSPIN220 DIR pin and the interlock gate).
    fn set_mot_dir(&mut self, high: bool);
    fn set_mcu_en(&mut self, high: bool);
    /// One `ARM_CLK` rising edge, idle low afterwards.
    fn arm_edge(&mut self);
    /// `LATCH_CLR_N` low (`true`) or released (`false`, open drain, never driven high).
    fn set_latch_clear(&mut self, asserted: bool);
    /// `DOCK_TEST` high: forces the gate's DOCKED to "undocked". Can never force docked.
    fn set_dock_test(&mut self, on: bool);
    /// `OC_TEST` high: lowers the over-current reference (trips easier). Can never mask the comparator.
    fn set_oc_test(&mut self, on: bool);
    /// STSPIN220 `STBY/RESET` high = active.
    fn set_stby(&mut self, active: bool);
    /// Drive `EN/FAULT` low (disables the power stage) or release it (input, 10 k pull-up on the board).
    fn drive_en_fault_low(&mut self, low: bool);
    fn read(&mut self) -> PinRead;
    fn vmot_mv(&mut self) -> u32;
    fn isense_mv(&mut self) -> u32;
    fn vbus_mv(&mut self) -> u32;
    /// 3V3 rail (SAADC `VDD`), 0 = not measured.
    fn vdd_mv(&mut self) -> u32;
    /// TMAG5273 answers at 0x35 with the right DEVICE_ID.
    fn tmag_ack(&mut self) -> bool;
    fn now_us(&mut self) -> u64;
    fn delay_us(&mut self, us: u32);
    /// Service the TPL5010 during a long proof (one DONE pulse if a WAKE is pending). Must NOT run the idle verification.
    fn kick(&mut self) {}
}

/// Configuration of the controller (board constants, `openpatch-bench/src/config.rs`).
#[derive(Clone, Copy, Debug)]
pub struct CtlCfg {
    /// `MOT_DIR` level for FORWARD: `false` with R96 fitted (default), `true` with R97 instead.
    pub forward_high: bool,
    /// Runtime "supply present" / "supply cut" levels on `VMOT_SENSE`.
    pub vmot_on_min_mv: u32,
    pub vmot_off_max_mv: u32,
    /// Supply settling time after the interlock closed.
    pub settle_ms: u32,
    /// Time allowed for the supply to collapse after a disarm.
    pub fall_timeout_ms: u32,
    /// STSPIN220 wake-up after STBY high and time to release EN/FAULT.
    pub stby_wake_us: u32,
    pub driver_ready_ms: u32,
    /// The hardware interlock board is fitted (bench controller). `false` on the DK: no gate, no readbacks, every
    /// proof stays UNKNOWN (never OK).
    pub interlock: bool,
    /// An STSPIN220 is fitted (EN/FAULT readiness check).
    pub driver: bool,
}

impl CtlCfg {
    /// Rev A defaults (R96 fitted).
    pub const BENCH: CtlCfg = CtlCfg {
        forward_high: false,
        vmot_on_min_mv: 3_000,
        vmot_off_max_mv: 1_500,
        settle_ms: 3,
        fall_timeout_ms: 20,
        stby_wake_us: 2_000,
        driver_ready_ms: 10,
        interlock: true,
        driver: true,
    };
    /// A board without the interlock (nRF52840-DK): direction, STBY and EN/FAULT only.
    pub const NO_INTERLOCK: CtlCfg = CtlCfg { interlock: false, driver: false, ..CtlCfg::BENCH };
}

/// What the controller does about a finding.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FailAction {
    /// Report only (the core latches delivery for L / F codes).
    Report,
    /// The supply could not be cut by the gates: withhold DONE so the TPL5010 resets the MCU and clears the latch.
    ResetToClear,
    /// The supply can not be cut by anything on the board (Q4 shorted): keep STBY low, never power up again, keep
    /// the MCU alive so the alarm works. USB is the last off switch.
    Quarantine,
}

/// One finding: the diagnostic event and what to do about it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Finding {
    pub event: DiagEvent,
    pub action: FailAction,
}

const fn finding(code: DiagCode, a: i32, b: i32, action: FailAction) -> Finding {
    Finding { event: DiagEvent { code, ctx_a: a, ctx_b: b, ctx_c: 0 }, action }
}

/// Q4 shorted: VMOT present although the P-FET gate is off.
const fn q4_short(vmot_mv: u32) -> Finding {
    finding(codes::VMOT_STUCK_ON, vmot_mv as i32, 1, FailAction::Quarantine)
}

/// The first open leg of the series chain, from the gate readbacks.
pub fn first_open_leg(r: &PinRead) -> i32 {
    if !r.mcu_en {
        leg::MCU_EN
    } else if !r.latch_q {
        leg::LATCH
    } else if !r.oc_ok {
        leg::OC
    } else if !r.docked_h && !r.dir_rev {
        leg::DOCK
    } else {
        leg::UNKNOWN
    }
}

/// `MOT_ALLOW` as the readbacks of the gate inputs say it must be.
pub fn gates_allow(r: &PinRead) -> bool {
    mot_allow(r.latch_q, r.mcu_en, r.oc_ok, r.docked_h, r.dir_rev)
}

/// Code for "a gate leg passes although its input says closed" (stuck pass), by leg.
fn stuck_pass(leg_id: i32, vmot_mv: u32) -> Finding {
    let action = FailAction::Report;
    match leg_id {
        leg::MCU_EN => finding(codes::GATE_MCUEN_STUCK_PASS, vmot_mv as i32, leg_id, action),
        leg::LATCH => finding(codes::GATE_LATCH_STUCK_PASS, vmot_mv as i32, leg_id, action),
        leg::OC => finding(codes::GATE_INPUT_READBACK_MISMATCH.with_inst(pin::OC), vmot_mv as i32, leg_id, action),
        // Q6 or Q10: no midpoint readback on Rev A, so the pair is reported as one (ctx_b = 3)
        _ => finding(codes::GATE_DOCK_STUCK_PASS, vmot_mv as i32, leg::DOCK, action),
    }
}

/// Classify the supply against the gate readbacks (the core of every runtime and POST check).
/// `None` = everything is consistent.
///
/// * `PGATE_MON` says on while the gate inputs say off: a leg passes although its input is closed (stuck pass);
/// * `PGATE_MON` says off while the gate inputs say on: a leg or the switch blocks (stuck block);
/// * gate on but no supply: Q4 open; gate off but supply: Q4 shorted (not cuttable: quarantine).
pub fn classify_supply(r: &PinRead, vmot_mv: u32, cfg: &CtlCfg) -> Option<Finding> {
    let allow = gates_allow(r);
    if r.mot_allow && !allow {
        return Some(stuck_pass(first_open_leg(r), vmot_mv));
    }
    if !r.mot_allow && allow {
        return Some(finding(codes::GATE_MCUEN_STUCK_BLOCK, vmot_mv as i32, leg::UNKNOWN, FailAction::Report));
    }
    if r.mot_allow {
        if vmot_mv < cfg.vmot_on_min_mv {
            return Some(finding(codes::VMOT_NOT_PRESENT, vmot_mv as i32, 0, FailAction::Report));
        }
    } else if vmot_mv > cfg.vmot_off_max_mv {
        return Some(q4_short(vmot_mv));
    }
    None
}

/// Own-pin readback mismatches as a bit mask (bit `n-1` = `pin::*` n): driven level against the level read back.
pub fn own_pin_mismatch(r: &PinRead, driven_mcu_en: bool, driven_stby: bool, driven_clr: bool) -> u8 {
    let mut m = 0u8;
    if r.mcu_en != driven_mcu_en {
        m |= 1 << (pin::MCU_EN - 1);
    }
    if r.arm_clk {
        m |= 1 << (pin::ARM_CLK - 1); // idle low always
    }
    if r.latch_clr != driven_clr {
        m |= 1 << (pin::LATCH_CLR_N - 1);
    }
    if r.stby != driven_stby {
        m |= 1 << (pin::STBY - 1);
    }
    m
}

/// The controller. Owns the pins; one instance in the safety task.
pub struct BenchCtl<P: BenchPins> {
    pub pins: P,
    pub cfg: CtlCfg,
    /// Driver powered for motion.
    pub powered: bool,
    /// A power-down could not be verified (or a leg is stuck pass): withhold DONE so the TPL5010 resets the MCU.
    pub failed: bool,
    /// Q4 shorted: no power-up ever again, STBY stays low, the MCU stays alive.
    pub quarantined: bool,
    dir_state: MotorDir,
    driven_mcu_en: bool,
    driven_stby: bool,
    driven_clr: bool,
    disarm_n: u8,
    /// Findings already reported (code identity), so a standing fault is raised once.
    reported: heapless::Vec<u32, 16>,
    events: Deque<DiagEvent, 8>,
    /// Cause of the last refused / failed power-up or burst, taken by `Hal::motor_fault`.
    pub fault: Option<MotorFault>,
    /// The disarm modes actually used, newest last (diagnostics and tests).
    pub last_disarm: Option<Disarm>,
}

impl<P: BenchPins> BenchCtl<P> {
    /// All outputs go to the fail-safe state: driver in standby, supply gates open, latch held clear.
    pub fn new(pins: P, cfg: CtlCfg) -> Self {
        let mut c = BenchCtl {
            pins,
            cfg,
            powered: false,
            failed: false,
            quarantined: false,
            dir_state: MotorDir::Forward,
            driven_mcu_en: false,
            driven_stby: false,
            driven_clr: true,
            disarm_n: 0,
            reported: heapless::Vec::new(),
            events: Deque::new(),
            fault: None,
            last_disarm: None,
        };
        c.safe_state();
        c
    }

    /// Idle state of every output: STBY low, EN/FAULT driven low, MCU_EN low, latch held clear, ARM idle low,
    /// test pins off, DIR at the forward level.
    pub fn safe_state(&mut self) {
        self.pins.set_stby(false);
        self.pins.drive_en_fault_low(true);
        self.pins.set_mcu_en(false);
        self.pins.set_latch_clear(true);
        self.pins.set_dock_test(false);
        self.pins.set_oc_test(false);
        self.set_dir(MotorDir::Forward);
        self.driven_stby = false;
        self.driven_mcu_en = false;
        self.driven_clr = true;
    }

    fn set_dir(&mut self, d: MotorDir) {
        let level = interlock::dir_level_high(d, self.cfg.forward_high);
        self.pins.set_mot_dir(level);
        self.dir_state = d;
    }

    /// Oldest finding event not yet taken (`Hal::take_diag`).
    pub fn take_event(&mut self) -> Option<DiagEvent> {
        self.events.pop_front()
    }

    /// Queue a finding (once per code identity) and apply its action.
    fn report(&mut self, f: Finding) {
        let id = f.event.code.identity().raw();
        let key = id ^ ((f.event.code.inst() as u32) << 24);
        if !self.reported.contains(&key) {
            let _ = self.reported.push(key);
            if self.events.push_back(f.event).is_err() {
                // queue full: drop the oldest so the newest (usually more specific) stays
                let _ = self.events.pop_front();
                let _ = self.events.push_back(f.event);
            }
        }
        match f.action {
            FailAction::Report => {}
            FailAction::ResetToClear => self.failed = true,
            FailAction::Quarantine => {
                self.quarantined = true;
                self.powered = false;
                self.pins.set_stby(false);
                self.driven_stby = false;
            }
        }
    }

    /// Forget which findings were reported (after a verified recovery or a new POST).
    pub fn clear_reported(&mut self) {
        self.reported.clear();
    }

    fn wait_until(&mut self, timeout_us: u64, mut cond: impl FnMut(&mut P) -> bool) -> bool {
        let t0 = self.pins.now_us();
        loop {
            if cond(&mut self.pins) {
                return true;
            }
            if self.pins.now_us().saturating_sub(t0) > timeout_us {
                return false;
            }
            self.pins.delay_us(250);
        }
    }

    fn vmot_off(&self, v: u32) -> bool {
        v <= self.cfg.vmot_off_max_mv
    }

    // ------------------------------------------------------------------------------------------
    // power-up / direction / verification (runtime)
    // ------------------------------------------------------------------------------------------

    /// Power the driver for motion in `dir`. DIR first (the gate needs it in a draw); forward needs DOCKED, reverse
    /// needs UNDOCKED (`interlock::check_request`).
    pub fn power_up(&mut self, docked: bool, dir: MotorDir) -> Result<(), PowerError> {
        if self.failed || self.quarantined {
            return Err(PowerError::InterlockFailed);
        }
        check_request(dir, docked).map_err(PowerError::Refused)?;
        for step in power_up_plan(dir) {
            if !self.cfg.interlock && !matches!(step, Step::SetDir(_) | Step::DriverOn) {
                continue;
            }
            match step {
                Step::SetDir(d) => self.set_dir(d),
                Step::ReleaseLatchClear => {
                    self.pins.set_latch_clear(false);
                    self.driven_clr = false;
                }
                Step::McuEnHigh => {
                    self.pins.set_mcu_en(true);
                    self.driven_mcu_en = true;
                    self.pins.delay_us(50);
                }
                Step::ArmEdge => {
                    self.pins.arm_edge();
                    self.pins.delay_us(50);
                }
                Step::CheckLatchSet => {
                    if !self.pins.read().latch_q {
                        self.report(finding(codes::LATCH_CANNOT_SET, 0, 0, FailAction::Report));
                        self.power_off();
                        return Err(PowerError::LatchNotSet);
                    }
                }
                Step::CheckVmotUp => {
                    self.pins.delay_us(self.cfg.settle_ms * 1000);
                    let r = self.pins.read();
                    let v = self.pins.vmot_mv();
                    if !(r.mot_allow && v >= self.cfg.vmot_on_min_mv) {
                        let f = classify_supply(&r, v, &self.cfg).unwrap_or(finding(codes::VMOT_NOT_PRESENT, v as i32, 0, FailAction::Report));
                        self.report(f);
                        self.power_off();
                        return Err(PowerError::NoSupply);
                    }
                }
                Step::CheckOcOk => {
                    let r = self.pins.read();
                    if !r.oc_ok {
                        let i = self.pins.isense_mv();
                        self.report(finding(codes::DRIVER_FAULT_IN_BURST, isense_ma(i) as i32, 1, FailAction::Report));
                        self.power_off();
                        return Err(PowerError::DriverFault);
                    }
                }
                Step::DriverOn => {
                    self.pins.drive_en_fault_low(false);
                    self.pins.set_stby(true);
                    self.driven_stby = true;
                    self.pins.delay_us(self.cfg.stby_wake_us);
                    let ready = !self.cfg.driver || self.wait_until(self.cfg.driver_ready_ms as u64 * 1000, |p| p.read().en_fault_high);
                    if !ready {
                        self.power_off();
                        return Err(PowerError::DriverFault);
                    }
                }
            }
        }
        self.powered = true;
        Ok(())
    }

    /// Direction change while powered. The supply must follow the gate afterwards.
    pub fn change_direction(&mut self, docked: bool, dir: MotorDir) -> Result<(), PowerError> {
        check_request(dir, docked).map_err(PowerError::Refused)?;
        if self.dir_state == dir {
            return Ok(());
        }
        if !self.cfg.interlock {
            self.set_dir(dir);
            return Ok(());
        }
        // STCK / STBY are the caller's business; the gate input follows DIR immediately
        self.set_dir(dir);
        self.verify_supply(docked)
    }

    /// Compare the supply with the gate model for the current direction and with the gate readbacks. `latch`,
    /// `MCU_EN` are set while powered.
    pub fn verify_supply(&mut self, docked: bool) -> Result<(), PowerError> {
        if !self.cfg.interlock {
            return Ok(());
        }
        let expected = interlock::vmot_expected(true, true, docked, self.dir_state);
        self.pins.delay_us(self.cfg.settle_ms * 1000);
        let r = self.pins.read();
        let v = self.pins.vmot_mv();
        // over-current latch tripped: the supply is cut by hardware, this is a driver / motor fault
        if self.powered && !r.oc_ok {
            let i = self.pins.isense_mv();
            self.report(finding(codes::DRIVER_FAULT_IN_BURST, isense_ma(i) as i32, 1, FailAction::Report));
            self.power_off();
            return Err(PowerError::DriverFault);
        }
        match interlock::check_supply(expected, v, self.cfg.vmot_on_min_mv, self.cfg.vmot_off_max_mv) {
            interlock::SupplyCheck::Ok => {
                // the supply agrees with the model; the gate readbacks must agree with the gate as well
                if let Some(f) = classify_supply(&r, v, &self.cfg) {
                    self.report(f);
                    if self.failed || self.quarantined {
                        self.power_off();
                        return Err(PowerError::UnexpectedSupply);
                    }
                }
                Ok(())
            }
            interlock::SupplyCheck::Missing => {
                let f = classify_supply(&r, v, &self.cfg).unwrap_or(finding(codes::VMOT_NOT_PRESENT, v as i32, 0, FailAction::Report));
                self.report(f);
                self.power_off();
                Err(PowerError::NoSupply)
            }
            interlock::SupplyCheck::Unexpected => {
                let f = classify_supply(&r, v, &self.cfg).unwrap_or(stuck_pass(first_open_leg(&r), v));
                self.report(f);
                self.failed = true;
                self.power_off();
                Err(PowerError::UnexpectedSupply)
            }
        }
    }

    /// The mode the next power-down uses (rotates every call).
    fn next_disarm(&mut self) -> Disarm {
        let d = Disarm::nth(self.disarm_n);
        self.disarm_n = self.disarm_n.wrapping_add(1);
        d
    }

    /// The supply is verified cut: the P-FET gate is off and VMOT is below the runtime "cut" level.
    fn is_cut(&mut self) -> bool {
        let r = self.pins.read();
        !r.mot_allow && {
            let v = self.pins.vmot_mv();
            self.vmot_off(v)
        }
    }

    fn wait_cut(&mut self) -> bool {
        let to = self.cfg.fall_timeout_ms as u64 * 1000;
        let t0 = self.pins.now_us();
        loop {
            if self.is_cut() {
                return true;
            }
            if self.pins.now_us().saturating_sub(t0) > to {
                return false;
            }
            self.pins.delay_us(250);
        }
    }

    /// `true` if the supply is verified cut. STBY goes low first, then ONE gate cuts (rotating), the collapse is
    /// verified, and if it does not happen the second gate follows at once and the stuck one is named.
    pub fn power_off(&mut self) -> bool {
        self.powered = false;
        self.pins.set_stby(false);
        self.driven_stby = false;
        self.pins.drive_en_fault_low(true);
        if !self.cfg.interlock {
            self.set_dir(MotorDir::Forward);
            return true;
        }
        let mode = self.next_disarm();
        self.last_disarm = Some(mode);
        let cut = match mode {
            Disarm::Both => {
                self.pins.set_mcu_en(false);
                self.driven_mcu_en = false;
                self.pins.set_latch_clear(true);
                self.driven_clr = true;
                self.wait_cut()
            }
            Disarm::McuEnOnly => {
                self.pins.set_mcu_en(false);
                self.driven_mcu_en = false;
                let first = self.wait_cut();
                if !first {
                    let r = self.pins.read();
                    let v = self.pins.vmot_mv();
                    // chain still conducting with MCU_EN low: that leg is stuck; otherwise Q4 shorted
                    self.report(if r.mot_allow { stuck_pass(leg::MCU_EN, v) } else { q4_short(v) });
                }
                self.pins.set_latch_clear(true);
                self.driven_clr = true;
                first || self.wait_cut()
            }
            Disarm::LatchOnly => {
                self.pins.set_latch_clear(true);
                self.driven_clr = true;
                let latch_down = self.wait_until(th::LATCH_MS as u64 * 1000, |p| !p.read().latch_q);
                if !latch_down {
                    self.report(finding(codes::LATCH_CANNOT_CLEAR, 0, 0, FailAction::ResetToClear));
                }
                let first = self.wait_cut();
                if !first {
                    let r = self.pins.read();
                    let v = self.pins.vmot_mv();
                    self.report(if r.mot_allow { stuck_pass(leg::LATCH, v) } else { q4_short(v) });
                }
                self.pins.set_mcu_en(false);
                self.driven_mcu_en = false;
                first || self.wait_cut()
            }
        };
        self.pins.set_dock_test(false);
        self.pins.set_oc_test(false);
        if !cut && !self.quarantined {
            self.failed = true;
        }
        // DIR is an input of the supply gate: back to forward only now that the supply is cut (or hopeless)
        self.set_dir(MotorDir::Forward);
        cut
    }

    /// Idle check (once per tick, driver off): latch clear, supply absent, gate closed, STBY low, own pins as driven.
    /// Returns `false` on any finding.
    pub fn verify_idle(&mut self) -> bool {
        if self.powered || !self.cfg.interlock {
            return true;
        }
        let r = self.pins.read();
        let v = self.pins.vmot_mv();
        let mut ok = true;
        if r.latch_q {
            self.report(finding(codes::LATCH_SET_WITHOUT_ARM, 0, 0, FailAction::ResetToClear));
            ok = false;
        }
        if r.mot_allow {
            // the supply is ON at idle: a reset clears the latch, the TPL5010 path does that
            self.report(Finding { action: FailAction::ResetToClear, ..stuck_pass(first_open_leg(&r), v) });
            ok = false;
        } else if v > self.cfg.vmot_off_max_mv {
            self.report(q4_short(v));
            ok = false;
        }
        let m = own_pin_mismatch(&r, false, false, true);
        if m != 0 {
            for n in 1..=4u8 {
                if m & (1 << (n - 1)) != 0 {
                    self.report(finding(codes::GATE_INPUT_READBACK_MISMATCH.with_inst(n), n as i32, 0, FailAction::ResetToClear));
                }
            }
            ok = false;
        }
        // the dock path must be consistent with the hall (DOCK_TEST is off at idle)
        if let Some(f) = dock_consistency(&r) {
            self.report(f);
            ok = false;
        }
        // an open DIR gate input at the forward level is a polarity error (R96 / R97 against `forward_high`)
        if r.dir_rev {
            self.report(finding(codes::DIR_INVERTED, 0, 1, FailAction::Report));
            ok = false;
        }
        ok
    }

    /// `true` if EN/FAULT reads low while the driver should be running.
    pub fn fault_asserted(&mut self) -> bool {
        self.cfg.driver && self.powered && !self.pins.read().en_fault_high
    }

    /// Interlock readbacks for the POST and the tick checks (`Hal::interlock_state`).
    pub fn readback(&mut self) -> InterlockReadback {
        let r = self.pins.read();
        let (v, i) = (self.pins.vmot_mv(), self.pins.isense_mv());
        readback_from(&r, v, i, own_pin_mismatch(&r, self.driven_mcu_en, self.driven_stby, self.driven_clr))
    }

    // ------------------------------------------------------------------------------------------
    // POST
    // ------------------------------------------------------------------------------------------

    /// POST-S, the passive part (every boot): the motor is never driven, the supply must be absent.
    /// Findings are queued as events; returns the first one (`None` = clean).
    pub fn post_s(&mut self) -> Option<Finding> {
        self.clear_reported();
        let r = self.pins.read();
        let v = self.pins.vmot_mv();
        let mut first: Option<Finding> = None;
        let mut rep = |c: &mut Self, f: Finding| {
            c.report(f);
            first.get_or_insert(f);
        };
        // step 1: everything off
        if r.latch_q {
            rep(self, finding(codes::LATCH_SET_WITHOUT_ARM, 0, 0, FailAction::ResetToClear));
        }
        if r.mot_allow {
            rep(self, Finding { action: FailAction::ResetToClear, ..stuck_pass(first_open_leg(&r), v) });
        } else if v > th::VMOT_OFF_MV {
            rep(self, q4_short(v));
        }
        if !r.oc_ok {
            // OC_OK is 1 after power-up while MCU_EN is low: a latch that reads tripped now is stuck (fail-safe)
            rep(self, finding(codes::GATE_MCUEN_STUCK_BLOCK, 0, leg::OC, FailAction::Report));
        }
        let m = own_pin_mismatch(&r, false, false, true);
        for n in 1..=4u8 {
            if m & (1 << (n - 1)) != 0 {
                rep(self, finding(codes::GATE_INPUT_READBACK_MISMATCH.with_inst(n), n as i32, 0, FailAction::ResetToClear));
            }
        }
        let vbus = self.pins.vbus_mv();
        if vbus < th::VBUS_IMPLAUSIBLE_MV {
            rep(self, finding(codes::VOLTAGE_SENSE_IMPLAUSIBLE.with_inst(2), vbus as i32, 0, FailAction::Report));
        } else if vbus < th::VBUS_MIN_MV {
            rep(self, finding(codes::USB_SUPPLY_LOW, vbus as i32, 0, FailAction::Report));
        } else if vbus > th::VBUS_MAX_MV {
            rep(self, finding(codes::USB_OVERVOLT, vbus as i32, 0, FailAction::Report));
        }
        let vdd = self.pins.vdd_mv();
        if vdd != 0 {
            if vdd < th::VDD_MIN_MV {
                rep(self, finding(codes::RAIL_3V3_LOW, vdd as i32, 0, FailAction::Report));
            } else if vdd > th::VDD_MAX_MV {
                rep(self, finding(codes::RAIL_3V3_HIGH, vdd as i32, 0, FailAction::Report));
            }
        }
        let i = self.pins.isense_mv();
        if i >= th::ISENSE_SAT_MV {
            rep(self, finding(codes::ISENSE_SATURATED, i as i32, 0, FailAction::Report));
        } else if i > th::ISENSE_IDLE_MAX_MV {
            rep(self, finding(codes::ISENSE_IDLE_OFFSET, i as i32, 0, FailAction::Report));
        }
        // step 2: FFC, pod, dock path
        let tmag = self.pins.tmag_ack();
        if !r.pod_present && !tmag {
            rep(self, finding(codes::FFC_ABSENT, 0, 0, FailAction::Report));
        }
        if r.dock_n_low && (!r.pod_present || !tmag) {
            // docked is impossible without the pod board: the dock line is wrong (3-30-004)
            rep(self, finding(codes::FFC_DOCK_LINE_FAULT, 0, 0, FailAction::Report));
        }
        if let Some(f) = dock_consistency(&r) {
            rep(self, f);
        }
        if r.dir_rev {
            rep(self, finding(codes::DIR_INVERTED, 0, 1, FailAction::Report));
        }
        first
    }

    /// Run one self-test proof. Only with the driver off (the core calls it while SUSPENDED). Every proof ends in the
    /// safe state, also when it fails.
    pub fn selftest(&mut self, step: SelfTestStep) -> SelfTestOutcome {
        if self.powered || self.quarantined || !self.cfg.interlock {
            return SelfTestOutcome::Unsupported;
        }
        self.pins.kick();
        let out = match step {
            SelfTestStep::GateCut => self.proof_gate_cut(),
            SelfTestStep::DockGateBlock => self.proof_dock_dir(),
            SelfTestStep::OverCurrentCut => self.proof_over_current(),
            SelfTestStep::PassiveChecks => match self.post_s() {
                None => Ok(()),
                Some(f) => Err(Some(f)),
            },
            SelfTestStep::WatchdogProof => return SelfTestOutcome::Unsupported,
        };
        self.safe_state();
        self.disarm_n = 0;
        match out {
            Ok(()) => SelfTestOutcome::Passed,
            Err(Some(f)) => {
                let code = f.event.code;
                self.report(f);
                SelfTestOutcome::Failed(code)
            }
            // the proof could not be made (precondition missing): UNKNOWN, never passed
            Err(None) => SelfTestOutcome::Unsupported,
        }
    }

    /// Wait for the supply to reach a level, polling every 250 us and servicing the watchdog.
    fn post_wait(&mut self, ms: u32, mut cond: impl FnMut(&PinRead, u32) -> bool) -> bool {
        let to = ms as u64 * 1000;
        let t0 = self.pins.now_us();
        loop {
            self.pins.kick();
            let r = self.pins.read();
            let v = self.pins.vmot_mv();
            if cond(&r, v) {
                return true;
            }
            if self.pins.now_us().saturating_sub(t0) > to {
                return false;
            }
            self.pins.delay_us(250);
        }
    }

    /// Hold a condition for `ms` (e.g. "the supply stays off"): `false` as soon as it is violated.
    fn post_hold(&mut self, ms: u32, mut cond: impl FnMut(&PinRead, u32) -> bool) -> bool {
        let to = ms as u64 * 1000;
        let t0 = self.pins.now_us();
        loop {
            self.pins.kick();
            let r = self.pins.read();
            let v = self.pins.vmot_mv();
            if !cond(&r, v) {
                return false;
            }
            if self.pins.now_us().saturating_sub(t0) >= to {
                return true;
            }
            self.pins.delay_us(250);
        }
    }

    /// Supply fault to report when a cut did not happen: gate chain still conducting = the leg `leg_id` is stuck
    /// pass; gate off but supply up = Q4 shorted (not cuttable).
    fn not_cut(&mut self, leg_id: i32) -> Finding {
        let r = self.pins.read();
        let v = self.pins.vmot_mv();
        if r.mot_allow {
            stuck_pass(leg_id, v)
        } else {
            q4_short(v)
        }
    }

    /// Bring the supply up for the proofs: DOCK_TEST (undocked at the gate), reverse level, latch armed, MCU_EN high.
    /// Returns the failing finding if it does not come up.
    fn bring_up_reverse(&mut self) -> Result<(), Option<Finding>> {
        self.pins.set_dock_test(true);
        self.set_dir(MotorDir::Reverse);
        self.pins.set_latch_clear(false);
        self.pins.set_mcu_en(true);
        self.pins.arm_edge();
        let up = self.post_wait(th::VMOT_MOVE_MS, |r, v| r.mot_allow && v >= th::VMOT_UP_MV);
        if up {
            return Ok(());
        }
        let r = self.pins.read();
        let v = self.pins.vmot_mv();
        // DOCK_TEST must have forced the gate's DOCKED low, otherwise the proof is not what it claims to be
        if r.docked_h {
            return Err(None);
        }
        if !r.latch_q {
            return Err(Some(finding(codes::LATCH_CANNOT_SET, 0, 0, FailAction::Report)));
        }
        if !r.oc_ok {
            return Err(Some(finding(codes::GATE_MCUEN_STUCK_BLOCK, v as i32, leg::OC, FailAction::Report)));
        }
        if !r.dir_rev {
            return Err(Some(dir_input_finding(&r, self.cfg.forward_high, true)));
        }
        if r.mot_allow {
            // every gate input is true and the switch is on, but VMOT is absent: Q4 open or the shunt
            return Err(Some(finding(codes::VMOT_NOT_PRESENT, v as i32, 0, FailAction::Report)));
        }
        Err(Some(finding(codes::GATE_MCUEN_STUCK_BLOCK, v as i32, leg::UNKNOWN, FailAction::Report)))
    }

    /// Common start of every proof: safe state, the supply must be absent, the DIR gate input must read FORWARD at the
    /// forward level (else the polarity R96 / R97 does not match `forward_high`, `4-40-003`).
    fn precheck(&mut self) -> Result<PinRead, Option<Finding>> {
        self.safe_state();
        // a previous proof leaves the bulk capacitors discharging through the bleeder (tau about 10 ms)
        self.post_wait(60, |r, v| !r.mot_allow && v <= th::VMOT_OFF_MV);
        let r0 = self.pins.read();
        let v0 = self.pins.vmot_mv();
        if r0.mot_allow || v0 > th::VMOT_OFF_MV {
            // nothing can be proven on a board whose supply is already up at idle
            return Err(Some(if r0.mot_allow { stuck_pass(first_open_leg(&r0), v0) } else { q4_short(v0) }));
        }
        if r0.dir_rev {
            return Err(Some(finding(codes::DIR_INVERTED, 0, 1, FailAction::Report)));
        }
        Ok(r0)
    }

    /// POST steps 1 and 3 to 8 (INTERLOCK.md F): the `MCU_EN` leg and the latch leg each cut the supply alone.
    fn proof_gate_cut(&mut self) -> Result<(), Option<Finding>> {
        self.precheck()?;
        // step 3: arm with MCU_EN low: the latch sets, the supply stays off (Q8 leg blocks)
        self.pins.set_latch_clear(false);
        self.pins.arm_edge();
        self.pins.delay_us(th::LATCH_MS * 1000);
        let r = self.pins.read();
        if !r.latch_q {
            return Err(Some(finding(codes::LATCH_CANNOT_SET, 0, 0, FailAction::Report)));
        }
        if !self.post_hold(10, |r, v| !r.mot_allow && v <= th::VMOT_OFF_MV) {
            let v = self.pins.vmot_mv();
            return Err(Some(if self.pins.read().mot_allow { stuck_pass(leg::MCU_EN, v) } else { q4_short(v) }));
        }
        // supply up through the reverse + DOCK_TEST path (nothing moves: STBY is low)
        self.pins.set_latch_clear(true);
        self.pins.delay_us(th::LATCH_MS * 1000);
        self.bring_up_reverse()?;
        // step 7: cut with LATCH_CLR_N only, MCU_EN stays high
        self.pins.set_latch_clear(true);
        let latch_down = self.post_wait(th::LATCH_MS, |r, _| !r.latch_q);
        if !latch_down {
            return Err(Some(finding(codes::LATCH_CANNOT_CLEAR, 0, 0, FailAction::Report)));
        }
        if !self.post_wait(th::VMOT_MOVE_MS, |r, v| !r.mot_allow && v < th::VMOT_CUT_MV) {
            return Err(Some(self.not_cut(leg::LATCH)));
        }
        // step 8: re-arm, then cut with MCU_EN only; the latch stays armed
        self.pins.set_latch_clear(false);
        self.pins.arm_edge();
        if !self.post_wait(th::VMOT_MOVE_MS, |r, v| r.mot_allow && v >= th::VMOT_UP_MV) {
            return Err(Some(finding(codes::VMOT_NOT_PRESENT, self.pins.vmot_mv() as i32, 0, FailAction::Report)));
        }
        self.pins.set_mcu_en(false);
        if !self.post_wait(th::VMOT_MOVE_MS, |r, v| !r.mot_allow && v < th::VMOT_CUT_MV) {
            return Err(Some(self.not_cut(leg::MCU_EN)));
        }
        Ok(())
    }

    /// POST steps 4 to 6: the dock leg and the DIR leg. Undocked at the gate (DOCK_TEST), forward must block, reverse
    /// must conduct and the DIR_REV readback must follow, forward again must cut.
    fn proof_dock_dir(&mut self) -> Result<(), Option<Finding>> {
        self.precheck()?;
        // step 4: DOCK_TEST + forward level, latch armed, MCU_EN high: both dock gates closed, the supply stays off
        self.pins.set_dock_test(true);
        self.set_dir(MotorDir::Forward);
        self.pins.set_latch_clear(false);
        self.pins.set_mcu_en(true);
        self.pins.arm_edge();
        self.pins.delay_us(th::LATCH_MS * 1000);
        let r = self.pins.read();
        if r.docked_h {
            return Err(None); // DOCK_TEST did not force the gate input: the proof is inconclusive
        }
        if !r.latch_q || !r.oc_ok {
            return Err(Some(if !r.latch_q { finding(codes::LATCH_CANNOT_SET, 0, 0, FailAction::Report) } else { finding(codes::GATE_MCUEN_STUCK_BLOCK, 0, leg::OC, FailAction::Report) }));
        }
        if !self.post_hold(th::BLOCK_HOLD_MS, |r, v| !r.mot_allow && v <= th::VMOT_OFF_MV) {
            let r = self.pins.read();
            let v = self.pins.vmot_mv();
            return Err(Some(if r.mot_allow { stuck_pass(leg::DOCK, v) } else { q4_short(v) }));
        }
        // step 5: reverse level: the Q10 path conducts, DIR_REV follows
        self.set_dir(MotorDir::Reverse);
        if !self.post_wait(th::VMOT_MOVE_MS, |r, v| r.mot_allow && v >= th::VMOT_UP_MV && r.dir_rev) {
            let r = self.pins.read();
            let v = self.pins.vmot_mv();
            if !r.dir_rev {
                return Err(Some(dir_input_finding(&r, self.cfg.forward_high, true)));
            }
            return Err(Some(if r.mot_allow { finding(codes::VMOT_NOT_PRESENT, v as i32, 0, FailAction::Report) } else { finding(codes::GATE_MCUEN_STUCK_BLOCK, v as i32, leg::DIR, FailAction::Report) }));
        }
        // step 6: forward again: the DIR leg cuts
        self.set_dir(MotorDir::Forward);
        if !self.post_wait(th::VMOT_MOVE_MS, |r, v| !r.mot_allow && v < th::VMOT_CUT_MV) {
            let r = self.pins.read();
            let v = self.pins.vmot_mv();
            return Err(Some(if r.mot_allow { finding(codes::GATE_DIRREV_STUCK_PASS, v as i32, leg::DIR, FailAction::Report) } else { q4_short(v) }));
        }
        Ok(())
    }

    /// POST steps 9 and 10: the over-current leg (comparator, latch, Q13) cuts the supply when `OC_TEST` lowers the
    /// reference, and the latch clears only by cycling `MCU_EN`.
    fn proof_over_current(&mut self) -> Result<(), Option<Finding>> {
        let r0 = self.precheck()?;
        if !r0.oc_ok {
            return Err(Some(finding(codes::GATE_MCUEN_STUCK_BLOCK, 0, leg::OC, FailAction::Report)));
        }
        self.bring_up_reverse()?;
        // the coils hold (STBY high, no step): the supply current is the holding current
        self.pins.drive_en_fault_low(false);
        self.pins.set_stby(true);
        self.driven_stby = true;
        self.pins.delay_us(self.cfg.stby_wake_us);
        let ready = self.post_wait(self.cfg.driver_ready_ms, |r, _| r.en_fault_high);
        let hold_t0 = self.pins.now_us();
        let i_mv = self.pins.isense_mv();
        if !ready || i_mv < th::OC_PROOF_MIN_MV {
            // no holding current (motor not connected, driver not ready): the proof can not be made
            self.pins.set_stby(false);
            self.driven_stby = false;
            return Err(None);
        }
        // trip: OC_TEST lowers the reference to about 45 mA
        self.pins.set_oc_test(true);
        let tripped = self.post_wait(th::OC_TRIP_MS, |r, _| !r.oc_ok);
        // never hold the coils longer than needed
        self.pins.set_stby(false);
        self.driven_stby = false;
        let held_ms = self.pins.now_us().saturating_sub(hold_t0) / 1000;
        let _ = held_ms; // bounded by OC_HOLD_MAX_MS through the waits above (10 ms + 10 ms)
        if !tripped {
            self.pins.set_oc_test(false);
            return Err(Some(finding(codes::GATE_INPUT_READBACK_MISMATCH.with_inst(pin::OC), i_mv as i32, 1, FailAction::Report)));
        }
        if !self.post_wait(th::VMOT_MOVE_MS, |r, v| !r.mot_allow && v < th::VMOT_CUT_MV) {
            self.pins.set_oc_test(false);
            return Err(Some(self.not_cut(leg::OC)));
        }
        // step 10: OC_TEST off, the latch stays tripped until MCU_EN is cycled; then OC_OK is 1 again, the supply
        // stays off (latch not armed)
        self.pins.set_oc_test(false);
        if self.pins.read().oc_ok {
            // the latch released by itself: it is not a latch
            return Err(Some(finding(codes::GATE_INPUT_READBACK_MISMATCH.with_inst(pin::OC), i_mv as i32, 2, FailAction::Report)));
        }
        self.pins.set_mcu_en(false);
        self.pins.set_latch_clear(true);
        self.pins.delay_us(1_000);
        self.pins.set_mcu_en(true);
        let cleared = self.post_wait(th::OC_CLEAR_MS, |r, _| r.oc_ok);
        // the latch is not armed, so the supply must not come back (it may still be discharging through the bleeder)
        let off = self.post_wait(th::VMOT_MOVE_MS, |r, v| !r.mot_allow && v < th::VMOT_CUT_MV);
        if !cleared {
            return Err(Some(finding(codes::GATE_MCUEN_STUCK_BLOCK, 0, leg::OC, FailAction::Report)));
        }
        if !off {
            return Err(Some(self.not_cut(leg::LATCH)));
        }
        Ok(())
    }
}

/// The readback snapshot RB1..RB10 from one pin read (Rev A has no mid-chain readbacks: RB2 / RB3 are `None`).
pub fn readback_from(r: &PinRead, vmot_mv: u32, isense_mv: u32, own_pin_mismatch: u8) -> InterlockReadback {
    InterlockReadback {
        pgate: Some(!r.mot_allow),
        pg_mid1: None,
        pg_mid2: None,
        docked_h: Some(r.docked_h),
        dir_rev: Some(r.dir_rev),
        latch_q: Some(r.latch_q),
        vmot_mv: Some(vmot_mv.min(u16::MAX as u32) as u16),
        i_sense_mv: Some(isense_mv.min(u16::MAX as u32) as u16),
        own_pin_mismatch,
        driver_fault: Some(!r.en_fault_high),
        oc_ok: Some(r.oc_ok),
        mot_allow: Some(r.mot_allow),
        pod_present: Some(r.pod_present),
    }
}

/// The DOCKED path must agree with the hall: `DOCKED_H = NOT DOCK_N` while `DOCK_TEST` is off.
pub fn dock_consistency(r: &PinRead) -> Option<Finding> {
    if r.dock_n_low && !r.docked_h {
        // hall says docked, the gate input says not docked: Q7 / Q12 block the dock leg
        Some(finding(codes::GATE_DOCK_STUCK_BLOCK, 0, 0, FailAction::Report))
    } else if !r.dock_n_low && r.docked_h {
        // the gate input says docked, the hall does not: the dock leg is stuck open (over-delivery class)
        Some(finding(codes::GATE_DOCK_STUCK_PASS, 0, 1, FailAction::Report))
    } else {
        None
    }
}

/// Finding for a `DIR_REV` readback that does not follow the commanded level. `reverse_commanded`: which level was set.
/// Reads high at the forward level = polarity inverted (R96 / R97 against `forward_high`): `4-40-003`.
/// Low at the reverse level = the DIR path is dead: `1-07-007` (MOT_DIR). Used where the readback is NOT what was
/// commanded.
fn dir_input_finding(r: &PinRead, _forward_high: bool, reverse_commanded: bool) -> Finding {
    if reverse_commanded && !r.dir_rev {
        // commanded reverse, gate sees forward. Inverted polarity and a dead path look the same here;
        // the forward-level idle check (dir_rev high at forward) tells the two apart, so report the polarity code
        // only when the forward level read as reverse (checked at idle). Here: the path does not follow.
        finding(codes::GATE_INPUT_READBACK_MISMATCH.with_inst(pin::MOT_DIR), 0, 1, FailAction::Report)
    } else {
        // commanded forward, gate sees reverse: wrong polarity fitted / configured
        finding(codes::DIR_INVERTED, 0, 1, FailAction::Report)
    }
}
