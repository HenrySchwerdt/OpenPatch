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
//! * `Nfp608_26_45G1_1` (coaxial, NOT the current CAD): 20 x 26.45 = 529 steps/turn -> 2 611 000 / 529 uU
//!   = 4 935.5 uU/step
//! * `Nfp608_26_45G16_20` (**primary, matches the current CAD**: GHW module 0.3 step-down pair, 16 T on the
//!   motor, 20 T on the screw, screw advance per motor turn 16/20 = 0.8, total ratio 26.45 / 0.8 = 33.0625 =
//!   529/16): 661.25 steps/turn -> 2 088 800 / 529 uU = 3 948.6 uU/step (0.003949 U; the mechanical report
//!   quotes 0.00395 / 0.003951 with a 74.63 mm^2 area). `gear_ratio_x100` is 3306 (33.0625 rounded to
//!   0.01): it only feeds the angle plausibility check (0.0076 % off), the dose uses the exact rational.
//! * `Nfp608_26_45Cup59Miter1_1` (**v0.1.0 cup pod, current CAD**, default of `scripts/build.sh`, id 0x27): miter pair 1:1,
//!   stadium bore 20.5 x 5.9 (challenge-review pass 2026-11-24): 897 624 525 / 119 554 uU = 7 508.1 uU/step (0.007508 U),
//!   133 steps per U, derivation at the constant. No suction draw.
//! * `Nfp608_26_45CupMiter1_1` (v0.1.0 cup pod, PREVIOUS bore 20.5 x 5.5, id 0x26, kept for pods built with that tank):
//!   840 503 125 / 119 554 uU = 7 030.3 uU/step (0.00703 U), 142 steps per U, derivation at the constant. No suction draw.
//! * `Nfp608_26_45G15_12` (purchased gear pair, 15 T on the motor, 12 T on the screw, effective ratio
//!   26.45 x 12/15 = 21.16): 423.2 steps/turn -> 3 263 750 / 529 uU = 6 169.7 uU/step. NOT the pair in the
//!   current CAD (it does not clear the carriage lane); kept as an option only
//! * `SyringeRig1ml` (bench rig, NFP direct, plunger of a 1 ml U100 syringe, area VERIFY):
//!   0.35 mm / 529 * 17.94 mm^2 / 10 -> 627 900 / 529 uU = 1 186.9 uU/step
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
    /// NFP-608-26.45-SGM geared stepper, coaxial with the leadscrew (20 steps/rev, ratio 26.45).
    Nfp608_26_45G1_1 = 0x20,
    /// Zhaowei ZWBPD006006, 1-stage ratio 6.43.
    Zwbpd006006_6_43 = 0x21,
    /// Zhaowei ZWBPD006006, 1-stage ratio 4.8.
    Zwbpd006006_4_8 = 0x22,
    /// Faulhaber ADM0620 + 16:1.
    FaulhaberAdm0620_16 = 0x23,
    /// NFP-608-26.45 + gear pair 15 T (motor) -> 12 T (screw). Not the pair of the current CAD: option only.
    Nfp608_26_45G15_12 = 0x24,
    /// Primary: NFP-608-26.45 + GHW module 0.3 step-down pair 16 T (motor) -> 20 T (screw), total ratio
    /// 33.0625 (matches the current CAD, `mechanical/params.json`).
    Nfp608_26_45G16_20 = 0x25,
    /// v0.1.0 "cup" pod: NFP-608-26.45 -> miter bevel pair z16:z16 (1:1) -> M1.6 x 0.35 rod rotating into a cup plunger in a
    /// stadium bore 20.5 x 5.5 mm (106.26 mm^2). NO check valve: this pod never aspirates (`Preset::allows_draw` is false).
    Nfp608_26_45CupMiter1_1 = 0x26,
    /// v0.1.0 "cup" pod after the challenge-review pass (mechanics 2026-11-24): the same drive as 0x26 but the stadium bore is
    /// 20.5 x 5.9 mm (113.48 mm^2), +6.8 % per step. NO check valve: never aspirates (`Preset::allows_draw` is false).
    Nfp608_26_45Cup59Miter1_1 = 0x27,
    /// Insulin BENCH RIG: NFP direct pushing a standard 1 ml U100 syringe plunger. The barrel area
    /// is an assumed 17.94 mm^2 (ID 4.78 mm): VERIFY against the measured barrel ID of the rig.
    SyringeRig1ml = 0x30,
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
    /// Plunger face area of the reservoir in 0.01 mm^2 (the SAME area the `uu_num / uu_den` derivation uses, rounded to
    /// 0.01 mm^2): converts a plunger TRAVEL into a volume or a step count for THIS drive (lost motion / take-up).
    /// 74.60 mm^2 (16 x 5 stadium, bench pods), 106.26 mm^2 (cup pod 20.5 x 5.5), 113.48 mm^2 (cup pod 20.5 x 5.9), 17.94 mm^2 (1 ml syringe rig).
    pub bore_area_x100: u32,
}

