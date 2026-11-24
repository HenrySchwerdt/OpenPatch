//! Burst stepping that respects the cell's peak current (cup board v4, `electronics/v010/INTERLOCK.md` I.2).
//!
//! The motor (NFP-608-26.45, 26.5 ohm per phase, no chopper on the DRV8838) draws 0.36 A at 4.96 V = about 1.74 W while it is
//! energised. Behind the 88 % boost that is 0.58 A at a 3.4 V cell and 0.66 A at 3.0 V: **6 to 10 C on a 60 to 90 mAh pouch cell**,
//! and the bulk capacitors do not change that (they bridge microseconds, a burst lasts tens of milliseconds). So steps go in
//! short bursts with rest gaps: the motor is energised only for the burst (`phase_drive::drive_burst` brakes at the end), the
//! cell recovers in the gap, and the average cell current stays below an average limit.
//!
//! Everything here is a pure function of configurable parameters ([`CellParams`], [`MotorLoad`]). The defaults describe the
//! Ampul 301030 of `docs/BUY-LIST.md` / `mechanical/battery-selection.md` (3.7 V, 3.0 x 10 x 30 mm, **90 mAh listed, 60 mAh
//! realistic**, integrated protection chip). The vendor page states **no discharge rate**: every limit below is a PLACEHOLDER
//! chosen conservatively from the numbers above and has to be confirmed on the bench (cell voltage under the burst, cell
//! temperature, PCM trip); change them in [`CellParams`], not in the logic.

use crate::battery::{start_gate, MotorSupplyLimits};

/// Electrical limits of the cell for pulsed discharge. All fields configurable.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct CellParams {
    /// Realistic capacity in mAh (informational, used for the C-rate report): 60 for the Ampul 301030 (90 listed).
    pub capacity_mah: u16,
    /// Highest cell current allowed during a burst, mA. A burst that would draw more is refused.
    pub max_pulse_ma: u16,
    /// Longest burst (energised time including the alignment period), ms.
    pub max_pulse_ms: u16,
    /// Average cell current over burst + rest, mA (1 C of the listed 90 mAh by default).
    pub avg_limit_ma: u16,
    /// Shortest rest gap after any burst, ms (cell voltage recovery, the protection chip's overcurrent timer resets).
    pub min_rest_ms: u16,
    /// Rest-voltage start threshold and loaded-voltage abort threshold (SPICE F2/F3; interim until the cell resistance is measured).
    /// Plan with [`plan_burst`], guard the running burst with `battery::LoadGuard::new(cell.supply)`.
    pub supply: MotorSupplyLimits,
}

impl CellParams {
    /// Ampul 301030 defaults (PLACEHOLDERS, see the module documentation).
    pub const AMPUL_301030: CellParams =
        CellParams {
            capacity_mah: 60,
            max_pulse_ma: 700,
            max_pulse_ms: 150,
            avg_limit_ma: 90,
            min_rest_ms: 250,
            supply: MotorSupplyLimits::DEFAULT,
        };
}

impl Default for CellParams {
    fn default() -> Self {
        Self::AMPUL_301030
    }
}

/// What the motor takes from the boost output while energised.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct MotorLoad {
    /// Power at the boost output while both windings are energised, mW (2 x 0.18 A x 4.96 V = 1.74 W after the bridge drop).
    pub power_mw: u32,
    /// Boost converter efficiency at that load, percent (TPS61023: about 88 to 90 % at 0.3 A).
    pub boost_eff_pct: u8,
}

impl MotorLoad {
    /// NFP-608-26.45-SGM through the DRV8838 bridges and the TPS61023 (INTERLOCK.md I.2 / I.6).
    pub const NFP_608_26_45: MotorLoad = MotorLoad { power_mw: 1_740, boost_eff_pct: 88 };
}

impl Default for MotorLoad {
    fn default() -> Self {
        Self::NFP_608_26_45
    }
}

/// Cell current in mA while the motor is energised at a cell voltage of `vbat_mv`: `P / (eff x V)`, rounded up.
/// `vbat_mv == 0` or `boost_eff_pct == 0` gives `u32::MAX` (nothing can supply that).
pub const fn cell_current_ma(load: MotorLoad, vbat_mv: u16) -> u32 {
    if vbat_mv == 0 || load.boost_eff_pct == 0 {
        return u32::MAX;
    }
    let den = load.boost_eff_pct as u64 * vbat_mv as u64;
    let num = load.power_mw as u64 * 100_000;
    ((num + den - 1) / den) as u32
}

/// A planned burst.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct BurstPlan {
    /// Steps of one full burst.
    pub steps: u32,
    /// Energised time of one full burst, ms (alignment period + steps).
    pub burst_ms: u32,
    /// Rest after a full burst, ms.
    pub rest_ms: u32,
    /// Cell current during the burst, mA.
    pub cell_ma: u32,
}

impl BurstPlan {
    /// Average cell current over one burst + rest, mA (rounded up).
    pub fn average_ma(&self) -> u32 {
        let cycle = (self.burst_ms + self.rest_ms) as u64;
        if cycle == 0 {
            return 0;
        }
        ((self.cell_ma as u64 * self.burst_ms as u64 + cycle - 1) / cycle) as u32
    }
    /// Whole safety ticks (`tick_ms`, nominal 1000) between the starts of two bursts: `ceil((burst + rest) / tick)`, at least 1.
    pub fn ticks_per_cycle(&self, tick_ms: u32) -> u32 {
        if tick_ms == 0 {
            return 1;
        }
        ((self.burst_ms + self.rest_ms + tick_ms - 1) / tick_ms).max(1)
    }
}

