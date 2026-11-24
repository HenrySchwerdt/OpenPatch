//! ACL write / erase protection of the bootloader (nRF52840 ACL peripheral): region arithmetic and policy, host tested against the
//! real layout (`firmware-rs/layout/layout.rs`).
use openpatch_boot_policy::acl::*;

#[path = "../../layout/layout.rs"]
mod layout;

fn map() -> FlashMap {
    FlashMap {
        page: layout::PAGE,
        flash_size: layout::FLASH_SIZE,
        bootloader: Span::new(layout::BOOTLOADER_START, layout::BOOTLOADER_SIZE),
        state: Span::new(layout::STATE_START, layout::STATE_SIZE),
        active: Span::new(layout::ACTIVE_START, layout::ACTIVE_SIZE),
        dfu: Span::new(layout::DFU_START, layout::DFU_SIZE),
        storage: Span::new(layout::STORAGE_START, layout::STORAGE_SIZE),
    }
}

// ---- the plan for the real layout -------------------------------------------------------------------------------------------

#[test]
fn the_real_layout_is_a_valid_map() {
    assert_eq!(validate_map(&map()), Ok(()));
}

#[test]
fn the_bootloader_code_is_write_and_erase_protected_read_allowed() {
    let plan = plan_bootloader(&map()).unwrap();
    assert_eq!(plan.entries().len(), 1);
    let e = plan.entries()[0];
    assert_eq!(e.region, 0);
    assert_eq!((e.addr, e.size), (0x0000_0000, 0x8000));
    // WRITE (bit 1) = 1 = disabled: no write, no erase. READ (bit 2) = 0: the code stays executable (we jump out of it).
    assert_eq!(e.perm, PERM_WRITE_DISABLE);
    assert_eq!(e.perm, 0b010);
}

#[test]
fn register_addresses_follow_the_product_specification() {
    // ACL base 0x4001E000, ACL[n].ADDR = 0x800 + 0x10 n, SIZE = +4, PERM = +8
    assert_eq!(ACL_BASE, 0x4001_E000);
    assert_eq!(reg_addr(0), 0x4001_E800);
    assert_eq!(reg_size(0), 0x4001_E804);
    assert_eq!(reg_perm(0), 0x4001_E808);
    assert_eq!(reg_addr(7), 0x4001_E870);
    assert_eq!(reg_perm(7), 0x4001_E878);
}

#[test]
fn the_writes_are_addr_size_perm_per_region_in_that_order() {
    let plan = plan_bootloader(&map()).unwrap();
    let w: Vec<(u32, u32)> = plan.writes().collect();
    assert_eq!(w, vec![(0x4001_E800, 0), (0x4001_E804, 0x8000), (0x4001_E808, PERM_WRITE_DISABLE)]);
}

#[test]
fn the_plan_never_touches_anything_the_application_writes() {
    let m = map();
    let plan = plan_bootloader(&m).unwrap();
    for e in plan.entries() {
        let s = Span::new(e.addr, e.size);
        for area in [m.state, m.active, m.dfu, m.storage] {
            assert!(!s.overlaps(area), "{s:?} overlaps {area:?}");
        }
    }
}

// ---- refusals ---------------------------------------------------------------------------------------------------------------

#[test]
fn the_bootloader_state_page_cannot_be_protected_because_the_application_confirms_through_it() {
    let m = map();
    let r = plan_with(&m, &[Protect::write(m.state)]);
    assert_eq!(r.unwrap_err(), AclError::AppWritable(Area::State));
}

#[test]
fn overlap_with_the_application_dfu_or_storage_is_refused() {
    let m = map();
    // one page into ACTIVE
    let r = plan_with(&m, &[Protect::write(Span::new(0, 0xA000))]);
    assert_eq!(r.unwrap_err(), AclError::AppWritable(Area::State));
    let r = plan_with(&m, &[Protect::write(Span::new(layout::ACTIVE_START, layout::PAGE))]);
    assert_eq!(r.unwrap_err(), AclError::AppWritable(Area::Active));
    let r = plan_with(&m, &[Protect::write(Span::new(layout::DFU_START, layout::PAGE))]);
    assert_eq!(r.unwrap_err(), AclError::AppWritable(Area::Dfu));
    let r = plan_with(&m, &[Protect::write(Span::new(layout::STORAGE_START, layout::PAGE))]);
    assert_eq!(r.unwrap_err(), AclError::AppWritable(Area::Storage));
}

#[test]
fn unaligned_start_or_size_is_refused() {
    let m = map();
    assert_eq!(plan_with(&m, &[Protect::write(Span::new(0x10, 0x1000))]).unwrap_err(), AclError::Unaligned);
    assert_eq!(plan_with(&m, &[Protect::write(Span::new(0, 0x1004))]).unwrap_err(), AclError::Unaligned);
}

