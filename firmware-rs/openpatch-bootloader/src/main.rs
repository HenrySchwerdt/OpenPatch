//! OpenPatch bootloader for the nRF52840 (embassy-boot-nrf). TEST PROJECT, never to be worn.
//!
//! Boot flow (see `firmware-rs/docs/bootloader.md`):
//! 1. If the state partition requests a swap and no swap progress exists yet ("pending update"),
//!    the ed25519 signature of the image in DFU is verified against the compiled-in public key
//!    (defense in depth: the application's `FirmwareUpdater::verify_and_mark_updated` already
//!    verified before arming the swap). An invalid pending update is cancelled.
//! 2. `embassy_boot_nrf::BootLoader::prepare` performs the power-fail-safe swap, or the revert of a
//!    trial boot that was not confirmed by the application (`mark_booted`).
//! 3. Jump to the application in ACTIVE.
//!
//! No `unsafe` besides the final jump (inside `BootLoader::load`).
#![no_std]
#![no_main]

#[path = "../../layout/layout.rs"]
mod layout;
mod pubkey {
    include!(concat!(env!("OUT_DIR"), "/pubkey.rs"));
}

use core::cell::RefCell;

use embassy_boot::{BlockingFirmwareState, BootLoaderConfig, State};
use embassy_boot_nrf::BootLoader;
#[cfg(feature = "board-bench-e73")]
use embassy_nrf::gpio::Output;
use embassy_nrf::nvmc::Nvmc;
use embassy_sync::blocking_mutex::raw::NoopRawMutex;
use embassy_sync::blocking_mutex::Mutex;
use embedded_storage::nor_flash::{ErrorType, NorFlash, ReadNorFlash};
use panic_reset as _;

/// Flash wrapper for the DFU swap. The Rev A controller QUALIFIES the TPL5010 DONE edge in hardware (INTERLOCK.md B): a DONE
/// rising edge counts only while WAKE is high, i.e. within 20 ms after the WAKE rising edge. A blind pulse before every erase
/// (the old scheme) is rejected, and a CPU that is stalled in a 85 ms page erase can not answer a WAKE in time. The swap
/// therefore answers WAKE entirely in HARDWARE for its whole duration (`done_path`): WAKE edge -> GPIOTE -> PPI -> DONE set,
/// TIMER1 compare 3 us later -> DONE clear, no CPU involved. The path is armed for the swap only and disarmed before the
/// application starts (the application arms its own, permit gated, path in `hal/wdt.rs`).
struct KickFlash<F> {
    flash: F,
}

#[cfg(feature = "board-bench-e73")]
mod done_path {
    //! Raw nRF52840 register map (GPIOTE 0x4000_6000, TIMER1 0x4000_9000, PPI 0x4001_F000), all addresses from the product
    //! specification; the bootloader has no other user of these peripherals.
    const GPIOTE: u32 = 0x4000_6000;
    const TIMER1: u32 = 0x4000_9000;
    const PPI: u32 = 0x4001_F000;
    /// P0.17 WDT_WAKE, P0.28 WDT_DONE.
    const WAKE_PIN: u32 = 17;
    const DONE_PIN: u32 = 28;

    unsafe fn w(addr: u32, v: u32) {
        (addr as *mut u32).write_volatile(v);
    }

