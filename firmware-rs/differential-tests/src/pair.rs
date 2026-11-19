//! A C pump and a Rust pump side by side, driven by identical operations, compared after every
//! single operation (responses, faults, step totals, motor-enable parity, buzzer, event log,
//! reservoir, wear, engine accumulators).
//!
//! Documented intentional differences (see docs/differential-testing.md) are normalised here:
//!  * status: DRIVE_CAL (id / steps-per-rev / ratio differ between C presets and Rust test
//!    calibrations; only the uU floor is compared), FW_VERSION, Rust-only tags 0x21..0x23,
//!    flags bits 11/12;
//!  * command 0x0F and error codes 26/27 never occur in shared streams.

use crate::ffi::*;
use crate::rmock::MockHal;
use openpatch_core::limits::*;
use openpatch_core::{DriveCal, Pump, PumpConfig};
use openpatch_proto::*;
use std::collections::{BTreeMap, BTreeSet};

pub const TEST_26100_C_ID: u32 = 1;
pub const TEST_8156_C_ID: u32 = 2;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CalSel {
    T26100,
    T8156,
    None,
}

impl CalSel {
    pub fn c_id(self) -> u32 {
        match self {
            CalSel::T26100 => TEST_26100_C_ID,
            CalSel::T8156 => TEST_8156_C_ID,
            CalSel::None => 0,
        }
    }
    pub fn rust_cal(self) -> Option<DriveCal> {
        match self {
            CalSel::T26100 => DriveCal::preset(0x7F01).ok(),
            CalSel::T8156 => DriveCal::preset(0x7F02).ok(),
            CalSel::None => None,
        }
    }
    pub fn uu(self) -> u32 {
        match self {
            CalSel::T26100 => 26_100,
            CalSel::T8156 => 8_156,
            CalSel::None => 0,
        }
    }
}

#[derive(Clone, Copy, Debug)]
pub struct Setup {
    pub cal: CalSel,
    pub capacity: u32,
    pub next_id: u32,
}

#[derive(Clone, Debug)]
pub enum Op {
    /// A frame fed to both pumps.
    Frame(Vec<u8>),
    /// Advance the mock clock by `dt` ms, then call `tick()` on both.
    Tick(u64),
    /// Advance the clock without ticking.
    Advance(u64),
    Dock(bool),
    Charger(bool),
    Battery(u16),
    DeliveredPct(u32),
    StepsLimit(i32),
    NewSession,
    RestorePod { pair: u32, role: u8, active: bool, act_id: u32, wear_ms: u64 },
}

/// Statistics of a run.
#[derive(Default, Debug, Clone)]
pub struct Stats {
    pub ops: u64,
    pub frames: u64,
    pub dropped_frames: BTreeMap<u8, u64>,
    /// (command type, result code) pairs of answered frames.
    pub kinds: BTreeSet<(u8, u8)>,
    pub fault_bits_seen: u16,
    pub fault_bit_counts: [u64; 8],
    pub event_types_seen: BTreeSet<i64>,
    pub total_steps_c: u64,
    /// Sum over all generated runs of the steps executed by the C mock motor.
    pub steps_all: u64,
    /// Runs ended early at a Rust-only per-revolution ENCODER_DEVIATION trip (documented
    /// difference (4); everything before the trip was compared strictly).
    pub documented_rev_stops: u64,
}

pub struct Pair {
    pub c: CPump,
    pub r: Pump<MockHal>,
    pub rh: MockHal,
    rs: Session<NoCrypto>,
    now: u64,
    prev_next_id: u32,
    prev_faults: u16,
    prev_total_steps: u64,
    /// Steps were executed while the actuator-health knob was degraded (pct != 100 or a step
    /// limit) since the supervisors were last rebaselined.
    tainted: bool,
    /// Set when the Rust-only per-revolution check fired (see `Stats::documented_rev_stops`).
    pub stopped: bool,
}

