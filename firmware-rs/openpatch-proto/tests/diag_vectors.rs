//! Golden frames of the diagnostics protocol extension (docs/06-diagnostics.md 5.4), shared with
//! the Swift suite through `docs/vectors/diag-frames.json`.
//!
//! The file is written ONCE by this test (`OPENPATCH_WRITE_VECTORS=1 cargo test -p openpatch-proto
//! --test diag_vectors`) and then only verified: any change of the wire format that is not an
//! intended, re-generated vector change fails here (and in `OpenPatchCoreTests/DiagVectorTests`).
//! Every frame is given plain (real CRC) and encrypted (real AES-128-CCM, directional keys, nonce
//! direction 0 for commands, 1 for responses, 2 for notifications).

use openpatch_diag::{codes, flags, DiagRecord, DiagSummary};
use openpatch_proto::ccm_impl::AesCcm;
use openpatch_proto::*;
use serde_json::{json, Value};
use std::path::PathBuf;

const KEY_C2P: [u8; 16] = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F];
const KEY_P2C: [u8; 16] = [0xF0, 0xE1, 0xD2, 0xC3, 0xB4, 0xA5, 0x96, 0x87, 0x78, 0x69, 0x5A, 0x4B, 0x3C, 0x2D, 0x1E, 0x0F];
const SALT: [u8; 4] = [0xA1, 0xA2, 0xA3, 0xA4];

fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}

fn rec_json(r: &DiagRecord) -> Value {
    json!({
        "rec_id": r.rec_id, "code": r.code.0, "severity": r.severity, "action": r.action, "fru": r.fru, "fru2": r.fru2,
        "t_s": r.t_s, "ctx_a": r.ctx_a, "ctx_b": r.ctx_b, "ctx_c": r.ctx_c, "count": r.count, "flags": r.flags, "cause_rec": r.cause_rec,
        "bytes": hex(&r.to_bytes()),
    })
}

fn summary_json(d: &DiagSummary) -> Value {
    json!({
        "top_code": d.top_code, "top_sev": d.top_sev, "top_action": d.top_action, "top_fru": d.top_fru, "n_latched": d.n_latched,
        "n_active": d.n_active, "post_state": d.post_state, "next_rec_id_lo": d.next_rec_id_lo, "schema": d.schema,
    })
}

/// The worked example of 5.4: `1-06-001` latched, 1840 mV against 1000 mV.
pub fn rec_vmot() -> DiagRecord {
    DiagRecord {
        rec_id: 5,
        code: codes::VMOT_STUCK_ON,
        severity: 3,
        action: 8,
        fru: 1,
        fru2: 0,
        t_s: 300,
        ctx_a: 1840,
        ctx_b: 1000,
        ctx_c: 12345,
        count: 1,
        flags: flags::LATCHED | flags::ACTIVE | flags::ROOT,
        cause_rec: 0,
    }
}

/// `7-76-001` caused by record 5 (cause chain).
pub fn rec_interlock() -> DiagRecord {
    DiagRecord {
        rec_id: 6,
        code: codes::INTERLOCK_FAILED_LATCH,
        severity: 3,
        action: 8,
        fru: 1,
        fru2: 0,
        t_s: 301,
        ctx_a: -1,
        ctx_b: 0,
        ctx_c: 0,
        count: 2,
        flags: flags::LATCHED | flags::ACTIVE,
        cause_rec: 5,
    }
}

/// `A-A0-001/01` battery low (bench VBUS source), a warning.
pub fn rec_battery() -> DiagRecord {
    DiagRecord {
        rec_id: 7,
        code: codes::BATTERY_LOW.with_inst(1),
        severity: 1,
        action: 7,
        fru: 11,
        fru2: 15,
        t_s: 4000,
        ctx_a: 3480,
        ctx_b: 3500,
        ctx_c: 0,
        count: 3,
        flags: flags::ACTIVE | flags::ROOT | flags::FIRST_SINCE_BOOT,
        cause_rec: 0,
    }
}

