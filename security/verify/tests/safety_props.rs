//! Safety-limit properties of the SafetySupervisor (firmware-rs/openpatch-core/src/safety.rs) under ARBITRARY
//! command/time sequences, including an adversary that acknowledges every fault immediately.
//! Rationale: with a fully malicious but *authenticated* phone app, these limits are the last software barrier
//! (docs/02-safety.md H1, spec section 7). Run: `cargo test --release` in security/verify.
use openpatch_core::drive_cal;
use openpatch_core::limits::*;
use openpatch_core::safety::SafetySupervisor;
use openpatch_core::units::*;
use openpatch_core::Faults;
use proptest::prelude::*;

const MINUTE: u64 = 60_000;
const HOUR: u64 = 3_600_000;

fn cals() -> Vec<PulseCal> {
    // Every production preset (test calibrations are not linked in this build).
    drive_cal::PRESETS.iter().map(|p| p.cal()).filter(|c| cal_in_range(*c)).collect()
}

fn supervisor(cal: PulseCal) -> SafetySupervisor {
    let mut s = SafetySupervisor::new(Millis(0), AngleCounts(0), cal);
    s.set_docked(true);
    s.set_active(true);
    s
}

#[derive(Clone, Debug)]
enum Op {
    Approve { dt_ms: u64, requested: u32, reservoir_mu: u32 },
    AckAll,
}

fn op() -> impl Strategy<Value = Op> {
    prop_oneof![
        8 => (0u64..=5 * MINUTE, 0u32..=6000, 0u32..=200_000).prop_map(|(d, r, m)| Op::Approve { dt_ms: d, requested: r, reservoir_mu: m }),
        2 => Just(Op::AckAll),
    ]
}

/// Replay the ops, return (timeline of (t_ms, approved), cal).
fn run(cal: PulseCal, ops: &[Op]) -> (Vec<(u64, u32)>, u32, u32) {
    let mut s = supervisor(cal);
    let mut t = 0u64;
    let mut timeline = Vec::new();
    let per_min = cal.mu_to_pulses(MAX_PER_MIN).0;
    let cap = s.hourly_cap_steps().0; // MAX_HOURLY less the calibration tolerance margin
    for o in ops {
        match o {
            Op::Approve { dt_ms, requested, reservoir_mu } => {
                t += dt_ms;
                let got = s.approve_steps(Millis(t), Pulses(*requested), MilliUnits(*reservoir_mu)).0;
                assert!(got <= *requested, "approved more than requested");
                assert!(got <= cal.mu_to_pulses(MilliUnits(*reservoir_mu)).0, "approved more than the reservoir holds");
                timeline.push((t, got));
            }
            Op::AckAll => {
                let _ = s.acknowledge(Faults::LIMIT_EXCEEDED | Faults::RESERVOIR_EMPTY);
            }
        }
    }
    (timeline, per_min, cap)
}

fn window_sum(tl: &[(u64, u32)], from: u64, to_excl: u64) -> u64 {
    tl.iter().filter(|(t, _)| *t >= from && *t < to_excl).map(|(_, n)| *n as u64).sum()
}

