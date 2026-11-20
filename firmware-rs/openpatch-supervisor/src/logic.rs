//! The supervisor state machine (`INTERLOCK.md` H and I.6): arm window, step budget, permit drop and latch.
//!
//! Event driven and free of time sources: every call carries `now_ms` (monotonic, the 1 kHz tick of the platform shell) and returns
//! the new [`Outputs`] immediately, so a permission drop caused by an input edge happens inside the interrupt handler that reported it
//! (the "within 1 ms" requirement is a property of the handler, not of a polling loop).
//!
//! ```text
//!            arm edge, all inputs ok            window over / budget used / MCU_EN low
//!   IDLE ───────────────────────────► ARMED ───────────────────────────────────────────► DEAD ──(dead time)──► IDLE
//!     ▲                                  │ any violation                                   │ any step edge
//!     │                                  ▼                                                 ▼
//!     └────(2 s quiet, inputs ok)─────  FAULT  ◄──────────────────────────────────────────┘
//!                                          │ 3rd fault within 10 min / bucket overflow
//!                                          ▼
//!                                        LOCKED   (until power cycle)
//! ```
//!
//! `SUP_PERMIT` is high only in `ARMED`. `SUP_OK` is high in `IDLE`, `ARMED` and `DEAD`.
//!
//! Inputs (decoded by the platform shell): `mcu_en` (`MCU_EN` high), `oc_ok` (`OC_OK` high = no over-current), `docked` (`DOCK_N`
//! low), `fwd_intent` (`MOT_FWD` high = forward intent; the reset default is forward), `link_ok` (challenge/response with the main MCU
//! healthy, always true on boards without the link). Events: ARM edge, PHASE samples, main MCU reset, the tick.
//!
//! Limits are `const` data in [`Config`]; there is no way to change them at run time and no command that does ("not changeable over
//! any link").

use crate::phase::{Decoded, Dir, PhaseDecoder};

/// Limits of the supervisor. One value set per drive, chosen at build time.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct Config {
    /// Boot self-check, ms.
    pub boot_check_ms: u32,
    /// Length of an armed window for FORWARD motion, ms (about 0.6 s).
    pub window_ms: u32,
    /// Length of an armed window for REVERSE motion (draw / assisted fill chunks of up to 0.8 s), ms.
    pub rev_window_ms: u32,
    /// Forward steps per armed window (the budget: 32 steps).
    pub fwd_budget: u32,
    /// Reverse steps per armed window (draw chunk: 500 steps at most).
    pub rev_budget: u32,
    /// Dead time after a window, ms: arm edges are ignored.
    pub dead_ms: u32,
    /// Minimum distance between two accepted arm edges, ms (arm at most once per 1 s tick).
    pub min_arm_interval_ms: u32,
    /// A FAULT is left only after this long without activity, ms.
    pub fault_hold_ms: u32,
    /// This many faults within [`Config::lock_window_ms`] lock the supervisor until a power cycle.
    pub lock_faults: u8,
    pub lock_window_ms: u32,
    /// Leaky bucket on the counted forward steps over 60 minutes (steps of capacity; the physical 15 U/h cap with its calibration
    /// margin) and over one minute (1.7 U/min).
    pub hour_cap_steps: u32,
    pub minute_cap_steps: u32,
    /// F7 (SPICE report): after ANY reset or brown-out (the supervisor's own power-up, a reset of the main MCU, a brown-out event)
    /// `SUP_PERMIT` stays low for at least this long before the first permit can be granted, ms. Values below
    /// [`MIN_RESET_HOLDOFF_MS`] are raised to it: the hold-off cannot be configured away.
    pub reset_holdoff_ms: u32,
}

/// Shortest permit hold-off after a reset or brown-out (F7): a 5 ms 3V3 dip that does not reset the latch must not be followed by an
/// immediate permit. Spec section 7, tightening item.
pub const MIN_RESET_HOLDOFF_MS: u32 = 10;

