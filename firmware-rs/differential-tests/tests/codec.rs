//! A. Frame / TLV / CRC codec differential (C `op_frame_*`, `op_session_open`, `op_cmd_decode`,
//! `op_cmd_encode_payload`, `op_rsp_encode_payload` vs the Rust `openpatch-proto` codec).
//! Command 0x0F (FillDraw) exists only in Rust (C answers UNSUPPORTED): pinned separately, never
//! part of the shared streams.

use differential_tests::desc::*;
use differential_tests::ffi::*;
use differential_tests::gen::{build_frame, payload_of};
use differential_tests::rng::Rng;
use openpatch_proto::crc::crc16_ccitt_false;
use openpatch_proto::*;
use proptest::prelude::*;

fn cfg(cases: u32) -> ProptestConfig {
    ProptestConfig { cases, max_shrink_iters: 0, failure_persistence: None, ..ProptestConfig::default() }
}

fn rust_decode(sess: &mut Session<NoCrypto>, bytes: &[u8]) -> Result<CmdDesc, u8> {
    let mut plain = [0u8; FRAME_MAX];
    let f = sess.open(bytes, &mut plain).map_err(|e| e.code())?;
    decode_command(f.type_, f.seq, f.payload).map(|c| CmdDesc::from_command(&c)).map_err(|e| e.code())
}

fn new_rust_session() -> Session<NoCrypto> {
    Session::new(NoCrypto, false, [0; 4], true)
}

/// Compare one input on (possibly stateful) sessions. Returns Ok(was_accepted).
fn compare_decode(cs: &mut CSession, rs: &mut Session<NoCrypto>, bytes: &[u8]) -> Result<bool, String> {
    if bytes.len() > 1 && differential_tests::rust_only_cmd(bytes[1]) {
        return Ok(false); // Rust-only command, documented
    }
    let c = cs.decode(bytes).map(|f| CmdDesc::from_flat(&f));
    let r = rust_decode(rs, bytes);
    if c != r {
        return Err(format!("decode mismatch for {bytes:02x?}\n  C    = {c:?}\n  Rust = {r:?}"));
    }
    Ok(c.is_ok())
}

fn known_tag_len(t: u8) -> usize {
    match t {
        tag::RESULT | tag::SUB_OP | tag::MAX_EVENTS | tag::ROLE => 1,
        tag::BASAL_SEG => 3,
        tag::RATE_MU_H | tag::DURATION_MIN | tag::PRIME_STEPS | tag::FAULT_MASK => 2,
        tag::AMOUNT_MU | tag::FILL_MU | tag::FROM_ID | tag::TIME_OF_DAY_MS | tag::PAIR_ID | tag::ACTIVATION_ID => 4,
        _ => 4,
    }
}

fn tlv_soup(r: &mut Rng) -> Vec<u8> {
    let mut p = Vec::new();
    for _ in 0..r.below(9) {
        let t = if r.chance(850) { r.range(1, 0x20) as u8 } else { r.below(256) as u8 };
        let l = if r.chance(700) { known_tag_len(t) } else { r.below(7) as usize };
        p.push(t);
        p.push(l as u8);
        p.extend(r.bytes(l));
    }
    if r.chance(80) {
        p.extend(r.bytes_between(0, 2)); // dangling bytes
    }
    p
}

fn random_type(r: &mut Rng) -> u8 {
    let t = if r.chance(900) { r.range(1, 0x0E) as u8 } else { r.below(256) as u8 };
    if differential_tests::rust_only_cmd(t) { cmd::GET_STATUS } else { t }
}

