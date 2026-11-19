//! The physical world around the MCU: plant, sensors, supply, watchdog, interlock, flash, clock.
//! [`SimHal`] is the core's `Hal` implementation on top of it.
//!
//! Time is a monotonic microsecond counter owned by the world; the core only ever sees
//! `time_ms()`. Nothing here uses wall clock or OS randomness: runs are reproducible from the seed.

use crate::electrical::{sample_angle, Battery, Tracker};
use crate::flash::Flash;
use crate::params::Params;
use crate::plant::Plant;
use crate::rng::Rng;
use openpatch_core::{AngleCounts, Buzzer, Hal, Millis, Pulses};
use std::cell::RefCell;
use std::rc::Rc;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ResetCause {
    /// TPL5010 timed out (RSTn pulse, latch cleared by hardware).
    Watchdog,
    /// Supply fell below the PCM cut-off or an injected power loss: everything volatile is lost.
    PowerLoss,
}

#[derive(Clone, Debug, Default)]
pub struct Stats {
    /// Pulses the firmware issued in forward bursts.
    pub forward_pulses_issued: u64,
    /// Forward steps the rotor really followed.
    pub forward_steps_moved: u64,
    /// ... of which while the pod was PHYSICALLY undocked.
    pub forward_steps_moved_undocked: u64,
    /// Forward pulses issued while physically undocked (whether or not VMOT was up).
    pub forward_pulses_issued_undocked: u64,
    /// Number of times the interlock refused a burst (VMOT not available).
    pub bursts_blocked_by_interlock: u64,
    pub bursts_blocked_forward_undocked: u64,
    /// Last time a forward step moved the rotor / moved it while undocked.
    pub last_forward_motion_us: Option<u64>,
    pub last_forward_motion_undocked_us: Option<u64>,
    pub resets: Vec<(u64, ResetCause)>,
    /// (time of the last DONE, time TPL5010 cut the supply)
    pub wdt_cuts: Vec<(u64, u64)>,
    /// forward steps the rotor made after the last valid DONE (runaway bound)
    pub forward_steps_during_wdt_window: u64,
    pub peak_current_ma: f64,
}

/// A named physical event for latency measurements (e.g. "occlusion_start").
#[derive(Clone, Debug)]
pub struct Marker {
    pub t_us: u64,
    pub name: String,
}

pub struct World {
    pub params: Params,
    pub plant: Plant,
    pub rng: Rng,
    pub t_us: u64,
    // ---- physical inputs (scenario) ----
    pub docked_phys: bool,
    pub hall_stuck_docked: bool,
    pub charger: bool,
    /// The interlock board's analog / fault model (`board.rs`).
    pub board: crate::board::BoardModel,
    pub magnet_strength: f64,
    pub angle_nack: bool,
    pub battery: Battery,
    // ---- interlock / watchdog ----
    pub mcu_en: bool,
    pub latch_q: bool,
    pub dir_reverse: bool,
    pub kick_stuck: bool,
    pub hung: bool,
    pub runaway_hz: Option<f64>,
    runaway_carry: f64,
    wdt_last_done_us: u64,
    wdt_period_us: u64,
    steps_since_done0: u64,
    // ---- power ----
    pub power_on: bool,
    pub power_cut_at_us: Option<u64>,
    pub power_restore_at_us: Option<u64>,
    pub boot_at_us: Option<u64>,
    pub reset_pending: Option<ResetCause>,
    /// Why the MCU started this boot, as `Hal::reset_cause` reports it (RESETREAS, retained across the reset).
    pub boot_cause: openpatch_core::hal::ResetCause,
    pub flash_cut_arm: Option<(f64, f64)>,
    pub brownout_until_us: Option<u64>,
    // ---- sensor ----
    tracker: Tracker,
    last_poll_us: u64,
    last_burst_peak_ma: f64,
    // ---- peripherals / records ----
    pub flash: Flash,
    pub buzzer: Buzzer,
    pub buzzer_log: Vec<(u64, Buzzer)>,
    pub stats: Stats,
    pub markers: Vec<Marker>,
}

