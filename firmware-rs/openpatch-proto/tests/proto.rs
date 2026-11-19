//! Port of `firmware/tests/test_proto.c` plus proptest round-trips.
use openpatch_proto::crc::crc16_ccitt_false;
use openpatch_proto::tlv::{TlvReader, TlvWriter};
use openpatch_proto::*;
use proptest::prelude::*;

const FW_VERSION: u16 = 0x0100;
const ROLE_B: u8 = 2;
const DS_PAUSED_UNDOCKED: u8 = 2;
const EV_BOLUS_START: u8 = 2;

fn frame(type_: u8, flags: u8, seq: u16, payload: &[u8]) -> Frame<'_> {
    Frame { version: PROTO_VERSION, type_, flags, seq, payload }
}

fn segs(v: &[(u8, u16)]) -> BasalSegs {
    v.iter().map(|&(s, r)| BasalSeg { start_slot: s, rate_mu_h: r }).collect()
}

// ---- CRC ----
#[test]
fn crc16_matches_ccitt_false_check_value() {
    assert_eq!(crc16_ccitt_false(b"123456789"), 0x29B1);
    assert_eq!(crc16_ccitt_false(&[]), 0xFFFF);
}

// ---- frame ----
#[test]
fn frame_golden_get_status() {
    let golden = [0x01, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0xBB, 0x7A];
    let mut out = [0u8; 32];
    let n = encode_frame(&frame(cmd::GET_STATUS, 0, 1, &[]), &mut out).unwrap();
    assert_eq!(&out[..n], &golden);
}

#[test]
fn frame_golden_bolus_decodes() {
    let golden = [0x01, 0x05, 0x00, 0x02, 0x01, 0x06, 0x00, 0x05, 0x04, 0xD0, 0x07, 0x00, 0x00, 0x38, 0x31];
    let f = decode_frame(&golden).unwrap();
    assert_eq!(f.type_, cmd::BOLUS);
    assert_eq!(f.seq, 0x0102);
    assert_eq!(f.payload.len(), 6);
    let c = decode_command(f.type_, f.seq, f.payload).unwrap();
    assert_eq!(c.body, CommandBody::Bolus { amount_mu: 2000 });
}

#[test]
fn frame_roundtrip_with_payload() {
    let payload: Vec<u8> = (0..20u8).map(|i| i.wrapping_mul(7)).collect();
    let mut buf = [0u8; 64];
    let n = encode_frame(&frame(0x42, FLAG_RESPONSE, 0xBEEF, &payload), &mut buf).unwrap();
    assert_eq!(n, FRAME_HEADER + 20 + FRAME_CRC);
    let d = decode_frame(&buf[..n]).unwrap();
    assert_eq!(d.version, PROTO_VERSION);
    assert_eq!(d.type_, 0x42);
    assert_eq!(d.flags, FLAG_RESPONSE);
    assert_eq!(d.seq, 0xBEEF);
    assert_eq!(d.payload, &payload[..]);
}

#[test]
fn frame_encode_rejects_bad_sizes() {
    // C cases with NULL frame / NULL payload (BAD_ARG) cannot occur: references and slices are never null.
    let big = [0u8; FRAME_MAX];
    let mut out = [0u8; FRAME_MAX + 8];
    let max_payload = FRAME_MAX - FRAME_HEADER - FRAME_CRC;
    assert_eq!(encode_frame(&frame(1, 0, 1, &big[..max_payload]), &mut out), Ok(FRAME_MAX));
    assert_eq!(encode_frame(&frame(1, 0, 1, &big[..max_payload + 1]), &mut out), Err(Error::TooLarge));
    assert_eq!(encode_frame(&frame(1, 0, 1, &big[..10]), &mut out[..10]), Err(Error::TooLarge));
}

