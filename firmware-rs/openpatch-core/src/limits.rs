//! Safety limits and dosing geometry (`spec/design-parameters.md` section 7). Hard upper bounds:
//! never relax silently.

use crate::units::{Millis, MilliUnits, MilliUnitsPerHour, PulseCal};

/// Sane range of the per-step volume (1 mU .. 60 mU). NFP-608-26.45 with the 16:20 pair: 3.95 mU, direct: 4.94 mU, 15:12: 6.17 mU, Zhaowei 6.43: 20.3 mU, syringe bench rig: 1.19 mU.
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
/// The 15 U/h cap bounds the PHYSICAL volume, not just the commanded one: the supervisor enforces
/// `MAX_HOURLY / (1 + HOURLY_CAL_MARGIN_PCT / 100)` in steps (14.42 U of nominal volume). 4 % = worst case of the
/// stadium area (frozen drawing +0.05/-0 mm on both axes: +1.3 %, spec 3a) + lead error (+-1.5 % at 3 sd, sim
/// `montecarlo`) + gearhead ratio (3 sd 0.9 %): 1.013 * 1.015 * 1.009 = +3.8 %. A tightening of the commanded
/// limit only; the spec limit of 15 U/h is never exceeded at the needle.
pub const HOURLY_CAL_MARGIN_PCT: u32 = 4;
pub const MAX_PER_MIN: MilliUnits = MilliUnits(1_700);
pub const OCCLUSION: MilliUnits = MilliUnits(2_000);
pub const ENCODER_WINDOW: MilliUnits = MilliUnits(1_000);
pub const ENCODER_TOLERANCE_PCT: i64 = 10;
pub const BATTERY_CRITICAL_MV: u16 = 3_300;
pub const BATTERY_LOW_MV: u16 = 3_500;
pub const BATTERY_HYSTERESIS_MV: u16 = 100;
pub const DEFAULT_LOW_RESERVOIR: MilliUnits = MilliUnits(10_000);
/// One prime command (C reference parity). The connector path is 2.21 U ([`PRIME_PATH_MU`]): the app primes it with
/// [`prime_commands_for_path`] commands; the first one after a draw also runs the backlash take-up.
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

// ---------------------------------------------------------------------------------------------
// Motor current (STSPIN220 + current sense). One run current, everything else derived from it.
// ---------------------------------------------------------------------------------------------
// ---- motor supply current sense, Rev A bench controller (electronics/bench/INTERLOCK.md, controller/parts.json) ----
/// Shunt resistors in parallel in the motor supply (R31, R39, R47).
pub const SHUNT_PARALLEL_N: u32 = 3;
/// Resistance of EACH shunt resistor in milliohm (1.0 ohm, RS-03L1R00FT). The total is 1000 / 3 = 0.333 ohm.
pub const SHUNT_EACH_MOHM: u32 = 1_000;
/// INA180A1 gain, V/V.
pub const INA180A1_GAIN: u32 = 20;
/// Output of the sense chain per mA of motor supply current, in uV: `gain x R_total`
/// = 20 x 0.3333 ohm = 6.667 mV per mA (a 1.0 ohm shunt would give 20 mV per mA: the old, wrong constant).
/// Full scale of the SAADC (3.6 V) is 540 mA; the INA saturates at about 3.25 V (490 mA); the hardware over-current
/// comparator trips at 3.0 V = 450 mA.
pub const I_SENSE_UV_PER_MA: u32 = INA180A1_GAIN * SHUNT_EACH_MOHM / SHUNT_PARALLEL_N;
/// `I_SENSE_UV_PER_MA` x 100 / 1000, i.e. mV x 100 per mA (667): lets integer maths divide by 6.67.
pub const I_SENSE_MV_X100_PER_MA: u32 = (I_SENSE_UV_PER_MA + 5) / 10;
/// Motor supply current in mA from an `I_SENSE` reading in mV (rounded down).
pub const fn isense_mv_to_ma(mv: u32) -> u32 {
    mv * SHUNT_PARALLEL_N * 1_000 / (INA180A1_GAIN * SHUNT_EACH_MOHM)
}
/// Hardware over-current trip (comparator reference 3.0 V), mA.
pub const HW_OVERCURRENT_MA: u32 = isense_mv_to_ma(3_000);

