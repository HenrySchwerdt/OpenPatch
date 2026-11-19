//! Application layer session key agreement (protocol v1.1 section 5.2, `docs/04-protocol.md`).
//!
//! Feature `key-agreement`. Pure functions (`derive_*`, `transcript_hash`, `confirm_tag`) shared by
//! both roles, the pod side state machine [`Responder`] and the phone side reference
//! [`Initiator`] (used by the tests and as the byte-exact reference for the Swift implementation;
//! both consume `docs/vectors/session-key-agreement.json`).
//!
//! Two handshakes with the same shape (INIT request / INIT response, FINISH request / FINISH
//! response, all unencrypted frames with a CRC):
//!
//! * pairing (frame types `0x40`/`0x41`), only while the pod's pairing window is open: an
//!   unauthenticated ephemeral X25519 exchange (optionally mixed with an out-of-band code) yields
//!   the long-term pairing secret `PS` (32 bytes) that both sides store;
//! * session (`0x42`/`0x43`), once per BLE connection: a fresh ephemeral X25519 exchange mixed with
//!   `PS` yields one AES-128-CCM key per direction plus the 4 byte nonce salt. The pod switches to
//!   the new keys only after the phone's FINISH carries a valid confirmation tag, so an attacker
//!   without `PS` can never displace a running session.
//!
//! No randomness is generated here: callers pass an `RngCore` (the pod seeds a ChaCha20 DRBG from
//! the nRF52840 TRNG at boot; the tests pass fixed bytes).
use crate::consts::{FLAG_RESPONSE, PROTO_VERSION, RSP_BIT};
use crate::error::Error;
use crate::frame::{decode_frame, encode_frame, Frame};
use crate::tlv::{TlvReader, TlvWriter};
use hkdf::Hkdf;
use hmac::{Hmac, Mac};
use rand_core::RngCore;
use sha2::{Digest, Sha256};
use subtle::ConstantTimeEq;
use x25519_dalek::{x25519, X25519_BASEPOINT_BYTES};

pub const PUB_LEN: usize = 32;
pub const NONCE_LEN: usize = 16;
pub const CONFIRM_LEN: usize = 16;
pub const PS_LEN: usize = 32;
pub const PS_ID_LEN: usize = 4;

/// Handshake frame types (requests; responses are `type | 0x80`).
pub mod htype {
    pub const PAIR_INIT: u8 = 0x40;
    pub const PAIR_FINISH: u8 = 0x41;
    pub const SESSION_INIT: u8 = 0x42;
    pub const SESSION_FINISH: u8 = 0x43;
}

/// Handshake TLV tags.
pub mod htag {
    pub const RESULT: u8 = crate::consts::tag::RESULT;
    /// 32 bytes, X25519 public key (u-coordinate, RFC 7748, little-endian).
    pub const EPH_PUB: u8 = 0x30;
    /// 16 bytes, random.
    pub const NONCE: u8 = 0x31;
    /// 16 bytes, truncated HMAC-SHA256 key confirmation.
    pub const CONFIRM: u8 = 0x32;
    /// 4 bytes, identifies the pairing secret (session INIT only).
    pub const PS_ID: u8 = 0x33;
}

/// `RESULT` codes used by the handshake (numbering of protocol section 4).
pub mod hresult {
    pub const OK: u8 = 0;
    pub const BAD_ARG: u8 = 1;
    pub const FRAME: u8 = 10;
    /// Pairing window closed / confirmation tag wrong.
    pub const AUTH: u8 = 14;
    /// FINISH without a matching INIT.
    pub const SESSION: u8 = 18;
    /// No pairing secret on the pod, or `PS_ID` does not match: pair again.
    pub const PAIR: u8 = 22;
}

const LABEL_TRANSCRIPT: &[u8] = b"OPENPATCH/1 transcript";
const LABEL_OOB: &[u8] = b"OPENPATCH/1 oob";
const LABEL_PS_ID: &[u8] = b"OPENPATCH/1 ps-id";
const LABEL_PAIRING: &[u8] = b"OPENPATCH/1 pairing";
const LABEL_SESSION: &[u8] = b"OPENPATCH/1 session";
const LABEL_CONFIRM_POD: &[u8] = b"OPENPATCH/1 confirm pod";
const LABEL_CONFIRM_APP: &[u8] = b"OPENPATCH/1 confirm app";

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum Mode {
    Pair = 1,
    Session = 2,
}

