//! WP-2 (first part): core detectors, one `diag_<code>` test per code that the core detects today
//! (docs/06-diagnostics.md 6.1 level "C"). `tools/diag_coverage.py` lists the catalogue rows tagged `C` that still
//! have no such test. Each test asserts the code, severity, FRU/action from the catalogue, the legacy bit, the cause
//! chain and the active / latched state, using the fault injectors of the mock HAL (`MockState`: `reset_cause`,
//! `breadcrumb`, `ex_drv_fault`, `ex_vmot_missing`, `ex_peak`, `fault`, `steps_limit`, `reverse_pct`, ...).
mod common;

use common::*;
use openpatch_core::diag::*;
use openpatch_core::hal::{MotorFault, ResetCause};
use openpatch_core::limits::*;
use openpatch_core::*;

fn active(p: &Pump<MockHal>, code: DiagCode) -> Option<Active> {
    p.supervisor().diag().active().iter().find(|a| a.code.identity() == code.identity()).copied()
}

fn record_of(p: &Pump<MockHal>, code: DiagCode) -> DiagRecord {
    let a = active(p, code).unwrap_or_else(|| panic!("{code} is not active: {:?}", p.supervisor().diag().active()));
    p.supervisor().diag().record(a.rec_id).expect("record in ring")
}

/// The catalogue row of `code` agrees with what the record carries.
fn assert_catalogue(r: &DiagRecord, code: DiagCode) {
    let i = code.info().unwrap();
    assert_eq!(r.code.identity(), code.identity());
    assert_eq!(r.severity(), i.severity, "{code}");
    assert_eq!(r.action(), Some(i.action), "{code}");
    assert_eq!(r.fru(), Some(i.fru), "{code}");
    assert_eq!(r.is_latched(), i.severity == Severity::Latched, "{code}");
}

fn pump_with_reset(cause: ResetCause, breadcrumb: u32) -> Pump<MockHal> {
    let hal = MockHal::new();
    hal.st().reset_cause = cause;
    hal.st().breadcrumb = breadcrumb;
    let cal = cal_test();
    Pump::new(hal, Some(&cal), CAPACITY_100, 1)
}

// ---- reset cause ---------------------------------------------------------------------------------------

#[test]
fn diag_1_01_002_brownout_reset() {
    let p = pump_with_reset(ResetCause::Brownout, 7);
    let r = record_of(&p, codes::BROWNOUT_RESET);
    assert_catalogue(&r, codes::BROWNOUT_RESET);
    assert_eq!(r.ctx_a, 3900, "VBUS mV after boot");
    assert!(r.is_root());
    // the generic unexpected-reset record is its consequence
    let u = record_of(&p, codes::UNEXPECTED_RESET);
    assert_eq!(u.cause_rec, r.rec_id as u16);
    assert_eq!(p.supervisor().diag().summary().top_code, codes::BROWNOUT_RESET.0, "headline = root");
    assert!(p.supervisor().faults().is_empty(), "W: no legacy bit");
    assert!(p.supervisor().diag().legacy_faults().is_empty());
}

#[test]
fn diag_7_74_002_unexpected_reset() {
    for (cause, ctx_a) in [(ResetCause::Watchdog, 1), (ResetCause::Lockup, 3), (ResetCause::Other, 4)] {
        let p = pump_with_reset(cause, 0xBEEF);
        let r = record_of(&p, codes::UNEXPECTED_RESET);
        assert_catalogue(&r, codes::UNEXPECTED_RESET);
        assert_eq!((r.ctx_a, r.ctx_c), (ctx_a, 0xBEEF), "reset cause and the breadcrumb of the last task state");
        assert!(r.is_root());
        assert!(active(&p, codes::BROWNOUT_RESET).is_none());
    }
    for quiet in [ResetCause::PowerOn, ResetCause::Commanded] {
        let p = pump_with_reset(quiet, 0);
        assert!(active(&p, codes::UNEXPECTED_RESET).is_none(), "{quiet:?}");
    }
    // the pod boots suspended
    let p = pump_with_reset(ResetCause::Watchdog, 1);
    assert!(p.engine().is_suspended());
}

// ---- timing ----------------------------------------------------------------------------------------------

