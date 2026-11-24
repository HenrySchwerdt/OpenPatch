//! The supervisor flasher against a simulated STM32C011 ROM bootloader (AN3155 framing as implemented by
//! `openpatch_supervisor::rom_bootloader`), with REAL Ed25519 / SHA-512. Water-only bench project, never worn.
use ed25519_dalek::{Signer, SigningKey, VerifyingKey};
use openpatch_boot_policy::manifest::DOMAIN;
use openpatch_boot_policy::{Digest512, ImageSource, Manifest, Reject, SigCheck, HW_ID_CUP_V4, HW_ID_SUP_C011, MANIFEST_LEN};
use openpatch_supervisor::flash_guard::{Preconditions, Refusal};
use openpatch_supervisor::rom_bootloader::{StrapStep, ACK, NACK};
use openpatch_supflash::*;
use sha2::{Digest, Sha512};

// ---- crypto and image helpers ---------------------------------------------------------------------------------------------

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

/// Image in "nRF flash". `flip_after_reads`: after that many reads, byte 0 changes (a source that is rewritten between the
/// verification and the write pass).
struct Mem {
    data: Vec<u8>,
    reads: usize,
    flip_after_reads: Option<usize>,
}
impl Mem {
    fn new(d: &[u8]) -> Self {
        Mem { data: d.to_vec(), reads: 0, flip_after_reads: None }
    }
}
impl ImageSource for Mem {
    fn read(&mut self, off: u32, buf: &mut [u8]) -> bool {
        self.reads += 1;
        if Some(self.reads) == self.flip_after_reads {
            self.data[0] ^= 0xFF;
        }
        let o = off as usize;
        if o + buf.len() > self.data.len() {
            return false;
        }
        buf.copy_from_slice(&self.data[o..o + buf.len()]);
        true
    }
}

fn sk() -> SigningKey {
    SigningKey::from_bytes(&[9u8; 32])
}
fn key() -> Key {
    Key(sk().verifying_key())
}
fn image(n: usize) -> Vec<u8> {
    (0..n).map(|i| (i * 13 + 5) as u8).collect()
}
fn sign_with(k: &SigningKey, img: &[u8], version: u32, hw: u32) -> [u8; MANIFEST_LEN] {
    let mut m = Manifest { image_len: img.len() as u32, version, hw_id: hw, signature: [0; 64] };
    let mut h = Sha512::new();
    Digest::update(&mut h, DOMAIN);
    Digest::update(&mut h, m.header());
    Digest::update(&mut h, img);
    let d: [u8; 64] = h.finalize().into();
    m.signature = k.sign(&d).to_bytes();
    m.encode()
}
fn sign(img: &[u8], version: u32) -> [u8; MANIFEST_LEN] {
    sign_with(&sk(), img, version, HW_ID_SUP_C011)
}

/// A pod that is ready for the update: supply cut for long enough, undocked, idle, full cell.
fn ready() -> Preconditions {
    Preconditions { vmot_mv: Some(20), vmot_low_for_ms: 500, docked: false, delivery_active: false, image_verified: false, vbat_mv: 4_000 }
}

// ---- the simulated ROM bootloader -----------------------------------------------------------------------------------------

const FLASH: usize = 16 * 1024;
const PAGE: usize = 2048;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Expect {
    Cmd,
    ReadAddr,
    ReadLen(u32),
    WriteAddr,
    WriteData(u32),
    Erase,
}

#[derive(Default, Clone)]
struct Faults {
    /// Product id answered by GetId.
    pid: Option<u16>,
    /// Commands left out of the Get answer.
    hide_cmd: Option<u8>,
    /// Read-out protection active at start.
    rdp: bool,
    /// The read-out unprotect leaves RDP active (a broken part).
    rdp_sticks: bool,
    /// NACK the n-th write data frame (0 based).
    nack_write: Option<usize>,
    /// Flip a bit in flash at this address when it is written.
    corrupt_at: Option<u32>,
    /// Never answer anything.
    silent: bool,
    /// Answer the first `n` init bytes with nothing.
    silent_inits: usize,
    /// Answer this byte instead of ACK to the GetId command.
    garbage_on_getid: Option<u8>,
    /// Drop (time out) the ACK of the erase payload.
    erase_timeout: bool,
}

