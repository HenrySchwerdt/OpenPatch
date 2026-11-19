//! SAADC: one 4-channel scan (I_SENSE, VMOT_SENSE, VBUS_SENSE, VDD), 12 bit, gain 1/6, internal 0.6 V
//! reference (full scale 3.6 V). The scan is blocking (a few 100 us) because it is used inside the
//! step burst loop of the safety task; the SAADC interrupt (P3) wakes the future.
use embassy_futures::block_on;
use embassy_nrf::peripherals::SAADC;
use embassy_nrf::saadc::{AnyInput, ChannelConfig, Config, Saadc, Time, VddInput};
use embassy_nrf::Peri;

use crate::config::*;
use crate::irqs::Irqs;

#[derive(Clone, Copy, Default, defmt::Format)]
pub struct Scan {
    pub isense: u16,
    pub vmot: u16,
    pub vbus: u16,
    /// The 3V3 rail (internal VDD channel).
    pub vdd: u16,
}

pub struct Adc {
    saadc: Saadc<'static, 4>,
}

#[inline]
pub fn raw_to_mv(raw: u16) -> u32 {
    raw as u32 * ADC_FULL_SCALE_MV / ADC_COUNTS
}

/// Motor supply current in mA from the I_SENSE counts: V = 20 x 0.333 ohm x I = 6.67 mV per mA.
#[inline]
pub fn isense_to_ma(raw: u16) -> u16 {
    openpatch_core::limits::isense_mv_to_ma(raw_to_mv(raw)).min(u16::MAX as u32) as u16
}

/// Supply voltage behind a 100k / 100k divider.
#[inline]
pub fn divided_to_mv(raw: u16) -> u32 {
    raw_to_mv(raw) * DIVIDER_RATIO
}

impl Adc {
    pub async fn new(
        saadc: Peri<'static, SAADC>,
        isense_pin: AnyInput<'static>,
        vmot_pin: AnyInput<'static>,
        vbus_pin: AnyInput<'static>,
    ) -> Self {
        let mut isense = ChannelConfig::single_ended(isense_pin);
        isense.time = Time::_20US; // 1k source impedance (RC filter)
        let mut vmot = ChannelConfig::single_ended(vmot_pin);
        vmot.time = Time::_40US; // 50k source impedance (divider)
        let mut vbus = ChannelConfig::single_ended(vbus_pin);
        vbus.time = Time::_40US;
        let mut vdd = ChannelConfig::single_ended(VddInput);
        vdd.time = Time::_10US; // low impedance internal source
        let adc = Saadc::new(saadc, Irqs, Config::default(), [isense, vmot, vbus, vdd]);
        adc.calibrate().await;
        Self { saadc: adc }
    }

    /// One scan. Negative readings (offset) are clamped to 0.
    pub fn scan(&mut self) -> Scan {
        let mut buf = [0i16; 4];
        block_on(self.saadc.sample(&mut buf));
        Scan { isense: buf[0].max(0) as u16, vmot: buf[1].max(0) as u16, vbus: buf[2].max(0) as u16, vdd: buf[3].max(0) as u16 }
    }
}
