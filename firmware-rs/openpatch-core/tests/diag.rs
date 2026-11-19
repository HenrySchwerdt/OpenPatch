//! WP-1: the core diagnostics engine (docs/06-diagnostics.md 1.6, 2.2, 2.6, 2.7, 5.1, 5.2).
mod common;

use common::*;
use openpatch_core::diag::*;
use openpatch_core::hal::DiagEvent;
use openpatch_core::limits::*;
use openpatch_core::*;

fn w(t: u32) -> DiagState {
    let mut d = DiagState::new();
    d.set_time_s(t);
    d
}

// ---- records, ids, ring ------------------------------------------------------------------------

#[test]
fn record_ids_start_at_one_and_strictly_increase() {
    let mut d = w(5);
    let a = d.raise(Raise::new(codes::TMAG_NO_ACK));
    let b = d.raise(Raise::new(codes::LATCH_CANNOT_CLEAR));
    assert_eq!((a, b), (1, 2));
    let r = d.record(1).unwrap();
    assert_eq!((r.rec_id, r.code, r.t_s, r.count), (1, codes::TMAG_NO_ACK, 5, 1));
    // catalogue defaults land in the record
    assert_eq!((r.severity(), r.action(), r.fru()), (Severity::Fault, Some(Action::Isolate), Some(Fru::Podb)));
    assert_eq!(r.fru2, Fru::Ffc as u8);
    assert_eq!(d.next_id(), 3);
    assert_eq!(d.oldest_id(), 1);
}

#[test]
fn ring_overwrites_oldest_and_the_id_gap_is_visible() {
    let mut d = w(0);
    // distinct identities so nothing coalesces: alternate two W codes with clears in between
    for i in 0..(RING as u32 + 10) {
        d.set_time_s(i * 100);
        d.raise(Raise::new(codes::BATTERY_LOW).a(i as i32));
        d.clear(codes::BATTERY_LOW); // writes a clear record too: 2 records per round
    }
    assert_eq!(d.len(), RING);
    assert_eq!(d.next_id() - d.oldest_id(), RING as u32);
    assert!(d.oldest_id() > 1, "old records are gone");
    assert!(d.record(1).is_none());
    let mut out = [DiagRecord::default(); 8];
    // asking for an id that was overwritten starts at the oldest (the app sees the gap)
    let n = d.records_from(1, &mut out);
    assert_eq!(n, 8);
    assert_eq!(out[0].rec_id, d.oldest_id());
    for k in 1..n {
        assert_eq!(out[k].rec_id, out[k - 1].rec_id + 1);
    }
    // asking beyond the end gives nothing
    assert_eq!(d.records_from(d.next_id(), &mut out), 0);
    assert_eq!(d.records_from(d.next_id() - 1, &mut out), 1);
}

#[test]
fn restore_continues_the_persistent_ids() {
    let mut d = DiagState::restore(1000, &[]);
    assert_eq!(d.raise(Raise::new(codes::BATTERY_LOW)), 1000);
    assert_eq!(DiagState::restore(0, &[]).next_id(), 1, "id 0 is never used");
}

// ---- coalescing, escalation, clear ---------------------------------------------------------------

#[test]
fn info_repeats_within_10_s_are_coalesced_into_the_first_record() {
    let mut d = w(100);
    let a = d.raise(Raise::new(codes::BOOT).a(1));
    d.set_time_s(105);
    let b = d.raise(Raise::new(codes::BOOT).a(2));
    assert_eq!(a, b);
    let r = d.record(a).unwrap();
    assert_eq!((r.count, r.ctx_a), (2, 2), "count incremented, last context kept");
    d.set_time_s(116);
    let c = d.raise(Raise::new(codes::BOOT).a(3));
    assert_ne!(c, a, "outside the window: a new record");
}

#[test]
fn active_repeats_coalesce_and_count_saturates_at_255() {
    let mut d = w(0);
    let first = d.raise(Raise::new(codes::BATTERY_LOW));
    for i in 0..400 {
        d.set_time_s(i);
        assert_eq!(d.raise(Raise::new(codes::BATTERY_LOW).a(i as i32)), first);
    }
    assert_eq!(d.record(first).unwrap().count, 255);
    assert_eq!(d.active().len(), 1);
}

