//! Plant parameters. Every field has a default taken from `spec/design-parameters.md` (sections 3,
//! 4, 5, 7) or, where the spec is silent, a clearly marked ASSUMPTION (see REPORT.md, assumptions
//! table). A scenario file (TOML/JSON) overrides any subset; unknown fields are rejected so a
//! typo in a scenario can never silently fall back to a default.

use serde::{Deserialize, Serialize};

/// Stepper motor + gearhead (NFP-608-26.45-SGM) and its driver (STSPIN220 + current sense).
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct MotorParams {
    /// Full steps per rotor revolution (spec 4: 20).
    pub steps_per_rev: f64,
    /// Gearhead ratio (spec 4: 26.45). The ACTUAL ratio of this unit (tolerance goes here).
    pub gearhead_ratio: f64,
    /// Gearhead efficiency (spec 4: ~0.64).
    pub gearhead_eff: f64,
    /// Pull-out torque at the rotor shaft in gf*cm (spec 4: 1.6).
    pub pullout_gf_cm: f64,
    /// Step rate at which the pull-out figure is valid (ASSUMPTION: the bench forward rate).
    pub rolloff_ref_hz: f64,
    /// Corner frequency of the speed derating (ASSUMPTION, back-EMF; docs/architecture.md).
    pub rolloff_corner_hz: f64,
    /// Per-step 1-sigma ripple of the available torque in percent (cogging, friction, supply ripple).
    pub torque_ripple_pct: f64,
    /// Forward step rate of the bench firmware (config::STEP_RATE_HZ).
    pub step_rate_hz: f64,
    /// Reverse (draw) step rate (config::REVERSE_RATE_HZ).
    pub reverse_rate_hz: f64,
    /// Supply voltage at which the chopper reaches its current limit (full torque above).
    pub vmot_full_v: f64,
    /// Below this supply the driver does nothing (STSPIN220 VS min 1.8 V).
    pub vmot_min_v: f64,
    /// Supply current of the free-running stage (mA, I_SENSE at the shunt).
    pub i_free_ma: f64,
    /// Supply current with a stalled / fully loaded rotor (mA). The core threshold is 140 mA.
    pub i_stall_ma: f64,
    /// 1-sigma noise of the current sense (mA).
    pub i_noise_ma: f64,
    /// The board has a motor current sense (bench board: yes). false = encoder-only occlusion detection,
    /// like the C reference.
    pub current_sense: bool,
}

impl Default for MotorParams {
    fn default() -> Self {
        MotorParams {
            steps_per_rev: 20.0,
            gearhead_ratio: 26.45,
            gearhead_eff: 0.64,
            pullout_gf_cm: 1.6,
            rolloff_ref_hz: 200.0,
            rolloff_corner_hz: 500.0,
            torque_ripple_pct: 4.0,
            step_rate_hz: 200.0,
            reverse_rate_hz: 600.0,
            vmot_full_v: 3.3,
            vmot_min_v: 1.8,
            i_free_ma: 70.0,
            i_stall_ma: 175.0,
            i_noise_ma: 3.0,
            current_sense: true,
        }
    }
}

/// Gear pair, leadscrew, carriage, plunger seal, reservoir geometry.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct DriveParams {
    /// Teeth of the gear on the gearhead output (spec 4: 15).
    pub z_motor: f64,
    /// Teeth of the gear on the leadscrew (spec 4: 12). 15:12 -> 0.00617 U/step; 18:18 -> 0.00494.
    pub z_screw: f64,
    /// Gear pair efficiency (ASSUMPTION: module 0.3 purchased pair).
    pub pair_eff: f64,
    /// Gear pair backlash, referred to the screw (deg) (ASSUMPTION).
    pub pair_backlash_deg: f64,
    /// Gearhead output backlash (deg at the gearhead output) (ASSUMPTION, typical 1-3 deg).
    pub gearhead_backlash_deg: f64,
    /// Leadscrew lead = pitch of a single-start M1.6 x 0.35 (mm).
    pub lead_mm: f64,
    /// Systematic lead error in percent (rolled/cut thread tolerance, ASSUMPTION +-1.5 %).
    pub pitch_error_pct: f64,
    /// Periodic lead error: once-per-turn sinusoid of this amplitude (um) (ASSUMPTION).
    pub pitch_periodic_um: f64,
    /// Screw efficiency (spec 4: 0.20, self-locking).
    pub screw_eff: f64,
    /// Carriage / nut friction in its lane (N) (ASSUMPTION).
    pub carriage_friction_n: f64,
    /// Axial stiffness carriage -> plunger incl. seal shear (N/mm) (ASSUMPTION).
    pub axial_stiffness_n_mm: f64,
    /// Static (break-away) friction of the plunger seal (N) (spec 3: biggest development risk).
    pub seal_static_n: f64,
    /// Dynamic friction of the plunger seal (N).
    pub seal_dynamic_n: f64,
    /// ACTUAL stadium area (mm^2). Spec 3: 74.6 nominal (tolerance goes here).
    pub area_mm2: f64,
    /// Travel above the capacity stroke (spec 3: +1.0 mm dead volume reserve).
    pub reserve_mm: f64,
    /// Capacity the housing is built for (U). Sets the rear end-stop.
    pub capacity_u: f64,
}

