//! Pairing window: opened by a button press, 60 s. LE Secure Connections bonding is only accepted
//! while it is open (docs/architecture.md, firmware/docs/openpatch-protocol.md section 1).
use core::cell::Cell;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::blocking_mutex::Mutex;
use embassy_time::{Duration, Instant};

use crate::config::PAIRING_WINDOW_S;

static UNTIL: Mutex<CriticalSectionRawMutex, Cell<Option<Instant>>> = Mutex::new(Cell::new(None));

pub fn open() {
    let until = Instant::now() + Duration::from_secs(PAIRING_WINDOW_S);
    UNTIL.lock(|c| c.set(Some(until)));
}

pub fn close() {
    UNTIL.lock(|c| c.set(None));
}

pub fn is_open() -> bool {
    UNTIL.lock(|c| matches!(c.get(), Some(t) if Instant::now() < t))
}
