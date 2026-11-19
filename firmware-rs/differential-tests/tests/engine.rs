//! B. Delivery-engine arithmetic: C `op_de_*` vs Rust `DeliveryEngine` on random schedules, temp
//! basals, boluses, suspend/resume, comm heartbeats, time-of-day changes and ticks of arbitrary
//! length (chunk boundaries at slot edges, temp end, comm-loss edge, midnight wrap), with partial
//! and over-reporting commits. Compared after every operation: steps per tick, accumulator,
//! delivered / scheduled mU, events, remaining values, counters.
//!
//! Calibrations: 26 100 and 8 156 uU/step (the two C presets), arbitrary uU in the sane range, and
//! 0 (uncalibrated: never a step). The engine only needs uU/step, so unlike the whole pump it is
//! not limited to preset calibrations.

use differential_tests::ffi::CEngine;
use differential_tests::rng::Rng;
use openpatch_core::*;
use proptest::prelude::*;

struct Side {
    c: CEngine,
    r: DeliveryEngine,
    uu: u32,
}

fn pulse_cal(uu: u32) -> PulseCal {
    if uu == 0 {
        PulseCal::NONE
    } else {
        PulseCal { uu_num: uu, uu_den: 1, turn_x100: 25_600 }
    }
}

fn err_code(r: Result<(), openpatch_proto::Error>) -> i32 {
    r.map(|_| 0).unwrap_or_else(|e| e.code() as i32)
}

fn rust_snap(e: &DeliveryEngine) -> [u64; 31] {
    let rep = e.report();
    let mut o = [0u64; 31];
    o[0] = e.is_suspended() as u64;
    o[1] = e.temp_active() as u64;
    o[2] = e.temp_rate().0 as u64;
    o[3] = e.temp_remaining().0 as u64;
    o[4] = e.bolus_active() as u64;
    o[5] = e.bolus_remaining().0 as u64;
    o[6] = e.ms_of_day() as u64;
    o[7] = e.ms_since_comm() as u64;
    o[8] = e.accumulator() as u64;
    o[9] = e.scheduled_scaled() as u64;
    o[10] = e.requested_steps().0 as u64;
    o[11] = e.delivered_steps().0 as u64;
    o[12] = e.dropped_steps().0 as u64;
    o[13] = e.pending_steps().0 as u64;
    o[14] = e.current_rate().0 as u64;
    o[15] = e.bolus_remaining().0 as u64;
    o[16] = e.temp_remaining().0 as u64;
    o[17] = rep.scheduled.0 as u64;
    o[18] = rep.delivered.0 as u64;
    o[19] = rep.delivered_steps.0 as u64;
    o[20] = rep.dropped_steps.0 as u64;
    o[21] = e.has_schedule() as u64;
    o[22] = e.schedule().count() as u64;
    for (i, s) in e.schedule().segs.iter().take(8).enumerate() {
        o[23 + i] = ((s.start_slot as u64) << 32) | s.rate.0 as u64;
    }
    o
}

const NAMES: [&str; 31] = [
    "suspended", "temp_active", "temp_rate", "temp_remaining_min", "bolus_active", "bolus_remaining_mu",
    "ms_of_day", "ms_since_comm", "acc", "scheduled_scaled", "requested", "delivered_steps", "dropped",
    "pending", "current_rate", "bolus_remaining_mu(2)", "temp_remaining_min(2)", "report.scheduled_mu",
    "report.delivered_mu", "report.delivered_steps", "report.dropped_steps", "has_schedule", "sched_count",
    "seg0", "seg1", "seg2", "seg3", "seg4", "seg5", "seg6", "seg7",
];

impl Side {
    fn new(uu: u32) -> Side {
        Side { c: CEngine::new(uu), r: DeliveryEngine::new(pulse_cal(uu)), uu }
    }
    fn check(&self, what: &str) -> Result<(), String> {
        let c = self.c.snap();
        let r = rust_snap(&self.r);
        for i in 0..31 {
            if c[i] != r[i] {
                return Err(format!("after {what} (uu={}): {}: C={} Rust={}", self.uu, NAMES[i], c[i] as i64, r[i] as i64));
            }
        }
        Ok(())
    }
}

