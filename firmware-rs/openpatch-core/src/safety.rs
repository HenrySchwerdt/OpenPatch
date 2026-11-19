//! Safety supervisor. Deliberately independent of the delivery engine and reservoir model: it
//! receives plain numbers and can veto every single step. Faults are latched and need an explicit
//! [`SafetySupervisor::acknowledge`].
//!
//! Monitored:
//! * max bolus / max basal (configurable, clamped to the hard caps)
//! * 15 U rolling 60 min window over ALL approved steps (10 s buckets: true rolling bound, reduced by the
//!   calibration tolerance margin so the physical volume is <= 15 U/h; + per-minute backstop)
//! * occlusion: (commanded - angle-confirmed) > 2 U; total stall ("no travel despite steps");
//!   **motor-current rise** (consecutive high-current bursts, new in the Rust port)
//! * encoder deviation > 10 % over each >= 1 U window, and **per leadscrew revolution** (TMAG5273:
//!   4096 counts +- 3 % per commanded revolution, new in the Rust port)
//! * reservoir empty, battery critical, wear limit, drive calibration
//! * hard preconditions for every step: calibrated, docked, active pod, no latched fault

use crate::delivery::BasalSchedule;
use crate::diag::{codes, DiagCode, DiagState, Raise};
use crate::faults::Faults;
use crate::limits::*;
use crate::units::*;
use openpatch_proto::Error;

const MINUTE_MS: u64 = 60_000;
/// Rolling-hour accounting: 10 s buckets, `HOUR_BUCKETS` = 360 + 1 of them. Any real 60 minute window touches at
/// most 361 consecutive bucket indexes, so "the sum of the 361 newest buckets <= cap" bounds the approved steps
/// in EVERY 60 minute window (FINDING-003: the old 60 wall-clock minute buckets allowed 15 U + 1.7 U in 59 min).
const BUCKET_MS: u64 = 10_000;
const HOUR_BUCKETS: usize = 361;

/// Inputs of the periodic monitor.
#[derive(Clone, Copy, Debug)]
pub struct Observation {
    pub battery_mv: u16,
    /// `None` = reservoir not filled yet (not monitored: no alarm at first boot).
    pub reservoir: Option<MilliUnits>,
    pub angle: AngleCounts,
}

#[derive(Clone, Debug)]
pub struct SafetySupervisor {
    max_bolus: MilliUnits,
    max_basal: MilliUnitsPerHour,
    cal: PulseCal,
    max_steps_per_min: u32,
    calibrated: bool,
    docked: bool,
    active: bool,
    wear_expired: bool,
    hour_buckets: [u16; HOUR_BUCKETS],
    last_bucket: u64,
    /// Steps approved in the current wall-clock minute (per-minute backstop).
    minute_used: u32,
    cur_minute: u64,
    /// Rolling-hour cap in steps: `MAX_HOURLY` reduced by the calibration tolerance margin.
    hourly_cap_steps: u32,
    /// C reference parity (host differential tests only): 15 U over 60 wall-clock minute buckets, no margin.
    c_compat: bool,
    /// Derived projection of `diag` (the active F/L records), recomputed after every change.
    faults: Faults,
    last_new_faults: Faults,
    diag: DiagState,
    // angle tracking (counts)
    cmd_steps: u64,
    cmd_counts: i64,
    enc_base: i64,
    last_enc: i64,
    win_cmd0: i64,
    win_enc0: i64,
    rev_steps0: u64,
    rev_enc0: i64,
    last_battery_mv: u16,
    last_reservoir: Option<MilliUnits>,
    battery_low: bool,
    high_current_bursts: u8,
    occlusion_ma: u16,
    /// Last forward-burst peak currents (ring), the lowest window minimum since the last re-baseline (0 = none yet) and
    /// the bursts since the last creep step.
    win: [u16; OCC_WINDOW_BURSTS],
    win_n: usize,
    base_ma: u16,
    base_bursts: u16,
}

