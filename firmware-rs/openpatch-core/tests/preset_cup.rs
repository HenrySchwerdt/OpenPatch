//! v0.1.0 "cup" drive: NFP-608-26.45 (20 steps/rev, 26.45) -> miter pair z16:z16 (1:1) -> M1.6 x 0.35 rod rotating into a
//! cup plunger in a stadium bore 20.5 x 5.5 mm (`mechanical/out/v010-cup/*.mech.json`: bore_w 20.5, bore_area 106.258 mm^2,
//! u_per_step 0.0070303; V010-CUP.md still quotes 20.3, the regenerated CAD data says 20.5). TEST PROJECT: water only.
//! There is no check valve: this pod must NEVER aspirate (FillMode::Draw is refused), only the assisted pressure fill exists.
mod common;
use common::*;
use openpatch_core::drive_cal::{DriveId, NFP_608_2645_CUP_MITER_1_1 as P, NFP_608_2645_G16_20, PRESETS};
use openpatch_core::limits::*;
use openpatch_core::*;

// Stadium area exactly as a rational: A = h (w - h) + pi (h/2)^2, h = 5.5, w = 20.5, pi = 355/113 (rel. error 8.5e-8):
//   A = 82.5 + (355/113) (121/16) = 192115 / 1808 mm^2 (= 106.2583, the CAD says 106.2583).
// uU/step = 0.35 mm / (20 x 26.45) x A mm^2 x 1e5 uU/mm^3 (1 U = 10 mm^3) = 35000 A / 529 = 840 503 125 / 119 554 (= 7030.32).
const A_NUM: u128 = 192_115;
const A_DEN: u128 = 1_808;

#[test]
fn preset_is_the_exact_rational_of_the_stadium_geometry() {
    assert_eq!(P.id as u16, 0x26);
    assert_eq!((P.uu_num, P.uu_den), (840_503_125, 119_554));
    // cross-multiplied: uu_num / uu_den == 35000 * A_NUM / (529 * A_DEN), no rounding anywhere
    assert_eq!(P.uu_num as u128 * 529 * A_DEN, 35_000 * A_NUM * P.uu_den as u128);
    assert_eq!((P.steps_per_rev, P.gear_ratio_x100), (20, 2645)); // miter 1:1: the rod turns once per gearhead turn
    assert_eq!(P.cal().turn_x100, 52_900);
    // and it agrees with the CAD's float value to better than 1e-6
    let cad = 0.007_030_321_938_557_747_f64;
    assert!(((P.uu_num as f64 / P.uu_den as f64) / 1e6 - cad).abs() / cad < 1e-6);
}

#[test]
fn u_per_step_and_steps_per_unit() {
    let cal = P.cal();
    assert_eq!(cal.micro_u_floor(), 7_030);
    assert_eq!(cal.mu_to_pulses(MilliUnits(1_000)).0, 142, "1 U = 142.24 steps, floored (never more than requested)");
    assert_eq!(cal.mu_to_pulses(MilliUnits(50)).0, 7);
    assert!(cal.pulses_to_mu(Pulses(142)).0 <= 1_000);
    // the cup drive doses 78 % more per step than the 16:20 pair: never confuse the two
    assert!(cal.micro_u_floor() > NFP_608_2645_G16_20.cal().micro_u_floor());
}

#[test]
fn one_thousand_pulses_of_005_u_accumulate_exactly() {
    let cal = P.cal();
    // 50 mU = 7 steps (floor); 1000 pulses are 7000 steps = exactly 7000 x uu_num / uu_den uU, no drift
    let steps = cal.mu_to_pulses(MilliUnits(50));
    let mut total = 0u32;
    for _ in 0..1000 {
        total += steps.0;
    }
    assert_eq!(total, 7_000);
    assert_eq!(cal.pulses_to_micro(Pulses(total)).0, 7_000u64 * 840_503_125 / 119_554);
    assert!(cal.pulses_to_mu(Pulses(total)).0 <= 50 * 1000, "never above the requested 50 U");
    // 119 554 steps are exactly 840 503 125 uU: no drift over any multiple
    assert_eq!(cal.pulses_to_micro(Pulses(119_554)).0, 840_503_125);
    assert_eq!(cal.pulses_to_micro(Pulses(119_554 * 7)).0, 7 * 840_503_125);
}

