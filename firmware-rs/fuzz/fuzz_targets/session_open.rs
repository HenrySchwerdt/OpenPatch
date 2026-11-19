//! Session::open (replay state machine + AES-CCM) on a stream of attacker frames, with a REAL keyed AesCcm.
//! Two sessions are driven by the same input: production style (encrypted only) and development style (plaintext allowed,
//! where nothing is authenticated, so the replay logic itself is exercised).
//! Properties: no panic; production style never accepts a fuzzer-made frame (needs a valid 64 bit tag); in the
//! plaintext session the accepted command seq values are strictly increasing and <= SEQ_MAX.
#![no_main]
use arbitrary::Arbitrary;
use libfuzzer_sys::fuzz_target;
use openpatch_proto::ccm_impl::AesCcm;
use openpatch_proto::{NoCrypto, Session, FRAME_MAX, FLAG_RESPONSE, SEQ_MAX};

#[derive(Arbitrary, Debug)]
struct Input {
    frames: Vec<Vec<u8>>,
}

fuzz_target!(|inp: Input| {
    let mut prod = Session::new(AesCcm::directional(&[0x42; 16], &[0x24; 16]), true, [1, 2, 3, 4], false);
    let mut dev: Session<NoCrypto> = Session::new(NoCrypto, false, [1, 2, 3, 4], true);
    let mut last: Option<u16> = None;
    for fr in inp.frames.iter().take(64) {
        let mut plain = [0u8; FRAME_MAX];
        assert!(prod.open(fr, &mut plain).is_err(), "production session accepted an unauthenticated frame");
        let mut plain2 = [0u8; FRAME_MAX];
        if let Ok(o) = dev.open(fr, &mut plain2) {
            assert!(o.seq <= SEQ_MAX || o.flags & FLAG_RESPONSE != 0);
            if o.flags & FLAG_RESPONSE == 0 {
                if let Some(l) = last {
                    assert!(o.seq > l, "replay window accepted seq {} after {}", o.seq, l);
                }
                last = Some(o.seq);
            }
        }
    }
});
