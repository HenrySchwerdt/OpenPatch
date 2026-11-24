//! `openpatch_core::Hal` for the bench controller (E73) and the DK.
use core::sync::atomic::Ordering;
use embassy_time::Instant;
use openpatch_core::units::{AngleCounts, Millis, Pulses};
use openpatch_core::hal::{DiagEvent, InterlockReadback, MotorDir, MotorFault, SelfTestOutcome, SelfTestStep};
use openpatch_core::interlock;
use openpatch_core::{Buzzer, Hal};

use crate::board;
use crate::config::*;
use crate::shared::*;

use super::adc::{self, Adc};
use super::angle::AngleSource;
use super::driver::{self, Driver};
use super::stepper::Stepper;
use super::{classify_resetreas, wdt};

pub struct BenchHal {
    /// Reverse (draw) STCK period in PWM ticks; set from the fill needle gauge by `set_draw_rate_pps`.
    reverse_period_ticks: u16,
    stepper: Stepper,
    /// The host-tested interlock controller over the pins (it owns the ADC and the DOCK_N input).
    drv: Driver,
    last_peak_ma: Option<u16>,
    angle: AngleSource,
    /// Burst bookkeeping for diagnostics.
    bursts: u32,
}

impl BenchHal {
    pub fn new(stepper: Stepper, adc: Adc, angle: AngleSource, io_dir: BoardIoDriver, dock_n: Option<embassy_nrf::Peri<'static, embassy_nrf::gpio::AnyPin>>, wdt_done: Option<embassy_nrf::Peri<'static, embassy_nrf::gpio::AnyPin>>) -> Self {
        // DONE is an output that idles low; the pulse is issued by the WAKE interrupt (`wdt`), never from here.
        let drv = driver::new_driver(adc, io_dir.dir, io_dir.stby, io_dir.en_fault, io_dir.interlock, dock_n, wdt_done);
        Self { reverse_period_ticks: REVERSE_PERIOD_TICKS, stepper, drv, last_peak_ma: None, angle, bursts: 0 }
    }

    /// POST-S, the passive part, at boot (before the first tick): the findings are queued as diagnostic events that
    /// the core raises on its first tick. The motor is never driven. Only with the interlock board.
    pub fn boot_post_s(&mut self) {
        if !board::HAS_INTERLOCK {
            return;
        }
        let clean = self.drv.post_s().is_none();
        INTERLOCK_FAILED.store(self.drv.failed, Ordering::Relaxed);
        defmt::info!("POST-S: {}", if clean { "clean" } else { "findings queued" });
    }

    /// Monotonic time for the safety task (same clock as `Hal::time_ms`).
    pub fn time_ms_now(&mut self) -> Millis {
        Millis(Instant::now().as_millis())
    }

    /// Interlock failure flag for the safety task (also published to the UI).
    pub fn interlock_failed(&self) -> bool {
        self.drv.failed || self.drv.quarantined
    }

    /// The supply could not be verified cut and a reset can clear it: DONE must be withheld (not for a quarantined board,
    /// where nothing on the board can cut the supply and a reset loop would only hide the alarm).
    pub fn watchdog_must_lapse(&self) -> bool {
        self.drv.failed
    }

    fn read_docked(&mut self) -> bool {
        match self.drv.pins.dock_n.as_ref() {
            Some(pin) => pin.is_low(), // DOCK_N active low
            None => DOCK_SIM.load(Ordering::Relaxed),
        }
    }
}

/// Driver related pins split out of `board::BoardIo` in `main`.
pub struct BoardIoDriver {
    pub dir: embassy_nrf::Peri<'static, embassy_nrf::gpio::AnyPin>,
    pub stby: embassy_nrf::Peri<'static, embassy_nrf::gpio::AnyPin>,
    pub en_fault: embassy_nrf::Peri<'static, embassy_nrf::gpio::AnyPin>,
    pub interlock: Option<board::InterlockPins>,
}

