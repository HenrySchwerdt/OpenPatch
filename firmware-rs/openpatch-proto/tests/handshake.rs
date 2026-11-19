//! Session key agreement (feature `key-agreement`): primitives vs RFC vectors, pod/phone round
//! trips, negative cases and the shared test vectors `docs/vectors/session-key-agreement.json`
//! (also consumed by the Swift suite in `ios/OpenPatchKit/OpenPatchCore`).
//!
//! Regenerate the vector file after an intentional protocol change:
//! `OPENPATCH_WRITE_VECTORS=1 cargo test -p openpatch-proto --features key-agreement --test handshake vectors`
#![cfg(feature = "key-agreement")]
use openpatch_proto::ccm_impl::AesCcm;
use openpatch_proto::handshake::*;
use openpatch_proto::*;
use rand_core::{impls, Error as RngError, RngCore};
use serde_json::{json, Value};

const VECTOR_FILE: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../../docs/vectors/session-key-agreement.json");

fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}
fn unhex(s: &str) -> Vec<u8> {
    (0..s.len() / 2).map(|i| u8::from_str_radix(&s[2 * i..2 * i + 2], 16).unwrap()).collect()
}
fn arr<const N: usize>(s: &str) -> [u8; N] {
    unhex(s).try_into().unwrap()
}

/// Deterministic "RNG": hands out the given bytes in order.
struct FixedRng {
    data: Vec<u8>,
    pos: usize,
}
impl FixedRng {
    fn new(parts: &[&[u8]]) -> Self {
        Self { data: parts.concat(), pos: 0 }
    }
}
impl RngCore for FixedRng {
    fn next_u32(&mut self) -> u32 {
        impls::next_u32_via_fill(self)
    }
    fn next_u64(&mut self) -> u64 {
        impls::next_u64_via_fill(self)
    }
    fn fill_bytes(&mut self, dest: &mut [u8]) {
        dest.copy_from_slice(&self.data[self.pos..self.pos + dest.len()]);
        self.pos += dest.len();
    }
    fn try_fill_bytes(&mut self, dest: &mut [u8]) -> Result<(), RngError> {
        self.fill_bytes(dest);
        Ok(())
    }
}

/// Counter based RNG for the property style tests (never used for keys outside tests).
struct CountRng(u8);
impl RngCore for CountRng {
    fn next_u32(&mut self) -> u32 {
        impls::next_u32_via_fill(self)
    }
    fn next_u64(&mut self) -> u64 {
        impls::next_u64_via_fill(self)
    }
    fn fill_bytes(&mut self, dest: &mut [u8]) {
        for b in dest {
            self.0 = self.0.wrapping_mul(73).wrapping_add(41);
            *b = self.0;
        }
    }
    fn try_fill_bytes(&mut self, dest: &mut [u8]) -> Result<(), RngError> {
        self.fill_bytes(dest);
        Ok(())
    }
}

fn pattern<const N: usize>(start: u8) -> [u8; N] {
    let mut a = [0u8; N];
    for (i, b) in a.iter_mut().enumerate() {
        *b = start.wrapping_add(i as u8);
    }
    a
}

// ---------------------------------------------------------------------------------------------
// Primitives vs published vectors
// ---------------------------------------------------------------------------------------------

const RFC7748_ALICE_SECRET: &str = "77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a";
const RFC7748_ALICE_PUBLIC: &str = "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a";
const RFC7748_BOB_SECRET: &str = "5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb";
const RFC7748_BOB_PUBLIC: &str = "de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f";
const RFC7748_SHARED: &str = "4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742";

#[test]
fn x25519_matches_rfc7748_section_6_1() {
    let a: [u8; 32] = arr(RFC7748_ALICE_SECRET);
    let b: [u8; 32] = arr(RFC7748_BOB_SECRET);
    assert_eq!(hex(&public_key(&a)), RFC7748_ALICE_PUBLIC);
    assert_eq!(hex(&public_key(&b)), RFC7748_BOB_PUBLIC);
    assert_eq!(hex(&shared_secret(&a, &public_key(&b)).unwrap()), RFC7748_SHARED);
    assert_eq!(hex(&shared_secret(&b, &public_key(&a)).unwrap()), RFC7748_SHARED);
}

