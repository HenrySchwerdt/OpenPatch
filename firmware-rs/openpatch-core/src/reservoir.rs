//! Reservoir model: fill volume, consumed steps, remaining volume, low alarm.

use crate::limits::DEFAULT_LOW_RESERVOIR;
use crate::units::{PulseCal, MilliUnits, Pulses};
use openpatch_proto::Error;

#[derive(Clone, Copy, Debug)]
pub struct Reservoir {
    capacity: MilliUnits,
    cal: PulseCal,
    fill: MilliUnits,
    consumed: Pulses,
    low_threshold: MilliUnits,
    filled: bool,
}

impl Reservoir {
    pub fn new(capacity: MilliUnits, cal: PulseCal) -> Self {
        Self {
            capacity,
            cal,
            fill: MilliUnits(0),
            consumed: Pulses(0),
            low_threshold: DEFAULT_LOW_RESERVOIR,
            filled: false,
        }
    }

    /// `fill` in (0, capacity]; resets consumption.
    pub fn fill(&mut self, fill: MilliUnits) -> Result<(), Error> {
        if fill.0 == 0 {
            return Err(Error::BadArg);
        }
        if fill > self.capacity {
            return Err(Error::Limit);
        }
        self.fill = fill;
        self.consumed = Pulses(0);
        self.filled = true;
        Ok(())
    }

    /// Boot: restore a persisted state (the platform stores it with a safety margin).
    pub fn restore(&mut self, fill: MilliUnits, consumed: Pulses) {
        self.fill = fill;
        self.consumed = consumed;
        self.filled = fill.0 != 0;
    }

    /// Draw (refill by reversing the plunger): add `drawn` steps worth of insulin. Exact in steps:
    /// first the consumed-steps counter shrinks, anything beyond that raises the fill level (floored
    /// to mU, i.e. conservative) up to the capacity.
    pub fn draw_in(&mut self, drawn: Pulses) {
        if drawn.0 <= self.consumed.0 && self.filled {
            self.consumed = Pulses(self.consumed.0 - drawn.0);
            return;
        }
        let extra = if self.filled { Pulses(drawn.0 - self.consumed.0) } else { drawn };
        let base = if self.filled { self.fill } else { MilliUnits(0) };
        let level = (base.0 as u64 + self.cal.pulses_to_mu(extra).0 as u64).min(self.capacity.0 as u64) as u32;
        self.fill = MilliUnits(level);
        self.consumed = Pulses(0);
        self.filled = level > 0;
    }

    pub fn set_low_threshold(&mut self, t: MilliUnits) -> Result<(), Error> {
        if t > self.capacity {
            return Err(Error::BadArg);
        }
        self.low_threshold = t;
        Ok(())
    }

    /// Saturating.
    pub fn consume(&mut self, steps: Pulses) {
        self.consumed = Pulses(self.consumed.0.saturating_add(steps.0));
    }

    /// Conservative (floor).
    pub fn remaining(&self) -> MilliUnits {
        if !self.filled || self.cal.is_none() {
            return MilliUnits(0);
        }
        let fill_uu = self.fill.to_micro().0;
        let used_uu = self.cal.pulses_to_micro(self.consumed).0;
        if used_uu >= fill_uu {
            MilliUnits(0)
        } else {
            MilliUnits(((fill_uu - used_uu) / 1000) as u32)
        }
    }

    pub fn is_filled(&self) -> bool {
        self.filled
    }
    pub fn fill_level(&self) -> MilliUnits {
        self.fill
    }
    pub fn consumed(&self) -> Pulses {
        self.consumed
    }
    pub fn capacity(&self) -> MilliUnits {
        self.capacity
    }
    /// Filled and nothing left.
    pub fn is_empty(&self) -> bool {
        self.filled && self.remaining().0 == 0
    }
    /// Filled and at or below the threshold.
    pub fn is_low(&self) -> bool {
        self.filled && self.remaining() <= self.low_threshold
    }
}

impl Reservoir {
    /// Configured low-reservoir threshold (test/diagnostic accessor).
    pub fn low_threshold(&self) -> MilliUnits {
        self.low_threshold
    }
}
