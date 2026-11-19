//! D. Whole-pump differential: identical random operation streams (frames, ticks, dock, charger,
//! battery, actuator health) on the C reference pump and the Rust pump; compared after EVERY op.

use differential_tests::harness::check_seed;
use differential_tests::pair::Stats;
use proptest::prelude::*;

proptest! {
    #![proptest_config(ProptestConfig { cases: 768, max_shrink_iters: 0, failure_persistence: None, ..ProptestConfig::default() })]

    #[test]
    fn random_pump_sequences_match(seed in any::<u64>()) {
        let mut stats = Stats::default();
        if let Err(report) = check_seed(seed, 400, &mut stats) {
            return Err(TestCaseError::fail(report));
        }
    }
}
