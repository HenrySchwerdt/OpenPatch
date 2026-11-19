//! Calibration of the plant against first principles: each tolerance must move the delivered
//! volume by the amount the geometry says. If these hold, the Monte Carlo distributions mean
//! what REPORT.md says they mean.

mod common;
use common::*;
use openpatch_sim::params::Params;
use openpatch_sim::scenario::{Action, Scenario};

/// Error (%) of a 5 U bolus after a warm-up bolus, for a given plant.
fn bolus_error(p: Params) -> f64 {
    let mut sc = Scenario { name: "physics".into(), seed: 5, duration_s: 900.0, ..Default::default() };
    sc.params = p;
    sc.setup.basal = vec![(0.0, 0.0)];
    sc.setup.fill_u = 30.0;
    let sc = sc.at(30.0, Action::Bolus { units: 2.0 }).at(300.0, Action::Bolus { units: 5.0 });
    let o = run_sc(sc);
    assert!(o.verdict.setup_ok, "{}", o.verdict.setup_note);
    assert!(o.verdict.faults.is_empty(), "{:?}", o.verdict.faults);
    o.verdict.boluses[1].error_pct.expect("completed")
}

#[test]
fn nominal_plant_delivers_what_the_geometry_says() {
    let e = bolus_error(Params::default());
    assert!(e.abs() < 0.7, "{e} %");
}

#[test]
fn reservoir_area_scales_the_dose_one_to_one() {
    let mut p = Params::default();
    p.drive.area_mm2 = 74.6 * 1.02;
    let e = bolus_error(p);
    assert!((e - 2.0).abs() < 0.7, "{e} %");
}

#[test]
fn lead_error_scales_the_dose_one_to_one() {
    let mut p = Params::default();
    p.drive.pitch_error_pct = -1.5;
    let e = bolus_error(p);
    assert!((e + 1.5).abs() < 0.7, "{e} %");
}

#[test]
fn the_firmware_preset_matters_25_percent_in_the_wrong_direction() {
    // 18:18 mechanics vs the 15:12 preset: 0.00494 / 0.00617 = 0.80. The encoder would stop it, so
    // look at the plant alone with the encoder checks made blind (huge noise tolerance is not
    // available), hence just the first 0.9 U of a bolus here.
    let mut sc = scenario("gear_preset_mismatch");
    sc.events.clear();
    sc.setup.basal = vec![(0.0, 0.0)];
    let sc = sc.at(30.0, Action::Bolus { units: 0.9 });
    let o = run_sc(sc);
    let b = &o.verdict.boluses[0];
    // (the encoder may stop the bolus early: only what flowed counts)
    // lost motion and the 0.80 ratio: the bolus window delivers well under 0.9 U
    assert!(b.actual_window_mu < 0.9 * 1000.0 * 0.85, "{}", b.actual_window_mu);
}

#[test]
fn seal_friction_and_stiffness_change_lost_motion_not_the_steady_state_dose() {
    let soft = {
        let mut p = Params::default();
        p.drive.axial_stiffness_n_mm = 15.0;
        p.drive.seal_static_n = 2.0;
        p.drive.seal_dynamic_n = 1.0;
        bolus_error(p)
    };
    let stiff = {
        let mut p = Params::default();
        p.drive.axial_stiffness_n_mm = 400.0;
        bolus_error(p)
    };
    // after the warm-up both are in steady state: the dose is the same within the step quantisation
    assert!(soft.abs() < 1.5 && stiff.abs() < 1.5, "soft {soft} stiff {stiff}");
}

#[test]
fn lost_motion_after_a_draw_scales_with_elasticity() {
    // first 1 U after the refill + prime: the shortfall grows with a softer plunger drive
    let first = |k: f64| {
        let mut p = Params::default();
        p.drive.axial_stiffness_n_mm = k;
        let mut sc = Scenario { name: "lost-motion".into(), seed: 6, duration_s: 400.0, ..Default::default() };
        sc.params = p;
        sc.setup.basal = vec![(0.0, 0.0)];
        let o = run_sc(sc.at(30.0, Action::Bolus { units: 1.0 }));
        o.verdict.boluses[0].actual_bolus_mu.unwrap() - 1000.0
    };
    let (soft, mid, stiff) = (first(15.0), first(40.0), first(400.0));
    assert!(soft < mid && mid < stiff, "{soft} {mid} {stiff}");
    assert!(stiff > -150.0, "a stiff drive only loses the backlash: {stiff}");
    assert!(soft < -300.0, "{soft}");
}

#[test]
fn the_duckbill_cracking_pressure_does_not_change_the_steady_dose() {
    let lo = {
        let mut p = Params::default();
        p.fluid.crack_kpa = 1.0;
        bolus_error(p)
    };
    let hi = {
        let mut p = Params::default();
        p.fluid.crack_kpa = 5.0;
        bolus_error(p)
    };
    // (the stored volume of a 4 kPa higher cracking pressure is ~0.4 % of a 5 U dose, plus the stick-slip phase)
    assert!((lo - hi).abs() < 1.6, "{lo} vs {hi}");
}

#[test]
fn a_bubble_in_the_reservoir_delays_but_does_not_change_the_settled_dose() {
    let e = {
        let mut p = Params::default();
        p.fluid.bubble_ul = 15.0;
        bolus_error(p)
    };
    assert!(e.abs() < 1.5, "{e} %");
}

#[test]
fn volume_is_conserved_over_a_whole_refill_and_delivery_cycle() {
    // water in the reservoir + water out through the needle = what was drawn in
    let o = run("refill_draw");
    let w = o.dev.world.borrow();
    let balance = w.plant.drawn_ul; // the setup draw and the mid-life draw
    let accounted = w.plant.liquid_ul + w.plant.out_ul;
    assert!((balance - accounted).abs() < 0.5, "drawn {balance} ul vs reservoir + needle {accounted} ul");
}
