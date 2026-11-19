//! The "firmware application" layer around the core: boot + restore from flash, the 1 s safety
//! tick, the persistence policy (a model of `openpatch-bench/src/safety.rs::Policy`), and a phone
//! that talks to the pod through the real protocol path (`Pump::handle_frame`).
//!
//! The persistence constants are copied from `openpatch-bench/src/config.rs`; if the bench app
//! changes them, change them here too (REPORT.md lists this as a model assumption).

use crate::flash::{Key, PodRec, Stored};
use crate::params::Params;
use crate::world::{ResetCause, SimHal, World};
use openpatch_core::drive_cal::{DriveCal, DriveId};
use openpatch_core::{MilliUnits, Millis, Pulses, Pump, Role};
use openpatch_proto::{self as proto, Command, CommandBody, NoCrypto, Response, Session, FRAME_MAX};
use std::cell::RefCell;
use std::rc::Rc;

pub const TICK_PERIOD_US: u64 = 1_000_000;
pub const EVT_CEILING_STEP: u32 = 64;
pub const EVT_CEILING_HEADROOM: u32 = 16;
pub const RES_MARGIN_STEPS: u32 = 64;
pub const RES_TRIGGER_STEPS: u32 = 16;
pub const WEAR_MARGIN_S: u32 = 600;
pub const WEAR_WRITE_PERIOD_S: u32 = 300;
pub const PAIR_ID: u32 = 0x0BE7_C0DE;

#[derive(Clone, Debug)]
pub struct DeviceConfig {
    pub preset: DriveId,
    pub capacity_mu: u32,
    /// Production setting: Resume refused until a prime ran after every fill / draw.
    pub strict_prime: bool,
    /// Time of day at t = 0 (ms); the phone sets it with every command.
    pub start_tod_ms: u32,
    pub heartbeat_s: u32,
}

impl Default for DeviceConfig {
    fn default() -> Self {
        DeviceConfig {
            preset: DriveId::Nfp608_26_45G15_12,
            capacity_mu: 100_000,
            strict_prime: true,
            start_tod_ms: 8 * 3_600_000,
            heartbeat_s: 60,
        }
    }
}

#[derive(Default)]
struct Policy {
    evt_ceiling: u32,
    res_fill: u32,
    res_persisted_consumed: u32,
    pod: Option<PodRec>,
    ticks_since_pod_write: u32,
}

/// What the boot code found in flash (for verdicts).
#[derive(Clone, Debug, Default)]
pub struct BootReport {
    pub t_us: u64,
    pub cause: Option<String>,
    pub reservoir_restored: Option<(u32, u32)>,
    pub pod_restored: Option<PodRec>,
    pub evt_start: u32,
    /// reservoir model after boot minus the physically present insulin (mU): lower is safer
    pub model_minus_actual_mu_before: Option<f64>,
    pub model_minus_actual_mu_after: Option<f64>,
    /// event id the pod before the reset would have issued next
    pub pre_reset_next_event_id: Option<u32>,
    pub status_flags: u16,
    pub suspended: bool,
    pub alarm_flag: bool,
}

pub struct Device {
    pub cfg: DeviceConfig,
    pub world: Rc<RefCell<World>>,
    pub pump: Option<Pump<SimHal>>,
    session: Session<NoCrypto>,
    phone: Session<NoCrypto>,
    policy: Policy,
    next_tick_us: u64,
    seq: u16,
    pub phone_connected: bool,
    next_heartbeat_us: u64,
    pub boots: u32,
    pub boot_reports: Vec<BootReport>,
    pub ticks: u64,
    /// model reservoir minus physical liquid, mU, captured just before the last reset
    last_discrepancy_mu: Option<f64>,
    last_next_event_id: Option<u32>,
    /// callbacks for the runner: (t_us, text)
    pub notes: Vec<(u64, String)>,
    pending_boot_cause: Option<String>,
}

fn new_session() -> Session<NoCrypto> {
    Session::new(NoCrypto, false, [0; 4], true)
}