struct Peer {
    f: Faults,
    flash: Vec<u8>,
    rdp: bool,
    boot0: bool,
    nrst_low: bool,
    in_bootloader: bool,
    synced: bool,
    even: bool,
    expect: Expect,
    out: Vec<u8>,
    writes: usize,
    inits: usize,
    resets: usize,
    straps: Vec<StrapStep>,
    sends: usize,
    /// Every command code received, in order.
    cmds: Vec<u8>,
}

impl Peer {
    fn new(f: Faults) -> Self {
        let rdp = f.rdp;
        Peer {
            f,
            flash: vec![0x5A; FLASH], // old image
            rdp,
            boot0: false,
            nrst_low: false,
            in_bootloader: false,
            synced: false,
            even: false,
            expect: Expect::Cmd,
            out: vec![],
            writes: 0,
            inits: 0,
            resets: 0,
            straps: vec![],
            sends: 0,
            cmds: vec![],
        }
    }

    fn strap(&mut self, s: StrapStep) {
        self.straps.push(s);
        match s {
            StrapStep::Boot0(b) => self.boot0 = b,
            StrapStep::NrstLow(true) => self.nrst_low = true,
            StrapStep::NrstLow(false) => {
                if self.nrst_low {
                    self.resets += 1;
                    self.reset();
                }
                self.nrst_low = false;
            }
            StrapStep::UartEven => self.even = true,
            StrapStep::UartNone => self.even = false,
            StrapStep::WaitMs(_) | StrapStep::SendInit => {}
        }
    }

    fn reset(&mut self) {
        self.in_bootloader = self.boot0;
        self.synced = false;
        self.expect = Expect::Cmd;
        self.out.clear();
    }

    fn send(&mut self, b: &[u8]) {
        self.sends += 1;
        if self.f.silent || !self.in_bootloader || !self.even || self.nrst_low {
            return;
        }
        if !self.synced {
            if b == [0x7F] {
                self.inits += 1;
                if self.inits > self.f.silent_inits {
                    self.synced = true;
                    self.out.push(ACK);
                }
            }
            return;
        }
        match self.expect {
            Expect::Cmd => self.command(b),
            Expect::ReadAddr => match addr(b) {
                Some(a) => {
                    self.out.push(ACK);
                    self.expect = Expect::ReadLen(a);
                }
                None => self.nack(),
            },
            Expect::ReadLen(a) => {
                if b.len() == 2 && b[0] ^ b[1] == 0xFF {
                    let n = b[0] as usize + 1;
                    let o = (a - 0x0800_0000) as usize;
                    self.out.push(ACK);
                    self.out.extend_from_slice(&self.flash[o..o + n]);
                    self.expect = Expect::Cmd;
                } else {
                    self.nack();
                }
            }
            Expect::WriteAddr => match addr(b) {
                Some(a) => {
                    self.out.push(ACK);
                    self.expect = Expect::WriteData(a);
                }
                None => self.nack(),
            },
            Expect::WriteData(a) => {
                let n = b[0] as usize + 1;
                let ok = b.len() == n + 2 && b[..n + 1].iter().fold(0, |x, y| x ^ y) == b[n + 1];
                let idx = self.writes;
                self.writes += 1;
                if !ok || self.f.nack_write == Some(idx) {
                    self.nack();
                    return;
                }
                let o = (a - 0x0800_0000) as usize;
                for i in 0..n {
                    // NOR flash: programming can only clear bits of an erased word
                    self.flash[o + i] &= b[1 + i];
                    if self.f.corrupt_at == Some(a + i as u32) {
                        self.flash[o + i] ^= 0x04;
                    }
                }
                self.out.push(ACK);
                self.expect = Expect::Cmd;
            }
            Expect::Erase => {
                let ck = b[..b.len() - 1].iter().fold(0, |x, y| x ^ y);
                if ck != b[b.len() - 1] {
                    self.nack();
                    return;
                }
                let n = u16::from_be_bytes([b[0], b[1]]) as usize + 1;
                for k in 0..n {
                    let p = u16::from_be_bytes([b[2 + 2 * k], b[3 + 2 * k]]) as usize;
                    self.flash[p * PAGE..(p + 1) * PAGE].fill(0xFF);
                }
                if !self.f.erase_timeout {
                    self.out.push(ACK);
                }
                self.expect = Expect::Cmd;
            }
        }
    }

    fn nack(&mut self) {
        self.out.push(NACK);
        self.expect = Expect::Cmd;
    }

