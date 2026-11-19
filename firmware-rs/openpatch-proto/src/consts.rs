//! Protocol constants and GATT UUIDs.

pub const PROTO_VERSION: u8 = 1;
pub const FRAME_HEADER: usize = 7;
pub const FRAME_CRC: usize = 2;
/// ATT MTU 247 - 3: one frame = one notification.
pub const FRAME_MAX: usize = 244;
pub const CCM_TAG_LEN: usize = 8;
pub const CCM_NONCE_LEN: usize = 13;
/// 0xFFFF is reserved: forces a rekey before a nonce could repeat.
pub const SEQ_MAX: u16 = 0xFFFE;
pub const HIST_MAX_PER_RESPONSE: usize = 10;
pub const BASAL_SEGMENTS_MAX: usize = 24;

pub const FLAG_ENCRYPTED: u8 = 1 << 0;
pub const FLAG_RESPONSE: u8 = 1 << 1;
/// Response type = command type | 0x80.
pub const RSP_BIT: u8 = 0x80;

/// 128-bit UUIDs, big-endian text order `2E092A48-506C-477E-ADD4-448BF149xxxx`.
pub const UUID_BASE: [u8; 16] = [
    0x2E, 0x09, 0x2A, 0x48, 0x50, 0x6C, 0x47, 0x7E, 0xAD, 0xD4, 0x44, 0x8B, 0xF1, 0x49, 0x00, 0x00,
];
pub const UUID_SERVICE: u128 = 0x2E092A48_506C_477E_ADD4_448BF1490001;
pub const UUID_COMMAND: u128 = 0x2E092A48_506C_477E_ADD4_448BF1490002;
pub const UUID_RESPONSE: u128 = 0x2E092A48_506C_477E_ADD4_448BF1490003;
pub const UUID_ALERT: u128 = 0x2E092A48_506C_477E_ADD4_448BF1490004;

/// Command ids.
pub mod cmd {
    pub const GET_STATUS: u8 = 0x01;
    pub const SET_BASAL_SCHEDULE: u8 = 0x02;
    pub const SET_TEMP_BASAL: u8 = 0x03;
    pub const CANCEL_TEMP_BASAL: u8 = 0x04;
    pub const BOLUS: u8 = 0x05;
    pub const CANCEL_BOLUS: u8 = 0x06;
    pub const SUSPEND: u8 = 0x07;
    pub const RESUME: u8 = 0x08;
    pub const FILL_PRIME: u8 = 0x09;
    pub const ACKNOWLEDGE: u8 = 0x0A;
    pub const GET_HISTORY: u8 = 0x0B;
    pub const SET_PAIRING: u8 = 0x0C;
    pub const ACTIVATE: u8 = 0x0D;
    pub const RELEASE: u8 = 0x0E;
    /// Rust extension: automatic draw (refill) of `FILL_MU` mU; amount 0 cancels a running draw.
    /// Only suspended + undocked.
    pub const FILL_DRAW: u8 = 0x0F;
}