impl Device {
    pub fn new(params: Params, seed: u64, cfg: DeviceConfig) -> Self {
        let world = Rc::new(RefCell::new(World::new(params, seed)));
        let mut d = Device {
            cfg,
            world,
            pump: None,
            session: new_session(),
            phone: new_session(),
            policy: Policy::default(),
            next_tick_us: 0,
            seq: 0,
            phone_connected: true,
            next_heartbeat_us: 0,
            boots: 0,
            boot_reports: Vec::new(),
            ticks: 0,
            last_discrepancy_mu: None,
            last_next_event_id: None,
            notes: Vec::new(),
            pending_boot_cause: None,
        };
        d.boot("cold start");
        d
    }

    pub fn now_us(&self) -> u64 {
        self.world.borrow().t_us
    }

    fn cal(&self) -> DriveCal {
        DriveCal::from_preset(self.cfg.preset.preset())
    }

    /// Model-minus-reality of the reservoir in mU (positive = the pod believes it has more
    /// insulin than it has).
    pub fn reservoir_discrepancy_mu(&self) -> Option<f64> {
        let p = self.pump.as_ref()?;
        let model = p.reservoir().remaining().0 as f64;
        let actual = self.world.borrow().plant.liquid_ul * 100.0; // 1 ul = 0.1 U = 100 mU
        Some(model - actual)
    }

    // ---- boot ---------------------------------------------------------------------------------
    fn boot(&mut self, cause: &str) {
        let (reservoir, pod, evt_c) = {
            let w = self.world.borrow();
            let res = match w.flash.read(Key::Reservoir) {
                Some(Stored::Reservoir(f, c)) => Some((f, c)),
                _ => None,
            };
            let pod = match w.flash.read(Key::Pod) {
                Some(Stored::Pod(p)) => Some(p),
                _ => None,
            };
            let evt = match w.flash.read(Key::EvtCeiling) {
                Some(Stored::EvtCeiling(e)) => e,
                _ => 0,
            };
            (res, pod, evt)
        };
        let cal = self.cal();
        let evt_start = evt_c.max(1);
        let hal = SimHal(self.world.clone());
        let mut pump = Pump::new(hal, Some(&cal), MilliUnits(self.cfg.capacity_mu), evt_start);
        if !self.cfg.strict_prime {
            pump.set_config(openpatch_core::PumpConfig::RELAXED);
        }
        if let Some((fill, consumed)) = reservoir {
            pump.reservoir_mut().restore(MilliUnits(fill), Pulses(consumed));
        }
        if let Some(p) = pod {
            if Role::from_u8(p.role).is_ok() || p.pair_id == 0 {
                pump.restore_pod(p.pair_id, p.role, p.active, p.activation_id, Millis(p.wear_s as u64 * 1000));
            }
        }
        let st = pump.get_status();
        let after = {
            let model = pump.reservoir().remaining().0 as f64;
            model - self.world.borrow().plant.liquid_ul * 100.0
        };
        let t = self.world.borrow().t_us;
        self.boot_reports.push(BootReport {
            t_us: t,
            cause: Some(cause.to_string()),
            reservoir_restored: reservoir,
            pod_restored: pod,
            evt_start,
            model_minus_actual_mu_before: self.last_discrepancy_mu,
            model_minus_actual_mu_after: Some(after),
            pre_reset_next_event_id: self.last_next_event_id,
            status_flags: st.flags,
            suspended: st.flags & proto::st::SUSPENDED != 0,
            alarm_flag: st.flags & proto::st::ALARM != 0,
        });
        self.policy = Policy {
            evt_ceiling: evt_start + EVT_CEILING_STEP,
            res_fill: reservoir.map_or(0, |r| r.0),
            res_persisted_consumed: reservoir.map_or(0, |r| r.1),
            pod,
            ticks_since_pod_write: 0,
        };
        self.world.borrow_mut().flash.queue(Stored::EvtCeiling(self.policy.evt_ceiling));
        self.pump = Some(pump);
        self.session = new_session();
        self.boots += 1;
        self.next_tick_us = t + TICK_PERIOD_US;
        self.next_heartbeat_us = t + self.cfg.heartbeat_s as u64 * 1_000_000;
        self.world.borrow_mut().booted();
    }