impl Default for DriveParams {
    fn default() -> Self {
        DriveParams {
            z_motor: 15.0,
            z_screw: 12.0,
            pair_eff: 0.95,
            pair_backlash_deg: 2.0,
            gearhead_backlash_deg: 1.5,
            lead_mm: 0.35,
            pitch_error_pct: 0.0,
            pitch_periodic_um: 0.2,
            screw_eff: 0.20,
            carriage_friction_n: 0.3,
            axial_stiffness_n_mm: 40.0,
            seal_static_n: 1.5,
            seal_dynamic_n: 0.8,
            area_mm2: 74.6,
            reserve_mm: 1.0,
            capacity_u: 100.0,
        }
    }
}

/// Fluid path: compliance, bubbles, duckbill check valve, cannula, fill needle.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct FluidParams {
    /// Lumped compliance of seal, housing, port, dead volume (mm^3 per kPa = ul/kPa) (ASSUMPTION).
    pub compliance_ul_per_kpa: f64,
    /// Air bubble in the reservoir at atmospheric pressure (ul). Isothermal: C = V * Patm / (Patm+P)^2.
    pub bubble_ul: f64,
    /// Air in the connector / needle / cannula path that must be primed out (ul). Spec 3: 30G needle
    /// plus cannula head: ASSUMPTION 1.5 ul (0.15 U).
    pub line_air_ul: f64,
    /// Duckbill cracking pressure (kPa), spec 4: 1..5.
    pub crack_kpa: f64,
    /// Duckbill closing pressure as a fraction of the cracking pressure (hysteresis, ASSUMPTION).
    pub close_ratio: f64,
    /// Subcutaneous back pressure at the cannula tip (kPa) (ASSUMPTION).
    pub tissue_kpa: f64,
    /// Hydraulic resistance of needle + cannula (kPa per mm^3/s). 30G x 10 mm, water-like: ~0.6.
    pub outlet_r: f64,
    /// Resistance factor applied to the outlet (1.0 = healthy; large = occluded). Scenario-driven.
    pub occlusion_factor: f64,
    /// Resistance of the fill needle (kPa per mm^3/s) while drawing (27G x 15 mm: ~0.4).
    pub fill_needle_r: f64,
    /// Air released into the reservoir per ml drawn (dissolved gas under vacuum), ul/ml.
    pub draw_air_ul_per_ml: f64,
    /// A vacuum left in the closed reservoir decays by air creeping in through the outlet (s)
    /// (ASSUMPTION): this is why the core demands a prime after every draw.
    pub vacuum_leak_tau_s: f64,
    /// Ambient pressure (kPa).
    pub atm_kpa: f64,
}

impl Default for FluidParams {
    fn default() -> Self {
        FluidParams {
            compliance_ul_per_kpa: 0.05,
            bubble_ul: 0.0,
            line_air_ul: 1.5,
            crack_kpa: 3.0,
            close_ratio: 0.5,
            tissue_kpa: 1.0,
            outlet_r: 0.6,
            occlusion_factor: 1.0,
            fill_needle_r: 0.4,
            draw_air_ul_per_ml: 2.0,
            vacuum_leak_tau_s: 30.0,
            atm_kpa: 101.3,
        }
    }
}

/// TMAG5273 angle sensor on the screw magnet, dock hall switch.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct SensorParams {
    /// Raw resolution of the sensor (TMAG5273: 13 bit). The HAL keeps the top 12 bits (4096/turn).
    pub angle_bits: u32,
    /// 1-sigma angle noise in degrees (ASSUMPTION: 0.1 deg).
    pub angle_noise_deg: f64,
    /// Constant mounting offset (deg); cancels in the unwrapped angle.
    pub angle_offset_deg: f64,
    /// Once-per-turn nonlinearity from magnet eccentricity (deg, amplitude) (ASSUMPTION).
    pub angle_inl_deg: f64,
    /// Field strength relative to nominal below which noise grows as 1/strength.
    pub weak_threshold: f64,
    /// Field strength relative to nominal below which the sensor output is garbage.
    pub lost_threshold: f64,
    /// Noise of a garbage reading (deg, 1 sigma, around the stray-field direction).
    pub garbage_noise_deg: f64,
    /// Samples of the angle during a burst (config::ANGLE_POLL_MS).
    pub poll_ms: f64,
}

