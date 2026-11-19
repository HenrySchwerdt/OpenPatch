//! Every scenario is a test. Acceptance criteria come from `spec/design-parameters.md` section 7 and
//! `docs/02-safety.md`. Plant parameters are the defaults of `params.rs` (spec values or marked
//! assumptions, see REPORT.md); a failing test means the core + platform logic no longer meets the
//! criterion on that plant.
//!
//! Real core bugs found by the simulator are NOT here: they are `#[ignore]`d tests in
//! `tests/findings.rs`, described in REPORT.md under "Findings for the core owner".

mod common;
use common::*;
use openpatch_core::faults::Faults;
use openpatch_core::EventType;
use openpatch_sim::scenario::Action;

// ---- 48 h wear -----------------------------------------------------------------------------------

#[test]
fn wear_48h_runs_clean_inside_all_limits() {
    let o = run("wear_48h");
    let v = &o.verdict;
    assert!(v.faults.is_empty(), "faults: {:?}", v.faults);
    assert!(v.resets.is_empty());
    assert!(v.limits.core_within_limits && v.limits.actual_within_limits, "{:?}", v.limits);
    assert!(!v.interlock.violated);
    assert_eq!(v.boluses.iter().filter(|b| b.accepted).count(), 11, "notes {:?}", v.notes);
    assert!(v.notes.is_empty(), "{:?}", v.notes);
}

#[test]
fn wear_48h_delivery_matches_command() {
    let o = run("wear_48h");
    let v = &o.verdict;
    // programmed vs what the core booked: exact rational accounting, quantisation only
    let sched = v.scheduled_mu as f64;
    assert!((v.core_delivered_mu as f64 - sched).abs() / sched < 0.002, "core {} sched {}", v.core_delivered_mu, sched);
    // what the needle saw vs what the core booked: plant tolerances + the refill lost motion
    assert!(v.actual_vs_core_pct.unwrap().abs() < 2.0, "{:?}", v.actual_vs_core_pct);
    // every bolus >= 1 U within +-5 % (spec bench target)
    for b in v.boluses.iter().filter(|b| b.units_cmd >= 1.0) {
        let e = b.error_pct.expect("completed");
        assert!(e.abs() <= 5.0, "bolus {} U at {} s: {e:.1} %", b.units_cmd, b.t_s);
    }
    // hourly: after the first hour (refill lost motion) every hour within 6 % of the programme
    for h in v.hourly.iter().filter(|h| h.hour >= 2) {
        let e = h.actual_vs_scheduled_pct.unwrap();
        // at 0.4 U/h an hour is ~100 steps of 3.9 mU: one stick-slip release of the seal (a few tens of mU) is several
        // percent, so slow hours are bounded in mU instead
        let err_mu = e / 100.0 * h.scheduled_mu as f64;
        if h.scheduled_mu < 500 {
            assert!(err_mu.abs() <= 45.0, "hour {}: {err_mu:.0} mU ({e:.1} %)", h.hour);
        } else {
            assert!(e.abs() <= 6.0, "hour {}: {e:.1} %", h.hour);
        }
    }
}

#[test]
fn wear_48h_temp_basals_and_profile_are_followed() {
    let o = run("wear_48h");
    // hourly programme: 0.8 U/h from 08:00 (hour 1-6 incl. boluses are separate), temp 0.4 U/h at 15:00 for 2 h
    let h = &o.verdict.hourly;
    // hour 16 and 17 (t = 54000 .. 61200 s) run the 0.4 U/h temp basal
    assert!((h[15].scheduled_mu as i64 - 400).abs() <= 5, "{:?}", h[15]);
    assert!((h[16].scheduled_mu as i64 - 400).abs() <= 5, "{:?}", h[16]);
    // day 2 temp 1.8 U/h at hour 30/31 (t = 108000)
    assert!((h[30].scheduled_mu as i64 - 1800).abs() <= 8, "{:?}", h[30]);
    assert!((h[31].scheduled_mu as i64 - 1800).abs() <= 8, "{:?}", h[31]);
}

#[test]
fn wear_48h_wear_warning_at_44_h_and_battery_survives() {
    let o = run("wear_48h");
    assert_eq!(log_count(&o, EventType::WearWarning), 1);
    assert_eq!(log_count(&o, EventType::WearExpired), 0);
    assert!(o.verdict.battery_end_mv > 3700.0, "battery {}", o.verdict.battery_end_mv);
    // the pod's reservoir model stays within 1 U of the real fluid after 48 h
    let d = (o.verdict.reservoir_end_model_mu as f64 - o.verdict.reservoir_end_actual_mu).abs();
    assert!(d < 1000.0, "model/actual differ by {d} mU");
}

