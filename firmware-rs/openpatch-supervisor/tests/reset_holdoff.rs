//! F7 of the SPICE report: `SUP_PERMIT` stays low for at least 10 ms after any reset or brown-out; the option byte requirement
//! "BOR level = highest" is recorded next to nBOOT_SEL.
use openpatch_supervisor::logic::*;
use openpatch_supervisor::provisioning::*;

const CFG: Config = Config::CUP_MITER_1_1;

/// Same as `CUP_MITER_1_1` but with the boot check and the dead time cut to nothing, so only the F7 hold-off is left in the way.
const FAST: Config = Config { boot_check_ms: 0, dead_ms: 0, min_arm_interval_ms: 0, ..Config::CUP_MITER_1_1 };

fn idle_at(cfg: Config, t: u64) -> Supervisor {
    let mut s = Supervisor::new(cfg, 0, Inputs::DELIVERING, false, false);
    s.tick(t);
    assert_eq!(s.state(), State::Idle);
    s
}

#[test]
fn the_default_holdoff_is_ten_ms() {
    assert_eq!(MIN_RESET_HOLDOFF_MS, 10);
    assert_eq!(CFG.reset_holdoff_ms, 10);
    assert_eq!(CFG.effective_reset_holdoff_ms(), 10);
}

#[test]
fn the_holdoff_cannot_be_configured_below_ten_ms() {
    let zero = Config { reset_holdoff_ms: 0, ..CFG };
    assert_eq!(zero.effective_reset_holdoff_ms(), 10);
    let nine = Config { reset_holdoff_ms: 9, ..CFG };
    assert_eq!(nine.effective_reset_holdoff_ms(), 10);
    let longer = Config { reset_holdoff_ms: 50, ..CFG };
    assert_eq!(longer.effective_reset_holdoff_ms(), 50);
}

#[test]
fn power_up_gives_no_permit_for_ten_ms_even_without_a_boot_check() {
    // power-up / supervisor reset at t = 1000: Supervisor::new starts the hold-off
    let mut s = Supervisor::new(FAST, 1_000, Inputs::DELIVERING, false, false);
    s.tick(1_000);
    assert_eq!(s.state(), State::Idle, "boot check of 0 ms: idle at once");
    let (o, r) = s.on_arm_edge(1_000);
    assert_eq!((o.permit, r), (false, Err(ArmReject::ResetHoldoff)));
    let (o, r) = s.on_arm_edge(1_009);
    assert_eq!((o.permit, r), (false, Err(ArmReject::ResetHoldoff)));
    let (o, r) = s.on_arm_edge(1_010);
    assert_eq!((o.permit, r), (true, Ok(())), "first permit exactly at 10 ms");
}

#[test]
fn the_standard_boot_check_already_covers_it() {
    let mut s = Supervisor::new(CFG, 0, Inputs::DELIVERING, false, false);
    for t in 0..CFG.boot_check_ms as u64 {
        let (o, r) = s.on_arm_edge(t);
        assert!(!o.permit && r.is_err(), "no permit at {t} ms");
    }
}

#[test]
fn a_main_mcu_reset_holds_the_permit_for_ten_ms_whatever_the_dead_time() {
    let mut s = idle_at(FAST, 100);
    // an armed burst is cut by a reset at t = 500
    assert!(s.on_arm_edge(500).0.permit);
    let o = s.on_main_reset(501, false, false);
    assert!(!o.permit, "the permit drops with the reset");
    let (o, r) = s.on_arm_edge(510);
    assert_eq!((o.permit, r), (false, Err(ArmReject::ResetHoldoff)), "9 ms after the reset");
    let (o, r) = s.on_arm_edge(511);
    assert_eq!((o.permit, r), (true, Ok(())), "10 ms after the reset");
}

#[test]
fn a_reset_in_the_dead_time_restarts_the_holdoff() {
    // already DEAD (window used up), the reset arrives 1 ms before the dead time ends: the old logic would allow an arm at once
    let cfg = Config { min_arm_interval_ms: 0, ..CFG };
    let mut s = Supervisor::new(cfg, 0, Inputs::DELIVERING, false, false);
    s.tick(cfg.boot_check_ms as u64);
    let t = 1_000;
    assert!(s.on_arm_edge(t).0.permit);
    s.on_inputs(t + 100, Inputs { mcu_en: false, ..Inputs::DELIVERING }); // burst over: DEAD
    assert_eq!(s.state(), State::Dead);
    s.on_inputs(t + 101, Inputs::DELIVERING);
    let late = t + 100 + CFG.dead_ms as u64 - 1;
    s.on_main_reset(late, false, false);
    s.tick(t + 100 + CFG.dead_ms as u64);
    assert_eq!(s.state(), State::Idle, "dead time over");
    // no minimum arm interval in this config; only the hold-off stands in the way
    assert_eq!(s.on_arm_edge(late + 5).1, Err(ArmReject::ResetHoldoff));
    assert!(s.on_arm_edge(late + 10).1.is_ok());
}