#[test]
fn diag_7_7b_001_tick_overrun() {
    let (mut p, h) = running(50_000, 1_000);
    h.advance_ms(1_000);
    p.tick();
    assert!(active(&p, codes::TICK_OVERRUN).is_none(), "a nominal tick is quiet");
    h.advance_ms(3_000); // above 2.5 s, below the 5 s stall limit
    p.tick();
    let r = record_of(&p, codes::TICK_OVERRUN);
    assert_catalogue(&r, codes::TICK_OVERRUN);
    assert_eq!((r.ctx_a, r.ctx_b), (3_000, TICK_OVERRUN_MS as i32));
    assert!(p.supervisor().faults().is_empty(), "W only: the 5 s stall stays a legacy tick overrun");
    h.advance_ms(1_000);
    p.tick();
    assert!(active(&p, codes::TICK_OVERRUN).is_none(), "cleared by a nominal tick");
    assert!(p.supervisor().diag().record(p.supervisor().diag().next_id() - 1).unwrap().is_clear_record());
}

// ---- power ------------------------------------------------------------------------------------------------

#[test]
fn diag_a_a0_001_battery_low() {
    let (mut p, h) = running(50_000, 1_000);
    h.st().battery_mv = BATTERY_LOW_MV - 50;
    run_secs(&mut p, &h, 1);
    let r = record_of(&p, codes::BATTERY_LOW);
    assert_catalogue(&r, codes::BATTERY_LOW);
    assert_eq!((r.code.inst(), r.ctx_a, r.ctx_b), (1, (BATTERY_LOW_MV - 50) as i32, BATTERY_LOW_MV as i32));
    assert!(p.supervisor().faults().is_empty());
    h.st().battery_mv = BATTERY_LOW_MV + 50; // inside the 100 mV hysteresis: still low
    run_secs(&mut p, &h, 1);
    assert!(active(&p, codes::BATTERY_LOW).is_some());
    h.st().battery_mv = BATTERY_LOW_MV + BATTERY_HYSTERESIS_MV;
    run_secs(&mut p, &h, 1);
    assert!(active(&p, codes::BATTERY_LOW).is_none(), "cleared at the hysteresis");
}

#[test]
fn diag_a_a0_002_battery_critical() {
    let (mut p, h) = running(50_000, 1_000);
    h.st().battery_mv = BATTERY_CRITICAL_MV - 10;
    run_secs(&mut p, &h, 1);
    let r = record_of(&p, codes::BATTERY_CRITICAL);
    assert_catalogue(&r, codes::BATTERY_CRITICAL);
    assert_eq!((r.code.inst(), r.ctx_a, r.ctx_b), (1, (BATTERY_CRITICAL_MV - 10) as i32, BATTERY_CRITICAL_MV as i32));
    assert_eq!(p.supervisor().faults(), Faults::BATTERY_CRITICAL, "legacy bit 3");
    assert!(p.engine().is_suspended());
}

// ---- reservoir -----------------------------------------------------------------------------------------------

#[test]
fn diag_5_50_002_reservoir_low() {
    let (mut p, h) = new_pump();
    p.fill(MilliUnits(11_000)).unwrap();
    activate(&mut p, 4_000).unwrap();
    p.resume().unwrap();
    assert!(active(&p, codes::RESERVOIR_LOW).is_none());
    run_secs(&mut p, &h, 1_200);
    let r = record_of(&p, codes::RESERVOIR_LOW);
    assert_catalogue(&r, codes::RESERVOIR_LOW);
    assert!(r.ctx_a > 0 && r.ctx_a <= 10_000, "remaining mU at or below the low level: {}", r.ctx_a);
    assert!(p.supervisor().faults().is_empty());
    p.suspend().unwrap();
    p.fill(MilliUnits(80_000)).unwrap();
    run_secs(&mut p, &h, 1);
    assert!(active(&p, codes::RESERVOIR_LOW).is_none(), "cleared by the refill");
}

#[test]
fn diag_5_50_001_reservoir_empty() {
    let (mut p, h) = new_pump();
    p.fill(MilliUnits(2_000)).unwrap();
    activate(&mut p, 4_000).unwrap();
    p.resume().unwrap();
    run_secs(&mut p, &h, 2_000);
    let r = record_of(&p, codes::RESERVOIR_EMPTY);
    assert_catalogue(&r, codes::RESERVOIR_EMPTY);
    assert_eq!(p.supervisor().faults(), Faults::RESERVOIR_EMPTY, "legacy bit 2");
}

