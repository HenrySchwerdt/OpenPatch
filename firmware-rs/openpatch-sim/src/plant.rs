//! Mechanical + hydraulic plant of the pod, advanced step by step (quasi-static: inertia is
//! neglected, a step at 200 Hz is 5 ms).
//!
//! ```text
//!  rotor --(20 steps/rev)--> gearhead 26.45 --backlash--> gear pair z_m:z_s --backlash--> leadscrew
//!  leadscrew --(M1.6 x 0.35, efficiency, pitch error)--> carriage/nut
//!  carriage --(axial spring k)--> plunger (static/dynamic seal friction: stick-slip) --> reservoir
//!  reservoir (stadium area A) --> compliance + bubble --> duckbill (crack/close) --> needle/cannula --> tissue
//! ```
//!
//! A step is LOST when the torque the load needs at the rotor exceeds the torque the motor can
//! deliver at that step rate and supply voltage (pull-out). Conventions: lengths mm, forces N,
//! torque N*mm, pressure kPa, volume ul (= mm^3), time s. Forward = delivery = positive.

use crate::params::Params;
use crate::rng::Rng;
use std::f64::consts::PI;

const GF_CM_TO_N_MM: f64 = 0.098_066_5;

/// What one commanded step did.
#[derive(Clone, Copy, Debug, Default)]
pub struct StepResult {
    /// The rotor followed the step.
    pub moved: bool,
    /// Supply current sampled for this step (mA).
    pub current_ma: f64,
    /// Load as a fraction of the torque the motor could deliver (diagnostics, may exceed 1).
    pub load_frac: f64,
}

#[derive(Clone, Debug)]
pub struct Plant {
    pub p: Params,
    // ---- faults injected by scenarios ----
    pub phase_open: bool,
    /// Draw: the fill needle is in the septum and the vial supplies fluid at ambient pressure.
    pub fill_needle: bool,
    /// Assisted fill: gauge pressure the user's syringe holds on the septum (kPa). 0 = suction from a vial at ambient pressure.
    pub fill_push_kpa: f64,
    /// Water that came in through the fill needle minus what left at the needle tip (ul): the net fill, including any
    /// water held compressed by the syringe pressure (`compressed_ul`).
    pub net_in_ul: f64,
    // ---- derived constants ----
    steps_per_turn: f64,
    backlash_rad: f64,
    torque_po: f64,
    lead_eff: f64,
    stroke: f64,
    // ---- mechanical state ----
    /// driver (rotor side, screw domain) minus screw angle, within +-backlash/2 (rad).
    gap: f64,
    /// cumulative screw angle (rad).
    pub theta_s: f64,
    /// spring deflection carriage -> plunger (mm, + = compressed forward).
    delta: f64,
    /// plunger distance from the front stop (mm). 0 = empty.
    pub plunger_x: f64,
    /// 0 stuck, +1 sliding forward, -1 sliding backward.
    sliding: i8,
    pub rotor_steps: i64,
    pub lost_steps: u64,
    pub forward_moved_steps: u64,
    parity: u64,
    // ---- fluid state ----
    pub pressure_kpa: f64,
    open: bool,
    /// water currently in the reservoir (ul).
    pub liquid_ul: f64,
    /// air bubble in the reservoir (ul at ambient pressure).
    pub bubble_ul: f64,
    /// air in the connector path (ul), flushed out first.
    pub line_air_ul: f64,
    /// water that left through the outlet (ul).
    pub out_ul: f64,
    pub out_air_ul: f64,
    /// water drawn in from the vial (ul).
    pub drawn_ul: f64,
    pub peak_pressure_kpa: f64,
}

