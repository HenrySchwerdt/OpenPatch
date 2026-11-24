//! Write / erase protection of the bootloader with the nRF52840 ACL peripheral, as data. The bootloader writes the registers this
//! module plans, right before it jumps to the application; the protection then holds until the next reset.
//!
//! **Source.** nRF52840 Product Specification, chapter "Peripherals", section "ACL - Access control lists"
//! (`docs.nordicsemi.com/bundle/ps_nrf52840/page/acl.html`, read 2026-11-24; the page shows no revision number). Facts used:
//! * instance ACL at `0x4001_E000`, 8 regions, `ACL[n].ADDR` at `0x800 + 0x10 n`, `ACL[n].SIZE` at `+0x4`, `ACL[n].PERM` at `+0x8`;
//! * ADDR must point to a flash page boundary, SIZE must be a multiple of the page size, "the maximum region is limited to half the
//!   flash size", writing 0 to SIZE has no effect; protection is enforced only when ADDR is valid and SIZE and PERM are non-zero;
//! * PERM.WRITE "configure write and erase permissions" (1 = disabled), PERM.READ (1 = disabled: also no instruction fetch);
//! * "The ADDR, SIZE, and PERM registers can only be written once", cleared only by a reset; enforcement starts two CPU cycles after
//!   the write; a violation is blocked and raises a BusFault (a debugger write is ignored).
//!
//! The bit positions (WRITE = bit 1, READ = bit 2) are not printed in the page text: they are taken from the register description of
//! `nrf-pac` 0.4.0 (generated from Nordic's SVD, `acl::regs::Perm`). TODO(verify-on-hardware): read PERM back after the write and
//! try a page erase / word write into the bootloader from the application (expected: BusFault, flash unchanged).
//!
//! **What is protected and what is not (policy, [`plan_bootloader`]):**
//! * the bootloader code `[BOOTLOADER_START, +BOOTLOADER_SIZE)`: WRITE disabled (no write, no erase), READ allowed. Read protection
//!   is refused ([`AclError::ReadProtectsBootloader`]): the ACL is configured while the bootloader still executes from that region
//!   (the jump itself), and the code is not secret.
//! * the embassy-boot STATE page is NOT protected and cannot be ([`AclError::AppWritable`]): the application confirms a trial image
//!   through it (`mark_booted`) and arms an update (`mark_updated`). A compromised application that rewrites it can only request a swap
//!   that the bootloader verifies again (signature, hardware id, rollback) or a revert to the previous signed image.
//! * the rollback counter lives in `UICR.CUSTOMER` (`counter.rs`), outside the code flash: the ACL page does not mention the UICR and
//!   ADDR must be a code flash page, so the ACL cannot protect it. The application can only clear bits of an erased word (which makes
//!   the counter `Corrupt` = updates refused, fail closed) or erase the whole UICR with NVMC `ERASEUICR` (which would reset the minimum
//!   version and also REGOUT0 / PSELRESET). TODO(verify-on-hardware): whether `ERASEUICR` / `ERASEALL` are blocked while an ACL region
//!   is active is not stated on the page. Residual risk accepted for the bench project: only a signed application runs there.
//! * ACTIVE, DFU and STORAGE are written by the application and are never part of a region.
#![allow(clippy::len_without_is_empty)]

/// Base address of the ACL instance.
pub const ACL_BASE: u32 = 0x4001_E000;
/// Number of ACL regions.
pub const ACL_REGIONS: usize = 8;
/// `PERM.WRITE` = disabled: no write, no erase.
pub const PERM_WRITE_DISABLE: u32 = 1 << 1;
/// `PERM.READ` = disabled: no read, no instruction fetch.
pub const PERM_READ_DISABLE: u32 = 1 << 2;

/// `ACL[n].ADDR`.
pub const fn reg_addr(n: usize) -> u32 {
    ACL_BASE + 0x800 + 0x10 * n as u32
}
/// `ACL[n].SIZE`.
pub const fn reg_size(n: usize) -> u32 {
    reg_addr(n) + 0x4
}
/// `ACL[n].PERM`.
pub const fn reg_perm(n: usize) -> u32 {
    reg_addr(n) + 0x8
}

/// A byte range of the code flash.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Span {
    pub start: u32,
    pub size: u32,
}

impl Span {
    pub const fn new(start: u32, size: u32) -> Self {
        Self { start, size }
    }
    /// One past the last byte; `None` on overflow.
    pub const fn end(&self) -> Option<u32> {
        self.start.checked_add(self.size)
    }
    /// Both non-empty and sharing at least one byte (computed in u64, no overflow).
    pub const fn overlaps(&self, o: Span) -> bool {
        if self.size == 0 || o.size == 0 {
            return false;
        }
        let (a0, a1) = (self.start as u64, self.start as u64 + self.size as u64);
        let (b0, b1) = (o.start as u64, o.start as u64 + o.size as u64);
        a0 < b1 && b0 < a1
    }
    const fn aligned(&self, page: u32) -> bool {
        self.start % page == 0 && self.size % page == 0
    }
}

/// The flash layout (`firmware-rs/layout/layout.rs`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct FlashMap {
    pub page: u32,
    pub flash_size: u32,
    pub bootloader: Span,
    pub state: Span,
    pub active: Span,
    pub dfu: Span,
    pub storage: Span,
}

