//! Reproducible, state-aware generation of pump operations (frames, ticks, environment changes).
//! The generator peeks at the Rust side to bias towards interesting states (paired -> filled ->
//! activated -> running); everything it emits is stored as explicit `Op`s so a run is replayable.

use crate::desc::CmdDesc;
use crate::pair::{Op, Pair, Setup};
use crate::rng::Rng;
use openpatch_proto::*;

/// Actuator-health knob values (percent of commanded steps the sensor sees). Restricted to
/// {100,100,100,50,0}: 1..9 % shortfalls could trip only the Rust per-revolution angle check
/// (4096 counts +-3 %), a documented intentional difference.
pub const DELIVERED_PCT_CHOICES: [u32; 5] = [100, 100, 100, 50, 0];

#[derive(Clone, Copy, Debug, Default)]
pub struct View {
    pub pair_id: u32,
    pub active: bool,
    pub filled: bool,
    pub suspended: bool,
    pub next_id: u32,
    pub activation_id: u32,
    pub docked: bool,
    pub charger_hint: bool,
}

pub fn view(p: &Pair) -> View {
    View {
        pair_id: p.r.pod().pair_id,
        active: p.r.pod().active,
        filled: p.r.reservoir().is_filled(),
        suspended: p.r.engine().is_suspended(),
        next_id: p.r.log().next_id(),
        activation_id: p.r.pod().activation_id,
        docked: p.r.pod().docked,
        charger_hint: false,
    }
}

pub struct Gen {
    pub rng: Rng,
    seq: u16,
    uu: u32,
    capacity: u32,
    dock: bool,
    charger: bool,
    mode: Mode,
    mode_left: u32,
    pct: u32,
}

/// Generation phases: `Normal` is the mixed stream; `Fast` mostly 5 s ticks (lets the pump
/// actually deliver: hourly limit, reservoir empty, temp done, encoder faults); `Quiet` is a long
/// stretch with (almost) no frames (comm-loss fallback of the temp basal, wear).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Mode {
    Normal,
    Fast,
    Quiet,
}

pub fn build_frame(ver: u8, ty: u8, flags: u8, seq: u16, payload: &[u8]) -> Vec<u8> {
    let mut out = vec![0u8; FRAME_MAX];
    let n = encode_frame(&Frame { version: ver, type_: ty, flags, seq, payload }, &mut out)
        .expect("frame within FRAME_MAX");
    out.truncate(n);
    out
}

pub fn payload_of(d: &CmdDesc) -> Vec<u8> {
    let mut buf = [0u8; FRAME_MAX];
    let n = encode_command_payload(&d.to_command(), &mut buf).expect("payload fits");
    buf[..n].to_vec()
}

impl Gen {
    pub fn new(seed: u64, setup: &Setup) -> Self {
        Gen { rng: Rng::new(seed), seq: 0, uu: setup.cal.uu().max(1), capacity: setup.capacity, dock: true, charger: false, mode: Mode::Normal, mode_left: 100, pct: 100 }
    }

    fn max_prime_steps(&self) -> u64 {
        (524_000 / self.uu as u64).max(1)
    }

    fn next_seq(&mut self) -> u16 {
        let r = self.rng.below(1000);
        if r < 5 {
            return self.rng.below(65535) as u16;
        }
        if r < 7 {
            return *self.rng.pick(&[0xFFFEu16, 0xFFFF]);
        }
        if r < 30 {
            return self.seq; // replay
        }
        self.seq = self.seq.saturating_add(1 + self.rng.below(2) as u16);
        self.seq
    }

    // ---- argument generators --------------------------------------------------------------
    fn rate(&mut self, valid: bool) -> u16 {
        if valid {
            (50 * self.rng.range(0, 100)) as u16
        } else {
            *self.rng.pick(&[1u16, 25, 5050, 30050, 65535, 6000, 49])
        }
    }

    fn schedule(&mut self, valid: bool) -> Vec<(u8, u16)> {
        if valid {
            let n = if self.rng.chance(500) { 1 } else { self.rng.range(1, 24) as usize };
            let mut slots: Vec<u8> = vec![0];
            while slots.len() < n {
                let s = self.rng.range(1, 47) as u8;
                if !slots.contains(&s) {
                    slots.push(s);
                }
            }
            slots.sort_unstable();
            slots.into_iter().map(|s| (s, self.rate(true))).collect()
        } else {
            let n = self.rng.range(1, 6) as usize;
            let mut v: Vec<(u8, u16)> = Vec::new();
            for _ in 0..n {
                let slot = self.rng.below(60) as u8;
                let ok = self.rng.chance(700);
                v.push((slot, self.rate(ok)));
            }
            if self.rng.chance(500) {
                v[0].0 = 0;
            }
            v
        }
    }