/// Directional AES-128-CCM keys of one session. NOT `Debug`: never print key material.
#[derive(Clone, PartialEq, Eq)]
pub struct SessionKeys {
    /// phone -> pod (nonce direction 0).
    pub key_c2p: [u8; 16],
    /// pod -> phone (nonce directions 1 and 2).
    pub key_p2c: [u8; 16],
    /// nonce prefix.
    pub salt: [u8; 4],
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Side {
    App,
    Pod,
}

/// Handshake failures seen by the phone side.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum HsError {
    /// Malformed frame / missing TLV.
    Frame,
    /// The pod answered with this `RESULT`.
    Rejected(u8),
    /// The pod's key confirmation did not verify (wrong `PS`, MITM, corrupted exchange).
    BadConfirm,
    /// Peer public key is a low-order point (shared secret all zero).
    LowOrderPoint,
}

impl From<Error> for HsError {
    fn from(_: Error) -> Self {
        HsError::Frame
    }
}

// ------------------------------------------------------------------------------------------
// Primitives
// ------------------------------------------------------------------------------------------

pub fn public_key(secret: &[u8; 32]) -> [u8; 32] {
    x25519(*secret, X25519_BASEPOINT_BYTES)
}

/// X25519; `None` for a low-order peer key (all-zero result), which must abort the handshake.
pub fn shared_secret(secret: &[u8; 32], peer_public: &[u8; 32]) -> Option<[u8; 32]> {
    let s = x25519(*secret, *peer_public);
    if bool::from(s.ct_eq(&[0u8; 32])) {
        None
    } else {
        Some(s)
    }
}

/// HKDF salt of the pairing handshake: 32 zero bytes without an out-of-band code, else
/// `SHA-256("OPENPATCH/1 oob" || oob)`.
pub fn oob_salt(oob: &[u8]) -> [u8; 32] {
    if oob.is_empty() {
        return [0u8; 32];
    }
    let mut h = Sha256::new();
    h.update(LABEL_OOB);
    h.update(oob);
    h.finalize().into()
}

/// 4 byte identifier of a pairing secret: `HKDF-Expand(PS, "OPENPATCH/1 ps-id", 4)`.
pub fn ps_id(ps: &[u8; PS_LEN]) -> [u8; PS_ID_LEN] {
    let hk = Hkdf::<Sha256>::from_prk(ps).expect("32 byte PRK");
    let mut out = [0u8; PS_ID_LEN];
    hk.expand(LABEL_PS_ID, &mut out).expect("4 bytes");
    out
}

pub struct Transcript<'a> {
    pub mode: Mode,
    /// zero for the pairing handshake.
    pub ps_id: [u8; PS_ID_LEN],
    pub pub_a: &'a [u8; PUB_LEN],
    pub pub_b: &'a [u8; PUB_LEN],
    pub nonce_a: &'a [u8; NONCE_LEN],
    pub nonce_b: &'a [u8; NONCE_LEN],
}

/// `SHA-256("OPENPATCH/1 transcript" || mode || ps_id || pubA || pubB || nonceA || nonceB)`.
pub fn transcript_hash(t: &Transcript<'_>) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(LABEL_TRANSCRIPT);
    h.update([t.mode as u8]);
    h.update(t.ps_id);
    h.update(t.pub_a);
    h.update(t.pub_b);
    h.update(t.nonce_a);
    h.update(t.nonce_b);
    h.finalize().into()
}

/// Pairing: `PRK = HKDF-Extract(salt = oob_salt, IKM = dh)`, `OKM = Expand(PRK, "OPENPATCH/1 pairing" || th, 64)`
/// = `PS(32) || confirm_key(32)`.
pub fn derive_pairing(dh: &[u8; 32], oob_salt: &[u8; 32], th: &[u8; 32]) -> ([u8; PS_LEN], [u8; 32]) {
    let hk = Hkdf::<Sha256>::new(Some(oob_salt), dh);
    let mut okm = [0u8; 64];
    hk.expand_multi_info(&[LABEL_PAIRING, th], &mut okm).expect("64 bytes");
    let mut ps = [0u8; PS_LEN];
    let mut ck = [0u8; 32];
    ps.copy_from_slice(&okm[..32]);
    ck.copy_from_slice(&okm[32..]);
    (ps, ck)
}