#[test]
fn escalation_makes_a_new_record_and_projects_to_the_legacy_bit() {
    let mut d = w(0);
    let a = d.raise(Raise::new(codes::TMAG_CRC_ERRORS));
    assert_eq!(d.legacy_faults(), Faults::NONE, "a W record never sets a legacy bit");
    let b = d.raise(Raise::new(codes::TMAG_CRC_ERRORS).severity(Severity::Fault));
    assert_ne!(a, b);
    let r = d.record(b).unwrap();
    assert_eq!(r.severity(), Severity::Fault);
    assert!(r.flags & flags::ESCALATED != 0);
    assert_eq!(d.legacy_faults(), Faults::INTERNAL);
    // the older W record is not active any more as a separate entry
    assert_eq!(d.active().len(), 1);
    assert_eq!(d.active()[0].severity, Severity::Fault);
}

#[test]
fn first_occurrence_after_a_clear_is_a_new_record_with_a_clear_record_between() {
    let mut d = w(0);
    let a = d.raise(Raise::new(codes::BATTERY_LOW));
    d.set_time_s(1);
    assert!(d.clear(codes::BATTERY_LOW));
    let clear = d.record(a + 1).unwrap();
    assert!(clear.flags & flags::CLEARED != 0);
    assert_eq!(clear.code, codes::BATTERY_LOW);
    assert!(!d.record(a).unwrap().is_active(), "the original is no longer active");
    assert!(d.active().is_empty());
    let b = d.raise(Raise::new(codes::BATTERY_LOW));
    assert!(b > a + 1, "new record even inside 10 s");
}

#[test]
fn notifications_raised_and_cleared_and_the_queue_is_lossy() {
    let mut d = w(0);
    let a = d.raise(Raise::new(codes::BATTERY_LOW));
    assert_eq!(d.take_note(), Some(DiagNote::Raised(d.record(a).unwrap())));
    d.clear(codes::BATTERY_LOW);
    assert_eq!(d.take_note(), Some(DiagNote::Cleared(codes::BATTERY_LOW)));
    assert_eq!(d.take_note(), None);
    for i in 0..(EVENTS_MAX as i32 + 5) {
        d.set_time_s(i as u32 * 20);
        d.raise(Raise::new(codes::BOOT).a(i));
    }
    let mut n = 0;
    while d.take_note().is_some() {
        n += 1;
    }
    assert_eq!(n, EVENTS_MAX, "oldest dropped, the reliable path is GetFaultLog");
}

// ---- cause chain ---------------------------------------------------------------------------------

#[test]
fn cause_chain_root_flag_and_headline() {
    let mut d = w(0);
    let root = d.raise(Raise::new(codes::I2C_ERROR_RATE));
    let mid = d.raise_caused_by(Raise::new(codes::TMAG_NO_ACK), root);
    let top = d.raise_caused_by(Raise::new(codes::ANGLE_CHANNEL_LOST), mid);
    assert!(d.record(root).unwrap().is_root());
    assert!(d.record(root).unwrap().flags & flags::ROOT != 0);
    assert_eq!(d.record(mid).unwrap().cause_rec, root as u16);
    assert_eq!(d.record(top).unwrap().cause_rec, mid as u16);
    assert!(d.record(top).unwrap().flags & flags::ROOT == 0);
    let r = d.root_of(&d.record(top).unwrap());
    assert_eq!(r.rec_id, root);
    // the headline is the ROOT of the most severe active record
    let s = d.summary();
    assert_eq!(s.top_code, codes::I2C_ERROR_RATE.0);
    assert_eq!(s.top_fru, Fru::Podb as u8);
    assert_eq!(s.n_active, 3);
}

