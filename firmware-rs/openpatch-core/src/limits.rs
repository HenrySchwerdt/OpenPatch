//! Safety limits and dosing geometry (`spec/design-parameters.md` section 7). Hard upper bounds:
//! never relax silently.

use crate::units::{Millis, MilliUnits, MilliUnitsPerHour, PulseCal};

/// Sane range of the per-step volume (1 mU .. 60 mU). NFP-608-26.45 direct: 4.94 mU, with the 15:12 gear
/// pair: 6.17 mU, Zhaowei 6.43: 20.3 mU, syringe bench rig: 1.19 mU.
pub const CAL_UU_MIN: u32 = 1_000;
pub const CAL_UU_MAX: u32 = 60_000;

/// Rate accumulator scale: R mU/h held for dt ms delivers R*dt / 3_600_000 mU.
pub const SCALED_PER_MU: i64 = 3_600_000;
pub const SCALED_PER_UU: i64 = 3_600;

pub const SLOT_MS: u32 = 1_800_000;
pub const SLOTS_PER_DAY: u8 = 48;
pub const DAY_MS: u32 = 86_400_000;
pub const BASAL_SEGMENTS_MAX: usize = 24;
pub const RATE_GRANULARITY: MilliUnitsPerHour = MilliUnitsPerHour(50);
pub const BOLUS_GRANULARITY: MilliUnits = MilliUnits(50);
pub const TEMP_MAX_MIN: u32 = 720;
pub const TEMP_GRANULARITY_MIN: u32 = 30;
/// Temp basal survives 30 min without communication, then falls back to the programmed basal.
pub const COMM_LOSS_TEMP_MS: u32 = 1_800_000;

pub const BOLUS_RATE: MilliUnitsPerHour = MilliUnitsPerHour(90_000); // 1.5 U/min
pub const HARD_MAX_BOLUS: MilliUnits = MilliUnits(25_000);
pub const HARD_MAX_BASAL: MilliUnitsPerHour = MilliUnitsPerHour(30_000);
pub const DEFAULT_MAX_BOLUS: MilliUnits = MilliUnits(10_000);
pub const DEFAULT_MAX_BASAL: MilliUnitsPerHour = MilliUnitsPerHour(5_000);
pub const MAX_HOURLY: MilliUnits = MilliUnits(15_000);
pub const MAX_PER_MIN: MilliUnits = MilliUnits(1_700);
pub const OCCLUSION: MilliUnits = MilliUnits(2_000);
pub const ENCODER_WINDOW: MilliUnits = MilliUnits(1_000);
pub const ENCODER_TOLERANCE_PCT: i64 = 10;
pub const BATTERY_CRITICAL_MV: u16 = 3_300;
pub const BATTERY_LOW_MV: u16 = 3_500;
pub const BATTERY_HYSTERESIS_MV: u16 = 100;
pub const DEFAULT_LOW_RESERVOIR: MilliUnits = MilliUnits(10_000);
pub const MAX_PRIME: MilliUnits = MilliUnits(524);
pub const TICK_MAX_DT: Millis = Millis(5_000);

pub const CAPACITY_70: MilliUnits = MilliUnits(70_000);
pub const CAPACITY_100: MilliUnits = MilliUnits(100_000);
pub const CAPACITY_200: MilliUnits = MilliUnits(200_000);

pub const WEAR_WARN: Millis = Millis(44 * 3_600_000);
pub const WEAR_MAX: Millis = Millis(52 * 3_600_000);

/// Per-revolution TMAG5273 verification: after every completed leadscrew revolution of commanded
/// steps the measured angle must be 4096 counts +- this percentage, else ENCODER_DEVIATION.
pub const REV_TOLERANCE_PCT: i64 = 3;

/// Motor-current occlusion input (Rust port addition; the C reference is encoder-only). Bench board:
/// `I_SENSE` = 20 V/V * 1.0 ohm shunt in the motor supply. PLACEHOLDER thresholds, calibrate on the
/// water bench (docs/bench-testing.md): a stalled rotor at the 105 mA phase limit draws more than a
/// free-running stage.
pub const OCCLUSION_CURRENT_MA: u16 = 140;
/// Consecutive bursts above the threshold (a lower burst in between resets) before OCCLUSION latches.
pub const OCCLUSION_CURRENT_BURSTS: u8 = 3;

/// Draw (refill) mode: only undocked + suspended, motor reverses exactly the requested volume.
pub const DRAW_MAX_PPS: u32 = 1_000;
/// Steps per tick-chunk of a draw job (0.5 s at 1000 pps; the tick is ~1 s, so <= 500 pps average).
pub const DRAW_CHUNK_STEPS: u32 = 500;
/// A reverse chunk whose encoder travel is below this percentage of the commanded travel is a stall
/// (rear end-stop reached or jam).
pub const DRAW_STALL_PCT: i64 = 50;

pub const FW_VERSION: u16 = 0x0200;

/// Sane calibration check.
#[inline]
pub const fn cal_in_range(c: PulseCal) -> bool {
    let f = c.micro_u_floor();
    !c.is_none() && f >= CAL_UU_MIN && f <= CAL_UU_MAX
}