/// A clear record for `7-76-001`.
pub fn rec_cleared() -> DiagRecord {
    DiagRecord {
        rec_id: 8,
        code: codes::INTERLOCK_FAILED_LATCH,
        severity: 3,
        action: 8,
        fru: 1,
        fru2: 0,
        t_s: 9000,
        ctx_a: 0,
        ctx_b: 0,
        ctx_c: 0,
        count: 1,
        flags: flags::CLEARED | flags::ROOT,
        cause_rec: 0,
    }
}

pub fn summary_example() -> DiagSummary {
    // 5.4: `27 0E | 00 01 60 10 | 03 08 01 01 01 03 | 06 00 | 01 00`
    DiagSummary { top_code: codes::VMOT_STUCK_ON.0, top_sev: 3, top_action: 8, top_fru: 1, n_latched: 1, n_active: 1, post_state: 3, next_rec_id_lo: 6, schema: 1 }
}

fn status_example() -> Status {
    Status {
        flags: st::SUSPENDED | st::ALARM | st::DOCKED | st::ACTIVE | st::DIAG_ACTIVE | st::LATCHED,
        faults: 0x0020,
        battery_mv: 3812,
        temp_rate_mu_h: 0,
        temp_remaining_min: 0,
        current_rate_mu_h: 1000,
        fw_version: 0x0200,
        reservoir_mu: 123_456,
        bolus_remaining_mu: 0,
        delivered_mu: 99_999,
        scheduled_mu: 100_000,
        next_event_id: 4242,
        last_seq: 12,
        cal_drive_id: 1,
        cal_steps_per_rev: 20,
        cal_gear_ratio_x100: 500,
        cal_uu_per_step: 26_100,
        pair_id: 0xCAFE_0001,
        wear_s: 3600,
        role: 1,
        delivery_state: 1,
        draw_state: 0,
        draw_requested_mu: 0,
        draw_done_mu: 0,
        diag: Some(summary_example()),
        // CTRL failed (3 << 2), PODB ok (1 << 4)
        fru_health: Some(0x1C),
        pod_uid: Some(0x0123_4567_89AB_CDEF),
    }
}

struct Case {
    name: &'static str,
    direction: &'static str,
    type_: u8,
    seq: u16,
    payload: Vec<u8>,
    expect: Value,
}

fn cmd_case(name: &'static str, seq: u16, body: CommandBody, expect: Value) -> Case {
    let c = Command::new(seq, body);
    let mut buf = [0u8; 128];
    let n = encode_command_payload(&c, &mut buf).unwrap();
    Case { name, direction: "command", type_: c.body.type_id(), seq, payload: buf[..n].to_vec(), expect }
}

fn rsp_case(name: &'static str, r: Response, expect: Value) -> Case {
    let mut buf = [0u8; FRAME_MAX];
    let n = encode_response_payload(&r, &mut buf).unwrap();
    Case { name, direction: "response", type_: r.type_ | RSP_BIT, seq: r.seq, payload: buf[..n].to_vec(), expect }
}

fn notify_case(name: &'static str, seq: u16, kind: u8, arg: u32, rec: Option<&DiagRecord>) -> Case {
    let mut buf = [0u8; 64];
    let n = encode_notification_payload_ex(kind, arg, rec, &mut buf).unwrap();
    let expect = json!({ "kind": kind, "arg": arg, "record": rec.map(rec_json) });
    Case { name, direction: "notification", type_: notify::FRAME_TYPE, seq, payload: buf[..n].to_vec(), expect }
}

fn latched_codes(n: usize) -> Vec<u32> {
    (0..n as u32).map(|i| 0x1050_0100 + (i << 8)).collect()
}

