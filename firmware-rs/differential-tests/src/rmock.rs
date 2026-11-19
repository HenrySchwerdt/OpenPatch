//! Rust-side mock HAL with the exact semantics of the C mock (`firmware/tests/mock_hal.c`):
//! 16 angle counts per executed step (Test26100/Test8156: 256 steps/turn = 16 counts/step), the
//! sensor sees `delivered_pct` % of the steps, `steps_limit` caps a burst. The angle sensor is
//! always present; the current sensor returns `None` (current occlusion disabled).

use openpatch_core::{AngleCounts, Buzzer, Hal, Millis, Pulses};
use std::cell::RefCell;
use std::rc::Rc;

#[derive(Debug)]
pub struct MockState {
    pub now_ms: u64,
    pub battery_mv: u16,
    pub angle_x100: i64,
    pub delivered_pct: i64,
    pub steps_limit: i64,
    pub total_steps: u32,
    pub enabled: bool,
    pub stepped_while_disabled: bool,
    pub kicks: u32,
    pub enable_calls: u32,
    pub buzzer: Buzzer,
    pub docked: bool,
    pub charger: bool,
}

impl Default for MockState {
    fn default() -> Self {
        MockState {
            now_ms: 0,
            battery_mv: 3900,
            angle_x100: 0,
            delivered_pct: 100,
            steps_limit: -1,
            total_steps: 0,
            enabled: false,
            stepped_while_disabled: false,
            kicks: 0,
            enable_calls: 0,
            buzzer: Buzzer::Off,
            docked: true,
            charger: false,
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
    /// Same numbering as C `op_buzzer_t` (Off 0, Beep 1, Alarm 2). `DoubleBeep` is draw-only: 3.
    pub fn buzzer_code(&self) -> u64 {
        match self.0.borrow().buzzer {
            Buzzer::Off => 0,
            Buzzer::Beep => 1,
            Buzzer::Alarm => 2,
            Buzzer::DoubleBeep => 3,
        }
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
        let d = n as i64 * 16 * m.delivered_pct;
        m.angle_x100 += d;
        Pulses(n)
    }
    fn motor_enable(&mut self, e: bool) {
        let mut m = self.0.borrow_mut();
        m.enabled = e;
        m.enable_calls += 1;
    }
    fn angle_read(&mut self) -> Option<AngleCounts> {
        Some(AngleCounts(self.0.borrow().angle_x100 / 100))
    }
    fn watchdog_kick(&mut self) {
        self.0.borrow_mut().kicks += 1;
    }
    fn buzzer(&mut self, p: Buzzer) {
        self.0.borrow_mut().buzzer = p;
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
}
