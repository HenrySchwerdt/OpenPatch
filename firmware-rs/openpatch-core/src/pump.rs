//! Pump controller: wires delivery engine, safety supervisor, reservoir and log to the HAL and
//! exposes command-level operations plus the protocol dispatcher. The only module that knows all
//! the others. Behaviour is identical to `firmware/core/src/pump_controller.c` (differential tests).

use crate::delivery::{BasalSchedule, BasalSeg, DeliveryEngine, EngineEvents};
use crate::diag::{codes, DiagCode, DiagNote, Raise};
use crate::drive_cal::DriveCal;
use crate::faults::Faults;
use crate::hal::{Buzzer, Hal, MotorFault};
use crate::limits::*;
use crate::log::{EventLog, EventType, REL_CHARGER, REL_COMMAND};
use crate::pod::{ActivateArgs, DeliveryState, PodState, Role};
use crate::reservoir::Reservoir;
use crate::safety::{Observation, SafetySupervisor};
use crate::units::*;
use heapless as _;
use openpatch_proto::{
    self as proto, st, Ccm, Command, CommandBody, Error, History, Response, Session, Status, FRAME_MAX,
    HIST_MAX_PER_RESPONSE, RSP_BIT, SUBOP_FILL, SUBOP_PRIME,
};

/// Behaviour switches. `STRICT` is the production setting; `RELAXED` is an explicit opt-in for unit
/// tests and first bench bring-up.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PumpConfig {
    /// After every fill / draw, `Resume` is refused until a prime has completed.
    pub require_prime_after_fill: bool,
    /// Hourly cap = true rolling 60 minutes reduced by the calibration tolerance margin
    /// ([`HOURLY_CAL_MARGIN_PCT`]). `false` = the frozen C reference's 60 wall-clock minute buckets without margin
    /// (differential tests only).
    pub strict_hourly: bool,
    /// Backlash / lost-motion take-up volume (mU) run before the first prime after a draw
    /// (`limits::TAKEUP_MU_AFTER_DRAW`); 0 = none (C reference). With a take-up the prime runs in watchdog-safe chunks.
    pub takeup_mu: u32,
    /// Draw mode: own current stall threshold (`DRAW_STALL_CURRENT_MA`), rate capped by the fill needle gauge, chunk
    /// length bound to 0.8 s. `false` = the C-compatible fixed chunks and the occlusion current threshold.
    pub strict_draw: bool,
    /// Fill needle of the refill syringe / vial (caps the draw rate, `limits::FillNeedle`). Default 29G.
    pub fill_needle: FillNeedle,
    /// `Resume` is refused with `NoSchedule` while no basal schedule is held (never silently deliver 0 U/h).
    pub require_schedule_on_resume: bool,
    /// An active pod that restarts unexpectedly (anything but a commanded reset) raises a FAULT-severity
    /// `7-74-002` record: ALARM flag, buzzer, notification, `Resume` refused until acknowledged (H3).
    pub alarm_on_unplanned_reset: bool,
}

impl PumpConfig {
    pub const STRICT: PumpConfig = PumpConfig {
        require_prime_after_fill: true,
        strict_hourly: true,
        takeup_mu: TAKEUP_MU_AFTER_DRAW,
        strict_draw: true,
        fill_needle: FillNeedle::G29,
        require_schedule_on_resume: true,
        alarm_on_unplanned_reset: true,
    };
    pub const RELAXED: PumpConfig = PumpConfig {
        require_prime_after_fill: false,
        strict_hourly: false,
        takeup_mu: 0,
        strict_draw: false,
        fill_needle: FillNeedle::G29,
        require_schedule_on_resume: false,
        alarm_on_unplanned_reset: false,
    };
}

/// Unsolicited notification for the Alert characteristic.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Notification {
    /// Draw progress: volume confirmed so far (mU).
    DrawProgress(u32),
    /// Draw finished: actual drawn volume (mU).
    DrawDone(u32),
    /// Draw ended early by a stall / end-stop: actual drawn volume (mU).
    DrawStalled(u32),
    /// Fault bits newly latched.
    Fault(u16),
}

/// Draw job states (wire values of `DRAW_STATE`).
pub use proto::draw as draw_state;

#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct DrawJob {
    pub(crate) state: u8,
    pub(crate) requested_mu: u32,
    pub(crate) remaining_steps: u32,
    /// Reverse steps commanded and executed so far.
    pub(crate) executed_steps: u32,
    /// Reverse steps confirmed by the angle sensor so far (conservative: min per chunk).
    pub(crate) confirmed_steps: u32,
    pub(crate) high_current: u8,
    pub(crate) drawn_mu: u32,
    /// Reverse step rate of this job (pulses per second).
    pub(crate) pps: u32,
}

pub struct Pump<H: Hal> {
    pub(crate) hal: H,
    pub(crate) pod: PodState,
    pub(crate) cal: DriveCal,
    pub(crate) cal_valid: bool,
    pub(crate) pcal: PulseCal,
    pub(crate) cfg: PumpConfig,
    pub(crate) de: DeliveryEngine,
    pub(crate) sv: SafetySupervisor,
    pub(crate) res: Reservoir,
    pub(crate) log: EventLog,
    pub(crate) last_tick: Millis,
    pub(crate) low_res_reported: bool,
    pub(crate) low_batt_reported: bool,
    pub(crate) tick_overruns: u32,
    pub(crate) prime_required: bool,
    pub(crate) draw: DrawJob,
    pub(crate) notes: heapless::Deque<Notification, 8>,
    pub(crate) notify_seq: u16,
    pub(crate) last_motor_fault: Option<crate::hal::MotorFault>,
    pub(crate) peak_ma: Option<u16>,
    /// Record id of the HAL-level cause raised by the burst in progress (0 = none): the core's own
    /// record (for example `7-70-005`) links to it (cause chain).
    pub(crate) hal_rec: u32,
    /// Last self-test (`SELFTEST_STATE`).
    pub(crate) selftest: proto::SelfTestState,
    /// Pending `SELFTEST_PROGRESS` notification argument.
    pub(crate) selftest_note: Option<u32>,
    /// Leadscrew angle at the end of the last tick, and whether the motor was driven since (H15 pressure anomaly check).
    pub(crate) rest_angle: Option<i64>,
    pub(crate) moved: bool,
    /// Write event type 31 for new diagnostic records (off by default, see [`Pump::set_diag_history`]).
    pub(crate) diag_history: bool,
    /// Next record id not yet written as event 31.
    pub(crate) diag_hist_next: u32,
    /// Forward take-up steps still owed before the next prime (set by a draw that moved the plunger back).
    pub(crate) takeup_pending: u32,
    /// Why the MCU started this boot.
    pub(crate) boot_cause: crate::hal::ResetCause,
    /// Draw-mode stall threshold in force (mA).
    pub(crate) draw_stall_ma: u16,
}

