//! Pump + Session integration (frame in -> response frame out). The pure session tests live in
//! `openpatch-proto/tests/session.rs`; these need a `Pump`.
mod common;
use common::*;
use openpatch_proto::{self as proto, cmd, tag, Ccm, CcmError, Error, Frame, NoCrypto, Session, FLAG_ENCRYPTED, FLAG_RESPONSE, PROTO_VERSION, RSP_BIT};

const SALT: [u8; 4] = [1, 2, 3, 4];

/// TEST-ONLY fake CCM (variant of `openpatch-proto/tests/common/mod.rs`). NOT SECURE.
#[derive(Default)]
struct FakeCcm;
fn ks(n: &[u8; 13], i: &[u8], o: &mut [u8]) {
    for (k, (x, b)) in o.iter_mut().zip(i).enumerate() {
        *x = b ^ n[k % 13].wrapping_add(0x5A).wrapping_add(k as u8);
    }
}
fn tg(n: &[u8; 13], a: &[u8], c: &[u8]) -> [u8; 8] {
    let mut h: u64 = 1469598103934665603;
    for &b in n.iter().chain(a).chain(c) {
        h = (h ^ b as u64).wrapping_mul(1099511628211);
    }
    h.to_le_bytes()
}
impl Ccm for FakeCcm {
    fn encrypt(&mut self, n: &[u8; 13], a: &[u8], pt: &[u8], ct: &mut [u8], tag: &mut [u8; 8]) -> Result<(), CcmError> {
        ks(n, pt, ct);
        *tag = tg(n, a, ct);
        Ok(())
    }
    fn decrypt(&mut self, n: &[u8; 13], a: &[u8], ct: &[u8], tag: &[u8; 8], pt: &mut [u8]) -> Result<(), CcmError> {
        if tg(n, a, ct) != *tag {
            return Err(CcmError);
        }
        ks(n, ct, pt);
        Ok(())
    }
}

fn plain_session() -> Session<NoCrypto> {
    Session::new(NoCrypto, false, SALT, true)
}

fn command_frame<C: Ccm>(s: &mut Session<C>, enc: bool, seq: u16, ty: u8, payload: &[u8]) -> Vec<u8> {
    let mut b = [0u8; proto::FRAME_MAX];
    let n = s.seal(false, ty, seq, enc, payload, &mut b).unwrap();
    b[..n].to_vec()
}

fn status_of(out: &[u8]) -> proto::Response {
    let f = proto::decode_frame(out).unwrap();
    assert_ne!(f.flags & FLAG_RESPONSE, 0);
    proto::decode_response(f.type_ & !RSP_BIT, f.seq, f.payload).unwrap()
}

#[test]
fn get_status_response_echoes_seq_and_reports_last_seq() {
    let (mut p, _h) = new_pump();
    let mut s = plain_session();
    let mut out = [0u8; proto::FRAME_MAX];
    let frame = command_frame(&mut s, false, 0x0042, cmd::GET_STATUS, &[]);
    let mut rx = plain_session();
    let n = p.handle_frame(&mut rx, &frame, &mut out).unwrap();
    let f = proto::decode_frame(&out[..n]).unwrap();
    assert_eq!(f.type_, cmd::GET_STATUS | RSP_BIT);
    assert_eq!(f.seq, 0x0042);
    let r = status_of(&out[..n]);
    assert_eq!(r.result, 0);
    assert_eq!(r.status.unwrap().last_seq, 0x0042);
}

#[test]
fn golden_get_status_frame_is_answered() {
    let (mut p, _h) = new_pump();
    let mut rx = plain_session();
    let mut out = [0u8; proto::FRAME_MAX];
    let golden = [0x01, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0xBB, 0x7A];
    let n = p.handle_frame(&mut rx, &golden, &mut out).unwrap();
    assert_eq!(status_of(&out[..n]).seq, 1);
}

#[test]
fn replayed_frame_is_dropped_without_response() {
    let (mut p, _h) = new_pump();
    let mut s = plain_session();
    let mut rx = plain_session();
    let mut out = [0u8; proto::FRAME_MAX];
    let frame = command_frame(&mut s, false, 5, cmd::GET_STATUS, &[]);
    assert!(p.handle_frame(&mut rx, &frame, &mut out).is_ok());
    assert_eq!(p.handle_frame(&mut rx, &frame, &mut out), Err(Error::Replay));
}

