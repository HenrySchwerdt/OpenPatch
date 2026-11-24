//! `openpatch_core::Hal` for the cup pod v4 (`board-cup-v4`). TEST PROJECT, never worn, water only.
//!
//! Every decision is in the host tested `openpatch_core::cup_ctl::CupCtl` (power-up order, burst checks, idle verification,
//! capacity); this file only binds it to the GPIOs, the SAADC and the nRF52840 watchdog:
//!
//! * bridge: `APHASE`, `BPHASE`, `AENBL`, `BENBL` (2 x DRV8838) written in the order of `phase_drive::apply_in_safe_order`;
//! * gate: `MOT_FWD`, `MCU_EN` (read back), `ARM_CLK`; readbacks `LATCH_Q`, `SUP_OK`, `OC_OK`, `DOCK_N`;
//! * analog: `VMOT_SENSE` (AIN2, x 2) and the cell through `VDDHDIV5`;
//! * angle: the TMAG5273 (`hal::tmag`), polled every `ANGLE_POLL_MS` during a burst;
//! * watchdog: the nRF52840 WDT (the board's TPL5010 watches the SUPERVISOR, not the nRF). It is fed only from `watchdog_kick`
//!   after `CupCtl::idle_check` passed, and between the chunks of a long request: a hung safety task or a failed interlock lets
//!   it expire. TODO(verify-on-hardware): WDT timeout against the longest blocking path (a 64-step prime = 3 chunks with two arm
//!   waits, about 2.6 s), and whether the WDT keeps running across the soft reset of a DFU swap (the bootloader feeds it while
//!   it runs, `openpatch-bootloader` `KickFlash`).
//!
//! Steps are made by busy waiting on the safety executor (like the bench board's hardware step counter wait): a full burst is at most
//! 30 steps at 200 pps = 155 ms. A request larger than one planned burst (a prime) is split into bursts, each with its own arm
//! (the supervisor budget is per armed window); the periodic paths (basal, bolus, draw) ask `motor_capacity` first and never wait.
use core::sync::atomic::Ordering;
use embassy_futures::block_on;
use embassy_nrf::gpio::{AnyPin, Flex, Input, Level, Output, OutputDrive, Pull};
use embassy_nrf::saadc::{AnyInput, ChannelConfig, Config as AdcConfig, Resolution, Saadc, Time, VddhDiv5Input};
use embassy_nrf::wdt::WatchdogHandle;
use embassy_nrf::Peri;
use embassy_time::{block_for, Duration, Instant};
use openpatch_core::battery::vddhdiv5_to_mv;
use openpatch_core::cup_ctl::{CupBoard, CupCfg, CupCtl, CupRead, CupSense};
use openpatch_core::hal::{DiagEvent, InterlockReadback, MotorDir, MotorFault, SelfTestOutcome, SelfTestStep};
use openpatch_core::phase_drive::{apply_in_safe_order, PhaseLevels, PhasePins, StepTimer};
use openpatch_core::units::{AngleCounts, Millis, Pulses};
use openpatch_core::{Buzzer, Hal};

use super::angle::AngleSource;
use crate::board::{CupIo, DOCK_ACTIVE_LOW, MOT_FWD_FORWARD_HIGH};
use crate::config::*;
use crate::irqs::Irqs;
use crate::shared::*;

/// SAADC: `VMOT_SENSE` and `VDDHDIV5`, 12 bit, gain 1/6, internal reference (3.6 V full scale).
pub struct CupAdc {
    saadc: Saadc<'static, 2>,
}

impl CupAdc {
    pub async fn new(saadc: Peri<'static, embassy_nrf::peripherals::SAADC>, vmot: AnyInput<'static>) -> Self {
        let mut cfg = AdcConfig::default();
        cfg.resolution = Resolution::_12bit;
        let mut v = ChannelConfig::single_ended(vmot);
        v.time = Time::_40US; // 100 k / 100 k divider
        let mut b = ChannelConfig::single_ended(VddhDiv5Input);
        b.time = Time::_40US;
        let adc = Saadc::new(saadc, Irqs, cfg, [v, b]);
        adc.calibrate().await;
        Self { saadc: adc }
    }
    /// `(VMOT mV, VBAT mV)`; a negative raw value reads 0.
    pub fn scan(&mut self) -> (u16, u16) {
        let mut buf = [0i16; 2];
        block_on(self.saadc.sample(&mut buf));
        let vmot = (buf[0].max(0) as u32 * ADC_FULL_SCALE_MV / ADC_COUNTS * DIVIDER_RATIO).min(u16::MAX as u32) as u16;
        let vbat = vddhdiv5_to_mv(buf[1] as i32, 12).unwrap_or(0);
        (vmot, vbat)
    }
}

