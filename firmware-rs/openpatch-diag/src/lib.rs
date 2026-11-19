//! OpenPatch diagnostic codes (docs/06-diagnostics.md sections 2 and 4).
//!
//! TEST PROJECT: not a medical device, never to be worn.
//!
//! * [`DiagCode`]: 32 bit `layer(4) | component(8) | fault(12) | inst(8)`.
//! * [`Severity`], [`Action`], [`Fru`]: the enumerations of 2.2 to 2.4 (wire values).
//! * [`DiagRecord`]: the 32 byte record of 2.6 (flash log, protocol tag `DIAG_RECORD`, app).
//! * [`catalogue`]: GENERATED from `spec/diag-codes.csv` by `tools/gen_diag.py`; never edit it.
//!
//! `no_std`, no alloc, no `unsafe`. The wire decoder is tolerant: unknown severity, action or FRU
//! values are kept verbatim in the record and mapped fail-safe by the accessors (an unknown
//! severity is a FAULT, never ignored).
#![no_std]
#![forbid(unsafe_code)]

use core::fmt;

pub mod catalogue;
pub use catalogue::{codes, CATALOGUE, SCHEMA_VERSION};

/// Size of a wire / flash record.
pub const RECORD_LEN: usize = 32;

/// 32 bit diagnostic code. The catalogue identity is [`DiagCode::identity`] (instance cleared).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash, PartialOrd, Ord)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct DiagCode(pub u32);

impl DiagCode {
    pub const NONE: DiagCode = DiagCode(0);

    pub const fn new(layer: u8, component: u8, fault: u16, inst: u8) -> DiagCode {
        DiagCode(((layer as u32 & 0xF) << 28) | ((component as u32) << 20) | ((fault as u32 & 0xFFF) << 8) | inst as u32)
    }
    #[inline]
    pub const fn raw(self) -> u32 {
        self.0
    }
    #[inline]
    pub const fn layer(self) -> u8 {
        (self.0 >> 28) as u8
    }
    #[inline]
    pub const fn component(self) -> u8 {
        (self.0 >> 20) as u8
    }
    #[inline]
    pub const fn fault(self) -> u16 {
        ((self.0 >> 8) & 0xFFF) as u16
    }
    #[inline]
    pub const fn inst(self) -> u8 {
        self.0 as u8
    }
    /// Catalogue identity: the code without its instance qualifier.
    #[inline]
    pub const fn identity(self) -> DiagCode {
        DiagCode(self.0 & 0xFFFF_FF00)
    }
    #[inline]
    pub const fn with_inst(self, inst: u8) -> DiagCode {
        DiagCode((self.0 & 0xFFFF_FF00) | inst as u32)
    }
    /// Bits 31..16 ("where").
    #[inline]
    pub const fn where_(self) -> u16 {
        (self.0 >> 16) as u16
    }
    /// Bits 15..0 ("what").
    #[inline]
    pub const fn what(self) -> u16 {
        self.0 as u16
    }
    #[inline]
    pub const fn is_none(self) -> bool {
        self.0 == 0
    }
    /// Catalogue row of this code (by identity), `None` for an unknown code.
    pub fn info(self) -> Option<&'static CodeInfo> {
        lookup(self)
    }
}

/// `L-CC-FFF` (hex), with `/II` when the instance is not 0: `1-06-001`, `1-06-001/03`.
impl fmt::Display for DiagCode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:X}-{:02X}-{:03X}", self.layer(), self.component(), self.fault())?;
        if self.inst() != 0 {
            write!(f, "/{:02X}", self.inst())?;
        }
        Ok(())
    }
}

/// Severity (docs/06-diagnostics.md 2.2). Ordered: `Info < Warning < Fault < Latched`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
#[repr(u8)]
pub enum Severity {
    Info = 0,
    Warning = 1,
    Fault = 2,
    Latched = 3,
}

impl Severity {
    pub const fn from_u8(v: u8) -> Option<Severity> {
        Some(match v {
            0 => Severity::Info,
            1 => Severity::Warning,
            2 => Severity::Fault,
            3 => Severity::Latched,
            _ => return None,
        })
    }
    /// Fail-safe decode: an unknown value is a FAULT.
    pub const fn from_u8_failsafe(v: u8) -> Severity {
        match Severity::from_u8(v) {
            Some(s) => s,
            None => Severity::Fault,
        }
    }
    /// F and L stop delivery.
    pub const fn stops_delivery(self) -> bool {
        self as u8 >= Severity::Fault as u8
    }
}