#[test]
fn cause_chain_depth_is_bounded_to_four() {
    let mut d = w(0);
    let codes_chain = [
        codes::I2C_ERROR_RATE,
        codes::TMAG_NO_ACK,
        codes::ANGLE_CHANNEL_LOST,
        codes::STEPS_SHORT_OF_APPROVAL,
        codes::MOTOR_LEAD_OPEN,
        codes::TMAG_FROZEN,
        codes::FFC_ABSENT,
    ];
    let mut prev = 0u32;
    let mut ids = Vec::new();
    for c in codes_chain {
        let id = if prev == 0 { d.raise(Raise::new(c)) } else { d.raise_caused_by(Raise::new(c), prev) };
        ids.push(id);
        prev = id;
    }
    for id in ids {
        let mut depth = 1;
        let mut cur = d.record(id).unwrap();
        while cur.cause_rec != 0 {
            cur = d.record(cur.cause_rec as u32).expect("cause in log");
            depth += 1;
        }
        assert!(depth <= CHAIN_MAX, "record {id} has depth {depth}");
    }
}

#[test]
fn a_missing_cause_ends_the_walk_without_panic() {
    let mut d = w(0);
    let id = d.raise(Raise::new(codes::ANGLE_CHANNEL_LOST).caused_by(0x7777));
    let r = d.record(id).unwrap();
    assert_eq!(d.root_of(&r).rec_id, id);
    assert!(d.summary().top_code != 0);
}

// ---- latched set, clear rules per severity -------------------------------------------------------------

#[test]
fn a_latched_record_survives_acknowledge_and_clear_and_needs_its_verification() {
    let mut d = w(0);
    d.raise(Raise::new(codes::VMOT_STUCK_ON).a(1840).b(1000));
    assert_eq!(d.legacy_faults(), Faults::INTERNAL);
    assert_eq!(d.latched().len(), 1);
    assert!(d.record(1).unwrap().is_latched());
    assert!(!d.clear(codes::VMOT_STUCK_ON), "the condition going away does not unlatch");
    assert_eq!(d.clear_legacy(Faults::ALL), Faults::NONE, "Acknowledge never clears a latched code");
    assert_eq!(d.legacy_faults(), Faults::INTERNAL);
    assert_eq!(d.clear_diag(codes::VMOT_STUCK_ON, false, |_| false), Err(ClearError::NotClearable));
    assert_eq!(d.clear_diag(DiagCode::NONE, false, |_| false), Ok(0), "ClearDiag(all) skips latched codes");
    assert_eq!(d.clear_diag(codes::VMOT_STUCK_ON, true, |_| false), Ok(1), "verification test passed");
    assert!(d.latched().is_empty());
    assert_eq!(d.legacy_faults(), Faults::NONE);
    assert_eq!(d.clear_diag(codes::VMOT_STUCK_ON, true, |_| false), Err(ClearError::NotFound));
}

#[test]
fn clear_diag_all_clears_w_and_f_but_not_when_the_cause_persists() {
    let mut d = w(0);
    d.raise(Raise::new(codes::BATTERY_LOW));
    d.raise(Raise::new(codes::TMAG_NO_ACK));
    d.raise(Raise::new(codes::BATTERY_CRITICAL));
    d.raise(Raise::new(codes::VMOT_STUCK_ON));
    let n = d.clear_diag(DiagCode::NONE, false, |a| a.code.identity() == codes::BATTERY_CRITICAL.identity());
    assert_eq!(n, Ok(2));
    let left: Vec<_> = d.active().iter().map(|a| a.code.identity()).collect();
    assert!(left.contains(&codes::BATTERY_CRITICAL.identity()) && left.contains(&codes::VMOT_STUCK_ON.identity()));
    assert_eq!(
        d.clear_diag(codes::BATTERY_CRITICAL, false, |_| true),
        Err(ClearError::NotClearable)
    );
}

#[test]
fn restored_latched_set_keeps_the_pod_faulted() {
    let mut d = w(0);
    d.raise(Raise::new(codes::GATE_MCUEN_STUCK_PASS));
    d.raise(Raise::new(codes::LATCH_CANNOT_CLEAR));
    let saved: Vec<Latched> = d.latched().to_vec();
    assert_eq!(saved.len(), 2);
    let r = DiagState::restore(d.next_id() + 64, &saved);
    assert_eq!(r.legacy_faults(), Faults::INTERNAL);
    assert_eq!(r.summary().n_latched, 2);
    assert_eq!(r.latched(), &saved[..]);
}

