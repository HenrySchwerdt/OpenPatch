//! FINDING-001 (medium): pod->phone RESPONSE frames reflected back to the pod authenticate, bypass the replay check,
//! refresh the communication heartbeat, and make the pod encrypt a SECOND, different message under the SAME
//! (key_p2c, nonce) as the original response (AES-CCM nonce reuse).
//!
//! Root cause: `Session::open()` (firmware-rs/openpatch-proto/src/session.rs) derives `is_response` from the
//! attacker-controlled header flag, selects the nonce direction (and therefore the AES key, `AesCcm::cipher`)
//! from it, and applies the replay check only `if !is_response`. `Pump::handle_frame()` then treats the opened frame
//! as a command: `comm_heartbeat()` is called, an error response is built and sealed with `seal(true, type|0x80, seq)`,
//! i.e. nonce (salt, dir = 1, seq) -- exactly the nonce of the original response.
//!
//! Test naming: `known_issue_*` PASS while the finding is open (they document the behaviour); `fixed_*` are #[ignore]d and
//! assert the desired behaviour -- when the implementation owner applies proposal security/proposals/01 (reject RESPONSE-
//! flagged frames on the pod, derive direction from the receiver role, not from the header), flip the two sets.
//! Run: `cargo test --release --test finding_001_reflection -- --include-ignored`.
#[path = "../../../firmware-rs/openpatch-core/tests/common/mod.rs"]
mod common;

use common::*;
use openpatch_proto::ccm_impl::AesCcm;
use openpatch_proto::{self as proto, cmd, Ccm, CcmError, Error, Session, FLAG_ENCRYPTED, FLAG_RESPONSE, RSP_BIT};
use std::cell::RefCell;
use std::rc::Rc;

const KC: [u8; 16] = *b"c2p-key-0123456!";
const KP: [u8; 16] = *b"p2c-key-0123456!";
const SALT: [u8; 4] = [9, 8, 7, 6];

/// Wraps the real AES-CCM and records every (nonce, key-direction) used for ENCRYPTION by the pod.
struct Recording {
    inner: AesCcm,
    nonces: Rc<RefCell<Vec<[u8; 13]>>>,
}
impl Ccm for Recording {
    fn encrypt(&mut self, n: &[u8; 13], a: &[u8], pt: &[u8], ct: &mut [u8], tag: &mut [u8; 8]) -> Result<(), CcmError> {
        self.nonces.borrow_mut().push(*n);
        self.inner.encrypt(n, a, pt, ct, tag)
    }
    fn decrypt(&mut self, n: &[u8; 13], a: &[u8], ct: &[u8], tag: &[u8; 8], pt: &mut [u8]) -> Result<(), CcmError> {
        self.inner.decrypt(n, a, ct, tag, pt)
    }
}

fn phone() -> Session<AesCcm> {
    Session::new(AesCcm::directional(&KC, &KP), true, SALT, false)
}

struct Setup {
    pod: openpatch_core::Pump<MockHal>,
    pod_session: Session<Recording>,
    nonces: Rc<RefCell<Vec<[u8; 13]>>>,
    r1: Vec<u8>,
}

/// One legitimate encrypted GetStatus -> the pod's (encrypted) response R1, which a relay on the link can copy.
fn setup() -> Setup {
    let (pod, _h) = new_pump();
    let nonces = Rc::new(RefCell::new(Vec::new()));
    let mut pod_session = Session::new(Recording { inner: AesCcm::directional(&KC, &KP), nonces: nonces.clone() }, true, SALT, false);
    let mut p = phone();
    let mut cmd_frame = [0u8; proto::FRAME_MAX];
    let n = p.seal(false, cmd::GET_STATUS, 5, true, &[], &mut cmd_frame).unwrap();
    let mut pod = pod;
    let mut out = [0u8; proto::FRAME_MAX];
    let m = pod.handle_frame(&mut pod_session, &cmd_frame[..n], &mut out).expect("legitimate command accepted");
    Setup { pod, pod_session, nonces, r1: out[..m].to_vec() }
}

#[test]
fn known_issue_reflected_response_is_accepted_replayable_and_answered() {
    let mut s = setup();
    let f = proto::decode_frame(&s.r1).unwrap();
    assert_ne!(f.flags & FLAG_RESPONSE, 0);
    assert_ne!(f.flags & FLAG_ENCRYPTED, 0);
    // The attacker (relay) replays the pod's own response to the pod, twice.
    for _ in 0..2 {
        let mut out = [0u8; proto::FRAME_MAX];
        let r = s.pod.handle_frame(&mut s.pod_session, &s.r1, &mut out);
        assert!(r.is_ok(), "FINDING-001: reflected response was refused ({r:?}); the finding is fixed -> flip the tests");
    }
}

#[test]
fn known_issue_nonce_reuse_under_key_p2c() {
    let mut s = setup();
    let mut out = [0u8; proto::FRAME_MAX];
    s.pod.handle_frame(&mut s.pod_session, &s.r1, &mut out).expect("reflected frame answered");
    let log = s.nonces.borrow();
    // log[0] = nonce of the original response R1, log[1] = nonce of the answer to the reflected frame.
    assert_eq!(log.len(), 2);
    assert_eq!(log[0], log[1], "FINDING-001: two different messages encrypted under one (key_p2c, nonce)");
    assert_eq!(log[0][4], 1, "nonce direction 1 = key_p2c");
}

/// What the attacker learns from the two-time pad without any key: C1 xor C2 = P1 xor P2, and P2 (the pod's error
/// answer: a RESULT TLV with a deterministic code) is predictable from the public header -> key stream bytes.
#[test]
fn known_issue_two_time_pad_leaks_keystream() {
    let mut s = setup();
    let c1 = ct(&s.r1);
    let mut out = [0u8; proto::FRAME_MAX];
    let m = s.pod.handle_frame(&mut s.pod_session, &s.r1, &mut out).unwrap();
    let c2 = ct(&out[..m]);
    let f1 = proto::decode_frame(&s.r1).unwrap();
    // predictable P2: response to an unknown command type (type | 0x80 is never a command)
    let code = Error::Unsupported.code();
    let p2 = [proto::tag::RESULT, 1, code];
    assert!(c2.len() >= 3 && c1.len() >= 3);
    let leaked_keystream: Vec<u8> = (0..3).map(|i| c2[i] ^ p2[i]).collect();
    let p1_prefix: Vec<u8> = (0..3).map(|i| c1[i] ^ leaked_keystream[i]).collect();
    // compare with the true plaintext of R1 (phone side decrypts it)
    let mut pl = [0u8; proto::FRAME_MAX];
    let mut ph = phone();
    let opened = ph.open(&s.r1, &mut pl).unwrap();
    assert_eq!(&opened.payload[..3], &p1_prefix[..], "attacker recovered 3 plaintext bytes of R1 without any key");
    assert_eq!(f1.type_ & RSP_BIT, RSP_BIT);
}

fn ct(frame: &[u8]) -> Vec<u8> {
    let f = proto::decode_frame(frame).unwrap();
    f.payload[..f.payload.len() - proto::CCM_TAG_LEN].to_vec()
}

#[test]
#[ignore = "FINDING-001 open: enable when Session::open rejects RESPONSE-flagged frames on the pod"]
fn fixed_reflected_response_is_refused_without_side_effects() {
    let mut s = setup();
    let mut out = [0u8; proto::FRAME_MAX];
    assert!(s.pod.handle_frame(&mut s.pod_session, &s.r1, &mut out).is_err());
    assert_eq!(s.nonces.borrow().len(), 1, "no second encryption under the nonce of R1");
}
