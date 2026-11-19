//! Production drive presets (geared stepper): exact rational uU/step, steps per unit, steps per
//! leadscrew turn, angle per step, drift-free accumulation, mu->angle consistency, the wire
//! calibration record and tamper rejection. Host-only test presets: tests/calibration.rs.
mod common;

use common::*;
use openpatch_core::drive_cal::{
    Preset, FAULHABER_ADM0620_16, NFP_608_2645, PRESETS, ZWBPD006006_4_8, ZWBPD006006_6_43,
};
use openpatch_core::limits::*;
use openpatch_core::*;

struct Expect {
    preset: Preset,
    uu_num: u64,
    uu_den: u64,
    floor_uu: u32,
    turn_x100: u32,
    steps_per_unit: u32,
    angle_x1000: i64,
    wire_id: u16,
    /// Mock sensor: integer counts per step and the percent the sensor sees (true angle/step).
    mock_counts: i64,
    mock_pct: i64,
}

fn expectations() -> [Expect; 4] {
    [
        Expect { preset: NFP_608_2645, uu_num: 2_611_000, uu_den: 529, floor_uu: 4_935, turn_x100: 52_900,
            steps_per_unit: 202, angle_x1000: 7_742, wire_id: 0x20, mock_counts: 8, mock_pct: 97 },
        Expect { preset: ZWBPD006006_6_43, uu_num: 13_055_000, uu_den: 643, floor_uu: 20_303, turn_x100: 12_860,
            steps_per_unit: 49, angle_x1000: 31_850, wire_id: 0x21, mock_counts: 32, mock_pct: 100 },
        Expect { preset: ZWBPD006006_4_8, uu_num: 1_305_500, uu_den: 48, floor_uu: 27_197, turn_x100: 9_600,
            steps_per_unit: 36, angle_x1000: 42_666, wire_id: 0x22, mock_counts: 43, mock_pct: 99 },
        Expect { preset: FAULHABER_ADM0620_16, uu_num: 130_550, uu_den: 16, floor_uu: 8_159, turn_x100: 32_000,
            steps_per_unit: 122, angle_x1000: 12_800, wire_id: 0x23, mock_counts: 13, mock_pct: 98 },
    ]
}

fn flat(rate: u32) -> BasalSchedule {
    BasalSchedule::flat(MilliUnitsPerHour(rate))
}

fn pump_with(rec: Option<&DriveCal>, e: Option<&Expect>) -> (Pump<MockHal>, MockHal) {
    let hal = MockHal::new();
    if let Some(e) = e {
        hal.st().counts_per_step = e.mock_counts;
        hal.st().delivered_pct = e.mock_pct;
    }
    let mut p = Pump::new(hal.clone(), rec, CAPACITY_100, 1);
    p.set_config(PumpConfig::RELAXED);
    (p, hal)
}

fn pump_for(e: &Expect) -> (Pump<MockHal>, MockHal) {
    let rec = DriveCal::from_preset(&e.preset);
    pump_with(Some(&rec), Some(e))
}

#[test]
fn production_presets_are_in_the_table_and_valid() {
    for e in expectations() {
        assert!(PRESETS.contains(&e.preset));
        let rec = DriveCal::from_preset(&e.preset);
        assert_eq!(DriveCal::validate(Some(&rec)), Ok(()));
        assert_eq!(rec.drive_id, e.wire_id);
        assert_eq!(DriveCal::preset(e.wire_id), Ok(rec));
        assert_eq!(rec.turn_x100(), e.turn_x100);
        assert_eq!(rec.pulse_cal(), Some(e.preset.cal()));
        assert_eq!(DriveCal::from_bytes(&rec.to_bytes()), rec);
    }
    for (i, a) in PRESETS.iter().enumerate() {
        assert_eq!(DriveCal::validate(Some(&DriveCal::from_preset(a))), Ok(()));
        for b in &PRESETS[i + 1..] {
            assert_ne!(a.id as u16, b.id as u16);
        }
    }
}

