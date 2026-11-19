//! Diagnostics engine (docs/06-diagnostics.md 1.6, 2.2, 2.6, 2.7, 5.2).
//!
//! * [`DiagState::raise`] / [`DiagState::raise_caused_by`]: every anomaly becomes a 32 byte
//!   [`DiagRecord`] in a ring (ids strictly increasing, a gap tells the app that records were
//!   overwritten). Repeats of the same code identity are coalesced (`count`), escalations and the
//!   first occurrence after a clear always create a new record.
//! * An **active set** (W/F/L records whose condition is present) and a **latched set** (L records,
//!   cleared only by a verification test, never by a plain acknowledge).
//! * **Cause chain**: `cause_rec` points at the record that caused this one (depth at most 4); the
//!   headline of a chain is its root.
//! * The legacy [`Faults`] bits are a **derived projection** of the active F/L set
//!   ([`DiagState::legacy_faults`]): every F or L code projects to at least one bit (default
//!   INTERNAL), I and W never set a bit. An old app therefore never sees a stopped pod without a
//!   fault.
//! * An unknown code is never dropped: it is raised as `7-7C-003 UNKNOWN_CODE_RAISED` (a fault).
//!
//! No alloc, no unsafe. Persistence (flash log, latched set) is the platform's job: it reads
//! [`DiagState::records_from`], [`DiagState::latched`] and restores with [`DiagState::restore`].

use crate::faults::Faults;
use heapless::{Deque, Vec};
pub use openpatch_diag::{
    codes, flags, health, legacy_bit, Action, CodeInfo, DiagCode, DiagRecord, DiagSummary, Fru, Severity, CATALOGUE,
    LEGACY_DEFAULT_BIT, SCHEMA_VERSION,
};

/// Records kept in RAM.
pub const RING: usize = 64;
/// Distinct active code identities (W/F/L).
pub const ACTIVE_MAX: usize = 32;
/// Size of the latched set (`DIAG_LATCHED` carries up to 16 codes).
pub const LATCHED_MAX: usize = 16;
/// Same code identity within this many seconds is coalesced (information records).
pub const COALESCE_S: u32 = 10;
/// Maximum depth of a cause chain.
pub const CHAIN_MAX: usize = 4;
/// Pending notifications for the app (lossy by design, the reliable path is pull).
pub const EVENTS_MAX: usize = 16;

/// One anomaly to record.
#[derive(Clone, Copy, Debug)]
pub struct Raise {
    pub code: DiagCode,
    pub ctx_a: i32,
    pub ctx_b: i32,
    pub ctx_c: u32,
    /// Low 16 bits of the causing record id, 0 = this is a root.
    pub cause: u16,
    /// Overrides the catalogue severity (escalation); never below the catalogue severity is
    /// *required* but allowed (a caller may deliberately downgrade only I/W records).
    pub severity: Option<Severity>,
    /// Overrides the catalogue primary FRU (isolation evidence).
    pub fru: Option<Fru>,
    /// Raised during POST.
    pub post: bool,
}

impl Raise {
    pub const fn new(code: DiagCode) -> Raise {
        Raise { code, ctx_a: 0, ctx_b: 0, ctx_c: 0, cause: 0, severity: None, fru: None, post: false }
    }
    pub const fn a(mut self, v: i32) -> Raise {
        self.ctx_a = v;
        self
    }
    pub const fn b(mut self, v: i32) -> Raise {
        self.ctx_b = v;
        self
    }
    pub const fn c(mut self, v: u32) -> Raise {
        self.ctx_c = v;
        self
    }
    pub const fn caused_by(mut self, rec_id: u32) -> Raise {
        self.cause = rec_id as u16;
        self
    }
    pub const fn severity(mut self, s: Severity) -> Raise {
        self.severity = Some(s);
        self
    }
    pub const fn fru(mut self, f: Fru) -> Raise {
        self.fru = Some(f);
        self
    }
    pub const fn inst(mut self, inst: u8) -> Raise {
        self.code = self.code.with_inst(inst);
        self
    }
    pub const fn during_post(mut self) -> Raise {
        self.post = true;
        self
    }
}

