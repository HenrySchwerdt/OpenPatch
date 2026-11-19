//! `sigtool gen|sign|verify|pubkey` for OpenPatch firmware images.
//!
//! Scheme (identical to `embassy_boot::FirmwareUpdater::verify_and_mark_updated`): the signature is
//! Ed25519 over the 64-byte SHA-512 digest of the image bytes. The manifest (76 bytes) is
//! `magic u32 | fmt u16 | reserved u16 | image_len u32 | signature [u8; 64]`, little endian, stored in
//! the manifest page of the DFU partition (see `layout/layout.rs`).
//!
//! The private key (32-byte seed) lives in `firmware-rs/keys/` (git-ignored). NEVER commit it.
#[path = "../../../layout/layout.rs"]
#[allow(dead_code)]
mod layout;

use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use sha2::{Digest, Sha512};
use std::{env, fs, io::Write, path::Path, process::exit};

const SECRET: &str = "ed25519-secret.bin";
const PUBLIC: &str = "ed25519-public.bin";

fn die(msg: &str) -> ! {
    eprintln!("sigtool: {msg}");
    exit(1)
}

fn usage() -> ! {
    eprintln!(
        "usage:\n  sigtool gen <keys-dir>                         create a new keypair (refuses to overwrite)\n  \
         sigtool pubkey <keys-dir>                      print the public key (hex)\n  \
         sigtool sign <keys-dir> <image.bin> <out-prefix>   writes <out-prefix>.manifest.bin and <out-prefix>.dfu.hex\n  \
         sigtool verify <keys-dir> <image.bin> <manifest.bin>"
    );
    exit(2)
}

fn load_signing(dir: &Path) -> SigningKey {
    let b = fs::read(dir.join(SECRET)).unwrap_or_else(|e| die(&format!("cannot read secret key: {e}")));
    let seed: [u8; 32] = b.try_into().unwrap_or_else(|_| die("secret key must be 32 bytes"));
    SigningKey::from_bytes(&seed)
}

fn load_public(dir: &Path) -> VerifyingKey {
    let b = fs::read(dir.join(PUBLIC)).unwrap_or_else(|e| die(&format!("cannot read public key: {e}")));
    let k: [u8; 32] = b.try_into().unwrap_or_else(|_| die("public key must be 32 bytes"));
    VerifyingKey::from_bytes(&k).unwrap_or_else(|e| die(&format!("bad public key: {e}")))
}

fn digest(image: &[u8]) -> [u8; 64] {
    let mut h = Sha512::new();
    h.update(image);
    h.finalize().into()
}

fn manifest(image_len: u32, sig: &[u8; 64]) -> [u8; layout::MANIFEST_LEN] {
    let mut m = [0u8; layout::MANIFEST_LEN];
    m[0..4].copy_from_slice(&layout::MANIFEST_MAGIC.to_le_bytes());
    m[4..6].copy_from_slice(&layout::MANIFEST_VERSION.to_le_bytes());
    m[8..12].copy_from_slice(&image_len.to_le_bytes());
    m[12..76].copy_from_slice(sig);
    m
}

fn ihex_record(out: &mut String, addr16: u16, rtype: u8, data: &[u8]) {
    let mut sum = (data.len() as u8).wrapping_add((addr16 >> 8) as u8).wrapping_add(addr16 as u8).wrapping_add(rtype);
    out.push_str(&format!(":{:02X}{:04X}{:02X}", data.len(), addr16, rtype));
    for b in data {
        out.push_str(&format!("{b:02X}"));
        sum = sum.wrapping_add(*b);
    }
    out.push_str(&format!("{:02X}\n", (!sum).wrapping_add(1)));
}

fn ihex_blob(out: &mut String, base: u32, data: &[u8]) {
    let mut cur_upper: Option<u16> = None;
    for (i, chunk) in data.chunks(16).enumerate() {
        let addr = base + (i * 16) as u32;
        let upper = (addr >> 16) as u16;
        if cur_upper != Some(upper) {
            ihex_record(out, 0, 0x04, &upper.to_be_bytes());
            cur_upper = Some(upper);
        }
        ihex_record(out, addr as u16, 0x00, chunk);
    }
}

fn main() {
    let a: Vec<String> = env::args().collect();
    match a.get(1).map(String::as_str) {
        Some("gen") if a.len() == 3 => {
            let dir = Path::new(&a[2]);
            fs::create_dir_all(dir).unwrap_or_else(|e| die(&e.to_string()));
            if dir.join(SECRET).exists() || dir.join(PUBLIC).exists() {
                die("a key already exists in that directory; refusing to overwrite");
            }
            let mut seed = [0u8; 32];
            getrandom::getrandom(&mut seed).unwrap_or_else(|e| die(&format!("no entropy: {e}")));
            let sk = SigningKey::from_bytes(&seed);
            let mut f = fs::File::create(dir.join(SECRET)).unwrap_or_else(|e| die(&e.to_string()));
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                f.set_permissions(fs::Permissions::from_mode(0o600)).ok();
            }
            f.write_all(&seed).unwrap_or_else(|e| die(&e.to_string()));
            fs::write(dir.join(PUBLIC), sk.verifying_key().to_bytes()).unwrap_or_else(|e| die(&e.to_string()));
            println!("created {}/{{{SECRET},{PUBLIC}}}. Keep the secret key private, never commit it.", dir.display());
        }
        Some("pubkey") if a.len() == 3 => {
            let k = load_public(Path::new(&a[2]));
            println!("{}", k.to_bytes().iter().map(|b| format!("{b:02x}")).collect::<String>());
        }
        Some("sign") if a.len() == 5 => {
            let sk = load_signing(Path::new(&a[2]));
            let image = fs::read(&a[3]).unwrap_or_else(|e| die(&format!("cannot read image: {e}")));
            if image.is_empty() || image.len() as u32 > layout::APP_SIZE {
                die(&format!("image size {} out of range (max {})", image.len(), layout::APP_SIZE));
            }
            let sig: Signature = sk.sign(&digest(&image));
            let m = manifest(image.len() as u32, &sig.to_bytes());
            fs::write(format!("{}.manifest.bin", a[4]), m).unwrap_or_else(|e| die(&e.to_string()));
            let mut hex = String::new();
            ihex_blob(&mut hex, layout::DFU_START, &image);
            ihex_blob(&mut hex, layout::DFU_START + layout::MANIFEST_OFFSET, &m);
            hex.push_str(":00000001FF\n");
            fs::write(format!("{}.dfu.hex", a[4]), hex).unwrap_or_else(|e| die(&e.to_string()));
            println!("signed {} bytes; manifest {}.manifest.bin, DFU hex {}.dfu.hex", image.len(), a[4], a[4]);
        }
        Some("verify") if a.len() == 5 => {
            let vk = load_public(Path::new(&a[2]));
            let image = fs::read(&a[3]).unwrap_or_else(|e| die(&e.to_string()));
            let m = fs::read(&a[4]).unwrap_or_else(|e| die(&e.to_string()));
            if m.len() != layout::MANIFEST_LEN || u32::from_le_bytes(m[0..4].try_into().unwrap()) != layout::MANIFEST_MAGIC {
                die("bad manifest");
            }
            if u32::from_le_bytes(m[8..12].try_into().unwrap()) as usize != image.len() {
                die("manifest length does not match the image");
            }
            let sig = Signature::from_bytes(m[12..76].try_into().unwrap());
            match vk.verify(&digest(&image), &sig) {
                Ok(()) => println!("signature OK"),
                Err(e) => die(&format!("signature INVALID: {e}")),
            }
        }
        _ => usage(),
    }
}