#[test]
fn preset_exact_volume_per_step() {
    for e in expectations() {
        let c = e.preset.cal();
        assert_eq!((c.uu_num as u64, c.uu_den as u64), (e.uu_num, e.uu_den));
        assert_eq!(c.micro_u_floor(), e.floor_uu);
        assert_eq!(c.turn_x100, e.turn_x100);
        assert_eq!(e.turn_x100, e.preset.steps_per_rev as u32 * e.preset.gear_ratio_x100 as u32);
        assert!(cal_in_range(c));
        // uU/step = 130 550 / ratio: the rational is the published geometry, not a rounded float
        assert_eq!(e.uu_num * e.preset.gear_ratio_x100 as u64, 130_550 * 100 * e.uu_den);
        // den steps are exactly num uU; any multiple stays exact
        assert_eq!(c.pulses_to_micro(Pulses(e.uu_den as u32)).0, e.uu_num);
        assert_eq!(c.pulses_to_micro(Pulses(9 * e.uu_den as u32)).0, 9 * e.uu_num);
    }
}

#[test]
fn preset_steps_per_unit() {
    for e in expectations() {
        let c = e.preset.cal();
        assert_eq!(c.mu_to_pulses(MilliUnits(1000)), Pulses(e.steps_per_unit), "{:?}", e.preset.id);
        assert_eq!(c.mu_to_pulses(MilliUnits(100_000)).0 as u64, 100_000_000 * e.uu_den / e.uu_num);
        // never more volume than requested (floor)
        assert!(c.pulses_to_mu(c.mu_to_pulses(MilliUnits(1000))).0 <= 1000);
    }
}

#[test]
fn preset_steps_per_turn_and_angle_per_step() {
    for e in expectations() {
        let c = e.preset.cal();
        assert_eq!(c.angle_per_pulse_x1000(), e.angle_x1000, "{:?}", e.preset.id);
        for n in [0u32, 1, 2, 55, 100, 529, 1000, 12_345] {
            let want = n as i64 * 4096 * 100 / e.turn_x100 as i64;
            assert_eq!(c.expected_angle(Pulses(n)), AngleCounts(want), "{n}");
        }
        // steps for exactly 100 turns => exactly 409 600 counts
        let steps_100_turns = e.turn_x100 as i64; // turn_x100 steps = 100 turns
        assert_eq!(c.expected_angle(Pulses(steps_100_turns as u32)), AngleCounts(409_600));
    }
    // NFP: 529 steps per turn, 7.74 counts per step
    assert_eq!(NFP_608_2645.cal().expected_angle(Pulses(529)), AngleCounts(4096));
    assert_eq!(NFP_608_2645.cal().expected_angle(Pulses(1)), AngleCounts(7));
}

#[test]
fn preset_mu_to_angle_is_consistent_with_steps_and_angle() {
    for e in expectations() {
        let c = e.preset.cal();
        let mut last = AngleCounts(0);
        for mu in [0u32, 1, 50, 500, 1000, 2000, 7777, 10_000, 100_000, 200_000] {
            let a = c.mu_to_angle(MilliUnits(mu));
            // independent integer reference
            let want = (mu as i128 * 1000 * e.uu_den as i128 * 409_600) / (e.uu_num as i128 * e.turn_x100 as i128);
            assert_eq!(a.0 as i128, want, "{:?} {mu}", e.preset.id);
            // monotonic
            assert!(a >= last);
            last = a;
            // whole steps of that volume give at most this angle, and less than one step short
            let via_steps = c.expected_angle(c.mu_to_pulses(MilliUnits(mu)));
            assert!(via_steps <= a, "{:?} {mu}", e.preset.id);
            let one_step = c.angle_per_pulse_x1000() / 1000 + 1;
            assert!(a.0 - via_steps.0 <= one_step, "{:?} {mu}: {a:?} vs {via_steps:?}", e.preset.id);
        }
        // 100 U is an exact fraction of a turn count
        assert_eq!(c.mu_to_angle(MilliUnits(0)), AngleCounts(0));
    }
}

