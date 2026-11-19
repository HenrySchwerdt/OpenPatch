//! Unit newtypes. Mixing them up (the classic U/step mistake: 10:1 vs 5:1 drive = 2x dose) is a
//! compile error: the only way from insulin volume to steps and back is a [`MicroUnitsPerStep`].
//!
//! Conventions (integer only, no floats anywhere in the core):
//! * `MilliUnits` (mU) = 0.001 U of insulin (U100: 1 U = 10 ul)
//! * `MicroUnits` (uU) = 0.000001 U
//! * `MilliUnitsPerHour` = rate
//! * `Pulses` = actuator pulses = full motor steps; `AngleCounts` = 1/4096 turn of the leadscrew
//!   (TMAG5273 angle)
//! * `Millis` = milliseconds (durations and monotonic timestamps)

use core::ops::{Add, AddAssign, Sub};

macro_rules! newtype {
    ($(#[$m:meta])* $name:ident($inner:ty)) => {
        $(#[$m])*
        #[derive(Clone, Copy, Debug, Default, PartialEq, Eq, PartialOrd, Ord, Hash)]
        pub struct $name(pub $inner);
        impl Add for $name {
            type Output = $name;
            #[inline]
            fn add(self, o: $name) -> $name { $name(self.0 + o.0) }
        }
        impl AddAssign for $name {
            #[inline]
            fn add_assign(&mut self, o: $name) { self.0 += o.0; }
        }
        impl Sub for $name {
            type Output = $name;
            #[inline]
            fn sub(self, o: $name) -> $name { $name(self.0 - o.0) }
        }
        #[cfg(feature = "defmt")]
        impl defmt::Format for $name {
            fn format(&self, f: defmt::Formatter) { defmt::write!(f, "{}({})", stringify!($name), self.0) }
        }
    };
}

newtype!(/// Insulin volume in milli-units (0.001 U).
    MilliUnits(u32));
newtype!(/// Insulin volume in micro-units (0.000001 U).
    MicroUnits(u64));
newtype!(/// Delivery rate in mU/h.
    MilliUnitsPerHour(u32));
newtype!(/// Actuator pulses (generic: one pulse = one full motor step of the stepper drive).
    Pulses(u32));
newtype!(/// Cumulative leadscrew angle in counts of 1/4096 turn (TMAG5273 12-bit angle, unwrapped). Signed.
    AngleCounts(i64));
newtype!(/// Milliseconds.
    Millis(u64));
newtype!(/// Minutes (temp basal durations, wear).
    Minutes(u32));

/// Angle counts per leadscrew turn.
pub const ANGLE_COUNTS_PER_TURN: i64 = 4096;
impl MilliUnits {
    #[inline]
    pub const fn to_micro(self) -> MicroUnits {
        MicroUnits(self.0 as u64 * 1000)
    }
}

impl Millis {
    pub const MINUTE: Millis = Millis(60_000);
    pub const HOUR: Millis = Millis(3_600_000);
    #[inline]
    pub const fn from_secs(s: u64) -> Millis {
        Millis(s * 1000)
    }
    #[inline]
    pub const fn from_minutes(m: u32) -> Millis {
        Millis(m as u64 * 60_000)
    }
    #[inline]
    pub const fn as_secs(self) -> u64 {
        self.0 / 1000
    }
    #[inline]
    pub const fn as_minutes(self) -> u64 {
        self.0 / 60_000
    }
}

/// Drive calibration as an EXACT rational: insulin per pulse = `uu_num / uu_den` micro-units, and
/// the leadscrew advances `100 / turn_x100` turn per pulse (`turn_x100` = pulses per leadscrew
/// turn x 100, e.g. 52 900 for 20 steps x 26.45:1 = 529 steps/turn).
/// `uu_num == 0` or `uu_den == 0` = missing/invalid: every conversion yields zero.
///
/// SAFETY CRITICAL: the only way from volume to pulses and back (so U/pulse mix-ups between gear /
/// pawl configurations are compile errors, not silent over-delivery).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct PulseCal {
    pub uu_num: u32,
    pub uu_den: u32,
    pub turn_x100: u32,
}

impl PulseCal {
    pub const NONE: PulseCal = PulseCal { uu_num: 0, uu_den: 1, turn_x100: 0 };

    #[inline]
    pub const fn is_none(self) -> bool {
        self.uu_num == 0 || self.uu_den == 0 || self.turn_x100 == 0
    }

    /// Whole micro-units per pulse (floor), as reported on the wire.
    pub const fn micro_u_floor(self) -> u32 {
        if self.uu_den == 0 {
            0
        } else {
            self.uu_num / self.uu_den
        }
    }

    /// Volume of `p` pulses in uU (floor).
    #[inline]
    pub fn pulses_to_micro(self, p: Pulses) -> MicroUnits {
        if self.is_none() {
            return MicroUnits(0);
        }
        MicroUnits(p.0 as u64 * self.uu_num as u64 / self.uu_den as u64)
    }

    /// Volume of `p` pulses in mU (floor).
    #[inline]
    pub fn pulses_to_mu(self, p: Pulses) -> MilliUnits {
        if self.is_none() {
            return MilliUnits(0);
        }
        MilliUnits((p.0 as u64 * self.uu_num as u64 / (self.uu_den as u64 * 1000)) as u32)
    }

    /// Whole pulses in `mu` (floor); 0 without calibration.
    #[inline]
    pub fn mu_to_pulses(self, mu: MilliUnits) -> Pulses {
        if self.is_none() {
            return Pulses(0);
        }
        Pulses((mu.0 as u64 * 1000 * self.uu_den as u64 / self.uu_num as u64) as u32)
    }

    /// Expected cumulative leadscrew angle of `p` pulses (floor).
    #[inline]
    pub fn expected_angle(self, p: Pulses) -> AngleCounts {
        if self.turn_x100 == 0 {
            return AngleCounts(0);
        }
        AngleCounts(p.0 as i64 * ANGLE_COUNTS_PER_TURN * 100 / self.turn_x100 as i64)
    }

    /// Expected angle of one pulse in 1/1000 counts (e.g. 529 steps/turn: 7742 = 7.74 counts).
    #[inline]
    pub fn angle_per_pulse_x1000(self) -> i64 {
        if self.turn_x100 == 0 {
            0
        } else {
            ANGLE_COUNTS_PER_TURN * 100_000 / self.turn_x100 as i64
        }
    }

    /// Angle corresponding to `mu` (floor).
    pub fn mu_to_angle(self, mu: MilliUnits) -> AngleCounts {
        if self.is_none() {
            return AngleCounts(0);
        }
        let p_num = mu.0 as i128 * 1000 * self.uu_den as i128 * ANGLE_COUNTS_PER_TURN as i128 * 100;
        AngleCounts((p_num / (self.uu_num as i128 * self.turn_x100 as i128)) as i64)
    }

    /// Delivery-engine accumulator threshold: `uu_num * 3600` (engine accumulates `rate*ms*uu_den`).
    #[inline]
    pub(crate) fn threshold(self) -> i64 {
        self.uu_num as i64 * crate::limits::SCALED_PER_UU
    }
}
