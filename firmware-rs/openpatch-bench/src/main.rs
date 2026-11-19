//! OpenPatch bench controller firmware (Embassy, nRF52840).
//!
//! TEST PROJECT. NOT a medical device. NEVER to be connected to a body or used with insulin on a
//! person (see DISCLAIMER.md). Bench tests use WATER ONLY.
//!
//! Task architecture (docs/architecture.md):
//!   safety task (P5 interrupt executor): sole owner of `Pump`, motor, interlock, TPL5010 DONE
//!   thread executor: BLE host + GATT, UI (button / LEDs / buzzer), persistence, encoder, DFU confirm
#![no_std]
#![no_main]

mod bench_mode;
mod ble;
mod board;
mod config;
mod crypto;
mod dfu;
mod hal;
mod irqs;
#[path = "../../layout/layout.rs"]
#[allow(dead_code)]
mod layout;
mod pairing;
mod safety;
mod shared;
mod storage;
mod ui;

use defmt_rtt as _;
use embassy_boot::AlignedBuffer;
use embassy_executor::{InterruptExecutor, Spawner};
use embassy_nrf::interrupt;
use embassy_nrf::interrupt::InterruptExt;
use embassy_nrf::rng;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use nrf_sdc::mpsl::{self, Flash, MultiprotocolServiceLayer};
use nrf_sdc::{self as sdc};
use openpatch_core::Pump;
use panic_probe as _;
use static_cell::StaticCell;

use crate::config::*;
use crate::hal::{adc::Adc, stepper::Stepper, BenchHal, BoardIoDriver};
use crate::irqs::Irqs;

static EXECUTOR_SAFETY: InterruptExecutor = InterruptExecutor::new();

#[embassy_nrf::pac::interrupt]
unsafe fn EGU1_SWI1() {
    // SAFETY: called from the interrupt the executor was started on.
    unsafe { EXECUTOR_SAFETY.on_interrupt() }
}

/// SDC memory: 1 peripheral link, 251 byte ACL buffers, 3 TX / 3 RX packets. Nordic's formulas
/// (sdc.h): per peripheral link 923 + 2 x (3 x (251 + 15) - 42) = 2435, shared 17, one advertising set
/// about 0.6 KB, LE power control / feature pages a few 100 bytes: about 4 KB in total. 16 KB leaves
/// a wide margin. `Builder::build` logs the exact requirement ("Memory buffer too big. N bytes
/// needed") at every boot; a too small value disables BLE, the safety task keeps running.
const SDC_MEM: usize = 16 * 1024;
const L2CAP_PDU: u16 = 251;
const L2CAP_TXQ: u8 = 3;
const L2CAP_RXQ: u8 = 3;

#[embassy_executor::task]
async fn mpsl_task(mpsl: &'static MultiprotocolServiceLayer<'static>) -> ! {
    mpsl.run().await
}