#[test]
fn frame_decode_detects_corruption() {
    let mut buf = [0u8; 32];
    let n = encode_frame(&frame(cmd::GET_STATUS, 0, 1, &[]), &mut buf).unwrap();
    for i in 0..n {
        for bit in 0..8 {
            let mut copy = buf;
            copy[i] ^= 1 << bit;
            assert!(decode_frame(&copy[..n]).is_err(), "byte {i} bit {bit}");
        }
    }
    assert_eq!(decode_frame(&buf[..n - 1]), Err(Error::Frame));
    assert_eq!(decode_frame(&buf[..5]), Err(Error::Frame));
    let mut longer = [0u8; 40];
    longer[..n].copy_from_slice(&buf[..n]);
    assert_eq!(decode_frame(&longer[..n + 1]), Err(Error::Frame));
}

#[test]
fn frame_decode_rejects_other_versions_with_valid_crc() {
    let f = Frame { version: 2, type_: cmd::GET_STATUS, flags: 0, seq: 1, payload: &[] };
    let mut buf = [0u8; 16];
    let n = encode_frame(&f, &mut buf).unwrap();
    assert_eq!(decode_frame(&buf[..n]), Err(Error::Version));
}

#[test]
fn frame_decode_rejects_oversize() {
    let buf = [0u8; FRAME_MAX + 16];
    assert_eq!(decode_frame(&buf[..FRAME_MAX + 1]), Err(Error::Frame));
}

// ---- TLV ----
#[test]
fn tlv_write_read_roundtrip_and_unknown_tags_skipped() {
    let mut buf = [0u8; 64];
    let mut w = TlvWriter::new(&mut buf);
    w.put_u8(0x01, 0xAA);
    w.put_u16(0x70, 0xBBCC); // unknown tag
    w.put_u32(0x02, 0x1122_3344);
    let len = w.finish().expect("no overflow");
    assert_eq!(len, 3 + 4 + 6);
    let expect = [0x01, 0x01, 0xAA, 0x70, 0x02, 0xCC, 0xBB, 0x02, 0x04, 0x44, 0x33, 0x22, 0x11];
    assert_eq!(&buf[..len], &expect);
    let items: Vec<_> = TlvReader::new(&buf[..len]).collect();
    assert_eq!(items.len(), 3);
    assert!(items.iter().all(|i| i.is_ok()));
}

#[test]
fn tlv_writer_flags_overflow_and_stays_in_bounds() {
    let mut buf = [0u8; 5];
    let mut w = TlvWriter::new(&mut buf);
    w.put_u32(1, 7); // needs 6
    w.put_u8(1, 7); // later small writes must not resurrect partial state
    assert_eq!(w.finish(), None);
    assert_eq!(buf, [0u8; 5], "nothing written out of a failed put");
}

#[test]
fn tlv_reader_detects_truncation() {
    let bad = [0x01, 0x04, 0xAA]; // claims 4 bytes, has 1
    let mut r = TlvReader::new(&bad);
    assert_eq!(r.next(), Some(Err(())));
    assert_eq!(r.next(), None);
    let mut r = TlvReader::new(&[0x01]);
    assert_eq!(r.next(), Some(Err(())));
    assert_eq!(r.next(), None);
}

// ---- commands ----
fn cmd_roundtrip(c: &Command) -> Command {
    let mut buf = [0u8; 200];
    let n = encode_command_payload(c, &mut buf).unwrap();
    let d = decode_command(c.body.type_id(), c.seq, &buf[..n]).unwrap();
    assert_eq!(d.seq, c.seq);
    assert_eq!(d.body.type_id(), c.body.type_id());
    d
}

#[test]
fn cmd_roundtrip_simple_commands() {
    for body in [
        CommandBody::GetStatus,
        CommandBody::CancelTempBasal,
        CommandBody::CancelBolus,
        CommandBody::Suspend,
        CommandBody::Resume,
    ] {
        let d = cmd_roundtrip(&Command::new(9, body.clone()));
        assert_eq!(d.time_of_day_ms, None);
        assert_eq!(d.body, body);
    }
}

#[test]
fn cmd_roundtrip_basal_schedule_24_segments() {
    let v: Vec<(u8, u16)> = (0..24u8).map(|i| (i * 2, 50 * (i as u16 + 1))).collect();
    let d = cmd_roundtrip(&Command::new(1, CommandBody::SetBasalSchedule(segs(&v))));
    match d.body {
        CommandBody::SetBasalSchedule(s) => {
            assert_eq!(s.len(), 24);
            assert_eq!(s[23].start_slot, 46);
            assert_eq!(s[23].rate_mu_h, 1200);
        }
        other => panic!("{other:?}"),
    }
}

