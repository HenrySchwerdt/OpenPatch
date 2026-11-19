//! Port of `firmware/tests/test_session.c`.
mod common;
use common::{BrokenCcm, FakeCcm};
use openpatch_proto::crc::crc16_ccitt_false;
use openpatch_proto::*;

const SALT: [u8; 4] = [1, 2, 3, 4];
const BOLUS_PAYLOAD: [u8; 6] = [tag::AMOUNT_MU, 4, 0xD0, 0x07, 0, 0];

fn fake(has_crypto: bool, allow_plain: bool) -> Session<FakeCcm> {
    Session::new(FakeCcm::default(), has_crypto, SALT, allow_plain)
}

fn make_cmd<C: Ccm>(s: &mut Session<C>, seq: u16, enc: bool, out: &mut [u8]) -> Result<usize, Error> {
    s.seal(false, cmd::BOLUS, seq, enc, &BOLUS_PAYLOAD, out)
}

/// Rewrite the trailing CRC so only the CCM tag can catch a modification.
fn fix_crc(buf: &mut [u8]) {
    let n = buf.len();
    let crc = crc16_ccitt_false(&buf[..n - 2]);
    buf[n - 2..].copy_from_slice(&crc.to_le_bytes());
}

#[test]
fn session_nonce_layout() {
    let s = fake(true, false);
    assert_eq!(s.nonce(true, 0x0A0B), [1, 2, 3, 4, 1, 0x0B, 0x0A, 0, 0, 0, 0, 0, 0]);
    assert_eq!(s.nonce(false, 1)[4], 0);
}

#[test]
fn session_plaintext_accepted_only_when_allowed() {
    let mut s = Session::new(NoCrypto, false, SALT, true);
    let mut buf = [0u8; 64];
    let mut plain = [0u8; 64];
    let n = make_cmd(&mut s, 1, false, &mut buf).unwrap();
    assert!(n > 0);
    assert_eq!(s.open(&buf[..n], &mut plain).unwrap().type_, cmd::BOLUS);

    let mut prod = fake(true, false); // production config
    assert_eq!(prod.open(&buf[..n], &mut plain).unwrap_err(), Error::Auth);
    assert!(!prod.rx_seen());
}

#[test]
fn session_encrypted_roundtrip_and_hook() {
    let mut s = fake(true, false);
    let mut buf = [0u8; 64];
    let mut plain = [0u8; 64];
    let n = make_cmd(&mut s, 7, true, &mut buf).unwrap();
    assert_ne!(buf[2] & FLAG_ENCRYPTED, 0);
    assert_ne!(&buf[FRAME_HEADER..FRAME_HEADER + 2], &[tag::AMOUNT_MU, 4], "really scrambled");
    let f = s.open(&buf[..n], &mut plain).unwrap();
    assert_eq!(f.payload.len(), 6);
    assert_eq!(f.payload[0], tag::AMOUNT_MU);
    let (ty, seq, payload) = (f.type_, f.seq, f.payload);
    let c = decode_command(ty, seq, payload).unwrap();
    assert_eq!(c.body, CommandBody::Bolus { amount_mu: 2000 });
    assert_eq!(s.ccm().accepted_calls, 1);
    assert_eq!(s.ccm().last_seq, 7);
}

#[test]
fn session_tampering_is_rejected_without_advancing_state() {
    let mut s = fake(true, false);
    let mut buf = [0u8; 64];
    let mut plain = [0u8; 64];
    let n = make_cmd(&mut s, 3, true, &mut buf).unwrap();
    let genuine = &buf[..n];
    // flip a ciphertext bit, repair the CRC so only the CCM tag can catch it
    let mut copy = genuine.to_vec();
    copy[FRAME_HEADER] ^= 1;
    fix_crc(&mut copy);
    assert_eq!(s.open(&copy, &mut plain).unwrap_err(), Error::Auth);
    assert!(!s.rx_seen());
    assert_eq!(s.ccm().accepted_calls, 0);
    // header tamper (type): AAD covers the header
    let mut copy = genuine.to_vec();
    copy[1] = cmd::SUSPEND;
    fix_crc(&mut copy);
    assert_eq!(s.open(&copy, &mut plain).unwrap_err(), Error::Auth);
    // the genuine frame still works afterwards
    assert!(s.open(genuine, &mut plain).is_ok());
}