/// `MAX_HOURLY` reduced so that the volume that PHYSICALLY leaves the needle stays <= 15 U/h even at the
/// worst-case tolerance of the stadium area and the leadscrew lead (F6, `limits::HOURLY_CAL_MARGIN_PCT`).
pub(crate) fn hourly_cap_mu() -> MilliUnits {
    MilliUnits((MAX_HOURLY.0 as u64 * 100 / (100 + HOURLY_CAL_MARGIN_PCT as u64)) as u32)
}

fn u16_sat(v: u32) -> u16 {
    v.min(0xFFFF) as u16
}

impl SafetySupervisor {
    /// A calibration that is `NONE` or outside [`CAL_UU_MIN`], [`CAL_UU_MAX`] latches
    /// `NO_CALIBRATION`: every check/approve then refuses and the fault cannot be acknowledged.
    pub fn new(now: Millis, angle: AngleCounts, cal: PulseCal) -> Self {
        let mut sv = Self {
            max_bolus: DEFAULT_MAX_BOLUS,
            max_basal: DEFAULT_MAX_BASAL,
            cal: PulseCal::NONE,
            max_steps_per_min: 0,
            calibrated: false,
            docked: false,
            active: false,
            wear_expired: false,
            hour_buckets: [0; HOUR_BUCKETS],
            last_bucket: now.0 / BUCKET_MS,
            minute_used: 0,
            cur_minute: now.0 / MINUTE_MS,
            hourly_cap_steps: 0,
            c_compat: false,
            faults: Faults::NONE,
            last_new_faults: Faults::NONE,
            diag: DiagState::new(),
            cmd_steps: 0,
            cmd_counts: 0,
            enc_base: 0,
            last_enc: 0,
            win_cmd0: 0,
            win_enc0: 0,
            rev_steps0: 0,
            rev_enc0: 0,
            last_battery_mv: 0xFFFF,
            last_reservoir: None,
            battery_low: false,
            high_current_bursts: 0,
            occlusion_ma: OCCLUSION_CURRENT_MA,
            win: [0; OCC_WINDOW_BURSTS],
            win_n: 0,
            base_ma: 0,
            base_bursts: 0,
        };
        if cal_in_range(cal) {
            sv.cal = cal;
            sv.calibrated = true;
            sv.max_steps_per_min = cal.mu_to_pulses(MAX_PER_MIN).0;
            sv.hourly_cap_steps = cal.mu_to_pulses(hourly_cap_mu()).0;
        } else {
            sv.diag.set_time_s((now.0 / 1000) as u32);
            // inst 1 = no calibration at all, 3 = outside the plausible range
            let inst = if cal.is_none() { 1 } else { 3 };
            sv.raise(Raise::new(codes::CAL_RECORD_INVALID).inst(inst).a(cal.micro_u_floor() as i32));
        }
        sv.rebaseline(angle);
        sv
    }

    /// Rejects (`Limit`) zero values and values above the hard caps.
    pub fn configure(&mut self, max_bolus: MilliUnits, max_basal: MilliUnitsPerHour) -> Result<(), Error> {
        if max_bolus.0 == 0 || max_basal.0 == 0 {
            return Err(Error::Limit);
        }
        if max_bolus > HARD_MAX_BOLUS || max_basal > HARD_MAX_BASAL {
            return Err(Error::Limit);
        }
        self.max_bolus = max_bolus;
        self.max_basal = max_basal;
        Ok(())
    }

    // ---- rolling window ------------------------------------------------------------
    fn roll(&mut self, now: Millis) {
        let b = now.0 / BUCKET_MS;
        if b > self.last_bucket {
            if b - self.last_bucket >= HOUR_BUCKETS as u64 {
                self.hour_buckets = [0; HOUR_BUCKETS];
            } else {
                for k in self.last_bucket + 1..=b {
                    self.hour_buckets[(k % HOUR_BUCKETS as u64) as usize] = 0;
                }
            }
            self.last_bucket = b; // time never goes backwards
        }
        let m = now.0 / MINUTE_MS;
        if m > self.cur_minute {
            self.cur_minute = m;
            self.minute_used = 0;
        }
    }