proptest! {
    #![proptest_config(cfg(1024))]

    #[test]
    fn crc16_matches(seed in any::<u64>()) {
        let mut r = Rng::new(seed);
        for _ in 0..16 {
            let n = r.below(260) as usize;
            let d = r.bytes(n);
            prop_assert_eq!(c_crc16(&d), crc16_ccitt_false(&d));
        }
    }

    #[test]
    fn frame_encode_and_decode_match(seed in any::<u64>()) {
        let mut r = Rng::new(seed);
        for _ in 0..12 {
            let n = r.below(250) as usize;
            let payload = r.bytes(n);
            let (ver, ty, flags, seq) = (r.below(256) as u8, r.below(256) as u8, r.below(256) as u8, r.below(65536) as u16);
            let cap = if r.chance(200) { r.below(260) as usize } else { 512 };
            let c = c_frame_encode(ver, ty, flags, seq, &payload, cap);
            let mut out = vec![0u8; cap.max(1)];
            let rr = encode_frame(&Frame { version: ver, type_: ty, flags, seq, payload: &payload }, &mut out[..cap])
                .map(|k| out[..k].to_vec()).map_err(|e| e.code());
            prop_assert_eq!(&c, &rr, "encode ver={} ty={} flags={} seq={} len={} cap={}", ver, ty, flags, seq, n, cap);
            // decode of the (possibly corrupted) bytes
            let mut bytes = c.unwrap_or_else(|_| r.bytes_between(0, 29));
            if !bytes.is_empty() && r.chance(400) {
                let i = r.below(bytes.len() as u64) as usize;
                bytes[i] ^= 1 << r.below(8);
            }
            if r.chance(100) { bytes.truncate(r.below(bytes.len() as u64 + 1) as usize); }
            let cd = c_frame_decode(&bytes);
            let rd = decode_frame(&bytes).map_err(|e| e.code());
            match (cd, rd) {
                (Ok(c), Ok(f)) => {
                    prop_assert_eq!(c[0] as u8, f.version);
                    prop_assert_eq!(c[1] as u8, f.type_);
                    prop_assert_eq!(c[2] as u8, f.flags);
                    prop_assert_eq!(c[3] as u16, f.seq);
                    prop_assert_eq!(&bytes[c[5] as usize..c[5] as usize + c[4] as usize], f.payload);
                }
                (Err(a), Err(b)) => prop_assert_eq!(a, b, "decode error for {:02x?}", bytes),
                (a, b) => prop_assert!(false, "accept/reject differs for {:02x?}: C={:?} Rust={:?}", bytes, a.is_ok(), b.is_ok()),
            }
        }
    }

    /// Random byte strings (almost always rejected: tests the error ordering Frame/CRC/Version).
    #[test]
    fn decode_random_byte_strings_match(seed in any::<u64>()) {
        let mut r = Rng::new(seed);
        for _ in 0..16 {
            let n = r.below(40) as usize;
            let mut bytes = r.bytes(n);
            if bytes.len() >= 9 && r.chance(600) {
                // make the length field consistent so that the CRC / version checks are reached
                let plen = (bytes.len() - 9) as u16;
                bytes[5..7].copy_from_slice(&plen.to_le_bytes());
                if r.chance(500) { bytes[0] = PROTO_VERSION; }
                if r.chance(500) {
                    let l = bytes.len();
                    let crc = c_crc16(&bytes[..l - 2]);
                    bytes[l - 2..].copy_from_slice(&crc.to_le_bytes());
                }
            }
            let mut cs = CSession::new();
            let mut rs = new_rust_session();
            if let Err(e) = compare_decode(&mut cs, &mut rs, &bytes) { prop_assert!(false, "{}", e); }
        }
    }

    /// Valid frames around random TLV soup (right/wrong lengths, unknown tags, dangling bytes).
    #[test]
    fn decode_tlv_soup_matches(seed in any::<u64>()) {
        let mut r = Rng::new(seed);
        let mut accepted = 0;
        for _ in 0..24 {
            let payload = tlv_soup(&mut r);
            let flags = if r.chance(850) { 0 } else { r.below(256) as u8 };
            let bytes = build_frame(PROTO_VERSION, random_type(&mut r), flags, r.below(65536) as u16, &payload);
            let mut cs = CSession::new();
            let mut rs = new_rust_session();
            match compare_decode(&mut cs, &mut rs, &bytes) { Ok(a) => accepted += a as u32, Err(e) => prop_assert!(false, "{}", e) }
        }
        let _ = accepted;
    }

    /// Valid encodings of random commands, then random mutation (bit flips, truncation, extension,
    /// CRC repaired or not).
    #[test]
    fn decode_mutated_valid_frames_match(seed in any::<u64>()) {
        let mut r = Rng::new(seed);
        for _ in 0..24 {
            let d = CmdDesc::random(&mut r);
            let mut payload = payload_of(&d);
            match r.below(6) {
                0 if !payload.is_empty() => { let i = r.below(payload.len() as u64) as usize; payload[i] ^= 1 << r.below(8); }
                1 if !payload.is_empty() => payload.truncate(r.below(payload.len() as u64) as usize),
                2 => payload.extend(r.bytes_between(1, 5)),
                3 if payload.len() > 2 => { let i = r.below(payload.len() as u64) as usize; payload[i] = r.below(256) as u8; }
                _ => {}
            }
            let mut bytes = build_frame(PROTO_VERSION, d.ty, 0, d.seq, &payload);
            if r.chance(150) { let l = bytes.len(); bytes[l - 1] ^= 0x40; }
            if r.chance(100) { bytes.truncate(r.below(bytes.len() as u64) as usize); }
            let mut cs = CSession::new();
            let mut rs = new_rust_session();
            if let Err(e) = compare_decode(&mut cs, &mut rs, &bytes) { prop_assert!(false, "{}", e); }
        }
    }

    /// Persistent sessions: replay protection, seq range limits (0xFFFE/0xFFFF), response-flag frames,
    /// encrypted flag without crypto.
    #[test]
    fn stateful_sessions_match(seed in any::<u64>()) {
        let mut r = Rng::new(seed);
        let mut cs = CSession::new();
        let mut rs = new_rust_session();
        let mut seq: u16 = 0;
        for _ in 0..60 {
            let d = CmdDesc::random(&mut r);
            seq = match r.below(10) {
                0 => seq,
                1 => seq.saturating_sub(r.below(3) as u16),
                2 => r.below(65536) as u16,
                3 => *r.pick(&[0xFFFEu16, 0xFFFF]),
                _ => seq.saturating_add(1),
            };
            let flags = *r.pick(&[0u8, 0, 0, 0, 0, FLAG_RESPONSE, FLAG_ENCRYPTED, FLAG_ENCRYPTED | FLAG_RESPONSE]);
            let bytes = build_frame(PROTO_VERSION, d.ty, flags, seq, &payload_of(&d));
            if let Err(e) = compare_decode(&mut cs, &mut rs, &bytes) { prop_assert!(false, "{}", e); }
        }
    }

    /// Commands encoded by Rust decode identically in C, and vice versa; the two encodings of the
    /// same logical command are byte-identical (including TooLarge for a too small buffer).
    #[test]
    fn command_encodings_are_byte_identical_and_cross_decode(seed in any::<u64>()) {
        let mut r = Rng::new(seed);
        for _ in 0..24 {
            let d = CmdDesc::random(&mut r);
            let cap = if r.chance(150) { r.below(30) as usize } else { 600 };
            let mut buf = vec![0u8; cap.max(1)];
            let rust = encode_command_payload(&d.to_command(), &mut buf[..cap]).map(|n| buf[..n].to_vec()).map_err(|e| e.code());
            let c = c_encode_cmd(&d.to_flat(), cap);
            prop_assert_eq!(&c, &rust, "encoding of {:?}", d);
            if let Ok(bytes) = c {
                // Rust bytes -> C decode, C bytes -> Rust decode: both give back the logical command
                let by_c = c_decode_payload(d.ty, d.seq, &bytes).map(|f| CmdDesc::from_flat(&f));
                prop_assert_eq!(by_c, Ok(d.clone()), "C decode of {:02x?}", bytes);
                let by_r = decode_command(d.ty, d.seq, &bytes).map(|c| CmdDesc::from_command(&c)).map_err(|e| e.code());
                prop_assert_eq!(by_r, Ok(d.clone()), "Rust decode of {:02x?}", bytes);
            }
        }
    }

    /// Response encoding: byte-identical for status-less answers and histories; with a status the
    /// Rust bytes minus the Rust-only tags 0x21..0x23 are byte-identical; Rust decodes C's bytes.
    #[test]
    fn response_encodings_match(seed in any::<u64>()) {
        let mut r = Rng::new(seed);
        for _ in 0..24 {
            let kind = r.below(4);
            let ty = if kind == 3 { cmd::GET_HISTORY } else { r.range(1, 0x0E) as u8 };
            let mut rsp = Response { type_: ty, seq: r.below(65535) as u16, result: r.below(30) as u8, ..Default::default() };
            if kind == 1 { rsp.status = Some(random_status(&mut r)); }
            if kind == 2 && r.chance(700) { rsp.act_delivered_mu = Some(r.u32()); }
            if kind == 2 { rsp.status = r.chance(500).then(|| random_status(&mut r)); }
            if kind == 3 { rsp.history = Some(random_history(&mut r)); }
            let mut buf = [0u8; 244];
            let rust = encode_response_payload(&rsp, &mut buf).map(|n| buf[..n].to_vec()).map_err(|e| e.code());
            let c = c_encode_rsp(&rsp_to_flat(&rsp), 244);
            let mut rust_cmp = rust.clone();
            if let (Ok(bytes), true) = (&rust, rsp.status.is_some()) {
                rust_cmp = Ok(strip_rust_only_tags(bytes));
            }
            prop_assert_eq!(&c, &rust_cmp, "response {:?}", rsp);
            if rsp.status.is_none() { prop_assert_eq!(&c, &rust); }
            if let Ok(cb) = &c {
                if rsp.status.is_none() || rsp.history.is_none() {
                    // decode of C's bytes by Rust gives back the logical response (history and
                    // status never together: both carry NEXT_EVENT_ID)
                    let back = decode_response(ty, rsp.seq, cb);
                    if rsp.history.is_none() || rsp.status.is_none() {
                        let mut want = rsp.clone();
                        if want.history.as_ref().map(|h| h.events.is_empty() && false).unwrap_or(false) { want.history = None; }
                        prop_assert_eq!(back.ok(), Some(want), "Rust decode of C response {:02x?}", cb);
                    }
                }
            }
        }
    }
}

