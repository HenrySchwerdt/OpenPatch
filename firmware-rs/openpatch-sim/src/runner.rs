//! Scenario runner: executes a [`Scenario`] on a [`Device`], records the time series and builds the
//! verdict (delivered vs commanded, detection latencies, undelivered amount at the alarm, safety
//! limit and interlock checks).

use crate::device::{Device, DeviceConfig, PAIR_ID};
use crate::scenario::{Action, Detector, Scenario};
use openpatch_core::faults::Faults;
use openpatch_proto::{CommandBody, SUBOP_PRIME};
use serde::Serialize;
use std::fmt::Write;

pub const FAULT_NAMES: [(u16, &str); 8] = [
    (1 << 0, "OCCLUSION"),
    (1 << 1, "ENCODER_DEVIATION"),
    (1 << 2, "RESERVOIR_EMPTY"),
    (1 << 3, "BATTERY_CRITICAL"),
    (1 << 4, "LIMIT_EXCEEDED"),
    (1 << 5, "INTERNAL"),
    (1 << 6, "NO_CALIBRATION"),
    (1 << 7, "WEAR_EXPIRED"),
];

pub fn fault_names(bits: u16) -> Vec<String> {
    FAULT_NAMES.iter().filter(|(b, _)| bits & b != 0).map(|(_, n)| n.to_string()).collect()
}

pub const MU_PER_UL: f64 = 100.0; // 1 ul of water-equivalent test fluid is booked as 0.1 U = 100 mU (U100 convention)

#[derive(Clone, Debug, Serialize)]
pub struct Row {
    pub t_s: f64,
    pub rate_mu_h: u32,
    pub scheduled_mu: u32,
    pub core_delivered_mu: u32,
    pub actual_out_mu: f64,
    pub reservoir_model_mu: u32,
    pub reservoir_actual_mu: f64,
    pub plunger_mm: f64,
    pub pressure_kpa: f64,
    pub angle_core: i64,
    pub angle_true: f64,
    pub current_ma: f64,
    pub battery_mv: f64,
    pub docked: bool,
    pub faults: u16,
    pub flags: u16,
}

pub const CSV_HEADER: &str = "t_s,rate_mu_h,scheduled_mu,core_delivered_mu,actual_out_mu,reservoir_model_mu,reservoir_actual_mu,plunger_mm,pressure_kpa,angle_core,angle_true,current_ma,battery_mv,docked,faults,flags";

impl Row {
    pub fn csv(&self) -> String {
        format!(
            "{:.1},{},{},{},{:.2},{},{:.2},{:.4},{:.2},{},{:.1},{:.1},{:.0},{},{},{}",
            self.t_s,
            self.rate_mu_h,
            self.scheduled_mu,
            self.core_delivered_mu,
            self.actual_out_mu,
            self.reservoir_model_mu,
            self.reservoir_actual_mu,
            self.plunger_mm,
            self.pressure_kpa,
            self.angle_core,
            self.angle_true,
            self.current_ma,
            self.battery_mv,
            self.docked as u8,
            self.faults,
            self.flags
        )
    }
}

