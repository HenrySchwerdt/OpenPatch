//! Signed images only, verify before swap, rollback protection, DFU receiver rules, with REAL Ed25519 and SHA-512.
use ed25519_dalek::{Signer, SigningKey, VerifyingKey};
use openpatch_boot_policy::counter::*;
use openpatch_boot_policy::dfu::*;
use openpatch_boot_policy::manifest::*;
use openpatch_boot_policy::verify::Context;
use openpatch_boot_policy::*;
use sha2::{Digest, Sha512};

struct Sha(Sha512);
impl Digest512 for Sha {
    fn new() -> Self {
        Sha(Sha512::new())
    }
    fn update(&mut self, d: &[u8]) {
        Digest::update(&mut self.0, d);
    }
    fn finish(self) -> [u8; 64] {
        self.0.finalize().into()
    }
}
struct Key(VerifyingKey);
impl SigCheck for Key {
    fn verify(&self, digest: &[u8; 64], sig: &[u8; 64]) -> bool {
        use ed25519_dalek::Verifier;
        self.0.verify(digest, &ed25519_dalek::Signature::from_bytes(sig)).is_ok()
    }
}
struct Mem(Vec<u8>);
impl ImageSource for Mem {
    fn read(&mut self, off: u32, buf: &mut [u8]) -> bool {
        let o = off as usize;
        if o + buf.len() > self.0.len() {
            return false;
        }
        buf.copy_from_slice(&self.0[o..o + buf.len()]);
        true
    }
}

const MAX: u32 = 0x76000;
const EMPTY: [u32; SLOTS] = [0xFFFF_FFFF; SLOTS];

fn sk() -> SigningKey {
    SigningKey::from_bytes(&[7u8; 32])
}
fn image(n: usize) -> Vec<u8> {
    (0..n).map(|i| (i * 31 + 7) as u8).collect()
}
fn sign(key: &SigningKey, img: &[u8], version: u32, hw: u32) -> [u8; MANIFEST_LEN] {
    let mut m = Manifest { image_len: img.len() as u32, version, hw_id: hw, signature: [0; 64] };
    let mut h = Sha512::new();
    Digest::update(&mut h, DOMAIN);
    Digest::update(&mut h, m.header());
    Digest::update(&mut h, img);
    let d: [u8; 64] = h.finalize().into();
    m.signature = key.sign(&d).to_bytes();
    m.encode()
}
fn check(manifest: &[u8], img: &[u8], key: Option<&Key>, slots: &[u32; SLOTS]) -> Result<ArmToken, Reject> {
    let ctx = Context { verifier: key, hw_id: HW_ID_CUP_V4, max_image: MAX, counter_slots: slots };
    verify_pending::<Sha, Key, Mem>(manifest, &mut Mem(img.to_vec()), &ctx)
}
fn pubkey() -> Key {
    Key(sk().verifying_key())
}

// ---- signed images only ------------------------------------------------------------------------------------------

#[test]
fn a_correctly_signed_image_is_accepted() {
    let img = image(10_000);
    let m = sign(&sk(), &img, 3, HW_ID_CUP_V4);
    let t = check(&m, &img, Some(&pubkey()), &EMPTY).unwrap();
    assert_eq!((t.version(), t.image_len()), (3, 10_000));
}

#[test]
fn an_unsigned_or_wrongly_signed_image_is_refused() {
    let img = image(5_000);
    let good = sign(&sk(), &img, 1, HW_ID_CUP_V4);
    // signed by another key
    let other = sign(&SigningKey::from_bytes(&[9u8; 32]), &img, 1, HW_ID_CUP_V4);
    assert_eq!(check(&other, &img, Some(&pubkey()), &EMPTY), Err(Reject::BadSignature));
    // zero signature
    let mut zero = good;
    zero[20..].fill(0);
    assert_eq!(check(&zero, &img, Some(&pubkey()), &EMPTY), Err(Reject::BadSignature));
    // a flipped bit in the signature
    let mut flip = good;
    flip[30] ^= 1;
    assert_eq!(check(&flip, &img, Some(&pubkey()), &EMPTY), Err(Reject::BadSignature));
}

