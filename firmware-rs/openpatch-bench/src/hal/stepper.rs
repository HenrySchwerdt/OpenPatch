//! STSPIN220 step clock generation with hardware timing.
//!
//! * PWM1 plays a one value sequence `N` times: every PWM period is one STCK pulse (rising edge in
//!   the middle of the period, normal polarity). No CPU involvement per step.
//! * PPI ch0: PWM `PWMPERIODEND` -> TIMER1 `COUNT` (TIMER1 in counter mode): independent count of
//!   the periods the hardware really produced. The burst returns this count, not `N`.
//! * PPI ch1: PWM `LOOPSDONE` -> PWM `STOP`: the generator stops by itself after the last period,
//!   even if the CPU were stalled (a flash erase can stall it for 85 ms) or hung. Without this the
//!   PWM would keep repeating the last value.
//!
//! `PWMPERIODEND` counts periods, not pad edges: it proves the PWM ran `N` periods, not that the
//! STSPIN220 followed. The pad itself is verified by the spindle encoder (QDEC) and the motor
//! current peak, both are separate paths in the core's supervisor.
use embassy_nrf::gpio::{AnyPin, Level, OutputDrive};
use embassy_nrf::peripherals::{PWM1, TIMER1};
use embassy_nrf::ppi::{AnyConfigurableChannel, Ppi};
use embassy_nrf::pwm::{
    Config, Prescaler, SequenceConfig, SequenceLoad, SequencePwm, SingleSequenceMode, SingleSequencer,
};
use embassy_nrf::timer::Timer;
use embassy_nrf::Peri;
use embassy_time::{Duration, Instant};

use crate::config::*;

pub struct Stepper {
    pwm: SequencePwm<'static>,
    /// One word in RAM (EasyDMA source): the compare value = 50 % duty.
    words: [u16; 1],
    counter: Timer<'static>,
    _ppi_count: Ppi<'static, AnyConfigurableChannel, 1, 1>,
    _ppi_stop: Ppi<'static, AnyConfigurableChannel, 1, 1>,
}

/// Result of one burst.
#[derive(Clone, Copy, Debug, defmt::Format)]
pub struct Burst {
    /// Periods counted by the hardware counter.
    pub counted: u32,
    /// The burst ended by timeout (hardware did not finish in time): counted < requested.
    pub timed_out: bool,
}

impl Stepper {
    pub fn new(
        pwm: Peri<'static, PWM1>,
        stck: Peri<'static, AnyPin>,
        timer: Peri<'static, TIMER1>,
        ppi_a: Peri<'static, AnyConfigurableChannel>,
        ppi_b: Peri<'static, AnyConfigurableChannel>,
    ) -> Self {
        let mut cfg = Config::default();
        cfg.prescaler = Prescaler::Div16; // 16 MHz / 16 = 1 MHz
        cfg.max_duty = STEP_PWM_PERIOD_TICKS;
        cfg.sequence_load = SequenceLoad::Common;
        cfg.ch0_drive = OutputDrive::Standard;
        cfg.ch0_idle_level = Level::Low; // STCK idle low (also required while MODE pins are latched)
        let pwm = match SequencePwm::new_1ch(pwm, stck, cfg) {
            Ok(p) => p,
            Err(_) => defmt::panic!("step PWM init"),
        };

        let counter = Timer::new_counter(timer);
        counter.clear();
        counter.start(); // counter mode: counts COUNT tasks while started; never stopped

        let ppi_count = Ppi::new_one_to_one(ppi_a, pwm.event_pwm_period_end(), counter.task_count());
        // SAFETY: `task_stop` is only unsafe because stopping a running sequence leaves the PWM in an
        // unknown sequence state; that is exactly intended here (the playback is over, and
        // `Stepper::burst` re-initialises the sequencer on every start).
        let stop_task = unsafe { pwm.task_stop() };
        let ppi_stop = Ppi::new_one_to_one(ppi_b, pwm.event_loops_done(), stop_task);
        let mut s = Self {
            pwm,
            words: [STEP_PWM_DUTY_TICKS],
            counter,
            _ppi_count: ppi_count,
            _ppi_stop: ppi_stop,
        };
        s._ppi_count.enable();
        s._ppi_stop.enable();
        s
    }

    /// Emit exactly `steps` STCK pulses. Blocks until the hardware counter reached `steps` (or the
    /// timeout expired). `poll` is called between counter reads (ADC sampling of the motor current).
    pub fn burst(&mut self, steps: u32, period_ticks: u16, mut poll: impl FnMut()) -> Burst {
        debug_assert!(steps >= 1 && steps <= u16::MAX as u32);
        self.counter.clear();
        // Period of this burst (forward `STEP_PWM_PERIOD_TICKS`, reverse `REVERSE_PERIOD_TICKS`).
        // The PWM is disabled here, so changing COUNTERTOP is safe.
        embassy_nrf::pac::PWM1.countertop().write(|w| w.set_countertop(period_ticks));
        self.words[0] = period_ticks / 2;
        let rate_hz = STEP_PWM_CLK_HZ / period_ticks as u32;
        let budget = Duration::from_micros(steps as u64 * 1_000_000 / rate_hz as u64)
            + Duration::from_millis(BURST_TIMEOUT_MARGIN_MS);
        let started = Instant::now();
        let mut counted;
        let mut timed_out = false;
        {
            let seq = SingleSequencer::new(&mut self.pwm, &self.words, SequenceConfig::default());
            if seq.start(SingleSequenceMode::Times(steps as u16)).is_err() {
                return Burst { counted: 0, timed_out: true };
            }
            loop {
                poll();
                counted = self.counter.cc(0).capture();
                if counted >= steps {
                    break;
                }
                if Instant::now() - started > budget {
                    timed_out = true;
                    break;
                }
            }
            // `seq` drops here: Sequencer::stop() = STOP task + PWM disabled, pin back to GPIO idle (low).
        }
        // Final read after the stop (the last period end may have arrived between read and stop).
        counted = self.counter.cc(0).capture();
        Burst { counted, timed_out }
    }
}