/// Recommended action (2.3).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
#[repr(u8)]
pub enum Action {
    None = 0,
    Retry = 1,
    Ack = 2,
    Refill = 3,
    Redock = 4,
    Recable = 5,
    Rephone = 6,
    CheckPower = 7,
    Replace = 8,
    Reseat = 9,
    SwapPod = 10,
    Prime = 11,
    Reprovision = 12,
    UpdateFw = 13,
    ReportBug = 14,
    WaitCool = 15,
    Repair = 16,
    UpdateApp = 17,
    CheckCannula = 18,
    Isolate = 19,
}

impl Action {
    pub const fn from_u8(v: u8) -> Option<Action> {
        Some(match v {
            0 => Action::None,
            1 => Action::Retry,
            2 => Action::Ack,
            3 => Action::Refill,
            4 => Action::Redock,
            5 => Action::Recable,
            6 => Action::Rephone,
            7 => Action::CheckPower,
            8 => Action::Replace,
            9 => Action::Reseat,
            10 => Action::SwapPod,
            11 => Action::Prime,
            12 => Action::Reprovision,
            13 => Action::UpdateFw,
            14 => Action::ReportBug,
            15 => Action::WaitCool,
            16 => Action::Repair,
            17 => Action::UpdateApp,
            18 => Action::CheckCannula,
            19 => Action::Isolate,
            _ => return None,
        })
    }
}

/// Field-replaceable unit (2.4). Ids 19 and up are reserved (Rev B).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
#[repr(u8)]
pub enum Fru {
    None = 0,
    Ctrl = 1,
    Podb = 2,
    Ffc = 3,
    Motor = 4,
    Gear = 5,
    Screw = 6,
    Resv = 7,
    Seal = 8,
    Cap = 9,
    Needle = 10,
    Batt = 11,
    App = 12,
    Magd = 13,
    Mags = 14,
    Usb = 15,
    Cann = 16,
    Fw = 17,
    Chg = 18,
}

impl Fru {
    pub const COUNT: u8 = 19;
    pub const fn from_u8(v: u8) -> Option<Fru> {
        Some(match v {
            0 => Fru::None,
            1 => Fru::Ctrl,
            2 => Fru::Podb,
            3 => Fru::Ffc,
            4 => Fru::Motor,
            5 => Fru::Gear,
            6 => Fru::Screw,
            7 => Fru::Resv,
            8 => Fru::Seal,
            9 => Fru::Cap,
            10 => Fru::Needle,
            11 => Fru::Batt,
            12 => Fru::App,
            13 => Fru::Magd,
            14 => Fru::Mags,
            15 => Fru::Usb,
            16 => Fru::Cann,
            17 => Fru::Fw,
            18 => Fru::Chg,
            _ => return None,
        })
    }
}

/// One catalogue row (generated). `legacy_bit` is `0xFF` for I and W codes.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CodeInfo {
    /// Instance 0.
    pub code: DiagCode,
    /// `NAME` of the CSV (bench console, copy report).
    pub name: &'static str,
    pub severity: Severity,
    pub action: Action,
    pub fru: Fru,
    pub fru2: Fru,
    /// Legacy `Faults` bit 0..7 (docs/06-diagnostics.md 2.7), `0xFF` = none.
    pub legacy_bit: u8,
    /// Bit n = hazard Hn (n = 1..13).
    pub hazards: u16,
}

impl CodeInfo {
    pub const fn legacy(&self) -> Option<u8> {
        if self.legacy_bit < 8 {
            Some(self.legacy_bit)
        } else {
            None
        }
    }
}

/// Binary search by catalogue identity.
pub fn lookup(code: DiagCode) -> Option<&'static CodeInfo> {
    let id = code.identity();
    CATALOGUE.binary_search_by(|c| c.code.cmp(&id)).ok().map(|i| &CATALOGUE[i])
}

/// Legacy default bit (INTERNAL) for every F or L code without an explicit mapping.
pub const LEGACY_DEFAULT_BIT: u8 = 5;