impl Plant {
    pub fn new(p: Params) -> Self {
        let steps_per_turn = p.steps_per_screw_turn();
        // gearhead output backlash (deg) -> screw domain via the pair ratio
        let backlash_deg = p.drive.pair_backlash_deg + p.drive.gearhead_backlash_deg * p.drive.z_motor / p.drive.z_screw;
        let lead_eff = p.drive.lead_mm * (1.0 + p.drive.pitch_error_pct / 100.0);
        let stroke = p.stroke_mm();
        let bubble = p.fluid.bubble_ul;
        let line_air = p.fluid.line_air_ul;
        Plant {
            phase_open: false,
            fill_needle: false,
            fill_push_kpa: 0.0,
            net_in_ul: 0.0,
            steps_per_turn,
            backlash_rad: backlash_deg.to_radians(),
            // pull-out torque at the run current (torque ~ phase current; the datasheet figure is at the rated current)
            torque_po: p.motor.pullout_gf_cm * GF_CM_TO_N_MM * (p.motor.run_current_ma / p.motor.rated_current_ma).min(1.0),
            lead_eff,
            stroke,
            gap: backlash_deg.to_radians() / 2.0, // loaded forward at assembly
            theta_s: 0.0,
            delta: p.drive.socket_play_mm / 2.0, // loaded forward at assembly: the first reversal crosses the whole socket play
            plunger_x: 0.0,
            sliding: 0,
            rotor_steps: 0,
            lost_steps: 0,
            forward_moved_steps: 0,
            parity: 0,
            pressure_kpa: p.fluid.tissue_kpa,
            open: false,
            liquid_ul: 0.0,
            bubble_ul: bubble,
            line_air_ul: line_air,
            out_ul: 0.0,
            out_air_ul: 0.0,
            drawn_ul: 0.0,
            peak_pressure_kpa: 0.0,
            p,
        }
    }

    // ---- helpers --------------------------------------------------------------------------
    /// Carriage position along the screw (mm, forward positive) as a function of screw angle,
    /// including the once-per-turn lead error.
    fn carriage_pos(&self, theta: f64) -> f64 {
        self.lead_eff * theta / (2.0 * PI) + self.p.drive.pitch_periodic_um / 1000.0 * theta.sin()
    }

    pub fn carriage_mm(&self) -> f64 {
        self.carriage_pos(self.theta_s)
    }

    pub fn stroke_mm(&self) -> f64 {
        self.stroke
    }

    /// Pressure force on the plunger (N).
    fn pressure_force(&self, p_kpa: f64) -> f64 {
        p_kpa * 1e-3 * self.p.drive.area_mm2
    }

    /// Total compliance dV/dP (ul/kPa) at pressure `p_kpa`: lumped + isothermal air.
    pub fn compliance(&self, p_kpa: f64) -> f64 {
        let atm = self.p.fluid.atm_kpa;
        let air = self.bubble_ul + self.line_air_ul;
        let denom = (atm + p_kpa).max(5.0);
        self.p.fluid.compliance_ul_per_kpa + air * atm / (denom * denom)
    }

    /// Volume pressed into the reservoir system at gauge pressure `p` (ul): lumped compliance plus
    /// isothermal air, S(P) = Cb*P + V*P/(Patm+P). Monotonic; the state variable that conserves volume.
    fn s_of_p(&self, p: f64) -> f64 {
        let atm = self.p.fluid.atm_kpa;
        let air = self.bubble_ul + self.line_air_ul;
        self.p.fluid.compliance_ul_per_kpa * p + air * p / (atm + p).max(5.0)
    }

    /// Inverse of [`Self::s_of_p`] (closed form: a quadratic), floored at about -0.95 atm.
    fn p_of_s(&self, s: f64) -> f64 {
        let atm = self.p.fluid.atm_kpa;
        let air = self.bubble_ul + self.line_air_ul;
        let cb = self.p.fluid.compliance_ul_per_kpa;
        let b = cb * atm + air - s;
        let disc = (b * b + 4.0 * cb * s * atm).max(0.0);
        ((-b + disc.sqrt()) / (2.0 * cb)).max(-0.95 * atm)
    }

    /// Torque the motor can deliver now (N*mm), nominal (no ripple, no supply droop).
    fn torque_nominal(&self, rate_hz: f64) -> f64 {
        let m = &self.p.motor;
        let f = |hz: f64| 1.0 / (1.0 + (hz / m.rolloff_corner_hz).powi(2)).sqrt();
        self.torque_po * f(rate_hz) / f(m.rolloff_ref_hz)
    }

    fn supply_factor(&self, vmot_v: f64) -> f64 {
        let m = &self.p.motor;
        if vmot_v <= m.vmot_min_v {
            0.0
        } else {
            ((vmot_v - m.vmot_min_v) / (m.vmot_full_v - m.vmot_min_v)).clamp(0.0, 1.0)
        }
    }