    /// Steps approved in the rolling 60 minute window (the 361 newest 10 s buckets: at least 60 minutes).
    /// In C-compat mode: the 60 wall-clock minute buckets of the frozen C reference (the same 10 s buckets,
    /// summed over the last 59 minutes plus the current one).
    pub fn hourly_steps(&mut self, now: Millis) -> Pulses {
        self.roll(now);
        if self.c_compat {
            let from = (now.0 / MINUTE_MS).saturating_sub(59) * (MINUTE_MS / BUCKET_MS);
            let mut sum = 0u32;
            let mut k = from.max(self.last_bucket.saturating_sub(HOUR_BUCKETS as u64 - 1));
            while k <= self.last_bucket {
                sum += self.hour_buckets[(k % HOUR_BUCKETS as u64) as usize] as u32;
                k += 1;
            }
            return Pulses(sum);
        }
        Pulses(self.hour_buckets.iter().map(|&v| v as u32).sum())
    }

    /// Switch to the legacy hourly accounting of the C reference (no tolerance margin, 60 wall-clock minute
    /// buckets). ONLY for the differential tests (`PumpConfig::RELAXED`); production keeps the default.
    pub fn set_c_compat(&mut self, on: bool) {
        self.c_compat = on;
        if self.calibrated {
            let cap = if on { MAX_HOURLY } else { hourly_cap_mu() };
            self.hourly_cap_steps = self.cal.mu_to_pulses(cap).0;
        }
    }

    /// How many steps `approve_steps` would approve right now (hourly cap, per-minute backstop, reservoir) without trimming.
    pub fn step_room(&mut self, now: Millis, reservoir: MilliUnits) -> Pulses {
        let used = self.hourly_steps(now).0;
        let room = self.hourly_cap_steps.saturating_sub(used);
        let minute_room = self.max_steps_per_min.saturating_sub(self.minute_used);
        Pulses(room.min(minute_room).min(self.cal.mu_to_pulses(reservoir).0))
    }

    /// The rolling-hour cap in steps (`MAX_HOURLY` less the calibration tolerance margin).
    pub fn hourly_cap_steps(&self) -> Pulses {
        Pulses(self.hourly_cap_steps)
    }

    // ---- preconditions -----------------------------------------------------------------
    pub fn set_docked(&mut self, d: bool) {
        self.docked = d;
    }
    pub fn set_active(&mut self, a: bool) {
        self.active = a;
    }

    /// Latches `WEAR_EXPIRED` at >= 52 h.
    pub fn observe_wear(&mut self, wear: Millis) {
        if wear < WEAR_MAX {
            return;
        }
        self.wear_expired = true;
        self.raise(Raise::new(codes::WEAR_EXPIRED).a((wear.0 / 60_000) as i32));
    }

    /// New activation: the wear timer restarts and the wear fault is released.
    pub fn reset_wear(&mut self) {
        self.wear_expired = false;
        self.diag.clear(codes::WEAR_EXPIRED);
        self.sync_faults_cache();
    }

    // ---- command validation --------------------------------------------------------------
    pub fn check_bolus(&mut self, now: Millis, amount: MilliUnits, reservoir: MilliUnits) -> Result<(), Error> {
        if !self.faults.is_empty() {
            return Err(Error::Fault);
        }
        if !self.active {
            return Err(Error::Released);
        }
        if !self.docked {
            return Err(Error::NotDocked);
        }
        if amount.0 == 0 || amount.0 % BOLUS_GRANULARITY.0 != 0 {
            return Err(Error::BadArg);
        }
        if amount > self.max_bolus {
            return Err(Error::Limit);
        }
        if amount > reservoir {
            return Err(Error::Reservoir);
        }
        let cap = self.hourly_cap_steps;
        if self.hourly_steps(now).0 + self.cal.mu_to_pulses(amount).0 > cap {
            return Err(Error::Hourly);
        }
        Ok(())
    }

    fn check_rate(&self, rate: MilliUnitsPerHour) -> Result<(), Error> {
        if rate.0 % RATE_GRANULARITY.0 != 0 {
            return Err(Error::BadArg);
        }
        if rate > self.max_basal {
            return Err(Error::Limit);
        }
        Ok(())
    }