fn repeated_boluses(cal: PulseCal, n: u32) -> (u64, DeliveryEngine) {
    let mut de = DeliveryEngine::new(cal);
    de.resume();
    let mut total: u64 = 0;
    for i in 0..n {
        de.comm_heartbeat();
        assert_eq!(de.start_bolus(MilliUnits(50)), Ok(()));
        let mut guard = 0;
        while de.bolus_active() {
            let p = de.tick(Millis(1000));
            de.commit(p);
            total += p.0 as u64;
            guard += 1;
            assert!(guard < 100);
        }
        let requested_uu = (i as u64 + 1) * 50_000;
        let delivered_num = total * cal.uu_num as u64;
        assert!(delivered_num <= requested_uu * cal.uu_den as u64);
        assert!(requested_uu * cal.uu_den as u64 - delivered_num < cal.uu_num as u64);
    }
    (total, de)
}

#[test]
fn preset_bolus_accumulation_is_rational_exact() {
    for e in expectations() {
        let (total, de) = repeated_boluses(e.preset.cal(), 1000); // 50 U in 0.05 U boluses
        assert_eq!(total, 50_000_000u64 * e.uu_den / e.uu_num, "{:?}", e.preset.id);
        assert_eq!(de.delivered_steps(), Pulses(total as u32));
        assert_eq!(de.dropped_steps(), Pulses(0));
        let acc = de.accumulator();
        assert!(acc >= 0 && acc < de.threshold());
        let rem = 50_000_000i64 * e.uu_den as i64 - total as i64 * e.uu_num as i64;
        assert_eq!(acc, rem * SCALED_PER_UU);
        assert_eq!(de.threshold(), e.uu_num as i64 * SCALED_PER_UU);
    }
}

#[test]
fn preset_basal_day_is_rational_exact() {
    for e in expectations() {
        let mut de = DeliveryEngine::new(e.preset.cal());
        de.set_schedule(&flat(1000)).unwrap(); // 24 U per day
        de.resume();
        let mut total: u64 = 0;
        for day in 1..=2u64 {
            for _ in 0..24 * 60 {
                de.comm_heartbeat();
                let p = de.tick(Millis(60_000));
                de.commit(p);
                total += p.0 as u64;
            }
            assert_eq!(total, day * 24_000_000 * e.uu_den / e.uu_num, "{:?} day {day}", e.preset.id);
            let acc = de.accumulator();
            assert!(acc >= 0 && acc < de.threshold());
        }
    }
}

#[test]
fn preset_wire_calibration_record_in_get_status() {
    for e in expectations() {
        let (mut p, _h) = pump_for(&e);
        let s = p.get_status();
        assert_eq!(s.faults, 0);
        assert_eq!(s.cal_drive_id, e.wire_id);
        assert_eq!(s.cal_uu_per_step, e.floor_uu);
        assert_eq!(s.cal_steps_per_rev, e.preset.steps_per_rev);
        assert_eq!(s.cal_gear_ratio_x100, e.preset.gear_ratio_x100);
        assert_eq!(p.pulse_cal(), e.preset.cal());
    }
    let (mut p, _h) = pump_for(&expectations()[0]);
    let s = p.get_status();
    assert_eq!((s.cal_drive_id, s.cal_uu_per_step, s.cal_steps_per_rev, s.cal_gear_ratio_x100), (0x20, 4_935, 20, 2645));
}