fn strip_rust_only_tags(bytes: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    for item in openpatch_proto::tlv::TlvReader::new(bytes) {
        let (t, v) = item.expect("well formed");
        if matches!(t, tag::DRAW_STATE | tag::DRAW_REQUESTED_MU | tag::DRAW_DONE_MU) {
            continue;
        }
        out.push(t);
        out.push(v.len() as u8);
        out.extend_from_slice(v);
    }
    out
}

#[test]
fn documented_difference_fill_draw_is_rust_only() {
    // C answers 0x0F with UNSUPPORTED at decode time; Rust decodes it (FILL_MU tag).
    let payload = [tag::FILL_MU, 4, 0x10, 0x27, 0, 0];
    let frame = build_frame(PROTO_VERSION, cmd::FILL_DRAW, 0, 1, &payload);
    assert_eq!(CSession::new().decode(&frame), Err(9));
    let c = decode_command(cmd::FILL_DRAW, 1, &payload).expect("Rust decodes FillDraw");
    assert_eq!(c.body, CommandBody::FillDraw { amount_mu: 10_000 });
}

#[test]
fn known_vectors_match() {
    // CRC-16/CCITT-FALSE check value
    assert_eq!(c_crc16(b"123456789"), 0x29B1);
    assert_eq!(crc16_ccitt_false(b"123456789"), 0x29B1);
    // minimal GetStatus frame
    let c = c_frame_encode(1, cmd::GET_STATUS, 0, 7, &[], 64).unwrap();
    let mut out = [0u8; 64];
    let n = encode_frame(&Frame { version: 1, type_: cmd::GET_STATUS, flags: 0, seq: 7, payload: &[] }, &mut out).unwrap();
    assert_eq!(c, out[..n].to_vec());
}

/// The generators must not be vacuous: a healthy share of inputs is accepted AND a healthy share
/// rejected by both implementations.
#[test]
fn decode_corpora_exercise_accept_and_reject_paths() {
    let (mut acc, mut rej) = (0u32, 0u32);
    let mut r = Rng::new(0xABCD);
    for _ in 0..4000 {
        let d = CmdDesc::random(&mut r);
        let mut payload = payload_of(&d);
        if r.chance(400) && !payload.is_empty() {
            let i = r.below(payload.len() as u64) as usize;
            payload[i] ^= 1 << r.below(8);
        }
        let bytes = build_frame(PROTO_VERSION, d.ty, 0, 1, &payload);
        let mut cs = CSession::new();
        let mut rs = new_rust_session();
        match compare_decode(&mut cs, &mut rs, &bytes) {
            Ok(true) => acc += 1,
            Ok(false) => rej += 1,
            Err(e) => panic!("{e}"),
        }
    }
    assert!(acc > 1000 && rej > 100, "accepted {acc}, rejected {rej}");
}
