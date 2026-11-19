//! Executable checks of the v1.1 handshake implementation (firmware-rs/openpatch-proto/src/handshake.rs) that the
//! symbolic models (security/formal) cannot express: concrete behaviour on garbage, pending-slot semantics, identifier
//! linkability. Needs feature `handshake`:  cargo test --release --features handshake --test handshake_props
#![cfg(feature = "handshake")]
use openpatch_proto::handshake::*;
use openpatch_proto::FRAME_MAX;
use proptest::prelude::*;
use rand_core::{Error as RngError, RngCore};

/// Deterministic test RNG (xorshift64*). NOT for production.
struct Det(u64);
impl RngCore for Det {
    fn next_u32(&mut self) -> u32 {
        self.next_u64() as u32
    }
    fn next_u64(&mut self) -> u64 {
        self.0 ^= self.0 >> 12;
        self.0 ^= self.0 << 25;
        self.0 ^= self.0 >> 27;
        self.0.wrapping_mul(0x2545F4914F6CDD1D)
    }
    fn fill_bytes(&mut self, d: &mut [u8]) {
        for c in d.chunks_mut(8) {
            let b = self.next_u64().to_le_bytes();
            c.copy_from_slice(&b[..c.len()]);
        }
    }
    fn try_fill_bytes(&mut self, d: &mut [u8]) -> Result<(), RngError> {
        self.fill_bytes(d);
        Ok(())
    }
}

fn pair_up(pod: &mut Responder, rng: &mut Det) -> [u8; PS_LEN] {
    let mut app = Initiator::pair(rng, b"");
    let (mut b1, mut b2, mut b3) = ([0u8; FRAME_MAX], [0u8; FRAME_MAX], [0u8; FRAME_MAX]);
    let n = app.init_frame(0, &mut b1).unwrap();
    let o = pod.handle(&b1[..n], true, rng, &mut b2).unwrap();
    let m = app.on_init_response(&b2[..o.reply_len], 1, &mut b3).unwrap();
    let o2 = pod.handle(&b3[..m], true, rng, &mut b2).unwrap();
    let ps = match o2.event {
        Event::Paired(p) => p,
        _ => panic!("pod did not pair"),
    };
    match app.on_finish_response(&b2[..o2.reply_len]).unwrap() {
        Outcome::Paired(p) => assert_eq!(p, ps),
        _ => panic!(),
    }
    ps
}

proptest! {
    #![proptest_config(ProptestConfig { cases: 20_000, .. ProptestConfig::default() })]

    /// The responder never panics on arbitrary bytes and garbage never yields a pairing or a session.
    #[test]
    fn responder_total_on_garbage(bytes in proptest::collection::vec(any::<u8>(), 0..300), open in any::<bool>(), seed in 1u64..u64::MAX) {
        let mut rng = Det(seed);
        let mut pod = Responder::new(Some([7u8; 32]));
        let mut out = [0u8; FRAME_MAX];
        if let Some(o) = pod.handle(&bytes, open, &mut rng, &mut out) {
            prop_assert!(matches!(o.event, Event::None));
        }
    }
}

#[test]
fn honest_pairing_then_session_agree() {
    let mut rng = Det(42);
    let mut pod = Responder::new(None);
    let ps = pair_up(&mut pod, &mut rng);
    let mut app = Initiator::session(&mut rng, ps);
    let (mut b1, mut b2, mut b3) = ([0u8; FRAME_MAX], [0u8; FRAME_MAX], [0u8; FRAME_MAX]);
    let n = app.init_frame(0, &mut b1).unwrap();
    let o = pod.handle(&b1[..n], false, &mut rng, &mut b2).unwrap();
    assert!(matches!(o.event, Event::None), "no keys before the phone's confirmation verified");
    let m = app.on_init_response(&b2[..o.reply_len], 1, &mut b3).unwrap();
    let o2 = pod.handle(&b3[..m], false, &mut rng, &mut b2).unwrap();
    let Event::SessionUp(k_pod) = o2.event else { panic!("no session") };
    let Outcome::Session(k_app) = app.on_finish_response(&b2[..o2.reply_len]).unwrap() else { panic!() };
    assert!(k_pod == k_app);
}

