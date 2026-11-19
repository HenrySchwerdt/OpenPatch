//! Diagnostics protocol extension (docs/06-diagnostics.md 5.4): codec round trips, size budget,
//! tolerance of the decoder, fuzzing, and the old-parser compatibility test.
use openpatch_diag::DiagRecord;
use openpatch_proto::tlv::{TlvReader, TlvWriter};
use openpatch_proto::*;
use proptest::prelude::*;

fn arb_record() -> impl Strategy<Value = DiagRecord> {
    (
        any::<u32>(),
        any::<u32>(),
        (any::<u8>(), any::<u8>(), any::<u8>(), any::<u8>()),
        (any::<u32>(), any::<i32>(), any::<i32>(), any::<u32>()),
        (any::<u8>(), any::<u8>(), any::<u16>()),
    )
        .prop_map(|(rec_id, code, (sev, act, fru, fru2), (t_s, a, b, c), (count, flags, cause))| DiagRecord {
            rec_id,
            code: openpatch_diag::DiagCode(code),
            severity: sev,
            action: act,
            fru,
            fru2,
            t_s,
            ctx_a: a,
            ctx_b: b,
            ctx_c: c,
            count,
            flags,
            cause_rec: cause,
        })
}

fn arb_summary() -> impl Strategy<Value = DiagSummary> {
    (any::<u32>(), (any::<u8>(), any::<u8>(), any::<u8>(), any::<u8>(), any::<u8>(), any::<u8>()), any::<u16>(), any::<u16>()).prop_map(
        |(top_code, (top_sev, top_action, top_fru, n_latched, n_active, post_state), next_rec_id_lo, schema)| DiagSummary {
            top_code,
            top_sev,
            top_action,
            top_fru,
            n_latched,
            n_active,
            post_state,
            next_rec_id_lo,
            schema,
        },
    )
}

fn arb_fault_log() -> impl Strategy<Value = FaultLog> {
    (any::<u32>(), any::<u32>(), prop::collection::vec(any::<u32>(), 0..=16), prop::collection::vec(arb_record(), 0..=4)).prop_map(|(n, o, l, r)| FaultLog {
        next_id: n,
        oldest_id: o,
        latched: l.into_iter().collect(),
        records: r.into_iter().collect(),
    })
}

