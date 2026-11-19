//! Property tests (stepper core + draw mode): random operation sequences against the pump with the
//! mock HAL; invariants are asserted after EVERY operation.
//!
//! Definitions used by the invariants:
//! * "hourly window": the supervisor buckets approved steps per WALL MINUTE (`now / 60 000 ms`) and
//!   sums the 60 most recent buckets (minutes `m-59 ..= m`). The test counts executed forward
//!   steps (tick and prime) per wall minute of the mock clock and asserts on exactly that.
//! * "commanded": `engine.scheduled_scaled() * uu_den` is the scheduled volume in the engine's
//!   exact accumulator units; one step is `engine.threshold()` of them, so
//!   `requested * threshold <= scheduled_scaled * den` and delivered <= requested.
//! * draw: the level may rise only by steps the angle sensor confirmed (total reverse travel of
//!   the job converted with the preset's steps-per-turn, +1 mU for the floored level arithmetic).
mod common;
use common::*;
use openpatch_core::drive_cal::PRESETS;
use openpatch_core::limits::*;
use openpatch_core::*;
use proptest::prelude::*;
use std::collections::BTreeMap;

#[derive(Clone, Debug)]
enum Op {
    Tick(u64),
    BigTick(u32),
    Bolus(u32),
    Temp(u32, u32),
    Schedule(u32),
    Suspend,
    Resume,
    Dock(bool),
    Charger(bool),
    DrawStart(u32),
    DrawCancel,
    Delivered(i64),
    StepsLimit(i64),
    ReversePct(i64),
    ReverseLimit(i64),
    Current(Option<u16>),
    AngleMissing(bool),
    Ack,
    Release,
    Activate,
    Prime(u32),
    Fill(u32),
}

fn op_strategy() -> impl Strategy<Value = Op> {
    prop_oneof![
        30 => prop_oneof![8 => 800u64..1500, 1 => 1u64..800, 1 => 1500u64..7000].prop_map(Op::Tick),
        1 => (1u32..20).prop_map(Op::BigTick),
        6 => (1u32..=200).prop_map(|u| Op::Bolus(u * 50)),
        3 => (0u32..=600, 1u32..=24).prop_map(|(r, d)| Op::Temp(r * 50, d * 30)),
        2 => (0u32..=100).prop_map(|r| Op::Schedule(r * 50)),
        3 => Just(Op::Suspend),
        8 => Just(Op::Resume),
        4 => prop_oneof![1 => Just(false), 2 => Just(true)].prop_map(Op::Dock),
        1 => prop_oneof![2 => Just(false), 1 => Just(true)].prop_map(Op::Charger),
        5 => prop_oneof![1 => 27u32..2_000, 2 => 2_000u32..40_000].prop_map(Op::DrawStart),
        2 => Just(Op::DrawCancel),
        3 => prop_oneof![3 => Just(100i64), 1 => Just(99i64), 1 => Just(50i64), 1 => Just(0i64)].prop_map(Op::Delivered),
        2 => prop_oneof![6 => Just(-1i64), 1 => Just(0i64), 1 => Just(3i64)].prop_map(Op::StepsLimit),
        2 => prop_oneof![5 => Just(100i64), 1 => Just(60i64), 1 => Just(30i64)].prop_map(Op::ReversePct),
        2 => prop_oneof![5 => Just(-1i64), 1 => Just(0i64), 1 => Just(100i64)].prop_map(Op::ReverseLimit),
        2 => prop_oneof![2 => Just(None), 1 => Just(Some(50u16)), 1 => Just(Some(200u16))].prop_map(Op::Current),
        1 => prop_oneof![5 => Just(false), 1 => Just(true)].prop_map(Op::AngleMissing),
        6 => Just(Op::Ack),
        1 => Just(Op::Release),
        2 => Just(Op::Activate),
        2 => (1u32..=20).prop_map(Op::Prime),
        2 => prop_oneof![Just(1_500u32), Just(20_000u32), Just(60_000u32)].prop_map(Op::Fill),
    ]
}