impl World {
    pub fn new(params: Params, seed: u64) -> Self {
        let plant = Plant::new(params.clone());
        let battery = Battery::new(&params.electrical);
        let flash = Flash::new(params.flash.write_ms, params.flash.tear_destroys_previous_prob);
        let wdt_period_us = (params.electrical.wdt_period_ms * 1000.0) as u64;
        World {
            plant,
            rng: Rng::new(seed),
            t_us: 0,
            docked_phys: true,
            hall_stuck_docked: false,
            charger: false,
            board: Default::default(),
            magnet_strength: 1.0,
            angle_nack: false,
            battery,
            mcu_en: false,
            latch_q: false,
            dir_reverse: false,
            kick_stuck: false,
            hung: false,
            runaway_hz: None,
            runaway_carry: 0.0,
            wdt_last_done_us: 0,
            wdt_period_us,
            steps_since_done0: 0,
            power_on: true,
            power_cut_at_us: None,
            power_restore_at_us: None,
            boot_at_us: None,
            reset_pending: None,
            boot_cause: openpatch_core::hal::ResetCause::PowerOn,
            flash_cut_arm: None,
            brownout_until_us: None,
            tracker: Tracker::default(),
            last_poll_us: 0,
            last_burst_peak_ma: 0.0,
            flash,
            buzzer: Buzzer::Off,
            buzzer_log: Vec::new(),
            stats: Stats::default(),
            markers: Vec::new(),
            params,
        }
    }

    pub fn now_s(&self) -> f64 {
        self.t_us as f64 / 1e6
    }

    pub fn mark(&mut self, name: &str) {
        self.markers.push(Marker { t_us: self.t_us, name: name.to_string() });
    }

    pub fn marker(&self, name: &str) -> Option<u64> {
        self.markers.iter().find(|m| m.name == name).map(|m| m.t_us)
    }

    // ---- inputs as the board sees them ---------------------------------------------------------
    /// DOCKED as the hall switch reports it (also what the interlock gate sees).
    pub fn docked_hw(&self) -> bool {
        (self.docked_phys || self.hall_stuck_docked) && !self.board.f.ffc_unplugged
    }

    /// `VMOT on = MCU_EN AND latch AND OC_OK AND (DOCKED XOR DIR_REVERSE)`, through the P-FET (`board.rs`, faults included).
    pub fn vmot_on(&self) -> bool {
        self.switch_on()
    }

    fn vmot_v(&self) -> f64 {
        self.battery.terminal_mv(self.params.motor.i_free_ma) / 1000.0
    }

    pub fn battery_idle_mv(&self) -> f64 {
        self.battery.terminal_mv(self.params.electrical.i_idle_ua / 1000.0)
    }

    // ---- sensors ---------------------------------------------------------------------------------
    fn poll_angle(&mut self) {
        let raw = sample_angle(&self.params.sensor, self.plant.theta_s, self.magnet_strength, &mut self.rng);
        self.tracker.update(raw);
        self.last_poll_us = self.t_us;
    }

    pub fn angle_read(&mut self) -> Option<i64> {
        if !self.power_on || self.angle_nack || self.board.f.ffc_unplugged {
            return None;
        }
        self.poll_angle();
        Some(self.tracker.cum)
    }

    /// True angle of the screw in 4096-count units (no noise), for verdicts.
    pub fn true_angle_counts(&self) -> f64 {
        self.plant.theta_s / (2.0 * std::f64::consts::PI) * 4096.0
    }

    // ---- power / watchdog ------------------------------------------------------------------------
    pub fn cut_power(&mut self, cause: ResetCause) {
        if !self.power_on {
            return;
        }
        self.power_on = false;
        self.mcu_en = false;
        self.latch_q = false;
        self.dir_reverse = false;
        self.runaway_hz = None;
        self.hung = false;
        self.board.oc_ok = true;
        self.board.stby = false;
        self.flash.power_cut(&mut self.rng);
        self.power_cut_at_us = None;
        self.reset_pending = Some(cause);
        self.stats.resets.push((self.t_us, cause));
        self.mark("power_loss");
    }

