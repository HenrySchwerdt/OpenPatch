mod common;
use common::*;

#[test]
fn basal_delivers_expected_pulses() {
    // 1 U/h for 1 h at 26.1 mU/pulse = 38.31 pulses
    let (mut p, h) = running(50_000, 1000);
    run_secs(&mut p, &h, 3600);
    let pulses = p.engine().delivered_steps().0;
    assert!(pulses == 38 || pulses == 39, "{pulses}");
    assert!(p.supervisor().faults().is_empty());
}