impl<H: Hal> Pump<H> {
    /// `cal = None` or an invalid record leaves the pump permanently without delivery:
    /// `NO_CALIBRATION` is latched and cannot be acknowledged. Uses [`PumpConfig::STRICT`].
    pub fn new(mut hal: H, cal: Option<&DriveCal>, capacity: MilliUnits, restored_next_event_id: u32) -> Self {
        let pcal = cal.filter(|_| DriveCal::validate(cal).is_ok()).and_then(|c| c.pulse_cal());
        let cal_valid = pcal.is_some();
        let cal_rec = match (cal_valid, cal) {
            (true, Some(c)) => *c,
            _ => DriveCal::default(),
        };
        let pcal = pcal.unwrap_or(PulseCal::NONE);
        let t = hal.time_ms();
        let ang = hal.angle_read().unwrap_or(AngleCounts(0));
        let mut p = Pump {
            pod: PodState::default(),
            cal: cal_rec,
            cal_valid,
            pcal,
            cfg: PumpConfig::STRICT,
            de: DeliveryEngine::new(pcal),
            sv: SafetySupervisor::new(t, ang, pcal),
            res: Reservoir::new(capacity, pcal),
            log: EventLog::restore(restored_next_event_id),
            last_tick: t,
            low_res_reported: false,
            low_batt_reported: false,
            tick_overruns: 0,
            prime_required: false,
            draw: DrawJob::default(),
            notes: heapless::Deque::new(),
            notify_seq: 0,
            last_motor_fault: None,
            peak_ma: None,
            hal_rec: 0,
            selftest: proto::SelfTestState::default(),
            selftest_note: None,
            rest_angle: None,
            moved: false,
            diag_history: false,
            diag_hist_next: 0,
            takeup_pending: 0,
            boot_cause: crate::hal::ResetCause::PowerOn,
            draw_stall_ma: DRAW_STALL_CURRENT_MA,
            hal,
        };
        p.pod.docked = p.hal_docked(); // no event for the boot state
        p.sv.set_docked(p.pod.docked);
        p.hal.motor_enable(false);
        p.hal.buzzer(Buzzer::Off);
        p.log_ev(EventType::Boot, 0, 0);
        p.sv.raise(Raise::new(codes::BOOT).a(FW_VERSION as i32));
        p.raise_reset_cause();
        p.observe();
        if !p.sv.faults().is_empty() {
            p.sync_faults(Faults::NONE); // e.g. NO_CALIBRATION: log + alarm, driver stays off
        }
        p
    }

    pub fn set_config(&mut self, cfg: PumpConfig) {
        self.cfg = cfg;
        self.sv.set_c_compat(!cfg.strict_hourly);
    }
    pub fn config(&self) -> PumpConfig {
        self.cfg
    }
    pub fn pulse_cal(&self) -> PulseCal {
        self.pcal
    }
    pub fn prime_required(&self) -> bool {
        self.prime_required
    }
    pub fn draw_state(&self) -> u8 {
        self.draw.state
    }
    /// Volume drawn so far / in the last finished draw job (step-exact, conservative), mU.
    pub fn draw_drawn(&self) -> MilliUnits {
        MilliUnits(self.draw.drawn_mu)
    }
    pub fn draw_running(&self) -> bool {
        self.draw.state == draw_state::DRAWING
    }
    /// Next pending notification for the Alert characteristic.
    pub fn take_notification(&mut self) -> Option<Notification> {
        self.notes.pop_front()
    }
    pub(crate) fn notify(&mut self, n: Notification) {
        if self.notes.is_full() {
            let _ = self.notes.pop_front();
        }
        let _ = self.notes.push_back(n);
    }

    /// Encode + seal the next pending notification as a frame (type 0x90, own nonce direction).
    pub fn notification_frame<C: Ccm>(&mut self, session: &mut Session<C>, encrypt: bool, out: &mut [u8]) -> Option<Result<usize, Error>> {
        // legacy notifications first, then the diagnostic ones (kinds 5 to 7)
        let mut record: Option<crate::diag::DiagRecord> = None;
        let (kind, arg) = if let Some(n) = self.take_notification() {
            match n {
                Notification::DrawProgress(v) => (proto::notify::DRAW_PROGRESS, v),
                Notification::DrawDone(v) => (proto::notify::DRAW_DONE, v),
                Notification::DrawStalled(v) => (proto::notify::DRAW_STALLED, v),
                Notification::Fault(b) => (proto::notify::FAULT, b as u32),
            }
        } else if let Some(d) = self.take_diag_note() {
            match d {
                DiagNote::Raised(r) => {
                    record = Some(r);
                    (proto::notify::DIAG_RAISED, r.code.0)
                }
                DiagNote::Cleared(c) => (proto::notify::DIAG_CLEARED, c.0),
            }
        } else if let Some(p) = self.selftest_note.take() {
            (proto::notify::SELFTEST_PROGRESS, p)
        } else {
            return None;
        };
        let mut body = [0u8; 64];
        let r = proto::encode_notification_payload_ex(kind, arg, record.as_ref(), &mut body).and_then(|l| {
            let seq = self.notify_seq;
            self.notify_seq = if seq >= proto::SEQ_MAX { 0 } else { seq + 1 };
            session.seal_notification(proto::notify::FRAME_TYPE, seq, encrypt, &body[..l], out)
        });
        Some(r)
    }

    // ---- accessors ---------------------------------------------------------------
    pub fn hal(&self) -> &H {
        &self.hal
    }
    pub fn hal_mut(&mut self) -> &mut H {
        &mut self.hal
    }
    pub fn pod(&self) -> &PodState {
        &self.pod
    }
    pub fn engine(&self) -> &DeliveryEngine {
        &self.de
    }
    pub fn supervisor(&self) -> &SafetySupervisor {
        &self.sv
    }
    pub fn reservoir(&self) -> &Reservoir {
        &self.res
    }
    pub fn log(&self) -> &EventLog {
        &self.log
    }
    pub fn calibration(&self) -> Option<&DriveCal> {
        self.cal_valid.then_some(&self.cal)
    }
    pub fn tick_overruns(&self) -> u32 {
        self.tick_overruns
    }
    /// Direct access for the platform layer and tests (limits, thresholds, restores).
    #[doc(hidden)]
    pub fn supervisor_mut(&mut self) -> &mut SafetySupervisor {
        &mut self.sv
    }
    #[doc(hidden)]
    pub fn engine_mut(&mut self) -> &mut DeliveryEngine {
        &mut self.de
    }
    #[doc(hidden)]
    pub fn reservoir_mut(&mut self) -> &mut Reservoir {
        &mut self.res
    }

    // ---- helpers -----------------------------------------------------------------
    pub(crate) fn now(&mut self) -> Millis {
        let t = self.hal.time_ms();
        self.sv.set_time(t);
        t
    }
    fn now_s(&mut self) -> u32 {
        (self.now().0 / 1000) as u32
    }
    pub(crate) fn log_ev(&mut self, kind: EventType, a: i32, b: i32) {
        let t = self.now_s();
        self.log.append(t, kind, a, b);
    }


    /// New faults: log, stop all delivery, alarm, keep the driver off, notify the phone.
    pub(crate) fn sync_faults(&mut self, before: Faults) {
        let added = self.sv.faults() & !before;
        if added.is_empty() {
            return;
        }
        self.log_ev(EventType::Fault, added.bits() as i32, 0);
        self.de.suspend();
        self.hal.motor_enable(false);
        self.hal.buzzer(Buzzer::Alarm);
        self.notify(Notification::Fault(added.bits()));
    }

    pub(crate) fn observe(&mut self) {
        let t = self.now();
        let battery_mv = self.hal.battery_mv();
        let reservoir = self.res_for_observe();
        let angle = match self.hal.angle_read() {
            Some(a) => a,
            None => {
                // angle sensor lost: nothing can be verified any more
                if self.pod.active && !self.de.is_suspended() {
                    self.sv.raise(Raise::new(codes::ANGLE_CHANNEL_LOST));
                }
                self.sv.last_angle()
            }
        };
        self.sv.observe(t, &Observation { battery_mv, reservoir, angle });
        if self.sv.battery_low() && !self.low_batt_reported {
            self.low_batt_reported = true;
            let mv = self.hal.battery_mv();
            self.log_ev(EventType::LowBattery, mv as i32, 0);
            // inst 1 = bench VBUS source
            self.sv.raise(Raise::new(codes::BATTERY_LOW).inst(1).a(mv as i32).b(BATTERY_LOW_MV as i32));
        } else if !self.sv.battery_low() {
            self.low_batt_reported = false;
        }
        if battery_mv >= BATTERY_LOW_MV + BATTERY_HYSTERESIS_MV {
            self.sv.diag_mut().clear(codes::BATTERY_LOW); // condition gone, with the 100 mV hysteresis
        }
    }

