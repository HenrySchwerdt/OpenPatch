//! Bench test mode (WATER ONLY, gravimetric sequences). Runs inside the safety task, stepped after
//! every `Pump::tick`. Every dose is a normal `Pump::bolus`, so all core limits stay active
//! (max bolus, 15 U/h window, 1.5 U/min, dock gate, reservoir, encoder and current checks).
//!
//! Output: one CSV row per pulse (`openpatch_core::bench::CSV_HEADER` / `CsvRow::write_csv`) as a
//! defmt/RTT line prefixed `CSV ` and as a notification on the BLE bench log characteristic.
//! Lines starting with `#` are status comments.
use core::fmt::Write;
use core::sync::atomic::Ordering;
use openpatch_core::bench::{self, BenchConfig, BenchEvent, BenchRunner, CSV_HEADER};
use openpatch_core::units::{Millis, MilliUnits};
use openpatch_core::Pump;
use openpatch_core::Error;

use crate::config::*;
use crate::hal::BoardHal;
use crate::shared::{CsvLine, BENCH_ACTIVE, CSV_OUT};

enum Phase {
    Idle,
    /// Waiting for DOCKED / prepare to succeed.
    Preparing(BenchConfig),
    Running(BenchRunner),
}

pub struct BenchCtl {
    phase: Phase,
    waiting_reported: bool,
}

pub fn emit(line: CsvLine) {
    defmt::info!("CSV {=str}", line.as_str());
    // The BLE log is best effort: dropped when nobody listens / the queue is full.
    let _ = CSV_OUT.try_send(line);
}

fn note(args: core::fmt::Arguments<'_>) {
    let mut l = CsvLine::new();
    let _ = l.write_fmt(args);
    emit(l);
}

impl BenchCtl {
    pub const fn new() -> Self {
        Self { phase: Phase::Idle, waiting_reported: false }
    }

    pub fn is_active(&self) -> bool {
        !matches!(self.phase, Phase::Idle)
    }

    /// Request a sequence. Validation is the core's (`amount` multiple of 0.05 U, `pulses` >= 1).
    pub fn start(&mut self, pulses: u16, amount_mu: u32, pause_ms: u32) {
        if self.is_active() {
            note(format_args!("# rejected: bench sequence already running"));
            return;
        }
        let cfg = BenchConfig { pulses, amount: MilliUnits(amount_mu), pause: Millis(pause_ms as u64) };
        if cfg.validate().is_err() {
            note(format_args!("# rejected: invalid config (amount must be a multiple of 50 mU, pulses >= 1)"));
            return;
        }
        self.waiting_reported = false;
        self.phase = Phase::Preparing(cfg);
        BENCH_ACTIVE.store(true, Ordering::Relaxed);
        note(format_args!("# bench start pulses={} amount_mu={} pause_ms={}", pulses, amount_mu, pause_ms));
    }

    pub fn abort(&mut self, pump: &mut Pump<BoardHal>) {
        if let Phase::Running(r) = &mut self.phase {
            r.abort(pump);
        } else {
            let _ = pump.cancel_bolus();
        }
        if self.is_active() {
            note(format_args!("# bench aborted"));
        }
        self.phase = Phase::Idle;
        BENCH_ACTIVE.store(false, Ordering::Relaxed);
    }

    fn finish(&mut self, msg: core::fmt::Arguments<'_>) {
        note(msg);
        self.phase = Phase::Idle;
        BENCH_ACTIVE.store(false, Ordering::Relaxed);
    }

    /// Call after every `Pump::tick`.
    pub fn step(&mut self, pump: &mut Pump<BoardHal>, now: Millis) {
        match &mut self.phase {
            Phase::Idle => {}
            Phase::Preparing(cfg) => {
                let cfg = *cfg;
                match bench::prepare(pump, MilliUnits(BENCH_FILL_MU)) {
                    Ok(()) => match BenchRunner::new(cfg) {
                        Ok(r) => {
                            note(format_args!("{}", CSV_HEADER));
                            self.phase = Phase::Running(r);
                        }
                        Err(e) => self.finish(format_args!("# failed: runner rejected config, code={}", e.code())),
                    },
                    Err(Error::NotDocked) => {
                        if !self.waiting_reported {
                            self.waiting_reported = true;
                            note(format_args!("# waiting for DOCKED"));
                        }
                    }
                    Err(e) => self.finish(format_args!("# failed: prepare code={}", e.code())),
                }
            }
            Phase::Running(r) => match r.step(pump, now) {
                BenchEvent::None => {}
                BenchEvent::Row(row) => {
                    let mut l = CsvLine::new();
                    let _ = row.write_csv(&mut l);
                    emit(l);
                }
                BenchEvent::Finished => self.finish(format_args!("# bench done")),
                BenchEvent::Failed(e) => self.finish(format_args!("# bench failed code={}", e.code())),
            },
        }
    }
}
