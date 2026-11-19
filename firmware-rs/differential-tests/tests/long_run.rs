//! Deterministic seeded long run (xorshift): >= 200 000 operations, reproducible, with coverage
//! statistics printed at the end (run with `-- --nocapture`).

use differential_tests::harness::check_seed;
use differential_tests::pair::Stats;

const BASE_SEEDS: u64 = 400;
/// `DIFF_SOAK=N` multiplies the number of seeds (local soak runs); `DIFF_SEED_BASE` shifts them.
fn soak() -> u64 {
    std::env::var("DIFF_SOAK").ok().and_then(|v| v.parse().ok()).unwrap_or(1)
}
fn seed_base() -> u64 {
    std::env::var("DIFF_SEED_BASE").ok().and_then(|v| v.parse().ok()).unwrap_or(0xC0FF_EE00)
}
/// Every 8th seed is a long run (3000 ops); the others 500 ops: 350*500 + 50*3000 = 325 000 ops.
fn ops_for(seed: u64) -> usize {
    if seed % 8 == 0 { 3000 } else { 500 }
}

#[test]
fn seeded_long_run_matches_c_reference() {
    let mut stats = Stats::default();
    let seeds = BASE_SEEDS * soak();
    for seed in 1..=seeds {
        if let Err(report) = check_seed(seed_base() + seed, ops_for(seed), &mut stats) {
            panic!("{report}");
        }
    }
    assert!(stats.ops >= 200_000, "executed only {} ops", stats.ops);
    assert!(stats.documented_rev_stops * 10 <= seeds, "too many runs truncated by the documented per-rev difference");
    let kinds: Vec<String> = stats.kinds.iter().map(|(t, r)| format!("{t:#04x}:{r}")).collect();
    println!("ops executed:            {}", stats.ops);
    println!("frames sent:             {} (dropped by both, by error code: {:?})", stats.frames, stats.dropped_frames);
    println!("distinct response kinds: {} (cmd:result) {}", stats.kinds.len(), kinds.join(" "));
    println!("fault bits seen:         {:#010b}  newly latched per bit [occl, enc, resv, batt, limit, internal, nocal, wear]: {:?}", stats.fault_bits_seen, stats.fault_bit_counts);
    println!("event types seen:        {:?}", stats.event_types_seen);
    println!("runs ended early at the documented Rust-only per-revolution trip: {} of {seeds}", stats.documented_rev_stops);
    println!("motor steps executed (all runs): {}", stats.steps_all);
    // coverage floor: the generator must reach the interesting corners
    assert!(stats.kinds.len() >= 40, "too few distinct response kinds: {}", stats.kinds.len());
    assert!(stats.fault_bits_seen != 0, "no faults ever seen");
}
