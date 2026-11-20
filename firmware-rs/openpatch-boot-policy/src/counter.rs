//! Rollback counter in a one-way store (nRF52840 `UICR.CUSTOMER[0..31]`, 32 words, bits only go 1 -> 0 without ERASEALL).
//!
//! Slot `i` holds `!version` once written (an erased word is all ones = version 0). Each slot is written once. Versions in written
//! slots strictly increase; after the first erased slot every later slot must be erased. The minimum acceptable version is the last
//! written one. 32 raises are available in the life of the chip: use a security version per RELEASE that fixes something, not per build.
//! Anything that does not fit this shape is `Corrupt`: the bootloader then refuses updates (fail closed) and still boots the active image.

pub const SLOTS: usize = 32;
/// `UICR.CUSTOMER[0]` address on the nRF52840.
pub const UICR_CUSTOMER_ADDR: u32 = 0x1000_1080;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CounterError {
    Corrupt,
    /// All 32 slots are used.
    Full,
}

/// Minimum acceptable security version (0 = never raised).
pub fn min_version(slots: &[u32; SLOTS]) -> Result<u32, CounterError> {
    let mut last = 0u32;
    let mut erased_seen = false;
    for &w in slots {
        if w == 0xFFFF_FFFF {
            erased_seen = true;
            continue;
        }
        if erased_seen {
            return Err(CounterError::Corrupt); // a written slot after an erased one
        }
        let v = !w;
        if v <= last {
            return Err(CounterError::Corrupt); // not strictly increasing
        }
        last = v;
    }
    Ok(last)
}

/// A one-word flash write: `(slot index, value)`. The value only clears bits of an erased word.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SlotWrite {
    pub slot: usize,
    pub value: u32,
}

/// Plan the raise to `new_version`. `Ok(None)` = nothing to do (already at or above).
pub fn plan_raise(slots: &[u32; SLOTS], new_version: u32) -> Result<Option<SlotWrite>, CounterError> {
    let cur = min_version(slots)?;
    if new_version <= cur {
        return Ok(None);
    }
    match slots.iter().position(|&w| w == 0xFFFF_FFFF) {
        Some(slot) => Ok(Some(SlotWrite { slot, value: !new_version })),
        None => Err(CounterError::Full),
    }
}

/// Called at EVERY boot with the state the bootloader found. Only when the active image was confirmed (`confirmed_boot`: no swap, no
/// revert in progress, the application ran `mark_booted`) is its version allowed to raise the minimum. A trial image, or one that was
/// reverted, never does.
pub fn bump_after_confirmed_boot(
    slots: &[u32; SLOTS],
    confirmed_boot: bool,
    active_version: Option<u32>,
) -> Result<Option<SlotWrite>, CounterError> {
    match (confirmed_boot, active_version) {
        (true, Some(v)) => plan_raise(slots, v),
        _ => Ok(None),
    }
}