#[derive(Clone, Copy, PartialEq)]
enum Kind {
    Tick,
    Prime,
    Other,
}

/// A running draw job as the model sees it.
struct Job {
    remaining_before: i64,
    angle_start: i64,
    reverse_start: u32,
    requested_mu: u32,
    requested_steps: u32,
}

struct Rig {
    p: Pump<MockHal>,
    h: MockHal,
    strict: bool,
    per_min: BTreeMap<u64, u32>,
    job: Option<Job>,
    calibrated: bool,
    cap_steps: u32,
    per_min_cap: u32,
    turn_x100: u32,
}

fn counts_for(turn_x100: u32) -> i64 {
    (409_600 + turn_x100 as i64 - 1) / turn_x100 as i64
}

impl Rig {
    fn build(cal: Option<DriveCal>, turn_x100: u32, fill_mu: u32, strict: bool, basal: u32) -> Rig {
        let hal = MockHal::new();
        hal.st().counts_per_step = counts_for(turn_x100.max(1));
        let mut p = Pump::new(hal.clone(), cal.as_ref(), CAPACITY_100, 1);
        p.set_config(PumpConfig::RELAXED);
        let _ = p.supervisor_mut().configure(MilliUnits(10_000), MilliUnitsPerHour(30_000));
        let _ = p.fill(MilliUnits(fill_mu));
        let _ = activate(&mut p, basal);
        let _ = p.resume();
        p.set_config(if strict { PumpConfig::STRICT } else { PumpConfig::RELAXED });
        let pc = p.pulse_cal();
        let calibrated = !pc.is_none();
        let (cap_steps, per_min_cap) =
            if calibrated { (pc.mu_to_pulses(MAX_HOURLY).0, pc.mu_to_pulses(MAX_PER_MIN).0) } else { (0, 0) };
        Rig { p, h: hal, strict, per_min: BTreeMap::new(), job: None, calibrated, cap_steps, per_min_cap, turn_x100 }
    }

    fn standard(preset: usize, fill_sel: usize, strict: bool, basal: u32) -> Rig {
        let pr = &PRESETS[preset];
        let fill = [1_500, 20_000, 100_000][fill_sel];
        Rig::build(Some(DriveCal::from_preset(pr)), pr.cal().turn_x100, fill, strict, basal)
    }

    fn faults(&self) -> Faults {
        self.p.supervisor().faults()
    }

    fn angle(&self) -> i64 {
        self.h.st().angle_x100 / 100
    }

    /// Run `f` (one operation) and check the step invariants against the state before it.
    fn run(&mut self, kind: Kind, f: impl FnOnce(&mut Self)) {
        let (docked, charger, angle_missing, fw0, rv0) = {
            let m = self.h.st();
            (m.docked, m.charger, m.angle_missing, m.total_steps, m.total_reverse_steps)
        };
        let faults_pre = self.faults();
        let active = self.p.pod().active;
        let suspended = self.p.engine().is_suspended();
        let drawing = self.p.draw_running();

        f(self);

        let (fw, rv, now, enabled, bad) = {
            let m = self.h.st();
            (m.total_steps - fw0, m.total_reverse_steps - rv0, m.now_ms, m.enabled, m.stepped_while_disabled)
        };
        // (d) the driver is off after every operation, and never stepped while disabled
        assert!(!enabled, "motor left enabled");
        assert!(!bad, "step while the motor was disabled");
        if fw > 0 {
            // (c) hard preconditions of every forward step
            assert!(self.calibrated, "forward step without a valid calibration");
            assert!(docked, "forward step while undocked");
            assert!(active, "forward step on a released pod");
            assert!(faults_pre.is_empty(), "forward step with {faults_pre:?} latched");
            assert!(!drawing, "forward step while a draw was running");
            assert!(!angle_missing, "forward step while the angle sensor is missing");
            match kind {
                Kind::Tick => {
                    assert!(!suspended, "forward step while suspended");
                    assert!(!charger, "forward step on a charger");
                }
                Kind::Prime => assert!(suspended),
                Kind::Other => panic!("forward step outside tick/prime"),
            }
            *self.per_min.entry(now / 60_000).or_insert(0) += fw;
        }
        if rv > 0 {
            assert!(kind == Kind::Tick, "reverse steps outside a tick");
            assert!(!docked, "reverse step while docked");
            assert!(drawing && suspended, "reverse step without a running draw");
            assert!(faults_pre.is_empty(), "reverse step with a fault latched");
            assert_eq!(fw, 0, "forward and reverse in one tick");
        }
        // (b) hourly window over wall minutes + per-minute backstop
        let m = now / 60_000;
        let window: u32 = self.per_min.range(m.saturating_sub(59)..=m).map(|(_, v)| *v).sum();
        assert!(window <= self.cap_steps, "{window} steps in the 60-minute window (cap {})", self.cap_steps);
        let this_min = self.per_min.get(&m).copied().unwrap_or(0);
        assert!(this_min <= self.per_min_cap, "{this_min} steps in one minute (cap {})", self.per_min_cap);
        self.check();
    }

