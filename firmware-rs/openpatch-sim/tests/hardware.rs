//! Unit-level checks of the hardware models behind the `Hal` trait: interlock gate, TPL5010,
//! supply, flash, angle sensor. Each of these is an assumption the system-level scenarios stand on.

use openpatch_core::{Buzzer, Hal, Pulses};
use openpatch_sim::params::Params;
use openpatch_sim::plant::Plant;
use openpatch_sim::rng::Rng;
use openpatch_sim::world::{ResetCause, SimHal, World};
use std::cell::RefCell;
use std::rc::Rc;

fn world() -> Rc<RefCell<World>> {
    Rc::new(RefCell::new(World::new(Params::default(), 1)))
}

fn at_us(w: &Rc<RefCell<World>>, us: u64) {
    w.borrow_mut().advance_to(us);
}

#[test]
fn interlock_gate_is_mcu_en_and_latch_and_docked_or_reverse() {
    let w = world();
    for bits in 0..16u32 {
        let (en, latch, docked, rev) = (bits & 1 != 0, bits & 2 != 0, bits & 4 != 0, bits & 8 != 0);
        let mut x = w.borrow_mut();
        x.mcu_en = en;
        x.latch_q = latch;
        x.docked_phys = docked;
        x.dir_reverse = rev;
        assert_eq!(x.vmot_on(), en && latch && (docked || rev), "en {en} latch {latch} docked {docked} rev {rev}");
    }
}

#[test]
fn a_burst_needs_the_interlock_and_reports_zero_pulses_otherwise() {
    let w = world();
    let mut h = SimHal(w.clone());
    // not enabled: refused
    assert_eq!(h.motor_step(Pulses(10)).0, 0);
    assert_eq!(w.borrow().plant.forward_moved_steps, 0);
    assert_eq!(w.borrow().stats.bursts_blocked_by_interlock, 1);
    // enabled and docked: runs
    h.motor_enable(true);
    assert_eq!(h.motor_step(Pulses(10)).0, 10);
    h.motor_enable(false);
    assert!(!w.borrow().vmot_on());
    // undocked: forward refused, reverse allowed (DIR_REVERSE)
    w.borrow_mut().docked_phys = false;
    h.motor_enable(true);
    assert_eq!(h.motor_step(Pulses(10)).0, 0);
    assert_eq!(h.motor_step_reverse(Pulses(10)).0, 10);
    assert_eq!(w.borrow().stats.bursts_blocked_forward_undocked, 1);
    assert_eq!(w.borrow().stats.forward_steps_moved_undocked, 0);
}

#[test]
fn burst_time_is_steps_over_rate_and_the_clock_is_monotonic() {
    let w = world();
    let mut h = SimHal(w.clone());
    h.motor_enable(true);
    let t0 = h.time_ms().0;
    h.motor_step(Pulses(100));
    let dt = h.time_ms().0 - t0;
    assert_eq!(dt, 500, "100 steps at 200 Hz"); // 5 ms each
    h.motor_step_reverse(Pulses(600));
    assert_eq!(h.time_ms().0 - t0 - dt, 1000, "600 steps at 600 Hz");
}

#[test]
fn watchdog_cuts_the_supply_exactly_one_period_after_the_last_done() {
    let w = world();
    let mut h = SimHal(w.clone());
    h.motor_enable(true);
    h.watchdog_kick();
    at_us(&w, 1_990_000);
    assert!(w.borrow().vmot_on() && w.borrow().reset_pending.is_none());
    at_us(&w, 2_010_000);
    assert!(!w.borrow().vmot_on());
    assert_eq!(w.borrow().reset_pending, Some(ResetCause::Watchdog));
    let (done, cut) = w.borrow().stats.wdt_cuts[0];
    assert!((cut - done) as f64 / 1000.0 <= 2001.0, "cut {} ms after DONE", (cut - done) / 1000);
}

#[test]
fn a_serviced_watchdog_never_fires() {
    let w = world();
    let mut h = SimHal(w.clone());
    for k in 1..=300u64 {
        at_us(&w, k * 1_000_000);
        h.watchdog_kick();
    }
    assert!(w.borrow().reset_pending.is_none());
    assert!(w.borrow().stats.wdt_cuts.is_empty());
}

#[test]
fn watchdog_period_is_a_parameter() {
    let mut p = Params::default();
    p.electrical.wdt_period_ms = 500.0;
    let w = Rc::new(RefCell::new(World::new(p, 1)));
    at_us(&w, 480_000);
    assert!(w.borrow().reset_pending.is_none());
    at_us(&w, 520_000);
    assert!(w.borrow().reset_pending.is_some());
}

