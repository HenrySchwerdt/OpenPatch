//! Pod side of the v1.1 handshake on arbitrary frame streams (openpatch-proto handshake.rs `Responder::handle`).
//! Properties: no panic; every reply is a well-formed frame within FRAME_MAX; fuzzer bytes alone never produce a pairing
//! (Event::Paired) or a session (Event::SessionUp): both need a valid key confirmation tag, i.e. knowledge of the shared
//! DH secret, which a blind byte stream cannot have.
#![no_main]
use arbitrary::Arbitrary;
use libfuzzer_sys::fuzz_target;
use openpatch_fuzz::Det;
use openpatch_proto::handshake::{Event, Responder};
use openpatch_proto::{decode_frame, FRAME_MAX};

#[derive(Arbitrary, Debug)]
struct Input {
    ps: Option<[u8; 32]>,
    oob: Vec<u8>,
    seed: u64,
    frames: Vec<(bool, Vec<u8>)>,
}

fuzz_target!(|i: Input| {
    let mut rng = Det(i.seed | 1);
    let mut pod = Responder::new(i.ps);
    if !i.oob.is_empty() {
        pod.set_oob(&i.oob[..i.oob.len().min(32)]);
    }
    for (open, fr) in i.frames.iter().take(16) {
        let mut out = [0u8; FRAME_MAX];
        if let Some(o) = pod.handle(fr, *open, &mut rng, &mut out) {
            assert!(o.reply_len <= FRAME_MAX);
            if o.reply_len > 0 {
                decode_frame(&out[..o.reply_len]).expect("reply must be a valid frame");
            }
            assert!(matches!(o.event, Event::None), "blind bytes produced a pairing/session");
        }
    }
});