#[test]
fn x25519_low_order_points_are_rejected() {
    let secret = pattern::<32>(7);
    assert!(shared_secret(&secret, &[0u8; 32]).is_none());
    let mut one = [0u8; 32];
    one[0] = 1; // u = 1, order 4
    assert!(shared_secret(&secret, &one).is_none());
}

// ---------------------------------------------------------------------------------------------
// Handshake round trips
// ---------------------------------------------------------------------------------------------

struct Pair {
    ps: [u8; 32],
    pod: Responder,
}

/// Full pairing against a fresh pod.
fn do_pairing(oob_phone: &[u8], oob_pod: &[u8]) -> Result<Pair, HsError> {
    let mut pod = Responder::new(None);
    pod.set_oob(oob_pod);
    let mut ini = Initiator::pair(&mut CountRng(1), oob_phone);
    let mut rng = CountRng(99);
    let (mut a, mut b, mut c) = ([0u8; 244], [0u8; 244], [0u8; 244]);
    let n = ini.init_frame(0, &mut a).unwrap();
    let o = pod.handle(&a[..n], true, &mut rng, &mut b).unwrap();
    assert!(matches!(o.event, Event::None));
    let m = ini.on_init_response(&b[..o.reply_len], 1, &mut c)?;
    let o = pod.handle(&c[..m], true, &mut rng, &mut a).unwrap();
    let ps_pod = match o.event {
        Event::Paired(p) => p,
        _ => panic!("no pairing event"),
    };
    match ini.on_finish_response(&a[..o.reply_len])? {
        Outcome::Paired(ps) => {
            assert_eq!(ps, ps_pod);
            Ok(Pair { ps, pod })
        }
        _ => panic!("wrong outcome"),
    }
}

/// Session handshake; returns (phone keys, pod keys).
fn do_session(pod: &mut Responder, ps: [u8; 32], seed: u8) -> Result<(SessionKeys, SessionKeys), HsError> {
    let mut ini = Initiator::session(&mut CountRng(seed), ps);
    let mut rng = CountRng(seed.wrapping_add(100));
    let (mut a, mut b, mut c) = ([0u8; 244], [0u8; 244], [0u8; 244]);
    let n = ini.init_frame(0, &mut a).unwrap();
    let o = pod.handle(&a[..n], false, &mut rng, &mut b).unwrap();
    let m = ini.on_init_response(&b[..o.reply_len], 1, &mut c)?;
    let o = pod.handle(&c[..m], false, &mut rng, &mut a).unwrap();
    let pod_keys = match o.event {
        Event::SessionUp(k) => k,
        _ => panic!("no session event"),
    };
    match ini.on_finish_response(&a[..o.reply_len])? {
        Outcome::Session(k) => Ok((k, pod_keys)),
        _ => panic!("wrong outcome"),
    }
}

fn sess(k: &SessionKeys) -> Session<AesCcm> {
    Session::new(AesCcm::directional(&k.key_c2p, &k.key_p2c), true, k.salt, false)
}

#[test]
fn pairing_then_session_yield_identical_keys_and_encrypted_traffic_works() {
    let mut p = do_pairing(b"", b"").unwrap();
    let (phone_keys, pod_keys) = do_session(&mut p.pod, p.ps, 3).unwrap();
    assert!(phone_keys == pod_keys);
    assert_ne!(phone_keys.key_c2p, phone_keys.key_p2c, "one key per direction");
    let (mut phone, mut pod) = (sess(&phone_keys), sess(&pod_keys));

    let payload = [tag::AMOUNT_MU, 4, 0xD0, 0x07, 0, 0];
    let (mut buf, mut plain) = ([0u8; 244], [0u8; 244]);
    let n = phone.seal(false, cmd::BOLUS, 1, true, &payload, &mut buf).unwrap();
    let o = pod.open(&buf[..n], &mut plain).unwrap();
    assert_eq!((o.type_, o.seq, o.payload), (cmd::BOLUS, 1, &payload[..]));
    // response and notification back
    let mut rsp = [0u8; 244];
    let r = pod.seal(true, cmd::BOLUS | RSP_BIT, 1, true, &[tag::RESULT, 1, 0], &mut rsp).unwrap();
    let mut plain2 = [0u8; 244];
    let o = phone.open(&rsp[..r], &mut plain2).unwrap();
    assert_eq!(o.payload, &[tag::RESULT, 1, 0]);
    // a response re-labelled as a command (flag cleared, CRC fixed) is refused: direction key + nonce + AAD
    let mut relabel = rsp;
    relabel[2] &= !FLAG_RESPONSE;
    let crc = crc::crc16_ccitt_false(&relabel[..r - 2]);
    relabel[r - 2..r].copy_from_slice(&crc.to_le_bytes());
    assert_eq!(pod.open(&relabel[..r], &mut plain).unwrap_err(), Error::Auth);
}

