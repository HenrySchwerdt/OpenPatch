//! Battery voltage from the SAADC `VDDHDIV5` channel, and the battery thresholds of the cup board v4.
//!
//! On the 45-part board the cell is wired to the HJ-840's `VDDH` pad (high-voltage mode, no LDO, `FIRMWARE-PINMAP.md` "v4 HJ-840
//! pin table"), so there is no sense divider and no sense pin: the SAADC measures `VDDH / 5` on the internal `VDDHDIV5` input
//! (nRF52840 product specification, SAADC `CH[n].PSELP = 0x0D`). The conversion is a pure function so it can be tested on the host.
//!
//! Conversion (single ended, internal 0.6 V reference, gain 1/6, i.e. a 3.6 V full scale at the input):
//! `V(VDDH) = raw x 3600 x 5 / 2^resolution` mV. At 12 bit one LSB is 4.39 mV of cell voltage, at 14 bit 1.10 mV. Negative results
//! (noise around 0 in single ended mode) clamp to 0.

/// SAADC full scale at the input with the internal reference and gain 1/6 (0.6 V x 6), mV.
pub const SAADC_FULL_SCALE_MV: u32 = 3_600;
/// `VDDHDIV5` divides VDDH by 5.
pub const VDDHDIV5_DIV: u32 = 5;
/// Highest VDDH that the input range can show (3.6 V x 5 = 18 V); the cell never gets near it.
pub const VDDH_MAX_MV: u32 = SAADC_FULL_SCALE_MV * VDDHDIV5_DIV;

/// No motor start below this open-circuit cell voltage (`FIRMWARE-PINMAP.md` "Motor supply and undervoltage lockout": cell
/// sag under 0.6 A plus the protection chip's cut-off at 2.5 to 2.9 V leave no margin below it). Measured at rest, no charger.
pub const MOTOR_MIN_VBAT_MV: u16 = 3_400;
/// Re-measured after the first 20 steps: below this under load the burst stops and retries only after a rest.
pub const MOTOR_LOAD_FLOOR_MV: u16 = 3_000;
/// Number of steps after which the loaded cell voltage is checked.
pub const MOTOR_LOAD_CHECK_STEPS: u32 = 20;
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

/// May the motor start at this open-circuit voltage (cell at rest, no charger)?
pub const fn motor_start_allowed(open_circuit_mv: u16, charger_present: bool) -> bool {
    !charger_present && open_circuit_mv >= MOTOR_MIN_VBAT_MV
}

/// Loaded check after [`MOTOR_LOAD_CHECK_STEPS`] steps: false = stop the burst, retry only after a rest.
pub const fn loaded_voltage_ok(loaded_mv: u16) -> bool {
    loaded_mv >= MOTOR_LOAD_FLOOR_MV
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