/// An active (condition present) W, F or L record.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Active {
    /// Latest raised code (with instance).
    pub code: DiagCode,
    pub severity: Severity,
    pub action: u8,
    pub fru: u8,
    pub fru2: u8,
    pub rec_id: u32,
}

/// Member of the persistent latched set (`diag/latched`, 5.3).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Latched {
    pub code: DiagCode,
    pub rec_id: u32,
}

/// Pending app notification (protocol notify kinds 5 and 6).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DiagNote {
    /// A new record (or an escalation): kind 5 `DIAG_RAISED` with the complete record.
    Raised(DiagRecord),
    /// A condition went away: kind 6 `DIAG_CLEARED`.
    Cleared(DiagCode),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ClearError {
    /// No active record with this code.
    NotFound,
    /// Latched and the verification test has not passed, or the cause persists.
    NotClearable,
}

#[derive(Clone, Debug)]
pub struct DiagState {
    ring: [DiagRecord; RING],
    last_s: [u32; RING],
    /// Id of the next record (never 0).
    next_id: u32,
    len: usize,
    active: Vec<Active, ACTIVE_MAX>,
    latched: Vec<Latched, LATCHED_MAX>,
    notes: Deque<DiagNote, EVENTS_MAX>,
    time_s: u32,
    post_state: u8,
    /// Bit n = a passing proof exists for FRU id n (otherwise the FRU is UNKNOWN, never OK).
    proven: u32,
    active_dropped: u32,
}

impl Default for DiagState {
    fn default() -> Self {
        Self::new()
    }
}

/// `7-7C-003 UNKNOWN_CODE_RAISED` as a literal: the safety path must not depend on a lookup (a
/// test checks it equals the catalogue row).
const fn unknown_info() -> CodeInfo {
    CodeInfo {
        code: codes::UNKNOWN_CODE_RAISED,
        name: "UNKNOWN_CODE_RAISED",
        severity: Severity::Fault,
        action: Action::ReportBug,
        fru: Fru::Fw,
        fru2: Fru::None,
        legacy_bit: LEGACY_DEFAULT_BIT,
        hazards: 1 << 13,
    }
}

fn next_nonzero(id: u32) -> u32 {
    match id.wrapping_add(1) {
        0 => 1,
        n => n,
    }
}

impl DiagState {
    pub fn new() -> DiagState {
        DiagState {
            ring: [DiagRecord::default(); RING],
            last_s: [0; RING],
            next_id: 1,
            len: 0,
            active: Vec::new(),
            latched: Vec::new(),
            notes: Deque::new(),
            time_s: 0,
            post_state: 0,
            proven: 0,
            active_dropped: 0,
        }
    }

    /// Boot: continue the persistent record ids (the platform stores a ceiling like the event ids)
    /// and reload the latched set BEFORE the interlock is ever armed. Every restored latched code
    /// is active again, so a pod with a non-empty latched set boots with a derived fault (SUSPENDED).
    pub fn restore(next_id: u32, latched: &[Latched]) -> DiagState {
        let mut s = DiagState::new();
        s.next_id = next_id.max(1);
        for l in latched.iter().take(LATCHED_MAX) {
            let info = l.code.info();
            let a = Active {
                code: l.code,
                severity: Severity::Latched,
                action: info.map_or(Action::ReportBug as u8, |i| i.action as u8),
                fru: info.map_or(Fru::Fw as u8, |i| i.fru as u8),
                fru2: info.map_or(0, |i| i.fru2 as u8),
                rec_id: l.rec_id,
            };
            let _ = s.active.push(a);
            let _ = s.latched.push(*l);
        }
        s
    }

    pub fn set_time_s(&mut self, t: u32) {
        self.time_s = t;
    }
    pub fn time_s(&self) -> u32 {
        self.time_s
    }

