//! Bench test mode (water only): pulse sequences paced through the normal bolus path.
mod common;
use common::*;
use openpatch_core::bench::*;
use openpatch_core::limits::*;
use openpatch_core::*;

fn strict_pump() -> (Pump<MockHal>, MockHal) {
    let hal = MockHal::new();
    let cal = cal_test();
    let p = Pump::new(hal.clone(), Some(&cal), CAPACITY_100, 1); // STRICT: priming mandatory
    (p, hal)
}

fn drive(p: &mut Pump<MockHal>, h: &MockHal, r: &mut BenchRunner, max_s: u64) -> (Vec<CsvRow>, BenchEvent) {
    let mut rows = Vec::new();
    let mut last = BenchEvent::None;
    for _ in 0..max_s {
        h.advance_ms(1000);
        p.tick();
        let ev = r.step(p, Millis(h.0.borrow().now_ms));
        match ev {
            BenchEvent::Row(row) => rows.push(row),
            BenchEvent::Finished | BenchEvent::Failed(_) => {
                last = ev;
                break;
            }
            BenchEvent::None => {}
        }
    }
    (rows, last)
}

#[test]
fn bench_prepare_primes_and_resumes_under_strict_config() {
    let (mut p, _h) = strict_pump();
    prepare(&mut p, MilliUnits(50_000)).unwrap();
    assert!(!p.engine().is_suspended());
    assert!(!p.prime_required());
    assert!(p.pod().active);
}

#[test]
fn bench_sequence_delivers_n_pulses_and_logs_csv() {
    let (mut p, h) = strict_pump();
    prepare(&mut p, MilliUnits(50_000)).unwrap();
    let mut r = BenchRunner::new(BenchConfig { pulses: 3, amount: MilliUnits(500), pause: Millis(2000) }).unwrap();
    let (rows, last) = drive(&mut p, &h, &mut r, 600);
    assert_eq!(last, BenchEvent::Finished);
    assert_eq!(rows.len(), 3);
    assert_eq!(rows[2].cmd_mu, 1500);
    // delivered within one step of commanded (26.1 mU/step)
    assert!(rows[2].delivered_mu.abs_diff(1500) <= 27, "{}", rows[2].delivered_mu);
    assert!(rows[2].delivered_steps > rows[0].delivered_steps);
    let mut s = String::new();
    rows[0].write_csv(&mut s).unwrap();
    assert_eq!(s.split(',').count(), CSV_HEADER.split(',').count());
    assert!(r.is_finished());
    assert_eq!(r.step(&mut p, Millis(0)), BenchEvent::Finished);
}

#[test]
fn bench_config_validation() {
    assert!(BenchRunner::new(BenchConfig { pulses: 0, amount: MilliUnits(500), pause: Millis(0) }).is_err());
    assert!(BenchRunner::new(BenchConfig { pulses: 1, amount: MilliUnits(0), pause: Millis(0) }).is_err());
    assert!(BenchRunner::new(BenchConfig { pulses: 1, amount: MilliUnits(525), pause: Millis(0) }).is_err());
}

#[test]
fn bench_hourly_limit_stays_active_and_fails_the_run() {
    let (mut p, h) = strict_pump();
    prepare(&mut p, MilliUnits(100_000)).unwrap();
    // 10 U pulses: the 15 U/h cap refuses the second one
    let mut r = BenchRunner::new(BenchConfig { pulses: 3, amount: MilliUnits(10_000), pause: Millis(0) }).unwrap();
    let (_rows, last) = drive(&mut p, &h, &mut r, 1200);
    assert_eq!(last, BenchEvent::Failed(Error::Hourly));
    assert_eq!(r.state(), BenchState::Failed(Error::Hourly));
}

#[test]
fn bench_abort_cancels_the_running_bolus() {
    let (mut p, h) = strict_pump();
    prepare(&mut p, MilliUnits(50_000)).unwrap();
    let mut r = BenchRunner::new(BenchConfig { pulses: 2, amount: MilliUnits(5000), pause: Millis(0) }).unwrap();
    for _ in 0..5 {
        h.advance_ms(1000);
        p.tick();
        r.step(&mut p, Millis(h.0.borrow().now_ms));
    }
    assert!(p.engine().bolus_active());
    r.abort(&mut p);
    assert!(!p.engine().bolus_active());
    assert!(r.is_finished());
    assert_eq!(r.config().pulses, 2);
}

#[test]
fn bench_fault_during_sequence_fails_it() {
    let (mut p, h) = strict_pump();
    prepare(&mut p, MilliUnits(50_000)).unwrap();
    let mut r = BenchRunner::new(BenchConfig { pulses: 2, amount: MilliUnits(2000), pause: Millis(0) }).unwrap();
    h.st().delivered_pct = 0; // jammed: occlusion
    let (_rows, last) = drive(&mut p, &h, &mut r, 600);
    assert_eq!(last, BenchEvent::Failed(Error::Fault));
}
