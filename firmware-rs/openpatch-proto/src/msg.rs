//! Typed messages (wire level). Core crate converts these to/from its unit-typed domain.

use crate::consts::{cmd, BASAL_SEGMENTS_MAX, HIST_MAX_PER_RESPONSE};
use heapless::Vec;

/// One basal segment on the wire: slot 0..47 (30 min), rate in mU/h (u16).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct BasalSeg {
    pub start_slot: u8,
    pub rate_mu_h: u16,
}

pub type BasalSegs = Vec<BasalSeg, BASAL_SEGMENTS_MAX>;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum CommandBody {
    GetStatus,
    SetBasalSchedule(BasalSegs),
    SetTempBasal { rate_mu_h: u16, duration_min: u16 },
    CancelTempBasal,
    Bolus { amount_mu: u32 },
    CancelBolus,
    Suspend,
    Resume,
    /// Raw sub-op as on the wire: 1 = Fill (uses `fill_mu`), 2 = Prime (uses `prime_steps`).
    FillPrime { sub_op: u8, fill_mu: u32, prime_steps: u16 },
    Acknowledge { fault_mask: u16 },
    GetHistory { from_id: u32, max_events: u8 },
    SetPairing { pair_id: u32, role: u8 },
    Activate {
        pair_id: u32,
        activation_id: u32,
        schedule: BasalSegs,
        /// Remaining temp basal handed over: `(rate_mu_h, duration_min)`.
        temp: Option<(u16, u16)>,
    },
    Release { pair_id: u32 },
    /// Rust extension: automatic draw of `amount_mu` (0 = cancel).
    FillDraw { amount_mu: u32 },
}

impl CommandBody {
    pub fn type_id(&self) -> u8 {
        match self {
            CommandBody::GetStatus => cmd::GET_STATUS,
            CommandBody::SetBasalSchedule(_) => cmd::SET_BASAL_SCHEDULE,
            CommandBody::SetTempBasal { .. } => cmd::SET_TEMP_BASAL,
            CommandBody::CancelTempBasal => cmd::CANCEL_TEMP_BASAL,
            CommandBody::Bolus { .. } => cmd::BOLUS,
            CommandBody::CancelBolus => cmd::CANCEL_BOLUS,
            CommandBody::Suspend => cmd::SUSPEND,
            CommandBody::Resume => cmd::RESUME,
            CommandBody::FillPrime { .. } => cmd::FILL_PRIME,
            CommandBody::Acknowledge { .. } => cmd::ACKNOWLEDGE,
            CommandBody::GetHistory { .. } => cmd::GET_HISTORY,
            CommandBody::SetPairing { .. } => cmd::SET_PAIRING,
            CommandBody::Activate { .. } => cmd::ACTIVATE,
            CommandBody::Release { .. } => cmd::RELEASE,
            CommandBody::FillDraw { .. } => cmd::FILL_DRAW,
        }
    }
}

/// A decoded command. `time_of_day_ms` may accompany any command.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Command {
    pub seq: u16,
    pub time_of_day_ms: Option<u32>,
    pub body: CommandBody,
}

impl Command {
    pub fn new(seq: u16, body: CommandBody) -> Self {
        Self { seq, time_of_day_ms: None, body }
    }
}

/// Status block (GetStatus / Activate / Release responses).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct Status {
    pub flags: u16,
    pub faults: u16,
    pub battery_mv: u16,
    pub temp_rate_mu_h: u16,
    pub temp_remaining_min: u16,
    pub current_rate_mu_h: u16,
    pub fw_version: u16,
    pub reservoir_mu: u32,
    pub bolus_remaining_mu: u32,
    pub delivered_mu: u32,
    pub scheduled_mu: u32,
    pub next_event_id: u32,
    pub last_seq: u16,
    pub cal_drive_id: u16,
    pub cal_steps_per_rev: u16,
    pub cal_gear_ratio_x100: u16,
    pub cal_uu_per_step: u32,
    pub pair_id: u32,
    pub wear_s: u32,
    pub role: u8,
    pub delivery_state: u8,
    /// Rust extensions (tags 0x21..0x23).
    pub draw_state: u8,
    pub draw_requested_mu: u32,
    pub draw_done_mu: u32,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct HistoryEvent {
    pub id: u32,
    pub time_s: u32,
    pub kind: u8,
    pub a: i32,
    pub b: i32,
}

#[derive(Clone, Debug, PartialEq, Eq, Default)]
pub struct History {
    pub next_event_id: u32,
    pub oldest_event_id: u32,
    pub events: Vec<HistoryEvent, HIST_MAX_PER_RESPONSE>,
}

#[derive(Clone, Debug, PartialEq, Eq, Default)]
pub struct Response {
    /// Command type (without the response bit).
    pub type_: u8,
    pub seq: u16,
    /// 0 = OK, else an [`crate::Error`] code.
    pub result: u8,
    pub status: Option<Status>,
    pub act_delivered_mu: Option<u32>,
    pub history: Option<History>,
}