    // ---- accessors -------------------------------------------------------------------------
    pub fn next_id(&self) -> u32 {
        self.next_id
    }
    /// Oldest record id still in the ring (= `next_id` when empty).
    pub fn oldest_id(&self) -> u32 {
        self.next_id.wrapping_sub(self.len as u32)
    }
    pub fn len(&self) -> usize {
        self.len
    }
    pub fn is_empty(&self) -> bool {
        self.len == 0
    }
    pub fn active(&self) -> &[Active] {
        &self.active
    }
    pub fn latched(&self) -> &[Latched] {
        &self.latched
    }
    /// Active entries that did not fit (never silently: raised as a counter the platform can log).
    pub fn active_dropped(&self) -> u32 {
        self.active_dropped
    }
    pub fn set_post_state(&mut self, s: u8) {
        self.post_state = s;
    }
    pub fn post_state(&self) -> u8 {
        self.post_state
    }
    /// A passing proof exists for this FRU: it may be shown OK (if nothing is active). Without a
    /// proof an FRU is UNKNOWN, never OK.
    pub fn set_proven(&mut self, fru: Fru, proven: bool) {
        if proven {
            self.proven |= 1 << fru as u8;
        } else {
            self.proven &= !(1 << fru as u8);
        }
    }

    pub fn take_note(&mut self) -> Option<DiagNote> {
        self.notes.pop_front()
    }
    fn note(&mut self, n: DiagNote) {
        if self.notes.is_full() {
            let _ = self.notes.pop_front();
        }
        let _ = self.notes.push_back(n);
    }

    fn idx(id: u32) -> usize {
        (id as usize) % RING
    }
    fn in_ring(&self, id: u32) -> bool {
        self.len > 0 && id.wrapping_sub(self.oldest_id()) < self.len as u32
    }
    /// Record by id, `None` when never written or already overwritten.
    pub fn record(&self, id: u32) -> Option<DiagRecord> {
        self.in_ring(id).then(|| self.ring[Self::idx(id)])
    }
    /// Copies records with id >= `from` (oldest first) into `out`; returns how many.
    pub fn records_from(&self, from: u32, out: &mut [DiagRecord]) -> usize {
        if self.len == 0 {
            return 0;
        }
        let oldest = self.oldest_id();
        let start = if self.in_ring(from) {
            from
        } else if from == 0 || oldest.wrapping_sub(from) < (1 << 31) {
            oldest // asked for something already overwritten: start at the oldest, the id gap is visible
        } else {
            return 0; // newer than anything written
        };
        let mut n = 0;
        let mut id = start;
        while n < out.len() && self.in_ring(id) {
            out[n] = self.ring[Self::idx(id)];
            n += 1;
            id = id.wrapping_add(1);
        }
        n
    }

    /// Record whose low 16 bits of the id match, newest first.
    fn by_low16(&self, low: u16) -> Option<DiagRecord> {
        let mut id = self.next_id;
        for _ in 0..self.len {
            id = id.wrapping_sub(1);
            let r = &self.ring[Self::idx(id)];
            if r.rec_id as u16 == low {
                return Some(*r);
            }
        }
        None
    }

    /// Chain depth of the record with this low id (1 = a root, 0 = not in the log).
    fn depth_of(&self, low: u16) -> usize {
        let mut d = 0;
        let mut cur = low;
        while cur != 0 && d < CHAIN_MAX + 2 {
            match self.by_low16(cur) {
                Some(r) => {
                    d += 1;
                    cur = r.cause_rec;
                }
                None => break,
            }
        }
        d
    }

    /// Root of the chain starting at `rec` (at most [`CHAIN_MAX`] hops; a missing cause ends the walk).
    pub fn root_of(&self, rec: &DiagRecord) -> DiagRecord {
        let mut cur = *rec;
        for _ in 0..CHAIN_MAX {
            if cur.cause_rec == 0 {
                break;
            }
            match self.by_low16(cur.cause_rec) {
                Some(p) => cur = p,
                None => break,
            }
        }
        cur
    }