// ---- wear ---------------------------------------------------------------------------------------------------------

#[test]
fn diag_b_b1_001_wear_warning() {
    let (mut p, h) = running(50_000, 1_000);
    p.restore_pod(TEST_PAIR, 1, true, 1, Millis(WEAR_WARN.0 - 500));
    run_secs(&mut p, &h, 1);
    let r = record_of(&p, codes::WEAR_WARNING);
    assert_catalogue(&r, codes::WEAR_WARNING);
    assert_eq!(r.ctx_a, (WEAR_WARN.0 / 60_000) as i32, "minutes worn");
    assert!(p.supervisor().faults().is_empty());
    p.release(TEST_PAIR).unwrap();
    p.activate(&ActivateArgs { pair_id: TEST_PAIR, activation_id: 2, schedule: BasalSchedule::flat(MilliUnitsPerHour(1_000)), temp: None }).unwrap();
    assert!(active(&p, codes::WEAR_WARNING).is_none(), "cleared by the new activation");
}

#[test]
fn diag_b_b1_002_wear_expired() {
    let (mut p, h) = running(50_000, 1_000);
    p.restore_pod(TEST_PAIR, 1, true, 1, Millis(WEAR_MAX.0 - 500));
    run_secs(&mut p, &h, 1);
    let r = record_of(&p, codes::WEAR_EXPIRED);
    assert_catalogue(&r, codes::WEAR_EXPIRED);
    assert_eq!(p.supervisor().faults(), Faults::WEAR_EXPIRED, "legacy bit 7");
    p.release(TEST_PAIR).unwrap();
    p.activate(&ActivateArgs { pair_id: TEST_PAIR, activation_id: 2, schedule: BasalSchedule::flat(MilliUnitsPerHour(1_000)), temp: None }).unwrap();
    assert!(active(&p, codes::WEAR_EXPIRED).is_none(), "cleared by Activate");
    assert!(p.supervisor().faults().is_empty());
}

// ---- calibration -------------------------------------------------------------------------------------------------------

#[test]
fn diag_7_7d_001_cal_record_invalid() {
    let p = Pump::new(MockHal::new(), None, CAPACITY_100, 1);
    let r = record_of(&p, codes::CAL_RECORD_INVALID);
    assert_catalogue(&r, codes::CAL_RECORD_INVALID);
    assert_eq!(r.code.inst(), 1, "missing");
    assert_eq!(p.supervisor().faults(), Faults::NO_CALIBRATION, "legacy bit 6");
    let out_of_range = PulseCal { uu_num: 1, uu_den: 1, turn_x100: 100 };
    let sv = SafetySupervisor::new(Millis(0), AngleCounts(0), out_of_range);
    assert_eq!(sv.diag().active()[0].code, codes::CAL_RECORD_INVALID.with_inst(3), "outside 1 to 60 mU per step");
}

// ---- supervisor limits ------------------------------------------------------------------------------------------------------

fn supervisor() -> SafetySupervisor {
    let mut sv = SafetySupervisor::new(Millis(0), AngleCounts(0), cal_test().pulse_cal().unwrap());
    sv.set_docked(true);
    sv.set_active(true);
    sv
}

#[test]
fn diag_7_70_002_per_minute_limit_veto() {
    let mut sv = supervisor();
    let per_min = sv.max_steps_per_min();
    assert_eq!(sv.approve_steps(Millis(0), per_min, MilliUnits(100_000)), per_min);
    assert!(sv.faults().is_empty());
    assert_eq!(sv.approve_steps(Millis(1_000), Pulses(1), MilliUnits(100_000)), Pulses(0), "no room left in this minute");
    let a = sv.diag().active().iter().find(|a| a.code.identity() == codes::PER_MINUTE_LIMIT_VETO.identity()).expect("7-70-002");
    let r = sv.diag().record(a.rec_id).unwrap();
    assert_catalogue(&r, codes::PER_MINUTE_LIMIT_VETO);
    assert_eq!((r.ctx_a, r.ctx_b), (per_min.0 as i32, per_min.0 as i32));
    assert_eq!(sv.faults(), Faults::LIMIT_EXCEEDED, "legacy bit 4");
}

