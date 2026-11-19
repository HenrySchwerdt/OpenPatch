//! Real AES-128-CCM (RFC 3610) with M = 8, L = 2 via RustCrypto. Feature `aes-ccm`.
//!
//! [`AesCcm::new`] takes one ready 16-byte key for both directions (development key);
//! [`AesCcm::directional`] takes one key per direction as produced by the session key agreement
//! (`handshake`, protocol v1.1 section 5.2). The key is selected by the nonce direction byte
//! (`nonce[4]`): 0 = phone -> pod commands use the first key, 1 (responses) and 2 (notifications)
//! the second, identically on both ends. Never log or persist keys in plaintext.

use crate::consts::{CCM_NONCE_LEN, CCM_TAG_LEN};
use crate::session::{Ccm, CcmError};
use aes::Aes128;
use ccm::aead::generic_array::GenericArray;
use ccm::aead::AeadInPlace;
use ccm::consts::{U13, U8};
use ccm::KeyInit;

type Cipher = ccm::Ccm<Aes128, U8, U13>;

pub struct AesCcm {
    c2p: Cipher,
    p2c: Cipher,
}

impl AesCcm {
    pub fn new(key: &[u8; 16]) -> Self {
        Self::directional(key, key)
    }

    /// `key_c2p` protects nonce direction 0 (commands), `key_p2c` directions 1 and 2.
    pub fn directional(key_c2p: &[u8; 16], key_p2c: &[u8; 16]) -> Self {
        Self { c2p: Cipher::new(GenericArray::from_slice(key_c2p)), p2c: Cipher::new(GenericArray::from_slice(key_p2c)) }
    }

    fn cipher(&self, nonce: &[u8; CCM_NONCE_LEN]) -> &Cipher {
        if nonce[4] == 0 {
            &self.c2p
        } else {
            &self.p2c
        }
    }
}

impl Ccm for AesCcm {
    fn encrypt(
        &mut self,
        nonce: &[u8; CCM_NONCE_LEN],
        aad: &[u8],
        pt: &[u8],
        ct: &mut [u8],
        tag: &mut [u8; CCM_TAG_LEN],
    ) -> Result<(), CcmError> {
        if ct.len() != pt.len() {
            return Err(CcmError);
        }
        ct.copy_from_slice(pt);
        let t = self
            .cipher(nonce)
            .encrypt_in_place_detached(GenericArray::from_slice(nonce), aad, ct)
            .map_err(|_| CcmError)?;
        tag.copy_from_slice(&t);
        Ok(())
    }

    fn decrypt(
        &mut self,
        nonce: &[u8; CCM_NONCE_LEN],
        aad: &[u8],
        ct: &[u8],
        tag: &[u8; CCM_TAG_LEN],
        pt: &mut [u8],
    ) -> Result<(), CcmError> {
        if ct.len() != pt.len() {
            return Err(CcmError);
        }
        pt.copy_from_slice(ct);
        self.cipher(nonce)
            .decrypt_in_place_detached(GenericArray::from_slice(nonce), aad, pt, GenericArray::from_slice(tag))
            .map_err(|_| CcmError)
    }
}