    // ---- raise -------------------------------------------------------------------------------
    /// Records an anomaly; returns the id of the record that holds it (an existing one when the
    /// raise was coalesced). Never panics, never drops: an unknown code becomes `7-7C-003`.
    pub fn raise(&mut self, r: Raise) -> u32 {
        let mut r = r;
        let info = match r.code.info() {
            Some(i) => *i,
            None => {
                let unknown = r.code;
                let i = unknown_info();
                r = Raise { code: codes::UNKNOWN_CODE_RAISED, ctx_a: unknown.0 as i32, ctx_b: r.ctx_a, ctx_c: r.ctx_c, cause: r.cause, severity: None, fru: None, post: r.post };
                i
            }
        };
        let sev = r.severity.unwrap_or(info.severity);
        let fru = r.fru.unwrap_or(info.fru);
        let ident = r.code.identity();
        let tracked = sev >= Severity::Warning;

        // a cause chain deeper than CHAIN_MAX is shortened: link to the cause's own cause
        let mut cause = r.cause;
        while cause != 0 && self.depth_of(cause) >= CHAIN_MAX {
            cause = self.by_low16(cause).map_or(0, |c| c.cause_rec);
        }

        let mut escalated = false;
        if tracked {
            if let Some(i) = self.active.iter().position(|a| a.code.identity() == ident) {
                let a = self.active[i];
                if sev > a.severity {
                    escalated = true;
                } else if self.in_ring(a.rec_id) {
                    return self.coalesce(a.rec_id, &r);
                }
            }
        } else if let Some(id) = self.recent_same(ident) {
            return self.coalesce(id, &r);
        }

        let id = self.push_record(&r, &info, sev, fru, cause, escalated);
        if tracked {
            let entry = Active { code: r.code, severity: sev, action: info.action as u8, fru: fru as u8, fru2: info.fru2 as u8, rec_id: id };
            match self.active.iter().position(|a| a.code.identity() == ident) {
                Some(i) => self.active[i] = entry,
                None => {
                    if self.active.push(entry).is_err() {
                        // full: the least severe, oldest entry makes room for a more severe one
                        // (the record itself is in the ring either way)
                        self.active_dropped += 1;
                        if let Some(w) = (0..self.active.len()).min_by_key(|&k| (self.active[k].severity, self.active[k].rec_id)) {
                            if self.active[w].severity < sev {
                                self.active[w] = entry;
                            }
                        }
                    }
                }
            }
        }
        if sev == Severity::Latched {
            let l = Latched { code: r.code, rec_id: id };
            match self.latched.iter().position(|x| x.code.identity() == ident) {
                Some(i) => self.latched[i] = l,
                None => {
                    // 16 entries are enough for every pod (the catalogue has 26 L codes, a pod never has that many at once)
                    let _ = self.latched.push(l);
                }
            }
        }
        if tracked {
            // I records are log only: no alert, no notification (the app pulls them)
            let rec = self.ring[Self::idx(id)];
            self.note(DiagNote::Raised(rec));
        }
        id
    }

    pub fn raise_caused_by(&mut self, r: Raise, cause_rec: u32) -> u32 {
        self.raise(r.caused_by(cause_rec))
    }

    fn recent_same(&self, ident: DiagCode) -> Option<u32> {
        let mut id = self.next_id;
        for _ in 0..self.len {
            id = id.wrapping_sub(1);
            let r = &self.ring[Self::idx(id)];
            if r.code.identity() == ident && r.flags & flags::CLEARED == 0 {
                let i = Self::idx(id);
                return (self.time_s.saturating_sub(self.last_s[i]) <= COALESCE_S).then_some(id);
            }
        }
        None
    }

    fn coalesce(&mut self, id: u32, r: &Raise) -> u32 {
        let i = Self::idx(id);
        let rec = &mut self.ring[i];
        rec.count = rec.count.saturating_add(1);
        rec.code = r.code; // keeps the latest instance
        rec.ctx_a = r.ctx_a;
        rec.ctx_b = r.ctx_b;
        rec.ctx_c = r.ctx_c;
        self.last_s[i] = self.time_s;
        id
    }

