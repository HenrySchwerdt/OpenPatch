//! Flashing the STM32C011 supervisor from the nRF52840 through the ST system (ROM) bootloader. TEST PROJECT, never worn, water
//! only (`DISCLAIMER.md`).
//!
//! Board path (`electronics/v010/INTERLOCK.md` I.4, `FIRMWARE-PINMAP.md`): the nRF drives `SUP_BOOT0` (BOOT0 strap), pulls `SUP_NRST`
//! (open drain only) and talks on `SUP_RXD` / `SUP_TXD` (supervisor USART1, PA9/PA10 remapped to PA11/PA12 on the 20-pin package) at
//! 115200 8E1 during the update. A programming reset also clears the motor latch, and the supervisor in its bootloader holds
//! `SUP_PERMIT` low: the motor supply is cut twice while this runs.
//!
//! This crate is the platform independent half: a **sans-IO state machine** ([`Updater`]). The embedded driver owns the UART, the two
//! strap pins, a timer and the `VMOT_SENSE` ADC; it calls [`Updater::poll`] with the event of the previous action and does what the
//! returned [`Action`] says. Everything is host tested against a simulated ROM bootloader (`tests/flash.rs`).
//!
//! Sequence:
//! 1. [`Updater::begin`]: the image is verified with the boot-policy rules (manifest format 2, Ed25519 over
//!    `SHA-512("OPFW2" || header || image)`, hardware id [`HW_ID_SUP_C011`], at most 16 KiB, security version not below the given
//!    minimum = no downgrade; no key = refused), THEN the flash guard preconditions (`openpatch_supervisor::flash_guard`: supply below
//!    0.3 V for 50 ms, undocked, no delivery, cell >= 3.6 V). Nothing moves before both passed.
//! 2. Entry: `BOOT0` high, reset pulse 10 ms, 100 ms, UART 8E1, `0x7F` (auto baud) -> ACK. No answer, NACK or garbage: up to
//!    [`timing::INIT_ATTEMPTS`] entries.
//! 3. `Get` (the commands this flow needs must be listed), `Get ID` = [`PID_STM32C011`] (0x443) else stop: nothing erased.
//! 4. Read-out protection probe: `Read Memory` of 8 bytes at 0x0800_0000. NACK = RDP level 1 (the provisioning state, INTERLOCK.md H):
//!    `Readout Unprotect` (ACK, mass erase, ACK, the part resets itself), entry again, once per update; still NACK = stop.
//! 5. `Extended Erase` (0x44; the STM32C0 bootloader has no legacy erase 0x43) of every 2 KiB page of the 16 KiB flash.
//! 6. `Write Memory` in blocks of 256 bytes (the tail padded with 0xFF to the 8-byte double word), XOR checksums by
//!    `rom_bootloader`; while writing, the signed digest is recomputed over the bytes really sent: a source that changed after the
//!    verification stops the update ([`FlashError::ImageChanged`]).
//! 7. Read-back of every block: compared with the source byte by byte (padding must read 0xFF) and hashed again: the digest of what is
//!    in the supervisor flash must equal the signed digest.
//! 8. Exit, ALWAYS (also after every failure): `BOOT0` low, UART 8N1, reset pulse. The supervisor boots its flash. A power cycle is
//!    still required (INTERLOCK.md I.4) and reported in [`Report::power_cycle_required`].
//!
//! **Option bytes are not written here.** `nBOOT_SEL = 0`, the BOR level and the IWDG option are set once at provisioning
//! (`openpatch_supervisor::provisioning`); read-out protection level 1 is re-set by the supervisor image itself after an update
//! (INTERLOCK.md I.4, open item of the STM32 platform shell). TODO(verify-on-hardware): that `Readout Unprotect` on the STM32C011
//! keeps `nBOOT_SEL` and the BOR level (only RDP goes back to level 0 with the mass erase).
//!
//! Every frame is produced by a live `flash_guard::FlashSession` with a FRESH `VMOT_SENSE` reading (the `vmot_mv` argument of every
//! poll): a reading above 0.3 V, or none, ends the session for good ([`FlashError::SupplyReturned`]) and only the exit sequence
//! follows. The strap steps are not gated (they only remove permission).
//!
//! **Sources and what is not verified.** The framing follows ST AN3155 as already encoded in `openpatch_supervisor::rom_bootloader`;
//! the product id 0x443, the USART pins and the extended erase of the STM32C011 follow ST AN2606 as cited there. Neither application
//! note could be fetched in this session (st.com answered 503): TODO(verify-on-hardware) for the product id, the RDP behaviour of
//! `Read Memory` (NACK of the command), the two ACKs and self-reset of `Readout Unprotect`, and every timeout in [`timing`].
#![no_std]
#![forbid(unsafe_code)]

