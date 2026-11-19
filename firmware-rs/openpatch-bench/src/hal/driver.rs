//! STSPIN220 control and the hardware interlock sequence (bench controller board).
//!
//! `VMOT = MCU_EN AND TPL5010_LATCH AND (DOCKED OR DIR_REVERSE)` (spec 4a, decision 2026-11-19).
//! DIR is therefore part of the supply gate: the plan in `openpatch_core::interlock::power_up_plan`
//! (host-tested) always sets DIR first. Power-up order (`power_up`), immediately before a burst and
//! only from the safety task:
//!  0. refuse forward while undocked / reverse while docked (`interlock::check_request`),
//!  1. DIR to the requested direction, release KILL_N, MCU_EN high, one ARM_CLK rising edge,
//!  2. LATCH_Q_MON must read high (latch set) and VMOT_SENSE must show the supply,
//!  3. STBY high (MODE pins latched, full step), wait, release EN/FAULT and wait until it reads high,
//!  4. the caller emits the step burst.
//! A DIR change while powered (`change_direction`) and the end of every burst re-check VMOT against
//! the gate model: missing supply = fault, supply where the gate must be open = interlock failure.
//! Power-down (`power_off`): STBY low, EN/FAULT driven low, MCU_EN low, KILL_N low (clears the latch),
//! ARM_CLK low, then LATCH_Q_MON must read low and VMOT must collapse. If not, `failed` is latched:
//! the safety task stops answering the TPL5010 and the hardware resets the MCU, which clears the
//! latch independently of the firmware. DIR returns to forward only after that.
//!
//! OPEN (datasheet, not checked here): the STSPIN220 latches MODE4/DIR at the STBY rising edge. In a
//! draw DIR is at the reverse level at that edge. Confirm in DS11633 that full step does not depend
//! on MODE4, else the DIR level at the STBY edge must be handled (docs/stubs.md).
use embassy_nrf::gpio::{AnyPin, Flex, Input, Level, Output, OutputDrive, Pull};
use embassy_nrf::Peri;
use embassy_time::{block_for, Duration, Instant};
use openpatch_core::hal::{MotorDir, MotorFault};
use openpatch_core::interlock::{self, power_up_plan, check_supply, vmot_expected, Refusal, Step, SupplyCheck};

use super::adc::{divided_to_mv, Adc};
use crate::board::{InterlockPins, HAS_INTERLOCK, HAS_MOTOR_DRIVER};
use crate::config::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, defmt::Format)]
pub enum PowerError {
    /// A previous power-down could not be verified; no further power-up until reset.
    InterlockFailed,
    /// Direction / dock combination refused before any pin was touched.
    Refused(Refusal),
    /// LATCH_Q_MON did not follow ARM_CLK.
    LatchNotSet,
    /// VMOT_SENSE does not show the supply although the interlock is closed.
    NoSupply,
    /// VMOT present where the gate must be open.
    UnexpectedSupply,
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
    /// Direction the driver is powered for (valid while `powered`).
    dir_state: MotorDir,
    /// Cause of the last refused / failed power-up or burst, taken by `Hal::motor_fault`.
    pub fault: Option<MotorFault>,
}

impl PowerError {
    pub fn to_fault(self) -> MotorFault {
        match self {
            PowerError::InterlockFailed => MotorFault::InterlockFailed,
            PowerError::Refused(r) => r.into(),
            PowerError::LatchNotSet | PowerError::NoSupply => MotorFault::SupplyMissing,
            PowerError::UnexpectedSupply => MotorFault::SupplyUnexpected,
            PowerError::DriverFault => MotorFault::Driver,
        }
    }
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
            dir_state: MotorDir::Forward,
            fault: None,
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

    /// DIR level for forward (piston advancing) or reverse (draw) motion. On the bench board DIR is
    /// an input of the supply gate: only call it as part of the plan / `change_direction`, or idle.
    pub fn set_direction(&mut self, forward: bool) {
        self.dir.set_level(Level::from(forward == DIR_FORWARD_HIGH));
    }

    fn vmot_check(&mut self, adc: &mut Adc, expected_on: bool) -> SupplyCheck {
        check_supply(expected_on, adc_vmot_mv(adc), VMOT_ON_MIN_MV, VMOT_OFF_MAX_MV)
    }

