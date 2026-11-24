//! The safety task: sole owner of the `Pump` (and through it of the motor, interlock and TPL5010
//! DONE pins). It runs on the P5 interrupt executor, so the BLE host in thread mode cannot delay it.
//!
//! * 1 s tick (`Ticker`): `Pump::tick()` (which services the watchdog last), then the bench runner,
//!   then housekeeping (persistence snapshots, status flags),
//! * frames from the BLE task (`FRAME_IN`) go through `Pump::handle_frame`, the answer goes to
//!   `FRAME_OUT`. Before a frame is executed its seq is made durable (ceiling, see `config.rs`),
//! * button events (`UI_CMD`) and bench commands (`BENCH_CMD`).
//!
//! Nothing in this task awaits flash: writes are requested through `PERSIST` (non-blocking) except
//! the seq ceiling, where the command is held back until the write is durable (bounded wait).
use core::sync::atomic::Ordering;
use embassy_futures::select::{select4, Either4};
use embassy_time::{with_timeout, Duration, Instant, Ticker};
use openpatch_core::units::{Millis, MilliUnits, Pulses};
use openpatch_core::persist::{ReservoirPolicy, SchedRec, TempRec};
use openpatch_core::{Pump, Role};
use openpatch_proto::ccm_impl::AesCcm;
use openpatch_proto::{decode_frame, Session, FRAME_MAX, SEQ_MAX};

use crate::bench_mode::BenchCtl;
use crate::config::*;
use crate::hal::BoardHal;
use crate::shared::*;
use crate::storage::{PersistMsg, PodRec};

/// Persistence policy state of the safety task.
struct Policy {
    seq_ceiling: u16,
    last_ceiling_write: Instant,
    evt_ceiling: u32,
    /// Reservoir snapshot policy (core logic, F3: the margin is not re-added on every boot).
    res: ReservoirPolicy,
    pod: Option<PodRec>,
    ticks_since_pod_write: u32,
    /// Last schedule / temp basal records handed to the flash task (F2).
    sched: SchedRec,
    temp: TempRec,
}

impl Policy {
    fn housekeeping(&mut self, pump: &Pump<BoardHal>) {
        // event id ceiling
        let next = pump.log().next_id();
        if next + EVT_CEILING_HEADROOM > self.evt_ceiling {
            self.evt_ceiling += EVT_CEILING_STEP;
            let _ = PERSIST.try_send(PersistMsg::EvtCeiling(self.evt_ceiling));
        }
        // reservoir: persisted value >= reality, so the model after a power loss can only be LOWER; the margin is added once
        // per run that consumed insulin, not on every boot (`ReservoirPolicy`)
        if let Some((fill_mu, stored)) = self.res.next_write(pump.reservoir()) {
            if PERSIST.try_send(PersistMsg::Reservoir { fill_mu, consumed_steps: stored }).is_ok() {
                self.res.written(fill_mu, stored);
            }
        }
        // basal schedule and temp basal: only when they change
        let sr = pump.schedule_record();
        if sr != self.sched && PERSIST.try_send(PersistMsg::Schedule(sr)).is_ok() {
            self.sched = sr;
        }
        let tr = pump.temp_record();
        if tr != self.temp && PERSIST.try_send(PersistMsg::Temp(tr)).is_ok() {
            self.temp = tr;
        }
        // pod state (wear stored as an upper bound)
        let p = pump.pod();
        let cur = PodRec {
            pair_id: p.pair_id,
            role: p.role,
            active: p.active,
            activation_id: p.activation_id,
            wear_s: if p.active { (p.wear.0 / 1000) as u32 + WEAR_MARGIN_S } else { 0 },
        };
        self.ticks_since_pod_write = self.ticks_since_pod_write.saturating_add(1);
        let changed = match self.pod {
            None => cur.pair_id != 0,
            Some(o) => o.pair_id != cur.pair_id || o.role != cur.role || o.active != cur.active || o.activation_id != cur.activation_id,
        };
        let wear_due = cur.active && self.ticks_since_pod_write >= WEAR_WRITE_PERIOD_S;
        if (changed || wear_due) && PERSIST.try_send(PersistMsg::Pod(cur)).is_ok() {
            self.pod = Some(cur);
            self.ticks_since_pod_write = 0;
        }
    }