// ---- refill / prime ---------------------------------------------------------------------------------

#[test]
fn refill_draw_delivers_requested_volume_through_the_reverse_interlock_path() {
    let o = run("refill_draw");
    let v = &o.verdict;
    assert_eq!(v.draws.len(), 1);
    let d = &v.draws[0];
    assert_eq!(d.core_state, openpatch_proto::draw::DONE);
    assert!((d.core_drawn_mu as f64 - 50_000.0).abs() < 500.0, "core says {}", d.core_drawn_mu);
    // the vial really gave 50 U less the lost motion of the first reversal (socket play 0.30 mm = 2.24 U, nut play, seal
    // elasticity): the core books the travel, the post-draw take-up corrects its reservoir model afterwards
    assert!(d.core_drawn_mu as f64 - d.actual_drawn_mu > 1_500.0 && d.core_drawn_mu as f64 - d.actual_drawn_mu < 3_500.0, "core {} actual {}", d.core_drawn_mu, d.actual_drawn_mu);
    // DIR_REVERSE lets VMOT come up undocked: no burst was refused, and nothing moved forward undocked
    assert_eq!(v.interlock.bursts_blocked_total, 0);
    assert!(!v.interlock.violated);
    assert!(v.faults.is_empty(), "{:?}", v.faults);
    // the pod's model of the reservoir after the draw is within 1 U of reality and not above it by more than that
    let d = v.reservoir_end_model_mu as f64 - v.reservoir_end_actual_mu;
    assert!(d.abs() < 1000.0, "model - actual = {d} mU");
}

#[test]
fn refill_draw_then_resume_is_refused_until_primed() {
    // no prime between the draw and the resume
    let sc = scenario("refill_draw");
    let mut sc = sc;
    sc.events.retain(|e| !matches!(e.action, Action::Prime { .. }));
    let o = run_sc(sc);
    assert!(o.verdict.notes.iter().any(|n| n.contains("resume -> result 26")), "notes {:?}", o.verdict.notes);
    assert_eq!(needle_mu(&o, 7000.0), needle_mu(&o, 2100.0), "nothing may be delivered while unprimed");
}

#[test]
fn draw_stalls_at_the_rear_end_stop_and_reports_what_was_drawn() {
    let o = run("draw_endstop");
    let d = &o.verdict.draws[0];
    assert_eq!(d.core_state, openpatch_proto::draw::STALLED);
    // 30 U fit behind the plunger, the pod was asked for 50 U
    assert!((d.actual_drawn_mu - 30_000.0).abs() < 1000.0, "actual {}", d.actual_drawn_mu);
    // the core books the travel including the 0.30 mm lost motion of the reversal (2.24 U); the take-up corrects it
    let over = d.core_drawn_mu as f64 - d.actual_drawn_mu;
    assert!(over > 0.0 && over < 3_000.0, "core {} actual {}", d.core_drawn_mu, d.actual_drawn_mu);
    assert!(!o.verdict.interlock.violated);
}

#[test]
fn a_prime_after_a_draw_takes_up_the_lost_motion_first_and_purges_the_line() {
    // Plant fact (REPORT.md, "lost motion"): after the draw reversed the drive, the first ~0.4 U of forward travel only
    // winds up backlash and seal elasticity. The core now runs a take-up (limits::TAKEUP_UM_AFTER_REVERSAL) before the first
    // prime, so the standard 0.3 U prime reaches the connector. The take-up is not delivery: the engine books nothing.
    let o = run("prime");
    let w = o.dev.world.borrow();
    assert!(w.plant.line_air_ul < 0.3, "line air {} ul", w.plant.line_air_ul);
    assert!(w.plant.out_ul > 0.5, "the prime pushed water through the needle: {} ul", w.plant.out_ul);
    // take-up and prime are not delivery: the core booked exactly the (basal) schedule, not the 0.9 U of forward travel
    let last = o.rows.last().unwrap();
    assert!(last.core_delivered_mu as f64 <= last.scheduled_mu as f64 + 15.0, "core {} scheduled {}", last.core_delivered_mu, last.scheduled_mu);
}