impl Config {
    /// The hold-off in force: never below [`MIN_RESET_HOLDOFF_MS`].
    pub const fn effective_reset_holdoff_ms(&self) -> u32 {
        if self.reset_holdoff_ms < MIN_RESET_HOLDOFF_MS {
            MIN_RESET_HOLDOFF_MS
        } else {
            self.reset_holdoff_ms
        }
    }

    /// Cup drive `nfp-608-26-45-cup-miter-1-1` (id 0x26, 7.0303 mU per step): 15 U/h reduced by the 4 % calibration margin
    /// (`limits::HOURLY_CAL_MARGIN_PCT`) = 14 423 mU = 2051 steps; 1.7 U/min = 241 steps. The integration test recomputes both from
    /// the core's limits and calibration, so a change of the drive or of the limits breaks it.
    pub const CUP_MITER_1_1: Config = Config {
        boot_check_ms: 200,
        window_ms: 600,
        rev_window_ms: 1_000,
        fwd_budget: 32,
        rev_budget: 512,
        dead_ms: 400,
        min_arm_interval_ms: 1_000,
        fault_hold_ms: 2_000,
        lock_faults: 3,
        lock_window_ms: 600_000,
        hour_cap_steps: 2_051,
        minute_cap_steps: 241,
        reset_holdoff_ms: MIN_RESET_HOLDOFF_MS,
    };
}

/// Why the supervisor is (or went) into `FAULT` / `LOCKED`, also the "last fault reason" of the status frame.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
#[repr(u8)]
pub enum FaultReason {
    None = 0,
    /// `OC_OK` fell (the TPS2553 current limit tripped): re-arming is locked out for the hold time.
    OverCurrent = 1,
    /// H15: docked and reverse intent (aspiration through the cannula), at arm time or while armed.
    DockedReverse = 2,
    /// Dock lost while armed with forward intent (the hardware gate opens as well).
    UndockedForward = 3,
    /// The decoded step direction disagrees with `MOT_FWD`.
    DirectionMismatch = 4,
    /// Both PHASE lines changed at once.
    PhaseSequence = 5,
    /// A step edge while no window was open (also after the budget was used up): the main MCU stepped without permission.
    StepOutsideWindow = 6,
    /// A step after the budget of the window was used up (the permit had already dropped with the last budgeted step).
    BudgetExceeded = 7,
    // 8: reserved (an intent change while armed is always a DockedReverse or UndockedForward violation, see `on_inputs`)
    /// The challenge/response link failed while armed.
    LinkLost = 9,
    /// Boot self-check: `OC_OK` low or PHASE activity during the first 200 ms.
    BootCheck = 10,
    /// A leaky bucket overflowed (hourly or per-minute cap): LOCKED.
    BucketOverflow = 11,
    /// The fault limit was reached (3 in 10 minutes): LOCKED.
    TooManyFaults = 12,
}

/// State of the machine.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
#[repr(u8)]
pub enum State {
    Boot = 0,
    Idle = 1,
    Armed = 2,
    Dead = 3,
    Fault = 4,
    Locked = 5,
}

/// The two output lines.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct Outputs {
    /// `SUP_PERMIT`: high only while ARMED.
    pub permit: bool,
    /// `SUP_OK`: healthy (IDLE, ARMED, DEAD).
    pub ok: bool,
    pub state: State,
}

/// Input levels, decoded by the platform shell.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct Inputs {
    pub mcu_en: bool,
    pub oc_ok: bool,
    pub docked: bool,
    pub fwd_intent: bool,
    pub link_ok: bool,
}

impl Inputs {
    /// Everything quiet and healthy, docked, forward: the usual delivery condition.
    pub const DELIVERING: Inputs = Inputs { mcu_en: true, oc_ok: true, docked: true, fwd_intent: true, link_ok: true };
}

