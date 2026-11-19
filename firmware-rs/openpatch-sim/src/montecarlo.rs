//! Monte Carlo: N virtual pods with manufacturing tolerances, same protocol, distributions out.
//!
//! Experiments:
//! * `accuracy`: after a standard refill + prime, a warm-up bolus, then 10 x 0.05 U, 6 x 1 U and one
//!   10 U bolus on a zero basal. Per bolus the fluid that left the needle (gravimetric equivalent,
//!   60 s settling) is compared with the command.
//! * `occlusion-basal[-no-current]`: cannula blocked at a random time during a 1 U/h basal;
//!   detection latency and the insulin not delivered at the alarm (spec: <= 2 U).
//! * `occlusion-bolus[-no-current]`: the same during an 8 U bolus.
//!
//! Runs are independent and reproducible from (seed, index); threads only split the index range, so
//! the result does not depend on the thread count.

use crate::params::Params;
use crate::rng::Rng;
use crate::runner::Runner;
use crate::scenario::{Action, Scenario};
use serde::Serialize;

/// Distribution parameters of the sampled tolerances (documented in REPORT.md).
#[derive(Clone, Debug, Serialize)]
pub struct Tolerances {
    /// 1-sigma of the systematic lead error (%), truncated at 3 sigma.
    pub pitch_error_pct_sd: f64,
    pub pitch_periodic_um: (f64, f64),
    pub gearhead_ratio_pct_sd: f64,
    /// 1-sigma of the stadium area (%).
    pub area_pct_sd: f64,
    /// (median, sigma of ln) of the static seal friction.
    pub seal_static_n: (f64, f64),
    /// dynamic / static friction ratio range.
    pub seal_dyn_ratio: (f64, f64),
    pub axial_k: (f64, f64),
    pub backlash_pair_deg: (f64, f64),
    pub backlash_gearhead_deg: (f64, f64),
    pub angle_noise_deg: (f64, f64),
    pub angle_inl_deg: (f64, f64),
    pub compliance: (f64, f64),
    pub crack_kpa: (f64, f64),
    /// 1-sigma of the pull-out torque (%), motor to motor.
    pub pullout_pct_sd: f64,
    pub screw_eff: (f64, f64),
    /// mean of the exponential air bubble (ul), capped.
    pub bubble_mean_ul: f64,
    pub bubble_cap_ul: f64,
    pub line_air_ul: (f64, f64),
}

impl Default for Tolerances {
    fn default() -> Self {
        Tolerances {
            pitch_error_pct_sd: 0.5,
            pitch_periodic_um: (0.0, 0.5),
            gearhead_ratio_pct_sd: 0.3,
            area_pct_sd: 0.5,
            seal_static_n: (1.5, 0.30),
            seal_dyn_ratio: (0.4, 0.7),
            axial_k: (40.0, 0.30),
            backlash_pair_deg: (1.0, 3.0),
            backlash_gearhead_deg: (0.5, 2.5),
            angle_noise_deg: (0.05, 0.25),
            angle_inl_deg: (0.0, 1.0),
            compliance: (0.05, 0.40),
            crack_kpa: (1.0, 5.0),
            pullout_pct_sd: 8.0,
            screw_eff: (0.15, 0.25),
            bubble_mean_ul: 3.0,
            bubble_cap_ul: 20.0,
            line_air_ul: (0.5, 2.5),
        }
    }
}