#[embassy_executor::main]
async fn main(spawner: Spawner) {
    defmt::info!(
        "OpenPatch bench controller, board {}, drive {:#x}, TEST PROJECT: water only, never on a person",
        board::BOARD_NAME,
        config::PRESET.id as u16
    );
    config::assert_no_test_calibrations();
    let p = embassy_nrf::init(irqs::embassy_config());
    board::uicr_setup();
    irqs::set_driver_priorities();
    let (io, common) = board::take(p);

    // ---- radio stack: MPSL (with timeslots for flash) + SDC ----
    let mpsl_p = mpsl::Peripherals::new(common.rtc0, common.timer0, common.temp, common.ppi_ch19, common.ppi_ch30, common.ppi_ch31);
    // 32.768 kHz crystal on P0.00 / P0.01 (bench board and DK)
    let lfclk_cfg = mpsl::raw::mpsl_clock_lfclk_cfg_t {
        source: mpsl::raw::MPSL_CLOCK_LF_SRC_XTAL as u8,
        rc_ctiv: 0,
        rc_temp_ctiv: 0,
        accuracy_ppm: 20,
        skip_wait_lfclk_started: mpsl::raw::MPSL_DEFAULT_SKIP_WAIT_LFCLK_STARTED != 0,
    };
    static MPSL: StaticCell<MultiprotocolServiceLayer<'static>> = StaticCell::new();
    static SESSION_MEM: StaticCell<mpsl::SessionMem<1>> = StaticCell::new();
    let mpsl = MPSL.init(match mpsl::MultiprotocolServiceLayer::with_timeslots(
        mpsl_p,
        Irqs,
        lfclk_cfg,
        SESSION_MEM.init(mpsl::SessionMem::new()),
    ) {
        Ok(m) => m,
        Err(_) => defmt::panic!("MPSL init failed"),
    });
    spawner.spawn(mpsl_task(&*mpsl).unwrap());

    let sdc_p = sdc::Peripherals::new(
        common.ppi_ch17,
        common.ppi_ch18,
        common.ppi_ch20,
        common.ppi_ch21,
        common.ppi_ch22,
        common.ppi_ch23,
        common.ppi_ch24,
        common.ppi_ch25,
        common.ppi_ch26,
        common.ppi_ch27,
        common.ppi_ch28,
        common.ppi_ch29,
    );
    static RNG: StaticCell<rng::Rng<'static, embassy_nrf::mode::Async>> = StaticCell::new();
    static SDC_MEM_CELL: StaticCell<sdc::Mem<SDC_MEM>> = StaticCell::new();
    let rng = RNG.init(rng::Rng::new(common.rng, Irqs));
    let sdc_mem = SDC_MEM_CELL.init(sdc::Mem::<SDC_MEM>::new());
    let sdc = sdc::Builder::new()
        .and_then(|b| b.support_adv().support_peripheral().peripheral_count(1))
        .and_then(|b| b.buffer_cfg(L2CAP_PDU, L2CAP_PDU, L2CAP_TXQ, L2CAP_RXQ))
        .and_then(|b| b.build(sdc_p, rng, &*mpsl, sdc_mem));

    // ---- flash: MPSL timeslot flash shared by settings and DFU ----
    static FLASH: StaticCell<storage::FlashMutex> = StaticCell::new();
    let flash: &'static storage::FlashMutex = FLASH.init(Mutex::<CriticalSectionRawMutex, _>::new(Flash::take(&*mpsl, common.nvmc)));

    // ---- persisted state ----
    let mut settings = storage::Settings::new(flash);
    let boot = settings.load().await;
    defmt::info!(
        "settings: seq ceiling {}, event ceiling {}, reservoir {}, pod {}, calibration {}",
        boot.seq_ceiling,
        boot.evt_ceiling,
        boot.reservoir,
        boot.pod,
        boot.cal
    );

    // ---- drive / analog / encoder hardware ----
    let mut io = io;
    let adc = Adc::new(common.saadc, io.adc_isense, io.adc_vmot, io.adc_vbus).await;
    let stepper = Stepper::new(common.pwm1, io.mot_stck, common.timer1, common.ppi_ch0.into(), common.ppi_ch1.into());
    let angle = if board::ENCODER_SIMULATED {
        defmt::warn!("angle SIMULATED from the executed pulses (board {})", board::BOARD_NAME);
        hal::angle::AngleSource::Simulated { num: 0 }
    } else if cfg!(feature = "angle-qdec-fallback") {
        defmt::warn!("angle from the DRV5032 hall quadrature (angle-qdec-fallback): NOT sufficient for the 3 %/revolution check");
        hal::angle::AngleSource::Qdec
    } else {
        match hal::tmag::Tmag::init(common.twispi0, io.i2c_sda, io.i2c_scl).await {
            Some(sensor) => hal::angle::AngleSource::Tmag { sensor, tracker: Default::default() },
            None => {
                // No sensor: `angle_read` must return None. A fault-parked source does exactly that.
                hal::angle::AngleSource::Missing
            }
        }
    };
    if cfg!(any(feature = "angle-qdec-fallback", feature = "coarse-qdec")) {
        spawner.spawn(hal::encoder::qdec_task(hal::encoder::new_qdec(common.qdec, io.hall_a, io.hall_b)).unwrap());
    }

    let drv = BoardIoDriver {
        dir: io.mot_dir,
        mode1: io.mot_mode1,
        mode2: io.mot_mode2,
        stby: io.mot_stby,
        en_fault: io.mot_en_fault,
        interlock: io.interlock.take(),
    };
    let (done_pin, wake_pin) = match io.watchdog.take() {
        Some(w) => (Some(w.done), Some(w.wake)),
        None => (None, None),
    };
    shared::DOCK_SIM.store(DOCK_SIM_INITIAL, core::sync::atomic::Ordering::Relaxed);
    let dock_pin = io.dock_n.take().filter(|_| !DOCK_FROM_SOFTWARE);
    let hal = BenchHal::new(stepper, adc, angle, drv, dock_pin, done_pin);
    if let Some(w) = wake_pin {
        spawner.spawn(hal::wake_task(embassy_nrf::gpio::Input::new(w, embassy_nrf::gpio::Pull::None)).unwrap());
    }

    // ---- pump + session ----
    let cal = boot.cal.cal();
    let evt_start = boot.evt_ceiling.max(1);
    let mut pump = Pump::new(hal, cal.as_ref(), RESERVOIR_CAPACITY, evt_start);
    let mut key_src = crypto::key_source();
    let mut session = crypto::make_session(&mut key_src);
    let bs = safety::BootState { seq_ceiling: boot.seq_ceiling, evt_ceiling: evt_start, reservoir: boot.reservoir, pod: boot.pod };
    safety::restore(&mut pump, &mut session, &bs);

    // ---- safety task on its own interrupt executor ----
    interrupt::EGU1_SWI1.set_priority(irqs::PRIO_SAFETY_EXECUTOR);
    let hp = EXECUTOR_SAFETY.start(interrupt::EGU1_SWI1);
    hp.spawn(safety::safety_task(pump, session, bs).unwrap());

    // ---- thread mode tasks ----
    spawner.spawn(
        ui::ui_task(common.pwm0, io.button, io.dock_sim_button.take(), io.led_status, io.led_alarm, io.buzzer).unwrap(),
    );
    spawner.spawn(storage::persist_task(settings).unwrap());
    static ALIGNED: StaticCell<AlignedBuffer<4>> = StaticCell::new();
    spawner.spawn(dfu::confirm_task(dfu::new_updater(flash, ALIGNED.init(AlignedBuffer([0; 4])))).unwrap());

    match sdc {
        Ok(sdc) => {
            let (address, name_bytes) = ble::device_address();
            static NAME: StaticCell<[u8; 14]> = StaticCell::new();
            let name_bytes: &'static [u8; 14] = NAME.init(name_bytes);
            let name = core::str::from_utf8(name_bytes).unwrap_or("OpenPatch");
            spawner.spawn(ble::ble_task(sdc, boot.bonds, address, name).unwrap());
        }
        Err(e) => defmt::error!("SDC init failed ({}): BLE disabled, the safety task keeps running", defmt::Debug2Format(&e)),
    }

    defmt::info!("all tasks started");
}