/// STSPIN220 peak phase current: `VREF 0.160 V / 1.0 ohm` sense (electronics/bench/pin-assignment.md, R24 100k/5.1k;
/// raised from 105 mA for thrust, mechanical sim 1.1: 4.0 N at 105 mA, 7.0 N at the rated current).
pub const MOTOR_RUN_CURRENT_MA: u16 = 160;
/// NFP-608-26.45 rating: 4.8 V / 26.5 ohm = 181 mA per phase. The run current must never exceed it.
pub const MOTOR_RATED_CURRENT_MA: u16 = 181;
/// Supply-side `I_SENSE` (INA180A1 20 V/V on the 0.333 ohm shunt R31 / R39 / R47, see [`I_SENSE_UV_PER_MA`]) relative to the run current, in percent. PLACEHOLDERS,
/// calibrate on the water bench (docs/bench-testing.md): a free-running stage at 200 pps draws about 2/3 of the
/// chopper limit (back-EMF), a stalled rotor about 5/3 (two windings at the limit, no back-EMF, supply above the
/// winding drop). The same ratios the simulator always used at 105 mA (70 / 175 mA), scaled to 160 mA.
pub const SENSE_FREE_PCT: u32 = 67;
pub const SENSE_STALL_PCT: u32 = 167;
/// Expected `I_SENSE` of a free-running stage: 107 mA.
pub const MOTOR_FREE_CURRENT_MA: u16 = (MOTOR_RUN_CURRENT_MA as u32 * SENSE_FREE_PCT / 100) as u16;
/// Expected `I_SENSE` of a stalled rotor: 267 mA.
pub const MOTOR_STALL_CURRENT_MA: u16 = (MOTOR_RUN_CURRENT_MA as u32 * SENSE_STALL_PCT / 100) as u16;
/// Forward occlusion (Rust port addition; the C reference is encoder-only): free-running + 2/3 of the span to the
/// stalled current = 213 mA. Consecutive bursts above it latch OCCLUSION (stored-volume accounting: `safety.rs`).
pub const OCCLUSION_CURRENT_MA: u16 = MOTOR_FREE_CURRENT_MA + ((MOTOR_STALL_CURRENT_MA - MOTOR_FREE_CURRENT_MA) as u32 * 2 / 3) as u16;
/// Draw (refill) mode has its OWN stall threshold: the reverse stroke runs at 600 pps where the motor has only 0.69 x
/// the torque of 200 pps, so a healthy high-friction pod legitimately loads the motor more than a forward dose. A draw
/// is stalled on current only within 5 % of the stalled current (real stalls are caught by the angle check as well).
pub const DRAW_STALL_CURRENT_MA: u16 = (MOTOR_STALL_CURRENT_MA as u32 * 95 / 100) as u16;
/// Consecutive bursts above the threshold (a lower burst in between resets) before OCCLUSION latches.
pub const OCCLUSION_CURRENT_BURSTS: u8 = 3;

/// STORED-VOLUME ACCOUNTING (spec 7 "alarm at <= 2 U undelivered", mechanical sim 5.4). An occlusion is only
/// recognised after the plunger train has soaked up water: the carriage keeps turning (the encoder sees nothing) while
/// the pressure builds in the compliance and the thrust train, and that stored volume is ADDITIONAL to the 2 U of
/// unconfirmed steps. With the stronger drive (16:20 pair, 160 mA) the stall pressure and therefore the stored volume
/// grew (simulator, absolute threshold only: median 1.4 U, 5.5 % of pods above 2 U at the alarm). The motor current
/// rises with the force, so the supply current ABOVE the pod's own running level is a measure of the stored volume:
/// `stored = OCC_STORED_MU_PER_MA x (I - I_baseline)`.
/// Derivation of the conservative factor: force per mA of sensed current `F_max / span` = 10 N / 160 mA = 0.0625 N/mA;
/// stored volume per newton of the softest tolerated train (mechanical report: tongue as drawn 19 N/mm, A / k =
/// 3.9 mm^3/N, plus compliance 0.29 mm^3/kPa x 13.4 kPa/N = 3.9 mm^3/N) = 0.78 U/N; so 0.0625 x 0.78 = 49 mU/mA.
pub const OCC_STORED_MU_PER_MA: u32 = 50;
/// The undelivered budget of spec 7, mU.
pub const OCC_BUDGET_MU: u32 = 2_000;
/// Rise of the burst current above the pod's baseline that stands for a full budget of stored volume:
/// 2000 / 50 = 40 mA. The comparison uses the MINIMUM of the last [`OCC_WINDOW_BURSTS`] bursts: the break-away peak
/// after a pause (static minus dynamic seal friction is up to 2 N = 130 mA on a tolerance-corner pod) must not look like
/// pressure, whereas the whole floor of the current rises when pressure builds. When that window minimum exceeds
/// `baseline + OCCLUSION_RISE_MA`, OCCLUSION latches (in addition to the absolute threshold [`OCCLUSION_CURRENT_MA`]).
/// The baseline is the lowest window minimum seen since the last fill / prime / draw / acknowledge, creeping up by
/// [`OCC_BASELINE_CREEP_MA`] per [`OCC_BASELINE_CREEP_BURSTS`] bursts (slow friction drift must not turn into an alarm;
/// an occlusion ramp is faster).
pub const OCCLUSION_RISE_MA: u16 = (OCC_BUDGET_MU / OCC_STORED_MU_PER_MA) as u16;
/// Window of the minimum filter. Simulator tuning (1000 pods, seed 1 / 20261119, `opsim mc`): the absolute threshold alone leaves 10.9 % of
/// the pods above 2 U at the alarm (max 3.8 U); with the rise criterion (mU per mA / window -> pods above 2 U, nominal pods that alarm
/// without an occlusion): 25/32 -> 10.9 % / 0 %, 33/16 -> 2.1 % / 0.2 %, 40/16 -> 0.8 % / 0.6 %, 40/24 -> 1.0 % / 0.6 %,
/// **50/16 -> 0.1 % (1 of 989, max 2.03 U) / 2.9 %**, 50/8 -> 0 % / 3.5 %. 50/16 is chosen: it is the derived value above and
/// puts the spec first; the false alarms are fail-safe (acknowledge, refill / re-prime) and are to be tuned on the water bench.
pub const OCC_WINDOW_BURSTS: usize = 16;
pub const OCC_BASELINE_CREEP_MA: u16 = 1;
pub const OCC_BASELINE_CREEP_BURSTS: u16 = 64;