#[test]
fn a_stuck_done_line_resets_every_period() {
    let w = world();
    w.borrow_mut().kick_stuck = true;
    let mut h = SimHal(w.clone());
    let mut resets = 0;
    for k in 1..=100u64 {
        at_us(&w, k * 100_000);
        h.watchdog_kick();
        if w.borrow_mut().reset_pending.take().is_some() {
            resets += 1;
            w.borrow_mut().booted();
        }
    }
    assert!((4..=6).contains(&resets), "{resets} resets in 10 s");
}

#[test]
fn power_loss_drops_the_driver_and_tears_the_flash_write() {
    let w = world();
    {
        let mut x = w.borrow_mut();
        x.mcu_en = true;
        x.latch_q = true;
        x.flash.queue(openpatch_sim::flash::Stored::EvtCeiling(64));
        x.advance_to(10_000);
        assert!(x.flash.busy());
        x.cut_power(ResetCause::PowerLoss);
        assert!(!x.vmot_on() && !x.power_on);
        assert_eq!(x.flash.writes_torn, 1);
        assert_eq!(x.flash.read(openpatch_sim::flash::Key::EvtCeiling), None);
    }
    let mut h = SimHal(w.clone());
    assert_eq!(h.motor_step(Pulses(5)).0, 0);
    assert!(h.angle_read().is_none(), "a dead pod does not answer I2C");
}

#[test]
fn a_supply_dip_below_the_pcm_cutoff_resets_the_mcu_and_it_boots_again() {
    let w = world();
    {
        let mut x = w.borrow_mut();
        x.battery.dip_mv = 2000.0;
        x.brownout_until_us = Some(60_000);
    }
    at_us(&w, 100_000);
    assert_eq!(w.borrow().stats.resets.len(), 1);
    assert!(w.borrow().power_on, "supply is back");
    assert!(w.borrow().boot_at_us.is_some());
}

#[test]
fn battery_voltage_follows_state_of_charge_and_load() {
    let w = world();
    let mut h = SimHal(w.clone());
    let full = h.battery_mv();
    assert!((4100..=4200).contains(&full), "{full}");
    w.borrow_mut().battery.soc = 0.1;
    let low = h.battery_mv();
    assert!((3500..3700).contains(&low), "{low}");
    // under motor load the terminal voltage sags by I x R
    let sag = w.borrow().battery.terminal_mv(0.1) - w.borrow().battery.terminal_mv(150.0);
    assert!((sag - 225.0).abs() < 1.0);
    // bench supply is fixed
    let mut p = Params::default();
    p.electrical.bench_supply = true;
    let wb = Rc::new(RefCell::new(World::new(p, 1)));
    assert_eq!(SimHal(wb).battery_mv(), 4000);
}

#[test]
fn motor_torque_collapses_with_the_supply() {
    let mut rng = Rng::new(1);
    let mut p = Params::default();
    p.motor.torque_ripple_pct = 0.0;
    let mk = || {
        let mut pl = Plant::new(p.clone());
        pl.plunger_x = 5.0;
        pl
    };
    assert!(mk().step(1, 200.0, 3.8, &mut rng).moved);
    assert!(!mk().step(1, 200.0, 1.7, &mut rng).moved, "below the driver's minimum supply nothing moves");
    // at 2.1 V the margin is ~20 %: the free-running drive still follows but a heavy load would not
    let mut pl = mk();
    pl.p.fluid.occlusion_factor = 1e6;
    let mut moved_hi = 0;
    for _ in 0..2000 {
        moved_hi += pl.step(1, 200.0, 3.8, &mut rng).moved as u32;
        pl.relax(0.005);
    }
    let mut pl2 = mk();
    pl2.p.fluid.occlusion_factor = 1e6;
    let mut moved_lo = 0;
    for _ in 0..2000 {
        moved_lo += pl2.step(1, 200.0, 2.4, &mut rng).moved as u32;
        pl2.relax(0.005);
    }
    assert!(moved_lo < moved_hi, "weak supply must stall earlier: {moved_lo} vs {moved_hi}");
    assert!(pl2.peak_pressure_kpa < pl.peak_pressure_kpa);
}

