//! Calibration is data, validated, and gates delivery (SMA pulse drive, exact rational uU/pulse).
//! Numeric expectations use the host-only `Test26100` / `Test8156` presets; production presets are
//! covered by tests/presets.rs.
mod common;

use common::*;
use openpatch_core::limits::*;
use openpatch_core::*;
use openpatch_proto::tlv::TlvReader;
use openpatch_proto::{cmd, st, tag, Command, CommandBody, Response, Status};

const UU: PulseCal = PulseCal { uu_num: TEST_UU, uu_den: 1, turn_x100: 25_600 };

fn cal_8156() -> DriveCal {
    DriveCal::preset(DriveId::Test8156 as u16).unwrap()
}

/// A record with the given edit applied and a CRC that matches the edited content.
fn tampered(edit: impl FnOnce(&mut DriveCal)) -> DriveCal {
    let mut c = cal_test();
    edit(&mut c);
    c.crc32 = c.compute_crc();
    c
}

fn rig(cal: Option<&DriveCal>) -> (Pump<MockHal>, MockHal) {
    let hal = MockHal::new();
    let mut p = Pump::new(hal.clone(), cal, CAPACITY_200, 1);
    p.set_config(PumpConfig::RELAXED);
    (p, hal)
}

fn advance(p: &mut Pump<MockHal>, h: &MockHal, secs: u32) {
    run_secs(p, h, secs as u64);
}

fn run_ms(de: &mut DeliveryEngine, ms: u32) -> u32 {
    let mut steps = 0;
    let mut t = 0;
    while t < ms {
        de.comm_heartbeat();
        steps += de.tick(Millis(1000)).0;
        t += 1000;
    }
    steps
}

fn flat_sched(rate: u32) -> BasalSchedule {
    BasalSchedule::flat(MilliUnitsPerHour(rate))
}

// ---- presets ---------------------------------------------------------------------------------
#[test]
fn cal_every_preset_validates_and_roundtrips() {
    assert!(drive_cal::PRESETS.len() >= 4);
    for pr in drive_cal::PRESETS {
        let c = DriveCal::from_preset(pr);
        assert_eq!(DriveCal::validate(Some(&c)), Ok(()), "{:?}", pr.id);
        assert_eq!(DriveCal::preset(pr.id as u16), Ok(c));
        assert_eq!(DriveId::from_u16(pr.id as u16), Some(pr.id));
        assert_eq!(c.pulse_cal(), Some(pr.cal()));
        assert_eq!(c.turn_x100(), pr.steps_per_rev as u32 * pr.gear_ratio_x100 as u32);
        // flash image round trip
        let back = DriveCal::from_bytes(&c.to_bytes());
        assert_eq!(back, c);
        assert_eq!(DriveCal::validate(Some(&back)), Ok(()));
    }
}

#[test]
fn cal_test_preset_matches_spec_numbers() {
    let a = cal_test();
    assert_eq!(a.uu_num, 26_100);
    assert_eq!(a.uu_den, 1);
    assert_eq!(a.turn_x100(), 25_600); // 256 steps per leadscrew turn
    assert_eq!((a.steps_per_rev, a.gear_ratio_x100), (16, 1600));
    let f = cal_8156();
    assert_eq!(f.uu_num, 8_156);
    assert_eq!(DriveCal::preset(99), Err(Error::BadArg));
    assert_eq!(DriveCal::preset(0), Err(Error::BadArg)); // no "none" drive id
    assert_eq!(DriveId::from_u16(0), None);
}