#[test]
fn a_larger_prime_series_purges_the_line() {
    let mut sc = scenario("prime");
    sc.setup.resume = false;
    sc.setup.prime_u = 0.5;
    sc = sc.at(5.0, Action::Prime { units: 0.5 }).at(15.0, Action::Prime { units: 0.5 });
    let o = run_sc(sc);
    let w = o.dev.world.borrow();
    assert!(w.plant.line_air_ul < 0.1, "line air {} ul", w.plant.line_air_ul);
    assert!(w.plant.out_ul > 5.0, "needle out {} ul", w.plant.out_ul);
}

// ---- occlusion ----------------------------------------------------------------------------------------

fn assert_occlusion_ok(o: &openpatch_sim::runner::RunOutput, max_latency_s: f64) {
    let d = det(&o.verdict, "Occlude");
    assert!(d.detected_at_s.is_some(), "occlusion never detected");
    assert!(d.fault_names.iter().any(|n| n == "OCCLUSION" || n == "ENCODER_DEVIATION"), "{:?}", d.fault_names);
    assert!(d.latency_s.unwrap() <= max_latency_s, "latency {} s", d.latency_s.unwrap());
    // spec 7: alarm at <= 2 U undelivered
    let u = d.undelivered_at_alarm_mu.unwrap();
    assert!(u <= 2000.0, "undelivered at the alarm: {u} mU");
    // after the alarm the pump does not push on: the core booked nothing more
    let t = d.detected_at_s.unwrap();
    assert_eq!(
        row_at(o, t + 120.0).core_delivered_mu,
        o.rows.last().unwrap().core_delivered_mu,
        "the core kept delivering after the alarm"
    );
    // the pressure stays far below what the motor could build
    assert!(o.verdict.peak_pressure_kpa < 120.0, "{}", o.verdict.peak_pressure_kpa);
}

#[test]
fn occlusion_during_basal_alarms_before_2_u_are_lost() {
    let o = run("occlusion_basal");
    assert_occlusion_ok(&o, 2.0 * 3600.0);
}

#[test]
fn occlusion_during_high_basal_alarms_before_2_u_are_lost() {
    let o = run("occlusion_basal_high");
    assert_occlusion_ok(&o, 3600.0);
}

#[test]
fn occlusion_during_bolus_alarms_within_two_minutes() {
    let o = run("occlusion_bolus");
    assert_occlusion_ok(&o, 120.0);
}

#[test]
fn occlusion_with_a_20_ul_bubble_still_alarms_before_2_u() {
    let o = run("occlusion_bubble");
    assert_occlusion_ok(&o, 2.0 * 3600.0);
    // the bubble costs water: more is soaked up than without one
    let plain = run("occlusion_basal");
    let (u_b, u_p) = (det(&o.verdict, "Occlude").undelivered_at_alarm_mu.unwrap(), det(&plain.verdict, "Occlude").undelivered_at_alarm_mu.unwrap());
    assert!(u_b > 0.5 * u_p, "bubble {u_b} plain {u_p}"); // (basal rates differ; only a sanity bound)
}

#[test]
fn occlusion_does_not_drive_the_motor_into_a_stall_before_the_alarm() {
    // the current-rise criterion catches it with the rotor still following (no lost steps)
    let o = run("occlusion_basal");
    assert_eq!(o.verdict.lost_steps, 0);
}

// ---- dock / interlock ---------------------------------------------------------------------------------------

#[test]
fn dock_loss_mid_bolus_stops_delivery_and_never_catches_up() {
    let o = run("dock_loss_mid_bolus");
    let v = &o.verdict;
    let b = &v.boluses[0];
    assert!(b.accepted && !b.completed);
    // within one tick (1 s) of the undock the needle goes quiet
    let quiet0 = needle_mu(&o, 662.0);
    let quiet1 = needle_mu(&o, 895.0);
    assert!(quiet1 - quiet0 < 30.0, "{} mU flowed while undocked", quiet1 - quiet0);
    // about 60 s of the bolus went out before the undock (1.5 U/min), the rest was cancelled, not queued
    assert!(b.actual_window_mu > 900.0 && b.actual_window_mu < 1800.0, "{}", b.actual_window_mu);
    assert!(needle_mu(&o, 1700.0) - quiet1 < 400.0, "the remainder must not be delivered after re-docking");
    assert_eq!(log_count(&o, EventType::BolusCancel), 1);
    assert!(!v.interlock.violated);
    assert!(v.faults.is_empty());
}