#[test]
fn bolus_and_basal_limits_in_steps() {
    let cal = P.cal();
    assert_eq!(cal.mu_to_pulses(DEFAULT_MAX_BOLUS).0, 1_422);
    assert_eq!(cal.mu_to_pulses(HARD_MAX_BOLUS).0, 3_556);
    assert_eq!(cal.mu_to_pulses(MilliUnits(HARD_MAX_BASAL.0)).0, 4_267, "30 U/h hard basal cap per hour");
    assert_eq!(cal.mu_to_pulses(MilliUnits(HARD_MAX_BASAL.0 / 60)).0, 71, "per minute");
    assert_eq!(cal.mu_to_pulses(MAX_PER_MIN).0, 241);
    let hourly_strict = MAX_HOURLY.0 * 100 / (100 + HOURLY_CAL_MARGIN_PCT);
    assert_eq!(cal.mu_to_pulses(MilliUnits(hourly_strict)).0, 2_051);
    // every cap in steps never exceeds its volume
    for mu in [DEFAULT_MAX_BOLUS.0, HARD_MAX_BOLUS.0, MAX_PER_MIN.0, hourly_strict] {
        assert!(cal.pulses_to_mu(cal.mu_to_pulses(MilliUnits(mu))).0 <= mu);
    }
}

#[test]
fn plunger_stroke_limits_the_deliverable_volume() {
    let cal = P.cal();
    // M1.6 x 0.35 rod: 0.35 mm per 529 steps. OP-100: 9.4 mm, OP-200: 18.8 mm.
    let steps_for = |stroke_um: u64| stroke_um * 529 / 350; // floor
    let op100 = steps_for(9_400);
    let op200 = steps_for(18_800);
    assert_eq!((op100, op200), (14_207, 28_414));
    let u100 = cal.pulses_to_mu(Pulses(op100 as u32)).0;
    let u200 = cal.pulses_to_mu(Pulses(op200 as u32)).0;
    assert_eq!((u100, u200), (99_879, 199_759), "mU: 99.88 U and 199.76 U, from 9.4 / 18.8 mm x 106.26 mm^2");
    // the stroke never delivers more than the nominal 100 / 200 U tank, and the tank is used to > 99.8 %
    assert!(u100 <= CAPACITY_100.0 && u100 > CAPACITY_100.0 * 998 / 1000);
    assert!(u200 <= CAPACITY_200.0 && u200 > CAPACITY_200.0 * 998 / 1000);
    // a fill of the full nominal volume would need 9.41 / 18.82 mm: one step more than the stroke (CAD stroke 9.41 / 18.82)
    assert!(cal.mu_to_pulses(CAPACITY_100).0 as u64 >= op100);
}

