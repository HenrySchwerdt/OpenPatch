//! v0.1.0 "cup" drive after the challenge-review pass (mechanics commit 7879e22, 2026-11-24): the same drive as preset 0x26
//! (NFP-608-26.45, 20 steps/rev, 26.45 -> miter pair 1:1 -> M1.6 x 0.35 rod into a cup plunger), but the stadium bore is now
//! 20.5 x 5.9 mm (`mechanical/out/v010-cup/*.mech.json`: bore_area 113.4797 mm^2, u_per_step 0.0075081). Preset 0x27; 0x26 keeps
//! the old 20.5 x 5.5 geometry. TEST PROJECT: water only. No check valve: this pod must NEVER aspirate either.
//!
//! The CAD tank is now 132.5 / 239.3 U (stroke 11.68 / 21.09 mm), but the firmware reservoir capacity stays at the nominal
//! 100 / 200 U (`CAPACITY_100` / `CAPACITY_200`) until the bigger tank is confirmed on the bench (V010-CUP.md).
mod common;
use common::*;
use openpatch_core::drive_cal::{DriveId, NFP_608_2645_CUP59_MITER_1_1 as P, NFP_608_2645_CUP_MITER_1_1 as OLD, PRESETS};
use openpatch_core::limits::*;
use openpatch_core::*;

// Stadium area exactly as a rational: A = h (w - h) + pi (h/2)^2, h = 5.9, w = 20.5, pi = 355/113 (as for 0x26):
//   A = 8614/100 + (355/113) (3481/400) = 5 129 283 / 45 200 mm^2 (= 113.47971, the CAD says 113.47971).
// uU/step = 0.35 mm / (20 x 26.45) x A mm^2 x 1e5 uU/mm^3 (1 U = 10 mm^3) = 35000 A / 529 = 897 624 525 / 119 554 (= 7508.11).
const A_NUM: u128 = 5_129_283;
const A_DEN: u128 = 45_200;

#[test]
fn preset_is_the_exact_rational_of_the_5_9_stadium_geometry() {
    assert_eq!(P.id as u16, 0x27);
    assert_eq!((P.uu_num, P.uu_den), (897_624_525, 119_554));
    // cross-multiplied: uu_num / uu_den == 35000 * A_NUM / (529 * A_DEN), no rounding anywhere
    assert_eq!(P.uu_num as u128 * 529 * A_DEN, 35_000 * A_NUM * P.uu_den as u128);
    assert_eq!((P.steps_per_rev, P.gear_ratio_x100), (20, 2645), "same drive as 0x26: miter 1:1");
    assert_eq!(P.cal().turn_x100, 52_900);
    // agrees with the CAD's float value (exact pi) to better than 1e-6
    let cad = 0.007_508_109_361_768_015_5_f64;
    assert!(((P.uu_num as f64 / P.uu_den as f64) / 1e6 - cad).abs() / cad < 1e-6);
}

#[test]
fn the_new_bore_doses_6_8_percent_more_per_step_than_0x26() {
    assert_eq!(P.cal().micro_u_floor(), 7_508);
    assert_eq!(OLD.cal().micro_u_floor(), 7_030);
    // same denominator (same drive), the ratio is the area ratio 5 129 283 / 45 200 : 192 115 / 1 808
    assert_eq!(P.uu_den, OLD.uu_den);
    let ratio = P.uu_num as f64 / OLD.uu_num as f64;
    assert!((ratio - 1.068).abs() < 0.001, "{ratio}");
    assert_ne!(P.id, OLD.id, "a different volume per step must never share a preset id");
}

#[test]
fn u_per_step_and_steps_per_unit() {
    let cal = P.cal();
    assert_eq!(cal.mu_to_pulses(MilliUnits(1_000)).0, 133, "1 U = 133.19 steps, floored (never more than requested)");
    assert_eq!(cal.mu_to_pulses(MilliUnits(50)).0, 6);
    assert!(cal.pulses_to_mu(Pulses(133)).0 <= 1_000);
}

#[test]
fn one_thousand_pulses_of_005_u_accumulate_exactly() {
    let cal = P.cal();
    let steps = cal.mu_to_pulses(MilliUnits(50));
    let total: u32 = (0..1000).map(|_| steps.0).sum();
    assert_eq!(total, 6_000);
    assert_eq!(cal.pulses_to_micro(Pulses(total)).0, 6_000u64 * 897_624_525 / 119_554);
    assert!(cal.pulses_to_mu(Pulses(total)).0 <= 50 * 1000, "never above the requested 50 U");
    assert_eq!(cal.pulses_to_micro(Pulses(119_554)).0, 897_624_525);
    assert_eq!(cal.pulses_to_micro(Pulses(119_554 * 7)).0, 7 * 897_624_525);
}