// ---- legacy projection ----------------------------------------------------------------------------

#[test]
fn every_catalogue_code_projects_per_2_7() {
    for info in CATALOGUE.iter() {
        let mut d = w(0);
        d.raise(Raise::new(info.code));
        let f = d.legacy_faults();
        match info.legacy() {
            Some(bit) => assert_eq!(f, Faults(1 << bit), "{}", info.code),
            None => assert_eq!(f, Faults::NONE, "{} (sev {:?}) must not set a bit", info.code, info.severity),
        }
        assert_eq!(f.is_empty(), !info.severity.stops_delivery(), "{}", info.code);
    }
}

#[test]
fn legacy_bits_are_the_or_of_all_active_fault_records() {
    let mut d = w(0);
    d.raise(Raise::new(codes::OCCLUSION_SHORTFALL));
    d.raise(Raise::new(codes::ENC_REV_DEVIATION));
    d.raise(Raise::new(codes::CAL_RECORD_INVALID));
    d.raise(Raise::new(codes::BATTERY_LOW)); // W: nothing
    assert_eq!(d.legacy_faults(), Faults::OCCLUSION | Faults::ENCODER_DEVIATION | Faults::NO_CALIBRATION);
    // legacy acknowledge of one bit clears only that family
    let cleared = d.clear_legacy(Faults::OCCLUSION);
    assert_eq!(cleared, Faults::OCCLUSION);
    assert_eq!(d.legacy_faults(), Faults::ENCODER_DEVIATION | Faults::NO_CALIBRATION);
}

// ---- unknown codes ---------------------------------------------------------------------------------

#[test]
fn an_unknown_code_is_a_fault_never_dropped() {
    let mut d = w(7);
    let id = d.raise(Raise::new(DiagCode(0x1ABC_D005)).a(42));
    let r = d.record(id).unwrap();
    assert_eq!(r.code, codes::UNKNOWN_CODE_RAISED);
    assert_eq!(r.severity(), Severity::Fault);
    assert_eq!(r.fru(), Some(Fru::Fw));
    assert_eq!(r.action(), Some(Action::ReportBug));
    assert_eq!(r.ctx_a as u32, 0x1ABC_D005, "the raw code is kept in the context");
    assert_eq!(r.ctx_b, 42);
    assert_eq!(d.legacy_faults(), Faults::INTERNAL);
}

#[test]
fn the_literal_unknown_info_equals_the_catalogue_row() {
    // `unknown_info()` is a literal so the safety path needs no lookup: it must match the generated row
    let row = codes::UNKNOWN_CODE_RAISED.info().unwrap();
    let mut d = w(0);
    let id = d.raise(Raise::new(DiagCode(0xF000_0100)));
    let r = d.record(id).unwrap();
    assert_eq!((r.severity(), r.action(), r.fru(), r.fru2), (row.severity, Some(row.action), Some(row.fru), row.fru2 as u8));
}

// ---- summary, FRU health ---------------------------------------------------------------------------------

#[test]
fn summary_fields() {
    let mut d = w(0);
    assert_eq!(d.summary(), DiagSummary { schema: SCHEMA_VERSION, next_rec_id_lo: 1, ..Default::default() });
    d.raise(Raise::new(codes::BATTERY_LOW));
    d.set_time_s(3);
    d.raise(Raise::new(codes::VMOT_STUCK_ON));
    d.set_post_state(1);
    let s = d.summary();
    assert_eq!(s.top_code, codes::VMOT_STUCK_ON.0);
    assert_eq!((s.top_sev, s.top_action, s.top_fru), (3, Action::Replace as u8, Fru::Ctrl as u8));
    assert_eq!((s.n_latched, s.n_active, s.post_state), (1, 2, 1));
    assert_eq!(s.next_rec_id_lo, 3);
    assert_eq!(s.schema, SCHEMA_VERSION);
    assert_eq!(DiagSummary::from_bytes(&s.to_bytes()), Some(s));
}