    /// Unfilled reservoirs are not monitored (no alarm at first boot).
    fn res_for_observe(&self) -> Option<MilliUnits> {
        self.res.is_filled().then(|| self.res.remaining())
    }

    /// Supervisor approval, plus: never step without the angle sensor (latches INTERNAL instead).
    fn approve_blind_safe(&mut self, now: Millis, requested: Pulses) -> Pulses {
        if requested.0 > 0 && self.hal.angle_read().is_none() {
            self.sv.raise(Raise::new(codes::ANGLE_CHANNEL_LOST).c(requested.0));
            return Pulses(0);
        }
        self.sv.approve_steps(now, requested, self.res.remaining())
    }

    fn run_motor(&mut self, steps: Pulses) -> Pulses {
        self.moved = true;
        self.hal_rec = 0;
        self.hal.motor_enable_dir(crate::hal::MotorDir::Forward);
        let r = self.hal.motor_step_ex(steps);
        self.hal.motor_enable(false);
        let done = Pulses(r.executed.0.min(steps.0));
        self.res.consume(done);
        if r.drv_fault {
            self.hal_rec = self.sv.raise(Raise::new(codes::DRIVER_FAULT_IN_BURST).a(r.peak_ma.unwrap_or(0) as i32).c(done.0));
        }
        if !r.vmot_ok {
            self.hal_rec = self.sv.raise(Raise::new(codes::VMOT_NOT_PRESENT).c(done.0));
        }
        if let Some(f) = self.hal.motor_fault() {
            // The HAL knows why the burst failed: remember it (precise cause for logs / alarm).
            self.last_motor_fault = Some(f);
            self.raise_motor_fault(f, done);
        }
        self.drain_hal_diag();
        let peak = r.peak_ma.or_else(|| self.hal.motor_current_peak_ma());
        if let Some(p) = peak {
            self.peak_ma = Some(self.peak_ma.map_or(p, |q| q.max(p)));
        }
        self.sv.observe_motor_burst(done, peak);
        done
    }

    /// Raises the catalogue code of a HAL motor fault (the HAL reports, the core decides policy).
    /// Refused requests (forward while undocked, reverse while docked) have no hardware cause: the
    /// core's own `7-70-005` follows from the burst that did not run.
    pub(crate) fn raise_motor_fault(&mut self, f: MotorFault, executed: Pulses) {
        let code: Option<DiagCode> = match f {
            MotorFault::Driver => Some(codes::DRIVER_FAULT_IN_BURST),
            MotorFault::SupplyMissing => Some(codes::VMOT_NOT_PRESENT),
            MotorFault::SupplyUnexpected => Some(codes::VMOT_STUCK_ON),
            MotorFault::InterlockFailed => Some(codes::INTERLOCK_FAILED_LATCH),
            MotorFault::Timeout => Some(codes::STEP_COUNT_SHORT),
            MotorFault::ReverseWhileDocked => Some(codes::REVERSE_REQUESTED_WHILE_DOCKED),
            MotorFault::ForwardWhileUndocked => None,
        };
        match code {
            Some(c) => self.hal_rec = self.sv.raise(Raise::new(c).c(executed.0)),
            None => {
                // no hardware cause: the burst simply did not run, the engine record says so
                let kind = if f == MotorFault::ForwardWhileUndocked { 1 } else { 2 };
                self.hal_rec = self.sv.raise(Raise::new(codes::STEPS_SHORT_OF_APPROVAL).a(executed.0 as i32).inst(kind));
            }
        }
    }

    /// The burst executed fewer steps than the supervisor approved: raise `7-70-005`, linked to
    /// the HAL-level cause when there is one.
    pub(crate) fn raise_steps_short(&mut self, executed: Pulses, approved: Pulses) {
        let r = Raise::new(codes::STEPS_SHORT_OF_APPROVAL).a(executed.0 as i32).b(approved.0 as i32);
        let cause = self.hal_rec;
        self.sv.raise(if cause != 0 { r.caused_by(cause) } else { r });
    }

    /// Boot: why did the MCU start? Anything other than power-on or a commanded reset is an unexpected
    /// reset (`7-74-002`; a brown-out also `1-01-002`, its root). The pod boots SUSPENDED anyway.
    fn raise_reset_cause(&mut self) {
        use crate::hal::ResetCause;
        let cause = self.hal.reset_cause();
        self.boot_cause = cause;
        let crumb = self.hal.breadcrumb();
        let code = match cause {
            ResetCause::PowerOn | ResetCause::Commanded => return,
            ResetCause::Watchdog => 1,
            ResetCause::Brownout => 2,
            ResetCause::Lockup => 3,
            ResetCause::Other => 4,
        };
        let mut root = 0;
        if cause == ResetCause::Brownout {
            let mv = self.hal.battery_mv();
            root = self.sv.raise(Raise::new(codes::BROWNOUT_RESET).a(mv as i32));
        }
        let r = Raise::new(codes::UNEXPECTED_RESET).a(code).c(crumb);
        self.sv.raise(if root != 0 { r.caused_by(root) } else { r });
    }

    /// Events the HAL detected on its own (as data): raised with the HAL's own code.
    pub(crate) fn drain_hal_diag(&mut self) {
        while let Some(e) = self.hal.take_diag() {
            self.hal_rec = self.sv.raise(Raise::new(e.code).a(e.ctx_a).b(e.ctx_b).c(e.ctx_c));
        }
    }

    /// Next pending diagnostic notification (record raised / cleared) for the Alert characteristic.
    pub fn take_diag_note(&mut self) -> Option<DiagNote> {
        self.sv.diag_mut().take_note()
    }

    /// Also write event type 31 `DIAG` (a = code, b = `ctx_a`) to the event log for every new
    /// diagnostic record, so a v1-only history reader sees that a record exists. Off by default:
    /// the C reference never writes it and the differential tests compare the event log.
    pub fn set_diag_history(&mut self, on: bool) {
        self.diag_history = on;
        if on {
            self.diag_hist_next = self.sv.diag().next_id();
        }
    }

    fn log_diag_history(&mut self) {
        if !self.diag_history {
            return;
        }
        let end = self.sv.diag().next_id();
        let mut id = self.diag_hist_next.max(self.sv.diag().oldest_id());
        while id != end {
            if let Some(r) = self.sv.diag().record(id) {
                if r.flags & openpatch_diag::flags::CLEARED == 0 {
                    self.log_ev(EventType::Diag, r.code.0 as i32, r.ctx_a);
                }
            }
            id = id.wrapping_add(1);
            if id == 0 {
                id = 1;
            }
        }
        self.diag_hist_next = end;
    }

    /// Diagnostic summary for `DIAG_SUMMARY`.
    pub fn diag_summary(&self) -> proto::DiagSummary {
        self.sv.diag().summary()
    }