    fn command(&mut self, b: &[u8]) {
        if b.len() != 2 || b[0] ^ b[1] != 0xFF {
            self.out.push(NACK);
            return;
        }
        self.cmds.push(b[0]);
        match b[0] {
            0x00 => {
                let mut cmds = vec![0x00, 0x01, 0x02, 0x11, 0x21, 0x31, 0x44, 0x63, 0x73, 0x82, 0x92];
                if let Some(h) = self.f.hide_cmd {
                    cmds.retain(|&c| c != h);
                }
                self.out.push(ACK);
                self.out.push(cmds.len() as u8);
                self.out.push(0x31); // bootloader version 3.1
                self.out.extend_from_slice(&cmds);
                self.out.push(ACK);
            }
            0x02 => {
                if let Some(g) = self.f.garbage_on_getid {
                    self.out.push(g);
                    return;
                }
                let pid = self.f.pid.unwrap_or(0x443).to_be_bytes();
                self.out.extend_from_slice(&[ACK, 1, pid[0], pid[1], ACK]);
            }
            0x11 => {
                if self.rdp {
                    self.out.push(NACK);
                } else {
                    self.out.push(ACK);
                    self.expect = Expect::ReadAddr;
                }
            }
            0x31 => {
                if self.rdp {
                    self.out.push(NACK);
                } else {
                    self.out.push(ACK);
                    self.expect = Expect::WriteAddr;
                }
            }
            0x44 => {
                if self.rdp {
                    self.out.push(NACK);
                } else {
                    self.out.push(ACK);
                    self.expect = Expect::Erase;
                }
            }
            0x92 => {
                // ACK, mass erase, RDP 0, ACK, then the part resets itself (BOOT0 still high: bootloader again, not synced)
                self.out.push(ACK);
                self.flash.fill(0xFF);
                self.rdp = self.f.rdp_sticks;
                self.out.push(ACK);
                self.synced = false;
            }
            _ => self.out.push(NACK),
        }
    }

    fn take(&mut self, n: usize) -> Option<Vec<u8>> {
        if self.out.len() < n {
            self.out.clear();
            return None;
        }
        Some(self.out.drain(..n).collect())
    }
}

fn addr(b: &[u8]) -> Option<u32> {
    if b.len() == 5 && b[..4].iter().fold(0, |x, y| x ^ y) == b[4] {
        Some(u32::from_be_bytes([b[0], b[1], b[2], b[3]]))
    } else {
        None
    }
}

// ---- driver loop (what the embedded task does with the UART and the strap pins) -------------------------------------------

struct Run {
    result: Result<Report, FlashError>,
    timeouts: Vec<u32>,
}

/// `vmot(i)` = the supply reading before poll number `i`.
fn drive(up: &mut Updater<Sha>, img: &mut Mem, peer: &mut Peer, mut vmot: impl FnMut(usize) -> Option<u16>) -> Run {
    enum Ev {
        Begin,
        Done,
        Rx,
        Timeout,
    }
    let mut ev = Ev::Begin;
    let mut rx: Vec<u8> = vec![];
    let mut timeouts = vec![];
    for i in 0..1_000_000 {
        let e = match ev {
            Ev::Begin => Event::Begin,
            Ev::Done => Event::Done,
            Ev::Rx => Event::Rx(&rx),
            Ev::Timeout => Event::Timeout,
        };
        match up.poll(img, vmot(i), e) {
            Action::Strap(s) => {
                peer.strap(s);
                ev = Ev::Done;
            }
            Action::Send(b) => {
                let b = b.to_vec();
                peer.send(&b);
                ev = Ev::Done;
            }
            Action::Recv { n, timeout_ms } => {
                timeouts.push(timeout_ms);
                match peer.take(n) {
                    Some(v) => {
                        rx = v;
                        ev = Ev::Rx;
                    }
                    None => ev = Ev::Timeout,
                }
            }
            Action::Finished(r) => return Run { result: r, timeouts },
        }
    }
    panic!("the updater never finished");
}

fn start(img: &[u8], m: &[u8], pre: Preconditions, min: u32) -> Result<(Updater<Sha>, Mem), FlashError> {
    let mut mem = Mem::new(img);
    let k = key();
    let up = Updater::<Sha>::begin(m, &mut mem, Some(&k), min, &pre)?;
    Ok((up, mem))
}

fn flash_ok(f: Faults, img: &[u8]) -> (Run, Peer) {
    let m = sign(img, 3);
    let (mut up, mut mem) = start(img, &m, ready(), 2).unwrap();
    let mut peer = Peer::new(f);
    let run = drive(&mut up, &mut mem, &mut peer, |_| Some(15));
    (run, peer)
}