impl BenchHal {
    /// Common burst: checks, power state, sampling of current and angle, honest executed count.
    fn burst(&mut self, steps: Pulses, forward: bool) -> Pulses {
        let max = if forward { MAX_BURST_STEPS } else { MAX_REVERSE_BURST_STEPS };
        let dir = if forward { MotorDir::Forward } else { MotorDir::Reverse };
        if !self.drv.powered {
            defmt::warn!("motor step without motor_enable: refused");
            self.drv.fault.get_or_insert(MotorFault::SupplyMissing);
            return Pulses(0);
        }
        if self.drv.quarantined {
            self.drv.fault = Some(MotorFault::InterlockFailed);
            return Pulses(0);
        }
        // Forward while undocked is a FAULT (the gate is open in hardware, nothing may be retried),
        // reverse while docked is refused too. Both cut the supply.
        let docked = self.read_docked();
        if let Err(r) = interlock::check_request(dir, docked) {
            defmt::error!("motor step refused: {}", r);
            self.drv.fault = Some(r.into());
            self.drv.power_off();
            INTERLOCK_FAILED.store(self.interlock_failed(), Ordering::Relaxed);
            return Pulses(0);
        }
        // DIR changes while powered (not the normal path: `motor_enable_dir` sets it first) are
        // checked against the gate model.
        if let Err(e) = self.drv.change_direction(docked, dir) {
            defmt::error!("direction change while powered failed: {}", e);
            self.drv.fault = Some(e.to_fault());
            INTERLOCK_FAILED.store(self.interlock_failed(), Ordering::Relaxed);
            return Pulses(0);
        }
        if steps.0 == 0 || steps.0 > max {
            defmt::warn!("motor step({}) outside 1..={}: refused", steps.0, max);
            self.drv.fault.get_or_insert(MotorFault::Timeout);
            return Pulses(0);
        }
        if !forward {
            // rate cap: the period can never go below 1 ms (<= 1000 pps)
            const _: () = assert!(REVERSE_PERIOD_TICKS as u32 >= STEP_PWM_CLK_HZ / REVERSE_RATE_MAX_HZ);
            self.service_watchdog(); // chunks take up to ~0.9 s, keep the TPL5010 happy between them
        }
        let period = if forward { STEP_PWM_PERIOD_TICKS } else { self.reverse_period_ticks };
        let mut peak_raw: u16 = 0;
        let mut samples: u32 = 0;
        let sense = board::HAS_CURRENT_SENSE;
        let mut last_poll = Instant::now();
        let adc = &mut self.drv.pins.adc;
        let angle = &mut self.angle;
        let burst = self.stepper.burst(steps.0, period, || {
            if sense && samples < ADC_MAX_SAMPLES_PER_BURST {
                let s = adc.scan();
                peak_raw = peak_raw.max(s.isense);
                samples += 1;
            }
            // keep the angle unwrap valid during the burst
            if Instant::now() - last_poll >= embassy_time::Duration::from_millis(ANGLE_POLL_MS) {
                last_poll = Instant::now();
                angle.poll();
            }
        });
        self.bursts = self.bursts.wrapping_add(1);
        let executed = burst.counted.min(steps.0);
        self.last_peak_ma = sense.then(|| adc::isense_to_ma(peak_raw));
        if board::ENCODER_SIMULATED {
            self.angle.simulate_pulses(if forward { executed as i64 } else { -(executed as i64) });
        } else {
            self.angle.poll();
        }
        if burst.timed_out || executed < steps.0 {
            defmt::error!("step burst incomplete: {} of {} (timeout={})", executed, steps.0, burst.timed_out);
        }
        defmt::debug!(
            "burst fwd={} pulses={} peak_ma={} samples={} qdec_counts={}",
            forward,
            executed,
            self.last_peak_ma,
            samples,
            ENC_COUNTS.load(Ordering::Relaxed)
        );
        if board::HAS_MOTOR_DRIVER && self.drv.fault_asserted() {
            // The STSPIN220 pulled EN/FAULT low (over-current / thermal): the power stage was off
            // for some or all of the burst. Report 0 pulses: the core latches INTERNAL / stops.
            defmt::error!("STSPIN220 EN/FAULT asserted during the burst: reporting 0 pulses");
            self.drv.fault = Some(MotorFault::Driver);
            return Pulses(0);
        }
        // The supply must still follow the gate (dock lost mid burst opens the gate in forward).
        let docked_now = self.read_docked();
        if let Err(e) = self.drv.verify_supply(docked_now) {
            defmt::error!("supply check after the burst failed: {}: reporting 0 pulses", e);
            self.drv.fault = Some(e.to_fault());
            INTERLOCK_FAILED.store(self.interlock_failed(), Ordering::Relaxed);
            return Pulses(0);
        }
        if burst.timed_out {
            self.drv.fault.get_or_insert(MotorFault::Timeout);
        }
        Pulses(executed)
    }

    /// Grant the DONE permit for the WAKE interrupt (`wdt`), only if the interlock verification passes. If it failed, the
    /// permit is withdrawn on purpose: DONE is withheld, the TPL5010 resets the MCU and its RSTn clears the interlock
    /// latch in hardware. A quarantined board (Q4 shorted: nothing on the board can cut the supply, a reset can not help)
    /// keeps the permit so the MCU stays alive for the alarm, with STBY low.
    fn service_watchdog(&mut self) {
        let idle_ok = self.drv.verify_idle();
        INTERLOCK_FAILED.store(self.interlock_failed(), Ordering::Relaxed);
        if self.drv.failed || (!idle_ok && !self.drv.quarantined) {
            wdt::revoke_permit();
            return;
        }
        wdt::grant_permit();
    }
}

impl Hal for BenchHal {
    fn motor_step(&mut self, steps: Pulses) -> Pulses {
        self.burst(steps, true)
    }