#[test]
fn preset_tampering_is_rejected_and_blocks_the_pump() {
    for e in expectations() {
        let good = DriveCal::from_preset(&e.preset);
        let fix = |mut c: DriveCal| {
            c.crc32 = c.compute_crc();
            c
        };
        let mut bad_crc = good;
        bad_crc.uu_num ^= 1;
        let records = [
            (bad_crc, Error::Crc),
            (fix(DriveCal { magic: good.magic ^ 1, ..good }), Error::NotFound),
            (fix(DriveCal { uu_num: good.uu_num + 1, ..good }), Error::BadArg),
            (fix(DriveCal { uu_den: good.uu_den + 1, ..good }), Error::BadArg),
            (fix(DriveCal { steps_per_rev: good.steps_per_rev + 1, ..good }), Error::BadArg),
            (fix(DriveCal { gear_ratio_x100: good.gear_ratio_x100 + 1, ..good }), Error::BadArg),
            (fix(DriveCal { reserved: 1, ..good }), Error::BadArg),
            (fix(DriveCal { drive_id: 0x7E, ..good }), Error::BadArg),
            (fix(DriveCal { uu_num: 100, ..good }), Error::Limit),
        ];
        for (c, err) in records {
            assert_eq!(DriveCal::validate(Some(&c)), Err(err), "{:?} {c:?}", e.preset.id);
            let (mut p, h) = pump_with(Some(&c), None);
            assert!(p.calibration().is_none());
            assert!(p.get_status().faults & Faults::NO_CALIBRATION.bits() != 0);
            assert_eq!(p.resume(), Err(Error::Fault));
            run_secs(&mut p, &h, 30);
            assert_eq!(h.st().total_steps, 0);
        }
        // another preset's record under this preset's id (swapped content, valid CRC)
        for o in expectations() {
            if o.wire_id == e.wire_id {
                continue;
            }
            let c = fix(DriveCal { drive_id: o.wire_id, ..good });
            assert_eq!(DriveCal::validate(Some(&c)), Err(Error::BadArg));
        }
    }
}

#[test]
fn preset_pump_delivers_one_unit_bolus() {
    for e in expectations() {
        let (mut p, h) = pump_for(&e);
        p.fill(MilliUnits(100_000)).unwrap();
        activate(&mut p, 0).unwrap();
        p.resume().unwrap();
        assert_eq!(p.bolus(MilliUnits(1000)), Ok(()));
        run_secs(&mut p, &h, 120);
        assert_eq!(h.st().total_steps, e.steps_per_unit, "{:?}", e.preset.id);
        let s = p.get_status();
        assert_eq!(s.faults, 0, "{:?}", e.preset.id);
        let cal = e.preset.cal();
        assert_eq!(s.delivered_mu, cal.pulses_to_mu(Pulses(e.steps_per_unit)).0);
        assert!(s.delivered_mu <= 1000);
        let used_uu = cal.pulses_to_micro(Pulses(e.steps_per_unit)).0;
        assert_eq!(s.reservoir_mu as u64, (100_000_000 - used_uu) / 1000);
    }
}

#[test]
fn preset_pump_basal_hour_matches_exact_steps() {
    for e in expectations() {
        let (mut p, h) = pump_for(&e);
        p.fill(MilliUnits(100_000)).unwrap();
        activate(&mut p, 1000).unwrap();
        p.resume().unwrap();
        run_secs(&mut p, &h, 3600);
        let want = 1_000_000u64 * e.uu_den / e.uu_num;
        assert_eq!(h.st().total_steps as u64, want, "{:?}", e.preset.id);
        assert_eq!(p.engine().delivered_steps().0 as u64, want);
        assert_eq!(p.get_status().faults, 0);
    }
}

#[test]
fn missing_calibration_latches_no_calibration_and_delivers_nothing() {
    let (mut p, hal) = pump_with(None, None);
    assert!(p.calibration().is_none());
    assert!(p.pulse_cal().is_none());
    let s = p.get_status();
    assert!(s.faults & Faults::NO_CALIBRATION.bits() != 0);
    assert_eq!((s.cal_drive_id, s.cal_uu_per_step, s.cal_steps_per_rev, s.cal_gear_ratio_x100), (0, 0, 0, 0));
    assert_eq!(p.resume(), Err(Error::Fault));
    assert_eq!(p.bolus(MilliUnits(50)), Err(Error::Fault));
    let _ = p.fill(MilliUnits(50_000));
    let _ = p.set_schedule(&flat(1000));
    run_secs(&mut p, &hal, 300);
    assert_eq!(hal.st().total_steps, 0);
    assert!(!hal.st().stepped_while_disabled);
    assert_eq!(p.acknowledge(Faults(0xFFFF)), Err(Error::Persists));
    assert!(p.get_status().faults & Faults::NO_CALIBRATION.bits() != 0);
}
