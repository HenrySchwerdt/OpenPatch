//! LED pattern state machine (`led`): charging pulse, full = green, low = red, and the rest of the table.
use openpatch_core::led::*;

fn inp(charger: Charger, vbat_mv: u16) -> LedInputs {
    LedInputs { fault: false, charger, vbat_mv, button_pressed: false }
}

/// Sample the colour every `step` ms for `dur` ms.
fn run(st: &mut LedState, from: u64, dur: u64, step: u64, i: LedInputs) -> Vec<(u64, Rgb)> {
    (0..dur / step).map(|k| (from + k * step, st.update(from + k * step, &i))).collect()
}

const RED: Rgb = Rgb::red(LED_LEVEL_PCT);
const GREEN: Rgb = Rgb::green(LED_LEVEL_PCT);

#[test]
fn normal_state_is_dark() {
    let mut s = LedState::new();
    for (_, c) in run(&mut s, 0, 10_000, 50, inp(Charger::None, 3_900)) {
        assert!(c.is_off());
    }
    assert_eq!(s.update(10_000, &inp(Charger::None, 3_500)), Rgb::OFF, "3.5 V is not low yet");
}

#[test]
fn charging_pulses_red_at_1_hz() {
    let mut s = LedState::new();
    let v = run(&mut s, 5_000, 3_000, 25, inp(Charger::Charging, 3_700));
    assert!(v.iter().all(|(_, c)| c.g == 0 && c.b == 0), "red only");
    assert_eq!(v[0].1, Rgb::OFF, "starts dark when the mode is entered");
    assert_eq!(v.iter().map(|(_, c)| c.r).max().unwrap(), LED_LEVEL_PCT);
    let at = |t: u64| v.iter().find(|(x, _)| *x == 5_000 + t).unwrap().1.r;
    assert!(at(0) < at(250) && at(250) < at(500));
    assert_eq!(at(500), LED_LEVEL_PCT);
    assert!(at(500) > at(750) && at(750) > at(975));
    assert_eq!(at(0), at(1_000));
    assert_eq!(at(250), at(1_250));
    assert_eq!(at(750), at(2_750));
}

#[test]
fn full_is_steady_green() {
    let mut s = LedState::new();
    for (_, c) in run(&mut s, 0, 5_000, 100, inp(Charger::Done, 4_190)) {
        assert_eq!(c, GREEN);
    }
}

#[test]
fn low_battery_flashes_red_once_every_four_seconds() {
    let mut s = LedState::new();
    let v = run(&mut s, 0, 12_000, 10, inp(Charger::None, 3_450));
    let lit: Vec<u64> = v.iter().filter(|(_, c)| !c.is_off()).map(|(t, _)| *t).collect();
    assert_eq!(lit.len(), 3 * 10);
    for start in [0u64, 4_000, 8_000] {
        assert!(lit.contains(&start) && lit.contains(&(start + 90)) && !lit.contains(&(start + 100)));
    }
    assert!(v.iter().all(|(_, c)| c.is_off() || *c == RED));
}

#[test]
fn critical_battery_double_flash() {
    let mut s = LedState::new();
    let v = run(&mut s, 0, 4_000, 10, inp(Charger::None, 3_300));
    let lit: Vec<u64> = v.iter().filter(|(_, c)| !c.is_off()).map(|(t, _)| *t).collect();
    assert_eq!(lit.len(), 20);
    assert!(lit.contains(&0) && lit.contains(&90) && !lit.contains(&100));
    assert!(lit.contains(&250) && lit.contains(&340) && !lit.contains(&350));
    assert!(!lit.iter().any(|t| *t > 350), "then dark until the next period");
    // the boundary is the motor-start limit: 3.4 V is low (single flash), 3.399 V is critical (double flash)
    let mut s2 = LedState::new();
    s2.update(0, &inp(Charger::None, 3_400));
    assert_eq!(s2.update(250, &inp(Charger::None, 3_400)), Rgb::OFF);
    let mut s3 = LedState::new();
    s3.update(0, &inp(Charger::None, 3_399));
    assert_eq!(s3.update(250, &inp(Charger::None, 3_399)), RED);
}

#[test]
fn fault_blinks_fast_red_until_acknowledged() {
    let mut s = LedState::new();
    let mut i = inp(Charger::None, 3_900);
    i.fault = true;
    let v = run(&mut s, 1_000, 1_000, 5, i);
    let on = v.iter().filter(|(_, c)| *c == RED).count();
    assert_eq!(on, 4 * 25, "4 Hz at 50 %: 125 ms on, 125 ms off");
    assert_eq!(v[0].1, RED);
    i.fault = false;
    assert_eq!(s.update(2_000, &i), Rgb::OFF, "acknowledged: dark again");
}