#[test]
fn cmd_roundtrip_temp_bolus_fill_ack_history() {
    let b = CommandBody::SetTempBasal { rate_mu_h: 2350, duration_min: 90 };
    assert_eq!(cmd_roundtrip(&Command::new(0, b.clone())).body, b);
    let b = CommandBody::Bolus { amount_mu: 24950 };
    assert_eq!(cmd_roundtrip(&Command::new(0, b.clone())).body, b);
    let b = CommandBody::FillPrime { sub_op: SUBOP_FILL, fill_mu: 180000, prime_steps: 0 };
    assert_eq!(cmd_roundtrip(&Command::new(0, b.clone())).body, b);
    let b = CommandBody::FillPrime { sub_op: SUBOP_PRIME, fill_mu: 0, prime_steps: 30 };
    assert_eq!(cmd_roundtrip(&Command::new(0, b.clone())).body, b);
    let b = CommandBody::Acknowledge { fault_mask: 0x0005 };
    assert_eq!(cmd_roundtrip(&Command::new(0, b.clone())).body, b);
    let b = CommandBody::GetHistory { from_id: 0xDEAD_BEEF, max_events: 4 };
    assert_eq!(cmd_roundtrip(&Command::new(0, b.clone())).body, b);
}

#[test]
fn cmd_time_of_day_is_optional_on_any_command() {
    let mut c = Command::new(0, CommandBody::GetStatus);
    c.time_of_day_ms = Some(12 * 3_600_000);
    assert_eq!(cmd_roundtrip(&c).time_of_day_ms, Some(12 * 3_600_000));
}

#[test]
fn cmd_ack_defaults_to_all_and_history_defaults() {
    let d = decode_command(cmd::ACKNOWLEDGE, 1, &[]).unwrap();
    assert_eq!(d.body, CommandBody::Acknowledge { fault_mask: 0xFFFF });
    let d = decode_command(cmd::GET_HISTORY, 1, &[]).unwrap();
    assert_eq!(d.body, CommandBody::GetHistory { from_id: 0, max_events: HIST_MAX_PER_RESPONSE as u8 });
}

#[test]
fn cmd_decode_rejects_malformed_input() {
    let short_amount = [tag::AMOUNT_MU, 2, 1, 2];
    assert_eq!(decode_command(cmd::BOLUS, 1, &short_amount), Err(Error::Frame));
    assert_eq!(decode_command(cmd::BOLUS, 1, &[]), Err(Error::Frame)); // amount required
    assert_eq!(decode_command(cmd::SET_TEMP_BASAL, 1, &[]), Err(Error::Frame));
    assert_eq!(decode_command(cmd::SET_BASAL_SCHEDULE, 1, &[]), Err(Error::Frame)); // needs >= 1 seg
    assert_eq!(decode_command(cmd::FILL_PRIME, 1, &[]), Err(Error::Frame));
    assert_eq!(decode_command(0x7E, 1, &[]), Err(Error::Unsupported));
    let trunc = [tag::AMOUNT_MU, 4, 1];
    assert_eq!(decode_command(cmd::BOLUS, 1, &trunc), Err(Error::Frame));
    // C: NULL output -> BAD_ARG; not representable in Rust.

    let mut many = [0u8; 2 + 25 * 5];
    let mut w = TlvWriter::new(&mut many);
    for i in 0..25u8 {
        w.put(tag::BASAL_SEG, &[i, 0, 0]);
    }
    let n = w.finish().unwrap();
    assert_eq!(decode_command(cmd::SET_BASAL_SCHEDULE, 1, &many[..n]), Err(Error::Frame)); // 25 > 24
}

#[test]
fn cmd_decode_ignores_unknown_tags() {
    let p = [0x77, 1, 9, tag::AMOUNT_MU, 4, 0x64, 0, 0, 0];
    let d = decode_command(cmd::BOLUS, 1, &p).unwrap();
    assert_eq!(d.body, CommandBody::Bolus { amount_mu: 100 });
}