#[test]
fn forced_forward_pulses_undocked_are_stopped_by_the_hardware_interlock() {
    let o = run("undocked_firmware_bug");
    let i = &o.verdict.interlock;
    assert_eq!(i.forward_steps_moved_undocked, 0);
    assert_eq!(i.forward_pulses_issued_undocked, 0);
    assert!(i.bursts_blocked_forward_undocked >= 1, "the interlock must have refused the burst");
    assert!(!i.violated);
    assert!(needle_mu(&o, 500.0) - needle_mu(&o, 100.0) < 10.0);
}

#[test]
fn the_dock_hall_is_a_single_point_of_failure() {
    // Design observation, not a pass criterion of the pod: the core AND the interlock gate read the
    // same hall signal. If it sticks at DOCKED the pod delivers while undocked. The simulator detects it.
    let o = run("hall_stuck_docked");
    let v = &o.verdict;
    assert!(v.interlock.hall_forced);
    assert!(v.interlock.violated, "forward motion undocked expected with a stuck hall");
    assert!(v.interlock.forward_steps_moved_undocked > 100);
    assert!(v.passed, "a forced hall is excluded from the interlock pass criterion");
}

// ---- sensors ----------------------------------------------------------------------------------------------

#[test]
fn magnet_loss_during_a_bolus_is_detected_within_the_one_unit_window() {
    // The design bound is the spec 7 window, not 10 s: the per-revolution check completes once per 661 steps (100 s at the
    // bolus rate) and the 10 % window check every 1 U (40 s at 1.5 U/min). The earlier "within 10 s" held only because the
    // phase of the revolution counter after the setup prime happened to be right at the injection (1 s for every seed);
    // the longer post-draw take-up moves the phase (5 to 33 s over seeds 51 to 56).
    let o = run("magnet_falls_off");
    let d = det(&o.verdict, "Magnet");
    assert!(d.latency_s.expect("detected") <= 45.0, "latency {:?}", d.latency_s);
    assert!(d.fault_names.iter().any(|n| n == "ENCODER_DEVIATION" || n == "OCCLUSION" || n == "INTERNAL"));
    // after the alarm no more water is booked
    let t = d.detected_at_s.unwrap();
    assert_eq!(row_at(&o, t + 60.0).core_delivered_mu, o.rows.last().unwrap().core_delivered_mu);
    // unverified delivery between the loss and the alarm stays small
    let unverified = needle_mu(&o, t + 1.0) - needle_mu(&o, 660.0);
    assert!(unverified < 1_100.0, "{unverified} mU delivered without verification (spec 7: 1 U window)");
}

#[test]
fn magnet_loss_during_basal_is_detected_before_1_u_goes_unverified() {
    let o = run("magnet_falls_off_basal");
    let d = det(&o.verdict, "Magnet");
    let t = d.detected_at_s.expect("detected");
    let unverified = needle_mu(&o, t) - needle_mu(&o, 1800.0);
    assert!(unverified <= 1000.0, "{unverified} mU delivered unverified (latency {} s)", d.latency_s.unwrap());
    assert!(has_fault(&o.verdict, "ENCODER_DEVIATION") || has_fault(&o.verdict, "OCCLUSION"));
}

#[test]
fn a_silent_angle_sensor_stops_delivery_within_one_tick() {
    let o = run("angle_sensor_nack");
    let d = det(&o.verdict, "AngleNack");
    assert!(d.latency_s.unwrap() <= 1.5, "{:?}", d.latency_s);
    assert!(d.fault_names.contains(&"INTERNAL".to_string()));
    assert!(needle_mu(&o, 1100.0) - needle_mu(&o, 305.0) < 10.0);
}

// ---- motor / gear faults ---------------------------------------------------------------------------------------

#[test]
fn an_open_motor_phase_trips_the_encoder_check_before_1_5_u_are_lost() {
    let o = run("motor_phase_open");
    let d = det(&o.verdict, "PhaseOpen");
    // the open phase loses steps AND loads the motor: the current rise (stored-volume criterion) or the encoder catches it
    assert!(d.fault_names.iter().any(|n| n == "ENCODER_DEVIATION" || n == "OCCLUSION"), "{:?}", d.fault_names);
    assert!(d.undelivered_at_alarm_mu.unwrap() <= 1500.0, "{:?}", d.undelivered_at_alarm_mu);
    assert!(o.verdict.lost_steps > 10, "the plant must really lose steps");
    let t = d.detected_at_s.unwrap();
    assert_eq!(row_at(&o, t + 60.0).core_delivered_mu, o.rows.last().unwrap().core_delivered_mu);
}

