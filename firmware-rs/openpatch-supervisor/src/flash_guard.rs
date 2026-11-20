//! The ENFORCED rule for flashing the supervisor: **only while the motor supply is cut** (`INTERLOCK.md` I.4).
//!
//! The nRF may re-flash the supervisor through the ST ROM bootloader. While the supervisor is in its bootloader it controls nothing:
//! `SUP_PERMIT` has a pull-down and the latch is held cleared, so the hardware cut path is open anyway. The rule protects the other
//! direction: a supervisor that is being rewritten must never be the thing that is relied on while the motor can still run. So:
//!
//! 1. **Precondition** ([`check`]): the supply was measured below [`VMOT_MAX_MV`] (0.3 V) for at least [`VMOT_LOW_MIN_MS`] (50 ms), the pod
//!    is NOT docked, no delivery or draw is active, the supervisor image carries a verified signature, and the battery can carry the
//!    update. A missing reading is "supply unknown" and refuses.
//! 2. **No bypass**: there is no function that encodes a flash-modifying frame without a [`FlashSession`], and a session can only be
//!    created by [`FlashSession::begin`], which runs the check. The raw encoders in `rom_bootloader` stay public for tools and tests,
//!    the firmware does not call them directly (the call sites are the methods below).
//! 3. **Continuous**: every frame request carries a FRESH supply reading. A reading above the limit (or none) aborts the session for good
//!    ([`SessionError::SupplyReturned`]); an aborted session produces no further frame, and the caller must run the exit sequence.
//!
//! The session knows nothing about timing or I/O: the HAL reads `VMOT_SENSE` before each frame and passes the value in.

use crate::rom_bootloader::{
    self as bl, address_frame, command_frame, extended_erase_pages, extended_erase_special, read_length_frame, write_data_frame,
    Command, FrameError, SpecialErase,
};

/// The supply counts as cut below this voltage (`VMOT_SENSE` x 2, mV).
pub const VMOT_MAX_MV: u16 = 300;
/// ... when it stayed below it for at least this long (the boost output caps are bled through 10 k / 10 k, time constant about 0.3 s).
pub const VMOT_LOW_MIN_MS: u32 = 50;
/// The cell must hold at least this much (open circuit) so a brown-out cannot interrupt a flash write.
pub const MIN_VBAT_MV: u16 = 3_600;

/// What the main firmware knows when it is asked to update the supervisor.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct Preconditions {
    /// Latest `VMOT_SENSE` reading in mV; `None` = no valid reading.
    pub vmot_mv: Option<u16>,
    /// How long the supply has been continuously below [`VMOT_MAX_MV`], ms.
    pub vmot_low_for_ms: u32,
    pub docked: bool,
    /// A delivery, prime, draw or assisted fill is running or pending.
    pub delivery_active: bool,
    /// The signature of the supervisor image was verified by the main firmware (`openpatch-boot-policy` rules, same key chain).
    pub image_verified: bool,
    pub vbat_mv: u16,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum Refusal {
    /// No reading of the supply: unknown is never "cut".
    SupplyUnknown,
    /// The supply is present (value in mV).
    SupplyPresent(u16),
    /// Below the limit, but not for long enough yet.
    SupplyNotCutLongEnough,
    Docked,
    DeliveryActive,
    ImageNotVerified,
    BatteryLow,
}

/// Evaluate the precondition. The order is the order of severity: supply first.
pub fn check(p: &Preconditions) -> Result<(), Refusal> {
    match p.vmot_mv {
        None => return Err(Refusal::SupplyUnknown),
        Some(v) if v >= VMOT_MAX_MV => return Err(Refusal::SupplyPresent(v)),
        Some(_) => {}
    }
    if p.vmot_low_for_ms < VMOT_LOW_MIN_MS {
        return Err(Refusal::SupplyNotCutLongEnough);
    }
    if p.docked {
        return Err(Refusal::Docked);
    }
    if p.delivery_active {
        return Err(Refusal::DeliveryActive);
    }
    if !p.image_verified {
        return Err(Refusal::ImageNotVerified);
    }
    if p.vbat_mv < MIN_VBAT_MV {
        return Err(Refusal::BatteryLow);
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum SessionError {
    /// The supply came back (or the reading is missing): the session is over.
    SupplyReturned,
    /// The session was aborted earlier; no frame is produced any more.
    Aborted,
    Frame(FrameError),
}

impl From<FrameError> for SessionError {
    fn from(e: FrameError) -> Self {
        SessionError::Frame(e)
    }
}

/// A flashing session. Exists only after [`check`] passed.
#[derive(Debug)]
pub struct FlashSession {
    alive: bool,
    frames: u32,
}

impl FlashSession {
    /// The only constructor.
    pub fn begin(p: &Preconditions) -> Result<FlashSession, Refusal> {
        check(p)?;
        Ok(FlashSession { alive: true, frames: 0 })
    }

    pub fn is_alive(&self) -> bool {
        self.alive
    }

    /// Frames produced so far (diagnostics).
    pub fn frames(&self) -> u32 {
        self.frames
    }

    /// Drop the session (the caller ends the update, or noticed something else): nothing more is produced.
    pub fn abort(&mut self) {
        self.alive = false;
    }

    /// Re-check the supply; every frame method does this first.
    fn gate(&mut self, vmot_mv: Option<u16>) -> Result<(), SessionError> {
        if !self.alive {
            return Err(SessionError::Aborted);
        }
        match vmot_mv {
            Some(v) if v < VMOT_MAX_MV => {
                self.frames = self.frames.wrapping_add(1);
                Ok(())
            }
            _ => {
                self.alive = false;
                Err(SessionError::SupplyReturned)
            }
        }
    }

    /// Frame for a bare command (`Get`, `GetVersion`, `GetId`, `ReadMemory`, `Go`, ...).
    pub fn command(&mut self, vmot_mv: Option<u16>, cmd: Command) -> Result<[u8; 2], SessionError> {
        self.gate(vmot_mv)?;
        Ok(command_frame(cmd))
    }

    pub fn address(&mut self, vmot_mv: Option<u16>, addr: u32) -> Result<[u8; 5], SessionError> {
        self.gate(vmot_mv)?;
        Ok(address_frame(addr))
    }

    pub fn read_length(&mut self, vmot_mv: Option<u16>, n: usize) -> Result<[u8; 2], SessionError> {
        self.gate(vmot_mv)?;
        Ok(read_length_frame(n)?)
    }

    /// The data frame of a write. The address was sent before with [`FlashSession::address`]; here it is validated again so a write
    /// below the flash or unaligned never reaches the wire.
    pub fn write_data(&mut self, vmot_mv: Option<u16>, addr: u32, data: &[u8], out: &mut [u8]) -> Result<usize, SessionError> {
        self.gate(vmot_mv)?;
        bl::check_write_address(addr)?;
        Ok(write_data_frame(data, out)?)
    }

    /// Mass erase payload (after the `ExtendedErase` command frame was acknowledged).
    pub fn erase_all(&mut self, vmot_mv: Option<u16>) -> Result<[u8; 3], SessionError> {
        self.gate(vmot_mv)?;
        Ok(extended_erase_special(SpecialErase::Mass))
    }

    pub fn erase_pages(&mut self, vmot_mv: Option<u16>, pages: &[u16], out: &mut [u8]) -> Result<usize, SessionError> {
        self.gate(vmot_mv)?;
        Ok(extended_erase_pages(pages, out)?)
    }
}