#[test]
fn every_session_gets_fresh_keys_and_old_frames_do_not_replay() {
    let mut p = do_pairing(b"", b"").unwrap();
    let (k1, _) = do_session(&mut p.pod, p.ps, 3).unwrap();
    let (k2, pod_k2) = do_session(&mut p.pod, p.ps, 4).unwrap();
    assert!(k1 != k2);
    let payload = [tag::AMOUNT_MU, 4, 0xD0, 0x07, 0, 0];
    let (mut buf, mut plain) = ([0u8; 244], [0u8; 244]);
    let n = sess(&k1).seal(false, cmd::BOLUS, 1, true, &payload, &mut buf).unwrap();
    // the recorded frame of session 1 is garbage to session 2, although seq 1 is fresh there
    let mut pod2 = sess(&pod_k2);
    assert_eq!(pod2.open(&buf[..n], &mut plain).unwrap_err(), Error::Auth);
    assert!(!pod2.rx_seen(), "a failed authentication must not burn the counter");
}

#[test]
fn seq_rules_are_unchanged_inside_a_session_and_restart_with_a_new_one() {
    let mut p = do_pairing(b"", b"").unwrap();
    let (kp, kd) = do_session(&mut p.pod, p.ps, 5).unwrap();
    let (mut phone, mut pod) = (sess(&kp), sess(&kd));
    let payload = [tag::AMOUNT_MU, 4, 0xD0, 0x07, 0, 0];
    let (mut b1, mut b2, mut plain) = ([0u8; 244], [0u8; 244], [0u8; 244]);
    let n1 = phone.seal(false, cmd::BOLUS, 5, true, &payload, &mut b1).unwrap();
    pod.open(&b1[..n1], &mut plain).unwrap();
    // replay of the same frame and a lower seq are refused
    assert_eq!(pod.open(&b1[..n1], &mut plain).unwrap_err(), Error::Replay);
    let n2 = phone.seal(false, cmd::BOLUS, 4, true, &payload, &mut b2).unwrap();
    assert_eq!(pod.open(&b2[..n2], &mut plain).unwrap_err(), Error::Replay);
    // the sequence space is per session: a re-established session starts again (SESSION is no longer terminal)
    let (kp2, kd2) = do_session(&mut p.pod, p.ps, 6).unwrap();
    let n3 = sess(&kp2).seal(false, cmd::BOLUS, 1, true, &payload, &mut b1).unwrap();
    assert_eq!(sess(&kd2).open(&b1[..n3], &mut plain).unwrap().seq, 1);
}

#[test]
fn pairing_refused_while_the_window_is_closed() {
    let mut pod = Responder::new(None);
    let ini = Initiator::pair(&mut CountRng(1), b"");
    let (mut a, mut b) = ([0u8; 244], [0u8; 244]);
    let n = ini.init_frame(0, &mut a).unwrap();
    let o = pod.handle(&a[..n], false, &mut CountRng(2), &mut b).unwrap();
    let f = decode_frame(&b[..o.reply_len]).unwrap();
    assert_eq!(f.type_, htype::PAIR_INIT | RSP_BIT);
    assert_eq!(f.payload, &[tag::RESULT, 1, hresult::AUTH]);
    assert!(!pod.has_pairing_secret());
}

