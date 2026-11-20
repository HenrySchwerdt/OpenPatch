//! Status LED patterns of the cup board v4 as a pure state machine (`FIRMWARE-PINMAP.md` "Status LED (RGB, ...)").
//!
//! The RGB LED `LD1` is common anode on VBAT with the cathodes on `LED_R` / `LED_G` / `LED_B` (active low), 1.5 to 2 mA per channel:
//! the firmware drives 20 to 50 % PWM. This module only decides the logical colour and brightness (0..=100 percent) from the inputs
//! and the time; the HAL inverts it for the active-low pins ([`Rgb::pwm_compare_active_low`]) and switches the PWM off for [`Rgb::OFF`]
//! (idle current stays negligible). No hardware, no allocation, no clock of its own: the caller passes `now_ms`.
//!
//! Patterns, highest priority first:
//!
//! | State | Pattern |
//! |---|---|
//! | fault (unacknowledged, from the supervisor / diagnostics) | red blink 4 Hz until acknowledged |
//! | charging (`CHG_STAT` low, on a cable) | red breathing, 1 Hz triangle |
//! | charge complete (on a cable, `CHG_STAT` high) | steady green |
//! | button press | the battery state for 0.8 s: green above 3.8 V, orange (red + green) 3.5 to 3.8 V, red below |
//! | critical battery (below the motor-start limit 3.4 V) | red double flash every 4 s |
//! | low battery (below 3.5 V) | red single flash every 4 s |
//! | otherwise | off |
//!
//! "Charging pulse, full = green, low = red" is the user requirement; the red channel is also lit by the charger status in hardware on
//! boards that keep the diode-OR (the 45-part board does not: the MCU wakes on VBUS and does it in firmware).

use crate::battery::{LED_GREEN_ABOVE_MV, LED_ORANGE_ABOVE_MV, MOTOR_MIN_VBAT_MV};
use crate::limits::BATTERY_LOW_MV;

/// Brightness of a lit channel, percent (the indicator is meant to be dim: 1.5 to 2 mA per channel at 100 %).
pub const LED_LEVEL_PCT: u8 = 30;

/// Charging breathing period, ms (1 Hz).
pub const CHARGING_PERIOD_MS: u64 = 1_000;
/// Fault blink period, ms (4 Hz) and its on time.
pub const FAULT_PERIOD_MS: u64 = 250;
pub const FAULT_ON_MS: u64 = 125;
/// Low battery: one flash every 4 s, 100 ms long; critical: two flashes 250 ms apart (start to start).
pub const LOW_PERIOD_MS: u64 = 4_000;
pub const FLASH_MS: u64 = 100;
pub const DOUBLE_GAP_MS: u64 = 250;
/// Button press indication time.
pub const BUTTON_SHOW_MS: u64 = 800;

/// Logical LED colour, brightness per channel in percent (0 = off).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct Rgb {
    pub r: u8,
    pub g: u8,
    pub b: u8,
}

impl Rgb {
    pub const OFF: Rgb = Rgb { r: 0, g: 0, b: 0 };
    pub const fn red(pct: u8) -> Rgb {
        Rgb { r: pct, g: 0, b: 0 }
    }
    pub const fn green(pct: u8) -> Rgb {
        Rgb { r: 0, g: pct, b: 0 }
    }
    /// Orange = red + green.
    pub const fn orange(pct: u8) -> Rgb {
        Rgb { r: pct, g: pct, b: 0 }
    }
    pub const fn is_off(&self) -> bool {
        self.r == 0 && self.g == 0 && self.b == 0
    }
    /// PWM compare value of one channel for an ACTIVE-LOW pin with counter top `top`: the pin is LOW for `pct` percent of the period.
    /// 0 percent gives `top` (always high = off). `pct` is clamped to 100.
    pub const fn pwm_compare_active_low(pct: u8, top: u16) -> u16 {
        let pct = if pct > 100 { 100 } else { pct } as u32;
        (top as u32 - top as u32 * pct / 100) as u16
    }
}

/// State of the charger as the firmware sees it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum Charger {
    /// No cable, or a cable and the charger idle (`CHG_STAT` high-Z).
    None,
    Charging,
    Done,
}

/// MCP73832 STAT: low = charging, high = charge complete, high-Z = no supply or shutdown. The pin is read twice, with the internal
/// pull-down and then the internal pull-up: a driven low reads (0, 0), a driven high (1, 1), a floating pin follows the pull (0, 1).
/// A cable (`vbus_present`) is required for either charging state; (1, 0) is not physical and reads as `None`.
pub const fn charger_state(vbus_present: bool, stat_with_pulldown: bool, stat_with_pullup: bool) -> Charger {
    if !vbus_present {
        return Charger::None;
    }
    match (stat_with_pulldown, stat_with_pullup) {
        (false, false) => Charger::Charging,
        (true, true) => Charger::Done,
        _ => Charger::None,
    }
}