    /// Arm the WAKE -> DONE hardware path.
    pub fn arm() {
        // SAFETY: fixed, valid peripheral registers; nothing else in the bootloader uses them.
        unsafe {
            // GPIOTE ch0: event on WAKE, LoToHi; ch1: DONE output task (SET / CLR), initial low
            w(GPIOTE + 0x510, 1 | (WAKE_PIN << 8) | (1 << 16));
            w(GPIOTE + 0x514, 3 | (DONE_PIN << 8) | (3 << 16));
            // TIMER1: 16 MHz, 16 bit, CC0 = 48 ticks = 3 us (qualifier needs >= 2 us), compare 0 clears and stops
            w(TIMER1 + 0x504, 0); // MODE = timer
            w(TIMER1 + 0x508, 0); // BITMODE = 16 bit
            w(TIMER1 + 0x510, 0); // PRESCALER = 0
            w(TIMER1 + 0x540, 48);
            w(TIMER1 + 0x200, (1 << 0) | (1 << 8)); // COMPARE0_CLEAR | COMPARE0_STOP
            // PPI ch0: WAKE event -> DONE set, fork -> TIMER1 start; ch1: TIMER1 compare0 -> DONE clear
            w(PPI + 0x510, GPIOTE + 0x100);
            w(PPI + 0x514, GPIOTE + 0x030 + 4);
            w(PPI + 0x910, TIMER1);
            w(PPI + 0x518, TIMER1 + 0x140);
            w(PPI + 0x51C, GPIOTE + 0x060 + 4);
            w(PPI + 0x504, 0b11); // CHENSET ch0, ch1
        }
    }

    /// Disarm before the application runs.
    pub fn disarm() {
        // SAFETY: as above.
        unsafe {
            w(PPI + 0x508, 0b11); // CHENCLR
            w(TIMER1 + 0x004, 1); // STOP
            w(GPIOTE + 0x510, 0);
            w(GPIOTE + 0x514, 0);
        }
    }
}

#[cfg(not(feature = "board-bench-e73"))]
mod done_path {
    pub fn arm() {}
    pub fn disarm() {}
}

impl<F: ErrorType> ErrorType for KickFlash<F> {
    type Error = F::Error;
}
impl<F: ReadNorFlash> ReadNorFlash for KickFlash<F> {
    const READ_SIZE: usize = F::READ_SIZE;
    fn read(&mut self, offset: u32, bytes: &mut [u8]) -> Result<(), Self::Error> {
        self.flash.read(offset, bytes)
    }
    fn capacity(&self) -> usize {
        self.flash.capacity()
    }
}
impl<F: NorFlash> NorFlash for KickFlash<F> {
    const WRITE_SIZE: usize = F::WRITE_SIZE;
    const ERASE_SIZE: usize = F::ERASE_SIZE;
    fn erase(&mut self, from: u32, to: u32) -> Result<(), Self::Error> {
        self.flash.erase(from, to)
    }
    fn write(&mut self, offset: u32, bytes: &[u8]) -> Result<(), Self::Error> {
        self.flash.write(offset, bytes)
    }
}

/// Outcome of the pre-swap check.
#[derive(PartialEq, Eq)]
enum Pending {
    /// No update pending, or a swap/revert is already in progress: hand over to embassy-boot.
    NotPending,
    /// Pending update with a valid signature.
    Valid,
    /// Pending update that must not be installed.
    Invalid,
}

type Flash = KickFlash<Nvmc<'static>>;
type Shared = Mutex<NoopRawMutex, RefCell<Flash>>;