#[test]
fn bolus_and_basal_limits_in_steps() {
    let cal = P.cal();
    assert_eq!(cal.mu_to_pulses(DEFAULT_MAX_BOLUS).0, 1_331);
    assert_eq!(cal.mu_to_pulses(HARD_MAX_BOLUS).0, 3_329);
    assert_eq!(cal.mu_to_pulses(MilliUnits(HARD_MAX_BASAL.0)).0, 3_995, "30 U/h hard basal cap per hour");
    assert_eq!(cal.mu_to_pulses(MilliUnits(HARD_MAX_BASAL.0 / 60)).0, 66, "per minute");
    assert_eq!(cal.mu_to_pulses(MAX_PER_MIN).0, 226);
    let hourly_strict = MAX_HOURLY.0 * 100 / (100 + HOURLY_CAL_MARGIN_PCT);
    assert_eq!(cal.mu_to_pulses(MilliUnits(hourly_strict)).0, 1_920);
    for mu in [DEFAULT_MAX_BOLUS.0, HARD_MAX_BOLUS.0, MAX_PER_MIN.0, hourly_strict] {
        assert!(cal.pulses_to_mu(cal.mu_to_pulses(MilliUnits(mu))).0 <= mu);
    }
}

#[test]
fn nominal_capacity_stays_100_and_200_u_and_fits_inside_the_cad_stroke() {
    let cal = P.cal();
    // M1.6 x 0.35 rod: 0.35 mm per 529 steps. CAD stroke (challenge-review pass): OP-100 11.68 mm, OP-200 21.09 mm.
    let steps_for = |stroke_um: u64| (stroke_um * 529 / 350) as u32; // floor
    let (cad100, cad200) = (steps_for(11_680), steps_for(21_090));
    assert_eq!((cal.pulses_to_mu(Pulses(cad100)).0, cal.pulses_to_mu(Pulses(cad200)).0), (132_540, 239_328), "CAD tank 132.5 / 239.3 U");
    // the firmware keeps the NOMINAL capacity (not the CAD tank) until the bigger tank is confirmed on the bench
    assert_eq!((CAPACITY_100.0, CAPACITY_200.0), (100_000, 200_000));
    let (n100, n200) = (cal.mu_to_pulses(CAPACITY_100).0, cal.mu_to_pulses(CAPACITY_200).0);
    assert_eq!((n100, n200), (13_318, 26_637), "steps of a full nominal tank: 8.81 / 17.62 mm of travel");
    assert!(n100 < cad100 && n200 < cad200, "a full nominal fill never reaches the end of the CAD stroke");
    assert!(cal.pulses_to_mu(Pulses(n100)).0 <= CAPACITY_100.0 && cal.pulses_to_mu(Pulses(n200)).0 <= CAPACITY_200.0);
}

#[test]
fn preset_is_registered_and_validates() {
    assert!(PRESETS.iter().any(|p| p.id == DriveId::Nfp608_26_45Cup59Miter1_1));
    let rec = DriveCal::from_preset(&P);
    assert_eq!(DriveCal::validate(Some(&rec)), Ok(()));
    assert_eq!(DriveCal::from_bytes(&rec.to_bytes()), rec);
    assert_eq!(DriveCal::preset(0x27), Ok(rec));
    assert_eq!(DriveId::from_u16(0x27), Some(DriveId::Nfp608_26_45Cup59Miter1_1));
    // a 0x26 record with the 0x27 numbers (or the reverse) is refused: the id pins the volume per step
    let mut wrong = rec;
    wrong.drive_id = 0x26;
    wrong.crc32 = wrong.compute_crc();
    assert_eq!(DriveCal::validate(Some(&wrong)), Err(Error::BadArg));
    let mut old_numbers = DriveCal::from_preset(&OLD);
    old_numbers.drive_id = 0x27;
    old_numbers.crc32 = old_numbers.compute_crc();
    assert_eq!(DriveCal::validate(Some(&old_numbers)), Err(Error::BadArg));
}

fn cup_pump() -> (Pump<MockHal>, MockHal) {
    let hal = MockHal::new();
    hal.st().counts_per_step = 8; // 4096 / 529 = 7.74
    hal.st().delivered_pct = 97;
    hal.st().docked = false;
    let rec = DriveCal::from_preset(&P);
    let mut p = Pump::new(hal.clone(), Some(&rec), CAPACITY_100, 1);
    p.set_config(PumpConfig::RELAXED);
    (p, hal)
}