impl Preset {
    /// Volume swept by a plunger travel of `um` micrometre on this preset's bore, in uU (1 um x 0.01 mm^2 = 1 uU). Exact.
    pub const fn travel_um_to_uu(&self, um: u32) -> u64 {
        um as u64 * self.bore_area_x100 as u64
    }

    /// Motor steps that cover a plunger travel of `um` micrometre, ROUNDED UP (a take-up must cover the play). Exact rational:
    /// `steps = ceil(um x area_x100 x uu_den / uu_num)`; 0 for a preset without a valid per-step volume.
    pub const fn travel_um_to_steps(&self, um: u32) -> u32 {
        if self.uu_num == 0 {
            return 0;
        }
        let n = self.travel_um_to_uu(um) * self.uu_den as u64;
        ((n + self.uu_num as u64 - 1) / self.uu_num as u64) as u32
    }

    /// Whether the suction draw (`FillMode::Draw`: the motor retracts the plunger and the pod pulls fluid in by itself) is
    /// allowed. The cup pod (both bores, 0x26 and 0x27) has no check valve between the tank and the needle: a suction draw could aspirate from the
    /// cannula side, so it is refused there. Only the assisted pressure fill (the user pushes, the motor retracts at a
    /// fixed rate) exists on that pod.
    pub const fn allows_draw(&self) -> bool {
        !matches!(self.id, DriveId::Nfp608_26_45CupMiter1_1 | DriveId::Nfp608_26_45Cup59Miter1_1)
    }

    pub const fn cal(&self) -> PulseCal {
        PulseCal {
            uu_num: self.uu_num,
            uu_den: self.uu_den,
            turn_x100: self.steps_per_rev as u32 * self.gear_ratio_x100 as u32,
        }
    }
}

pub const NFP_608_2645_G1_1: Preset =
    Preset { id: DriveId::Nfp608_26_45G1_1, steps_per_rev: 20, gear_ratio_x100: 2645, uu_num: 2_611_000, uu_den: 529, bore_area_x100: 7460 };
/// NOT the pair of the current CAD (option only). Effective ratio 26.45 * 12/15 = 21.16 (x100 = 2116, exact);
/// 0.35 * 12 / (20 * 26.45 * 15) * 7.46 U.
pub const NFP_608_2645_G15_12: Preset =
    Preset { id: DriveId::Nfp608_26_45G15_12, steps_per_rev: 20, gear_ratio_x100: 2116, uu_num: 3_263_750, uu_den: 529, bore_area_x100: 7460 };
/// PRIMARY. GHW 16 T (motor) : 20 T (screw): total ratio 26.45 / 0.8 = 33.0625 = 529/16 (x100 = 3306.25, stored
/// rounded as 3306); uU/step = 130 550 / 33.0625 = 130 550 * 16 / 529 = 2 088 800 / 529 (exact).
pub const NFP_608_2645_G16_20: Preset =
    Preset { id: DriveId::Nfp608_26_45G16_20, steps_per_rev: 20, gear_ratio_x100: 3306, uu_num: 2_088_800, uu_den: 529, bore_area_x100: 7460 };
/// v0.1.0 CUP POD, PREVIOUS BORE (superseded by [`NFP_608_2645_CUP59_MITER_1_1`] since the challenge-review pass 2026-11-24;
/// kept for pods built with the 5.5 tank: a pod must report the preset of the tank it really has). Bore 20.5 x 5.5, bore_area 106.258 mm^2, u_per_step 0.0070303; the
/// V010-CUP.md table still says 20.3, the regenerated CAD data says 20.5). Miter pair 1:1 -> rod turns once per gearhead turn,
/// so the ratio stays 26.45 (x100 = 2645, exact) and the angle check sees 20 x 26.45 = 529 steps per rod turn.
/// Stadium area, exact rational: A = h (w - h) + pi (h/2)^2 with h = 5.5, w = 20.5, pi ~ 355/113 (rel. error 8.5e-8):
///   A = 82.5 + (355/113)(121/16) = 192115 / 1808 mm^2 = 106.2583 mm^2.
/// 1 U = 10 mm^3 = 1e6 uU, so 1 mm^3 = 1e5 uU. Advance per step = 0.35 / (20 x 26.45) = 0.35 / 529 mm.
/// uU/step = (0.35 / 529) x (192115 / 1808) x 1e5 = 35000 x 192115 / (529 x 1808) = 840 503 125 / 119 554 = 7 030.32 uU
/// (0.00703 U). Fits u32; `pulses_to_micro` widens to u64.
pub const NFP_608_2645_CUP_MITER_1_1: Preset =
    Preset { id: DriveId::Nfp608_26_45CupMiter1_1, steps_per_rev: 20, gear_ratio_x100: 2645, uu_num: 840_503_125, uu_den: 119_554, bore_area_x100: 10626 };
