//! Deterministic scenarios that the random streams reach only rarely (temp basal completion,
//! comm-loss fallback, hourly limit, occlusion, wear expiry, reservoir empty, uncalibrated pump).
//! Each scenario runs on both pumps with the full per-op comparison and asserts that the expected
//! event / fault really happened, so none of them is vacuous.

use differential_tests::desc::CmdDesc;
use differential_tests::gen::{build_frame, payload_of};
use differential_tests::pair::{CalSel, Op, Pair, Setup, Stats};
use openpatch_proto::*;

struct Sc {
    p: Pair,
    seq: u16,
    stats: Stats,
}

impl Sc {
    fn new(cal: CalSel, capacity: u32) -> Sc {
        let setup = Setup { cal, capacity, next_id: 1 };
        let mut p = Pair::new(&setup);
        let mut stats = Stats::default();
        p.check_boot(&mut stats).expect("boot");
        Sc { p, seq: 0, stats }
    }
    fn op(&mut self, op: Op) {
        if let Err(e) = self.p.apply(&op, &mut self.stats) {
            panic!("DIVERGENCE on {op:?}: {e}");
        }
    }
    fn cmd(&mut self, mut d: CmdDesc) {
        self.seq += 1;
        d.seq = self.seq;
        let f = build_frame(PROTO_VERSION, d.ty, 0, self.seq, &payload_of(&d.encodable()));
        self.op(Op::Frame(f));
    }
    fn ticks(&mut self, n: u32, dt: u64) {
        for _ in 0..n {
            self.op(Op::Tick(dt));
        }
    }
    fn pair_fill_activate(&mut self, fill: u32, rate: u16, temp: Option<(u16, u16)>) {
        let mut d = CmdDesc::new(cmd::SET_PAIRING);
        d.pair_id = 0xA1B2_C3D4;
        d.role = 1;
        self.cmd(d);
        let mut d = CmdDesc::new(cmd::FILL_PRIME);
        d.sub_op = SUBOP_FILL;
        d.fill_mu = fill;
        self.cmd(d);
        let mut d = CmdDesc::new(cmd::ACTIVATE);
        d.pair_id = 0xA1B2_C3D4;
        d.activation_id = 1;
        d.segs = vec![(0, rate), (20, rate / 2), (40, rate)];
        d.temp = temp;
        self.cmd(d);
        let mut d = CmdDesc::new(cmd::FILL_PRIME);
        d.sub_op = SUBOP_PRIME;
        d.prime = 10;
        self.cmd(d);
        self.cmd(CmdDesc::new(cmd::RESUME));
    }
    fn status(&mut self) {
        let mut d = CmdDesc::new(cmd::GET_STATUS);
        d.tod = Some(0);
        self.cmd(d);
    }
    fn bolus(&mut self, mu: u32) {
        let mut d = CmdDesc::new(cmd::BOLUS);
        d.amount = mu;
        self.cmd(d);
    }
    fn history(&mut self) {
        let mut d = CmdDesc::new(cmd::GET_HISTORY);
        d.from_id = 1;
        d.max_events = 10;
        self.cmd(d);
    }
}

fn each_cal(f: impl Fn(&mut Sc)) {
    for cal in [CalSel::T26100, CalSel::T8156] {
        let mut sc = Sc::new(cal, 100_000);
        f(&mut sc);
    }
}

#[test]
fn temp_basal_runs_to_completion_and_emits_temp_done() {
    each_cal(|sc| {
        sc.pair_fill_activate(50_000, 2000, Some((3000, 30)));
        for _ in 0..40 {
            sc.ticks(10, 5000);
            sc.status(); // keeps the comm heartbeat alive
        }
        assert!(sc.stats.event_types_seen.contains(&6), "TEMP_DONE (6) never logged");
        assert!(!sc.stats.event_types_seen.contains(&8));
    });
}

#[test]
fn temp_basal_falls_back_after_30_minutes_without_comm() {
    each_cal(|sc| {
        sc.pair_fill_activate(50_000, 2000, Some((3500, 120)));
        sc.ticks(450, 5000); // 37.5 min of silence
        sc.history();
        assert!(sc.stats.event_types_seen.contains(&8), "TEMP_COMM_FALLBACK (8) never logged");
    });
}

#[test]
fn hourly_cap_vetoes_boluses_and_latches_limit_fault() {
    each_cal(|sc| {
        sc.pair_fill_activate(100_000, 5000, None);
        sc.bolus(7000);
        sc.ticks(100, 5000);
        sc.bolus(7000);
        sc.ticks(300, 5000); // basal after the bolus pushes the rolling hour over 15 U: veto + fault
        sc.cmd(CmdDesc::new(cmd::ACKNOWLEDGE));
        sc.bolus(500); // rolling hour is full: Hourly
        sc.ticks(60, 5000);
        sc.status();
        sc.history();
        assert!(sc.stats.fault_bits_seen & 0x10 != 0, "LIMIT_EXCEEDED fault never latched");
    });
}

#[test]
fn stalled_motor_latches_occlusion_and_encoder_deviation() {
    each_cal(|sc| {
        sc.pair_fill_activate(100_000, 3000, None);
        sc.op(Op::DeliveredPct(0));
        sc.bolus(5000);
        sc.ticks(60, 1000);
        sc.status();
        sc.cmd(CmdDesc::new(cmd::ACKNOWLEDGE));
        sc.op(Op::DeliveredPct(50));
        sc.cmd(CmdDesc::new(cmd::RESUME));
        sc.bolus(3000);
        sc.ticks(120, 1000);
        sc.history();
        assert!(sc.stats.fault_bits_seen & 0b11 != 0, "no encoder fault seen");
    });
}