/// An arm edge that did not open a window.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum ArmReject {
    /// Not IDLE (BOOT, ARMED, DEAD, FAULT, LOCKED).
    State(State),
    /// Less than `min_arm_interval_ms` since the last accepted arm.
    TooSoon,
    McuEnLow,
    OverCurrent,
    LinkDown,
    /// Undocked and forward: the hardware gate is closed, there is nothing to permit.
    UndockedForward,
    /// A bucket has less room than one full forward budget.
    BucketFull,
    /// F7: less than the reset hold-off ([`MIN_RESET_HOLDOFF_MS`] at least) since the last reset or brown-out.
    ResetHoldoff,
}

/// Leaky bucket in micro-steps.
#[derive(Clone, Copy, Debug)]
struct Bucket {
    cap_micro: u64,
    level_micro: u64,
    leak_micro_per_ms: u64,
}

const MICRO: u64 = 1_000_000;

impl Bucket {
    /// `cap` steps leaking out over `period_ms` (rounded DOWN: it never leaks faster than the limit allows).
    fn new(cap_steps: u32, period_ms: u64) -> Self {
        let cap_micro = cap_steps as u64 * MICRO;
        Self { cap_micro, level_micro: 0, leak_micro_per_ms: cap_micro / period_ms }
    }
    fn leak(&mut self, dt_ms: u64) {
        self.level_micro = self.level_micro.saturating_sub(self.leak_micro_per_ms.saturating_mul(dt_ms));
    }
    /// Adds one step; false = overflow.
    fn add_step(&mut self) -> bool {
        self.level_micro = self.level_micro.saturating_add(MICRO);
        self.level_micro <= self.cap_micro
    }
    fn room_steps(&self) -> u32 {
        (self.cap_micro.saturating_sub(self.level_micro) / MICRO) as u32
    }
    fn level_steps(&self) -> u32 {
        (self.level_micro / MICRO) as u32
    }
}

/// The supervisor.
#[derive(Clone, Copy, Debug)]
pub struct Supervisor {
    cfg: Config,
    state: State,
    reason: FaultReason,
    inputs: Inputs,
    dec: PhaseDecoder,
    now: u64,
    boot_at: u64,
    /// Start of the current / last accepted arm (for the minimum interval) and the window end.
    last_arm_at: Option<u64>,
    window_end: u64,
    /// The direction intent latched at arm time.
    armed_fwd: bool,
    fwd_in_window: u32,
    rev_in_window: u32,
    /// The last window ended because its step budget was used up (a further step is then a budget violation, not a stray step).
    budget_used: bool,
    /// F7: no permit before this time (power-up, main MCU reset, brown-out + the hold-off).
    holdoff_until: u64,
    /// When DEAD began.
    dead_since: u64,
    /// Last activity (input change, step edge) for the FAULT hold.
    quiet_since: u64,
    /// Times of the last faults (for the lock-up), oldest first; `lock_faults` entries at most 8.
    fault_times: [u64; 8],
    fault_n: usize,
    hour: Bucket,
    minute: Bucket,
    last_leak: u64,
    // statistics for the status frame
    arm_edges: u16,
    arms_rejected: u16,
    steps_total: u32,
}

impl Supervisor {
    /// Power-up / reset. `a`, `b` are the PHASE levels at that moment.
    pub fn new(cfg: Config, now_ms: u64, inputs: Inputs, a: bool, b: bool) -> Self {
        Self {
            cfg,
            state: State::Boot,
            reason: FaultReason::None,
            inputs,
            dec: PhaseDecoder::new(a, b),
            now: now_ms,
            boot_at: now_ms,
            last_arm_at: None,
            window_end: 0,
            armed_fwd: true,
            fwd_in_window: 0,
            rev_in_window: 0,
            budget_used: false,
            holdoff_until: now_ms + cfg.effective_reset_holdoff_ms() as u64,
            dead_since: 0,
            quiet_since: now_ms,
            fault_times: [0; 8],
            fault_n: 0,
            hour: Bucket::new(cfg.hour_cap_steps, 3_600_000),
            minute: Bucket::new(cfg.minute_cap_steps, 60_000),
            last_leak: now_ms,
            arm_edges: 0,
            arms_rejected: 0,
            steps_total: 0,
        }
    }