    fn push_record(&mut self, r: &Raise, info: &CodeInfo, sev: Severity, fru: Fru, cause: u16, escalated: bool) -> u32 {
        let ident = r.code.identity();
        let first = !(0..self.len).any(|k| self.ring[Self::idx(self.next_id.wrapping_sub(1 + k as u32))].code.identity() == ident);
        let mut f = 0u8;
        if sev >= Severity::Warning {
            f |= flags::ACTIVE;
        }
        if sev == Severity::Latched {
            f |= flags::LATCHED;
        }
        if escalated {
            f |= flags::ESCALATED;
        }
        if first {
            f |= flags::FIRST_SINCE_BOOT;
        }
        if r.post {
            f |= flags::POST;
        }
        if cause == 0 {
            f |= flags::ROOT;
        }
        let id = self.next_id;
        self.next_id = next_nonzero(self.next_id);
        let rec = DiagRecord {
            rec_id: id,
            code: r.code,
            severity: sev as u8,
            action: info.action as u8,
            fru: fru as u8,
            fru2: info.fru2 as u8,
            t_s: self.time_s,
            ctx_a: r.ctx_a,
            ctx_b: r.ctx_b,
            ctx_c: r.ctx_c,
            count: 1,
            flags: f,
            cause_rec: cause,
        };
        let i = Self::idx(id);
        self.ring[i] = rec;
        self.last_s[i] = self.time_s;
        if self.len < RING {
            self.len += 1;
        }
        id
    }

    // ---- clear ---------------------------------------------------------------------------------
    fn deactivate(&mut self, pos: usize) {
        let a = self.active.remove(pos);
        if a.severity == Severity::Latched {
            self.latched.retain(|l| l.code.identity() != a.code.identity());
        }
        if self.in_ring(a.rec_id) {
            let i = Self::idx(a.rec_id);
            self.ring[i].flags &= !flags::ACTIVE;
        }
        // clear record: the app learns about the clearance through the reliable pull path too
        let id = self.next_id;
        self.next_id = next_nonzero(self.next_id);
        let rec = DiagRecord {
            rec_id: id,
            code: a.code,
            severity: a.severity as u8,
            action: a.action,
            fru: a.fru,
            fru2: a.fru2,
            t_s: self.time_s,
            ctx_a: 0,
            ctx_b: 0,
            ctx_c: 0,
            count: 1,
            flags: flags::CLEARED | flags::ROOT,
            cause_rec: 0,
        };
        let i = Self::idx(id);
        self.ring[i] = rec;
        self.last_s[i] = self.time_s;
        if self.len < RING {
            self.len += 1;
        }
        self.note(DiagNote::Cleared(a.code));
    }

    /// The condition of a W or F record is gone (auto clear). A latched record is NOT cleared by
    /// this: it needs [`DiagState::clear_diag`] with a passed verification. Returns `true` when an
    /// active record was cleared.
    pub fn clear(&mut self, code: DiagCode) -> bool {
        match self.active.iter().position(|a| a.code.identity() == code.identity()) {
            Some(p) if self.active[p].severity != Severity::Latched => {
                self.deactivate(p);
                true
            }
            _ => false,
        }
    }

    /// `ClearDiag` (5.4). `code == NONE` clears every clearable W/F record (latched ones stay,
    /// not an error). A specific code: `NotFound` when not active; `NotClearable` when latched and
    /// `verified` is false (its verification test has not passed) or when `blocked` says the cause
    /// persists. Returns the number of cleared records.
    pub fn clear_diag(&mut self, code: DiagCode, verified: bool, mut blocked: impl FnMut(&Active) -> bool) -> Result<usize, ClearError> {
        if code.is_none() {
            let mut n = 0;
            let mut i = 0;
            while i < self.active.len() {
                let a = self.active[i];
                if a.severity == Severity::Latched || blocked(&a) {
                    i += 1;
                } else {
                    self.deactivate(i);
                    n += 1;
                    i = 0; // deactivate reorders
                }
            }
            return Ok(n);
        }
        let Some(p) = self.active.iter().position(|a| a.code.identity() == code.identity()) else {
            return Err(ClearError::NotFound);
        };
        let a = self.active[p];
        if (a.severity == Severity::Latched && !verified) || blocked(&a) {
            return Err(ClearError::NotClearable);
        }
        self.deactivate(p);
        Ok(1)
    }