#[test]
fn motor_not_executing_approved_steps_latches_internal() {
    each_cal(|sc| {
        sc.pair_fill_activate(100_000, 3000, None);
        sc.op(Op::StepsLimit(0));
        sc.bolus(2000);
        sc.ticks(20, 1000);
        sc.status();
        assert!(sc.stats.fault_bits_seen & 0x20 != 0, "no INTERNAL fault");
        sc.op(Op::StepsLimit(-1));
        sc.cmd(CmdDesc::new(cmd::ACKNOWLEDGE));
        sc.cmd(CmdDesc::new(cmd::RESUME));
        sc.ticks(30, 1000);
    });
}

#[test]
fn small_reservoir_runs_empty() {
    each_cal(|sc| {
        sc.pair_fill_activate(1500, 5000, None);
        sc.bolus(1000);
        sc.ticks(100, 1000);
        sc.bolus(1000); // more than what is left: Reservoir
        sc.ticks(400, 1000); // basal drains the rest
        sc.status();
        assert!(sc.stats.fault_bits_seen & 0x04 != 0, "reservoir never ran empty");
        sc.cmd(CmdDesc::new(cmd::ACKNOWLEDGE)); // persists (reservoir empty)
        sc.history();
    });
}

#[test]
fn wear_warning_expiry_and_reactivation() {
    each_cal(|sc| {
        sc.pair_fill_activate(100_000, 2000, None);
        sc.ticks(3, 1000);
        sc.op(Op::Tick(44 * 3_600_000));
        sc.status();
        sc.op(Op::Tick(9 * 3_600_000));
        sc.status();
        assert!(sc.stats.event_types_seen.contains(&22) && sc.stats.event_types_seen.contains(&23));
        sc.cmd(CmdDesc::new(cmd::ACKNOWLEDGE)); // persists
        let mut d = CmdDesc::new(cmd::RELEASE);
        d.pair_id = 0xA1B2_C3D4;
        sc.cmd(d);
        sc.cmd(CmdDesc::new(cmd::ACKNOWLEDGE));
        let mut d = CmdDesc::new(cmd::ACTIVATE);
        d.pair_id = 0xA1B2_C3D4;
        d.activation_id = 2;
        d.segs = vec![(0, 1000)];
        d.temp = Some((500, 60));
        sc.cmd(d);
        sc.cmd(CmdDesc::new(cmd::RESUME));
        sc.ticks(50, 1000);
        sc.op(Op::RestorePod { pair: 0xA1B2_C3D4, role: 1, active: true, act_id: 2, wear_ms: 53 * 3_600_000 });
        sc.status();
        sc.op(Op::RestorePod { pair: 0xA1B2_C3D4, role: 2, active: true, act_id: 3, wear_ms: 45 * 3_600_000 });
        sc.status();
    });
}

#[test]
fn dock_charger_and_battery_interplay() {
    each_cal(|sc| {
        sc.pair_fill_activate(100_000, 5000, None);
        sc.bolus(3000);
        sc.ticks(10, 1000);
        sc.op(Op::Dock(false));
        sc.ticks(5, 1000);
        sc.bolus(500);
        sc.op(Op::Dock(true));
        sc.cmd(CmdDesc::new(cmd::RESUME));
        sc.bolus(1000);
        sc.op(Op::Charger(true));
        sc.ticks(3, 1000);
        sc.status();
        sc.op(Op::Charger(false));
        sc.op(Op::Battery(3400));
        sc.ticks(2, 1000);
        sc.op(Op::Battery(3250));
        sc.ticks(2, 1000);
        sc.cmd(CmdDesc::new(cmd::ACKNOWLEDGE));
        sc.op(Op::Battery(3500));
        sc.cmd(CmdDesc::new(cmd::ACKNOWLEDGE));
        sc.history();
        for k in [17u8, 18, 19, 21] {
            assert!(sc.stats.event_types_seen.contains(&(k as i64)), "event {k} missing");
        }
    });
}

#[test]
fn uncalibrated_pump_never_delivers() {
    let mut sc = Sc::new(CalSel::None, 100_000);
    sc.pair_fill_activate(50_000, 2000, None);
    sc.bolus(500);
    sc.ticks(30, 1000);
    sc.cmd(CmdDesc::new(cmd::ACKNOWLEDGE));
    sc.status();
    sc.history();
    assert_eq!(sc.stats.total_steps_c, 0);
    assert!(sc.stats.fault_bits_seen & 0x40 != 0);
}

#[test]
fn hourly_cap_rejects_a_bolus_that_would_not_fit() {
    each_cal(|sc| {
        sc.pair_fill_activate(100_000, 1000, None);
        sc.bolus(10_000);
        sc.ticks(160, 5000); // bolus done (6.7 min)
        sc.bolus(5_000); // 10 U + prime + 5 U > 15 U in the rolling hour
        sc.ticks(5, 1000);
        assert!(sc.stats.kinds.contains(&(cmd::BOLUS, 16)), "no Hourly rejection: {:?}", sc.stats.kinds);
    });
}