#[test]
fn pairing_window_closing_between_init_and_finish_aborts() {
    let mut pod = Responder::new(None);
    let mut ini = Initiator::pair(&mut CountRng(1), b"");
    let (mut a, mut b, mut c) = ([0u8; 244], [0u8; 244], [0u8; 244]);
    let n = ini.init_frame(0, &mut a).unwrap();
    let o = pod.handle(&a[..n], true, &mut CountRng(2), &mut b).unwrap();
    let m = ini.on_init_response(&b[..o.reply_len], 1, &mut c).unwrap();
    let o = pod.handle(&c[..m], false, &mut CountRng(3), &mut a).unwrap();
    assert!(matches!(o.event, Event::None));
    assert!(!pod.has_pairing_secret());
}

#[test]
fn oob_code_must_match_on_both_sides() {
    assert!(do_pairing(b"123456", b"123456").is_ok());
    assert_eq!(do_pairing(b"123456", b"654321").err(), Some(HsError::BadConfirm));
    assert_eq!(do_pairing(b"", b"123456").err(), Some(HsError::BadConfirm));
}

#[test]
fn session_with_the_wrong_pairing_secret_is_rejected_by_the_pod() {
    let mut p = do_pairing(b"", b"").unwrap();
    let mut wrong = p.ps;
    wrong[0] ^= 1;
    // wrong PS_ID: the pod answers PAIR (re-pair needed) and creates no pending state
    assert_eq!(do_session(&mut p.pod, wrong, 7).err(), Some(HsError::Rejected(hresult::PAIR)));
    // an unpaired pod answers PAIR as well
    let mut fresh = Responder::new(None);
    assert_eq!(do_session(&mut fresh, p.ps, 7).err(), Some(HsError::Rejected(hresult::PAIR)));
}

#[test]
fn attacker_knowing_ps_id_but_not_ps_cannot_replace_the_session() {
    let mut p = do_pairing(b"", b"").unwrap();
    let id = ps_id(&p.ps);
    // forge: valid INIT (public PS_ID), then a FINISH with a made up confirmation tag
    let (secret, nonce) = draw(&mut CountRng(9));
    let pub_a = public_key(&secret);
    let mut payload = [0u8; 80];
    let mut w = openpatch_proto::tlv::TlvWriter::new(&mut payload);
    w.put(htag::EPH_PUB, &pub_a);
    w.put(htag::NONCE, &nonce);
    w.put(htag::PS_ID, &id);
    let n = w.finish().unwrap();
    let (mut f, mut r) = ([0u8; 244], [0u8; 244]);
    let fl = encode_frame(&Frame { version: 1, type_: htype::SESSION_INIT, flags: 0, seq: 0, payload: &payload[..n] }, &mut f).unwrap();
    let o = p.pod.handle(&f[..fl], false, &mut CountRng(5), &mut r).unwrap();
    assert!(matches!(o.event, Event::None));
    let mut fin = [0u8; 32];
    let mut w = openpatch_proto::tlv::TlvWriter::new(&mut fin);
    w.put(htag::CONFIRM, &[0xAA; 16]);
    let n = w.finish().unwrap();
    let fl = encode_frame(&Frame { version: 1, type_: htype::SESSION_FINISH, flags: 0, seq: 1, payload: &fin[..n] }, &mut f).unwrap();
    let o = p.pod.handle(&f[..fl], false, &mut CountRng(6), &mut r).unwrap();
    assert!(matches!(o.event, Event::None), "no SessionUp without the key confirmation");
    assert_eq!(decode_frame(&r[..o.reply_len]).unwrap().payload, &[tag::RESULT, 1, hresult::AUTH]);
    // the real phone is not locked out afterwards
    assert!(do_session(&mut p.pod, p.ps, 8).is_ok());
}

