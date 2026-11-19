//! Error / result codes, numerically identical to `op_err_t` of the C reference.

/// Non-zero result codes (0 = OK is `Ok(..)` in Rust). `repr(u8)` values are the wire values.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
#[repr(u8)]
pub enum Error {
    BadArg = 1,
    /// Above the configured / hard limit.
    Limit = 2,
    Busy = 3,
    Fault = 4,
    Suspended = 5,
    NotSuspended = 6,
    Reservoir = 7,
    Persists = 8,
    Unsupported = 9,
    Frame = 10,
    Crc = 11,
    Version = 12,
    Replay = 13,
    Auth = 14,
    TooLarge = 15,
    Hourly = 16,
    NotFound = 17,
    Session = 18,
    NotDocked = 19,
    Released = 20,
    AlreadyActive = 21,
    Pair = 22,
    WearExpired = 23,
    Charging = 24,
    /// Rust extension: mandatory priming after a fill has not been done.
    PrimeRequired = 26,
    /// Rust extension: refused because the pod is docked (draw mode only when undocked).
    Docked = 27,
    /// Diagnostics: not suspended, a draw is running or a test is already running.
    SelfTestRefused = 28,
    /// Diagnostics: `Resume` / `Activate` refused because a latched code is set (the response
    /// carries `DIAG_CODE` of the root latched code).
    Latched = 29,
    /// Diagnostics: the code is latched and its verification test has not passed (or the cause persists).
    NotClearable = 30,
    /// Rust extension: `Resume` refused because the pod holds no basal schedule (for example after a reset whose
    /// schedule could not be restored): send `SetBasalSchedule` (or `Activate`) first. Never silently 0 U/h.
    NoSchedule = 31,
}

impl Error {
    /// Wire value.
    #[inline]
    pub const fn code(self) -> u8 {
        self as u8
    }

    /// Inverse of [`Error::code`]; `0` (OK) and unknown codes give `None`.
    pub const fn from_code(c: u8) -> Option<Error> {
        Some(match c {
            1 => Error::BadArg,
            2 => Error::Limit,
            3 => Error::Busy,
            4 => Error::Fault,
            5 => Error::Suspended,
            6 => Error::NotSuspended,
            7 => Error::Reservoir,
            8 => Error::Persists,
            9 => Error::Unsupported,
            10 => Error::Frame,
            11 => Error::Crc,
            12 => Error::Version,
            13 => Error::Replay,
            14 => Error::Auth,
            15 => Error::TooLarge,
            16 => Error::Hourly,
            17 => Error::NotFound,
            18 => Error::Session,
            19 => Error::NotDocked,
            20 => Error::Released,
            21 => Error::AlreadyActive,
            22 => Error::Pair,
            23 => Error::WearExpired,
            24 => Error::Charging,
            26 => Error::PrimeRequired,
            27 => Error::Docked,
            28 => Error::SelfTestRefused,
            29 => Error::Latched,
            30 => Error::NotClearable,
            31 => Error::NoSchedule,
            _ => return None,
        })
    }

    /// `Result` to the wire result byte (0 = OK).
    #[inline]
    pub fn result_code<T>(r: &Result<T, Error>) -> u8 {
        match r {
            Ok(_) => 0,
            Err(e) => e.code(),
        }
    }
}