    fn check(&mut self) {
        assert!(!self.h.st().enabled, "motor enabled between operations");
        let e = self.p.engine();
        // (a) delivered never exceeds commanded, exact
        let den = e.calibration().uu_den as i128;
        let commanded = e.scheduled_scaled() as i128 * den;
        let thr = e.threshold() as i128;
        assert!(e.requested_steps().0 as i128 * thr <= commanded, "requested above commanded");
        assert!(e.delivered_steps().0 <= e.requested_steps().0);
        assert!(e.delivered_steps().0 as i128 * thr <= commanded, "delivered above commanded");
        assert_eq!(
            e.delivered_steps().0 + e.dropped_steps().0 + e.pending_steps().0,
            e.requested_steps().0,
            "step accounting"
        );
        let r = self.p.reservoir();
        assert!(r.remaining() <= r.capacity(), "level above capacity");
        assert!(r.consumed().0 <= self.p.pulse_cal().mu_to_pulses(r.fill_level()).0 + 1, "consumed above fill");
        if self.p.draw_running() {
            assert!(self.p.engine().is_suspended(), "draw running while delivering");
        }
        if !self.calibrated {
            let moved = {
                let m = self.h.st();
                m.total_steps + m.total_reverse_steps
            };
            assert_eq!(moved, 0, "motor moved without calibration");
            assert!(self.faults().contains(Faults::NO_CALIBRATION), "NO_CALIBRATION was cleared");
        }
        self.check_draw();
    }

    /// (e) + (f): the level rises only by angle-confirmed steps; drawn never exceeds requested.
    fn check_draw(&mut self) {
        let Some(job) = &self.job else { return };
        assert!(self.p.draw_drawn().0 <= job.requested_mu, "drawn above requested (running)");
        assert!(self.h.st().total_reverse_steps - job.reverse_start <= job.requested_steps, "more reverse steps than requested");
        if self.p.draw_running() {
            return;
        }
        // job finished in the operation just executed
        let st = self.p.get_status();
        assert!(st.draw_done_mu <= st.draw_requested_mu, "drawn {} > requested {}", st.draw_done_mu, st.draw_requested_mu);
        let gain = self.p.reservoir().remaining().0 as i64 - job.remaining_before;
        let travelled = (job.angle_start - self.angle()).max(0) as u128;
        let measured = (travelled * self.turn_x100 as u128 / 409_600) as u32;
        let confirmed_mu = self.p.pulse_cal().pulses_to_mu(Pulses(measured)).0 as i64;
        assert!(gain <= confirmed_mu + 1, "level rose by {gain} mU, angle confirmed only {confirmed_mu} mU");
        assert!(gain <= job.requested_mu as i64 + 1, "level rose by {gain} > requested {}", job.requested_mu);
        assert!(self.p.draw_drawn().0 as i64 <= confirmed_mu, "drawn above angle-confirmed");
        self.job = None;
    }

