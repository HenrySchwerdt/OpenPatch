//! Draw mode (automatic refill): the app sends `FillDraw(amount)`, the motor reverses exactly that
//! volume at a limited rate (<= 1000 pps: 500 steps per ~1 s tick), the angle sensor and the motor
//! current detect a stall / the rear end-stop, and the pump reports the volume actually drawn.
//!
//! Only while suspended AND undocked (a docked pod is connected to the body: never reverse there).
//! The reservoir level is set from the steps the angle sensor confirmed (conservative minimum of
//! commanded and measured), mandatory priming follows.

use crate::diag::{codes, Raise};
use crate::hal::{Buzzer, Hal, MotorDir};
use crate::limits::*;
use crate::log::EventType;
use crate::pump::{draw_state, Notification, Pump};
use crate::units::*;
use openpatch_proto::Error;

impl<H: Hal> Pump<H> {
    /// Start (or with `amount` 0 cancel) a draw of `amount` mU.
    pub fn fill_draw(&mut self, amount: MilliUnits) -> Result<(), Error> {
        if amount.0 == 0 {
            if !self.draw_running() {
                return Err(Error::NotFound);
            }
            self.draw_abort();
            return Ok(());
        }
        if !self.de.is_suspended() {
            return Err(Error::NotSuspended);
        }
        self.refresh_dock();
        if self.pod.docked {
            return Err(Error::Docked);
        }
        if !self.sv.motor_allowed() {
            return Err(Error::Fault);
        }
        if self.draw_running() {
            return Err(Error::Busy);
        }
        let room = self.res.capacity().0 - self.res.remaining().0.min(self.res.capacity().0);
        if amount.0 > room {
            return Err(Error::Limit);
        }
        let steps = self.pcal.mu_to_pulses(amount);
        if steps.0 == 0 {
            return Err(Error::BadArg);
        }
        if self.hal.angle_read().is_none() {
            return Err(Error::Fault); // never move blind
        }
        let pps = if self.cfg.strict_draw { draw_pps(self.cfg.fill_needle, self.pcal) } else { DRAW_DEFAULT_PPS };
        self.hal.set_draw_rate_pps(pps);
        self.draw = crate::pump::DrawJob {
            pps,
            state: draw_state::DRAWING,
            requested_mu: amount.0,
            remaining_steps: steps.0,
            ..Default::default()
        };
        self.log_ev(EventType::DrawStart, amount.0 as i32, steps.0 as i32);
        Ok(())
    }

    /// Cancel a running draw (partial volume is booked). No-op when idle.
    pub(crate) fn draw_abort(&mut self) {
        if self.draw_running() {
            self.draw_finish(draw_state::ABORTED, 3); // cancelled
        }
    }