#[test]
fn diag_7_70_001_hourly_limit_veto() {
    let mut sv = supervisor();
    let per_min = sv.max_steps_per_min();
    let mut vetoed_at = None;
    for minute in 0..20u64 {
        let got = sv.approve_steps(Millis(minute * 60_000), per_min, MilliUnits(1_000_000));
        if got < per_min {
            vetoed_at = Some(minute);
            break;
        }
    }
    assert!(vetoed_at.is_some_and(|m| (8..=10).contains(&m)), "about 15 U / 1.7 U per minute: {vetoed_at:?}");
    let a = sv.diag().active().iter().find(|a| a.code.identity() == codes::HOURLY_LIMIT_VETO.identity()).expect("7-70-001");
    let r = sv.diag().record(a.rec_id).unwrap();
    assert_catalogue(&r, codes::HOURLY_LIMIT_VETO);
    assert!(r.ctx_a <= r.ctx_b, "used steps against the cap");
    assert_eq!(sv.faults(), Faults::LIMIT_EXCEEDED);
}

#[test]
fn diag_5_53_001_occlusion_shortfall() {
    let mut sv = supervisor();
    let one_and_a_half_u = sv.calibration().mu_to_pulses(MilliUnits(1_500));
    sv.approve_steps(Millis(0), one_and_a_half_u, MilliUnits(100_000));
    sv.approve_steps(Millis(61_000), one_and_a_half_u, MilliUnits(100_000));
    // the spindle never moved: 3 U commanded, 0 confirmed (above the 2 U limit)
    sv.observe(Millis(62_000), &Observation { battery_mv: 3900, reservoir: Some(MilliUnits(90_000)), angle: AngleCounts(0) });
    let a = sv.diag().active().iter().find(|a| a.code.identity() == codes::OCCLUSION_SHORTFALL.identity()).expect("5-53-001");
    let r = sv.diag().record(a.rec_id).unwrap();
    assert_catalogue(&r, codes::OCCLUSION_SHORTFALL);
    assert!(r.ctx_a > 2_000, "undelivered mU {}", r.ctx_a);
    assert_eq!(r.ctx_b, 2_000, "threshold");
    assert!(sv.faults().contains(Faults::OCCLUSION), "legacy bit 0");
}

#[test]
fn diag_6_60_006_enc_rev_deviation() {
    let mut sv = supervisor();
    let turn = (sv.calibration().turn_x100 as u32).div_ceil(100);
    // the per-minute backstop lets about 65 steps through: command one revolution over several minutes
    let mut minute = 0u64;
    while sv.commanded_steps().0 < turn {
        sv.approve_steps(Millis(minute * 60_000), Pulses(60), MilliUnits(100_000));
        minute += 1;
    }
    let exact = sv.commanded_counts().0;
    // the commanded revolution reads 20 % short
    sv.observe(Millis(minute * 60_000), &Observation { battery_mv: 3900, reservoir: Some(MilliUnits(90_000)), angle: AngleCounts(exact * 80 / 100) });
    let a = sv.diag().active().iter().find(|a| a.code.identity() == codes::ENC_REV_DEVIATION.identity()).expect("6-60-006");
    let r = sv.diag().record(a.rec_id).unwrap();
    assert_catalogue(&r, codes::ENC_REV_DEVIATION);
    assert_eq!((r.ctx_a as i64, r.ctx_b as i64), (exact * 80 / 100, exact));
    assert!(sv.faults().contains(Faults::ENCODER_DEVIATION), "legacy bit 1");
}

// ---- pump level: stalls, current, HAL faults ----------------------------------------------------------------------------------

#[test]
fn diag_6_60_007_enc_window_deviation() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().delivered_pct = 50;
    p.bolus(MilliUnits(4_000)).unwrap();
    run_secs(&mut p, &h, 60);
    let r = record_of(&p, codes::ENC_WINDOW_DEVIATION);
    assert_catalogue(&r, codes::ENC_WINDOW_DEVIATION);
    assert!(r.ctx_a > 100 && r.ctx_b == 100, "permille deviation against the 10 % limit: {} / {}", r.ctx_a, r.ctx_b);
    assert!(p.supervisor().faults().contains(Faults::ENCODER_DEVIATION));
}