const SNAP_NAMES: &[(usize, &str)] = &[
    (0, "faults"),
    (1, "de.suspended"),
    (2, "de.temp_active"),
    (3, "de.temp_rate"),
    (4, "de.temp_remaining_min"),
    (5, "de.bolus_active"),
    (6, "de.bolus_remaining_mu"),
    (7, "de.ms_of_day"),
    (8, "de.ms_since_comm"),
    (9, "de.acc"),
    (10, "de.scheduled_scaled"),
    (11, "de.requested_steps"),
    (12, "de.delivered_steps"),
    (13, "de.dropped_steps"),
    (14, "de.pending_steps"),
    (15, "res.fill"),
    (16, "res.consumed"),
    (17, "res.filled"),
    (18, "res.remaining"),
    (19, "pod.pair_id"),
    (20, "pod.role"),
    (21, "pod.active"),
    (22, "pod.activation_id"),
    (23, "pod.wear_ms"),
    (24, "pod.wear_warned"),
    (25, "pod.docked"),
    (26, "pod.pending_temp"),
    (27, "pod.pending_temp_rate"),
    (28, "pod.pending_temp_min"),
    (29, "pod.act_base_steps"),
    (30, "pod.last_release"),
    (31, "sv.docked"),
    (32, "sv.active"),
    (33, "sv.wear_expired"),
    (34, "sv.battery_low"),
    (35, "sv.commanded_counts"),
    (36, "sv.last_angle"),
    (37, "sv.enc_base"),
    (38, "tick_overruns"),
    (39, "log.next_id"),
    (40, "log.oldest_id"),
    (41, "de.has_schedule"),
    (42, "cal_valid"),
    (46, "sv.calibrated"),
    (47, "de.current_rate"),
    (48, "sv.max_steps_per_min"),
    (49, "sv.max_bolus"),
    (50, "de.schedule_count"),
    (100, "status.flags"),
    (101, "status.faults"),
    (102, "status.reservoir_mu"),
    (103, "status.battery_mv"),
    (104, "status.bolus_remaining_mu"),
    (105, "status.temp_rate"),
    (106, "status.temp_remaining_min"),
    (107, "status.current_rate"),
    (108, "status.delivered_mu"),
    (109, "status.scheduled_mu"),
    (110, "status.next_event_id"),
    (111, "status.cal_uu_per_step"),
    (112, "status.pair_id"),
    (113, "status.wear_s"),
    (114, "status.role"),
    (115, "status.delivery_state"),
];

