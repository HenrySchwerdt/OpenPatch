//! `opsim`: scenario runner, Monte Carlo, report generator and JSON interface of the virtual pod.
//! TEST PROJECT: not a medical device, never to be worn.

use openpatch_sim::runner::Runner;
use openpatch_sim::scenarios;
use std::process::ExitCode;

const USAGE: &str = "opsim - OpenPatch virtual pod (TEST PROJECT, never to be worn)

USAGE:
  opsim list                                  built-in scenarios
  opsim run <name|file.toml|file.json> [--csv FILE] [--json FILE] [--seed N] [--quiet]
  opsim all [--outdir DIR]                    run every built-in scenario, print the verdict table
  opsim mc <experiment> [--runs N] [--seed S] [--threads T] [--json FILE]
        experiments: accuracy | occlusion-basal | occlusion-bolus
  opsim report [--runs N] [--out FILE]        regenerate REPORT.md (scenario table + Monte Carlo)
  opsim serve [--stdio | --tcp ADDR]          JSON-lines interface for end-to-end harnesses
";

fn arg_val(args: &[String], flag: &str) -> Option<String> {
    args.iter().position(|a| a == flag).and_then(|i| args.get(i + 1)).cloned()
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(cmd) = args.first().map(|s| s.as_str()) else {
        eprint!("{USAGE}");
        return ExitCode::from(2);
    };
    let rest = &args[1..];
    let r = match cmd {
        "list" => {
            for n in scenarios::names() {
                let s = scenarios::get(n).unwrap();
                println!("{n:26} {:>8.0} s  {}", s.duration_s, s.description);
            }
            Ok(true)
        }
        "run" => cmd_run(rest),
        "all" => cmd_all(rest),
        "mc" => openpatch_sim::montecarlo::cli(rest),
        "report" => openpatch_sim::report::cli(rest),
        "serve" => openpatch_sim::server::cli(rest),
        "-h" | "--help" | "help" => {
            print!("{USAGE}");
            Ok(true)
        }
        _ => {
            eprint!("{USAGE}");
            return ExitCode::from(2);
        }
    };
    match r {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::from(1),
        Err(e) => {
            eprintln!("opsim: {e}");
            ExitCode::from(2)
        }
    }
}

fn cmd_run(args: &[String]) -> Result<bool, String> {
    let name = args.first().ok_or("run: scenario name or file missing")?;
    let mut sc = scenarios::load(name)?;
    if let Some(s) = arg_val(args, "--seed") {
        sc.seed = s.parse().map_err(|_| "bad --seed")?;
    }
    let out = Runner::run(sc)?;
    if let Some(p) = arg_val(args, "--csv") {
        std::fs::write(&p, out.csv()).map_err(|e| format!("{p}: {e}"))?;
    }
    let json = serde_json::to_string_pretty(&out.verdict).map_err(|e| e.to_string())?;
    if let Some(p) = arg_val(args, "--json") {
        std::fs::write(&p, &json).map_err(|e| format!("{p}: {e}"))?;
    }
    if !args.iter().any(|a| a == "--quiet") {
        println!("{json}");
    }
    Ok(out.verdict.passed)
}

fn cmd_all(args: &[String]) -> Result<bool, String> {
    let outdir = arg_val(args, "--outdir");
    if let Some(d) = &outdir {
        std::fs::create_dir_all(d).map_err(|e| format!("{d}: {e}"))?;
    }
    let mut ok = true;
    println!("{:26} {:6} {:>9} {:>9} {:>8}  faults / notes", "scenario", "verdict", "core mU", "needle mU", "err %");
    for n in scenarios::names() {
        let sc = scenarios::get(n)?;
        let out = Runner::run(sc)?;
        let v = &out.verdict;
        let faults: Vec<String> = v.faults.iter().flat_map(|f| f.names.clone()).collect();
        println!(
            "{:26} {:6} {:>9} {:>9.0} {:>8}  {}",
            n,
            if v.passed { "ok" } else { "FAIL" },
            v.core_delivered_mu,
            v.actual_out_mu,
            v.actual_vs_core_pct.map_or("-".into(), |p| format!("{p:+.1}")),
            faults.join(",")
        );
        ok &= v.passed;
        if let Some(d) = &outdir {
            std::fs::write(format!("{d}/{n}.csv"), out.csv()).map_err(|e| e.to_string())?;
            std::fs::write(format!("{d}/{n}.json"), serde_json::to_string_pretty(v).unwrap()).map_err(|e| e.to_string())?;
        }
    }
    Ok(ok)
}
