//! STSPIN220 control and the hardware interlock, bench controller board. The decisions (power-up plan, rotating
//! single-gate disarm, readback classification, POST) live in `openpatch_core::bench_ctl` and are host tested; this file
//! only binds the controller to the pins ([`EmbassyPins`]).
//!
//! `MOT_ALLOW = MCU_EN AND LATCH_Q AND OC_OK AND (DOCKED_H OR DIR_REV)` (INTERLOCK.md). DIR is part of the gate: the plan
//! always sets it first, and it returns to forward only after the supply is verified cut. Power-down rotates the cutting
//! gate (MCU_EN only, LATCH_CLR_N only, both) and verifies the collapse; STBY is low whenever the driver is idle (the
//! motor would dissipate about 1.4 W at 160 mA in both phases).
//!
//! Board without the interlock (DK): the controller runs with `CtlCfg::NO_INTERLOCK` (direction, STBY, EN/FAULT only).
use core::sync::atomic::Ordering;
use embassy_nrf::gpio::{AnyPin, Flex, Input, Level, Output, OutputDrive, Pull};
use embassy_nrf::Peri;
use embassy_time::{block_for, Duration, Instant};
use openpatch_core::bench_ctl::{BenchCtl, BenchPins, CtlCfg, PinRead};

use super::adc::{divided_to_mv, raw_to_mv, Adc};
use crate::board::{InterlockPins, HAS_INTERLOCK, HAS_MOTOR_DRIVER};
use crate::config::*;
use crate::shared::TMAG_PRESENT;

/// The interlock pins (E73 bench board only).
struct IlPins {
    arm_clk: Flex<'static>,
    latch_clr_n: Flex<'static>,
    mcu_en: Flex<'static>,
    latch_q: Input<'static>,
    oc_ok: Input<'static>,
    pgate_mon: Input<'static>,
    dir_rev: Input<'static>,
    docked_h: Input<'static>,
    dock_test: Output<'static>,
    oc_test: Output<'static>,
    pod_id_n: Input<'static>,
}

/// `BenchPins` over the embassy GPIO and the SAADC.
pub struct EmbassyPins {
    pub adc: Adc,
    dir: Output<'static>,
    stby: Flex<'static>,
    en_fault: Flex<'static>,
    il: Option<IlPins>,
    /// DOCK_N (pod dock hall, low = docked); `None` on boards that simulate DOCKED.
    pub dock_n: Option<Input<'static>>,
    /// Keeps WDT_DONE configured as an output, idle low. The pulse itself is issued by the WAKE interrupt (`hal::wdt`).
    _done: Option<Output<'static>>,
}