#[test]
fn any_changed_image_byte_is_refused() {
    let img = image(3_000);
    let m = sign(&sk(), &img, 1, HW_ID_CUP_V4);
    for pos in [0usize, 1, 255, 256, 1_500, 2_999] {
        let mut bad = img.clone();
        bad[pos] ^= 0x01;
        assert_eq!(check(&m, &bad, Some(&pubkey()), &EMPTY), Err(Reject::BadSignature), "byte {pos}");
    }
}

#[test]
fn the_header_is_signed_too() {
    // raising the version, changing the hardware id or the length in the manifest breaks the signature
    let img = image(4_000);
    let m = sign(&sk(), &img, 5, HW_ID_CUP_V4);
    let mut v = m;
    v[12] = 9; // version 5 -> 9: an attacker cannot lift an old image over the counter (or lower a new one)
    assert_eq!(check(&v, &img, Some(&pubkey()), &EMPTY), Err(Reject::BadSignature));
    let mut short = m;
    short[8..12].copy_from_slice(&3_999u32.to_le_bytes());
    assert_eq!(check(&short, &img, Some(&pubkey()), &EMPTY), Err(Reject::BadSignature));
    // a manifest for another board, correctly signed for THAT board, is refused on ours
    let other_hw = sign(&sk(), &img, 5, 0x1234);
    assert_eq!(check(&other_hw, &img, Some(&pubkey()), &EMPTY), Err(Reject::WrongHardware { got: 0x1234 }));
    // and the hw id cannot be patched to ours
    let mut patched = other_hw;
    patched[16..20].copy_from_slice(&HW_ID_CUP_V4.to_le_bytes());
    assert_eq!(check(&patched, &img, Some(&pubkey()), &EMPTY), Err(Reject::BadSignature));
}

#[test]
fn a_v1_style_signature_over_the_image_alone_does_not_verify_as_v2() {
    let img = image(2_000);
    let d: [u8; 64] = Sha512::digest(&img).into();
    let sig = sk().sign(&d).to_bytes();
    let mut m = Manifest { image_len: 2_000, version: 1, hw_id: HW_ID_CUP_V4, signature: sig }.encode();
    assert_eq!(check(&m, &img, Some(&pubkey()), &EMPTY), Err(Reject::BadSignature));
    // and a real format 1 manifest is refused outright
    m[4] = 1;
    assert_eq!(check(&m, &img, Some(&pubkey()), &EMPTY), Err(Reject::Manifest(ManifestError::Format)));
}

#[test]
fn no_key_compiled_in_refuses_everything() {
    let img = image(1_000);
    let m = sign(&sk(), &img, 1, HW_ID_CUP_V4);
    assert_eq!(check(&m, &img, None, &EMPTY), Err(Reject::NoKey));
}

#[test]
fn size_and_read_errors() {
    let img = image(1_000);
    let big = Manifest { image_len: MAX + 1, version: 1, hw_id: HW_ID_CUP_V4, signature: [0; 64] }.encode();
    assert_eq!(check(&big, &img, Some(&pubkey()), &EMPTY), Err(Reject::TooLarge));
    // the manifest claims more bytes than the partition delivers
    let m = sign(&sk(), &image(2_000), 1, HW_ID_CUP_V4);
    assert_eq!(check(&m, &img, Some(&pubkey()), &EMPTY), Err(Reject::ReadError));
    assert_eq!(check(&m[..40], &img, Some(&pubkey()), &EMPTY), Err(Reject::Manifest(ManifestError::Length)));
}