impl Default for SensorParams {
    fn default() -> Self {
        SensorParams {
            angle_bits: 13,
            angle_noise_deg: 0.1,
            angle_offset_deg: 17.0,
            angle_inl_deg: 0.5,
            weak_threshold: 0.25,
            lost_threshold: 0.05,
            garbage_noise_deg: 40.0,
            poll_ms: 20.0,
        }
    }
}

/// Battery, supply, watchdog timer, interlock.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct ElectricalParams {
    pub battery_capacity_mah: f64,
    /// State of charge at t = 0 (0..1).
    pub soc_start: f64,
    /// Internal resistance of a 17-26 mAh pouch cell + PCM (ohm) (ASSUMPTION).
    pub r_int_ohm: f64,
    /// Average quiescent + BLE current (uA) (spec 1b: ~100 uA).
    pub i_idle_ua: f64,
    /// PCM undervoltage cut-off: below this the pod is dead (mV).
    pub power_off_mv: f64,
    /// Voltage at which the pod boots again after a power cut (mV).
    pub power_on_mv: f64,
    /// TPL5010 period before it resets the MCU if no DONE arrived (ms). architecture.md: ~2 s.
    pub wdt_period_ms: f64,
    /// Time from reset release to the first tick of the firmware (ms).
    pub boot_ms: f64,
    /// Bench supply: battery_mv is fixed (USB 5 V LDO, config::BATTERY_MV_FIXED).
    pub bench_supply: bool,
}

impl Default for ElectricalParams {
    fn default() -> Self {
        ElectricalParams {
            battery_capacity_mah: 25.0,
            soc_start: 1.0,
            r_int_ohm: 1.5,
            i_idle_ua: 100.0,
            power_off_mv: 2500.0,
            power_on_mv: 2900.0,
            wdt_period_ms: 2000.0,
            boot_ms: 300.0,
            bench_supply: false,
        }
    }
}

/// Flash (settings map) behaviour.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct FlashParams {
    /// Time one record write occupies the flash (erase ~85 ms + program) (architecture.md).
    pub write_ms: f64,
    /// Probability that a power cut during a write also destroys the previous copy of that record
    /// (worst case: page erase interrupted). 0 = A/B atomic (sequential-storage map assumption).
    pub tear_destroys_previous_prob: f64,
}

impl Default for FlashParams {
    fn default() -> Self {
        FlashParams { write_ms: 90.0, tear_destroys_previous_prob: 0.0 }
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Params {
    pub motor: MotorParams,
    pub drive: DriveParams,
    pub fluid: FluidParams,
    pub sensor: SensorParams,
    pub electrical: ElectricalParams,
    pub flash: FlashParams,
}

impl Params {
    /// Rotor steps per screw turn implied by the MECHANICS (not by the firmware preset).
    pub fn steps_per_screw_turn(&self) -> f64 {
        self.motor.steps_per_rev * self.motor.gearhead_ratio * self.drive.z_screw / self.drive.z_motor
    }

    /// Water volume per step the mechanics really deliver (U, 1 U = 10 mm^3), ideal fluid.
    pub fn true_u_per_step(&self) -> f64 {
        self.drive.lead_mm * (1.0 + self.drive.pitch_error_pct / 100.0) / self.steps_per_screw_turn() * self.drive.area_mm2 / 10.0
    }

    /// Total plunger travel between the front stop and the rear stop (mm).
    pub fn stroke_mm(&self) -> f64 {
        // spec 3: capacity stroke at the NOMINAL area, plus the reserve
        self.drive.capacity_u * 10.0 / 74.6 + self.drive.reserve_mm
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_match_spec() {
        let p = Params::default();
        // spec 4: 15:12 -> 0.00617 U/step
        assert!((p.true_u_per_step() - 0.006170).abs() < 2e-5, "{}", p.true_u_per_step());
        assert!((p.steps_per_screw_turn() - 423.2).abs() < 1e-9);
        // spec 3: 100 U -> 13.4 mm (+1.0)
        assert!((p.stroke_mm() - 14.4).abs() < 0.01);
    }

    #[test]
    fn g1_1_matches_spec() {
        let mut p = Params::default();
        p.drive.z_motor = 18.0;
        p.drive.z_screw = 18.0;
        assert!((p.true_u_per_step() - 0.00494).abs() < 1e-5);
    }

    #[test]
    fn unknown_field_rejected() {
        let r: Result<Params, _> = toml::from_str("[motor]\nstep_per_rev = 20\n");
        assert!(r.is_err());
    }
}