/// Session: `PRK = HKDF-Extract(salt = PS, IKM = dh)`, `OKM = Expand(PRK, "OPENPATCH/1 session" || th, 68)`
/// = `key_c2p(16) || key_p2c(16) || salt(4) || confirm_key(32)`.
pub fn derive_session(dh: &[u8; 32], ps: &[u8; PS_LEN], th: &[u8; 32]) -> (SessionKeys, [u8; 32]) {
    let hk = Hkdf::<Sha256>::new(Some(ps), dh);
    let mut okm = [0u8; 68];
    hk.expand_multi_info(&[LABEL_SESSION, th], &mut okm).expect("68 bytes");
    let mut k = SessionKeys { key_c2p: [0; 16], key_p2c: [0; 16], salt: [0; 4] };
    k.key_c2p.copy_from_slice(&okm[..16]);
    k.key_p2c.copy_from_slice(&okm[16..32]);
    k.salt.copy_from_slice(&okm[32..36]);
    let mut ck = [0u8; 32];
    ck.copy_from_slice(&okm[36..]);
    (k, ck)
}

/// `HMAC-SHA256(confirm_key, "OPENPATCH/1 confirm pod|app" || th)` truncated to 16 bytes.
pub fn confirm_tag(confirm_key: &[u8; 32], side: Side, th: &[u8; 32]) -> [u8; CONFIRM_LEN] {
    let mut m = <Hmac<Sha256> as Mac>::new_from_slice(confirm_key).expect("any key length");
    m.update(match side {
        Side::Pod => LABEL_CONFIRM_POD,
        Side::App => LABEL_CONFIRM_APP,
    });
    m.update(th);
    let full = m.finalize().into_bytes();
    let mut out = [0u8; CONFIRM_LEN];
    out.copy_from_slice(&full[..CONFIRM_LEN]);
    out
}

fn tag_eq(a: &[u8], b: &[u8]) -> bool {
    a.len() == b.len() && bool::from(a.ct_eq(b))
}

/// Draw the ephemeral secret (32 bytes) and then the nonce (16 bytes) from `rng`.
pub fn draw<R: RngCore>(rng: &mut R) -> ([u8; 32], [u8; NONCE_LEN]) {
    let mut secret = [0u8; 32];
    let mut nonce = [0u8; NONCE_LEN];
    rng.fill_bytes(&mut secret);
    rng.fill_bytes(&mut nonce);
    (secret, nonce)
}

// ------------------------------------------------------------------------------------------
// Framing helpers
// ------------------------------------------------------------------------------------------

/// `true` when byte 1 of a frame is one of the four handshake request types.
pub fn is_handshake_frame(frame: &[u8]) -> bool {
    frame.len() > 1 && (htype::PAIR_INIT..=htype::SESSION_FINISH).contains(&frame[1])
}

fn put_frame(type_: u8, flags: u8, seq: u16, build: impl FnOnce(&mut TlvWriter<'_>), out: &mut [u8]) -> Result<usize, Error> {
    let mut payload = [0u8; 128];
    let mut w = TlvWriter::new(&mut payload);
    build(&mut w);
    let n = w.finish().ok_or(Error::TooLarge)?;
    encode_frame(&Frame { version: PROTO_VERSION, type_, flags, seq, payload: &payload[..n] }, out)
}

fn result_frame(req_type: u8, seq: u16, result: u8, out: &mut [u8]) -> usize {
    put_frame(req_type | RSP_BIT, FLAG_RESPONSE, seq, |w| w.put_u8(htag::RESULT, result), out).unwrap_or(0)
}

struct Fields<'a> {
    pubkey: Option<&'a [u8]>,
    nonce: Option<&'a [u8]>,
    confirm: Option<&'a [u8]>,
    ps_id: Option<&'a [u8]>,
    result: Option<u8>,
}

