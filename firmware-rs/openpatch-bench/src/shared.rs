//! State shared between the tasks: channels and atomics. All cross-task communication of the
//! firmware is in this file, so the data flow can be audited in one place.
//!
//! Ownership rules (docs/architecture.md):
//! * `Pump`, the motor / interlock pins and the TPL5010 DONE pin belong to the safety task ONLY.
//! * The BLE task only moves frames through [`FRAME_IN`] / [`FRAME_OUT`]; it never touches the pump.
//! * Flash is written only by the persistence task (and the DFU updater).
use core::fmt::Write;
use core::sync::atomic::{AtomicBool, AtomicI32};
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex as Raw;
use embassy_sync::channel::Channel;
use embassy_sync::signal::Signal;

use crate::config::FRAME_BUF;
use crate::storage::PersistMsg;

/// One protocol frame (at most 244 bytes: ATT MTU 247 - 3).
#[derive(Clone)]
pub struct Frame {
    pub len: u8,
    pub data: [u8; FRAME_BUF],
}

impl Frame {
    pub fn from_slice(s: &[u8]) -> Option<Frame> {
        if s.len() > FRAME_BUF {
            return None;
        }
        let mut f = Frame { len: s.len() as u8, data: [0; FRAME_BUF] };
        f.data[..s.len()].copy_from_slice(s);
        Some(f)
    }
    pub fn bytes(&self) -> &[u8] {
        &self.data[..self.len as usize]
    }
}

pub const CSV_LINE_MAX: usize = 100;

/// One bench log line (ASCII, no terminator): a CSV row, the header, or a `#` status comment.
#[derive(Clone)]
pub struct CsvLine {
    pub len: u8,
    pub data: [u8; CSV_LINE_MAX],
}

impl CsvLine {
    pub fn new() -> Self {
        CsvLine { len: 0, data: [0; CSV_LINE_MAX] }
    }
    pub fn as_str(&self) -> &str {
        core::str::from_utf8(&self.data[..self.len as usize]).unwrap_or("")
    }
    pub fn bytes(&self) -> &[u8] {
        &self.data[..self.len as usize]
    }
}

impl Write for CsvLine {
    fn write_str(&mut self, s: &str) -> core::fmt::Result {
        let b = s.as_bytes();
        let n = self.len as usize;
        if n + b.len() > CSV_LINE_MAX {
            return Err(core::fmt::Error);
        }
        self.data[n..n + b.len()].copy_from_slice(b);
        self.len = (n + b.len()) as u8;
        Ok(())
    }
}

/// UI task -> safety task.
#[derive(Clone, Copy, defmt::Format)]
pub enum UiCmd {
    /// Button short press: silence the alarm buzzer (no fault is cleared).
    SilenceAlarm,
    /// Button held >= 3 s: `Pump::emergency_stop`.
    EmergencyStop,
}

/// BLE bench control / bench defaults -> safety task.
#[derive(Clone, Copy, defmt::Format)]
pub enum BenchCmd {
    Start { pulses: u16, amount_mu: u32, pause_ms: u32 },
    Abort,
}

/// BLE -> safety (raw frames, one per write), safety -> BLE (one per notification).
pub static FRAME_IN: Channel<Raw, Frame, 4> = Channel::new();
pub static FRAME_OUT: Channel<Raw, Frame, 4> = Channel::new();
/// Safety -> BLE: unsolicited notifications for the Alert characteristic (frame type 0x90).
pub static ALERT_OUT: Channel<Raw, Frame, 8> = Channel::new();
/// Safety -> BLE bench log notifications (RTT gets every line too).
pub static CSV_OUT: Channel<Raw, CsvLine, 16> = Channel::new();
pub static UI_CMD: Channel<Raw, UiCmd, 4> = Channel::new();
pub static BENCH_CMD: Channel<Raw, BenchCmd, 2> = Channel::new();
/// Safety / BLE -> persistence task. Producers use `try_send` except for the seq ceiling.
pub static PERSIST: Channel<Raw, PersistMsg, 16> = Channel::new();
/// `POWER.RESETREAS` as read at the very start of `main` (before anything clears it); see `hal::classify_resetreas`.
pub static RESET_REASON: core::sync::atomic::AtomicU32 = core::sync::atomic::AtomicU32::new(0);
/// Persistence -> safety: the seq ceiling that is now durable.
pub static SEQ_ACK: Signal<Raw, u16> = Signal::new();
/// Safety -> DFU task: the safety task ran N good ticks, confirm the image.
pub static BOOT_OK: Signal<Raw, ()> = Signal::new();
/// BLE -> safety: a session key agreement finished (replace the `Session`) or the link that used
/// one closed (back to the key-less production session). Latest value wins.
pub static SESSION_EVT: Signal<Raw, SessionEvent> = Signal::new();

/// See [`SESSION_EVT`]. The keys are secret: never log them.
pub enum SessionEvent {
    Up(openpatch_proto::handshake::SessionKeys),
    Reset,
}

// ---- atomics (single writer each, see comments) ----
/// Written by the HAL (safety task): alarm buzzer requested.
pub static ALARM_ON: AtomicBool = AtomicBool::new(false);
/// Written by the HAL: one confirmation beep requested (cleared by the UI task).
pub static BEEP_REQ: AtomicBool = AtomicBool::new(false);
/// Two beeps requested (draw finished / stalled).
pub static DOUBLE_BEEP_REQ: AtomicBool = AtomicBool::new(false);
/// Simulated DOCKED input (DK; written by the UI task, read by the HAL).
pub static DOCK_SIM: AtomicBool = AtomicBool::new(false);
/// QDEC edge counter (written by the encoder task, read by the HAL).
pub static ENC_COUNTS: AtomicI32 = AtomicI32::new(0);
/// TPL5010 WAKE seen and not yet answered with DONE (set by the helper task, cleared by the HAL).
pub static WAKE_PENDING: AtomicBool = AtomicBool::new(false);
/// Status for the LEDs (written by the safety task / BLE task).
pub static BLE_CONNECTED: AtomicBool = AtomicBool::new(false);
pub static DELIVERING: AtomicBool = AtomicBool::new(false);
pub static BENCH_ACTIVE: AtomicBool = AtomicBool::new(false);
pub static INTERLOCK_FAILED: AtomicBool = AtomicBool::new(false);
pub static TMAG_PRESENT: AtomicBool = AtomicBool::new(false);
/// Set by the safety task when it has a fault latched (alarm LED).
pub static FAULT_LATCHED: AtomicBool = AtomicBool::new(false);
