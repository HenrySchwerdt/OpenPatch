//! Application layer security: AES-128-CCM session (`openpatch_proto` feature `aes-ccm`) whose keys
//! come from the per-connection key agreement (`openpatch_proto::handshake`, protocol v1.1 section
//! 5.2, `docs/04-protocol.md`).
//!
//! * production build (no `dev-plaintext`): a connection starts WITHOUT session keys
//!   ([`HandshakeKeySource`] with no keys): every non-handshake frame is refused with `AUTH`. The
//!   BLE task runs the handshake (`ble/mod.rs`: pairing inside the pairing window, session once per
//!   connection) and hands the derived keys over through `SESSION_EVT`; [`apply_session_event`] then
//!   swaps in a `Session` that uses them. When the link closes the session is replaced by the
//!   key-less one again, so keys never outlive a connection. Plaintext is never accepted.
//! * `dev-plaintext`: [`DevKeySource`] returns a FIXED, PUBLIC development key and accepts plaintext
//!   frames next to encrypted ones. Bench use only. Never ship it, never use it for a person.
//!   Behaviour is unchanged: a phone that never runs the handshake sees exactly the old pod. A phone
//!   that does run it gets a negotiated session (plaintext still accepted) for that connection.
use openpatch_proto::ccm_impl::AesCcm;
use openpatch_proto::handshake::SessionKeys;
use openpatch_proto::Session;

use crate::shared::{SessionEvent, SESSION_EVT};

#[derive(Clone)]
pub struct SessionKey {
    /// phone -> pod (nonce direction 0).
    pub key_c2p: [u8; 16],
    /// pod -> phone (nonce directions 1 and 2).
    pub key_p2c: [u8; 16],
    pub salt: [u8; 4],
}

impl From<SessionKeys> for SessionKey {
    fn from(k: SessionKeys) -> Self {
        SessionKey { key_c2p: k.key_c2p, key_p2c: k.key_p2c, salt: k.salt }
    }
}

/// Provider of the application layer keys + salt of the current connection.
pub trait SessionKeySource {
    fn session_key(&mut self) -> Option<SessionKey>;
    /// Accept unencrypted frames (development only).
    fn allow_plaintext(&self) -> bool;
}

/// Production: the keys of the handshake that completed on this connection, or none yet.
pub struct HandshakeKeySource {
    keys: Option<SessionKey>,
    allow_plaintext: bool,
}

impl HandshakeKeySource {
    /// No keys yet (connection start): every frame outside the handshake is refused.
    #[cfg_attr(feature = "dev-plaintext", allow(dead_code))]
    pub fn none() -> Self {
        Self { keys: None, allow_plaintext: false }
    }

    /// Keys of a completed handshake. `allow_plaintext` is only ever true in `dev-plaintext` builds.
    pub fn negotiated(keys: SessionKeys) -> Self {
        Self { keys: Some(keys.into()), allow_plaintext: cfg!(feature = "dev-plaintext") }
    }
}

impl SessionKeySource for HandshakeKeySource {
    fn session_key(&mut self) -> Option<SessionKey> {
        self.keys.clone()
    }
    fn allow_plaintext(&self) -> bool {
        self.allow_plaintext
    }
}

/// DEVELOPMENT ONLY. Public key: anybody can read it from this source file.
#[cfg(feature = "dev-plaintext")]
pub struct DevKeySource;

#[cfg(feature = "dev-plaintext")]
impl SessionKeySource for DevKeySource {
    fn session_key(&mut self) -> Option<SessionKey> {
        Some(SessionKey {
            key_c2p: *b"OPENPATCH-DEVKEY", // 16 bytes, ASCII
            key_p2c: *b"OPENPATCH-DEVKEY",
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
pub type KeySource = HandshakeKeySource;

/// The key source of a fresh boot (no handshake yet).
pub fn key_source() -> KeySource {
    #[cfg(feature = "dev-plaintext")]
    {
        defmt::warn!("dev-plaintext: plaintext frames and the fixed DEV session key are ACTIVE (bench only)");
        DevKeySource
    }
    #[cfg(not(feature = "dev-plaintext"))]
    {
        HandshakeKeySource::none()
    }
}

pub fn make_session<S: SessionKeySource>(src: &mut S) -> Session<AesCcm> {
    match src.session_key() {
        Some(k) => Session::new(AesCcm::directional(&k.key_c2p, &k.key_p2c), true, k.salt, src.allow_plaintext()),
        None => {
            defmt::debug!("no session keys yet: frames outside the handshake are refused with AUTH");
            Session::new(AesCcm::new(&[0u8; 16]), false, [0; 4], src.allow_plaintext())
        }
    }
}

/// Called by the safety task before it looks at anything else in a loop iteration: install the
/// session of a finished handshake, or drop back to the key-less session after the link closed.
pub fn apply_session_event(session: &mut Session<AesCcm>) {
    match SESSION_EVT.try_take() {
        None => {}
        Some(SessionEvent::Up(keys)) => {
            defmt::info!("session keys installed (new connection session, seq space restarts)");
            *session = make_session(&mut HandshakeKeySource::negotiated(keys));
        }
        Some(SessionEvent::Reset) => {
            defmt::info!("link closed: session keys erased");
            #[cfg(feature = "dev-plaintext")]
            {
                *session = make_session(&mut DevKeySource); // back to the fixed dev key + plaintext
            }
            #[cfg(not(feature = "dev-plaintext"))]
            {
                *session = make_session(&mut HandshakeKeySource::none());
            }
        }
    }
}