use openpatch_boot_policy::verify::{verify_image, ImageContext};
use openpatch_boot_policy::{digest_start, Digest512, ImageSource, Manifest, Reject, SigCheck, VerifiedImage};
pub use openpatch_boot_policy::{HW_ID_SUP_C011, SUP_C011_FLASH_SIZE};
use openpatch_supervisor::flash_guard::{FlashSession, Preconditions, Refusal, SessionError};
use openpatch_supervisor::rom_bootloader::{
    padded_len, parse_get, parse_get_id, Command, StrapStep, ACK, ENTRY, EXIT, FLASH_BASE, INIT, MAX_BLOCK, MAX_FRAME, NACK,
};
pub use openpatch_supervisor::rom_bootloader::PID_STM32C011;

/// Flash page of the STM32C011 (2 KiB) and the number of pages of the F4 part (16 KiB).
pub const PAGE_SIZE: u32 = 2_048;
pub const PAGES: u16 = (SUP_C011_FLASH_SIZE / PAGE_SIZE) as u16;
/// Bytes read by the read-out protection probe.
pub const PROBE_LEN: usize = 8;

/// Timeouts and retries. Design values, TODO(verify-on-hardware) against AN3155 / the STM32C011 flash timings (page erase,
/// double-word programming) on a real part.
pub mod timing {
    /// Entries (reset pulse + auto baud) before the update is given up.
    pub const INIT_ATTEMPTS: u8 = 3;
    /// Answer to the auto-baud byte.
    pub const INIT_TIMEOUT_MS: u32 = 100;
    /// ACK of a command / address / length frame, and the data of a read (256 bytes at 115200 8E1 take about 25 ms).
    pub const ACK_TIMEOUT_MS: u32 = 100;
    /// ACK after the erase of 8 pages.
    pub const ERASE_TIMEOUT_MS: u32 = 2_000;
    /// ACK after a 256-byte write.
    pub const WRITE_TIMEOUT_MS: u32 = 200;
    /// Second ACK of `Readout Unprotect` (mass erase + option reload).
    pub const UNPROTECT_TIMEOUT_MS: u32 = 3_000;
}

/// Where on the wire something went wrong.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Stage {
    Init,
    Get,
    GetId,
    ProbeCmd,
    ProbeAddr,
    ProbeLen,
    Unprotect,
    UnprotectDone,
    EraseCmd,
    ErasePayload,
    WriteCmd,
    WriteAddr,
    WriteData,
    ReadCmd,
    ReadAddr,
    ReadLen,
    /// Data bytes after an ACK (Get, Get ID, read).
    Data,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FlashError {
    /// The flash guard refused (supply present / unknown / not cut long enough, docked, delivery active, cell low).
    Refused(Refusal),
    /// The image failed the boot-policy verification (unsigned, wrong key, downgrade, nRF image, too large, unreadable).
    Image(Reject),
    /// No answer to the auto-baud byte after every attempt.
    InitFailed,
    Timeout(Stage),
    Nack(Stage),
    /// A byte that is neither ACK nor NACK.
    Garbage(Stage, u8),
    /// An answer that does not parse.
    Parse(Stage),
    /// `Get ID` answered another product id.
    WrongId(u16),
    /// The bootloader does not list a command this flow needs.
    MissingCommand(u8),
    /// Read-out protection still active after one `Readout Unprotect`.
    RdpStillActive,
    /// The supply reading went above 0.3 V (or was missing) while frames were needed.
    SupplyReturned,
    /// A frame could not be encoded (internal).
    Frame,
    /// The image source could not be read during the write or verify pass.
    ImageRead,
    /// The bytes sent are not the bytes that were verified (the source changed in between).
    ImageChanged,
    /// The read-back differs from the image at this address.
    VerifyMismatch { addr: u32 },
    /// The driver answered with an event that does not belong to the last action.
    Driver,
}