    // ---- observation -----------------------------------------------------------------------------------------------------------
    pub fn state(&self) -> State {
        self.state
    }
    pub fn reason(&self) -> FaultReason {
        self.reason
    }
    pub fn inputs(&self) -> Inputs {
        self.inputs
    }
    pub fn config(&self) -> &Config {
        &self.cfg
    }
    pub fn outputs(&self) -> Outputs {
        Outputs {
            permit: self.state == State::Armed,
            ok: matches!(self.state, State::Idle | State::Armed | State::Dead),
            state: self.state,
        }
    }
    pub fn fwd_in_window(&self) -> u32 {
        self.fwd_in_window
    }
    pub fn rev_in_window(&self) -> u32 {
        self.rev_in_window
    }
    pub fn hour_level_steps(&self) -> u32 {
        self.hour.level_steps()
    }
    pub fn minute_level_steps(&self) -> u32 {
        self.minute.level_steps()
    }
    pub fn arm_edges(&self) -> u16 {
        self.arm_edges
    }
    pub fn arms_rejected(&self) -> u16 {
        self.arms_rejected
    }
    pub fn steps_total(&self) -> u32 {
        self.steps_total
    }
    /// Faults currently counted towards the lock-up.
    pub fn recent_faults(&self) -> usize {
        self.fault_n
    }

    // ---- time ------------------------------------------------------------------------------------------------------------------
    fn advance(&mut self, now: u64) {
        let now = now.max(self.now); // time never goes backwards
        let dt = now - self.last_leak;
        if dt > 0 {
            self.hour.leak(dt);
            self.minute.leak(dt);
            self.last_leak = now;
        }
        self.now = now;
        match self.state {
            State::Boot => {
                if now - self.boot_at >= self.cfg.boot_check_ms as u64 {
                    if self.inputs.oc_ok {
                        self.state = State::Idle;
                    } else {
                        self.fault(FaultReason::BootCheck);
                    }
                }
            }
            State::Armed => {
                if now >= self.window_end {
                    self.close_window(); // the window ran out
                }
            }
            State::Dead => {
                if now - self.dead_since >= self.cfg.dead_ms as u64 {
                    self.state = State::Idle;
                }
            }
            State::Fault => {
                if now - self.quiet_since >= self.cfg.fault_hold_ms as u64 && self.can_leave_fault() {
                    self.state = State::Idle;
                    self.reason = FaultReason::None;
                }
            }
            State::Idle | State::Locked => {}
        }
    }

    fn can_leave_fault(&self) -> bool {
        let i = &self.inputs;
        // an over-current that is still present, a dead link and the H15 condition keep the fault
        i.oc_ok && i.link_ok && !(i.docked && !i.fwd_intent)
    }

    /// Window over (time, budget, `MCU_EN` low): permit drops, dead time starts. Not a fault.
    fn close_window(&mut self) {
        self.state = State::Dead;
        self.dead_since = self.now;
    }

    fn fault(&mut self, why: FaultReason) {
        match self.state {
            State::Locked => return,
            State::Fault => {
                // activity during a fault restarts the hold; the first reason stays as the root cause
                self.quiet_since = self.now;
                return;
            }
            _ => {}
        }
        self.reason = why;
        self.quiet_since = self.now;
        self.state = State::Fault;
        // lock-up: the last `lock_faults` faults inside the window
        let n = (self.cfg.lock_faults as usize).clamp(1, self.fault_times.len());
        if self.fault_n == self.fault_times.len() {
            self.fault_times.copy_within(1.., 0);
            self.fault_n -= 1;
        }
        self.fault_times[self.fault_n] = self.now;
        self.fault_n += 1;
        if self.fault_n >= n {
            let first = self.fault_times[self.fault_n - n];
            if self.now - first <= self.cfg.lock_window_ms as u64 {
                self.lock(FaultReason::TooManyFaults);
            }
        }
    }

    fn lock(&mut self, why: FaultReason) {
        self.state = State::Locked;
        self.reason = why;
    }

