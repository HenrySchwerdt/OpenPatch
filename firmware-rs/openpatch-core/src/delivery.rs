//! Delivery engine: turns basal schedule / temp basal / bolus into SMA pulses on a tick basis.
//! Fixed point only; fractional pulses are accumulated exactly (as a rational), so over any period
//! `|scheduled - delivered| < 1 pulse` (plus whatever was explicitly dropped).
//!
//! The engine knows NOTHING about safety limits: every step it requests must be approved by the
//! safety supervisor before it reaches the motor.
//!
//! Semantics (DASH-like): starts SUSPENDED; basal rests during a bolus (no catch-up), bolus runs
//! at 1.5 U/min; suspend cancels bolus and temp basal; temp basal falls back to the programmed
//! basal [`COMM_LOSS_TEMP_MS`] after the last [`DeliveryEngine::comm_heartbeat`].

use crate::limits::*;
use crate::units::*;
use heapless::Vec;
use openpatch_proto::Error;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct BasalSeg {
    /// 0..47, 30-minute slot where this segment starts.
    pub start_slot: u8,
    pub rate: MilliUnitsPerHour,
}

/// Up to 24 segments; `seg[0].start_slot == 0`; strictly ascending; a segment ends where the next
/// starts (the last one at midnight).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct BasalSchedule {
    pub segs: Vec<BasalSeg, BASAL_SEGMENTS_MAX>,
}

impl BasalSchedule {
    pub fn new() -> Self {
        Self { segs: Vec::new() }
    }

    /// A single 24 h segment.
    pub fn flat(rate: MilliUnitsPerHour) -> Self {
        let mut s = Self::new();
        let _ = s.segs.push(BasalSeg { start_slot: 0, rate });
        s
    }

    pub fn from_pairs(pairs: &[(u8, u32)]) -> Option<Self> {
        let mut s = Self::new();
        for &(slot, rate) in pairs {
            s.segs.push(BasalSeg { start_slot: slot, rate: MilliUnitsPerHour(rate) }).ok()?;
        }
        Some(s)
    }

    pub fn validate(&self) -> Result<(), Error> {
        if self.segs.is_empty() || self.segs.len() > BASAL_SEGMENTS_MAX {
            return Err(Error::BadArg);
        }
        if self.segs[0].start_slot != 0 {
            return Err(Error::BadArg);
        }
        for (i, s) in self.segs.iter().enumerate() {
            if s.start_slot >= SLOTS_PER_DAY {
                return Err(Error::BadArg);
            }
            if i > 0 && s.start_slot <= self.segs[i - 1].start_slot {
                return Err(Error::BadArg);
            }
        }
        Ok(())
    }

    pub fn count(&self) -> usize {
        self.segs.len()
    }
}

/// Events raised by the engine, consumed by the controller via [`DeliveryEngine::take_events`].
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct EngineEvents(pub u8);

