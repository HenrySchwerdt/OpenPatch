//! Framing of the STM32 UART system bootloader (ST AN3155, bootloader protocol of AN2606 for the STM32C0 series), used by the nRF to
//! flash the supervisor (`INTERLOCK.md` I.4: `SUP_BOOT0` high + `SUP_NRST` pulse, then this protocol on `SUP_TXD` / `SUP_RXD`).
//!
//! **Line settings: 115200 baud, 8 data bits, EVEN parity, 1 stop bit (8E1).** This is NOT the 8N1 of the challenge/response link: the
//! nRF UARTE must be switched to even parity for the update and back afterwards (`CONFIG.PARITY = Included` is even parity on the
//! nRF52840).
//!
//! Everything here is pure encoding / decoding into caller supplied buffers (no alloc, no I/O, no timing): the sequencing belongs to the
//! HAL, the ENFORCED precondition (motor supply cut) to [`crate::flash_guard`], which is the only way to get a write or erase frame
//! (those encoders are crate private; the read-only ones and the parsers are public).
//!
//! Frames (all multi-byte fields MSB first, checksums are the XOR of the bytes covered):
//!
//! | Item | Bytes |
//! |---|---|
//! | init | `0x7F` (auto baud), answered by ACK |
//! | command | `cmd`, `cmd ^ 0xFF`, answered by ACK / NACK |
//! | address | `a31..a24, a23..a16, a15..a8, a7..a0, xor` |
//! | read length | `N-1, (N-1) ^ 0xFF`, then N data bytes follow |
//! | write data | `N-1, d0 .. d(N-1), xor(N-1, d0..)` |
//! | extended erase, special | `0xFF 0xFF 0x00` (mass), `0xFF 0xFE 0x01` (bank 1), `0xFF 0xFD 0x02` (bank 2) |
//! | extended erase, pages | `(n-1) hi, lo, then n x (page hi, lo), xor of all` |

/// Answer bytes.
pub const ACK: u8 = 0x79;
pub const NACK: u8 = 0x1F;
/// Auto-baud byte.
pub const INIT: u8 = 0x7F;

/// Largest data block of a read or write command.
pub const MAX_BLOCK: usize = 256;
/// Flash programming granularity of the STM32C0 (64-bit double word): writes are 8-byte aligned and a multiple of 8 bytes.
pub const WRITE_ALIGN: usize = 8;
/// Flash start of the STM32C011 (16 KiB at 0x0800_0000 for the F4 parts).
pub const FLASH_BASE: u32 = 0x0800_0000;
/// Largest number of pages of one extended erase frame that this module encodes (a frame must fit [`MAX_FRAME`]).
pub const MAX_ERASE_PAGES: usize = 32;
/// Largest frame this module produces: erase 2 + 2 x 32 + 1, write 1 + 256 + 1.
pub const MAX_FRAME: usize = 258;

/// Commands (AN3155 table 2).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
#[repr(u8)]
pub enum Command {
    Get = 0x00,
    GetVersion = 0x01,
    GetId = 0x02,
    ReadMemory = 0x11,
    Go = 0x21,
    WriteMemory = 0x31,
    /// Legacy erase (not used: the STM32C0 bootloader implements the extended one).
    Erase = 0x43,
    ExtendedErase = 0x44,
    WriteProtect = 0x63,
    WriteUnprotect = 0x73,
    ReadoutProtect = 0x82,
    /// Disables read-out protection AND MASS-ERASES the flash, then resets.
    ReadoutUnprotect = 0x92,
}

impl Command {
    pub const fn code(self) -> u8 {
        self as u8
    }
    /// The commands that change the flash or the option bytes (everything but Get / GetVersion / GetId / ReadMemory): these are only
    /// reachable through a live [`crate::flash_guard::FlashSession`].
    pub const fn modifies_flash(self) -> bool {
        !matches!(self, Command::Get | Command::GetVersion | Command::GetId | Command::ReadMemory)
    }
    pub fn from_code(c: u8) -> Option<Command> {
        Some(match c {
            0x00 => Command::Get,
            0x01 => Command::GetVersion,
            0x02 => Command::GetId,
            0x11 => Command::ReadMemory,
            0x21 => Command::Go,
            0x31 => Command::WriteMemory,
            0x43 => Command::Erase,
            0x44 => Command::ExtendedErase,
            0x63 => Command::WriteProtect,
            0x73 => Command::WriteUnprotect,
            0x82 => Command::ReadoutProtect,
            0x92 => Command::ReadoutUnprotect,
            _ => return None,
        })
    }
}

/// A byte of an answer.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum Reply {
    Ack,
    Nack,
    /// Anything else: line noise or a device that is not in the bootloader.
    Unknown(u8),
}

