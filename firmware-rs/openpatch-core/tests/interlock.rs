//! Bench interlock model (`VMOT = MCU_EN AND LATCH AND (DOCKED OR DIR_REVERSE)`), the power-up plan,
//! draw-mode direction sequencing at the Hal boundary, HAL fault return, runtime occlusion
//! threshold and the peak-current CSV column.
mod common;
use common::*;
use openpatch_core::bench::*;
use openpatch_core::interlock::*;
use openpatch_core::limits::*;
use openpatch_core::*;

const ON_MV: u32 = 3_000;
const OFF_MV: u32 = 1_500;

#[test]
fn gate_truth_table() {
    use MotorDir::*;
    for latch in [false, true] {
        for mcu in [false, true] {
            for docked in [false, true] {
                for dir in [Forward, Reverse] {
                    let want = latch && mcu && (docked || dir == Reverse);
                    assert_eq!(vmot_expected(latch, mcu, docked, dir), want);
                }
            }
        }
    }
    // the point of the new gate
    assert!(vmot_expected(true, true, false, Reverse));
    assert!(!vmot_expected(true, true, false, Forward));
    assert!(vmot_expected(true, true, true, Forward));
}

#[test]
fn requests_forward_needs_docked_reverse_needs_undocked() {
    use MotorDir::*;
    assert_eq!(check_request(Forward, true), Ok(()));
    assert_eq!(check_request(Reverse, false), Ok(()));
    assert_eq!(check_request(Forward, false), Err(Refusal::ForwardWhileUndocked));
    assert_eq!(check_request(Reverse, true), Err(Refusal::ReverseWhileDocked));
    assert_eq!(MotorFault::from(Refusal::ForwardWhileUndocked), MotorFault::ForwardWhileUndocked);
    assert_eq!(MotorFault::from(Refusal::ReverseWhileDocked), MotorFault::ReverseWhileDocked);
}

#[test]
fn dir_is_set_before_the_supply_is_requested_in_both_directions() {
    for dir in [MotorDir::Forward, MotorDir::Reverse] {
        let plan = power_up_plan(dir);
        assert_eq!(plan[0], Step::SetDir(dir), "DIR must be the first action");
        let pos = |s: Step| plan.iter().position(|x| *x == s).unwrap();
        assert!(pos(Step::SetDir(dir)) < pos(Step::McuEnHigh));
        assert!(pos(Step::McuEnHigh) < pos(Step::ArmEdge));
        assert!(pos(Step::ArmEdge) < pos(Step::CheckLatchSet));
        assert!(pos(Step::CheckLatchSet) < pos(Step::CheckVmotUp));
        assert!(pos(Step::CheckVmotUp) < pos(Step::DriverOn), "driver wakes only after the supply is verified");
    }
}

/// Executes the plan on a model of the board, the way the HAL does.
struct Board {
    dir: MotorDir,
    mcu_en: bool,
    latch: bool,
    docked: bool,
    /// Simulates a failed (always conducting) supply switch.
    gate_shorted: bool,
    /// Supply seen by the very first MCU_EN edge (for the ordering test).
    vmot_at_mcu_en: Option<bool>,
}

impl Board {
    fn new(docked: bool) -> Self {
        Board { dir: MotorDir::Forward, mcu_en: false, latch: false, docked, gate_shorted: false, vmot_at_mcu_en: None }
    }
    fn vmot(&self) -> bool {
        self.gate_shorted || vmot_expected(self.latch, self.mcu_en, self.docked, self.dir)
    }
    fn vmot_mv(&self) -> u32 {
        if self.vmot() {
            4_800
        } else {
            0
        }
    }
    fn run(&mut self, plan: &[Step]) -> Result<(), SupplyCheck> {
        for s in plan {
            match *s {
                Step::SetDir(d) => self.dir = d,
                Step::ReleaseKill => {}
                Step::McuEnHigh => self.mcu_en = true,
                Step::ArmEdge => self.latch = true,
                Step::CheckLatchSet => assert!(self.latch),
                Step::CheckVmotUp => {
                    self.vmot_at_mcu_en = Some(self.vmot());
                    // power-up requires the supply to be present
                    match check_supply(true, self.vmot_mv(), ON_MV, OFF_MV) {
                        SupplyCheck::Ok => {}
                        e => return Err(e),
                    }
                }
                Step::DriverOn => {}
            }
        }
        Ok(())
    }
}

