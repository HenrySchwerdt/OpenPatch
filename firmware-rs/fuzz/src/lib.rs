//! Shared helpers of the fuzz targets. TEST PROJECT, not a medical device.
//!
//! `manifest` MIRRORS the manifest check of `openpatch-bootloader/src/main.rs::check_pending` (that crate is a
//! `no_std` binary and cannot be linked from here). Keep it identical; proposal security/proposals/04 asks for the
//! parser to move into a small library crate so this mirror disappears and the REAL code is fuzzed.
#![allow(dead_code)]

#[path = "../../layout/layout.rs"]
pub mod layout;

pub mod manifest {
    use super::layout;
    use ed25519_dalek::{Signature, Verifier, VerifyingKey};
    use sha2::{Digest, Sha512};

    /// `magic u32 | format u16 | reserved u16 | image_len u32 | signature [u8; 64]` (76 bytes, little endian).
    /// `None` = the bootloader would classify the pending update as Invalid.
    pub fn parse(m: &[u8]) -> Option<(u32, [u8; 64])> {
        if m.len() < layout::MANIFEST_LEN {
            return None;
        }
        let magic = u32::from_le_bytes([m[0], m[1], m[2], m[3]]);
        let len = u32::from_le_bytes([m[8], m[9], m[10], m[11]]);
        if magic != layout::MANIFEST_MAGIC || len == 0 || len > layout::APP_SIZE {
            return None;
        }
        let mut sig = [0u8; 64];
        sig.copy_from_slice(&m[12..76]);
        Some((len, sig))
    }

    /// Ed25519 over the SHA-512 digest of `image[..len]` (docs/bootloader.md "Signing scheme").
    pub fn verify(pk: &[u8; 32], image: &[u8], len: u32, sig: &[u8; 64]) -> bool {
        if len as usize > image.len() {
            return false; // the bootloader would read erased flash (0xFF) here; the model needs bytes
        }
        let digest = Sha512::digest(&image[..len as usize]);
        let Ok(vk) = VerifyingKey::from_bytes(pk) else { return false };
        vk.verify(&digest, &Signature::from_bytes(sig)).is_ok()
    }

    pub fn build(seed: &[u8; 32], image: &[u8]) -> Vec<u8> {
        use ed25519_dalek::{Signer, SigningKey};
        let sk = SigningKey::from_bytes(seed);
        let digest = Sha512::digest(image);
        let sig = sk.sign(&digest);
        let mut m = Vec::with_capacity(layout::MANIFEST_LEN);
        m.extend_from_slice(&layout::MANIFEST_MAGIC.to_le_bytes());
        m.extend_from_slice(&layout::MANIFEST_VERSION.to_le_bytes());
        m.extend_from_slice(&[0, 0]);
        m.extend_from_slice(&(image.len() as u32).to_le_bytes());
        m.extend_from_slice(&sig.to_bytes());
        m
    }

    pub fn public(seed: &[u8; 32]) -> [u8; 32] {
        use ed25519_dalek::SigningKey;
        SigningKey::from_bytes(seed).verifying_key().to_bytes()
    }
}

/// Deterministic xorshift RNG for the handshake targets (NOT for production).
#[cfg(feature = "handshake")]
pub struct Det(pub u64);

#[cfg(feature = "handshake")]
impl rand_core::RngCore for Det {
    fn next_u32(&mut self) -> u32 {
        self.next_u64() as u32
    }
    fn next_u64(&mut self) -> u64 {
        self.0 ^= self.0 >> 12;
        self.0 ^= self.0 << 25;
        self.0 ^= self.0 >> 27;
        self.0.wrapping_mul(0x2545F4914F6CDD1D)
    }
    fn fill_bytes(&mut self, d: &mut [u8]) {
        for c in d.chunks_mut(8) {
            let b = self.next_u64().to_le_bytes();
            c.copy_from_slice(&b[..c.len()]);
        }
    }
    fn try_fill_bytes(&mut self, d: &mut [u8]) -> Result<(), rand_core::Error> {
        self.fill_bytes(d);
        Ok(())
    }
}