fn rate(r: &mut Rng) -> u32 {
    match r.below(100) {
        0..=59 => (50 * r.below(100)) as u32,
        60..=79 => r.below(30_001) as u32,
        80..=94 => r.below(120_000) as u32,
        95..=98 => r.below(2_000_000) as u32,
        _ => 0,
    }
}

fn dt(r: &mut Rng) -> u32 {
    match r.below(100) {
        0..=29 => 1000,
        30..=39 => 0,
        40..=44 => 1,
        45..=59 => r.below(5001) as u32,
        60..=69 => *r.pick(&[1_799_999u32, 1_800_000, 1_800_001, 1_799_000, 3_600_000, 900_000]),
        70..=84 => r.below(3_600_000) as u32,
        85..=94 => r.below(20_000_000) as u32,
        _ => r.range(80_000_000, 200_000_000) as u32, // wraps midnight
    }
}

fn schedule(r: &mut Rng) -> Vec<(u8, u32)> {
    let valid = r.chance(800);
    let n = if valid { r.range(1, 24) as usize } else { r.below(26) as usize };
    if valid {
        let mut slots = vec![0u8];
        while slots.len() < n {
            let s = r.range(1, 47) as u8;
            if !slots.contains(&s) {
                slots.push(s);
            }
        }
        slots.sort_unstable();
        slots.into_iter().map(|s| (s, rate(r))).collect()
    } else {
        let n = n.min(24);
        let mut v = Vec::new();
        for i in 0..n {
            let slot = if i == 0 && r.chance(500) { 0 } else { r.below(60) as u8 };
            v.push((slot, rate(r)));
        }
        v
    }
}

fn uu_choice(r: &mut Rng) -> u32 {
    match r.below(10) {
        0..=3 => 26_100,
        4..=6 => 8_156,
        7 => 0,
        8 => 4_000,
        _ => r.range(4_000, 60_000) as u32,
    }
}