#[test]
fn session_replay_protection() {
    let mut s = fake(true, false);
    let (mut b1, mut b2, mut b3, mut plain) = ([0u8; 64], [0u8; 64], [0u8; 64], [0u8; 64]);
    let n1 = make_cmd(&mut s, 5, true, &mut b1).unwrap();
    let n2 = make_cmd(&mut s, 6, true, &mut b2).unwrap();
    let n3 = make_cmd(&mut s, 4, true, &mut b3).unwrap();
    assert!(s.open(&b1[..n1], &mut plain).is_ok());
    assert_eq!(s.open(&b1[..n1], &mut plain).unwrap_err(), Error::Replay); // exact replay
    assert_eq!(s.open(&b3[..n3], &mut plain).unwrap_err(), Error::Replay); // older
    assert!(s.open(&b2[..n2], &mut plain).is_ok());
    assert_eq!(s.last_rx_seq(), 6);
}

#[test]
fn session_first_sequence_may_be_zero_and_gaps_are_allowed() {
    let mut s = Session::new(NoCrypto, false, SALT, true);
    let (mut buf, mut plain) = ([0u8; 64], [0u8; 64]);
    let n = make_cmd(&mut s, 0, false, &mut buf).unwrap();
    assert!(s.open(&buf[..n], &mut plain).is_ok());
    let n = make_cmd(&mut s, 1000, false, &mut buf).unwrap();
    assert!(s.open(&buf[..n], &mut plain).is_ok());
}

#[test]
fn session_exhausted_sequence_space_requires_rekey() {
    let mut s = Session::new(NoCrypto, false, SALT, true);
    let (mut buf, mut plain) = ([0u8; 64], [0u8; 64]);
    let raw = Frame { version: PROTO_VERSION, type_: cmd::BOLUS, flags: 0, seq: 0xFFFF, payload: &[] };
    let n = encode_frame(&raw, &mut buf).unwrap();
    assert_eq!(s.open(&buf[..n], &mut plain).unwrap_err(), Error::Session);
    let n = make_cmd(&mut s, SEQ_MAX, false, &mut buf).unwrap();
    assert!(s.open(&buf[..n], &mut plain).is_ok());
    // C seals with encrypt=true on a NULL-ccm session; the seq check precedes the crypto check
    assert_eq!(s.seal(false, cmd::BOLUS, 0xFFFF, true, &[], &mut buf), Err(Error::Session));
}

#[test]
fn session_rejects_garbage_and_encrypted_without_crypto() {
    let mut s = Session::new(NoCrypto, false, SALT, true);
    let (mut buf, mut plain) = ([0u8; 64], [0u8; 64]);
    let bad = [0u8; 9];
    assert_eq!(s.open(&bad, &mut plain).unwrap_err(), Error::Crc);
    let mut enc = fake(true, false);
    let n = make_cmd(&mut enc, 1, true, &mut buf).unwrap();
    assert_eq!(s.open(&buf[..n], &mut plain).unwrap_err(), Error::Auth); // no crypto
    assert_eq!(enc.open(&buf[..4], &mut plain).unwrap_err(), Error::Frame);
    assert_eq!(enc.open(&buf[..n], &mut plain[..3]).unwrap_err(), Error::TooLarge);
}

#[test]
fn session_rejects_encrypted_payload_shorter_than_tag() {
    let mut s = fake(true, false);
    let raw = Frame { version: PROTO_VERSION, type_: cmd::BOLUS, flags: FLAG_ENCRYPTED, seq: 1, payload: b"abc" };
    let (mut buf, mut plain) = ([0u8; 32], [0u8; 32]);
    let n = encode_frame(&raw, &mut buf).unwrap();
    assert_eq!(s.open(&buf[..n], &mut plain).unwrap_err(), Error::Frame);
}

#[test]
fn session_seal_cannot_encrypt_without_crypto() {
    let mut s = Session::new(NoCrypto, false, SALT, true);
    let mut buf = [0u8; 64];
    assert_eq!(make_cmd(&mut s, 1, true, &mut buf), Err(Error::Auth));
    // C: NULL payload with length 1 -> BAD_ARG; not representable with Rust slices.
}