    fn fire_watchdog(&mut self) {
        self.stats.wdt_cuts.push((self.wdt_last_done_us, self.t_us));
        self.stats.forward_steps_during_wdt_window = self.plant.forward_moved_steps - self.steps_since_done0;
        self.latch_q = false;
        self.mcu_en = false;
        self.dir_reverse = false;
        self.board.stby = false;
        self.runaway_hz = None;
        self.hung = false; // a software hang is cleared by the reset; a stuck DONE line is not
        self.reset_pending = Some(ResetCause::Watchdog);
        self.stats.resets.push((self.t_us, ResetCause::Watchdog));
        self.wdt_last_done_us = self.t_us; // TPL5010 restarts its period
        self.mark("watchdog_reset");
    }

    /// Everything that happens "in the background" while `dt_us` passes with `motor_ma` drawn.
    fn background(&mut self, dt_us: u64, motor_ma: f64) {
        let dt_s = dt_us as f64 / 1e6;
        if let Some(u) = self.brownout_until_us {
            if self.t_us >= u {
                self.battery.dip_mv = 0.0;
                self.brownout_until_us = None;
            }
        }
        if self.power_on {
            self.battery.drain(self.params.electrical.i_idle_ua / 1000.0 + motor_ma, dt_s);
            // flash writer
            if let Some(start) = self.flash.advance(self.t_us) {
                if let Some((frac, off_ms)) = self.flash_cut_arm.take() {
                    let cut = start + (frac * self.params.flash.write_ms * 1000.0) as u64;
                    self.power_cut_at_us = Some(cut);
                    self.power_restore_at_us = Some(cut + (off_ms * 1000.0) as u64);
                }
            }
            if let Some(tc) = self.power_cut_at_us {
                if self.t_us >= tc {
                    self.cut_power(ResetCause::PowerLoss);
                }
            }
            if self.power_on && self.battery.terminal_mv(motor_ma + self.params.electrical.i_idle_ua / 1000.0) < self.params.electrical.power_off_mv {
                self.cut_power(ResetCause::PowerLoss);
            }
            if self.power_on && self.t_us.saturating_sub(self.wdt_last_done_us) > self.wdt_period_us {
                self.fire_watchdog();
            }
        } else {
            // dead: wait for the supply to recover
            let ok = self.battery.terminal_mv(0.1) >= self.params.electrical.power_on_mv;
            let due = self.power_restore_at_us.map_or(true, |t| self.t_us >= t);
            if ok && due && self.boot_at_us.is_none() {
                self.power_on = true;
                self.power_restore_at_us = None;
                self.wdt_last_done_us = self.t_us;
                self.boot_at_us = Some(self.t_us + (self.params.electrical.boot_ms * 1000.0) as u64);
                self.mark("power_restored");
            }
        }
    }

    // ---- time ------------------------------------------------------------------------------------
    /// Let `target_us` arrive with the MCU idle (or hung): plant relaxes, runaway stepping if armed.
    pub fn advance_to(&mut self, target_us: u64) {
        while self.t_us < target_us {
            self.background(0, 0.0); // conditions that hold NOW (supply dip, due flash cut, watchdog)
            if self.t_us >= target_us {
                break;
            }
            let runaway = self.runaway_hz.filter(|_| self.vmot_on());
            let mut quantum: u64 = if runaway.is_some() { 5_000 } else { 250_000 };
            for d in [self.power_cut_at_us, self.brownout_until_us, self.power_restore_at_us, self.boot_at_us, self.flash.in_flight_window().map(|w| w.1)].into_iter().flatten() {
                if d > self.t_us {
                    quantum = quantum.min(d - self.t_us);
                }
            }
            if self.power_on && self.wdt_last_done_us + self.wdt_period_us >= self.t_us {
                quantum = quantum.min(self.wdt_last_done_us + self.wdt_period_us + 1 - self.t_us);
            }
            let dt = quantum.max(1).min(target_us - self.t_us);
            self.t_us += dt;
            self.board_step();
            let mut motor_ma = 0.0;
            if let Some(hz) = runaway {
                self.runaway_carry += hz * dt as f64 / 1e6;
                let n = self.runaway_carry.floor();
                self.runaway_carry -= n;
                for _ in 0..n as u64 {
                    let vmot = self.vmot_v();
                    let was_undocked = !self.docked_phys;
                    let r = self.plant.step(1, hz, vmot, &mut self.rng);
                    motor_ma = r.current_ma;
                    if r.moved {
                        self.note_forward_motion(was_undocked);
                    }
                    self.stats.forward_pulses_issued_undocked += was_undocked as u64;
                }
            }
            self.plant.relax(dt as f64 / 1e6);
            self.background(dt, motor_ma);
        }
    }