#[test]
fn manifest_field_rules() {
    let mut m = Manifest { image_len: 10, version: 1, hw_id: 1, signature: [0; 64] }.encode();
    assert!(Manifest::parse(&m).is_ok());
    m[0] ^= 1;
    assert_eq!(Manifest::parse(&m), Err(ManifestError::Magic));
    let mut m = Manifest { image_len: 10, version: 1, hw_id: 1, signature: [0; 64] }.encode();
    m[6] = 1;
    assert_eq!(Manifest::parse(&m), Err(ManifestError::Reserved));
    assert_eq!(Manifest::parse(&Manifest { image_len: 0, version: 1, hw_id: 1, signature: [0; 64] }.encode()), Err(ManifestError::ZeroLength));
    assert_eq!(Manifest::parse(&Manifest { image_len: 1, version: 0, hw_id: 1, signature: [0; 64] }.encode()), Err(ManifestError::ZeroVersion));
    let m = Manifest { image_len: 77, version: 4, hw_id: 9, signature: [5; 64] };
    assert_eq!(Manifest::parse(&m.encode()), Ok(m));
}

// ---- rollback protection --------------------------------------------------------------------------------------------

fn slots_with(versions: &[u32]) -> [u32; SLOTS] {
    let mut s = EMPTY;
    for (i, v) in versions.iter().enumerate() {
        s[i] = !v;
    }
    s
}

#[test]
fn an_older_image_is_refused_a_same_or_newer_one_accepted() {
    let img = image(2_000);
    let slots = slots_with(&[2, 5]);
    for (v, ok) in [(1u32, false), (4, false), (5, true), (6, true), (100, true)] {
        let m = sign(&sk(), &img, v, HW_ID_CUP_V4);
        let r = check(&m, &img, Some(&pubkey()), &slots);
        if ok {
            assert!(r.is_ok(), "version {v}");
        } else {
            assert_eq!(r.unwrap_err(), Reject::Rollback { version: v, minimum: 5 }, "version {v}");
        }
    }
}

#[test]
fn rollback_is_checked_before_the_expensive_signature() {
    // an old image with a garbage signature is a Rollback, not a BadSignature: the cheap check ran first
    let img = image(2_000);
    let mut m = sign(&sk(), &img, 1, HW_ID_CUP_V4);
    m[20..].fill(0xAA);
    assert!(matches!(check(&m, &img, Some(&pubkey()), &slots_with(&[3])), Err(Reject::Rollback { .. })));
}

#[test]
fn counter_encoding_and_minimum() {
    assert_eq!(min_version(&EMPTY), Ok(0));
    assert_eq!(min_version(&slots_with(&[1])), Ok(1));
    assert_eq!(min_version(&slots_with(&[1, 3, 4, 10])), Ok(10));
    assert_eq!(UICR_CUSTOMER_ADDR, 0x1000_1080);
}

#[test]
fn counter_shape_violations_are_corrupt_and_fail_closed() {
    assert_eq!(min_version(&slots_with(&[3, 2])), Err(CounterError::Corrupt), "decreasing");
    assert_eq!(min_version(&slots_with(&[3, 3])), Err(CounterError::Corrupt), "equal");
    let mut s = slots_with(&[1]);
    s[5] = !9; // a gap, then a written slot
    assert_eq!(min_version(&s), Err(CounterError::Corrupt));
    let img = image(1_000);
    let m = sign(&sk(), &img, 50, HW_ID_CUP_V4);
    assert_eq!(check(&m, &img, Some(&pubkey()), &s), Err(Reject::Counter(CounterError::Corrupt)), "a damaged counter refuses updates");
    // an all-zero word decodes as version 0xFFFFFFFF: the first slot, then nothing can be greater
    assert_eq!(min_version(&{
        let mut z = EMPTY;
        z[0] = 0;
        z
    }), Ok(u32::MAX));
}

#[test]
fn raising_the_counter_uses_the_next_free_slot_and_only_clears_bits() {
    assert_eq!(plan_raise(&EMPTY, 3), Ok(Some(SlotWrite { slot: 0, value: !3 })));
    let s = slots_with(&[3]);
    let w = plan_raise(&s, 7).unwrap().unwrap();
    assert_eq!(w, SlotWrite { slot: 1, value: !7 });
    assert_eq!(s[w.slot] & w.value, w.value, "an erased word can take any value: only 1 -> 0");
    assert_eq!(plan_raise(&s, 3), Ok(None), "no change at the same version");
    assert_eq!(plan_raise(&s, 2), Ok(None), "never lowered");
}