#[test]
fn diag_4_42_001_carriage_jam_fwd() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().delivered_pct = 0;
    p.bolus(MilliUnits(4_000)).unwrap();
    run_secs(&mut p, &h, 60);
    let jam = record_of(&p, codes::CARRIAGE_JAM_FWD);
    assert_catalogue(&jam, codes::CARRIAGE_JAM_FWD);
    assert_eq!(jam.cause_rec, record_of(&p, codes::ENC_WINDOW_DEVIATION).rec_id as u16, "the stall follows from the window deviation");
    assert!(p.supervisor().faults().contains(Faults::OCCLUSION), "legacy bit 0");
}

#[test]
fn diag_5_53_002_occlusion_current_rise() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().current_ma = Some(OCCLUSION_CURRENT_MA + 25);
    p.bolus(MilliUnits(4_000)).unwrap();
    run_secs(&mut p, &h, 30);
    let r = record_of(&p, codes::OCCLUSION_CURRENT_RISE);
    assert_catalogue(&r, codes::OCCLUSION_CURRENT_RISE);
    assert_eq!((r.ctx_a, r.ctx_b), ((OCCLUSION_CURRENT_MA + 25) as i32, OCCLUSION_CURRENT_MA as i32));
    assert!(p.supervisor().faults().contains(Faults::OCCLUSION));
}

#[test]
fn diag_6_60_001_angle_channel_lost() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().angle_missing = true;
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 2);
    let r = record_of(&p, codes::ANGLE_CHANNEL_LOST);
    assert_catalogue(&r, codes::ANGLE_CHANNEL_LOST);
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
}

#[test]
fn diag_7_70_005_steps_short_of_approval() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().steps_limit = 0;
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 3);
    let r = record_of(&p, codes::STEPS_SHORT_OF_APPROVAL);
    assert_catalogue(&r, codes::STEPS_SHORT_OF_APPROVAL);
    assert!(r.ctx_a < r.ctx_b, "executed {} against approved {}", r.ctx_a, r.ctx_b);
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
}

#[test]
fn diag_1_03_001_driver_fault_in_burst() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().ex_drv_fault = true;
    h.st().ex_peak = Some(150);
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 3);
    let r = record_of(&p, codes::DRIVER_FAULT_IN_BURST);
    assert_catalogue(&r, codes::DRIVER_FAULT_IN_BURST);
    assert_eq!(r.ctx_a, 150, "peak mA");
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
}

#[test]
fn diag_1_06_002_vmot_not_present() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().ex_vmot_missing = true;
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 3);
    assert_catalogue(&record_of(&p, codes::VMOT_NOT_PRESENT), codes::VMOT_NOT_PRESENT);
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
    // a HAL that reports the same through `motor_fault`
    let (mut p, h) = running(50_000, 2_000);
    h.st().fault = Some(MotorFault::SupplyMissing);
    h.st().steps_limit = 0;
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 3);
    let hal = record_of(&p, codes::VMOT_NOT_PRESENT);
    assert_eq!(record_of(&p, codes::STEPS_SHORT_OF_APPROVAL).cause_rec, hal.rec_id as u16);
}

#[test]
fn diag_1_06_001_vmot_stuck_on() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().fault = Some(MotorFault::SupplyUnexpected);
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 3);
    let r = record_of(&p, codes::VMOT_STUCK_ON);
    assert_catalogue(&r, codes::VMOT_STUCK_ON);
    assert!(r.is_latched());
    assert_eq!(p.supervisor().diag().latched().len(), 1);
    assert_eq!(p.acknowledge(Faults::ALL), Err(Error::Persists), "a latched code is never acknowledged away");
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
}

#[test]
fn diag_7_76_001_interlock_failed_latch() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().fault = Some(MotorFault::InterlockFailed);
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 3);
    let r = record_of(&p, codes::INTERLOCK_FAILED_LATCH);
    assert_catalogue(&r, codes::INTERLOCK_FAILED_LATCH);
    assert_eq!(p.supervisor().diag().latched().len(), 1);
}