#[test]
fn stale_pending_and_out_of_order_finish_are_refused() {
    let mut p = do_pairing(b"", b"").unwrap();
    let (mut a, mut b, mut c, mut d) = ([0u8; 244], [0u8; 244], [0u8; 244], [0u8; 244]);
    let mut ini = Initiator::session(&mut CountRng(1), p.ps);
    let n = ini.init_frame(0, &mut a).unwrap();
    let o = p.pod.handle(&a[..n], false, &mut CountRng(2), &mut b).unwrap();
    let m = ini.on_init_response(&b[..o.reply_len], 1, &mut c).unwrap();
    // a second INIT replaces the pending handshake: the first FINISH no longer matches
    let ini2 = Initiator::session(&mut CountRng(3), p.ps);
    let n2 = ini2.init_frame(0, &mut a).unwrap();
    p.pod.handle(&a[..n2], false, &mut CountRng(4), &mut d).unwrap();
    let o = p.pod.handle(&c[..m], false, &mut CountRng(5), &mut a).unwrap();
    assert!(matches!(o.event, Event::None));
    // replaying that FINISH once more: nothing pending any more -> SESSION
    let o = p.pod.handle(&c[..m], false, &mut CountRng(5), &mut a).unwrap();
    assert_eq!(decode_frame(&a[..o.reply_len]).unwrap().payload, &[tag::RESULT, 1, hresult::SESSION]);
    // link reset drops a half-open handshake
    let mut ini3 = Initiator::session(&mut CountRng(6), p.ps);
    let n3 = ini3.init_frame(0, &mut a).unwrap();
    let o = p.pod.handle(&a[..n3], false, &mut CountRng(7), &mut b).unwrap();
    let m3 = ini3.on_init_response(&b[..o.reply_len], 1, &mut c).unwrap();
    p.pod.reset();
    let o = p.pod.handle(&c[..m3], false, &mut CountRng(8), &mut a).unwrap();
    assert!(matches!(o.event, Event::None));
}

#[test]
fn recorded_handshake_replayed_to_the_pod_never_yields_a_session() {
    let mut p = do_pairing(b"", b"").unwrap();
    let mut ini = Initiator::session(&mut CountRng(11), p.ps);
    let (mut a, mut b, mut c) = ([0u8; 244], [0u8; 244], [0u8; 244]);
    let n = ini.init_frame(0, &mut a).unwrap();
    let o = p.pod.handle(&a[..n], false, &mut CountRng(12), &mut b).unwrap();
    let m = ini.on_init_response(&b[..o.reply_len], 1, &mut c).unwrap();
    let first = p.pod.handle(&c[..m], false, &mut CountRng(13), &mut b).unwrap();
    assert!(matches!(first.event, Event::SessionUp(_)));
    // attacker replays the recorded INIT: the pod picks a fresh ephemeral key and nonce, so the
    // recorded FINISH (bound to the old transcript) fails
    p.pod.handle(&a[..n], false, &mut CountRng(14), &mut b).unwrap();
    let o = p.pod.handle(&c[..m], false, &mut CountRng(15), &mut b).unwrap();
    assert!(matches!(o.event, Event::None));
}

#[test]
fn handshake_frames_with_bad_crc_flags_or_type_are_dropped() {
    let mut pod = Responder::new(None);
    let ini = Initiator::pair(&mut CountRng(1), b"");
    let (mut a, mut b) = ([0u8; 244], [0u8; 244]);
    let n = ini.init_frame(0, &mut a).unwrap();
    let mut bad = a;
    bad[10] ^= 1;
    assert!(pod.handle(&bad[..n], true, &mut CountRng(2), &mut b).is_none());
    let mut enc = a;
    enc[2] = FLAG_ENCRYPTED;
    assert!(pod.handle(&enc[..n], true, &mut CountRng(2), &mut b).is_none());
    assert!(!is_handshake_frame(&[1, cmd::BOLUS, 0]));
    assert!(is_handshake_frame(&[1, htype::SESSION_FINISH, 0]));
    assert!(pod.handle(&[1, cmd::GET_STATUS, 0, 1, 0, 0, 0, 0xBB, 0x7A], true, &mut CountRng(2), &mut b).is_none());
}

#[test]
fn initiator_rejects_a_tampered_pod_response() {
    let mut p = do_pairing(b"", b"").unwrap();
    let mut ini = Initiator::session(&mut CountRng(1), p.ps);
    let (mut a, mut b, mut c) = ([0u8; 244], [0u8; 244], [0u8; 244]);
    let n = ini.init_frame(0, &mut a).unwrap();
    let o = p.pod.handle(&a[..n], false, &mut CountRng(2), &mut b).unwrap();
    // flip a bit of the pod's ephemeral key and fix the CRC: the confirmation no longer verifies
    let mut t = b;
    t[7 + 3 + 3] ^= 0x40;
    let l = o.reply_len;
    let crc = crc::crc16_ccitt_false(&t[..l - 2]);
    t[l - 2..l].copy_from_slice(&crc.to_le_bytes());
    assert_eq!(ini.on_init_response(&t[..l], 1, &mut c), Err(HsError::BadConfirm));
}

