//! TEST-ONLY fake CCM (port of `firmware/tests/fake_ccm.c`): XOR keystream + FNV-style 8-byte tag.
//! NOT SECURE. Never move this into `src`.
#![allow(dead_code)]

use openpatch_proto::{Ccm, CcmError};

#[derive(Default, Debug)]
pub struct FakeCcm {
    pub accepted_calls: u32,
    pub last_seq: u16,
}

fn keystream_xor(nonce: &[u8; 13], input: &[u8], out: &mut [u8]) {
    for (i, (o, b)) in out.iter_mut().zip(input).enumerate() {
        *o = b ^ nonce[i % 13].wrapping_add(0x5A).wrapping_add(i as u8);
    }
}

fn tag_of(nonce: &[u8; 13], aad: &[u8], ct: &[u8]) -> [u8; 8] {
    let mut h: u64 = 1469598103934665603;
    for &b in nonce.iter().chain(aad).chain(ct) {
        h = (h ^ b as u64).wrapping_mul(1099511628211);
    }
    h.to_le_bytes()
}

impl Ccm for FakeCcm {
    fn encrypt(&mut self, nonce: &[u8; 13], aad: &[u8], pt: &[u8], ct: &mut [u8], tag: &mut [u8; 8]) -> Result<(), CcmError> {
        keystream_xor(nonce, pt, ct);
        *tag = tag_of(nonce, aad, ct);
        Ok(())
    }
    fn decrypt(&mut self, nonce: &[u8; 13], aad: &[u8], ct: &[u8], tag: &[u8; 8], pt: &mut [u8]) -> Result<(), CcmError> {
        if tag_of(nonce, aad, ct) != *tag {
            return Err(CcmError);
        }
        keystream_xor(nonce, ct, pt);
        Ok(())
    }
    fn on_seq_accepted(&mut self, seq: u16) {
        self.accepted_calls += 1;
        self.last_seq = seq;
    }
}

/// Backend whose every operation fails (C: `op_ccm_ops_t` with NULL function pointers).
pub struct BrokenCcm;

impl Ccm for BrokenCcm {
    fn encrypt(&mut self, _: &[u8; 13], _: &[u8], _: &[u8], _: &mut [u8], _: &mut [u8; 8]) -> Result<(), CcmError> {
        Err(CcmError)
    }
    fn decrypt(&mut self, _: &[u8; 13], _: &[u8], _: &[u8], _: &[u8; 8], _: &mut [u8]) -> Result<(), CcmError> {
        Err(CcmError)
    }
}
