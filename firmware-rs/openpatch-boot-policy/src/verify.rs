//! Verify-before-swap.
use crate::counter::{min_version, CounterError, SLOTS};
use crate::manifest::{Manifest, ManifestError, DOMAIN};

/// SHA-512, streaming (the bootloader implements it with salty, the host tests with sha2).
pub trait Digest512: Sized {
    fn new() -> Self;
    fn update(&mut self, data: &[u8]);
    fn finish(self) -> [u8; 64];
}

/// Ed25519 verification of a 64-byte message (the digest) against the compiled-in public key.
pub trait SigCheck {
    fn verify(&self, digest: &[u8; 64], signature: &[u8; 64]) -> bool;
}

/// Read access to the image in the DFU partition.
pub trait ImageSource {
    /// Fill `buf` from `offset`; false = read error.
    fn read(&mut self, offset: u32, buf: &mut [u8]) -> bool;
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Reject {
    Manifest(ManifestError),
    /// No public key compiled in.
    NoKey,
    /// `image_len` above the application window.
    TooLarge,
    WrongHardware { got: u32 },
    Rollback { version: u32, minimum: u32 },
    /// The rollback counter is damaged: fail closed.
    Counter(CounterError),
    ReadError,
    BadSignature,
}

/// The only proof that an image may be installed. Cannot be constructed outside [`verify_pending`].
#[derive(Debug, PartialEq, Eq)]
pub struct ArmToken {
    version: u32,
    image_len: u32,
}

impl ArmToken {
    pub fn version(&self) -> u32 {
        self.version
    }
    pub fn image_len(&self) -> u32 {
        self.image_len
    }
}

/// Everything the check needs besides the image.
pub struct Context<'a, V: SigCheck> {
    /// `None` = no key compiled in (fail closed).
    pub verifier: Option<&'a V>,
    pub hw_id: u32,
    /// Largest image (the application window without the manifest page).
    pub max_image: u32,
    /// The rollback store.
    pub counter_slots: &'a [u32; SLOTS],
}

/// Check a pending update: manifest, key, size, hardware, rollback, then the signature over the whole image. The order is cheap
/// checks first; the signature (SHA-512 over up to 472 KB) runs only for a plausible candidate.
pub fn verify_pending<H: Digest512, V: SigCheck, S: ImageSource>(
    manifest_bytes: &[u8],
    src: &mut S,
    ctx: &Context<'_, V>,
) -> Result<ArmToken, Reject> {
    let m = Manifest::parse(manifest_bytes).map_err(Reject::Manifest)?;
    let Some(verifier) = ctx.verifier else { return Err(Reject::NoKey) };
    if m.image_len > ctx.max_image {
        return Err(Reject::TooLarge);
    }
    if m.hw_id != ctx.hw_id {
        return Err(Reject::WrongHardware { got: m.hw_id });
    }
    let minimum = min_version(ctx.counter_slots).map_err(Reject::Counter)?;
    if m.version < minimum {
        return Err(Reject::Rollback { version: m.version, minimum });
    }
    let mut h = H::new();
    h.update(DOMAIN);
    h.update(&m.header());
    let mut buf = [0u8; 256];
    let mut off = 0u32;
    while off < m.image_len {
        let n = core::cmp::min(buf.len() as u32, m.image_len - off) as usize;
        if !src.read(off, &mut buf[..n]) {
            return Err(Reject::ReadError);
        }
        h.update(&buf[..n]);
        off += n as u32;
    }
    let digest = h.finish();
    if verifier.verify(&digest, &m.signature) {
        Ok(ArmToken { version: m.version, image_len: m.image_len })
    } else {
        Err(Reject::BadSignature)
    }
}