    // ---- events ----------------------------------------------------------------------------------------------------------------
    /// The tick (1 kHz): time based transitions only.
    pub fn tick(&mut self, now_ms: u64) -> Outputs {
        self.advance(now_ms);
        self.outputs()
    }

    /// An input line changed (EXTI on `MCU_EN`, `OC_OK`, `DOCK_N`, `MOT_FWD`) or the link status changed. `i` holds ALL current levels.
    /// Call it for every edge, also for glitches: a glitch pair is two calls and the first one already faults.
    pub fn on_inputs(&mut self, now_ms: u64, i: Inputs) -> Outputs {
        self.advance(now_ms);
        let old = self.inputs;
        self.inputs = i;
        if old != i {
            self.quiet_since = self.now;
        }
        // over-current: ANY falling edge is a trip, in every state but LOCKED (which is final)
        if old.oc_ok && !i.oc_ok {
            match self.state {
                State::Boot | State::Idle | State::Armed | State::Dead => self.fault(FaultReason::OverCurrent),
                _ => {}
            }
        }
        if self.state == State::Armed {
            if i.docked && !i.fwd_intent {
                self.fault(FaultReason::DockedReverse); // H15
            } else if !i.docked && i.fwd_intent {
                self.fault(FaultReason::UndockedForward);
            } else if !i.link_ok {
                self.fault(FaultReason::LinkLost);
            } else if !i.mcu_en {
                // the normal end of a burst: the main MCU takes its enable away, the permit goes with it
                self.close_window();
            }
        }
        self.outputs()
    }

    /// The arm edge (`ARM_CLK` rising). Returns the outputs and, when no window opened, why.
    pub fn on_arm_edge(&mut self, now_ms: u64) -> (Outputs, Result<(), ArmReject>) {
        self.advance(now_ms);
        self.arm_edges = self.arm_edges.wrapping_add(1);
        let r = self.try_arm();
        if r.is_err() {
            self.arms_rejected = self.arms_rejected.wrapping_add(1);
        }
        (self.outputs(), r)
    }

    fn try_arm(&mut self) -> Result<(), ArmReject> {
        if self.state != State::Idle {
            return Err(ArmReject::State(self.state));
        }
        if self.now < self.holdoff_until {
            return Err(ArmReject::ResetHoldoff);
        }
        if let Some(t) = self.last_arm_at {
            if self.now - t < self.cfg.min_arm_interval_ms as u64 {
                return Err(ArmReject::TooSoon);
            }
        }
        let i = self.inputs;
        if !i.oc_ok {
            return Err(ArmReject::OverCurrent);
        }
        if i.docked && !i.fwd_intent {
            // H15: the main MCU asks for reverse while docked: a firmware bug, latch it
            self.fault(FaultReason::DockedReverse);
            return Err(ArmReject::State(State::Fault));
        }
        if !i.mcu_en {
            return Err(ArmReject::McuEnLow);
        }
        if !i.link_ok {
            return Err(ArmReject::LinkDown);
        }
        if !i.docked && i.fwd_intent {
            return Err(ArmReject::UndockedForward);
        }
        if i.fwd_intent && (self.hour.room_steps() < self.cfg.fwd_budget || self.minute.room_steps() < self.cfg.fwd_budget) {
            return Err(ArmReject::BucketFull);
        }
        self.state = State::Armed;
        self.last_arm_at = Some(self.now);
        self.armed_fwd = i.fwd_intent;
        self.fwd_in_window = 0;
        self.rev_in_window = 0;
        self.budget_used = false;
        let w = if i.fwd_intent { self.cfg.window_ms } else { self.cfg.rev_window_ms };
        self.window_end = self.now + w as u64;
        Ok(())
    }