impl EngineEvents {
    pub const BOLUS_DONE: u8 = 1 << 0;
    pub const TEMP_DONE: u8 = 1 << 1;
    pub const TEMP_COMM_FALLBACK: u8 = 1 << 2;
    pub fn has(self, bit: u8) -> bool {
        self.0 & bit != 0
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct EngineReport {
    pub scheduled: MilliUnits,
    pub delivered: MilliUnits,
    pub delivered_steps: Pulses,
    pub dropped_steps: Pulses,
}

#[derive(Clone, Debug)]
pub struct DeliveryEngine {
    schedule: BasalSchedule,
    has_schedule: bool,
    suspended: bool,
    temp_active: bool,
    temp_rate: u32,
    temp_remaining_ms: u32,
    bolus_active: bool,
    bolus_remaining_scaled: i64,
    ms_of_day: u32,
    ms_since_comm: u32,
    cal: PulseCal,
    threshold: i64,
    cal_den: i64,
    acc: i64,
    scheduled_scaled: i64,
    requested_steps: u32,
    delivered_steps: u32,
    dropped_steps: u32,
    pending_steps: u32,
    events: u8,
}

impl DeliveryEngine {
    /// An invalid calibration (`PulseCal::NONE`): the engine never requests a pulse.
    pub fn new(cal: PulseCal) -> Self {
        Self {
            schedule: BasalSchedule::new(),
            has_schedule: false,
            suspended: true, // safe default: nothing runs until explicitly resumed
            temp_active: false,
            temp_rate: 0,
            temp_remaining_ms: 0,
            bolus_active: false,
            bolus_remaining_scaled: 0,
            ms_of_day: 0,
            ms_since_comm: 0,
            cal,
            threshold: if cal.is_none() { 0 } else { cal.threshold() },
            cal_den: cal.uu_den as i64,
            acc: 0,
            scheduled_scaled: 0,
            requested_steps: 0,
            delivered_steps: 0,
            dropped_steps: 0,
            pending_steps: 0,
            events: 0,
        }
    }

    pub fn set_schedule(&mut self, s: &BasalSchedule) -> Result<(), Error> {
        s.validate()?;
        self.schedule = s.clone();
        self.has_schedule = true;
        Ok(())
    }

    pub fn set_time_of_day(&mut self, t: Millis) {
        self.ms_of_day = (t.0 % DAY_MS as u64) as u32;
    }

    pub fn comm_heartbeat(&mut self) {
        self.ms_since_comm = 0;
    }

    fn basal_rate_at(&self, ms_of_day: u32) -> u32 {
        if !self.has_schedule {
            return 0;
        }
        let slot = ms_of_day / SLOT_MS;
        let mut rate = self.schedule.segs[0].rate.0;
        for s in self.schedule.segs.iter().skip(1) {
            if s.start_slot as u32 > slot {
                break;
            }
            rate = s.rate.0;
        }
        rate
    }

    pub fn start_temp_basal(&mut self, rate: MilliUnitsPerHour, duration: Minutes) -> Result<(), Error> {
        let d = duration.0;
        if d == 0 || d > TEMP_MAX_MIN || d % TEMP_GRANULARITY_MIN != 0 {
            return Err(Error::BadArg);
        }
        if self.suspended {
            return Err(Error::Suspended);
        }
        self.temp_active = true;
        self.temp_rate = rate.0;
        self.temp_remaining_ms = d * 60_000;
        Ok(())
    }

    /// `true` if a temp basal was active.
    pub fn cancel_temp_basal(&mut self) -> bool {
        let was = self.temp_active;
        self.temp_active = false;
        self.temp_remaining_ms = 0;
        was
    }

    pub fn start_bolus(&mut self, amount: MilliUnits) -> Result<(), Error> {
        if amount.0 == 0 {
            return Err(Error::BadArg);
        }
        if self.suspended {
            return Err(Error::Suspended);
        }
        if self.bolus_active {
            return Err(Error::Busy);
        }
        self.bolus_active = true;
        self.bolus_remaining_scaled = amount.0 as i64 * SCALED_PER_MU;
        Ok(())
    }

    /// The amount that will NOT be delivered (0 if none was active).
    pub fn cancel_bolus(&mut self) -> MilliUnits {
        if !self.bolus_active {
            return MilliUnits(0);
        }
        let left = self.bolus_remaining();
        self.bolus_active = false;
        self.bolus_remaining_scaled = 0;
        left
    }

    /// Cancels bolus and temp basal.
    pub fn suspend(&mut self) {
        self.cancel_bolus();
        self.cancel_temp_basal();
        self.suspended = true;
    }

    pub fn resume(&mut self) {
        self.suspended = false;
    }

    /// Largest time slice in which rate, bolus state and comm-loss state are constant.
    fn next_chunk(&self, dt: u32) -> u32 {
        let mut chunk = dt;
        let to_slot = SLOT_MS - (self.ms_of_day % SLOT_MS);
        chunk = chunk.min(to_slot);
        if self.temp_active {
            chunk = chunk.min(self.temp_remaining_ms);
            if self.ms_since_comm < COMM_LOSS_TEMP_MS {
                chunk = chunk.min(COMM_LOSS_TEMP_MS - self.ms_since_comm);
            }
        }
        chunk
    }

    /// Advance by `dt`; returns the steps the engine wants executed now. The controller clamps
    /// stalls to 5 s; durations beyond `u32::MAX` ms saturate.
    pub fn tick(&mut self, dt: Millis) -> Pulses {
        let mut dt_ms = u32::try_from(dt.0).unwrap_or(u32::MAX);
        let mut steps_total: u32 = 0;
        while dt_ms > 0 {
            if self.temp_active && self.ms_since_comm >= COMM_LOSS_TEMP_MS {
                self.cancel_temp_basal();
                self.events |= EngineEvents::TEMP_COMM_FALLBACK;
            }
            let mut chunk = self.next_chunk(dt_ms);
            if chunk == 0 {
                chunk = 1; // defensive: never spin
            }

            let inc: i64;
            if self.bolus_active {
                // suspend cancels the bolus, so it is never active while suspended
                let mut i = BOLUS_RATE.0 as i64 * chunk as i64;
                if i >= self.bolus_remaining_scaled {
                    i = self.bolus_remaining_scaled;
                    self.bolus_active = false;
                    self.events |= EngineEvents::BOLUS_DONE;
                }
                self.bolus_remaining_scaled -= i;
                self.scheduled_scaled += i;
                inc = i;
            } else {
                let rate = if self.temp_active { self.temp_rate } else { self.basal_rate_at(self.ms_of_day) };
                inc = rate as i64 * chunk as i64;
                self.scheduled_scaled += inc; // counted even while suspended: shows the deficit
            }
            if !self.suspended && self.threshold > 0 {
                // exact rational accounting: accumulate rate*ms*den, emit one pulse per num*3600
                self.acc += inc * self.cal_den;
                let steps = self.acc / self.threshold;
                self.acc -= steps * self.threshold;
                steps_total += steps as u32;
            }

            self.ms_of_day = ((self.ms_of_day as u64 + chunk as u64) % DAY_MS as u64) as u32;
            if self.ms_since_comm < COMM_LOSS_TEMP_MS {
                self.ms_since_comm = (self.ms_since_comm + chunk).min(COMM_LOSS_TEMP_MS);
            }
            if self.temp_active {
                self.temp_remaining_ms -= chunk;
                if self.temp_remaining_ms == 0 {
                    self.temp_active = false;
                    self.events |= EngineEvents::TEMP_DONE;
                }
            }
            dt_ms -= chunk;
        }
        self.requested_steps = self.requested_steps.wrapping_add(steps_total);
        self.pending_steps = self.pending_steps.wrapping_add(steps_total);
        Pulses(steps_total)
    }

    /// Report how many of the pending steps were really executed.
    pub fn commit(&mut self, executed: Pulses) {
        let executed = executed.0.min(self.pending_steps);
        self.delivered_steps = self.delivered_steps.wrapping_add(executed);
        self.dropped_steps = self.dropped_steps.wrapping_add(self.pending_steps - executed);
        self.pending_steps = 0;
    }

    /// Account `executed` pulses as delivered without touching the rest of the pending ones
    /// (pulses wait for the SMA cooling time instead of being dropped).
    pub fn commit_partial(&mut self, executed: Pulses) {
        let executed = executed.0.min(self.pending_steps);
        self.delivered_steps = self.delivered_steps.wrapping_add(executed);
        self.pending_steps -= executed;
    }

    /// Count extra delivered pulses (a double advance moved more than one tooth).
    pub fn add_delivered(&mut self, n: Pulses) {
        self.delivered_steps = self.delivered_steps.wrapping_add(n.0);
    }

    /// Give up `n` pending pulses (vetoed / not executable): counted as dropped.
    pub fn drop_pending(&mut self, n: Pulses) {
        let n = n.0.min(self.pending_steps);
        self.dropped_steps = self.dropped_steps.wrapping_add(n);
        self.pending_steps -= n;
    }

    pub fn take_events(&mut self) -> EngineEvents {
        let e = self.events;
        self.events = 0;
        EngineEvents(e)
    }

    pub fn current_rate(&self) -> MilliUnitsPerHour {
        MilliUnitsPerHour(if self.temp_active { self.temp_rate } else { self.basal_rate_at(self.ms_of_day) })
    }

    /// Rounded up.
    pub fn bolus_remaining(&self) -> MilliUnits {
        if !self.bolus_active {
            return MilliUnits(0);
        }
        MilliUnits(((self.bolus_remaining_scaled + SCALED_PER_MU - 1) / SCALED_PER_MU) as u32)
    }

    /// Rounded up.
    pub fn temp_remaining(&self) -> Minutes {
        Minutes(if self.temp_active { self.temp_remaining_ms.div_ceil(60_000) } else { 0 })
    }

    pub fn report(&self) -> EngineReport {
        EngineReport {
            scheduled: MilliUnits((self.scheduled_scaled / SCALED_PER_MU) as u32),
            delivered: self.cal.pulses_to_mu(Pulses(self.delivered_steps)),
            delivered_steps: Pulses(self.delivered_steps),
            dropped_steps: Pulses(self.dropped_steps),
        }
    }

    // ---- accessors -------------------------------------------------------------
    pub fn is_suspended(&self) -> bool {
        self.suspended
    }
    pub fn bolus_active(&self) -> bool {
        self.bolus_active
    }
    pub fn temp_active(&self) -> bool {
        self.temp_active
    }
    pub fn temp_rate(&self) -> MilliUnitsPerHour {
        MilliUnitsPerHour(self.temp_rate)
    }
    pub fn has_schedule(&self) -> bool {
        self.has_schedule
    }
    pub fn schedule(&self) -> &BasalSchedule {
        &self.schedule
    }
    pub fn ms_of_day(&self) -> u32 {
        self.ms_of_day
    }
    pub fn ms_since_comm(&self) -> u32 {
        self.ms_since_comm
    }
    pub fn delivered_steps(&self) -> Pulses {
        Pulses(self.delivered_steps)
    }
    pub fn dropped_steps(&self) -> Pulses {
        Pulses(self.dropped_steps)
    }
    pub fn requested_steps(&self) -> Pulses {
        Pulses(self.requested_steps)
    }
    pub fn pending_steps(&self) -> Pulses {
        Pulses(self.pending_steps)
    }
    /// Exact fractional-pulse accumulator (scaled by uu_den); `0 <= acc < threshold()`.
    pub fn accumulator(&self) -> i64 {
        self.acc
    }
    /// Accumulator size of one pulse (`uu_num * 3600`).
    pub fn threshold(&self) -> i64 {
        self.threshold
    }
    /// What the program asked for, in scaled units (`rate[mU/h] * ms`).
    pub fn scheduled_scaled(&self) -> i64 {
        self.scheduled_scaled
    }
    pub fn calibration(&self) -> PulseCal {
        self.cal
    }
}