#[test]
fn pairing_refused_outside_window() {
    let mut rng = Det(1);
    let mut pod = Responder::new(None);
    let mut app = Initiator::pair(&mut rng, b"");
    let (mut b1, mut b2) = ([0u8; FRAME_MAX], [0u8; FRAME_MAX]);
    let n = app.init_frame(0, &mut b1).unwrap();
    let o = pod.handle(&b1[..n], false, &mut rng, &mut b2).unwrap();
    assert!(matches!(app.on_init_response(&b2[..o.reply_len], 1, &mut b1), Err(HsError::Rejected(r)) if r == hresult::AUTH));
}

#[test]
fn wrong_pairing_secret_cannot_open_a_session() {
    let mut rng = Det(3);
    let mut pod = Responder::new(None);
    let ps = pair_up(&mut pod, &mut rng);
    let mut wrong = ps;
    wrong[0] ^= 1;
    let mut app = Initiator::session(&mut rng, wrong);
    let (mut b1, mut b2) = ([0u8; FRAME_MAX], [0u8; FRAME_MAX]);
    let n = app.init_frame(0, &mut b1).unwrap();
    let o = pod.handle(&b1[..n], false, &mut rng, &mut b2).unwrap();
    // PS_ID differs, so the pod answers PAIR (and no keys): an attacker without PS gets nothing to attack offline.
    assert!(matches!(app.on_init_response(&b2[..o.reply_len], 1, &mut b1), Err(HsError::Rejected(r)) if r == hresult::PAIR));
}

#[test]
fn low_order_public_keys_are_rejected() {
    let mut rng = Det(5);
    let mut pod = Responder::new(None);
    for pubkey in [[0u8; 32], { let mut p = [0u8; 32]; p[0] = 1; p }] {
        let mut app = Initiator::pair(&mut rng, b"");
        let mut b1 = [0u8; FRAME_MAX];
        let n = app.init_frame(0, &mut b1).unwrap();
        // splice the low-order key into the EPH_PUB TLV: header(7) | tag 0x30 | len 32 | key ... | crc
        let mut f = b1[..n].to_vec();
        f[9..41].copy_from_slice(&pubkey);
        let crc = openpatch_proto::crc::crc16_ccitt_false(&f[..n - 2]);
        f[n - 2..].copy_from_slice(&crc.to_le_bytes());
        let mut out = [0u8; FRAME_MAX];
        let o = pod.handle(&f, true, &mut rng, &mut out).unwrap();
        let r = openpatch_proto::decode_frame(&out[..o.reply_len]).unwrap();
        assert_eq!(&r.payload[..3], &[0x01, 1, hresult::BAD_ARG], "low-order key must be answered BAD_ARG");
    }
}