pub fn run_engine(seed: u64, n: usize) -> Result<u64, String> {
    let mut r = Rng::new(seed);
    let mut s = Side::new(uu_choice(&mut r));
    s.check("init")?;
    let mut steps_total = 0u64;
    for i in 0..n {
        let what: String;
        match r.below(100) {
            0..=7 => {
                let sch = schedule(&mut r);
                let c = s.c.set_schedule(&sch);
                let rs = match BasalSchedule::from_pairs(&sch) {
                    Some(b) => err_code(s.r.set_schedule(&b)),
                    None => unreachable!("<= 24 segments"),
                };
                what = format!("set_schedule({sch:?}) c={c} r={rs}");
                if c != rs {
                    return Err(format!("step {i}: {what}"));
                }
            }
            8..=11 => {
                let t = if r.chance(800) { r.below(86_400_000) as u32 } else { r.u32() };
                s.c.set_tod(t);
                s.r.set_time_of_day(Millis(t as u64));
                what = format!("set_tod({t})");
            }
            12..=17 => {
                s.c.heartbeat();
                s.r.comm_heartbeat();
                what = "heartbeat".into();
            }
            18..=26 => {
                let rt = rate(&mut r);
                let dur = if r.chance(750) { 30 * r.range(1, 24) as u32 } else { *r.pick(&[0u32, 1, 29, 31, 720, 721, 750, 1000]) };
                let c = s.c.start_temp(rt, dur);
                let rs = err_code(s.r.start_temp_basal(MilliUnitsPerHour(rt), Minutes(dur)));
                what = format!("start_temp({rt},{dur}) c={c} r={rs}");
                if c != rs {
                    return Err(format!("step {i}: {what}"));
                }
            }
            27..=30 => {
                let c = s.c.cancel_temp();
                let rs = s.r.cancel_temp_basal();
                what = format!("cancel_temp c={c} r={rs}");
                if c != rs {
                    return Err(format!("step {i}: {what}"));
                }
            }
            31..=39 => {
                let mu = if r.chance(850) { 50 * r.range(0, 200) as u32 } else { r.u32() / 8 };
                let c = s.c.start_bolus(mu);
                let rs = err_code(s.r.start_bolus(MilliUnits(mu)));
                what = format!("start_bolus({mu}) c={c} r={rs}");
                if c != rs {
                    return Err(format!("step {i}: {what}"));
                }
            }
            40..=43 => {
                let c = s.c.cancel_bolus();
                let rs = s.r.cancel_bolus().0;
                what = format!("cancel_bolus c={c} r={rs}");
                if c != rs {
                    return Err(format!("step {i}: {what}"));
                }
            }
            44..=47 => {
                s.c.suspend();
                s.r.suspend();
                what = "suspend".into();
            }
            48..=55 => {
                s.c.resume();
                s.r.resume();
                what = "resume".into();
            }
            _ => {
                let d = dt(&mut r);
                let c = s.c.tick(d);
                let rs = s.r.tick(Millis(d as u64)).0;
                what = format!("tick({d}) c={c} r={rs}");
                if c != rs {
                    return Err(format!("step {i}: steps per tick differ: {what}"));
                }
                steps_total += c as u64;
                let executed = match r.below(10) {
                    0..=6 => c,
                    7..=8 => if c == 0 { 0 } else { r.below(c as u64 + 1) as u32 },
                    _ => c.saturating_add(r.below(5) as u32),
                };
                s.c.commit(executed);
                s.r.commit(Pulses(executed));
                let (ce, re) = (s.c.take_events(), s.r.take_events().0 as u32);
                if ce != re {
                    return Err(format!("step {i}: events differ after {what}: C={ce:#b} Rust={re:#b}"));
                }
            }
        }
        s.check(&what).map_err(|e| format!("step {i}: {e}"))?;
    }
    Ok(steps_total)
}

proptest! {
    #![proptest_config(ProptestConfig { cases: 1024, max_shrink_iters: 0, failure_persistence: None, ..ProptestConfig::default() })]

    #[test]
    fn random_engine_sequences_match(seed in any::<u64>()) {
        if let Err(e) = run_engine(seed, 300) {
            return Err(TestCaseError::fail(format!("seed {seed}: {e}")));
        }
    }
}

/// Deterministic long run (>= 100 000 engine operations).
#[test]
fn seeded_engine_long_run() {
    let mut steps = 0u64;
    for seed in 1..=400u64 {
        steps += run_engine(0xE16E_0000 + seed, 300).unwrap_or_else(|e| panic!("seed {seed}: {e}"));
    }
    assert!(steps > 10_000, "engine produced too few steps to be meaningful: {steps}");
    println!("engine long run: 120000 ops, {steps} steps requested");
}

/// The accumulator bound the engine documents: |scheduled - delivered| < 1 step, exactly as C.
#[test]
fn exact_accounting_one_day_flat_rate() {
    for uu in [26_100u32, 8_156] {
        let mut s = Side::new(uu);
        s.c.set_schedule(&[(0, 1200)]);
        s.r.set_schedule(&BasalSchedule::flat(MilliUnitsPerHour(1200))).unwrap();
        s.c.resume();
        s.r.resume();
        let mut total = 0u64;
        for _ in 0..86_400 {
            let a = s.c.tick(1000);
            let b = s.r.tick(Millis(1000)).0;
            assert_eq!(a, b);
            s.c.commit(a);
            s.r.commit(Pulses(b));
            total += a as u64;
        }
        s.check("one day").unwrap();
        let expect = 1200u64 * 24 * 1000 / uu as u64; // mU/day * 1000 uU/mU / uU per step
        assert!(total == expect || total + 1 == expect, "uu={uu}: {total} vs {expect}");
    }
}