    fn valid_activate(&mut self, v: &View, d: &mut CmdDesc) {
        d.pair_id = if self.rng.chance(900) { v.pair_id } else { self.rng.u32() };
        d.activation_id = if v.active && self.rng.chance(500) { v.activation_id } else { self.rng.range(0, 5) as u32 };
        let sched_ok = self.rng.chance(850);
        d.segs = self.schedule(sched_ok);
        d.temp = None;
        if self.rng.chance(400) {
            let ok = self.rng.chance(800);
            d.temp = Some(if ok {
                (self.rate(true), (30 * self.rng.range(1, 24)) as u16)
            } else {
                let r_ok = self.rng.chance(500);
                (self.rate(r_ok), *self.rng.pick(&[0u16, 29, 31, 721, 750, 30]))
            });
        }
    }

    /// A logical command; `ty == 0` picks one.
    pub fn command(&mut self, v: &View) -> CmdDesc {
        let ty = if self.rng.chance(380) {
            // progress towards a delivering pod
            if v.pair_id == 0 {
                cmd::SET_PAIRING
            } else if !v.filled {
                cmd::FILL_PRIME
            } else if !v.active {
                cmd::ACTIVATE
            } else if v.suspended {
                if self.rng.chance(350) { cmd::FILL_PRIME } else { cmd::RESUME }
            } else {
                *self.rng.pick(&[cmd::BOLUS, cmd::BOLUS, cmd::SET_TEMP_BASAL, cmd::GET_STATUS, cmd::SET_BASAL_SCHEDULE, cmd::CANCEL_BOLUS, cmd::GET_HISTORY])
            }
        } else {
            self.rng.range(1, 0x0E) as u8
        };
        let mut d = CmdDesc::new(ty);
        d.tod = self.rng.chance(150).then(|| if self.rng.chance(800) { self.rng.below(86_400_000) as u32 } else { self.rng.u32() });
        let valid = self.rng.chance(750);
        match ty {
            cmd::SET_BASAL_SCHEDULE => d.segs = self.schedule(valid),
            cmd::SET_TEMP_BASAL => {
                d.rate = self.rate(valid);
                d.duration = if valid { (30 * self.rng.range(1, 24)) as u16 } else { *self.rng.pick(&[0u16, 29, 31, 721, 750, 65535]) };
            }
            cmd::BOLUS => {
                let hi = if self.mode == Mode::Fast || self.rng.chance(250) { 200 } else { 30 };
                d.amount = if valid {
                    (50 * self.rng.range(1, hi)) as u32
                } else {
                    *self.rng.pick(&[0u32, 25, 49, 10050, 11000, 25000, 100000, u32::MAX])
                }
            }
            cmd::FILL_PRIME => {
                if v.filled && v.active && self.rng.chance(600) || (v.filled && !v.active && self.rng.chance(200)) {
                    d.sub_op = SUBOP_PRIME;
                    let maxp = self.max_prime_steps();
                    d.prime = if valid { self.rng.range(1, maxp) as u16 } else { *self.rng.pick(&[0u16, 1000, 65535, (maxp + 1) as u16]) };
                } else if self.rng.chance(40) {
                    d.sub_op = *self.rng.pick(&[0u8, 3, 255]);
                } else {
                    d.sub_op = SUBOP_FILL;
                    d.fill_mu = if valid {
                        if self.rng.chance(250) {
                            self.rng.range(50, 3000) as u32 // small: empties quickly
                        } else {
                            self.rng.range(1000, self.capacity as u64) as u32
                        }
                    } else {
                        *self.rng.pick(&[0u32, self.capacity + 1, u32::MAX])
                    };
                }
            }
            cmd::ACKNOWLEDGE => d.fault_mask = *self.rng.pick(&[0xFFFFu16, 0xFFFF, 0xFFFF, 0, 1, 2, 4, 8, 16, 32, 64, 128, 0x3F, 0x00FF]),
            cmd::GET_HISTORY => {
                d.from_id = if self.rng.chance(700) { v.next_id.saturating_sub(self.rng.below(40) as u32) } else { self.rng.u32() };
                d.max_events = self.rng.below(14) as u8;
            }
            cmd::SET_PAIRING => {
                d.pair_id = if valid { *self.rng.pick(&[0xA1B2_C3D4u32, 0x1234_5678, v.pair_id.max(1), 7]) } else { 0 };
                d.role = if valid { 1 + self.rng.below(2) as u8 } else { *self.rng.pick(&[0u8, 3, 255]) };
            }
            cmd::ACTIVATE => self.valid_activate(v, &mut d),
            cmd::RELEASE => d.pair_id = if valid { v.pair_id } else { self.rng.u32() },
            _ => {}
        }
        d.encodable()
    }