    /// Draw rate from the core (fill needle gauge): clamped to the hard cap `REVERSE_RATE_MAX_HZ` (period >= 1 ms) and to
    /// what the 15 bit PWM countertop can express (>= 31 pps at the 1 MHz PWM clock).
    fn set_draw_rate_pps(&mut self, pps: u32) {
        let pps = pps.clamp(STEP_PWM_CLK_HZ / 32_767 + 1, REVERSE_RATE_MAX_HZ);
        self.reverse_period_ticks = (STEP_PWM_CLK_HZ / pps) as u16;
    }

    fn reset_cause(&mut self) -> openpatch_core::hal::ResetCause {
        classify_resetreas(RESET_REASON.load(Ordering::Relaxed))
    }

    /// Draw mode: DIR reversed, <= 1000 pps (600 Hz here). The core calls this undocked.
    fn motor_step_reverse(&mut self, steps: Pulses) -> Pulses {
        self.burst(steps, false)
    }

    fn motor_enable(&mut self, enable: bool) {
        if enable {
            self.motor_enable_dir(MotorDir::Forward);
        } else {
            self.drv.power_off();
            INTERLOCK_FAILED.store(self.interlock_failed(), Ordering::Relaxed);
        }
    }

    /// DIR is set BEFORE the supply is requested (`VMOT = MCU_EN AND latch AND (DOCKED XOR DIR_REVERSE)`):
    /// a draw (undocked, reverse) only comes up this way; forward needs DOCKED.
    fn motor_enable_dir(&mut self, dir: MotorDir) {
        let docked = self.read_docked();
        self.drv.fault = None;
        if let Err(e) = self.drv.power_up(docked, dir) {
            defmt::error!("motor power-up refused: {}", e);
            self.drv.fault = Some(e.to_fault());
        }
        INTERLOCK_FAILED.store(self.interlock_failed(), Ordering::Relaxed);
    }

    fn motor_fault(&mut self) -> Option<MotorFault> {
        self.drv.fault.take()
    }

    /// Cumulative unwrapped leadscrew angle; `None` = sensor missing (the core refuses to deliver).
    fn angle_read(&mut self) -> Option<AngleCounts> {
        self.angle.read().map(AngleCounts)
    }

    /// Answers the TPL5010 WAKE with one DONE pulse, only if the driver side is verified safe.
    /// If the interlock verification failed, DONE is withheld on purpose: the TPL5010 then resets
    /// the MCU, and its RSTn clears the interlock latch in hardware.
    fn watchdog_kick(&mut self) {
        if board::HAS_MOTOR_DRIVER && self.drv.fault_asserted() {
            defmt::error!("STSPIN220 EN/FAULT low while powered");
        }
        self.service_watchdog();
    }

    fn buzzer(&mut self, pattern: Buzzer) {
        match pattern {
            Buzzer::Off => {
                ALARM_ON.store(false, Ordering::Relaxed);
                BEEP_REQ.store(false, Ordering::Relaxed);
                DOUBLE_BEEP_REQ.store(false, Ordering::Relaxed);
            }
            Buzzer::Beep => BEEP_REQ.store(true, Ordering::Relaxed),
            Buzzer::DoubleBeep => DOUBLE_BEEP_REQ.store(true, Ordering::Relaxed),
            Buzzer::Alarm => ALARM_ON.store(true, Ordering::Relaxed),
        }
    }

    /// Bench board: VBUS through the 100k/100k divider (about 5000 mV). A sagging USB supply below
    /// the core's thresholds (3500 / 3300 mV) raises LOW_BATTERY / BATTERY_CRITICAL on purpose.
    /// DK: the fixed `BATTERY_MV_FIXED`.
    fn battery_mv(&mut self) -> u16 {
        if !board::HAS_VBUS_SENSE {
            return BATTERY_MV_FIXED;
        }
        adc::divided_to_mv(self.drv.pins.adc.scan().vbus).min(u16::MAX as u32) as u16
    }

    fn time_ms(&mut self) -> Millis {
        Millis(Instant::now().as_millis())
    }

    fn docked(&mut self) -> bool {
        self.read_docked()
    }

    fn motor_current_peak_ma(&mut self) -> Option<u16> {
        self.last_peak_ma
    }

    /// Findings of the controller (POST-S at boot, idle checks, power-up / power-down verification), as data.
    fn take_diag(&mut self) -> Option<DiagEvent> {
        self.drv.take_event()
    }

    /// RB1..RB10 snapshot for the POST and the tick checks. `None` on a board without the interlock (UNKNOWN, never OK).
    fn interlock_state(&mut self) -> Option<InterlockReadback> {
        board::HAS_INTERLOCK.then(|| self.drv.readback())
    }

    /// POST proofs (core sequences, the controller owns the pins). Only while the pump is SUSPENDED. A board without
    /// the interlock reports `Unsupported`, so the DK never shows an interlock proof as passed.
    fn selftest(&mut self, step: SelfTestStep) -> SelfTestOutcome {
        let out = self.drv.selftest(step);
        INTERLOCK_FAILED.store(self.interlock_failed(), Ordering::Relaxed);
        out
    }
}

