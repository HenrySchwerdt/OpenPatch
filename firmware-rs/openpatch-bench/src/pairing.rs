//! Pairing window: opened by a button press, 60 s. LE Secure Connections bonding is only accepted
//! while it is open (docs/architecture.md, firmware/docs/openpatch-protocol.md section 1).
use core::cell::Cell;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::blocking_mutex::Mutex;
use embassy_time::{Duration, Instant};

use crate::config::PAIRING_WINDOW_S;

static UNTIL: Mutex<CriticalSectionRawMutex, Cell<Option<Instant>>> = Mutex::new(Cell::new(None));
/// Application layer pairing window (protocol v1.1 section 5.2, pairing secret). Opened by the same
/// button press, but NOT closed by the BLE bond: the bond is created first, the app layer pairing
/// follows on the encrypted link. Closed by a finished application layer pairing or by the timeout.
static APP_UNTIL: Mutex<CriticalSectionRawMutex, Cell<Option<Instant>>> = Mutex::new(Cell::new(None));

pub fn open() {
    let until = Instant::now() + Duration::from_secs(PAIRING_WINDOW_S);
    UNTIL.lock(|c| c.set(Some(until)));
    APP_UNTIL.lock(|c| c.set(Some(until)));
}

pub fn close() {
    UNTIL.lock(|c| c.set(None));
}

/// Application layer pairing (pairing secret) allowed?
pub fn app_is_open() -> bool {
    APP_UNTIL.lock(|c| matches!(c.get(), Some(t) if Instant::now() < t))
}

/// One application layer pairing per button press.
pub fn app_close() {
    APP_UNTIL.lock(|c| c.set(None));
}

pub fn is_open() -> bool {
    UNTIL.lock(|c| matches!(c.get(), Some(t) if Instant::now() < t))
}