#[test]
fn cal_flash_image_layout_is_little_endian_24_bytes() {
    let c = cal_test();
    let b = c.to_bytes();
    assert_eq!(b.len(), 24);
    assert_eq!(&b[0..4], &drive_cal::DRIVE_CAL_MAGIC.to_le_bytes());
    assert_eq!(u16::from_le_bytes([b[4], b[5]]), 0x7F01);
    assert_eq!(u32::from_le_bytes([b[12], b[13], b[14], b[15]]), 26_100);
    assert_eq!(u32::from_le_bytes([b[16], b[17], b[18], b[19]]), 1);
    assert_eq!(u32::from_le_bytes([b[20], b[21], b[22], b[23]]), c.crc32);
    // a flipped bit in flash is caught
    let mut bad = b;
    bad[12] ^= 1;
    assert_eq!(DriveCal::validate(Some(&DriveCal::from_bytes(&bad))), Err(Error::Crc));
}

#[test]
fn cal_rejects_missing_corrupt_out_of_range_and_wrong_volume() {
    assert_eq!(DriveCal::validate(None), Err(Error::NotFound));
    let z = DriveCal::default(); // erased / zero flash
    assert_eq!(DriveCal::validate(Some(&z)), Err(Error::NotFound));
    // wrong CRC (bit flip, stale CRC)
    let mut c = cal_test();
    c.uu_num ^= 1;
    assert_eq!(DriveCal::validate(Some(&c)), Err(Error::Crc));
    // bad magic (CRC recomputed)
    let c = tampered(|c| c.magic ^= 1);
    assert_eq!(DriveCal::validate(Some(&c)), Err(Error::NotFound));
    // out of the sane range, valid CRC
    for bad in [0u32, 999, 60_001, 100_000, u32::MAX] {
        let c = tampered(|c| c.uu_num = bad);
        assert_eq!(DriveCal::validate(Some(&c)), Err(Error::Limit), "{bad}");
    }
    // zero denominator
    let c = tampered(|c| c.uu_den = 0);
    assert_eq!(DriveCal::validate(Some(&c)), Err(Error::BadArg));
    // plausible but wrong volume (in range, valid CRC): must not pass
    let c = tampered(|c| c.uu_num = 13_100);
    assert_eq!(DriveCal::validate(Some(&c)), Err(Error::BadArg));
    // wrong denominator (floor 13 050 is in range)
    let c = tampered(|c| c.uu_den = 2);
    assert_eq!(DriveCal::validate(Some(&c)), Err(Error::BadArg));
    // wrong steps_per_rev / gear ratio
    let c = tampered(|c| c.steps_per_rev += 1);
    assert_eq!(DriveCal::validate(Some(&c)), Err(Error::BadArg));
    let c = tampered(|c| c.gear_ratio_x100 += 1);
    assert_eq!(DriveCal::validate(Some(&c)), Err(Error::BadArg));
    // unknown drive id
    let c = tampered(|c| c.drive_id = 7);
    assert_eq!(DriveCal::validate(Some(&c)), Err(Error::BadArg));
    // reserved != 0
    let c = tampered(|c| c.reserved = 1);
    assert_eq!(DriveCal::validate(Some(&c)), Err(Error::BadArg));
    // an invalid record has no typed calibration
    assert_eq!(c.pulse_cal(), None);
    assert_eq!(c.turn_x100(), 0);
}

// ---- dose arithmetic with the 26 100 uU/pulse test drive ------------------------------------------------------
#[test]
fn cal_one_unit_bolus_is_38_pulses() {
    let cal = cal_test();
    let (mut p, h) = rig(Some(&cal));
    assert_eq!(p.fill(MilliUnits(100_000)), Ok(()));
    assert_eq!(activate(&mut p, 0), Ok(()));
    assert_eq!(p.resume(), Ok(()));
    assert_eq!(p.bolus(MilliUnits(1000)), Ok(()));
    advance(&mut p, &h, 60);
    let total = h.st().total_steps;
    assert!(total == 38 || total == 39);
    assert_eq!(total, 38); // floor(1000 / 26.1)
    let s = p.get_status();
    assert_eq!(s.faults, 0);
    assert_eq!(s.delivered_mu, 991);
    assert_eq!(s.reservoir_mu, 99_008); // 100000 - 38 * 26.1 = 99008.2
}