    pub fn check_basal_schedule(&self, s: &BasalSchedule) -> Result<(), Error> {
        if !self.faults.is_empty() {
            return Err(Error::Fault);
        }
        s.validate()?;
        for seg in s.segs.iter() {
            self.check_rate(seg.rate)?;
        }
        Ok(())
    }

    pub fn check_temp_basal(&self, rate: MilliUnitsPerHour, duration: Minutes) -> Result<(), Error> {
        if !self.faults.is_empty() {
            return Err(Error::Fault);
        }
        let d = duration.0;
        if d == 0 || d > TEMP_MAX_MIN || d % TEMP_GRANULARITY_MIN != 0 {
            return Err(Error::BadArg);
        }
        self.check_rate(rate)
    }

    // ---- step veto -------------------------------------------------------------------------
    /// Latch legacy fault bits detected by a caller that has no more specific diagnostic code.
    /// Each bit is raised as the catalogue code that projects to it (INTERNAL: `7-7C-003`, an
    /// unattributed internal fault). New call sites should use [`SafetySupervisor::raise`].
    pub fn latch(&mut self, mask: Faults) {
        for (bit, code) in LEGACY_CODES {
            if mask.contains(Faults(1 << bit)) {
                self.raise(Raise::new(code).a(mask.bits() as i32));
            }
        }
    }

    /// Records a diagnostic anomaly (the single entry point of the core) and refreshes the derived
    /// legacy fault bits. Returns the id of the record.
    pub fn raise(&mut self, r: Raise) -> u32 {
        let id = self.diag.raise(r);
        self.sync_faults_cache();
        id
    }

    /// Like [`SafetySupervisor::raise`], linked to the record that caused it (cause chain).
    pub fn raise_caused_by(&mut self, r: Raise, cause_rec: u32) -> u32 {
        self.raise(r.caused_by(cause_rec))
    }

    /// Recomputes the derived legacy bits after the diagnostic state was changed through
    /// [`SafetySupervisor::diag_mut`].
    pub fn resync_faults(&mut self) {
        self.sync_faults_cache();
    }

    fn sync_faults_cache(&mut self) {
        let now = self.diag.legacy_faults();
        self.last_new_faults |= now & !self.faults;
        self.faults = now;
    }

    /// Time base for the record timestamps (seconds since boot).
    pub fn set_time(&mut self, now: Millis) {
        self.diag.set_time_s((now.0 / 1000) as u32);
    }

    /// The diagnostic engine (records, active and latched sets, projections).
    pub fn diag(&self) -> &DiagState {
        &self.diag
    }
    pub fn diag_mut(&mut self) -> &mut DiagState {
        &mut self.diag
    }

    /// Veto point for EVERY step: how many of `requested` may run. Trimming below `requested`
    /// for limit/reservoir reasons latches a fault. Never approves while faulted, uncalibrated,
    /// wear-expired, released (not the active pod) or undocked.
    pub fn approve_steps(&mut self, now: Millis, requested: Pulses, reservoir: MilliUnits) -> Pulses {
        if requested.0 == 0 {
            return Pulses(0);
        }
        self.set_time(now);
        if !self.faults.is_empty() || !self.calibrated || self.wear_expired {
            return Pulses(0);
        }
        if !self.active || !self.docked {
            return Pulses(0); // released or off the cannula adapter: never a step
        }
        let mut allowed = requested.0;

        let res_steps = self.cal.mu_to_pulses(reservoir).0;
        if res_steps < allowed {
            allowed = res_steps;
            self.raise(Raise::new(codes::RESERVOIR_EMPTY).a(reservoir.0 as i32));
        }
        let used = self.hourly_steps(now).0;
        let cap = self.hourly_cap_steps;
        let room = cap.saturating_sub(used);
        if room < allowed {
            allowed = room;
            self.raise(Raise::new(codes::HOURLY_LIMIT_VETO).a(used as i32).b(cap as i32).c(requested.0));
        }
        let minute_used = self.minute_used.min(self.max_steps_per_min);
        let minute_room = self.max_steps_per_min - minute_used;
        if minute_room < allowed {
            allowed = minute_room;
            self.raise(Raise::new(codes::PER_MINUTE_LIMIT_VETO).a(minute_used as i32).b(self.max_steps_per_min as i32).c(requested.0));
        }
        let b = (self.last_bucket % HOUR_BUCKETS as u64) as usize;
        self.hour_buckets[b] = u16_sat(self.hour_buckets[b] as u32 + allowed);
        self.minute_used = self.minute_used.saturating_add(allowed);
        self.cmd_steps += allowed as u64;
        self.cmd_counts = self.cal.expected_angle(Pulses(self.cmd_steps.min(u32::MAX as u64) as u32)).0;
        Pulses(allowed)
    }