    fn note_forward_motion(&mut self, undocked: bool) {
        self.stats.forward_steps_moved += 1;
        self.stats.last_forward_motion_us = Some(self.t_us);
        if undocked {
            self.stats.forward_steps_moved_undocked += 1;
            self.stats.last_forward_motion_undocked_us = Some(self.t_us);
        }
    }

    /// One blocking burst of `n` pulses (a HAL `motor_step` / `motor_step_reverse`). Returns the
    /// pulses produced; 0 when the interlock does not provide VMOT (the real HAL verifies it).
    pub fn burst(&mut self, forward: bool, n: u32) -> u32 {
        if !self.power_on || n == 0 {
            return 0;
        }
        self.dir_reverse = !forward;
        let rate = if forward { self.params.motor.step_rate_hz } else { self.params.motor.reverse_rate_hz };
        let step_us = (1e6 / rate).round() as u64;
        let mut peak: f64 = 0.0;
        let mut issued = 0;
        for i in 0..n {
            if !self.vmot_on() {
                if i == 0 {
                    self.stats.bursts_blocked_by_interlock += 1;
                    if forward && !self.docked_phys {
                        self.stats.bursts_blocked_forward_undocked += 1;
                    }
                }
                break;
            }
            let undocked = !self.docked_phys;
            let vmot = self.vmot_v();
            let r = self.plant.step(if forward { 1 } else { -1 }, rate, vmot, &mut self.rng);
            issued += 1;
            peak = peak.max(r.current_ma);
            if forward {
                self.stats.forward_pulses_issued += 1;
                self.stats.forward_pulses_issued_undocked += undocked as u64;
                if r.moved {
                    self.note_forward_motion(undocked);
                }
            }
            self.t_us += step_us;
            self.plant.relax(step_us as f64 / 1e6);
            self.background(step_us, r.current_ma);
            if (self.t_us - self.last_poll_us) as f64 >= self.params.sensor.poll_ms * 1000.0 && self.power_on && !self.angle_nack {
                self.poll_angle(); // keeps the unwrap valid, like hal/angle.rs::poll
            }
            if !self.power_on || self.reset_pending.is_some() {
                break;
            }
        }
        self.dir_reverse = false;
        self.last_burst_peak_ma = peak;
        self.stats.peak_current_ma = self.stats.peak_current_ma.max(peak);
        issued
    }

    /// DONE pulse of the safety path.
    pub fn kick(&mut self) {
        if self.kick_stuck || !self.power_on {
            return;
        }
        self.wdt_last_done_us = self.t_us;
        self.steps_since_done0 = self.plant.forward_moved_steps;
    }

    pub fn set_buzzer(&mut self, b: Buzzer) {
        if self.buzzer != b {
            self.buzzer_log.push((self.t_us, b));
        }
        self.buzzer = b;
    }

    /// Boot completed: the firmware starts running (called by the device layer).
    pub fn booted(&mut self) {
        self.boot_at_us = None;
        self.reset_pending = None;
        self.tracker = Tracker::default();
        self.wdt_last_done_us = self.t_us;
        self.steps_since_done0 = self.plant.forward_moved_steps;
    }
}