#[test]
fn cmd_encode_reports_overflow_and_unknown() {
    let mut tiny = [0u8; 3];
    let c = Command::new(0, CommandBody::Bolus { amount_mu: 0 });
    assert_eq!(encode_command_payload(&c, &mut tiny), Err(Error::TooLarge));
    // C: encoding an unknown command type 0x55 -> UNSUPPORTED; the typed CommandBody enum makes
    // that state unrepresentable in Rust.
}

// ---- responses ----
#[test]
fn rsp_roundtrip_status() {
    let st = Status {
        flags: st::SUSPENDED | st::ALARM,
        faults: 0x0003,
        battery_mv: 3812,
        temp_rate_mu_h: 2100,
        temp_remaining_min: 25,
        current_rate_mu_h: 1000,
        fw_version: FW_VERSION,
        reservoir_mu: 123456,
        bolus_remaining_mu: 750,
        delivered_mu: 99999,
        scheduled_mu: 100000,
        next_event_id: 4242,
        last_seq: 0xBEEF,
        cal_drive_id: 1,
        cal_steps_per_rev: 20,
        cal_gear_ratio_x100: 500,
        cal_uu_per_step: 26100,
        pair_id: 0xCAFE_0001,
        wear_s: 3600,
        role: ROLE_B,
        delivery_state: DS_PAUSED_UNDOCKED,
        draw_state: draw::STALLED,
        draw_requested_mu: 5000,
        draw_done_mu: 4321,
        ..Default::default()
    };
    let r = Response { type_: cmd::GET_STATUS, seq: 77, result: 0, status: Some(st), ..Default::default() };
    let mut buf = [0u8; 200];
    let n = encode_response_payload(&r, &mut buf).unwrap();
    assert!(n > 0);
    let d = decode_response(r.type_, r.seq, &buf[..n]).unwrap();
    assert_eq!(d.status, Some(st));
    assert_eq!(d.result, 0);
    assert_eq!(d, r);
}

#[test]
fn rsp_roundtrip_history() {
    let mut events = heapless::Vec::new();
    for i in 0..3u32 {
        events
            .push(HistoryEvent { id: 98 + i, time_s: 1000 + i, kind: EV_BOLUS_START, a: -5 * i as i32, b: 7 })
            .unwrap();
    }
    let r = Response {
        type_: cmd::GET_HISTORY,
        seq: 5,
        history: Some(History { next_event_id: 100, oldest_event_id: 20, events }),
        ..Default::default()
    };
    let mut buf = [0u8; 200];
    let n = encode_response_payload(&r, &mut buf).unwrap();
    let d = decode_response(r.type_, r.seq, &buf[..n]).unwrap();
    let h = d.history.as_ref().unwrap();
    assert_eq!(h.events.len(), 3);
    assert_eq!(h.next_event_id, 100);
    assert_eq!(h.oldest_event_id, 20);
    assert_eq!(h.events[2].id, 100);
    assert_eq!(h.events[2].a, -10);
    assert_eq!(h.events[2].b, 7);
    assert_eq!(h.events[1].time_s, 1001);
    assert_eq!(h.events[1].kind, EV_BOLUS_START);
}

#[test]
fn rsp_result_only_and_errors() {
    let r = Response { type_: cmd::BOLUS, result: Error::Limit.code(), ..Default::default() };
    let mut buf = [0u8; 16];
    let n = encode_response_payload(&r, &mut buf).unwrap();
    assert_eq!(n, 3);
    let d = decode_response(r.type_, 1, &buf[..n]).unwrap();
    assert_eq!(d.result, Error::Limit.code());
    assert!(d.status.is_none());
    assert_eq!(decode_response(r.type_, 1, &[]), Err(Error::Frame)); // result is mandatory
    assert_eq!(encode_response_payload(&r, &mut buf[..2]), Err(Error::TooLarge));
    let bad = [tag::RESULT, 2, 0, 0];
    assert_eq!(decode_response(r.type_, 1, &bad), Err(Error::Frame));
    // too many history events
    let mut big = [0u8; 400];
    let mut w = TlvWriter::new(&mut big);
    w.put_u8(tag::RESULT, 0);
    for _ in 0..11 {
        w.put(tag::HISTORY_EVENT, &[0u8; 17]);
    }
    let n = w.finish().unwrap();
    assert_eq!(decode_response(cmd::GET_HISTORY, 1, &big[..n]), Err(Error::Frame));
    let shortev = [tag::RESULT, 1, 0, tag::HISTORY_EVENT, 2, 1, 2];
    assert_eq!(decode_response(cmd::GET_HISTORY, 1, &shortev), Err(Error::Frame));
}

