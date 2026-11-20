//! Step counting from the PHASE lines.
//!
//! The nRF drives the DRV8835 in PHASE/ENABLE mode and walks the full-step table `(APHASE, BPHASE)`:
//! `00 -> 10 -> 11 -> 01 -> 00` forward, the reverse order for reverse (`openpatch_core::phase_drive`). Exactly one line toggles per
//! step, so a step is one edge of A or of B. The supervisor sees the same two lines on `PA` pins (EXTI on both edges): on every edge
//! it samples both levels and calls [`PhaseDecoder::sample`].
//!
//! The decoder has no notion of time, budget or permission: it only answers "what happened between the previous sample and this one".

/// Direction of a decoded step.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum Dir {
    Forward,
    Reverse,
}

/// Result of one sample.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum Decoded {
    /// Same levels as before (a duplicate EXTI, or both edges of a glitch already gone).
    NoChange,
    /// One full step.
    Step(Dir),
    /// Both lines changed at once (a lost edge or a glitch): not a legal step, nothing is counted, the decoder resyncs to the new
    /// levels and the caller treats it as a sequence error.
    Invalid,
}

/// Position in the table of a pair of levels.
const fn position(a: bool, b: bool) -> u8 {
    match (a, b) {
        (false, false) => 0,
        (true, false) => 1,
        (true, true) => 2,
        (false, true) => 3,
    }
}

/// The decoder: remembers the last sampled levels.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct PhaseDecoder {
    pos: u8,
}

impl PhaseDecoder {
    /// Start from the levels read at boot (or after a main MCU reset): nothing is counted for them.
    pub const fn new(a: bool, b: bool) -> Self {
        Self { pos: position(a, b) }
    }

    /// Resynchronise to the given levels without counting (after a main MCU reset).
    pub fn resync(&mut self, a: bool, b: bool) {
        self.pos = position(a, b);
    }

    /// Current table position (0..=3).
    pub const fn position(&self) -> u8 {
        self.pos
    }

    /// Decode a new sample.
    pub fn sample(&mut self, a: bool, b: bool) -> Decoded {
        let new = position(a, b);
        let d = (new + 4 - self.pos) % 4;
        self.pos = new;
        match d {
            0 => Decoded::NoChange,
            1 => Decoded::Step(Dir::Forward),
            3 => Decoded::Step(Dir::Reverse),
            _ => Decoded::Invalid,
        }
    }
}
