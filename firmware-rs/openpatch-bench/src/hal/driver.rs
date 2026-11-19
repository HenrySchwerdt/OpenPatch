//! STSPIN220 control and the hardware interlock sequence (bench controller board).
//!
//! `VMOT on = latch AND MCU_EN AND DOCKED` (electronics/bench/pin-assignment.md). Power-up order
//! (`power_up`), always immediately before a burst and only from the safety task:
//!  1. release KILL_N (open drain), MCU_EN high, one ARM_CLK rising edge,
//!  2. LATCH_Q_MON must read high (latch set) and VMOT_SENSE must show the supply,
//!  3. STBY high (MODE pins latched, full step), wait, release EN/FAULT and wait until it reads high,
//!  4. the caller emits the step burst.
//! Power-down (`power_off`): STBY low, EN/FAULT driven low, MCU_EN low, KILL_N low (clears the latch),
//! ARM_CLK low, then LATCH_Q_MON must read low and VMOT must collapse. If not, `failed` is latched:
//! the safety task stops answering the TPL5010 and the hardware resets the MCU, which clears the
//! latch independently of the firmware.
use embassy_nrf::gpio::{AnyPin, Flex, Input, Level, Output, OutputDrive, Pull};
use embassy_nrf::Peri;
use embassy_time::{block_for, Duration, Instant};

use super::adc::{divided_to_mv, Adc};
use crate::board::{InterlockPins, HAS_INTERLOCK, HAS_MOTOR_DRIVER};
use crate::config::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, defmt::Format)]
pub enum PowerError {
    /// A previous power-down could not be verified; no further power-up until reset.
    InterlockFailed,
    NotDocked,
    /// LATCH_Q_MON did not follow ARM_CLK.
    LatchNotSet,
    /// VMOT_SENSE does not show the supply although the interlock is closed.
    NoSupply,
    /// EN/FAULT stayed low (STSPIN220 fault or not ready).
    DriverFault,
}

struct Interlock {
    arm_clk: Output<'static>,
    kill_n: Output<'static>,
    mcu_en: Output<'static>,
    latch_mon: Input<'static>,
}

pub struct Driver {
    dir: Output<'static>,
    /// MODE1/MODE2 are only written at construction (latched by the STSPIN220 at the STBY edge);
    /// kept so the pins stay configured as outputs.
    #[allow(dead_code)]
    mode1: Output<'static>,
    #[allow(dead_code)]
    mode2: Output<'static>,
    stby: Output<'static>,
    en_fault: Flex<'static>,
    il: Option<Interlock>,
    pub powered: bool,
    pub failed: bool,
}

fn short_delay_us(us: u32) {
    // 64 MHz core, ~4 cycles per loop iteration margin included
    cortex_m::asm::delay(us * 64);
}

impl Driver {
    /// All outputs are put into the fail-safe state: driver in standby, supply gates open.
    pub fn new(
        dir: Peri<'static, AnyPin>,
        mode1: Peri<'static, AnyPin>,
        mode2: Peri<'static, AnyPin>,
        stby: Peri<'static, AnyPin>,
        en_fault: Peri<'static, AnyPin>,
        il: Option<InterlockPins>,
    ) -> Self {
        let il = il.map(|p| Interlock {
            arm_clk: Output::new(p.arm_clk, Level::Low, OutputDrive::Standard),
            // Open drain: low pulls the latch clear, "high" releases the line (board pull-up). Never driven high.
            kill_n: Output::new(p.kill_n, Level::Low, OutputDrive::Standard0Disconnect1),
            mcu_en: Output::new(p.mcu_en, Level::Low, OutputDrive::Standard),
            latch_mon: Input::new(p.latch_q_mon, Pull::None),
        });
        let mut en_fault = Flex::new(en_fault);
        en_fault.set_low();
        en_fault.set_as_output(OutputDrive::Standard0Disconnect1);
        Self {
            dir: Output::new(dir, Level::from(DIR_FORWARD_HIGH), OutputDrive::Standard),
            mode1: Output::new(mode1, Level::from(MODE1_LEVEL_HIGH), OutputDrive::Standard),
            mode2: Output::new(mode2, Level::from(MODE2_LEVEL_HIGH), OutputDrive::Standard),
            stby: Output::new(stby, Level::Low, OutputDrive::Standard),
            en_fault,
            il,
            powered: false,
            failed: false,
        }
    }

