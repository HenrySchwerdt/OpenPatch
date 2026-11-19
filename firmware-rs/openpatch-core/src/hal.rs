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
    /// Reverse (draw) step rate for the following draw, pulses per second. The core derives it from the fill needle gauge
    /// (`limits::draw_pps`: <= 600 pps default, lower for fine needles); the HAL clamps it to its own hard cap
    /// (1000 pps). Default: the HAL keeps its compile-time rate.
    fn set_draw_rate_pps(&mut self, _pps: u32) {}
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

    // ---- diagnostics (docs/06-diagnostics.md 5.1): additive, every method has a no-op default so
    // mocks, the DK, the simulator and the differential tests keep compiling and behaving the same
    // until they opt in. ----

    /// Drains one fault the HAL detected on its own (as data). Polled by `Pump::tick()` after
    /// every burst. The HAL never decides policy; the core raises the record and decides.
    fn take_diag(&mut self) -> Option<DiagEvent> {
        None
    }
    /// A step burst with everything the HAL measured. Default: `motor_step` and nothing else known
    /// (the core then still asks `motor_fault` / `motor_current_peak_ma` as before).
    fn motor_step_ex(&mut self, steps: Pulses) -> StepResult {
        StepResult { executed: self.motor_step(steps), drv_fault: false, peak_ma: None, vmot_ok: true }
    }
    /// Interlock readbacks RB1..RB10 for the POST and the idle-tick checks. Default: none.
    fn interlock_state(&mut self) -> Option<InterlockReadback> {
        None
    }
    /// A self-test step that needs pin-level control. The core only calls it while SUSPENDED.
    /// Default: unsupported (the proof stays UNKNOWN, never OK).
    fn selftest(&mut self, _step: SelfTestStep) -> SelfTestOutcome {
        SelfTestOutcome::Unsupported
    }
    /// Why the MCU started (retained across the reset). Default: power on.
    fn reset_cause(&mut self) -> ResetCause {
        ResetCause::PowerOn
    }
    /// Retained-RAM breadcrumb of the last task state before a reset. Default: 0.
    fn breadcrumb(&mut self) -> u32 {
        0
    }
    /// Stable identity of the pod (nRF `FICR.DEVICEID`), 0 = unknown (then `POD_UID` is not reported).
    fn pod_uid(&mut self) -> u64 {
        0
    }
}

/// A fault the HAL detected on its own, reported as data (see [`Hal::take_diag`]).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct DiagEvent {
    pub code: crate::diag::DiagCode,
    pub ctx_a: i32,
    pub ctx_b: i32,
    pub ctx_c: u32,
}

/// Result of a step burst with everything the HAL measured.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct StepResult {
    pub executed: Pulses,
    /// STSPIN220 EN/FAULT asserted during the burst.
    pub drv_fault: bool,
    pub peak_ma: Option<u16>,
    /// The motor supply was verified present for the burst.
    pub vmot_ok: bool,
}

/// Snapshot of the interlock readbacks RB1..RB10 (docs/06-diagnostics.md 3.1). `None` = this board
/// does not have the signal: the proof is then UNKNOWN, never OK.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct InterlockReadback {
    /// RB1 P-FET gate level.
    pub pgate: Option<bool>,
    /// RB2 and RB3 gate chain midpoints.
    pub pg_mid1: Option<bool>,
    pub pg_mid2: Option<bool>,
    /// RB4 dock input after the inverter.
    pub docked_h: Option<bool>,
    /// RB5 DIR_REV level.
    pub dir_rev: Option<bool>,
    /// RB6 latch output.
    pub latch_q: Option<bool>,
    /// RB7 motor supply in mV.
    pub vmot_mv: Option<u16>,
    /// RB8 current sense in mV.
    pub i_sense_mv: Option<u16>,
    /// RB9 own-pin readback: a set bit means that output reads back differently from what was driven.
    pub own_pin_mismatch: u8,
    /// RB10 `EN/FAULT` low.
    pub driver_fault: Option<bool>,
    /// `OC_OK`: the hardware over-current latch has not tripped.
    pub oc_ok: Option<bool>,
    /// The composite `MOT_ALLOW` (`PGATE_MON` low): the supply switch is on.
    pub mot_allow: Option<bool>,
    /// `POD_ID_N` low: pod board present, FFC intact.
    pub pod_present: Option<bool>,
}

/// Steps of the self-test whose proof needs pin-level control (the core owns the sequencing, the
/// HAL owns the pins).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum SelfTestStep {
    /// A01: each gate can cut the supply, one at a time.
    GateCut,
    /// A02: the DOCKED and DIR_REV gates block (undocked only).
    DockGateBlock,
    /// A08: the watchdog is effective (service command, resets the MCU).
    WatchdogProof,
    /// A12: the over-current leg (comparator, latch, supply switch) cuts the supply when the test pin lowers the
    /// reference, and the latch clears only by cycling MCU_EN. Needs the motor connected (holding current).
    OverCurrentCut,
    /// S05..S08, S10: passive readbacks at idle (supply absent, latch clear, gate closed, own pins, rails, FFC / pod,
    /// dock path consistency). The motor is never driven.
    PassiveChecks,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum SelfTestOutcome {
    /// The board cannot do this proof: it stays UNKNOWN (never OK).
    Unsupported,
    Passed,
    /// Failed with this diagnostic code (the HAL's own code).
    Failed(crate::diag::DiagCode),
}

/// Why the MCU started (`RESETREAS`).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum ResetCause {
    #[default]
    PowerOn,
    /// Commanded soft reset (DFU, service command).
    Commanded,
    Watchdog,
    Brownout,
    Lockup,
    /// Any other unexpected reset (pin, soft, unknown).
    Other,
}