    /// Reset / power events raised by the world.
    fn handle_world_events(&mut self) {
        let cause = self.world.borrow_mut().reset_pending.take();
        if let Some(c) = cause {
            self.last_discrepancy_mu = self.reservoir_discrepancy_mu();
            self.last_next_event_id = self.pump.as_ref().map(|p| p.log().next_id());
            self.pump = None; // everything volatile is gone
            let s = match c {
                ResetCause::Watchdog => "watchdog",
                ResetCause::PowerLoss => "power loss",
            };
            self.notes.push((self.now_us(), format!("reset: {s}")));
            if c == ResetCause::Watchdog {
                let mut w = self.world.borrow_mut();
                if w.boot_at_us.is_none() {
                    let t = w.t_us + (w.params.electrical.boot_ms * 1000.0) as u64;
                    w.boot_at_us = Some(t);
                }
            }
            self.pending_boot_cause = Some(s.to_string());
        }
        let due = {
            let w = self.world.borrow();
            w.power_on && self.pump.is_none() && w.boot_at_us.is_some_and(|b| w.t_us >= b)
        };
        if due {
            let c = self.pending_boot_cause.take().unwrap_or_else(|| "boot".into());
            self.boot(&c);
        }
    }

    // ---- time ---------------------------------------------------------------------------------
    /// Run the pod (ticks, background, boots) up to and including `t_us`.
    pub fn run_to(&mut self, t_us: u64) {
        loop {
            let now = self.world.borrow().t_us;
            let mut next = t_us;
            if self.pump.is_some() {
                next = next.min(self.next_tick_us);
            } else {
                let w = self.world.borrow();
                if let (true, Some(b)) = (w.power_on, w.boot_at_us) {
                    next = next.min(b);
                }
            }
            self.world.borrow_mut().advance_to(next.max(now));
            self.handle_world_events();
            let now = self.world.borrow().t_us;
            if self.pump.is_some() && now >= self.next_tick_us {
                self.do_tick();
                self.handle_world_events();
                continue;
            }
            if now >= t_us {
                break;
            }
        }
    }

    fn do_tick(&mut self) {
        let hung = self.world.borrow().hung;
        let now = self.world.borrow().t_us;
        // keep the 1 s grid; if a long burst overran, skip the missed grid points (Ticker semantics)
        while self.next_tick_us <= now {
            self.next_tick_us += TICK_PERIOD_US;
        }
        if hung {
            return; // firmware stuck: no tick, no DONE
        }
        // phone keep-alive through the real protocol path
        if self.phone_connected && now >= self.next_heartbeat_us {
            self.next_heartbeat_us = now + self.cfg.heartbeat_s as u64 * 1_000_000;
            let _ = self.send(CommandBody::GetStatus);
        }
        if let Some(p) = self.pump.as_mut() {
            p.tick();
        }
        self.ticks += 1;
        // a reset raised during the tick (brown-out / watchdog) makes the rest meaningless
        if self.world.borrow().reset_pending.is_some() {
            return;
        }
        self.housekeeping();
    }