// ---------------------------------------------------------------------------------------------
// Shared vectors
// ---------------------------------------------------------------------------------------------

fn handshake_case(name: &str, mode: Mode, ps: Option<[u8; 32]>, oob: &[u8], seeds: (u8, u8, u8, u8)) -> (Value, Option<[u8; 32]>, Option<SessionKeys>) {
    let app_secret: [u8; 32] = pattern(seeds.0);
    let app_nonce: [u8; 16] = pattern(seeds.1);
    let pod_secret: [u8; 32] = pattern(seeds.2);
    let pod_nonce: [u8; 16] = pattern(seeds.3);
    let mut ini_rng = FixedRng::new(&[&app_secret, &app_nonce]);
    let mut pod_rng = FixedRng::new(&[&pod_secret, &pod_nonce]);
    let mut ini = match mode {
        Mode::Pair => Initiator::pair(&mut ini_rng, oob),
        Mode::Session => Initiator::session(&mut ini_rng, ps.unwrap()),
    };
    let mut pod = Responder::new(if mode == Mode::Session { ps } else { None });
    pod.set_oob(oob);
    let (mut f1, mut f2, mut f3, mut f4) = ([0u8; 244], [0u8; 244], [0u8; 244], [0u8; 244]);
    let n1 = ini.init_frame(0, &mut f1).unwrap();
    let o2 = pod.handle(&f1[..n1], true, &mut pod_rng, &mut f2).unwrap();
    let n3 = ini.on_init_response(&f2[..o2.reply_len], 1, &mut f3).unwrap();
    let o4 = pod.handle(&f3[..n3], true, &mut pod_rng, &mut f4).unwrap();
    let outcome = ini.on_finish_response(&f4[..o4.reply_len]).unwrap();

    let pub_a = public_key(&app_secret);
    let pub_b = public_key(&pod_secret);
    let dh = shared_secret(&app_secret, &pub_b).unwrap();
    assert_eq!(dh, shared_secret(&pod_secret, &pub_a).unwrap());
    let id = ps.map_or([0u8; 4], |p| ps_id(&p));
    let th = transcript_hash(&Transcript { mode, ps_id: id, pub_a: &pub_a, pub_b: &pub_b, nonce_a: &app_nonce, nonce_b: &pod_nonce });
    let mut v = json!({
        "name": name,
        "mode": if mode == Mode::Pair { "pair" } else { "session" },
        "oob": hex(oob),
        "app_eph_secret": hex(&app_secret), "app_nonce": hex(&app_nonce),
        "pod_eph_secret": hex(&pod_secret), "pod_nonce": hex(&pod_nonce),
        "app_eph_public": hex(&pub_a), "pod_eph_public": hex(&pub_b),
        "dh": hex(&dh),
        "ps_id": hex(&id),
        "transcript_hash": hex(&th),
        "frames": {
            "init_request": hex(&f1[..n1]), "init_response": hex(&f2[..o2.reply_len]),
            "finish_request": hex(&f3[..n3]), "finish_response": hex(&f4[..o4.reply_len]),
        },
    });
    let (new_ps, keys) = match outcome {
        Outcome::Paired(p) => {
            let (ps2, ck) = derive_pairing(&dh, &oob_salt(oob), &th);
            assert_eq!(ps2, p);
            v["oob_salt"] = json!(hex(&oob_salt(oob)));
            v["ps"] = json!(hex(&p));
            v["confirm_key"] = json!(hex(&ck));
            v["confirm_pod"] = json!(hex(&confirm_tag(&ck, Side::Pod, &th)));
            v["confirm_app"] = json!(hex(&confirm_tag(&ck, Side::App, &th)));
            (Some(p), None)
        }
        Outcome::Session(k) => {
            let (k2, ck) = derive_session(&dh, &ps.unwrap(), &th);
            assert!(k2 == k);
            v["ps"] = json!(hex(&ps.unwrap()));
            v["key_c2p"] = json!(hex(&k.key_c2p));
            v["key_p2c"] = json!(hex(&k.key_p2c));
            v["salt"] = json!(hex(&k.salt));
            v["confirm_key"] = json!(hex(&ck));
            v["confirm_pod"] = json!(hex(&confirm_tag(&ck, Side::Pod, &th)));
            v["confirm_app"] = json!(hex(&confirm_tag(&ck, Side::App, &th)));
            (None, Some(k))
        }
    };
    (v, new_ps, keys)
}

