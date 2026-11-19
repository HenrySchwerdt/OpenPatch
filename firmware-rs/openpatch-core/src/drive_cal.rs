//! Drive calibration: how much insulin one motor step delivers, as an EXACT rational, plus the
//! angle geometry used to verify the drive with the leadscrew angle sensor.
//!
//! SAFETY CRITICAL. The per-step volume scales every dose. Therefore: exact rational uU/step, one
//! preset per physical motor/gear ratio (exact published ratios, e.g. 26.45 = 2645/100), NO implicit
//! default (the application selects a preset at compile time and fails to build otherwise), magic +
//! CRC-32, the stored record must equal the preset of its drive id, and the supervisor refuses all
//! delivery without a valid calibration. The preset id travels in `GetStatus` (`DRIVE_CAL`).
//!
//! `U/step = 0.35 mm / (steps_per_rev * ratio) * 74.6 mm^2 / 10` (M1.6 x 0.35 leadscrew, 74.6 mm^2
//! reservoir, U100: 1 U = 10 ul), i.e. `uU/step = 130 550 / ratio`:
//! * `Nfp608_26_45`: 20 x 26.45 = 529 steps/turn -> 2 611 000 / 529 uU = 4 935.5 uU/step
//! * `Zwbpd006006_6_43`: 20 x 6.43 -> 13 055 000 / 643 uU = 20 303.3 uU/step
//! * `Zwbpd006006_4_8`: 20 x 4.8 -> 1 305 500 / 48 uU = 27 197.9 uU/step
//! * `FaulhaberAdm0620_16`: 20 x 16 -> 130 550 / 16 uU = 8 159.4 uU/step

use crate::limits::{CAL_UU_MAX, CAL_UU_MIN};
use crate::units::PulseCal;
use openpatch_proto::Error;

pub const DRIVE_CAL_MAGIC: u32 = 0x4F50_4443; // "OPDC"

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
#[repr(u16)]
pub enum DriveId {
    /// Primary: NFP-608-26.45-SGM geared stepper (20 steps/rev, ratio 26.45).
    Nfp608_26_45 = 0x20,
    /// Zhaowei ZWBPD006006, 1-stage ratio 6.43.
    Zwbpd006006_6_43 = 0x21,
    /// Zhaowei ZWBPD006006, 1-stage ratio 4.8.
    Zwbpd006006_4_8 = 0x22,
    /// Faulhaber ADM0620 + 16:1.
    FaulhaberAdm0620_16 = 0x23,
    /// HOST TESTS ONLY (feature `test-calibrations`): 26 100 uU/step, 256 steps/turn (16 counts/step).
    #[cfg(feature = "test-calibrations")]
    Test26100 = 0x7F01,
    /// HOST TESTS ONLY: 8 156 uU/step, 256 steps/turn.
    #[cfg(feature = "test-calibrations")]
    Test8156 = 0x7F02,
}

/// Static description of one preset.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Preset {
    pub id: DriveId,
    /// Motor full steps per motor revolution.
    pub steps_per_rev: u16,
    /// Gear ratio x 100 (26.45 -> 2645).
    pub gear_ratio_x100: u16,
    pub uu_num: u32,
    pub uu_den: u32,
}

impl Preset {
    pub const fn cal(&self) -> PulseCal {
        PulseCal {
            uu_num: self.uu_num,
            uu_den: self.uu_den,
            turn_x100: self.steps_per_rev as u32 * self.gear_ratio_x100 as u32,
        }
    }
}

pub const NFP_608_2645: Preset =
    Preset { id: DriveId::Nfp608_26_45, steps_per_rev: 20, gear_ratio_x100: 2645, uu_num: 2_611_000, uu_den: 529 };
pub const ZWBPD006006_6_43: Preset =
    Preset { id: DriveId::Zwbpd006006_6_43, steps_per_rev: 20, gear_ratio_x100: 643, uu_num: 13_055_000, uu_den: 643 };
pub const ZWBPD006006_4_8: Preset =
    Preset { id: DriveId::Zwbpd006006_4_8, steps_per_rev: 20, gear_ratio_x100: 480, uu_num: 1_305_500, uu_den: 48 };
pub const FAULHABER_ADM0620_16: Preset =
    Preset { id: DriveId::FaulhaberAdm0620_16, steps_per_rev: 20, gear_ratio_x100: 1600, uu_num: 130_550, uu_den: 16 };
#[cfg(feature = "test-calibrations")]
pub const TEST_26100: Preset =
    Preset { id: DriveId::Test26100, steps_per_rev: 16, gear_ratio_x100: 1600, uu_num: 26_100, uu_den: 1 };
#[cfg(feature = "test-calibrations")]
pub const TEST_8156: Preset =
    Preset { id: DriveId::Test8156, steps_per_rev: 16, gear_ratio_x100: 1600, uu_num: 8_156, uu_den: 1 };

/// All presets available in this build.
pub const PRESETS: &[Preset] = &[
    NFP_608_2645,
    ZWBPD006006_6_43,
    ZWBPD006006_4_8,
    FAULHABER_ADM0620_16,
    #[cfg(feature = "test-calibrations")]
    TEST_26100,
    #[cfg(feature = "test-calibrations")]
    TEST_8156,
];