pub fn rust_snapshot(p: &mut Pump<MockHal>) -> [u64; SNAP_LEN] {
    let mut o = [0u64; SNAP_LEN];
    {
        let de = p.engine();
        o[1] = de.is_suspended() as u64;
        o[2] = de.temp_active() as u64;
        o[3] = de.temp_rate().0 as u64;
        o[4] = de.temp_remaining().0 as u64;
        o[5] = de.bolus_active() as u64;
        o[6] = de.bolus_remaining().0 as u64;
        o[7] = de.ms_of_day() as u64;
        o[8] = de.ms_since_comm() as u64;
        o[9] = de.accumulator() as u64;
        o[10] = de.scheduled_scaled() as u64;
        o[11] = de.requested_steps().0 as u64;
        o[12] = de.delivered_steps().0 as u64;
        o[13] = de.dropped_steps().0 as u64;
        o[14] = de.pending_steps().0 as u64;
        o[41] = de.has_schedule() as u64;
        o[47] = de.current_rate().0 as u64;
        o[50] = de.schedule().count() as u64;
        for (i, s) in de.schedule().segs.iter().enumerate() {
            o[64 + i] = ((s.start_slot as u64) << 32) | s.rate.0 as u64;
        }
    }
    {
        let r = p.reservoir();
        o[15] = r.fill_level().0 as u64;
        o[16] = r.consumed().0 as u64;
        o[17] = r.is_filled() as u64;
        o[18] = r.remaining().0 as u64;
    }
    {
        let pod = p.pod();
        o[19] = pod.pair_id as u64;
        o[20] = pod.role as u64;
        o[21] = pod.active as u64;
        o[22] = pod.activation_id as u64;
        o[23] = pod.wear.0;
        o[24] = pod.wear_warned as u64;
        o[25] = pod.docked as u64;
        o[26] = pod.pending_temp.is_some() as u64;
        o[27] = pod.pending_temp.map(|t| t.0 .0 as u64).unwrap_or(0);
        o[28] = pod.pending_temp.map(|t| t.1 .0 as u64).unwrap_or(0);
        o[29] = pod.act_base_steps.0 as u64;
        o[30] = pod.last_release.0 as u64;
    }
    {
        let sv = p.supervisor();
        o[0] = sv.faults().bits() as u64;
        o[31] = sv.is_docked() as u64;
        o[32] = sv.is_active() as u64;
        o[33] = sv.wear_expired() as u64;
        o[34] = sv.battery_low() as u64;
        o[35] = sv.commanded_counts().0 as u64;
        o[36] = sv.last_angle().0 as u64;
        o[37] = sv.encoder_baseline().0 as u64;
        o[46] = sv.is_calibrated() as u64;
        o[48] = sv.max_steps_per_min().0 as u64;
        o[49] = sv.max_bolus().0 as u64;
    }
    o[38] = p.tick_overruns() as u64;
    o[39] = p.log().next_id() as u64;
    o[40] = p.log().oldest_id() as u64;
    o[42] = p.calibration().is_some() as u64;
    let st = p.get_status();
    o[100] = (st.flags & !((1 << 11) | (1 << 12))) as u64;
    o[101] = st.faults as u64;
    o[102] = st.reservoir_mu as u64;
    o[103] = st.battery_mv as u64;
    o[104] = st.bolus_remaining_mu as u64;
    o[105] = st.temp_rate_mu_h as u64;
    o[106] = st.temp_remaining_min as u64;
    o[107] = st.current_rate_mu_h as u64;
    o[108] = st.delivered_mu as u64;
    o[109] = st.scheduled_mu as u64;
    o[110] = st.next_event_id as u64;
    o[111] = st.cal_uu_per_step as u64;
    o[112] = st.pair_id as u64;
    o[113] = st.wear_s as u64;
    o[114] = st.role as u64;
    o[115] = st.delivery_state as u64;
    o
}

// ---------------------------------------------------------------------------------------------
// response normalisation
// ---------------------------------------------------------------------------------------------

type Tlvs = Vec<(u8, Vec<u8>)>;

/// Validate the frame and return (type, flags, seq, normalised TLVs, has_status).
fn parse_response(bytes: &[u8], who: &str) -> Result<(u8, u8, u16, Tlvs, bool), String> {
    let f = decode_frame(bytes).map_err(|e| format!("{who}: response frame does not decode: {e:?}"))?;
    let mut tlvs: Tlvs = Vec::new();
    for item in openpatch_proto::tlv::TlvReader::new(f.payload) {
        let (t, v) = item.map_err(|_| format!("{who}: bad TLV in response"))?;
        tlvs.push((t, v.to_vec()));
    }
    let has_status = tlvs.iter().any(|t| t.0 == tag::STATE_FLAGS);
    // normalise the documented differences
    tlvs.retain(|t| !matches!(t.0, tag::DRAW_STATE | tag::DRAW_REQUESTED_MU | tag::DRAW_DONE_MU | tag::FW_VERSION));
    for t in tlvs.iter_mut() {
        match t.0 {
            tag::STATE_FLAGS if t.1.len() == 2 => {
                let v = u16::from_le_bytes([t.1[0], t.1[1]]) & !((1 << 11) | (1 << 12));
                t.1 = v.to_le_bytes().to_vec();
            }
            tag::DRIVE_CAL if t.1.len() == 10 => t.1 = t.1[2..6].to_vec(), // uU floor only
            _ => {}
        }
    }
    Ok((f.type_, f.flags, f.seq, tlvs, has_status))
}