impl Tolerances {
    pub fn sample(&self, base: &Params, rng: &mut Rng) -> Params {
        let mut p = base.clone();
        let lnorm = |rng: &mut Rng, (m, s): (f64, f64)| m * (s * rng.gauss_trunc(3.0)).exp();
        let uni = |rng: &mut Rng, (a, b): (f64, f64)| rng.range(a, b);
        p.drive.pitch_error_pct = self.pitch_error_pct_sd * rng.gauss_trunc(3.0);
        p.drive.pitch_periodic_um = uni(rng, self.pitch_periodic_um);
        p.motor.gearhead_ratio = base.motor.gearhead_ratio * (1.0 + self.gearhead_ratio_pct_sd / 100.0 * rng.gauss_trunc(3.0));
        p.drive.area_mm2 = base.drive.area_mm2 * (1.0 + self.area_pct_sd / 100.0 * rng.gauss_trunc(3.0));
        p.drive.seal_static_n = lnorm(rng, self.seal_static_n);
        p.drive.seal_dynamic_n = p.drive.seal_static_n * uni(rng, self.seal_dyn_ratio);
        p.drive.axial_stiffness_n_mm = lnorm(rng, self.axial_k);
        p.drive.pair_backlash_deg = uni(rng, self.backlash_pair_deg);
        p.drive.gearhead_backlash_deg = uni(rng, self.backlash_gearhead_deg);
        p.sensor.angle_noise_deg = uni(rng, self.angle_noise_deg);
        p.sensor.angle_inl_deg = uni(rng, self.angle_inl_deg);
        p.fluid.compliance_ul_per_kpa = lnorm(rng, self.compliance);
        p.fluid.crack_kpa = uni(rng, self.crack_kpa);
        p.motor.pullout_gf_cm = base.motor.pullout_gf_cm * (1.0 + self.pullout_pct_sd / 100.0 * rng.gauss_trunc(3.0));
        p.drive.screw_eff = uni(rng, self.screw_eff);
        let e = -rng.uniform().max(1e-12).ln() * self.bubble_mean_ul;
        p.fluid.bubble_ul = e.min(self.bubble_cap_ul);
        p.fluid.line_air_ul = uni(rng, self.line_air_ul);
        p
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Experiment {
    Accuracy,
    OcclusionBasal { current_sense: bool },
    OcclusionBolus { current_sense: bool },
}

impl Experiment {
    pub fn parse(s: &str) -> Option<Experiment> {
        Some(match s {
            "accuracy" => Experiment::Accuracy,
            "occlusion-basal" => Experiment::OcclusionBasal { current_sense: true },
            "occlusion-basal-no-current" => Experiment::OcclusionBasal { current_sense: false },
            "occlusion-bolus" => Experiment::OcclusionBolus { current_sense: true },
            "occlusion-bolus-no-current" => Experiment::OcclusionBolus { current_sense: false },
            _ => return None,
        })
    }
    pub fn name(&self) -> &'static str {
        match self {
            Experiment::Accuracy => "accuracy",
            Experiment::OcclusionBasal { current_sense: true } => "occlusion-basal",
            Experiment::OcclusionBasal { current_sense: false } => "occlusion-basal-no-current",
            Experiment::OcclusionBolus { current_sense: true } => "occlusion-bolus",
            Experiment::OcclusionBolus { current_sense: false } => "occlusion-bolus-no-current",
        }
    }
}

#[derive(Clone, Debug)]
pub struct McConfig {
    pub experiment: Experiment,
    pub runs: usize,
    pub seed: u64,
    pub threads: usize,
    pub tol: Tolerances,
    pub base: Params,
}

impl McConfig {
    pub fn new(experiment: Experiment, runs: usize, seed: u64) -> Self {
        McConfig { experiment, runs, seed, threads: 4, tol: Tolerances::default(), base: Params::default() }
    }
}

#[derive(Clone, Debug, Serialize, Default)]
pub struct Dist {
    pub n: usize,
    pub mean: f64,
    pub sd: f64,
    pub min: f64,
    pub p01: f64,
    pub p05: f64,
    pub p50: f64,
    pub p95: f64,
    pub p99: f64,
    pub max: f64,
}

pub fn dist(v: &[f64]) -> Dist {
    if v.is_empty() {
        return Dist::default();
    }
    let mut s = v.to_vec();
    s.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = s.len();
    let mean = s.iter().sum::<f64>() / n as f64;
    let var = if n > 1 { s.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (n - 1) as f64 } else { 0.0 };
    let q = |p: f64| s[(((n - 1) as f64) * p).round() as usize];
    Dist { n, mean, sd: var.sqrt(), min: s[0], p01: q(0.01), p05: q(0.05), p50: q(0.5), p95: q(0.95), p99: q(0.99), max: s[n - 1] }
}

/// Accuracy of one bolus size class.
#[derive(Clone, Debug, Serialize, Default)]
pub struct SizeClass {
    pub units: f64,
    /// relative error in percent
    pub error_pct: Dist,
    /// absolute error in mU
    pub error_mu: Dist,
    pub within_5pct: f64,
    pub within_10pct: f64,
    pub within_20pct: f64,
}

#[derive(Clone, Debug, Serialize, Default)]
pub struct AccuracyResult {
    pub classes: Vec<SizeClass>,
    /// first 1 U after the refill, error in mU (lost motion after the draw reversal)
    pub first_after_refill_mu: Dist,
    /// cumulative error over the 10 x 0.05 U series, mU
    pub series_005_cumulative_mu: Dist,
    /// error of the 6 x 1 U series as a whole, percent
    pub series_1u_pct: Dist,
    pub failed_runs: usize,
    pub failure_reasons: Vec<(String, usize)>,
    /// runs that completed but latched a fault during the nominal sequence (false alarms)
    pub false_alarm_runs: Vec<(String, usize)>,
    /// mean (seal static N, screw efficiency, pull-out gf*cm) of the failed / the good runs
    pub failed_param_means: Option<[f64; 3]>,
    pub good_param_means: Option<[f64; 3]>,
}

#[derive(Clone, Debug, Serialize, Default)]
pub struct OcclusionResult {
    pub detected: usize,
    pub undetected: usize,
    pub latency_s: Dist,
    pub undelivered_mu: Dist,
    pub over_2u: usize,
    pub by_fault: Vec<(String, usize)>,
    /// bubble size (ul) of the runs that exceeded 2 U
    pub over_2u_bubbles_ul: Vec<f64>,
    pub bubble_vs_undelivered: Vec<(f64, f64)>,
    /// (bubble range label, runs, median undelivered mU)
    pub bubble_bins: Vec<(String, usize, f64)>,
    pub failure_reasons: Vec<(String, usize)>,
}

#[derive(Clone, Debug, Serialize)]
pub struct McResult {
    pub experiment: String,
    pub runs: usize,
    pub seed: u64,
    pub tol: Tolerances,
    pub accuracy: Option<AccuracyResult>,
    pub occlusion: Option<OcclusionResult>,
}

// ---- scenarios of the experiments ---------------------------------------------------------------

const ACC_SMALL: usize = 10;
const ACC_ONE: usize = 6;

fn accuracy_scenario(p: Params, seed: u64) -> Scenario {
    let mut sc = Scenario { name: "mc-accuracy".into(), seed, ..Default::default() };
    sc.params = p;
    sc.setup.fill_u = 40.0;
    sc.setup.basal = vec![(0.0, 0.0)];
    sc.setup.prime_u = 0.3;
    sc.log_interval_s = 3600.0;
    sc = sc.at(30.0, Action::Bolus { units: 1.0 }); // warm-up: takes up the lost motion of the reversal
    for k in 0..ACC_SMALL {
        sc = sc.at(600.0 + 300.0 * k as f64, Action::Bolus { units: 0.05 });
    }
    for k in 0..ACC_ONE {
        sc = sc.at(3900.0 + 300.0 * k as f64, Action::Bolus { units: 1.0 });
    }
    sc = sc.at(9000.0, Action::Bolus { units: 10.0 });
    sc.duration_s = 9000.0 + 10.0 / 1.5 * 60.0 + 120.0;
    sc
}

fn occlusion_scenario(p: Params, seed: u64, bolus: bool, current_sense: bool, rng: &mut Rng) -> (Scenario, f64) {
    let mut sc = Scenario { name: "mc-occlusion".into(), seed, ..Default::default() };
    sc.params = p;
    sc.params.motor.current_sense = current_sense;
    sc.setup.fill_u = 40.0;
    sc.log_interval_s = 3600.0;
    if bolus {
        sc.setup.basal = vec![(0.0, 0.5)];
        sc = sc.at(600.0, Action::Bolus { units: 8.0 });
        let t = 600.0 + rng.range(5.0, 300.0);
        sc = sc.at(t, Action::Occlude { factor: None });
        sc.duration_s = 3600.0;
        (sc, t)
    } else {
        sc.setup.basal = vec![(0.0, 1.0)];
        let t = rng.range(1800.0, 5400.0);
        sc = sc.at(t, Action::Occlude { factor: None });
        sc.duration_s = t + 6.0 * 3600.0;
        (sc, t)
    }
}

enum RunOut {
    Accuracy { first: Option<f64>, boluses: Vec<(f64, f64, f64)>, pm: [f64; 3], faults: Vec<String> },
    Occlusion { latency: Option<f64>, undelivered: Option<f64>, fault: String, bubble: f64 },
    Failed(String, [f64; 3]),
}

fn one_run(cfg: &McConfig, i: usize) -> RunOut {
    let mut prng = Rng::fork(cfg.seed, i as u64);
    let p = cfg.tol.sample(&cfg.base, &mut prng);
    let run_seed = cfg.seed ^ (i as u64).wrapping_mul(0x9E37_79B9_7F4A_7C15);
    match cfg.experiment {
        Experiment::Accuracy => {
            let pm = [p.drive.seal_static_n, p.drive.screw_eff, p.motor.pullout_gf_cm];
            let Ok(out) = Runner::run(accuracy_scenario(p, run_seed)) else { return RunOut::Failed("scenario error".into(), pm) };
            if !out.verdict.setup_ok {
                return RunOut::Failed(out.verdict.setup_note.split(" (").next().unwrap_or("").to_string(), pm);
            }
            let b = &out.verdict.boluses;
            // b[0] = warm-up
            let first = b.first().and_then(|x| x.actual_bolus_mu.map(|a| a - x.units_cmd * 1000.0));
            let boluses = b
                .iter()
                .skip(1)
                .filter_map(|x| x.actual_bolus_mu.map(|a| (x.units_cmd, x.units_cmd * 1000.0, a)))
                .collect();
            let faults = out.verdict.faults.iter().flat_map(|f| f.names.clone()).collect();
            RunOut::Accuracy { first, boluses, pm, faults }
        }
        Experiment::OcclusionBasal { current_sense } | Experiment::OcclusionBolus { current_sense } => {
            let bolus = matches!(cfg.experiment, Experiment::OcclusionBolus { .. });
            let bubble = p.fluid.bubble_ul;
            let (sc, _t) = occlusion_scenario(p, run_seed, bolus, current_sense, &mut prng);
            let Ok(out) = Runner::run(sc) else { return RunOut::Failed("scenario error".into(), [0.0; 3]) };
            if !out.verdict.setup_ok {
                return RunOut::Failed(out.verdict.setup_note.split(" (").next().unwrap_or("").to_string(), [0.0; 3]);
            }
            let d = out.verdict.detections.iter().find(|d| d.injection.starts_with("Occlude"));
            match d {
                Some(d) => RunOut::Occlusion {
                    latency: d.latency_s,
                    undelivered: d.undelivered_at_alarm_mu,
                    fault: d.fault_names.join("+"),
                    bubble,
                },
                None => RunOut::Failed("no detection".into(), [0.0; 3]),
            }
        }
    }
}

pub fn run(cfg: &McConfig) -> McResult {
    let threads = cfg.threads.max(1).min(cfg.runs.max(1));
    let mut outs: Vec<(usize, RunOut)> = Vec::with_capacity(cfg.runs);
    std::thread::scope(|s| {
        let handles: Vec<_> = (0..threads)
            .map(|t| {
                s.spawn(move || {
                    let mut v = Vec::new();
                    let mut i = t;
                    while i < cfg.runs {
                        v.push((i, one_run(cfg, i)));
                        i += threads;
                    }
                    v
                })
            })
            .collect();
        for h in handles {
            outs.extend(h.join().expect("monte carlo worker panicked"));
        }
    });
    outs.sort_by_key(|(i, _)| *i);
    let mut r = McResult { experiment: cfg.experiment.name().into(), runs: cfg.runs, seed: cfg.seed, tol: cfg.tol.clone(), accuracy: None, occlusion: None };
    match cfg.experiment {
        Experiment::Accuracy => r.accuracy = Some(summarize_accuracy(&outs)),
        _ => r.occlusion = Some(summarize_occlusion(&outs)),
    }
    r
}

fn summarize_accuracy(outs: &[(usize, RunOut)]) -> AccuracyResult {
    let mut res = AccuracyResult::default();
    let mut reasons: std::collections::BTreeMap<String, usize> = Default::default();
    let mut alarms: std::collections::BTreeMap<String, usize> = Default::default();
    let (mut good_pm, mut bad_pm): (Vec<[f64; 3]>, Vec<[f64; 3]>) = (Vec::new(), Vec::new());
    let mut firsts = Vec::new();
    let mut series005 = Vec::new();
    let mut series1 = Vec::new();
    let sizes = [0.05, 1.0, 10.0];
    let mut per: Vec<Vec<(f64, f64)>> = vec![Vec::new(); sizes.len()]; // (cmd_mu, actual_mu)
    for (_, o) in outs {
        match o {
            RunOut::Accuracy { first, boluses, pm, faults } => {
                good_pm.push(*pm);
                for f in faults {
                    *alarms.entry(f.clone()).or_default() += 1;
                }
                if let Some(f) = first {
                    firsts.push(*f);
                }
                let (mut c5, mut a5, mut c1, mut a1) = (0.0, 0.0, 0.0, 0.0);
                for &(u, cmd, act) in boluses {
                    if let Some(k) = sizes.iter().position(|s| (*s - u).abs() < 1e-9) {
                        per[k].push((cmd, act));
                    }
                    if (u - 0.05).abs() < 1e-9 {
                        c5 += cmd;
                        a5 += act;
                    } else if (u - 1.0).abs() < 1e-9 {
                        c1 += cmd;
                        a1 += act;
                    }
                }
                if c5 > 0.0 {
                    series005.push(a5 - c5);
                }
                if c1 > 0.0 {
                    series1.push((a1 / c1 - 1.0) * 100.0);
                }
            }
            RunOut::Failed(why, pm) => {
                res.failed_runs += 1;
                *reasons.entry(why.clone()).or_default() += 1;
                bad_pm.push(*pm);
            }
            _ => res.failed_runs += 1,
        }
    }
    let mean3 = |v: &Vec<[f64; 3]>| if v.is_empty() { None } else { Some([0, 1, 2].map(|k| v.iter().map(|x| x[k]).sum::<f64>() / v.len() as f64)) };
    res.failed_param_means = mean3(&bad_pm);
    res.good_param_means = mean3(&good_pm);
    res.false_alarm_runs = alarms.into_iter().collect();
    res.failure_reasons = reasons.into_iter().collect();
    for (k, u) in sizes.iter().enumerate() {
        let pct: Vec<f64> = per[k].iter().map(|(c, a)| (a / c - 1.0) * 100.0).collect();
        let abs: Vec<f64> = per[k].iter().map(|(c, a)| a - c).collect();
        let frac = |lim: f64| if pct.is_empty() { 0.0 } else { pct.iter().filter(|p| p.abs() <= lim).count() as f64 / pct.len() as f64 };
        res.classes.push(SizeClass { units: *u, error_pct: dist(&pct), error_mu: dist(&abs), within_5pct: frac(5.0), within_10pct: frac(10.0), within_20pct: frac(20.0) });
    }
    res.first_after_refill_mu = dist(&firsts);
    res.series_005_cumulative_mu = dist(&series005);
    res.series_1u_pct = dist(&series1);
    res
}

fn summarize_occlusion(outs: &[(usize, RunOut)]) -> OcclusionResult {
    let mut r = OcclusionResult::default();
    let (mut lat, mut und) = (Vec::new(), Vec::new());
    let mut by: std::collections::BTreeMap<String, usize> = Default::default();
    let mut reasons: std::collections::BTreeMap<String, usize> = Default::default();
    for (_, o) in outs {
        match o {
            RunOut::Occlusion { latency: Some(l), undelivered: Some(u), fault, bubble } => {
                r.detected += 1;
                lat.push(*l);
                und.push(*u);
                *by.entry(fault.clone()).or_default() += 1;
                if *u > 2000.0 {
                    r.over_2u += 1;
                    r.over_2u_bubbles_ul.push(*bubble);
                }
                r.bubble_vs_undelivered.push((*bubble, *u));
            }
            RunOut::Failed(why, _) => {
                r.undetected += 1;
                *reasons.entry(why.clone()).or_default() += 1;
            }
            _ => r.undetected += 1,
        }
    }
    r.failure_reasons = reasons.into_iter().collect();
    for (lo, hi) in [(0.0, 1.0), (1.0, 3.0), (3.0, 6.0), (6.0, 10.0), (10.0, 100.0)] {
        let v: Vec<f64> = r.bubble_vs_undelivered.iter().filter(|(b, _)| *b >= lo && *b < hi).map(|(_, u)| *u).collect();
        if !v.is_empty() {
            let label = if hi >= 100.0 { format!(">= {lo} ul") } else { format!("{lo} .. {hi} ul") };
            r.bubble_bins.push((label, v.len(), dist(&v).p50));
        }
    }
    r.latency_s = dist(&lat);
    r.undelivered_mu = dist(&und);
    r.by_fault = by.into_iter().collect();
    r
}

// ---- markdown --------------------------------------------------------------------------------

fn f(x: f64, d: usize) -> String {
    format!("{x:.d$}")
}

pub fn accuracy_markdown(r: &McResult) -> String {
    let a = r.accuracy.as_ref().expect("accuracy result");
    let mut s = String::new();
    s.push_str(&format!("Runs: {} (seed {}), failed set-ups: {} {:?}.", r.runs, r.seed, a.failed_runs, a.failure_reasons));
    if let (Some(b), Some(g)) = (a.failed_param_means, a.good_param_means) {
        s.push_str(&format!(
            " Mean seal static friction / screw efficiency / pull-out of failed vs good pods: {:.2} N / {:.3} / {:.2} gf*cm vs {:.2} N / {:.3} / {:.2} gf*cm.",
            b[0], b[1], b[2], g[0], g[1], g[2]
        ));
    }
    if !a.false_alarm_runs.is_empty() {
        s.push_str(&format!(" Faults latched during the nominal sequence (false alarms): {:?}.", a.false_alarm_runs));
    }
    s.push_str("\n\n");
    s.push_str("| bolus | n | mean err % | sd % | 5th % | 50th % | 95th % | worst % | within +-5 % | within +-10 % | mean err mU | sd mU |\n|---|---|---|---|---|---|---|---|---|---|---|---|\n");
    for c in &a.classes {
        let worst = if c.error_pct.max.abs() > c.error_pct.min.abs() { c.error_pct.max } else { c.error_pct.min };
        s.push_str(&format!(
            "| {} U | {} | {} | {} | {} | {} | {} | {} | {} % | {} % | {} | {} |\n",
            c.units,
            c.error_pct.n,
            f(c.error_pct.mean, 2),
            f(c.error_pct.sd, 2),
            f(c.error_pct.p05, 2),
            f(c.error_pct.p50, 2),
            f(c.error_pct.p95, 2),
            f(worst, 1),
            f(c.within_5pct * 100.0, 1),
            f(c.within_10pct * 100.0, 1),
            f(c.error_mu.mean, 2),
            f(c.error_mu.sd, 2),
        ));
    }
    s.push_str(&format!(
        "\nSeries: 10 x 0.05 U cumulative error {} mU mean (sd {}, 5th..95th {} .. {}); 6 x 1 U series {} % mean (sd {}).\n",
        f(a.series_005_cumulative_mu.mean, 2),
        f(a.series_005_cumulative_mu.sd, 2),
        f(a.series_005_cumulative_mu.p05, 1),
        f(a.series_005_cumulative_mu.p95, 1),
        f(a.series_1u_pct.mean, 2),
        f(a.series_1u_pct.sd, 2)
    ));
    s.push_str(&format!(
        "\nFirst 1 U bolus after a refill + 0.3 U prime (lost motion of the draw reversal): mean error {} mU, 5th..95th {} .. {} mU, worst {} mU.\n",
        f(a.first_after_refill_mu.mean, 0),
        f(a.first_after_refill_mu.p05, 0),
        f(a.first_after_refill_mu.p95, 0),
        f(a.first_after_refill_mu.min, 0)
    ));
    s
}

pub fn occlusion_markdown(r: &McResult) -> String {
    let o = r.occlusion.as_ref().expect("occlusion result");
    let mut s = String::new();
    s.push_str(&format!("Runs: {} (seed {}), detected {}, not detected / set-up failed {} {:?}.\n\n", r.runs, r.seed, o.detected, o.undetected, o.failure_reasons));
    s.push_str("| metric | mean | sd | 5th | median | 95th | 99th | max |\n|---|---|---|---|---|---|---|---|\n");
    let d = &o.latency_s;
    s.push_str(&format!("| detection latency (s) | {} | {} | {} | {} | {} | {} | {} |\n", f(d.mean, 0), f(d.sd, 0), f(d.p05, 0), f(d.p50, 0), f(d.p95, 0), f(d.p99, 0), f(d.max, 0)));
    let d = &o.undelivered_mu;
    s.push_str(&format!("| undelivered at alarm (mU) | {} | {} | {} | {} | {} | {} | {} |\n", f(d.mean, 0), f(d.sd, 0), f(d.p05, 0), f(d.p50, 0), f(d.p95, 0), f(d.p99, 0), f(d.max, 0)));
    s.push_str(&format!("\nRuns above the 2 U spec: {} of {} ({} %).", o.over_2u, o.detected, f(100.0 * o.over_2u as f64 / o.detected.max(1) as f64, 1)));
    if !o.over_2u_bubbles_ul.is_empty() {
        let mn = o.over_2u_bubbles_ul.iter().cloned().fold(f64::MAX, f64::min);
        s.push_str(&format!(" Smallest bubble among them: {} ul.", f(mn, 1)));
    }
    if !o.bubble_bins.is_empty() {
        s.push_str("\n\n| reservoir air bubble | runs | median undelivered at alarm (mU) |\n|---|---|---|\n");
        for (l, n, m) in &o.bubble_bins {
            s.push_str(&format!("| {l} | {n} | {} |\n", f(*m, 0)));
        }
    }
    s.push_str("\nDetected by: ");
    s.push_str(&o.by_fault.iter().map(|(k, v)| format!("{k} {v}")).collect::<Vec<_>>().join(", "));
    s.push('\n');
    s
}

pub fn markdown(r: &McResult) -> String {
    if r.accuracy.is_some() {
        accuracy_markdown(r)
    } else {
        occlusion_markdown(r)
    }
}

pub fn cli(args: &[String]) -> Result<bool, String> {
    let exp = args.first().ok_or("mc: experiment missing")?;
    let exp = Experiment::parse(exp).ok_or_else(|| format!("unknown experiment {exp:?}"))?;
    let get = |flag: &str| args.iter().position(|a| a == flag).and_then(|i| args.get(i + 1)).cloned();
    let runs: usize = get("--runs").map_or(Ok(200), |s| s.parse().map_err(|_| "bad --runs"))?;
    let seed: u64 = get("--seed").map_or(Ok(1), |s| s.parse().map_err(|_| "bad --seed"))?;
    let threads: usize = get("--threads").map_or(Ok(std::thread::available_parallelism().map_or(4, |n| n.get())), |s| s.parse().map_err(|_| "bad --threads"))?;
    let mut cfg = McConfig::new(exp, runs, seed);
    cfg.threads = threads;
    let num = |flag: &str| -> Result<Option<f64>, String> { get(flag).map(|s| s.parse::<f64>().map_err(|_| format!("bad {flag}"))).transpose() };
    if let Some(k) = num("--axial-k")? {
        cfg.tol.axial_k.0 = k;
    }
    if let Some(c) = num("--compliance")? {
        cfg.tol.compliance.0 = c;
    }
    if let Some(b) = num("--bubble-mean")? {
        cfg.tol.bubble_mean_ul = b;
    }
    let r = run(&cfg);
    if let Some(p) = get("--json") {
        std::fs::write(&p, serde_json::to_string_pretty(&r).map_err(|e| e.to_string())?).map_err(|e| format!("{p}: {e}"))?;
    }
    println!("{}", markdown(&r));
    Ok(true)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dist_basics() {
        let d = dist(&[1.0, 2.0, 3.0, 4.0, 5.0]);
        assert_eq!(d.n, 5);
        assert!((d.mean - 3.0).abs() < 1e-12);
        assert_eq!(d.min, 1.0);
        assert_eq!(d.max, 5.0);
        assert_eq!(d.p50, 3.0);
    }

    #[test]
    fn sampling_stays_inside_the_documented_ranges() {
        let t = Tolerances::default();
        let base = Params::default();
        let mut rng = Rng::new(5);
        for _ in 0..500 {
            let p = t.sample(&base, &mut rng);
            assert!(p.drive.pitch_error_pct.abs() <= 1.5 + 1e-9);
            assert!(p.fluid.crack_kpa >= 1.0 && p.fluid.crack_kpa <= 5.0);
            assert!(p.fluid.bubble_ul <= 20.0);
            assert!(p.drive.seal_dynamic_n < p.drive.seal_static_n);
            assert!(p.drive.area_mm2 > 70.0 && p.drive.area_mm2 < 79.0);
        }
    }
}
