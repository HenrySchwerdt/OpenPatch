//! Burst stepping for the cell's peak current (`burst`): timing as a pure function, configurable cell parameters.
use openpatch_core::battery::{MotorSupplyLimits, MOTOR_MIN_VBAT_MV, MOTOR_REST_MIN_MV};
use openpatch_core::burst::*;

const P: u32 = 5_000; // 200 pps

#[test]
fn cell_current_matches_the_interlock_numbers() {
    // INTERLOCK.md I.2: 1.74 W at 88 % -> 0.58 A at 3.4 V, 0.66 A at 3.0 V
    let l = MotorLoad::NFP_608_26_45;
    assert_eq!(cell_current_ma(l, 3_400), 582);
    assert_eq!(cell_current_ma(l, 3_000), 660);
    assert_eq!(cell_current_ma(l, 4_200), 471);
    assert_eq!(cell_current_ma(l, 0), u32::MAX);
    assert_eq!(cell_current_ma(MotorLoad { power_mw: 1_000, boost_eff_pct: 0 }, 3_700), u32::MAX);
    let mut prev = u32::MAX;
    for mv in (3_000..=4_200).step_by(50) {
        let i = cell_current_ma(l, mv);
        assert!(i <= prev, "more current at a lower voltage, always");
        prev = i;
    }
}

#[test]
fn default_plan_is_short_bursts_with_long_rests() {
    let plan = plan_burst(CellParams::AMPUL_301030, MotorLoad::NFP_608_26_45, 3_800, P, 32).unwrap();
    // 150 ms / 5 ms = 30 periods, the first is the alignment period: 29 steps, 150 ms energised
    assert_eq!((plan.steps, plan.burst_ms), (29, 150));
    assert_eq!(plan.cell_ma, 521); // 1740 mW / 0.88 / 3.8 V
    // 90 mA average: rest = ceil(150 x (521 - 90) / 90) = 719 ms
    assert_eq!(plan.rest_ms, 719);
    assert!(plan.average_ma() <= 90, "average {} mA", plan.average_ma());
    assert!(plan.rest_ms >= CellParams::AMPUL_301030.min_rest_ms as u32);
    assert!(plan.steps <= 32, "fits the supervisor budget of one armed window");
    assert_eq!(plan.ticks_per_cycle(1_000), 1);
}

#[test]
fn average_current_is_bounded_over_the_whole_voltage_range() {
    for mv in (MOTOR_REST_MIN_MV..=4_200).step_by(25) {
        let plan = plan_burst(CellParams::AMPUL_301030, MotorLoad::NFP_608_26_45, mv, P, 32).unwrap();
        assert!(plan.average_ma() <= CellParams::AMPUL_301030.avg_limit_ma as u32, "{mv} mV: {} mA", plan.average_ma());
        assert!(plan.cell_ma <= CellParams::AMPUL_301030.max_pulse_ma as u32);
        assert!(plan.burst_ms <= CellParams::AMPUL_301030.max_pulse_ms as u32);
    }
}

#[test]
fn lower_cell_voltage_means_longer_rest() {
    let rest = |mv| plan_burst(CellParams::default(), MotorLoad::default(), mv, P, 32).unwrap().rest_ms;
    assert!(rest(3_700) > rest(3_800));
    assert!(rest(3_800) > rest(4_200));
}

#[test]
fn refused_below_the_rest_threshold_and_when_the_cell_cannot_supply() {
    // F2: interim rest threshold 3.7 V (was 3.4 V); the old limit is now only the floor under the configurable threshold
    assert_eq!(plan_burst(CellParams::default(), MotorLoad::default(), 3_699, P, 32), Err(BurstRefusal::BatteryLow));
    assert!(plan_burst(CellParams::default(), MotorLoad::default(), 3_700, P, 32).is_ok());
    let weak = CellParams { max_pulse_ma: 500, ..CellParams::default() };
    assert_eq!(plan_burst(weak, MotorLoad::default(), 3_700, P, 32), Err(BurstRefusal::CellCannotSupply));
    assert!(plan_burst(weak, MotorLoad::default(), 4_200, P, 32).is_ok(), "471 mA at 4.2 V");
}

#[test]
fn the_rest_threshold_is_configurable_but_never_below_the_boost_minimum() {
    let lenient = CellParams { supply: MotorSupplyLimits::new(3_400, 2_800).unwrap(), ..CellParams::default() };
    assert!(plan_burst(lenient, MotorLoad::default(), 3_400, P, 32).is_ok(), "bench setting after the ESR is measured");
    assert_eq!(plan_burst(lenient, MotorLoad::default(), 3_399, P, 32), Err(BurstRefusal::BatteryLow));
    // a hand-built value below the floor does not relax anything
    let hacked = CellParams { supply: MotorSupplyLimits { rest_min_mv: 0, load_abort_mv: 0 }, ..CellParams::default() };
    assert_eq!(plan_burst(hacked, MotorLoad::default(), MOTOR_MIN_VBAT_MV - 1, P, 32), Err(BurstRefusal::BatteryLow));
    let strict = CellParams { supply: MotorSupplyLimits::new(3_900, 2_800).unwrap(), ..CellParams::default() };
    assert_eq!(plan_burst(strict, MotorLoad::default(), 3_800, P, 32), Err(BurstRefusal::BatteryLow));
    assert!(plan_burst(strict, MotorLoad::default(), 3_900, P, 32).is_ok());
}

