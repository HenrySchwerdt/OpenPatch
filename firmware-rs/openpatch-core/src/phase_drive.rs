//! Full-step drive of a dual H-bridge in PHASE/ENABLE mode (2 x DRV8838: U7A coil A, U7B coil B; same truth table as the former DRV8835 with MODE = VCC) for the 45-part cup board
//! (`electronics/v010/INTERLOCK.md` I.6, `FIRMWARE-PINMAP.md` "v4 motor driver pins").
//!
//! The board has no STEP/DIR/STBY pins and no hardware step clock: the firmware itself walks the four lines
//! `APHASE`, `AENBL`, `BPHASE`, `BENBL`. This module is the hardware independent half (host tested):
//!
//! * the **full-step table**: `(A, B)` = `(0,0) -> (1,0) -> (1,1) -> (0,1) -> (0,0)` forward, the reverse order for
//!   reverse. Exactly ONE phase line toggles per step (the supervisor counts steps from these edges, so this is a
//!   contract, not an implementation detail: `openpatch-supervisor` decodes the same sequence);
//! * [`PhaseStepper`]: the position in the table, direction, energise / de-energise;
//! * [`drive_burst`]: a whole burst through the [`PhasePins`] trait with a [`StepTimer`] for the delays.
//!
//! The board HAL (`openpatch-bench/src/hal/phase.rs`) implements [`PhasePins`] by writing the four GPIOs.
//!
//! De-energise at idle: `AENBL = BENBL = 0` brakes (both outputs of the bridge low: the winding is shorted, no supply
//! current, no torque change worth mentioning on a self-locking leadscrew). The PHASE lines are NOT touched when
//! de-energising, so the position in the table survives an idle period: the next burst continues from it and the
//! supervisor sees no spurious edge. The enable lines are always raised AFTER the phase lines were set, and lowered
//! BEFORE anything else changes, so a bridge is never energised in a state the table did not ask for.

use crate::hal::MotorDir;

/// The four driver inputs. `true` = pin high. `aenbl` / `benbl` are the nRF side of the enables (`AENBL_MCU`, `BENBL_MCU`);
/// 1 = bridge driven, 0 = brake.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct PhaseLevels {
    pub aphase: bool,
    pub bphase: bool,
    pub aenbl: bool,
    pub benbl: bool,
}

impl PhaseLevels {
    /// Reset state of the board: PHASE low, both bridges braked (the enables have 100 k pull-downs).
    pub const RESET: PhaseLevels = PhaseLevels { aphase: false, bphase: false, aenbl: false, benbl: false };
}

/// Number of positions of the full-step table.
pub const FULL_STEP_POSITIONS: u8 = 4;

/// `(APHASE, BPHASE)` of position `i` (0..=3), forward order. Position 0 is the power-up position.
pub const FULL_STEP_TABLE: [(bool, bool); 4] = [(false, false), (true, false), (true, true), (false, true)];