    /// Legacy `Acknowledge`: clears active FAULT records whose legacy bit is in `mask` (latched
    /// records stay). Returns the bits cleared.
    pub fn clear_legacy(&mut self, mask: Faults) -> Faults {
        let before = self.legacy_faults();
        let mut i = 0;
        while i < self.active.len() {
            let a = self.active[i];
            let hit = a.severity == Severity::Fault && legacy_bit(a.code, a.severity).is_some_and(|b| mask.bits() & (1 << b) != 0);
            if hit {
                self.deactivate(i);
                i = 0;
            } else {
                i += 1;
            }
        }
        before & !self.legacy_faults()
    }

    /// Drops all active state without records (a probe copy of the supervisor).
    pub(crate) fn clear_all_silent(&mut self) {
        self.active.clear();
        self.latched.clear();
        self.notes.clear();
    }

    // ---- projections -----------------------------------------------------------------------
    /// The legacy fault bits: OR of the legacy bit of every active F or L record (2.7).
    pub fn legacy_faults(&self) -> Faults {
        let mut f = 0u16;
        for a in self.active.iter() {
            if let Some(b) = legacy_bit(a.code, a.severity) {
                f |= 1 << b;
            }
        }
        Faults(f)
    }

    /// `true` when an active F or L record projects to this legacy bit.
    pub fn has_active_bit(&self, bit: u8) -> bool {
        self.active.iter().any(|a| legacy_bit(a.code, a.severity) == Some(bit))
    }

    /// Headline of the diagnostic state (`DIAG_SUMMARY`).
    pub fn summary(&self) -> DiagSummary {
        let mut s = DiagSummary {
            n_latched: self.latched.len() as u8,
            n_active: self.active.len() as u8,
            post_state: self.post_state,
            next_rec_id_lo: self.next_id as u16,
            schema: SCHEMA_VERSION,
            ..Default::default()
        };
        // most severe active record, newest wins a tie; the headline is its root
        if let Some(top) = self.active.iter().max_by_key(|a| (a.severity, a.rec_id)) {
            let top_rec = self.record(top.rec_id);
            let root = top_rec.map(|r| self.root_of(&r));
            match root {
                Some(r) => {
                    s.top_code = r.code.0;
                    s.top_sev = r.severity;
                    s.top_action = r.action;
                    s.top_fru = r.fru;
                }
                None => {
                    s.top_code = top.code.0;
                    s.top_sev = top.severity as u8;
                    s.top_action = top.action;
                    s.top_fru = top.fru;
                }
            }
        }
        s
    }

    /// `FRU_HEALTH`: 2 bits per FRU id. An FRU is OK only with a passing proof and no active
    /// record; failed for an active F/L record, degraded for a W; otherwise UNKNOWN.
    pub fn fru_health(&self) -> u64 {
        let mut packed = 0u64;
        for id in 0..Fru::COUNT {
            if self.proven & (1 << id) != 0 {
                packed = health::set(packed, id, health::OK);
            }
        }
        for a in self.active.iter() {
            let fru = match self.record(a.rec_id) {
                Some(r) => self.root_of(&r).fru,
                None => a.fru,
            };
            if fru == 0 || fru >= Fru::COUNT {
                continue;
            }
            let st = if a.severity >= Severity::Fault { health::FAILED } else { health::DEGRADED };
            if st > health::get(packed, fru) {
                packed = health::set(packed, fru, st);
            }
        }
        packed
    }
}