    fn mutate(&mut self, d: &CmdDesc) -> Vec<u8> {
        let mut payload = payload_of(d);
        let (mut ty, mut flags, mut ver) = (d.ty, 0u8, PROTO_VERSION);
        let seq = self.next_seq();
        let mut bad_crc = false;
        match self.rng.below(10) {
            0 if !payload.is_empty() => {
                for _ in 0..self.rng.range(1, 3) {
                    let i = self.rng.below(payload.len() as u64) as usize;
                    payload[i] ^= 1 << self.rng.below(8);
                }
            }
            1 if !payload.is_empty() => payload.truncate(self.rng.below(payload.len() as u64) as usize),
            2 => {
                let n = self.rng.range(1, 6) as usize;
                payload.extend(self.rng.bytes(n));
            }
            3 => {
                let mut p = vec![0x55, self.rng.below(4) as u8];
                p.extend(self.rng.bytes(p[1] as usize));
                p.extend(payload);
                payload = p;
            }
            4 => ty = self.rng.below(256) as u8,
            5 => flags = self.rng.below(256) as u8,
            6 => ver = self.rng.below(256) as u8,
            7 => {
                let n = self.rng.below(40) as usize;
                return self.rng.bytes(n);
            }
            8 => bad_crc = true,
            _ => {
                let mut f = build_frame(ver, ty, flags, seq, &payload);
                let n = f.len();
                f[5] = f[5].wrapping_add(self.rng.range(1, 3) as u8);
                if self.rng.chance(500) {
                    let crc = crate::ffi::c_crc16(&f[..n - 2]);
                    f[n - 2..].copy_from_slice(&crc.to_le_bytes());
                }
                return f;
            }
        }
        if crate::rust_only_cmd(ty) {
            ty = cmd::GET_STATUS; // 0x0F..0x12 are Rust-only (documented)
        }
        let mut f = build_frame(ver, ty, flags, seq, &payload);
        if bad_crc {
            let n = f.len();
            f[n - 1] ^= 0x5A;
        }
        // a random byte string may still carry a Rust-only type in byte 1: keep it out of shared streams
        if f.len() > 1 && crate::rust_only_cmd(f[1]) {
            f[1] = cmd::GET_STATUS;
        }
        f
    }

    fn tick_dt(&mut self) -> u64 {
        match self.rng.below(100) {
            0..=59 => 1000,
            60..=69 => 1,
            70..=79 => self.rng.range(1, 4999),
            80..=86 => self.rng.range(5000, 7000),
            87..=93 => self.rng.range(7000, 600_000),
            94..=97 => self.rng.range(600_000, 3 * 3_600_000),
            98 => 0,
            _ => self.rng.range(40, 60) * 3_600_000,
        }
    }

    fn switch_mode(&mut self) {
        let m = self.rng.below(100);
        self.mode = if m < 45 { Mode::Normal } else if m < 80 { Mode::Fast } else { Mode::Quiet };
        self.mode_left = match self.mode {
            Mode::Normal => self.rng.range(40, 250) as u32,
            Mode::Fast => self.rng.range(100, 700) as u32,
            Mode::Quiet => self.rng.range(300, 600) as u32,
        };
    }

    /// Actuator-health knob. A degraded value stays until an encoder / occlusion fault tripped on
    /// both sides: a short degraded episode could trip only the Rust per-revolution check
    /// (documented difference (4)); a persistent one makes the C window check fire as well.
    fn pct_op(&mut self, p: &Pair) -> Op {
        let tripped = p.r.supervisor().faults().bits() & 0x3 != 0;
        if self.pct != 100 && !tripped {
            return Op::DeliveredPct(self.pct);
        }
        self.pct = *self.rng.pick(&DELIVERED_PCT_CHOICES);
        Op::DeliveredPct(self.pct)
    }