#[test]
fn full_counter_cannot_be_raised_but_stays_readable() {
    let all: Vec<u32> = (1..=SLOTS as u32).collect();
    let s = slots_with(&all);
    assert_eq!(min_version(&s), Ok(32));
    assert_eq!(plan_raise(&s, 33), Err(CounterError::Full));
    assert_eq!(plan_raise(&s, 32), Ok(None));
}

#[test]
fn the_counter_rises_only_after_a_confirmed_boot() {
    let s = slots_with(&[2]);
    // trial boot (swap just done, not confirmed) or revert: never
    assert_eq!(bump_after_confirmed_boot(&s, false, Some(9)), Ok(None));
    // confirmed with the active version
    assert_eq!(bump_after_confirmed_boot(&s, true, Some(9)), Ok(Some(SlotWrite { slot: 1, value: !9 })));
    // active manifest unreadable: nothing
    assert_eq!(bump_after_confirmed_boot(&s, true, None), Ok(None));
    // already current
    assert_eq!(bump_after_confirmed_boot(&s, true, Some(2)), Ok(None));
}

#[test]
fn full_update_story_with_a_revert() {
    let img1 = image(1_000);
    let img2 = image(1_200);
    let mut slots = EMPTY;
    // v1 installed at the factory and confirmed
    let w = bump_after_confirmed_boot(&slots, true, Some(1)).unwrap().unwrap();
    slots[w.slot] = w.value;
    // v2 arrives, passes, swaps in on trial; it crashes and is reverted: the counter stays at 1
    let m2 = sign(&sk(), &img2, 2, HW_ID_CUP_V4);
    assert!(check(&m2, &img2, Some(&pubkey()), &slots).is_ok());
    assert_eq!(bump_after_confirmed_boot(&slots, false, Some(2)), Ok(None));
    assert_eq!(min_version(&slots), Ok(1));
    // v2 is fixed, confirmed this time: now the counter is 2 and v1 can no longer be installed
    let w = bump_after_confirmed_boot(&slots, true, Some(2)).unwrap().unwrap();
    slots[w.slot] = w.value;
    let m1 = sign(&sk(), &img1, 1, HW_ID_CUP_V4);
    assert_eq!(check(&m1, &img1, Some(&pubkey()), &slots), Err(Reject::Rollback { version: 1, minimum: 2 }));
}

// ---- DFU receiver ---------------------------------------------------------------------------------------------------------

struct Flash {
    mem: Vec<u8>,
    writes: Vec<(u32, usize)>,
    fail: bool,
}
impl Sink for Flash {
    fn write(&mut self, off: u32, data: &[u8]) -> bool {
        if self.fail {
            return false;
        }
        let o = off as usize;
        if self.mem.len() < o + data.len() {
            self.mem.resize(o + data.len(), 0xFF);
        }
        self.mem[o..o + data.len()].copy_from_slice(data);
        self.writes.push((off, data.len()));
        true
    }
}
fn flash() -> Flash {
    Flash { mem: vec![], writes: vec![], fail: false }
}
const APP: u32 = 0x76000;

#[test]
fn a_whole_transfer_then_verification_then_arm() {
    let img = image(1_000);
    let m = sign(&sk(), &img, 4, HW_ID_CUP_V4);
    let mut f = flash();
    let mut rx = DfuReceiver::new(APP, APP);
    assert_eq!(rx.state(), RxState::Idle);
    rx.start();
    for (i, c) in img.chunks(64).enumerate() {
        rx.image_block((i * 64) as u32, c, &mut f).unwrap();
    }
    assert_eq!(rx.received(), 1_000);
    assert!(!rx.is_complete());
    let parsed = rx.manifest(&m, &mut f).unwrap();
    assert_eq!(parsed.version, 4);
    assert!(rx.is_complete());
    // what landed in the partition verifies
    let token = check(&f.mem[APP as usize..], &f.mem[..1_000], Some(&pubkey()), &EMPTY).unwrap();
    assert_eq!(token.version(), 4);
    assert_eq!(f.writes.last(), Some(&(APP, MANIFEST_LEN)), "the manifest went to the manifest page, last");
}