    /// `ClearDiag`. `NotFound` when the code is not active, `NotClearable` when it is latched and
    /// its verification test has not passed, or when the cause persists (battery, calibration,
    /// wear, empty reservoir). Returns the number of cleared records.
    pub fn clear_diag(&mut self, code: DiagCode) -> Result<usize, Error> {
        let before = self.sv.faults();
        // verification tests of latched codes (A01/A02, S04..S06, ...) are WP-3: nothing is verified yet
        let r = {
            let persist_bits = self.sv.persisting(Faults::ALL);
            self.sv.diag_mut().clear_diag(code, false, |a| {
                crate::diag::legacy_bit(a.code, a.severity).is_some_and(|b| persist_bits.bits() & (1 << b) != 0)
            })
        };
        self.sv.resync_faults();
        let cleared = before & !self.sv.faults();
        if !cleared.is_empty() {
            self.log_ev(EventType::Ack, cleared.bits() as i32, 0);
        }
        if self.sv.faults().is_empty() {
            self.hal.buzzer(Buzzer::Off);
        }
        self.log_diag_history();
        r.map_err(|e| match e {
            crate::diag::ClearError::NotFound => Error::NotFound,
            crate::diag::ClearError::NotClearable => Error::NotClearable,
        })
    }

    /// `RunSelfTest`: refused while not suspended, while a draw runs, or while a test runs. The
    /// core sequences the steps; the pin-level proofs are the HAL's (`Hal::selftest`). A proof the
    /// HAL cannot do stays UNKNOWN (neither passed nor failed). Ends with `7-74-006 POST_RESULT`
    /// (`ctx_a` = steps passed mask, `ctx_b` = steps failed mask).
    pub fn run_self_test(&mut self, sub_op: u8) -> Result<(), Error> {
        use crate::hal::{SelfTestOutcome, SelfTestStep};
        if !(proto::selftest::SUBOP_POST_S..=proto::selftest::SUBOP_WATCHDOG).contains(&sub_op) {
            return Err(Error::BadArg);
        }
        if !self.de.is_suspended() || self.draw_running() || self.selftest.state == proto::selftest::RUNNING {
            return Err(Error::SelfTestRefused);
        }
        self.selftest = proto::SelfTestState { state: proto::selftest::RUNNING, kind: sub_op, ..Default::default() };
        let steps: &[SelfTestStep] = match sub_op {
            proto::selftest::SUBOP_POST_S => &[SelfTestStep::PassiveChecks],
            proto::selftest::SUBOP_POST_A => &[SelfTestStep::GateCut, SelfTestStep::DockGateBlock, SelfTestStep::OverCurrentCut, SelfTestStep::ReverseDockedBlock],
            proto::selftest::SUBOP_WATCHDOG => &[SelfTestStep::WatchdogProof],
            _ => &[],
        };
        let faults_before = self.sv.faults();
        let (mut passed, mut failed) = (0u16, 0u16);
        for (i, step) in steps.iter().enumerate() {
            match self.hal.selftest(*step) {
                SelfTestOutcome::Unsupported => {}
                SelfTestOutcome::Passed => passed |= 1 << i,
                SelfTestOutcome::Failed(code) => {
                    failed |= 1 << i;
                    self.hal_rec = self.sv.raise(Raise::new(code).during_post());
                }
            }
        }
        self.selftest = proto::SelfTestState { state: proto::selftest::DONE, kind: sub_op, steps_passed: passed, steps_failed: failed };
        self.sv.raise(Raise::new(codes::POST_RESULT).a(passed as i32).b(failed as i32).inst(sub_op).during_post());
        // a proof that was not performed is UNKNOWN, never "passed": only a complete pass counts
        let all_passed = !steps.is_empty() && passed.count_ones() as usize == steps.len();
        let post = match (sub_op, failed != 0, all_passed) {
            (proto::selftest::SUBOP_POST_S, true, _) => 3,
            (proto::selftest::SUBOP_POST_A, true, _) => 4,
            (proto::selftest::SUBOP_POST_S, false, true) => 1,
            (proto::selftest::SUBOP_POST_A, false, true) => 2,
            _ => self.sv.diag().post_state(),
        };
        self.sv.diag_mut().set_post_state(post);
        self.selftest_note = Some(((passed as u32) << 16) | failed as u32);
        self.sv.resync_faults();
        self.sync_faults(faults_before);
        self.log_diag_history();
        Ok(())
    }

    /// Latched code that makes `Resume` / `Activate` refuse (`Latched`), if any.
    fn latched_root(&self) -> Option<u32> {
        let l = self.sv.diag().latched().first()?;
        let root = self.sv.diag().record(l.rec_id).map(|r| self.sv.diag().root_of(&r).code.0);
        Some(root.unwrap_or(l.code.0))
    }

    // ---- two-pod helpers ---------------------------------------------------------------
    pub(crate) fn hal_docked(&mut self) -> bool {
        self.hal.docked()
    }
    pub(crate) fn hal_charger(&mut self) -> bool {
        self.hal.charger_present()
    }

    /// Sample the DOCKED input into the supervisor. Called before every action that could move
    /// the motor.
    pub(crate) fn refresh_dock(&mut self) {
        let d = self.hal_docked();
        self.sv.set_docked(d);
        if d == self.pod.docked {
            return;
        }
        self.pod.docked = d;
        self.log_ev(if d { EventType::Docked } else { EventType::Undocked }, 0, 0);
        if !d && self.de.bolus_active() {
            // a bolus is never resumed or "caught up" after an undock
            let left = self.de.cancel_bolus();
            self.log_ev(EventType::BolusCancel, left.0 as i32, 0);
        }
    }

    fn act_delivered(&self) -> MilliUnits {
        self.pcal.pulses_to_mu(Pulses(self.de.delivered_steps().0.wrapping_sub(self.pod.act_base_steps.0)))
    }

    pub(crate) fn release_now(&mut self, reason: i32) {
        self.de.suspend(); // also cancels bolus and temp basal
        self.hal.motor_enable(false);
        self.pod.active = false;
        self.pod.pending_temp = None;
        self.sv.set_active(false);
        self.pod.last_release = self.act_delivered();
        let v = self.pod.last_release.0 as i32;
        self.log_ev(EventType::Release, v, reason);
    }

    fn wear_step(&mut self, dt: Millis) {
        if !self.pod.active {
            return;
        }
        self.pod.wear.0 += dt.0;
        let minutes = (self.pod.wear.0 / 60_000) as i32;
        if !self.pod.wear_warned && self.pod.wear >= WEAR_WARN {
            self.pod.wear_warned = true;
            self.log_ev(EventType::WearWarning, minutes, 0);
            self.sv.raise(Raise::new(codes::WEAR_WARNING).a(minutes));
            if self.sv.faults().is_empty() {
                self.hal.buzzer(Buzzer::Beep);
            }
        }
        let was = self.sv.wear_expired();
        self.sv.observe_wear(self.pod.wear);
        if self.sv.wear_expired() && !was {
            self.log_ev(EventType::WearExpired, minutes, 0);
        }
    }

