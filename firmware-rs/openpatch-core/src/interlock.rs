//! Model of the bench controller's hardware motor-supply interlock and the power-up plan the HAL
//! executes. Pure (no hardware), so the ordering and the gate logic are host-tested.
//!
//! Hardware (decision 2026-11-19, `electronics/bench`):
//! `VMOT = MCU_EN AND TPL5010_LATCH AND (DOCKED OR DIR_REVERSE)`.
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

/// Combinational gate of the supply switch.
pub const fn vmot_expected(latch: bool, mcu_en: bool, docked: bool, dir: MotorDir) -> bool {
    latch && mcu_en && (docked || matches!(dir, MotorDir::Reverse))
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
    /// Release KILL_N (open drain).
    ReleaseKill,
    /// MCU_EN high (second series gate).
    McuEnHigh,
    /// One ARM_CLK rising edge: sets the latch.
    ArmEdge,
    /// LATCH_Q_MON must read high.
    CheckLatchSet,
    /// Wait for the supply to settle, then VMOT_SENSE must show the supply (the model says ON).
    CheckVmotUp,
    /// STSPIN220 STBY high, release EN/FAULT, wait until it reads high.
    DriverOn,
}

/// The power-up plan for a direction. DIR is ALWAYS the first step: the direction is part of the
/// supply gate, so it has to be right before MCU_EN is requested.
pub const fn power_up_plan(dir: MotorDir) -> [Step; 7] {
    [
        Step::SetDir(dir),
        Step::ReleaseKill,
        Step::McuEnHigh,
        Step::ArmEdge,
        Step::CheckLatchSet,
        Step::CheckVmotUp,
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
