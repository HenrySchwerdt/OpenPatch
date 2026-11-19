//! Generates `REPORT.md`: the hand-written text in `docs/REPORT.template.md` (assumptions, findings)
//! with the numbers filled in from the simulator itself, so the tables can never go stale.
//!
//! `opsim report [--runs N] [--out FILE]` (default 500 runs per Monte Carlo experiment).

use crate::montecarlo::{self, Experiment, McConfig, Tolerances};
use crate::runner::{Runner, Verdict};
use crate::scenarios;

use crate::report_text::TEMPLATE;

fn scenario_row(name: &str, desc: &str, v: &Verdict) -> String {
    let mut facts: Vec<String> = Vec::new();
    facts.push(format!(
        "core {:.2} U, needle {:.2} U{}",
        v.core_delivered_mu as f64 / 1000.0,
        v.actual_out_mu / 1000.0,
        v.actual_vs_core_pct.map_or(String::new(), |p| format!(" ({p:+.1} %)"))
    ));
    for d in &v.detections {
        let short = d.injection.split([' ', '{']).next().unwrap_or("").to_string();
        match (d.latency_s, d.detected_by_reset, d.undelivered_at_alarm_mu) {
            (Some(l), true, _) => facts.push(format!("{short}: pod reset after {l:.1} s")),
            (Some(l), false, Some(u)) => facts.push(format!("{short}: alarm {} after {l:.0} s, {:.2} U undelivered", d.fault_names.join("+"), u / 1000.0)),
            (None, _, _) if !matches!(short.as_str(), "Dock" | "PhoneConnected" | "ForceSteps" | "HallStuckDocked") => facts.push(format!("{short}: NOT detected")),
            _ => {}
        }
    }
    for dr in &v.draws {
        facts.push(format!("draw {:.1} U requested, core {:.2} U, vial {:.2} U (state {})", dr.requested_mu as f64 / 1000.0, dr.core_drawn_mu as f64 / 1000.0, dr.actual_drawn_mu / 1000.0, dr.core_state));
    }
    if v.interlock.bursts_blocked_forward_undocked > 0 {
        facts.push(format!("interlock refused {} forward burst(s) undocked", v.interlock.bursts_blocked_forward_undocked));
    }
    if v.interlock.violated {
        facts.push(format!("**{} forward steps while undocked**{}", v.interlock.forward_steps_moved_undocked, if v.interlock.hall_forced { " (hall forced)" } else { "" }));
    }
    if !v.resets.is_empty() {
        facts.push(format!("{} reset(s)", v.resets.len()));
    }
    if v.forward_steps_during_wdt_window > 0 {
        facts.push(format!("runaway before the watchdog cut: {} steps", v.forward_steps_during_wdt_window));
    }
    if v.limits.max_rolling_hour_core_mu > 0.0 {
        facts.push(format!("max 60 min: core {:.2} U, needle {:.2} U", v.limits.max_rolling_hour_core_mu / 1000.0, v.limits.max_rolling_hour_actual_mu / 1000.0));
    }
    format!("| `{name}` | {} | {} | {} |\n", desc.replace('|', "/"), if v.passed { "ok" } else { "FAIL" }, facts.join("; "))
}

fn scenario_table() -> Result<String, String> {
    let mut s = String::from("| scenario | what happens | verdict | result |\n|---|---|---|---|\n");
    for n in scenarios::names() {
        let sc = scenarios::get(n)?;
        let desc = sc.description.clone();
        let o = Runner::run(sc)?;
        s.push_str(&scenario_row(n, &desc, &o.verdict));
    }
    Ok(s)
}

fn tolerance_table(t: &Tolerances) -> String {
    let r = |(a, b): (f64, f64)| format!("{a} .. {b}");
    format!(
        "| quantity | distribution |\n|---|---|\n\
| lead error (systematic) | normal, sd {} %, truncated at 3 sd (+-{} %) |\n\
| lead error (once per turn) | uniform {} um |\n\
| gearhead ratio | normal, sd {} % |\n\
| stadium area | normal, sd {} % (nominal 74.6 mm^2) |\n\
| seal static friction | log-normal, median {} N, sigma(ln) {} |\n\
| seal dynamic / static | uniform {} |\n\
| carriage -> plunger stiffness | log-normal, median {} N/mm, sigma(ln) {} |\n\
| gear pair backlash (at the screw) | uniform {} deg |\n\
| gearhead backlash (at its output) | uniform {} deg |\n\
| TMAG5273 noise | uniform {} deg rms |\n\
| TMAG5273 once-per-turn nonlinearity | uniform {} deg |\n\
| fluid compliance | log-normal, median {} ul/kPa, sigma(ln) {} |\n\
| duckbill cracking pressure | uniform {} kPa (spec 1 .. 5) |\n\
| motor pull-out torque | normal, sd {} % (nominal 1.6 gf*cm) |\n\
| screw efficiency | uniform {} (spec ~0.20) |\n\
| air bubble in the reservoir | exponential, mean {} ul, capped at {} ul |\n\
| air in the connector | uniform {} ul |\n",
        t.pitch_error_pct_sd,
        3.0 * t.pitch_error_pct_sd,
        r(t.pitch_periodic_um),
        t.gearhead_ratio_pct_sd,
        t.area_pct_sd,
        t.seal_static_n.0,
        t.seal_static_n.1,
        r(t.seal_dyn_ratio),
        t.axial_k.0,
        t.axial_k.1,
        r(t.backlash_pair_deg),
        r(t.backlash_gearhead_deg),
        r(t.angle_noise_deg),
        r(t.angle_inl_deg),
        t.compliance.0,
        t.compliance.1,
        r(t.crack_kpa),
        t.pullout_pct_sd,
        r(t.screw_eff),
        t.bubble_mean_ul,
        t.bubble_cap_ul,
        r(t.line_air_ul),
    )
}