    // ---- lifecycle ------------------------------------------------------------------------
    /// Call every ~1 s from the safety task. Also services the watchdog (last action).
    pub fn tick(&mut self) {
        let t = self.now();
        let mut dt = Millis(t.0.saturating_sub(self.last_tick.0));
        let wear_dt = dt; // a stalled loop still wears the pod: never clamped
        self.last_tick = t;
        if dt > TICK_MAX_DT {
            // stalled loop: never "catch up" with a burst
            dt = TICK_MAX_DT;
            self.tick_overruns += 1;
        }
        let before = self.sv.faults();
        if wear_dt.0 > TICK_OVERRUN_MS {
            // warning only: `7-7B-002` (F at 5 s) would add a fault bit the C reference does not have
            self.sv.raise(Raise::new(codes::TICK_OVERRUN).a(wear_dt.0 as i32).b(TICK_OVERRUN_MS as i32));
        } else {
            self.sv.diag_mut().clear(codes::TICK_OVERRUN);
        }

        self.refresh_dock();
        if self.pod.active && self.hal_charger() {
            self.release_now(REL_CHARGER); // on a charger: forced released
        }
        self.check_docked_pressure();
        self.wear_step(wear_dt);
        self.drain_hal_diag();

        let requested = self.de.tick(dt);
        let approved = self.approve_blind_safe(t, requested);
        let executed = if approved.0 > 0 { self.run_motor(approved) } else { Pulses(0) };
        self.de.commit(executed);
        if executed < approved {
            self.raise_steps_short(executed, approved);
        }
        self.draw_step();

        let ev = self.de.take_events();
        if ev.has(EngineEvents::BOLUS_DONE) {
            self.log_ev(EventType::BolusDone, 0, 0);
        }
        if ev.has(EngineEvents::TEMP_DONE) {
            self.log_ev(EventType::TempDone, 0, 0);
        }
        if ev.has(EngineEvents::TEMP_COMM_FALLBACK) {
            self.log_ev(EventType::TempCommFallback, 0, 0);
        }

        if self.res.is_low() && !self.low_res_reported {
            self.low_res_reported = true;
            let rem = self.res.remaining().0 as i32;
            self.log_ev(EventType::LowReservoir, rem, 0);
            self.sv.raise(Raise::new(codes::RESERVOIR_LOW).a(rem));
        } else if !self.res.is_low() {
            self.sv.diag_mut().clear(codes::RESERVOIR_LOW); // refilled
        }
        self.drain_hal_diag();
        self.observe();
        self.sync_faults(before);
        self.log_diag_history();
        self.hal.watchdog_kick();
    }

    /// H15: docked, the motor not driven since the last tick, and the leadscrew angle moved: the self-locking drive was
    /// back-driven from the reservoir side (possible manual injection into the cannula). Raises `5-54-001` (latched).
    /// The reference angle follows every driven tick, so commanded motion never trips it.
    fn check_docked_pressure(&mut self) {
        let angle = self.hal.angle_read().map(|a| a.0);
        if let (Some(a), Some(r)) = (angle, self.rest_angle) {
            if self.pod.docked && !self.moved && !self.draw_running() && (a - r).abs() > PRESSURE_ANOMALY_ANGLE_COUNTS {
                self.sv.raise(Raise::new(codes::PRESSURE_ANOMALY_WHILE_DOCKED).a((a - r) as i32));
            }
        }
        self.rest_angle = angle;
        self.moved = false;
    }

    // ---- commands ----------------------------------------------------------------------------
    fn require_active(&self) -> Result<(), Error> {
        if self.pod.active {
            Ok(())
        } else {
            Err(Error::Released)
        }
    }

    pub fn set_schedule(&mut self, s: &BasalSchedule) -> Result<(), Error> {
        self.sv.check_basal_schedule(s)?;
        self.require_active()?;
        self.de.set_schedule(s)?;
        self.log_ev(EventType::BasalSet, s.count() as i32, 0);
        Ok(())
    }

    pub fn set_temp_basal(&mut self, rate: MilliUnitsPerHour, duration: Minutes) -> Result<(), Error> {
        self.sv.check_temp_basal(rate, duration)?;
        self.require_active()?;
        self.de.start_temp_basal(rate, duration)?;
        self.log_ev(EventType::TempStart, rate.0 as i32, duration.0 as i32);
        Ok(())
    }

    pub fn cancel_temp_basal(&mut self) -> Result<(), Error> {
        if !self.de.cancel_temp_basal() {
            return Err(Error::NotFound);
        }
        self.log_ev(EventType::TempCancel, 0, 0);
        Ok(())
    }

    pub fn bolus(&mut self, amount: MilliUnits) -> Result<(), Error> {
        self.refresh_dock();
        let t = self.now();
        let rem = self.res.remaining();
        self.sv.check_bolus(t, amount, rem)?;
        self.de.start_bolus(amount)?;
        self.log_ev(EventType::BolusStart, amount.0 as i32, 0);
        Ok(())
    }

    pub fn cancel_bolus(&mut self) -> Result<(), Error> {
        if !self.de.bolus_active() {
            return Err(Error::NotFound);
        }
        let left = self.de.cancel_bolus();
        self.log_ev(EventType::BolusCancel, left.0 as i32, 0);
        Ok(())
    }

    pub fn suspend(&mut self) -> Result<(), Error> {
        if !self.de.is_suspended() {
            self.log_ev(EventType::Suspend, 0, 0);
        }
        self.de.suspend();
        Ok(())
    }

    /// Emergency stop (button hold >= 3 s): cancel bolus, suspend, stop the driver. Never fails.
    pub fn emergency_stop(&mut self) {
        if self.de.bolus_active() {
            let left = self.de.cancel_bolus();
            self.log_ev(EventType::BolusCancel, left.0 as i32, 0);
        }
        let _ = self.suspend();
        self.draw_abort();
        self.hal.motor_enable(false);
    }

    pub fn resume(&mut self) -> Result<(), Error> {
        self.refresh_dock();
        if !self.sv.motor_allowed() {
            return Err(Error::Fault);
        }
        if !self.pod.active {
            return Err(Error::Released);
        }
        if !self.pod.docked {
            return Err(Error::NotDocked);
        }
        if self.draw_running() {
            return Err(Error::Busy);
        }
        if self.cfg.require_schedule_on_resume && !self.de.has_schedule() {
            return Err(Error::NoSchedule); // e.g. after a reset whose schedule could not be restored: never 0 U/h silently
        }
        if self.prime_required {
            return Err(Error::PrimeRequired);
        }
        if self.de.is_suspended() {
            self.log_ev(EventType::Resume, 0, 0);
        }
        self.de.resume();
        if let Some((rate, min)) = self.pod.pending_temp.take() {
            // temp basal handed over by Activate
            self.de.start_temp_basal(rate, min)?;
            self.log_ev(EventType::TempStart, rate.0 as i32, min.0 as i32);
        }
        Ok(())
    }

    /// Set the reservoir level after a manual (syringe) fill. Suspended only. Mandatory priming
    /// follows when [`PumpConfig::require_prime_after_fill`].
    pub fn fill(&mut self, fill: MilliUnits) -> Result<(), Error> {
        if !self.de.is_suspended() {
            return Err(Error::NotSuspended);
        }
        if self.draw_running() {
            return Err(Error::Busy);
        }
        self.res.fill(fill)?;
        let ang = self.hal.angle_read().unwrap_or(AngleCounts(0));
        self.sv.rebaseline(ang); // the piston moved while filling
        self.low_res_reported = self.res.is_low();
        if self.cfg.require_prime_after_fill {
            self.prime_required = true;
        }
        self.log_ev(EventType::Fill, fill.0 as i32, 0);
        Ok(())
    }