#[test]
fn preset_is_registered_and_validates() {
    assert!(PRESETS.iter().any(|p| p.id == DriveId::Nfp608_26_45CupMiter1_1));
    let rec = DriveCal::from_preset(&P);
    assert_eq!(DriveCal::validate(Some(&rec)), Ok(()));
    assert_eq!(DriveCal::from_bytes(&rec.to_bytes()), rec);
    assert_eq!(DriveCal::preset(0x26), Ok(rec));
    assert_eq!(DriveId::from_u16(0x26), Some(DriveId::Nfp608_26_45CupMiter1_1));
    let mut wrong = rec;
    wrong.drive_id = 0x25;
    wrong.crc32 = wrong.compute_crc();
    assert_eq!(DriveCal::validate(Some(&wrong)), Err(Error::BadArg));
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
fn cup_preset_forbids_suction_draw_and_never_moves_the_motor_in_reverse() {
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
fn cup_preset_keeps_the_assisted_pressure_fill() {
    let (mut p, h) = cup_pump();
    p.fill(MilliUnits(10_000)).unwrap();
    p.fill_with_mode(FillMode::Assisted, MilliUnits(5_000)).unwrap();
    run_draw(&mut p, &h);
    assert!(h.st().total_reverse_steps > 0);
    assert_eq!(h.st().draw_rate_pps, Some(ASSISTED_FILL_PPS), "fixed retract rate, no suction rate");
    // the wire command AssistedFill is the same path
    let (mut p2, h2) = cup_pump();
    p2.fill(MilliUnits(10_000)).unwrap();
    p2.assisted_fill(MilliUnits(5_000)).unwrap();
    run_draw(&mut p2, &h2);
    assert_eq!(h2.st().total_reverse_steps, h.st().total_reverse_steps);
}

#[test]
fn other_presets_still_allow_the_draw_mode() {
    for p in PRESETS {
        assert_eq!(p.allows_draw(), p.id != DriveId::Nfp608_26_45CupMiter1_1, "{:?}", p.id);
    }
}

// ---- take-up after a reversal: a TRAVEL converted with the bore of the ACTIVE preset -------------------------------------
#[test]
fn bore_area_is_part_of_each_preset_and_matches_its_uu_per_step_derivation() {
    assert_eq!(P.bore_area_x100, 10_626, "20.5 x 5.5 stadium = 106.258 mm^2");
    let exact_x100 = A_NUM as f64 / A_DEN as f64 * 100.0;
    assert!((P.bore_area_x100 as f64 - exact_x100).abs() <= 0.5);
    assert_eq!(NFP_608_2645_G16_20.bore_area_x100, 7_460, "16 x 5 stadium: the old pods' 74.6 mm^2");
}

#[test]
fn takeup_travel_converts_with_the_active_presets_bore_exactly() {
    // 0.33 mm of play: 330 um x 106.26 mm^2 = 35.07 mm^3 = 3.507 U on the cup pod, 330 x 74.60 = 2.462 U on the 16:20 pod
    assert_eq!(P.travel_um_to_uu(TAKEUP_UM_AFTER_REVERSAL), 3_506_580);
    assert_eq!(NFP_608_2645_G16_20.travel_um_to_uu(TAKEUP_UM_AFTER_REVERSAL), 2_461_800);
    // steps, rounded up: cup 3 506 580 x 119 554 / 840 503 125 = 498.8 -> 499; 16:20: 2 461 800 x 529 / 2 088 800 = 623.4 -> 624
    assert_eq!(P.travel_um_to_steps(TAKEUP_UM_AFTER_REVERSAL), 499);
    assert_eq!(NFP_608_2645_G16_20.travel_um_to_steps(TAKEUP_UM_AFTER_REVERSAL), 624);
    // cross-check without the area: steps = travel / advance per step = 330 um / (350 um / 529 steps) = 498.8 (the bore cancels)
    let by_lead = 330.0 / (350.0 / 529.0);
    assert!((P.travel_um_to_steps(330) as f64 - by_lead).abs() < 1.0, "cup: {} vs lead {by_lead}", P.travel_um_to_steps(330));
    // as a volume the cup pod's take-up is 43 % bigger than the old pods': the bug of the fixed 74.63 mm^2
    assert!(P.travel_um_to_uu(330) * 100 / NFP_608_2645_G16_20.travel_um_to_uu(330) >= 142);
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
    let takeup = P.travel_um_to_steps(TAKEUP_UM_AFTER_REVERSAL);
    assert_eq!(fwd, takeup + 3, "take-up of the CUP bore (499 steps), not of the old 74.63 mm^2 bore (about 350 steps)");
    // expected remaining volume: fill + reverse steps - forward steps (take-up and prime), in uU at the preset's exact rational
    let cal = P.cal();
    let expect_uu = 50_000_000i64 + cal.pulses_to_micro(Pulses(drawn)).0 as i64 - cal.pulses_to_micro(Pulses(fwd)).0 as i64;
    let have_uu = p.reservoir().remaining().0 as i64 * 1000;
    let one_step = cal.micro_u_floor() as i64 + 1;
    assert!((have_uu - expect_uu).abs() <= one_step, "model {have_uu} uU vs exact {expect_uu} uU, one step = {one_step}");
}
