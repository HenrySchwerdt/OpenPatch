//! Named compile-time configuration. Nothing in here relaxes a core safety limit
//! (`openpatch_core::limits` stays authoritative).
#![allow(dead_code)]

use openpatch_core::drive_cal::{self, DriveCal, Preset};

// ---------------------------------------------------------------------------------------------
// Drive selection (cargo features, exactly one, NO default)
// ---------------------------------------------------------------------------------------------
#[cfg(not(any(
    feature = "drive-nfp-608-26-45",
    feature = "drive-zwbpd006006-6-43",
    feature = "drive-zwbpd006006-4-8",
    feature = "drive-faulhaber-adm0620-16"
)))]
compile_error!("select exactly one drive feature: drive-nfp-608-26-45 | drive-zwbpd006006-6-43 | drive-zwbpd006006-4-8 | drive-faulhaber-adm0620-16 (there is no default)");
#[cfg(any(
    all(feature = "drive-nfp-608-26-45", feature = "drive-zwbpd006006-6-43"),
    all(feature = "drive-nfp-608-26-45", feature = "drive-zwbpd006006-4-8"),
    all(feature = "drive-nfp-608-26-45", feature = "drive-faulhaber-adm0620-16"),
    all(feature = "drive-zwbpd006006-6-43", feature = "drive-zwbpd006006-4-8"),
    all(feature = "drive-zwbpd006006-6-43", feature = "drive-faulhaber-adm0620-16"),
    all(feature = "drive-zwbpd006006-4-8", feature = "drive-faulhaber-adm0620-16"),
))]
compile_error!("enable exactly one drive feature");

#[cfg(all(feature = "angle-tmag", feature = "angle-qdec-fallback"))]
compile_error!("enable exactly one angle source: angle-tmag | angle-qdec-fallback");
#[cfg(not(any(feature = "angle-tmag", feature = "angle-qdec-fallback")))]
compile_error!("enable exactly one angle source: angle-tmag | angle-qdec-fallback");

#[cfg(feature = "drive-nfp-608-26-45")]
pub const PRESET: &Preset = &drive_cal::NFP_608_2645;
#[cfg(feature = "drive-zwbpd006006-6-43")]
pub const PRESET: &Preset = &drive_cal::ZWBPD006006_6_43;
#[cfg(feature = "drive-zwbpd006006-4-8")]
pub const PRESET: &Preset = &drive_cal::ZWBPD006006_4_8;
#[cfg(feature = "drive-faulhaber-adm0620-16")]
pub const PRESET: &Preset = &drive_cal::FAULHABER_ADM0620_16;

/// Calibration record of this build (magic + CRC set). Stored on first boot, compared afterwards.
pub fn build_drive_cal() -> DriveCal {
    DriveCal::from_preset(PRESET)
}

/// Host-test presets (id >= 0x7F00, core feature `test-calibrations`) must NEVER be in a firmware
/// build. A cargo feature of the core cannot be seen from here, so this is checked at startup
/// against the preset table the core was really compiled with. Panics (-> watchdog reset) if not.
pub fn assert_no_test_calibrations() {
    if drive_cal::PRESETS.iter().any(|p| p.id as u16 >= 0x7F00) {
        defmt::panic!("core built with test-calibrations: refusing to run firmware");
    }
}

/// Motor steps per leadscrew turn x 100 (steps/rev x gear ratio x 100), exact.
pub const TURN_X100: u32 = PRESET.steps_per_rev as u32 * PRESET.gear_ratio_x100 as u32;

/// Reservoir capacity of the bench cartridge/syringe model.
pub const RESERVOIR_CAPACITY: openpatch_core::MilliUnits = openpatch_core::limits::CAPACITY_100;