#[test]
fn a_wrong_gear_preset_is_caught_by_the_encoder_within_the_first_bolus() {
    // 18:18 fitted, 16:20 flashed: 25 % OVER-delivery on the needle (0.00494 vs 0.003949 U/step), caught by
    // encoder deviation at the end of the first 1 U window
    // Since the post-draw take-up covers the lost motion of the mechanics (623 steps, nearly one screw turn) the per-revolution
    // check sees the wrong ratio DURING THE SETUP PRIME, before anything is delivered (refused with Fault = 4); the run itself
    // never starts. Either way the encoder catches it.
    let o = run_sc(scenario("gear_preset_mismatch"));
    assert!(caught_by_encoder(&o), "setup {:?} faults {:?}", o.verdict.setup_note, o.verdict.faults);
    if let Some(f) = o.verdict.faults.first() {
        assert!(f.t_s < 400.0, "alarm after {} s", f.t_s);
    }
    // the 1 U window plus 25 % plus the steps of one more tick: well under 1.6 U left the needle
    assert!(o.verdict.actual_out_mu < 1600.0, "{} mU were delivered with the wrong preset", o.verdict.actual_out_mu);
}

/// The encoder caught the wrong ratio: a latched ENCODER_DEVIATION in the run, or the setup prime (its take-up is nearly a
/// full screw turn) refused with Fault before any delivery.
fn caught_by_encoder(o: &openpatch_sim::runner::RunOutput) -> bool {
    has_fault(&o.verdict, "ENCODER_DEVIATION") || (!o.verdict.setup_ok && o.verdict.setup_note.contains("Prime refused: 4"))
}

fn gear_error_run(ratio_error_pct: f64) -> openpatch_sim::runner::RunOutput {
    // actual gearhead ratio = nominal * (1 + e): the screw turns 1/(1+e) of what the firmware expects
    let mut sc = scenario("gear_preset_mismatch");
    sc.params.drive.z_motor = 16.0;
    sc.params.drive.z_screw = 20.0; // the mechanics match the flashed preset, only the gearhead ratio is off
    sc.params.motor.gearhead_ratio = 26.45 * (1.0 + ratio_error_pct / 100.0);
    sc.setup.basal = vec![(0.0, 0.0)];
    sc.events.clear();
    sc = sc.at(100.0, Action::Bolus { units: 8.0 });
    sc.duration_s = 900.0;
    run_sc(sc)
}

#[test]
fn encoder_threshold_1_percent_error_is_tolerated() {
    // (2 % already trips the 3 % per-turn check right after a draw: the backlash taken up by the first
    // forward turn costs another ~1 %, see REPORT.md "margins")
    let o = gear_error_run(1.0);
    assert!(o.verdict.faults.is_empty(), "{:?}", o.verdict.faults);
    assert!(o.verdict.core_delivered_mu >= 7900);
}

#[test]
fn encoder_threshold_6_percent_error_is_caught_by_the_per_revolution_check() {
    // deficit 1 - 1/1.0638 = 6 %: below the 10 % window check, above the 3 % per-turn check
    let o = gear_error_run(6.4);
    assert!(caught_by_encoder(&o));
    let commanded = o.verdict.core_delivered_mu as f64;
    assert!(commanded < 4000.0, "caught only after {commanded} mU");
}

#[test]
fn encoder_threshold_over_10_percent_over_1_u_stops_delivery_with_alarm() {
    // spec 7: encoder deviation > 10 % over 1 U -> delivery stop + alarm (12 % deficit: ratio x 1.136)
    let o = gear_error_run(13.6);
    assert!(caught_by_encoder(&o));
    let commanded = o.verdict.core_delivered_mu as f64;
    assert!(commanded < 1800.0, "caught only after {commanded} mU (window is 1 U)");
    // the supervisor really stopped the motor
    assert_eq!(row_at(&o, 300.0).core_delivered_mu, o.rows.last().unwrap().core_delivered_mu);
}

// ---- watchdog, supply, flash --------------------------------------------------------------------------------------

