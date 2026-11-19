//! Deterministic seeded long run (xorshift): >= 200 000 operations, reproducible, with coverage
//! statistics printed at the end (run with `-- --nocapture`).

use differential_tests::harness::check_seed;
use differential_tests::pair::Stats;

const SEEDS: u64 = 400;
const OPS_PER_SEED: usize = 600; // 240 000 ops in total

#[test]
fn seeded_long_run_matches_c_reference() {
    let mut stats = Stats::default();
    for seed in 1..=SEEDS {
        if let Err(report) = check_seed(0xC0FF_EE00 + seed, OPS_PER_SEED, &mut stats) {
            panic!("{report}");
        }
    }
    assert!(stats.ops >= 200_000, "executed only {} ops", stats.ops);
    let kinds: Vec<String> = stats.kinds.iter().map(|(t, r)| format!("{t:#04x}:{r}")).collect();
    println!("ops executed:            {}", stats.ops);
    println!("frames sent:             {} (dropped by both, by error code: {:?})", stats.frames, stats.dropped_frames);
    println!("distinct response kinds: {} (cmd:result) {}", stats.kinds.len(), kinds.join(" "));
    println!("fault bits seen:         {:#010b}  newly latched per bit [occl, enc, resv, batt, limit, internal, nocal, wear]: {:?}", stats.fault_bits_seen, stats.fault_bit_counts);
    println!("event types seen:        {:?}", stats.event_types_seen);
    println!("(last run) motor steps executed by C mock: {}", stats.total_steps_c);
    // coverage floor: the generator must reach the interesting corners
    assert!(stats.kinds.len() >= 40, "too few distinct response kinds: {}", stats.kinds.len());
    assert!(stats.fault_bits_seen != 0, "no faults ever seen");
}
