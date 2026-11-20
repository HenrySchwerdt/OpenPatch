//! Option bytes the STM32C011 supervisor must carry after provisioning (`electronics/v010/INTERLOCK.md` H, I.7; SPICE report
//! `electronics/v010/cup/sim/REPORT.md` F7). Constants only: the platform shell (not in this repository) and the bench provisioning
//! procedure check the read-back against this table, so a requirement is written down in ONE place next to its neighbours.
//!
//! The register layout (FLASH_OPTR field names and positions) is in the STM32C0 reference manual and is deliberately NOT
//! hard-coded here: the table names the requirement, the shell maps it to bits and verifies the read-back.

/// One option byte requirement.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct OptionRequirement {
    /// Field name as in the reference manual.
    pub field: &'static str,
    /// Required setting, as text (what the provisioning procedure reads back).
    pub required: &'static str,
    /// Why (finding or hazard).
    pub why: &'static str,
}

/// `nBOOT_SEL` = 0: the BOOT0 PIN (not the option bit) selects the system bootloader, so the nRF can re-flash the supervisor through
/// `SUP_BOOT0` / `SUP_NRST` (`rom_bootloader`, `flash_guard`).
pub const NBOOT_SEL: OptionRequirement = OptionRequirement {
    field: "nBOOT_SEL",
    required: "0",
    why: "BOOT0 pin selects the system bootloader (nRF re-flash path)",
};

/// F7: BOR level = highest, BOR enabled. A 3V3 dip of a few ms that stays above a low BOR level does not reset the supervisor or
/// clear the motor enable latch; at the highest level the supervisor resets (and then holds `SUP_PERMIT` low, see
/// `logic::MIN_RESET_HOLDOFF_MS`) before the rail is too low for the gates to be trusted. Recorded next to `nBOOT_SEL` because both are
/// set in the same provisioning step (same FLASH_OPTR word).
pub const BOR_LEVEL_HIGHEST: OptionRequirement = OptionRequirement {
    field: "BOR level (BOR_EN set, BORR_LEV / BORF_LEV)",
    required: "highest",
    why: "F7: a short 3V3 dip must reset the supervisor, not leave the latch set",
};

/// Every option byte requirement of the provisioning step, in the order of the provisioning checklist (`nBOOT_SEL` first, BOR
/// directly after it). Read-out protection level 1 and the independent watchdog are set in the same step (INTERLOCK.md H) and are
/// listed in the documentation, not duplicated here.
pub const PROVISIONING_OPTION_BYTES: [OptionRequirement; 2] = [NBOOT_SEL, BOR_LEVEL_HIGHEST];