#[test]
fn the_current_sense_reads_higher_under_load_and_can_be_absent() {
    let mut rng = Rng::new(2);
    let mut p = Params::default();
    p.motor.torque_ripple_pct = 0.0;
    p.motor.i_noise_ma = 0.0;
    let mut pl = Plant::new(p.clone());
    pl.plunger_x = 5.0;
    let free = pl.step(1, 200.0, 3.8, &mut rng).current_ma;
    pl.p.fluid.occlusion_factor = 1e6;
    let mut hi = 0.0f64;
    for _ in 0..1500 {
        hi = hi.max(pl.step(1, 200.0, 3.8, &mut rng).current_ma);
        pl.relax(0.005);
    }
    use openpatch_core::limits::{MOTOR_FREE_CURRENT_MA, OCCLUSION_CURRENT_MA};
    assert!(free < MOTOR_FREE_CURRENT_MA as f64 + 15.0, "{free}");
    assert!(free < OCCLUSION_CURRENT_MA as f64 - 50.0, "a free-running stage must be far below the occlusion threshold: {free}");
    assert!(hi > OCCLUSION_CURRENT_MA as f64, "a stalled rotor must exceed the occlusion threshold: {hi}");
    // absent sensor -> None for the core
    p.motor.current_sense = false;
    let w = Rc::new(RefCell::new(World::new(p, 1)));
    assert_eq!(SimHal(w).motor_current_peak_ma(), None);
}

#[test]
fn angle_noise_is_about_the_configured_value_and_the_unwrap_tracks_a_burst() {
    let w = world();
    w.borrow_mut().plant.plunger_x = 10.0; // somewhere mid-stroke, so the screw can turn
    let mut h = SimHal(w.clone());
    // noise at rest: 0.1 deg = 1.14 counts rms (+ quantisation)
    let mut v = Vec::new();
    let a0 = h.angle_read().unwrap().0;
    for _ in 0..4000 {
        v.push((h.angle_read().unwrap().0 - a0) as f64);
    }
    let m = v.iter().sum::<f64>() / v.len() as f64;
    let sd = (v.iter().map(|x| (x - m).powi(2)).sum::<f64>() / v.len() as f64).sqrt();
    assert!(sd > 0.6 && sd < 3.0, "sd {sd} counts");
    // a burst of 800 steps = 1.89 turns: the unwrapped angle follows within the INL + noise
    h.motor_enable(true);
    let before = h.angle_read().unwrap().0;
    for _ in 0..8 {
        h.watchdog_kick(); // bursts are <= 128 steps in the firmware; the TPL5010 is serviced between them
        h.motor_step(Pulses(100));
    }
    let after = h.angle_read().unwrap().0;
    let want = 800.0 / w.borrow().params.steps_per_screw_turn() * 4096.0; // 661.25 steps per turn (16:20)
    assert!(((after - before) as f64 - want).abs() < 30.0, "moved {} want {want}", after - before);
    // reverse with the fill needle in the septum (without it the closed reservoir would pull a vacuum)
    w.borrow_mut().plant.fill_needle = true;
    for _ in 0..2 {
        h.watchdog_kick();
        h.motor_step_reverse(Pulses(400));
    }
    let back = h.angle_read().unwrap().0;
    assert!((after - back) as f64 > want - 150.0, "backlash accounts for a few counts only");
}

#[test]
fn a_weak_magnet_is_noisier_and_a_missing_one_reads_garbage() {
    let spread = |strength: f64| {
        let w = world();
        w.borrow_mut().magnet_strength = strength;
        let mut h = SimHal(w);
        let a0 = h.angle_read().unwrap().0;
        let v: Vec<f64> = (0..2000).map(|_| (h.angle_read().unwrap().0 - a0) as f64).collect();
        let m = v.iter().sum::<f64>() / v.len() as f64;
        (v.iter().map(|x| (x - m).powi(2)).sum::<f64>() / v.len() as f64).sqrt()
    };
    let (good, weak, gone) = (spread(1.0), spread(0.1), spread(0.0));
    assert!(weak > 3.0 * good, "{weak} vs {good}");
    assert!(gone > 100.0, "garbage must be wild: {gone}");
}

#[test]
fn charger_dock_and_buzzer_pass_through_the_hal() {
    let w = world();
    let mut h = SimHal(w.clone());
    assert!(h.docked() && !h.charger_present());
    w.borrow_mut().docked_phys = false;
    w.borrow_mut().charger = true;
    assert!(!h.docked() && h.charger_present());
    h.buzzer(Buzzer::Alarm);
    assert_eq!(w.borrow().buzzer, Buzzer::Alarm);
    assert_eq!(w.borrow().buzzer_log.len(), 1);
}
