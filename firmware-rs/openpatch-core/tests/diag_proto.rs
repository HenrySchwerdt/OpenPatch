//! WP-4 on the pod side: the diagnostics commands, status tags, flags, refusals and notification
//! frames through `Pump::handle_frame` / `Pump::notification_frame` (docs/06-diagnostics.md 5.4).
mod common;

use common::*;
use openpatch_core::diag::*;
use openpatch_core::hal::{DiagEvent, SelfTestOutcome};
use openpatch_core::limits::*;
use openpatch_core::*;
use openpatch_proto::{self as proto, notify, st, Command, CommandBody, Session, FRAME_MAX};

type S = Session<proto::NoCrypto>;

fn session() -> S {
    Session::new(proto::NoCrypto, false, [1, 2, 3, 4], true)
}

fn rpc(p: &mut Pump<MockHal>, s: &mut S, seq: u16, body: CommandBody) -> proto::Response {
    let cmd = Command::new(seq, body);
    let mut payload = [0u8; 64];
    let pl = proto::encode_command_payload(&cmd, &mut payload).unwrap();
    let mut frame = [0u8; FRAME_MAX];
    let n = s.seal(false, cmd.body.type_id(), seq, false, &payload[..pl], &mut frame).unwrap();
    let mut out = [0u8; FRAME_MAX];
    let m = p.handle_frame(s, &frame[..n], &mut out).unwrap();
    let f = proto::decode_frame(&out[..m]).unwrap();
    assert_eq!(f.type_, cmd.body.type_id() | proto::RSP_BIT);
    proto::decode_response(cmd.body.type_id(), f.seq, f.payload).unwrap()
}

/// A pump with a latched code (1-06-001, delivered by the HAL as data) and a W record.
fn latched_pump() -> (Pump<MockHal>, MockHal) {
    let (mut p, h) = running(50_000, 1_000);
    h.st().diag_events.push(DiagEvent { code: codes::VMOT_STUCK_ON, ctx_a: 1840, ctx_b: 1000, ctx_c: 12345 });
    run_secs(&mut p, &h, 2);
    assert!(p.supervisor().diag().latched().len() == 1);
    (p, h)
}

// ---- status ---------------------------------------------------------------------------------------------

#[test]
fn get_status_reports_summary_health_flags_and_uid() {
    let (mut p, _h) = new_pump();
    let mut s = session();
    let r = rpc(&mut p, &mut s, 1, CommandBody::GetStatus);
    let st0 = r.status.unwrap();
    let d = st0.diag.expect("DIAG_SUMMARY is the feature test");
    assert_eq!((d.top_code, d.n_active, d.n_latched, d.schema), (0, 0, 0, SCHEMA_VERSION));
    assert_eq!(d.next_rec_id_lo, 2, "the BOOT record has id 1");
    assert_eq!(st0.fru_health, Some(0), "nothing is proven: every FRU is UNKNOWN");
    assert_eq!(st0.pod_uid, None, "the mock HAL has no uid");
    assert_eq!(st0.flags & (st::DIAG_ACTIVE | st::LATCHED), 0);
}

#[test]
fn flags_and_summary_follow_the_diagnostic_state() {
    let (mut p, _h) = latched_pump();
    let mut s = session();
    let st0 = rpc(&mut p, &mut s, 1, CommandBody::GetStatus).status.unwrap();
    assert!(st0.flags & st::DIAG_ACTIVE != 0 && st0.flags & st::LATCHED != 0);
    assert!(st0.flags & st::ALARM != 0, "legacy alarm flag unchanged");
    assert_eq!(st0.faults, Faults::INTERNAL.bits(), "FAULT_MASK is the derived projection");
    let d = st0.diag.unwrap();
    assert_eq!((d.top_code, d.top_sev, d.top_fru, d.n_latched, d.n_active), (codes::VMOT_STUCK_ON.0, 3, Fru::Ctrl as u8, 1, 1));
    assert_eq!(proto::DiagSummary::from_bytes(&d.to_bytes()), Some(d));
    let h = st0.fru_health.unwrap();
    assert_eq!(health::get(h, Fru::Ctrl as u8), health::FAILED);
}

// ---- GetFaultLog ----------------------------------------------------------------------------------------------

