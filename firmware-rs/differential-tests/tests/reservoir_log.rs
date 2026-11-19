//! C. Reservoir model and event log: C `op_res_*` / `op_log_*` vs Rust `Reservoir` / `EventLog`.

use differential_tests::ffi::{CLog, CReservoir};
use differential_tests::rng::Rng;
use openpatch_core::log::EventType;
use openpatch_core::*;
use proptest::prelude::*;

fn cal(uu: u32) -> PulseCal {
    if uu == 0 {
        PulseCal::NONE
    } else {
        PulseCal { uu_num: uu, uu_den: 1, turn_x100: 25_600 }
    }
}

fn code(r: Result<(), Error>) -> i32 {
    r.map(|_| 0).unwrap_or_else(|e| e.code() as i32)
}

fn res_check(c: &CReservoir, r: &Reservoir, what: &str) -> Result<(), String> {
    let cs = c.snap();
    let rs = [
        r.fill_level().0 as u64,
        r.consumed().0 as u64,
        r.is_filled() as u64,
        r.low_threshold().0 as u64,
        r.remaining().0 as u64,
        r.is_empty() as u64,
        r.is_low() as u64,
        r.capacity().0 as u64,
    ];
    let names = ["fill", "consumed", "filled", "low_threshold", "remaining", "empty", "low", "capacity"];
    for i in 0..8 {
        if cs[i] != rs[i] {
            return Err(format!("after {what}: {}: C={} Rust={}", names[i], cs[i], rs[i]));
        }
    }
    Ok(())
}

fn run_reservoir(seed: u64, n: usize) -> Result<(), String> {
    let mut r = Rng::new(seed);
    let cap = *r.pick(&[70_000u32, 100_000, 200_000, 1, 1_000_000, u32::MAX / 2000]);
    let uu = match r.below(6) {
        0 => 26_100,
        1 => 8_156,
        2 => 0,
        3 => 4_000,
        4 => 60_000,
        _ => r.range(1, 70_000) as u32,
    };
    let mut c = CReservoir::new(cap, uu);
    let mut m = Reservoir::new(MilliUnits(cap), cal(uu));
    res_check(&c, &m, "init")?;
    for i in 0..n {
        let what;
        match r.below(10) {
            0..=2 => {
                let mu = match r.below(10) {
                    0 => 0,
                    1 => cap.saturating_add(1),
                    2 => u32::MAX,
                    _ => r.range(1, cap as u64) as u32,
                };
                let (a, b) = (c.fill(mu), code(m.fill(MilliUnits(mu))));
                what = format!("fill({mu}) c={a} r={b}");
                if a != b {
                    return Err(format!("step {i}: {what}"));
                }
            }
            3 => {
                let mu = if r.chance(200) { cap.saturating_add(1) } else { r.range(0, cap as u64) as u32 };
                let (a, b) = (c.set_low(mu), code(m.set_low_threshold(MilliUnits(mu))));
                what = format!("set_low({mu}) c={a} r={b}");
                if a != b {
                    return Err(format!("step {i}: {what}"));
                }
            }
            _ => {
                let st = match r.below(10) {
                    0 => u32::MAX,
                    1 => r.u32(),
                    2..=4 => r.below(10_000) as u32,
                    _ => r.below(200) as u32,
                };
                c.consume(st);
                m.consume(Pulses(st));
                what = format!("consume({st})");
            }
        }
        res_check(&c, &m, &what).map_err(|e| format!("step {i}: {e}"))?;
    }
    Ok(())
}

const KINDS: [EventType; 24] = [
    EventType::Boot, EventType::BolusStart, EventType::BolusDone, EventType::BolusCancel, EventType::TempStart,
    EventType::TempDone, EventType::TempCancel, EventType::TempCommFallback, EventType::BasalSet, EventType::Suspend,
    EventType::Resume, EventType::Fill, EventType::Prime, EventType::Fault, EventType::Ack, EventType::LowReservoir,
    EventType::LowBattery, EventType::Undocked, EventType::Docked, EventType::Activate, EventType::Release,
    EventType::WearWarning, EventType::WearExpired, EventType::Paired,
];

fn run_log(seed: u64, n: usize) -> Result<(), String> {
    let mut r = Rng::new(seed);
    let restore = *r.pick(&[0u32, 1, 2, 1000, u32::MAX - 100, u32::MAX - 5, u32::MAX, 0x8000_0000]);
    let mut c = CLog::new(restore);
    let mut m = EventLog::restore(restore);
    for i in 0..n {
        if r.chance(750) {
            let k = *r.pick(&KINDS);
            let (t, a, b) = (r.u32(), r.u32() as i32, r.u32() as i32);
            let ci = c.append(t, k as u8, a, b);
            let ri = m.append(t, k, a, b);
            if ci != ri {
                return Err(format!("step {i}: append id C={ci} Rust={ri}"));
            }
        } else {
            let from = match r.below(5) {
                0 => 0,
                1 => m.next_id(),
                2 => m.oldest_id().wrapping_add(r.below(10) as u32),
                3 => m.next_id().wrapping_sub(r.below(200) as u32),
                _ => r.u32(),
            };
            let max = r.range(0, 140) as u32;
            let cv = c.read(from, max);
            let mut buf = vec![Event::default(); max.min(128) as usize];
            let k = m.read(from, &mut buf);
            let rv: Vec<[i64; 5]> = buf[..k].iter().map(|e| [e.id as i64, e.time_s as i64, e.kind as i64, e.a as i64, e.b as i64]).collect();
            if cv != rv {
                return Err(format!("step {i}: read(from={from}, max={max}): C={cv:?} Rust={rv:?}"));
            }
        }
        if c.next_id() != m.next_id() || c.oldest_id() != m.oldest_id() {
            return Err(format!("step {i}: next/oldest C=({},{}) Rust=({},{})", c.next_id(), c.oldest_id(), m.next_id(), m.oldest_id()));
        }
    }
    Ok(())
}

proptest! {
    #![proptest_config(ProptestConfig { cases: 1024, max_shrink_iters: 0, failure_persistence: None, ..ProptestConfig::default() })]

    #[test]
    fn reservoir_sequences_match(seed in any::<u64>()) {
        if let Err(e) = run_reservoir(seed, 200) { return Err(TestCaseError::fail(format!("seed {seed}: {e}"))); }
    }

    #[test]
    fn event_log_sequences_match(seed in any::<u64>()) {
        if let Err(e) = run_log(seed, 400) { return Err(TestCaseError::fail(format!("seed {seed}: {e}"))); }
    }
}

#[test]
fn seeded_reservoir_and_log_long_runs() {
    for s in 1..=300u64 {
        run_reservoir(0x5E5E_0000 + s, 300).unwrap_or_else(|e| panic!("reservoir seed {s}: {e}"));
        run_log(0x1061_0000 + s, 600).unwrap_or_else(|e| panic!("log seed {s}: {e}"));
    }
}
