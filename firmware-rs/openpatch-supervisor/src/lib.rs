//! OpenPatch supervisor (STM32C011F4U6) logic. TEST PROJECT: not a medical device, never to be worn (`DISCLAIMER.md`).
//!
//! The supervisor is the independent second opinion on the cup board v4 (`electronics/v010/INTERLOCK.md` H, I.5 to I.7). It watches
//! the two PHASE lines of the motor driver and the step budget (HW-A) and controls the permit line `SUP_PERMIT`:
//!
//! ```text
//! motor supply = LATCH_Q AND SUP_PERMIT AND NOT(DOCK_N AND MOT_FWD)       (hardware, one AND/NAND chain on the TPS2553 enable)
//! ```
//!
//! This crate is the platform independent part, host tested (no registers, no interrupts, no clock of its own, no alloc, no unsafe):
//!
//! * [`phase`]: step counting from the PHASE edges. One full step toggles exactly ONE of `APHASE` / `BPHASE`
//!   (sequence (A,B) = 00, 10, 11, 01), so steps are the transitions of A plus those of B, and the direction is the order of the
//!   transitions. Anything else (both lines at once, a repeated state) is a sequence error.
//! * [`logic`]: the state machine (`BOOT`, `IDLE`, `ARMED`, `DEAD`, `FAULT`, `LOCKED`): arm window and step budget, permit drop,
//!   latch on fault, reset / brown-out permit hold-off of at least 10 ms (F7), leaky buckets, direction / dock consistency (including the H15 vector: docked + reverse), over-current lock-out.
//! * [`rom_bootloader`]: the frame encoder and response parser of the STM32 UART system bootloader (AN3155), used by the nRF to
//!   re-flash the supervisor.
//! * [`flash_guard`]: the ENFORCED precondition for that: the motor supply must be cut (VMOT below 0.3 V for 50 ms, undocked, no
//!   delivery, image verified). A [`flash_guard::FlashSession`] is the only way to obtain a write / erase frame, and it dies the moment
//!   the supply comes back.
//!
//! The platform binary (STM32C0 HAL: EXTI on the PHASE / `MCU_EN` / `DOCK_N` / `MOT_FWD` / `OC_OK` pins, a 1 kHz tick, `SUP_PERMIT`
//! and `SUP_OK` outputs, IWDG, TPL5010 DONE) is a thin shell around [`logic::Supervisor`] and is NOT in this repository yet (hardware
//! item, no STM32C0 target build is possible here).
#![no_std]
#![forbid(unsafe_code)]

pub mod flash_guard;
pub mod logic;
pub mod phase;
pub mod provisioning;
pub mod rom_bootloader;
#[cfg(test)]
mod rom_bootloader_tests;
pub mod status;

// Platform shell requirements (not testable on the host, recorded here so they are not lost):
// * the supervisor idles in STOP mode on LPTIM / LSI and wakes on the EXTI edges and a coarse LPTIM tick (power budget); the
//   `tick()` calls need only be as frequent as the shortest deadline (window end 600 ms, dead time 400 ms), not 1 kHz;
// * provisioning sets the option byte nBOOT_SEL = 0 so that the BOOT0 PIN (not the option bit) selects the system bootloader, AND
//   the BOR level to the HIGHEST setting (F7, `provisioning::PROVISIONING_OPTION_BYTES`); after any reset or brown-out the shell
//   starts the supervisor through `Supervisor::new` (or calls `on_brown_out`), which holds `SUP_PERMIT` low for >= 10 ms;
// * the nRF drives `SUP_NRST` OPEN DRAIN only, never push-pull high;
// * `MCU_EN` is a hardware leg of the motor enable now (3-input AND LATCH_Q & SUP_PERMIT & MCU_EN): the supervisor still treats MCU_EN
//   low as the normal end of a burst (permit drops, no fault).
