//! Transport independent DFU receiver rules (USB DFU class, BLE or file): the transport hands over blocks, this decides whether they are
//! acceptable and where they go. It writes ONLY into the DFU partition through the [`Sink`], never arms a swap and knows no keys:
//! arming needs an `ArmToken` from `verify::verify_pending`.
//!
//! Sequence: `start` -> `image_block`* (strictly sequential from offset 0) -> `manifest` (exactly once, last; the image length in the
//! manifest must equal the bytes received) -> `Complete`. Any error aborts the transfer (state `Failed`); a new `start` is needed.

use crate::manifest::{Manifest, ManifestError, MANIFEST_LEN};

/// Writes into the DFU partition. `offset` is relative to the partition start.
pub trait Sink {
    fn write(&mut self, offset: u32, data: &[u8]) -> bool;
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DfuError {
    /// Not in the right state for this call (not started, manifest already received, failed).
    State,
    /// Block offset is not the next expected one.
    Offset,
    /// More than the application window.
    TooLarge,
    /// Empty block.
    Empty,
    Manifest(ManifestError),
    /// Manifest length differs from the bytes received.
    LengthMismatch,
    /// The sink refused the write.
    Sink,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RxState {
    Idle,
    Receiving,
    Complete,
    Failed,
}

pub struct DfuReceiver {
    state: RxState,
    received: u32,
    max_image: u32,
    manifest_offset: u32,
}

impl DfuReceiver {
    /// `max_image`: the application window (`APP_SIZE`); `manifest_offset`: where the manifest page starts in the partition.
    pub const fn new(max_image: u32, manifest_offset: u32) -> Self {
        Self { state: RxState::Idle, received: 0, max_image, manifest_offset }
    }

    pub fn state(&self) -> RxState {
        self.state
    }
    pub fn received(&self) -> u32 {
        self.received
    }

    /// (Re)start a transfer. Allowed from every state: it forgets what came before.
    pub fn start(&mut self) {
        self.state = RxState::Receiving;
        self.received = 0;
    }

    fn fail<T>(&mut self, e: DfuError) -> Result<T, DfuError> {
        self.state = RxState::Failed;
        Err(e)
    }

    pub fn image_block<S: Sink>(&mut self, offset: u32, data: &[u8], sink: &mut S) -> Result<(), DfuError> {
        if self.state != RxState::Receiving {
            return Err(DfuError::State);
        }
        if data.is_empty() {
            return self.fail(DfuError::Empty);
        }
        if offset != self.received {
            return self.fail(DfuError::Offset);
        }
        let end = match offset.checked_add(data.len() as u32) {
            Some(e) if e <= self.max_image => e,
            _ => return self.fail(DfuError::TooLarge),
        };
        if !sink.write(offset, data) {
            return self.fail(DfuError::Sink);
        }
        self.received = end;
        Ok(())
    }

    /// The manifest, last. Parsed and cross-checked with the received length, then written to the manifest page.
    pub fn manifest<S: Sink>(&mut self, bytes: &[u8], sink: &mut S) -> Result<Manifest, DfuError> {
        if self.state != RxState::Receiving {
            return Err(DfuError::State);
        }
        if bytes.len() != MANIFEST_LEN {
            return self.fail(DfuError::Manifest(ManifestError::Length));
        }
        let m = match Manifest::parse(bytes) {
            Ok(m) => m,
            Err(e) => return self.fail(DfuError::Manifest(e)),
        };
        if m.image_len != self.received {
            return self.fail(DfuError::LengthMismatch);
        }
        if !sink.write(self.manifest_offset, bytes) {
            return self.fail(DfuError::Sink);
        }
        self.state = RxState::Complete;
        Ok(m)
    }

    /// Ready for `verify_pending`.
    pub fn is_complete(&self) -> bool {
        self.state == RxState::Complete
    }
}