/// The four driver inputs.
pub struct Bridge {
    aphase: Output<'static>,
    bphase: Output<'static>,
    aenbl: Output<'static>,
    benbl: Output<'static>,
    last: PhaseLevels,
}

impl PhasePins for Bridge {
    fn apply(&mut self, to: PhaseLevels) {
        let from = self.last;
        let phase = core::cell::RefCell::new((&mut self.aphase, &mut self.bphase));
        let enable = core::cell::RefCell::new((&mut self.aenbl, &mut self.benbl));
        apply_in_safe_order(
            from,
            to,
            |a, b| {
                let mut p = phase.borrow_mut();
                p.0.set_level(Level::from(a));
                p.1.set_level(Level::from(b));
            },
            |a, b| {
                let mut e = enable.borrow_mut();
                e.0.set_level(Level::from(a));
                e.1.set_level(Level::from(b));
            },
        );
        self.last = to;
    }
}

pub struct BusyDelay;
impl StepTimer for BusyDelay {
    fn delay_us(&mut self, us: u32) {
        block_for(Duration::from_micros(us as u64));
    }
}

/// Gate outputs, readbacks, analog and the angle sensor.
pub struct Sense {
    mot_fwd: Output<'static>,
    mcu_en: Flex<'static>,
    arm_clk: Output<'static>,
    latch_q: Input<'static>,
    sup_ok: Input<'static>,
    oc_ok: Input<'static>,
    dock_n: Input<'static>,
    adc: CupAdc,
    angle: AngleSource,
    last_poll: Instant,
}

impl CupSense for Sense {
    fn set_mot_fwd(&mut self, forward: bool) {
        self.mot_fwd.set_level(Level::from(forward == MOT_FWD_FORWARD_HIGH));
    }
    fn set_mcu_en(&mut self, high: bool) {
        self.mcu_en.set_level(Level::from(high));
    }
    fn arm_edge(&mut self) {
        self.arm_clk.set_high();
        block_for(Duration::from_micros(10));
        self.arm_clk.set_low();
    }
    fn read(&mut self) -> CupRead {
        CupRead {
            latch_q: self.latch_q.is_high(),
            sup_ok: self.sup_ok.is_high(),
            oc_ok: self.oc_ok.is_high(),
            docked: self.dock_n.is_low() == DOCK_ACTIVE_LOW,
            mcu_en: self.mcu_en.is_high(),
        }
    }
    fn vmot_mv(&mut self) -> Option<u16> {
        Some(self.adc.scan().0)
    }
    fn vbat_mv(&mut self) -> Option<u16> {
        Some(self.adc.scan().1)
    }
    fn now_ms(&mut self) -> u64 {
        Instant::now().as_millis()
    }
    fn charger_present(&mut self) -> bool {
        usb_detected()
    }
    fn on_step(&mut self) {
        if Instant::now() - self.last_poll >= Duration::from_millis(ANGLE_POLL_MS) {
            self.last_poll = Instant::now();
            self.angle.poll();
        }
    }
}

/// `POWER.USBREGSTATUS.VBUSDETECT`: a USB cable is connected (`VBUS_P` on the module).
pub fn usb_detected() -> bool {
    embassy_nrf::pac::POWER.usbregstatus().read().vbusdetect()
}

pub struct CupParts {
    bridge: Bridge,
    delay: BusyDelay,
    sense: Sense,
}

impl CupBoard for CupParts {
    type Phase = Bridge;
    type Timer = BusyDelay;
    type Sense = Sense;
    fn parts(&mut self) -> (&mut Bridge, &mut BusyDelay, &mut Sense) {
        (&mut self.bridge, &mut self.delay, &mut self.sense)
    }
}

pub struct CupHal {
    ctl: CupCtl<CupParts>,
    fault: Option<MotorFault>,
    dir: MotorDir,
    wdt: Option<WatchdogHandle>,
}

/// The board pins the HAL owns (split out of `board::CupIo` in `main`).
pub struct CupHalPins {
    pub vmot_sense: AnyInput<'static>,
    pub aphase: Peri<'static, AnyPin>,
    pub bphase: Peri<'static, AnyPin>,
    pub aenbl: Peri<'static, AnyPin>,
    pub benbl: Peri<'static, AnyPin>,
    pub mot_fwd: Peri<'static, AnyPin>,
    pub mcu_en: Peri<'static, AnyPin>,
    pub arm_clk: Peri<'static, AnyPin>,
    pub latch_q: Peri<'static, AnyPin>,
    pub sup_ok: Peri<'static, AnyPin>,
    pub oc_ok: Peri<'static, AnyPin>,
    pub dock_n: Peri<'static, AnyPin>,
    /// TMAG5273 (angle), I2C 100 kHz.
    pub i2c_scl: Peri<'static, AnyPin>,
    pub i2c_sda: Peri<'static, AnyPin>,
}

