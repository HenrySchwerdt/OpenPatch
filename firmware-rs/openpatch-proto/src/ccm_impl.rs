//! Real AES-128-CCM (RFC 3610) with M = 8, L = 2 via RustCrypto. Feature `aes-ccm`.
//!
//! Key agreement is still an open point of protocol v1 (section 5.2 of the spec): this type takes
//! a ready 16-byte session key. Never log or persist the key in plaintext.

use crate::consts::{CCM_NONCE_LEN, CCM_TAG_LEN};
use crate::session::{Ccm, CcmError};
use aes::Aes128;
use ccm::aead::generic_array::GenericArray;
use ccm::aead::AeadInPlace;
use ccm::consts::{U13, U8};
use ccm::KeyInit;

type Cipher = ccm::Ccm<Aes128, U8, U13>;

pub struct AesCcm {
    cipher: Cipher,
}

impl AesCcm {
    pub fn new(key: &[u8; 16]) -> Self {
        Self { cipher: Cipher::new(GenericArray::from_slice(key)) }
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
            .cipher
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
        self.cipher
            .decrypt_in_place_detached(GenericArray::from_slice(nonce), aad, pt, GenericArray::from_slice(tag))
            .map_err(|_| CcmError)
    }
}