/// The core's `Hal` over the shared world.
#[derive(Clone)]
pub struct SimHal(pub Rc<RefCell<World>>);

impl Hal for SimHal {
    fn motor_step(&mut self, steps: Pulses) -> Pulses {
        Pulses(self.0.borrow_mut().burst(true, steps.0))
    }
    fn motor_step_reverse(&mut self, steps: Pulses) -> Pulses {
        let r = Pulses(self.0.borrow_mut().burst(false, steps.0));
        r
    }
    fn set_draw_rate_pps(&mut self, pps: u32) {
        // the HAL clamps to its hard cap (REVERSE_RATE_MAX_HZ = 1000)
        self.0.borrow_mut().params.motor.reverse_rate_hz = pps.clamp(1, 1000) as f64;
    }
    fn reset_cause(&mut self) -> openpatch_core::hal::ResetCause {
        self.0.borrow().boot_cause
    }
    fn motor_enable(&mut self, enable: bool) {
        let mut w = self.0.borrow_mut();
        if !w.power_on {
            return;
        }
        if enable {
            w.mcu_en = true;
            w.latch_q = true; // ARM_CLK edge, accepted while the watchdog has not timed out
        } else {
            w.mcu_en = false;
            w.latch_q = false;
        }
    }
    fn angle_read(&mut self) -> Option<AngleCounts> {
        self.0.borrow_mut().angle_read().map(AngleCounts)
    }
    fn watchdog_kick(&mut self) {
        self.0.borrow_mut().kick();
    }
    fn buzzer(&mut self, pattern: Buzzer) {
        self.0.borrow_mut().set_buzzer(pattern);
    }
    fn battery_mv(&mut self) -> u16 {
        self.0.borrow().battery_idle_mv().clamp(0.0, 65535.0) as u16
    }
    fn time_ms(&mut self) -> Millis {
        Millis(self.0.borrow().t_us / 1000)
    }
    fn docked(&mut self) -> bool {
        self.0.borrow().docked_hw()
    }
    fn charger_present(&mut self) -> bool {
        self.0.borrow().charger
    }
    fn motor_current_peak_ma(&mut self) -> Option<u16> {
        let w = self.0.borrow();
        if w.power_on && w.params.motor.current_sense {
            Some(w.last_burst_peak_ma.round().clamp(0.0, 65535.0) as u16)
        } else {
            None
        }
    }
    /// Findings of the bench controller (POST), as data.
    fn take_diag(&mut self) -> Option<openpatch_core::hal::DiagEvent> {
        self.0.borrow_mut().board.events.pop_front()
    }
    /// RB1..RB10 from the board model.
    fn interlock_state(&mut self) -> Option<openpatch_core::hal::InterlockReadback> {
        use openpatch_core::bench_ctl::{own_pin_mismatch, readback_from, BenchPins};
        let mut pins = crate::board::SimPins(self.0.clone());
        let r = pins.read();
        let (v, i) = (pins.vmot_mv(), pins.isense_mv());
        let (stby, en) = { let w = self.0.borrow(); (w.board.stby, w.mcu_en) };
        Some(readback_from(&r, v, i, own_pin_mismatch(&r, en, stby, r.latch_clr)))
    }
    /// The core's POST proofs (`BenchCtl::selftest`) run unchanged against the board model.
    fn selftest(&mut self, step: openpatch_core::hal::SelfTestStep) -> openpatch_core::hal::SelfTestOutcome {
        use openpatch_core::bench_ctl::{BenchCtl, CtlCfg};
        let mut c = BenchCtl::new(crate::board::SimPins(self.0.clone()), CtlCfg::BENCH);
        {
            let w = self.0.borrow();
            c.quarantined = w.board.quarantined;
            c.failed = w.board.failed;
        }
        let out = c.selftest(step);
        let mut w = self.0.borrow_mut();
        w.board.quarantined = c.quarantined;
        w.board.failed = c.failed;
        while let Some(e) = c.take_event() {
            w.board.events.push_back(e);
        }
        out
    }
}
