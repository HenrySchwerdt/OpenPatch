//! Model of the bench controller's hardware motor-supply interlock and the power-up plan the HAL
//! executes. Pure (no hardware), so the ordering and the gate logic are host-tested.
//!
//! Hardware (Rev A, `electronics/bench/INTERLOCK.md`):
//! `MOT_ALLOW = MCU_EN AND LATCH_Q AND OC_OK AND (DOCKED XOR DIR_REVERSE)` (H14: forward only docked, reverse only undocked), `VMOT = VBUS` through the
//! P-FET Q4 while `MOT_ALLOW`. `OC_OK` is the hardware over-current latch (trip about 450 mA, cleared only
//! by cycling `MCU_EN` low).
//! `DIR_REVERSE` is the STSPIN220 DIR line at its REVERSE level, a direct hardware input of the
//! gate. Consequences enforced here and in `openpatch-bench/src/hal/driver.rs`:
//!
//! * a draw (undocked, reverse only) must set DIR = reverse BEFORE MCU_EN is raised, otherwise the
//!   supply never comes up;
//! * a forward step while undocked must never be attempted: the gate would (and must) be open, so
//!   it is a fault, not a retry;
//! * a reverse step while docked is refused too (a docked pod is connected to the cannula);
//! * after every DIR change while powered the supply is checked against this model: missing supply
//!   where the model says ON, or present supply where it says OFF (a gate that does not open), are
//!   both faults; the latter latches the interlock failure in the HAL.
//!
//! The firmware never bypasses the gate; it only checks it.

use crate::hal::{MotorDir, MotorFault};

/// Combinational gate of the supply switch without the over-current leg (`OC_OK` = 1).
pub const fn vmot_expected(latch: bool, mcu_en: bool, docked: bool, dir: MotorDir) -> bool {
    mot_allow(latch, mcu_en, true, docked, matches!(dir, MotorDir::Reverse))
}

/// The complete gate network: every leg in series, the last one is the `DOCKED_H XOR DIR_REV` pair (H14): forward only
/// docked, reverse only undocked, both wrong combinations are cut in hardware.
pub const fn mot_allow(latch_q: bool, mcu_en: bool, oc_ok: bool, docked_h: bool, dir_rev: bool) -> bool {
    latch_q && mcu_en && oc_ok && (docked_h != dir_rev)
}

/// `MOT_DIR` pin level for a direction. `forward_high` is the board polarity (`DIR_FORWARD_HIGH`: `false` with R96
/// fitted, `true` with R97 instead, INTERLOCK.md). The gate input `DIR_REV` is high for REVERSE in both variants.
pub const fn dir_level_high(dir: MotorDir, forward_high: bool) -> bool {
    matches!(dir, MotorDir::Forward) == forward_high
}

/// Why a power-up (or a direction change while powered) is refused before any pin is touched.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum Refusal {
    /// Forward motion requires DOCKED (also: the hardware gate would stay open).
    ForwardWhileUndocked,
    /// Reverse (draw) motion is only for an undocked pod.
    ReverseWhileDocked,
}

/// Direction/dock combinations the firmware accepts.
pub const fn check_request(dir: MotorDir, docked: bool) -> Result<(), Refusal> {
    match (dir, docked) {
        (MotorDir::Forward, false) => Err(Refusal::ForwardWhileUndocked),
        (MotorDir::Reverse, true) => Err(Refusal::ReverseWhileDocked),
        _ => Ok(()),
    }
}

impl From<Refusal> for MotorFault {
    fn from(r: Refusal) -> Self {
        match r {
            Refusal::ForwardWhileUndocked => MotorFault::ForwardWhileUndocked,
            Refusal::ReverseWhileDocked => MotorFault::ReverseWhileDocked,
        }
    }
}