/// Why no burst can be planned.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum BurstRefusal {
    /// Resting cell voltage below the start threshold (`cell.supply`, default 3.7 V; never below the 3.4 V boost enable minimum):
    /// no motor start. Raise `A-A0-004` instance 2 (`battery::rest_refusal_raise`).
    BatteryLow,
    /// The burst current at this cell voltage exceeds `max_pulse_ma`.
    CellCannotSupply,
    /// The step period is so long that not even one step fits into `max_pulse_ms`, or the period is 0.
    PeriodOutOfRange,
}

/// Rest after a burst of `burst_ms` at `cell_ma`: long enough that the average over burst + rest is at most
/// `avg_limit_ma`, and never shorter than `min_rest_ms`. `rest = ceil(burst x (I / I_avg - 1))`.
pub fn rest_for_burst(cell: CellParams, cell_ma: u32, burst_ms: u32) -> u32 {
    let avg = cell.avg_limit_ma.max(1) as u64;
    let by_average = if cell_ma as u64 > avg {
        let num = burst_ms as u64 * (cell_ma as u64 - avg);
        ((num + avg - 1) / avg) as u32
    } else {
        0
    };
    by_average.max(cell.min_rest_ms as u32)
}

/// Plan the standard burst for a step period of `period_us` (5000 us at 200 pps) at cell voltage `vbat_mv`.
///
/// * the burst never exceeds `cell.max_pulse_ms` (alignment period included) nor `max_steps` (the supervisor's step budget
///   per armed window, 32);
/// * refused when `vbat_mv` (the cell at REST, no load) is below `cell.supply.rest_min_mv` (default 3.7 V, interim until the cell
///   resistance is measured; `battery::start_gate` also enforces the 3.4 V boost enable minimum, F3) and when the burst current
///   exceeds `cell.max_pulse_ma`.
pub fn plan_burst(
    cell: CellParams,
    load: MotorLoad,
    vbat_mv: u16,
    period_us: u32,
    max_steps: u32,
) -> Result<BurstPlan, BurstRefusal> {
    if start_gate(cell.supply, vbat_mv, false).is_err() {
        return Err(BurstRefusal::BatteryLow);
    }
    let cell_ma = cell_current_ma(load, vbat_mv);
    if cell_ma > cell.max_pulse_ma as u32 {
        return Err(BurstRefusal::CellCannotSupply);
    }
    if period_us == 0 {
        return Err(BurstRefusal::PeriodOutOfRange);
    }
    // time budget in periods: the first period is the alignment period of `drive_burst`
    let periods = (cell.max_pulse_ms as u64 * 1_000 / period_us as u64) as u32;
    if periods < 2 {
        return Err(BurstRefusal::PeriodOutOfRange);
    }
    let steps = (periods - 1).min(max_steps);
    if steps == 0 {
        return Err(BurstRefusal::PeriodOutOfRange);
    }
    let burst_ms = burst_ms_for(steps, period_us);
    Ok(BurstPlan { steps, burst_ms, rest_ms: rest_for_burst(cell, cell_ma, burst_ms), cell_ma })
}

/// Energised time of a burst of `steps` steps: `(steps + 1)` periods (alignment period included), rounded up to ms.
pub const fn burst_ms_for(steps: u32, period_us: u32) -> u32 {
    (((steps as u64 + 1) * period_us as u64 + 999) / 1_000) as u32
}

/// One chunk of a split request.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct Chunk {
    pub steps: u32,
    /// Rest to keep after this chunk, ms (for the last chunk too: the next request starts after it).
    pub rest_ms: u32,
}

/// Splits `total` steps into bursts of `plan.steps` (the last one shorter, with its own, shorter rest from
/// [`rest_for_burst`]). `period_us` is the step period the plan was made for.
#[derive(Clone, Copy, Debug)]
pub struct Chunks {
    left: u32,
    plan: BurstPlan,
    cell: CellParams,
    period_us: u32,
}

impl Chunks {
    pub fn new(total: u32, plan: BurstPlan, cell: CellParams, period_us: u32) -> Self {
        Self { left: total, plan, cell, period_us }
    }
}

impl Iterator for Chunks {
    type Item = Chunk;
    fn next(&mut self) -> Option<Chunk> {
        if self.left == 0 || self.plan.steps == 0 {
            return None;
        }
        let n = self.left.min(self.plan.steps);
        self.left -= n;
        let rest_ms = if n == self.plan.steps {
            self.plan.rest_ms
        } else {
            rest_for_burst(self.cell, self.plan.cell_ma, burst_ms_for(n, self.period_us))
        };
        Some(Chunk { steps: n, rest_ms })
    }
}

/// Wall-clock time for `total` steps in bursts, ms: all bursts, and the rests between them (no rest after the last).
pub fn total_time_ms(total: u32, plan: BurstPlan, cell: CellParams, period_us: u32) -> u64 {
    let mut t = 0u64;
    let mut it = Chunks::new(total, plan, cell, period_us).peekable();
    while let Some(c) = it.next() {
        t += burst_ms_for(c.steps, period_us) as u64;
        if it.peek().is_some() {
            t += c.rest_ms as u64;
        }
    }
    t
}