    /// Plunger response to a carriage move of `dc` mm: returns (delta_out, plunger_move signed
    /// forward-positive, slipped, breakaway force N). Pressure coupling is solved linearly (the
    /// plunger moving changes the pressure that holds it back).
    /// Spring deflection that carries force: the free socket play (`socket_play_mm`) is a dead band around zero.
    fn eff(&self, delta: f64) -> f64 {
        let h = self.p.drive.socket_play_mm / 2.0;
        if delta > h {
            delta - h
        } else if delta < -h {
            delta + h
        } else {
            0.0
        }
    }

    fn plunger_response(&self, dc: f64) -> (f64, f64, Option<f64>) {
        let d = &self.p.drive;
        let h = d.socket_play_mm / 2.0;
        let k = d.axial_stiffness_n_mm;
        let pn = self.pressure_force(self.pressure_kpa);
        let a = d.area_mm2;
        let c = self.compliance(self.pressure_kpa);
        let beta = a * a * 1e-3 / (k * c);
        let dtrial_full = self.delta + dc;
        let dtrial = self.eff(dtrial_full);
        for s in [1i8, -1i8] {
            let sf = s as f64;
            let f_thr = if self.sliding == s { d.seal_dynamic_n } else { d.seal_static_n };
            let hold = f_thr + sf * pn;
            if sf * k * dtrial > hold {
                // slip: settle where the spring force equals dynamic friction + pressure
                let target = (d.seal_dynamic_n + sf * pn) / k;
                let mut dp = sf * (sf * dtrial - target) / (1.0 + beta); // signed forward
                if sf * dp < 0.0 {
                    dp = 0.0;
                }
                // end stops: front at 0, rear at stroke
                let x_new = self.plunger_x - dp;
                if x_new < 0.0 {
                    dp = self.plunger_x;
                } else if x_new > self.stroke {
                    dp = self.plunger_x - self.stroke;
                }
                if dp != 0.0 {
                    return (dtrial - dp + sf * h, dp, Some(hold));
                }
                // pushed against a stop: stuck, spring takes the load
                return (dtrial_full, 0.0, None);
            }
        }
        (dtrial_full, 0.0, None)
    }

    fn apply_plunger(&mut self, dp: f64, delta_out: f64, slipped: bool) {
        self.delta = delta_out;
        if slipped {
            self.sliding = if dp > 0.0 { 1 } else { -1 };
            self.plunger_x -= dp;
            let dv = self.p.drive.area_mm2 * dp; // ul displaced forward (negative: cavity grows)
            let s = self.s_of_p(self.pressure_kpa) + dv;
            self.pressure_kpa = self.p_of_s(s);
            self.peak_pressure_kpa = self.peak_pressure_kpa.max(self.pressure_kpa);
        } else {
            self.sliding = 0;
        }
    }

