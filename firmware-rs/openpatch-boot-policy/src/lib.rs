//! Bootloader policy of the OpenPatch nRF52840 (TEST PROJECT, never worn). Everything that decides whether an image may be installed
//! lives here, host tested; the bootloader binary (`openpatch-bootloader`) only supplies flash access, SHA-512 and Ed25519 (salty).
//!
//! Rules:
//! 1. **Only signed images.** The manifest (format 2, 84 bytes) carries the image length, a security version and the hardware id; the
//!    Ed25519 signature covers SHA-512(`"OPFW2"` || the 20 header bytes || the image), so none of the header fields can be changed
//!    without the key. No key compiled in = nothing is accepted (fail closed).
//! 2. **Verify before swap.** [`verify_pending`] runs on the image in the DFU partition BEFORE the swap is allowed; the only value
//!    that arms a swap is an [`ArmToken`], which only a successful verification produces.
//! 3. **Rollback protection.** The security version must be at least the stored minimum ([`counter`]), kept in a one-way store
//!    (the nRF52840 UICR customer words, bits only go 1 -> 0). The minimum is raised only after a new image was CONFIRMED by the application
//!    (`mark_booted`), so an image that is reverted never raises it ([`counter::bump_after_confirmed_boot`]).
//! 4. **Hardware id.** An image for another board is refused.
//! 5. **DFU transport rules** ([`dfu`]): sequential writes only, size bounded, manifest last, the transport cannot arm anything.
//! 6. **Bootloader write protection** ([`acl`]): before the jump to the application the bootloader code is write- and erase-protected
//!    with the nRF52840 ACL peripheral until the next reset (region arithmetic and policy here, three register writes per region in
//!    the bootloader).
//!
//! The USB DFU class glue (embassy-usb + the DFU class) is behind the `usb-dfu` feature of `openpatch-bootloader` and calls
//! [`dfu::DfuReceiver`]; it is not buildable on the host.
#![no_std]
#![forbid(unsafe_code)]

pub mod acl;
pub mod counter;
pub mod dfu;
pub mod manifest;
pub mod verify;

pub use manifest::{Manifest, ManifestError, HEADER_LEN, HW_ID_CUP_V4, HW_ID_SUP_C011, MANIFEST_LEN, SUP_C011_FLASH_SIZE};
pub use verify::{
    digest_start, signed_digest, verify_image, verify_pending, ArmToken, Digest512, ImageContext, ImageSource, Reject, SigCheck, VerifiedImage,
};