    /// Make `seq` durable before the frame is executed. `false` = refuse the frame.
    async fn ensure_seq(&mut self, seq: u16) -> bool {
        if seq > SEQ_MAX || seq < self.seq_ceiling {
            return true; // invalid seqs are rejected by the session; below the ceiling = already durable
        }
        // limit flash wear from spamming high seqs
        if Instant::now() - self.last_ceiling_write < Duration::from_millis(250) {
            defmt::warn!("seq ceiling write rate limit: frame dropped");
            return false;
        }
        let new = seq.saturating_add(SEQ_CEILING_STEP);
        SEQ_ACK.reset();
        PERSIST.send(PersistMsg::SeqCeiling(new)).await;
        self.last_ceiling_write = Instant::now();
        let waited = with_timeout(Duration::from_millis(SEQ_PERSIST_TIMEOUT_MS), async {
            loop {
                if SEQ_ACK.wait().await >= new {
                    return;
                }
            }
        })
        .await;
        if waited.is_err() {
            defmt::error!("seq ceiling {} not durable in time: frame refused", new);
            return false;
        }
        self.seq_ceiling = new;
        true
    }
}

/// Header peek: `version | type | flags | seq(2, LE) | len(2)`. Only frames that pass length,
/// CRC and version checks may extend the ceiling.
fn peek_seq(frame: &[u8]) -> Option<u16> {
    decode_frame(frame).ok().map(|f| f.seq)
}

pub struct BootState {
    pub seq_ceiling: Option<u16>,
    pub evt_ceiling: u32,
    pub reservoir: Option<(u32, u32)>,
    pub pod: Option<PodRec>,
    pub sched: Option<SchedRec>,
    pub temp: Option<TempRec>,
}

/// Restore everything the platform persisted into a fresh `Pump` and `Session`.
pub fn restore(pump: &mut Pump<BoardHal>, session: &mut Session<AesCcm>, b: &BootState) {
    if let Some((fill, consumed)) = b.reservoir {
        pump.reservoir_mut().restore(MilliUnits(fill), Pulses(consumed));
    }
    if let Some(p) = b.pod {
        if Role::from_u8(p.role).is_ok() || p.pair_id == 0 {
            pump.restore_pod(p.pair_id, p.role, p.active, p.activation_id, Millis(p.wear_s as u64 * 1000));
        }
    }
    // F2: the basal schedule and a running temp basal come back; if the schedule is missing or invalid the pod stays
    // without one and `Resume` is refused with `NoSchedule`
    if let Some(s) = b.sched.and_then(|r| SchedRec::decode(r.as_bytes())) {
        if pump.restore_schedule(&s).is_err() {
            defmt::warn!("stored basal schedule is outside the limits: not restored");
        }
    }
    if let Some(t) = b.temp {
        pump.restore_temp(t);
    }
    if let Some(c) = b.seq_ceiling {
        // seqs below the ceiling may have been accepted before the reset
        session.restore_last_seq(c.saturating_sub(1));
    }
}