    /// Prime the cannula connector: `steps` forward steps, delivered through the safety supervisor
    /// and verified by the angle sensor. Suspended + active + docked only. Clears `prime_required`.
    pub fn prime(&mut self, steps: Pulses) -> Result<(), Error> {
        if steps.0 == 0 {
            return Err(Error::BadArg);
        }
        if steps > self.sv.calibration().mu_to_pulses(MAX_PRIME) {
            return Err(Error::Limit);
        }
        if !self.de.is_suspended() {
            return Err(Error::NotSuspended);
        }
        if !self.res.is_filled() {
            return Err(Error::Reservoir);
        }
        self.refresh_dock();
        if !self.pod.active {
            return Err(Error::Released); // only the active pod primes, and only docked
        }
        if !self.pod.docked {
            return Err(Error::NotDocked);
        }
        if self.draw_running() {
            return Err(Error::Busy);
        }
        let before = self.sv.faults();
        // After a draw the first forward travel only takes up backlash and elasticity: run the take-up first. It goes
        // through the supervisor like every forward step but is NOT delivery (engine totals are untouched).
        let takeup = if self.cfg.takeup_mu > 0 { self.takeup_pending } else { 0 };
        // The lost motion of the mechanics is larger than one minute of the 1.7 U/min backstop allows together with a
        // prime (`limits::TAKEUP_MU_AFTER_DRAW`): it is recovered no faster than the caps allow, over several prime
        // commands. A command whose take-up + prime does not fit runs the part of the take-up that fits (through the
        // supervisor, never beyond the per-minute / hourly caps), does NOT prime and answers `Hourly`: the phone repeats
        // the prime after the cap has recovered. Never latches.
        let (mut takeup_now, mut prime_now, mut partial) = (takeup, steps.0, false);
        if takeup > 0 {
            let t = self.now();
            let rem = self.res.remaining();
            let room = self.sv.step_room(t, rem).0;
            if room < takeup + steps.0 {
                takeup_now = takeup.min(room);
                prime_now = 0;
                partial = true;
                if takeup_now == 0 {
                    return Err(Error::Hourly);
                }
            }
        }
        // RELAXED (C parity): one burst. Otherwise watchdog-safe chunks, verified and followed by a DONE pulse.
        let chunk = if self.cfg.takeup_mu > 0 { PRIME_CHUNK_STEPS } else { u32::MAX };
        let (mut left_takeup, mut left) = (takeup_now, prime_now);
        let mut ok = true;
        while left_takeup + left > 0 {
            let in_takeup = left_takeup > 0;
            let n = if in_takeup { left_takeup.min(chunk) } else { left.min(chunk) };
            let t = self.now();
            let approved = self.approve_blind_safe(t, Pulses(n));
            let executed = if approved.0 > 0 { self.run_motor(approved) } else { Pulses(0) };
            if executed < approved {
                self.raise_steps_short(executed, approved);
            }
            if executed.0 != n {
                ok = false;
                break;
            }
            if in_takeup {
                left_takeup -= n;
            } else {
                left -= n;
            }
            if left_takeup + left > 0 {
                self.observe();
                if self.sv.faults() != before {
                    ok = false;
                    break;
                }
                self.hal.watchdog_kick(); // between verified chunks, so a long prime never starves the TPL5010
            }
        }
        if ok {
            self.takeup_pending = takeup.saturating_sub(takeup_now);
            if !partial {
                self.log_ev(EventType::Prime, steps.0 as i32, 0);
            }
            self.observe(); // the angle sensor verifies the prime like any other delivery
        }
        self.sync_faults(before);
        if ok && partial && self.sv.faults() == before {
            return Err(Error::Hourly);
        }
        if ok && self.sv.faults() == before {
            self.prime_required = false;
            Ok(())
        } else {
            Err(Error::Fault)
        }
    }

    pub fn acknowledge(&mut self, mask: Faults) -> Result<(), Error> {
        let before = self.sv.faults();
        let e = self.sv.acknowledge(mask);
        let cleared = before & !self.sv.faults();
        if !cleared.is_empty() {
            self.log_ev(EventType::Ack, cleared.bits() as i32, 0);
        }
        if self.sv.faults().is_empty() {
            self.hal.buzzer(Buzzer::Off);
        }
        e
    }

    /// Silence an active alarm buzzer without clearing any fault (button short press).
    pub fn silence_alarm(&mut self) {
        self.hal.buzzer(Buzzer::Off);
    }

    pub fn get_status(&mut self) -> Status {
        let rep = self.de.report();
        let mut f: u16 = 0;
        if self.de.is_suspended() {
            f |= st::SUSPENDED;
        }
        if self.de.bolus_active() {
            f |= st::BOLUS_ACTIVE;
        }
        if self.de.temp_active() {
            f |= st::TEMP_ACTIVE;
        }
        if self.de.has_schedule() {
            f |= st::HAS_SCHEDULE;
        }
        if self.res.is_low() {
            f |= st::LOW_RESERVOIR;
        }
        if !self.sv.faults().is_empty() {
            f |= st::ALARM;
        }
        if self.res.is_filled() {
            f |= st::FILLED;
        }
        if self.sv.battery_low() {
            f |= st::LOW_BATTERY;
        }
        if self.pod.docked {
            f |= st::DOCKED;
        }
        if self.pod.active {
            f |= st::ACTIVE;
        }
        if self.pod.wear_warned && self.pod.active {
            f |= st::WEAR_WARNING;
        }
        if self.draw_running() {
            f |= st::DRAWING;
        }
        if self.prime_required {
            f |= st::PRIME_REQUIRED;
        }
        let delivery_state = if !self.pod.active {
            DeliveryState::Released
        } else if self.sv.wear_expired() {
            DeliveryState::StoppedWear
        } else if !self.pod.docked {
            DeliveryState::PausedUndocked
        } else {
            DeliveryState::Active
        };
        let mut s = Status {
            flags: f,
            faults: self.sv.faults().bits(),
            reservoir_mu: self.res.remaining().0,
            battery_mv: self.hal.battery_mv(),
            bolus_remaining_mu: self.de.bolus_remaining().0,
            temp_rate_mu_h: if self.de.temp_active() { self.de.temp_rate().0 as u16 } else { 0 },
            temp_remaining_min: self.de.temp_remaining().0 as u16,
            current_rate_mu_h: self.de.current_rate().0 as u16,
            delivered_mu: rep.delivered.0,
            scheduled_mu: rep.scheduled.0,
            next_event_id: self.log.next_id(),
            fw_version: FW_VERSION,
            pair_id: self.pod.pair_id,
            role: self.pod.role,
            wear_s: (self.pod.wear.0 / 1000) as u32,
            delivery_state: delivery_state as u8,
            ..Default::default()
        };
        if self.cal_valid {
            s.cal_drive_id = self.cal.drive_id;
            s.cal_uu_per_step = self.pcal.micro_u_floor();
            s.cal_steps_per_rev = self.cal.steps_per_rev;
            s.cal_gear_ratio_x100 = self.cal.gear_ratio_x100; // else all zero: the app must refuse
        }
        s.draw_state = self.draw.state;
        s.draw_requested_mu = self.draw.requested_mu;
        s.draw_done_mu = self.draw.drawn_mu;
        // diagnostics: the presence of DIAG_SUMMARY is the feature test for the app
        s.diag = Some(self.sv.diag().summary());
        s.fru_health = Some(self.sv.diag().fru_health());
        let uid = self.hal.pod_uid();
        s.pod_uid = (uid != 0).then_some(uid);
        if !self.sv.diag().active().is_empty() {
            s.flags |= st::DIAG_ACTIVE;
        }
        if !self.sv.diag().latched().is_empty() {
            s.flags |= st::LATCHED;
        }
        s
    }

    // ---- two-pod commands ---------------------------------------------------------------------
    /// Only a released pod accepts pairing; `pair_id` 0 and unknown roles are rejected.
    pub fn set_pairing(&mut self, pair_id: u32, role: u8) -> Result<(), Error> {
        if pair_id == 0 || (role != Role::A as u8 && role != Role::B as u8) {
            return Err(Error::BadArg);
        }
        if self.pod.active {
            return Err(Error::AlreadyActive); // never re-pair a delivering pod
        }
        self.pod.pair_id = pair_id;
        self.pod.role = role;
        self.log_ev(EventType::Paired, role as i32, pair_id as i32);
        Ok(())
    }

