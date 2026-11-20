//! Battery voltage from the SAADC `VDDHDIV5` channel, and the battery thresholds of the cup board v4.
//!
//! On the 45-part board the cell is wired to the HJ-840's `VDDH` pad (high-voltage mode, no LDO, `FIRMWARE-PINMAP.md` "v4 HJ-840
//! pin table"), so there is no sense divider and no sense pin: the SAADC measures `VDDH / 5` on the internal `VDDHDIV5` input
//! (nRF52840 product specification, SAADC `CH[n].PSELP = 0x0D`). The conversion is a pure function so it can be tested on the host.
//!
//! Conversion (single ended, internal 0.6 V reference, gain 1/6, i.e. a 3.6 V full scale at the input):
//! `V(VDDH) = raw x 3600 x 5 / 2^resolution` mV. At 12 bit one LSB is 4.39 mV of cell voltage, at 14 bit 1.10 mV. Negative results
//! (noise around 0 in single ended mode) clamp to 0.

use crate::diag::{codes, Raise};

/// SAADC full scale at the input with the internal reference and gain 1/6 (0.6 V x 6), mV.
pub const SAADC_FULL_SCALE_MV: u32 = 3_600;
/// `VDDHDIV5` divides VDDH by 5.
pub const VDDHDIV5_DIV: u32 = 5;
/// Highest VDDH that the input range can show (3.6 V x 5 = 18 V); the cell never gets near it.
pub const VDDH_MAX_MV: u32 = SAADC_FULL_SCALE_MV * VDDHDIV5_DIV;

/// Absolute floor: no motor start (and no boost enable) below this open-circuit cell voltage (`FIRMWARE-PINMAP.md` "Motor supply and
/// undervoltage lockout": cell sag under 0.6 A plus the protection chip's cut-off at 2.5 to 2.9 V leave no margin below it).
/// Measured at rest, no charger. The configurable rest threshold ([`MotorSupplyLimits`]) can only be set at or above it.
pub const MOTOR_MIN_VBAT_MV: u16 = 3_400;
/// SPICE finding F3 (`electronics/v010/cup/sim/REPORT.md`): the boost pre-charge draws about 1 A, so it is enabled only when the
/// RESTING cell voltage is at least this. It is deliberately a separate constant from the motor start threshold: the start gate
/// ([`start_gate`]) checks it first and the configuration can never lower the effective start threshold below it.
pub const BOOST_ENABLE_MIN_MV: u16 = 3_400;
/// SPICE finding F2, interim conservative threshold until the cell ESR is measured: no move is started when the resting cell voltage
/// is below this (the 3.4 V lockout alone still lets VBAT fall below the nRF VDDH minimum of 2.5 V at a cell resistance of 1.2 ohm
/// or more). Default of [`MotorSupplyLimits::rest_min_mv`]; spec/design-parameters.md section 7.
pub const MOTOR_REST_MIN_MV: u16 = 3_700;
/// SPICE finding F2: the cell voltage measured under load after the first step of a burst; below this the move is stopped
/// (diag `A-A0-004`). Default of [`MotorSupplyLimits::load_abort_mv`]; 300 mV above the nRF VDDH minimum of 2.5 V.
pub const MOTOR_LOAD_ABORT_MV: u16 = 2_800;
/// Accepted configuration range of the rest threshold: never below the absolute floor, never above a full cell.
pub const MOTOR_REST_MIN_MV_RANGE: (u16, u16) = (MOTOR_MIN_VBAT_MV, 4_150);
/// Accepted configuration range of the loaded abort threshold: never so low that the check is moot (100 mV above the nRF VDDH
/// minimum, leaving the measurement error), never above the 3.0 V check after 20 steps.
pub const MOTOR_LOAD_ABORT_MV_RANGE: (u16, u16) = (2_600, 3_000);
/// Existing check, kept unchanged (never relaxed): re-measured after the first 20 steps, below this under load the burst stops and
/// retries only after a rest. The new first-step check ([`MOTOR_LOAD_ABORT_MV`]) comes in addition to it.
pub const MOTOR_LOAD_FLOOR_MV: u16 = 3_000;
/// Number of steps after which the loaded cell voltage is checked against [`MOTOR_LOAD_FLOOR_MV`].
pub const MOTOR_LOAD_CHECK_STEPS: u32 = 20;
// The F3 dependency, checked at compile time: the default start threshold can never be below the boost enable threshold.
const _: () = assert!(MOTOR_REST_MIN_MV >= BOOST_ENABLE_MIN_MV);
const _: () = assert!(MOTOR_LOAD_ABORT_MV <= MOTOR_LOAD_FLOOR_MV);
/// Charge complete: cell voltage above which green means "full" when no charger status is available (informational).
pub const FULL_MV: u16 = 4_150;
/// LED battery state boundaries (`FIRMWARE-PINMAP.md` "Status LED"): green above, orange between, red below.
pub const LED_GREEN_ABOVE_MV: u16 = 3_800;
pub const LED_ORANGE_ABOVE_MV: u16 = 3_500;