fn flex_out(pin: Peri<'static, AnyPin>, level: Level, drive: OutputDrive) -> Flex<'static> {
    let mut f = Flex::new(pin);
    if level == Level::High {
        f.set_high();
    } else {
        f.set_low();
    }
    // input buffer connected while driven: the own-pin readback of the diagnostics (RB9)
    f.set_as_input_output(Pull::None, drive);
    f
}

impl BenchPins for EmbassyPins {
    fn set_mot_dir(&mut self, high: bool) {
        self.dir.set_level(Level::from(high));
    }
    fn set_mcu_en(&mut self, high: bool) {
        if let Some(il) = self.il.as_mut() {
            il.mcu_en.set_level(Level::from(high));
        }
    }
    fn arm_edge(&mut self) {
        if let Some(il) = self.il.as_mut() {
            il.arm_clk.set_high(); // rising edge = ARM
            cortex_m::asm::delay(64 * 5);
            il.arm_clk.set_low();
        }
    }
    fn set_latch_clear(&mut self, asserted: bool) {
        if let Some(il) = self.il.as_mut() {
            // open drain: low clears the latch, "high" releases the line (board pull-up). Never driven high.
            il.latch_clr_n.set_level(Level::from(!asserted));
        }
    }
    fn set_dock_test(&mut self, on: bool) {
        if let Some(il) = self.il.as_mut() {
            il.dock_test.set_level(Level::from(on));
        }
    }
    fn set_oc_test(&mut self, on: bool) {
        if let Some(il) = self.il.as_mut() {
            il.oc_test.set_level(Level::from(on));
        }
    }
    fn set_stby(&mut self, active: bool) {
        self.stby.set_level(Level::from(active));
    }
    fn drive_en_fault_low(&mut self, low: bool) {
        if low {
            self.en_fault.set_low();
            self.en_fault.set_as_output(OutputDrive::Standard0Disconnect1);
        } else {
            // without a driver (DK) EN/FAULT is a floating pin: pull it up
            self.en_fault.set_as_input(if HAS_MOTOR_DRIVER { Pull::None } else { Pull::Up });
        }
    }
    fn read(&mut self) -> PinRead {
        let en_fault_high = self.en_fault.is_high();
        let dock_n_low = self.dock_n.as_ref().is_some_and(|p| p.is_low());
        let stby = self.stby.is_high();
        match self.il.as_ref() {
            Some(il) => PinRead {
                latch_q: il.latch_q.is_high(),
                oc_ok: il.oc_ok.is_high(),
                mot_allow: il.pgate_mon.is_low(),
                docked_h: il.docked_h.is_high(),
                dir_rev: il.dir_rev.is_high(),
                mcu_en: il.mcu_en.is_high(),
                stby,
                arm_clk: il.arm_clk.is_high(),
                latch_clr: il.latch_clr_n.is_low(),
                dock_n_low,
                pod_present: il.pod_id_n.is_low(),
                en_fault_high,
            },
            None => PinRead { stby, dock_n_low, en_fault_high, oc_ok: true, ..PinRead::default() },
        }
    }
    fn vmot_mv(&mut self) -> u32 {
        divided_to_mv(self.adc.scan().vmot)
    }
    fn isense_mv(&mut self) -> u32 {
        raw_to_mv(self.adc.scan().isense)
    }
    fn vbus_mv(&mut self) -> u32 {
        divided_to_mv(self.adc.scan().vbus)
    }
    fn vdd_mv(&mut self) -> u32 {
        raw_to_mv(self.adc.scan().vdd)
    }
    fn tmag_ack(&mut self) -> bool {
        TMAG_PRESENT.load(Ordering::Relaxed)
    }
    fn now_us(&mut self) -> u64 {
        Instant::now().as_micros()
    }
    fn delay_us(&mut self, us: u32) {
        block_for(Duration::from_micros(us as u64));
    }
    /// During a long proof the POST is itself verifying: refresh the DONE permit (no idle verification here).
    fn kick(&mut self) {
        super::wdt::grant_permit();
    }
}

fn ctl_cfg() -> CtlCfg {
    CtlCfg {
        forward_high: DIR_FORWARD_HIGH,
        vmot_on_min_mv: VMOT_ON_MIN_MV,
        vmot_off_max_mv: VMOT_OFF_MAX_MV,
        settle_ms: VMOT_SETTLE_MS as u32,
        fall_timeout_ms: VMOT_FALL_TIMEOUT_MS as u32,
        stby_wake_us: STBY_WAKE_US as u32,
        driver_ready_ms: DRIVER_READY_TIMEOUT_MS as u32,
        interlock: HAS_INTERLOCK,
        driver: HAS_MOTOR_DRIVER,
    }
}

/// The driver: the host-tested controller over the embassy pins.
pub type Driver = BenchCtl<EmbassyPins>;

/// All outputs are put into the fail-safe state: driver in standby, supply gates open, latch held clear, test pins low,
/// DIR at the forward level.
pub fn new_driver(
    adc: Adc,
    dir: Peri<'static, AnyPin>,
    stby: Peri<'static, AnyPin>,
    en_fault: Peri<'static, AnyPin>,
    il: Option<InterlockPins>,
    dock_n: Option<Peri<'static, AnyPin>>,
    done: Option<Peri<'static, AnyPin>>,
) -> Driver {
    let il = il.map(|p| IlPins {
        arm_clk: flex_out(p.arm_clk, Level::Low, OutputDrive::Standard),
        // Open drain: low pulls the latch clear (held clear at idle), "high" releases the line. Never driven high.
        latch_clr_n: flex_out(p.latch_clr_n, Level::Low, OutputDrive::Standard0Disconnect1),
        mcu_en: flex_out(p.mcu_en, Level::Low, OutputDrive::Standard),
        latch_q: Input::new(p.latch_q_mon, Pull::None),
        oc_ok: Input::new(p.oc_ok, Pull::None),
        pgate_mon: Input::new(p.pgate_mon, Pull::None),
        dir_rev: Input::new(p.dir_rev, Pull::None),
        docked_h: Input::new(p.docked_h, Pull::None),
        dock_test: Output::new(p.dock_test, Level::Low, OutputDrive::Standard),
        oc_test: Output::new(p.oc_test, Level::Low, OutputDrive::Standard),
        pod_id_n: Input::new(p.pod_id_n, Pull::None),
    });
    let mut en_fault = Flex::new(en_fault);
    en_fault.set_low();
    en_fault.set_as_output(OutputDrive::Standard0Disconnect1);
    let pins = EmbassyPins {
        adc,
        dir: Output::new(dir, Level::from(DIR_FORWARD_HIGH), OutputDrive::Standard),
        stby: flex_out(stby, Level::Low, OutputDrive::Standard),
        en_fault,
        il,
        dock_n: dock_n.map(|p| Input::new(p, Pull::None)),
        _done: done.map(|p| Output::new(p, Level::Low, OutputDrive::Standard)),
    };
    BenchCtl::new(pins, ctl_cfg())
}
