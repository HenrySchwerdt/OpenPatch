//! Button, LEDs, buzzer. Owns no safety function: it forwards button events to the safety task
//! (`UI_CMD`) and drives the outputs from atomics written by the others.
//!
//! * short press: open the pairing window (60 s) and silence the alarm,
//! * hold >= 3 s: emergency stop (sent once while the button is still held),
//! * status LED: heartbeat (idle), double rate while BLE connected, fast blink while the pairing
//!   window is open, solid while delivering, 5 Hz while a bench sequence runs,
//! * alarm LED: solid while a fault is latched or the buzzer alarm is on, blinking on interlock failure.
use core::sync::atomic::Ordering;
use embassy_nrf::gpio::{AnyPin, Input, Level, Output, OutputDrive, Pull};
use embassy_nrf::peripherals::PWM0;
use embassy_nrf::pwm::{DutyCycle, SimpleConfig, SimplePwm};
use embassy_nrf::Peri;
use embassy_time::{Duration, Instant, Timer};

use crate::board;
use crate::config::*;
use crate::pairing;
use crate::shared::*;

const POLL_MS: u64 = 10;

struct Led {
    pin: Output<'static>,
}

impl Led {
    fn new(pin: Peri<'static, AnyPin>) -> Self {
        let off = Level::from(!board::LED_ACTIVE_HIGH);
        Self { pin: Output::new(pin, off, OutputDrive::Standard) }
    }
    fn set(&mut self, on: bool) {
        self.pin.set_level(Level::from(on == board::LED_ACTIVE_HIGH));
    }
}

struct Buzzer {
    pwm: SimplePwm<'static>,
}

impl Buzzer {
    fn new(pwm: Peri<'static, PWM0>, pin: Peri<'static, AnyPin>) -> Self {
        let pwm = SimplePwm::new_1ch(pwm, pin, &SimpleConfig::default());
        pwm.set_period(BUZZER_HZ);
        let mut b = Self { pwm };
        b.set(false);
        b
    }
    fn set(&mut self, on: bool) {
        if on {
            let half = self.pwm.max_duty() / 2;
            self.pwm.set_duty(0, DutyCycle::normal(half)); // 50 %
            self.pwm.enable();
        } else {
            self.pwm.disable(); // idle low
        }
    }
}

#[embassy_executor::task]
pub async fn ui_task(
    pwm0: Peri<'static, PWM0>,
    button: Peri<'static, AnyPin>,
    dock_sim_button: Option<Peri<'static, AnyPin>>,
    led_status: Peri<'static, AnyPin>,
    led_alarm: Peri<'static, AnyPin>,
    buzzer: Peri<'static, AnyPin>,
) -> ! {
    let button = Input::new(button, Pull::None);
    let dock_btn = dock_sim_button.map(|p| Input::new(p, Pull::None));
    let mut st = Led::new(led_status);
    let mut alm = Led::new(led_alarm);
    let mut buz = Buzzer::new(pwm0, buzzer);

    let pressed = |i: &Input<'static>| i.is_low() == board::BUTTON_ACTIVE_LOW;
    let mut press_start: Option<Instant> = None;
    let mut stop_sent = false;
    let mut dock_prev = false;
    let mut debounce_until = Instant::now();
    let mut beep_until: Option<Instant> = None;
    let mut double_until: Option<Instant> = None;
    let mut phase: u64 = 0; // 10 ms units

    loop {
        Timer::after_millis(POLL_MS).await;
        phase = phase.wrapping_add(1);
        let now = Instant::now();

        // ---- pod button ----
        let down = pressed(&button);
        match (down, press_start) {
            (true, None) if now >= debounce_until => {
                press_start = Some(now);
                stop_sent = false;
            }
            (true, Some(t0)) => {
                if !stop_sent && now - t0 >= Duration::from_millis(EMERGENCY_HOLD_MS) {
                    stop_sent = true;
                    let _ = UI_CMD.try_send(UiCmd::EmergencyStop);
                    defmt::warn!("button hold: EMERGENCY STOP");
                }
            }
            (false, Some(_)) => {
                press_start = None;
                debounce_until = now + Duration::from_millis(BUTTON_DEBOUNCE_MS);
                if !stop_sent {
                    pairing::open();
                    let _ = UI_CMD.try_send(UiCmd::SilenceAlarm);
                    beep_until = Some(now + Duration::from_millis(BEEP_MS));
                    defmt::info!("button: pairing window open for {} s", PAIRING_WINDOW_S);
                }
            }
            _ => {}
        }

        // ---- DK: BUTTON2 toggles the simulated DOCKED input ----
        if let Some(b) = dock_btn.as_ref() {
            let d = pressed(b);
            if d && !dock_prev {
                let v = !DOCK_SIM.load(Ordering::Relaxed);
                DOCK_SIM.store(v, Ordering::Relaxed);
                defmt::info!("simulated DOCKED = {}", v);
            }
            dock_prev = d;
        }

        // ---- buzzer ----
        if BEEP_REQ.swap(false, Ordering::Relaxed) {
            beep_until = Some(now + Duration::from_millis(BEEP_MS));
        }
        if DOUBLE_BEEP_REQ.swap(false, Ordering::Relaxed) {
            double_until = Some(now + Duration::from_millis(5 * BEEP_MS));
        }
        let alarm = ALARM_ON.load(Ordering::Relaxed);
        let mut beeping = matches!(beep_until, Some(t) if now < t);
        // double beep over 5 units of BEEP_MS: on, off, on, off, off
        if let Some(t) = double_until {
            if now < t {
                let rem = (t - now).as_millis() / BEEP_MS; // 4..0
                beeping |= rem == 4 || rem == 2;
            }
        }
        // alarm: 200 ms on / 200 ms off
        let alarm_phase_on = (phase / 20) % 2 == 0;
        buz.set(beeping || (alarm && alarm_phase_on));

        // ---- LEDs ----
        let bench = BENCH_ACTIVE.load(Ordering::Relaxed);
        let delivering = DELIVERING.load(Ordering::Relaxed);
        let pairing_open = pairing::is_open();
        let connected = BLE_CONNECTED.load(Ordering::Relaxed);
        let st_on = if delivering {
            true
        } else if bench {
            (phase / 10) % 2 == 0 // 5 Hz
        } else if pairing_open {
            (phase / 12) % 2 == 0 // about 4 Hz
        } else if connected {
            phase % 100 < 10 // 100 ms every 1 s
        } else {
            phase % 200 < 10 // 100 ms every 2 s
        };
        st.set(st_on);
        let interlock_bad = INTERLOCK_FAILED.load(Ordering::Relaxed);
        let alm_on = if interlock_bad {
            (phase / 10) % 2 == 0
        } else {
            alarm || FAULT_LATCHED.load(Ordering::Relaxed)
        };
        alm.set(alm_on);
    }
}