fn cases() -> Vec<Case> {
    let mut v = Vec::new();
    v.push(cmd_case(
        "cmd_get_fault_log",
        5,
        CommandBody::GetFaultLog { from_id: 5, max_events: 4 },
        json!({"command": "GetFaultLog", "from_id": 5, "max_events": 4}),
    ));
    v.push(cmd_case("cmd_run_self_test_post_a", 6, CommandBody::RunSelfTest { sub_op: 2 }, json!({"command": "RunSelfTest", "sub_op": 2})));
    v.push(cmd_case(
        "cmd_clear_diag_code",
        7,
        CommandBody::ClearDiag { code: codes::VMOT_STUCK_ON.0 },
        json!({"command": "ClearDiag", "code": codes::VMOT_STUCK_ON.0}),
    ));
    v.push(cmd_case("cmd_clear_diag_all", 8, CommandBody::ClearDiag { code: 0 }, json!({"command": "ClearDiag", "code": 0})));

    let st = status_example();
    v.push(rsp_case(
        "rsp_get_status_with_diag",
        Response { type_: cmd::GET_STATUS, seq: 9, result: 0, status: Some(st), ..Default::default() },
        json!({
            "result": 0, "flags": st.flags, "fault_mask": st.faults,
            "diag_summary": summary_json(&summary_example()), "fru_health": 0x1Cu64, "pod_uid": "0123456789abcdef",
        }),
    ));

    let mut log = FaultLog { next_id: 9, oldest_id: 5, ..Default::default() };
    let recs = [rec_vmot(), rec_interlock()];
    let _ = log.latched.push(codes::VMOT_STUCK_ON.0);
    let _ = log.latched.push(codes::INTERLOCK_FAILED_LATCH.0);
    for r in recs {
        let _ = log.records.push(r);
    }
    v.push(rsp_case(
        "rsp_get_fault_log",
        Response { type_: cmd::GET_FAULT_LOG, seq: 10, result: 0, fault_log: Some(log.clone()), ..Default::default() },
        json!({
            "result": 0, "next_id": 9, "oldest_id": 5, "latched": [codes::VMOT_STUCK_ON.0, codes::INTERLOCK_FAILED_LATCH.0],
            "records": recs.iter().map(rec_json).collect::<Vec<_>>(),
        }),
    ));

    // worst case: 4 records + 16 latched codes (the frame must still fit 244 bytes encrypted)
    let mut worst = FaultLog { next_id: 100, oldest_id: 1, ..Default::default() };
    for c in latched_codes(16) {
        let _ = worst.latched.push(c);
    }
    let wrecs = [rec_vmot(), rec_interlock(), rec_battery(), rec_cleared()];
    for r in wrecs {
        let _ = worst.records.push(r);
    }
    v.push(rsp_case(
        "rsp_get_fault_log_worst_case",
        Response { type_: cmd::GET_FAULT_LOG, seq: 11, result: 0, fault_log: Some(worst), ..Default::default() },
        json!({
            "result": 0, "next_id": 100, "oldest_id": 1, "latched": latched_codes(16),
            "records": wrecs.iter().map(rec_json).collect::<Vec<_>>(),
        }),
    ));

    v.push(rsp_case(
        "rsp_clear_diag_ok",
        Response { type_: cmd::CLEAR_DIAG, seq: 12, result: 0, diag: Some(DiagSummary { schema: 1, next_rec_id_lo: 9, ..Default::default() }), ..Default::default() },
        json!({"result": 0, "diag_summary": summary_json(&DiagSummary { schema: 1, next_rec_id_lo: 9, ..Default::default() })}),
    ));
    v.push(rsp_case(
        "rsp_clear_diag_not_clearable",
        Response {
            type_: cmd::CLEAR_DIAG,
            seq: 13,
            result: Error::NotClearable.code(),
            diag_code: Some(codes::VMOT_STUCK_ON.0),
            diag: Some(summary_example()),
            ..Default::default()
        },
        json!({"result": 30, "diag_code": codes::VMOT_STUCK_ON.0, "diag_summary": summary_json(&summary_example())}),
    ));
    v.push(rsp_case(
        "rsp_resume_refused_latched",
        Response { type_: cmd::RESUME, seq: 14, result: Error::Latched.code(), diag_code: Some(codes::VMOT_STUCK_ON.0), ..Default::default() },
        json!({"result": 29, "diag_code": codes::VMOT_STUCK_ON.0}),
    ));
    v.push(rsp_case(
        "rsp_self_test_done",
        Response {
            type_: cmd::RUN_SELF_TEST,
            seq: 15,
            result: 0,
            selftest: Some(SelfTestState { state: selftest::DONE, kind: 2, steps_passed: 0b0011, steps_failed: 0b0100 }),
            ..Default::default()
        },
        json!({"result": 0, "selftest": {"state": 2, "kind": 2, "steps_passed": 3, "steps_failed": 4}}),
    ));
    v.push(rsp_case(
        "rsp_self_test_refused",
        Response { type_: cmd::RUN_SELF_TEST, seq: 16, result: Error::SelfTestRefused.code(), selftest: Some(SelfTestState::default()), ..Default::default() },
        json!({"result": 28, "selftest": {"state": 0, "kind": 0, "steps_passed": 0, "steps_failed": 0}}),
    ));

    v.push(notify_case("notify_diag_raised", 0, notify::DIAG_RAISED, codes::VMOT_STUCK_ON.0, Some(&rec_vmot())));
    v.push(notify_case("notify_diag_cleared", 1, notify::DIAG_CLEARED, codes::INTERLOCK_FAILED_LATCH.0, None));
    v.push(notify_case("notify_selftest_progress", 2, notify::SELFTEST_PROGRESS, (3u32 << 16) | 4, None));
    v
}