#[test]
fn rsp_full_history_response_fits_one_frame() {
    let events = (0..HIST_MAX_PER_RESPONSE).map(|_| HistoryEvent::default()).collect();
    let r = Response {
        type_: cmd::GET_HISTORY,
        history: Some(History { events, ..Default::default() }),
        ..Default::default()
    };
    let mut buf = [0u8; FRAME_MAX];
    let n = encode_response_payload(&r, &mut buf).unwrap();
    assert!(n > 0);
    assert!(n + FRAME_HEADER + FRAME_CRC + CCM_TAG_LEN <= FRAME_MAX);
}

#[test]
fn frame_golden_bolus_ok_response() {
    let golden = [0x01, 0x85, 0x02, 0x02, 0x01, 0x03, 0x00, 0x01, 0x01, 0x00, 0x34, 0x06];
    let r = Response { type_: cmd::BOLUS, seq: 0x0102, ..Default::default() };
    let mut body = [0u8; 16];
    let mut out = [0u8; 32];
    let bl = encode_response_payload(&r, &mut body).unwrap();
    assert_eq!(bl, 3);
    let n = encode_frame(&frame(cmd::BOLUS | RSP_BIT, FLAG_RESPONSE, r.seq, &body[..bl]), &mut out).unwrap();
    assert_eq!(&out[..n], &golden);
}

// ---- proptest ----
fn arb_segs() -> impl Strategy<Value = BasalSegs> {
    prop::collection::vec((0u8..48, any::<u16>()), 1..=24).prop_map(|v| segs(&v))
}

fn arb_body() -> impl Strategy<Value = CommandBody> {
    prop_oneof![
        Just(CommandBody::GetStatus),
        arb_segs().prop_map(CommandBody::SetBasalSchedule),
        (any::<u16>(), any::<u16>()).prop_map(|(r, d)| CommandBody::SetTempBasal { rate_mu_h: r, duration_min: d }),
        Just(CommandBody::CancelTempBasal),
        any::<u32>().prop_map(|a| CommandBody::Bolus { amount_mu: a }),
        Just(CommandBody::CancelBolus),
        Just(CommandBody::Suspend),
        Just(CommandBody::Resume),
        any::<u32>().prop_map(|f| CommandBody::FillPrime { sub_op: SUBOP_FILL, fill_mu: f, prime_steps: 0 }),
        any::<u16>().prop_map(|p| CommandBody::FillPrime { sub_op: SUBOP_PRIME, fill_mu: 0, prime_steps: p }),
        any::<u16>().prop_map(|m| CommandBody::Acknowledge { fault_mask: m }),
        (any::<u32>(), any::<u8>()).prop_map(|(f, m)| CommandBody::GetHistory { from_id: f, max_events: m }),
        (any::<u32>(), any::<u8>()).prop_map(|(p, r)| CommandBody::SetPairing { pair_id: p, role: r }),
        any::<u32>().prop_map(|p| CommandBody::Release { pair_id: p }),
        (any::<u32>(), any::<u32>(), arb_segs(), prop::option::of((any::<u16>(), any::<u16>())))
            .prop_map(|(p, a, s, t)| CommandBody::Activate { pair_id: p, activation_id: a, schedule: s, temp: t }),
    ]
}