fn check_pending(flash: &'static Shared) -> Pending {
    let mut aligned = embassy_boot::AlignedBuffer([0u8; 256]);
    let cfg = BootLoaderConfig::from_linkerfile_blocking(flash, flash, flash);
    let mut state_part = cfg.state;
    let mut dfu = cfg.dfu;

    // Swap requested? (public API of embassy-boot)
    let mut probe = [0u8; 4];
    if state_part.read(0, &mut probe).is_err() {
        return Pending::Invalid;
    }
    let cfg2 = BootLoaderConfig::from_linkerfile_blocking(flash, flash, flash);
    let state = embassy_boot::BootLoader::new(cfg2).read_state(&mut aligned.0);
    if !matches!(state, Ok(State::Swap)) {
        return Pending::NotPending;
    }
    // Swap progress word 0 (state partition layout: magic | progress validity | progress...). Erased
    // (0xFF) = the swap has not started yet, i.e. this is a PENDING update, not a trial boot.
    let mut progress = [0u8; 4];
    if state_part.read(2 * 4, &mut progress).is_err() {
        return Pending::Invalid;
    }
    if progress != [0xFF; 4] {
        return Pending::NotPending;
    }

    let Some(pk) = pubkey::PUBLIC_KEY else { return Pending::Invalid };

    // Manifest page: magic u32 | fmt u16 | reserved u16 | image_len u32 | signature [u8; 64]
    let mut m = [0u8; layout::MANIFEST_LEN];
    if dfu.read(layout::MANIFEST_OFFSET, &mut m).is_err() {
        return Pending::Invalid;
    }
    let magic = u32::from_le_bytes([m[0], m[1], m[2], m[3]]);
    let len = u32::from_le_bytes([m[8], m[9], m[10], m[11]]);
    if magic != layout::MANIFEST_MAGIC || len == 0 || len > layout::APP_SIZE {
        return Pending::Invalid;
    }
    let mut sig = [0u8; 64];
    sig.copy_from_slice(&m[12..76]);

    let mut hasher = salty::Sha512::new();
    let mut off = 0u32;
    while off < len {
        let n = core::cmp::min(aligned.0.len() as u32, len - off) as usize;
        if dfu.read(off, &mut aligned.0[..n]).is_err() {
            return Pending::Invalid;
        }
        hasher.update(&aligned.0[..n]);
        off += n as u32;
    }
    let digest = hasher.finalize();

    let Ok(public_key) = salty::PublicKey::try_from(&pk) else { return Pending::Invalid };
    let Ok(signature) = salty::Signature::try_from(&sig);
    if public_key.verify(&digest, &signature).is_ok() {
        Pending::Valid
    } else {
        Pending::Invalid
    }
}

#[cortex_m_rt::entry]
fn main() -> ! {
    let p = embassy_nrf::init(Default::default());

    // WDT_DONE idles LOW (the qualifier needs a clean rising edge); the pulse itself comes from the hardware path.
    #[cfg(feature = "board-bench-e73")]
    let _done = Output::new(p.P0_28, embassy_nrf::gpio::Level::Low, embassy_nrf::gpio::OutputDrive::Standard);
    #[cfg(not(any(feature = "board-bench-e73", feature = "board-nrf52840-dk")))]
    compile_error!("enable exactly one board feature");
    done_path::arm();

    let flash: &'static Shared = {
        static CELL: static_cell_shim::Cell<Shared> = static_cell_shim::Cell::new();
        CELL.init(Mutex::new(RefCell::new(KickFlash { flash: Nvmc::new(p.NVMC) })))
    };

    if check_pending(flash) == Pending::Invalid {
        // Cancel: never install an update that does not carry a valid signature.
        let cfg = BootLoaderConfig::from_linkerfile_blocking(flash, flash, flash);
        let mut aligned = embassy_boot::AlignedBuffer([0u8; 4]);
        let mut st = BlockingFirmwareState::new(cfg.state, &mut aligned.0);
        let _ = st.mark_booted();
    }

    let cfg = BootLoaderConfig::from_linkerfile_blocking(flash, flash, flash);
    let active_offset = cfg.active.offset();
    let bl: BootLoader = BootLoader::prepare(cfg);
    done_path::disarm();
    // SAFETY: ACTIVE holds a vector table (linked at ACTIVE_START); `load` sets VTOR/MSP and jumps.
    unsafe { bl.load(active_offset) }
}

/// Minimal `static` once-cell (no extra dependency, single-threaded bootloader).
mod static_cell_shim {
    use core::cell::UnsafeCell;
    use core::mem::MaybeUninit;

    pub struct Cell<T>(UnsafeCell<MaybeUninit<T>>);
    // SAFETY: only used once from `main` before anything else runs.
    unsafe impl<T> Sync for Cell<T> {}
    impl<T> Cell<T> {
        pub const fn new() -> Self {
            Self(UnsafeCell::new(MaybeUninit::uninit()))
        }
        pub fn init(&'static self, v: T) -> &'static T {
            // SAFETY: called exactly once.
            unsafe { (*self.0.get()).write(v) }
        }
    }
}
