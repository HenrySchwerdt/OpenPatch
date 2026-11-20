//! The status frame the supervisor sends to the main MCU on the UART (`INTERLOCK.md` H: every 500 ms and on every state change).
//! The main firmware turns it into diagnostic records. Fixed 13 bytes: `0xA6 | state | reason | fwd | rev lo hi | hour lo hi |
//! minute lo hi | arms lo hi | crc8` (CRC-8, polynomial 0x07, over the first 12 bytes).

use crate::logic::{FaultReason, State};

pub const FRAME_LEN: usize = 13;
pub const SYNC: u8 = 0xA6;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct StatusFrame {
    pub state: State,
    pub reason: FaultReason,
    pub fwd_in_window: u8,
    pub rev_in_window: u16,
    pub hour_level: u16,
    pub minute_level: u16,
    pub arm_edges: u16,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum DecodeError {
    Length,
    Sync,
    Crc,
    BadState,
    BadReason,
}

pub fn crc8(data: &[u8]) -> u8 {
    let mut c = 0u8;
    for &b in data {
        c ^= b;
        for _ in 0..8 {
            c = if c & 0x80 != 0 { (c << 1) ^ 0x07 } else { c << 1 };
        }
    }
    c
}

fn state_from(b: u8) -> Option<State> {
    Some(match b {
        0 => State::Boot,
        1 => State::Idle,
        2 => State::Armed,
        3 => State::Dead,
        4 => State::Fault,
        5 => State::Locked,
        _ => return None,
    })
}

fn reason_from(b: u8) -> Option<FaultReason> {
    Some(match b {
        0 => FaultReason::None,
        1 => FaultReason::OverCurrent,
        2 => FaultReason::DockedReverse,
        3 => FaultReason::UndockedForward,
        4 => FaultReason::DirectionMismatch,
        5 => FaultReason::PhaseSequence,
        6 => FaultReason::StepOutsideWindow,
        7 => FaultReason::BudgetExceeded,
        9 => FaultReason::LinkLost,
        10 => FaultReason::BootCheck,
        11 => FaultReason::BucketOverflow,
        12 => FaultReason::TooManyFaults,
        _ => return None,
    })
}

impl StatusFrame {
    pub fn encode(&self) -> [u8; FRAME_LEN] {
        let mut f = [0u8; FRAME_LEN];
        f[0] = SYNC;
        f[1] = self.state as u8;
        f[2] = self.reason as u8;
        f[3] = self.fwd_in_window;
        f[4..6].copy_from_slice(&self.rev_in_window.to_le_bytes());
        f[6..8].copy_from_slice(&self.hour_level.to_le_bytes());
        f[8..10].copy_from_slice(&self.minute_level.to_le_bytes());
        f[10..12].copy_from_slice(&self.arm_edges.to_le_bytes());
        f[12] = crc8(&f[..12]);
        f
    }

    pub fn decode(b: &[u8]) -> Result<Self, DecodeError> {
        if b.len() != FRAME_LEN {
            return Err(DecodeError::Length);
        }
        if b[0] != SYNC {
            return Err(DecodeError::Sync);
        }
        if crc8(&b[..12]) != b[12] {
            return Err(DecodeError::Crc);
        }
        Ok(Self {
            state: state_from(b[1]).ok_or(DecodeError::BadState)?,
            reason: reason_from(b[2]).ok_or(DecodeError::BadReason)?,
            fwd_in_window: b[3],
            rev_in_window: u16::from_le_bytes([b[4], b[5]]),
            hour_level: u16::from_le_bytes([b[6], b[7]]),
            minute_level: u16::from_le_bytes([b[8], b[9]]),
            arm_edges: u16::from_le_bytes([b[10], b[11]]),
        })
    }
}