    /// Become the active pod. Refused unless paired (matching pair id), docked, filled, not on a
    /// charger, fault free (except an old wear fault) and not already active. The same activation
    /// id on an already active pod is an `Ok` no-op (lost response). Delivery stays SUSPENDED: the
    /// app primes the connector, then sends Resume (which also starts the temp basal).
    pub fn activate(&mut self, a: &ActivateArgs) -> Result<(), Error> {
        if self.pod.pair_id == 0 || a.pair_id != self.pod.pair_id {
            return Err(Error::Pair);
        }
        if self.pod.active {
            return if a.activation_id == self.pod.activation_id { Ok(()) } else { Err(Error::AlreadyActive) };
        }
        if a.activation_id == 0 {
            return Err(Error::BadArg);
        }
        self.refresh_dock();
        if self.hal_charger() {
            return Err(Error::Charging);
        }
        if !self.pod.docked {
            return Err(Error::NotDocked);
        }
        if self.sv.faults() & !Faults::WEAR_EXPIRED != Faults::NONE {
            return Err(Error::Fault);
        }
        if !self.res.is_filled() {
            return Err(Error::Reservoir);
        }
        // validate everything before touching anything: Activate is all or nothing; an old wear
        // fault must not hide schedule errors, so check against a fault-free copy
        self.sv.fault_free_probe().check_basal_schedule(&a.schedule)?;
        if let Some((rate, min)) = a.temp {
            if min.0 == 0
                || min.0 > TEMP_MAX_MIN
                || min.0 % TEMP_GRANULARITY_MIN != 0
                || rate.0 % RATE_GRANULARITY.0 != 0
                || rate > self.sv.max_basal()
            {
                return Err(if rate > self.sv.max_basal() { Error::Limit } else { Error::BadArg });
            }
        }
        self.de.set_schedule(&a.schedule)?;
        self.de.suspend(); // stays suspended until Resume, so the connector can be primed first
        self.pod.pending_temp = a.temp;
        self.sv.reset_wear();
        self.sv.diag_mut().clear(codes::WEAR_WARNING);
        self.pod.wear = Millis(0);
        self.pod.wear_warned = false;
        self.pod.activation_id = a.activation_id;
        self.pod.act_base_steps = self.de.delivered_steps();
        self.pod.last_release = MilliUnits(0);
        self.pod.active = true;
        self.sv.set_active(true);
        self.hal.buzzer(Buzzer::Off);
        self.log_ev(EventType::BasalSet, a.schedule.count() as i32, 0);
        let role = self.pod.role as i32;
        self.log_ev(EventType::Activate, role, a.activation_id as i32);
        Ok(())
    }

    /// Stop delivering and become released. Idempotent. Returns the insulin delivered since the
    /// activation.
    pub fn release(&mut self, pair_id: u32) -> Result<MilliUnits, Error> {
        if self.pod.pair_id == 0 || pair_id != self.pod.pair_id {
            return Err(Error::Pair);
        }
        if self.pod.active {
            self.release_now(REL_COMMAND);
        }
        Ok(self.pod.last_release)
    }

    /// Boot: restore what the platform persisted. The pod comes up suspended even if it was active.
    pub fn restore_pod(&mut self, pair_id: u32, role: u8, active: bool, activation_id: u32, wear: Millis) {
        self.pod.pair_id = pair_id;
        self.pod.role = role;
        self.pod.active = active;
        self.pod.activation_id = activation_id;
        self.pod.wear = if active { wear } else { Millis(0) };
        self.pod.wear_warned = active && wear >= WEAR_WARN;
        self.sv.set_active(active);
        if active {
            self.sv.observe_wear(self.pod.wear);
            if !self.sv.faults().is_empty() {
                self.sync_faults(Faults::NONE);
            }
            self.alarm_unplanned_reset();
        }
    }

    /// H3 (docs/02-safety.md): an ACTIVE pod that restarts for any reason other than a commanded reset announces itself.
    /// The pod comes up SUSPENDED anyway; without this it looked like a normal suspended pod until the app asked (F1).
    /// A `7-74-002 UNEXPECTED_RESET` record of FAULT severity (the catalogue severity of a released pod is W) sets the
    /// ALARM flag and the buzzer, notifies the phone and refuses `Resume` until acknowledged. `ctx_a` = reset cause
    /// (0 power-on, 1 watchdog, 2 brown-out, 3 lockup, 4 other).
    fn alarm_unplanned_reset(&mut self) {
        use crate::hal::ResetCause;
        use openpatch_diag::Severity;
        if !self.cfg.alarm_on_unplanned_reset || self.boot_cause == ResetCause::Commanded {
            return;
        }
        let code = match self.boot_cause {
            ResetCause::PowerOn | ResetCause::Commanded => 0,
            ResetCause::Watchdog => 1,
            ResetCause::Brownout => 2,
            ResetCause::Lockup => 3,
            ResetCause::Other => 4,
        };
        let crumb = self.hal.breadcrumb();
        let before = self.sv.faults();
        self.sv.raise(Raise::new(codes::UNEXPECTED_RESET).a(code).c(crumb).severity(Severity::Fault));
        self.sync_faults(before);
    }

    // ---- persistence records (platform stores / loads the bytes, `persist.rs`) ----------------------
    /// The held basal schedule as a flash record (`SchedRec::NONE` when there is none).
    pub fn schedule_record(&self) -> crate::persist::SchedRec {
        if self.de.has_schedule() {
            crate::persist::SchedRec::encode(self.de.schedule())
        } else {
            crate::persist::SchedRec::NONE
        }
    }

    /// The active temp basal as a flash record: remaining minutes rounded DOWN to 30 (a restored temp can only be shorter).
    pub fn temp_record(&self) -> crate::persist::TempRec {
        crate::persist::TempRec::from_engine(self.de.temp_active(), self.de.temp_rate(), self.de.temp_remaining().0)
    }

    /// Boot: restore the basal schedule. Checked against the pure limits like a command; `Err` = not restorable (the
    /// pod then refuses `Resume` with `NoSchedule` under the STRICT config).
    pub fn restore_schedule(&mut self, s: &BasalSchedule) -> Result<(), Error> {
        self.sv.fault_free_probe().check_basal_schedule(s)?;
        self.de.set_schedule(s)
    }

    /// Boot: a temp basal that was running is handed to the next `Resume` like the temp basal of an `Activate`.
    pub fn restore_temp(&mut self, t: crate::persist::TempRec) {
        if t.is_none() || !self.pod.active {
            return;
        }
        let rate = MilliUnitsPerHour(t.rate_mu_h as u32);
        let min = Minutes(t.remaining_min as u32);
        if self.sv.check_temp_basal(rate, min).is_ok() {
            self.pod.pending_temp = Some((rate, min));
        }
    }

    // ---- protocol -----------------------------------------------------------------------------
    fn schedule_from_wire(segs: &proto::BasalSegs) -> Result<BasalSchedule, Error> {
        let mut s = BasalSchedule::new();
        for g in segs.iter() {
            s.segs
                .push(BasalSeg { start_slot: g.start_slot, rate: MilliUnitsPerHour(g.rate_mu_h as u32) })
                .map_err(|_| Error::BadArg)?;
        }
        Ok(s)
    }