fn build() -> Value {
    let mut s = Session::new(AesCcm::directional(&KEY_C2P, &KEY_P2C), true, SALT, false);
    let mut frames = Vec::new();
    for c in cases() {
        let mut plain = [0u8; FRAME_MAX];
        let mut enc = [0u8; FRAME_MAX];
        let (response, ty) = (c.direction != "command", c.type_);
        let pn = match c.direction {
            "notification" => s.seal_notification(ty, c.seq, false, &c.payload, &mut plain).unwrap(),
            _ => s.seal(response, ty, c.seq, false, &c.payload, &mut plain).unwrap(),
        };
        let en = match c.direction {
            "notification" => s.seal_notification(ty, c.seq, true, &c.payload, &mut enc).unwrap(),
            _ => s.seal(response, ty, c.seq, true, &c.payload, &mut enc).unwrap(),
        };
        assert!(en <= FRAME_MAX, "{}: encrypted frame of {en} bytes", c.name);
        frames.push(json!({
            "name": c.name, "direction": c.direction, "frame_type": c.type_, "seq": c.seq,
            "payload": hex(&c.payload), "wire_plain": hex(&plain[..pn]), "wire_encrypted": hex(&enc[..en]),
            "encrypted_len": en, "expect": c.expect,
        }));
    }
    json!({
        "description": "OpenPatch diagnostics protocol extension (docs/06-diagnostics.md 5.4, docs/04-protocol.md): golden frames with real CRC and AES-128-CCM. \
Generated by firmware-rs/openpatch-proto/tests/diag_vectors.rs, consumed by the Rust and the Swift suites. All bytes are hex. \
Commands are sealed with key c2p (nonce direction 0), responses and notifications with key p2c (directions 1 and 2); nonce = salt(4) | dir(1) | seq(2 LE) | 6 zero bytes.",
        "keys": {"c2p": hex(&KEY_C2P), "p2c": hex(&KEY_P2C), "salt": hex(&SALT)},
        "frames": frames,
    })
}

fn path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../docs/vectors/diag-frames.json")
}

#[test]
fn golden_file_is_up_to_date() {
    let want = serde_json::to_string_pretty(&build()).unwrap() + "\n";
    if std::env::var("OPENPATCH_WRITE_VECTORS").is_ok() {
        std::fs::write(path(), &want).unwrap();
    }
    let have = std::fs::read_to_string(path()).expect("docs/vectors/diag-frames.json (generate with OPENPATCH_WRITE_VECTORS=1)");
    assert_eq!(have, want, "diag-frames.json is stale: wire format changed? regenerate with OPENPATCH_WRITE_VECTORS=1 and review");
}

