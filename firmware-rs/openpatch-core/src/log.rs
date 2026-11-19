//! Event log: fixed ring (no heap) with persistent, strictly increasing 32-bit ids. Ids survive
//! power cycles if the platform stores [`EventLog::next_id`] (as a ceiling) and passes it to
//! [`EventLog::restore`] at boot; the events themselves live in RAM.

use openpatch_proto::HistoryEvent;

pub const LOG_CAPACITY: usize = 128;

/// `Release.b` reasons.
pub const REL_COMMAND: i32 = 0;
pub const REL_CHARGER: i32 = 1;
pub const REL_WEAR: i32 = 2;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
#[repr(u8)]
pub enum EventType {
    Boot = 1,
    BolusStart = 2,
    BolusDone = 3,
    BolusCancel = 4,
    TempStart = 5,
    TempDone = 6,
    TempCancel = 7,
    TempCommFallback = 8,
    BasalSet = 9,
    Suspend = 10,
    Resume = 11,
    Fill = 12,
    Prime = 13,
    Fault = 14,
    Ack = 15,
    LowReservoir = 16,
    LowBattery = 17,
    Undocked = 18,
    Docked = 19,
    Activate = 20,
    Release = 21,
    WearWarning = 22,
    WearExpired = 23,
    Paired = 24,
    /// Draw (refill) started. a = requested mU, b = steps.
    DrawStart = 25,
    /// Draw finished. a = drawn mU (step-exact), b = requested mU.
    DrawDone = 26,
    /// Draw ended by a stall / end-stop before the requested volume. a = drawn mU, b = requested mU.
    DrawStall = 27,
    /// Prime finished. a = steps.
    PrimeDone = 30,
    /// A diagnostic record was raised (docs/06-diagnostics.md 5.4): a = code, b = `ctx_a`. Written
    /// only after [`crate::Pump::set_diag_history`], so a v1-only history reader sees that
    /// something happened; the legacy `Fault` event (14) is written as before.
    Diag = 31,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Event {
    pub id: u32,
    pub time_s: u32,
    pub kind: u8,
    pub a: i32,
    pub b: i32,
}

impl From<Event> for HistoryEvent {
    fn from(e: Event) -> Self {
        HistoryEvent { id: e.id, time_s: e.time_s, kind: e.kind, a: e.a, b: e.b }
    }
}

#[derive(Clone)]
pub struct EventLog {
    ev: [Event; LOG_CAPACITY],
    next_id: u32,
    count: u32,
}

impl Default for EventLog {
    fn default() -> Self {
        Self::new()
    }
}

impl EventLog {
    pub const fn new() -> Self {
        Self { ev: [Event { id: 0, time_s: 0, kind: 0, a: 0, b: 0 }; LOG_CAPACITY], next_id: 1, count: 0 }
    }

    /// Empty log continuing at `next_id` (0 is treated as 1).
    pub fn restore(next_id: u32) -> Self {
        let mut l = Self::new();
        l.next_id = if next_id == 0 { 1 } else { next_id };
        l
    }

    pub fn next_id(&self) -> u32 {
        self.next_id
    }

    /// Oldest stored id (== `next_id` when empty).
    pub fn oldest_id(&self) -> u32 {
        self.next_id.wrapping_sub(self.count)
    }

    pub fn append(&mut self, time_s: u32, kind: EventType, a: i32, b: i32) -> u32 {
        let id = self.next_id;
        self.next_id = self.next_id.wrapping_add(1);
        self.ev[id as usize % LOG_CAPACITY] = Event { id, time_s, kind: kind as u8, a, b };
        if (self.count as usize) < LOG_CAPACITY {
            self.count += 1;
        }
        id
    }

    /// Up to `out.len()` events with id >= `from_id`, oldest first. Returns how many were copied.
    pub fn read(&self, from_id: u32, out: &mut [Event]) -> usize {
        let mut id = self.oldest_id();
        if from_id > id {
            id = from_id;
        }
        let mut n = 0;
        while id < self.next_id && n < out.len() {
            out[n] = self.ev[id as usize % LOG_CAPACITY];
            n += 1;
            id += 1;
        }
        n
    }

    pub fn len(&self) -> usize {
        self.count as usize
    }
    pub fn is_empty(&self) -> bool {
        self.count == 0
    }
}
