//! Scenario description (TOML or JSON). Times are seconds since the end of the setup procedure
//! (`t = 0` = the pod is filled, primed and delivering the basal profile).

use crate::params::Params;
use openpatch_core::drive_cal::DriveId;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "action", rename_all = "snake_case")]
pub enum Action {
    // ---- phone -> pod commands (through the protocol path) ----
    Bolus { units: f64 },
    TempBasal { u_per_h: f64, minutes: u32 },
    CancelTemp,
    CancelBolus,
    Suspend,
    Resume,
    /// (hour of day, U/h) segments.
    SetBasal { profile: Vec<(f64, f64)> },
    Prime { units: f64 },
    /// Automatic refill: the fill needle is put into the septum and the motor reverses.
    Draw { units: f64 },
    Activate,
    Release,
    Acknowledge { mask: Option<u16> },
    /// Phone in / out of range: no heartbeat while away (comm-loss fallback of a temp basal).
    PhoneConnected { on: bool },
    // ---- physical world ----
    Dock { on: bool },
    Charger { on: bool },
    /// Downstream resistance multiplier (default: fully blocked).
    Occlude { factor: Option<f64> },
    ClearOcclusion,
    /// Air bubble in the reservoir, ul at ambient pressure.
    Bubble { ul: f64 },
    /// Relative magnet field at the sensor (1 = nominal, 0 = magnet fell off).
    Magnet { strength: f64 },
    AngleNack { on: bool },
    PhaseOpen { on: bool },
    HallStuckDocked { on: bool },
    // ---- electronics / firmware faults ----
    /// Firmware hangs: no tick, no DONE. With `runaway_hz` the step generator keeps running
    /// while the driver stays armed (worst case).
    Hang { runaway_hz: Option<f64> },
    /// The DONE line of the safety path is dead (hardware defect): the TPL5010 resets every period.
    KickStuck { on: bool },
    /// Extra voltage drop on the supply for a while (mV, ms).
    Brownout { dip_mv: f64, duration_ms: f64 },
    /// Override the open-circuit battery voltage (mV); none = back to the discharge curve.
    BatteryOcv { mv: Option<f64> },
    /// Total power loss now, back after `duration_ms`.
    PowerLoss { duration_ms: f64 },
    /// Cut the power `frac` of the way through the NEXT flash write, back after `off_ms`.
    FlashPowerLoss { frac: f64, off_ms: f64 },
    /// Firmware-bug injection: issue forward pulses straight on the HAL, bypassing the supervisor.
    ForceSteps { n: u32 },
    /// Inject (or remove) a hardware fault of the bench controller's interlock board (`board::BoardFaults` field names),
    /// or fit the R97 DIR option (`"r97_fitted"`, the firmware assumes R96).
    BoardFault { fault: String, on: bool },
    /// `RunSelfTest` through the protocol path: 1 = POST-S, 2 = POST-A, 3 = watchdog. The pod must be suspended. The
    /// verdict records the result and the diagnostic codes that are active afterwards.
    SelfTest { sub_op: u8 },
    /// Name a physical instant (shows up in the verdict).
    Mark { name: String },
}

/// How the core is expected to notice an injected fault.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Detector {
    /// A latched fault out of this mask.
    Fault(u16),
    /// A reset of the pod (watchdog / power loss).
    Reset,
    /// Nothing is expected to alarm (dock loss, comm loss, bug injection): only effects are measured.
    Neither,
}