    fn command_gate(&mut self, ok: bool, what: &str) {
        if !ok {
            return;
        }
        let docked = self.h.st().docked;
        assert!(docked, "{what} accepted while undocked");
        assert!(self.faults().is_empty(), "{what} accepted with a fault latched");
        assert!(self.p.pod().active, "{what} accepted on a released pod");
        assert!(!self.p.draw_running(), "{what} accepted while drawing");
    }

    fn apply(&mut self, op: &Op) {
        match op {
            Op::Tick(dt) => {
                let dt = *dt;
                self.run(Kind::Tick, |r| {
                    r.h.advance_ms(dt);
                    r.p.tick();
                })
            }
            Op::BigTick(min) => {
                let ms = *min as u64 * 60_000;
                self.run(Kind::Tick, |r| {
                    r.h.advance_ms(ms);
                    r.p.tick();
                })
            }
            Op::Prime(n) => {
                let n = *n;
                self.run(Kind::Prime, |r| {
                    let res = r.p.prime(Pulses(n));
                    r.command_gate(res.is_ok(), "prime");
                })
            }
            Op::DrawStart(mu) => {
                let mu = *mu;
                let remaining_before = self.p.reservoir().remaining().0 as i64;
                let angle_start = self.angle();
                let reverse_start = self.h.st().total_reverse_steps;
                let mut ok = false;
                self.run(Kind::Other, |r| {
                    ok = r.p.fill_draw(MilliUnits(mu)).is_ok();
                });
                if ok {
                    let steps = self.p.pulse_cal().mu_to_pulses(MilliUnits(mu)).0;
                    assert!(self.h.st().docked == false, "draw started while docked");
                    assert!(self.p.engine().is_suspended());
                    assert!(self.faults().is_empty());
                    self.job = Some(Job { remaining_before, angle_start, reverse_start, requested_mu: mu, requested_steps: steps });
                    self.check();
                }
            }
            other => self.run(Kind::Other, |r| r.apply_plain(other)),
        }
    }