#[test]
fn step_budget_cap_and_period_limits() {
    let p = plan_burst(CellParams::default(), MotorLoad::default(), 3_800, P, 16).unwrap();
    assert_eq!(p.steps, 16);
    assert_eq!(p.burst_ms, 85); // 17 periods
    assert_eq!(plan_burst(CellParams::default(), MotorLoad::default(), 3_800, 0, 32), Err(BurstRefusal::PeriodOutOfRange));
    // a period of 100 ms: only one period fits into the 150 ms limit, no step after the alignment period
    assert_eq!(plan_burst(CellParams::default(), MotorLoad::default(), 3_800, 100_000, 32), Err(BurstRefusal::PeriodOutOfRange));
    assert_eq!(plan_burst(CellParams::default(), MotorLoad::default(), 3_800, P, 0), Err(BurstRefusal::PeriodOutOfRange));
}

#[test]
fn parameters_are_configurable() {
    let cell = CellParams { capacity_mah: 90, max_pulse_ma: 900, max_pulse_ms: 60, avg_limit_ma: 200, min_rest_ms: 100, supply: MotorSupplyLimits::DEFAULT };
    let plan = plan_burst(cell, MotorLoad::default(), 3_800, P, 32).unwrap();
    assert_eq!((plan.steps, plan.burst_ms), (11, 60));
    assert_eq!(plan.rest_ms, 100.max((60 * (521 - 200) as u32).div_ceil(200)));
    assert!(plan.average_ma() <= 200);
    // a cell that is never limited by the average still keeps the minimum rest
    let strong = CellParams { avg_limit_ma: 1_000, min_rest_ms: 40, ..cell };
    assert_eq!(plan_burst(strong, MotorLoad::default(), 3_800, P, 32).unwrap().rest_ms, 40);
}

#[test]
fn rest_for_burst_formula() {
    let c = CellParams { avg_limit_ma: 100, min_rest_ms: 10, ..CellParams::default() };
    assert_eq!(rest_for_burst(c, 600, 100), 500); // duty 1/6
    assert_eq!(rest_for_burst(c, 100, 100), 10); // at the limit: only the minimum
    assert_eq!(rest_for_burst(c, 50, 100), 10);
    assert_eq!(rest_for_burst(c, 601, 100), 501); // rounds up
}

#[test]
fn a_request_is_split_into_bursts_with_a_shorter_last_one() {
    let cell = CellParams::default();
    let plan = plan_burst(cell, MotorLoad::default(), 3_800, P, 32).unwrap();
    let chunks: Vec<_> = Chunks::new(70, plan, cell, P).collect();
    assert_eq!(chunks.iter().map(|c| c.steps).collect::<Vec<_>>(), [29, 29, 12]);
    assert_eq!(chunks[0].rest_ms, plan.rest_ms);
    assert!(chunks[2].rest_ms < plan.rest_ms, "a shorter burst needs a shorter rest");
    assert!(chunks[2].rest_ms >= cell.min_rest_ms as u32);
    assert_eq!(Chunks::new(0, plan, cell, P).count(), 0);
    assert_eq!(Chunks::new(29, plan, cell, P).count(), 1);
    assert_eq!(Chunks::new(30, plan, cell, P).count(), 2);
}

#[test]
fn total_time_counts_bursts_and_the_rests_between_them() {
    let cell = CellParams::default();
    let plan = plan_burst(cell, MotorLoad::default(), 3_800, P, 32).unwrap();
    assert_eq!(total_time_ms(0, plan, cell, P), 0);
    assert_eq!(total_time_ms(29, plan, cell, P), 150, "one burst, no rest after the last");
    assert_eq!(total_time_ms(58, plan, cell, P), 150 + plan.rest_ms as u64 + 150);
    // sustained, the average over many bursts stays at the limit
    let t = total_time_ms(29 * 100, plan, cell, P);
    let avg_ma = plan.cell_ma as u64 * (150 * 100) / t;
    assert!(avg_ma <= 90 + 1, "sustained average {avg_ma} mA");
}

#[test]
fn burst_ms_for_rounds_up_and_counts_the_alignment_period() {
    assert_eq!(burst_ms_for(1, 5_000), 10);
    assert_eq!(burst_ms_for(29, 5_000), 150);
    assert_eq!(burst_ms_for(3, 1_500), 6);
    assert_eq!(burst_ms_for(2, 1_500), 5); // 4.5 ms rounds up
}

#[test]
fn bolus_rate_is_well_inside_what_the_cell_allows() {
    // 1.5 U/min bolus on the cup drive = 213 steps/min = 3.6 steps/s; the burst capacity is about 30 steps/s
    let cell = CellParams::default();
    let plan = plan_burst(cell, MotorLoad::default(), 3_700, P, 32).unwrap();
    let capacity = plan.steps as u64 * 1_000 / (plan.burst_ms + plan.rest_ms) as u64;
    assert!(capacity >= 10, "capacity {capacity} steps/s");
}