fn traffic(keys: &SessionKeys) -> Value {
    let mut phone = sess(keys);
    let mut pod = sess(keys);
    let mut out = Vec::new();
    let mut buf = [0u8; 244];
    let mut push = |name: &str, dir: u8, type_: u8, seq: u16, payload: &[u8], frame: &[u8]| {
        out.push(json!({"name": name, "dir": dir, "type": type_, "seq": seq, "payload": hex(payload), "frame": hex(frame)}));
    };
    // GetStatus with TIME_OF_DAY_MS = 12:00:00.000 = 43 200 000 ms
    let status = [tag::TIME_OF_DAY_MS, 4, 0x80, 0xF7, 0x92, 0x02];
    let n = phone.seal(false, cmd::GET_STATUS, 1, true, &status, &mut buf).unwrap();
    push("command GetStatus", 0, cmd::GET_STATUS, 1, &status, &buf[..n]);
    // Bolus 2.00 U
    let bolus = [tag::AMOUNT_MU, 4, 0xD0, 0x07, 0, 0];
    let n = phone.seal(false, cmd::BOLUS, 2, true, &bolus, &mut buf).unwrap();
    push("command Bolus 2.00 U", 0, cmd::BOLUS, 2, &bolus, &buf[..n]);
    // response RESULT OK echoing seq 2 (nonce direction 1)
    let ok = [tag::RESULT, 1, 0];
    let n = pod.seal(true, cmd::BOLUS | RSP_BIT, 2, true, &ok, &mut buf).unwrap();
    push("response Bolus OK", 1, cmd::BOLUS | RSP_BIT, 2, &ok, &buf[..n]);
    // notification (Alert characteristic, type 0x90, nonce direction 2, pod's own counter)
    let note = [tag::NOTIFY_KIND, 1, notify::DRAW_DONE, tag::NOTIFY_ARG, 4, 0xE8, 0x03, 0, 0];
    let n = pod.seal_notification(notify::FRAME_TYPE, 1, true, &note, &mut buf).unwrap();
    push("notification draw done", 2, notify::FRAME_TYPE, 1, &note, &buf[..n]);
    Value::Array(out)
}

fn compute_vectors() -> Value {
    let (pair0, ps, _) = handshake_case("pairing without out-of-band code", Mode::Pair, None, b"", (0x10, 0x90, 0x50, 0xB0));
    let (pair1, _, _) = handshake_case("pairing with out-of-band code 123456", Mode::Pair, None, b"123456", (0x11, 0x91, 0x51, 0xB1));
    let ps = ps.unwrap();
    let (session, _, keys) = handshake_case("session using the pairing secret of the first pairing case", Mode::Session, Some(ps), b"", (0x20, 0xA0, 0x60, 0xC0));
    let keys = keys.unwrap();
    json!({
        "description": "OpenPatch protocol v1.1 section 5.2 test vectors (docs/04-protocol.md). Generated by firmware-rs/openpatch-proto/tests/handshake.rs, consumed by the Rust and the Swift suites. All values are hex.",
        "version": 1,
        "primitives": {
            "x25519_rfc7748_6_1": {"alice_secret": RFC7748_ALICE_SECRET, "alice_public": RFC7748_ALICE_PUBLIC, "bob_secret": RFC7748_BOB_SECRET, "bob_public": RFC7748_BOB_PUBLIC, "shared": RFC7748_SHARED},
            "hkdf_sha256_rfc5869_a1": {
                "ikm": "0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b", "salt": "000102030405060708090a0b0c", "info": "f0f1f2f3f4f5f6f7f8f9", "length": 42,
                "okm": "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865",
            },
            "aes128_ccm_rfc3610_packet_vector_1": {
                "key": "c0c1c2c3c4c5c6c7c8c9cacbcccdcecf", "nonce": "00000003020100a0a1a2a3a4a5", "aad": "0001020304050607",
                "plaintext": "08090a0b0c0d0e0f101112131415161718191a1b1c1d1e", "ciphertext": "588c979a61c663d2f066d0c2c0f989806d5f6b61dac384", "tag": "17e8d12cfdf926e0",
            },
        },
        "pairing": [pair0, pair1],
        "session": session,
        "traffic": traffic(&keys),
        "low_order_public_keys": [hex(&[0u8; 32]), "0100000000000000000000000000000000000000000000000000000000000000"],
    })
}

