#![allow(dead_code)]
//! Helpers shared by the scenario tests.

use openpatch_sim::runner::{Detection, RunOutput, Runner, Verdict, MU_PER_UL};
use openpatch_sim::scenario::{Action, Scenario};
use openpatch_sim::scenarios;

pub fn scenario(name: &str) -> Scenario {
    scenarios::get(name).unwrap_or_else(|e| panic!("{e}"))
}

pub fn run_sc(sc: Scenario) -> RunOutput {
    Runner::run(sc).expect("scenario runs")
}

pub fn run(name: &str) -> RunOutput {
    let out = run_sc(scenario(name));
    assert!(out.verdict.setup_ok, "{name}: setup failed: {}", out.verdict.setup_note);
    out
}

pub fn det<'a>(v: &'a Verdict, prefix: &str) -> &'a Detection {
    v.detections.iter().find(|d| d.injection.starts_with(prefix)).unwrap_or_else(|| panic!("no injection {prefix}: {:?}", v.detections))
}

/// Cumulative fluid that left the needle (mU) `t_s` seconds after the end of setup.
pub fn needle_mu(o: &RunOutput, t_s: f64) -> f64 {
    let i = (t_s as usize).min(o.out_by_sec.len() - 1);
    o.out_by_sec[i] * MU_PER_UL
}

/// Row of the time series at (or just after) `t_s`.
pub fn row_at(o: &RunOutput, t_s: f64) -> &openpatch_sim::runner::Row {
    o.rows.iter().find(|r| r.t_s >= t_s - 1e-9).expect("row")
}

pub fn has_fault(v: &Verdict, name: &str) -> bool {
    v.faults.iter().any(|f| f.names.iter().any(|n| n == name))
}

/// Number of log events of a type in the pod's current log.
pub fn log_count(o: &RunOutput, kind: openpatch_core::EventType) -> usize {
    let mut e = vec![openpatch_core::Event::default(); openpatch_core::log::LOG_CAPACITY];
    let n = o.dev.pump().log().read(0, &mut e);
    e[..n].iter().filter(|x| x.kind == kind as u8).count()
}

pub fn at(sc: Scenario, t: f64, a: Action) -> Scenario {
    sc.at(t, a)
}
