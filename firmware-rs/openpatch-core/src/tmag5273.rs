//! TMAG5273 3D Hall sensor: register map, angle decoding and CRC, pure and host-testable.
//!
//! Source: TI TMAG5273 datasheet SLYS045C (June 2021, revised April 2026). Section numbers in the
//! comments refer to that revision. VERIFIED AGAINST THE DATASHEET ONLY; nothing has been run on a
//! device (hardware verification is still open, see `firmware-rs/docs/stubs.md`).

/// Table 6-2 (section 6.3.4): factory default 7-bit I2C address per orderable suffix.
pub const ADDR_A: u8 = 0x35;
pub const ADDR_B: u8 = 0x22;
pub const ADDR_C: u8 = 0x78;
pub const ADDR_D: u8 = 0x44;

// Table 8-1 (section 8.1): register offsets.
pub const REG_DEVICE_CONFIG_1: u8 = 0x00;
pub const REG_DEVICE_CONFIG_2: u8 = 0x01;
pub const REG_SENSOR_CONFIG_1: u8 = 0x02;
pub const REG_SENSOR_CONFIG_2: u8 = 0x03;
pub const REG_DEVICE_ID: u8 = 0x0D;
pub const REG_MANUFACTURER_ID_LSB: u8 = 0x0E;
pub const REG_MANUFACTURER_ID_MSB: u8 = 0x0F;
pub const REG_CONV_STATUS: u8 = 0x18;
pub const REG_ANGLE_RESULT_MSB: u8 = 0x19;
pub const REG_ANGLE_RESULT_LSB: u8 = 0x1A;
pub const REG_MAGNITUDE_RESULT: u8 = 0x1B;
pub const REG_DEVICE_STATUS: u8 = 0x1C;

/// Tables 8-17 / 8-18: MANUFACTURER_ID LSB then MSB read as 0x49, 0x54 ("TI").
pub const MANUFACTURER_ID: [u8; 2] = [0x49, 0x54];
/// Table 8-16: DEVICE_ID.VER = 1 for the +-40 mT / +-80 mT parts (A1..D1), 2 for +-133/266 mT.
pub const DEVICE_VER_40MT: u8 = 1;

// Table 8-3 DEVICE_CONFIG_1: CRC_EN bit 7, MAG_TEMPCO 6:5, CONV_AVG 4:2, I2C_RD 1:0.
/// CRC off, no tempco, 1x averaging (10 kSPS 3-axis / 20 kSPS 1-axis), standard 3-byte read.
pub const DEVICE_CONFIG_1_CRC_OFF: u8 = 0x00;
pub const DEVICE_CONFIG_1_CRC_ON: u8 = 0x80;
// Table 8-5 SENSOR_CONFIG_1: MAG_CH_EN 7:4 (3h = X and Y), SLEEPTIME 3:0 (unused in continuous mode).
pub const SENSOR_CONFIG_1_XY: u8 = 0x30;
// Table 8-6 SENSOR_CONFIG_2: ANGLE_EN 3:2 (1h = X first, Y second), X_Y_RANGE bit 1 = 0 (+-40 mT on A1).
pub const SENSOR_CONFIG_2_ANGLE_XY: u8 = 0x04;
// Table 8-4 DEVICE_CONFIG_2: OPERATING_MODE 1:0 (2h = continuous measure), TRIGGER_MODE bit 2 = 0.
pub const DEVICE_CONFIG_2_CONTINUOUS: u8 = 0x02;

/// Section 6.4 / electrical table: standby -> continuous takes tstart_measure (70 us max), power up
/// to standby tstart_power_up (270 us max). We wait a generous 1 ms before the first read.
pub const T_START_POWER_UP_US: u32 = 270;
pub const T_START_MEASURE_US: u32 = 70;

// Table 8-27 CONV_STATUS: SET_COUNT 7:5, POR bit 4 (R/W1C), DIAG_STATUS bit 1, RESULT_STATUS bit 0.
pub const CONV_POR: u8 = 0x10;
pub const CONV_DIAG_FAIL: u8 = 0x02;
pub const CONV_RESULT_READY: u8 = 0x01;
pub const CONV_SET_COUNT_MASK: u8 = 0xE0;

/// Section 6.5.2.3, Figure 6-17: the angle is a 16 bit word {ANGLE_RESULT_MSB, ANGLE_RESULT_LSB};
/// D15:D13 are always 0, D12:D4 = integer degrees (0..359), D3:D0 = fraction in 1/16 degree.
pub const ANGLE_UNITS_PER_TURN: u32 = 360 * 16; // 5760
/// Counts per turn the core uses (`ANGLE_COUNTS_PER_TURN`).
pub const COUNTS_PER_TURN: u32 = 4096;

