//! Pins every INTENTIONAL difference between the Rust core and the C reference, so that the
//! normalisations in the differential harness cannot hide anything else, and so a change that
//! silently removes one of the differences is noticed too.
//!
//! (1) status DRIVE_CAL ids/ratios, (2) status tags 0x21..0x23 / FW_VERSION / flags bits 11,12,
//! (3) command 0x0F and error codes 26/27, (4) per-revolution angle check, (5) pending-temp stale
//! values (not observable). Rust-only behaviour is tested on the Rust side only.

use differential_tests::desc::CmdDesc;
use differential_tests::gen::{build_frame, payload_of};
use differential_tests::pair::{CalSel, Pair, Setup, Stats};
use openpatch_core::*;
use openpatch_proto::*;

const PAIR: u32 = 0xA1B2_C3D4;

fn setup() -> Setup {
    Setup { cal: CalSel::T26100, capacity: 100_000, next_id: 1 }
}

fn c_frame_roundtrip(p: &mut Pair, seq: u16, d: CmdDesc) -> Result<Vec<u8>, u8> {
    let f = build_frame(PROTO_VERSION, d.ty, 0, seq, &payload_of(&d.encodable()));
    p.c.handle_frame(&f)
}

fn tlvs(frame: &[u8]) -> Vec<(u8, Vec<u8>)> {
    let f = decode_frame(frame).expect("valid frame");
    openpatch_proto::tlv::TlvReader::new(f.payload).map(|t| t.map(|(a, b)| (a, b.to_vec())).unwrap()).collect()
}

fn find(t: &[(u8, Vec<u8>)], tag: u8) -> Option<&Vec<u8>> {
    t.iter().find(|x| x.0 == tag).map(|x| &x.1)
}

#[test]
fn status_differences_are_exactly_the_documented_ones() {
    let mut p = Pair::new(&setup());
    let c = c_frame_roundtrip(&mut p, 1, CmdDesc::new(cmd::GET_STATUS)).unwrap();
    let ct = tlvs(&c);
    // Rust side: encode its own status with the same session semantics
    let st = p.rust_status();
    let mut buf = [0u8; 244];
    let n = encode_response_payload(&Response { type_: 1, seq: 1, status: Some(st), ..Default::default() }, &mut buf).unwrap();
    let rt: Vec<(u8, Vec<u8>)> = openpatch_proto::tlv::TlvReader::new(&buf[..n]).map(|t| t.map(|(a, b)| (a, b.to_vec())).unwrap()).collect();

    // (2) firmware version and Rust-only tags
    assert_eq!(find(&ct, tag::FW_VERSION).unwrap(), &0x0100u16.to_le_bytes().to_vec());
    assert_eq!(find(&rt, tag::FW_VERSION).unwrap(), &0x0200u16.to_le_bytes().to_vec());
    for t in [tag::DRAW_STATE, tag::DRAW_REQUESTED_MU, tag::DRAW_DONE_MU] {
        assert!(find(&ct, t).is_none() && find(&rt, t).is_some(), "tag {t:#x}");
    }
    // (1) drive calibration: ids / steps per rev / ratio differ, uU floor equal
    let (cc, rc) = (find(&ct, tag::DRIVE_CAL).unwrap(), find(&rt, tag::DRIVE_CAL).unwrap());
    assert_eq!(cc[0..2], 1u16.to_le_bytes());
    assert_eq!(rc[0..2], 0x7F01u16.to_le_bytes());
    assert_eq!(cc[2..6], rc[2..6], "uU/step floor must be identical");
    assert_ne!(cc[6..10], rc[6..10]);
    // everything else identical byte for byte
    let strip = |t: &[(u8, Vec<u8>)]| -> Vec<(u8, Vec<u8>)> {
        t.iter()
            .filter(|x| !matches!(x.0, tag::FW_VERSION | tag::DRIVE_CAL | tag::DRAW_STATE | tag::DRAW_REQUESTED_MU | tag::DRAW_DONE_MU | tag::LAST_SEQ | tag::DIAG_SUMMARY | tag::FRU_HEALTH | tag::POD_UID))
            .cloned()
            .collect()
    };
    assert_eq!(strip(&ct), strip(&rt));
}

#[test]
fn assisted_fill_command_is_rust_only_and_new_error_codes_exist_only_in_rust() {
    let mut p = Pair::new(&setup());
    // C: unsupported (result 9, type echoed)
    let mut fd = CmdDesc::new(cmd::ASSISTED_FILL);
    fd.fill_mu = 5000;
    let f = build_frame(PROTO_VERSION, cmd::ASSISTED_FILL, 0, 1, &[tag::FILL_MU, 4, 0x88, 0x13, 0, 0]);
    let _ = fd;
    let c = p.c.handle_frame(&f).expect("C answers");
    assert_eq!(find(&tlvs(&c), tag::RESULT).unwrap(), &vec![9u8]);
    // Rust: docked pod refuses a draw with the Rust-only code 27
    let mut sess = Session::new(NoCrypto, false, [0; 4], true);
    let mut out = [0u8; 256];
    let n = p.r.handle_frame(&mut sess, &f, &mut out).unwrap();
    assert_eq!(find(&tlvs(&out[..n]), tag::RESULT).unwrap(), &vec![27u8]);
    assert_eq!(Error::Docked.code(), 27);
    assert_eq!(Error::PrimeRequired.code(), 26);
}

