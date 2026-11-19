//! Monte Carlo sanity: reproducibility and the distributions REPORT.md quotes (small N here, the
//! report uses 1000+). Plant tolerances are the defaults of `montecarlo::Tolerances`.

use openpatch_sim::montecarlo::{run, Experiment, McConfig};

fn cfg(e: Experiment, runs: usize, threads: usize) -> McConfig {
    let mut c = McConfig::new(e, runs, 7);
    c.threads = threads;
    c
}

#[test]
fn the_result_does_not_depend_on_the_thread_count() {
    let a = serde_json::to_string(&run(&cfg(Experiment::Accuracy, 12, 1))).unwrap();
    let b = serde_json::to_string(&run(&cfg(Experiment::Accuracy, 12, 4))).unwrap();
    assert_eq!(a, b);
}

#[test]
fn another_seed_gives_another_population() {
    let a = run(&cfg(Experiment::Accuracy, 8, 2));
    let mut c = cfg(Experiment::Accuracy, 8, 2);
    c.seed = 8;
    let b = run(&c);
    assert_ne!(serde_json::to_string(&a).unwrap(), serde_json::to_string(&b).unwrap());
}

#[test]
fn delivery_accuracy_distribution() {
    let r = run(&cfg(Experiment::Accuracy, 150, 4));
    let a = r.accuracy.as_ref().unwrap();
    let c: Vec<_> = a.classes.iter().collect();
    assert_eq!(c.len(), 3);
    // 10 U: step quantisation vanishes; only tolerances remain
    assert!(c[2].error_pct.sd < 2.0 && c[2].within_5pct >= 0.99, "10 U: {:?}", c[2]);
    // 1 U: spec bench target +-5 %: most pods meet it, the stick-slip tail is visible
    assert!(c[1].error_pct.mean.abs() < 1.0, "1 U mean {}", c[1].error_pct.mean);
    assert!(c[1].within_5pct >= 0.85, "1 U within 5 %: {}", c[1].within_5pct);
    assert!(c[1].within_10pct >= 0.97, "1 U within 10 %: {}", c[1].within_10pct);
    // 0.05 U single doses are quantised (+-1 step = +-12 %) and lumped by stiction, but unbiased
    assert!(c[0].error_pct.mean.abs() < 5.0, "0.05 U mean {}", c[0].error_pct.mean);
    assert!(c[0].within_20pct < 0.6, "single 0.05 U doses are NOT accurate to 20 %: {}", c[0].within_20pct);
    // the series of ten sums out: cumulative error well under one bolus
    assert!(a.series_005_cumulative_mu.mean.abs() < 15.0 && a.series_005_cumulative_mu.sd < 60.0, "{:?}", a.series_005_cumulative_mu);
    // lost motion of the refill: taken up by the core before the prime, so the first 1 U is within ~0.15 U (never over);
    // without the take-up it was short by a few hundred mU (REPORT.md)
    assert!(a.first_after_refill_mu.mean < 0.0 && a.first_after_refill_mu.mean > -200.0, "{:?}", a.first_after_refill_mu);
    assert!(a.first_after_refill_mu.p95 < 50.0, "never over-delivers after a refill: {:?}", a.first_after_refill_mu);
}

#[test]
fn no_nominal_pod_raises_a_false_alarm() {
    let r = run(&cfg(Experiment::Accuracy, 100, 4));
    let a = r.accuracy.as_ref().unwrap();
    // Fail-safe false occlusion alarms of the stored-volume rise criterion (limits.rs: 50 mU per mA, window 16): 2.9 % of the
    // 1000 simulated pods (tolerance corners with a large static-minus-dynamic seal friction), none of them silent
    assert!(a.false_alarm_runs.len() <= 6, "false alarms: {:?}", a.false_alarm_runs);
}

#[test]
fn occlusion_with_current_sense_meets_the_2_u_spec_for_nearly_every_pod() {
    let r = run(&cfg(Experiment::OcclusionBasal { current_sense: true }, 100, 4));
    let o = r.occlusion.as_ref().unwrap();
    assert!(o.detected >= 80, "detected {} of {}", o.detected, r.runs);
    assert!(o.over_2u as f64 / o.detected as f64 <= 0.05, "{} of {} above 2 U", o.over_2u, o.detected);
    assert!(o.undelivered_mu.p95 <= 2000.0, "{:?}", o.undelivered_mu);
    let r = run(&cfg(Experiment::OcclusionBolus { current_sense: true }, 100, 4));
    let o = r.occlusion.as_ref().unwrap();
    assert!(o.latency_s.p95 <= 150.0, "bolus occlusion latency {:?}", o.latency_s);
    assert!(o.undelivered_mu.p95 <= 2000.0, "{:?}", o.undelivered_mu);
}

#[test]
fn encoder_only_occlusion_detection_loses_much_more_water_than_with_the_current_sense() {
    let with = run(&cfg(Experiment::OcclusionBasal { current_sense: true }, 60, 4));
    let without = run(&cfg(Experiment::OcclusionBasal { current_sense: false }, 60, 4));
    let (w, wo) = (with.occlusion.unwrap(), without.occlusion.unwrap());
    assert!(wo.undelivered_mu.mean > 1.4 * w.undelivered_mu.mean, "{} vs {}", wo.undelivered_mu.mean, w.undelivered_mu.mean);
    assert!(wo.latency_s.mean > 1.4 * w.latency_s.mean);
}
