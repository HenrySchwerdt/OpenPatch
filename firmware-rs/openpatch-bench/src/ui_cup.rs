//! Button, RGB LED and sounder of the cup pod v4. Owns no safety function (same contract as `ui.rs`): button events go to the
//! safety task (`UI_CMD`), the outputs follow atomics written by the others.
//!
//! * button (`BTN_N`, internal pull-up, active low): short press = pairing window (60 s) + silence; hold >= 3 s = emergency stop;
//! * RGB LED (common anode on VBAT, active low; no PWM, a channel is on when its share is above 0): the colour comes from the host
//!   tested `openpatch_core::led::LedState` (fault 4 Hz red, charging pulse, full green, low / critical red, button = battery colour);
//!   on top of it the pairing window blinks blue, a failed interlock overrides everything with fast red;
//! * sounder (`BUZ_A`, NFET gate, PWM0): beep / double beep / alarm as on the bench board. TODO(verify-on-hardware): the
//!   resonance of the fitted 4 x 4 mm magnetic sounder (2.7 kHz is the bench MLT-8530 value).
use core::sync::atomic::Ordering;
use embassy_nrf::gpio::{AnyPin, Input, Level, Output, OutputDrive, Pull};
use embassy_nrf::peripherals::PWM0;
use embassy_nrf::pwm::{DutyCycle, SimpleConfig, SimplePwm};
use embassy_nrf::Peri;
use embassy_time::{Duration, Instant, Timer};
use openpatch_core::led::{charger_state, LedInputs, LedState, Rgb};

use crate::config::*;
use crate::pairing;
use crate::shared::*;

const POLL_MS: u64 = 10;

struct RgbLed {
    r: Output<'static>,
    g: Output<'static>,
    b: Output<'static>,
}

impl RgbLed {
    fn show(&mut self, c: Rgb) {
        // active low: LOW = lit
        self.r.set_level(Level::from(c.r == 0));
        self.g.set_level(Level::from(c.g == 0));
        self.b.set_level(Level::from(c.b == 0));
    }
}

struct Sounder {
    pwm: SimplePwm<'static>,
}

impl Sounder {
    fn set(&mut self, on: bool) {
        if on {
            let half = self.pwm.max_duty() / 2;
            self.pwm.set_duty(0, DutyCycle::normal(half));
            self.pwm.enable();
        } else {
            self.pwm.disable(); // gate idles low: NFET off
        }
    }
}

#[allow(clippy::too_many_arguments)]
#[embassy_executor::task]
pub async fn ui_task(
    pwm0: Peri<'static, PWM0>,
    button: Peri<'static, AnyPin>,
    led_r: Peri<'static, AnyPin>,
    led_g: Peri<'static, AnyPin>,
    led_b: Peri<'static, AnyPin>,
    buz_a: Peri<'static, AnyPin>,
    chg_stat: Peri<'static, AnyPin>,
) -> ! {
    let button = Input::new(button, Pull::Up);
    let chg_stat = Input::new(chg_stat, Pull::None);
    let off = |p| Output::new(p, Level::High, OutputDrive::Standard);
    let mut led = RgbLed { r: off(led_r), g: off(led_g), b: off(led_b) };
    let pwm = SimplePwm::new_1ch(pwm0, buz_a, &SimpleConfig::default());
    pwm.set_period(BUZZER_HZ);
    let mut buz = Sounder { pwm };
    buz.set(false);
    let mut ledsm = LedState::new();
    let mut press_start: Option<Instant> = None;
    let mut stop_sent = false;
    let mut short_press = false;
    let mut debounce_until = Instant::now();
    let mut beep_until: Option<Instant> = None;
    let mut double_until: Option<Instant> = None;
    let mut phase: u64 = 0;
    loop {
        Timer::after_millis(POLL_MS).await;
        phase = phase.wrapping_add(1);
        let now = Instant::now();
        // ---- button ----
        let down = button.is_low();
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
                    short_press = true;
                    pairing::open();
                    let _ = UI_CMD.try_send(UiCmd::SilenceAlarm);
                    beep_until = Some(now + Duration::from_millis(BEEP_MS));
                    defmt::info!("button: pairing window open for {} s", PAIRING_WINDOW_S);
                }
            }
            _ => {}
        }
        // ---- sounder ----
        if BEEP_REQ.swap(false, Ordering::Relaxed) {
            beep_until = Some(now + Duration::from_millis(BEEP_MS));
        }
        if DOUBLE_BEEP_REQ.swap(false, Ordering::Relaxed) {
            double_until = Some(now + Duration::from_millis(5 * BEEP_MS));
        }
        let mut beeping = matches!(beep_until, Some(t) if now < t);
        if let Some(t) = double_until {
            if now < t {
                let rem = (t - now).as_millis() / BEEP_MS;
                beeping |= rem == 4 || rem == 2;
            }
        }
        let alarm = ALARM_ON.load(Ordering::Relaxed);
        buz.set(beeping || (alarm && (phase / 20) % 2 == 0));
        // ---- LED ----
        let interlock_bad = INTERLOCK_FAILED.load(Ordering::Relaxed);
        let inputs = LedInputs {
            fault: alarm || FAULT_LATCHED.load(Ordering::Relaxed),
            charger: charger_state(crate::hal::cup::usb_detected(), chg_stat.is_low()),
            vbat_mv: VBAT_MV.load(Ordering::Relaxed),
            button_pressed: core::mem::take(&mut short_press),
        };
        let mut c = ledsm.update(now.as_millis(), &inputs);
        if pairing::is_open() && (phase / 12) % 2 == 0 {
            c = Rgb { r: 0, g: 0, b: 100 };
        }
        if interlock_bad {
            c = if (phase / 5) % 2 == 0 { Rgb::red(100) } else { Rgb::OFF };
        }
        led.show(c);
    }
}
