//! Shared test fixtures: mock HAL (same semantics as the C reference `firmware/tests/mock_hal.c`,
//! extended with reverse stepping for draw mode and a missing-sensor switch) and helpers.
//!
//! Calibration used by most tests: the HOST-ONLY test preset `Test26100` (26 100 uU/step, 256
//! steps per turn = exactly 16 angle counts per step, like the C encoder's 16 substeps), so the
//! numeric expectations of the C reference tests stay valid. Production presets: tests/presets.rs.
#![allow(dead_code)]

use openpatch_core::limits::*;
use openpatch_core::*;
use std::cell::RefCell;
use std::rc::Rc;

#[derive(Debug)]
pub struct MockState {
    pub now_ms: u64,
    pub battery_mv: u16,
    /// Leadscrew angle * 100 (counts).
    pub angle_x100: i64,
    /// Counts the angle sensor advances per executed forward step when healthy (16 for Test26100).
    pub counts_per_step: i64,
    /// Percent of commanded forward steps the sensor sees (100 = healthy).
    pub delivered_pct: i64,
    /// -1 unlimited; else max forward steps the motor executes per call.
    pub steps_limit: i64,
    /// Same for reverse steps (draw mode); -1 unlimited.
    pub reverse_limit: i64,
    /// Percent of reverse steps the sensor sees.
    pub reverse_pct: i64,
    pub total_steps: u32,
    pub total_reverse_steps: u32,
    pub enabled: bool,
    pub stepped_while_disabled: bool,
    pub kicks: u32,
    pub enable_calls: u32,
    pub buzzer: Buzzer,
    pub buzzer_history: Vec<Buzzer>,
    pub docked: bool,
    pub charger: bool,
    pub angle_missing: bool,
    pub current_ma: Option<u16>,
    pub step_calls: Vec<u32>,
    pub reverse_calls: Vec<u32>,
    /// Directions passed to `motor_enable_dir`, in order.
    pub enable_dirs: Vec<MotorDir>,
    /// Returned (once) by `motor_fault`.
    pub fault: Option<MotorFault>,
    /// Drained one by one by `take_diag` (HAL-detected faults, as data).
    pub diag_events: Vec<openpatch_core::hal::DiagEvent>,
    /// FaultyHal injectors (docs/06-diagnostics.md 6.1): why the MCU started, the retained-RAM breadcrumb, and what
    /// `motor_step_ex` reports about the burst.
    pub reset_cause: openpatch_core::hal::ResetCause,
    pub breadcrumb: u32,
    pub ex_drv_fault: bool,
    pub ex_vmot_missing: bool,
    pub ex_peak: Option<u16>,
    /// Last rate passed to `set_draw_rate_pps`.
    pub draw_rate_pps: Option<u32>,
}

impl Default for MockState {
    fn default() -> Self {
        MockState {
            now_ms: 0,
            battery_mv: 3900,
            angle_x100: 0,
            counts_per_step: 16,
            delivered_pct: 100,
            steps_limit: -1,
            reverse_limit: -1,
            reverse_pct: 100,
            total_steps: 0,
            total_reverse_steps: 0,
            enabled: false,
            stepped_while_disabled: false,
            kicks: 0,
            enable_calls: 0,
            buzzer: Buzzer::Off,
            buzzer_history: Vec::new(),
            docked: true,
            charger: false,
            angle_missing: false,
            current_ma: None,
            step_calls: Vec::new(),
            reverse_calls: Vec::new(),
            enable_dirs: Vec::new(),
            fault: None,
            diag_events: Vec::new(),
            reset_cause: openpatch_core::hal::ResetCause::PowerOn,
            breadcrumb: 0,
            ex_drv_fault: false,
            ex_vmot_missing: false,
            ex_peak: None,
            draw_rate_pps: None,
        }
    }
}

#[derive(Clone, Default)]
pub struct MockHal(pub Rc<RefCell<MockState>>);

impl MockHal {
    pub fn new() -> Self {
        Self::default()
    }
    pub fn st(&self) -> std::cell::RefMut<'_, MockState> {
        self.0.borrow_mut()
    }
    pub fn advance_ms(&self, ms: u64) {
        self.0.borrow_mut().now_ms += ms;
    }
    /// Turn the leadscrew by hand (counts).
    pub fn turn_counts(&self, counts: i64) {
        self.0.borrow_mut().angle_x100 += counts * 100;
    }
}