impl DriveId {
    pub fn from_u16(v: u16) -> Option<DriveId> {
        PRESETS.iter().find(|p| p.id as u16 == v).map(|p| p.id)
    }
    pub fn preset(self) -> &'static Preset {
        PRESETS.iter().find(|p| p.id == self).expect("preset table covers every DriveId")
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct DriveCal {
    pub magic: u32,
    pub drive_id: u16,
    pub steps_per_rev: u16,
    pub gear_ratio_x100: u16,
    pub reserved: u16,
    pub uu_num: u32,
    pub uu_den: u32,
    pub crc32: u32,
}

fn crc32(data: &[u8]) -> u32 {
    let mut crc = !0u32;
    for &b in data {
        crc ^= b as u32;
        for _ in 0..8 {
            crc = (crc >> 1) ^ (0xEDB8_8320 & 0u32.wrapping_sub(crc & 1));
        }
    }
    !crc
}

impl DriveCal {
    /// Little-endian serialisation of everything before the CRC (20 bytes).
    fn crc_input(&self) -> [u8; 20] {
        let mut b = [0u8; 20];
        b[0..4].copy_from_slice(&self.magic.to_le_bytes());
        b[4..6].copy_from_slice(&self.drive_id.to_le_bytes());
        b[6..8].copy_from_slice(&self.steps_per_rev.to_le_bytes());
        b[8..10].copy_from_slice(&self.gear_ratio_x100.to_le_bytes());
        b[10..12].copy_from_slice(&self.reserved.to_le_bytes());
        b[12..16].copy_from_slice(&self.uu_num.to_le_bytes());
        b[16..20].copy_from_slice(&self.uu_den.to_le_bytes());
        b
    }

    pub fn compute_crc(&self) -> u32 {
        crc32(&self.crc_input())
    }

    /// Record of a preset (magic and CRC set).
    pub fn from_preset(p: &Preset) -> DriveCal {
        let mut c = DriveCal {
            magic: DRIVE_CAL_MAGIC,
            drive_id: p.id as u16,
            steps_per_rev: p.steps_per_rev,
            gear_ratio_x100: p.gear_ratio_x100,
            reserved: 0,
            uu_num: p.uu_num,
            uu_den: p.uu_den,
            crc32: 0,
        };
        c.crc32 = c.compute_crc();
        c
    }

    /// Preset for a known drive id. `BadArg` for unknown ids.
    pub fn preset(id: u16) -> Result<DriveCal, Error> {
        PRESETS.iter().find(|p| p.id as u16 == id).map(DriveCal::from_preset).ok_or(Error::BadArg)
    }

    /// `Ok` only if magic and CRC are right, `reserved == 0`, the per-pulse volume is within
    /// range and the record equals the preset of its drive id (a plausible but wrong volume is
    /// refused too).
    pub fn validate(c: Option<&DriveCal>) -> Result<(), Error> {
        let c = c.ok_or(Error::NotFound)?;
        if c.magic != DRIVE_CAL_MAGIC {
            return Err(Error::NotFound);
        }
        if c.crc32 != c.compute_crc() {
            return Err(Error::Crc);
        }
        if c.reserved != 0 || c.uu_den == 0 {
            return Err(Error::BadArg);
        }
        let floor = c.uu_num / c.uu_den;
        if !(CAL_UU_MIN..=CAL_UU_MAX).contains(&floor) {
            return Err(Error::Limit);
        }
        if DriveCal::preset(c.drive_id)? == *c {
            Ok(())
        } else {
            Err(Error::BadArg)
        }
    }

    /// The typed calibration, only for a valid record.
    pub fn pulse_cal(&self) -> Option<PulseCal> {
        DriveCal::validate(Some(self)).ok().map(|_| PulseCal {
            uu_num: self.uu_num,
            uu_den: self.uu_den,
            turn_x100: self.steps_per_rev as u32 * self.gear_ratio_x100 as u32,
        })
    }

    /// Steps per leadscrew revolution x 100 (`steps_per_rev * ratio_x100`), 0 if invalid.
    pub fn turn_x100(&self) -> u32 {
        if DriveCal::validate(Some(self)).is_err() {
            return 0;
        }
        self.steps_per_rev as u32 * self.gear_ratio_x100 as u32
    }

    /// 24-byte little-endian flash image (fields in declaration order, CRC last).
    pub fn to_bytes(&self) -> [u8; 24] {
        let mut b = [0u8; 24];
        b[..20].copy_from_slice(&self.crc_input());
        b[20..].copy_from_slice(&self.crc32.to_le_bytes());
        b
    }

    pub fn from_bytes(b: &[u8; 24]) -> DriveCal {
        let u16at = |i: usize| u16::from_le_bytes([b[i], b[i + 1]]);
        let u32at = |i: usize| u32::from_le_bytes([b[i], b[i + 1], b[i + 2], b[i + 3]]);
        DriveCal {
            magic: u32at(0),
            drive_id: u16at(4),
            steps_per_rev: u16at(6),
            gear_ratio_x100: u16at(8),
            reserved: u16at(10),
            uu_num: u32at(12),
            uu_den: u32at(16),
            crc32: u32at(20),
        }
    }
}