/// v0.1.0 CUP POD, CURRENT CAD (mechanics commit 7879e22, `mechanical/out/v010-cup/*.mech.json`: bore 20.5 x 5.9, bore_area
/// 113.4797 mm^2, u_per_step 0.0075081). Same drive as 0x26 (miter 1:1, ratio 26.45, 529 steps per rod turn), only the bore changed.
/// Stadium area, exact rational: A = h (w - h) + pi (h/2)^2 with h = 5.9, w = 20.5, pi ~ 355/113 (rel. error 8.5e-8):
///   A = 86.14 + (355/113)(3481/400) = 5 129 283 / 45 200 mm^2 = 113.4797 mm^2 (CAD with exact pi: 113.4797, rel. 2e-8).
/// uU/step = (0.35 / 529) x (5 129 283 / 45 200) x 1e5 = 35000 x 5 129 283 / (529 x 45 200) = 897 624 525 / 119 554 = 7 508.11 uU
/// (0.007508 U, +6.8 % vs 0x26). Fits u32 (< 2^32); `pulses_to_micro` widens to u64. The CAD tank is 132.5 / 239.3 U, but the
/// reservoir capacity stays the nominal `CAPACITY_100` / `CAPACITY_200` (a capacity is not part of a preset).
pub const NFP_608_2645_CUP59_MITER_1_1: Preset =
    Preset { id: DriveId::Nfp608_26_45Cup59Miter1_1, steps_per_rev: 20, gear_ratio_x100: 2645, uu_num: 897_624_525, uu_den: 119_554, bore_area_x100: 11348 };
/// VERIFY: barrel area 17.94 mm^2 is an assumption (BD-class 1 ml U100, ID 4.78 mm) until the
/// mechanics agent publishes the measured value. uU/step = 0.35 / 529 * 17.94 / 10 * 1e6.
pub const SYRINGE_RIG_1ML: Preset =
    Preset { id: DriveId::SyringeRig1ml, steps_per_rev: 20, gear_ratio_x100: 2645, uu_num: 627_900, uu_den: 529, bore_area_x100: 1794 };
pub const ZWBPD006006_6_43: Preset =
    Preset { id: DriveId::Zwbpd006006_6_43, steps_per_rev: 20, gear_ratio_x100: 643, uu_num: 13_055_000, uu_den: 643, bore_area_x100: 7460 };
pub const ZWBPD006006_4_8: Preset =
    Preset { id: DriveId::Zwbpd006006_4_8, steps_per_rev: 20, gear_ratio_x100: 480, uu_num: 1_305_500, uu_den: 48, bore_area_x100: 7460 };
pub const FAULHABER_ADM0620_16: Preset =
    Preset { id: DriveId::FaulhaberAdm0620_16, steps_per_rev: 20, gear_ratio_x100: 1600, uu_num: 130_550, uu_den: 16, bore_area_x100: 7460 };
#[cfg(feature = "test-calibrations")]
pub const TEST_26100: Preset =
    Preset { id: DriveId::Test26100, steps_per_rev: 16, gear_ratio_x100: 1600, uu_num: 26_100, uu_den: 1, bore_area_x100: 7460 };
#[cfg(feature = "test-calibrations")]
pub const TEST_8156: Preset =
    Preset { id: DriveId::Test8156, steps_per_rev: 16, gear_ratio_x100: 1600, uu_num: 8_156, uu_den: 1, bore_area_x100: 7460 };

/// All presets available in this build.
pub const PRESETS: &[Preset] = &[
    NFP_608_2645_G1_1,
    NFP_608_2645_G15_12,
    NFP_608_2645_G16_20,
    NFP_608_2645_CUP_MITER_1_1,
    NFP_608_2645_CUP59_MITER_1_1,
    SYRINGE_RIG_1ML,
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
