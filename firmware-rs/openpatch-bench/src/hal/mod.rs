//! `openpatch_core::Hal` for the bench controller. Owned by the `Pump` in the safety task.
//!
//! The core's `motor_step` is a short blocking call. Here it generates the pulses in hardware
//! ([`stepper`]) and busy-waits on the hardware counter while sampling the motor current.
use core::sync::atomic::Ordering;
use embassy_nrf::gpio::{Input, Level, Output, OutputDrive, Pull};
use embassy_time::Instant;
use openpatch_core::units::{AngleCounts, Millis, Pulses};
use openpatch_core::hal::{MotorDir, MotorFault};
use openpatch_core::interlock;
use openpatch_core::{Buzzer, Hal};

use crate::board;
use crate::config::*;
use crate::shared::*;

pub mod adc;
pub mod angle;
pub mod driver;
pub mod encoder;
pub mod stepper;
pub mod tmag;

use adc::Adc;
use angle::AngleSource;
use driver::Driver;
use stepper::Stepper;

/// TPL5010 DONE. Pulsed by `watchdog_kick` (safety task) only.
struct Done(Output<'static>);

/// Read `POWER.RESETREAS` and clear it (write 1 to clear). Must run before anything else touches the peripheral.
pub fn read_and_clear_resetreas() -> u32 {
    let r = embassy_nrf::pac::POWER.resetreas().read().0;
    embassy_nrf::pac::POWER.resetreas().write_value(embassy_nrf::pac::power::regs::Resetreas(0xFFFF_FFFF));
    r
}

/// RESETREAS (nRF52840: RESETPIN bit 0, DOG bit 1, SREQ bit 2, LOCKUP bit 3, OFF bit 16, ... ; a power-on reset reads 0) as
/// the cause the core reports (docs/06-diagnostics.md `7-74-002`). The TPL5010 resets the MCU through the RESET pin
/// (UICR PSELRESET = P0.18), so a RESETPIN reset on the bench board IS the external watchdog; the internal WDT is not used.
/// A soft reset (SREQ) is the commanded one (DFU, service). A cold power-up and a wake from System OFF are `PowerOn`.
pub fn classify_resetreas(bits: u32) -> openpatch_core::hal::ResetCause {
    use openpatch_core::hal::ResetCause;
    const RESETPIN: u32 = 1 << 0;
    const DOG: u32 = 1 << 1;
    const SREQ: u32 = 1 << 2;
    const LOCKUP: u32 = 1 << 3;
    if bits & LOCKUP != 0 {
        ResetCause::Lockup
    } else if bits & DOG != 0 || bits & RESETPIN != 0 {
        ResetCause::Watchdog
    } else if bits & SREQ != 0 {
        ResetCause::Commanded
    } else {
        ResetCause::PowerOn
    }
}

pub struct BenchHal {
    /// Reverse (draw) STCK period in PWM ticks; set from the fill needle gauge by `set_draw_rate_pps`.
    reverse_period_ticks: u16,
    stepper: Stepper,
    adc: Adc,
    drv: Driver,
    dock: Option<Input<'static>>,
    done: Option<Done>,
    last_peak_ma: Option<u16>,
    angle: AngleSource,
    /// Burst bookkeeping for diagnostics.
    bursts: u32,
}

impl BenchHal {
    pub fn new(
        stepper: Stepper,
        adc: Adc,
        angle: AngleSource,
        io_dir: BoardIoDriver,
        dock_n: Option<embassy_nrf::Peri<'static, embassy_nrf::gpio::AnyPin>>,
        wdt_done: Option<embassy_nrf::Peri<'static, embassy_nrf::gpio::AnyPin>>,
    ) -> Self {
        let drv = Driver::new(io_dir.dir, io_dir.mode1, io_dir.mode2, io_dir.stby, io_dir.en_fault, io_dir.interlock);
        // DONE is an output that idles low. WAKE is handled by `wake_task`.
        let done = wdt_done.map(|p| Done(Output::new(p, Level::Low, OutputDrive::Standard)));
        Self {
            reverse_period_ticks: REVERSE_PERIOD_TICKS,
            stepper,
            adc,
            drv,
            dock: dock_n.map(|p| Input::new(p, Pull::None)),
            done,
            last_peak_ma: None,
            angle,
            bursts: 0,
        }
    }

    /// Monotonic time for the safety task (same clock as `Hal::time_ms`).
    pub fn time_ms_now(&mut self) -> Millis {
        Millis(Instant::now().as_millis())
    }

    /// Interlock failure flag for the safety task (also published to the UI).
    pub fn interlock_failed(&self) -> bool {
        self.drv.failed
    }

    fn read_docked(&mut self) -> bool {
        match self.dock.as_ref() {
            Some(pin) => pin.is_low(), // DOCK_N active low
            None => DOCK_SIM.load(Ordering::Relaxed),
        }
    }
}

/// Driver related pins split out of `board::BoardIo` in `main`.
pub struct BoardIoDriver {
    pub dir: embassy_nrf::Peri<'static, embassy_nrf::gpio::AnyPin>,
    pub mode1: embassy_nrf::Peri<'static, embassy_nrf::gpio::AnyPin>,
    pub mode2: embassy_nrf::Peri<'static, embassy_nrf::gpio::AnyPin>,
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
        // Forward while undocked is a FAULT (the gate is open in hardware, nothing may be retried),
        // reverse while docked is refused too. Both cut the supply.
        let docked = self.read_docked();
        if let Err(r) = interlock::check_request(dir, docked) {
            defmt::error!("motor step refused: {}", r);
            self.drv.fault = Some(r.into());
            self.drv.power_off(&mut self.adc);
            INTERLOCK_FAILED.store(self.drv.failed, Ordering::Relaxed);
            return Pulses(0);
        }
        // DIR changes while powered (not the normal path: `motor_enable_dir` sets it first) are
        // checked against the gate model.
        if let Err(e) = self.drv.change_direction(&mut self.adc, docked, dir) {
            defmt::error!("direction change while powered failed: {}", e);
            self.drv.fault = Some(e.to_fault());
            INTERLOCK_FAILED.store(self.drv.failed, Ordering::Relaxed);
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
        let adc = &mut self.adc;
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
        if self.drv.fault_asserted() {
            // The STSPIN220 pulled EN/FAULT low (over-current / thermal): the power stage was off
            // for some or all of the burst. Report 0 pulses: the core latches INTERNAL / stops.
            defmt::error!("STSPIN220 EN/FAULT asserted during the burst: reporting 0 pulses");
            self.drv.fault = Some(MotorFault::Driver);
            return Pulses(0);
        }
        // The supply must still follow the gate (dock lost mid burst opens the gate in forward).
        let docked_now = self.read_docked();
        if let Err(e) = self.drv.verify_supply(&mut self.adc, docked_now) {
            defmt::error!("supply check after the burst failed: {}: reporting 0 pulses", e);
            self.drv.fault = Some(e.to_fault());
            INTERLOCK_FAILED.store(self.drv.failed, Ordering::Relaxed);
            return Pulses(0);
        }
        if burst.timed_out {
            self.drv.fault.get_or_insert(MotorFault::Timeout);
        }
        Pulses(executed)
    }

    /// DONE for a pending WAKE, only if the idle interlock verification passes.
    fn service_watchdog(&mut self) {
        let idle_ok = self.drv.verify_idle(&mut self.adc);
        INTERLOCK_FAILED.store(self.drv.failed, Ordering::Relaxed);
        if self.drv.failed || !idle_ok {
            return;
        }
        let Some(done) = self.done.as_mut() else { return };
        if WAKE_PENDING.swap(false, Ordering::AcqRel) {
            done.0.set_high();
            cortex_m::asm::delay(64 * 2); // >= 100 ns, about 2 us
            done.0.set_low();
        }
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
            self.drv.power_off(&mut self.adc);
            INTERLOCK_FAILED.store(self.drv.failed, Ordering::Relaxed);
        }
    }

    /// DIR is set BEFORE the supply is requested (`VMOT = MCU_EN AND latch AND (DOCKED OR DIR_REVERSE)`):
    /// a draw (undocked, reverse) only comes up this way; forward needs DOCKED.
    fn motor_enable_dir(&mut self, dir: MotorDir) {
        let docked = self.read_docked();
        self.drv.fault = None;
        if let Err(e) = self.drv.power_up(&mut self.adc, docked, dir) {
            defmt::error!("motor power-up refused: {}", e);
            self.drv.fault = Some(e.to_fault());
        }
        INTERLOCK_FAILED.store(self.drv.failed, Ordering::Relaxed);
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
        if self.drv.fault_asserted() {
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
        adc::divided_to_mv(self.adc.scan().vbus).min(u16::MAX as u32) as u16
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
}

/// Helper task: only records the TPL5010 WAKE edge. It never touches DONE.
#[embassy_executor::task]
pub async fn wake_task(mut wake: Input<'static>) -> ! {
    loop {
        wake.wait_for_rising_edge().await;
        WAKE_PENDING.store(true, Ordering::Release);
    }
}