fn parse_fields(payload: &[u8]) -> Option<Fields<'_>> {
    let mut f = Fields { pubkey: None, nonce: None, confirm: None, ps_id: None, result: None };
    for item in TlvReader::new(payload) {
        let (t, v) = item.ok()?;
        match t {
            htag::EPH_PUB => f.pubkey = Some(v),
            htag::NONCE => f.nonce = Some(v),
            htag::CONFIRM => f.confirm = Some(v),
            htag::PS_ID => f.ps_id = Some(v),
            htag::RESULT if v.len() == 1 => f.result = Some(v[0]),
            _ => {} // unknown tags are skipped (forward compatibility)
        }
    }
    Some(f)
}

fn arr<const N: usize>(v: Option<&[u8]>) -> Option<[u8; N]> {
    let v = v?;
    if v.len() != N {
        return None;
    }
    let mut a = [0u8; N];
    a.copy_from_slice(v);
    Some(a)
}

// ------------------------------------------------------------------------------------------
// Pod side
// ------------------------------------------------------------------------------------------

enum Pending {
    Pair { ps: [u8; PS_LEN], ck: [u8; 32], th: [u8; 32] },
    Session { keys: SessionKeys, ck: [u8; 32], th: [u8; 32] },
}

/// What a completed handshake step asks the platform to do.
pub enum Event {
    None,
    /// Pairing finished: persist this pairing secret (the responder already uses it).
    Paired([u8; PS_LEN]),
    /// Session established: replace the `Session` by one that uses these keys.
    SessionUp(SessionKeys),
}

pub struct Output {
    /// Length of the response frame written to `out` (0 = nothing to send).
    pub reply_len: usize,
    pub event: Event,
}

/// Pod side state machine. One pending (half-open) handshake at a time; the running session is
/// owned by the caller and is only replaced on [`Event::SessionUp`].
pub struct Responder {
    ps: Option<[u8; PS_LEN]>,
    oob_salt: [u8; 32],
    pending: Option<Pending>,
}

impl Responder {
    pub fn new(ps: Option<[u8; PS_LEN]>) -> Self {
        Self { ps, oob_salt: [0; 32], pending: None }
    }

    /// Out-of-band pairing code known to the pod (empty = none).
    pub fn set_oob(&mut self, oob: &[u8]) {
        self.oob_salt = oob_salt(oob);
    }

    pub fn has_pairing_secret(&self) -> bool {
        self.ps.is_some()
    }

    /// Erase the pairing secret (factory reset).
    pub fn forget(&mut self) {
        self.ps = None;
        self.pending = None;
    }

    /// Link closed: drop any half-open handshake.
    pub fn reset(&mut self) {
        self.pending = None;
    }