#[test]
fn cal_remainder_stays_exact_over_many_pulses() {
    let mut de = DeliveryEngine::new(UU);
    de.resume();
    let mut requested_mu: u64 = 0;
    let mut steps: u32 = 0;
    for _ in 0..1000 {
        // 1000 pulses of 0.05 U
        assert_eq!(de.start_bolus(MilliUnits(50)), Ok(()));
        steps += run_ms(&mut de, 5000);
        assert!(!de.bolus_active());
        requested_mu += 50;
        // running invariant: |requested - delivered| < 1 step + what is still in the accumulator
        let delivered_uu = steps as i64 * TEST_UU as i64;
        let requested_uu = requested_mu as i64 * 1000;
        assert!(requested_uu - delivered_uu >= 0);
        assert!(requested_uu - delivered_uu < TEST_UU as i64);
    }
    assert_eq!(requested_mu, 50_000);
    assert_eq!(steps, 1915); // floor(50 U / 26.1 mU)
    // average pulse = 0.05 U within 0.1 %
    let avg_u = steps as f64 * 0.0261 / 1000.0;
    assert!(avg_u > 0.05 * 0.999 && avg_u < 0.05 * 1.001);
    // exact remainder: accumulator holds (requested - delivered) uU, scaled by SCALED_PER_UU
    assert_eq!(de.accumulator(), (50_000i64 * 1000 - steps as i64 * TEST_UU as i64) * SCALED_PER_UU);
}

#[test]
fn cal_basal_day_delivers_scheduled_volume() {
    let mut de = DeliveryEngine::new(UU);
    assert_eq!(de.set_schedule(&flat_sched(1000)), Ok(()));
    de.resume();
    let mut steps = 0;
    for _ in 0..24 * 60 {
        steps += run_ms(&mut de, 60_000);
    }
    assert_eq!(steps, 919); // 24 U / 26.1 mU = 919.5
}

// ---- Faulhaber preset ------------------------------------------------------------------------
#[test]
fn cal_8156_preset_gives_about_122_5_pulses_per_unit() {
    let f = cal_8156();
    let uu = f.pulse_cal().unwrap();
    let mut de = DeliveryEngine::new(uu);
    de.resume();
    let mut steps = 0;
    for _ in 0..100 {
        // 100 U in 1 U boluses
        assert_eq!(de.start_bolus(MilliUnits(1000)), Ok(()));
        steps += run_ms(&mut de, 40_000);
    }
    let per_u = steps as f64 / 100.0;
    assert!(per_u > 122.0 && per_u < 123.0);
    assert_eq!(steps, 12_260); // floor(100 U / 8.156 mU)
    assert_eq!(uu.mu_to_pulses(MilliUnits(1000)), Pulses(122));
    assert_eq!(uu.pulses_to_mu(Pulses(1000)), MilliUnits(8156));
}

#[test]
fn cal_8156_pump_runs_and_limits_follow_calibration() {
    let f = cal_8156();
    let (mut p, h) = rig(Some(&f));
    assert_eq!(p.fill(MilliUnits(100_000)), Ok(()));
    assert_eq!(activate(&mut p, 0), Ok(()));
    // prime limit is a VOLUME (0.52 U), so it is more steps on the finer drive
    assert_eq!(p.prime(Pulses(65)), Err(Error::Limit));
    assert_eq!(p.prime(Pulses(64)), Ok(()));
    assert_eq!(h.st().total_steps, 64);
    // basal (a 1.5 U/min bolus would need > 1 pulse/s on this fine test drive)
    assert_eq!(p.set_schedule(&flat_sched(1000)), Ok(()));
    assert_eq!(p.resume(), Ok(()));
    let before = h.st().total_steps;
    advance(&mut p, &h, 3600); // 1 U/h = 122.6 pulses
    let d = h.st().total_steps - before;
    assert_eq!(d, 122);
    assert_eq!(p.get_status().faults, 0);
}

