//! Typed messages (wire level). Core crate converts these to/from its unit-typed domain.

use crate::consts::{cmd, BASAL_SEGMENTS_MAX, DIAG_LATCHED_MAX, DIAG_RECORDS_PER_RESPONSE, HIST_MAX_PER_RESPONSE};
use heapless::Vec;
pub use openpatch_diag::{DiagRecord, DiagSummary};

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
    /// Diagnostics: records from `from_id` on. `max_events` as on the wire (0 or above 4 gives 4).
    GetFaultLog { from_id: u32, max_events: u8 },
    /// Diagnostics: `selftest::SUBOP_*`.
    RunSelfTest { sub_op: u8 },
    /// Diagnostics: code to clear, 0 = every clearable W/F record.
    ClearDiag { code: u32 },
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
            CommandBody::GetFaultLog { .. } => cmd::GET_FAULT_LOG,
            CommandBody::RunSelfTest { .. } => cmd::RUN_SELF_TEST,
            CommandBody::ClearDiag { .. } => cmd::CLEAR_DIAG,
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
    /// Diagnostics (tags 0x27, 0x28, 0x2F). `None` = the pod does not report them (v1 pod).
    pub diag: Option<DiagSummary>,
    pub fru_health: Option<u64>,
    pub pod_uid: Option<u64>,
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

/// `GetFaultLog` answer.
#[derive(Clone, Debug, PartialEq, Eq, Default)]
pub struct FaultLog {
    pub next_id: u32,
    pub oldest_id: u32,
    /// Codes of the latched set (up to 16).
    pub latched: Vec<u32, DIAG_LATCHED_MAX>,
    pub records: Vec<DiagRecord, DIAG_RECORDS_PER_RESPONSE>,
}

/// `SELFTEST_STATE` (tag 0x2D).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct SelfTestState {
    /// `selftest::IDLE`, `RUNNING`, `DONE`.
    pub state: u8,
    /// 1 POST-S, 2 POST-A, 3 watchdog proof.
    pub kind: u8,
    pub steps_passed: u16,
    pub steps_failed: u16,
}

/// An unsolicited notification (Alert characteristic), decoded.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NotifyBody {
    pub kind: u8,
    pub arg: u32,
    /// `DIAG_RECORD` of a `DIAG_RAISED` notification.
    pub record: Option<DiagRecord>,
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
    /// Diagnostics (tags 0x27 and 0x2A..0x2E): the `DIAG_SUMMARY` of a response without a status
    /// (`ClearDiag`), the fault log, the self-test state, and the code a refusal refers to.
    pub diag: Option<DiagSummary>,
    pub fault_log: Option<FaultLog>,
    pub selftest: Option<SelfTestState>,
    pub diag_code: Option<u32>,
}
