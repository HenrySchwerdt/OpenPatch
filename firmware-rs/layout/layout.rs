//! Flash / RAM layout of the OpenPatch nRF52840 firmware (1 MB flash, 256 KB RAM).
//!
//! SINGLE SOURCE OF TRUTH. Included by path from:
//! * `openpatch-bootloader/build.rs` and `openpatch-bench/build.rs` (generate `memory.x`),
//! * `openpatch-bench/src/layout.rs` (runtime constants for storage / DFU / manifest).
//!
//! ```text
//! 0x000000  BOOTLOADER        32 KB   embassy-boot-nrf, verifies the ed25519 manifest before a swap
//! 0x008000  BOOTLOADER_STATE   4 KB   embassy-boot swap state (magic + progress)
//! 0x009000  ACTIVE           476 KB   application (vector table first) + MANIFEST page at its end
//! 0x080000  DFU              480 KB   ACTIVE + one spare page (embassy-boot swap scratch page)
//! 0x0F8000  STORAGE           32 KB   settings (sequential-storage map): seq ceiling, event ceiling,
//!                                     reservoir, drive calibration, pod state, BLE bonds
//! ```
//!
//! The last page of the ACTIVE window is the MANIFEST page (magic, image length, ed25519 signature
//! over the SHA-512 digest of the image). It is part of the swapped range, so the manifest of the
//! image sits at the same relative offset in DFU and in ACTIVE. The application linker region
//! therefore ends one page before the end of ACTIVE.
#![allow(dead_code)]

pub const PAGE: u32 = 0x1000;

pub const BOOTLOADER_START: u32 = 0x0000_0000;
pub const BOOTLOADER_SIZE: u32 = 0x8000;

pub const STATE_START: u32 = BOOTLOADER_START + BOOTLOADER_SIZE;
pub const STATE_SIZE: u32 = PAGE;

pub const ACTIVE_START: u32 = STATE_START + STATE_SIZE;
pub const ACTIVE_SIZE: u32 = 0x77000;

pub const MANIFEST_SIZE: u32 = PAGE;
/// Linker region of the application (ACTIVE minus the manifest page).
pub const APP_SIZE: u32 = ACTIVE_SIZE - MANIFEST_SIZE;
/// Offset of the manifest page inside ACTIVE / DFU.
pub const MANIFEST_OFFSET: u32 = APP_SIZE;

pub const DFU_START: u32 = ACTIVE_START + ACTIVE_SIZE;
pub const DFU_SIZE: u32 = ACTIVE_SIZE + PAGE;

pub const STORAGE_START: u32 = DFU_START + DFU_SIZE;
pub const STORAGE_SIZE: u32 = 0x8000;

pub const FLASH_SIZE: u32 = 0x10_0000;
pub const RAM_START: u32 = 0x2000_0000;
pub const RAM_SIZE: u32 = 0x4_0000;

const _: () = assert!(STORAGE_START + STORAGE_SIZE == FLASH_SIZE, "layout must fill the flash exactly");
const _: () = assert!(ACTIVE_START % PAGE == 0 && DFU_START % PAGE == 0 && STORAGE_START % PAGE == 0);
const _: () = assert!(DFU_SIZE == ACTIVE_SIZE + PAGE, "embassy-boot needs DFU = ACTIVE + one page");

/// Magic of the manifest page ("OPFW").
pub const MANIFEST_MAGIC: u32 = 0x5746_504F;
/// Manifest FORMAT 2 (`openpatch-boot-policy`): format 1 had no security version and is refused.
pub const MANIFEST_VERSION: u16 = 2;
/// Manifest page layout (little endian): magic u32, format u16, reserved u16, image_len u32, security version u32, hw_id u32,
/// signature [u8; 64] = 84 bytes, rest of the page is 0xFF. The signature covers SHA-512("OPFW2" || header[0..20] || image).
pub const MANIFEST_LEN: usize = 84;
/// Hardware id of the cup board v4 (same value as `openpatch_boot_policy::HW_ID_CUP_V4`).
pub const HW_ID: u32 = 0x0C0F_0004;
/// `UICR.CUSTOMER[0..32]`: the one-way rollback store (`openpatch_boot_policy::counter`).
pub const UICR_CUSTOMER: u32 = 0x1000_1080;

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Target {
    Bootloader,
    App,
}

/// `memory.x` for the given target (build scripts only).
#[cfg(not(target_os = "none"))]
pub fn memory_x(target: Target) -> String {
    let (flash_origin, flash_len) = match target {
        Target::Bootloader => (BOOTLOADER_START, BOOTLOADER_SIZE),
        Target::App => (ACTIVE_START, APP_SIZE),
    };
    format!(
        "/* generated from firmware-rs/layout/layout.rs, do not edit */\n\
         MEMORY\n{{\n\
         \x20 FLASH : ORIGIN = 0x{flash_origin:08X}, LENGTH = {flash_len}\n\
         \x20 RAM   : ORIGIN = 0x{RAM_START:08X}, LENGTH = {RAM_SIZE}\n\
         }}\n\
         __bootloader_state_start = 0x{STATE_START:08X};\n\
         __bootloader_state_end   = 0x{state_end:08X};\n\
         __bootloader_active_start = 0x{ACTIVE_START:08X};\n\
         __bootloader_active_end   = 0x{active_end:08X};\n\
         __bootloader_dfu_start = 0x{DFU_START:08X};\n\
         __bootloader_dfu_end   = 0x{dfu_end:08X};\n\
         __storage_start = 0x{STORAGE_START:08X};\n\
         __storage_end   = 0x{storage_end:08X};\n",
        state_end = STATE_START + STATE_SIZE,
        active_end = ACTIVE_START + ACTIVE_SIZE,
        dfu_end = DFU_START + DFU_SIZE,
        storage_end = STORAGE_START + STORAGE_SIZE,
    )
}