fn assert_left_in_normal_boot(peer: &Peer) {
    // BOOT0 low at the end, reset pulse after it, UART back to 8N1: the supervisor boots its (new or erased) flash
    let s = &peer.straps;
    let last_boot0 = s.iter().rposition(|x| matches!(x, StrapStep::Boot0(_))).unwrap();
    assert_eq!(s[last_boot0], StrapStep::Boot0(false));
    assert!(s[last_boot0..].contains(&StrapStep::UartNone));
    assert!(s[last_boot0..].contains(&StrapStep::NrstLow(true)));
    assert_eq!(*s.last().unwrap(), StrapStep::WaitMs(100));
    assert!(!peer.boot0 && !peer.nrst_low && !peer.in_bootloader);
}

// ---- the happy paths ------------------------------------------------------------------------------------------------------

#[test]
fn a_signed_image_is_written_verified_and_the_supervisor_boots_normally() {
    let img = image(5_000);
    let (run, peer) = flash_ok(Faults::default(), &img);
    let r = run.result.unwrap();
    assert_eq!(r, Report { version: 3, image_len: 5_000, rdp_was_active: false, power_cycle_required: true });
    assert_eq!(&peer.flash[..5_000], &img[..]);
    assert!(peer.flash[5_000..].iter().all(|&b| b == 0xFF), "rest erased, tail padded with 0xFF");
    // entry: BOOT0 high before the reset pulse, then the 8E1 switch
    assert_eq!(peer.straps[0], StrapStep::Boot0(true));
    assert_eq!(&peer.straps[1..6], &[StrapStep::NrstLow(true), StrapStep::WaitMs(10), StrapStep::NrstLow(false), StrapStep::WaitMs(100), StrapStep::UartEven]);
    assert_left_in_normal_boot(&peer);
    // Get, GetId, read probe, erase, 20 x write (256 bytes), 20 x read back; no read-out unprotect on an unprotected part
    let writes = peer.cmds.iter().filter(|&&c| c == 0x31).count();
    let reads = peer.cmds.iter().filter(|&&c| c == 0x11).count();
    assert_eq!((writes, reads), (20, 21));
    assert!(!peer.cmds.contains(&0x92));
    assert_eq!(&peer.cmds[..3], &[0x00, 0x02, 0x11]);
    assert!(peer.cmds.contains(&0x44));
}

#[test]
fn a_protected_part_is_unprotected_re_entered_and_flashed() {
    let img = image(3_000);
    let (run, peer) = flash_ok(Faults { rdp: true, ..Default::default() }, &img);
    let r = run.result.unwrap();
    assert!(r.rdp_was_active);
    assert_eq!(&peer.flash[..3_000], &img[..]);
    assert_eq!(peer.cmds.iter().filter(|&&c| c == 0x92).count(), 1);
    // a second entry (reset pulse with BOOT0 high) after the self-reset of the read-out unprotect
    assert_eq!(peer.inits, 2);
    assert_left_in_normal_boot(&peer);
}

#[test]
fn an_image_length_that_is_not_a_multiple_of_eight_is_padded_and_verifies() {
    for n in [1usize, 7, 255, 257, 16 * 1024 - 3, 16 * 1024] {
        let img = image(n);
        let (run, peer) = flash_ok(Faults::default(), &img);
        assert!(run.result.is_ok(), "len {n}: {:?}", run.result);
        assert_eq!(&peer.flash[..n], &img[..]);
        assert!(peer.flash[n..].iter().all(|&b| b == 0xFF));
    }
}

#[test]
fn erase_and_writes_get_their_own_longer_timeouts() {
    let img = image(600);
    let (run, _) = flash_ok(Faults::default(), &img);
    assert!(run.timeouts.contains(&timing::ERASE_TIMEOUT_MS));
    assert!(run.timeouts.contains(&timing::WRITE_TIMEOUT_MS));
    assert!(run.timeouts.iter().all(|&t| t >= timing::ACK_TIMEOUT_MS));
}

// ---- refused before any pin moves -----------------------------------------------------------------------------------------