#[test]
fn strict_config_demands_a_prime_after_fill_rust_only() {
    let hal = differential_tests::rmock::MockHal::new();
    let cal = CalSel::T26100.rust_cal().unwrap();
    let mut r = Pump::new(hal.clone(), Some(&cal), MilliUnits(100_000), 1); // STRICT by default
    r.set_pairing(PAIR, 1).unwrap();
    r.fill(MilliUnits(50_000)).unwrap();
    r.activate(&ActivateArgs { pair_id: PAIR, activation_id: 1, schedule: BasalSchedule::flat(MilliUnitsPerHour(1000)), temp: None })
        .unwrap();
    assert_eq!(r.resume(), Err(Error::PrimeRequired));
    r.prime(Pulses(10)).unwrap();
    assert_eq!(r.resume(), Ok(()));
}

/// (4) A 5 % actuator shortfall: C tolerates 10 % per 1 U window, Rust additionally checks every
/// commanded leadscrew revolution at +-3 %. This is why the shared random streams only use
/// delivered_pct in {100, 50, 0}.
#[test]
fn per_revolution_angle_check_is_rust_only() {
    let mut p = Pair::new(&setup());
    let mut seq = 0u16;
    let mut next = |d: CmdDesc| {
        seq += 1;
        (seq, d)
    };
    // C side via frames
    let mut pairing = CmdDesc::new(cmd::SET_PAIRING);
    pairing.pair_id = PAIR;
    pairing.role = 1;
    let mut fill = CmdDesc::new(cmd::FILL_PRIME);
    fill.sub_op = SUBOP_FILL;
    fill.fill_mu = 50_000;
    let mut act = CmdDesc::new(cmd::ACTIVATE);
    act.pair_id = PAIR;
    act.activation_id = 1;
    act.segs = vec![(0, 1000)];
    let mut bolus = CmdDesc::new(cmd::BOLUS);
    bolus.amount = 10_000;
    for d in [pairing, fill, act, CmdDesc::new(cmd::RESUME), bolus] {
        let (s, d) = next(d);
        p.c_frame(s, d);
    }
    // Rust side directly
    p.r.set_pairing(PAIR, 1).unwrap();
    p.r.fill(MilliUnits(50_000)).unwrap();
    p.r.activate(&ActivateArgs { pair_id: PAIR, activation_id: 1, schedule: BasalSchedule::flat(MilliUnitsPerHour(1000)), temp: None })
        .unwrap();
    p.r.resume().unwrap();
    p.r.bolus(MilliUnits(10_000)).unwrap();
    p.c.set_delivered_pct(95);
    p.rh.st().delivered_pct = 95;
    let mut t = 0u64;
    for _ in 0..420 {
        t += 1000;
        p.c.set_time(t);
        p.rh.st().now_ms = t;
        p.c.tick();
        p.r.tick();
    }
    let c_faults = p.c.snapshot()[0] as u16;
    let r_faults = p.r.supervisor().faults().bits();
    assert_eq!(c_faults, 0, "C tolerates a 5 % shortfall");
    assert_ne!(r_faults & Faults::ENCODER_DEVIATION.bits(), 0, "Rust per-revolution check must fire");
    let _ = Stats::default();
}

/// (6) FINDING-001: a RESPONSE-flagged frame. The C reference opens it as if it were a command (no replay check,
/// heartbeat refreshed); the Rust pod refuses every wrong-direction frame before doing anything else.
#[test]
fn response_flagged_frames_are_refused_by_the_rust_pod_only() {
    let mut p = Pair::new(&setup());
    let f = build_frame(PROTO_VERSION, cmd::GET_STATUS, FLAG_RESPONSE, 1, &[]);
    assert!(p.c.handle_frame(&f).is_ok(), "C answers a RESPONSE-flagged command");
    let mut s = Session::new(NoCrypto, false, [0; 4], true);
    let mut out = [0u8; 256];
    assert_eq!(p.r.handle_frame(&mut s, &f, &mut out), Err(Error::Frame));
}

/// (7) The hourly cap: Rust is a true rolling 60 minutes reduced by `HOURLY_CAL_MARGIN_PCT`; the C reference sums
/// 60 wall-clock minute buckets of exactly 15 U. `PumpConfig::RELAXED` (what the differential harness uses) restores
/// the C accounting; the production STRICT config is tighter.
#[test]
fn strict_hourly_cap_is_tighter_than_the_c_reference() {
    use openpatch_core::limits::*;
    let hal = differential_tests::rmock::MockHal::new();
    let cal = CalSel::T26100.rust_cal().unwrap();
    let strict = Pump::new(hal.clone(), Some(&cal), MilliUnits(100_000), 1);
    let mut relaxed = Pump::new(hal.clone(), Some(&cal), MilliUnits(100_000), 1);
    relaxed.set_config(PumpConfig::RELAXED);
    let (s, r) = (strict.supervisor().hourly_cap_steps().0, relaxed.supervisor().hourly_cap_steps().0);
    assert!(s < r);
    assert_eq!(r, strict.pulse_cal().mu_to_pulses(MAX_HOURLY).0);
    // the physical volume at the worst-case tolerance stays within 15 U
    let uu = strict.pulse_cal().pulses_to_micro(Pulses(s)).0;
    assert!(uu * (100 + HOURLY_CAL_MARGIN_PCT as u64) <= MAX_HOURLY.0 as u64 * 1000 * 100);
}