/// One action of the power-up plan, in execution order.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum Step {
    /// Drive DIR to the level of this direction (before the supply gate is requested).
    SetDir(MotorDir),
    /// Release LATCH_CLR_N (open drain).
    ReleaseLatchClear,
    /// MCU_EN high (second series gate).
    McuEnHigh,
    /// One ARM_CLK rising edge: sets the latch.
    ArmEdge,
    /// LATCH_Q_MON must read high.
    CheckLatchSet,
    /// Wait for the supply to settle, then PGATE_MON must show MOT_ALLOW and VMOT_SENSE the supply (the model says ON).
    CheckVmotUp,
    /// OC_OK must still read high (the over-current latch has not tripped).
    CheckOcOk,
    /// STSPIN220 STBY high, release EN/FAULT, wait until it reads high.
    DriverOn,
}

/// The power-up plan for a direction. DIR is ALWAYS the first step: the direction is part of the
/// supply gate, so it has to be right before MCU_EN is requested.
pub const fn power_up_plan(dir: MotorDir) -> [Step; 8] {
    [
        Step::SetDir(dir),
        Step::ReleaseLatchClear,
        Step::McuEnHigh,
        Step::ArmEdge,
        Step::CheckLatchSet,
        Step::CheckVmotUp,
        Step::CheckOcOk,
        Step::DriverOn,
    ]
}

/// Result of comparing the measured supply with the gate model.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum SupplyCheck {
    Ok,
    /// Model says ON, no supply measured (gate stuck open, wiring, DOCK / DIR sense wrong).
    Missing,
    /// Model says OFF, supply measured: the gate did not open. Safety failure.
    Unexpected,
}

/// Compare VMOT_SENSE (mV) with the model. Between `off_max_mv` and `on_min_mv` is neither ON nor
/// OFF: it fails whichever state was expected.
pub const fn check_supply(expected_on: bool, vmot_mv: u32, on_min_mv: u32, off_max_mv: u32) -> SupplyCheck {
    if expected_on {
        if vmot_mv >= on_min_mv {
            SupplyCheck::Ok
        } else {
            SupplyCheck::Missing
        }
    } else if vmot_mv <= off_max_mv {
        SupplyCheck::Ok
    } else {
        SupplyCheck::Unexpected
    }
}

/// Why a power-up (or a direction change while powered) failed.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum PowerError {
    /// A previous power-down could not be verified; no further power-up until reset.
    InterlockFailed,
    /// Direction / dock combination refused before any pin was touched.
    Refused(Refusal),
    /// LATCH_Q_MON did not follow ARM_CLK.
    LatchNotSet,
    /// VMOT_SENSE does not show the supply although the interlock is closed.
    NoSupply,
    /// VMOT present where the gate must be open.
    UnexpectedSupply,
    /// EN/FAULT stayed low (STSPIN220 fault or not ready) or the over-current latch tripped.
    DriverFault,
}

impl PowerError {
    pub fn to_fault(self) -> MotorFault {
        match self {
            PowerError::InterlockFailed => MotorFault::InterlockFailed,
            PowerError::Refused(r) => r.into(),
            PowerError::LatchNotSet | PowerError::NoSupply => MotorFault::SupplyMissing,
            PowerError::UnexpectedSupply => MotorFault::SupplyUnexpected,
            PowerError::DriverFault => MotorFault::Driver,
        }
    }
}

/// Which gate cuts the supply in a power-down. The HAL rotates through the three so a single stuck gate
/// can never hide behind the other one (docs/06-diagnostics.md 3.4).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum Disarm {
    /// `MCU_EN` low only; the latch stays armed until the supply is verified cut.
    McuEnOnly,
    /// `LATCH_CLR_N` low only; `MCU_EN` stays high until the supply is verified cut.
    LatchOnly,
    /// Both at once (the fast path).
    Both,
}

impl Disarm {
    /// The `n`-th power-down uses this mode (round robin).
    pub const fn nth(n: u8) -> Disarm {
        match n % 3 {
            0 => Disarm::McuEnOnly,
            1 => Disarm::LatchOnly,
            _ => Disarm::Both,
        }
    }
}