    /// One chunk of the running draw job. Called from `tick()`.
    pub(crate) fn draw_step(&mut self) {
        if !self.draw_running() {
            return;
        }
        // safety gates re-checked every chunk
        if self.pod.docked || !self.de.is_suspended() || !self.sv.motor_allowed() {
            let reason = if self.pod.docked { 1 } else { 2 }; // docked / fault
            self.draw_finish(draw_state::ABORTED, reason);
            return;
        }
        let Some(a0) = self.hal.angle_read() else {
            self.sv.raise(Raise::new(codes::ANGLE_CHANNEL_LOST));
            self.draw_finish(draw_state::ABORTED, 2);
            return;
        };
        let chunk = if self.cfg.strict_draw { draw_chunk_steps(self.draw.pps) } else { DRAW_CHUNK_STEPS };
        let steps = Pulses(self.draw.remaining_steps.min(chunk));
        // DIR = reverse is set before the supply is requested (the bench gate needs it).
        self.hal.motor_enable_dir(MotorDir::Reverse);
        let n = self.hal.motor_step_reverse(steps);
        self.hal.motor_enable(false);
        let executed = Pulses(n.0.min(steps.0));
        if let Some(f) = self.hal.motor_fault() {
            self.last_motor_fault = Some(f);
            self.raise_motor_fault(f, executed);
            if f == crate::hal::MotorFault::SupplyMissing {
                // the reverse burst executed nothing because VMOT never came up: the bench interlock limitation
                let cause = self.hal_rec;
                self.sv.raise(Raise::new(codes::DRAW_BLOCKED_NO_VMOT).a(executed.0 as i32).caused_by(cause));
            }
            self.draw.executed_steps += executed.0;
            self.draw_finish(draw_state::ABORTED, 2);
            return;
        }
        let peak = self.hal.motor_current_peak_ma();
        let Some(a1) = self.hal.angle_read() else {
            self.sv.raise(Raise::new(codes::ANGLE_CHANNEL_LOST));
            self.draw_finish(draw_state::ABORTED, 2);
            return;
        };
        // A04: reverse pulses must DECREASE the angle. A burst that moved it forward proves a wrong
        // direction polarity (which would let an undocked pod run forward): latched.
        let rose = a1.0 - a0.0;
        let expected = self.pcal.expected_angle(executed).0;
        if executed.0 >= DIR_INVERTED_MIN_STEPS && rose * 100 > expected * DIR_INVERTED_PCT {
            self.sv.raise(Raise::new(codes::DIR_INVERTED).a(rose as i32).b(expected as i32).c(executed.0));
            self.draw.executed_steps += executed.0;
            self.draw_finish(draw_state::ABORTED, 2);
            return;
        }
        // steps confirmed by the angle sensor (reverse travel), never more than commanded
        let travelled = (a0.0 - a1.0).max(0);
        let measured = Pulses(((travelled as u128 * self.pcal.turn_x100 as u128) / (ANGLE_COUNTS_PER_TURN as u128 * 100)) as u32);
        let confirmed = Pulses(measured.0.min(executed.0));
        self.draw.executed_steps += executed.0;
        self.draw.confirmed_steps += confirmed.0;
        self.draw.remaining_steps -= executed.0;
        self.draw.drawn_mu = self.pcal.pulses_to_mu(Pulses(self.draw.confirmed_steps)).0;
        self.sv.rebaseline(a1); // reverse travel is not a forward-delivery deviation

        let slipped = steps.0 > 0 && (confirmed.0 as i64) * 100 < (steps.0 as i64) * DRAW_STALL_PCT;
        // draw mode has its own stall threshold (F5): the reverse stroke at 600 pps legitimately loads the motor more
        let stall_ma = if self.cfg.strict_draw { self.draw_stall_ma } else { self.sv.occlusion_current_ma() };
        match peak {
            Some(ma) if ma > stall_ma => self.draw.high_current += 1,
            Some(_) => self.draw.high_current = 0,
            None => {}
        }
        let current_stall = self.draw.high_current >= OCCLUSION_CURRENT_BURSTS;
        if executed.0 < steps.0 || slipped || current_stall {
            self.draw_finish(draw_state::STALLED, 4);
        } else if self.draw.remaining_steps == 0 {
            self.draw_finish(draw_state::DONE, 0);
        } else {
            let d = self.draw.drawn_mu;
            self.notify(Notification::DrawProgress(d));
        }
    }

    /// `reason` (for `7-73-001` inst): 1 docked, 2 fault, 3 cancelled, 4 stall; 0 = finished normally.
    fn draw_finish(&mut self, state: u8, reason: u8) {
        self.draw.state = state;
        self.hal.motor_enable(false);
        let drawn = Pulses(self.draw.confirmed_steps);
        if drawn.0 > 0 {
            self.res.draw_in(drawn);
            let ang = self.hal.angle_read().unwrap_or(AngleCounts(0));
            self.sv.rebaseline(ang);
            self.low_res_reported = self.res.is_low();
            if self.cfg.require_prime_after_fill {
                self.prime_required = true;
            }
            self.takeup_pending = self.pcal.mu_to_pulses(MilliUnits(self.cfg.takeup_mu)).0; // the drive reversed: backlash must be taken up before the prime
        }
        let (d, req) = (self.draw.drawn_mu as i32, self.draw.requested_mu as i32);
        match state {
            draw_state::DONE => {
                self.log_ev(EventType::DrawDone, d, req);
                self.hal.buzzer(Buzzer::DoubleBeep);
                self.notify(Notification::DrawDone(self.draw.drawn_mu));
            }
            draw_state::STALLED => {
                self.log_ev(EventType::DrawStall, d, req);
                self.hal.buzzer(Buzzer::DoubleBeep);
                self.notify(Notification::DrawStalled(self.draw.drawn_mu));
            }
            _ => self.log_ev(EventType::DrawStall, d, req),
        }
        if state == draw_state::ABORTED || state == draw_state::STALLED {
            self.sv.raise(Raise::new(codes::DRAW_ABORTED).inst(reason).a(d).b(req));
        }
    }
}
