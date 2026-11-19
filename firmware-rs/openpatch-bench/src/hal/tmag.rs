//! TMAG5273A1 (I2C 0x35) absolute angle sensor on the pod: the angle channel of the core
//! (`Hal::angle_read`, 4096 counts per leadscrew turn, cumulative).
//!
//! BOARD CONFLICT (docs/stubs.md): the pod FFC of the current board documentation may not carry
//! the I2C pins; without them the sensor never answers, `angle_read` returns `None` and the core
//! refuses to deliver. Use `angle-qdec-fallback` to run on a bench without the sensor.
//!
//! TODO(verify-on-hardware): the register map below is from memory of the TMAG5273 datasheet and
//! has not been checked against it or against a device: DEVICE_CONFIG_2 0x01 (OPERATING_MODE 2 =
//! continuous), SENSOR_CONFIG_1 0x02 (MAG_CH_EN = X,Y), SENSOR_CONFIG_2 0x03 (ANGLE_EN = XY),
//! MANUFACTURER_ID 0x0E/0x0F = 0x49 0x54, ANGLE_RESULT 0x19/0x1A (13 bit, 4 fractional bits of a degree).
use embassy_futures::block_on;
use embassy_futures::select::{select, Either};
use embassy_nrf::gpio::AnyPin;
use embassy_nrf::peripherals::TWISPI0;
use embassy_nrf::twim::{self, Twim};
use embassy_nrf::Peri;
use embassy_time::Timer;
use static_cell::StaticCell;

use crate::config::*;
use crate::irqs::Irqs;
use crate::shared::TMAG_PRESENT;
use core::sync::atomic::Ordering;

const REG_DEVICE_CONFIG_2: u8 = 0x01;
const REG_SENSOR_CONFIG_1: u8 = 0x02;
const REG_SENSOR_CONFIG_2: u8 = 0x03;
const REG_MANUFACTURER_ID_LSB: u8 = 0x0E;
const REG_ANGLE_RESULT_MSB: u8 = 0x19;
/// "TI": 0x49 (LSB), 0x54 (MSB).
const MANUFACTURER_ID: [u8; 2] = [0x49, 0x54];
/// 360 degrees in 1/16 degree units.
const ANGLE_FULL_SCALE: u32 = 360 * 16;

pub struct Tmag {
    twim: Twim<'static>,
    fails: u8,
}

/// 13 bit angle (MSB = angle[12:5], LSB bits 7:3 = angle[4:0]) to 12 bit counts.
pub fn decode_angle(msb: u8, lsb: u8) -> u16 {
    let a13 = ((msb as u32) << 5) | ((lsb as u32) >> 3);
    ((a13 * ANGLE_COUNTS_PER_TURN as u32) / ANGLE_FULL_SCALE).min(ANGLE_COUNTS_PER_TURN as u32 - 1) as u16
}

impl Tmag {
    /// Probe and configure. `None` if the sensor does not answer.
    pub async fn init(twi: Peri<'static, TWISPI0>, sda: Peri<'static, AnyPin>, scl: Peri<'static, AnyPin>) -> Option<Tmag> {
        static TXBUF: StaticCell<[u8; 8]> = StaticCell::new();
        let mut cfg = twim::Config::default();
        cfg.frequency = twim::Frequency::K400;
        let mut t = Twim::new(twi, Irqs, sda, scl, cfg, TXBUF.init([0; 8]));
        let mut id = [0u8; 2];
        let r = select(t.write_read(TMAG_ADDR, &[REG_MANUFACTURER_ID_LSB], &mut id), Timer::after_millis(30)).await;
        let present = matches!(r, Either::First(Ok(()))) && id == MANUFACTURER_ID;
        TMAG_PRESENT.store(present, Ordering::Relaxed);
        if !present {
            defmt::warn!("TMAG5273 not found at 0x35: angle_read will return None (core refuses to deliver)");
            return None;
        }
        for (reg, val) in [(REG_SENSOR_CONFIG_1, 0x30u8), (REG_SENSOR_CONFIG_2, 0x04), (REG_DEVICE_CONFIG_2, 0x02)] {
            let w = select(t.write(TMAG_ADDR, &[reg, val]), Timer::after_millis(30)).await;
            if !matches!(w, Either::First(Ok(()))) {
                defmt::warn!("TMAG5273 configuration write failed");
                TMAG_PRESENT.store(false, Ordering::Relaxed);
                return None;
            }
        }
        defmt::info!("TMAG5273 found and configured (angle XY, continuous)");
        Some(Tmag { twim: t, fails: 0 })
    }

    /// One raw angle sample (0..4095). `None` after `TMAG_FAIL_LIMIT` consecutive failures.
    pub fn read_raw(&mut self) -> Result<u16, ()> {
        let mut b = [0u8; 2];
        let t = embassy_time::Duration::from_millis(TMAG_TIMEOUT_MS);
        let r = block_on(embassy_time::with_timeout(t, self.twim.write_read(TMAG_ADDR, &[REG_ANGLE_RESULT_MSB], &mut b)));
        match r {
            Ok(Ok(())) => {
                self.fails = 0;
                Ok(decode_angle(b[0], b[1]))
            }
            _ => {
                self.fails = self.fails.saturating_add(1);
                if self.fails == TMAG_FAIL_LIMIT {
                    defmt::error!("TMAG5273 stopped answering");
                    TMAG_PRESENT.store(false, Ordering::Relaxed);
                }
                Err(())
            }
        }
    }

    pub fn missing(&self) -> bool {
        self.fails >= TMAG_FAIL_LIMIT
    }
}