/// The areas the application writes.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Area {
    State,
    Active,
    Dfu,
    Storage,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AclError {
    /// The map itself is broken (zero page, unaligned or overlapping areas, beyond the flash).
    InvalidMap,
    /// Start or size not on a page boundary.
    Unaligned,
    Empty,
    /// Neither write nor read protection asked for (the hardware would ignore the region).
    NoProtection,
    OutsideFlash,
    /// Larger than half the flash (PS: maximum region size).
    TooLarge,
    /// The region covers an area the application must write.
    AppWritable(Area),
    /// Read protection on the code that is still running.
    ReadProtectsBootloader,
    RegionsOverlap,
    TooManyRegions,
    /// Some page of the bootloader code stays writable.
    BootloaderNotCovered,
}

/// A region the caller asks to protect.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Protect {
    pub span: Span,
    /// Disable write and erase.
    pub no_write: bool,
    /// Disable read and execute.
    pub no_read: bool,
}

impl Protect {
    /// Write and erase protected, readable.
    pub const fn write(span: Span) -> Self {
        Self { span, no_write: true, no_read: false }
    }
}

/// One configured region: the three register values.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct AclEntry {
    pub region: u8,
    pub addr: u32,
    pub size: u32,
    pub perm: u32,
}

/// The register values to write, at most [`ACL_REGIONS`] regions from region 0 upwards.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct AclPlan {
    entries: [AclEntry; ACL_REGIONS],
    n: usize,
}

/// A register that read back differently from what was written.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Mismatch {
    pub reg: u32,
    pub expected: u32,
    pub got: u32,
}

impl AclPlan {
    pub fn entries(&self) -> &[AclEntry] {
        &self.entries[..self.n]
    }

    /// `(register address, value)` in write order: ADDR, SIZE, PERM per region (PERM last: the region is complete before it is armed).
    pub fn writes(&self) -> impl Iterator<Item = (u32, u32)> + '_ {
        self.entries().iter().flat_map(|e| {
            let n = e.region as usize;
            [(reg_addr(n), e.addr), (reg_size(n), e.size), (reg_perm(n), e.perm)]
        })
    }

    /// Compare every register with `read(addr)`.
    pub fn verify(&self, mut read: impl FnMut(u32) -> u32) -> Result<(), Mismatch> {
        for (reg, expected) in self.writes() {
            let got = read(reg);
            if got != expected {
                return Err(Mismatch { reg, expected, got });
            }
        }
        Ok(())
    }
}

/// Every area page aligned, inside the flash, pairwise disjoint.
pub fn validate_map(m: &FlashMap) -> Result<(), AclError> {
    if m.page == 0 || m.flash_size == 0 || m.flash_size % m.page != 0 {
        return Err(AclError::InvalidMap);
    }
    let areas = [m.bootloader, m.state, m.active, m.dfu, m.storage];
    for (i, a) in areas.iter().enumerate() {
        if a.size == 0 || !a.aligned(m.page) {
            return Err(AclError::InvalidMap);
        }
        match a.end() {
            Some(e) if e <= m.flash_size => {}
            _ => return Err(AclError::InvalidMap),
        }
        for b in &areas[i + 1..] {
            if a.overlaps(*b) {
                return Err(AclError::InvalidMap);
            }
        }
    }
    Ok(())
}

/// Plan the given regions. Every rule of the module documentation is checked; nothing is planned unless all pass.
pub fn plan_with(m: &FlashMap, regions: &[Protect]) -> Result<AclPlan, AclError> {
    validate_map(m)?;
    if regions.len() > ACL_REGIONS {
        return Err(AclError::TooManyRegions);
    }
    let empty = AclEntry { region: 0, addr: 0, size: 0, perm: 0 };
    let mut plan = AclPlan { entries: [empty; ACL_REGIONS], n: 0 };
    for (i, p) in regions.iter().enumerate() {
        let s = p.span;
        if s.size == 0 {
            return Err(AclError::Empty);
        }
        if !s.aligned(m.page) {
            return Err(AclError::Unaligned);
        }
        match s.end() {
            Some(e) if e <= m.flash_size => {}
            _ => return Err(AclError::OutsideFlash),
        }
        if s.size > m.flash_size / 2 {
            return Err(AclError::TooLarge);
        }
        if !p.no_write && !p.no_read {
            return Err(AclError::NoProtection);
        }
        for (area, a) in [(Area::State, m.state), (Area::Active, m.active), (Area::Dfu, m.dfu), (Area::Storage, m.storage)] {
            if s.overlaps(a) {
                return Err(AclError::AppWritable(area));
            }
        }
        if p.no_read && s.overlaps(m.bootloader) {
            return Err(AclError::ReadProtectsBootloader);
        }
        for q in &regions[..i] {
            if s.overlaps(q.span) {
                return Err(AclError::RegionsOverlap);
            }
        }
        let perm = if p.no_write { PERM_WRITE_DISABLE } else { 0 } | if p.no_read { PERM_READ_DISABLE } else { 0 };
        plan.entries[i] = AclEntry { region: i as u8, addr: s.start, size: s.size, perm };
        plan.n = i + 1;
    }
    // every page of the bootloader must be in a write protected region
    let mut addr = m.bootloader.start;
    let end = m.bootloader.start + m.bootloader.size; // validated above
    while addr < end {
        let page = Span::new(addr, m.page);
        if !regions.iter().any(|p| p.no_write && p.span.overlaps(page)) {
            return Err(AclError::BootloaderNotCovered);
        }
        addr += m.page;
    }
    Ok(plan)
}

/// The project policy: the bootloader code, write and erase protected, readable (see the module documentation).
pub fn plan_bootloader(m: &FlashMap) -> Result<AclPlan, AclError> {
    plan_with(m, &[Protect::write(m.bootloader)])
}