    /// A PHASE edge: the shell reads both levels and calls this.
    pub fn on_phase(&mut self, now_ms: u64, a: bool, b: bool) -> Outputs {
        self.advance(now_ms);
        match self.dec.sample(a, b) {
            Decoded::NoChange => {}
            Decoded::Invalid => {
                self.quiet_since = self.now;
                if matches!(self.state, State::Idle | State::Armed | State::Dead | State::Boot) {
                    self.fault(FaultReason::PhaseSequence);
                }
            }
            Decoded::Step(dir) => self.on_step(dir),
        }
        self.outputs()
    }

    fn on_step(&mut self, dir: Dir) {
        self.quiet_since = self.now;
        self.steps_total = self.steps_total.wrapping_add(1);
        match self.state {
            State::Armed => {}
            State::Boot => return self.fault(FaultReason::BootCheck),
            State::Fault | State::Locked => return, // already stopped; the activity only restarts the hold
            State::Dead if self.budget_used => return self.fault(FaultReason::BudgetExceeded),
            State::Idle | State::Dead => return self.fault(FaultReason::StepOutsideWindow),
        }
        // direction must agree with the intent line (latched at arm; a change of the line is a separate fault)
        let fwd = dir == Dir::Forward;
        if fwd != self.inputs.fwd_intent {
            return self.fault(FaultReason::DirectionMismatch);
        }
        if fwd {
            self.fwd_in_window += 1;
            let ok_h = self.hour.add_step();
            let ok_m = self.minute.add_step();
            if !ok_h || !ok_m {
                // the caps are the physical limits: overflowing one is final
                return self.lock(FaultReason::BucketOverflow);
            }
            if self.fwd_in_window >= self.cfg.fwd_budget {
                self.budget_used = true;
                self.close_window(); // the permit drops with the last budgeted step; the next step edge is a violation
            }
        } else {
            self.rev_in_window += 1;
            if self.rev_in_window >= self.cfg.rev_budget {
                self.budget_used = true;
                self.close_window();
            }
        }
    }

    /// The main MCU was reset (by the supervisor's own `NRST` pulse or seen on the reset line). Its pins float: the permit drops, the
    /// PHASE decoder resyncs to `a`, `b` without counting, the state goes to IDLE after the dead time (never straight to ARMED).
    /// A FAULT / LOCKED state stays. F7: whatever the state, no permit is granted for the reset hold-off (>= 10 ms) after this call.
    pub fn on_main_reset(&mut self, now_ms: u64, a: bool, b: bool) -> Outputs {
        self.advance(now_ms);
        self.reset_event(a, b);
        self.outputs()
    }

    /// A brown-out of the 3V3 rail that the platform shell saw (BOR / PVD flag, or a dip seen on a supply monitor) without a full
    /// reset of this chip (F7). Same as a reset of the main MCU: the permit drops at once, the PHASE decoder resyncs, an armed or idle
    /// supervisor goes to DEAD, and no permit can be granted for the reset hold-off (at least [`MIN_RESET_HOLDOFF_MS`]) even if the
    /// dead time is shorter. The supervisor's own reset needs no call: [`Supervisor::new`] starts the same hold-off.
    pub fn on_brown_out(&mut self, now_ms: u64, a: bool, b: bool) -> Outputs {
        self.advance(now_ms);
        self.reset_event(a, b);
        self.outputs()
    }

    fn reset_event(&mut self, a: bool, b: bool) {
        self.dec.resync(a, b);
        self.holdoff_until = self.holdoff_until.max(self.now + self.cfg.effective_reset_holdoff_ms() as u64);
        if matches!(self.state, State::Armed | State::Idle) {
            self.state = State::Dead;
            self.dead_since = self.now;
        }
    }

    /// Everything the status frame needs.
    pub fn snapshot(&self) -> crate::status::StatusFrame {
        crate::status::StatusFrame {
            state: self.state,
            reason: self.reason,
            fwd_in_window: self.fwd_in_window.min(255) as u8,
            rev_in_window: self.rev_in_window.min(0xFFFF) as u16,
            hour_level: self.hour.level_steps().min(0xFFFF) as u16,
            minute_level: self.minute.level_steps().min(0xFFFF) as u16,
            arm_edges: self.arm_edges,
        }
    }
}
