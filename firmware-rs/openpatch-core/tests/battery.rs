//! SAADC VDDHDIV5 conversion, battery classes and the UICR REGOUT0 decision (`battery`).
use openpatch_core::battery::*;

#[test]
fn vddhdiv5_conversion_endpoints_and_known_points() {
    // 12 bit: full scale 4096 = 18 V (3.6 V x 5)
    assert_eq!(vddhdiv5_to_mv(0, 12), Some(0));
    assert_eq!(vddhdiv5_to_mv(4096, 12), Some(18_000));
    // 3.7 V cell: VDDH/5 = 0.74 V = 0.74/3.6 x 4096 = 841.9 counts
    assert_eq!(vddhdiv5_to_mv(842, 12), Some(3_700));
    // 4.2 V: 0.84 V -> 955.7
    assert_eq!(vddhdiv5_to_mv(956, 12), Some(4_201));
    // 14 bit is four times finer
    assert_eq!(vddhdiv5_to_mv(4 * 842, 14), Some(3_700));
    assert_eq!(vddhdiv5_to_mv(16_384, 14), Some(18_000));
    assert_eq!(vddhdiv5_to_mv(1024, 10), Some(18_000));
    assert_eq!(vddhdiv5_to_mv(256, 8), Some(18_000));
}

#[test]
fn rounds_to_nearest_and_clamps() {
    // one LSB at 12 bit = 4.3945 mV
    assert_eq!(vddhdiv5_to_mv(1, 12), Some(4));
    assert_eq!(vddhdiv5_to_mv(2, 12), Some(9));
    assert_eq!(vddhdiv5_to_mv(-5, 12), Some(0), "single ended noise below zero");
    assert_eq!(vddhdiv5_to_mv(i32::MIN, 12), Some(0));
    assert_eq!(vddhdiv5_to_mv(i32::MAX, 8), Some(u16::MAX), "saturates instead of wrapping");
    assert_eq!(vddhdiv5_to_mv(100, 11), None);
    assert_eq!(vddhdiv5_to_mv(100, 0), None);
}

#[test]
fn monotonic_and_within_half_a_millivolt_of_the_ideal_line() {
    let mut prev = 0u16;
    for raw in 0..=4095 {
        let mv = vddhdiv5_to_mv(raw, 12).unwrap();
        assert!(mv >= prev);
        prev = mv;
        let ideal = raw as f64 * 18_000.0 / 4096.0;
        assert!((mv as f64 - ideal).abs() <= 0.5 + 1e-9, "raw {raw}: {mv} vs {ideal}");
    }
}

#[test]
fn oversampled_mean() {
    assert_eq!(vddhdiv5_mean_to_mv(&[], 12), None);
    assert_eq!(vddhdiv5_mean_to_mv(&[842, 842, 842, 842], 12), Some(3_700));
    assert_eq!(vddhdiv5_mean_to_mv(&[840, 844], 12), Some(3_700));
    assert_eq!(vddhdiv5_mean_to_mv(&[-3, 3], 12), Some(0));
    assert_eq!(vddhdiv5_mean_to_mv(&[i16::MAX; 8], 14), vddhdiv5_to_mv(i16::MAX as i32, 14));
}

#[test]
fn battery_classes_follow_the_limits() {
    assert_eq!(MOTOR_MIN_VBAT_MV, 3_400);
    assert_eq!(classify(4_200), BatteryClass::Ok);
    assert_eq!(classify(3_500), BatteryClass::Ok);
    assert_eq!(classify(3_499), BatteryClass::Low);
    assert_eq!(classify(3_400), BatteryClass::Low);
    assert_eq!(classify(3_399), BatteryClass::Critical);
    assert_eq!(classify(0), BatteryClass::Critical);
}

#[test]
fn motor_start_policy() {
    assert!(motor_start_allowed(3_400, false));
    assert!(!motor_start_allowed(3_399, false));
    assert!(!motor_start_allowed(4_200, true), "never on a cable (H8)");
    assert!(loaded_voltage_ok(3_000));
    assert!(!loaded_voltage_ok(2_999));
    assert_eq!(MOTOR_LOAD_CHECK_STEPS, 20);
}

#[test]
fn regout0_decision() {
    assert_eq!(UICR_REGOUT0_ADDR, 0x1000_1304);
    assert_eq!(REGOUT0_3V3_WORD, 0xFFFF_FFFD);
    // fresh module: erased, default 1.8 V -> write 3.3 V, and the write only clears bits (1 -> 0)
    assert_eq!(regout0_action(0xFFFF_FFFF), Regout0Action::Write);
    assert_eq!(0xFFFF_FFFFu32 & REGOUT0_3V3_WORD, REGOUT0_3V3_WORD);
    assert_eq!(regout0_action(REGOUT0_3V3_WORD), Regout0Action::Nothing);
    // another programmed voltage needs an ERASEALL: 1.8 V (0), 2.1 V (1), 2.4 V (2), 2.7 V (3), 3.0 V (4), reserved (6)
    for v in [0u32, 1, 2, 3, 4, 6] {
        assert_eq!(regout0_action(0xFFFF_FFF8 | v), Regout0Action::NeedsErase, "vout {v}");
    }
}

#[test]
fn rail_window() {
    assert!(vdd_rail_ok(3_300));
    assert!(vdd_rail_ok(3_100));
    assert!(!vdd_rail_ok(3_099));
    assert!(!vdd_rail_ok(1_800), "REGOUT0 still at the 1.8 V default");
    assert!(!vdd_rail_ok(3_501));
}