pub fn parse_reply(b: u8) -> Reply {
    match b {
        ACK => Reply::Ack,
        NACK => Reply::Nack,
        x => Reply::Unknown(x),
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum FrameError {
    /// The output buffer is too small.
    Buffer,
    /// Empty or oversize data block (1..=256 bytes).
    Length,
    /// The address is not 8-byte aligned (write) or below the flash base.
    Address,
    /// The data length is not a multiple of 8.
    Alignment,
    /// Page list empty or longer than [`MAX_ERASE_PAGES`].
    Pages,
}

fn put(out: &mut [u8], at: usize, bytes: &[u8]) -> Result<usize, FrameError> {
    let end = at + bytes.len();
    if end > out.len() {
        return Err(FrameError::Buffer);
    }
    out[at..end].copy_from_slice(bytes);
    Ok(end)
}

pub fn xor(bytes: &[u8]) -> u8 {
    bytes.iter().fold(0, |a, b| a ^ b)
}

/// `cmd, cmd ^ 0xFF`. Crate private: a command that modifies the flash is only reachable through a `flash_guard::FlashSession`.
pub(crate) fn command_frame(cmd: Command) -> [u8; 2] {
    let c = cmd.code();
    [c, c ^ 0xFF]
}

/// The frame of a command that cannot change anything (`Get`, `GetVersion`, `GetId`, `ReadMemory`); `None` for every other command.
pub fn read_only_command_frame(cmd: Command) -> Option<[u8; 2]> {
    if cmd.modifies_flash() {
        None
    } else {
        Some(command_frame(cmd))
    }
}

/// `a3 a2 a1 a0 xor`.
pub fn address_frame(addr: u32) -> [u8; 5] {
    let a = addr.to_be_bytes();
    [a[0], a[1], a[2], a[3], xor(&a)]
}

/// `N-1, ~(N-1)` for a read of `n` bytes (1..=256).
pub fn read_length_frame(n: usize) -> Result<[u8; 2], FrameError> {
    if n == 0 || n > MAX_BLOCK {
        return Err(FrameError::Length);
    }
    let m = (n - 1) as u8;
    Ok([m, m ^ 0xFF])
}

/// `N-1, data..., xor` into `out`; returns the length. `data` is 1..=256 bytes and a multiple of [`WRITE_ALIGN`].
pub(crate) fn write_data_frame(data: &[u8], out: &mut [u8]) -> Result<usize, FrameError> {
    if data.is_empty() || data.len() > MAX_BLOCK {
        return Err(FrameError::Length);
    }
    if data.len() % WRITE_ALIGN != 0 {
        return Err(FrameError::Alignment);
    }
    let m = (data.len() - 1) as u8;
    let mut at = put(out, 0, &[m])?;
    at = put(out, at, data)?;
    let ck = m ^ xor(data);
    put(out, at, &[ck])
}

/// Address of a write: 8-byte aligned and inside the flash window.
pub fn check_write_address(addr: u32) -> Result<(), FrameError> {
    if addr < FLASH_BASE || addr % WRITE_ALIGN as u32 != 0 {
        return Err(FrameError::Address);
    }
    Ok(())
}

/// Special extended erase codes.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum SpecialErase {
    Mass,
    Bank1,
    Bank2,
}

/// Extended erase payload for a special code: `0xFF code checksum`.
pub(crate) fn extended_erase_special(s: SpecialErase) -> [u8; 3] {
    match s {
        SpecialErase::Mass => [0xFF, 0xFF, 0x00],
        SpecialErase::Bank1 => [0xFF, 0xFE, 0x01],
        SpecialErase::Bank2 => [0xFF, 0xFD, 0x02],
    }
}

/// Extended erase payload for a list of pages: `(n-1) hi lo, pages (hi lo)..., xor`. Returns the length.
pub(crate) fn extended_erase_pages(pages: &[u16], out: &mut [u8]) -> Result<usize, FrameError> {
    if pages.is_empty() || pages.len() > MAX_ERASE_PAGES {
        return Err(FrameError::Pages);
    }
    let n1 = (pages.len() - 1) as u16;
    let mut at = put(out, 0, &n1.to_be_bytes())?;
    for p in pages {
        at = put(out, at, &p.to_be_bytes())?;
    }
    let ck = xor(&out[..at]);
    put(out, at, &[ck])
}

/// The page number of a flash address for the given page size (STM32C0: 2 KiB).
pub fn page_of(addr: u32, page_size: u32) -> Option<u16> {
    if addr < FLASH_BASE || page_size == 0 {
        return None;
    }
    u16::try_from((addr - FLASH_BASE) / page_size).ok()
}

/// Answer of `Get`: bootloader version and the supported command codes.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct GetReply {
    pub version: u8,
    /// Supported command codes (at most 16).
    pub commands: [u8; 16],
    pub n_commands: usize,
}