#[test]
fn get_fault_log_pages_through_the_records() {
    let (mut p, h) = running(50_000, 1_000);
    let mut s = session();
    // six distinct W records
    for c in [codes::BATTERY_LOW, codes::TMAG_CRC_ERRORS, codes::TEMP_HIGH_WARN, codes::TEMP_LOW, codes::TIME_NOT_SET, codes::DRAW_ABORTED] {
        h.st().diag_events.push(DiagEvent { code: c, ..Default::default() });
    }
    run_secs(&mut p, &h, 2);
    let mut from = 0u32;
    let mut seen = Vec::new();
    let mut seq = 1;
    loop {
        let r = rpc(&mut p, &mut s, seq, CommandBody::GetFaultLog { from_id: from, max_events: 0 });
        seq += 1;
        assert_eq!(r.result, 0);
        let f = r.fault_log.unwrap();
        assert!(f.records.len() <= 4, "0 or above 4 gives 4");
        assert_eq!(f.next_id, p.supervisor().diag().next_id());
        assert_eq!(f.oldest_id, p.supervisor().diag().oldest_id());
        if f.records.is_empty() {
            break;
        }
        for rec in f.records.iter() {
            seen.push(rec.rec_id);
        }
        from = f.records.last().unwrap().rec_id + 1;
    }
    let expect: Vec<u32> = (1..p.supervisor().diag().next_id()).collect();
    assert_eq!(seen, expect, "every record exactly once, in order");
    assert!(seen.len() >= 7, "boot + six warnings");
    let r = rpc(&mut p, &mut s, seq, CommandBody::GetFaultLog { from_id: 2, max_events: 2 });
    assert_eq!(r.fault_log.unwrap().records.len(), 2);
}

#[test]
fn get_fault_log_carries_the_latched_set() {
    let (mut p, _h) = latched_pump();
    let mut s = session();
    let f = rpc(&mut p, &mut s, 1, CommandBody::GetFaultLog { from_id: 0, max_events: 4 }).fault_log.unwrap();
    assert_eq!(f.latched.as_slice(), &[codes::VMOT_STUCK_ON.0]);
    let rec = f.records.iter().find(|r| r.code == codes::VMOT_STUCK_ON).unwrap();
    assert_eq!((rec.ctx_a, rec.ctx_b, rec.ctx_c), (1840, 1000, 12345));
}

// ---- Latched refusals, ClearDiag --------------------------------------------------------------------------------

#[test]
fn resume_and_activate_are_refused_with_latched_and_the_root_code() {
    let (mut p, _h) = latched_pump();
    let mut s = session();
    let r = rpc(&mut p, &mut s, 1, CommandBody::Resume);
    assert_eq!(r.result, proto::Error::Latched.code());
    assert_eq!(r.diag_code, Some(codes::VMOT_STUCK_ON.0));
    let r = rpc(
        &mut p,
        &mut s,
        2,
        CommandBody::Activate {
            pair_id: TEST_PAIR,
            activation_id: 9,
            schedule: [proto::BasalSeg { start_slot: 0, rate_mu_h: 1000 }].into_iter().collect(),
            temp: None,
        },
    );
    assert_eq!(r.result, proto::Error::Latched.code());
    assert_eq!(r.diag_code, Some(codes::VMOT_STUCK_ON.0));
    assert!(r.status.is_some(), "Activate still reports the status");
}

#[test]
fn clear_diag_is_not_clearable_for_a_latched_code_and_not_found_for_an_inactive_one() {
    let (mut p, _h) = latched_pump();
    let mut s = session();
    let r = rpc(&mut p, &mut s, 1, CommandBody::ClearDiag { code: codes::VMOT_STUCK_ON.0 });
    assert_eq!(r.result, proto::Error::NotClearable.code());
    assert_eq!(r.diag_code, Some(codes::VMOT_STUCK_ON.0));
    assert_eq!(r.diag.unwrap().n_latched, 1);
    let r = rpc(&mut p, &mut s, 2, CommandBody::ClearDiag { code: codes::TMAG_NO_ACK.0 });
    assert_eq!(r.result, proto::Error::NotFound.code());
    // ClearDiag(all) succeeds but leaves the latched code
    let r = rpc(&mut p, &mut s, 3, CommandBody::ClearDiag { code: 0 });
    assert_eq!(r.result, 0);
    assert_eq!(r.diag.unwrap().n_latched, 1);
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
}