impl Action {
    /// `Some` for actions that inject a fault; the latency to the matching detector is measured.
    pub fn detector(&self) -> Option<Detector> {
        use openpatch_core::faults::Faults as F;
        let occ = F::OCCLUSION.bits() | F::ENCODER_DEVIATION.bits();
        match self {
            Action::Occlude { .. } => Some(Detector::Fault(occ)),
            Action::Magnet { strength } if *strength < 0.3 => Some(Detector::Fault(occ | F::INTERNAL.bits())),
            Action::AngleNack { on: true } => Some(Detector::Fault(F::INTERNAL.bits())),
            Action::PhaseOpen { on: true } => Some(Detector::Fault(occ)),
            Action::BatteryOcv { mv: Some(mv) } if *mv < 3300.0 => Some(Detector::Fault(F::BATTERY_CRITICAL.bits())),
            Action::Hang { .. } | Action::KickStuck { on: true } | Action::Brownout { .. } | Action::PowerLoss { .. } | Action::FlashPowerLoss { .. } => {
                Some(Detector::Reset)
            }
            Action::Dock { on: false } | Action::PhoneConnected { on: false } | Action::ForceSteps { .. } | Action::HallStuckDocked { on: true } => {
                Some(Detector::Neither)
            }
            _ => None,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Event {
    pub at_s: f64,
    #[serde(flatten)]
    pub action: Action,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct DeviceSpec {
    /// `DriveId` variant name, e.g. "Nfp608_26_45G16_20" (the pair of the current CAD).
    pub preset: String,
    pub capacity_u: f64,
    pub strict_prime: bool,
    pub start_hour: f64,
    pub heartbeat_s: u32,
}

impl Default for DeviceSpec {
    fn default() -> Self {
        DeviceSpec { preset: "Nfp608_26_45G16_20".into(), capacity_u: 100.0, strict_prime: true, start_hour: 8.0, heartbeat_s: 60 }
    }
}

impl DeviceSpec {
    pub fn drive_id(&self) -> Result<DriveId, String> {
        openpatch_core::drive_cal::PRESETS
            .iter()
            .find(|p| format!("{:?}", p.id) == self.preset)
            .map(|p| p.id)
            .ok_or_else(|| format!("unknown drive preset {:?}", self.preset))
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct Setup {
    /// Run the standard bring-up: draw, dock, pair, activate, prime, resume.
    pub standard: bool,
    /// Water drawn into the reservoir (U).
    pub fill_u: f64,
    /// Basal profile (hour of day, U/h).
    pub basal: Vec<(f64, f64)>,
    pub prime_u: f64,
    /// Resume delivery at the end of setup.
    pub resume: bool,
}

impl Default for Setup {
    fn default() -> Self {
        Setup { standard: true, fill_u: 80.0, basal: vec![(0.0, 1.0)], prime_u: 0.3, resume: true }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct Scenario {
    pub name: String,
    pub description: String,
    pub seed: u64,
    pub duration_s: f64,
    /// Time series sampling period (s). Divide 3600 for the hourly table.
    pub log_interval_s: f64,
    /// Settling time after a bolus before its fluid is counted (s).
    pub settle_s: f64,
    pub params: Params,
    pub device: DeviceSpec,
    pub setup: Setup,
    pub events: Vec<Event>,
}

impl Default for Scenario {
    fn default() -> Self {
        Scenario {
            name: "unnamed".into(),
            description: String::new(),
            seed: 1,
            duration_s: 3600.0,
            log_interval_s: 60.0,
            settle_s: 60.0,
            params: Params::default(),
            device: DeviceSpec::default(),
            setup: Setup::default(),
            events: Vec::new(),
        }
    }
}

impl Scenario {
    pub fn from_toml(s: &str) -> Result<Scenario, String> {
        toml::from_str(s).map_err(|e| e.to_string())
    }
    pub fn from_json(s: &str) -> Result<Scenario, String> {
        serde_json::from_str(s).map_err(|e| e.to_string())
    }
    pub fn from_str_auto(s: &str) -> Result<Scenario, String> {
        if s.trim_start().starts_with('{') {
            Scenario::from_json(s)
        } else {
            Scenario::from_toml(s)
        }
    }
    pub fn at(mut self, at_s: f64, a: Action) -> Self {
        self.events.push(Event { at_s, action: a });
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn toml_roundtrip_with_events() {
        let t = r#"
name = "x"
duration_s = 100.0
[setup]
fill_u = 50.0
[[events]]
at_s = 10.0
action = "bolus"
units = 2.0
[[events]]
at_s = 20
action = "occlude"
[[events]]
at_s = 30.0
action = "temp_basal"
u_per_h = 1.5
minutes = 60
[params.fluid]
bubble_ul = 5.0
"#;
        let s = Scenario::from_toml(t).unwrap();
        assert_eq!(s.events.len(), 3);
        assert!(matches!(s.events[0].action, Action::Bolus { units } if units == 2.0));
        assert!(matches!(s.events[1].action, Action::Occlude { factor: None }));
        assert_eq!(s.params.fluid.bubble_ul, 5.0);
        assert_eq!(s.params.motor.steps_per_rev, 20.0);
        let j = serde_json::to_string(&s).unwrap();
        let s2 = Scenario::from_json(&j).unwrap();
        assert_eq!(s2.events.len(), 3);
    }

    #[test]
    fn unknown_preset_is_an_error() {
        let d = DeviceSpec { preset: "Nope".into(), ..Default::default() };
        assert!(d.drive_id().is_err());
    }
}