#[test]
fn a_runaway_after_a_firmware_hang_is_cut_by_the_watchdog_within_its_period() {
    let o = run("hang_runaway");
    let v = &o.verdict;
    let d = det(v, "Hang");
    assert!(d.detected_by_reset);
    assert!(d.latency_s.unwrap() <= 2.1, "cut after {} s", d.latency_s.unwrap());
    assert_eq!(v.resets.len(), 1);
    assert_eq!(v.resets[0].cause, "Watchdog");
    // TPL5010: <= period + 5 ms after the last DONE
    assert!(v.wdt_cut_latency_ms[0] <= 2010.0, "{:?}", v.wdt_cut_latency_ms);
    // worst-case runaway bound: period x step rate = 400 steps = 2.5 U (documented hardware bound)
    assert!(v.forward_steps_during_wdt_window <= 410, "{} steps", v.forward_steps_during_wdt_window);
    let overdelivery = v.actual_out_mu - v.core_delivered_mu as f64;
    assert!(overdelivery < 2600.0, "runaway over-delivery {overdelivery} mU");
    // nothing moves after the cut and the pod boots suspended
    let t = v.resets[0].t_s;
    assert_eq!(needle_mu(&o, t + 5.0), needle_mu(&o, 590.0));
    assert!(v.boots.last().unwrap().suspended);
}

#[test]
fn a_plain_firmware_hang_resets_and_the_pod_comes_back_suspended() {
    let o = run("hang_soft");
    let v = &o.verdict;
    assert_eq!(v.resets.len(), 1);
    assert!(v.boots.len() == 2 && v.boots[1].suspended);
    assert_eq!(v.forward_steps_during_wdt_window, 0);
    let t = v.resets[0].t_s;
    assert_eq!(needle_mu(&o, 800.0), needle_mu(&o, t + 1.0), "nothing may be delivered after the reset");
}

#[test]
fn a_dead_done_line_makes_the_pod_reboot_loop_without_ever_delivering() {
    let o = run("watchdog_kick_stuck");
    let v = &o.verdict;
    assert!(v.resets.len() > 50, "{} resets", v.resets.len());
    assert!(v.boots.iter().skip(1).all(|b| b.suspended));
    let t = v.resets[0].t_s;
    assert_eq!(needle_mu(&o, 500.0), needle_mu(&o, t + 0.5), "delivery must stop at the first reset");
    assert!(!v.interlock.violated);
}

#[test]
fn a_brownout_mid_bolus_resets_restores_conservatively_and_stays_suspended() {
    let o = run("brownout_bolus");
    let v = &o.verdict;
    assert_eq!(v.resets.len(), 1);
    assert_eq!(v.resets[0].cause, "PowerLoss");
    let b = &o.dev.boot_reports[1];
    assert!(b.suspended);
    // the restored reservoir model can only be LOWER than before the reset (<= 64 steps of margin)
    let (before, after) = (b.model_minus_actual_mu_before.unwrap(), b.model_minus_actual_mu_after.unwrap());
    assert!(after <= before + 6.0, "model went UP across the reset: {before} -> {after}");
    assert!(before - after <= 450.0, "margin larger than expected: {}", before - after);
    // event ids never go backwards over a reset
    assert!(b.evt_start >= b.pre_reset_next_event_id.unwrap());
    // the remaining bolus is not caught up: nothing flows between the reset and the explicit resume
    assert_eq!(needle_mu(&o, 689.0), needle_mu(&o, 641.0));
    // after the app acknowledged the reset alarm and resumed, delivery restarts
    assert!(needle_mu(&o, 1700.0) > needle_mu(&o, 700.0) + 100.0);
}

#[test]
fn battery_critical_stops_delivery_and_low_battery_is_reported() {
    let o = run("battery_depletion");
    let d = det(&o.verdict, "BatteryOcv");
    assert!(d.fault_names.contains(&"BATTERY_CRITICAL".to_string()));
    assert!(d.latency_s.unwrap() <= 2.0);
    assert_eq!(needle_mu(&o, 3500.0), needle_mu(&o, 1205.0));
    // LOW_BATTERY flag (bit 7 of the status flags) between 3.5 V and 3.3 V
    assert!(row_at(&o, 900.0).flags & (1 << 7) != 0, "flags {:#x}", row_at(&o, 900.0).flags);
    assert!(row_at(&o, 300.0).flags & (1 << 7) == 0);
}