    // ---- monitoring -------------------------------------------------------------------------
    /// Restart angle bookkeeping (after fill/prime/draw or fault acknowledge).
    pub fn rebaseline(&mut self, angle: AngleCounts) {
        self.cmd_steps = 0;
        self.cmd_counts = 0;
        self.enc_base = angle.0;
        self.last_enc = angle.0;
        self.win_cmd0 = 0;
        self.win_enc0 = angle.0;
        self.rev_steps0 = 0;
        self.rev_enc0 = angle.0;
        self.high_current_bursts = 0;
        self.win_n = 0; // the running level of the pod is measured again after a fill / prime / draw / acknowledge
        self.base_ma = 0;
        self.base_bursts = 0;
    }

    fn check_encoder(&mut self, enc: i64) {
        self.last_enc = enc;
        if !self.calibrated {
            return;
        }
        let travelled = enc - self.enc_base;
        let undelivered = self.cmd_counts - travelled;
        if undelivered > self.cal.mu_to_angle(OCCLUSION).0 {
            self.raise(Raise::new(codes::OCCLUSION_SHORTFALL).a((undelivered * OCCLUSION.0 as i64 / self.cal.mu_to_angle(OCCLUSION).0.max(1)) as i32).b(OCCLUSION.0 as i32).c(self.cmd_steps.min(u32::MAX as u64) as u32));
        }

        let cmd_win = self.cmd_counts - self.win_cmd0;
        if cmd_win >= self.cal.mu_to_angle(ENCODER_WINDOW).0 {
            let enc_win = enc - self.win_enc0;
            let err = (cmd_win - enc_win).abs();
            if err * 100 > cmd_win * ENCODER_TOLERANCE_PCT {
                let permille = (err * 1000 / cmd_win.max(1)) as i32;
                let steps = self.cmd_steps.min(u32::MAX as u64) as u32;
                let id = self.raise(Raise::new(codes::ENC_WINDOW_DEVIATION).a(permille).b(ENCODER_TOLERANCE_PCT as i32 * 10).c(steps));
                // "no travel despite steps": the spindle barely moved at all
                if enc_win * 10 < cmd_win {
                    self.raise_caused_by(Raise::new(codes::CARRIAGE_JAM_FWD).a(enc_win as i32).b(cmd_win as i32).c(steps), id);
                }
            }
            self.win_cmd0 = self.cmd_counts;
            self.win_enc0 = enc;
        }

        // per leadscrew revolution (TMAG5273 absolute angle): one commanded revolution must read
        // 4096 counts +- REV_TOLERANCE_PCT
        let turn_steps = (self.cal.turn_x100 as u64).div_ceil(100);
        if turn_steps > 0 && self.cmd_steps - self.rev_steps0 >= turn_steps {
            let exact = self.cal.expected_angle(Pulses((self.cmd_steps - self.rev_steps0).min(u32::MAX as u64) as u32)).0;
            let measured = enc - self.rev_enc0;
            if (measured - exact).abs() * 100 > exact * REV_TOLERANCE_PCT {
                self.raise(Raise::new(codes::ENC_REV_DEVIATION).a(measured as i32).b(exact as i32).c(self.cmd_steps.min(u32::MAX as u64) as u32));
            }
            self.rev_steps0 = self.cmd_steps;
            self.rev_enc0 = enc;
        }
    }