/// Raw angle in 1/16 degree. `None` if the reserved top bits are not 0 or the value is >= 360
/// degrees (a corrupted transfer or a device that is not in angle mode).
pub fn angle_raw(msb: u8, lsb: u8) -> Option<u16> {
    if msb & 0xE0 != 0 {
        return None;
    }
    let v = ((msb as u16) << 8) | lsb as u16;
    (v < ANGLE_UNITS_PER_TURN as u16).then_some(v)
}

/// Angle in 4096 counts per turn (rounded to nearest, wrapping at a full turn).
pub fn angle_counts(msb: u8, lsb: u8) -> Option<u16> {
    let raw = angle_raw(msb, lsb)? as u32;
    Some(((raw * COUNTS_PER_TURN + ANGLE_UNITS_PER_TURN / 2) / ANGLE_UNITS_PER_TURN) as u16 % COUNTS_PER_TURN as u16)
}

/// Section 6.5.1.3.6: CRC-8, polynomial x^8 + x^2 + x + 1, initial value 0xFF, MSB first, no final XOR.
pub fn crc8(data: &[u8]) -> u8 {
    let mut c: u8 = 0xFF;
    for &b in data {
        c ^= b;
        for _ in 0..8 {
            c = if c & 0x80 != 0 { (c << 1) ^ 0x07 } else { c << 1 };
        }
    }
    c
}

/// Why a sample was rejected.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FrameError {
    /// CRC byte did not match (only when CRC is enabled).
    Crc,
    /// Reserved angle bits set or angle out of range.
    BadAngle,
    /// CONV_STATUS.POR set: the sensor was reset, its configuration is gone (standby mode).
    PowerOnReset,
    /// CONV_STATUS.DIAG_STATUS set (VCC UV, memory CRC, INT pin or clock error).
    Diag,
}

/// One decoded sample.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Sample {
    pub counts: u16,
    /// MAGNITUDE_RESULT (constant over a rotation; useful to detect a missing/decoupled magnet).
    pub magnitude: u8,
    /// Rolling conversion set counter (CONV_STATUS 7:5), for torn-read detection.
    pub set_count: u8,
}

/// Bytes read per sample: CONV_STATUS (0x18), ANGLE_MSB (0x19), ANGLE_LSB (0x1A), MAGNITUDE (0x1B)
/// in one auto-incrementing standard read (section 6.5.1.3.3), plus a fifth CRC byte if CRC_EN.
pub const FRAME_LEN: usize = 4;

/// Decode the 4 register bytes (`[CONV_STATUS, ANGLE_MSB, ANGLE_LSB, MAGNITUDE]`) and, with CRC
/// enabled, check `crc` (datasheet 6.5.1.3.3: CRC over the four register bytes read).
pub fn decode_frame(regs: &[u8; FRAME_LEN], crc: Option<u8>) -> Result<Sample, FrameError> {
    if let Some(c) = crc {
        if crc8(regs) != c {
            return Err(FrameError::Crc);
        }
    }
    let st = regs[0];
    if st & CONV_POR != 0 {
        return Err(FrameError::PowerOnReset);
    }
    if st & CONV_DIAG_FAIL != 0 {
        return Err(FrameError::Diag);
    }
    let counts = angle_counts(regs[1], regs[2]).ok_or(FrameError::BadAngle)?;
    Ok(Sample { counts, magnitude: regs[3], set_count: (st & CONV_SET_COUNT_MASK) >> 5 })
}

/// Section 7.3: result registers are updated at the end of a conversion, so a multi byte read can
/// straddle an update. Compare CONV_STATUS read again after the frame: a changed SET_COUNT means
/// the frame may be torn and must be read again.
pub fn torn(frame_status: u8, status_after: u8) -> bool {
    (frame_status & CONV_SET_COUNT_MASK) != (status_after & CONV_SET_COUNT_MASK)
}

/// Register writes that put the sensor into angle mode (X/Y, continuous, 1x averaging), in order.
/// DEVICE_CONFIG_1 first (CRC / read mode), the mode register LAST (it starts conversions).
pub fn config_writes(crc: bool) -> [(u8, u8); 4] {
    [
        (REG_DEVICE_CONFIG_1, if crc { DEVICE_CONFIG_1_CRC_ON } else { DEVICE_CONFIG_1_CRC_OFF }),
        (REG_SENSOR_CONFIG_1, SENSOR_CONFIG_1_XY),
        (REG_SENSOR_CONFIG_2, SENSOR_CONFIG_2_ANGLE_XY),
        (REG_DEVICE_CONFIG_2, DEVICE_CONFIG_2_CONTINUOUS),
    ]
}