    fn wait_until(timeout_ms: u64, mut cond: impl FnMut() -> bool) -> bool {
        let t0 = Instant::now();
        loop {
            if cond() {
                return true;
            }
            if Instant::now() - t0 > Duration::from_millis(timeout_ms) {
                return false;
            }
        }
    }

    /// DIR level for forward (piston advancing) or reverse (draw) motion. Only call while the
    /// driver is idle or powered with STCK low.
    pub fn set_direction(&mut self, forward: bool) {
        self.dir.set_level(Level::from(forward == DIR_FORWARD_HIGH));
    }

    /// `require_docked`: forward delivery needs DOCKED. Draw mode runs UNDOCKED by definition; the
    /// bench board interlock still needs DOCKED in hardware, so on that board the supply check
    /// fails (docs/stubs.md, "draw vs interlock").
    pub fn power_up(&mut self, adc: &mut Adc, docked: bool, require_docked: bool) -> Result<(), PowerError> {
        if self.failed {
            return Err(PowerError::InterlockFailed);
        }
        if require_docked && !docked {
            return Err(PowerError::NotDocked);
        }
        // 1. interlock
        if let Some(il) = self.il.as_mut() {
            il.kill_n.set_high(); // release
            il.mcu_en.set_high();
            short_delay_us(50);
            il.arm_clk.set_high(); // rising edge = ARM
            short_delay_us(5);
            il.arm_clk.set_low();
            short_delay_us(50);
            // 2. read back
            if il.latch_mon.is_low() {
                self.power_off(adc);
                return Err(PowerError::LatchNotSet);
            }
            block_for(Duration::from_millis(VMOT_SETTLE_MS));
            let ok = adc_vmot_mv(adc) >= VMOT_ON_MIN_MV;
            if !ok {
                self.power_off(adc);
                return Err(PowerError::NoSupply);
            }
        }
        // 3. driver: MODE pins are already at their levels (STBY low); DIR at the forward level.
        self.set_direction(true);
        // Without a driver (DK) EN/FAULT is a floating pin: pull it up and skip the readiness check.
        self.en_fault.set_as_input(if HAS_MOTOR_DRIVER { Pull::None } else { Pull::Up });
        self.stby.set_high();
        block_for(Duration::from_micros(STBY_WAKE_US));
        let ready = HAS_MOTOR_DRIVER && {
            let en = &self.en_fault;
            Self::wait_until(DRIVER_READY_TIMEOUT_MS, || en.is_high())
        } || !HAS_MOTOR_DRIVER;
        if !ready {
            self.power_off(adc);
            return Err(PowerError::DriverFault);
        }
        self.powered = true;
        Ok(())
    }

    /// `true` if the supply is verified cut. A failed verification latches `failed`.
    pub fn power_off(&mut self, adc: &mut Adc) -> bool {
        self.powered = false;
        self.stby.set_low();
        self.en_fault.set_low();
        self.en_fault.set_as_output(OutputDrive::Standard0Disconnect1);
        let Some(il) = self.il.as_mut() else { return true };
        il.mcu_en.set_low();
        il.kill_n.set_low();
        il.arm_clk.set_low();
        let cut = Self::wait_until(VMOT_FALL_TIMEOUT_MS, || {
            il.latch_mon.is_low() && adc_vmot_mv(adc) <= VMOT_OFF_MAX_MV
        });
        if !cut {
            self.failed = true;
            defmt::error!("INTERLOCK: supply not verified cut after KILL_N/MCU_EN low");
        }
        cut
    }

    /// Idle check (once per tick): with the driver off the latch must be clear and VMOT absent.
    pub fn verify_idle(&mut self, adc: &mut Adc) -> bool {
        if self.powered {
            return true;
        }
        let Some(il) = self.il.as_ref() else { return true };
        let ok = il.latch_mon.is_low() && adc_vmot_mv(adc) <= VMOT_OFF_MAX_MV;
        if !ok {
            self.failed = true;
            defmt::error!("INTERLOCK: latch or VMOT active while the driver is off");
        }
        ok
    }

    /// `true` if EN/FAULT reads low while the driver should be running (STSPIN220 over-current /
    /// thermal protection disabled the power stage).
    pub fn fault_asserted(&self) -> bool {
        HAS_MOTOR_DRIVER && self.powered && self.en_fault.is_low()
    }

    #[allow(dead_code)]
    pub fn has_interlock(&self) -> bool {
        HAS_INTERLOCK && self.il.is_some()
    }
}

fn adc_vmot_mv(adc: &mut Adc) -> u32 {
    divided_to_mv(adc.scan().vmot)
}
