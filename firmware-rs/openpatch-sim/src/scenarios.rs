//! The built-in scenario library (`scenarios/*.toml`, embedded at build time).

use crate::scenario::Scenario;

macro_rules! lib {
    ($($name:literal),* $(,)?) => {
        pub const BUILTIN: &[(&str, &str)] = &[
            $(($name, include_str!(concat!("../scenarios/", $name, ".toml")))),*
        ];
    };
}

lib!(
    "wear_48h",
    "refill_draw",
    "draw_endstop",
    "prime",
    "occlusion_basal",
    "occlusion_basal_high",
    "occlusion_bolus",
    "occlusion_bubble",
    "dock_loss_mid_bolus",
    "undocked_firmware_bug",
    "hall_stuck_docked",
    "magnet_falls_off",
    "magnet_falls_off_basal",
    "angle_sensor_nack",
    "motor_phase_open",
    "hang_runaway",
    "hang_soft",
    "watchdog_kick_stuck",
    "brownout_bolus",
    "battery_depletion",
    "flash_power_loss",
    "flash_power_loss_worst",
    "comms_loss_temp",
    "gear_preset_mismatch",
    "limits_stress",
    "assisted_fill_user_pushes",
    "assisted_fill_user_does_not_push",
    "assisted_fill_user_pushes_hard",
    "post_clean",
    "post_stuck_latch",
    "post_stuck_q4",
    "post_dock_gate_stuck",
    "post_ffc_unplugged",
    "post_oc_leg_stuck",
    "post_dir_polarity",
    "post_xor_lost",
);

pub fn names() -> Vec<&'static str> {
    BUILTIN.iter().map(|(n, _)| *n).collect()
}

/// Load a built-in scenario by name.
pub fn get(name: &str) -> Result<Scenario, String> {
    let (_, text) = BUILTIN.iter().find(|(n, _)| *n == name).ok_or_else(|| format!("no built-in scenario {name:?}"))?;
    Scenario::from_toml(text).map_err(|e| format!("{name}: {e}"))
}

/// A built-in name or a path to a `.toml` / `.json` file.
pub fn load(name_or_path: &str) -> Result<Scenario, String> {
    if let Ok(s) = get(name_or_path) {
        return Ok(s);
    }
    let text = std::fs::read_to_string(name_or_path).map_err(|e| format!("{name_or_path}: {e}"))?;
    Scenario::from_str_auto(&text)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_builtin_parses_and_has_its_own_name() {
        for (n, t) in BUILTIN {
            let s = Scenario::from_toml(t).unwrap_or_else(|e| panic!("{n}: {e}"));
            assert_eq!(&s.name, n);
            assert!(s.device.drive_id().is_ok());
            assert!(!s.description.is_empty());
        }
    }
}