impl CupHalPins {
    /// Takes the HAL's pins out of `io`; the remaining fields (LED, button, buzzer, supervisor UART / straps, charger status)
    /// stay with the caller.
    pub fn split(io: CupIo) -> (CupHalPins, CupRest) {
        (
            CupHalPins {
                vmot_sense: io.vmot_sense,
                aphase: io.aphase,
                bphase: io.bphase,
                aenbl: io.aenbl,
                benbl: io.benbl,
                mot_fwd: io.mot_fwd,
                mcu_en: io.mcu_en,
                arm_clk: io.arm_clk,
                latch_q: io.latch_q,
                sup_ok: io.sup_ok,
                oc_ok: io.oc_ok,
                dock_n: io.dock_n,
                i2c_scl: io.i2c_scl,
                i2c_sda: io.i2c_sda,
            },
            CupRest {
                chg_stat: io.chg_stat,
                led_r: io.led_r,
                led_g: io.led_g,
                led_b: io.led_b,
                sup_rx: io.sup_rx,
                sup_tx: io.sup_tx,
                sup_boot0: io.sup_boot0,
                sup_nrst: io.sup_nrst,
                button: io.button,
                buz_a: io.buz_a,
            },
        )
    }
}

/// Everything of `CupIo` the HAL does not own.
pub struct CupRest {
    pub chg_stat: Peri<'static, AnyPin>,
    pub led_r: Peri<'static, AnyPin>,
    pub led_g: Peri<'static, AnyPin>,
    pub led_b: Peri<'static, AnyPin>,
    pub sup_rx: Peri<'static, AnyPin>,
    pub sup_tx: Peri<'static, AnyPin>,
    pub sup_boot0: Peri<'static, AnyPin>,
    pub sup_nrst: Peri<'static, AnyPin>,
    pub button: Peri<'static, AnyPin>,
    pub buz_a: Peri<'static, AnyPin>,
}

impl CupHal {
    /// All outputs start in the safe state (bridges braked, `MCU_EN` low, `ARM_CLK` low, `MOT_FWD` forward = reset default).
    pub async fn new(
        p: CupHalPins,
        saadc: Peri<'static, embassy_nrf::peripherals::SAADC>,
        twi: Peri<'static, embassy_nrf::peripherals::TWISPI0>,
    ) -> Self {
        let adc = CupAdc::new(saadc, p.vmot_sense).await;
        // no sensor: `angle_read` returns None and the core refuses to deliver
        let angle = match super::tmag::Tmag::init(twi, p.i2c_sda, p.i2c_scl).await {
            Some(sensor) => AngleSource::Tmag { sensor, tracker: Default::default() },
            None => AngleSource::Missing,
        };
        let out = |pin, level| Output::new(pin, level, OutputDrive::Standard);
        let mut mcu_en = Flex::new(p.mcu_en);
        mcu_en.set_low();
        mcu_en.set_as_input_output(Pull::None, OutputDrive::Standard); // input buffer on: own-pin readback
        let parts = CupParts {
            bridge: Bridge {
                aphase: out(p.aphase, Level::Low),
                bphase: out(p.bphase, Level::Low),
                aenbl: out(p.aenbl, Level::Low),
                benbl: out(p.benbl, Level::Low),
                last: PhaseLevels::RESET,
            },
            delay: BusyDelay,
            sense: Sense {
                mot_fwd: out(p.mot_fwd, Level::from(MOT_FWD_FORWARD_HIGH)),
                mcu_en,
                arm_clk: out(p.arm_clk, Level::Low),
                latch_q: Input::new(p.latch_q, Pull::None),
                sup_ok: Input::new(p.sup_ok, Pull::None),
                oc_ok: Input::new(p.oc_ok, Pull::None),
                dock_n: Input::new(p.dock_n, Pull::None),
                adc,
                angle,
                last_poll: Instant::now(),
            },
        };
        Self { ctl: CupCtl::new(parts, CupCfg::DEFAULT), fault: None, dir: MotorDir::Forward, wdt: None }
    }

    /// The watchdog handle, fed only after a verified tick.
    pub fn set_watchdog(&mut self, h: WatchdogHandle) {
        self.wdt = Some(h);
    }

    /// Passive check at boot (supply cut, `MCU_EN` low): findings are queued for the core's first tick.
    pub fn boot_check(&mut self) {
        let ok = self.ctl.idle_check();
        INTERLOCK_FAILED.store(self.ctl.failed(), Ordering::Relaxed);
        defmt::info!("cup boot check: {}", if ok { "clean" } else { "findings queued" });
    }

    pub fn time_ms_now(&mut self) -> Millis {
        Millis(Instant::now().as_millis())
    }

    pub fn interlock_failed(&self) -> bool {
        self.ctl.failed()
    }

