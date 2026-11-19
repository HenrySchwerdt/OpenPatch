//! Platform persistence helpers that are PURE LOGIC and therefore live (and are tested) in the core: the platform
//! (`openpatch-bench` flash task, the simulator's `Device`) only stores and loads the bytes.
//!
//! * [`SchedRec`]: the basal schedule as a compact record (F2: a reset must never leave the pod with "not suspended"
//!   and no schedule, delivering 0 U/h silently).
//! * [`TempRec`]: an active temp basal (rate, remaining minutes rounded DOWN to the 30 minute granularity).
//! * [`ReservoirPolicy`]: when the reservoir snapshot is rewritten and how the safety margin is NOT re-added on every
//!   boot (F3).
//!
//! `no_std`, no alloc, no unsafe.

use crate::delivery::{BasalSchedule, BasalSeg};
use crate::limits::{BASAL_SEGMENTS_MAX, TEMP_GRANULARITY_MIN};
use crate::reservoir::Reservoir;
use crate::units::MilliUnitsPerHour;

/// Longest schedule record: `count(1) + 24 x (slot(1) + rate u16 LE)`.
pub const SCHED_REC_MAX: usize = 1 + 3 * BASAL_SEGMENTS_MAX;

/// A basal schedule as stored in flash. `len == 0` = no schedule.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SchedRec {
    pub bytes: [u8; SCHED_REC_MAX],
    pub len: u8,
}

impl SchedRec {
    pub const NONE: SchedRec = SchedRec { bytes: [0; SCHED_REC_MAX], len: 0 };

    pub fn is_none(&self) -> bool {
        self.len == 0
    }

    pub fn as_bytes(&self) -> &[u8] {
        &self.bytes[..self.len as usize]
    }

    /// The record of a stored byte string; `None` unless it decodes to a valid schedule (a torn or foreign record is
    /// never restored).
    pub fn from_slice(b: &[u8]) -> Option<SchedRec> {
        SchedRec::decode(b)?;
        let mut r = SchedRec::NONE;
        r.bytes[..b.len()].copy_from_slice(b);
        r.len = b.len() as u8;
        Some(r)
    }

    /// Rates above `u16::MAX` mU/h (the wire limit) cannot occur: the hard cap is 30 000 mU/h.
    pub fn encode(s: &BasalSchedule) -> SchedRec {
        let mut r = SchedRec::NONE;
        let n = s.segs.len().min(BASAL_SEGMENTS_MAX);
        if n == 0 {
            return r;
        }
        r.bytes[0] = n as u8;
        for (i, g) in s.segs.iter().take(n).enumerate() {
            let rate = g.rate.0.min(u16::MAX as u32) as u16;
            r.bytes[1 + 3 * i] = g.start_slot;
            r.bytes[2 + 3 * i..4 + 3 * i].copy_from_slice(&rate.to_le_bytes());
        }
        r.len = (1 + 3 * n) as u8;
        r
    }

    /// `None` for anything that is not exactly a valid record (truncated, wrong length, slots not ascending, ...).
    pub fn decode(b: &[u8]) -> Option<BasalSchedule> {
        let (&n, rest) = b.split_first()?;
        let n = n as usize;
        if n == 0 || n > BASAL_SEGMENTS_MAX || rest.len() != 3 * n {
            return None;
        }
        let mut s = BasalSchedule::new();
        for c in rest.chunks_exact(3) {
            let seg = BasalSeg { start_slot: c[0], rate: MilliUnitsPerHour(u16::from_le_bytes([c[1], c[2]]) as u32) };
            s.segs.push(seg).ok()?;
        }
        s.validate().ok()?;
        Some(s)
    }
}

/// An active temp basal as stored in flash: `(0, 0)` = none.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct TempRec {
    pub rate_mu_h: u16,
    /// Remaining minutes, rounded down to `TEMP_GRANULARITY_MIN`: a restored temp basal can only be SHORTER than it was.
    pub remaining_min: u16,
}

impl TempRec {
    pub const NONE: TempRec = TempRec { rate_mu_h: 0, remaining_min: 0 };

    pub fn from_engine(active: bool, rate: MilliUnitsPerHour, remaining_min: u32) -> TempRec {
        let m = remaining_min / TEMP_GRANULARITY_MIN * TEMP_GRANULARITY_MIN;
        if !active || m == 0 {
            return TempRec::NONE;
        }
        TempRec { rate_mu_h: rate.0.min(u16::MAX as u32) as u16, remaining_min: m as u16 }
    }

    pub fn is_none(&self) -> bool {
        self.remaining_min == 0
    }

    pub fn to_bytes(&self) -> [u8; 4] {
        let r = self.rate_mu_h.to_le_bytes();
        let m = self.remaining_min.to_le_bytes();
        [r[0], r[1], m[0], m[1]]
    }

    pub fn from_bytes(b: &[u8]) -> Option<TempRec> {
        let b: [u8; 4] = b.try_into().ok()?;
        Some(TempRec { rate_mu_h: u16::from_le_bytes([b[0], b[1]]), remaining_min: u16::from_le_bytes([b[2], b[3]]) })
    }
}

/// Reservoir snapshot policy. The persisted value is the consumed steps PLUS a margin, so after a power loss the model can
/// only be LOWER (emptier) than reality: `stored = consumed + margin`, rewritten whenever `consumed + trigger >= stored`.
///
/// F3: the restored value already CONTAINS the margin of the previous run. The old policy compared the restored model
/// with the stored value at the first tick (they are equal), rewrote `consumed + margin` immediately and so made the model
/// one margin emptier on EVERY boot (0.25 U per reset on the 16:20 drive; a reboot loop drained the reservoir model to
/// RESERVOIR_EMPTY). Now nothing is rewritten after a boot until the reservoir actually moved: the margin is added once
/// per run that consumed insulin, never per reboot.
#[derive(Clone, Copy, Debug)]
pub struct ReservoirPolicy {
    margin: u32,
    trigger: u32,
    fill: u32,
    stored: u32,
    boot_consumed: u32,
}

impl ReservoirPolicy {
    /// `restored` = the `(fill_mu, consumed_with_margin)` the platform loaded at boot (`None` = no record).
    pub fn at_boot(margin: u32, trigger: u32, restored: Option<(u32, u32)>) -> ReservoirPolicy {
        let (fill, stored) = restored.unwrap_or((0, 0));
        ReservoirPolicy { margin, trigger, fill, stored, boot_consumed: stored }
    }

    /// The record to write now, if any: `(fill_mu, consumed_steps_with_margin)`. Call [`Self::written`] once queued.
    pub fn next_write(&self, res: &Reservoir) -> Option<(u32, u32)> {
        if !res.is_filled() {
            return None;
        }
        let (fill, consumed) = (res.fill_level().0, res.consumed().0);
        let moved = consumed > self.boot_consumed; // not at the first tick after a boot
        if fill != self.fill || (moved && consumed + self.trigger >= self.stored) {
            Some((fill, consumed.saturating_add(self.margin)))
        } else {
            None
        }
    }

    /// The record was handed to the flash task.
    pub fn written(&mut self, fill: u32, stored: u32) {
        self.fill = fill;
        self.stored = stored;
        self.boot_consumed = 0; // from now on every consumption beyond the new record is tracked normally
    }

    pub fn stored(&self) -> u32 {
        self.stored
    }
}