#[test]
fn clear_diag_clears_warnings_and_faults_whose_cause_is_gone() {
    let (mut p, h) = running(50_000, 1_000);
    let mut s = session();
    h.st().diag_events.push(DiagEvent { code: codes::TMAG_NO_ACK, ..Default::default() }); // F
    h.st().diag_events.push(DiagEvent { code: codes::BATTERY_LOW, ..Default::default() }); // W
    run_secs(&mut p, &h, 2);
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
    let r = rpc(&mut p, &mut s, 1, CommandBody::ClearDiag { code: 0 });
    assert_eq!(r.result, 0);
    let d = r.diag.unwrap();
    assert_eq!((d.n_active, d.top_code), (0, 0));
    assert!(p.supervisor().faults().is_empty());
    let st0 = rpc(&mut p, &mut s, 2, CommandBody::GetStatus).status.unwrap();
    assert_eq!(st0.flags & (st::DIAG_ACTIVE | st::ALARM), 0);
    // the clear records are part of the pull path
    let log = rpc(&mut p, &mut s, 3, CommandBody::GetFaultLog { from_id: 0, max_events: 4 }).fault_log.unwrap();
    assert!(log.next_id > 4);
}

#[test]
fn clear_diag_refuses_a_fault_whose_cause_persists() {
    let (mut p, h) = running(50_000, 1_000);
    let mut s = session();
    h.st().battery_mv = BATTERY_CRITICAL_MV - 50;
    run_secs(&mut p, &h, 2);
    assert!(p.supervisor().faults().contains(Faults::BATTERY_CRITICAL));
    let r = rpc(&mut p, &mut s, 1, CommandBody::ClearDiag { code: codes::BATTERY_CRITICAL.0 });
    assert_eq!(r.result, proto::Error::NotClearable.code());
    h.st().battery_mv = 3900;
    run_secs(&mut p, &h, 1);
    let r = rpc(&mut p, &mut s, 2, CommandBody::ClearDiag { code: codes::BATTERY_CRITICAL.0 });
    assert_eq!(r.result, 0);
    assert!(!p.supervisor().faults().contains(Faults::BATTERY_CRITICAL));
}

// ---- RunSelfTest ------------------------------------------------------------------------------------------------

#[test]
fn run_self_test_is_refused_unless_suspended_and_records_the_result() {
    let (mut p, h) = running(50_000, 1_000);
    let mut s = session();
    let r = rpc(&mut p, &mut s, 1, CommandBody::RunSelfTest { sub_op: 2 });
    assert_eq!(r.result, proto::Error::SelfTestRefused.code(), "delivering");
    p.suspend().unwrap();
    let r = rpc(&mut p, &mut s, 2, CommandBody::RunSelfTest { sub_op: 9 });
    assert_eq!(r.result, proto::Error::BadArg.code());
    let r = rpc(&mut p, &mut s, 3, CommandBody::RunSelfTest { sub_op: 2 });
    assert_eq!(r.result, 0);
    let t = r.selftest.unwrap();
    assert_eq!((t.state, t.kind, t.steps_passed, t.steps_failed), (proto::selftest::DONE, 2, 0, 0), "the mock HAL cannot do the proofs: UNKNOWN, not passed");
    let post = p.supervisor().diag().record(p.supervisor().diag().next_id() - 1).unwrap();
    assert_eq!(post.code.identity(), codes::POST_RESULT.identity());
    assert_eq!(post.code.inst(), 2);
    assert_eq!((post.ctx_a, post.ctx_b), (0, 0));
    assert_eq!(rpc(&mut p, &mut s, 4, CommandBody::GetStatus).status.unwrap().diag.unwrap().post_state, 0, "nothing passed, nothing failed: not 'passed'");
    let _ = h;
}