#[test]
fn session_seal_sets_response_flag_and_respects_capacity() {
    let mut s = fake(true, false);
    let (mut buf, mut small) = ([0u8; 64], [0u8; 10]);
    let n = s.seal(true, cmd::BOLUS | RSP_BIT, 9, true, &[1, 1, 0], &mut buf).unwrap();
    let f = decode_frame(&buf[..n]).unwrap();
    assert_ne!(f.flags & FLAG_RESPONSE, 0);
    assert_ne!(f.flags & FLAG_ENCRYPTED, 0);
    assert_eq!(f.payload.len(), 3 + CCM_TAG_LEN);
    assert_eq!(s.seal(true, 0x85, 9, true, &[1, 1, 0], &mut small), Err(Error::TooLarge));
}

#[test]
fn session_seal_fails_when_ccm_backend_fails() {
    let mut s = Session::new(BrokenCcm, true, SALT, false);
    let mut buf = [0u8; 64];
    assert_eq!(s.seal(true, 0x85, 1, true, &[], &mut buf), Err(Error::Auth));
}

#[test]
fn session_restore_last_seq_blocks_replay_of_older_frames() {
    let mut s = Session::new(NoCrypto, false, SALT, true);
    s.restore_last_seq(10);
    let (mut buf, mut plain) = ([0u8; 64], [0u8; 64]);
    let n = make_cmd(&mut s, 10, false, &mut buf).unwrap();
    assert_eq!(s.open(&buf[..n], &mut plain).unwrap_err(), Error::Replay);
    let n = make_cmd(&mut s, 11, false, &mut buf).unwrap();
    assert!(s.open(&buf[..n], &mut plain).is_ok());
}

// ---- direction is fixed by the role (FINDING-001) ----
#[test]
fn pod_refuses_response_and_notification_frames_before_anything_else() {
    for (allow_plain, enc) in [(false, true), (true, true), (true, false)] {
        let mut pod = fake(true, allow_plain);
        let mut own = fake(true, allow_plain); // the pod's sealing side: its own output reflected back
        let (mut buf, mut plain) = ([0u8; 96], [0u8; 96]);
        let n = own.seal(true, cmd::BOLUS | RSP_BIT, 5, enc, &[tag::RESULT, 1, 0], &mut buf).unwrap();
        assert_eq!(pod.open(&buf[..n], &mut plain).unwrap_err(), Error::Frame, "reflected response (enc {enc}, plain ok {allow_plain})");
        let n = own.seal_notification(notify::FRAME_TYPE, 9, enc, &[tag::NOTIFY_KIND, 1, 2], &mut buf).unwrap();
        assert_eq!(pod.open(&buf[..n], &mut plain).unwrap_err(), Error::Frame, "reflected notification");
        // no state touched: not seen, no replay counter, the crypto hook never ran
        assert!(!pod.rx_seen());
        assert_eq!(pod.last_rx_seq(), 0);
        assert_eq!(pod.ccm().accepted_calls, 0);
        // a genuine command with a LOWER seq than the reflected frame is still accepted afterwards
        let n = make_cmd(&mut own, 1, enc, &mut buf).unwrap();
        assert!(pod.open(&buf[..n], &mut plain).is_ok(), "reflection must not advance the replay state");
    }
}

#[test]
fn phone_accepts_only_responses_and_notifications() {
    let mut pod = fake(true, false);
    let mut phone = fake(true, false).with_role(LinkRole::Phone);
    let (mut buf, mut plain) = ([0u8; 96], [0u8; 96]);
    let n = pod.seal(true, cmd::BOLUS | RSP_BIT, 5, true, &[tag::RESULT, 1, 0], &mut buf).unwrap();
    assert_eq!(phone.open(&buf[..n], &mut plain).unwrap().seq, 5);
    let n = pod.seal_notification(notify::FRAME_TYPE, 9, true, &[tag::NOTIFY_KIND, 1, 2], &mut buf).unwrap();
    assert_eq!(phone.open(&buf[..n], &mut plain).unwrap().type_, notify::FRAME_TYPE);
    // a command-direction frame (its own, or an attacker's) is not a valid inbound frame for the phone
    let n = make_cmd(&mut phone, 3, true, &mut buf).unwrap();
    assert_eq!(phone.open(&buf[..n], &mut plain).unwrap_err(), Error::Frame);
    // responses are not replay-checked (they echo the command seq)
    let n = pod.seal(true, cmd::BOLUS | RSP_BIT, 5, true, &[tag::RESULT, 1, 0], &mut buf).unwrap();
    assert!(phone.open(&buf[..n], &mut plain).is_ok());
    assert!(phone.open(&buf[..n], &mut plain).is_ok());
}