#[test]
fn fru_health_is_unknown_until_proven_and_never_ok_with_an_active_record() {
    let mut d = w(0);
    assert_eq!(d.fru_health(), 0, "nothing proven: every FRU is UNKNOWN");
    d.set_proven(Fru::Ctrl, true);
    d.set_proven(Fru::Motor, true);
    let h = d.fru_health();
    assert_eq!(health::get(h, Fru::Ctrl as u8), health::OK);
    assert_eq!(health::get(h, Fru::Podb as u8), health::UNKNOWN);
    d.raise(Raise::new(codes::TMAG_CRC_ERRORS)); // W on PODB
    d.raise(Raise::new(codes::VMOT_STUCK_ON)); // L on CTRL
    let h = d.fru_health();
    assert_eq!(health::get(h, Fru::Podb as u8), health::DEGRADED);
    assert_eq!(health::get(h, Fru::Ctrl as u8), health::FAILED);
    assert_eq!(health::get(h, Fru::Motor as u8), health::OK);
    d.clear(codes::TMAG_CRC_ERRORS);
    assert_eq!(health::get(d.fru_health(), Fru::Podb as u8), health::UNKNOWN, "unproven again, not OK");
}

#[test]
fn fru_health_uses_the_root_cause_fru() {
    let mut d = w(0);
    let root = d.raise(Raise::new(codes::FFC_ABSENT)); // FFC
    d.raise_caused_by(Raise::new(codes::ANGLE_CHANNEL_LOST), root); // would say PODB
    let h = d.fru_health();
    assert_eq!(health::get(h, Fru::Ffc as u8), health::FAILED);
    assert_eq!(health::get(h, Fru::Podb as u8), health::UNKNOWN, "the consequence does not blame the FRU of its own default");
}

// ---- supervisor integration: legacy behaviour is a derived projection -----------------------------------

#[test]
fn supervisor_latch_and_acknowledge_keep_the_legacy_semantics() {
    let mut sv = SafetySupervisor::new(Millis(0), AngleCounts(0), cal_test().pulse_cal().unwrap());
    assert!(sv.faults().is_empty());
    for (bit, expect) in [
        (Faults::OCCLUSION, codes::OCCLUSION_SHORTFALL),
        (Faults::ENCODER_DEVIATION, codes::ENC_WINDOW_DEVIATION),
        (Faults::RESERVOIR_EMPTY, codes::RESERVOIR_EMPTY),
        (Faults::LIMIT_EXCEEDED, codes::HOURLY_LIMIT_VETO),
        (Faults::INTERNAL, codes::UNKNOWN_CODE_RAISED),
    ] {
        sv.latch(bit);
        assert!(sv.faults().contains(bit));
        assert!(sv.diag().active().iter().any(|a| a.code.identity() == expect.identity()), "{expect}");
        assert_eq!(sv.acknowledge(bit), Ok(()));
        assert!(!sv.faults().contains(bit));
        assert!(sv.diag().active().is_empty());
    }
}

#[test]
fn a_latched_code_makes_acknowledge_report_persists() {
    let mut sv = SafetySupervisor::new(Millis(0), AngleCounts(0), cal_test().pulse_cal().unwrap());
    sv.raise(Raise::new(codes::VMOT_STUCK_ON));
    assert_eq!(sv.acknowledge(Faults::INTERNAL), Err(Error::Persists));
    assert!(sv.faults().contains(Faults::INTERNAL));
    assert!(!sv.motor_allowed());
}

#[test]
fn invalid_calibration_raises_7_7d_001_and_projects_to_bit_6() {
    let sv = SafetySupervisor::new(Millis(0), AngleCounts(0), PulseCal::NONE);
    assert_eq!(sv.faults(), Faults::NO_CALIBRATION);
    let a = sv.diag().active()[0];
    assert_eq!(a.code, codes::CAL_RECORD_INVALID.with_inst(1));
}