#[test]
fn draw_undocked_with_reverse_first_brings_the_supply_up() {
    let mut b = Board::new(false);
    assert_eq!(check_request(MotorDir::Reverse, b.docked), Ok(()));
    assert_eq!(b.run(&power_up_plan(MotorDir::Reverse)), Ok(()));
    assert_eq!(b.vmot_at_mcu_en, Some(true));
}

#[test]
fn draw_with_dir_set_after_the_enable_would_not_come_up() {
    // The ordering the plan forbids: MCU_EN / ARM first, DIR afterwards.
    let mut b = Board::new(false);
    let wrong = [Step::ReleaseKill, Step::McuEnHigh, Step::ArmEdge, Step::CheckLatchSet, Step::CheckVmotUp, Step::SetDir(MotorDir::Reverse)];
    assert_eq!(b.run(&wrong), Err(SupplyCheck::Missing));
}

#[test]
fn forward_undocked_is_refused_and_a_closed_gate_would_show_missing_supply() {
    assert_eq!(check_request(MotorDir::Forward, false), Err(Refusal::ForwardWhileUndocked));
    // even if the request check were skipped, the supply check catches it
    let mut b = Board::new(false);
    assert_eq!(b.run(&power_up_plan(MotorDir::Forward)), Err(SupplyCheck::Missing));
}

#[test]
fn forward_docked_comes_up() {
    let mut b = Board::new(true);
    assert_eq!(b.run(&power_up_plan(MotorDir::Forward)), Ok(()));
}

#[test]
fn dir_change_while_powered_is_checked_against_the_model() {
    // powered reverse undocked, then DIR goes forward: the supply must collapse
    let mut b = Board::new(false);
    b.run(&power_up_plan(MotorDir::Reverse)).unwrap();
    b.dir = MotorDir::Forward;
    let exp = vmot_expected(b.latch, b.mcu_en, b.docked, b.dir);
    assert!(!exp);
    assert_eq!(check_supply(exp, b.vmot_mv(), ON_MV, OFF_MV), SupplyCheck::Ok);
    // a shorted switch keeps the supply up: this is an interlock failure
    b.gate_shorted = true;
    assert_eq!(check_supply(exp, b.vmot_mv(), ON_MV, OFF_MV), SupplyCheck::Unexpected);
}

#[test]
fn supply_check_thresholds_and_dead_band() {
    assert_eq!(check_supply(true, 3_000, ON_MV, OFF_MV), SupplyCheck::Ok);
    assert_eq!(check_supply(true, 2_999, ON_MV, OFF_MV), SupplyCheck::Missing);
    assert_eq!(check_supply(false, 1_500, ON_MV, OFF_MV), SupplyCheck::Ok);
    assert_eq!(check_supply(false, 1_501, ON_MV, OFF_MV), SupplyCheck::Unexpected);
    // dead band fails either way
    assert_eq!(check_supply(true, 2_000, ON_MV, OFF_MV), SupplyCheck::Missing);
    assert_eq!(check_supply(false, 2_000, ON_MV, OFF_MV), SupplyCheck::Unexpected);
}

// ---- Hal boundary ----------------------------------------------------------------------------

#[test]
fn draw_requests_the_supply_with_reverse_direction_and_delivery_with_forward() {
    let (mut p, h) = new_pump();
    p.fill(MilliUnits(10_000)).unwrap();
    h.st().docked = false;
    p.fill_draw(MilliUnits(2_000)).unwrap();
    run_secs(&mut p, &h, 3);
    {
        let st = h.st();
        assert!(!st.enable_dirs.is_empty());
        assert!(st.enable_dirs.iter().all(|d| *d == MotorDir::Reverse));
    }
    let (mut p, h) = running(50_000, 2_000);
    h.st().enable_dirs.clear();
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 5);
    let st = h.st();
    assert!(!st.enable_dirs.is_empty());
    assert!(st.enable_dirs.iter().all(|d| *d == MotorDir::Forward));
}

#[test]
fn hal_fault_after_a_forward_burst_latches_internal_and_is_remembered() {
    let (mut p, h) = running(50_000, 2_000);
    h.st().fault = Some(MotorFault::ForwardWhileUndocked);
    p.bolus(MilliUnits(500)).unwrap();
    run_secs(&mut p, &h, 3);
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
    assert_eq!(p.last_motor_fault(), Some(MotorFault::ForwardWhileUndocked));
}