/// Compare two answers to the same frame. Returns `(cmd type, result)` or the drop code.
pub fn compare_response(c: &Result<Vec<u8>, u8>, r: &Result<Vec<u8>, Error>) -> Result<Result<(u8, u8), u8>, String> {
    match (c, r) {
        (Err(ce), Err(re)) => {
            if *ce != re.code() {
                return Err(format!("both drop the frame but with different errors: C={ce} Rust={}", re.code()));
            }
            Ok(Err(*ce))
        }
        (Ok(_), Err(re)) => Err(format!("C answered, Rust dropped the frame ({re:?})")),
        (Err(ce), Ok(_)) => Err(format!("Rust answered, C dropped the frame (code {ce})")),
        (Ok(cb), Ok(rb)) => {
            let (ct, cf, cs, ctl, cst) = parse_response(cb, "C")?;
            let (rt, rf, rs, rtl, rst) = parse_response(rb, "Rust")?;
            if (ct, cf, cs) != (rt, rf, rs) {
                return Err(format!("response header differs: C=({ct:#x},{cf},{cs}) Rust=({rt:#x},{rf},{rs})"));
            }
            if cst != rst {
                return Err("only one side returned a status block".into());
            }
            if !cst && cb != rb {
                return Err(format!("status-less responses not byte-identical:\n C={cb:02x?}\n R={rb:02x?}"));
            }
            if ctl != rtl {
                return Err(format!("normalised response TLVs differ:\n C={ctl:02x?}\n R={rtl:02x?}"));
            }
            let result = ctl.iter().find(|t| t.0 == tag::RESULT).map(|t| t.1[0]).unwrap_or(255);
            Ok(Ok((ct & 0x7F, result)))
        }
    }
}

impl Pair {
    pub fn new(setup: &Setup) -> Self {
        let rh = MockHal::new();
        let cal = setup.cal.rust_cal();
        let mut r = Pump::new(rh.clone(), cal.as_ref(), openpatch_core::MilliUnits(setup.capacity), setup.next_id);
        r.set_config(PumpConfig::RELAXED);
        let c = CPump::new(setup.cal.c_id(), setup.capacity, setup.next_id);
        let prev_next_id = r.log().next_id();
        Pair {
            c,
            r,
            rh,
            rs: Session::new(NoCrypto, false, [0; 4], true),
            now: 0,
            prev_next_id,
            prev_faults: 0,
            prev_total_steps: 0,
            tainted: false,
            stopped: false,
        }
    }

    /// Check right after construction (boot events, boot faults).
    pub fn check_boot(&mut self, stats: &mut Stats) -> Result<(), String> {
        self.prev_next_id = self.r.log().oldest_id();
        self.check(stats)
    }

    /// Send a command frame to the C pump only (used by tests of documented differences).
    pub fn c_frame(&mut self, seq: u16, d: crate::desc::CmdDesc) {
        let f = crate::gen::build_frame(PROTO_VERSION, d.ty, 0, seq, &crate::gen::payload_of(&d.encodable()));
        let _ = self.c.handle_frame(&f);
    }

    pub fn now(&self) -> u64 {
        self.now
    }

    pub fn rust_status(&mut self) -> Status {
        self.r.get_status()
    }