#[test]
fn fault_free_probe_has_no_faults_and_does_not_touch_the_original() {
    let mut sv = SafetySupervisor::new(Millis(0), AngleCounts(0), cal_test().pulse_cal().unwrap());
    sv.raise(Raise::new(codes::TMAG_NO_ACK));
    let p = sv.fault_free_probe();
    assert!(p.faults().is_empty());
    assert!(!sv.faults().is_empty());
}

// ---- pump integration -------------------------------------------------------------------------------------

#[test]
fn boot_raises_an_info_record_that_changes_nothing_else() {
    let (p, _h) = new_pump();
    let d = p.supervisor().diag();
    assert_eq!(d.len(), 1);
    let r = d.record(1).unwrap();
    assert_eq!((r.code, r.severity()), (codes::BOOT, Severity::Info));
    assert_eq!(r.ctx_a, FW_VERSION as i32);
    assert!(p.supervisor().faults().is_empty());
    assert_eq!(d.summary().n_active, 0);
}

#[test]
fn hal_fault_becomes_a_hal_record_and_the_core_record_is_linked_to_it() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().fault = Some(MotorFault::SupplyMissing);
    h.st().steps_limit = 0; // the burst executes nothing
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 3);
    assert!(p.supervisor().faults().contains(Faults::INTERNAL), "legacy projection unchanged");
    let d = p.supervisor().diag();
    let hal = d.active().iter().find(|a| a.code.identity() == codes::VMOT_NOT_PRESENT.identity()).expect("HAL record");
    let core = d.active().iter().find(|a| a.code.identity() == codes::STEPS_SHORT_OF_APPROVAL.identity()).expect("core record");
    let core_rec = d.record(core.rec_id).unwrap();
    assert_eq!(core_rec.cause_rec, hal.rec_id as u16, "7-70-005 is caused by 1-06-002");
    assert_eq!(d.summary().top_code, codes::VMOT_NOT_PRESENT.0, "the headline is the root cause");
    assert_eq!(d.summary().top_fru, Fru::Ctrl as u8);
}

#[test]
fn refused_forward_burst_has_no_hardware_cause_but_still_one_record() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().fault = Some(MotorFault::ForwardWhileUndocked);
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 3);
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
    assert!(p.supervisor().diag().active().iter().any(|a| a.code.identity() == codes::STEPS_SHORT_OF_APPROVAL.identity()));
}

#[test]
fn hal_take_diag_events_are_raised_with_the_hals_own_code() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().diag_events.push(DiagEvent { code: codes::LATCH_CANNOT_SET, ctx_a: 7, ctx_b: 8, ctx_c: 9 });
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 2);
    let d = p.supervisor().diag();
    let a = d.active().iter().find(|a| a.code.identity() == codes::LATCH_CANNOT_SET.identity()).expect("raised");
    let r = d.record(a.rec_id).unwrap();
    assert_eq!((r.ctx_a, r.ctx_b, r.ctx_c), (7, 8, 9));
    assert!(p.supervisor().faults().contains(Faults::INTERNAL), "F projects to INTERNAL: delivery stops");
}

#[test]
fn lost_angle_sensor_raises_6_60_001() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().angle_missing = true;
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 2);
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
    assert!(p.supervisor().diag().active().iter().any(|a| a.code.identity() == codes::ANGLE_CHANNEL_LOST.identity()));
}