    /// Process one handshake request frame. `None` = dropped silently (bad CRC/version/flags,
    /// not a handshake frame). A response frame with an error `RESULT` is a normal output.
    pub fn handle<R: RngCore>(&mut self, frame: &[u8], pairing_open: bool, rng: &mut R, out: &mut [u8]) -> Option<Output> {
        let f = decode_frame(frame).ok()?;
        if f.flags != 0 || !is_handshake_frame(frame) {
            return None;
        }
        let reject = |code: u8, out: &mut [u8]| Some(Output { reply_len: result_frame(f.type_, f.seq, code, out), event: Event::None });
        let fields = match parse_fields(f.payload) {
            Some(x) => x,
            None => return reject(hresult::FRAME, out),
        };
        match f.type_ {
            htype::PAIR_INIT | htype::SESSION_INIT => {
                let mode = if f.type_ == htype::PAIR_INIT { Mode::Pair } else { Mode::Session };
                // A new INIT replaces any half-open handshake (but never the running session).
                self.pending = None;
                if mode == Mode::Pair && !pairing_open {
                    return reject(hresult::AUTH, out);
                }
                let (pub_a, nonce_a) = match (arr::<32>(fields.pubkey), arr::<16>(fields.nonce)) {
                    (Some(p), Some(n)) => (p, n),
                    _ => return reject(hresult::FRAME, out),
                };
                let ps = self.ps;
                let mut id = [0u8; PS_ID_LEN];
                if mode == Mode::Session {
                    let ps = match ps {
                        Some(p) => p,
                        None => return reject(hresult::PAIR, out),
                    };
                    id = ps_id(&ps);
                    if !fields.ps_id.is_some_and(|v| tag_eq(v, &id)) {
                        return reject(hresult::PAIR, out);
                    }
                }
                let (secret, nonce_b) = draw(rng);
                let pub_b = public_key(&secret);
                let dh = match shared_secret(&secret, &pub_a) {
                    Some(d) => d,
                    None => return reject(hresult::BAD_ARG, out),
                };
                let th = transcript_hash(&Transcript { mode, ps_id: id, pub_a: &pub_a, pub_b: &pub_b, nonce_a: &nonce_a, nonce_b: &nonce_b });
                let (ck, pending) = match mode {
                    Mode::Pair => {
                        let (new_ps, ck) = derive_pairing(&dh, &self.oob_salt, &th);
                        (ck, Pending::Pair { ps: new_ps, ck, th })
                    }
                    Mode::Session => {
                        let (keys, ck) = derive_session(&dh, &ps.unwrap_or([0; 32]), &th);
                        (ck, Pending::Session { keys, ck, th })
                    }
                };
                let confirm = confirm_tag(&ck, Side::Pod, &th);
                let n = put_frame(
                    f.type_ | RSP_BIT,
                    FLAG_RESPONSE,
                    f.seq,
                    |w| {
                        w.put_u8(htag::RESULT, hresult::OK);
                        w.put(htag::EPH_PUB, &pub_b);
                        w.put(htag::NONCE, &nonce_b);
                        w.put(htag::CONFIRM, &confirm);
                    },
                    out,
                )
                .ok()?;
                self.pending = Some(pending);
                Some(Output { reply_len: n, event: Event::None })
            }
            htype::PAIR_FINISH | htype::SESSION_FINISH => {
                let pending = self.pending.take();
                let want_pair = f.type_ == htype::PAIR_FINISH;
                let (ck, th) = match (&pending, want_pair) {
                    (Some(Pending::Pair { ck, th, .. }), true) | (Some(Pending::Session { ck, th, .. }), false) => (*ck, *th),
                    _ => return reject(hresult::SESSION, out),
                };
                if want_pair && !pairing_open {
                    return reject(hresult::AUTH, out);
                }
                let expect = confirm_tag(&ck, Side::App, &th);
                if !fields.confirm.is_some_and(|v| tag_eq(v, &expect)) {
                    return reject(hresult::AUTH, out);
                }
                let event = match pending {
                    Some(Pending::Pair { ps, .. }) => {
                        self.ps = Some(ps);
                        Event::Paired(ps)
                    }
                    Some(Pending::Session { keys, .. }) => Event::SessionUp(keys),
                    None => Event::None,
                };
                Some(Output { reply_len: result_frame(f.type_, f.seq, hresult::OK, out), event })
            }
            _ => None,
        }
    }
}

// ------------------------------------------------------------------------------------------
// Phone side reference
// ------------------------------------------------------------------------------------------

/// What a finished initiator yields.
pub enum Outcome {
    Paired([u8; PS_LEN]),
    Session(SessionKeys),
}

/// Phone side reference (the iOS app has its own Swift implementation of exactly this).
pub struct Initiator {
    mode: Mode,
    secret: [u8; 32],
    pub_a: [u8; PUB_LEN],
    nonce_a: [u8; NONCE_LEN],
    ps: Option<[u8; PS_LEN]>,
    oob_salt: [u8; 32],
    outcome: Option<Outcome>,
}

impl Initiator {
    /// Pairing handshake (optionally with an out-of-band code, empty = none).
    pub fn pair<R: RngCore>(rng: &mut R, oob: &[u8]) -> Self {
        let (secret, nonce_a) = draw(rng);
        Self { mode: Mode::Pair, secret, pub_a: public_key(&secret), nonce_a, ps: None, oob_salt: oob_salt(oob), outcome: None }
    }