#[test]
fn replay_protection_survives_restore_of_last_seq() {
    let (mut p, _h) = new_pump();
    let mut s = plain_session();
    let frame = command_frame(&mut s, false, 20, cmd::GET_STATUS, &[]);
    let mut rx = plain_session();
    rx.restore_last_seq(20); // "reboot": persisted seq restored
    let mut out = [0u8; proto::FRAME_MAX];
    assert_eq!(p.handle_frame(&mut rx, &frame, &mut out), Err(Error::Replay));
    let newer = command_frame(&mut s, false, 21, cmd::GET_STATUS, &[]);
    assert!(p.handle_frame(&mut rx, &newer, &mut out).is_ok());
    let third = command_frame(&mut s, false, 22, cmd::GET_STATUS, &[]);
    let n = p.handle_frame(&mut rx, &third, &mut out).unwrap();
    assert_eq!(status_of(&out[..n]).status.unwrap().last_seq, 22);
}

#[test]
fn encrypted_command_gets_encrypted_response() {
    let (mut p, _h) = running(50_000, 1000);
    let mut phone = Session::new(FakeCcm, true, SALT, false).with_role(proto::LinkRole::Phone);
    let mut pod = Session::new(FakeCcm, true, SALT, false);
    let frame = command_frame(&mut phone, true, 1, cmd::GET_STATUS, &[]);
    let mut out = [0u8; proto::FRAME_MAX];
    let n = p.handle_frame(&mut pod, &frame, &mut out).unwrap();
    assert_ne!(out[2] & FLAG_ENCRYPTED, 0);
    let mut plain = [0u8; proto::FRAME_MAX];
    let o = phone.open(&out[..n], &mut plain).unwrap();
    assert_eq!(o.type_, cmd::GET_STATUS | RSP_BIT);
    let r = proto::decode_response(cmd::GET_STATUS, o.seq, o.payload).unwrap();
    assert_eq!(r.result, 0);
    assert!(r.status.is_some());
}

#[test]
fn plaintext_refused_by_production_session() {
    let (mut p, _h) = new_pump();
    let mut s = plain_session();
    let mut prod = Session::new(FakeCcm, true, SALT, false);
    let frame = command_frame(&mut s, false, 1, cmd::GET_STATUS, &[]);
    let mut out = [0u8; proto::FRAME_MAX];
    assert_eq!(p.handle_frame(&mut prod, &frame, &mut out), Err(Error::Auth));
}

#[test]
fn unsupported_command_type_yields_error_response() {
    let (mut p, _h) = new_pump();
    let mut rx = plain_session();
    let mut out = [0u8; proto::FRAME_MAX];
    let raw = Frame { version: PROTO_VERSION, type_: 0x7E, flags: 0, seq: 1, payload: &[] };
    let mut b = [0u8; 16];
    let n = proto::encode_frame(&raw, &mut b).unwrap();
    let m = p.handle_frame(&mut rx, &b[..n], &mut out).unwrap();
    assert_eq!(status_of(&out[..m]).result, Error::Unsupported.code());
    let _ = tag::RESULT;
}

#[test]
fn status_carries_draw_fields_and_new_firmware_version() {
    let (mut p, _h) = new_pump();
    let mut s = plain_session();
    let mut rx = plain_session();
    let mut out = [0u8; proto::FRAME_MAX];
    let frame = command_frame(&mut s, false, 3, cmd::GET_STATUS, &[]);
    let n = p.handle_frame(&mut rx, &frame, &mut out).unwrap();
    let st = status_of(&out[..n]).status.unwrap();
    assert_eq!(st.draw_state, proto::draw::IDLE);
    assert_eq!(st.draw_requested_mu, 0);
    assert_eq!(st.draw_done_mu, 0);
    assert_eq!(st.flags & (1 << 11), 0); // DRAWING
    assert_eq!(st.flags & (1 << 12), 0); // PRIME_REQUIRED (relaxed config)
    assert_eq!(st.fw_version, 0x0200);
}