#[test]
fn unsigned_wrongly_signed_or_nrf_images_are_refused_before_anything_happens() {
    let img = image(1_000);
    let evil = sign_with(&SigningKey::from_bytes(&[1u8; 32]), &img, 3, HW_ID_SUP_C011);
    assert_eq!(start(&img, &evil, ready(), 0).err(), Some(FlashError::Image(Reject::BadSignature)));
    let nrf = sign_with(&sk(), &img, 3, HW_ID_CUP_V4);
    assert_eq!(start(&img, &nrf, ready(), 0).err(), Some(FlashError::Image(Reject::WrongHardware { got: HW_ID_CUP_V4 })));
    // no key compiled in: fail closed
    let m = sign(&img, 3);
    let mut mem = Mem::new(&img);
    assert_eq!(Updater::<Sha>::begin::<Key, _>(&m, &mut mem, None, 0, &ready()).err(), Some(FlashError::Image(Reject::NoKey)));
    // garbage manifest
    assert!(matches!(start(&img, &[0u8; 84], ready(), 0).err(), Some(FlashError::Image(Reject::Manifest(_)))));
}

#[test]
fn a_downgrade_is_refused() {
    let img = image(1_000);
    let m = sign(&img, 3);
    assert_eq!(start(&img, &m, ready(), 4).err(), Some(FlashError::Image(Reject::Rollback { version: 3, minimum: 4 })));
    assert!(start(&img, &m, ready(), 3).is_ok(), "the same version may be re-flashed");
}

#[test]
fn the_flash_guard_preconditions_are_enforced() {
    let img = image(1_000);
    let m = sign(&img, 3);
    let cases = [
        (Preconditions { vmot_mv: Some(4_900), ..ready() }, Refusal::SupplyPresent(4_900)),
        (Preconditions { vmot_mv: None, ..ready() }, Refusal::SupplyUnknown),
        (Preconditions { vmot_low_for_ms: 10, ..ready() }, Refusal::SupplyNotCutLongEnough),
        (Preconditions { docked: true, ..ready() }, Refusal::Docked),
        (Preconditions { delivery_active: true, ..ready() }, Refusal::DeliveryActive),
        (Preconditions { vbat_mv: 3_300, ..ready() }, Refusal::BatteryLow),
    ];
    for (p, why) in cases {
        assert_eq!(start(&img, &m, p, 0).err(), Some(FlashError::Refused(why)));
    }
    // the caller cannot claim a verified image: the flag is set by the updater's own verification only
    let evil = sign_with(&SigningKey::from_bytes(&[1u8; 32]), &img, 3, HW_ID_SUP_C011);
    let p = Preconditions { image_verified: true, ..ready() };
    assert_eq!(start(&img, &evil, p, 0).err(), Some(FlashError::Image(Reject::BadSignature)));
}

#[test]
fn the_image_source_must_hold_the_whole_image() {
    let img = image(1_000);
    let m = sign(&img, 3);
    let mut short = Mem::new(&img[..500]);
    let k = key();
    assert_eq!(Updater::<Sha>::begin(&m, &mut short, Some(&k), 0, &ready()).err(), Some(FlashError::Image(Reject::ReadError)));
}

// ---- failures on the wire: always leave the supervisor out of its bootloader ------------------------------------------------

fn flash_err(f: Faults, n: usize) -> (FlashError, Peer) {
    let img = image(n);
    let (run, peer) = flash_ok(f, &img);
    let e = run.result.unwrap_err();
    assert_left_in_normal_boot(&peer);
    (e, peer)
}

#[test]
fn a_wrong_product_id_stops_before_anything_is_erased() {
    let (e, peer) = flash_err(Faults { pid: Some(0x453), ..Default::default() }, 1_000);
    assert_eq!(e, FlashError::WrongId(0x453));
    assert!(peer.flash.iter().all(|&b| b == 0x5A), "old image untouched");
    assert!(!peer.cmds.contains(&0x44) && !peer.cmds.contains(&0x31) && !peer.cmds.contains(&0x92));
}

#[test]
fn a_silent_device_is_retried_then_given_up() {
    let (e, peer) = flash_err(Faults { silent: true, ..Default::default() }, 1_000);
    assert_eq!(e, FlashError::InitFailed);
    assert_eq!(peer.resets, timing::INIT_ATTEMPTS as usize + 1, "one reset per attempt plus the exit");
}

#[test]
fn a_late_autobaud_answer_is_caught_by_the_retry() {
    let img = image(800);
    let (run, peer) = flash_ok(Faults { silent_inits: 2, ..Default::default() }, &img);
    assert!(run.result.is_ok());
    assert_eq!(peer.inits, 3);
}