#[embassy_executor::task]
pub async fn safety_task(mut pump: Pump<BoardHal>, mut session: Session<AesCcm>, boot: BootState) -> ! {
    let mut policy = Policy {
        seq_ceiling: boot.seq_ceiling.unwrap_or(0),
        last_ceiling_write: Instant::now() - Duration::from_secs(10),
        // `Pump::new` was given `boot.evt_ceiling` as the next id: ids from there on are above the
        // persisted ceiling until the extension below is durable, so extend right away.
        evt_ceiling: boot.evt_ceiling + EVT_CEILING_STEP,
        res: ReservoirPolicy::at_boot(RES_MARGIN_STEPS, RES_TRIGGER_STEPS, boot.reservoir),
        pod: boot.pod,
        ticks_since_pod_write: 0,
        sched: boot.sched.unwrap_or(SchedRec::NONE),
        temp: boot.temp.unwrap_or(TempRec::NONE),
    };
    let _ = PERSIST.try_send(PersistMsg::EvtCeiling(policy.evt_ceiling));

    let mut bench = BenchCtl::new();
    #[cfg(feature = "bench-autostart")]
    bench.start(BENCH_PULSES as u16, BENCH_AMOUNT_MU, BENCH_PAUSE_MS);

    let mut ticker = Ticker::every(Duration::from_millis(TICK_PERIOD_MS));
    let mut good_ticks: u32 = 0;
    let mut boot_ok_sent = false;
    let mut last_overruns = pump.tick_overruns();
    defmt::info!("safety task running, tick {} ms", TICK_PERIOD_MS);

    loop {
        let event = select4(ticker.next(), FRAME_IN.receive(), UI_CMD.receive(), BENCH_CMD.receive()).await;
        // A finished key agreement (or a closed link) replaces the session BEFORE the frame that woke us is opened.
        crate::crypto::apply_session_event(&mut session);
        match event {
            Either4::First(()) => {
                pump.tick();
                let now = pump.hal_mut().time_ms_now();
                bench.step(&mut pump, now);
                drain_notifications(&mut pump, &mut session);
                policy.housekeeping(&pump);
                publish_status(&pump);

                // "good tick" for the DFU confirmation: ran in time, interlock verified
                let overruns = pump.tick_overruns();
                if !pump.hal().interlock_failed() && overruns == last_overruns {
                    good_ticks = good_ticks.saturating_add(1);
                } else {
                    good_ticks = 0;
                }
                last_overruns = overruns;
                if good_ticks >= BOOT_OK_TICKS && !boot_ok_sent {
                    boot_ok_sent = true;
                    BOOT_OK.signal(());
                }
            }
            Either4::Second(frame) => {
                let bytes = frame.bytes();
                if let Some(seq) = peek_seq(bytes) {
                    if !policy.ensure_seq(seq).await {
                        continue;
                    }
                }
                let mut out = [0u8; FRAME_MAX];
                match pump.handle_frame(&mut session, bytes, &mut out) {
                    Ok(n) => {
                        if let Some(f) = Frame::from_slice(&out[..n]) {
                            if FRAME_OUT.try_send(f).is_err() {
                                defmt::warn!("response dropped (queue full / nobody connected)");
                            }
                        }
                    }
                    Err(e) => defmt::debug!("frame dropped silently: {}", e),
                }
                drain_notifications(&mut pump, &mut session);
                policy.housekeeping(&pump);
                publish_status(&pump);
            }
            Either4::Third(cmd) => {
                match cmd {
                    UiCmd::SilenceAlarm => pump.silence_alarm(),
                    UiCmd::EmergencyStop => {
                        pump.emergency_stop();
                        bench.abort(&mut pump);
                    }
                }
                publish_status(&pump);
            }
            Either4::Fourth(cmd) => {
                match cmd {
                    BenchCmd::Start { pulses, amount_mu, pause_ms } => bench.start(pulses, amount_mu, pause_ms),
                    BenchCmd::Abort => bench.abort(&mut pump),
                }
            }
        }
    }
}

/// Alert characteristic: draw progress / done / stalled / fault frames (type 0x90, own seq counter,
/// encrypted with nonce direction 2 when a session key exists).
fn drain_notifications(pump: &mut Pump<BoardHal>, session: &mut Session<AesCcm>) {
    let encrypt = !cfg!(feature = "dev-plaintext");
    loop {
        let mut out = [0u8; FRAME_MAX];
        match pump.notification_frame(session, encrypt, &mut out) {
            None => break,
            Some(Ok(n)) => {
                if let Some(f) = Frame::from_slice(&out[..n]) {
                    if ALERT_OUT.try_send(f).is_err() {
                        defmt::warn!("alert notification dropped (queue full)");
                    }
                }
            }
            Some(Err(e)) => defmt::warn!("notification frame not sealed: {}", e),
        }
    }
}

fn publish_status(pump: &Pump<BoardHal>) {
    DELIVERING.store(pump.engine().bolus_active(), Ordering::Relaxed);
    FAULT_LATCHED.store(!pump.supervisor().faults().is_empty(), Ordering::Relaxed);
}
