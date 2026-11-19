//! FINDINGS F1..F6 of the virtual pod, FIXED. Each test states the behaviour the safety concept asks for; they were
//! `#[ignore]`d while the findings were open and are regression tests now. REPORT.md ("Findings") explains each one
//! and the fix.

mod common;
use common::*;
use openpatch_sim::scenario::Action;

/// F1 (docs/02-safety.md H3): "brown-out reset -> the pod starts SUSPENDED and announces itself with
/// an alarm instead of silently continuing". Before the fix the core booted suspended but raised no alarm: no
/// `ALARM` status flag, no buzzer pattern. Now an active pod that restarts unplanned raises `7-74-002` at FAULT
/// severity (core `alarm_unplanned_reset`).
#[test]
fn unplanned_reset_of_an_active_pod_announces_itself() {
    let o = run("brownout_bolus");
    let b = &o.dev.boot_reports[1];
    assert!(b.pod_restored.is_some_and(|p| p.active), "precondition: the pod was active before the reset");
    let buzzer_alarm = o.dev.world.borrow().buzzer_log.iter().any(|(t, p)| *t >= b.t_us && *p == openpatch_core::Buzzer::Alarm);
    assert!(b.alarm_flag || buzzer_alarm, "booted suspended but silent: flags {:#x}", b.status_flags);
    assert!(b.alarm_flag && buzzer_alarm, "both the ALARM flag and the buzzer: flags {:#x}", b.status_flags);
}

/// F2: the basal schedule lives in RAM only (`restore_pod` restores pair / role / active / wear, not
/// the schedule). After a reset the app's `Resume` succeeds (result 0), the pod reports "not
/// suspended" and delivers 0 U/h without any alarm until the schedule is sent again. Either persist
/// the schedule, or refuse `Resume` while `HAS_SCHEDULE` is clear.
#[test]
fn resume_after_a_reset_without_a_schedule_is_refused_or_delivers() {
    let mut sc = scenario("flash_power_loss");
    sc.events.retain(|e| !matches!(e.action, Action::SetBasal { .. })); // the app only sends Resume
    let o = run_sc(sc);
    let resume_refused = o.verdict.notes.iter().any(|n| n.contains("resume -> result"));
    let delivering = needle_mu(&o, 3500.0) > needle_mu(&o, 1800.0) + 400.0;
    assert!(resume_refused || delivering, "Resume accepted, 0 mU delivered afterwards, no fault: notes {:?}", o.verdict.notes);
}

/// F3 (platform persistence policy, openpatch-bench `safety.rs`; modelled in the simulator): the
/// reservoir snapshot stores `consumed + 64 steps`. At boot the restored value becomes the new
/// baseline and the policy immediately rewrites `consumed + 64` again, so EVERY reboot makes the
/// model 64 steps (0.39 U) emptier. In a reboot loop (brown-out chatter, dead DONE line) the model
/// drains by 0.39 U per reset until RESERVOIR_EMPTY.
#[test]
fn reservoir_margin_does_not_accumulate_across_reboots() {
    let o = run("watchdog_kick_stuck");
    let boots = &o.dev.boot_reports;
    assert!(boots.len() > 20);
    let first = boots[1].model_minus_actual_mu_after.unwrap();
    let last = boots.last().unwrap().model_minus_actual_mu_after.unwrap();
    assert!(first - last < 500.0, "model drifted {} mU across {} reboots", first - last, boots.len() - 1);
}

/// F4 (core `MAX_PRIME` = 0.524 U vs the drive's lost motion): after a draw reverses the drive, the
/// first ~0.4 U of forward travel only takes up backlash and seal elasticity (REPORT.md "lost
/// motion"). A standard prime of 0.3 U delivers nothing and leaves the connector full of air; the
/// pod then reports "primed". The largest allowed prime is barely above the lost motion.
#[test]
fn a_standard_prime_after_a_draw_purges_the_connector() {
    let o = run("prime");
    let w = o.dev.world.borrow();
    assert!(w.plant.line_air_ul < 0.3, "{} ul of air still in the connector after the prime", w.plant.line_air_ul);
}

/// F5: the draw runs at 600 Hz (derated torque) and reuses the forward occlusion current threshold
/// (140 mA, 3 bursts). A pod with high seal friction, low screw efficiency and low pull-out torque
/// (all inside the Monte Carlo tolerance: ~11 % of the population) cannot finish a refill: the draw
/// "stalls" on motor current although nothing is wrong.
#[test]
fn a_high_friction_pod_can_still_refill() {
    let mut sc = scenario("prime");
    sc.params.drive.seal_static_n = 2.6;
    sc.params.drive.seal_dynamic_n = 1.7;
    sc.params.drive.screw_eff = 0.16;
    sc.params.motor.pullout_gf_cm = 1.5;
    let o = run_sc(sc);
    assert!(o.verdict.setup_ok, "{}", o.verdict.setup_note);
}

/// F6 (spec 7 "Max. delivery per hour (total): 15 U"): the limit is enforced on the COMMANDED
/// volume. At the tolerance corner (+2 % stadium area, +1.5 % lead) the needle sees 3.6 % more:
/// 15.4 U in one hour with the core exactly at its cap.
#[test]
fn the_needle_never_sees_more_than_15_u_in_an_hour() {
    let mut sc = scenario("limits_stress");
    sc.events.clear();
    sc.setup.basal = vec![(0.0, 0.2)];
    sc.duration_s = 9000.0;
    // a warm-up bolus takes up the lost motion of the refill; then 75 minutes later the cap is approached
    let sc = sc
        .at(30.0, Action::Bolus { units: 2.0 })
        .at(4500.0, Action::Bolus { units: 10.0 })
        .at(5100.0, Action::Bolus { units: 4.4 }) // 10.3 + 4.4 would be 14.7 U: over the margin-reduced cap, refused
        .at(5300.0, Action::Bolus { units: 3.9 }) // 10.3 + 3.9 = 14.2 U: accepted, the core is at its cap
        .at(5500.0, Action::Bolus { units: 0.3 });
    let o = run_sc(sc);
    let l = &o.verdict.limits;
    assert!(o.verdict.boluses.iter().any(|b| b.units_cmd == 4.4 && b.result_code == 16), "the 4.4 U bolus must be refused (Hourly)");
    // the cap is 15 U less the 4 % calibration tolerance margin (14 423 mU); the sequence approaches it
    assert!(l.max_rolling_hour_core_mu > 13_900.0 && l.max_rolling_hour_core_mu <= 14_423.0, "precondition: the core is at its cap ({:?})", l);
    assert!(l.max_rolling_hour_actual_mu <= 15_000.0, "needle saw {:.0} mU in an hour", l.max_rolling_hour_actual_mu);
}