// ---- invalid calibration blocks delivery -----------------------------------------------------
fn expect_blocked(p: &mut Pump<MockHal>, h: &MockHal) {
    let s = p.get_status();
    assert!(s.faults & Faults::NO_CALIBRATION.bits() != 0);
    assert!(s.flags & st::ALARM != 0);
    assert_eq!(s.cal_uu_per_step, 0);
    assert_eq!(s.cal_drive_id, 0);
    assert_eq!(h.st().buzzer, Buzzer::Alarm);
    assert_eq!(p.resume(), Err(Error::Fault));
    assert_eq!(p.bolus(MilliUnits(50)), Err(Error::Fault));
    assert_eq!(p.set_schedule(&flat_sched(1000)), Err(Error::Fault));
    assert_eq!(p.set_temp_basal(MilliUnitsPerHour(1000), Minutes(30)), Err(Error::Fault));
    // priming goes through the same veto: no pulses
    let _ = p.fill(MilliUnits(50_000));
    assert!(p.prime(Pulses(5)).is_err());
    advance(p, h, 120);
    assert_eq!(h.st().total_steps, 0);
    assert!(!h.st().stepped_while_disabled);
    assert!(!h.st().enabled);
    // not acknowledgeable
    assert_eq!(p.acknowledge(Faults(0xFFFF)), Err(Error::Persists));
    let s = p.get_status();
    assert!(s.faults & Faults::NO_CALIBRATION.bits() != 0);
    assert_eq!(p.resume(), Err(Error::Fault));
}

#[test]
fn cal_missing_blocks_delivery() {
    let (mut p, h) = rig(None);
    assert!(p.calibration().is_none()); // C: !pump.cal_valid
    expect_blocked(&mut p, &h);
}

#[test]
fn cal_corrupt_crc_blocks_delivery() {
    let mut c = cal_test();
    c.uu_num = 13_100; // a wrong value written without fixing the CRC
    let (mut p, h) = rig(Some(&c));
    expect_blocked(&mut p, &h);
}

#[test]
fn cal_every_tampered_record_blocks_delivery() {
    let records = [
        tampered(|c| c.uu_num = 13_100),
        tampered(|c| c.uu_den = 2),
        tampered(|c| c.steps_per_rev += 1),
        tampered(|c| c.gear_ratio_x100 += 1),
        tampered(|c| c.magic ^= 1),
        tampered(|c| c.drive_id = 7),
        tampered(|c| c.reserved = 1),
        DriveCal::default(),
    ];
    for c in records {
        let (mut p, h) = rig(Some(&c));
        assert!(p.calibration().is_none());
        expect_blocked(&mut p, &h);
    }
}

#[test]
fn cal_out_of_range_with_valid_crc_blocks_delivery() {
    for bad in [0u32, 1, 999, 60_001, 1_000_000, 0xFFFF_FFFF] {
        let c = tampered(|c| c.uu_num = bad);
        let (mut p, h) = rig(Some(&c));
        expect_blocked(&mut p, &h);
    }
}

