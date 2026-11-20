//! The enforced rule: the supervisor is flashed only while the motor supply is cut.
use openpatch_supervisor::flash_guard::*;
use openpatch_supervisor::rom_bootloader::{Command, FrameError};

fn ok() -> Preconditions {
    Preconditions { vmot_mv: Some(40), vmot_low_for_ms: 200, docked: false, delivery_active: false, image_verified: true, vbat_mv: 3_900 }
}

#[test]
fn all_preconditions_met_gives_a_session() {
    assert!(check(&ok()).is_ok());
    assert!(FlashSession::begin(&ok()).unwrap().is_alive());
}

#[test]
fn every_precondition_is_enforced_on_its_own() {
    let cases: [(Preconditions, Refusal); 9] = [
        (Preconditions { vmot_mv: None, ..ok() }, Refusal::SupplyUnknown),
        (Preconditions { vmot_mv: Some(300), ..ok() }, Refusal::SupplyPresent(300)),
        (Preconditions { vmot_mv: Some(4_960), ..ok() }, Refusal::SupplyPresent(4_960)),
        (Preconditions { vmot_low_for_ms: 49, ..ok() }, Refusal::SupplyNotCutLongEnough),
        (Preconditions { docked: true, ..ok() }, Refusal::Docked),
        (Preconditions { delivery_active: true, ..ok() }, Refusal::DeliveryActive),
        (Preconditions { image_verified: false, ..ok() }, Refusal::ImageNotVerified),
        (Preconditions { vbat_mv: 3_599, ..ok() }, Refusal::BatteryLow),
        (Preconditions { vmot_mv: Some(0), vmot_low_for_ms: 0, ..ok() }, Refusal::SupplyNotCutLongEnough),
    ];
    for (p, want) in cases {
        assert_eq!(check(&p), Err(want));
        assert_eq!(FlashSession::begin(&p).err(), Some(want), "no session without the precondition");
    }
    // the boundaries that pass
    assert!(check(&Preconditions { vmot_mv: Some(299), vmot_low_for_ms: 50, vbat_mv: 3_600, ..ok() }).is_ok());
}

#[test]
fn supply_is_checked_before_everything_else() {
    let p = Preconditions { vmot_mv: Some(5_000), docked: true, delivery_active: true, image_verified: false, vbat_mv: 0, ..ok() };
    assert_eq!(check(&p), Err(Refusal::SupplyPresent(5_000)));
}

#[test]
fn frames_need_a_fresh_reading_every_time() {
    let mut s = FlashSession::begin(&ok()).unwrap();
    assert_eq!(s.command(Some(10), Command::Get), Ok([0x00, 0xFF]));
    assert_eq!(s.command(Some(10), Command::ExtendedErase), Ok([0x44, 0xBB]));
    assert_eq!(s.erase_all(Some(10)), Ok([0xFF, 0xFF, 0x00]));
    assert_eq!(s.address(Some(10), 0x0800_0000), Ok([0x08, 0, 0, 0, 0x08]));
    let mut out = [0u8; 258];
    assert_eq!(s.write_data(Some(10), 0x0800_0000, &[0u8; 8], &mut out), Ok(10));
    assert_eq!(s.frames(), 5);
    assert!(s.is_alive());
}

#[test]
fn the_supply_coming_back_ends_the_session_for_good() {
    let mut out = [0u8; 258];
    for bad in [Some(300u16), Some(4_960), None] {
        let mut s = FlashSession::begin(&ok()).unwrap();
        assert!(s.command(Some(0), Command::Get).is_ok());
        assert_eq!(s.write_data(bad, 0x0800_0000, &[0u8; 8], &mut out), Err(SessionError::SupplyReturned));
        assert!(!s.is_alive());
        // every later call fails, even with a perfect reading
        assert_eq!(s.write_data(Some(0), 0x0800_0000, &[0u8; 8], &mut out), Err(SessionError::Aborted));
        assert_eq!(s.erase_all(Some(0)), Err(SessionError::Aborted));
        assert_eq!(s.command(Some(0), Command::Get), Err(SessionError::Aborted));
        assert_eq!(s.address(Some(0), 0x0800_0000), Err(SessionError::Aborted));
        assert_eq!(s.read_length(Some(0), 4), Err(SessionError::Aborted));
        assert_eq!(s.erase_pages(Some(0), &[0], &mut out), Err(SessionError::Aborted));
    }
}

#[test]
fn bad_frames_do_not_kill_the_session_but_never_reach_the_wire() {
    let mut s = FlashSession::begin(&ok()).unwrap();
    let mut out = [0u8; 258];
    assert_eq!(s.write_data(Some(0), 0x0800_0004, &[0u8; 8], &mut out), Err(SessionError::Frame(FrameError::Address)));
    assert_eq!(s.write_data(Some(0), 0x0800_0000, &[0u8; 5], &mut out), Err(SessionError::Frame(FrameError::Alignment)));
    assert_eq!(s.erase_pages(Some(0), &[], &mut out), Err(SessionError::Frame(FrameError::Pages)));
    assert_eq!(s.read_length(Some(0), 0), Err(SessionError::Frame(FrameError::Length)));
    assert!(s.is_alive());
}

#[test]
fn explicit_abort() {
    let mut s = FlashSession::begin(&ok()).unwrap();
    s.abort();
    assert_eq!(s.command(Some(0), Command::Get), Err(SessionError::Aborted));
}

#[test]
fn the_limits_are_the_documented_ones() {
    assert_eq!(VMOT_MAX_MV, 300);
    assert_eq!(VMOT_LOW_MIN_MS, 50);
}