// ---------------------------------------------------------------------------------------------
// Step generation (STSPIN220 STCK)
// ---------------------------------------------------------------------------------------------
/// STCK step rate. Trade-off (docs/architecture.md):
/// * higher: shorter blocking burst (a 64 step prime takes 64 / rate), less time with the motor
///   supply on; but less torque margin (back-EMF at speed) and more risk of lost steps on a
///   loaded 5:1 drive,
/// * lower: more torque margin, quieter, easier encoder correlation; but the safety task is
///   blocked longer per burst (64 steps at 100 Hz = 640 ms).
/// Typical dosing is 1 to 4 steps per 1 s tick (a 1.5 U/min bolus is 3.4 steps/s), so the burst
/// is 5 to 20 ms; only a prime (up to 64 steps) is visibly long. 200 Hz = 5 ms period.
pub const STEP_RATE_HZ: u32 = 200;
const _: () = assert!(STEP_RATE_HZ >= 40 && STEP_RATE_HZ <= 1000, "step rate out of the supported range");
/// PWM clock after the prescaler (16 MHz / 16).
pub const STEP_PWM_CLK_HZ: u32 = 1_000_000;
/// PWM COUNTERTOP = one STCK period (15 bit register, max 32767).
pub const STEP_PWM_PERIOD_TICKS: u16 = (STEP_PWM_CLK_HZ / STEP_RATE_HZ) as u16;
/// 50 % duty: STCK high >= tSTCKH (100 ns) by orders of magnitude.
pub const STEP_PWM_DUTY_TICKS: u16 = STEP_PWM_PERIOD_TICKS / 2;
/// Upper bound of one burst. The core never asks for more than a prime (max 64 steps on the 16:1
/// drive) or a few steps of a bolus tick; anything above is refused (returns 0 steps).
pub const MAX_BURST_STEPS: u32 = 128;
/// Reverse (draw) bursts: the core asks for chunks of 500 steps. The HAL limits the rate to
/// <= 1000 pps (hard cap `REVERSE_RATE_MAX_HZ`); 600 Hz keeps a 500 step chunk below 0.9 s so the
/// TPL5010 (about 2 s) is serviced between chunks.
pub const REVERSE_RATE_HZ: u32 = 600;
pub const REVERSE_RATE_MAX_HZ: u32 = 1_000;
const _: () = assert!(REVERSE_RATE_HZ <= REVERSE_RATE_MAX_HZ);
pub const REVERSE_PERIOD_TICKS: u16 = (STEP_PWM_CLK_HZ / REVERSE_RATE_HZ) as u16;
pub const MAX_REVERSE_BURST_STEPS: u32 = 600;
/// Extra time allowed on top of `steps / rate` before a burst is declared failed.
pub const BURST_TIMEOUT_MARGIN_MS: u64 = 25;

/// STSPIN220 MODE1/MODE2/MODE3(STCK)/MODE4(DIR) latched when leaving standby. All low = full step
/// (one core step = one full motor step; 20 steps/rev). Table 8 of DS11633.
pub const MODE1_LEVEL_HIGH: bool = false;
pub const MODE2_LEVEL_HIGH: bool = false;
/// DIR level for forward (piston advancing) motion. Flip if the motor is wired the other way round.
pub const DIR_FORWARD_HIGH: bool = true;
/// tMODEsu is 1 us; wake-up of the control logic after STBY high (EN/FAULT is forced low meanwhile).
pub const STBY_WAKE_US: u64 = 2_000;
/// Give the driver this long to release EN/FAULT after leaving standby, else "not ready".
pub const DRIVER_READY_TIMEOUT_MS: u64 = 10;
/// Supply settling time after the interlock closed, before leaving standby.
pub const VMOT_SETTLE_MS: u64 = 3;
/// VMOT_SENSE (x2, divider 100k/100k) above this = supply applied; below `OFF` = supply cut.
pub const VMOT_ON_MIN_MV: u32 = 3_000;
pub const VMOT_OFF_MAX_MV: u32 = 1_500;
/// Time allowed for the supply to collapse after KILL_N / MCU_EN were dropped.
pub const VMOT_FALL_TIMEOUT_MS: u64 = 20;

// ---------------------------------------------------------------------------------------------
// Analog front end (SAADC)
// ---------------------------------------------------------------------------------------------
/// 12 bit, gain 1/6, internal 0.6 V reference: full scale 3.6 V = 4096 counts.
pub const ADC_FULL_SCALE_MV: u32 = 3_600;
pub const ADC_COUNTS: u32 = 4_096;
/// INA180A1: 20 V/V across the 1.0 ohm shunt => 20 mV per mA of motor supply current.
pub const I_SENSE_MV_PER_MA: u32 = 20;
/// VBUS_SENSE and VMOT_SENSE are 100k/100k dividers.
pub const DIVIDER_RATIO: u32 = 2;
/// ADC samples per burst are taken back to back; this caps the loop (about 100 us per 3-channel scan).
pub const ADC_MAX_SAMPLES_PER_BURST: u32 = 4_000;
/// `Hal::battery_mv` on boards without a VBUS divider (DK): fixed, documented value.
pub const BATTERY_MV_FIXED: u16 = 4_000;

// ---------------------------------------------------------------------------------------------
// Leadscrew angle (TMAG5273, 4096 counts per turn, cumulative and unwrapped)
// ---------------------------------------------------------------------------------------------
pub const ANGLE_COUNTS_PER_TURN: i32 = 4096;
/// I2C address of the TMAG5273A1.
pub const TMAG_ADDR: u8 = 0x35;
/// The unwrap assumes the shaft moves less than HALF a turn (2048 counts) between two samples.
/// During a burst the HAL samples every `ANGLE_POLL_MS` ms. Fastest shaft speed = max step rate /
/// steps per turn: 600 Hz reverse on the 529 steps/turn NFP drive = 1.13 turns/s = 0.56 turn per
/// 500 ms, so 20 ms sampling leaves a factor of about 20 margin; the smallest turn_x100 preset
/// (Faulhaber 20 x 16 = 320 steps/turn: 1.9 turns/s) still leaves a factor of about 12.
pub const ANGLE_POLL_MS: u64 = 20;
/// I2C transaction timeout.
pub const TMAG_TIMEOUT_MS: u64 = 5;
/// Consecutive failed reads before the sensor is declared missing (`angle_read` -> None).
pub const TMAG_FAIL_LIMIT: u8 = 3;
/// `angle-qdec-fallback`: counts per quadrature EDGE (1 pole pair placeholder: 4 edges per turn).
pub const QDEC_ANGLE_COUNTS_PER_EDGE: i64 = 1024;
/// +1 / -1: sign of QDEC counts for forward motion (fallback and coarse cross-check).
pub const ENC_DIRECTION: i32 = 1;
/// QDEC accumulator poll interval (the hall switches update at 20 Hz).
pub const ENC_POLL_MS: u64 = 20;

