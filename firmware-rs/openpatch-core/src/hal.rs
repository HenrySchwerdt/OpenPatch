//! Hardware abstraction. The core never touches hardware: the embedded app implements [`Hal`]
//! (embassy-nrf), host tests and the differential tests use mocks.

use crate::units::{AngleCounts, Millis, Pulses};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum Buzzer {
    Off,
    /// Single short confirmation beep.
    Beep,
    /// Two short beeps (draw finished).
    DoubleBeep,
    /// Repeating alarm until set to `Off`.
    Alarm,
}

/// Direction of motor travel. `Reverse` is the draw (refill) direction. On the bench board DIR is
/// part of the hardware supply gate (`crate::interlock`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum MotorDir {
    Forward,
    Reverse,
}

/// Why a step burst or power-up failed, when the HAL knows (see [`Hal::motor_fault`]).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum MotorFault {
    /// STSPIN220 EN/FAULT asserted (over-current / thermal).
    Driver,
    /// A forward step was requested while undocked (hardware gate open): never retried.
    ForwardWhileUndocked,
    /// A reverse step was requested while docked.
    ReverseWhileDocked,
    /// The interlock is closed per the model but VMOT is absent.
    SupplyMissing,
    /// VMOT present where the gate must be open: interlock failure.
    SupplyUnexpected,
    /// An earlier power-down could not be verified: the interlock is latched failed.
    InterlockFailed,
    /// The step generator did not finish in time.
    Timeout,
}

pub trait Hal {
    /// Execute `steps` forward motor steps (blocking, short). Returns the steps executed.
    fn motor_step(&mut self, steps: Pulses) -> Pulses;
    /// Execute `steps` REVERSE steps (draw mode only), rate-limited by the HAL to <= 1000 pps.
    /// Default: unsupported (0 executed).
    fn motor_step_reverse(&mut self, _steps: Pulses) -> Pulses {
        Pulses(0)
    }
    /// Driver power gate (second, independent path next to the hardware watchdog interlock).
    fn motor_enable(&mut self, enable: bool);
    /// Power the driver for motion in `dir`. A board whose supply gate depends on the direction
    /// (bench board: `VMOT = MCU_EN AND latch AND (DOCKED OR DIR_REVERSE)`) sets DIR BEFORE it
    /// requests the supply. Default: direction independent, same as `motor_enable(true)`.
    fn motor_enable_dir(&mut self, _dir: MotorDir) {
        self.motor_enable(true);
    }
    /// Cause of the most recent short / failed burst or refused power-up, if the HAL knows it
    /// (take-and-clear). Default: unknown (the core only sees fewer steps than requested).
    fn motor_fault(&mut self) -> Option<MotorFault> {
        None
    }
    /// Cumulative leadscrew angle (TMAG5273), unwrapped, 4096 counts per turn. `None` = sensor
    /// missing: nothing is ever delivered without it.
    fn angle_read(&mut self) -> Option<AngleCounts>;
    /// Feed the external watchdog (TPL5010 DONE pulse). Called only from the safety path.
    fn watchdog_kick(&mut self);
    fn buzzer(&mut self, pattern: Buzzer);
    fn battery_mv(&mut self) -> u16;
    /// Monotonic milliseconds since boot.
    fn time_ms(&mut self) -> Millis;
    /// DOCKED input (Hall switch + magnet in the cannula adapter). Default: not docked.
    fn docked(&mut self) -> bool {
        false
    }
    /// Qi / USB charger present. Default: no charger.
    fn charger_present(&mut self) -> bool {
        false
    }
    /// Peak motor supply current (mA) during the last step burst, if the board has a sensor.
    /// Feeds the occlusion detector next to the encoder. Default: no sensor.
    fn motor_current_peak_ma(&mut self) -> Option<u16> {
        None
    }
}