#[test]
fn a_brown_out_without_reset_cuts_the_permit_and_holds_it_off() {
    // F7: a short 3V3 dip that did not reset the chip
    let mut s = idle_at(FAST, 100);
    assert!(s.on_arm_edge(500).0.permit);
    let o = s.on_brown_out(502, false, false);
    assert_eq!((o.permit, o.state), (false, State::Dead));
    assert_eq!(s.on_arm_edge(505).1, Err(ArmReject::ResetHoldoff));
    assert_eq!(s.on_arm_edge(511).1, Err(ArmReject::ResetHoldoff), "9 ms after the brown-out");
    assert_eq!(s.on_arm_edge(512).1, Ok(()), "10 ms after the brown-out");
}

#[test]
fn a_brown_out_while_idle_also_holds_the_permit_off() {
    let mut s = idle_at(FAST, 100);
    s.on_brown_out(200, false, false);
    assert_eq!(s.on_arm_edge(209).1, Err(ArmReject::ResetHoldoff));
    assert!(s.on_arm_edge(210).1.is_ok());
}

#[test]
fn repeated_resets_extend_the_holdoff() {
    let mut s = idle_at(FAST, 100);
    s.on_main_reset(200, false, false);
    s.on_brown_out(205, false, false);
    assert_eq!(s.on_arm_edge(214).1, Err(ArmReject::ResetHoldoff), "10 ms count from the LAST event");
    assert!(s.on_arm_edge(215).1.is_ok());
}

#[test]
fn a_reset_never_clears_a_fault_and_never_grants_a_permit() {
    let mut s = idle_at(FAST, 100);
    s.on_inputs(200, Inputs { oc_ok: false, ..Inputs::DELIVERING });
    assert_eq!(s.state(), State::Fault);
    let o = s.on_brown_out(201, false, false);
    assert_eq!((o.permit, o.state), (false, State::Fault));
}

#[test]
fn the_holdoff_never_shortens_a_longer_dead_time() {
    let mut s = Supervisor::new(CFG, 0, Inputs::DELIVERING, false, false);
    s.tick(CFG.boot_check_ms as u64);
    s.on_main_reset(1_000, false, false);
    assert_eq!(s.state(), State::Dead);
    s.tick(1_000 + 10);
    assert_eq!(s.state(), State::Dead, "10 ms hold-off is over, the 400 ms dead time is not");
    assert_eq!(s.on_arm_edge(1_010).1, Err(ArmReject::State(State::Dead)));
    s.tick(1_000 + CFG.dead_ms as u64);
    assert!(s.on_arm_edge(1_000 + CFG.dead_ms as u64).1.is_ok());
}

// ---- provisioning constants ---------------------------------------------------------------------------------------------------

#[test]
fn bor_level_highest_is_recorded_right_after_nboot_sel() {
    assert_eq!(PROVISIONING_OPTION_BYTES[0].field, "nBOOT_SEL");
    assert_eq!(PROVISIONING_OPTION_BYTES[0].required, "0");
    assert!(PROVISIONING_OPTION_BYTES[1].field.starts_with("BOR level"));
    assert_eq!(PROVISIONING_OPTION_BYTES[1].required, "highest");
    assert_eq!(PROVISIONING_OPTION_BYTES[1], BOR_LEVEL_HIGHEST);
    assert!(PROVISIONING_OPTION_BYTES.iter().all(|r| !r.why.is_empty()));
}

#[test]
fn the_docs_carry_the_same_requirement_next_to_nboot_sel() {
    let doc = include_str!("../../docs/board-cup-v4.md");
    let at = doc.find("nBOOT_SEL").expect("nBOOT_SEL in board-cup-v4.md");
    let near = &doc[at..(at + 200).min(doc.len())];
    assert!(near.contains("BOR level = highest"), "BOR requirement next to nBOOT_SEL: {near}");
    let lib = include_str!("../src/lib.rs");
    let at = lib.find("nBOOT_SEL").unwrap();
    assert!(lib[at..(at + 400).min(lib.len())].contains("BOR level to the HIGHEST"));
}
