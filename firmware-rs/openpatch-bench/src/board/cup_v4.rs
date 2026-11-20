//! Cup pod v4 board (45 fitted parts): HJ-840 nRF52840 SiP, DRV8835 motor driver, STM32C011 supervisor. ALL pin knowledge of this
//! board is in this file, so a netlist change is a change here only.
//!
//! Source of truth: `electronics/v010/design/netlist_v4.py` (`HJ_PIN` pad -> nRF pin, signal -> pad assignment) and
//! `electronics/v010/netlist_v4_cup.json`; the HJ-840 table in `FIRMWARE-PINMAP.md` is stale. Pad / nRF pin as of the netlist at
//! commit 1f9d20d (45 parts) and the 2026-11-20 review:
//!
//! | HJ-840 pad | nRF pin | Net | Use |
//! |---|---|---|---|
//! | A2  | P1.01 | `APHASE`   | out: DRV8835 PHASE A, also supervisor input (PA) |
//! | A3  | P0.21 | `BPHASE`   | out: DRV8835 PHASE B, also supervisor input |
//! | A4  | P0.20 | `AENBL`    | out: bridge A enable, 100 k pull-down: 1 = driven, 0 = brake |
//! | A5  | P0.17 | `BENBL`    | out: bridge B enable |
//! | A6  | P0.14 | `CHG_STAT` | in: MCP73832 STAT, low = charging (high / high-Z otherwise: use `USBDETECTED` for the cable) |
//! | B1  | P0.22 | `OC_OK`    | in: TPS2553 FAULT, low = current limit active (100 k pull-up) |
//! | B2  | P1.04 | `LATCH_Q`  | in: interlock latch readback (RB6) |
//! | B3  | P1.07 | `DOCK_N`   | in: dock hall DRV5032FA, LOW = docked |
//! | B5  | P1.05 | `SUP_OK`   | in: supervisor healthy |
//! | B6  | P0.24 | `LED_R`    | out, active low (RGB common anode on VBAT, 1 k) |
//! | B7  | P1.06 | `LED_G`    | out, active low |
//! | B8  | P1.14 | `LED_B`    | out, active low |
//! | C1  | P0.25 | `SUP_TXD`  | in: UART RX from the supervisor |
//! | C6  | P0.13 | `SUP_RXD`  | out: UART TX to the supervisor |
//! | C7  | P1.11 | `SUP_BOOT0`| out: supervisor BOOT0 strap (100 k pull-down) |
//! | C8  | P1.12 | `SUP_NRST` | io, OPEN DRAIN ONLY (never push-pull high): pulls the supervisor NRST low |
//! | D1  | P0.19 | `MOT_FWD`  | out: forward intent, HIGH = forward (pull-up: reset default = forward = blocked when undocked) |
//! | D2  | P1.00 | `BTN_N`    | in: side button, internal pull-up |
//! | D3  | P1.02 | `I2C_SCL`  | TWIM: TMAG5273 (rear strip), 4.7 k pull-ups, 100 kHz |
//! | D4  | P1.03 | `I2C_SDA`  | TWIM |
//! | D5  | P0.23 | `ARM_CLK`  | out: rising edge sets the latch and arms the supervisor, 100 k pull-down |
//! | D6  | P1.10 | `MCU_EN`   | out: hardware leg of the motor enable (3-input AND `LATCH_Q` & `SUP_PERMIT` & `MCU_EN`), 100 k pull-down |
//! | D7  | P1.13 | `BUZ_A`    | out: sounder NFET gate |
//! | E1  | P0.18 | `NRST`     | reset (UICR PSELRESET), TPL5010 RSTn |
//! | H7  | P0.04 | `VMOT_SENSE` | SAADC AIN2: motor supply after the load switch, 100 k / 100 k (x 2) |
//! | F1/G1/F2 | D+ / D- / VBUS | `USB_DP` / `USB_DM` / `VBUS_P` | USB (DFU, charging); `USBDETECTED` = cable |
//! | C2/C3 | SWDIO / SWCLK | bare pads | one-time bootloader flash |
//! | H2 | VDDH | `VBAT` | the cell: battery voltage through the SAADC `VDDHDIV5` channel (no pin) |
//!
//! Removed against the older boards: no STEP/DIR/STBY/EN-FAULT, no `I_SENSE` (no shunt: occlusion is the angle shortfall only,
//! `OcclusionSource::AngleOnly`), no `OC_TEST`, no `DOCK_TEST`, no `NTC`, no `WDT_*` (the TPL5010 watches the supervisor).
//! The `MOT_FWD` polarity is the OPPOSITE of the older `MOT_DIR` (high = reverse there).
//!
//! Power: HV mode (VDDH = the cell, REG0 supplies the 3V3 rail on the VDD pads): `UICR.REGOUT0` must be 3.3 V ([`regout0_setup`]); the
//! module has no LDO and no 32 kHz crystal (`LfclkSource::InternalRC`).
use embassy_nrf::gpio::AnyPin;
use embassy_nrf::saadc::Input as _;
use embassy_nrf::{Peri, Peripherals};