/// Inputs sampled by the caller.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct LedInputs {
    /// A fault from the supervisor or the diagnostics that is still unacknowledged.
    pub fault: bool,
    pub charger: Charger,
    /// Open-circuit (rest) cell voltage, mV (`battery::vddhdiv5_to_mv`). While charging the value is not used.
    pub vbat_mv: u16,
    /// A button press happened since the last call (edge, not level).
    pub button_pressed: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Mode {
    Off,
    Fault,
    Charging,
    Full,
    Button,
    Critical,
    Low,
}

/// The pattern generator.
#[derive(Clone, Copy, Debug)]
pub struct LedState {
    mode: Mode,
    /// Pattern phase origin: the time the mode was entered (breathing starts at zero brightness, blinks start with "on").
    since_ms: u64,
    /// The button indication ends at this time (0 = not showing).
    button_until_ms: u64,
    /// The colour latched at the button press (battery state at that moment).
    button_color: Rgb,
}

impl Default for LedState {
    fn default() -> Self {
        Self::new()
    }
}

impl LedState {
    pub const fn new() -> Self {
        Self { mode: Mode::Off, since_ms: 0, button_until_ms: 0, button_color: Rgb::OFF }
    }

    /// Colour for the current time and inputs. Call at least every 25 ms while the LED is not [`Rgb::OFF`] (smooth breathing),
    /// and every time an input changes; when `is_idle` is true the HAL may stop the timer and sleep.
    pub fn update(&mut self, now_ms: u64, inp: &LedInputs) -> Rgb {
        if inp.button_pressed && inp.charger == Charger::None && !inp.fault {
            self.button_until_ms = now_ms + BUTTON_SHOW_MS;
            self.button_color = battery_color(inp.vbat_mv);
        }
        let showing_button = now_ms < self.button_until_ms;
        let want = if inp.fault {
            Mode::Fault
        } else if inp.charger == Charger::Charging {
            Mode::Charging
        } else if inp.charger == Charger::Done {
            Mode::Full
        } else if showing_button {
            Mode::Button
        } else if inp.vbat_mv < MOTOR_MIN_VBAT_MV {
            Mode::Critical
        } else if inp.vbat_mv < BATTERY_LOW_MV {
            Mode::Low
        } else {
            Mode::Off
        };
        if want != self.mode {
            self.mode = want;
            self.since_ms = now_ms;
        }
        let t = now_ms.saturating_sub(self.since_ms);
        match self.mode {
            Mode::Off => Rgb::OFF,
            Mode::Fault => {
                if t % FAULT_PERIOD_MS < FAULT_ON_MS {
                    Rgb::red(LED_LEVEL_PCT)
                } else {
                    Rgb::OFF
                }
            }
            Mode::Charging => Rgb::red(breathing_pct(t % CHARGING_PERIOD_MS, CHARGING_PERIOD_MS, LED_LEVEL_PCT)),
            Mode::Full => Rgb::green(LED_LEVEL_PCT),
            Mode::Button => self.button_color,
            Mode::Low => {
                if t % LOW_PERIOD_MS < FLASH_MS {
                    Rgb::red(LED_LEVEL_PCT)
                } else {
                    Rgb::OFF
                }
            }
            Mode::Critical => {
                let p = t % LOW_PERIOD_MS;
                if p < FLASH_MS || (p >= DOUBLE_GAP_MS && p < DOUBLE_GAP_MS + FLASH_MS) {
                    Rgb::red(LED_LEVEL_PCT)
                } else {
                    Rgb::OFF
                }
            }
        }
    }

    /// True when the LED is off and no pattern is running except the periodic low-battery flash: the HAL may stop the PWM and the
    /// fast timer. (Off and the idle part of a low / critical pattern.)
    pub fn is_dark_mode(&self) -> bool {
        matches!(self.mode, Mode::Off | Mode::Low | Mode::Critical)
    }
}

/// Button indication colour: green above 3.8 V, orange from 3.5 to 3.8 V, red below.
pub const fn battery_color(vbat_mv: u16) -> Rgb {
    if vbat_mv > LED_GREEN_ABOVE_MV {
        Rgb::green(LED_LEVEL_PCT)
    } else if vbat_mv >= LED_ORANGE_ABOVE_MV {
        Rgb::orange(LED_LEVEL_PCT)
    } else {
        Rgb::red(LED_LEVEL_PCT)
    }
}

/// Triangle (breathing) brightness: 0 at `t = 0`, `max_pct` at half the period, 0 at the end. `t` in `0..period`.
pub const fn breathing_pct(t: u64, period: u64, max_pct: u8) -> u8 {
    if period == 0 {
        return 0;
    }
    let half = period / 2;
    let x = if t < half { t } else { period.saturating_sub(t) };
    if half == 0 {
        return 0;
    }
    (x * max_pct as u64 / half) as u8
}