// ---------------------------------------------------------------------------------------------
// Draw (refill) mode: only undocked + suspended, motor reverses exactly the requested volume.
// ---------------------------------------------------------------------------------------------
pub const DRAW_MAX_PPS: u32 = 1_000;
/// Default draw rate (the bench `REVERSE_RATE_HZ`): lower than the cap, keeps torque margin.
pub const DRAW_DEFAULT_PPS: u32 = 600;
/// Largest number of steps in one tick-chunk of a draw job (0.5 s at 1000 pps). The chunk is also limited to
/// 0.8 s of motion at the rate in use ([`draw_chunk_steps`]) so that a slow draw never starves the watchdog.
pub const DRAW_CHUNK_STEPS: u32 = 500;
/// A reverse chunk whose encoder travel is below this percentage of the commanded travel is a stall
/// (rear end-stop reached or jam).
pub const DRAW_STALL_PCT: i64 = 50;

/// Gauge of the fill needle (syringe / vial through the septum). The suction the plunger must pull grows with the
/// flow, so the draw rate is capped per gauge (mechanical sim 1.5: Hagen-Poiseuille, 12.7 mm needle, water at 10 C
/// 1.6 mPa*s, vacuum <= 30 kPa to avoid degassing, derated to 80 % = 24 kPa).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FillNeedle {
    G27,
    G28,
    G29,
    G30,
    G31,
}

impl FillNeedle {
    /// Largest flow in nl/s that keeps the vacuum at or below 24 kPa (inner diameter from the gauge table: 27G 0.210,
    /// 28G and 29G 0.184, 30G 0.159, 31G 0.133 mm).
    pub const fn max_flow_nl_s(self) -> u32 {
        match self {
            FillNeedle::G27 => 56_400,
            FillNeedle::G28 | FillNeedle::G29 => 33_200,
            FillNeedle::G30 => 18_500,
            FillNeedle::G31 => 9_070,
        }
    }

    /// The same cap in pulses per second for this drive (`flow / volume per step`); 841 pps for 29G on the 16:20 drive.
    pub fn max_pps(self, cal: PulseCal) -> u32 {
        if cal.is_none() {
            return 1;
        }
        // 1 uU/step = 0.01 nl/step: pps = flow_nl_s x 100 x den / num
        let pps = self.max_flow_nl_s() as u64 * 100 * cal.uu_den as u64 / cal.uu_num as u64;
        (pps as u32).max(1)
    }
}

/// The reverse step rate used for a draw: [`DRAW_DEFAULT_PPS`], or less when the needle gauge demands it.
pub fn draw_pps(needle: FillNeedle, cal: PulseCal) -> u32 {
    DRAW_DEFAULT_PPS.min(needle.max_pps(cal)).min(DRAW_MAX_PPS)
}