pub const BOARD_NAME: &str = "cup-v4";
/// LED pins are active low.
pub const LED_ACTIVE_HIGH: bool = false;
/// Hall output polarity: low = docked.
pub const DOCK_ACTIVE_LOW: bool = true;
/// `MOT_FWD` level for forward.
pub const MOT_FWD_FORWARD_HIGH: bool = true;
/// I2C: 100 kHz (external 4.7 k pull-ups), the TMAG is put to sleep after boot.
pub const I2C_FREQUENCY_HZ: u32 = 100_000;
/// TPL5010 interval (R26 6.8 k): about 2.0 s. Kick timing and the "one watchdog interval" bound use it.
pub const TPL5010_INTERVAL_MS: u32 = 2_000;

/// All pins of the board by function.
pub struct CupIo {
    pub saadc: Peri<'static, embassy_nrf::peripherals::SAADC>,
    /// `VMOT_SENSE` (P0.04, AIN2).
    pub vmot_sense: embassy_nrf::saadc::AnyInput<'static>,
    pub nvmc: Peri<'static, embassy_nrf::peripherals::NVMC>,
    pub aphase: Peri<'static, AnyPin>,
    pub bphase: Peri<'static, AnyPin>,
    pub aenbl: Peri<'static, AnyPin>,
    pub benbl: Peri<'static, AnyPin>,
    pub chg_stat: Peri<'static, AnyPin>,
    pub oc_ok: Peri<'static, AnyPin>,
    pub latch_q: Peri<'static, AnyPin>,
    pub dock_n: Peri<'static, AnyPin>,
    pub sup_ok: Peri<'static, AnyPin>,
    pub led_r: Peri<'static, AnyPin>,
    pub led_g: Peri<'static, AnyPin>,
    pub led_b: Peri<'static, AnyPin>,
    pub sup_rx: Peri<'static, AnyPin>,
    pub sup_tx: Peri<'static, AnyPin>,
    pub sup_boot0: Peri<'static, AnyPin>,
    pub sup_nrst: Peri<'static, AnyPin>,
    pub mot_fwd: Peri<'static, AnyPin>,
    pub button: Peri<'static, AnyPin>,
    pub i2c_scl: Peri<'static, AnyPin>,
    pub i2c_sda: Peri<'static, AnyPin>,
    pub arm_clk: Peri<'static, AnyPin>,
    pub mcu_en: Peri<'static, AnyPin>,
    pub buz_a: Peri<'static, AnyPin>,
}

/// Moves the board pins and the peripherals the bring-up firmware needs out of `p` (partial move).
pub fn take(p: Peripherals) -> CupIo {
    CupIo {
        saadc: p.SAADC,
        vmot_sense: p.P0_04.degrade_saadc(),
        nvmc: p.NVMC,
        aphase: p.P1_01.into(),
        bphase: p.P0_21.into(),
        aenbl: p.P0_20.into(),
        benbl: p.P0_17.into(),
        chg_stat: p.P0_14.into(),
        oc_ok: p.P0_22.into(),
        latch_q: p.P1_04.into(),
        dock_n: p.P1_07.into(),
        sup_ok: p.P1_05.into(),
        led_r: p.P0_24.into(),
        led_g: p.P1_06.into(),
        led_b: p.P1_14.into(),
        sup_rx: p.P0_25.into(),
        sup_tx: p.P0_13.into(),
        sup_boot0: p.P1_11.into(),
        sup_nrst: p.P1_12.into(),
        mot_fwd: p.P0_19.into(),
        button: p.P1_00.into(),
        i2c_scl: p.P1_02.into(),
        i2c_sda: p.P1_03.into(),
        arm_clk: p.P0_23.into(),
        mcu_en: p.P1_10.into(),
        buz_a: p.P1_13.into(),
    }
}

/// One-time UICR handling (runs before anything else): `REGOUT0` = 3.3 V, `PSELRESET` = P0.18. The decision is the host tested
/// `openpatch_core::battery::regout0_action`. A fresh module resets once after the write (the new rail voltage needs a reset); a
/// module with another programmed voltage needs `probe-rs erase` once and is NOT started (the rail would be wrong).
pub fn regout0_setup() {
    use embassy_nrf::{uicr_write_masked, WriteResult};
    use openpatch_core::battery::*;
    const PSELRESET0: *mut u32 = 0x1000_1200 as *mut u32;
    const PSELRESET1: *mut u32 = 0x1000_1204 as *mut u32;
    let regout = UICR_REGOUT0_ADDR as *mut u32;
    // SAFETY: fixed UICR registers of the nRF52840; reads and the one-way masked writes of `uicr_write_masked`.
    let word = unsafe { regout.read_volatile() };
    let mut reset = false;
    match regout0_action(word) {
        Regout0Action::Nothing => {}
        Regout0Action::Write => {
            // only bits 2..0 are written (1 -> 0), the upper bits stay as they are
            if let WriteResult::Written = unsafe { uicr_write_masked(regout, REGOUT0_3V3_WORD, REGOUT0_VOUT_MASK) } {
                reset = true;
            }
        }
        Regout0Action::NeedsErase => {
            defmt::error!("UICR.REGOUT0 holds another voltage: erase the UICR once (probe-rs erase); the 3V3 rail is wrong, not starting");
            loop {
                cortex_m::asm::wfi();
            }
        }
    }
    for reg in [PSELRESET0, PSELRESET1] {
        if let WriteResult::Written = unsafe { embassy_nrf::uicr_write(reg, 18) } {
            reset = true;
        }
    }
    if reset {
        defmt::warn!("UICR written (REGOUT0 3.3 V / PSELRESET), resetting once");
        cortex_m::peripheral::SCB::sys_reset();
    }
}
