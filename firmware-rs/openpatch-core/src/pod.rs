//! Two-pod state (spec section 1b). The platform persists pair id / role / active / activation id
//! / wear and restores them with [`crate::Pump::restore_pod`].

use crate::delivery::BasalSchedule;
use crate::units::{MilliUnits, MilliUnitsPerHour, Millis, Minutes, Pulses};
use openpatch_proto::Error;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
#[repr(u8)]
pub enum Role {
    A = 1,
    B = 2,
}

impl Role {
    pub fn from_u8(v: u8) -> Result<Role, Error> {
        match v {
            1 => Ok(Role::A),
            2 => Ok(Role::B),
            _ => Err(Error::BadArg),
        }
    }
}

/// What the pod is doing, reported in `POD_INFO.delivery_state`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
#[repr(u8)]
pub enum DeliveryState {
    /// Not the active pod of its pair: never delivers.
    Released = 0,
    Active = 1,
    /// Active but off the cannula adapter: no steps.
    PausedUndocked = 2,
    /// Wear limit reached: delivery stopped, alarm.
    StoppedWear = 3,
}

#[derive(Clone, Copy, Debug, Default)]
pub struct PodState {
    /// 0 = not paired.
    pub pair_id: u32,
    /// 0 none, 1 A, 2 B.
    pub role: u8,
    pub active: bool,
    pub activation_id: u32,
    /// Since activation, frozen while released.
    pub wear: Millis,
    pub wear_warned: bool,
    /// Last sampled DOCKED input.
    pub docked: bool,
    /// Temp basal from Activate, started by the first Resume.
    pub pending_temp: Option<(MilliUnitsPerHour, Minutes)>,
    /// Engine delivered steps at activation.
    pub act_base_steps: Pulses,
    /// Delivered since activation, as of the last release.
    pub last_release: MilliUnits,
}

#[derive(Clone, Debug)]
pub struct ActivateArgs {
    pub pair_id: u32,
    pub activation_id: u32,
    pub schedule: BasalSchedule,
    /// Remaining temp basal handed over from the previous pod.
    pub temp: Option<(MilliUnitsPerHour, Minutes)>,
}