    pub fn apply(&mut self, op: &Op, stats: &mut Stats) -> Result<(), String> {
        if self.stopped {
            return Ok(());
        }
        stats.ops += 1;
        match op {
            Op::Frame(bytes) => {
                stats.frames += 1;
                let mut out = [0u8; 256];
                let cr = self.c.handle_frame(bytes);
                let rr = self.r.handle_frame(&mut self.rs, bytes, &mut out).map(|n| out[..n].to_vec());
                let cmp = compare_response(&cr, &rr);
                if cmp.is_err() && self.documented_stop(stats) {
                    return Ok(());
                }
                match cmp? {
                    Ok(k) => {
                        stats.kinds.insert(k);
                    }
                    Err(code) => *stats.dropped_frames.entry(code).or_default() += 1,
                }
            }
            Op::Tick(dt) => {
                self.now += dt;
                self.c.set_time(self.now);
                self.rh.st().now_ms = self.now;
                self.c.tick();
                self.r.tick();
            }
            Op::Advance(dt) => {
                self.now += dt;
                self.c.set_time(self.now);
                self.rh.st().now_ms = self.now;
            }
            Op::Dock(v) => {
                self.c.set_docked(*v);
                self.rh.st().docked = *v;
            }
            Op::Charger(v) => {
                self.c.set_charger(*v);
                self.rh.st().charger = *v;
            }
            Op::Battery(mv) => {
                self.c.set_battery(*mv);
                self.rh.st().battery_mv = *mv;
            }
            Op::DeliveredPct(p) => {
                self.c.set_delivered_pct(*p);
                self.rh.st().delivered_pct = *p as i64;
            }
            Op::StepsLimit(l) => {
                self.c.set_steps_limit(*l);
                self.rh.st().steps_limit = *l as i64;
            }
            Op::NewSession => {
                self.c.new_session();
                self.rs = Session::new(NoCrypto, false, [0; 4], true);
            }
            Op::RestorePod { pair, role, active, act_id, wear_ms } => {
                self.c.restore_pod(*pair, *role, *active, *act_id, *wear_ms);
                self.r.restore_pod(*pair, *role, *active, *act_id, openpatch_core::Millis(*wear_ms));
            }
        }
        self.check(stats)
    }

    /// Documented difference (4): the Rust-only per-revolution angle check (4096 counts +-3 % per
    /// commanded revolution) can latch ENCODER_DEVIATION where C's 10 % / 1 U window check has not
    /// (yet) fired, after the actuator was degraded. Everything before is compared strictly; at
    /// that point the run stops (the two pumps are legitimately in different fault states).
    fn documented_stop(&mut self, stats: &mut Stats) -> bool {
        let cm = self.c.mock();
        {
            let m = self.rh.st();
            if cm[0] > self.prev_total_steps && (m.delivered_pct != 100 || m.steps_limit >= 0) {
                self.tainted = true;
            }
            self.prev_total_steps = cm[0];
        }
        let cf = self.c.snapshot();
        let rf = self.r.supervisor().faults().bits() as u64;
        let rcmd = self.r.supervisor().commanded_counts().0 as u64;
        if self.tainted && (rf & 0x2) != 0 && (cf[0] & 0x2) == 0 {
            self.stopped = true;
            stats.documented_rev_stops += 1;
            return true;
        }
        if cf[35] == 0 && rcmd == 0 {
            self.tainted = false; // both supervisors rebaselined, nothing commanded since
        }
        false
    }