    /// Periodic monitor: call after motor activity. Returns the newly latched faults.
    pub fn observe(&mut self, now: Millis, o: &Observation) -> Faults {
        self.set_time(now);
        self.last_new_faults = Faults::NONE;
        self.last_battery_mv = o.battery_mv;
        self.last_reservoir = o.reservoir;
        self.battery_low = o.battery_mv < BATTERY_LOW_MV;
        if o.battery_mv < BATTERY_CRITICAL_MV {
            // inst 1 = bench VBUS source
            self.raise(Raise::new(codes::BATTERY_CRITICAL).inst(1).a(o.battery_mv as i32).b(BATTERY_CRITICAL_MV as i32));
        }
        if o.reservoir == Some(MilliUnits(0)) {
            self.raise(Raise::new(codes::RESERVOIR_EMPTY).a(0));
        }
        self.check_encoder(o.angle.0);
        self.last_new_faults
    }

    /// Occlusion current threshold in force (mA); starts at the hard limit.
    pub fn occlusion_current_ma(&self) -> u16 {
        self.occlusion_ma
    }

    /// Tune the occlusion current threshold on the bench. Only LOWERING is possible: values above
    /// [`OCCLUSION_CURRENT_MA`] (the hard limit) or 0 are refused with `Err(Limit)`.
    pub fn set_occlusion_current_ma(&mut self, ma: u16) -> Result<(), openpatch_proto::Error> {
        if ma == 0 || ma > OCCLUSION_CURRENT_MA {
            return Err(openpatch_proto::Error::Limit);
        }
        self.occlusion_ma = ma;
        Ok(())
    }

    /// Motor-current occlusion input. Call after every forward step burst with the peak supply
    /// current measured during the burst. [`OCCLUSION_CURRENT_BURSTS`] consecutive bursts above
    /// [`OCCLUSION_CURRENT_MA`] latch `OCCLUSION`; a sub-threshold burst resets the count; `None`
    /// (no sensor) changes nothing. Returns `true` when OCCLUSION was newly latched.
    pub fn observe_motor_burst(&mut self, steps: Pulses, peak_ma: Option<u16>) -> bool {
        let Some(ma) = peak_ma else { return false };
        if steps.0 == 0 {
            return false;
        }
        // stored-volume accounting: the floor of the burst current (window minimum) rising above the pod's baseline
        let slot = self.win_n % OCC_WINDOW_BURSTS;
        self.win[slot] = ma;
        self.win_n = self.win_n.saturating_add(1);
        if self.win_n >= OCC_WINDOW_BURSTS {
            let floor = self.win.iter().copied().min().unwrap_or(ma);
            if self.base_ma == 0 || floor < self.base_ma {
                self.base_ma = floor;
                self.base_bursts = 0;
            } else {
                self.base_bursts += 1;
                if self.base_bursts >= OCC_BASELINE_CREEP_BURSTS {
                    self.base_bursts = 0;
                    self.base_ma = self.base_ma.saturating_add(OCC_BASELINE_CREEP_MA).min(floor);
                }
            }
            if floor > self.base_ma.saturating_add(OCCLUSION_RISE_MA) && !self.faults.contains(Faults::OCCLUSION) {
                self.raise(Raise::new(codes::OCCLUSION_CURRENT_RISE).a(floor as i32).b(self.base_ma.saturating_add(OCCLUSION_RISE_MA) as i32).c(self.cmd_steps.min(u32::MAX as u64) as u32));
                return true;
            }
        }
        // absolute threshold: consecutive bursts above it
        let thr = self.occlusion_ma;
        if ma <= thr {
            self.high_current_bursts = 0;
            return false;
        }
        self.high_current_bursts = self.high_current_bursts.saturating_add(1);
        if self.high_current_bursts >= OCCLUSION_CURRENT_BURSTS && !self.faults.contains(Faults::OCCLUSION) {
            self.raise(Raise::new(codes::OCCLUSION_CURRENT_RISE).a(ma as i32).b(thr as i32).c(self.cmd_steps.min(u32::MAX as u64) as u32));
            return true;
        }
        false
    }