/// FINDING-004 (low-medium) -- MITIGATED. Anyone who can read the (cleartext, static) PS_ID could replay the phone's
/// INIT between its INIT and FINISH and displace the single pending handshake, so the phone's FINISH failed. The
/// responder now keeps `PENDING_SLOTS` half-open handshakes and a FINISH is matched to its slot by the key confirmation
/// tag (which needs the session keys), a failed FINISH discards nothing. One replayed INIT, or any number of bogus
/// FINISH frames, no longer displaces the phone. Residual (documented, proposal 03 s.5): a flood of >= PENDING_SLOTS
/// INITs inside one handshake round trip still evicts the oldest slot; that needs a rate limit on a pod clock.
#[test]
fn fixed_pending_slot_cannot_be_displaced_by_one_replayed_init_or_bogus_finish() {
    let mut rng = Det(9);
    let mut pod = Responder::new(None);
    let ps = pair_up(&mut pod, &mut rng);
    let mut phone = Initiator::session(&mut rng, ps);
    let (mut b1, mut b2, mut b3, mut b4) = ([0u8; FRAME_MAX], [0u8; FRAME_MAX], [0u8; FRAME_MAX], [0u8; FRAME_MAX]);
    let n = phone.init_frame(0, &mut b1).unwrap();
    let o = pod.handle(&b1[..n], false, &mut rng, &mut b2).unwrap();
    // the attacker replays the observed phone INIT (PS_ID in clear): used to replace the pending handshake
    let _ = pod.handle(&b1[..n], false, &mut rng, &mut b4).unwrap();
    // ... and sends a FINISH with a made-up confirm tag: used to discard it
    let mut bogus = Vec::new();
    {
        let mut tmp = [0u8; FRAME_MAX];
        let mut w = openpatch_proto::tlv::TlvWriter::new(&mut tmp);
        w.put(htag::CONFIRM, &[0xAB; 16]);
        let l = w.finish().unwrap();
        bogus.extend_from_slice(&tmp[..l]);
    }
    let mut fb = [0u8; FRAME_MAX];
    let fl = openpatch_proto::encode_frame(
        &openpatch_proto::Frame { version: 1, type_: htype::SESSION_FINISH, flags: 0, seq: 9, payload: &bogus },
        &mut fb,
    )
    .unwrap();
    let _ = pod.handle(&fb[..fl], false, &mut rng, &mut b4).unwrap();
    // the phone's genuine FINISH still succeeds
    let m = phone.on_init_response(&b2[..o.reply_len], 1, &mut b3).unwrap();
    let o2 = pod.handle(&b3[..m], false, &mut rng, &mut b2).unwrap();
    assert!(matches!(o2.event, Event::SessionUp(_)), "FINDING-004: the phone's handshake was displaced");
    let r = openpatch_proto::decode_frame(&b2[..o2.reply_len]).unwrap();
    assert_eq!(&r.payload[..3], &[0x01, 1, hresult::OK]);
}

/// The residual risk stays visible: PENDING_SLOTS or more INITs between the phone's INIT and FINISH evict its slot.
#[test]
fn residual_finding_004_an_init_flood_still_evicts_the_oldest_pending() {
    let mut rng = Det(10);
    let mut pod = Responder::new(None);
    let ps = pair_up(&mut pod, &mut rng);
    let mut phone = Initiator::session(&mut rng, ps);
    let (mut b1, mut b2, mut b3, mut b4) = ([0u8; FRAME_MAX], [0u8; FRAME_MAX], [0u8; FRAME_MAX], [0u8; FRAME_MAX]);
    let n = phone.init_frame(0, &mut b1).unwrap();
    let o = pod.handle(&b1[..n], false, &mut rng, &mut b2).unwrap();
    for _ in 0..PENDING_SLOTS {
        let _ = pod.handle(&b1[..n], false, &mut rng, &mut b4).unwrap();
    }
    let m = phone.on_init_response(&b2[..o.reply_len], 1, &mut b3).unwrap();
    let o2 = pod.handle(&b3[..m], false, &mut rng, &mut b2).unwrap();
    assert!(matches!(o2.event, Event::None));
}

/// FINDING-005 (low, privacy): PS_ID is a 4 byte STATIC identifier of the pairing, sent in clear in every SESSION_INIT.
/// Anyone who can read the (link-layer encrypted, but possibly Just-Works) traffic can link all sessions of one phone/pod pair.
#[test]
fn known_issue_ps_id_is_a_static_linkable_identifier() {
    let mut rng = Det(11);
    let mut pod = Responder::new(None);
    let ps = pair_up(&mut pod, &mut rng);
    let mut ids = Vec::new();
    for _ in 0..3 {
        let app = Initiator::session(&mut rng, ps);
        let mut b = [0u8; FRAME_MAX];
        let n = app.init_frame(0, &mut b).unwrap();
        let f = openpatch_proto::decode_frame(&b[..n]).unwrap();
        let tlvs: Vec<_> = openpatch_proto::tlv::TlvReader::new(f.payload).map(|x| x.unwrap()).collect();
        let id = tlvs.iter().find(|(t, _)| *t == htag::PS_ID).unwrap().1.to_vec();
        ids.push(id);
    }
    assert!(ids.windows(2).all(|w| w[0] == w[1]), "same PS_ID in every session (linkable)");
}