    fn sense(&mut self) -> &mut Sense {
        self.ctl.board_mut().parts().2
    }

    fn feed(&mut self) {
        if let Some(h) = self.wdt.as_mut() {
            h.pet();
        }
    }

    /// One request, split into planned bursts with their own arm each. Honest count of the steps made.
    fn run(&mut self, steps: Pulses, dir: MotorDir) -> Pulses {
        let max = if dir == MotorDir::Forward { MAX_BURST_STEPS } else { MAX_REVERSE_BURST_STEPS };
        if steps.0 == 0 || steps.0 > max {
            defmt::warn!("motor step({}) outside 1..={}: refused", steps.0, max);
            self.fault.get_or_insert(MotorFault::Timeout);
            return Pulses(0);
        }
        let mut left = steps.0;
        let mut made_total = 0;
        while left > 0 {
            let chunk = left.min(self.ctl.plan_steps(dir).unwrap_or(1).max(1));
            let docked = self.sense().read().docked;
            if let Err(f) = self.ctl.power_up(docked, dir) {
                defmt::error!("cup power-up refused: {}", f);
                self.fault = Some(f);
                break;
            }
            let made = self.ctl.burst(chunk);
            self.ctl.power_off();
            made_total += made;
            left -= made.min(left);
            if made < chunk {
                self.fault = self.ctl.take_fault().or(Some(MotorFault::Timeout));
                defmt::error!("cup burst short: {} of {} ({})", made, chunk, self.fault);
                break;
            }
            if left > 0 && !self.ctl.failed() {
                self.feed(); // the burst itself was verified step by step
            }
        }
        self.sense().angle.poll();
        INTERLOCK_FAILED.store(self.ctl.failed(), Ordering::Relaxed);
        Pulses(made_total)
    }
}

impl Hal for CupHal {
    fn motor_step(&mut self, steps: Pulses) -> Pulses {
        self.run(steps, MotorDir::Forward)
    }
    fn motor_step_reverse(&mut self, steps: Pulses) -> Pulses {
        self.run(steps, MotorDir::Reverse)
    }
    fn set_draw_rate_pps(&mut self, pps: u32) {
        self.ctl.set_reverse_pps(pps.min(REVERSE_RATE_MAX_HZ));
    }
    fn motor_capacity(&mut self, dir: MotorDir) -> Option<u32> {
        Some(self.ctl.capacity(dir))
    }
    /// The supply is requested per burst inside `motor_step` (each burst needs its own arm): only the intent is kept here.
    fn motor_enable_dir(&mut self, dir: MotorDir) {
        self.dir = dir;
        self.fault = None;
    }
    fn motor_enable(&mut self, enable: bool) {
        if enable {
            self.motor_enable_dir(MotorDir::Forward);
        } else if self.ctl.is_powered() {
            self.ctl.power_off();
        }
    }
    fn motor_fault(&mut self) -> Option<MotorFault> {
        self.fault.take().or_else(|| self.ctl.take_fault())
    }
    fn angle_read(&mut self) -> Option<AngleCounts> {
        self.sense().angle.read().map(AngleCounts)
    }
    /// Feeds the nRF watchdog only if the idle verification passes (supply cut, `MCU_EN` low, no latched failure).
    fn watchdog_kick(&mut self) {
        let ok = self.ctl.idle_check();
        INTERLOCK_FAILED.store(self.ctl.failed(), Ordering::Relaxed);
        if ok {
            self.feed();
        }
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
    /// The cell itself (`VDDHDIV5`), at rest when no burst runs.
    fn battery_mv(&mut self) -> u16 {
        let mv = self.sense().adc.scan().1;
        VBAT_MV.store(mv, Ordering::Relaxed);
        mv
    }
    fn time_ms(&mut self) -> Millis {
        Millis(Instant::now().as_millis())
    }
    fn docked(&mut self) -> bool {
        self.sense().read().docked
    }
    fn charger_present(&mut self) -> bool {
        usb_detected()
    }
    fn take_diag(&mut self) -> Option<DiagEvent> {
        self.ctl.take_event()
    }
    fn interlock_state(&mut self) -> Option<InterlockReadback> {
        Some(self.ctl.readback())
    }
    /// The POST proofs of the bench board (gate cut, dock gate, over-current leg) need pins this board does not have
    /// (`DOCK_TEST`, `OC_TEST`, `LATCH_CLR_N`): UNKNOWN, never OK. Cup POST proofs are an open item (docs/board-cup-v4.md).
    fn selftest(&mut self, _step: SelfTestStep) -> SelfTestOutcome {
        SelfTestOutcome::Unsupported
    }
    fn reset_cause(&mut self) -> openpatch_core::hal::ResetCause {
        super::classify_resetreas(RESET_REASON.load(Ordering::Relaxed))
    }
}