proptest! {
    #[test]
    fn prop_record_bytes_roundtrip(r in arb_record()) {
        prop_assert_eq!(DiagRecord::from_bytes(&r.to_bytes()), Some(r));
    }

    #[test]
    fn prop_summary_bytes_roundtrip(d in arb_summary()) {
        prop_assert_eq!(DiagSummary::from_bytes(&d.to_bytes()), Some(d));
    }

    #[test]
    fn prop_fault_log_response_roundtrip(seq in any::<u16>(), res in any::<u8>(), log in arb_fault_log()) {
        let r = Response { type_: cmd::GET_FAULT_LOG, seq, result: res, fault_log: Some(log), ..Default::default() };
        let mut buf = [0u8; FRAME_MAX];
        let n = encode_response_payload(&r, &mut buf).unwrap();
        // 4 records + 16 latched codes: far below the 235 byte payload budget (244 - 9)
        prop_assert!(n <= 235, "{} bytes", n);
        let back = decode_response(cmd::GET_FAULT_LOG, seq, &buf[..n]).unwrap();
        prop_assert_eq!(back, r);
    }

    #[test]
    fn prop_status_with_diag_roundtrip(d in arb_summary(), h in any::<u64>(), uid in any::<u64>(), seq in any::<u16>()) {
        let st = Status { diag: Some(d), fru_health: Some(h), pod_uid: Some(uid), flags: st::DIAG_ACTIVE | st::LATCHED, ..Default::default() };
        let r = Response { type_: cmd::GET_STATUS, seq, result: 0, status: Some(st), ..Default::default() };
        let mut buf = [0u8; FRAME_MAX];
        let n = encode_response_payload(&r, &mut buf).unwrap();
        prop_assert_eq!(decode_response(cmd::GET_STATUS, seq, &buf[..n]).unwrap(), r);
    }

    #[test]
    fn prop_diag_commands_roundtrip(seq in any::<u16>(), from in any::<u32>(), max in any::<u8>(), sub in any::<u8>(), code in any::<u32>(), tod in prop::option::of(any::<u32>())) {
        for body in [CommandBody::GetFaultLog { from_id: from, max_events: max }, CommandBody::RunSelfTest { sub_op: sub }, CommandBody::ClearDiag { code }] {
            let c = Command { seq, time_of_day_ms: tod, body };
            let mut buf = [0u8; 64];
            let n = encode_command_payload(&c, &mut buf).unwrap();
            prop_assert_eq!(decode_command(c.body.type_id(), seq, &buf[..n]).unwrap(), c);
        }
    }

    #[test]
    fn prop_notification_roundtrip(kind in 1u8..=7, arg in any::<u32>(), rec in prop::option::of(arb_record())) {
        let mut buf = [0u8; 64];
        let n = encode_notification_payload_ex(kind, arg, rec.as_ref(), &mut buf).unwrap();
        let b = decode_notification_payload(&buf[..n]).unwrap();
        prop_assert_eq!((b.kind, b.arg, b.record), (kind, arg, rec));
    }

    // ---- fuzz: garbage never panics, wrong-size diagnostic TLVs never change state ----------------

    #[test]
    fn fuzz_decoders_never_panic(ty in any::<u8>(), seq in any::<u16>(), payload in prop::collection::vec(any::<u8>(), 0..300)) {
        let _ = decode_command(ty, seq, &payload);
        let _ = decode_response(ty, seq, &payload);
        let _ = decode_notification_payload(&payload);
        let _ = decode_frame(&payload);
        for t in [cmd::GET_STATUS, cmd::GET_FAULT_LOG, cmd::RUN_SELF_TEST, cmd::CLEAR_DIAG] {
            let _ = decode_response(t, seq, &payload);
            let _ = decode_command(t, seq, &payload);
        }
    }

    /// TLV soup built from the diagnostic tags only, with random lengths.
    #[test]
    fn fuzz_diag_tag_soup(items in prop::collection::vec((0x25u8..=0x30, prop::collection::vec(any::<u8>(), 0..70)), 0..12)) {
        let mut buf = [0u8; 600];
        let mut w = TlvWriter::new(&mut buf);
        w.put_u8(tag::RESULT, 0);
        for (t, v) in &items {
            w.put(*t, v);
        }
        let n = w.finish().unwrap();
        for ty in [cmd::GET_STATUS, cmd::GET_FAULT_LOG, cmd::RUN_SELF_TEST, cmd::CLEAR_DIAG] {
            let _ = decode_response(ty, 1, &buf[..n]);
            let _ = decode_command(ty, 1, &buf[1..n]);
        }
        let _ = decode_notification_payload(&buf[3..n]);
    }
}

#[test]
fn wrong_sized_diag_tlvs_are_skipped_not_fatal() {
    // a future schema may change a size: the old fields still decode, the diag field is ignored
    let mut buf = [0u8; 128];
    let mut w = TlvWriter::new(&mut buf);
    w.put_u8(tag::RESULT, 0);
    w.put_u16(tag::STATE_FLAGS, st::SUSPENDED);
    w.put(tag::DIAG_SUMMARY, &[0u8; 15]); // one byte too long
    w.put(tag::FRU_HEALTH, &[0u8; 7]);
    w.put(tag::POD_UID, &[0u8; 9]);
    let n = w.finish().unwrap();
    let r = decode_response(cmd::GET_STATUS, 1, &buf[..n]).unwrap();
    let s = r.status.unwrap();
    assert_eq!(s.flags, st::SUSPENDED);
    assert_eq!((s.diag, s.fru_health, s.pod_uid), (None, None, None));
}

#[test]
fn more_than_four_records_in_a_fault_log_is_a_frame_error() {
    let mut buf = [0u8; 400];
    let mut w = TlvWriter::new(&mut buf);
    w.put_u8(tag::RESULT, 0);
    w.put_u32(tag::NEXT_DIAG_ID, 1);
    w.put_u32(tag::OLDEST_DIAG_ID, 1);
    for _ in 0..5 {
        w.put(tag::DIAG_RECORD, &[0u8; 32]);
    }
    let n = w.finish().unwrap();
    assert_eq!(decode_response(cmd::GET_FAULT_LOG, 1, &buf[..n]), Err(Error::Frame));
}

