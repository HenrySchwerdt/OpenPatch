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
    // the rollback minimum comes from the one-way store; a damaged store refuses (after the cheap manifest / key / size checks)
    let m = precheck(manifest_bytes, ctx.verifier.is_some(), ctx.hw_id, ctx.max_image)?;
    let minimum = min_version(ctx.counter_slots).map_err(Reject::Counter)?;
    let v = check_rest::<H, V, S>(&m, src, ctx.verifier, minimum)?;
    Ok(ArmToken { version: v.version, image_len: v.image_len })
}

/// Everything [`verify_image`] needs besides the image: for images that are not the nRF application (the STM32C011 supervisor).
pub struct ImageContext<'a, V: SigCheck> {
    /// `None` = no key compiled in (fail closed).
    pub verifier: Option<&'a V>,
    pub hw_id: u32,
    pub max_image: u32,
    /// Lowest acceptable security version (the version of the image installed now, or a stored floor): older is a downgrade.
    pub min_version: u32,
}

/// A verified image: version, length and the SIGNED digest `SHA-512("OPFW2" || header || image)`. A flasher recomputes the digest
/// over the bytes it really sends and reads back and compares it with this one (closes the gap between "verified" and "written").
/// Cannot be constructed outside [`verify_image`].
#[derive(Debug, PartialEq, Eq)]
pub struct VerifiedImage {
    version: u32,
    image_len: u32,
    digest: [u8; 64],
}

impl VerifiedImage {
    pub fn version(&self) -> u32 {
        self.version
    }
    pub fn image_len(&self) -> u32 {
        self.image_len
    }
    pub fn digest(&self) -> &[u8; 64] {
        &self.digest
    }
}

/// Same rules as [`verify_pending`] (manifest format 2, key, size, hardware id, rollback, signature) with an explicit minimum version.
pub fn verify_image<H: Digest512, V: SigCheck, S: ImageSource>(
    manifest_bytes: &[u8],
    src: &mut S,
    ctx: &ImageContext<'_, V>,
) -> Result<VerifiedImage, Reject> {
    let m = precheck(manifest_bytes, ctx.verifier.is_some(), ctx.hw_id, ctx.max_image)?;
    check_rest::<H, V, S>(&m, src, ctx.verifier, ctx.min_version)
}

/// The signed digest of `image` under the manifest `m` (the message the Ed25519 signature covers).
pub fn signed_digest<H: Digest512>(m: &Manifest, image: &[u8]) -> [u8; 64] {
    let mut h = digest_start::<H>(m);
    h.update(image);
    h.finish()
}

/// A hasher primed with the domain and the header of `m`: feed the image bytes, then `finish` gives the signed digest.
pub fn digest_start<H: Digest512>(m: &Manifest) -> H {
    let mut h = H::new();
    h.update(DOMAIN);
    h.update(&m.header());
    h
}

fn precheck(manifest_bytes: &[u8], has_key: bool, hw_id: u32, max_image: u32) -> Result<Manifest, Reject> {
    let m = Manifest::parse(manifest_bytes).map_err(Reject::Manifest)?;
    if !has_key {
        return Err(Reject::NoKey);
    }
    if m.image_len > max_image {
        return Err(Reject::TooLarge);
    }
    if m.hw_id != hw_id {
        return Err(Reject::WrongHardware { got: m.hw_id });
    }
    Ok(m)
}

fn check_rest<H: Digest512, V: SigCheck, S: ImageSource>(
    m: &Manifest,
    src: &mut S,
    verifier: Option<&V>,
    minimum: u32,
) -> Result<VerifiedImage, Reject> {
    let Some(verifier) = verifier else { return Err(Reject::NoKey) };
    if m.version < minimum {
        return Err(Reject::Rollback { version: m.version, minimum });
    }
    let mut h = digest_start::<H>(m);
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
        Ok(VerifiedImage { version: m.version, image_len: m.image_len, digest })
    } else {
        Err(Reject::BadSignature)
    }
}