#[test]
fn hal_fault_during_draw_aborts_and_latches_internal() {
    let (mut p, h) = new_pump();
    p.fill(MilliUnits(10_000)).unwrap();
    h.st().docked = false;
    h.st().fault = Some(MotorFault::SupplyMissing);
    p.fill_draw(MilliUnits(2_000)).unwrap();
    run_draw(&mut p, &h);
    assert!(!p.draw_running());
    assert!(p.supervisor().faults().contains(Faults::INTERNAL));
    assert_eq!(p.last_motor_fault(), Some(MotorFault::SupplyMissing));
}

// ---- occlusion threshold setter ---------------------------------------------------------------

#[test]
fn occlusion_threshold_can_only_be_lowered() {
    let (mut p, _h) = new_pump();
    assert_eq!(p.supervisor().occlusion_current_ma(), OCCLUSION_CURRENT_MA);
    assert_eq!(p.set_occlusion_current_ma(OCCLUSION_CURRENT_MA + 1), Err(Error::Limit));
    assert_eq!(p.set_occlusion_current_ma(0), Err(Error::Limit));
    assert_eq!(p.supervisor().occlusion_current_ma(), OCCLUSION_CURRENT_MA);
    assert_eq!(p.set_occlusion_current_ma(OCCLUSION_CURRENT_MA), Ok(()));
    assert_eq!(p.set_occlusion_current_ma(90), Ok(()));
    assert_eq!(p.supervisor().occlusion_current_ma(), 90);
}

#[test]
fn lowered_threshold_triggers_occlusion_earlier() {
    let (mut p, h) = running(50_000, 5_000);
    p.set_occlusion_current_ma(90).unwrap();
    h.st().current_ma = Some(100); // above 90, below the hard 140
    for _ in 0..OCCLUSION_CURRENT_BURSTS {
        p.bolus(MilliUnits(100)).ok();
        run_secs(&mut p, &h, 4);
    }
    assert!(p.supervisor().faults().contains(Faults::OCCLUSION));
}

#[test]
fn default_threshold_does_not_trigger_at_100_ma() {
    let (mut p, h) = running(50_000, 5_000);
    h.st().current_ma = Some(100);
    for _ in 0..OCCLUSION_CURRENT_BURSTS + 2 {
        p.bolus(MilliUnits(100)).ok();
        run_secs(&mut p, &h, 4);
    }
    assert!(!p.supervisor().faults().contains(Faults::OCCLUSION));
}

// ---- bench CSV peak current ---------------------------------------------------------------------

#[test]
fn csv_has_a_peak_current_column() {
    assert!(CSV_HEADER.ends_with(",peak_ma"));
    let row = CsvRow { t_ms: 1, pulse: 1, cmd_mu: 2, delivered_steps: 3, delivered_mu: 4, angle_counts: 5, faults: 0, peak_ma: Some(87) };
    let mut s = String::new();
    row.write_csv(&mut s).unwrap();
    assert_eq!(s, "1,1,2,3,4,5,0,87");
    let none = CsvRow { peak_ma: None, ..row };
    let mut s = String::new();
    none.write_csv(&mut s).unwrap();
    assert_eq!(s, "1,1,2,3,4,5,0,");
    assert_eq!(s.split(',').count(), CSV_HEADER.split(',').count());
}

#[test]
fn bench_rows_carry_the_peak_of_the_pulse() {
    let hal = MockHal::new();
    let cal = cal_test();
    let mut p = Pump::new(hal.clone(), Some(&cal), CAPACITY_100, 1);
    prepare(&mut p, MilliUnits(50_000)).unwrap();
    hal.st().current_ma = Some(77);
    let mut r = BenchRunner::new(BenchConfig { pulses: 1, amount: MilliUnits(500), pause: Millis(1000) }).unwrap();
    let mut got = None;
    for _ in 0..100 {
        hal.advance_ms(1000);
        p.tick();
        if let BenchEvent::Row(row) = r.step(&mut p, Millis(hal.0.borrow().now_ms)) {
            got = Some(row);
            break;
        }
    }
    assert_eq!(got.unwrap().peak_ma, Some(77));
}
