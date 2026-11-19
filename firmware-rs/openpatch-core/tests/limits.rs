//! The motor-current, draw-rate, take-up and prime constants (limits.rs) and the relations between them.
//! They are derived, not free numbers: a change that breaks a relation is a design change.
use openpatch_core::drive_cal::NFP_608_2645_G16_20;
use openpatch_core::limits::*;
use openpatch_core::MilliUnits;

#[test]
fn motor_current_thresholds_are_derived_from_the_run_current() {
    // electronics/bench: VREF 0.160 V / 1.0 ohm sense = 160 mA peak per phase; NFP-608-26.45 is rated 181 mA (4.8 V / 26.5 ohm)
    assert_eq!(MOTOR_RUN_CURRENT_MA, 160);
    assert!(MOTOR_RUN_CURRENT_MA <= MOTOR_RATED_CURRENT_MA);
    // supply-side I_SENSE of a free-running stage and of a stalled rotor, relative to the run current
    assert_eq!(MOTOR_FREE_CURRENT_MA, 107);
    assert_eq!(MOTOR_STALL_CURRENT_MA, 267);
    // forward occlusion: two thirds of the way from free-running to stalled
    assert_eq!(OCCLUSION_CURRENT_MA, MOTOR_FREE_CURRENT_MA + (MOTOR_STALL_CURRENT_MA - MOTOR_FREE_CURRENT_MA) * 2 / 3);
    assert_eq!(OCCLUSION_CURRENT_MA, 213);
    // draw: a separate, higher threshold (reverse at 600 pps has less torque margin): within 5 % of the stalled current
    assert_eq!(DRAW_STALL_CURRENT_MA, MOTOR_STALL_CURRENT_MA * 95 / 100);
    assert!(MOTOR_FREE_CURRENT_MA < OCCLUSION_CURRENT_MA && OCCLUSION_CURRENT_MA < DRAW_STALL_CURRENT_MA && DRAW_STALL_CURRENT_MA < MOTOR_STALL_CURRENT_MA);
    // margin above the free-running level: at least 10 sigma of the 3 mA sense noise
    assert!(OCCLUSION_CURRENT_MA - MOTOR_FREE_CURRENT_MA >= 30);
}

#[test]
fn draw_rate_is_capped_by_the_fill_needle_gauge() {
    let cal = NFP_608_2645_G16_20.cal();
    // mechanical sim 1.5: 29G 1051 pps at 30 kPa, derated to 80 % (24 kPa) = 841 pps on the 16:20 drive
    let g29 = FillNeedle::G29.max_pps(cal);
    assert!((840..=842).contains(&g29), "{g29}");
    assert_eq!(FillNeedle::G28.max_pps(cal), g29, "28G and 29G share the inner diameter in the gauge table");
    assert!(FillNeedle::G27.max_pps(cal) > g29);
    assert!(FillNeedle::G30.max_pps(cal) < g29 && FillNeedle::G31.max_pps(cal) < FillNeedle::G30.max_pps(cal));
    // the rate really used: the default 600 pps unless the needle is finer
    assert_eq!(draw_pps(FillNeedle::G29, cal), DRAW_DEFAULT_PPS);
    assert_eq!(draw_pps(FillNeedle::G27, cal), DRAW_DEFAULT_PPS);
    assert_eq!(draw_pps(FillNeedle::G31, cal), FillNeedle::G31.max_pps(cal));
    assert!(draw_pps(FillNeedle::G31, cal) < DRAW_DEFAULT_PPS);
    // never above the hard cap
    assert!(DRAW_DEFAULT_PPS <= DRAW_MAX_PPS);
    // a chunk never blocks the safety task longer than 0.8 s at the rate in use
    for n in [FillNeedle::G27, FillNeedle::G29, FillNeedle::G30, FillNeedle::G31] {
        let pps = draw_pps(n, cal);
        let steps = draw_chunk_steps(pps);
        assert!(steps >= 1 && steps <= DRAW_CHUNK_STEPS);
        assert!(steps as u64 * 1000 <= pps as u64 * 800 + 999, "{n:?}: {steps} steps at {pps} pps");
    }
}

#[test]
fn takeup_covers_the_measured_lost_motion_and_the_prime_path_needs_several_primes() {
    // mechanical sim 2.9 / recommendation 11: backlash take-up of >= 152 steps after every draw
    let cal = NFP_608_2645_G16_20.cal();
    let takeup = cal.mu_to_pulses(MilliUnits(TAKEUP_MU_AFTER_DRAW)).0;
    assert_eq!(takeup, 160);
    assert!(takeup >= 152);
    // the take-up fits one minute of the 1.7 U/min backstop together with a maximum prime
    let minute = cal.mu_to_pulses(MAX_PER_MIN).0;
    assert!(takeup + cal.mu_to_pulses(MAX_PRIME).0 <= minute);
    // the connector path of the mechanical report (2.21 U) is purged by a few prime commands, never by one
    assert_eq!(PRIME_PATH_MU.0, 2_210);
    assert!(MAX_PRIME.0 < PRIME_PATH_MU.0);
    assert_eq!(prime_commands_for_path(), 5);
    // one prime command stays below the chunk-free burst the safety task can serve: 64 steps per chunk
    assert!(PRIME_CHUNK_STEPS <= 64);
}

#[test]
fn hourly_margin_bounds_the_physical_volume() {
    assert!(HOURLY_CAL_MARGIN_PCT >= 4);
    let cap = MAX_HOURLY.0 as u64 * 100 / (100 + HOURLY_CAL_MARGIN_PCT as u64);
    assert!(cap * (100 + HOURLY_CAL_MARGIN_PCT as u64) <= MAX_HOURLY.0 as u64 * 100);
}

#[test]
fn stored_volume_accounting_constants_are_derived() {
    // 2 U budget / 50 mU per mA = 40 mA rise above the pod's running level
    assert_eq!(OCC_BUDGET_MU, 2_000);
    assert_eq!(OCCLUSION_RISE_MA as u32 * OCC_STORED_MU_PER_MA, OCC_BUDGET_MU);
    // 0.0625 N/mA x 0.78 U/N = 49 mU/mA: the factor is at least that (conservative)
    assert!(OCC_STORED_MU_PER_MA >= 49);
    // the rise is far above the sense noise (3 mA) and the stick-slip swing of normal delivery (~11 mA)
    assert!(OCCLUSION_RISE_MA >= 30);
    // and the baseline creep is slower than an occlusion ramp
    assert!(OCC_BASELINE_CREEP_MA as u32 * 100 / OCC_BASELINE_CREEP_BURSTS as u32 <= 2);
}
