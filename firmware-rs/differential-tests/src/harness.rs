//! Shared test drivers: run a generated sequence, and on divergence shrink it to a minimal
//! reproducer and fail with a readable report.

use crate::gen::run_generated;
use crate::pair::{describe, minimize, run, Op, Setup, Stats};

pub fn report_divergence(setup: &Setup, ops: &[Op], idx: usize, msg: &str) -> String {
    let min = minimize(setup, ops);
    let err = run(setup, &min, &mut Stats::default()).err();
    format!(
        "DIVERGENCE at op {idx}: {msg}\n--- minimal reproducer ({} ops, fails with: {:?}) ---\n{}",
        min.len(),
        err.map(|e| e.1),
        describe(setup, &min)
    )
}

/// Runs `n` generated ops for `seed`; returns `Err(report)` on the first divergence.
pub fn check_seed(seed: u64, n: usize, stats: &mut Stats) -> Result<(), String> {
    let (setup, ops, res) = run_generated(seed, n, stats);
    match res {
        Ok(()) => Ok(()),
        Err((i, msg)) => {
            let shown = if i == usize::MAX { 0 } else { i };
            Err(format!("seed {seed}: {}", report_divergence(&setup, &ops, shown, &msg)))
        }
    }
}
