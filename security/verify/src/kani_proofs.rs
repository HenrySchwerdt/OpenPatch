//! Kani (CBMC) proofs for the safety-critical, panic-free properties of openpatch-proto / openpatch-core.
//! Run: `cd security/verify && cargo kani` (all harnesses) or `cargo kani --harness proof_approve_steps_bounds`.
//! Bounds are explicit (input sizes) and stated in each harness: this is bounded model checking, not an unbounded proof; the
//! unbounded statements are covered by the proptests in tests/ and by the fuzz targets.
use openpatch_core::drive_cal;
use openpatch_core::limits::*;
use openpatch_core::safety::SafetySupervisor;
use openpatch_core::units::*;
use openpatch_proto::tlv::TlvReader;
use openpatch_proto::{decode_command, decode_frame, NoCrypto, Session, FRAME_HEADER, FRAME_CRC};

fn supervisor() -> (SafetySupervisor, PulseCal) {
    let cal = drive_cal::NFP_608_2645_G15_12.cal();
    let mut s = SafetySupervisor::new(Millis(0), AngleCounts(0), cal);
    s.set_docked(true);
    s.set_active(true);
    (s, cal)
}

/// TLV reader: for ANY input of up to 10 bytes it terminates within len+1 items and never panics or reads out of bounds.
#[kani::proof]
#[kani::unwind(14)]
fn proof_tlv_reader_total() {
    let buf: [u8; 10] = kani::any();
    let n: usize = kani::any();
    kani::assume(n <= 10);
    let mut count = 0usize;
    for item in TlvReader::new(&buf[..n]) {
        count += 1;
        assert!(count <= n + 1);
        if let Ok((_, v)) = item {
            assert!(v.len() <= n);
        }
    }
}

/// Frame decoder: for any input of up to 16 bytes, no panic, and an accepted frame is internally consistent
/// (payload length + header + CRC == input length).
#[kani::proof]
#[kani::unwind(20)]
fn proof_decode_frame_total() {
    let buf: [u8; 16] = kani::any();
    let n: usize = kani::any();
    kani::assume(n <= 16);
    if let Ok(f) = decode_frame(&buf[..n]) {
        assert_eq!(FRAME_HEADER + f.payload.len() + FRAME_CRC, n);
    }
}

/// Command decoder never panics for any type byte and up to 12 payload bytes.
#[kani::proof]
#[kani::unwind(16)]
fn proof_decode_command_total() {
    let t: u8 = kani::any();
    let seq: u16 = kani::any();
    let p: [u8; 12] = kani::any();
    let n: usize = kani::any();
    kani::assume(n <= 12);
    let _ = decode_command(t, seq, &p[..n]);
}

/// Replay state machine of the plaintext (development) session: for any two frames of up to 12 bytes, the second accepted
/// command seq is strictly greater than the first. (The encrypted path has the same replay logic after the AEAD check.)
#[kani::proof]
#[kani::unwind(20)]
fn proof_session_replay_monotonic() {
    let mut s: Session<NoCrypto> = Session::new(NoCrypto, false, [0; 4], true);
    let a: [u8; 12] = kani::any();
    let b: [u8; 12] = kani::any();
    let (la, lb): (usize, usize) = (kani::any(), kani::any());
    kani::assume(la <= 12 && lb <= 12);
    let mut p1 = [0u8; 244];
    let mut p2 = [0u8; 244];
    let first = s.open(&a[..la], &mut p1).map(|o| (o.seq, o.flags & 2 != 0));
    let second = s.open(&b[..lb], &mut p2).map(|o| (o.seq, o.flags & 2 != 0));
    if let (Ok((s1, false)), Ok((s2, false))) = (first, second) {
        assert!(s2 > s1);
    }
}

/// Step veto: from a fresh supervisor, for ANY time, request and reservoir, one approval never exceeds the request, the
/// reservoir, the per-minute cap or the hourly cap.
#[kani::proof]
#[kani::unwind(70)]
fn proof_approve_steps_bounds() {
    let (mut s, cal) = supervisor();
    let now: u64 = kani::any();
    kani::assume(now < 10 * 3_600_000);
    let requested: u32 = kani::any();
    kani::assume(requested <= 100_000);
    let reservoir: u32 = kani::any();
    kani::assume(reservoir <= 200_000);
    let got = s.approve_steps(Millis(now), Pulses(requested), MilliUnits(reservoir)).0;
    assert!(got <= requested);
    assert!(got <= cal.mu_to_pulses(MilliUnits(reservoir)).0);
    assert!(got <= cal.mu_to_pulses(MAX_PER_MIN).0);
    assert!(got <= cal.mu_to_pulses(MAX_HOURLY).0);
}

/// Two approvals inside the same wall-clock minute never exceed the per-minute cap together.
#[kani::proof]
#[kani::unwind(70)]
fn proof_approve_steps_two_calls_same_minute() {
    let (mut s, cal) = supervisor();
    let t1: u64 = kani::any();
    kani::assume(t1 < 3_600_000);
    let d: u64 = kani::any();
    kani::assume(d < 60_000 && (t1 / 60_000) == ((t1 + d) / 60_000));
    let r1: u32 = kani::any();
    let r2: u32 = kani::any();
    kani::assume(r1 <= 100_000 && r2 <= 100_000);
    let a = s.approve_steps(Millis(t1), Pulses(r1), MilliUnits(200_000)).0;
    let b = s.approve_steps(Millis(t1 + d), Pulses(r2), MilliUnits(200_000)).0;
    assert!(a as u64 + b as u64 <= cal.mu_to_pulses(MAX_PER_MIN).0 as u64);
}

/// check_bolus never accepts more than the hard maximum, for any configured maximum and any amount.
#[kani::proof]
#[kani::unwind(70)]
fn proof_check_bolus_hard_limit() {
    let (mut s, _) = supervisor();
    let maxb: u32 = kani::any();
    let maxr: u32 = kani::any();
    let _ = s.configure(MilliUnits(maxb), MilliUnitsPerHour(maxr));
    let amount: u32 = kani::any();
    let reservoir: u32 = kani::any();
    if s.check_bolus(Millis(0), MilliUnits(amount), MilliUnits(reservoir)).is_ok() {
        assert!(amount <= HARD_MAX_BOLUS.0);
        assert!(amount <= reservoir);
        assert!(amount % BOLUS_GRANULARITY.0 == 0 && amount > 0);
    }
}

/// configure() never stores a value above the hard caps.
#[kani::proof]
fn proof_configure_hard_caps() {
    let (mut s, _) = supervisor();
    let maxb: u32 = kani::any();
    let maxr: u32 = kani::any();
    if s.configure(MilliUnits(maxb), MilliUnitsPerHour(maxr)).is_ok() {
        assert!(s.max_bolus().0 <= HARD_MAX_BOLUS.0 && s.max_basal().0 <= HARD_MAX_BASAL.0);
        assert!(s.max_bolus().0 > 0 && s.max_basal().0 > 0);
    }
}