    fn apply_plain(&mut self, op: &Op) {
        match op {
            Op::Bolus(mu) => {
                let r = self.p.bolus(MilliUnits(*mu));
                self.command_gate(r.is_ok(), "bolus");
            }
            Op::Temp(rate, dur) => {
                let _ = self.p.set_temp_basal(MilliUnitsPerHour(*rate), Minutes(*dur));
            }
            Op::Schedule(rate) => {
                let _ = self.p.set_schedule(&BasalSchedule::flat(MilliUnitsPerHour(*rate)));
            }
            Op::Suspend => {
                let _ = self.p.suspend();
            }
            Op::Resume => {
                let r = self.p.resume();
                self.command_gate(r.is_ok(), "resume");
                if r.is_ok() && self.strict {
                    assert!(!self.p.prime_required(), "resume accepted before the mandatory prime");
                }
            }
            Op::Dock(d) => self.h.st().docked = *d,
            Op::Charger(c) => self.h.st().charger = *c,
            Op::DrawCancel => {
                let _ = self.p.fill_draw(MilliUnits(0));
            }
            Op::Delivered(pct) => self.h.st().delivered_pct = *pct,
            Op::StepsLimit(l) => self.h.st().steps_limit = *l,
            Op::ReversePct(pct) => self.h.st().reverse_pct = *pct,
            Op::ReverseLimit(l) => self.h.st().reverse_limit = *l,
            Op::Current(c) => self.h.st().current_ma = *c,
            Op::AngleMissing(m) => self.h.st().angle_missing = *m,
            Op::Ack => {
                let _ = self.p.acknowledge(Faults::ALL);
            }
            Op::Release => {
                let _ = self.p.release(TEST_PAIR);
            }
            Op::Activate => {
                let _ = activate(&mut self.p, 1000);
            }
            Op::Fill(mu) => {
                let _ = self.p.fill(MilliUnits(*mu));
            }
            Op::Tick(_) | Op::BigTick(_) | Op::Prime(_) | Op::DrawStart(_) => unreachable!(),
        }
    }
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(256))]

    /// Invariants (a)-(f) under random sequences, RELAXED or STRICT, all six calibrations.
    #[test]
    fn random_operation_sequences_keep_every_invariant(
        preset in 0usize..6,
        fill_sel in 0usize..3,
        strict in any::<bool>(),
        basal in (0u32..=100).prop_map(|r| r * 50),
        ops in proptest::collection::vec(op_strategy(), 100..800),
    ) {
        let mut rig = Rig::standard(preset, fill_sel, strict, basal);
        rig.check();
        for op in &ops {
            rig.apply(op);
        }
    }

    /// Bolus-heavy sequences: reach the 15 U / 60 min cap and the reservoir end, never exceed them.
    #[test]
    fn bolus_storms_never_exceed_the_hourly_cap(
        preset in 0usize..6,
        boluses in proptest::collection::vec((1u32..=200, 1u32..=3), 20..60),
    ) {
        let mut rig = Rig::standard(preset, 2, false, 0);
        for (u, acks) in boluses {
            for _ in 0..acks {
                rig.apply(&Op::Ack);
                rig.apply(&Op::Resume);
            }
            rig.apply(&Op::Bolus(u * 50));
            for _ in 0..120 {
                rig.apply(&Op::Tick(1000));
            }
        }
    }

    /// Draw-heavy sequences on a healthy mock with random stalls: the level never rises by more
    /// than the angle-confirmed steps, drawn never exceeds requested.
    #[test]
    fn draw_sequences_never_overbook_the_level(
        preset in 0usize..6,
        draws in proptest::collection::vec((27u32..40_000, 0usize..5, 1u32..12), 5..40),
    ) {
        let mut rig = Rig::standard(preset, 1, false, 500);
        rig.apply(&Op::Suspend);
        rig.apply(&Op::Dock(false));
        for (mu, mode, ticks) in draws {
            match mode {
                0 => rig.apply(&Op::ReversePct(100)),
                1 => rig.apply(&Op::ReversePct(30)),
                2 => rig.apply(&Op::ReverseLimit(100)),
                3 => rig.apply(&Op::Current(Some(200))),
                _ => { rig.apply(&Op::ReverseLimit(-1)); rig.apply(&Op::Current(None)); rig.apply(&Op::ReversePct(100)); }
            }
            rig.apply(&Op::DrawStart(mu));
            for _ in 0..ticks {
                rig.apply(&Op::Tick(1000));
            }
            rig.apply(&Op::ReverseLimit(-1));
            rig.apply(&Op::Current(None));
            rig.apply(&Op::ReversePct(100));
            rig.apply(&Op::DrawCancel);
        }
    }

    /// No / invalid calibration: the motor never moves in either direction.
    #[test]
    fn without_a_valid_calibration_nothing_ever_moves(
        variant in 0usize..4,
        ops in proptest::collection::vec(op_strategy(), 50..400),
    ) {
        let good = DriveCal::from_preset(&drive_cal_test());
        let cal = match variant {
            0 => None,
            1 => { let mut c = good; c.crc32 ^= 1; Some(c) }
            2 => { let mut c = good; c.uu_num = 20_000; c.crc32 = c.compute_crc(); Some(c) }
            _ => { let mut c = good; c.magic = 0; Some(c) }
        };
        let mut rig = Rig::build(cal, 25_600, 50_000, false, 1000);
        rig.check();
        for op in &ops {
            rig.apply(op);
        }
    }
}

fn drive_cal_test() -> openpatch_core::drive_cal::Preset {
    openpatch_core::drive_cal::TEST_26100
}
