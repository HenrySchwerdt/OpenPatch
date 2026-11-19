//! Frame / TLV / command / response decoders (openpatch-proto frame.rs, tlv.rs, codec_cmd.rs, codec_rsp.rs).
//! Properties: no panic, no overflow; a frame that decodes re-encodes byte-identically; the TLV reader terminates and
//! stays inside its input.
#![no_main]
use libfuzzer_sys::fuzz_target;
use openpatch_proto::tlv::TlvReader;
use openpatch_proto::{decode_command, decode_frame, decode_response, encode_frame, FRAME_MAX};

fuzz_target!(|data: &[u8]| {
    if let Ok(f) = decode_frame(data) {
        let mut out = [0u8; FRAME_MAX];
        let n = encode_frame(&f, &mut out).expect("a decoded frame must re-encode");
        assert_eq!(&out[..n], data, "frame codec is not canonical");
        let _ = decode_command(f.type_, f.seq, f.payload);
        let _ = decode_response(f.type_ & 0x7F, f.seq, f.payload);
    }
    // Payload parsers also see arbitrary bytes directly (attacker controls the decrypted payload of an authenticated peer).
    if data.len() >= 3 {
        let (t, rest) = (data[0], &data[3..]);
        let seq = u16::from_le_bytes([data[1], data[2]]);
        let _ = decode_command(t, seq, rest);
        let _ = decode_response(t, seq, rest);
    }
    let mut count = 0usize;
    for item in TlvReader::new(data) {
        count += 1;
        assert!(count <= data.len() + 1, "TLV reader does not terminate");
        if let Ok((_, v)) = item {
            assert!(v.len() <= data.len());
        }
    }
});