    /// Session handshake with the stored pairing secret.
    pub fn session<R: RngCore>(rng: &mut R, ps: [u8; PS_LEN]) -> Self {
        let (secret, nonce_a) = draw(rng);
        Self { mode: Mode::Session, secret, pub_a: public_key(&secret), nonce_a, ps: Some(ps), oob_salt: [0; 32], outcome: None }
    }

    fn id(&self) -> [u8; PS_ID_LEN] {
        self.ps.map_or([0; PS_ID_LEN], |p| ps_id(&p))
    }

    pub fn init_frame(&self, seq: u16, out: &mut [u8]) -> Result<usize, Error> {
        let t = if self.mode == Mode::Pair { htype::PAIR_INIT } else { htype::SESSION_INIT };
        let id = self.id();
        put_frame(
            t,
            0,
            seq,
            |w| {
                w.put(htag::EPH_PUB, &self.pub_a);
                w.put(htag::NONCE, &self.nonce_a);
                if self.mode == Mode::Session {
                    w.put(htag::PS_ID, &id);
                }
            },
            out,
        )
    }

    /// Verify the pod's INIT response and write the FINISH request into `out`.
    pub fn on_init_response(&mut self, frame: &[u8], finish_seq: u16, out: &mut [u8]) -> Result<usize, HsError> {
        let f = decode_frame(frame)?;
        let want = if self.mode == Mode::Pair { htype::PAIR_INIT } else { htype::SESSION_INIT } | RSP_BIT;
        if f.type_ != want || f.flags != FLAG_RESPONSE {
            return Err(HsError::Frame);
        }
        let fields = parse_fields(f.payload).ok_or(HsError::Frame)?;
        match fields.result {
            Some(hresult::OK) => {}
            Some(c) => return Err(HsError::Rejected(c)),
            None => return Err(HsError::Frame),
        }
        let pub_b = arr::<32>(fields.pubkey).ok_or(HsError::Frame)?;
        let nonce_b = arr::<16>(fields.nonce).ok_or(HsError::Frame)?;
        let confirm_b = fields.confirm.ok_or(HsError::Frame)?;
        let dh = shared_secret(&self.secret, &pub_b).ok_or(HsError::LowOrderPoint)?;
        let th = transcript_hash(&Transcript {
            mode: self.mode,
            ps_id: self.id(),
            pub_a: &self.pub_a,
            pub_b: &pub_b,
            nonce_a: &self.nonce_a,
            nonce_b: &nonce_b,
        });
        let (ck, outcome) = match self.mode {
            Mode::Pair => {
                let (ps, ck) = derive_pairing(&dh, &self.oob_salt, &th);
                (ck, Outcome::Paired(ps))
            }
            Mode::Session => {
                let (k, ck) = derive_session(&dh, &self.ps.ok_or(HsError::Frame)?, &th);
                (ck, Outcome::Session(k))
            }
        };
        if !tag_eq(confirm_b, &confirm_tag(&ck, Side::Pod, &th)) {
            return Err(HsError::BadConfirm);
        }
        let ft = if self.mode == Mode::Pair { htype::PAIR_FINISH } else { htype::SESSION_FINISH };
        let confirm_a = confirm_tag(&ck, Side::App, &th);
        let n = put_frame(ft, 0, finish_seq, |w| w.put(htag::CONFIRM, &confirm_a), out)?;
        self.outcome = Some(outcome);
        Ok(n)
    }

    /// Check the pod's FINISH response; on `RESULT = OK` returns the outcome to store / use.
    pub fn on_finish_response(&mut self, frame: &[u8]) -> Result<Outcome, HsError> {
        let f = decode_frame(frame)?;
        let ft = if self.mode == Mode::Pair { htype::PAIR_FINISH } else { htype::SESSION_FINISH } | RSP_BIT;
        if f.type_ != ft || f.flags != FLAG_RESPONSE {
            return Err(HsError::Frame);
        }
        match parse_fields(f.payload).and_then(|x| x.result) {
            Some(hresult::OK) => self.outcome.take().ok_or(HsError::Frame),
            Some(c) => Err(HsError::Rejected(c)),
            None => Err(HsError::Frame),
        }
    }
}