/// Steps of one draw chunk at `pps`: at most [`DRAW_CHUNK_STEPS`] and at most 0.8 s of motion.
pub const fn draw_chunk_steps(pps: u32) -> u32 {
    let s = pps * 800 / 1000;
    let s = if s > DRAW_CHUNK_STEPS { DRAW_CHUNK_STEPS } else { s };
    if s == 0 {
        1
    } else {
        s
    }
}

// ---------------------------------------------------------------------------------------------
// Backlash take-up and priming
// ---------------------------------------------------------------------------------------------
/// Lost motion at a reversal of the CURRENT mechanics (side-slot carriage with a shim in the plunger socket), from the
/// mechanical design and the independent review 2026-11-19 (item 5, "Lost motion"): carriage-to-plunger socket play
/// (0.8 mm slot minus 0.5 mm shim) = 0.30 mm, plus nut play 0.03 to 0.08 mm (the low end is taken here, the rest is
/// absorbed by the bench calibration). It is a property of the MECHANICS, not of the drive: it WILL change with the new
/// drive (push rod with a captured, play-free link: the socket play disappears and this takes the value of the new train).
pub const LOST_MOTION_SOCKET_UM: u32 = 300;
pub const LOST_MOTION_NUT_UM: u32 = 30;
/// Plunger face area of the reservoir: 5 x 11 mm stadium bore + two 2.5 mm radius ends = 74.63 mm^2, in 0.01 mm^2.
pub const PLUNGER_AREA_MM2_X100: u32 = 7_463;
/// Volume swept by a plunger travel of `um` micrometre, mU (1 U = 10 mm^3 = 1000 mU, so mU = um x mm^2 x 0.1).
pub const fn plunger_um_to_mu(um: u32) -> u32 {
    (um as u64 * PLUNGER_AREA_MM2_X100 as u64 / 1000) as u32
}
/// Forward travel (as a volume, so it scales with the drive) run BEFORE the first prime after a draw: after the reversal
/// the first forward travel only takes up the free motion of the socket and the nut and the elasticity of carriage,
/// seal and tongue (mechanical sim 2.9: first 1 U after a draw -22 ... -60 % without it). It is the lost motion above
/// ([`LOST_MOTION_SOCKET_UM`] + [`LOST_MOTION_NUT_UM`] = 0.33 mm = 2 463 mU = 623 steps on the 16:20 drive; the old
/// value, 632 mU = 160 steps, was the simulator recommendation and covered only a quarter of the socket play). The steps
/// go through the supervisor like every forward step (hourly / per-minute accounting, docked, interlock) but are NOT
/// counted as delivery (engine totals, `delivered_mu`); the reservoir model consumes them (a draw credits steps whose
/// first part never moved the plunger, so this corrects the model). Configurable: `PumpConfig::takeup_mu` (0 = none).
pub const TAKEUP_MU_AFTER_DRAW: u32 = plunger_um_to_mu(LOST_MOTION_SOCKET_UM + LOST_MOTION_NUT_UM);
/// Volume of the fluid path from the reservoir port to the needle tip (mechanical report 5.1: 22.1 mm^3), mU. This
/// is what a complete purge must push through; the 1.0 mm dead layer in front of the plunger (7.5 U of air) is not
/// reachable by priming.
pub const PRIME_PATH_MU: MilliUnits = MilliUnits(2_210);
/// Largest prime command in steps per chunk: a longer prime runs in several bursts and the watchdog is serviced between
/// them (a burst longer than about 0.5 s plus the 1 s tick would exceed the 2 s TPL5010 period).
pub const PRIME_CHUNK_STEPS: u32 = 64;
/// Prime commands of [`MAX_PRIME`] needed to push [`PRIME_PATH_MU`] through the connector (5).
pub const fn prime_commands_for_path() -> u32 {
    (PRIME_PATH_MU.0 + MAX_PRIME.0 - 1) / MAX_PRIME.0
}

pub const FW_VERSION: u16 = 0x0200;

/// `7-7B-001 TICK_OVERRUN`: a safety tick later than this (nominal 1 s) raises a warning.
pub const TICK_OVERRUN_MS: u64 = 2_500;
/// `4-40-003 DIR_INVERTED`: a reverse burst of at least this many steps whose angle moved FORWARD by more than
/// this percentage of the expected reverse travel proves a wrong direction polarity.
pub const DIR_INVERTED_MIN_STEPS: u32 = 16;
pub const DIR_INVERTED_PCT: i64 = 50;

/// Sane calibration check.
#[inline]
pub const fn cal_in_range(c: PulseCal) -> bool {
    let f = c.micro_u_floor();
    !c.is_none() && f >= CAL_UU_MIN && f <= CAL_UU_MAX
}