    // ---- one motor step -----------------------------------------------------------------------
    /// Execute one commanded step in direction `dir` (+1 forward / -1 reverse) at `rate_hz` with the
    /// motor supply at `vmot_v` volts. Returns whether the rotor followed and the current drawn.
    pub fn step(&mut self, dir: i32, rate_hz: f64, vmot_v: f64, rng: &mut Rng) -> StepResult {
        let m = self.p.motor.clone();
        let d = dir as f64;
        self.parity = self.parity.wrapping_add(1);
        let nominal = self.torque_nominal(rate_hz);
        let mut avail = nominal * self.supply_factor(vmot_v) * (1.0 + m.torque_ripple_pct / 100.0 * rng.gauss());
        if self.phase_open {
            avail *= 0.5;
        }
        let noise = m.i_noise_ma * rng.gauss();

        // driver motion in the screw domain
        let dth = d * 2.0 * PI / self.steps_per_turn;
        let b = self.backlash_rad;
        let g = self.gap + dth;
        let (gap_new, dtheta_s) = if g > b / 2.0 {
            (b / 2.0, g - b / 2.0)
        } else if g < -b / 2.0 {
            (-b / 2.0, g + b / 2.0)
        } else {
            (g, 0.0)
        };

        let mut t_req = 0.0;
        let mut plan: Option<(f64, f64, bool, f64)> = None; // delta_out, dp, slipped, carriage dc
        if dtheta_s != 0.0 {
            let c_new = self.carriage_pos(self.theta_s + dtheta_s);
            if c_new < -self.stroke {
                // the carriage meets the rear end-stop of the housing: the screw cannot turn any more
                self.lost_steps += 1;
                let current = (m.i_stall_ma) * if self.phase_open { 0.55 } else { 1.0 } + noise;
                return StepResult { moved: false, current_ma: current.max(0.0), load_frac: 9.9 };
            }
            let dc = c_new - self.carriage_pos(self.theta_s);
            let (delta_out, dp, brk) = self.plunger_response(dc);
            let k = self.p.drive.axial_stiffness_n_mm;
            let spring_after = d * k * self.eff(delta_out);
            // The screw must supply the break-away force (static friction + pressure) at the moment the
            // plunger lets go; with the plunger stuck it supplies the spring force. An assisting spring
            // (reverse motion unloading it) costs nothing. Friction in the lane always opposes.
            let opp = match brk {
                Some(h) => h.max(0.0),
                None => spring_after.max(0.0),
            };
            let force = opp + self.p.drive.carriage_friction_n;
            let t_screw = force * self.lead_eff / (2.0 * PI * self.p.drive.screw_eff);
            let rot_per_screw = self.steps_per_turn / m.steps_per_rev;
            t_req = t_screw / (rot_per_screw * m.gearhead_eff * self.p.drive.pair_eff);
            plan = Some((delta_out, dp, brk.is_some(), dc));
        }

        let load_frac = if nominal > 0.0 { t_req / nominal } else { 9.9 };
        let open_fac = if self.phase_open { 0.55 } else { 1.0 };
        let mut lost = t_req > avail;
        if self.phase_open && self.parity % 2 == 1 {
            lost = true; // an open phase: the rotor can only follow every other step
        }
        if avail <= 0.0 {
            lost = true;
        }
        let frac_i = if lost { 1.0 } else { load_frac.clamp(0.0, 1.0) };
        let current = (m.i_free_ma + (m.i_stall_ma - m.i_free_ma) * frac_i) * open_fac + noise;
        if lost {
            self.lost_steps += 1;
            return StepResult { moved: false, current_ma: current.max(0.0), load_frac };
        }

        // the step happens
        self.rotor_steps += dir as i64;
        self.gap = gap_new;
        if dir > 0 {
            self.forward_moved_steps += 1;
        }
        if let Some((delta_out, dp, slipped, _dc)) = plan {
            self.theta_s += dtheta_s;
            self.apply_plunger(dp, delta_out, slipped);
        }
        StepResult { moved: true, current_ma: current.max(0.0), load_frac }
    }

    // ---- time passing ---------------------------------------------------------------------------
    /// Let the plant relax for `dt` seconds: stored spring energy creeps the plunger forward when the
    /// pressure fell, the duckbill bleeds the compliance, the vial refills the reservoir.
    pub fn relax(&mut self, dt: f64) {
        // plunger creep from stored spring force
        let (delta_out, dp, brk) = self.plunger_response(0.0);
        if brk.is_some() {
            self.apply_plunger(dp, delta_out, true);
        } else if self.sliding != 0 {
            self.sliding = 0;
        }
        let f = self.p.fluid.clone();
        let c = self.compliance(self.pressure_kpa);
        let p0 = self.pressure_kpa;
        let s0 = self.s_of_p(p0);
        // ---- inflow from the vial (negative pressure, needle in the septum) ----
        // (assisted fill: the syringe holds `fill_push_kpa` on the septum, 0 for suction from a vial)
        let p_src = self.fill_push_kpa.max(0.0);
        if self.fill_needle && p0 < p_src {
            let a = dt / (f.fill_needle_r * c);
            let vin = dt / f.fill_needle_r * (p_src - p0) / (1.0 + a); // linearised backward Euler, ul
            self.pressure_kpa = self.p_of_s(s0 + vin).min(p_src);
            self.liquid_ul += vin;
            self.drawn_ul += vin;
            self.net_in_ul += vin;
            if p_src <= 0.0 {
                self.bubble_ul += vin * f.draw_air_ul_per_ml / 1000.0;
            }
            if p0 < 0.0 {
                return;
            }
        }
        let (p0, s0) = (self.pressure_kpa, self.s_of_p(self.pressure_kpa));
        // ---- closed reservoir under vacuum: air creeps in through the outlet ----
        if p0 < 0.0 {
            let p_new = p0 * (-dt / f.vacuum_leak_tau_s.max(1e-3)).exp();
            let leaked = self.s_of_p(p_new) - s0;
            self.pressure_kpa = p_new;
            self.line_air_ul += leaked.max(0.0);
            return;
        }
        // ---- outflow through the duckbill ----
        if !self.open && p0 >= f.crack_kpa {
            self.open = true;
        }
        if self.open {
            let r = f.outlet_r * f.occlusion_factor.max(1e-6);
            let a = dt / (r * c);
            let mut v_out = dt / r * (p0 - f.tissue_kpa) / (1.0 + a);
            let mut p_new = self.p_of_s(s0 - v_out);
            let p_close = (f.crack_kpa * f.close_ratio).max(f.tissue_kpa);
            if p_new <= p_close {
                p_new = p_close.min(p0);
                v_out = s0 - self.s_of_p(p_new);
                self.open = false;
            }
            self.pressure_kpa = p_new;
            self.emit(v_out);
        }
    }