#[derive(Clone, Debug, Serialize, Default)]
pub struct BolusResult {
    pub t_s: f64,
    pub units_cmd: f64,
    pub result_code: u8,
    pub accepted: bool,
    pub window_end_s: f64,
    /// Fluid that left the needle in the window (mU), basal included.
    pub actual_window_mu: f64,
    /// What the core booked as delivered in the window (mU), basal included.
    pub core_window_mu: f64,
    /// Basal inside the window (mU), only known when the bolus ran to completion.
    pub basal_est_mu: Option<f64>,
    /// Bolus fluid actually delivered (mU), only for completed boluses.
    pub actual_bolus_mu: Option<f64>,
    pub error_pct: Option<f64>,
    pub completed: bool,
    #[serde(skip)]
    base_out_ul: f64,
    #[serde(skip)]
    base_sched_mu: u32,
    #[serde(skip)]
    base_core_mu: u32,
    #[serde(skip)]
    done: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct HourRow {
    pub hour: u32,
    pub scheduled_mu: u32,
    pub core_delivered_mu: u32,
    pub actual_out_mu: f64,
    pub actual_vs_scheduled_pct: Option<f64>,
}

#[derive(Clone, Debug, Serialize)]
pub struct FaultRecord {
    pub t_s: f64,
    pub bits: u16,
    pub names: Vec<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct Detection {
    pub injection: String,
    pub injected_at_s: f64,
    pub detected_at_s: Option<f64>,
    pub latency_s: Option<f64>,
    pub fault_names: Vec<String>,
    /// Commanded minus actually delivered since the injection, at the first alarm (mU).
    pub undelivered_at_alarm_mu: Option<f64>,
    /// Pod reset (watchdog / power) as the "detection" of a hang or power fault.
    pub detected_by_reset: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct DrawResult {
    pub t_s: f64,
    pub requested_mu: u32,
    pub core_state: u8,
    pub core_drawn_mu: u32,
    pub actual_drawn_mu: f64,
    pub error_mu: f64,
}

#[derive(Clone, Debug, Serialize, Default)]
pub struct LimitVerdict {
    pub hourly_limit_mu: u32,
    pub max_rolling_hour_core_mu: f64,
    pub max_rolling_hour_actual_mu: f64,
    pub per_minute_backstop_mu: u32,
    pub max_minute_actual_mu: f64,
    pub max_bolus_accepted_mu: u32,
    /// Commanded (core) side stayed inside the limits.
    pub core_within_limits: bool,
    /// The fluid that really left the needle stayed inside the limits.
    pub actual_within_limits: bool,
    pub actual_hourly_over_limit_pct: f64,
}

#[derive(Clone, Debug, Serialize, Default)]
pub struct InterlockVerdict {
    pub forward_pulses_issued_undocked: u64,
    pub forward_steps_moved_undocked: u64,
    pub bursts_blocked_forward_undocked: u64,
    pub bursts_blocked_total: u64,
    /// The rotor moved forward while the pod was physically undocked.
    pub violated: bool,
    /// The dock hall was forced high at some point (a violation is then expected by construction).
    pub hall_forced: bool,
    pub last_forward_motion_undocked_s: Option<f64>,
}

/// One `RunSelfTest` of a scenario and what was active afterwards (`1-06-001` style codes).
#[derive(Clone, Debug, Serialize)]
pub struct SelfTestRecord {
    pub t_s: f64,
    pub sub_op: u8,
    pub result: u8,
    pub steps_passed: u16,
    pub steps_failed: u16,
    pub codes: Vec<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ResetRecord {
    pub t_s: f64,
    pub cause: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct BootSummary {
    pub t_s: f64,
    pub cause: String,
    pub suspended: bool,
    pub alarm_flag: bool,
    pub model_minus_actual_before_mu: Option<f64>,
    pub model_minus_actual_after_mu: Option<f64>,
    pub reservoir_restored: Option<(u32, u32)>,
    pub evt_start: u32,
}

#[derive(Clone, Debug, Serialize, Default)]
pub struct Verdict {
    pub scenario: String,
    pub seed: u64,
    pub duration_s: f64,
    pub setup_ok: bool,
    pub setup_note: String,
    pub scheduled_mu: u32,
    pub core_delivered_mu: u32,
    pub actual_out_mu: f64,
    pub actual_vs_core_pct: Option<f64>,
    pub boluses: Vec<BolusResult>,
    pub hourly: Vec<HourRow>,
    pub faults: Vec<FaultRecord>,
    pub detections: Vec<Detection>,
    pub limits: LimitVerdict,
    pub interlock: InterlockVerdict,
    pub resets: Vec<ResetRecord>,
    pub selftests: Vec<SelfTestRecord>,
    pub boots: Vec<BootSummary>,
    pub draws: Vec<DrawResult>,
    pub reservoir_end_model_mu: u32,
    pub reservoir_end_actual_mu: f64,
    pub battery_end_mv: f64,
    pub markers: Vec<(String, f64)>,
    pub notes: Vec<String>,
    pub lost_steps: u64,
    pub peak_pressure_kpa: f64,
    pub peak_current_ma: f64,
    pub forward_steps_during_wdt_window: u64,
    pub wdt_cut_latency_ms: Vec<f64>,
    pub passed: bool,
    pub failures: Vec<String>,
}

pub struct RunOutput {
    pub verdict: Verdict,
    pub rows: Vec<Row>,
    pub dev: Device,
    /// cumulative actual fluid out (ul) at every second since t0
    pub out_by_sec: Vec<f64>,
}

impl RunOutput {
    pub fn csv(&self) -> String {
        let mut s = String::new();
        s.push_str(CSV_HEADER);
        s.push('\n');
        for r in &self.rows {
            let _ = writeln!(s, "{}", r.csv());
        }
        s
    }
}

struct Injection {
    name: String,
    detector: Detector,
    t_s: f64,
    core_mu: u32,
    out_mu: f64,
    detected: Option<(f64, u16, f64)>,
    reset_seen: Option<f64>,
}

pub struct Runner {
    pub dev: Device,
    sc: Scenario,
    t0_us: u64,
    rows: Vec<Row>,
    out_by_sec: Vec<f64>,
    core_by_sec: Vec<f64>,
    boluses: Vec<BolusResult>,
    faults: Vec<FaultRecord>,
    prev_faults: u16,
    selftests: Vec<SelfTestRecord>,
    injections: Vec<Injection>,
    draws: Vec<DrawResult>,
    draw_base: Option<(f64, u32, f64)>, // t_s, requested, drawn_ul base
    notes: Vec<String>,
    hall_forced: bool,
    setup_note: String,
    setup_ok: bool,
    activation_id: u32,
    next_reset_idx: usize,
    profile: Vec<(f64, f64)>,
    max_bolus_mu: u32,
    last_numbers: (u32, u32, u32),
    needle_off_at_us: Option<u64>,
    next_sec: u64,
    sched_off: u32,
    core_off: u32,
    seen_boots: u32,
}

/// (hour, U/h) -> wire segments (30 min slots, 50 mU/h granularity).
pub fn profile_segs(profile: &[(f64, f64)]) -> openpatch_proto::BasalSegs {
    let mut v = openpatch_proto::BasalSegs::new();
    for &(h, r) in profile {
        let slot = ((h * 2.0).round() as i64).clamp(0, 47) as u8;
        let rate = ((r * 1000.0 / 50.0).round() * 50.0) as u16;
        let _ = v.push(openpatch_proto::BasalSeg { start_slot: slot, rate_mu_h: rate });
    }
    v
}

impl Runner {
    pub fn new(sc: Scenario) -> Result<Runner, String> {
        let preset = sc.device.drive_id()?;
        let cfg = DeviceConfig {
            preset,
            capacity_mu: (sc.device.capacity_u * 1000.0).round() as u32,
            strict_prime: sc.device.strict_prime,
            start_tod_ms: (sc.device.start_hour * 3_600_000.0) as u32,
            heartbeat_s: sc.device.heartbeat_s,
        };
        let dev = Device::new(sc.params.clone(), sc.seed, cfg);
        let profile = sc.setup.basal.clone();
        Ok(Runner {
            dev,
            t0_us: 0,
            rows: Vec::new(),
            out_by_sec: Vec::new(),
            core_by_sec: Vec::new(),
            boluses: Vec::new(),
            faults: Vec::new(),
            prev_faults: 0,
            selftests: Vec::new(),
            injections: Vec::new(),
            draws: Vec::new(),
            draw_base: None,
            notes: Vec::new(),
            hall_forced: false,
            setup_note: String::new(),
            setup_ok: true,
            activation_id: 0,
            next_reset_idx: 0,
            profile,
            max_bolus_mu: 0,
            last_numbers: (0, 0, 0),
            needle_off_at_us: None,
            next_sec: 1,
            sched_off: 0,
            core_off: 0,
            seen_boots: 1,
            sc,
        })
    }

    pub fn run(sc: Scenario) -> Result<RunOutput, String> {
        let mut r = Runner::new(sc)?;
        r.run_setup();
        r.run_events();
        Ok(r.finish())
    }

    fn t_s(&self) -> f64 {
        (self.dev.now_us().saturating_sub(self.t0_us)) as f64 / 1e6
    }

    fn run_s(&mut self, s: f64) {
        let t = self.dev.now_us() + (s * 1e6) as u64;
        self.dev.run_to(t);
    }

    // ---- setup ----------------------------------------------------------------------------------
    pub fn run_setup(&mut self) {
        self.run_s(2.0); // boot settle
        if self.sc.setup.standard {
            if let Err(e) = self.standard_setup() {
                self.setup_ok = false;
                self.setup_note = e;
            }
        }
        self.t0_us = self.dev.now_us();
        // fault baseline: whatever latched during setup is a setup problem, not part of the run
        self.prev_faults = self.dev.pump.as_ref().map_or(0, |p| p.supervisor().faults().bits());
        self.next_reset_idx = self.dev.world.borrow().stats.resets.len();
        self.sample_second(0);
    }

    fn standard_setup(&mut self) -> Result<(), String> {
        let fill_mu = (self.sc.setup.fill_u * 1000.0).round() as u32;
        // 1. undock, draw the water in
        self.dev.world.borrow_mut().docked_phys = false;
        self.run_s(2.0);
        let r = self.dev.cmd(CommandBody::FillDraw { amount_mu: fill_mu });
        if r != 0 {
            return Err(format!("FillDraw refused: {r}"));
        }
        self.dev.world.borrow_mut().plant.fill_needle = true;
        for _ in 0..900 {
            self.run_s(1.0);
            let s = self.dev.status().map(|s| s.draw_state).unwrap_or(0);
            if s != openpatch_proto::draw::DRAWING {
                break;
            }
        }
        self.run_s(3.0); // the user pulls the needle a moment after the beep
        self.dev.world.borrow_mut().plant.fill_needle = false;
        let st = self.dev.status().ok_or("no status after draw")?;
        if st.draw_state != openpatch_proto::draw::DONE {
            return Err(format!("draw ended in state {} ({} mU of {})", st.draw_state, st.draw_done_mu, fill_mu));
        }
        // 2. dock, pair, activate
        self.dev.world.borrow_mut().docked_phys = true;
        self.run_s(2.0);
        let r = self.dev.cmd(CommandBody::SetPairing { pair_id: PAIR_ID, role: 1 });
        if r != 0 {
            return Err(format!("SetPairing refused: {r}"));
        }
        self.activation_id += 1;
        let r = self.dev.cmd(CommandBody::Activate {
            pair_id: PAIR_ID,
            activation_id: self.activation_id,
            schedule: profile_segs(&self.profile),
            temp: None,
        });
        if r != 0 {
            return Err(format!("Activate refused: {r}"));
        }
        // 3. prime the connector
        let steps = self.dev.pump().pulse_cal().mu_to_pulses(openpatch_core::MilliUnits((self.sc.setup.prime_u * 1000.0) as u32)).0;
        if steps > 0 {
            // The prime after a draw first recovers the lost motion of the mechanics (0.33 mm = 2.5 U), which counts against the
            // 1.7 U per minute backstop: the pod answers `Hourly` (16) after the part that fits and the app repeats the prime
            // a minute later, exactly like a phone.
            let mut r = 255;
            for _ in 0..6 {
                r = self.dev.cmd(CommandBody::FillPrime { sub_op: SUBOP_PRIME, fill_mu: 0, prime_steps: steps as u16 });
                if r != 16 {
                    break;
                }
                self.run_s(62.0);
            }
            if r != 0 {
                return Err(format!("Prime refused: {r}"));
            }
            self.run_s(62.0);
        }
        // 4. resume
        if self.sc.setup.resume {
            let r = self.dev.cmd(CommandBody::Resume);
            if r != 0 {
                return Err(format!("Resume refused: {r}"));
            }
        }
        self.run_s(1.0);
        Ok(())
    }

    // ---- main loop -------------------------------------------------------------------------------
    /// Advance the simulation to `t_s` seconds after setup (sampling every second on the way).
    pub fn advance_to_s(&mut self, t_s: f64) {
        let target = self.t0_us + (t_s * 1e6) as u64;
        loop {
            let sec_t = self.t0_us + self.next_sec * 1_000_000;
            if sec_t > target {
                break;
            }
            self.dev.run_to(sec_t);
            let s = self.next_sec;
            self.next_sec += 1;
            self.sample_second(s);
        }
        self.dev.run_to(target);
    }

    fn run_events(&mut self) {
        let mut evs = self.sc.events.clone();
        evs.sort_by(|a, b| a.at_s.partial_cmp(&b.at_s).unwrap());
        for e in evs {
            if e.at_s > self.sc.duration_s {
                break;
            }
            self.advance_to_s(e.at_s);
            self.exec(&e.action);
        }
        self.advance_to_s(self.sc.duration_s);
    }

    /// Seconds since the end of setup.
    pub fn now_s(&self) -> f64 {
        self.t_s()
    }

    fn core_numbers(&self) -> (u32, u32, u32) {
        match self.dev.pump.as_ref() {
            Some(p) => {
                let r = p.engine().report();
                (r.scheduled.0 + self.sched_off, r.delivered.0 + self.core_off, p.reservoir().remaining().0)
            }
            None => (self.last_numbers.0, self.last_numbers.1, self.last_numbers.2),
        }
    }

    fn sample_second(&mut self, sec: u64) {
        if self.dev.boots != self.seen_boots {
            // a new pump instance counts from zero: carry the totals over the reset
            self.sched_off = self.last_numbers.0;
            self.core_off = self.last_numbers.1;
            self.seen_boots = self.dev.boots;
        }
        let (sched, core, res) = self.core_numbers();
        self.last_numbers = (sched, core, res);
        let t_s = self.t_s();
        let (out_ul, plunger, pressure, angle_true, current, battery, docked, liquid) = {
            let w = self.dev.world.borrow();
            (
                w.plant.out_ul,
                w.plant.plunger_x,
                w.plant.pressure_kpa,
                w.true_angle_counts(),
                w.stats.peak_current_ma,
                w.battery_idle_mv(),
                w.docked_phys,
                w.plant.liquid_ul,
            )
        };
        self.out_by_sec.push(out_ul);
        self.core_by_sec.push(core as f64);

        // faults
        if let Some(p) = self.dev.pump.as_ref() {
            let f = p.supervisor().faults().bits();
            let new = f & !self.prev_faults;
            if new != 0 {
                self.faults.push(FaultRecord { t_s, bits: new, names: fault_names(new) });
                let actual_mu = out_ul * MU_PER_UL;
                for inj in self.injections.iter_mut().filter(|i| i.detected.is_none() && matches!(i.detector, Detector::Fault(m) if m & new != 0)) {
                    let und = (core as f64 - inj.core_mu as f64) - (actual_mu - inj.out_mu);
                    inj.detected = Some((t_s, new, und));
                }
            }
            self.prev_faults = f;
        } else {
            self.prev_faults = 0;
        }
        // resets as detections of firmware / power faults
        let nres = self.dev.world.borrow().stats.resets.len();
        while self.next_reset_idx < nres {
            let t_reset = self.dev.world.borrow().stats.resets[self.next_reset_idx].0;
            let rs = (t_reset.saturating_sub(self.t0_us)) as f64 / 1e6;
            for inj in self.injections.iter_mut().filter(|i| i.reset_seen.is_none() && i.detector == Detector::Reset && i.t_s <= rs) {
                inj.reset_seen = Some(rs);
            }
            self.next_reset_idx += 1;
        }
        // draw completion
        if let (Some((t0, req, base)), Some(p)) = (self.draw_base, self.dev.pump.as_ref()) {
            if !p.draw_running() {
                let drawn_now = self.dev.world.borrow().plant.drawn_ul;
                let actual = (drawn_now - base) * MU_PER_UL;
                let core_drawn = p.draw_drawn().0;
                self.draws.push(DrawResult {
                    t_s: t0,
                    requested_mu: req,
                    core_state: p.draw_state(),
                    core_drawn_mu: core_drawn,
                    actual_drawn_mu: actual,
                    error_mu: actual - core_drawn as f64,
                });
                self.draw_base = None;
                self.needle_off_at_us = Some(self.dev.now_us() + 3_000_000);
            }
        }
        if let Some(t) = self.needle_off_at_us {
            if self.dev.now_us() >= t {
                self.dev.world.borrow_mut().plant.fill_needle = false;
                self.needle_off_at_us = None;
            }
        }
        // bolus windows
        let now_s = t_s;
        let out_now = out_ul;
        let completed_now = self.dev.pump.as_ref().map(|p| !p.engine().bolus_active());
        for b in self.boluses.iter_mut().filter(|b| b.accepted && !b.done) {
            if now_s + 1e-9 >= b.window_end_s {
                let bolus_mu = (b.units_cmd * 1000.0).round();
                b.actual_window_mu = (out_now - b.base_out_ul) * MU_PER_UL;
                b.core_window_mu = core as f64 - b.base_core_mu as f64;
                let sched_delta = sched as f64 - b.base_sched_mu as f64;
                b.completed = completed_now == Some(true) && (sched_delta + 1.0 >= bolus_mu);
                if b.completed {
                    let basal = (sched_delta - bolus_mu).max(0.0);
                    b.basal_est_mu = Some(basal);
                    let ab = b.actual_window_mu - basal;
                    b.actual_bolus_mu = Some(ab);
                    b.error_pct = Some((ab - bolus_mu) / bolus_mu * 100.0);
                }
                b.done = true;
            }
        }
        // time series
        let every = self.sc.log_interval_s.max(1.0) as u64;
        if sec % every == 0 || sec == 0 {
            let (rate, flags, faults, angle_core) = match self.dev.pump.as_mut() {
                Some(p) => {
                    let s = p.get_status();
                    (s.current_rate_mu_h as u32, s.flags, s.faults, p.supervisor().last_angle().0)
                }
                None => (0, 0, 0xFFFF, 0),
            };
            self.rows.push(Row {
                t_s,
                rate_mu_h: rate,
                scheduled_mu: sched,
                core_delivered_mu: core,
                actual_out_mu: out_ul * MU_PER_UL,
                reservoir_model_mu: res,
                reservoir_actual_mu: liquid * MU_PER_UL,
                plunger_mm: plunger,
                pressure_kpa: pressure,
                angle_core,
                angle_true,
                current_ma: current,
                battery_mv: battery,
                docked,
                faults,
                flags,
            });
            self.dev.world.borrow_mut().stats.peak_current_ma = 0.0;
        }
    }

    // ---- actions ---------------------------------------------------------------------------------
    fn inject(&mut self, name: &str, detector: Detector) {
        let (_, core, _) = self.core_numbers();
        let out = self.dev.world.borrow().plant.out_ul * MU_PER_UL;
        self.injections.push(Injection { name: name.to_string(), detector, t_s: self.t_s(), core_mu: core, out_mu: out, detected: None, reset_seen: None });
        self.dev.world.borrow_mut().mark(name);
    }

    pub fn exec(&mut self, a: &Action) {
        if let Some(d) = a.detector() {
            self.inject(&format!("{a:?}"), d);
        }
        let t_s = self.t_s();
        match a {
            Action::Bolus { units } => {
                let mu = (units * 1000.0).round() as u32;
                let code = self.dev.cmd(CommandBody::Bolus { amount_mu: mu });
                let (sched, core, _) = self.core_numbers();
                let out_ul = self.dev.world.borrow().plant.out_ul;
                let dur = units / 1.5 * 60.0;
                if code == 0 {
                    self.max_bolus_mu = self.max_bolus_mu.max(mu);
                }
                self.boluses.push(BolusResult {
                    t_s,
                    units_cmd: *units,
                    result_code: code,
                    accepted: code == 0,
                    window_end_s: t_s + dur + self.sc.settle_s,
                    base_out_ul: out_ul,
                    base_sched_mu: sched,
                    base_core_mu: core,
                    ..Default::default()
                });
            }
            Action::TempBasal { u_per_h, minutes } => {
                let r = self.dev.cmd(CommandBody::SetTempBasal { rate_mu_h: (u_per_h * 1000.0).round() as u16, duration_min: *minutes as u16 });
                self.note_result("temp_basal", r);
            }
            Action::CancelTemp => {
                let r = self.dev.cmd(CommandBody::CancelTempBasal);
                self.note_result("cancel_temp", r);
            }
            Action::CancelBolus => {
                let r = self.dev.cmd(CommandBody::CancelBolus);
                self.note_result("cancel_bolus", r);
            }
            Action::Suspend => {
                let r = self.dev.cmd(CommandBody::Suspend);
                self.note_result("suspend", r);
            }
            Action::Resume => {
                let r = self.dev.cmd(CommandBody::Resume);
                self.note_result("resume", r);
            }
            Action::SetBasal { profile } => {
                self.profile = profile.clone();
                let r = self.dev.cmd(CommandBody::SetBasalSchedule(profile_segs(profile)));
                self.note_result("set_basal", r);
            }
            Action::Prime { units } => {
                let steps = self.dev.pump.as_ref().map_or(0, |p| p.pulse_cal().mu_to_pulses(openpatch_core::MilliUnits((units * 1000.0) as u32)).0);
                let r = self.dev.cmd(CommandBody::FillPrime { sub_op: SUBOP_PRIME, fill_mu: 0, prime_steps: steps as u16 });
                self.note_result("prime", r);
            }
            Action::Draw { units } => {
                let mu = (units * 1000.0).round() as u32;
                let r = self.dev.cmd(CommandBody::FillDraw { amount_mu: mu });
                self.note_result("draw", r);
                if r == 0 {
                    let mut w = self.dev.world.borrow_mut();
                    w.plant.fill_needle = true;
                    self.draw_base = Some((t_s, mu, w.plant.drawn_ul));
                }
            }
            Action::Activate => {
                let _ = self.dev.cmd(CommandBody::SetPairing { pair_id: PAIR_ID, role: 1 });
                self.activation_id += 1;
                let r = self.dev.cmd(CommandBody::Activate {
                    pair_id: PAIR_ID,
                    activation_id: self.activation_id,
                    schedule: profile_segs(&self.profile),
                    temp: None,
                });
                self.note_result("activate", r);
            }
            Action::Release => {
                let r = self.dev.cmd(CommandBody::Release { pair_id: PAIR_ID });
                self.note_result("release", r);
            }
            Action::Acknowledge { mask } => {
                let r = self.dev.cmd(CommandBody::Acknowledge { fault_mask: mask.unwrap_or(0xFFFF) });
                self.note_result("acknowledge", r);
                self.prev_faults = self.dev.pump.as_ref().map_or(0, |p| p.supervisor().faults().bits());
            }
            Action::PhoneConnected { on } => self.dev.phone_connected = *on,
            Action::Dock { on } => self.dev.world.borrow_mut().docked_phys = *on,
            Action::Charger { on } => self.dev.world.borrow_mut().charger = *on,
            Action::Occlude { factor } => self.dev.world.borrow_mut().plant.set_occlusion_factor(factor.unwrap_or(1e6)),
            Action::ClearOcclusion => self.dev.world.borrow_mut().plant.set_occlusion_factor(1.0),
            Action::Bubble { ul } => self.dev.world.borrow_mut().plant.bubble_ul = *ul,
            Action::Magnet { strength } => self.dev.world.borrow_mut().magnet_strength = *strength,
            Action::AngleNack { on } => self.dev.world.borrow_mut().angle_nack = *on,
            Action::PhaseOpen { on } => self.dev.world.borrow_mut().plant.phase_open = *on,
            Action::HallStuckDocked { on } => {
                self.dev.world.borrow_mut().hall_stuck_docked = *on;
                self.hall_forced |= *on;
            }
            Action::Hang { runaway_hz } => {
                let mut w = self.dev.world.borrow_mut();
                w.hung = true;
                if let Some(hz) = runaway_hz {
                    w.runaway_hz = Some(*hz);
                    w.mcu_en = true;
                    w.latch_q = true;
                }
            }
            Action::KickStuck { on } => self.dev.world.borrow_mut().kick_stuck = *on,
            Action::Brownout { dip_mv, duration_ms } => {
                let mut w = self.dev.world.borrow_mut();
                w.battery.dip_mv = *dip_mv;
                w.brownout_until_us = Some(w.t_us + (duration_ms * 1000.0) as u64);
            }
            Action::BatteryOcv { mv } => self.dev.world.borrow_mut().battery.ocv_override = *mv,
            Action::PowerLoss { duration_ms } => {
                let mut w = self.dev.world.borrow_mut();
                w.cut_power(crate::world::ResetCause::PowerLoss);
                w.power_restore_at_us = Some(w.t_us + (duration_ms * 1000.0) as u64);
            }
            Action::FlashPowerLoss { frac, off_ms } => self.dev.world.borrow_mut().flash_cut_arm = Some((*frac, *off_ms)),
            Action::ForceSteps { n } => {
                let _ = self.dev.force_forward_steps(*n);
            }
            Action::BoardFault { fault, on } => {
                let mut w = self.dev.world.borrow_mut();
                if fault == "r97_fitted" {
                    w.board.r97_fitted = *on;
                } else if let Err(e) = w.board.f.set(fault, *on) {
                    drop(w);
                    self.notes.push(e);
                }
            }
            Action::SelfTest { sub_op } => {
                let rsp = self.dev.send(CommandBody::RunSelfTest { sub_op: *sub_op });
                let result = rsp.as_ref().map_or(255, |r| r.result);
                let st = rsp.as_ref().and_then(|r| r.selftest).unwrap_or_default();
                self.note_result("self_test", result);
                let codes = self.dev.pump.as_ref().map_or(vec![], |p| {
                    p.supervisor().diag().active().iter().map(|a| format!("{:X}-{:02X}-{:03X}", a.code.layer(), a.code.component(), a.code.fault())).collect()
                });
                self.selftests.push(SelfTestRecord { t_s, sub_op: *sub_op, result, steps_passed: st.steps_passed, steps_failed: st.steps_failed, codes });
            }
            Action::Mark { name } => self.dev.world.borrow_mut().mark(name),
        }
    }

    fn note_result(&mut self, what: &str, code: u8) {
        if code != 0 {
            let t = self.t_s();
            self.notes.push(format!("t={t:.1}s: {what} -> result {code}"));
        }
    }

    // ---- verdict ---------------------------------------------------------------------------------
    pub fn finish(self) -> RunOutput {
        let verdict = self.verdict();
        RunOutput { verdict, rows: self.rows, dev: self.dev, out_by_sec: self.out_by_sec }
    }

    /// The verdict as of now (can be taken repeatedly while a run is in progress).
    pub fn verdict(&self) -> Verdict {
        let t0 = self.t0_us;
        let (sched, core, res) = self.core_numbers();
        let w = self.dev.world.borrow();
        let out_mu = w.plant.out_ul * MU_PER_UL;
        let mut v = Verdict {
            scenario: self.sc.name.clone(),
            seed: self.sc.seed,
            duration_s: self.sc.duration_s,
            setup_ok: self.setup_ok,
            setup_note: self.setup_note.clone(),
            scheduled_mu: sched,
            core_delivered_mu: core,
            actual_out_mu: out_mu,
            actual_vs_core_pct: if core > 0 { Some((out_mu / core as f64 - 1.0) * 100.0) } else { None },
            boluses: self.boluses.clone(),
            faults: self.faults.clone(),
            selftests: self.selftests.clone(),
            reservoir_end_model_mu: res,
            reservoir_end_actual_mu: w.plant.liquid_ul * MU_PER_UL,
            battery_end_mv: w.battery_idle_mv(),
            markers: w.markers.iter().map(|m| (m.name.clone(), (m.t_us.saturating_sub(t0)) as f64 / 1e6)).collect(),
            notes: self.notes.clone(),
            lost_steps: w.plant.lost_steps,
            peak_pressure_kpa: w.plant.peak_pressure_kpa,
            peak_current_ma: w.stats.peak_current_ma,
            draws: self.draws.clone(),
            forward_steps_during_wdt_window: w.stats.forward_steps_during_wdt_window,
            ..Default::default()
        };
        // hourly table
        let hours = (self.sc.duration_s / 3600.0).floor() as u32;
        let every = self.sc.log_interval_s.max(1.0);
        let mut prev: Option<&Row> = self.rows.iter().find(|r| r.t_s == 0.0);
        for h in 1..=hours {
            let tt = h as f64 * 3600.0;
            if let Some(r) = self.rows.iter().find(|r| (r.t_s - tt).abs() < every / 2.0 + 0.01) {
                if let Some(p) = prev {
                    let sch = r.scheduled_mu.saturating_sub(p.scheduled_mu);
                    let cor = r.core_delivered_mu.saturating_sub(p.core_delivered_mu);
                    let act = r.actual_out_mu - p.actual_out_mu;
                    v.hourly.push(HourRow {
                        hour: h,
                        scheduled_mu: sch,
                        core_delivered_mu: cor,
                        actual_out_mu: act,
                        actual_vs_scheduled_pct: if sch > 0 { Some((act / sch as f64 - 1.0) * 100.0) } else { None },
                    });
                }
                prev = Some(r);
            }
        }
        // detections
        for inj in &self.injections {
            let (det, lat, und, names) = match inj.detected {
                Some((t, bits, und)) => (Some(t), Some(t - inj.t_s), Some(und), fault_names(bits)),
                None => (None, None, None, Vec::new()),
            };
            let (det, lat, by_reset) = match (det, inj.reset_seen) {
                (None, Some(r)) => (Some(r), Some(r - inj.t_s), true),
                _ => (det, lat, false),
            };
            v.detections.push(Detection {
                injection: inj.name.clone(),
                injected_at_s: inj.t_s,
                detected_at_s: det,
                latency_s: lat,
                fault_names: names,
                undelivered_at_alarm_mu: und,
                detected_by_reset: by_reset,
            });
        }
        // limits
        let lim = &mut v.limits;
        lim.hourly_limit_mu = openpatch_core::limits::MAX_HOURLY.0;
        lim.per_minute_backstop_mu = openpatch_core::limits::MAX_PER_MIN.0;
        lim.max_bolus_accepted_mu = self.max_bolus_mu;
        let roll = |series: &[f64], win: usize, scale: f64| -> f64 {
            let mut best: f64 = 0.0;
            for i in 1..series.len() {
                best = best.max((series[i] - series[i.saturating_sub(win)]) * scale);
            }
            best
        };
        lim.max_rolling_hour_actual_mu = roll(&self.out_by_sec, 3600, MU_PER_UL);
        lim.max_rolling_hour_core_mu = roll(&self.core_by_sec, 3600, 1.0);
        lim.max_minute_actual_mu = roll(&self.out_by_sec, 60, MU_PER_UL);
        lim.core_within_limits = lim.max_rolling_hour_core_mu <= lim.hourly_limit_mu as f64 && lim.max_bolus_accepted_mu <= 10_000;
        lim.actual_within_limits = lim.max_rolling_hour_actual_mu <= lim.hourly_limit_mu as f64 && lim.max_minute_actual_mu <= lim.per_minute_backstop_mu as f64;
        lim.actual_hourly_over_limit_pct = ((lim.max_rolling_hour_actual_mu / lim.hourly_limit_mu as f64) - 1.0) * 100.0;
        // interlock
        let s = &w.stats;
        v.interlock = InterlockVerdict {
            forward_pulses_issued_undocked: s.forward_pulses_issued_undocked,
            forward_steps_moved_undocked: s.forward_steps_moved_undocked,
            bursts_blocked_forward_undocked: s.bursts_blocked_forward_undocked,
            bursts_blocked_total: s.bursts_blocked_by_interlock,
            violated: s.forward_steps_moved_undocked > 0,
            hall_forced: self.hall_forced,
            last_forward_motion_undocked_s: s.last_forward_motion_undocked_us.map(|t| (t.saturating_sub(t0)) as f64 / 1e6),
        };
        v.resets = s
            .resets
            .iter()
            .map(|(t, c)| ResetRecord { t_s: (t.saturating_sub(t0)) as f64 / 1e6, cause: format!("{c:?}") })
            .collect();
        v.wdt_cut_latency_ms = s.wdt_cuts.iter().map(|(a, b)| (b - a) as f64 / 1000.0).collect();
        drop(w);
        v.boots = self
            .dev
            .boot_reports
            .iter()
            .map(|b| BootSummary {
                t_s: (b.t_us.saturating_sub(t0)) as f64 / 1e6,
                cause: b.cause.clone().unwrap_or_default(),
                suspended: b.suspended,
                alarm_flag: b.alarm_flag,
                model_minus_actual_before_mu: b.model_minus_actual_mu_before,
                model_minus_actual_after_mu: b.model_minus_actual_mu_after,
                reservoir_restored: b.reservoir_restored,
                evt_start: b.evt_start,
            })
            .collect();
        v.passed = v.setup_ok;
        if !v.setup_ok {
            v.failures.push(format!("setup failed: {}", v.setup_note));
        }
        if v.interlock.violated && !v.interlock.hall_forced {
            v.passed = false;
            v.failures.push("forward motion while undocked".into());
        }
        if !v.limits.core_within_limits {
            v.passed = false;
            v.failures.push("core exceeded a safety limit".into());
        }
        let _ = Faults::NONE;
        v
    }
}