    fn housekeeping(&mut self) {
        let Some(pump) = self.pump.as_ref() else { return };
        let pol = &mut self.policy;
        let mut w = self.world.borrow_mut();
        let next = pump.log().next_id();
        if next + EVT_CEILING_HEADROOM > pol.evt_ceiling {
            pol.evt_ceiling += EVT_CEILING_STEP;
            w.flash.queue(Stored::EvtCeiling(pol.evt_ceiling));
        }
        let res = pump.reservoir();
        if res.is_filled() {
            let fill = res.fill_level().0;
            let consumed = res.consumed().0;
            if fill != pol.res_fill || consumed + RES_TRIGGER_STEPS >= pol.res_persisted_consumed {
                let stored = consumed.saturating_add(RES_MARGIN_STEPS);
                w.flash.queue(Stored::Reservoir(fill, stored));
                pol.res_fill = fill;
                pol.res_persisted_consumed = stored;
            }
        }
        let p = pump.pod();
        let cur = PodRec {
            pair_id: p.pair_id,
            role: p.role,
            active: p.active,
            activation_id: p.activation_id,
            wear_s: if p.active { (p.wear.0 / 1000) as u32 + WEAR_MARGIN_S } else { 0 },
        };
        pol.ticks_since_pod_write = pol.ticks_since_pod_write.saturating_add(1);
        let changed = match pol.pod {
            None => cur.pair_id != 0,
            Some(o) => o.pair_id != cur.pair_id || o.role != cur.role || o.active != cur.active || o.activation_id != cur.activation_id,
        };
        let wear_due = cur.active && pol.ticks_since_pod_write >= WEAR_WRITE_PERIOD_S;
        if changed || wear_due {
            w.flash.queue(Stored::Pod(cur));
            pol.pod = Some(cur);
            pol.ticks_since_pod_write = 0;
        }
    }

    // ---- the phone ------------------------------------------------------------------------------
    /// Send one command through the protocol path (CRC, replay protection, TLV codec).
    /// `None` = no answer (pod off, booting or hung).
    pub fn send(&mut self, body: CommandBody) -> Option<Response> {
        let (t_us, hung) = {
            let w = self.world.borrow();
            (w.t_us, w.hung || !w.power_on || w.reset_pending.is_some())
        };
        if hung || self.pump.is_none() {
            return None;
        }
        self.seq = if self.seq >= proto::SEQ_MAX - 1 { 1 } else { self.seq + 1 };
        let tod = (self.cfg.start_tod_ms as u64 + t_us / 1000) % 86_400_000;
        let cmd = Command { seq: self.seq, time_of_day_ms: Some(tod as u32), body };
        let mut payload = [0u8; FRAME_MAX];
        let n = proto::encode_command_payload(&cmd, &mut payload).ok()?;
        let mut frame = [0u8; FRAME_MAX];
        let fl = self.phone.seal(false, cmd.body.type_id(), cmd.seq, false, &payload[..n], &mut frame).ok()?;
        let mut out = [0u8; FRAME_MAX];
        let pump = self.pump.as_mut()?;
        let ol = pump.handle_frame(&mut self.session, &frame[..fl], &mut out).ok()?;
        let f = proto::decode_frame(&out[..ol]).ok()?;
        proto::decode_response(f.type_ & !proto::RSP_BIT, f.seq, f.payload).ok()
    }

    /// Result code of a command (0 = OK), `255` if the pod did not answer.
    pub fn cmd(&mut self, body: CommandBody) -> u8 {
        self.send(body).map_or(255, |r| r.result)
    }

    /// Raw bytes in, raw bytes out: the hook for an external end-to-end harness (BLE frame level).
    pub fn handle_raw_frame(&mut self, frame: &[u8]) -> Option<Vec<u8>> {
        let hung = {
            let w = self.world.borrow();
            w.hung || !w.power_on
        };
        if hung {
            return None;
        }
        let pump = self.pump.as_mut()?;
        let mut out = [0u8; FRAME_MAX];
        let n = pump.handle_frame(&mut self.session, frame, &mut out).ok()?;
        Some(out[..n].to_vec())
    }

    /// Status via the protocol (what an app would see).
    pub fn status(&mut self) -> Option<proto::Status> {
        self.send(CommandBody::GetStatus).and_then(|r| r.status)
    }

    pub fn pump(&self) -> &Pump<SimHal> {
        self.pump.as_ref().expect("pod is running")
    }

    /// Firmware-bug injection: issue forward pulses directly on the HAL, bypassing the core's
    /// supervisor. Only the hardware interlock can stop this.
    pub fn force_forward_steps(&mut self, n: u32) -> u32 {
        use openpatch_core::Hal;
        let mut h = SimHal(self.world.clone());
        h.motor_enable(true);
        let r = h.motor_step(Pulses(n)).0;
        h.motor_enable(false);
        r
    }
}