#[test]
fn hkdf_and_ccm_primitives_match_the_published_vectors() {
    use hkdf::Hkdf;
    use sha2::Sha256;
    let all = compute_vectors();
    let v = &all["primitives"];
    let h = &v["hkdf_sha256_rfc5869_a1"];
    let hk = Hkdf::<Sha256>::new(Some(&unhex(h["salt"].as_str().unwrap())), &unhex(h["ikm"].as_str().unwrap()));
    let mut okm = [0u8; 42];
    hk.expand(&unhex(h["info"].as_str().unwrap()), &mut okm).unwrap();
    assert_eq!(hex(&okm), h["okm"].as_str().unwrap());

    let c = &v["aes128_ccm_rfc3610_packet_vector_1"];
    let mut ccm = AesCcm::new(&arr(c["key"].as_str().unwrap()));
    let pt = unhex(c["plaintext"].as_str().unwrap());
    let mut ct = vec![0u8; pt.len()];
    let mut tag = [0u8; 8];
    ccm.encrypt(&arr(c["nonce"].as_str().unwrap()), &unhex(c["aad"].as_str().unwrap()), &pt, &mut ct, &mut tag).unwrap();
    assert_eq!(hex(&ct), c["ciphertext"].as_str().unwrap());
    assert_eq!(hex(&tag), c["tag"].as_str().unwrap());
}

#[test]
fn vectors_file_matches_the_implementation() {
    let computed = compute_vectors();
    if std::env::var("OPENPATCH_WRITE_VECTORS").is_ok() {
        std::fs::write(VECTOR_FILE, serde_json::to_string_pretty(&computed).unwrap() + "\n").unwrap();
    }
    let stored: Value = serde_json::from_str(&std::fs::read_to_string(VECTOR_FILE).expect("vector file missing: run with OPENPATCH_WRITE_VECTORS=1")).unwrap();
    assert_eq!(stored, computed, "docs/vectors/session-key-agreement.json is stale");
    check_stored_traffic();
}

fn check_stored_traffic() {
    let stored: Value = serde_json::from_str(&std::fs::read_to_string(VECTOR_FILE).unwrap()).unwrap();
    let s = &stored["session"];
    let keys = SessionKeys { key_c2p: arr(s["key_c2p"].as_str().unwrap()), key_p2c: arr(s["key_p2c"].as_str().unwrap()), salt: arr(s["salt"].as_str().unwrap()) };
    let mut ccm = AesCcm::directional(&keys.key_c2p, &keys.key_p2c);
    for t in stored["traffic"].as_array().unwrap() {
        let frame = unhex(t["frame"].as_str().unwrap());
        let f = decode_frame(&frame).unwrap();
        assert_ne!(f.flags & FLAG_ENCRYPTED, 0);
        let dir = t["dir"].as_u64().unwrap() as u8;
        let mut nonce = [0u8; 13];
        nonce[..4].copy_from_slice(&keys.salt);
        nonce[4] = dir;
        nonce[5..7].copy_from_slice(&f.seq.to_le_bytes());
        let ct_len = f.payload.len() - 8;
        let mut pt = vec![0u8; ct_len];
        let mut tag = [0u8; 8];
        tag.copy_from_slice(&f.payload[ct_len..]);
        ccm.decrypt(&nonce, &frame[..7], &f.payload[..ct_len], &tag, &mut pt).unwrap();
        assert_eq!(hex(&pt), t["payload"].as_str().unwrap());
        // flipping the direction (a reflected frame) must fail authentication
        nonce[4] = if dir == 0 { 1 } else { 0 };
        assert!(ccm.decrypt(&nonce, &frame[..7], &f.payload[..ct_len], &tag, &mut pt).is_err());
    }
}
