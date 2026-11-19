//! AES-128-CCM (M=8, L=2) open/seal wrapper (openpatch-proto ccm_impl.rs, RustCrypto `aes` + `ccm`).
//! Properties: no panic for any lengths; seal then open round-trips; any single-bit change of ciphertext, tag, AAD or
//! nonce makes open fail; open of arbitrary (ct, tag) only succeeds if re-sealing the result reproduces (ct, tag).
#![no_main]
use arbitrary::Arbitrary;
use libfuzzer_sys::fuzz_target;
use openpatch_proto::ccm_impl::AesCcm;
use openpatch_proto::Ccm;

#[derive(Arbitrary, Debug)]
struct Input {
    key_c2p: [u8; 16],
    key_p2c: [u8; 16],
    nonce: [u8; 13],
    aad: Vec<u8>,
    data: Vec<u8>,
    tag: [u8; 8],
    flip: u16,
}

fuzz_target!(|i: Input| {
    let mut c = AesCcm::directional(&i.key_c2p, &i.key_p2c);
    let n = i.data.len().min(300);
    let pt = &i.data[..n];
    let aad = &i.aad[..i.aad.len().min(64)];
    // 1. round trip
    let mut ct = vec![0u8; n];
    let mut tag = [0u8; 8];
    if c.encrypt(&i.nonce, aad, pt, &mut ct, &mut tag).is_ok() {
        let mut back = vec![0u8; n];
        assert!(c.decrypt(&i.nonce, aad, &ct, &tag, &mut back).is_ok());
        assert_eq!(back, pt);
        // 2. single bit flips are detected
        let bit = i.flip as usize % (8 * (n + 8 + aad.len() + 13));
        let (mut ct2, mut tag2, mut aad2, mut nonce2) = (ct.clone(), tag, aad.to_vec(), i.nonce);
        let region = bit / 8;
        let b = 1u8 << (bit % 8);
        if region < n {
            ct2[region] ^= b;
        } else if region < n + 8 {
            tag2[region - n] ^= b;
        } else if region < n + 8 + aad.len() {
            aad2[region - n - 8] ^= b;
        } else {
            nonce2[region - n - 8 - aad.len()] ^= b;
        }
        let mut sink = vec![0u8; n];
        assert!(c.decrypt(&nonce2, &aad2, &ct2, &tag2, &mut sink).is_err(), "bit flip not detected");
    }
    // 3. arbitrary (ct, tag): acceptance requires that sealing the output reproduces them
    let mut out = vec![0u8; n];
    if c.decrypt(&i.nonce, aad, pt, &i.tag, &mut out).is_ok() {
        let mut ct3 = vec![0u8; n];
        let mut tag3 = [0u8; 8];
        c.encrypt(&i.nonce, aad, &out, &mut ct3, &mut tag3).unwrap();
        assert_eq!(&ct3[..], pt);
        assert_eq!(tag3, i.tag);
    }
});