#[test]
fn a_failed_selftest_step_raises_the_hals_code_and_marks_post_failed() {
    struct Failing(MockHal);
    impl Hal for Failing {
        fn motor_step(&mut self, s: Pulses) -> Pulses {
            self.0.motor_step(s)
        }
        fn motor_enable(&mut self, e: bool) {
            self.0.motor_enable(e)
        }
        fn angle_read(&mut self) -> Option<AngleCounts> {
            self.0.angle_read()
        }
        fn watchdog_kick(&mut self) {
            self.0.watchdog_kick()
        }
        fn buzzer(&mut self, p: Buzzer) {
            self.0.buzzer(p)
        }
        fn battery_mv(&mut self) -> u16 {
            self.0.battery_mv()
        }
        fn time_ms(&mut self) -> Millis {
            self.0.time_ms()
        }
        fn docked(&mut self) -> bool {
            self.0.docked()
        }
        fn selftest(&mut self, step: openpatch_core::hal::SelfTestStep) -> SelfTestOutcome {
            match step {
                openpatch_core::hal::SelfTestStep::GateCut => SelfTestOutcome::Passed,
                _ => SelfTestOutcome::Failed(codes::GATE_DOCK_STUCK_PASS),
            }
        }
    }
    let hal = MockHal::new();
    let cal = cal_test();
    let mut p = Pump::new(Failing(hal.clone()), Some(&cal), CAPACITY_100, 1);
    let mut s = Session::new(proto::NoCrypto, false, [0; 4], true);
    let cmd = Command::new(1, CommandBody::RunSelfTest { sub_op: 2 });
    let mut payload = [0u8; 16];
    let pl = proto::encode_command_payload(&cmd, &mut payload).unwrap();
    let mut frame = [0u8; FRAME_MAX];
    let n = s.seal(false, cmd.body.type_id(), 1, false, &payload[..pl], &mut frame).unwrap();
    let mut out = [0u8; FRAME_MAX];
    let m = p.handle_frame(&mut s, &frame[..n], &mut out).unwrap();
    let f = proto::decode_frame(&out[..m]).unwrap();
    let r = proto::decode_response(cmd::RUN_SELF_TEST, f.seq, f.payload).unwrap();
    use proto::cmd;
    let t = r.selftest.unwrap();
    assert_eq!((t.steps_passed, t.steps_failed), (0b01, 0b10));
    let d = p.supervisor().diag();
    assert!(d.active().iter().any(|a| a.code.identity() == codes::GATE_DOCK_STUCK_PASS.identity() && a.severity == Severity::Latched));
    assert_eq!(d.summary().post_state, 4, "POST-A failed");
    assert!(p.supervisor().faults().contains(Faults::INTERNAL), "an L code stops delivery and projects");
}

// ---- notifications ------------------------------------------------------------------------------------------------

fn next_note(p: &mut Pump<MockHal>, s: &mut S) -> Option<proto::NotifyBody> {
    let mut out = [0u8; FRAME_MAX];
    let n = p.notification_frame(s, false, &mut out)?.unwrap();
    let f = proto::decode_frame(&out[..n]).unwrap();
    assert_eq!(f.type_, notify::FRAME_TYPE);
    Some(proto::decode_notification_payload(f.payload).unwrap())
}

#[test]
fn raised_cleared_and_selftest_notifications_are_framed_with_the_record() {
    let (mut p, h) = running(50_000, 1_000);
    let mut s = session();
    assert!(next_note(&mut p, &mut s).is_none(), "the BOOT record is information: no notification");
    h.st().diag_events.push(DiagEvent { code: codes::TMAG_CRC_ERRORS, ctx_a: 4, ctx_b: 3, ctx_c: 0 });
    run_secs(&mut p, &h, 2);
    let n = next_note(&mut p, &mut s).expect("DIAG_RAISED");
    assert_eq!(n.kind, notify::DIAG_RAISED);
    assert_eq!(n.arg, codes::TMAG_CRC_ERRORS.0);
    let rec = n.record.expect("the complete record travels with the notification");
    assert_eq!((rec.code, rec.ctx_a, rec.ctx_b), (codes::TMAG_CRC_ERRORS, 4, 3));
    assert_eq!(rec.severity(), Severity::Warning);
    assert!(next_note(&mut p, &mut s).is_none());

    // clear
    let _ = rpc(&mut p, &mut s, 1, CommandBody::ClearDiag { code: codes::TMAG_CRC_ERRORS.0 });
    let n = next_note(&mut p, &mut s).expect("DIAG_CLEARED");
    assert_eq!((n.kind, n.arg, n.record), (notify::DIAG_CLEARED, codes::TMAG_CRC_ERRORS.0, None));

    // self test
    p.suspend().unwrap();
    let _ = rpc(&mut p, &mut s, 2, CommandBody::RunSelfTest { sub_op: 1 });
    let mut kinds = Vec::new();
    while let Some(n) = next_note(&mut p, &mut s) {
        kinds.push((n.kind, n.arg));
    }
    assert!(kinds.contains(&(notify::SELFTEST_PROGRESS, 0)), "{kinds:?}");
}

