//! Real AES-128-CCM (feature `aes-ccm`): RFC 3610 vector, tamper detection, sealed frame via Session.
#![cfg(feature = "aes-ccm")]
use openpatch_proto::ccm_impl::AesCcm;
use openpatch_proto::crc::crc16_ccitt_false;
use openpatch_proto::*;

const KEY: [u8; 16] = [0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xCB, 0xCC, 0xCD, 0xCE, 0xCF];
const NONCE: [u8; 13] = [0x00, 0x00, 0x00, 0x03, 0x02, 0x01, 0x00, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5];
const AAD: [u8; 8] = [0, 1, 2, 3, 4, 5, 6, 7];
const PT: [u8; 23] = [
    0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B,
    0x1C, 0x1D, 0x1E,
];
const CT: [u8; 23] = [
    0x58, 0x8C, 0x97, 0x9A, 0x61, 0xC6, 0x63, 0xD2, 0xF0, 0x66, 0xD0, 0xC2, 0xC0, 0xF9, 0x89, 0x80, 0x6D, 0x5F, 0x6B, 0x61,
    0xDA, 0xC3, 0x84,
];
const TAG: [u8; 8] = [0x17, 0xE8, 0xD1, 0x2C, 0xFD, 0xF9, 0x26, 0xE0];

#[test]
fn rfc3610_packet_vector_1_encrypts() {
    let mut c = AesCcm::new(&KEY);
    let mut ct = [0u8; 23];
    let mut tag = [0u8; 8];
    c.encrypt(&NONCE, &AAD, &PT, &mut ct, &mut tag).unwrap();
    assert_eq!(ct, CT);
    assert_eq!(tag, TAG);
}

#[test]
fn rfc3610_packet_vector_1_decrypts() {
    let mut c = AesCcm::new(&KEY);
    let mut pt = [0u8; 23];
    c.decrypt(&NONCE, &AAD, &CT, &TAG, &mut pt).unwrap();
    assert_eq!(pt, PT);
}

#[test]
fn tampering_with_ciphertext_aad_tag_or_nonce_fails() {
    let mut c = AesCcm::new(&KEY);
    let mut pt = [0u8; 23];
    for bit in 0..8 {
        let mut ct = CT;
        ct[5] ^= 1 << bit;
        assert!(c.decrypt(&NONCE, &AAD, &ct, &TAG, &mut pt).is_err());
        let mut aad = AAD;
        aad[3] ^= 1 << bit;
        assert!(c.decrypt(&NONCE, &aad, &CT, &TAG, &mut pt).is_err());
        let mut tag = TAG;
        tag[7] ^= 1 << bit;
        assert!(c.decrypt(&NONCE, &AAD, &CT, &tag, &mut pt).is_err());
        let mut nonce = NONCE;
        nonce[12] ^= 1 << bit;
        assert!(c.decrypt(&nonce, &AAD, &CT, &TAG, &mut pt).is_err());
    }
}

#[test]
fn mismatched_buffer_lengths_are_rejected() {
    let mut c = AesCcm::new(&KEY);
    let mut ct = [0u8; 22];
    let mut tag = [0u8; 8];
    assert!(c.encrypt(&NONCE, &AAD, &PT, &mut ct, &mut tag).is_err());
}

#[test]
fn end_to_end_sealed_and_opened_frame_via_session() {
    let key = [0x42u8; 16];
    let salt = [9, 8, 7, 6];
    let mut phone = Session::new(AesCcm::new(&key), true, salt, false).with_role(LinkRole::Phone);
    let mut pod = Session::new(AesCcm::new(&key), true, salt, false);
    let payload = [tag::AMOUNT_MU, 4, 0xD0, 0x07, 0, 0];
    let mut buf = [0u8; 64];
    let mut plain = [0u8; 64];
    let n = phone.seal(false, cmd::BOLUS, 3, true, &payload, &mut buf).unwrap();
    assert_ne!(buf[2] & FLAG_ENCRYPTED, 0);
    assert_ne!(&buf[FRAME_HEADER..FRAME_HEADER + 6], &payload, "payload is not in the clear");
    let f = pod.open(&buf[..n], &mut plain).unwrap();
    assert_eq!((f.type_, f.seq, f.payload), (cmd::BOLUS, 3, &payload[..]));

    // replay is refused
    let mut plain2 = [0u8; 64];
    assert_eq!(pod.open(&buf[..n], &mut plain2).unwrap_err(), Error::Replay);

    // flipping a ciphertext bit with a repaired CRC is caught by the tag
    let n2 = phone.seal(false, cmd::BOLUS, 4, true, &payload, &mut buf).unwrap();
    buf[FRAME_HEADER] ^= 0x80;
    let crc = crc16_ccitt_false(&buf[..n2 - 2]);
    buf[n2 - 2..n2].copy_from_slice(&crc.to_le_bytes());
    assert_eq!(pod.open(&buf[..n2], &mut plain2).unwrap_err(), Error::Auth);

    // a wrong key does not open a genuine frame
    let n3 = phone.seal(false, cmd::BOLUS, 5, true, &payload, &mut buf).unwrap();
    let mut other = Session::new(AesCcm::new(&[0x43u8; 16]), true, salt, false);
    assert_eq!(other.open(&buf[..n3], &mut plain2).unwrap_err(), Error::Auth);

    // pod response sealed, phone opens it (response direction nonce)
    let mut rbuf = [0u8; 64];
    let rn = pod.seal(true, cmd::BOLUS | RSP_BIT, 3, true, &[tag::RESULT, 1, 0], &mut rbuf).unwrap();
    let rf = decode_frame(&rbuf[..rn]).unwrap();
    assert_eq!(rf.payload.len(), 3 + CCM_TAG_LEN);
    let ro = phone.open(&rbuf[..rn], &mut plain2).unwrap();
    assert_eq!(ro.payload, &[tag::RESULT, 1, 0]);
}