fn unhex(s: &str) -> Vec<u8> {
    (0..s.len() / 2).map(|i| u8::from_str_radix(&s[2 * i..2 * i + 2], 16).unwrap()).collect()
}

/// Decodes every golden frame from its wire bytes (both forms) and checks the `expect` block.
#[test]
fn every_golden_frame_decodes_to_its_expectation() {
    let file: Value = serde_json::from_str(&std::fs::read_to_string(path()).unwrap()).unwrap();
    let key = |n: &str| -> [u8; 16] { unhex(file["keys"][n].as_str().unwrap()).try_into().unwrap() };
    let salt: [u8; 4] = unhex(file["keys"]["salt"].as_str().unwrap()).try_into().unwrap();
    for f in file["frames"].as_array().unwrap() {
        let name = f["name"].as_str().unwrap();
        let payload = unhex(f["payload"].as_str().unwrap());
        for form in ["wire_plain", "wire_encrypted"] {
            let wire = unhex(f[form].as_str().unwrap());
            assert!(wire.len() <= FRAME_MAX, "{name}");
            // a fresh receiving session per frame: commands are opened by the pod side, responses and
            // notifications by the phone side (same two directional keys)
            let mut rx = Session::new(AesCcm::directional(&key("c2p"), &key("p2c")), true, salt, true);
            let mut plain = [0u8; FRAME_MAX];
            let dir = f["direction"].as_str().unwrap();
            let (ty, seq, got): (u8, u16, Vec<u8>) = if dir == "command" {
                let o = rx.open(&wire, &mut plain).unwrap_or_else(|e| panic!("{name} {form}: {e:?}"));
                (o.type_, o.seq, o.payload.to_vec())
            } else {
                // responses / notifications: only CRC + (for the encrypted form) the directional CCM check
                let fr = decode_frame(&wire).unwrap();
                let body = if fr.flags & FLAG_ENCRYPTED != 0 {
                    let ct_len = fr.payload.len() - CCM_TAG_LEN;
                    let mut nonce = [0u8; CCM_NONCE_LEN];
                    nonce[..4].copy_from_slice(&salt);
                    nonce[4] = if dir == "notification" { 2 } else { 1 };
                    nonce[5..7].copy_from_slice(&fr.seq.to_le_bytes());
                    let mut tag = [0u8; CCM_TAG_LEN];
                    tag.copy_from_slice(&fr.payload[ct_len..]);
                    let mut pt = vec![0u8; ct_len];
                    rx.ccm_mut().decrypt(&nonce, &wire[..FRAME_HEADER], &fr.payload[..ct_len], &tag, &mut pt).unwrap_or_else(|_| panic!("{name}: CCM"));
                    pt
                } else {
                    fr.payload.to_vec()
                };
                (fr.type_, fr.seq, body)
            };
            assert_eq!(got, payload, "{name} {form}");
            assert_eq!(ty as u64, f["frame_type"].as_u64().unwrap(), "{name}");
            assert_eq!(seq as u64, f["seq"].as_u64().unwrap(), "{name}");
            check_expect(name, dir, ty, seq, &got, &f["expect"]);
        }
    }
}