#[test]
fn stalled_spindle_and_current_rise_raise_their_own_codes() {
    // the sensor sees nothing: the 1 U window check trips first (6-60-007) and, because the spindle
    // barely moved, the old "no travel despite steps" OCCLUSION becomes 4-42-001 caused by it
    let (mut p, h) = running(50_000, 2_000);
    h.st().delivered_pct = 0;
    p.bolus(MilliUnits(4_000)).unwrap();
    run_secs(&mut p, &h, 60);
    assert!(p.supervisor().faults().contains(Faults::OCCLUSION | Faults::ENCODER_DEVIATION));
    let d = p.supervisor().diag();
    let win = d.active().iter().find(|a| a.code.identity() == codes::ENC_WINDOW_DEVIATION.identity()).expect("6-60-007");
    let jam = d.active().iter().find(|a| a.code.identity() == codes::CARRIAGE_JAM_FWD.identity()).expect("4-42-001");
    assert!(d.record(win.rec_id).unwrap().ctx_a > 100, "ctx_a is the deviation in permille, above the 10 % limit");
    assert_eq!(d.record(jam.rec_id).unwrap().cause_rec, win.rec_id as u16);
    // current rise
    let (mut p, h) = running(50_000, 2_000);
    h.st().current_ma = Some(OCCLUSION_CURRENT_MA + 20);
    p.bolus(MilliUnits(4_000)).unwrap();
    run_secs(&mut p, &h, 30);
    assert!(p.supervisor().faults().contains(Faults::OCCLUSION));
    let d = p.supervisor().diag();
    let a = d.active().iter().find(|a| a.code.identity() == codes::OCCLUSION_CURRENT_RISE.identity()).expect("5-53-002");
    assert_eq!(d.record(a.rec_id).unwrap().ctx_a, (OCCLUSION_CURRENT_MA + 20) as i32);
}

#[test]
fn acknowledge_clears_non_latched_fault_records_and_logs_a_clear_record() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().delivered_pct = 0;
    p.bolus(MilliUnits(4_000)).unwrap();
    run_secs(&mut p, &h, 60);
    assert!(p.supervisor().faults().contains(Faults::OCCLUSION));
    h.st().delivered_pct = 100;
    assert_eq!(p.acknowledge(Faults::ALL), Ok(()));
    assert!(p.supervisor().faults().is_empty());
    let d = p.supervisor().diag();
    assert!(d.active().is_empty());
    assert!(d.record(d.next_id() - 1).unwrap().is_clear_record());
}

#[test]
fn diag_notes_are_available_for_the_alert_characteristic() {
    let (mut p, h) = running(50_000, 2_000);
    while p.take_diag_note().is_some() {}
    h.st().diag_events.push(DiagEvent { code: codes::LATCH_CANNOT_SET, ..Default::default() });
    run_secs(&mut p, &h, 2);
    match p.take_diag_note() {
        Some(DiagNote::Raised(r)) => assert_eq!(r.code.identity(), codes::LATCH_CANNOT_SET.identity()),
        other => panic!("expected a raised note, got {other:?}"),
    }
}

#[test]
fn hal_defaults_are_no_ops() {
    struct Bare;
    impl Hal for Bare {
        fn motor_step(&mut self, s: Pulses) -> Pulses {
            s
        }
        fn motor_enable(&mut self, _: bool) {}
        fn angle_read(&mut self) -> Option<AngleCounts> {
            Some(AngleCounts(0))
        }
        fn watchdog_kick(&mut self) {}
        fn buzzer(&mut self, _: Buzzer) {}
        fn battery_mv(&mut self) -> u16 {
            3900
        }
        fn time_ms(&mut self) -> Millis {
            Millis(0)
        }
    }
    let mut b = Bare;
    assert_eq!(b.take_diag(), None);
    assert_eq!(b.interlock_state(), None);
    assert_eq!(b.selftest(openpatch_core::hal::SelfTestStep::GateCut), openpatch_core::hal::SelfTestOutcome::Unsupported);
    assert_eq!(b.reset_cause(), openpatch_core::hal::ResetCause::PowerOn);
    assert_eq!(b.breadcrumb(), 0);
    let r = b.motor_step_ex(Pulses(5));
    assert_eq!((r.executed, r.drv_fault, r.peak_ma, r.vmot_ok), (Pulses(5), false, None, true));
}

#[test]
fn ram_and_flash_footprint_is_bounded() {
    // RAM: ring 64 x 32 B + bookkeeping (host pointer width); flash: 150 catalogue rows
    let ram = std::mem::size_of::<DiagState>();
    eprintln!("DiagState = {ram} bytes, CodeInfo = {} bytes x {}", std::mem::size_of::<CodeInfo>(), CATALOGUE.len());
    assert!(ram < 5_000, "DiagState grew to {ram} bytes");
    assert!(std::mem::size_of::<CodeInfo>() * CATALOGUE.len() < 8_000);
}