#[test]
fn diag_commands_decode_rules() {
    // SUB_OP and DIAG_CODE are mandatory for their commands
    assert_eq!(decode_command(cmd::RUN_SELF_TEST, 1, &[]), Err(Error::Frame));
    assert_eq!(decode_command(cmd::CLEAR_DIAG, 1, &[]), Err(Error::Frame));
    assert_eq!(decode_command(cmd::CLEAR_DIAG, 1, &[tag::DIAG_CODE, 3, 0, 0, 0]), Err(Error::Frame), "wrong length");
    // GetFaultLog without tags: from 0, MAX_EVENTS default (the pod clamps 0 or above 4 to 4)
    let c = decode_command(cmd::GET_FAULT_LOG, 1, &[]).unwrap();
    assert!(matches!(c.body, CommandBody::GetFaultLog { from_id: 0, .. }));
    // ids above the last diagnostics command are still unknown
    assert_eq!(decode_command(0x13, 1, &[]), Err(Error::Unsupported));
}

#[test]
fn new_result_codes_have_the_documented_values() {
    assert_eq!(Error::SelfTestRefused.code(), 28);
    assert_eq!(Error::Latched.code(), 29);
    assert_eq!(Error::NotClearable.code(), 30);
    for c in 28..=30u8 {
        assert_eq!(Error::from_code(c).unwrap().code(), c);
    }
    assert_eq!(Error::from_code(31), None);
    assert_eq!((st::DIAG_ACTIVE, st::LATCHED), (1 << 13, 1 << 14));
    assert_eq!((notify::DIAG_RAISED, notify::DIAG_CLEARED, notify::SELFTEST_PROGRESS), (5, 6, 7));
}

// ---- size budget ---------------------------------------------------------------------------------------

#[test]
fn worst_case_fault_log_frame_is_at_most_244_bytes_even_encrypted() {
    use openpatch_proto::ccm_impl::AesCcm;
    let mut log = FaultLog { next_id: u32::MAX, oldest_id: 1, ..Default::default() };
    for i in 0..16u32 {
        let _ = log.latched.push(0x1000_0000 + i);
    }
    for i in 0..4u32 {
        let _ = log.records.push(DiagRecord { rec_id: i, count: 255, flags: 0xFF, ..Default::default() });
    }
    let r = Response { type_: cmd::GET_FAULT_LOG, seq: 0xFFFE, result: 0, fault_log: Some(log), ..Default::default() };
    let mut body = [0u8; FRAME_MAX];
    let n = encode_response_payload(&r, &mut body).unwrap();
    assert_eq!(n, 3 + 6 + 6 + 66 + 4 * 34, "RESULT + ids + latched + 4 records");
    let mut s = Session::new(AesCcm::new(&[7; 16]), true, [1, 2, 3, 4], false);
    let mut out = [0u8; 300];
    let total = s.seal(true, cmd::GET_FAULT_LOG | RSP_BIT, 0xFFFE, true, &body[..n], &mut out).unwrap();
    assert!(total <= FRAME_MAX, "{total}");
    assert_eq!(total, FRAME_HEADER + n + CCM_TAG_LEN + FRAME_CRC);
}

#[test]
fn status_with_all_diag_tags_still_fits_one_frame() {
    use openpatch_proto::ccm_impl::AesCcm;
    let st = Status {
        diag: Some(DiagSummary::default()),
        fru_health: Some(u64::MAX),
        pod_uid: Some(u64::MAX),
        draw_state: 4,
        ..Default::default()
    };
    let r = Response { type_: cmd::RELEASE, seq: 1, result: 0, status: Some(st), act_delivered_mu: Some(1), ..Default::default() };
    let mut body = [0u8; FRAME_MAX];
    let n = encode_response_payload(&r, &mut body).unwrap();
    let mut s = Session::new(AesCcm::new(&[7; 16]), true, [1, 2, 3, 4], false);
    let mut out = [0u8; 300];
    let total = s.seal(true, cmd::RELEASE | RSP_BIT, 1, true, &body[..n], &mut out).unwrap();
    assert!(total <= FRAME_MAX, "{total}");
}

