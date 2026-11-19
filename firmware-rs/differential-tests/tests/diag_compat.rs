//! Old-parser compatibility of the diagnostics protocol extension (docs/06-diagnostics.md 5.4, 6.1):
//! the frozen C reference parser (`op_*`) must skip the new tags and still decode the old commands,
//! and answer `UNSUPPORTED` to the new commands 0x20..0x22, which only Rust knows.

use differential_tests::desc::*;
use differential_tests::ffi::*;
use differential_tests::gen::{build_frame, payload_of};
use differential_tests::rng::Rng;
use openpatch_proto::tlv::TlvWriter;
use openpatch_proto::*;

const NEW_TAGS: [u8; 9] = [
    tag::DIAG_SUMMARY,
    tag::FRU_HEALTH,
    tag::DIAG_RECORD,
    tag::NEXT_DIAG_ID,
    tag::OLDEST_DIAG_ID,
    tag::DIAG_LATCHED,
    tag::SELFTEST_STATE,
    tag::DIAG_CODE,
    tag::POD_UID,
];

fn with_new_tags(payload: &[u8], r: &mut Rng) -> Vec<u8> {
    let mut out = payload.to_vec();
    let mut buf = [0u8; 200];
    let mut w = TlvWriter::new(&mut buf);
    for _ in 0..r.range(1, 4) {
        let t = NEW_TAGS[r.below(NEW_TAGS.len() as u64) as usize];
        let len = r.below(40) as usize;
        let v: Vec<u8> = (0..len).map(|_| r.below(256) as u8).collect();
        w.put(t, &v);
    }
    let n = w.finish().unwrap();
    out.extend_from_slice(&buf[..n]);
    out
}

fn c_decode(frame: &[u8]) -> Result<CmdDesc, u8> {
    CSession::new().decode(frame).map(|f| CmdDesc::from_flat(&f))
}

fn rust_decode(frame: &[u8]) -> Result<CmdDesc, u8> {
    let mut s = Session::new(NoCrypto, false, [0; 4], true);
    let mut plain = [0u8; FRAME_MAX];
    let f = s.open(frame, &mut plain).map_err(|e| e.code())?;
    decode_command(f.type_, f.seq, f.payload).map(|c| CmdDesc::from_command(&c)).map_err(|e| e.code())
}

#[test]
fn c_parser_skips_the_new_tags_on_every_old_command() {
    let mut r = Rng::new(0xD1A6_0001);
    let mut accepted = 0;
    for i in 0..3000u32 {
        let d = CmdDesc::random(&mut r);
        let clean = build_frame(PROTO_VERSION, d.ty, 0, (i % 60000 + 1) as u16, &payload_of(&d));
        let extra = with_new_tags(&payload_of(&d), &mut r);
        if FRAME_HEADER + extra.len() + FRAME_CRC > FRAME_MAX {
            continue;
        }
        let dirty = build_frame(PROTO_VERSION, d.ty, 0, (i % 60000 + 1) as u16, &extra);
        let (c_clean, c_dirty) = (c_decode(&clean), c_decode(&dirty));
        assert_eq!(c_clean, c_dirty, "C parser must ignore the new tags: {:02x?}", dirty);
        // and Rust agrees with C on the dirty frame (documented-difference-free for old commands)
        assert_eq!(c_dirty, rust_decode(&dirty), "{:02x?}", dirty);
        if c_dirty.is_ok() {
            accepted += 1;
        }
    }
    assert!(accepted > 300, "the corpus must exercise accepted commands ({accepted})");
}

#[test]
fn c_answers_unsupported_to_the_new_commands_and_rust_decodes_them() {
    for (ty, payload) in [
        (cmd::GET_FAULT_LOG, vec![tag::FROM_ID, 4, 1, 0, 0, 0]),
        (cmd::RUN_SELF_TEST, vec![tag::SUB_OP, 1, 2]),
        (cmd::CLEAR_DIAG, vec![tag::DIAG_CODE, 4, 0, 1, 0x60, 0x10]),
    ] {
        let frame = build_frame(PROTO_VERSION, ty, 0, 1, &payload);
        assert_eq!(CSession::new().decode(&frame), Err(9), "C reference: UNSUPPORTED for 0x{ty:02X}");
        assert!(rust_decode(&frame).is_ok(), "Rust decodes 0x{ty:02X}");
    }
    assert!(differential_tests::rust_only_cmd(0x20) && differential_tests::rust_only_cmd(0x22) && differential_tests::rust_only_cmd(0x0F));
    assert!(!differential_tests::rust_only_cmd(0x10) && !differential_tests::rust_only_cmd(0x23) && !differential_tests::rust_only_cmd(0x0E));
}

#[test]
fn c_encoder_output_is_decoded_by_the_new_response_decoder() {
    // a response made by the C reference has none of the new tags: the new decoder reads it with
    // all diagnostics fields absent (a v1-only pod)
    let mut r = Rng::new(7);
    for _ in 0..200 {
        let rsp = Response { type_: cmd::GET_STATUS, seq: 1, result: 0, status: Some(random_status(&mut r)), ..Default::default() };
        let c = c_encode_rsp(&rsp_to_flat(&rsp), 244).unwrap();
        let back = decode_response(cmd::GET_STATUS, 1, &c).unwrap();
        let s = back.status.unwrap();
        assert_eq!((s.diag, s.fru_health, s.pod_uid), (None, None, None));
        assert!(back.fault_log.is_none() && back.selftest.is_none() && back.diag_code.is_none());
    }
}