/// TLV tags.
pub mod tag {
    pub const RESULT: u8 = 0x01;
    pub const BASAL_SEG: u8 = 0x02;
    pub const RATE_MU_H: u8 = 0x03;
    pub const DURATION_MIN: u8 = 0x04;
    pub const AMOUNT_MU: u8 = 0x05;
    pub const FILL_MU: u8 = 0x06;
    pub const PRIME_STEPS: u8 = 0x07;
    pub const SUB_OP: u8 = 0x08;
    pub const FAULT_MASK: u8 = 0x09;
    pub const FROM_ID: u8 = 0x0A;
    pub const MAX_EVENTS: u8 = 0x0B;
    pub const TIME_OF_DAY_MS: u8 = 0x0C;
    pub const HISTORY_EVENT: u8 = 0x0D;
    pub const NEXT_EVENT_ID: u8 = 0x0E;
    pub const OLDEST_EVENT_ID: u8 = 0x0F;
    pub const STATE_FLAGS: u8 = 0x10;
    pub const RESERVOIR_MU: u8 = 0x11;
    pub const BATTERY_MV: u8 = 0x12;
    pub const BOLUS_REMAINING_MU: u8 = 0x13;
    pub const TEMP_RATE_MU_H: u8 = 0x14;
    pub const TEMP_REMAINING_MIN: u8 = 0x15;
    pub const CURRENT_RATE_MU_H: u8 = 0x16;
    pub const DELIVERED_MU: u8 = 0x17;
    pub const SCHEDULED_MU: u8 = 0x18;
    pub const FW_VERSION: u8 = 0x19;
    /// Highest accepted command seq (GetStatus; resync after a pod reboot).
    pub const LAST_SEQ: u8 = 0x1A;
    /// 10 bytes: `u16 drive_id, u32 uU/step, u16 steps/rev, u16 gear ratio x100`.
    pub const DRIVE_CAL: u8 = 0x1B;
    /// 10 bytes: `u32 pair_id, u8 role, u8 delivery_state, u32 wear_s`.
    pub const POD_INFO: u8 = 0x1C;
    pub const PAIR_ID: u8 = 0x1D;
    pub const ROLE: u8 = 0x1E;
    pub const ACTIVATION_ID: u8 = 0x1F;
    pub const ACT_DELIVERED_MU: u8 = 0x20;
    // ---- Rust extensions (additive; the C reference skips unknown tags) ----
    /// u8 draw state, see `draw`.
    pub const DRAW_STATE: u8 = 0x21;
    /// u32 volume requested by the last/current draw (mU).
    pub const DRAW_REQUESTED_MU: u8 = 0x22;
    /// u32 volume drawn so far / in the last draw (mU, step-exact and encoder-confirmed).
    pub const DRAW_DONE_MU: u8 = 0x23;
    /// Notification: u8 kind, u32 argument.
    pub const NOTIFY_KIND: u8 = 0x25;
    pub const NOTIFY_ARG: u8 = 0x26;
}

pub const SUBOP_FILL: u8 = 1;
pub const SUBOP_PRIME: u8 = 2;

/// `Status::flags` bits (STATE_FLAGS tag).
pub mod st {
    pub const SUSPENDED: u16 = 1 << 0;
    pub const BOLUS_ACTIVE: u16 = 1 << 1;
    pub const TEMP_ACTIVE: u16 = 1 << 2;
    pub const HAS_SCHEDULE: u16 = 1 << 3;
    pub const LOW_RESERVOIR: u16 = 1 << 4;
    pub const ALARM: u16 = 1 << 5;
    pub const FILLED: u16 = 1 << 6;
    pub const LOW_BATTERY: u16 = 1 << 7;
    pub const WEAR_WARNING: u16 = 1 << 8;
    pub const DOCKED: u16 = 1 << 9;
    pub const ACTIVE: u16 = 1 << 10;
    /// Draw (refill) in progress.
    pub const DRAWING: u16 = 1 << 11;
    /// Mandatory priming after a fill / draw has not been done yet.
    pub const PRIME_REQUIRED: u16 = 1 << 12;
}

pub(crate) const EVENT_TLV_LEN: usize = 17;
pub(crate) const POD_INFO_TLV_LEN: usize = 10;
pub(crate) const DRIVE_CAL_TLV_LEN: usize = 10;

/// `DRAW_STATE` values.
pub mod draw {
    pub const IDLE: u8 = 0;
    pub const DRAWING: u8 = 1;
    /// Requested volume drawn.
    pub const DONE: u8 = 2;
    /// Ended early by a stall (rear end-stop or jam): `DRAW_DONE_MU` is what was actually drawn.
    pub const STALLED: u8 = 3;
    /// Cancelled (FillDraw 0, dock, fault, emergency stop): partial volume in `DRAW_DONE_MU`.
    pub const ABORTED: u8 = 4;
}

/// Unsolicited notifications on the Alert characteristic (frame type 0x90, own sequence counter,
/// nonce direction 2 when encrypted).
pub mod notify {
    pub const FRAME_TYPE: u8 = 0x90;
    /// Draw progress, arg = volume confirmed so far (mU).
    pub const DRAW_PROGRESS: u8 = 1;
    /// Fault latched, arg = new fault bits.
    pub const FAULT: u8 = 2;
    /// Draw finished, arg = drawn volume (mU).
    pub const DRAW_DONE: u8 = 3;
    /// Draw ended early by a stall, arg = drawn volume (mU).
    pub const DRAW_STALLED: u8 = 4;
}