/// Which line toggles when going from position `i` to `i + 1` (forward): A, B, A, B.
pub const fn toggling_line_forward(i: u8) -> Line {
    if i % 2 == 0 {
        Line::A
    } else {
        Line::B
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum Line {
    A,
    B,
}

/// Position and direction in the full-step table plus the energised flag.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub struct PhaseStepper {
    pos: u8,
    energised: bool,
    /// Net forward steps since power-up (reverse subtracts); diagnostics only, wraps.
    net: i32,
}

impl Default for PhaseStepper {
    fn default() -> Self {
        Self::new()
    }
}

impl PhaseStepper {
    /// Power-up: position 0, de-energised.
    pub const fn new() -> Self {
        Self { pos: 0, energised: false, net: 0 }
    }

    /// Current table position (0..=3).
    pub const fn position(&self) -> u8 {
        self.pos
    }

    pub const fn is_energised(&self) -> bool {
        self.energised
    }

    /// Net steps (forward positive) since power-up.
    pub const fn net_steps(&self) -> i32 {
        self.net
    }

    /// The pin levels for the current position and energise state.
    pub const fn levels(&self) -> PhaseLevels {
        let (a, b) = FULL_STEP_TABLE[self.pos as usize];
        PhaseLevels { aphase: a, bphase: b, aenbl: self.energised, benbl: self.energised }
    }

    /// Energise at the CURRENT position (no phase change: the rotor is aligned to this position already, nothing moves).
    /// Returns the levels to apply; the caller writes the phase lines first and the enables second (see [`drive_burst`]).
    pub fn energise(&mut self) -> PhaseLevels {
        self.energised = true;
        self.levels()
    }

    /// De-energise (brake). The phase lines keep their levels.
    pub fn de_energise(&mut self) -> PhaseLevels {
        self.energised = false;
        self.levels()
    }

    /// One full step in `dir`. Exactly one PHASE line changes; the enable state is unchanged. A step while de-energised
    /// is allowed here (the position still advances: used by tests and by the supervisor model) but the HAL never does it.
    pub fn step(&mut self, dir: MotorDir) -> PhaseLevels {
        match dir {
            MotorDir::Forward => {
                self.pos = (self.pos + 1) % FULL_STEP_POSITIONS;
                self.net = self.net.wrapping_add(1);
            }
            MotorDir::Reverse => {
                self.pos = (self.pos + FULL_STEP_POSITIONS - 1) % FULL_STEP_POSITIONS;
                self.net = self.net.wrapping_sub(1);
            }
        }
        self.levels()
    }
}

/// The pins side of the driver (implemented by the board HAL).
pub trait PhasePins {
    /// Apply new levels. The implementation writes the PHASE lines first and raises the enables last, and lowers the
    /// enables first: [`apply_in_safe_order`] does exactly that on top of two raw writers.
    fn apply(&mut self, levels: PhaseLevels);
}

/// Delays of a burst (implemented by the HAL with a hardware timer, by tests with a counter).
pub trait StepTimer {
    /// Wait `us` microseconds (a step period is 5 ms at 200 pps).
    fn delay_us(&mut self, us: u32);
}

/// Safe write order: when `to` de-energises or keeps the enables, the enables are written FIRST (a bridge that is to be
/// off goes off before anything else changes); when `to` energises, the PHASE lines are written first.
/// `set_phase(a, b)` and `set_enable(a, b)` are the raw pin writers.
pub fn apply_in_safe_order(
    from: PhaseLevels,
    to: PhaseLevels,
    mut set_phase: impl FnMut(bool, bool),
    mut set_enable: impl FnMut(bool, bool),
) {
    let energising = (to.aenbl && !from.aenbl) || (to.benbl && !from.benbl);
    if energising {
        set_phase(to.aphase, to.bphase);
        set_enable(to.aenbl, to.benbl);
    } else {
        set_enable(to.aenbl, to.benbl);
        set_phase(to.aphase, to.bphase);
    }
}

/// Why a burst stopped early.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum BurstStop {
    /// All requested steps were made.
    Done,
    /// The `keep_going` callback returned false (supply lost, permission withdrawn, ...): de-energised at once.
    Aborted,
}

/// Run `steps` full steps of period `period_us` in `dir`.
///
/// Sequence: phase levels of the current position are already on the pins (the stepper keeps them), enables up, then for each
/// step: toggle one phase line, wait one period. `keep_going` is asked before EVERY step (the HAL reads the supply / stop
/// flag there); on false the bridge is braked and the burst ends. The bridge is ALWAYS braked at the end, also when
/// `steps == 0` (nothing is energised for an empty burst). Returns the steps made and why it stopped.
///
/// The first step happens one period after the enables went up, so the rotor has time to align to the starting position and the
/// first step is a full step like all others (the step timing the supervisor budget assumes).
pub fn drive_burst<P: PhasePins, T: StepTimer>(
    st: &mut PhaseStepper,
    pins: &mut P,
    timer: &mut T,
    dir: MotorDir,
    steps: u32,
    period_us: u32,
    mut keep_going: impl FnMut(u32) -> bool,
) -> (u32, BurstStop) {
    if steps == 0 {
        pins.apply(st.de_energise());
        return (0, BurstStop::Done);
    }
    pins.apply(st.energise());
    timer.delay_us(period_us);
    let mut made = 0u32;
    let mut stop = BurstStop::Done;
    while made < steps {
        if !keep_going(made) {
            stop = BurstStop::Aborted;
            break;
        }
        pins.apply(st.step(dir));
        made += 1;
        timer.delay_us(period_us);
    }
    pins.apply(st.de_energise());
    (made, stop)
}
