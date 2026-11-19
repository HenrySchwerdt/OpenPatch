//! DFU manifest / signature glue (mirror of openpatch-bootloader check_pending, see src/lib.rs).
//! Properties: parse never panics and only accepts magic + 0 < len <= APP_SIZE; a correctly signed manifest verifies; ANY
//! change of the image, of the length field, of the signature or of the key makes verification fail; changing the
//! format/reserved bytes does NOT (documented weakness FINDING-006: the unsigned manifest fields are ignored, there is
//! no version / rollback binding).
#![no_main]
use arbitrary::Arbitrary;
use libfuzzer_sys::fuzz_target;
use openpatch_fuzz::{layout, manifest};

#[derive(Arbitrary, Debug)]
struct Input {
    raw_manifest: Vec<u8>,
    seed: [u8; 32],
    image: Vec<u8>,
    mutate_what: u8,
    pos: u16,
    xor: u8,
}

fuzz_target!(|i: Input| {
    // 1. arbitrary bytes as manifest
    if let Some((len, _)) = manifest::parse(&i.raw_manifest) {
        assert!(len > 0 && len <= layout::APP_SIZE);
        assert_eq!(&i.raw_manifest[..4], &layout::MANIFEST_MAGIC.to_le_bytes());
    }
    // 2. honest manifest verifies, tampered ones do not
    if i.image.is_empty() {
        return;
    }
    let pk = manifest::public(&i.seed);
    let good = manifest::build(&i.seed, &i.image);
    let (len, sig) = manifest::parse(&good).expect("honest manifest parses");
    assert!(manifest::verify(&pk, &i.image, len, &sig), "honest manifest rejected");
    if i.xor == 0 {
        return;
    }
    match i.mutate_what % 5 {
        0 => {
            let mut img = i.image.clone();
            let p = i.pos as usize % img.len();
            img[p] ^= i.xor;
            assert!(!manifest::verify(&pk, &img, len, &sig), "modified image accepted");
        }
        1 => {
            let mut s = sig;
            s[i.pos as usize % 64] ^= i.xor;
            assert!(!manifest::verify(&pk, &i.image, len, &s), "modified signature accepted");
        }
        2 => {
            // image longer than signed length, or a shorter claimed length
            let mut longer = i.image.clone();
            longer.push(i.xor);
            let shorter = len.saturating_sub(1 + (i.pos as u32 % len.max(1)));
            if shorter > 0 && shorter != len {
                assert!(!manifest::verify(&pk, &i.image, shorter, &sig), "truncated length accepted");
            }
            assert!(manifest::verify(&pk, &longer, len, &sig), "trailing bytes beyond len are not covered, by design");
        }
        3 => {
            let mut other = i.seed;
            other[(i.pos % 32) as usize] ^= i.xor;
            assert!(!manifest::verify(&manifest::public(&other), &i.image, len, &sig), "wrong key accepted");
        }
        _ => {
            // FINDING-006: format / reserved bytes (4..8) are not covered by the signature and not checked.
            let mut m = good.clone();
            m[4 + (i.pos as usize % 4)] ^= i.xor;
            let (l2, s2) = manifest::parse(&m).expect("format/reserved changes do not stop parsing");
            assert!(manifest::verify(&pk, &i.image, l2, &s2));
        }
    }
});