/// Cell voltage in mV from a raw `VDDHDIV5` sample at `resolution_bits` (8, 10, 12 or 14). Rounded to nearest; negative raw values
/// give 0; an unsupported resolution gives `None`; the result saturates at `u16::MAX`.
pub fn vddhdiv5_to_mv(raw: i32, resolution_bits: u8) -> Option<u16> {
    if !matches!(resolution_bits, 8 | 10 | 12 | 14) {
        return None;
    }
    if raw <= 0 {
        return Some(0);
    }
    let full = 1u64 << resolution_bits;
    let num = raw as u64 * VDDH_MAX_MV as u64;
    let mv = (num + full / 2) / full;
    Some(mv.min(u16::MAX as u64) as u16)
}

/// Average of the samples (oversampling in firmware), then converted. Empty input gives `None`.
pub fn vddhdiv5_mean_to_mv(samples: &[i16], resolution_bits: u8) -> Option<u16> {
    if samples.is_empty() {
        return None;
    }
    let sum: i64 = samples.iter().map(|&s| s as i64).sum();
    let n = samples.len() as i64;
    // round half away from zero of sum / n
    let mean = if sum >= 0 { (sum + n / 2) / n } else { (sum - n / 2) / n };
    vddhdiv5_to_mv(mean as i32, resolution_bits)
}

/// Battery class used by the motor policy and the LED.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum BatteryClass {
    /// At or above `BATTERY_LOW_MV` (3.5 V).
    Ok,
    /// Below `BATTERY_LOW_MV`, at or above the motor-start limit: alert, motor still starts.
    Low,
    /// Below the motor-start limit ([`MOTOR_MIN_VBAT_MV`]): no motor start.
    Critical,
}

/// Classification with the limits of `limits.rs` (`BATTERY_LOW_MV` 3.5 V) and [`MOTOR_MIN_VBAT_MV`]. Open circuit voltage.
pub const fn classify(mv: u16) -> BatteryClass {
    if mv < MOTOR_MIN_VBAT_MV {
        BatteryClass::Critical
    } else if mv < crate::limits::BATTERY_LOW_MV {
        BatteryClass::Low
    } else {
        BatteryClass::Ok
    }
}

/// May the motor start at this open-circuit voltage (cell at rest, no charger)? Uses the default limits.
pub const fn motor_start_allowed(open_circuit_mv: u16, charger_present: bool) -> bool {
    start_gate(MotorSupplyLimits::DEFAULT, open_circuit_mv, charger_present).is_ok()
}

/// Loaded check after [`MOTOR_LOAD_CHECK_STEPS`] steps: false = stop the burst, retry only after a rest.
pub const fn loaded_voltage_ok(loaded_mv: u16) -> bool {
    loaded_mv >= MOTOR_LOAD_FLOOR_MV
}

// ---- configurable supply limits: rest threshold, loaded abort, boost enable (SPICE F2, F3) --------------------------------------

/// The two configurable thresholds of the cell supply policy. Both are NEW safety limits that only tighten (spec section 7); they are
/// data, not constants of the logic, because the right values depend on the cell resistance, which is not measured yet.
///
/// A value outside its range is rejected by [`MotorSupplyLimits::new`]; a hand-built struct is clamped on use
/// ([`MotorSupplyLimits::effective_rest_min_mv`], [`MotorSupplyLimits::effective_load_abort_mv`]) so that no configuration can
/// switch a check off or lower the start threshold below [`BOOST_ENABLE_MIN_MV`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct MotorSupplyLimits {
    /// No move starts when the resting cell voltage is below this, mV (default [`MOTOR_REST_MIN_MV`] 3.7 V, interim).
    pub rest_min_mv: u16,
    /// A move is stopped when the cell voltage under load, measured after the first step of a burst, is below this, mV
    /// (default [`MOTOR_LOAD_ABORT_MV`] 2.8 V).
    pub load_abort_mv: u16,
}

/// A configured threshold is outside its accepted range.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum LimitsError {
    /// `rest_min_mv` outside [`MOTOR_REST_MIN_MV_RANGE`].
    RestMinOutOfRange,
    /// `load_abort_mv` outside [`MOTOR_LOAD_ABORT_MV_RANGE`].
    LoadAbortOutOfRange,
}