#[test]
fn priority_fault_over_charging_over_low() {
    let mut s = LedState::new();
    let mut i = inp(Charger::Done, 3_300);
    assert_eq!(s.update(0, &i), GREEN, "on a cable the charger state wins over the battery warning");
    i.charger = Charger::Charging;
    assert_eq!(s.update(500, &i).g, 0);
    i.fault = true;
    assert_eq!(s.update(1_000, &i), RED, "a fault wins over everything");
    i.fault = false;
    i.charger = Charger::None;
    assert_eq!(s.update(1_100, &i), RED, "low battery pattern restarts with its flash");
}

#[test]
fn button_press_shows_the_battery_state_for_0_8_s() {
    let orange = Rgb::orange(LED_LEVEL_PCT);
    for (mv, want) in [(3_900, GREEN), (3_801, GREEN), (3_800, orange), (3_500, orange), (3_499, RED), (3_200, RED)] {
        let mut s = LedState::new();
        let mut i = inp(Charger::None, mv);
        i.button_pressed = true;
        assert_eq!(s.update(1_000, &i), want, "{mv} mV");
        i.button_pressed = false;
        assert_eq!(s.update(1_000 + BUTTON_SHOW_MS - 1, &i), want);
        let after = s.update(1_000 + BUTTON_SHOW_MS, &i);
        assert!(after.is_off() || after == RED, "{mv} mV: back to the idle pattern");
    }
    // the colour is latched at the press, a changing battery does not recolour it
    let mut s = LedState::new();
    let mut i = inp(Charger::None, 3_900);
    i.button_pressed = true;
    s.update(0, &i);
    i.button_pressed = false;
    i.vbat_mv = 3_600;
    assert_eq!(s.update(400, &i), GREEN);
}

#[test]
fn button_is_ignored_while_on_a_cable() {
    let mut s = LedState::new();
    let mut i = inp(Charger::Done, 3_900);
    i.button_pressed = true;
    assert_eq!(s.update(0, &i), GREEN);
    i.charger = Charger::None;
    i.button_pressed = false;
    assert_eq!(s.update(100, &i), Rgb::OFF, "no stale button indication after the cable is pulled");
}

#[test]
fn charger_state_from_the_two_stat_reads() {
    assert_eq!(charger_state(true, false, false), Charger::Charging);
    assert_eq!(charger_state(true, true, true), Charger::Done);
    assert_eq!(charger_state(true, false, true), Charger::None, "floating = no supply / shutdown");
    assert_eq!(charger_state(true, true, false), Charger::None, "not physical");
    assert_eq!(charger_state(false, false, false), Charger::None, "no cable");
    assert_eq!(charger_state(false, true, true), Charger::None);
}

#[test]
fn breathing_is_a_triangle() {
    assert_eq!(breathing_pct(0, 1000, 30), 0);
    assert_eq!(breathing_pct(250, 1000, 30), 15);
    assert_eq!(breathing_pct(500, 1000, 30), 30);
    assert_eq!(breathing_pct(750, 1000, 30), 15);
    assert_eq!(breathing_pct(999, 1000, 30), 0);
    assert_eq!(breathing_pct(10, 0, 30), 0);
    assert_eq!(breathing_pct(0, 1, 30), 0);
}

#[test]
fn active_low_pwm_compare() {
    assert_eq!(Rgb::pwm_compare_active_low(0, 1000), 1000, "off = always high");
    assert_eq!(Rgb::pwm_compare_active_low(100, 1000), 0, "full = always low");
    assert_eq!(Rgb::pwm_compare_active_low(30, 1000), 700);
    assert_eq!(Rgb::pwm_compare_active_low(250, 1000), 0, "clamped");
}

#[test]
fn the_user_requirement_in_one_place() {
    // charging pulse, full = green, low = red
    let mut s = LedState::new();
    let charging: Vec<_> = (0..40).map(|k| s.update(k * 25, &inp(Charger::Charging, 3_700))).collect();
    assert!(charging.iter().any(|c| c.r > 0) && charging.iter().any(|c| c.r < LED_LEVEL_PCT));
    assert_eq!(s.update(2_000, &inp(Charger::Done, 4_200)), GREEN);
    let low: Vec<_> = (0..200).map(|k| s.update(2_100 + k * 25, &inp(Charger::None, 3_450))).collect();
    assert!(low.iter().any(|c| *c == RED) && low.iter().all(|c| c.g == 0 && c.b == 0));
}