#[test]
fn a_power_cut_during_a_flash_write_restores_a_consistent_state() {
    let o = run("flash_power_loss");
    let v = &o.verdict;
    assert_eq!(v.resets.len(), 1);
    let b = &o.dev.boot_reports[1];
    assert!(b.suspended);
    let pod = b.pod_restored.expect("pod record survived (A/B)");
    assert!(pod.active);
    assert!(b.reservoir_restored.is_some());
    let (before, after) = (b.model_minus_actual_mu_before.unwrap(), b.model_minus_actual_mu_after.unwrap());
    assert!(after <= before + 6.0, "model went UP across the reset: {before} -> {after}");
    assert!(b.evt_start >= b.pre_reset_next_event_id.unwrap());
    // nothing flows while suspended (alarm), then the basal restarts after the app acknowledged and resumed
    let t_reset = v.resets[0].t_s;
    assert!(t_reset < 1990.0);
    assert_eq!(needle_mu(&o, 1990.0), needle_mu(&o, t_reset + 5.0));
    assert!(needle_mu(&o, 3500.0) > needle_mu(&o, 2200.0) + 400.0);
    // the only alarm is the announced reset (H3, F1)
    assert!(v.faults.iter().all(|f| f.names == ["INTERNAL"]), "{:?}", v.faults);
}

#[test]
fn a_flash_write_that_destroys_the_old_record_fails_safe() {
    let o = run("flash_power_loss_worst");
    let v = &o.verdict;
    assert_eq!(v.resets.len(), 1);
    let b = &o.dev.boot_reports[1];
    // one record is gone: either the reservoir (model reads empty) or the pod (not paired / released)
    assert!(b.reservoir_restored.is_none() || b.pod_restored.is_none());
    // after the reset the pod never delivers more than it knows it has: no water after the alarm/refusal
    let after_reset = needle_mu(&o, 3500.0) - needle_mu(&o, v.resets[0].t_s + 5.0);
    assert!(after_reset < 50.0, "{after_reset} mU flowed after a state loss");
    assert!(has_fault(v, "RESERVOIR_EMPTY") || v.notes.iter().any(|n| n.contains("result")), "silent: faults {:?} notes {:?}", v.faults, v.notes);
}

// ---- communication loss ----------------------------------------------------------------------------------------------

#[test]
fn a_temp_basal_falls_back_to_the_programme_30_minutes_after_the_last_frame() {
    let o = run("comms_loss_temp");
    // temp basal 3 U/h runs while the phone talks
    assert_eq!(row_at(&o, 1000.0).rate_mu_h, 3000);
    // phone gone at 1200 s; last heartbeat <= 60 s earlier: fallback in [1200+1740, 1200+1800]
    let first_fallback = o.rows.iter().find(|r| r.t_s > 1300.0 && r.rate_mu_h == 1000).expect("fell back").t_s;
    assert!((1200.0 + 1740.0 - 61.0..=1200.0 + 1800.0 + 61.0).contains(&first_fallback), "fallback at {first_fallback} s");
    assert_eq!(row_at(&o, first_fallback - 120.0).rate_mu_h, 3000, "must not fall back earlier");
    assert_eq!(log_count(&o, EventType::TempCommFallback), 1);
    // and the needle follows: 1 U/h in the hour after the fallback
    let a = needle_mu(&o, 3600.0);
    let b = needle_mu(&o, 7200.0);
    assert!(((b - a) - 1000.0).abs() < 60.0, "{} mU in the hour after the fallback", b - a);
}

// ---- limits --------------------------------------------------------------------------------------------------------

#[test]
fn the_core_never_commands_more_than_15_u_in_any_hour_and_refuses_the_excess() {
    let o = run("limits_stress");
    let v = &o.verdict;
    assert!(v.limits.core_within_limits, "{:?}", v.limits);
    assert!(v.limits.max_rolling_hour_core_mu <= 15_000.0);
    assert!(v.limits.max_bolus_accepted_mu <= 10_000);
    // the boluses that would break the hourly limit are refused with Error::Hourly (16)
    assert!(v.boluses.iter().any(|b| b.result_code == 16), "{:?}", v.boluses.iter().map(|b| b.result_code).collect::<Vec<_>>());
    assert!(v.faults.is_empty(), "refusing a command must not alarm: {:?}", v.faults);
}

#[test]
fn bolus_speed_is_1_5_u_per_minute_and_the_backstop_is_never_reached() {
    let o = run("limits_stress");
    let m = o.verdict.limits.max_minute_actual_mu;
    // 1.5 U/min commanded, +2 % area +1.5 % lead on this plant: 1.55 U/min
    assert!(m > 1450.0 && m < 1700.0, "{m} mU per minute at the needle");
    assert!(o.verdict.limits.actual_within_limits || m <= 1700.0 * 1.05);
}

// ---- global properties --------------------------------------------------------------------------------------------