#[test]
fn an_empty_region_or_one_without_any_protection_bit_is_refused() {
    let m = map();
    assert_eq!(plan_with(&m, &[Protect::write(Span::new(0, 0))]).unwrap_err(), AclError::Empty);
    let none = Protect { span: Span::new(0, 0x1000), no_write: false, no_read: false };
    assert_eq!(plan_with(&m, &[none]).unwrap_err(), AclError::NoProtection);
}

#[test]
fn a_region_beyond_the_flash_or_above_half_the_flash_is_refused() {
    let mut m = map();
    assert_eq!(plan_with(&m, &[Protect::write(Span::new(0xFF000, 0x2000))]).unwrap_err(), AclError::OutsideFlash);
    // the address overflows u32
    assert_eq!(plan_with(&m, &[Protect::write(Span::new(0xFFFF_F000, 0x2000))]).unwrap_err(), AclError::OutsideFlash);
    // "The maximum region is limited to half the flash size": a 512 KB + 4 KB bootloader cannot be one region
    m.bootloader = Span::new(0, 0x81000);
    m.state = Span::new(0x81000, 0x1000);
    m.active = Span::new(0x82000, 0x3D000);
    m.dfu = Span::new(0xBF000, 0x3E000);
    m.storage = Span::new(0xFD000, 0x3000);
    assert_eq!(validate_map(&m), Ok(()));
    assert_eq!(plan_bootloader(&m).unwrap_err(), AclError::TooLarge);
}

#[test]
fn read_protecting_the_bootloader_code_is_refused_it_still_executes_the_jump() {
    let m = map();
    let p = Protect { span: m.bootloader, no_write: true, no_read: true };
    assert_eq!(plan_with(&m, &[p]).unwrap_err(), AclError::ReadProtectsBootloader);
}

#[test]
fn overlapping_regions_and_more_than_eight_are_refused() {
    let m = map();
    let a = Protect::write(Span::new(0, 0x2000));
    let b = Protect::write(Span::new(0x1000, 0x2000));
    assert_eq!(plan_with(&m, &[a, b]).unwrap_err(), AclError::RegionsOverlap);
    let many: Vec<Protect> = (0..9).map(|i| Protect::write(Span::new(i * 0x1000, 0x1000))).collect();
    assert_eq!(plan_with(&m, &many).unwrap_err(), AclError::TooManyRegions);
}

#[test]
fn a_plan_that_leaves_part_of_the_bootloader_writable_is_refused() {
    let m = map();
    assert_eq!(plan_with(&m, &[Protect::write(Span::new(0, 0x4000))]).unwrap_err(), AclError::BootloaderNotCovered);
    // two regions that together cover it are fine
    let p = plan_with(&m, &[Protect::write(Span::new(0, 0x4000)), Protect::write(Span::new(0x4000, 0x4000))]).unwrap();
    assert_eq!(p.entries().len(), 2);
    assert_eq!(p.entries()[1].region, 1);
}

#[test]
fn a_broken_map_is_refused_before_anything_is_planned() {
    let mut m = map();
    m.page = 0;
    assert_eq!(validate_map(&m), Err(AclError::InvalidMap));
    let mut m = map();
    m.active = Span::new(layout::ACTIVE_START - layout::PAGE, layout::ACTIVE_SIZE); // overlaps the state page
    assert_eq!(validate_map(&m), Err(AclError::InvalidMap));
    assert_eq!(plan_bootloader(&m).unwrap_err(), AclError::InvalidMap);
    let mut m = map();
    m.bootloader = Span::new(0x800, 0x7800); // not page aligned
    assert_eq!(validate_map(&m), Err(AclError::InvalidMap));
}

// ---- read-back --------------------------------------------------------------------------------------------------------------

#[test]
fn the_read_back_must_match_every_register() {
    let plan = plan_bootloader(&map()).unwrap();
    let regs: std::collections::HashMap<u32, u32> = plan.writes().collect();
    assert_eq!(plan.verify(|a| regs.get(&a).copied().unwrap_or(0)), Ok(()));
    // a PERM that reads back 0 (write ignored, e.g. a second configuration attempt) is a mismatch
    let r = plan.verify(|a| if a == reg_perm(0) { 0 } else { regs.get(&a).copied().unwrap_or(0) });
    assert_eq!(r, Err(Mismatch { reg: reg_perm(0), expected: PERM_WRITE_DISABLE, got: 0 }));
}

#[test]
fn span_arithmetic() {
    let a = Span::new(0x1000, 0x1000);
    assert!(a.overlaps(Span::new(0x1FFF, 1)));
    assert!(!a.overlaps(Span::new(0x2000, 0x1000)));
    assert!(!a.overlaps(Span::new(0, 0x1000)));
    assert_eq!(a.end(), Some(0x2000));
    assert_eq!(Span::new(0xFFFF_FFFF, 2).end(), None);
}
