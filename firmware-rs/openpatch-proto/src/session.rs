//! Session: replay protection, AES-CCM hook, frame sealing/opening.
//!
//! Sequence rules: command `seq` must strictly increase (gaps allowed); state advances only after
//! successful authentication; `seq == 0xFFFF` is reserved, from `0xFFFE` on a rekey is needed.

use crate::consts::*;
use crate::error::Error;
use crate::frame::{decode_frame, encode_frame, Frame};
use crate::crc::crc16_ccitt_false;

/// Authenticated-encryption failure (tag mismatch or backend error).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CcmError;

/// AES-128-CCM backend (M = 8, L = 2, 13-byte nonce). Real implementation: [`crate::ccm_impl`]
/// (feature `aes-ccm`). An insecure test dummy must never be linked into firmware.
pub trait Ccm {
    /// `ct.len() == pt.len()`; writes the 8-byte tag.
    fn encrypt(
        &mut self,
        nonce: &[u8; CCM_NONCE_LEN],
        aad: &[u8],
        pt: &[u8],
        ct: &mut [u8],
        tag: &mut [u8; CCM_TAG_LEN],
    ) -> Result<(), CcmError>;

    /// `pt.len() == ct.len()`; verifies the tag.
    fn decrypt(
        &mut self,
        nonce: &[u8; CCM_NONCE_LEN],
        aad: &[u8],
        ct: &[u8],
        tag: &[u8; CCM_TAG_LEN],
        pt: &mut [u8],
    ) -> Result<(), CcmError>;

    /// Replay hook: persist the highest accepted sequence number (optional).
    fn on_seq_accepted(&mut self, _seq: u16) {}
}

/// "No crypto available": every encrypted frame is refused with `Auth`.
#[derive(Clone, Copy, Debug, Default)]
pub struct NoCrypto;

impl Ccm for NoCrypto {
    fn encrypt(&mut self, _: &[u8; CCM_NONCE_LEN], _: &[u8], _: &[u8], _: &mut [u8], _: &mut [u8; CCM_TAG_LEN]) -> Result<(), CcmError> {
        Err(CcmError)
    }
    fn decrypt(&mut self, _: &[u8; CCM_NONCE_LEN], _: &[u8], _: &[u8], _: &[u8; CCM_TAG_LEN], _: &mut [u8]) -> Result<(), CcmError> {
        Err(CcmError)
    }
}

/// Which end of the link a [`Session`] is. The receive direction is FIXED by the role, never taken from
/// the (attacker-controlled) frame header: a pod only accepts phone->pod command frames (nonce direction
/// 0), a phone only accepts pod->phone responses (1) and notifications (2). A frame of the wrong
/// direction is refused before decryption, replay state or any heartbeat is touched (FINDING-001: a
/// reflected pod response used to authenticate on the pod and caused AES-CCM nonce reuse).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LinkRole {
    Pod,
    Phone,
}

pub struct Session<C: Ccm> {
    role: LinkRole,
    ccm: C,
    has_crypto: bool,
    allow_plaintext: bool,
    salt: [u8; 4],
    rx_seen: bool,
    last_rx_seq: u16,
}

/// An opened (verified, replay-checked, decrypted) command frame.
#[derive(Clone, Copy, Debug)]
pub struct Opened<'a> {
    pub type_: u8,
    pub flags: u8,
    pub seq: u16,
    pub payload: &'a [u8],
}

impl<C: Ccm> Session<C> {
    /// A POD-side session (the default: all firmware uses it). `has_crypto = false` behaves like a NULL
    /// `ccm` in the C reference (encrypted frames: `Auth`). The phone side uses [`Session::with_role`].
    pub fn new(ccm: C, has_crypto: bool, salt: [u8; 4], allow_plaintext: bool) -> Self {
        Self { role: LinkRole::Pod, ccm, has_crypto, allow_plaintext, salt, rx_seen: false, last_rx_seq: 0 }
    }

    /// The same session for the other end of the link.
    pub fn with_role(mut self, role: LinkRole) -> Self {
        self.role = role;
        self
    }

    pub fn role(&self) -> LinkRole {
        self.role
    }

    pub fn ccm(&self) -> &C {
        &self.ccm
    }
    pub fn ccm_mut(&mut self) -> &mut C {
        &mut self.ccm
    }
    pub fn last_rx_seq(&self) -> u16 {
        self.last_rx_seq
    }
    pub fn rx_seen(&self) -> bool {
        self.rx_seen
    }
    pub fn set_salt(&mut self, salt: [u8; 4]) {
        self.salt = salt;
    }

    /// Boot: restore the persisted highest accepted seq (replay protection across restarts).
    pub fn restore_last_seq(&mut self, seq: u16) {
        self.rx_seen = true;
        self.last_rx_seq = seq;
    }

    /// Nonce: `salt(4) | dir(1: 0 cmd, 1 rsp, 2 notification) | seq u16 LE | 6 zero bytes`.
    pub fn nonce(&self, response: bool, seq: u16) -> [u8; CCM_NONCE_LEN] {
        self.nonce_dir(response as u8, seq)
    }

    fn nonce_dir(&self, dir: u8, seq: u16) -> [u8; CCM_NONCE_LEN] {
        let mut n = [0u8; CCM_NONCE_LEN];
        n[..4].copy_from_slice(&self.salt);
        n[4] = dir;
        n[5..7].copy_from_slice(&seq.to_le_bytes());
        n
    }