#[test]
fn cal_supervisor_range_check_is_independent() {
    // the supervisor does its own range check on the raw calibration it is handed
    let bad_cals = [
        PulseCal { uu_num: 0, uu_den: 1, turn_x100: 25_600 },
        PulseCal { uu_num: 999, uu_den: 1, turn_x100: 25_600 },
        PulseCal { uu_num: 60_001, uu_den: 1, turn_x100: 25_600 },
        PulseCal { uu_num: 522_200, uu_den: 1, turn_x100: 25_600 }, // floor out of range
        PulseCal { uu_num: 26_100, uu_den: 0, turn_x100: 25_600 },
        PulseCal { uu_num: 26_100, uu_den: 1, turn_x100: 0 },
        PulseCal::NONE,
    ];
    for bad in bad_cals {
        let mut sv = SafetySupervisor::new(Millis(0), AngleCounts(0), bad);
        sv.set_docked(true);
        sv.set_active(true);
        assert!(sv.faults().contains(Faults::NO_CALIBRATION), "{bad:?}");
        assert_eq!(sv.approve_steps(Millis(0), Pulses(10), MilliUnits(100_000)), Pulses(0));
        assert_eq!(sv.check_bolus(Millis(0), MilliUnits(50), MilliUnits(100_000)), Err(Error::Fault));
        assert_eq!(sv.acknowledge(Faults(0xFFFF)), Err(Error::Persists));
        assert!(sv.faults().contains(Faults::NO_CALIBRATION));
    }
    let good_cals = [
        PulseCal { uu_num: CAL_UU_MIN, uu_den: 1, turn_x100: 25_600 },
        PulseCal { uu_num: CAL_UU_MAX, uu_den: 1, turn_x100: 25_600 },
        PulseCal { uu_num: 26_100, uu_den: 1, turn_x100: 25_600 },
        PulseCal { uu_num: 522_200, uu_den: 9, turn_x100: 25_600 },
    ];
    for good in good_cals {
        let mut sv = SafetySupervisor::new(Millis(0), AngleCounts(0), good);
        sv.set_docked(true);
        sv.set_active(true);
        assert_eq!(sv.faults(), Faults::NONE, "{good:?}");
        assert_eq!(sv.approve_steps(Millis(0), Pulses(1), MilliUnits(100_000)), Pulses(1));
    }
}

#[test]
fn cal_engine_without_calibration_never_requests_pulses() {
    let mut de = DeliveryEngine::new(PulseCal::NONE);
    de.resume();
    assert_eq!(de.start_bolus(MilliUnits(1000)), Ok(()));
    assert_eq!(run_ms(&mut de, 60_000), 0);
    assert_eq!(de.accumulator(), 0);
}

#[test]
fn cal_valid_status_reports_calibration_over_protocol() {
    let cal = cal_test();
    let (mut p, _h) = rig(Some(&cal));
    let rsp = p.execute(&Command::new(1, CommandBody::GetStatus));
    let mut buf = [0u8; 200];
    let n = openpatch_proto::encode_response_payload(&rsp, &mut buf).unwrap();
    assert!(n > 0);
    let d = openpatch_proto::decode_response(cmd::GET_STATUS, 1, &buf[..n]).unwrap();
    let s = d.status.unwrap();
    assert_eq!(s.cal_drive_id, 0x7F01);
    assert_eq!(s.cal_uu_per_step, 26_100);
    assert_eq!(s.cal_steps_per_rev, 16);
    assert_eq!(s.cal_gear_ratio_x100, 1600);
    assert_eq!(s.faults & Faults::NO_CALIBRATION.bits(), 0);
}

#[test]
fn cal_status_tlv_wire_format() {
    let r = Response {
        status: Some(Status {
            cal_drive_id: 0x20,
            cal_uu_per_step: 4_935,
            cal_steps_per_rev: 20,
            cal_gear_ratio_x100: 2645,
            ..Default::default()
        }),
        ..Default::default()
    };
    let mut buf = [0u8; 200];
    let n = openpatch_proto::encode_response_payload(&r, &mut buf).unwrap();
    assert!(n > 0);
    let mut found = false;
    for item in TlvReader::new(&buf[..n]) {
        let (t, v) = item.unwrap();
        if t != tag::DRIVE_CAL {
            continue;
        }
        found = true;
        assert_eq!(v.len(), 10);
        assert_eq!(u16::from_le_bytes([v[0], v[1]]), 0x20);
        assert_eq!(u32::from_le_bytes([v[2], v[3], v[4], v[5]]), 4_935);
        assert_eq!(u16::from_le_bytes([v[6], v[7]]), 20);
        assert_eq!(u16::from_le_bytes([v[8], v[9]]), 2645);
    }
    assert!(found);
}