fn arb_status() -> impl Strategy<Value = Status> {
    (
        (any::<u16>(), any::<u16>(), any::<u16>(), any::<u16>(), any::<u16>(), any::<u16>(), any::<u16>()),
        (any::<u32>(), any::<u32>(), any::<u32>(), any::<u32>(), any::<u32>()),
        (any::<u16>(), any::<u16>(), any::<u16>(), any::<u16>(), any::<u32>()),
        (any::<u32>(), any::<u32>(), any::<u8>(), any::<u8>()),
    )
        .prop_map(|(a, b, c, d)| Status {
            flags: a.0,
            faults: a.1,
            battery_mv: a.2,
            temp_rate_mu_h: a.3,
            temp_remaining_min: a.4,
            current_rate_mu_h: a.5,
            fw_version: a.6,
            reservoir_mu: b.0,
            bolus_remaining_mu: b.1,
            delivered_mu: b.2,
            scheduled_mu: b.3,
            next_event_id: b.4,
            last_seq: c.0,
            cal_drive_id: c.1,
            cal_steps_per_rev: c.2,
            cal_gear_ratio_x100: c.3,
            cal_uu_per_step: c.4,
            pair_id: d.0,
            wear_s: d.1,
            role: d.2,
            delivery_state: d.3,
            draw_state: d.2,
            draw_requested_mu: d.0,
            draw_done_mu: d.1,
            ..Default::default()
        })
}

fn arb_event() -> impl Strategy<Value = HistoryEvent> {
    (any::<u32>(), any::<u32>(), any::<u8>(), any::<i32>(), any::<i32>())
        .prop_map(|(id, time_s, kind, a, b)| HistoryEvent { id, time_s, kind, a, b })
}

fn arb_response() -> impl Strategy<Value = Response> {
    let status = (any::<u16>(), any::<u8>(), any::<u8>(), prop::option::of(arb_status()), prop::option::of(any::<u32>()))
        .prop_map(|(seq, ty, res, st, act)| Response {
            type_: ty & 0x7F,
            seq,
            result: res,
            status: st,
            act_delivered_mu: act,
            history: None,
            ..Default::default()
        });
    let history = (any::<u16>(), any::<u8>(), any::<u32>(), any::<u32>(), prop::collection::vec(arb_event(), 0..=10))
        .prop_map(|(seq, res, n, o, ev)| Response {
            type_: cmd::GET_HISTORY,
            seq,
            result: res,
            status: None,
            act_delivered_mu: None,
            history: Some(History { next_event_id: n, oldest_event_id: o, events: ev.into_iter().collect() }),
            ..Default::default()
        });
    prop_oneof![status, history]
}

proptest! {
    #[test]
    fn prop_command_roundtrip(seq in any::<u16>(), tod in prop::option::of(any::<u32>()), body in arb_body()) {
        let c = Command { seq, time_of_day_ms: tod, body };
        let mut buf = [0u8; FRAME_MAX];
        let n = encode_command_payload(&c, &mut buf).unwrap();
        prop_assert_eq!(decode_command(c.body.type_id(), seq, &buf[..n]).unwrap(), c);
    }

    #[test]
    fn prop_response_roundtrip(r in arb_response()) {
        let mut buf = [0u8; FRAME_MAX];
        let n = encode_response_payload(&r, &mut buf).unwrap();
        let d = decode_response(r.type_, r.seq, &buf[..n]).unwrap();
        // a status response always carries next_event_id inside the status; history is separate
        prop_assert_eq!(d, r);
    }

    #[test]
    fn prop_frame_roundtrip(ty in any::<u8>(), fl in any::<u8>(), seq in any::<u16>(),
                            p in prop::collection::vec(any::<u8>(), 0..=FRAME_MAX - FRAME_HEADER - FRAME_CRC)) {
        let mut buf = [0u8; FRAME_MAX];
        let n = encode_frame(&frame(ty, fl, seq, &p), &mut buf).unwrap();
        let d = decode_frame(&buf[..n]).unwrap();
        prop_assert_eq!((d.type_, d.flags, d.seq, d.payload), (ty, fl, seq, &p[..]));
    }

    #[test]
    fn prop_decoders_never_panic(ty in any::<u8>(), seq in any::<u16>(), bytes in prop::collection::vec(any::<u8>(), 0..300)) {
        let _ = decode_frame(&bytes);
        let _ = decode_command(ty, seq, &bytes);
        let _ = decode_response(ty, seq, &bytes);
        let _ = TlvReader::new(&bytes).count();
    }
}