impl Hal for MockHal {
    fn motor_step(&mut self, steps: Pulses) -> Pulses {
        let mut m = self.0.borrow_mut();
        if !m.enabled {
            m.stepped_while_disabled = true;
        }
        let mut n = steps.0;
        if m.steps_limit >= 0 && (m.steps_limit as u32) < n {
            n = m.steps_limit as u32;
        }
        m.total_steps += n;
        let d = n as i64 * m.counts_per_step * m.delivered_pct;
        m.angle_x100 += d;
        m.step_calls.push(n);
        Pulses(n)
    }
    fn set_draw_rate_pps(&mut self, pps: u32) {
        self.0.borrow_mut().draw_rate_pps = Some(pps);
    }
    fn motor_step_reverse(&mut self, steps: Pulses) -> Pulses {
        let mut m = self.0.borrow_mut();
        if !m.enabled {
            m.stepped_while_disabled = true;
        }
        let mut n = steps.0;
        if m.reverse_limit >= 0 && (m.reverse_limit as u32) < n {
            n = m.reverse_limit as u32;
        }
        m.total_reverse_steps += n;
        let d = n as i64 * m.counts_per_step * m.reverse_pct;
        m.angle_x100 -= d;
        m.reverse_calls.push(n);
        Pulses(n)
    }
    fn motor_enable(&mut self, e: bool) {
        let mut m = self.0.borrow_mut();
        m.enabled = e;
        m.enable_calls += 1;
    }
    fn motor_enable_dir(&mut self, dir: MotorDir) {
        self.0.borrow_mut().enable_dirs.push(dir);
        self.motor_enable(true);
    }
    fn motor_fault(&mut self) -> Option<MotorFault> {
        self.0.borrow_mut().fault.take()
    }
    fn angle_read(&mut self) -> Option<AngleCounts> {
        let m = self.0.borrow();
        if m.angle_missing {
            None
        } else {
            Some(AngleCounts(m.angle_x100 / 100))
        }
    }
    fn watchdog_kick(&mut self) {
        self.0.borrow_mut().kicks += 1;
    }
    fn buzzer(&mut self, p: Buzzer) {
        let mut m = self.0.borrow_mut();
        m.buzzer = p;
        m.buzzer_history.push(p);
    }
    fn battery_mv(&mut self) -> u16 {
        self.0.borrow().battery_mv
    }
    fn time_ms(&mut self) -> Millis {
        Millis(self.0.borrow().now_ms)
    }
    fn docked(&mut self) -> bool {
        self.0.borrow().docked
    }
    fn charger_present(&mut self) -> bool {
        self.0.borrow().charger
    }
    fn motor_current_peak_ma(&mut self) -> Option<u16> {
        self.0.borrow().current_ma
    }
    fn motor_step_ex(&mut self, steps: Pulses) -> openpatch_core::hal::StepResult {
        let executed = self.motor_step(steps);
        let m = self.0.borrow();
        openpatch_core::hal::StepResult { executed, drv_fault: m.ex_drv_fault, peak_ma: m.ex_peak, vmot_ok: !m.ex_vmot_missing }
    }
    fn reset_cause(&mut self) -> openpatch_core::hal::ResetCause {
        self.0.borrow().reset_cause
    }
    fn breadcrumb(&mut self) -> u32 {
        self.0.borrow().breadcrumb
    }
    fn take_diag(&mut self) -> Option<openpatch_core::hal::DiagEvent> {
        let mut m = self.0.borrow_mut();
        if m.diag_events.is_empty() {
            None
        } else {
            Some(m.diag_events.remove(0))
        }
    }
}

pub const TEST_UU: u32 = 26_100;
pub const TEST_PAIR: u32 = 0xA1B2_C3D4;

/// Host-only test calibration (26 100 uU/step, 16 counts/step).
pub fn cal_test() -> DriveCal {
    DriveCal::preset(DriveId::Test26100 as u16).unwrap()
}

/// Pump with the test calibration, 100 U capacity, docked, nothing filled, RELAXED config (no
/// mandatory priming after fill; tests of that use `PumpConfig::STRICT` explicitly).
pub fn new_pump() -> (Pump<MockHal>, MockHal) {
    new_pump_cap(CAPACITY_100)
}

pub fn new_pump_cap(cap: MilliUnits) -> (Pump<MockHal>, MockHal) {
    let hal = MockHal::new();
    let cal = cal_test();
    let mut p = Pump::new(hal.clone(), Some(&cal), cap, 1);
    p.set_config(PumpConfig::RELAXED);
    (p, hal)
}

/// Pair + activate with a flat schedule (filled + docked required). Leaves the pod suspended.
pub fn activate(p: &mut Pump<MockHal>, flat_rate_mu_h: u32) -> Result<(), Error> {
    p.set_pairing(TEST_PAIR, 1)?;
    p.activate(&ActivateArgs {
        pair_id: TEST_PAIR,
        activation_id: 1,
        schedule: BasalSchedule::flat(MilliUnitsPerHour(flat_rate_mu_h)),
        temp: None,
    })
}

/// Filled with `fill_mu`, activated with a flat basal, resumed.
pub fn running(fill_mu: u32, flat_rate_mu_h: u32) -> (Pump<MockHal>, MockHal) {
    let (mut p, h) = new_pump();
    p.fill(MilliUnits(fill_mu)).unwrap();
    activate(&mut p, flat_rate_mu_h).unwrap();
    p.resume().unwrap();
    (p, h)
}

/// Advance the clock by `secs` seconds, ticking once per second.
pub fn run_secs(p: &mut Pump<MockHal>, h: &MockHal, secs: u64) {
    for _ in 0..secs {
        h.advance_ms(1000);
        p.tick();
    }
}

/// Tick (1 s each) until a running draw job has finished (bounded).
pub fn run_draw(p: &mut Pump<MockHal>, h: &MockHal) {
    for _ in 0..2000 {
        if !p.draw_running() {
            break;
        }
        run_secs(p, h, 1);
    }
}