proptest! {
    #![proptest_config(ProptestConfig { cases: 2000, .. ProptestConfig::default() })]

    /// P1: per wall-clock minute never more than MAX_PER_MIN (1.7 U) is approved.
    #[test]
    fn p1_per_minute_cap(ops in proptest::collection::vec(op(), 1..200), ci in 0usize..8) {
        let cs = cals(); let cal = cs[ci % cs.len()];
        let (tl, per_min, _) = run(cal, &ops);
        let mut minutes = std::collections::BTreeMap::<u64, u64>::new();
        for (t, n) in &tl { *minutes.entry(t / MINUTE).or_default() += *n as u64; }
        for (m, sum) in minutes { prop_assert!(sum <= per_min as u64, "minute {m}: {sum} > {per_min}"); }
    }

    /// P2: in any 60 consecutive wall-clock minutes never more than MAX_HOURLY (15 U) is approved.
    #[test]
    fn p2_wall_clock_hour_cap(ops in proptest::collection::vec(op(), 1..200), ci in 0usize..8) {
        let cs = cals(); let cal = cs[ci % cs.len()];
        let (tl, _, cap) = run(cal, &ops);
        for (t, _) in &tl {
            let m = t / MINUTE;
            let start = m.saturating_sub(59) * MINUTE;
            let sum = window_sum(&tl, start, (m + 1) * MINUTE);
            prop_assert!(sum <= cap as u64, "wall-clock hour ending minute {m}: {sum} > {cap}");
        }
    }

    /// P3: in ANY sliding real-time 60 minute window at most the hourly cap (MAX_HOURLY less the calibration
    /// tolerance margin, i.e. <= 15 U physical) is approved. (FINDING-003 fixed: the old wall-clock buckets allowed 16.7 U.)
    #[test]
    fn p3_sliding_hour_bound(ops in proptest::collection::vec(op(), 1..200), ci in 0usize..8) {
        let cs = cals(); let cal = cs[ci % cs.len()];
        let (tl, _per_min, cap) = run(cal, &ops);
        for (t, _) in &tl {
            // every window [t, t + 60 min) and the window ending at t
            let sum = window_sum(&tl, *t, *t + HOUR);
            prop_assert!(sum <= cap as u64, "sliding hour from {t}: {sum} > {cap}");
            let back = window_sum(&tl, t.saturating_sub(HOUR - 1), *t + 1);
            prop_assert!(back <= cap as u64, "sliding hour ending {t}: {back} > {cap}");
        }
    }

    /// P4: check_bolus accepts only amounts <= the configured and the hard maximum, granular, within the reservoir.
    #[test]
    fn p4_bolus_check(max_bolus in 0u32..=60_000, max_basal in 0u32..=60_000, amount in 0u32..=60_000, res in 0u32..=250_000, ci in 0usize..8) {
        let cs = cals(); let cal = cs[ci % cs.len()];
        let mut s = supervisor(cal);
        let cfg = s.configure(MilliUnits(max_bolus), MilliUnitsPerHour(max_basal));
        if max_bolus == 0 || max_basal == 0 || max_bolus > HARD_MAX_BOLUS.0 || max_basal > HARD_MAX_BASAL.0 {
            prop_assert!(cfg.is_err(), "configure accepted a value above a hard limit");
        }
        if s.check_bolus(Millis(0), MilliUnits(amount), MilliUnits(res)).is_ok() {
            prop_assert!(amount > 0 && amount % BOLUS_GRANULARITY.0 == 0);
            prop_assert!(amount <= s.max_bolus().0 && amount <= HARD_MAX_BOLUS.0 && amount <= res);
            prop_assert!(cal.mu_to_pulses(MilliUnits(amount)).0 <= cal.mu_to_pulses(MAX_HOURLY).0);
        }
    }

    /// P5: temp basal / basal rates above the configured / hard maximum are never accepted.
    #[test]
    fn p5_rate_check(max_basal in 1u32..=30_000, rate in 0u32..=80_000, dur in 0u32..=1000, ci in 0usize..8) {
        let cs = cals(); let cal = cs[ci % cs.len()];
        let mut s = supervisor(cal);
        s.configure(MilliUnits(1000), MilliUnitsPerHour(max_basal)).unwrap();
        if s.check_temp_basal(MilliUnitsPerHour(rate), Minutes(dur)).is_ok() {
            prop_assert!(rate <= s.max_basal().0 && rate <= HARD_MAX_BASAL.0);
            prop_assert!(dur > 0 && dur <= TEMP_MAX_MIN && dur % TEMP_GRANULARITY_MIN == 0);
        }
    }
}

/// FINDING-003 (low) -- FIXED. The "rolling 60 minute" limit used to be 60 wall-clock minute buckets: a full per-minute
/// budget taken at the end of minute 0 and again at the start of minute 60 gave MAX_HOURLY + MAX_PER_MIN = 16.7 U in
/// 59 minutes. The supervisor now sums 10 s buckets over the newest 361 of them (a true rolling bound) and the cap is
/// reduced by the calibration tolerance margin. This is the exact boundary attack of the finding: it must now be refused.
#[test]
fn fixed_finding_003_sliding_window_never_exceeds_the_hourly_cap() {
    let cal = drive_cal::NFP_608_2645_G15_12.cal();
    let mut s = supervisor(cal);
    let cap = s.hourly_cap_steps().0;
    assert!(cap < cal.mu_to_pulses(MAX_HOURLY).0, "the cap carries the calibration tolerance margin");
    let per_min = cal.mu_to_pulses(MAX_PER_MIN).0;
    let mut tl = Vec::new();
    let mut go = |t: u64, req: u32, tl: &mut Vec<(u64, u32)>| {
        let n = s.approve_steps(Millis(t), Pulses(req), MilliUnits(200_000)).0;
        let _ = s.acknowledge(Faults::LIMIT_EXCEEDED);
        tl.push((t, n));
        n
    };
    // the attack: a full per-minute budget as late as possible in minute 0, then everything the window allows ...
    let m0 = go(59_900, per_min, &mut tl);
    assert_eq!(m0, per_min);
    let mut got = m0;
    for m in 1..60u64 {
        got += go(m * MINUTE + 1_000, per_min, &mut tl);
    }
    assert_eq!(got, cap, "the first 59 minutes fill the cap exactly");
    // ... and the same again just after minute 60 starts: minute 0's steps are still inside a real hour
    let late = go(60 * MINUTE + 100, per_min, &mut tl);
    assert_eq!(late, 0, "FINDING-003: the old bucket window released a whole minute early");
    let total: u64 = window_sum(&tl, 59_900, 60 * MINUTE + 101);
    assert!(total <= cap as u64);
    // once the 10 s bucket of the first approval has really aged out, delivery continues
    let after = go(59_900 + HOUR + 10_000, per_min, &mut tl);
    assert!(after > 0, "the window must not stay closed longer than an hour (+ one bucket)");
}