#[test]
fn preset_forbids_suction_draw_and_never_moves_the_motor_in_reverse() {
    assert!(!P.allows_draw());
    let (mut p, h) = cup_pump();
    p.fill(MilliUnits(10_000)).unwrap();
    assert_eq!(p.fill_with_mode(FillMode::Draw, MilliUnits(5_000)), Err(Error::Unsupported));
    assert!(!p.draw_running());
    for _ in 0..5 {
        run_secs(&mut p, &h, 1);
    }
    assert_eq!(h.st().total_reverse_steps, 0, "a refused draw moved nothing");
    assert!(h.st().reverse_calls.is_empty());
}

#[test]
fn preset_keeps_the_assisted_pressure_fill() {
    let (mut p, h) = cup_pump();
    p.fill(MilliUnits(10_000)).unwrap();
    p.assisted_fill(MilliUnits(5_000)).unwrap();
    run_draw(&mut p, &h);
    assert!(h.st().total_reverse_steps > 0);
    assert_eq!(h.st().draw_rate_pps, Some(ASSISTED_FILL_PPS));
}

#[test]
fn a_full_nominal_tank_is_accepted_and_one_unit_more_is_refused() {
    let (mut p, _h) = cup_pump();
    assert!(p.fill(CAPACITY_100).is_ok(), "100 U nominal");
    let (mut p, _h) = cup_pump();
    assert!(p.fill(MilliUnits(CAPACITY_100.0 + 1_000)).is_err(), "the 132.5 U CAD tank is NOT usable by the firmware yet");
}

// ---- take-up after a reversal on the 5.9 bore ----------------------------------------------------------------------------
#[test]
fn bore_area_matches_its_uu_per_step_derivation() {
    assert_eq!(P.bore_area_x100, 11_348, "20.5 x 5.9 stadium = 113.48 mm^2");
    let exact_x100 = A_NUM as f64 / A_DEN as f64 * 100.0;
    assert!((P.bore_area_x100 as f64 - exact_x100).abs() <= 0.5);
    assert_eq!(OLD.bore_area_x100, 10_626, "0x26 keeps the 20.5 x 5.5 bore");
}

#[test]
fn takeup_travel_converts_with_the_5_9_bore() {
    // 0.33 mm of play: 330 um x 113.48 mm^2 = 37.45 mm^3 = 3.745 U
    assert_eq!(P.travel_um_to_uu(TAKEUP_UM_AFTER_REVERSAL), 3_744_840);
    // steps, rounded up: 3 744 840 x 119 554 / 897 624 525 = 498.8 -> 499 (the bore cancels: 330 / (350 / 529) = 498.8)
    assert_eq!(P.travel_um_to_steps(TAKEUP_UM_AFTER_REVERSAL), 499);
    assert_eq!(P.travel_um_to_steps(TAKEUP_UM_AFTER_REVERSAL), OLD.travel_um_to_steps(TAKEUP_UM_AFTER_REVERSAL), "same lead: same steps");
    assert_eq!(P.travel_um_to_steps(0), 0);
}

#[test]
fn reservoir_bookkeeping_after_an_assisted_fill_and_takeup_is_exact_within_one_step() {
    let (mut p, h) = cup_pump();
    p.set_config(PumpConfig::STRICT);
    p.fill(MilliUnits(50_000)).unwrap();
    h.st().docked = true;
    activate(&mut p, 1000).unwrap();
    h.st().docked = false;
    run_secs(&mut p, &h, 1);
    p.assisted_fill(MilliUnits(5_000)).unwrap();
    run_draw(&mut p, &h);
    let drawn = h.st().total_reverse_steps;
    assert!(drawn > 0);
    h.st().docked = true;
    run_secs(&mut p, &h, 1);
    let steps0 = h.st().total_steps;
    prime_all(&mut p, &h, 3);
    let fwd = h.st().total_steps - steps0;
    assert_eq!(fwd, P.travel_um_to_steps(TAKEUP_UM_AFTER_REVERSAL) + 3);
    let cal = P.cal();
    let expect_uu = 50_000_000i64 + cal.pulses_to_micro(Pulses(drawn)).0 as i64 - cal.pulses_to_micro(Pulses(fwd)).0 as i64;
    let have_uu = p.reservoir().remaining().0 as i64 * 1000;
    let one_step = cal.micro_u_floor() as i64 + 1;
    assert!((have_uu - expect_uu).abs() <= one_step, "model {have_uu} uU vs exact {expect_uu} uU, one step = {one_step}");
}

#[test]
fn the_angle_check_sees_enough_counts_per_unit() {
    let one_u = P.cal().mu_to_angle(MilliUnits(1_000)).0;
    assert!((1_010..=1_050).contains(&one_u), "{one_u}");
    assert!(one_u > 100 * 4, "more than 100 x the 4 count noise floor");
}