#[test]
fn receiver_refuses_out_of_order_oversize_and_early_manifests() {
    let mut f = flash();
    let mut rx = DfuReceiver::new(APP, APP);
    assert_eq!(rx.image_block(0, &[1], &mut f), Err(DfuError::State), "not started");
    rx.start();
    assert_eq!(rx.image_block(16, &[1; 16], &mut f), Err(DfuError::Offset), "must begin at 0");
    assert_eq!(rx.state(), RxState::Failed);
    assert_eq!(rx.image_block(0, &[1; 16], &mut f), Err(DfuError::State), "failed until restarted");
    assert!(f.writes.is_empty(), "nothing was written by refused blocks");
    rx.start();
    rx.image_block(0, &[1; 16], &mut f).unwrap();
    assert_eq!(rx.image_block(0, &[1; 16], &mut f), Err(DfuError::Offset), "a replayed block");
    rx.start();
    assert_eq!(rx.image_block(0, &[], &mut f), Err(DfuError::Empty));
    rx.start();
    assert_eq!(rx.image_block(0, &vec![0u8; APP as usize + 1], &mut f), Err(DfuError::TooLarge));
    rx.start();
    assert_eq!(rx.image_block(u32::MAX, &[1; 4], &mut f), Err(DfuError::Offset));
}

#[test]
fn the_size_limit_is_exact() {
    let mut f = flash();
    let mut rx = DfuReceiver::new(64, 64);
    rx.start();
    rx.image_block(0, &[0u8; 64], &mut f).unwrap();
    assert_eq!(rx.image_block(64, &[0u8; 1], &mut f), Err(DfuError::TooLarge));
}

#[test]
fn manifest_must_match_the_received_length_and_come_last() {
    let img = image(100);
    let m = sign(&sk(), &img, 1, HW_ID_CUP_V4);
    let mut f = flash();
    let mut rx = DfuReceiver::new(APP, APP);
    rx.start();
    rx.image_block(0, &img[..99], &mut f).unwrap();
    assert_eq!(rx.manifest(&m, &mut f), Err(DfuError::LengthMismatch));
    rx.start();
    rx.image_block(0, &img, &mut f).unwrap();
    assert_eq!(rx.manifest(&m[..50], &mut f), Err(DfuError::Manifest(ManifestError::Length)));
    rx.start();
    rx.image_block(0, &img, &mut f).unwrap();
    rx.manifest(&m, &mut f).unwrap();
    assert_eq!(rx.image_block(100, &[1], &mut f), Err(DfuError::State), "no data after the manifest");
    assert_eq!(rx.manifest(&m, &mut f), Err(DfuError::State), "the manifest only once");
}

#[test]
fn a_flash_error_aborts_the_transfer() {
    let mut f = flash();
    f.fail = true;
    let mut rx = DfuReceiver::new(APP, APP);
    rx.start();
    assert_eq!(rx.image_block(0, &[1; 8], &mut f), Err(DfuError::Sink));
    assert_eq!(rx.state(), RxState::Failed);
}

#[test]
fn a_transfer_of_an_unsigned_image_completes_but_cannot_be_armed() {
    // the receiver knows no keys: completion is not acceptance
    let img = image(500);
    let evil = sign(&SigningKey::from_bytes(&[1u8; 32]), &img, 99, HW_ID_CUP_V4);
    let mut f = flash();
    let mut rx = DfuReceiver::new(APP, APP);
    rx.start();
    rx.image_block(0, &img, &mut f).unwrap();
    rx.manifest(&evil, &mut f).unwrap();
    assert!(rx.is_complete());
    assert_eq!(check(&f.mem[APP as usize..], &f.mem[..500], Some(&pubkey()), &EMPTY), Err(Reject::BadSignature));
}