    pub fn op(&mut self, p: &Pair) -> Op {
        let v = view(p);
        if self.seq > 65_000 {
            self.seq = 0;
            return Op::NewSession;
        }
        if self.mode_left == 0 {
            self.switch_mode();
        }
        self.mode_left -= 1;
        if self.mode != Mode::Normal {
            let q = self.rng.below(1000);
            let cmd_pm = if self.mode == Mode::Fast { 90 } else { 2 };
            if q < cmd_pm {
                let d = self.command(&v);
                return Op::Frame(build_frame(PROTO_VERSION, d.ty, 0, self.next_seq(), &payload_of(&d)));
            }
            if q < cmd_pm + 15 {
                return Op::Battery(*self.rng.pick(&[3900u16, 3900, 3900, 3900, 3900, 3900, 3499, 3350, 3250]));
            }
            if q < cmd_pm + 25 {
                return self.pct_op(p);
            }
            if q < cmd_pm + 30 {
                return Op::Dock(self.rng.chance(800));
            }
            if q < cmd_pm + 33 {
                return Op::Charger(self.rng.chance(200));
            }
            return Op::Tick(if self.rng.chance(900) { 5000 } else { 1000 });
        }
        let r = self.rng.below(1000);
        match r {
            0..=419 => {
                let d = self.command(&v);
                let seq = self.next_seq();
                let mut d = d;
                d.seq = seq;
                Op::Frame(build_frame(PROTO_VERSION, d.ty, 0, seq, &payload_of(&d)))
            }
            420..=709 => Op::Tick(1000),
            710..=759 => Op::Tick(self.tick_dt()),
            760..=789 => Op::Advance(self.rng.range(0, 90_000)),
            790..=819 => {
                self.dock = if self.dock { self.rng.chance(930) } else { self.rng.chance(700) };
                Op::Dock(self.dock)
            }
            820..=839 => {
                self.charger = if self.charger { self.rng.chance(400) } else { self.rng.chance(60) };
                Op::Charger(self.charger)
            }
            840..=869 => Op::Battery(*self.rng.pick(&[3900u16, 3900, 3900, 3900, 3900, 3900, 3900, 3900, 3700, 3600, 3499, 3400, 3350, 3300, 3299, 3100, 3000, 4100])),
            870..=899 => self.pct_op(p),
            900..=919 => Op::StepsLimit(*self.rng.pick(&[-1i32, -1, -1, -1, 0, 1, 2, 5])),
            920..=934 => {
                self.seq = 0;
                Op::NewSession
            }
            935..=944 => Op::RestorePod {
                pair: *self.rng.pick(&[0u32, v.pair_id, v.pair_id, 0xA1B2_C3D4, 99]),
                role: self.rng.below(4) as u8,
                active: self.rng.chance(600),
                act_id: self.rng.range(0, 4) as u32,
                wear_ms: *self.rng.pick(&[0u64, 1000, 3_600_000, 43 * 3_600_000, 44 * 3_600_000, 51 * 3_600_000 + 3_599_000, 52 * 3_600_000, 60 * 3_600_000]),
            },
            _ => {
                let d = self.command(&v);
                Op::Frame(self.mutate(&d))
            }
        }
    }

    /// Random setup (calibration, capacity, restored next event id incl. near u32 wrap).
    pub fn setup(&mut self) -> Setup {
        use crate::pair::CalSel;
        let cal = match self.rng.below(100) {
            0..=2 => CalSel::None,
            3..=49 => CalSel::T8156,
            _ => CalSel::T26100,
        };
        let capacity = *self.rng.pick(&[70_000u32, 100_000, 200_000]);
        let next_id = match self.rng.below(20) {
            0 => 0,
            1 => u32::MAX - 2_000_000 - self.rng.below(200) as u32, // high ids, but no wrap inside a run (the C/Rust log read both stop at a wrapped id: tested separately)
            2 => self.rng.u32(),
            _ => 1,
        };
        Setup { cal, capacity, next_id }
    }
}

/// Generate a whole sequence of `n` ops for `seed`, driving a live `Pair` (state-aware).
/// Returns the setup, the ops and (when diverging) the first error.
pub fn run_generated(seed: u64, n: usize, stats: &mut crate::pair::Stats) -> (Setup, Vec<Op>, Result<(), (usize, String)>) {
    let mut g = Gen::new(seed, &Setup { cal: crate::pair::CalSel::T26100, capacity: 100_000, next_id: 1 });
    let setup = g.setup();
    g.uu = setup.cal.uu().max(1);
    g.capacity = setup.capacity;
    let mut pair = Pair::new(&setup);
    let mut ops = Vec::with_capacity(n);
    if let Err(e) = pair.check_boot(stats) {
        return (setup, ops, Err((usize::MAX, e)));
    }
    for i in 0..n {
        let op = g.op(&pair);
        let res = pair.apply(&op, stats);
        ops.push(op);
        if let Err(e) = res {
            return (setup, ops, Err((i, e)));
        }
        if pair.stopped {
            break;
        }
    }
    stats.steps_all += stats.total_steps_c;
    (setup, ops, Ok(()))
}