#[test]
fn diag_7_77_001_step_count_short() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().fault = Some(MotorFault::Timeout);
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 3);
    assert_catalogue(&record_of(&p, codes::STEP_COUNT_SHORT), codes::STEP_COUNT_SHORT);
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
}

// ---- draw -----------------------------------------------------------------------------------------------------------------------

fn draw_pump() -> (Pump<MockHal>, MockHal) {
    let (mut p, h) = new_pump();
    p.fill(MilliUnits(10_000)).unwrap();
    h.st().docked = false;
    (p, h)
}

#[test]
fn diag_7_73_001_draw_aborted() {
    // cancelled (inst 3)
    let (mut p, h) = draw_pump();
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_secs(&mut p, &h, 1);
    p.fill_draw(MilliUnits(0)).unwrap();
    let r = record_of(&p, codes::DRAW_ABORTED);
    assert_catalogue(&r, codes::DRAW_ABORTED);
    assert_eq!(r.code.inst(), 3);
    assert!(p.supervisor().faults().is_empty(), "W: refill stopped early, no fault");
    // docked meanwhile (inst 1)
    let (mut p, h) = draw_pump();
    p.fill_draw(MilliUnits(40_000)).unwrap();
    h.st().docked = true;
    run_secs(&mut p, &h, 2);
    assert_eq!(record_of(&p, codes::DRAW_ABORTED).code.inst(), 1);
    // stall (inst 4): the sensor sees too little reverse travel
    let (mut p, h) = draw_pump();
    h.st().reverse_pct = 10;
    p.fill_draw(MilliUnits(40_000)).unwrap();
    run_draw(&mut p, &h);
    assert_eq!(record_of(&p, codes::DRAW_ABORTED).code.inst(), 4);
}

#[test]
fn diag_7_73_002_draw_blocked_no_vmot() {
    let (mut p, h) = draw_pump();
    h.st().fault = Some(MotorFault::SupplyMissing);
    p.fill_draw(MilliUnits(2_000)).unwrap();
    run_draw(&mut p, &h);
    let r = record_of(&p, codes::DRAW_BLOCKED_NO_VMOT);
    assert_catalogue(&r, codes::DRAW_BLOCKED_NO_VMOT);
    assert_eq!(r.cause_rec, record_of(&p, codes::VMOT_NOT_PRESENT).rec_id as u16, "chain to 1-06-002");
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
}

#[test]
fn diag_4_40_003_dir_inverted() {
    let (mut p, h) = draw_pump();
    h.st().reverse_pct = -100; // reverse pulses INCREASE the angle: wrong DIR polarity
    p.fill_draw(MilliUnits(2_000)).unwrap();
    run_draw(&mut p, &h);
    let r = record_of(&p, codes::DIR_INVERTED);
    assert_catalogue(&r, codes::DIR_INVERTED);
    assert!(r.ctx_a > 0 && r.ctx_b > 0, "the angle ROSE by {} against an expected travel of {}", r.ctx_a, r.ctx_b);
    assert!(r.is_latched());
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
    assert!(!p.draw_running(), "the draw is aborted");
    assert_eq!(p.draw_state(), openpatch_proto::draw::ABORTED);
}

// ---- engine-internal codes that are exercised in diag.rs, named here for the coverage report -------------------------------------

#[test]
fn diag_7_7c_003_unknown_code_raised() {
    let mut d = DiagState::new();
    let id = d.raise(Raise::new(DiagCode(0x1ABC_D000)));
    assert_catalogue(&d.record(id).unwrap(), codes::UNKNOWN_CODE_RAISED);
    assert_eq!(d.legacy_faults(), Faults::INTERNAL);
}

#[test]
fn diag_7_74_001_boot() {
    let (p, _h) = new_pump();
    let r = p.supervisor().diag().record(1).unwrap();
    assert_catalogue(&r, codes::BOOT);
    assert!(!r.is_active());
}

#[test]
fn diag_7_74_006_post_result() {
    let (mut p, _h) = new_pump();
    p.run_self_test(2).unwrap();
    let r = p.supervisor().diag().record(p.supervisor().diag().next_id() - 1).unwrap();
    assert_catalogue(&r, codes::POST_RESULT);
    assert!(r.flags & flags::POST != 0);
}
