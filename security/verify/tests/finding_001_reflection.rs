//! FINDING-001 (medium) -- FIXED. Before the fix, pod->phone RESPONSE frames reflected back to the pod authenticated,
//! bypassed the replay check, refreshed the communication heartbeat, and made the pod encrypt a SECOND, different
//! message under the SAME (key_p2c, nonce) as the original response (AES-CCM nonce reuse).
//!
//! Root cause was `Session::open()` (firmware-rs/openpatch-proto/src/session.rs): it derived `is_response` from the
//! attacker-controlled header flag and selected the nonce direction (and with it the AES key) from it.
//! Fix: the direction is fixed by the ROLE (`LinkRole`): a pod only accepts command frames (no RESPONSE flag, nonce
//! direction 0, strict replay check); a frame of the other direction is refused with `Error::Frame` BEFORE the key is
//! used, the replay state advances, or `Pump::handle_frame` refreshes the communication heartbeat.
//!
//! These `fixed_*` tests assert the repaired behaviour (they replaced the `known_issue_*` tests that documented the bug).
//! The CI step "FINDING-001 stays fixed" runs them; if one fails the finding has regressed.
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
fn fixed_reflected_response_is_refused_without_side_effects() {
    let mut s = setup();
    let f = proto::decode_frame(&s.r1).unwrap();
    assert_ne!(f.flags & FLAG_RESPONSE, 0);
    assert_ne!(f.flags & FLAG_ENCRYPTED, 0);
    // The attacker (relay) replays the pod's own response to the pod, twice: refused every time, never answered.
    for _ in 0..2 {
        let mut out = [0u8; proto::FRAME_MAX];
        let r = s.pod.handle_frame(&mut s.pod_session, &s.r1, &mut out);
        assert_eq!(r, Err(Error::Frame), "a reflected response must be refused as a wrong-direction frame");
    }
    assert_eq!(s.nonces.borrow().len(), 1, "no second encryption under the nonce of R1");
}

#[test]
fn fixed_no_nonce_reuse_under_key_p2c() {
    let mut s = setup();
    let mut out = [0u8; proto::FRAME_MAX];
    let _ = s.pod.handle_frame(&mut s.pod_session, &s.r1, &mut out);
    let log = s.nonces.borrow();
    // only the original response was ever encrypted: log[0] = nonce of R1, direction 1 = key_p2c
    assert_eq!(log.len(), 1);
    assert_eq!(log[0][4], 1);
    let mut seen = std::collections::BTreeSet::new();
    assert!(log.iter().all(|n| seen.insert(*n)), "a (key, nonce) pair was used twice");
}

#[test]
fn fixed_the_two_time_pad_is_gone_and_the_pod_stays_silent() {
    let mut s = setup();
    let mut out = [0u8; proto::FRAME_MAX];
    // nothing comes back, so there is no second ciphertext to xor against R1
    assert!(s.pod.handle_frame(&mut s.pod_session, &s.r1, &mut out).is_err());
    assert_eq!(s.nonces.borrow().len(), 1);
    let f1 = proto::decode_frame(&s.r1).unwrap();
    assert_eq!(f1.type_ & RSP_BIT, RSP_BIT);
}

#[test]
fn fixed_a_reflected_notification_is_refused_too() {
    let mut s = setup();
    let mut ph_pod = Session::new(AesCcm::directional(&KC, &KP), true, SALT, false); // a pod-side sealing session
    let mut note = [0u8; proto::FRAME_MAX];
    let n = ph_pod.seal_notification(proto::notify::FRAME_TYPE, 1, true, &[proto::tag::NOTIFY_KIND, 1, 1], &mut note).unwrap();
    let mut out = [0u8; proto::FRAME_MAX];
    assert_eq!(s.pod.handle_frame(&mut s.pod_session, &note[..n], &mut out), Err(Error::Frame));
    assert_eq!(s.nonces.borrow().len(), 1);
}

#[test]
fn fixed_the_phone_still_opens_the_genuine_response() {
    // the repair must not break the real direction: the phone role opens R1 with the response nonce
    let s = setup();
    let mut pl = [0u8; proto::FRAME_MAX];
    let mut ph = phone().with_role(proto::LinkRole::Phone);
    let opened = ph.open(&s.r1, &mut pl).expect("genuine response opens on the phone");
    assert_eq!(opened.type_, cmd::GET_STATUS | RSP_BIT);
    assert_eq!(opened.seq, 5);
}
