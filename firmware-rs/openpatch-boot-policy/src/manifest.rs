//! Manifest format 2.
//!
//! ```text
//! 0   magic        u32 LE  "OPFW" (0x5746504F)
//! 4   format       u16 LE  2
//! 6   reserved     u16     must be 0
//! 8   image_len    u32 LE  bytes of the image
//! 12  version      u32 LE  security version (anti-rollback), at least 1
//! 16  hw_id        u32 LE  board the image is for
//! 20  signature    [u8;64] Ed25519 over SHA-512("OPFW2" || bytes 0..20 || image)
//! ```
//! Format 1 (no version, signature over the image only) is refused: it cannot carry rollback protection.

pub const MAGIC: u32 = 0x5746_504F;
pub const FORMAT: u16 = 2;
pub const MANIFEST_LEN: usize = 84;
pub const HEADER_LEN: usize = 20;
pub const DOMAIN: &[u8; 5] = b"OPFW2";
/// Hardware id of the 45-part cup board v4 (nRF52840 HJ-840).
pub const HW_ID_CUP_V4: u32 = 0x0C0F_0004;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Manifest {
    pub image_len: u32,
    pub version: u32,
    pub hw_id: u32,
    pub signature: [u8; 64],
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ManifestError {
    Length,
    Magic,
    /// Format 1 or unknown.
    Format,
    Reserved,
    ZeroLength,
    /// Version 0 is reserved for "never written".
    ZeroVersion,
}

impl Manifest {
    pub fn parse(b: &[u8]) -> Result<Manifest, ManifestError> {
        if b.len() < MANIFEST_LEN {
            return Err(ManifestError::Length);
        }
        let u32_at = |o: usize| u32::from_le_bytes([b[o], b[o + 1], b[o + 2], b[o + 3]]);
        if u32_at(0) != MAGIC {
            return Err(ManifestError::Magic);
        }
        if u16::from_le_bytes([b[4], b[5]]) != FORMAT {
            return Err(ManifestError::Format);
        }
        if b[6] != 0 || b[7] != 0 {
            return Err(ManifestError::Reserved);
        }
        let image_len = u32_at(8);
        if image_len == 0 {
            return Err(ManifestError::ZeroLength);
        }
        let version = u32_at(12);
        if version == 0 {
            return Err(ManifestError::ZeroVersion);
        }
        let mut signature = [0u8; 64];
        signature.copy_from_slice(&b[20..84]);
        Ok(Manifest { image_len, version, hw_id: u32_at(16), signature })
    }

    /// The 20 header bytes that are signed together with the image.
    pub fn header(&self) -> [u8; HEADER_LEN] {
        let mut h = [0u8; HEADER_LEN];
        h[0..4].copy_from_slice(&MAGIC.to_le_bytes());
        h[4..6].copy_from_slice(&FORMAT.to_le_bytes());
        h[8..12].copy_from_slice(&self.image_len.to_le_bytes());
        h[12..16].copy_from_slice(&self.version.to_le_bytes());
        h[16..20].copy_from_slice(&self.hw_id.to_le_bytes());
        h
    }

    pub fn encode(&self) -> [u8; MANIFEST_LEN] {
        let mut m = [0u8; MANIFEST_LEN];
        m[..HEADER_LEN].copy_from_slice(&self.header());
        m[HEADER_LEN..].copy_from_slice(&self.signature);
        m
    }
}