fn mc(exp: Experiment, runs: usize, threads: usize, tweak: impl Fn(&mut McConfig)) -> String {
    let mut c = McConfig::new(exp, runs, 20261119);
    c.threads = threads;
    tweak(&mut c);
    montecarlo::markdown(&montecarlo::run(&c))
}

fn sensitivity(runs: usize, threads: usize) -> String {
    let mut s = String::from("| carriage -> plunger stiffness | detection | median undelivered at alarm | 95th percentile | runs above 2 U |\n|---|---|---|---|---|\n");
    for k in [15.0, 40.0, 150.0, 600.0] {
        for (label, cs) in [("current rise + encoder", true), ("encoder only", false)] {
            let mut c = McConfig::new(Experiment::OcclusionBasal { current_sense: cs }, runs, 4242);
            c.threads = threads;
            c.tol.axial_k.0 = k;
            let r = montecarlo::run(&c);
            let o = r.occlusion.unwrap();
            s.push_str(&format!(
                "| {k} N/mm | {label} | {:.0} mU | {:.0} mU | {:.1} % (of {} detected, {} not detected) |\n",
                o.undelivered_mu.p50,
                o.undelivered_mu.p95,
                100.0 * o.over_2u as f64 / o.detected.max(1) as f64,
                o.detected,
                o.undetected
            ));
        }
    }
    s
}

pub fn generate(runs: usize, threads: usize) -> Result<String, String> {
    let mut t = TEMPLATE.to_string();
    let rep = |t: &mut String, key: &str, val: String| {
        *t = t.replace(&format!("{{{{{key}}}}}"), &val);
    };
    rep(&mut t, "RUNS", runs.to_string());
    rep(&mut t, "SCENARIO_TABLE", scenario_table()?);
    rep(&mut t, "TOLERANCES", tolerance_table(&Tolerances::default()));
    rep(&mut t, "MC_ACCURACY", mc(Experiment::Accuracy, runs, threads, |_| {}));
    rep(&mut t, "MC_OCC_BASAL", mc(Experiment::OcclusionBasal { current_sense: true }, runs, threads, |_| {}));
    rep(&mut t, "MC_OCC_BASAL_NC", mc(Experiment::OcclusionBasal { current_sense: false }, runs, threads, |_| {}));
    rep(&mut t, "MC_OCC_BOLUS", mc(Experiment::OcclusionBolus { current_sense: true }, runs, threads, |_| {}));
    rep(&mut t, "MC_OCC_BOLUS_NC", mc(Experiment::OcclusionBolus { current_sense: false }, runs, threads, |_| {}));
    rep(&mut t, "SENSITIVITY", sensitivity((runs / 3).max(60), threads));
    Ok(t)
}

pub fn cli(args: &[String]) -> Result<bool, String> {
    let get = |flag: &str| args.iter().position(|a| a == flag).and_then(|i| args.get(i + 1)).cloned();
    let runs: usize = get("--runs").map_or(Ok(500), |s| s.parse().map_err(|_| "bad --runs"))?;
    let threads: usize = get("--threads").map_or(Ok(std::thread::available_parallelism().map_or(4, |n| n.get())), |s| s.parse().map_err(|_| "bad --threads"))?;
    let out = get("--out").unwrap_or_else(|| "REPORT.md".into());
    let text = generate(runs, threads)?;
    std::fs::write(&out, text).map_err(|e| format!("{out}: {e}"))?;
    eprintln!("opsim: wrote {out}");
    Ok(true)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn template_has_every_placeholder_the_generator_fills() {
        for k in ["RUNS", "SCENARIO_TABLE", "TOLERANCES", "MC_ACCURACY", "MC_OCC_BASAL", "MC_OCC_BASAL_NC", "MC_OCC_BOLUS", "MC_OCC_BOLUS_NC", "SENSITIVITY"] {
            assert!(TEMPLATE.contains(&format!("{{{{{k}}}}}")), "placeholder {k} missing");
        }
    }

    #[test]
    fn a_small_report_generates_without_leftover_placeholders() {
        let r = generate(6, 2).unwrap();
        assert!(!r.contains("{{"), "unfilled placeholder");
        assert!(r.contains("wear_48h"));
    }
}
