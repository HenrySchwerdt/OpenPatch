//! Cup pod v4 bring-up firmware (`--features board-cup-v4`, `cargo check --bin cup_bringup --no-default-features --features board-cup-v4`).
//! TEST PROJECT, never worn. WATER ONLY, bench, no insulin or other drug in the pump, ever.
//!
//! It exercises the new board with the host-tested core pieces and nothing else (no BLE, no pump logic):
//!
//! 1. UICR: `REGOUT0` = 3.3 V (HV mode, no LDO), `PSELRESET`; reset once after the first write;
//! 2. battery voltage from the SAADC `VDDHDIV5` channel (`openpatch_core::battery::vddhdiv5_to_mv`), logged and shown on the LED
//!    (`openpatch_core::led`: charging pulse, full = green, low = red);
//! 3. on a button press, ONE burst of the DRV8835 full-step sequence (`openpatch_core::phase_drive`) planned by
//!    `openpatch_core::burst::plan_burst` for the cell's peak current, through the hardware gate:
//!    `MOT_FWD` first, `ARM_CLK` edge, `MCU_EN` high, wait, burst, `MCU_EN` low, `MOT_FWD` back to forward. The direction follows the dock
//!    hall (docked = forward, undocked = reverse): the hardware gate is "docked XOR reverse". The burst aborts when `SUP_OK` drops.
//!
//! The firmware cannot move the motor on its own: the supply needs the latch, the supervisor permit AND `MCU_EN` in hardware.
#![no_std]
#![no_main]

#[allow(dead_code)]
#[path = "../board/cup_v4.rs"]
mod cup_v4;

use defmt_rtt as _;
use panic_probe as _;

use embassy_executor::Spawner;
use embassy_nrf::bind_interrupts;
use embassy_nrf::gpio::{Input, Level, Output, OutputDrive, Pull};
use embassy_nrf::saadc::{self, ChannelConfig, Config as AdcConfig, Resolution, Saadc, Time, VddhDiv5Input};
use embassy_time::{block_for, Duration, Instant, Timer};

use openpatch_core::battery::{vddhdiv5_to_mv, MOTOR_MIN_VBAT_MV};
use openpatch_core::burst::{plan_burst, CellParams, MotorLoad};
use openpatch_core::hal::MotorDir;
use openpatch_core::led::{Charger, LedInputs, LedState, Rgb};
use openpatch_core::phase_drive::{apply_in_safe_order, drive_burst, PhaseLevels, PhasePins, PhaseStepper, StepTimer};

/// Single core critical section (the pump application gets it from nrf-mpsl; this bring-up binary has no radio stack).
struct Cs;
critical_section::set_impl!(Cs);
// SAFETY: single core Cortex-M4; interrupts are masked for the section and the previous PRIMASK state is restored.
unsafe impl critical_section::Impl for Cs {
    unsafe fn acquire() -> critical_section::RawRestoreState {
        let was_active = cortex_m::register::primask::read().is_active();
        cortex_m::interrupt::disable();
        was_active
    }
    unsafe fn release(was_active: critical_section::RawRestoreState) {
        if was_active {
            cortex_m::interrupt::enable();
        }
    }
}

bind_interrupts!(struct Irqs {
    SAADC => saadc::InterruptHandler;
});

/// 200 pps full steps.
const STEP_PERIOD_US: u32 = 5_000;
/// The supervisor's budget per armed window.
const SUP_BUDGET_STEPS: u32 = 32;

/// The four DRV8835 inputs on the GPIOs. Written in the safe order of `phase_drive::apply_in_safe_order`.
struct Bridge {
    aphase: Output<'static>,
    bphase: Output<'static>,
    aenbl: Output<'static>,
    benbl: Output<'static>,
    sup_ok: Input<'static>,
    last: PhaseLevels,
}