    /// Legacy fault bits (of `target`) whose cause is still present and that can therefore not be
    /// acknowledged (battery critical, no calibration, wear expired, reservoir empty).
    pub fn persisting(&self, target: Faults) -> Faults {
        let mut blocked = Faults::NONE;
        if target.contains(Faults::BATTERY_CRITICAL)
            && self.last_battery_mv < BATTERY_CRITICAL_MV + BATTERY_HYSTERESIS_MV
        {
            blocked |= Faults::BATTERY_CRITICAL;
        }
        if target.contains(Faults::NO_CALIBRATION) && !self.calibrated {
            blocked |= Faults::NO_CALIBRATION;
        }
        if target.contains(Faults::WEAR_EXPIRED) && self.wear_expired {
            blocked |= Faults::WEAR_EXPIRED;
        }
        if target.contains(Faults::RESERVOIR_EMPTY) && self.last_reservoir == Some(MilliUnits(0)) {
            blocked |= Faults::RESERVOIR_EMPTY;
        }
        blocked
    }

    /// Clears acknowledgeable faults. Faults whose cause persists (battery critical, no
    /// calibration, wear expired, reservoir empty) stay latched: `Err(Persists)`.
    pub fn acknowledge(&mut self, mask: Faults) -> Result<(), Error> {
        let target = self.faults & mask;
        let mut blocked = self.persisting(target);
        let clear = target & !blocked;
        // latched (L) records stay: they are cleared only by their verification test (ClearDiag)
        let cleared = self.diag.clear_legacy(clear);
        self.sync_faults_cache();
        blocked |= clear & self.faults;
        if cleared.intersects(Faults::OCCLUSION | Faults::ENCODER_DEVIATION | Faults::INTERNAL) {
            self.rebaseline(AngleCounts(self.last_enc));
        }
        if blocked.is_empty() {
            Ok(())
        } else {
            Err(Error::Persists)
        }
    }

    // ---- accessors -----------------------------------------------------------------------------
    pub fn faults(&self) -> Faults {
        self.faults
    }
    pub fn motor_allowed(&self) -> bool {
        self.faults.is_empty()
    }
    pub fn battery_low(&self) -> bool {
        self.battery_low
    }
    pub fn wear_expired(&self) -> bool {
        self.wear_expired
    }
    pub fn calibration(&self) -> PulseCal {
        self.cal
    }
    pub fn is_calibrated(&self) -> bool {
        self.calibrated
    }
    pub fn is_docked(&self) -> bool {
        self.docked
    }
    pub fn is_active(&self) -> bool {
        self.active
    }
    pub fn max_bolus(&self) -> MilliUnits {
        self.max_bolus
    }
    pub fn max_basal(&self) -> MilliUnitsPerHour {
        self.max_basal
    }
    pub fn max_steps_per_min(&self) -> Pulses {
        Pulses(self.max_steps_per_min)
    }
    /// Steps approved since the last baseline, as expected angle counts.
    pub fn commanded_counts(&self) -> AngleCounts {
        AngleCounts(self.cmd_counts)
    }
    pub fn commanded_steps(&self) -> Pulses {
        Pulses(self.cmd_steps.min(u32::MAX as u64) as u32)
    }
    pub fn last_angle(&self) -> AngleCounts {
        AngleCounts(self.last_enc)
    }
    pub fn encoder_baseline(&self) -> AngleCounts {
        AngleCounts(self.enc_base)
    }

    /// Copy with all faults cleared: lets a caller check a request against the pure limits (an
    /// old wear fault must not hide schedule errors).
    pub fn fault_free_probe(&self) -> SafetySupervisor {
        let mut p = self.clone();
        p.diag.clear_all_silent();
        p.faults = Faults::NONE;
        p
    }
}

/// Legacy bit -> the catalogue code a bare `latch(Faults::X)` raises (docs/06-diagnostics.md 2.7).
const LEGACY_CODES: [(u8, DiagCode); 8] = [
    (0, codes::OCCLUSION_SHORTFALL),
    (1, codes::ENC_WINDOW_DEVIATION),
    (2, codes::RESERVOIR_EMPTY),
    (3, DiagCode(codes::BATTERY_CRITICAL.0 | 1)),
    (4, codes::HOURLY_LIMIT_VETO),
    (5, codes::UNKNOWN_CODE_RAISED),
    (6, codes::CAL_RECORD_INVALID),
    (7, codes::WEAR_EXPIRED),
];