#[test]
fn legacy_notifications_come_first_and_keep_their_kind() {
    let (mut p, h) = running(50_000, 1_000);
    let mut s = session();
    h.st().diag_events.push(DiagEvent { code: codes::LATCH_CANNOT_SET, ..Default::default() });
    run_secs(&mut p, &h, 2);
    let a = next_note(&mut p, &mut s).unwrap();
    assert_eq!((a.kind, a.arg), (notify::FAULT, Faults::INTERNAL.bits() as u32), "kind 2 FAULT is still sent");
    let b = next_note(&mut p, &mut s).unwrap();
    assert_eq!(b.kind, notify::DIAG_RAISED);
}

/// Records the nonce of every encrypt call; the "ciphertext" is the plaintext.
#[derive(Default)]
struct Spy {
    nonces: Vec<[u8; proto::CCM_NONCE_LEN]>,
}

impl proto::Ccm for Spy {
    fn encrypt(&mut self, nonce: &[u8; proto::CCM_NONCE_LEN], _aad: &[u8], pt: &[u8], ct: &mut [u8], tag: &mut [u8; proto::CCM_TAG_LEN]) -> Result<(), proto::CcmError> {
        self.nonces.push(*nonce);
        ct.copy_from_slice(pt);
        *tag = [0; proto::CCM_TAG_LEN];
        Ok(())
    }
    fn decrypt(&mut self, _: &[u8; proto::CCM_NONCE_LEN], _: &[u8], ct: &[u8], _: &[u8; proto::CCM_TAG_LEN], pt: &mut [u8]) -> Result<(), proto::CcmError> {
        pt.copy_from_slice(ct);
        Ok(())
    }
}

#[test]
fn encrypted_notifications_use_nonce_direction_2() {
    let (mut p, h) = running(50_000, 1_000);
    h.st().diag_events.push(DiagEvent { code: codes::TMAG_CRC_ERRORS, ..Default::default() });
    run_secs(&mut p, &h, 2);
    let mut s = Session::new(Spy::default(), true, [9, 8, 7, 6], false);
    let mut out = [0u8; FRAME_MAX];
    let n = p.notification_frame(&mut s, true, &mut out).unwrap().unwrap();
    let f = proto::decode_frame(&out[..n]).unwrap();
    assert!(f.flags & proto::FLAG_ENCRYPTED != 0);
    let nonce = s.ccm().nonces[0];
    assert_eq!(&nonce[..4], &[9, 8, 7, 6]);
    assert_eq!(nonce[4], 2, "notification direction");
    assert_eq!(&nonce[5..7], &f.seq.to_le_bytes());
    let ct_len = f.payload.len() - proto::CCM_TAG_LEN;
    let b = proto::decode_notification_payload(&f.payload[..ct_len]).unwrap();
    assert_eq!(b.kind, notify::DIAG_RAISED);
    assert_eq!(b.record.unwrap().code, codes::TMAG_CRC_ERRORS);
}

// ---- history event 31 -----------------------------------------------------------------------------------------------

#[test]
fn event_31_is_off_by_default_and_written_when_enabled() {
    let (mut p, h) = running(50_000, 1_000);
    let before = p.log().next_id();
    h.st().diag_events.push(DiagEvent { code: codes::TMAG_CRC_ERRORS, ctx_a: 7, ..Default::default() });
    run_secs(&mut p, &h, 2);
    let mut buf = [log::Event::default(); 32];
    let n = p.log().read(before, &mut buf);
    assert!(buf[..n].iter().all(|e| e.kind != EventType::Diag as u8), "off by default: the event log stays identical to the C reference");

    p.set_diag_history(true);
    h.st().diag_events.push(DiagEvent { code: codes::TEMP_LOW, ctx_a: 11, ..Default::default() });
    let before = p.log().next_id();
    run_secs(&mut p, &h, 2);
    let n = p.log().read(before, &mut buf);
    let e = buf[..n].iter().find(|e| e.kind == EventType::Diag as u8).expect("event 31");
    assert_eq!((e.a, e.b), (codes::TEMP_LOW.0 as i32, 11));
}

use openpatch_core::log;