fn check_expect(name: &str, dir: &str, ty: u8, seq: u16, payload: &[u8], e: &Value) {
    let u = |k: &str| e[k].as_u64().unwrap_or_else(|| panic!("{name}: expect.{k}"));
    match dir {
        "command" => {
            let c = decode_command(ty, seq, payload).unwrap();
            match (e["command"].as_str().unwrap(), c.body) {
                ("GetFaultLog", CommandBody::GetFaultLog { from_id, max_events }) => assert_eq!((from_id as u64, max_events as u64), (u("from_id"), u("max_events"))),
                ("RunSelfTest", CommandBody::RunSelfTest { sub_op }) => assert_eq!(sub_op as u64, u("sub_op")),
                ("ClearDiag", CommandBody::ClearDiag { code }) => assert_eq!(code as u64, u("code")),
                (n, b) => panic!("{name}: {n} vs {b:?}"),
            }
        }
        "response" => {
            let r = decode_response(ty & !RSP_BIT, seq, payload).unwrap();
            assert_eq!(r.result as u64, u("result"), "{name}");
            if let Some(s) = &r.status {
                assert_eq!(s.flags as u64, u("flags"));
                assert_eq!(s.faults as u64, u("fault_mask"));
                assert_eq!(s.diag, Some(summary_example()));
                assert_eq!(s.fru_health, Some(u("fru_health")));
                assert_eq!(format!("{:016x}", s.pod_uid.unwrap()), e["pod_uid"].as_str().unwrap());
            }
            if let Some(f) = &r.fault_log {
                assert_eq!((f.next_id as u64, f.oldest_id as u64), (u("next_id"), u("oldest_id")));
                let want: Vec<u64> = e["latched"].as_array().unwrap().iter().map(|x| x.as_u64().unwrap()).collect();
                assert_eq!(f.latched.iter().map(|c| *c as u64).collect::<Vec<_>>(), want);
                let recs = e["records"].as_array().unwrap();
                assert_eq!(f.records.len(), recs.len());
                for (got, want) in f.records.iter().zip(recs) {
                    assert_eq!(&rec_json(got), want, "{name}");
                }
            }
            if let Some(c) = r.diag_code {
                assert_eq!(c as u64, u("diag_code"));
            }
            if let Some(t) = r.selftest {
                let w = &e["selftest"];
                assert_eq!((t.state as u64, t.kind as u64, t.steps_passed as u64, t.steps_failed as u64), (w["state"].as_u64().unwrap(), w["kind"].as_u64().unwrap(), w["steps_passed"].as_u64().unwrap(), w["steps_failed"].as_u64().unwrap()));
            }
            if r.status.is_none() {
                if let Some(d) = &r.diag {
                    assert_eq!(&summary_json(d), &e["diag_summary"], "{name}");
                }
            }
        }
        _ => {
            let n = decode_notification_payload(payload).unwrap();
            assert_eq!((n.kind as u64, n.arg as u64), (u("kind"), u("arg")));
            assert_eq!(n.record.as_ref().map(rec_json), if e["record"].is_null() { None } else { Some(e["record"].clone()) });
        }
    }
}

#[test]
fn worked_example_of_5_4_matches_byte_for_byte() {
    // DIAG_SUMMARY  27 0E | 00 01 60 10 | 03 08 01 01 01 03 | 06 00 | 01 00
    // (the printed example has head = 6 and post_state 3 as in summary_example())
    let mut buf = [0u8; 64];
    let r = Response { type_: cmd::CLEAR_DIAG, seq: 1, result: 0, diag: Some(summary_example()), ..Default::default() };
    let n = encode_response_payload(&r, &mut buf).unwrap();
    assert_eq!(&buf[..3], &[tag::RESULT, 1, 0]);
    assert_eq!(&buf[3..n], &[0x27, 0x0E, 0x00, 0x01, 0x60, 0x10, 0x03, 0x08, 0x01, 0x01, 0x01, 0x03, 0x06, 0x00, 0x01, 0x00]);
    // DIAG_RECORD   29 20 | 05 00 00 00 | 00 01 60 10 | 03 08 01 00 | 2C 01 00 00 | 30 07 00 00 | E8 03 00 00 | 39 30 00 00 | 01 43 00 00
    let mut b2 = [0u8; 64];
    let m = encode_notification_payload_ex(notify::DIAG_RAISED, codes::VMOT_STUCK_ON.0, Some(&rec_vmot()), &mut b2).unwrap();
    assert_eq!(&b2[..m][9..], &[
        0x29, 0x20, 0x05, 0, 0, 0, 0x00, 0x01, 0x60, 0x10, 0x03, 0x08, 0x01, 0x00, 0x2C, 0x01, 0, 0, 0x30, 0x07, 0, 0, 0xE8, 0x03, 0, 0, 0x39, 0x30, 0, 0, 0x01,
        0x43, 0, 0
    ]);
}