impl PhasePins for Bridge {
    fn apply(&mut self, to: PhaseLevels) {
        let from = self.last;
        let (ap, bp, ae, be) = (&mut self.aphase, &mut self.bphase, &mut self.aenbl, &mut self.benbl);
        // two raw writers over disjoint pins, ordered by `apply_in_safe_order`
        let phase = core::cell::RefCell::new((ap, bp));
        let enable = core::cell::RefCell::new((ae, be));
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

struct Delay;
impl StepTimer for Delay {
    fn delay_us(&mut self, us: u32) {
        block_for(Duration::from_micros(us as u64));
    }
}

/// Software PWM of the three LED channels (active low), 10 slots of 1 ms: a bring-up convenience; the production firmware uses the
/// PWM peripheral and switches it off when the LED is dark.
struct Led {
    r: Output<'static>,
    g: Output<'static>,
    b: Output<'static>,
}

impl Led {
    fn show(&mut self, c: Rgb, slot: u8) {
        let on = |pct: u8| slot < (pct as u16 * 10 / 100) as u8 + (pct > 0 && (pct as u16 * 10 / 100) == 0) as u8;
        // active low: the pin is LOW while the channel is lit
        self.r.set_level(Level::from(!on(c.r)));
        self.g.set_level(Level::from(!on(c.g)));
        self.b.set_level(Level::from(!on(c.b)));
    }
}

#[embassy_executor::main]
async fn main(_spawner: Spawner) {
    // UICR first: REGOUT0 = 3.3 V. Without it the 3V3 rail stays at the 1.8 V default and nothing on the board works.
    cup_v4::regout0_setup();

    let mut cfg = embassy_nrf::config::Config::default();
    // no 32 kHz crystal on the HJ-840 board: internal RC
    cfg.lfclk_source = embassy_nrf::config::LfclkSource::InternalRC;
    let p = embassy_nrf::init(cfg);
    let io = cup_v4::take(p);

    // Outputs: everything that can permit motion starts LOW / braked (the board pull-downs agree).
    let mut mot_fwd = Output::new(io.mot_fwd, Level::from(cup_v4::MOT_FWD_FORWARD_HIGH), OutputDrive::Standard);
    let mut arm_clk = Output::new(io.arm_clk, Level::Low, OutputDrive::Standard);
    let mut mcu_en = Output::new(io.mcu_en, Level::Low, OutputDrive::Standard);
    let mut bridge = Bridge {
        aphase: Output::new(io.aphase, Level::Low, OutputDrive::Standard),
        bphase: Output::new(io.bphase, Level::Low, OutputDrive::Standard),
        aenbl: Output::new(io.aenbl, Level::Low, OutputDrive::Standard),
        benbl: Output::new(io.benbl, Level::Low, OutputDrive::Standard),
        sup_ok: Input::new(io.sup_ok, Pull::None),
        last: PhaseLevels::RESET,
    };
    // SUP_NRST: open drain only, released (never driven high)
    let _sup_nrst = Output::new(io.sup_nrst, Level::High, OutputDrive::Standard0Disconnect1);
    let _sup_boot0 = Output::new(io.sup_boot0, Level::Low, OutputDrive::Standard);
    let dock_n = Input::new(io.dock_n, Pull::None);
    let chg_stat = Input::new(io.chg_stat, Pull::None);
    let button = Input::new(io.button, Pull::Up);
    let mut led = Led {
        r: Output::new(io.led_r, Level::High, OutputDrive::Standard),
        g: Output::new(io.led_g, Level::High, OutputDrive::Standard),
        b: Output::new(io.led_b, Level::High, OutputDrive::Standard),
    };

    // SAADC: VDDHDIV5 (cell), 12 bit, internal reference, gain 1/6 (3.6 V full scale = 18 V of VDDH)
    let mut acfg = AdcConfig::default();
    acfg.resolution = Resolution::_12bit;
    let mut ch = ChannelConfig::single_ended(VddhDiv5Input);
    ch.time = Time::_40US;
    let mut adc = Saadc::new(io.saadc, Irqs, acfg, [ch]);
    adc.calibrate().await;

    defmt::info!("cup-v4 bring-up: REGOUT0 ok, board {}", cup_v4::BOARD_NAME);

    let mut ledsm = LedState::new();
    let mut slot = 0u8;
    let mut last_battery = Instant::now() - Duration::from_secs(60);
    let mut vbat_mv: u16 = 0;
    let mut was_pressed = false;
    loop {
        let now = Instant::now();
        if now - last_battery >= Duration::from_secs(10) || vbat_mv == 0 {
            let mut buf = [0i16; 1];
            adc.sample(&mut buf).await;
            vbat_mv = vddhdiv5_to_mv(buf[0] as i32, 12).unwrap_or(0);
            last_battery = now;
            defmt::info!("battery {} mV (motor start limit {} mV)", vbat_mv, MOTOR_MIN_VBAT_MV);
        }
        let pressed = button.is_low();
        // USBDETECTED is read from the POWER peripheral in the full firmware; this bring-up treats STAT low as "charging" only
        let charger = if chg_stat.is_low() { Charger::Charging } else { Charger::None };
        let inputs = LedInputs { fault: false, charger, vbat_mv, button_pressed: pressed && !was_pressed };
        let colour = ledsm.update(now.as_millis(), &inputs);
        led.show(colour, slot);
        slot = (slot + 1) % 10;

        if pressed && !was_pressed {
            run_one_burst(&dock_n, &mut mot_fwd, &mut arm_clk, &mut mcu_en, &mut bridge, vbat_mv).await;
        }
        was_pressed = pressed;
        Timer::after(Duration::from_millis(1)).await;
    }
}

/// One planned burst through the hardware gate. Water only.
async fn run_one_burst(
    dock_n: &Input<'static>,
    mot_fwd: &mut Output<'static>,
    arm_clk: &mut Output<'static>,
    mcu_en: &mut Output<'static>,
    bridge: &mut Bridge,
    vbat_mv: u16,
) {
    let docked = dock_n.is_low() == cup_v4::DOCK_ACTIVE_LOW;
    // docked -> forward (the delivery direction), undocked -> reverse (retract): the gate is "docked XOR reverse"
    let dir = if docked { MotorDir::Forward } else { MotorDir::Reverse };
    let plan = match plan_burst(CellParams::AMPUL_301030, MotorLoad::NFP_608_26_45, vbat_mv, STEP_PERIOD_US, SUP_BUDGET_STEPS) {
        Ok(p) => p,
        Err(e) => {
            defmt::warn!("no burst: {}", defmt::Debug2Format(&e));
            return;
        }
    };
    // 1. direction FIRST (it is part of the hardware gate), 2. arm edge, 3. MCU_EN
    mot_fwd.set_level(Level::from(matches!(dir, MotorDir::Forward) == cup_v4::MOT_FWD_FORWARD_HIGH));
    block_for(Duration::from_micros(100));
    arm_clk.set_high();
    block_for(Duration::from_micros(10));
    arm_clk.set_low();
    mcu_en.set_high();
    block_for(Duration::from_millis(10)); // the supply switch and the boost start
    let mut st = PhaseStepper::new();
    let mut delay = Delay;
    let (made, why) = {
        // keep_going reads SUP_OK through a raw pointer-free copy: the bridge is borrowed mutably by the driver, so sample before
        let ok = bridge.sup_ok.is_high();
        drive_burst(&mut st, bridge, &mut delay, dir, plan.steps, STEP_PERIOD_US, |_| ok)
    };
    // power down: MCU_EN first, direction back to forward only after
    mcu_en.set_low();
    block_for(Duration::from_millis(20));
    mot_fwd.set_level(Level::from(cup_v4::MOT_FWD_FORWARD_HIGH));
    defmt::info!("burst: {} of {} steps ({}), rest {} ms", made, plan.steps, defmt::Debug2Format(&why), plan.rest_ms);
    Timer::after(Duration::from_millis(plan.rest_ms as u64)).await;
}
