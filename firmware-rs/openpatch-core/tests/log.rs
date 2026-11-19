//! Event log.
mod common;

use openpatch_core::log::LOG_CAPACITY;
use openpatch_core::*;

#[test]
fn log_ids_start_at_one_and_increase() {
    let mut l = EventLog::new();
    assert_eq!(l.oldest_id(), l.next_id());
    assert_eq!(l.append(10, EventType::Boot, 0, 0), 1);
    assert_eq!(l.append(11, EventType::Resume, 7, 8), 2);
    let mut e = [Event::default(); 4];
    assert_eq!(l.read(1, &mut e), 2);
    assert_eq!(e[1].id, 2);
    assert_eq!(e[1].time_s, 11);
    assert_eq!(e[1].kind, EventType::Resume as u8);
    assert_eq!(e[1].a, 7);
    assert_eq!(e[1].b, 8);
}

#[test]
fn log_read_from_id_and_max() {
    let mut l = EventLog::new();
    for i in 0..10 {
        l.append(0, EventType::Boot, i, 0);
    }
    let mut e = [Event::default(); 4];
    assert_eq!(l.read(5, &mut e), 4);
    assert_eq!(e[0].id, 5);
    assert_eq!(e[3].id, 8);
    assert_eq!(l.read(11, &mut e), 0);
    // C: max == 0 and NULL output buffer both give 0; in Rust both are an empty slice.
    assert_eq!(l.read(5, &mut e[..0]), 0);
    assert_eq!(l.read(5, &mut []), 0);
}

#[test]
fn log_ring_overwrites_oldest_but_ids_persist() {
    let cap = LOG_CAPACITY as u32;
    let mut l = EventLog::new();
    for i in 0..cap + 72 {
        l.append(0, EventType::Boot, i as i32, 0);
    }
    assert_eq!(l.len(), LOG_CAPACITY);
    assert_eq!(l.next_id(), cap + 72 + 1);
    assert_eq!(l.oldest_id(), 73);
    let mut e = [Event::default(); LOG_CAPACITY];
    assert_eq!(l.read(1, &mut e), LOG_CAPACITY);
    assert_eq!(e[0].id, 73);
    assert_eq!(e[0].a, 72);
    assert_eq!(e[LOG_CAPACITY - 1].id, cap + 72);
}

#[test]
fn log_restore_continues_persistent_ids() {
    let mut l = EventLog::restore(1000);
    assert_eq!(l.oldest_id(), 1000);
    assert_eq!(l.append(0, EventType::Boot, 0, 0), 1000);
    let l = EventLog::restore(0); // 0 is invalid -> clamps to 1
    assert_eq!(l.next_id(), 1);
}
