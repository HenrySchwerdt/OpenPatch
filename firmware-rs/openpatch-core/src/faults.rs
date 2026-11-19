//! Latched fault bits (protocol section 4.1).

use core::ops::{BitAnd, BitOr, BitOrAssign, Not};

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct Faults(pub u16);

impl Faults {
    pub const NONE: Faults = Faults(0);
    /// (commanded - angle-confirmed) > 2 U, spindle stands still, or sustained motor-current rise.
    pub const OCCLUSION: Faults = Faults(1 << 0);
    pub const ENCODER_DEVIATION: Faults = Faults(1 << 1);
    pub const RESERVOIR_EMPTY: Faults = Faults(1 << 2);
    pub const BATTERY_CRITICAL: Faults = Faults(1 << 3);
    /// Veto by the 15 U/h window or the per-minute backstop.
    pub const LIMIT_EXCEEDED: Faults = Faults(1 << 4);
    /// Motor did not execute approved steps / angle sensor missing.
    pub const INTERNAL: Faults = Faults(1 << 5);
    /// Drive calibration missing / invalid: no step is ever approved; cannot be acknowledged.
    pub const NO_CALIBRATION: Faults = Faults(1 << 6);
    /// >= 52 h since activation: delivery stopped, cleared only by a new Activate.
    pub const WEAR_EXPIRED: Faults = Faults(1 << 7);
    pub const ALL: Faults = Faults(0xFFFF);

    #[inline]
    pub const fn bits(self) -> u16 {
        self.0
    }
    #[inline]
    pub const fn is_empty(self) -> bool {
        self.0 == 0
    }
    #[inline]
    pub const fn contains(self, o: Faults) -> bool {
        self.0 & o.0 == o.0
    }
    #[inline]
    pub const fn intersects(self, o: Faults) -> bool {
        self.0 & o.0 != 0
    }
}

impl BitOr for Faults {
    type Output = Faults;
    #[inline]
    fn bitor(self, o: Faults) -> Faults {
        Faults(self.0 | o.0)
    }
}
impl BitOrAssign for Faults {
    #[inline]
    fn bitor_assign(&mut self, o: Faults) {
        self.0 |= o.0;
    }
}
impl BitAnd for Faults {
    type Output = Faults;
    #[inline]
    fn bitand(self, o: Faults) -> Faults {
        Faults(self.0 & o.0)
    }
}
impl Not for Faults {
    type Output = Faults;
    #[inline]
    fn not(self) -> Faults {
        Faults(!self.0)
    }
}