    fn emit(&mut self, v: f64) {
        if v <= 0.0 {
            return;
        }
        let air = v.min(self.line_air_ul);
        self.line_air_ul -= air;
        self.out_air_ul += air;
        let rest = v - air;
        let liq = rest.min(self.liquid_ul.max(0.0));
        self.liquid_ul -= liq;
        self.out_ul += liq;
        self.net_in_ul -= liq;
        self.out_air_ul += rest - liq; // reservoir ran dry: air is pumped
    }

    /// Volume pressed into the system by the current gauge pressure (ul): lumped compliance plus compressed air.
    pub fn compressed_ul(&self) -> f64 {
        self.s_of_p(self.pressure_kpa.max(0.0))
    }

    /// Water that really sits behind the plunger (ul): the cavity the plunger opened (`plunger_x` x area) less the air that
    /// came in with it (bubble and line air). Independent of the syringe pressure and of what leaks at the needle tip, so
    /// it is the fill as a gravimetric check would see it.
    pub fn filled_ul(&self) -> f64 {
        self.p.drive.area_mm2 * self.plunger_x - self.bubble_ul - self.line_air_ul
    }

    /// Fluid still held under pressure (not yet delivered), ul.
    pub fn stored_ul(&self) -> f64 {
        self.compliance(self.pressure_kpa) * (self.pressure_kpa - self.p.fluid.tissue_kpa).max(0.0)
    }

    /// Volume the plunger has displaced since the start net of the draw (U), for diagnostics.
    pub fn plunger_volume_ul(&self) -> f64 {
        self.p.drive.area_mm2 * self.plunger_x
    }