// ---------------------------------------------------------------------------------------------
// Task timing / UI
// ---------------------------------------------------------------------------------------------
pub const TICK_PERIOD_MS: u64 = 1_000;
pub const PAIRING_WINDOW_S: u64 = 60;
/// Button hold time for the emergency stop.
pub const EMERGENCY_HOLD_MS: u64 = 3_000;
pub const BUTTON_DEBOUNCE_MS: u64 = 30;
pub const BEEP_MS: u64 = 120;
/// Buzzer resonance (MLT-8530) and duty.
pub const BUZZER_HZ: u32 = 2_700;
/// Consecutive good safety ticks before the new image is confirmed (`mark_booted`).
pub const BOOT_OK_TICKS: u32 = 30;

// ---------------------------------------------------------------------------------------------
// Persistence policy (protocol section 6.1)
// ---------------------------------------------------------------------------------------------
/// The seq ceiling is persisted BEFORE a command with a higher seq is executed. After a reboot
/// `LAST_SEQ` is restored to the ceiling, so a replay of anything accepted before the loss is
/// impossible. Step 8 keeps the post-reboot jump below the phone's "last known + 16" restart rule.
pub const SEQ_CEILING_STEP: u16 = 8;
/// Event id ceiling: extend by 64 when fewer than 16 ids of headroom remain.
pub const EVT_CEILING_STEP: u32 = 64;
pub const EVT_CEILING_HEADROOM: u32 = 16;
/// Reservoir: persist `consumed + MARGIN` whenever `consumed + TRIGGER >= persisted`, so that after a
/// power loss the model can only be LOWER than reality (up to MARGIN steps per reset).
pub const RES_MARGIN_STEPS: u32 = 64;
pub const RES_TRIGGER_STEPS: u32 = 16;
/// Pod wear is persisted as an upper bound: wear + margin, refreshed every `WEAR_WRITE_PERIOD_S`.
pub const WEAR_MARGIN_S: u32 = 600;
pub const WEAR_WRITE_PERIOD_S: u32 = 300;
/// Wait this long for the seq ceiling write before a command is refused.
pub const SEQ_PERSIST_TIMEOUT_MS: u64 = 500;

// ---------------------------------------------------------------------------------------------
// BLE
// ---------------------------------------------------------------------------------------------
pub const ATT_MTU: u16 = 247;
pub const ADV_INTERVAL_MS: u64 = 1_000;
/// Frames are at most FRAME_MAX = 244 bytes (MTU 247 - 3).
pub const FRAME_BUF: usize = openpatch_proto::FRAME_MAX;
pub const MAX_BONDS: usize = 2;

// ---------------------------------------------------------------------------------------------
// Bench defaults (headless runs; env OPENPATCH_BENCH_* at build time, see build.rs)
// ---------------------------------------------------------------------------------------------
const fn parse_u32(s: Option<&str>, default: u32) -> u32 {
    let Some(s) = s else { return default };
    let b = s.as_bytes();
    let mut v: u32 = 0;
    let mut i = 0;
    while i < b.len() {
        let c = b[i];
        assert!(c >= b'0' && c <= b'9', "OPENPATCH_BENCH_*: digits only");
        v = v * 10 + (c - b'0') as u32;
        i += 1;
    }
    v
}

/// Pulses, amount per pulse (mU, multiple of 50), pause (ms), reservoir fill (mU).
pub const BENCH_PULSES: u32 = parse_u32(option_env!("OPENPATCH_BENCH_PULSES"), 10);
pub const BENCH_AMOUNT_MU: u32 = parse_u32(option_env!("OPENPATCH_BENCH_AMOUNT_MU"), 1_000);
pub const BENCH_PAUSE_MS: u32 = parse_u32(option_env!("OPENPATCH_BENCH_PAUSE_MS"), 30_000);
pub const BENCH_FILL_MU: u32 = parse_u32(option_env!("OPENPATCH_BENCH_FILL_MU"), 50_000);
const _: () = assert!(BENCH_PULSES >= 1 && BENCH_PULSES <= 65_535);
const _: () = assert!(BENCH_AMOUNT_MU % 50 == 0 && BENCH_AMOUNT_MU > 0);