/// The legacy `Faults` bit a record projects to (2.7): none below FAULT; the catalogue bit, or
/// INTERNAL for unknown codes. `severity` is the record's own severity (it may exceed the
/// catalogue default after an escalation).
pub fn legacy_bit(code: DiagCode, severity: Severity) -> Option<u8> {
    if !severity.stops_delivery() {
        return None;
    }
    Some(code.info().and_then(|i| i.legacy()).unwrap_or(LEGACY_DEFAULT_BIT))
}

/// `DiagRecord::flags` bits (2.6).
pub mod flags {
    pub const LATCHED: u8 = 1 << 0;
    /// Condition still present.
    pub const ACTIVE: u8 = 1 << 1;
    pub const ESCALATED: u8 = 1 << 2;
    pub const FIRST_SINCE_BOOT: u8 = 1 << 3;
    pub const POST: u8 = 1 << 4;
    /// Clear record: the condition of `cause_rec` is gone.
    pub const CLEARED: u8 = 1 << 5;
    /// No `cause_rec`: this record is a root cause.
    pub const ROOT: u8 = 1 << 6;
}

/// The 32 byte diagnostic record (2.6), little endian on the wire.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct DiagRecord {
    pub rec_id: u32,
    pub code: DiagCode,
    /// Raw wire value; see [`DiagRecord::severity`].
    pub severity: u8,
    /// Raw wire value; see [`DiagRecord::action`].
    pub action: u8,
    /// Raw wire value; see [`DiagRecord::fru`].
    pub fru: u8,
    pub fru2: u8,
    /// Seconds since boot.
    pub t_s: u32,
    pub ctx_a: i32,
    pub ctx_b: i32,
    pub ctx_c: u32,
    pub count: u8,
    pub flags: u8,
    /// Low 16 bits of the `rec_id` of the causing record, 0 = root.
    pub cause_rec: u16,
}

impl DiagRecord {
    pub fn to_bytes(&self) -> [u8; RECORD_LEN] {
        let mut b = [0u8; RECORD_LEN];
        b[0..4].copy_from_slice(&self.rec_id.to_le_bytes());
        b[4..8].copy_from_slice(&self.code.0.to_le_bytes());
        b[8] = self.severity;
        b[9] = self.action;
        b[10] = self.fru;
        b[11] = self.fru2;
        b[12..16].copy_from_slice(&self.t_s.to_le_bytes());
        b[16..20].copy_from_slice(&self.ctx_a.to_le_bytes());
        b[20..24].copy_from_slice(&self.ctx_b.to_le_bytes());
        b[24..28].copy_from_slice(&self.ctx_c.to_le_bytes());
        b[28] = self.count;
        b[29] = self.flags;
        b[30..32].copy_from_slice(&self.cause_rec.to_le_bytes());
        b
    }

    /// Exactly 32 bytes, otherwise `None`. Every byte pattern of the right length decodes (a
    /// record is data; unknown enum values are kept and handled fail-safe by the accessors).
    pub fn from_bytes(b: &[u8]) -> Option<DiagRecord> {
        if b.len() != RECORD_LEN {
            return None;
        }
        let u32_at = |o: usize| u32::from_le_bytes([b[o], b[o + 1], b[o + 2], b[o + 3]]);
        Some(DiagRecord {
            rec_id: u32_at(0),
            code: DiagCode(u32_at(4)),
            severity: b[8],
            action: b[9],
            fru: b[10],
            fru2: b[11],
            t_s: u32_at(12),
            ctx_a: u32_at(16) as i32,
            ctx_b: u32_at(20) as i32,
            ctx_c: u32_at(24),
            count: b[28],
            flags: b[29],
            cause_rec: u16::from_le_bytes([b[30], b[31]]),
        })
    }

    /// Fail-safe: an unknown severity value is a FAULT.
    pub fn severity(&self) -> Severity {
        Severity::from_u8_failsafe(self.severity)
    }
    pub fn action(&self) -> Option<Action> {
        Action::from_u8(self.action)
    }
    pub fn fru(&self) -> Option<Fru> {
        Fru::from_u8(self.fru)
    }
    pub fn is_root(&self) -> bool {
        self.cause_rec == 0
    }
    pub fn is_active(&self) -> bool {
        self.flags & flags::ACTIVE != 0
    }
    pub fn is_latched(&self) -> bool {
        self.flags & flags::LATCHED != 0
    }
    pub fn is_clear_record(&self) -> bool {
        self.flags & flags::CLEARED != 0
    }
}