// ---- old-parser compatibility -----------------------------------------------------------------------------------

/// Frozen copy of the v1 response decoder as it was before the diagnostics tags (tags 0x01..0x23
/// only, everything else skipped). A new response must decode with it exactly like the same
/// response without the new tags.
fn old_v1_decode(type_: u8, payload: &[u8]) -> Result<(u8, Vec<(u8, Vec<u8>)>), ()> {
    let mut out = Vec::new();
    let mut result = None;
    for item in TlvReader::new(payload) {
        let (t, v) = item.map_err(|_| ())?;
        match t {
            0x01 => result = Some(v[0]),
            0x09..=0x20 | 0x21..=0x23 => out.push((t, v.to_vec())),
            _ => {} // unknown tags (0x24 and up): skipped
        }
    }
    let _ = type_;
    Ok((result.ok_or(())?, out))
}

fn strip_new(payload: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    for item in TlvReader::new(payload) {
        let (t, v) = item.unwrap();
        if (0x27..=0x2F).contains(&t) {
            continue;
        }
        out.push(t);
        out.push(v.len() as u8);
        out.extend_from_slice(v);
    }
    out
}

proptest! {
    #[test]
    fn old_parser_skips_the_new_tags_and_decodes_the_old_ones(
        d in arb_summary(), h in any::<u64>(), uid in any::<u64>(), log in arb_fault_log(), sel in any::<[u8; 6]>(), code in any::<u32>()
    ) {
        let st = Status { flags: st::SUSPENDED | st::DIAG_ACTIVE, faults: 0x20, battery_mv: 3800, diag: Some(d), fru_health: Some(h), pod_uid: Some(uid), ..Default::default() };
        let mut cases = vec![
            Response { type_: cmd::GET_STATUS, seq: 1, result: 0, status: Some(st), ..Default::default() },
            Response { type_: cmd::GET_FAULT_LOG, seq: 2, result: 0, fault_log: Some(log), ..Default::default() },
            Response {
                type_: cmd::RUN_SELF_TEST,
                seq: 3,
                result: 28,
                selftest: Some(SelfTestState { state: sel[0], kind: sel[1], steps_passed: 1, steps_failed: 2 }),
                diag_code: Some(code),
                ..Default::default()
            },
        ];
        cases.push(Response { type_: cmd::CLEAR_DIAG, seq: 4, result: 0, diag: Some(d), ..Default::default() });
        for r in cases {
            let mut buf = [0u8; FRAME_MAX];
            let n = encode_response_payload(&r, &mut buf).unwrap();
            let new = &buf[..n];
            let old_view = old_v1_decode(r.type_, new);
            let without = strip_new(new);
            prop_assert_eq!(old_view, old_v1_decode(r.type_, &without), "old parser must see the same legacy fields");
            // the legacy fields also survive in the new decoder (status legacy part unchanged)
            if let Some(s) = &r.status {
                let back = decode_response(r.type_, r.seq, new).unwrap();
                let bs = back.status.unwrap();
                prop_assert_eq!((bs.flags, bs.faults, bs.battery_mv), (s.flags, s.faults, s.battery_mv));
            }
        }
    }
}

#[test]
fn old_command_decoder_ignores_trailing_diag_tags() {
    // an old command with the new tags appended decodes to the same command
    let mut buf = [0u8; 64];
    let c = Command::new(3, CommandBody::Bolus { amount_mu: 2000 });
    let n = encode_command_payload(&c, &mut buf).unwrap();
    let mut w = TlvWriter::new(&mut buf[n..]);
    w.put_u32(tag::DIAG_CODE, 0x1060_0100);
    w.put_u8(tag::SUB_OP, 2);
    w.put_u32(tag::FROM_ID, 9);
    let m = w.finish().unwrap();
    assert_eq!(decode_command(cmd::BOLUS, 3, &buf[..n + m]).unwrap(), c);
    // and the legacy GetHistory still takes FROM_ID/MAX_EVENTS exactly as before
    let h = decode_command(cmd::GET_HISTORY, 1, &[tag::FROM_ID, 4, 7, 0, 0, 0]).unwrap();
    assert_eq!(h.body, CommandBody::GetHistory { from_id: 7, max_events: 10 });
}