#[test]
fn a_nack_on_a_write_aborts() {
    let (e, peer) = flash_err(Faults { nack_write: Some(3), ..Default::default() }, 2_000);
    assert_eq!(e, FlashError::Nack(Stage::WriteData));
    assert_eq!(peer.writes, 4, "nothing written after the NACK");
}

#[test]
fn a_timeout_on_the_erase_aborts() {
    let (e, _) = flash_err(Faults { erase_timeout: true, ..Default::default() }, 2_000);
    assert_eq!(e, FlashError::Timeout(Stage::ErasePayload));
}

#[test]
fn a_byte_that_is_neither_ack_nor_nack_aborts() {
    let (e, _) = flash_err(Faults { garbage_on_getid: Some(0x00), ..Default::default() }, 2_000);
    assert_eq!(e, FlashError::Garbage(Stage::GetId, 0x00));
}

#[test]
fn a_bootloader_without_extended_erase_is_refused() {
    let (e, peer) = flash_err(Faults { hide_cmd: Some(0x44), ..Default::default() }, 2_000);
    assert_eq!(e, FlashError::MissingCommand(0x44));
    assert!(peer.flash.iter().all(|&b| b == 0x5A));
}

#[test]
fn a_part_that_stays_protected_after_the_unprotect_is_given_up() {
    let (e, peer) = flash_err(Faults { rdp: true, rdp_sticks: true, ..Default::default() }, 2_000);
    assert_eq!(e, FlashError::RdpStillActive);
    assert_eq!(peer.cmds.iter().filter(|&&c| c == 0x92).count(), 1, "only one unprotect (mass erase) per update");
}

#[test]
fn a_read_back_mismatch_is_reported_with_its_address() {
    let (e, _) = flash_err(Faults { corrupt_at: Some(0x0800_0123), ..Default::default() }, 2_000);
    assert_eq!(e, FlashError::VerifyMismatch { addr: 0x0800_0123 });
}

#[test]
fn a_source_that_changes_after_the_verification_is_caught_by_the_digest() {
    let img = image(2_000);
    let m = sign(&img, 3);
    let k = key();
    let mut mem = Mem::new(&img);
    let mut up = Updater::<Sha>::begin(&m, &mut mem, Some(&k), 0, &ready()).unwrap();
    // the verification read the image once (8 x 256 bytes): the next read (the first block of the write pass) sees a changed byte
    mem.flip_after_reads = Some(mem.reads + 1);
    let mut peer = Peer::new(Faults::default());
    let run = drive(&mut up, &mut mem, &mut peer, |_| Some(15));
    assert_eq!(run.result.unwrap_err(), FlashError::ImageChanged);
    assert_left_in_normal_boot(&peer);
    assert!(!peer.cmds.contains(&0x11) || peer.cmds.iter().filter(|&&c| c == 0x11).count() == 1, "no read-back pass");
}

#[test]
fn the_supply_coming_back_ends_the_session_and_no_frame_follows() {
    let img = image(4_000);
    let m = sign(&img, 3);
    let (mut up, mut mem) = start(&img, &m, ready(), 0).unwrap();
    let mut peer = Peer::new(Faults::default());
    let run = drive(&mut up, &mut mem, &mut peer, |i| if i >= 60 { Some(2_000) } else { Some(15) });
    assert_eq!(run.result.unwrap_err(), FlashError::SupplyReturned);
    assert_left_in_normal_boot(&peer);
    // and a missing reading is the same as a present supply
    let (mut up, mut mem) = start(&img, &m, ready(), 0).unwrap();
    let mut peer = Peer::new(Faults::default());
    let run = drive(&mut up, &mut mem, &mut peer, |i| if i >= 40 { None } else { Some(15) });
    assert_eq!(run.result.unwrap_err(), FlashError::SupplyReturned);
    assert_left_in_normal_boot(&peer);
}

#[test]
fn after_finishing_the_updater_only_repeats_the_result() {
    let img = image(300);
    let m = sign(&img, 3);
    let (mut up, mut mem) = start(&img, &m, ready(), 0).unwrap();
    let mut peer = Peer::new(Faults::default());
    let run = drive(&mut up, &mut mem, &mut peer, |_| Some(15));
    assert!(run.result.is_ok());
    let sends = peer.sends;
    for _ in 0..3 {
        assert!(matches!(up.poll(&mut mem, Some(15), Event::Done), Action::Finished(Ok(_))));
    }
    assert_eq!(peer.sends, sends);
}