    /// Validate, replay-check and decrypt an inbound frame. The payload borrows from `plain`
    /// (encrypted) or `input` (plaintext). Sequence state advances only on success.
    ///
    /// The direction is decided by the ROLE: a pod accepts only command frames (no RESPONSE flag,
    /// nonce direction 0, strict replay check), a phone only responses (direction 1) and notifications
    /// (type [`notify::FRAME_TYPE`], direction 2). Anything else is `Error::Frame`, before the key is used.
    pub fn open<'a>(&mut self, input: &'a [u8], plain: &'a mut [u8]) -> Result<Opened<'a>, Error> {
        let f = decode_frame(input)?;
        let is_response = f.flags & FLAG_RESPONSE != 0;
        let dir = match (self.role, is_response) {
            (LinkRole::Pod, false) => 0u8,
            (LinkRole::Phone, true) => {
                if f.type_ == notify::FRAME_TYPE {
                    2
                } else {
                    1
                }
            }
            _ => return Err(Error::Frame), // wrong direction for this end: refused before anything else
        };

        let payload: &'a [u8] = if f.flags & FLAG_ENCRYPTED != 0 {
            if !self.has_crypto {
                return Err(Error::Auth);
            }
            if f.payload.len() < CCM_TAG_LEN {
                return Err(Error::Frame);
            }
            let ct_len = f.payload.len() - CCM_TAG_LEN;
            if ct_len > plain.len() {
                return Err(Error::TooLarge);
            }
            let nonce = self.nonce_dir(dir, f.seq);
            let mut tag = [0u8; CCM_TAG_LEN];
            tag.copy_from_slice(&f.payload[ct_len..]);
            self.ccm
                .decrypt(&nonce, &input[..FRAME_HEADER], &f.payload[..ct_len], &tag, &mut plain[..ct_len])
                .map_err(|_| Error::Auth)?;
            &plain[..ct_len]
        } else if !self.allow_plaintext {
            return Err(Error::Auth);
        } else {
            f.payload
        };

        if self.role == LinkRole::Pod {
            if self.rx_seen && f.seq <= self.last_rx_seq {
                return Err(Error::Replay);
            }
            if f.seq > SEQ_MAX {
                return Err(Error::Session);
            }
            self.rx_seen = true;
            self.last_rx_seq = f.seq;
            if self.has_crypto {
                self.ccm.on_seq_accepted(f.seq);
            }
        }
        Ok(Opened { type_: f.type_, flags: f.flags, seq: f.seq, payload })
    }

    /// Build a (possibly encrypted) frame. `response` selects the nonce direction and the
    /// RESPONSE flag; responses echo the command's `seq`.
    pub fn seal(
        &mut self,
        response: bool,
        type_: u8,
        seq: u16,
        encrypt: bool,
        payload: &[u8],
        out: &mut [u8],
    ) -> Result<usize, Error> {
        self.seal_dir(response as u8, type_, seq, encrypt, payload, out)
    }

    /// Unsolicited notification (Alert characteristic): RESPONSE flag set, nonce direction 2 so a
    /// notification can never reuse the nonce of a command echo. `seq` is the pump's own counter.
    pub fn seal_notification(&mut self, type_: u8, seq: u16, encrypt: bool, payload: &[u8], out: &mut [u8]) -> Result<usize, Error> {
        self.seal_dir(2, type_, seq, encrypt, payload, out)
    }

    fn seal_dir(
        &mut self,
        dir: u8,
        type_: u8,
        seq: u16,
        encrypt: bool,
        payload: &[u8],
        out: &mut [u8],
    ) -> Result<usize, Error> {
        let response = dir != 0;
        if seq > SEQ_MAX {
            return Err(Error::Session);
        }
        let flags = if response { FLAG_RESPONSE } else { 0 };
        if !encrypt {
            return encode_frame(&Frame { version: PROTO_VERSION, type_, flags, seq, payload }, out);
        }
        if !self.has_crypto {
            return Err(Error::Auth);
        }
        let body = payload.len() + CCM_TAG_LEN;
        let total = FRAME_HEADER + body + FRAME_CRC;
        if total > FRAME_MAX || total > out.len() {
            return Err(Error::TooLarge);
        }
        out[0] = PROTO_VERSION;
        out[1] = type_;
        out[2] = flags | FLAG_ENCRYPTED;
        out[3..5].copy_from_slice(&seq.to_le_bytes());
        out[5..7].copy_from_slice(&(body as u16).to_le_bytes());
        let nonce = self.nonce_dir(dir, seq);
        let (head, rest) = out.split_at_mut(FRAME_HEADER);
        let (ct, rest) = rest.split_at_mut(payload.len());
        let mut tag = [0u8; CCM_TAG_LEN];
        self.ccm.encrypt(&nonce, head, payload, ct, &mut tag).map_err(|_| Error::Auth)?;
        rest[..CCM_TAG_LEN].copy_from_slice(&tag);
        let crc = crc16_ccitt_false(&out[..total - FRAME_CRC]);
        out[total - 2..total].copy_from_slice(&crc.to_le_bytes());
        Ok(total)
    }
}