    /// Power the driver for motion in `dir`. DIR is set BEFORE MCU_EN is requested (the gate needs
    /// it in a draw); forward needs DOCKED, reverse needs UNDOCKED (`interlock::check_request`).
    pub fn power_up(&mut self, adc: &mut Adc, docked: bool, dir: MotorDir) -> Result<(), PowerError> {
        if self.failed {
            return Err(PowerError::InterlockFailed);
        }
        interlock::check_request(dir, docked).map_err(PowerError::Refused)?;
        for step in power_up_plan(dir) {
            match step {
                Step::SetDir(d) => {
                    self.set_direction(d == MotorDir::Forward);
                    self.dir_state = d;
                }
                Step::ReleaseKill => {
                    if let Some(il) = self.il.as_mut() {
                        il.kill_n.set_high(); // release
                    }
                }
                Step::McuEnHigh => {
                    if let Some(il) = self.il.as_mut() {
                        il.mcu_en.set_high();
                        short_delay_us(50);
                    }
                }
                Step::ArmEdge => {
                    if let Some(il) = self.il.as_mut() {
                        il.arm_clk.set_high(); // rising edge = ARM
                        short_delay_us(5);
                        il.arm_clk.set_low();
                        short_delay_us(50);
                    }
                }
                Step::CheckLatchSet => {
                    if self.il.as_ref().is_some_and(|il| il.latch_mon.is_low()) {
                        self.power_off(adc);
                        return Err(PowerError::LatchNotSet);
                    }
                }
                Step::CheckVmotUp => {
                    if self.il.is_some() {
                        block_for(Duration::from_millis(VMOT_SETTLE_MS));
                        // the plan only reaches here with a request the gate must satisfy
                        if self.vmot_check(adc, true) != SupplyCheck::Ok {
                            self.power_off(adc);
                            return Err(PowerError::NoSupply);
                        }
                    }
                }
                Step::DriverOn => {
                    // Without a driver (DK) EN/FAULT is a floating pin: pull it up and skip the readiness check.
                    self.en_fault.set_as_input(if HAS_MOTOR_DRIVER { Pull::None } else { Pull::Up });
                    self.stby.set_high();
                    block_for(Duration::from_micros(STBY_WAKE_US));
                    let ready = !HAS_MOTOR_DRIVER || {
                        let en = &self.en_fault;
                        Self::wait_until(DRIVER_READY_TIMEOUT_MS, || en.is_high())
                    };
                    if !ready {
                        self.power_off(adc);
                        return Err(PowerError::DriverFault);
                    }
                }
            }
        }
        self.powered = true;
        Ok(())
    }

    /// Direction change while powered. The supply must follow the gate model afterwards: present
    /// where the model says ON (else `NoSupply`), absent where it says OFF (else the gate did not
    /// open: `failed` latched, `UnexpectedSupply`).
    pub fn change_direction(&mut self, adc: &mut Adc, docked: bool, dir: MotorDir) -> Result<(), PowerError> {
        interlock::check_request(dir, docked).map_err(PowerError::Refused)?;
        if self.dir_state == dir {
            return Ok(());
        }
        self.set_direction(dir == MotorDir::Forward);
        self.dir_state = dir;
        self.verify_supply(adc, docked)
    }

    /// Compare VMOT with the gate model for the current direction (`latch` and `MCU_EN` are set while powered).
    pub fn verify_supply(&mut self, adc: &mut Adc, docked: bool) -> Result<(), PowerError> {
        if self.il.is_none() {
            return Ok(());
        }
        let expected = vmot_expected(true, true, docked, self.dir_state);
        block_for(Duration::from_millis(VMOT_SETTLE_MS));
        match self.vmot_check(adc, expected) {
            SupplyCheck::Ok => Ok(()),
            SupplyCheck::Missing => {
                self.power_off(adc);
                Err(PowerError::NoSupply)
            }
            SupplyCheck::Unexpected => {
                self.failed = true;
                defmt::error!("INTERLOCK: supply present where the gate must be open");
                self.power_off(adc);
                Err(PowerError::UnexpectedSupply)
            }
        }
    }

    /// `true` if the supply is verified cut. A failed verification latches `failed`.
    pub fn power_off(&mut self, adc: &mut Adc) -> bool {
        self.powered = false;
        self.stby.set_low();
        self.en_fault.set_low();
        self.en_fault.set_as_output(OutputDrive::Standard0Disconnect1);
        let Some(il) = self.il.as_mut() else {
            self.set_direction(true);
            self.dir_state = MotorDir::Forward;
            return true;
        };
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
        // DIR is an input of the supply gate: back to forward only now that the supply is cut.
        self.set_direction(true);
        self.dir_state = MotorDir::Forward;
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
