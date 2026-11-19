//! Firmware update state handling (embassy-boot `FirmwareUpdater`). The DFU TRANSPORT (BLE or
//! file based) is out of scope; what is implemented:
//!
//! * the updater over the DFU and STATE partitions of the shared layout (`layout/layout.rs`),
//!   sharing the MPSL timeslot flash with the settings,
//! * [`confirm_task`]: after the safety task ran `BOOT_OK_TICKS` good ticks the new image is
//!   confirmed with `mark_booted`. If the image crashes or hangs before that, the bootloader
//!   reverts to the previous image on the next reset (the TPL5010 reset on the bench board),
//! * [`finalize`]: verifies the ed25519 signature of the image in DFU against the public key
//!   compiled in (`keys/ed25519-public.bin`, see docs/bootloader.md) and arms the swap. The DFU
//!   transport must call it only while delivery is suspended (protocol section 1).
use embassy_boot::{AlignedBuffer, FirmwareUpdater, FirmwareUpdaterConfig, FirmwareUpdaterError, State};
use embassy_embedded_hal::flash::partition::Partition;

use crate::layout;
use crate::shared::BOOT_OK;
use crate::storage::{FlashMutex, Part};

mod pubkey {
    include!(concat!(env!("OUT_DIR"), "/pubkey.rs"));
}

pub type Updater = FirmwareUpdater<'static, Part, Part>;

pub fn new_updater(flash: &'static FlashMutex, aligned: &'static mut AlignedBuffer<4>) -> Updater {
    let cfg = FirmwareUpdaterConfig {
        dfu: Partition::new(flash, layout::DFU_START, layout::DFU_SIZE),
        state: Partition::new(flash, layout::STATE_START, layout::STATE_SIZE),
    };
    FirmwareUpdater::new(cfg, &mut aligned.0)
}

/// Verify the image of `image_len` bytes in DFU against `signature` (Ed25519 over the SHA-512
/// digest) and mark it for the next boot. Fails closed without a compiled-in key.
#[allow(dead_code)]
pub async fn finalize(u: &mut Updater, signature: &[u8; 64], image_len: u32) -> Result<(), FirmwareUpdaterError> {
    let Some(pk) = pubkey::PUBLIC_KEY else {
        defmt::error!("DFU refused: no signing public key compiled in");
        return Err(FirmwareUpdaterError::Signature(Default::default()));
    };
    u.verify_and_mark_updated(&pk, signature, image_len).await
}

#[embassy_executor::task]
pub async fn confirm_task(mut u: Updater) -> ! {
    let state = u.get_state().await;
    match state {
        Ok(State::Swap) => defmt::info!("DFU: new image is on trial, confirming after {} good ticks", crate::config::BOOT_OK_TICKS),
        Ok(State::Revert) => defmt::warn!("DFU: the previous update was REVERTED (not confirmed in time)"),
        Ok(_) => {}
        Err(_) => defmt::error!("DFU: cannot read the boot state"),
    }
    BOOT_OK.wait().await;
    if matches!(state, Ok(State::Swap) | Ok(State::Revert)) {
        match u.mark_booted().await {
            Ok(()) => defmt::info!("DFU: image confirmed (mark_booted)"),
            Err(_) => defmt::error!("DFU: mark_booted failed"),
        }
    }
    core::future::pending::<()>().await;
    unreachable!()
}