#[test]
fn no_scenario_moves_the_motor_forward_undocked_unless_the_hall_itself_is_broken() {
    for name in openpatch_sim::scenarios::names() {
        if name == "wear_48h" {
            continue; // covered by its own test, keeps this one fast
        }
        let o = run_sc(scenario(name));
        let i = &o.verdict.interlock;
        assert!(!i.violated || i.hall_forced, "{name}: forward motion undocked ({:?})", i);
    }
}

#[test]
fn the_core_never_exceeds_a_limit_in_any_scenario() {
    for name in openpatch_sim::scenarios::names() {
        if name == "wear_48h" {
            continue;
        }
        let o = run_sc(scenario(name));
        assert!(o.verdict.limits.core_within_limits, "{name}: {:?}", o.verdict.limits);
        // the wrong-preset scenario is caught by the encoder during the setup prime (take-up): setup does not complete
        assert!(o.verdict.setup_ok || name == "gear_preset_mismatch", "{name}: {}", o.verdict.setup_note);
    }
}

#[test]
fn runs_are_deterministic_and_sampling_does_not_change_the_physics() {
    let a = run("hang_runaway");
    let b = run("hang_runaway");
    assert_eq!(serde_json::to_string(&a.verdict).unwrap(), serde_json::to_string(&b.verdict).unwrap());
    // logging every 10 s instead of every 60 s must not change a single bit of the plant
    let mut sc = scenario("occlusion_bolus");
    sc.log_interval_s = 10.0;
    let c = run_sc(sc);
    let d = run("occlusion_bolus");
    assert_eq!(c.verdict.actual_out_mu, d.verdict.actual_out_mu);
    assert_eq!(c.verdict.core_delivered_mu, d.verdict.core_delivered_mu);
}

#[test]
fn another_seed_changes_the_noise_not_the_story() {
    let mut sc = scenario("occlusion_basal");
    sc.seed = 99;
    let o = run_sc(sc);
    let d = det(&o.verdict, "Occlude");
    assert!(d.undelivered_at_alarm_mu.unwrap() <= 2000.0);
    assert!(has_fault(&o.verdict, "OCCLUSION"));
    let _ = Faults::NONE;
}

// ---- more safety-concept hazards (docs/02-safety.md) -------------------------------------------------------------------

#[test]
fn h9_a_pod_put_on_the_charger_releases_and_stops_delivering() {
    let mut sc = scenario("prime");
    sc.duration_s = 1200.0;
    sc.setup.basal = vec![(0.0, 2.0)];
    let o = run_sc(sc.at(300.0, Action::Charger { on: true }));
    assert_eq!(log_count(&o, EventType::Release), 1);
    assert_eq!(needle_mu(&o, 1100.0), needle_mu(&o, 305.0), "nothing may flow on the charger");
    let flags = row_at(&o, 900.0).flags;
    assert!(flags & (1 << 10) == 0, "the pod must report itself as not ACTIVE: {flags:#x}");
}

#[test]
fn spec_1b_the_pod_stops_at_52_h_with_a_wear_alarm() {
    let mut sc = scenario("prime");
    sc.setup.basal = vec![(0.0, 0.5)];
    sc.setup.fill_u = 60.0;
    sc.duration_s = 53.0 * 3600.0;
    sc.log_interval_s = 600.0;
    let o = run_sc(sc);
    assert!(has_fault(&o.verdict, "WEAR_EXPIRED"));
    let t = o.verdict.faults.iter().find(|f| f.names.contains(&"WEAR_EXPIRED".to_string())).unwrap().t_s;
    assert!((t - 52.0 * 3600.0).abs() < 130.0, "wear fault at {t} s");
    assert_eq!(needle_mu(&o, 52.0 * 3600.0 + 120.0), needle_mu(&o, 53.0 * 3600.0 - 1.0), "no delivery after the wear alarm");
    assert_eq!(log_count(&o, EventType::WearWarning), 1);
}

#[test]
fn h6_without_the_phone_the_programmed_basal_continues_autonomously() {
    let mut sc = scenario("prime");
    sc.duration_s = 6.0 * 3600.0;
    sc.setup.basal = vec![(0.0, 1.0)];
    sc.log_interval_s = 300.0;
    let o = run_sc(sc.at(600.0, Action::PhoneConnected { on: false }));
    for h in o.verdict.hourly.iter().filter(|h| h.hour >= 2) {
        assert!(h.actual_vs_scheduled_pct.unwrap().abs() < 4.0, "{:?}", h);
    }
    assert!(o.verdict.faults.is_empty());
}