impl MotorSupplyLimits {
    pub const DEFAULT: MotorSupplyLimits = MotorSupplyLimits { rest_min_mv: MOTOR_REST_MIN_MV, load_abort_mv: MOTOR_LOAD_ABORT_MV };

    /// Checked constructor.
    pub const fn new(rest_min_mv: u16, load_abort_mv: u16) -> Result<Self, LimitsError> {
        if rest_min_mv < MOTOR_REST_MIN_MV_RANGE.0 || rest_min_mv > MOTOR_REST_MIN_MV_RANGE.1 {
            return Err(LimitsError::RestMinOutOfRange);
        }
        if load_abort_mv < MOTOR_LOAD_ABORT_MV_RANGE.0 || load_abort_mv > MOTOR_LOAD_ABORT_MV_RANGE.1 {
            return Err(LimitsError::LoadAbortOutOfRange);
        }
        Ok(Self { rest_min_mv, load_abort_mv })
    }

    /// The rest threshold in force: never below [`BOOST_ENABLE_MIN_MV`] (F3) whatever the field holds.
    pub const fn effective_rest_min_mv(&self) -> u16 {
        if self.rest_min_mv < BOOST_ENABLE_MIN_MV {
            BOOST_ENABLE_MIN_MV
        } else {
            self.rest_min_mv
        }
    }

    /// The loaded abort threshold in force: never below the bottom of [`MOTOR_LOAD_ABORT_MV_RANGE`], so the check cannot be disabled.
    pub const fn effective_load_abort_mv(&self) -> u16 {
        if self.load_abort_mv < MOTOR_LOAD_ABORT_MV_RANGE.0 {
            MOTOR_LOAD_ABORT_MV_RANGE.0
        } else {
            self.load_abort_mv
        }
    }
}

impl Default for MotorSupplyLimits {
    fn default() -> Self {
        Self::DEFAULT
    }
}

/// F3: may the boost converter be enabled? Only when the RESTING cell voltage is at least [`BOOST_ENABLE_MIN_MV`]. Measure at rest,
/// before `MCU_EN` goes high: the pre-charge current of about 1 A pulls a weak cell far down.
pub const fn boost_enable_allowed(resting_mv: u16) -> bool {
    resting_mv >= BOOST_ENABLE_MIN_MV
}

/// Why a move may not start.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum StartRefusal {
    /// A charger is connected (H8): never move on a cable.
    Charger,
    /// Resting cell voltage below [`BOOST_ENABLE_MIN_MV`]: the boost may not even be enabled (F3).
    BoostBelowMinimum,
    /// Resting cell voltage below the (configured) rest threshold (F2).
    RestBelowThreshold,
}

/// The gate in front of every move, in this order: charger, boost enable (F3, [`boost_enable_allowed`]), rest threshold (F2).
/// The boost check comes first and does not depend on the configuration, so a pass here always implies a resting voltage of at
/// least [`BOOST_ENABLE_MIN_MV`].
pub const fn start_gate(limits: MotorSupplyLimits, resting_mv: u16, charger_present: bool) -> Result<(), StartRefusal> {
    if charger_present {
        return Err(StartRefusal::Charger);
    }
    if !boost_enable_allowed(resting_mv) {
        return Err(StartRefusal::BoostBelowMinimum);
    }
    if resting_mv < limits.effective_rest_min_mv() {
        return Err(StartRefusal::RestBelowThreshold);
    }
    Ok(())
}

/// Diagnostic for a refused start (`A-A0-004`, instance 2): `ctx_a` = resting mV, `ctx_b` = the threshold that was missed.
/// A charger refusal is not a battery fault and gives `None`.
pub fn rest_refusal_raise(limits: MotorSupplyLimits, resting_mv: u16, why: StartRefusal) -> Option<Raise> {
    let threshold = match why {
        StartRefusal::Charger => return None,
        StartRefusal::BoostBelowMinimum => BOOST_ENABLE_MIN_MV,
        StartRefusal::RestBelowThreshold => limits.effective_rest_min_mv(),
    };
    Some(Raise::new(codes::CELL_SAG_UNDER_LOAD).inst(2).a(resting_mv as i32).b(threshold as i32))
}

/// A move that was stopped because the cell sagged under load.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct SagAbort {
    /// Cell voltage under load, mV.
    pub loaded_mv: u16,
    /// The threshold that was missed, mV.
    pub floor_mv: u16,
    /// Steps made in the burst when the sample was taken.
    pub steps_made: u32,
}