/// A successful update.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Report {
    pub version: u32,
    pub image_len: u32,
    /// The part was at read-out protection level 1 and was unprotected (mass erase) for the update.
    pub rdp_was_active: bool,
    /// Always true: INTERLOCK.md I.4 asks for a power cycle after a supervisor update.
    pub power_cycle_required: bool,
}

/// What the driver reports about the previous action.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Event<'a> {
    /// First call.
    Begin,
    /// The strap step / wait / send is complete.
    Done,
    /// Exactly the requested number of bytes arrived.
    Rx(&'a [u8]),
    /// Fewer bytes than requested arrived within the timeout (the driver discards what it got).
    Timeout,
}

/// What the driver must do next.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Action<'a> {
    /// Set a strap pin, wait, or switch the UART parity (`SendInit` is never emitted: the auto-baud byte comes as a `Send`).
    Strap(StrapStep),
    /// Write these bytes to the UART (8E1).
    Send(&'a [u8]),
    /// Read exactly `n` bytes, give up after `timeout_ms`.
    Recv { n: usize, timeout_ms: u32 },
    /// The update is over (the exit sequence has already run). Repeated on every further poll.
    Finished(Result<Report, FlashError>),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum St {
    /// ENTRY step i (0..6; ENTRY[6], the auto-baud byte, is sent as a frame).
    Entry(u8),
    Frame(Stage),
    Ack(Stage),
    GetHead,
    GetBody(usize),
    IdBody,
    ProbeData,
    ReadData(usize),
    Exit(u8),
    Finished,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Pending {
    Start,
    Done,
    Rx(usize),
    Nothing,
}

const ENTRY_STRAPS: u8 = 6;

/// The update state machine. `H` is the SHA-512 implementation (salty on the nRF, sha2 in the tests).
pub struct Updater<H: Digest512> {
    session: FlashSession,
    manifest: Manifest,
    verified: VerifiedImage,
    st: St,
    pending: Pending,
    init_tries: u8,
    unprotected: bool,
    rdp_was_active: bool,
    commands: [u8; 16],
    n_commands: usize,
    /// Offset in the image of the current block.
    off: u32,
    /// Image bytes in the current block (the frame carries `padded_len` of them).
    blk_len: usize,
    hasher: Option<H>,
    blk: [u8; MAX_BLOCK],
    buf: [u8; MAX_FRAME],
    result: Option<Result<Report, FlashError>>,
}

impl<H: Digest512> Updater<H> {
    /// Verify the image (boot-policy rules, hardware id [`HW_ID_SUP_C011`], `min_version` = the lowest acceptable security version,
    /// i.e. the installed one) and check the flash guard preconditions. `pre.image_verified` is ignored: only this verification sets it.
    pub fn begin<V: SigCheck, S: ImageSource>(
        manifest: &[u8],
        img: &mut S,
        verifier: Option<&V>,
        min_version: u32,
        pre: &Preconditions,
    ) -> Result<Self, FlashError> {
        let ctx = ImageContext { verifier, hw_id: HW_ID_SUP_C011, max_image: SUP_C011_FLASH_SIZE, min_version };
        let verified = verify_image::<H, V, S>(manifest, img, &ctx).map_err(FlashError::Image)?;
        let manifest = Manifest::parse(manifest).map_err(|e| FlashError::Image(Reject::Manifest(e)))?;
        let pre = Preconditions { image_verified: true, ..*pre };
        let session = FlashSession::begin(&pre).map_err(FlashError::Refused)?;
        Ok(Self {
            session,
            manifest,
            verified,
            st: St::Entry(0),
            pending: Pending::Start,
            init_tries: 0,
            unprotected: false,
            rdp_was_active: false,
            commands: [0; 16],
            n_commands: 0,
            off: 0,
            blk_len: 0,
            hasher: None,
            blk: [0xFF; MAX_BLOCK],
            buf: [0; MAX_FRAME],
            result: None,
        })
    }

    /// Advance with the event of the previous action and return the next action. `vmot_mv` is a FRESH `VMOT_SENSE` reading in mV
    /// (`None` = no valid reading).
    pub fn poll<S: ImageSource>(&mut self, img: &mut S, vmot_mv: Option<u16>, ev: Event<'_>) -> Action<'_> {
        self.on_event(img, ev);
        loop {
            match self.st {
                St::Entry(i) => {
                    self.pending = Pending::Done;
                    return Action::Strap(ENTRY[i as usize]);
                }
                St::Exit(i) => {
                    self.pending = Pending::Done;
                    return Action::Strap(EXIT[i as usize]);
                }
                St::Finished => {
                    self.pending = Pending::Nothing;
                    return Action::Finished(self.result.unwrap_or(Err(FlashError::Driver)));
                }
                St::Frame(stage) => match self.build(img, vmot_mv, stage) {
                    Ok(n) => {
                        self.pending = Pending::Done;
                        return Action::Send(&self.buf[..n]);
                    }
                    Err(e) => self.fail(e), // -> Exit, emitted by the next loop round
                },
                St::Ack(stage) => return self.recv(1, ack_timeout(stage)),
                St::GetHead | St::IdBody | St::ProbeData | St::ReadData(_) | St::GetBody(_) => {
                    let n = match self.st {
                        St::GetHead => 1,
                        St::GetBody(n) => n,
                        St::IdBody => 4,
                        St::ProbeData => PROBE_LEN,
                        St::ReadData(n) => n,
                        _ => 0,
                    };
                    return self.recv(n, timing::ACK_TIMEOUT_MS);
                }
            }
        }
    }

    fn recv(&mut self, n: usize, timeout_ms: u32) -> Action<'static> {
        self.pending = Pending::Rx(n);
        Action::Recv { n, timeout_ms }
    }

    fn fail(&mut self, e: FlashError) {
        if self.result.is_none() {
            self.result = Some(Err(e));
        }
        self.session.abort();
        self.st = St::Exit(0);
    }

    fn succeed(&mut self) {
        self.result = Some(Ok(Report {
            version: self.verified.version(),
            image_len: self.verified.image_len(),
            rdp_was_active: self.rdp_was_active,
            power_cycle_required: true,
        }));
        self.session.abort(); // no frame after the read-back
        self.st = St::Exit(0);
    }

    fn on_event<S: ImageSource>(&mut self, img: &mut S, ev: Event<'_>) {
        if self.st == St::Finished {
            return;
        }
        match (self.pending, ev) {
            (Pending::Start, Event::Begin) => {}
            (Pending::Done, Event::Done) => self.after_done(),
            (Pending::Rx(n), Event::Rx(b)) if b.len() == n => self.after_rx(img, b),
            (Pending::Rx(_), Event::Timeout) => self.after_timeout(),
            _ => match self.st {
                St::Exit(_) => self.after_done(), // never get stuck in the exit sequence
                _ => self.fail(FlashError::Driver),
            },
        }
    }

    fn after_done(&mut self) {
        self.st = match self.st {
            St::Entry(i) if i + 1 < ENTRY_STRAPS => St::Entry(i + 1),
            St::Entry(_) => St::Frame(Stage::Init),
            St::Frame(s) => St::Ack(s),
            St::Exit(i) if (i as usize) + 1 < EXIT.len() => St::Exit(i + 1),
            St::Exit(_) => St::Finished,
            other => other,
        };
    }

    fn retry_entry(&mut self) {
        self.init_tries += 1;
        if self.init_tries < timing::INIT_ATTEMPTS {
            self.st = St::Entry(0);
        } else {
            self.fail(FlashError::InitFailed);
        }
    }

    fn after_timeout(&mut self) {
        match self.st {
            St::Ack(Stage::Init) => self.retry_entry(),
            St::Ack(s) => self.fail(FlashError::Timeout(s)),
            _ => self.fail(FlashError::Timeout(Stage::Data)),
        }
    }

    fn after_rx<S: ImageSource>(&mut self, img: &mut S, b: &[u8]) {
        match self.st {
            St::Ack(stage) => match b[0] {
                ACK => self.acked(stage),
                NACK if stage == Stage::Init => self.retry_entry(),
                NACK if stage == Stage::ProbeCmd => {
                    // read-out protection active: one unprotect (mass erase) per update
                    if self.unprotected {
                        self.fail(FlashError::RdpStillActive);
                    } else if !self.supports(Command::ReadoutUnprotect) {
                        self.fail(FlashError::MissingCommand(Command::ReadoutUnprotect.code()));
                    } else {
                        self.rdp_was_active = true;
                        self.st = St::Frame(Stage::Unprotect);
                    }
                }
                NACK => self.fail(FlashError::Nack(stage)),
                _ if stage == Stage::Init => self.retry_entry(),
                x => self.fail(FlashError::Garbage(stage, x)),
            },
            St::GetHead => {
                let n = b[0] as usize;
                if n > 16 {
                    self.fail(FlashError::Parse(Stage::Get));
                } else {
                    self.n_commands = n; // remembered for the body length check
                    self.st = St::GetBody(n + 2);
                }
            }
            St::GetBody(_) => {
                let mut r = [0u8; 20];
                r[0] = ACK;
                r[1] = self.n_commands as u8;
                r[2..2 + b.len()].copy_from_slice(b);
                match parse_get(&r[..2 + b.len()]) {
                    Ok(g) => {
                        self.commands = g.commands;
                        self.n_commands = g.n_commands;
                        let needed = [Command::GetId, Command::ReadMemory, Command::WriteMemory, Command::ExtendedErase];
                        match needed.iter().find(|c| !g.supports(**c)) {
                            Some(c) => self.fail(FlashError::MissingCommand(c.code())),
                            None => self.st = St::Frame(Stage::GetId),
                        }
                    }
                    Err(_) => self.fail(FlashError::Parse(Stage::Get)),
                }
            }
            St::IdBody => {
                let r = [ACK, b[0], b[1], b[2], b[3]];
                match parse_get_id(&r) {
                    Ok(PID_STM32C011) => self.st = St::Frame(Stage::ProbeCmd),
                    Ok(pid) => self.fail(FlashError::WrongId(pid)),
                    Err(_) => self.fail(FlashError::Parse(Stage::GetId)),
                }
            }
            St::ProbeData => self.st = St::Frame(Stage::EraseCmd),
            St::ReadData(n) => self.check_block(img, &b[..n]),
            _ => self.fail(FlashError::Driver),
        }
    }

    fn supports(&self, c: Command) -> bool {
        self.commands[..self.n_commands].contains(&c.code())
    }

    fn acked(&mut self, stage: Stage) {
        self.st = match stage {
            Stage::Init => St::Frame(if self.unprotected { Stage::GetId } else { Stage::Get }),
            Stage::Get => St::GetHead,
            Stage::GetId => St::IdBody,
            Stage::ProbeCmd => St::Frame(Stage::ProbeAddr),
            Stage::ProbeAddr => St::Frame(Stage::ProbeLen),
            Stage::ProbeLen => St::ProbeData,
            Stage::Unprotect => St::Ack(Stage::UnprotectDone),
            Stage::UnprotectDone => {
                // mass erased, RDP 0, the part resets itself: enter the bootloader again
                self.unprotected = true;
                self.init_tries = 0;
                St::Entry(0)
            }
            Stage::EraseCmd => St::Frame(Stage::ErasePayload),
            Stage::ErasePayload => {
                self.off = 0;
                self.hasher = Some(digest_start::<H>(&self.manifest));
                St::Frame(Stage::WriteCmd)
            }
            Stage::WriteCmd => St::Frame(Stage::WriteAddr),
            Stage::WriteAddr => St::Frame(Stage::WriteData),
            Stage::WriteData => {
                self.off += self.blk_len as u32;
                if self.off < self.verified.image_len() {
                    St::Frame(Stage::WriteCmd)
                } else if !self.digest_matches() {
                    self.fail(FlashError::ImageChanged);
                    return;
                } else {
                    self.off = 0;
                    self.hasher = Some(digest_start::<H>(&self.manifest));
                    St::Frame(Stage::ReadCmd)
                }
            }
            Stage::ReadCmd => St::Frame(Stage::ReadAddr),
            Stage::ReadAddr => St::Frame(Stage::ReadLen),
            Stage::ReadLen => St::ReadData(padded_len(self.blk_len)),
            Stage::Data => St::Exit(0),
        };
    }

    fn digest_matches(&mut self) -> bool {
        match self.hasher.take() {
            Some(h) => &h.finish() == self.verified.digest(),
            None => false,
        }
    }

    /// Image bytes of the block at `self.off` into `self.blk`, padded with 0xFF; returns the padded length.
    fn load_block<S: ImageSource>(&mut self, img: &mut S) -> Result<usize, FlashError> {
        let n = (self.verified.image_len() - self.off).min(MAX_BLOCK as u32) as usize;
        if !img.read(self.off, &mut self.blk[..n]) {
            return Err(FlashError::ImageRead);
        }
        let p = padded_len(n);
        self.blk[n..p].fill(0xFF);
        self.blk_len = n;
        Ok(p)
    }

    fn check_block<S: ImageSource>(&mut self, img: &mut S, got: &[u8]) {
        let n = self.blk_len;
        let mut src = [0u8; MAX_BLOCK];
        if !img.read(self.off, &mut src[..n]) {
            self.fail(FlashError::ImageRead);
            return;
        }
        if let Some(i) = (0..got.len()).find(|&i| got[i] != if i < n { src[i] } else { 0xFF }) {
            self.fail(FlashError::VerifyMismatch { addr: FLASH_BASE + self.off + i as u32 });
            return;
        }
        if let Some(h) = self.hasher.as_mut() {
            h.update(&got[..n]);
        }
        self.off += n as u32;
        if self.off < self.verified.image_len() {
            self.st = St::Frame(Stage::ReadCmd);
        } else if self.digest_matches() {
            self.succeed();
        } else {
            self.fail(FlashError::ImageChanged);
        }
    }

    /// Encode the frame of `stage` into `self.buf` through the flash session (fresh supply reading).
    fn build<S: ImageSource>(&mut self, img: &mut S, vmot: Option<u16>, stage: Stage) -> Result<usize, FlashError> {
        let map = |e: SessionError| match e {
            SessionError::SupplyReturned | SessionError::Aborted => FlashError::SupplyReturned,
            SessionError::Frame(_) => FlashError::Frame,
        };
        let addr = FLASH_BASE + self.off;
        if stage == Stage::WriteData {
            let p = self.load_block(img)?;
            let r = self.session.write_data(vmot, addr, &self.blk[..p], &mut self.buf).map_err(map);
            // hash only what really goes on the wire
            if let (Ok(_), Some(h)) = (r, self.hasher.as_mut()) {
                h.update(&self.blk[..self.blk_len]);
            }
            return r;
        }
        let s = &mut self.session;
        let put = |buf: &mut [u8], b: &[u8]| {
            buf[..b.len()].copy_from_slice(b);
            Ok(b.len())
        };
        match stage {
            Stage::Init => {
                if !s.is_alive() {
                    return Err(FlashError::SupplyReturned);
                }
                put(&mut self.buf, &[INIT])
            }
            Stage::Get => put(&mut self.buf, &s.command(vmot, Command::Get).map_err(map)?),
            Stage::GetId => put(&mut self.buf, &s.command(vmot, Command::GetId).map_err(map)?),
            Stage::ProbeCmd | Stage::ReadCmd => put(&mut self.buf, &s.command(vmot, Command::ReadMemory).map_err(map)?),
            Stage::ProbeAddr => put(&mut self.buf, &s.address(vmot, FLASH_BASE).map_err(map)?),
            Stage::ProbeLen => put(&mut self.buf, &s.read_length(vmot, PROBE_LEN).map_err(map)?),
            Stage::Unprotect => put(&mut self.buf, &s.command(vmot, Command::ReadoutUnprotect).map_err(map)?),
            Stage::EraseCmd => put(&mut self.buf, &s.command(vmot, Command::ExtendedErase).map_err(map)?),
            Stage::ErasePayload => {
                let mut pages = [0u16; PAGES as usize];
                for (i, p) in pages.iter_mut().enumerate() {
                    *p = i as u16;
                }
                s.erase_pages(vmot, &pages, &mut self.buf).map_err(map)
            }
            Stage::WriteCmd => put(&mut self.buf, &s.command(vmot, Command::WriteMemory).map_err(map)?),
            Stage::WriteAddr | Stage::ReadAddr => put(&mut self.buf, &s.address(vmot, addr).map_err(map)?),
            Stage::ReadLen => {
                let n = (self.verified.image_len() - self.off).min(MAX_BLOCK as u32) as usize;
                self.blk_len = n;
                put(&mut self.buf, &s.read_length(vmot, padded_len(n)).map_err(map)?)
            }
            Stage::WriteData | Stage::UnprotectDone | Stage::Data => Err(FlashError::Driver),
        }
    }
}

fn ack_timeout(stage: Stage) -> u32 {
    match stage {
        Stage::Init => timing::INIT_TIMEOUT_MS,
        Stage::ErasePayload => timing::ERASE_TIMEOUT_MS,
        Stage::WriteData => timing::WRITE_TIMEOUT_MS,
        Stage::UnprotectDone => timing::UNPROTECT_TIMEOUT_MS,
        _ => timing::ACK_TIMEOUT_MS,
    }
}
