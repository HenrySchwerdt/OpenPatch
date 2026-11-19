//! Bench test mode: gravimetric delivery sequences (N boluses of X U with a pause), WATER ONLY.
//!
//! Every dose goes through the normal `Pump::bolus` path, so all safety limits (max bolus, 15 U/h
//! window, dock gate, reservoir, encoder checks) stay in force. The runner only paces the pulses
//! and produces CSV rows (RTT/defmt and the BLE log characteristic).

use crate::delivery::BasalSchedule;
use crate::hal::Hal;
use crate::pump::Pump;
use crate::units::*;
use core::fmt::Write;
use openpatch_proto::Error;

/// Fixed pair id of the bench controller (it pairs with itself, no phone needed).
pub const BENCH_PAIR_ID: u32 = 0x0BE7_C001;
pub const BENCH_ACTIVATION_ID: u32 = 1;
pub const CSV_HEADER: &str = "t_ms,pulse,cmd_mu,delivered_pulses,delivered_mu,angle_counts,faults";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BenchConfig {
    pub pulses: u16,
    pub amount: MilliUnits,
    /// Pause after each pulse (settling / weighing time on the scale).
    pub pause: Millis,
}

impl BenchConfig {
    /// `amount` must be a multiple of 0.05 U; `pulses` >= 1.
    pub fn validate(&self) -> Result<(), Error> {
        if self.pulses == 0 || self.amount.0 == 0 || self.amount.0 % crate::limits::BOLUS_GRANULARITY.0 != 0 {
            return Err(Error::BadArg);
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CsvRow {
    pub t_ms: u64,
    /// 1-based pulse number.
    pub pulse: u16,
    /// Cumulative commanded amount.
    pub cmd_mu: u32,
    pub delivered_steps: u32,
    pub delivered_mu: u32,
    pub angle_counts: i64,
    pub faults: u16,
}

impl CsvRow {
    pub fn write_csv<W: Write>(&self, w: &mut W) -> core::fmt::Result {
        write!(
            w,
            "{},{},{},{},{},{},{}",
            self.t_ms, self.pulse, self.cmd_mu, self.delivered_steps, self.delivered_mu, self.angle_counts, self.faults
        )
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BenchState {
    Idle,
    Dosing { pulse: u16 },
    Pausing { pulse: u16, until: Millis },
    Done,
    Failed(Error),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BenchEvent {
    None,
    /// A pulse finished: log this row.
    Row(CsvRow),
    Finished,
    Failed(Error),
}

pub struct BenchRunner {
    cfg: BenchConfig,
    state: BenchState,
}

/// Pair the bench controller with itself, fill the (water) reservoir, activate with a zero basal and
/// resume. After this, `Pump::bolus` works. Requires the DOCKED input to be asserted.
pub fn prepare<H: Hal>(pump: &mut Pump<H>, fill: MilliUnits) -> Result<(), Error> {
    if pump.pod().pair_id == 0 {
        pump.set_pairing(BENCH_PAIR_ID, crate::pod::Role::A as u8)?;
    }
    if pump.engine().is_suspended() && !pump.reservoir().is_filled() {
        pump.fill(fill)?;
    }
    if !pump.pod().active {
        let a = crate::pod::ActivateArgs {
            pair_id: pump.pod().pair_id,
            activation_id: BENCH_ACTIVATION_ID,
            schedule: BasalSchedule::flat(MilliUnitsPerHour(0)),
            temp: None,
        };
        pump.activate(&a)?;
    }
    if pump.prime_required() {
        // mandatory priming after a fill (bench: 0.2 U of water through the connector)
        let n = pump.pulse_cal().mu_to_pulses(MilliUnits(200));
        pump.prime(n)?;
    }
    pump.resume()
}

impl BenchRunner {
    pub fn new(cfg: BenchConfig) -> Result<Self, Error> {
        cfg.validate()?;
        Ok(Self { cfg, state: BenchState::Idle })
    }

    pub fn state(&self) -> BenchState {
        self.state
    }
    pub fn config(&self) -> BenchConfig {
        self.cfg
    }
    pub fn is_finished(&self) -> bool {
        matches!(self.state, BenchState::Done | BenchState::Failed(_))
    }

    /// Abort at any time (also stops a running bolus).
    pub fn abort<H: Hal>(&mut self, pump: &mut Pump<H>) {
        let _ = pump.cancel_bolus();
        if !self.is_finished() {
            self.state = BenchState::Failed(Error::Suspended);
        }
    }

    /// Call after every `Pump::tick`. Starts pulses, detects their completion, paces the pauses.
    pub fn step<H: Hal>(&mut self, pump: &mut Pump<H>, now: Millis) -> BenchEvent {
        match self.state {
            BenchState::Idle => self.start_pulse(pump, 1),
            BenchState::Dosing { pulse } => {
                if !pump.sv_ok() {
                    return self.fail(Error::Fault);
                }
                if pump.engine().bolus_active() {
                    return BenchEvent::None;
                }
                // The engine finished handing out steps. A bolus cancelled by undocking also ends here.
                let rep = pump.engine().report();
                let row = CsvRow {
                    t_ms: now.0,
                    pulse,
                    cmd_mu: self.cfg.amount.0 * pulse as u32,
                    delivered_steps: rep.delivered_steps.0,
                    delivered_mu: rep.delivered.0,
                    angle_counts: pump.supervisor().last_angle().0,
                    faults: pump.supervisor().faults().bits(),
                };
                self.state = BenchState::Pausing { pulse, until: Millis(now.0 + self.cfg.pause.0) };
                BenchEvent::Row(row)
            }
            BenchState::Pausing { pulse, until } => {
                if now < until {
                    return BenchEvent::None;
                }
                if pulse >= self.cfg.pulses {
                    self.state = BenchState::Done;
                    return BenchEvent::Finished;
                }
                self.start_pulse(pump, pulse + 1)
            }
            BenchState::Done => BenchEvent::Finished,
            BenchState::Failed(e) => BenchEvent::Failed(e),
        }
    }

    fn fail(&mut self, e: Error) -> BenchEvent {
        self.state = BenchState::Failed(e);
        BenchEvent::Failed(e)
    }

    fn start_pulse<H: Hal>(&mut self, pump: &mut Pump<H>, pulse: u16) -> BenchEvent {
        match pump.bolus(self.cfg.amount) {
            Ok(()) => {
                self.state = BenchState::Dosing { pulse };
                BenchEvent::None
            }
            Err(e) => self.fail(e),
        }
    }
}
