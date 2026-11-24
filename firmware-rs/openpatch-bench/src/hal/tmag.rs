//! TMAG5273A1 (I2C 0x35) absolute angle sensor on the pod: the angle channel of the core
//! (`Hal::angle_read`, 4096 counts per leadscrew turn, cumulative).
//!
//! BOARD CONFLICT (docs/stubs.md): the pod FFC of the current board documentation may not carry
//! the I2C pins; without them the sensor never answers, `angle_read` returns `None` and the core
//! refuses to deliver. Use `angle-qdec-fallback` to run on a bench without the sensor.
//!
//! Register map, angle decoding, CRC and configuration come from `openpatch_core::tmag5273`, which is
//! checked on the host against TI datasheet SLYS045C (section numbers in that module). Verified against
//! the DATASHEET only: TODO(verify-on-hardware) remains for the real device (I2C timing on the FFC,
//! first-conversion behaviour, CRC coverage of the 4-byte read, magnet/magnitude range).
//! Read frame: CONV_STATUS, ANGLE_MSB, ANGLE_LSB, MAGNITUDE (0x18..0x1B, one auto-increment read),
//! CONV_STATUS again to detect a torn read (section 7.3), POR / DIAG bits reject the sample.
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

use openpatch_core::tmag5273 as t;
const _: () = assert!(ANGLE_COUNTS_PER_TURN as u32 == t::COUNTS_PER_TURN);

pub struct Tmag {
    twim: Twim<'static>,
    fails: u8,
}

impl Tmag {
    /// Probe and configure. `None` if the sensor does not answer.
    pub async fn init(twi: Peri<'static, TWISPI0>, sda: Peri<'static, AnyPin>, scl: Peri<'static, AnyPin>) -> Option<Tmag> {
        static TXBUF: StaticCell<[u8; 8]> = StaticCell::new();
        let mut cfg = twim::Config::default();
        // cup pod v4: 100 kHz on the 4.7 k pull-ups of the rear strip (board::I2C_FREQUENCY_HZ); bench board / DK: 400 kHz
        cfg.frequency = if cfg!(feature = "board-cup-v4") { twim::Frequency::K100 } else { twim::Frequency::K400 };
        let mut t = Twim::new(twi, Irqs, sda, scl, cfg, TXBUF.init([0; 8]));
        let mut id = [0u8; 2];
        // tstart_power_up is 270 us (datasheet electrical table); the board has been powered for ages here.
        let r = select(t.write_read(TMAG_ADDR, &[t::REG_MANUFACTURER_ID_LSB], &mut id), Timer::after_millis(30)).await;
        let present = matches!(r, Either::First(Ok(()))) && id == t::MANUFACTURER_ID;
        TMAG_PRESENT.store(present, Ordering::Relaxed);
        if !present {
            defmt::warn!("TMAG5273 not found at 0x35: angle_read will return None (core refuses to deliver)");
            return None;
        }
        // DEVICE_ID.VER must be the +-40 mT part (TMAG5273x1): the angle range is configured for it.
        let mut ver = [0u8; 1];
        let r = select(t.write_read(TMAG_ADDR, &[t::REG_DEVICE_ID], &mut ver), Timer::after_millis(30)).await;
        if !matches!(r, Either::First(Ok(()))) || ver[0] & 0x03 != t::DEVICE_VER_40MT {
            defmt::warn!("TMAG5273 DEVICE_ID version {} is not the +-40 mT part: refusing", ver[0]);
            TMAG_PRESENT.store(false, Ordering::Relaxed);
            return None;
        }
        for (reg, val) in t::config_writes_for(TMAG_CRC_EN, TMAG_PLANE, TMAG_RANGE_80MT) {
            let w = select(t.write(TMAG_ADDR, &[reg, val]), Timer::after_millis(30)).await;
            if !matches!(w, Either::First(Ok(()))) {
                defmt::warn!("TMAG5273 configuration write failed");
                TMAG_PRESENT.store(false, Ordering::Relaxed);
                return None;
            }
        }
        // Clear the power-on-reset flag (CONV_STATUS.POR is write-1-to-clear): a LATER POR means the
        // sensor reset and lost its configuration, `read_raw` then fails.
        let w = select(t.write(TMAG_ADDR, &[t::REG_CONV_STATUS, t::CONV_POR]), Timer::after_millis(30)).await;
        if !matches!(w, Either::First(Ok(()))) {
            defmt::warn!("TMAG5273 POR clear failed");
            TMAG_PRESENT.store(false, Ordering::Relaxed);
            return None;
        }
        Timer::after_millis(2).await; // tstart_measure 70 us, first conversion well below 1 ms
        defmt::info!("TMAG5273 found and configured (angle XY, continuous, crc={})", TMAG_CRC_EN);
        Some(Tmag { twim: t, fails: 0 })
    }

    /// One raw angle sample (0..4095). `None` after `TMAG_FAIL_LIMIT` consecutive failures.
    pub fn read_raw(&mut self) -> Result<u16, ()> {
        let r = self.read_frame().or_else(|_| self.read_frame()); // one retry (torn read / glitch)
        match r {
            Ok(s) => {
                self.fails = 0;
                Ok(s.counts)
            }
            Err(()) => {
                self.fails = self.fails.saturating_add(1);
                if self.fails == TMAG_FAIL_LIMIT {
                    defmt::error!("TMAG5273 stopped answering or reports errors (POR/DIAG/CRC/angle)");
                    TMAG_PRESENT.store(false, Ordering::Relaxed);
                }
                Err(())
            }
        }
    }

    fn read_frame(&mut self) -> Result<t::Sample, ()> {
        let to = embassy_time::Duration::from_millis(TMAG_TIMEOUT_MS);
        let mut buf = [0u8; t::FRAME_LEN + 1];
        let n = if TMAG_CRC_EN { t::FRAME_LEN + 1 } else { t::FRAME_LEN };
        let r = block_on(embassy_time::with_timeout(to, self.twim.write_read(TMAG_ADDR, &[t::REG_CONV_STATUS], &mut buf[..n])));
        if !matches!(r, Ok(Ok(()))) {
            return Err(());
        }
        let mut st = [0u8; 1];
        let r = block_on(embassy_time::with_timeout(to, self.twim.write_read(TMAG_ADDR, &[t::REG_CONV_STATUS], &mut st)));
        if !matches!(r, Ok(Ok(()))) || t::torn(buf[0], st[0]) {
            return Err(());
        }
        let regs = [buf[0], buf[1], buf[2], buf[3]];
        t::decode_frame(&regs, TMAG_CRC_EN.then_some(buf[4])).map_err(|e| {
            defmt::warn!("TMAG5273 frame rejected: {}", defmt::Debug2Format(&e));
        })
    }

    pub fn missing(&self) -> bool {
        self.fails >= TMAG_FAIL_LIMIT
    }
}