    pub fn set_occlusion_factor(&mut self, f: f64) {
        self.p.fluid.occlusion_factor = f;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run_steps(pl: &mut Plant, n: u32, dir: i32, rate: f64, rng: &mut Rng) -> u32 {
        let mut ok = 0;
        for _ in 0..n {
            if pl.step(dir, rate, 3.8, rng).moved {
                ok += 1;
            }
            pl.relax(1.0 / rate);
        }
        ok
    }

    fn quiet() -> Params {
        let mut p = Params::default();
        p.motor.torque_ripple_pct = 0.0;
        p
    }

    #[test]
    fn draw_from_empty_fills_by_the_plunger_travel() {
        let mut rng = Rng::new(1);
        let mut pl = Plant::new(quiet());
        pl.fill_needle = true;
        // draw 3000 steps (~18.5 U) starting with the plunger at the front stop
        let n = run_steps(&mut pl, 3000, -1, 600.0, &mut rng);
        assert_eq!(n, 3000);
        pl.relax(5.0);
        // plunger travel x area = drawn volume (the first ~6 steps only take up the backlash)
        let want = pl.plunger_x * pl.p.drive.area_mm2;
        assert!((pl.drawn_ul - want).abs() / want < 0.02, "drawn {} vs travel {}", pl.drawn_ul, want);
        // from the as-assembled state (loaded forward) the whole socket play (0.30 mm) of the first reversal is lost motion
        let lost_u = pl.p.drive.socket_play_mm * pl.p.drive.area_mm2 / 10.0;
        assert!((pl.drawn_ul / 10.0 - (3000.0 * pl.p.true_u_per_step() - lost_u)).abs() < 0.4, "{}", pl.drawn_ul);
    }

    #[test]
    fn fill_requires_room_behind_the_plunger() {
        // start with the plunger mid-stroke, then draw
        let mut rng = Rng::new(1);
        let mut pl = Plant::new(quiet());
        pl.plunger_x = 5.0;
        pl.fill_needle = true;
        let n = run_steps(&mut pl, 1000, -1, 600.0, &mut rng);
        assert!(n > 900, "{n}");
        assert!(pl.plunger_x > 5.0);
        pl.relax(5.0);
        assert!(pl.drawn_ul > 12.0, "drawn {}", pl.drawn_ul); // 1000 steps x 3.95 mU = 39 ul less the 0.30 mm of socket play (22 ul)
    }

    #[test]
    fn delivery_matches_geometry() {
        let mut rng = Rng::new(2);
        let mut pl = Plant::new(quiet());
        pl.plunger_x = 10.0;
        pl.liquid_ul = 745.0;
        pl.line_air_ul = 0.0;
        // wind up the system first (backlash, stiction), then measure
        run_steps(&mut pl, 400, 1, 200.0, &mut rng);
        pl.relax(30.0);
        let out0 = pl.out_ul;
        let n = run_steps(&mut pl, 2000, 1, 200.0, &mut rng);
        pl.relax(60.0);
        assert_eq!(n, 2000);
        let got_u = (pl.out_ul - out0) / 10.0;
        let want_u = 2000.0 * pl.p.true_u_per_step();
        assert!((got_u - want_u).abs() / want_u < 0.01, "got {got_u} want {want_u}");
    }

    #[test]
    fn full_occlusion_pressure_is_torque_limited() {
        let mut rng = Rng::new(3);
        let mut p = quiet();
        p.fluid.occlusion_factor = 1e6;
        let mut pl = Plant::new(p);
        pl.plunger_x = 10.0;
        pl.liquid_ul = 745.0;
        let n = run_steps(&mut pl, 3000, 1, 200.0, &mut rng);
        assert!(n < 3000, "motor must stall");
        assert!(pl.lost_steps > 0);
        // pull-out limit: ~7 N / 74.6 mm^2 ~ 90 kPa
        assert!(pl.peak_pressure_kpa > 40.0 && pl.peak_pressure_kpa < 150.0, "{}", pl.peak_pressure_kpa);
        assert!(pl.out_ul < 5.0);
    }

    #[test]
    fn backlash_after_reversal_loses_steps_of_travel() {
        let mut rng = Rng::new(4);
        let mut pl = Plant::new(quiet());
        pl.plunger_x = 10.0;
        pl.fill_needle = true;
        run_steps(&mut pl, 100, 1, 200.0, &mut rng);
        run_steps(&mut pl, 100, -1, 600.0, &mut rng);
        let th0 = pl.theta_s;
        run_steps(&mut pl, 100, 1, 200.0, &mut rng);
        let moved_steps = (pl.theta_s - th0) / (2.0 * PI) * pl.steps_per_turn;
        let lost = 100.0 - moved_steps;
        // backlash 2 + 1.5*16/20 = 3.2 deg (screw domain) at 0.544 deg/step ~ 5.9 steps
        assert!(lost > 4.5 && lost < 7.5, "lost {lost}");
    }

    #[test]
    fn open_phase_loses_half_the_steps() {
        let mut rng = Rng::new(5);
        let mut pl = Plant::new(quiet());
        pl.plunger_x = 10.0;
        pl.phase_open = true;
        let n = run_steps(&mut pl, 400, 1, 200.0, &mut rng);
        assert!((150..=210).contains(&n), "{n}");
    }

    #[test]
    fn torque_budget_matches_spec_thrust() {
        // spec 4: pull-out 1.6 gf*cm x 26.45 x 0.64 -> 2.65 N*mm at the gearhead output, ~9.5 N at 20 %
        let p = Params::default();
        let t_out = p.motor.pullout_gf_cm * GF_CM_TO_N_MM * p.motor.gearhead_ratio * p.motor.gearhead_eff;
        assert!((t_out - 2.65).abs() < 0.03, "{t_out}");
        let f = t_out * 2.0 * PI * p.drive.screw_eff / p.drive.lead_mm;
        assert!((f - 9.5).abs() < 0.2, "{f}");
    }
}
