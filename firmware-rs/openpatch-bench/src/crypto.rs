//! Application layer security: AES-128-CCM session (`openpatch_proto` feature `aes-ccm`).
//!
//! OPEN POINT (protocol section 5.2 / 9.1): the key agreement that yields the session key and the
//! 4 byte nonce salt is not defined in protocol v1. This file isolates it behind
//! [`SessionKeySource`]:
//!
//! * production build (no `dev-plaintext`): [`NoKeyAgreement`], a stub that returns no key. The
//!   `Session` is created with `has_crypto = false` and `allow_plaintext = false`, so EVERY frame is
//!   refused with `AUTH`: a production configured pod cannot be commanded until a key agreement is
//!   defined (same state as the C reference). TODO(stub), see docs/stubs.md.
//! * `dev-plaintext`: [`DevKeySource`] returns a FIXED, PUBLIC development key and accepts plaintext
//!   frames next to encrypted ones. Bench use only. Never ship it, never use it for a person.
use openpatch_proto::ccm_impl::AesCcm;
use openpatch_proto::Session;

pub struct SessionKey {
    pub key: [u8; 16],
    pub salt: [u8; 4],
}

/// Provider of the application layer key + salt (to be replaced by the real key agreement, e.g.
/// ephemeral X25519 + HKDF bound to the BLE bond, per `docs/02-safety.md` H7).
pub trait SessionKeySource {
    fn session_key(&mut self) -> Option<SessionKey>;
    /// Accept unencrypted frames (development only).
    fn allow_plaintext(&self) -> bool;
}

/// Production stub: no key agreement exists yet.
#[cfg_attr(feature = "dev-plaintext", allow(dead_code))]
pub struct NoKeyAgreement;

#[cfg_attr(feature = "dev-plaintext", allow(dead_code))]
impl SessionKeySource for NoKeyAgreement {
    fn session_key(&mut self) -> Option<SessionKey> {
        None // TODO(stub): key agreement (protocol open point)
    }
    fn allow_plaintext(&self) -> bool {
        false
    }
}

/// DEVELOPMENT ONLY. Public key: anybody can read it from this source file.
#[cfg(feature = "dev-plaintext")]
pub struct DevKeySource;

#[cfg(feature = "dev-plaintext")]
impl SessionKeySource for DevKeySource {
    fn session_key(&mut self) -> Option<SessionKey> {
        Some(SessionKey {
            key: *b"OPENPATCH-DEVKEY", // 16 bytes, ASCII
            salt: *b"DEV0",
        })
    }
    fn allow_plaintext(&self) -> bool {
        true
    }
}

#[cfg(feature = "dev-plaintext")]
pub type KeySource = DevKeySource;
#[cfg(not(feature = "dev-plaintext"))]
pub type KeySource = NoKeyAgreement;

pub fn key_source() -> KeySource {
    #[cfg(feature = "dev-plaintext")]
    {
        defmt::warn!("dev-plaintext: plaintext frames and the fixed DEV session key are ACTIVE (bench only)");
        DevKeySource
    }
    #[cfg(not(feature = "dev-plaintext"))]
    {
        NoKeyAgreement
    }
}

pub fn make_session<S: SessionKeySource>(src: &mut S) -> Session<AesCcm> {
    match src.session_key() {
        Some(k) => Session::new(AesCcm::new(&k.key), true, k.salt, src.allow_plaintext()),
        None => {
            defmt::warn!("no session key available: all frames will be refused with AUTH (production stub)");
            Session::new(AesCcm::new(&[0u8; 16]), false, [0; 4], src.allow_plaintext())
        }
    }
}