    /// Execute an already-decoded command.
    pub fn execute(&mut self, c: &Command) -> Response {
        let mut rsp = Response { type_: c.body.type_id(), seq: c.seq, ..Default::default() };
        if let Some(t) = c.time_of_day_ms {
            self.de.set_time_of_day(Millis(t as u64));
        }
        let r: Result<(), Error> = match &c.body {
            CommandBody::GetStatus => {
                rsp.status = Some(self.get_status());
                Ok(())
            }
            CommandBody::SetBasalSchedule(segs) => match Self::schedule_from_wire(segs) {
                Ok(s) => self.set_schedule(&s),
                Err(e) => Err(e),
            },
            CommandBody::SetTempBasal { rate_mu_h, duration_min } => {
                self.set_temp_basal(MilliUnitsPerHour(*rate_mu_h as u32), Minutes(*duration_min as u32))
            }
            CommandBody::CancelTempBasal => self.cancel_temp_basal(),
            CommandBody::Bolus { amount_mu } => self.bolus(MilliUnits(*amount_mu)),
            CommandBody::CancelBolus => self.cancel_bolus(),
            CommandBody::Suspend => self.suspend(),
            CommandBody::Resume => match self.latched_root() {
                Some(root) => {
                    rsp.diag_code = Some(root);
                    Err(Error::Latched)
                }
                None => self.resume(),
            },
            CommandBody::FillPrime { sub_op, fill_mu, prime_steps } => match *sub_op {
                SUBOP_FILL => self.fill(MilliUnits(*fill_mu)),
                SUBOP_PRIME => self.prime(Pulses(*prime_steps as u32)),
                _ => Err(Error::BadArg),
            },
            CommandBody::Acknowledge { fault_mask } => self.acknowledge(Faults(*fault_mask)),
            CommandBody::SetPairing { pair_id, role } => self.set_pairing(*pair_id, *role),
            CommandBody::Activate { pair_id, activation_id, schedule, temp } => {
                let latched = self.latched_root();
                let r = match Self::schedule_from_wire(schedule) {
                    Ok(_) if latched.is_some() => {
                        rsp.diag_code = latched;
                        Err(Error::Latched)
                    }
                    Ok(s) => {
                        let a = ActivateArgs {
                            pair_id: *pair_id,
                            activation_id: *activation_id,
                            schedule: s,
                            temp: temp.map(|(r, m)| (MilliUnitsPerHour(r as u32), Minutes(m as u32))),
                        };
                        self.activate(&a)
                    }
                    Err(e) => Err(e),
                };
                rsp.status = Some(self.get_status());
                r
            }
            CommandBody::AssistedFill { amount_mu } => self.assisted_fill(MilliUnits(*amount_mu)),
            CommandBody::Release { pair_id } => {
                let r = self.release(*pair_id);
                if let Ok(mu) = r {
                    rsp.act_delivered_mu = Some(mu.0);
                }
                rsp.status = Some(self.get_status()); // final totals + reservoir
                r.map(|_| ())
            }
            CommandBody::GetHistory { from_id, max_events } => {
                let mut max = *max_events as usize;
                if max == 0 || max > HIST_MAX_PER_RESPONSE {
                    max = HIST_MAX_PER_RESPONSE;
                }
                let mut buf = [crate::log::Event::default(); HIST_MAX_PER_RESPONSE];
                let n = self.log.read(*from_id, &mut buf[..max]);
                let mut h = History {
                    next_event_id: self.log.next_id(),
                    oldest_event_id: self.log.oldest_id(),
                    ..Default::default()
                };
                for e in &buf[..n] {
                    let _ = h.events.push((*e).into());
                }
                rsp.history = Some(h);
                Ok(())
            }
            CommandBody::GetFaultLog { from_id, max_events } => {
                let mut max = *max_events as usize;
                if max == 0 || max > proto::DIAG_RECORDS_PER_RESPONSE {
                    max = proto::DIAG_RECORDS_PER_RESPONSE;
                }
                let mut buf = [proto::DiagRecord::default(); proto::DIAG_RECORDS_PER_RESPONSE];
                let n = self.sv.diag().records_from(*from_id, &mut buf[..max]);
                let mut f = proto::FaultLog {
                    next_id: self.sv.diag().next_id(),
                    oldest_id: self.sv.diag().oldest_id(),
                    ..Default::default()
                };
                for l in self.sv.diag().latched().iter().take(proto::DIAG_LATCHED_MAX) {
                    let _ = f.latched.push(l.code.0);
                }
                for r in &buf[..n] {
                    let _ = f.records.push(*r);
                }
                rsp.fault_log = Some(f);
                Ok(())
            }
            CommandBody::RunSelfTest { sub_op } => {
                let r = self.run_self_test(*sub_op);
                rsp.selftest = Some(self.selftest);
                r
            }
            CommandBody::ClearDiag { code } => {
                let r = self.clear_diag(DiagCode(*code));
                if r.is_err() {
                    rsp.diag_code = Some(*code);
                }
                rsp.diag = Some(self.sv.diag().summary());
                r.map(|_| ())
            }
        };
        self.log_diag_history();
        rsp.result = Error::result_code(&r);
        rsp
    }

    /// Full protocol path: decode/authenticate -> execute -> response frame. Returns the response
    /// length, or the error when no response can be produced (undecodable / unauthenticated /
    /// replayed frames are dropped silently, without side effects).
    pub fn handle_frame<C: Ccm>(&mut self, session: &mut Session<C>, input: &[u8], out: &mut [u8]) -> Result<usize, Error> {
        let mut plain = [0u8; FRAME_MAX];
        let (ftype, fseq, fflags, mut rsp) = {
            let f = session.open(input, &mut plain)?;
            self.de.comm_heartbeat(); // authenticated + fresh = the phone is alive
            let rsp = match proto::decode_command(f.type_, f.seq, f.payload) {
                Err(e) => Response { type_: f.type_, seq: f.seq, result: e.code(), ..Default::default() },
                Ok(c) => self.execute(&c),
            };
            (f.type_, f.seq, f.flags, rsp)
        };
        if let Some(s) = rsp.status.as_mut() {
            s.last_seq = session.last_rx_seq(); // lets the phone resync after a pod reboot
        }
        let mut body = [0u8; FRAME_MAX];
        let n = proto::encode_response_payload(&rsp, &mut body)?;
        session.seal(true, ftype | RSP_BIT, fseq, fflags & proto::FLAG_ENCRYPTED != 0, &body[..n], out)
    }
}

impl<H: Hal> Pump<H> {
    /// Cause reported by the HAL for the most recent failed burst / refused power-up, if any.
    pub fn last_motor_fault(&self) -> Option<crate::hal::MotorFault> {
        self.last_motor_fault
    }

    /// Largest motor-current peak (mA) of the forward bursts since the last call (take-and-clear);
    /// `None` if the board has no current sensor or nothing ran. Used for the bench CSV.
    pub fn take_peak_ma(&mut self) -> Option<u16> {
        self.peak_ma.take()
    }

    /// Lower the occlusion motor-current threshold (mA) at runtime for bench tuning. Never above
    /// the hard limit `limits::OCCLUSION_CURRENT_MA`, never 0 (`Err(Limit)`).
    pub fn set_occlusion_current_ma(&mut self, ma: u16) -> Result<(), Error> {
        self.sv.set_occlusion_current_ma(ma)
    }

    /// `true` while no fault is latched.
    pub fn sv_ok(&self) -> bool {
        self.sv.motor_allowed()
    }

    /// Direct log access for tests (inject events).
    #[doc(hidden)]
    pub fn log_mut(&mut self) -> &mut EventLog {
        &mut self.log
    }
}