    fn check(&mut self, stats: &mut Stats) -> Result<(), String> {
        if self.documented_stop(stats) {
            return Ok(());
        }
        let cm = self.c.mock();
        // ---- mock / motor / buzzer parity
        {
            let m = self.rh.st();
            let pairs: [(&str, u64, u64); 7] = [
                ("mock.total_steps", cm[0], m.total_steps as u64),
                ("mock.motor_enable_calls", cm[1], m.enable_calls as u64),
                ("mock.watchdog_kicks", cm[2], m.kicks as u64),
                ("mock.stepped_while_disabled", cm[4], m.stepped_while_disabled as u64),
                ("mock.motor_enabled", cm[5], m.enabled as u64),
                ("mock.angle_x100", cm[6], m.angle_x100 as u64),
                ("mock.now_ms", cm[7], m.now_ms),
            ];
            for (name, a, b) in pairs {
                if a != b {
                    return Err(format!("{name}: C={a} Rust={b}"));
                }
            }
            if m.stepped_while_disabled {
                return Err("SAFETY: the motor stepped while disabled (both sides)".into());
            }
            stats.total_steps_c = cm[0];
        }
        let bz = self.rh.buzzer_code();
        if cm[3] != bz {
            return Err(format!("buzzer: C={} Rust={bz}", cm[3]));
        }
        // ---- state snapshots
        let mut cs = self.c.snapshot();
        if cs[26] == 0 {
            // C keeps a stale pending-temp rate/minutes after use; Rust clears the Option.
            // Not observable (only meaningful while pending): normalised.
            cs[27] = 0;
            cs[28] = 0;
        }
        let rs = rust_snapshot(&mut self.r);
        for &(i, name) in SNAP_NAMES {
            if cs[i] != rs[i] {
                return Err(format!("{name}: C={} Rust={}", cs[i] as i64, rs[i] as i64));
            }
        }
        for i in 0..cs[50].min(24) as usize {
            if cs[64 + i] != rs[64 + i] {
                return Err(format!("schedule segment {i}: C={:#x} Rust={:#x}", cs[64 + i], rs[64 + i]));
            }
        }
        // ---- faults seen
        let f = cs[0] as u16;
        stats.fault_bits_seen |= f;
        let newly = f & !self.prev_faults;
        for b in 0..8 {
            if newly & (1 << b) != 0 {
                stats.fault_bit_counts[b] += 1;
            }
        }
        self.prev_faults = f;
        // ---- event log: every new event, field by field
        let next = self.r.log().next_id();
        let oldest = self.r.log().oldest_id();
        let mut id = self.prev_next_id.max(oldest);
        let mut guard = 0;
        while id != next && guard < 200 {
            let ce = self.c.log_event(id).ok_or_else(|| format!("log event {id} missing in C"))?;
            let mut buf = [openpatch_core::Event::default(); 1];
            if self.r.log().read(id, &mut buf) != 1 || buf[0].id != id {
                return Err(format!("log event {id} missing in Rust"));
            }
            let e = buf[0];
            let re = [e.id as i64, e.time_s as i64, e.kind as i64, e.a as i64, e.b as i64];
            if ce != re {
                return Err(format!("log event {id}: C={ce:?} Rust={re:?}"));
            }
            stats.event_types_seen.insert(ce[2]);
            id = id.wrapping_add(1);
            guard += 1;
        }
        self.prev_next_id = next;
        Ok(())
    }
}

/// Run `ops` from a fresh setup; the first error includes the op index.
pub fn run(setup: &Setup, ops: &[Op], stats: &mut Stats) -> Result<(), (usize, String)> {
    let mut p = Pair::new(setup);
    p.check_boot(stats).map_err(|e| (usize::MAX, e))?;
    for (i, op) in ops.iter().enumerate() {
        p.apply(op, stats).map_err(|e| (i, e))?;
        if p.stopped {
            break;
        }
    }
    Ok(())
}

/// Delta-debugging: shrink a diverging op list to a (locally) minimal reproducer.
pub fn minimize(setup: &Setup, ops: &[Op]) -> Vec<Op> {
    let fails = |o: &[Op]| run(setup, o, &mut Stats::default()).is_err();
    let mut cur: Vec<Op> = ops.to_vec();
    if !fails(&cur) {
        return cur;
    }
    // everything after the first failing op is irrelevant
    if let Err((i, _)) = run(setup, &cur, &mut Stats::default()) {
        if i != usize::MAX {
            cur.truncate(i + 1);
        }
    }
    let mut chunk = cur.len() / 2;
    while chunk >= 1 {
        let mut i = 0;
        while i < cur.len() {
            let end = (i + chunk).min(cur.len());
            let mut cand = cur.clone();
            cand.drain(i..end);
            if !cand.is_empty() && fails(&cand) {
                cur = cand;
            } else {
                i += chunk;
            }
        }
        chunk /= 2;
    }
    cur
}

pub fn describe(setup: &Setup, ops: &[Op]) -> String {
    let mut s = format!("setup: {setup:?}\n");
    for (i, o) in ops.iter().enumerate() {
        match o {
            Op::Frame(b) => {
                let ty = b.get(1).copied().unwrap_or(0);
                s += &format!("  {i:3}: Frame type={ty:#04x} {:02x?}\n", b);
            }
            other => s += &format!("  {i:3}: {other:?}\n"),
        }
    }
    s
}

pub const _SANITY: u32 = MAX_HOURLY.0;