impl SagAbort {
    /// Diagnostic `A-A0-004`, instance 1: `ctx_a` = loaded mV, `ctx_b` = threshold, `ctx_c` = steps made.
    pub fn raise(&self) -> Raise {
        Raise::new(codes::CELL_SAG_UNDER_LOAD).inst(1).a(self.loaded_mv as i32).b(self.floor_mv as i32).c(self.steps_made)
    }
}

/// Loaded-voltage guard of one burst. Plug it into the per-step `keep_going` callback of `phase_drive::drive_burst`, which is asked
/// before every step with the number of steps already made:
///
/// ```ignore
/// let mut guard = LoadGuard::new(limits);
/// drive_burst(.., |made| guard.keep_going(made, || read_vbat_mv()));
/// if let Some(abort) = guard.abort() { diag.raise(abort.raise()); }
/// ```
///
/// The cell voltage is sampled (through the closure; a failed sample must be mapped to 0 mV, which aborts) after the FIRST step
/// (`steps_made == 1`, against [`MotorSupplyLimits::effective_load_abort_mv`], F2) and after [`MOTOR_LOAD_CHECK_STEPS`] steps
/// (against the unchanged [`MOTOR_LOAD_FLOOR_MV`]). Once tripped it stays tripped and never lets another step go.
#[derive(Clone, Copy, Debug)]
pub struct LoadGuard {
    limits: MotorSupplyLimits,
    abort: Option<SagAbort>,
}

impl LoadGuard {
    pub const fn new(limits: MotorSupplyLimits) -> Self {
        Self { limits, abort: None }
    }

    /// Answer for `drive_burst`'s `keep_going`: false = stop now. `steps_made == 0` (nothing has moved yet) takes no sample.
    pub fn keep_going(&mut self, steps_made: u32, mut sample_vbat_mv: impl FnMut() -> u16) -> bool {
        if self.abort.is_some() {
            return false;
        }
        let floor = if steps_made == 1 {
            self.limits.effective_load_abort_mv()
        } else if steps_made == MOTOR_LOAD_CHECK_STEPS {
            MOTOR_LOAD_FLOOR_MV
        } else {
            return true;
        };
        let mv = sample_vbat_mv();
        if mv < floor {
            self.abort = Some(SagAbort { loaded_mv: mv, floor_mv: floor, steps_made });
            return false;
        }
        true
    }

    /// Why the burst was stopped, if the guard tripped.
    pub fn abort(&self) -> Option<SagAbort> {
        self.abort
    }
}

// ---- UICR REGOUT0 (HV mode) --------------------------------------------------------------------------------------------------

/// `UICR.REGOUT0` register address of the nRF52840.
pub const UICR_REGOUT0_ADDR: u32 = 0x1000_1304;
/// Field `VOUT` = bits 2..0: 0 = 1.8 V, 1 = 2.1, 2 = 2.4, 3 = 2.7, 4 = 3.0, 5 = 3.3 V, 7 = default (erased, 1.8 V).
pub const REGOUT0_VOUT_MASK: u32 = 0x7;
pub const REGOUT0_3V3: u32 = 5;
/// The word value that selects 3.3 V: the unused upper bits stay 1 (erased), so the write only clears bits.
pub const REGOUT0_3V3_WORD: u32 = 0xFFFF_FFF8 | REGOUT0_3V3;

/// What to do about `UICR.REGOUT0` at boot (HV mode: the HJ-840 SiP has no LDO, the 3V3 rail comes from REG0, default 1.8 V).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum Regout0Action {
    /// Already 3.3 V.
    Nothing,
    /// Erased (default 1.8 V): write [`REGOUT0_3V3_WORD`] (bits only go 1 -> 0), then reset once: the new voltage takes effect
    /// after a reset.
    Write,
    /// Holds another programmed voltage: a UICR word cannot be rewritten without ERASEALL. Refuse to run (rail is wrong), report.
    NeedsErase,
}

/// Decide from the current register word.
pub const fn regout0_action(word: u32) -> Regout0Action {
    let vout = word & REGOUT0_VOUT_MASK;
    if vout == REGOUT0_3V3 {
        Regout0Action::Nothing
    } else if vout == 7 {
        // erased / default: only bits 2..0 are written 1 -> 0 (the upper bits are left as they are)
        Regout0Action::Write
    } else {
        Regout0Action::NeedsErase
    }
}

/// Is the rail running at 3.3 V right now? The SAADC `VDD` channel (1/6 gain, full scale 3.6 V) must read inside the window; a rail
/// at the default 1.8 V (UICR not written yet, or the reset after the write did not happen) means the board is under-supplied.
pub const fn vdd_rail_ok(vdd_mv: u16) -> bool {
    vdd_mv >= 3_100 && vdd_mv <= 3_500
}
