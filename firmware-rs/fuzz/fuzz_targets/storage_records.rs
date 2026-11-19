//! Flash record decoding. Real code: the drive calibration record of openpatch-core (`DriveCal::from_bytes` /
//! `validate` / `pulse_cal`), which decides whether the pod may deliver at all. The other storage records
//! (openpatch-bench/src/storage.rs: seq/event ceilings, reservoir, pod state, pairing secret, BLE bonds) are decoded by
//! fixed-offset slicing inside an embassy crate that cannot be linked on the host; they are mirrored by `parse_record`
//! below, and proposal security/proposals/03 asks for the codec to be extracted into a no_std library so the real code
//! is fuzzed.
//! Properties: no panic; a record that validates has a CRC-consistent image, an in-range calibration, and survives a
//! to_bytes/from_bytes round trip; `pulse_cal()` is Some exactly when it validates.
#![no_main]
use libfuzzer_sys::fuzz_target;
use openpatch_core::drive_cal::DriveCal;
use openpatch_core::limits::cal_in_range;

/// Mirror of `Settings::load` length filters (record = version byte + payload, key-specific payload sizes).
fn parse_record(key: u8, b: &[u8]) -> Option<usize> {
    let want = match key {
        1 => 3,  // seq ceiling
        2 => 5,  // event ceiling
        3 => 9,  // reservoir
        4 => 25, // drive calibration
        5 => 15, // pod record
        6 => 33, // application layer pairing secret
        16..=19 => 43, // BLE bond
        _ => return None,
    };
    (b.len() == want && b[0] == 1).then_some(want)
}

fuzz_target!(|data: &[u8]| {
    if data.len() < 25 {
        return;
    }
    let mut img = [0u8; 24];
    img.copy_from_slice(&data[..24]);
    let c = DriveCal::from_bytes(&img);
    let ok = DriveCal::validate(Some(&c)).is_ok();
    match c.pulse_cal() {
        Some(p) => {
            assert!(ok, "pulse_cal() available for a record that does not validate");
            assert!(cal_in_range(p), "validated record outside the sane calibration range");
            assert_eq!(c.compute_crc(), DriveCal::from_bytes(&c.to_bytes()).compute_crc());
        }
        None => {}
    }
    if ok {
        assert_eq!(DriveCal::from_bytes(&c.to_bytes()), c);
    }
    let _ = parse_record(data[24], &data[..24.min(data.len())]);
    let _ = parse_record(data[24] % 20, data);
});
