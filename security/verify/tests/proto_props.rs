//! Parser / session robustness properties of openpatch-proto (complements the cargo-fuzz targets in firmware-rs/fuzz).
//! Run: `cargo test --release --test proto_props`.
use openpatch_proto::ccm_impl::AesCcm;
use openpatch_proto::tlv::TlvReader;
use openpatch_proto::{self as proto, Error, Frame, Session, FRAME_MAX};
use proptest::prelude::*;

const KC: [u8; 16] = [0x11; 16];
const KP: [u8; 16] = [0x22; 16];
const SALT: [u8; 4] = [1, 2, 3, 4];

fn sess() -> Session<AesCcm> {
    Session::new(AesCcm::directional(&KC, &KP), true, SALT, false)
}

proptest! {
    #![proptest_config(ProptestConfig { cases: 20_000, .. ProptestConfig::default() })]

    /// The frame decoder never panics and, if it accepts, the frame re-encodes to the identical bytes.
    #[test]
    fn frame_decoder_total_and_canonical(bytes in proptest::collection::vec(any::<u8>(), 0..300)) {
        if let Ok(f) = proto::decode_frame(&bytes) {
            let mut out = [0u8; FRAME_MAX];
            let n = proto::encode_frame(&Frame { ..f }, &mut out).unwrap();
            prop_assert_eq!(&out[..n], &bytes[..]);
        }
    }

    /// TLV reader: never panics, never yields a slice outside the input, terminates.
    #[test]
    fn tlv_reader_total(bytes in proptest::collection::vec(any::<u8>(), 0..300)) {
        let mut n = 0;
        for item in TlvReader::new(&bytes) {
            n += 1;
            prop_assert!(n <= bytes.len() + 1);
            if let Ok((_, v)) = item { prop_assert!(v.len() <= bytes.len()); }
        }
    }

    /// Command / response decoders never panic on any (type, seq, payload).
    #[test]
    fn codecs_total(t in any::<u8>(), seq in any::<u16>(), payload in proptest::collection::vec(any::<u8>(), 0..250)) {
        let _ = proto::decode_command(t, seq, &payload);
        let _ = proto::decode_response(t, seq, &payload);
    }

    /// Arbitrary bytes into an encrypted session: never panic; anything accepted must carry a valid tag
    /// (probability 2^-64 per attempt, i.e. never in this test).
    #[test]
    fn session_open_rejects_garbage(bytes in proptest::collection::vec(any::<u8>(), 0..300)) {
        let mut s = sess();
        let mut plain = [0u8; FRAME_MAX];
        prop_assert!(s.open(&bytes, &mut plain).is_err());
    }

    /// Any single bit flip anywhere in a sealed frame is rejected (CRC, length, version or AEAD tag).
    #[test]
    fn sealed_frame_bitflip_rejected(seq in 1u16..0xFFFE, payload in proptest::collection::vec(any::<u8>(), 0..100), bit in 0usize..(8 * 200)) {
        let mut tx = sess();
        let mut buf = [0u8; FRAME_MAX];
        let n = tx.seal(false, 0x05, seq, true, &payload, &mut buf).unwrap();
        let mut frame = buf[..n].to_vec();
        let bit = bit % (8 * n);
        frame[bit / 8] ^= 1 << (bit % 8);
        let mut rx = sess();
        let mut plain = [0u8; FRAME_MAX];
        prop_assert!(rx.open(&frame, &mut plain).is_err());
    }

    /// Replay: a frame is accepted at most once; seq must strictly increase; state does not advance on failure.
    #[test]
    fn replay_and_ordering(seqs in proptest::collection::vec(1u16..0xFFFE, 1..40)) {
        let mut tx = sess();
        let mut rx = sess();
        let mut last: Option<u16> = None;
        for q in seqs {
            let mut buf = [0u8; FRAME_MAX];
            let n = tx.seal(false, 0x01, q, true, &[], &mut buf).unwrap();
            let mut plain = [0u8; FRAME_MAX];
            let r = rx.open(&buf[..n], &mut plain);
            match last {
                Some(l) if q <= l => prop_assert_eq!(r.err(), Some(Error::Replay)),
                _ => { prop_assert!(r.is_ok()); last = Some(q); }
            }
        }
    }

    /// Without keys (production, before the handshake) nothing is ever accepted.
    #[test]
    fn keyless_session_refuses_everything(bytes in proptest::collection::vec(any::<u8>(), 0..300)) {
        let mut s: Session<proto::NoCrypto> = Session::new(proto::NoCrypto, false, SALT, false);
        let mut plain = [0u8; FRAME_MAX];
        prop_assert!(s.open(&bytes, &mut plain).is_err());
    }
}