impl GetReply {
    pub fn supports(&self, c: Command) -> bool {
        self.commands[..self.n_commands].contains(&c.code())
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum ParseError {
    /// Too short / too long for the announced length.
    Length,
    /// Missing ACK at the start or the end.
    NoAck,
    TooManyCommands,
}

/// Parse the whole answer of `Get` (after the command was acknowledged): `ACK, N, version, N commands, ACK` where N counts the version
/// byte plus the commands minus one (AN3155: "N = number of bytes to follow - 1"): the bytes between the first ACK and the last ACK are
/// `N+1` bytes (`version` + `N` commands).
pub fn parse_get(reply: &[u8]) -> Result<GetReply, ParseError> {
    if reply.len() < 4 {
        return Err(ParseError::Length);
    }
    if reply[0] != ACK {
        return Err(ParseError::NoAck);
    }
    let n = reply[1] as usize; // bytes to follow minus one
    let total = 2 + (n + 1) + 1;
    if reply.len() != total {
        return Err(ParseError::Length);
    }
    if reply[total - 1] != ACK {
        return Err(ParseError::NoAck);
    }
    let ncmd = n; // version + n commands = n + 1 bytes
    if ncmd > 16 {
        return Err(ParseError::TooManyCommands);
    }
    let mut commands = [0u8; 16];
    commands[..ncmd].copy_from_slice(&reply[3..3 + ncmd]);
    Ok(GetReply { version: reply[2], commands, n_commands: ncmd })
}

/// Parse the answer of `GetId`: `ACK, N(=1), pid hi, pid lo, ACK`.
pub fn parse_get_id(reply: &[u8]) -> Result<u16, ParseError> {
    if reply.len() != 5 {
        return Err(ParseError::Length);
    }
    if reply[0] != ACK || reply[4] != ACK {
        return Err(ParseError::NoAck);
    }
    if reply[1] != 1 {
        return Err(ParseError::Length);
    }
    Ok(u16::from_be_bytes([reply[2], reply[3]]))
}

/// STM32C011xx product ID (AN2606: 0x443).
pub const PID_STM32C011: u16 = 0x443;

/// Split a write of `data` at `addr` into blocks of at most `block` bytes (a multiple of 8, at most 256). Yields `(address, bytes)`.
/// A trailing partial block must be padded to 8 bytes by the caller with 0xFF ([`pad_tail`]).
pub struct Blocks<'a> {
    addr: u32,
    data: &'a [u8],
    block: usize,
}

impl<'a> Blocks<'a> {
    pub fn new(addr: u32, data: &'a [u8], block: usize) -> Result<Self, FrameError> {
        if block == 0 || block > MAX_BLOCK || block % WRITE_ALIGN != 0 {
            return Err(FrameError::Length);
        }
        check_write_address(addr)?;
        if data.len() % WRITE_ALIGN != 0 {
            return Err(FrameError::Alignment);
        }
        Ok(Self { addr, data, block })
    }
}

impl<'a> Iterator for Blocks<'a> {
    type Item = (u32, &'a [u8]);
    fn next(&mut self) -> Option<Self::Item> {
        if self.data.is_empty() {
            return None;
        }
        let n = self.data.len().min(self.block);
        let (head, tail) = self.data.split_at(n);
        let a = self.addr;
        self.addr += n as u32;
        self.data = tail;
        Some((a, head))
    }
}

/// Length rounded up to the write granularity (the caller fills the tail with 0xFF).
pub const fn padded_len(len: usize) -> usize {
    (len + WRITE_ALIGN - 1) / WRITE_ALIGN * WRITE_ALIGN
}

/// Copy `src` into `dst` and fill the rest with 0xFF; returns the padded length. `dst` must hold `padded_len(src.len())` bytes.
pub fn pad_tail(src: &[u8], dst: &mut [u8]) -> Result<usize, FrameError> {
    let n = padded_len(src.len());
    if dst.len() < n {
        return Err(FrameError::Buffer);
    }
    dst[..src.len()].copy_from_slice(src);
    dst[src.len()..n].fill(0xFF);
    Ok(n)
}

/// Boot entry / exit sequence of the two strap lines (`FIRMWARE-PINMAP.md`: `SUP_BOOT0` high + `SUP_NRST` pulse, 10 ms, wait 100 ms).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum StrapStep {
    Boot0(bool),
    /// `SUP_NRST` driven low (open drain), `true` = pulled low.
    NrstLow(bool),
    WaitMs(u16),
    /// Switch the UART to 8E1.
    UartEven,
    /// Send the auto-baud byte and expect ACK.
    SendInit,
    /// Back to 8N1.
    UartNone,
}

/// Enter the ROM bootloader: BOOT0 high, reset pulse 10 ms, 100 ms for the bootloader to start, UART to 8E1, init byte.
pub const ENTRY: [StrapStep; 7] = [
    StrapStep::Boot0(true),
    StrapStep::NrstLow(true),
    StrapStep::WaitMs(10),
    StrapStep::NrstLow(false),
    StrapStep::WaitMs(100),
    StrapStep::UartEven,
    StrapStep::SendInit,
];

/// Leave: BOOT0 low, reset pulse, UART back to 8N1. A power cycle follows (INTERLOCK.md I.4).
pub const EXIT: [StrapStep; 6] = [
    StrapStep::Boot0(false),
    StrapStep::UartNone,
    StrapStep::NrstLow(true),
    StrapStep::WaitMs(10),
    StrapStep::NrstLow(false),
    StrapStep::WaitMs(100),
];
