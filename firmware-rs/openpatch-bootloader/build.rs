//! Generates `memory.x` from the shared layout and embeds the ed25519 public key (if present).
//!
//! Key lookup order: env `OPENPATCH_SIGNING_PUBKEY` (path), then `../keys/ed25519-public.bin`
//! (32 raw bytes). Without a key the bootloader is built "fail closed": a pending update is never
//! accepted (see `docs/bootloader.md`). The PRIVATE key is never read here.
#[path = "../layout/layout.rs"]
mod layout;

use std::{env, fs, path::PathBuf};

fn main() {
    let out = PathBuf::from(env::var_os("OUT_DIR").unwrap());
    fs::write(out.join("memory.x"), layout::memory_x(layout::Target::Bootloader)).unwrap();
    println!("cargo::rustc-link-search={}", out.display());
    println!("cargo::rerun-if-changed=../layout/layout.rs");

    println!("cargo::rerun-if-env-changed=OPENPATCH_SIGNING_PUBKEY");
    let key_path = env::var_os("OPENPATCH_SIGNING_PUBKEY")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("../keys/ed25519-public.bin"));
    println!("cargo::rerun-if-changed={}", key_path.display());
    let src = match fs::read(&key_path) {
        Ok(k) if k.len() == 32 => {
            let bytes: Vec<String> = k.iter().map(|b| format!("0x{b:02X}")).collect();
            format!("pub const PUBLIC_KEY: Option<[u8; 32]> = Some([{}]);\n", bytes.join(", "))
        }
        Ok(k) => panic!("{}: public key must be exactly 32 bytes, got {}", key_path.display(), k.len()),
        Err(_) => {
            println!("cargo::warning=no ed25519 public key found: bootloader built FAIL-CLOSED (updates refused)");
            "pub const PUBLIC_KEY: Option<[u8; 32]> = None;\n".to_string()
        }
    };
    fs::write(out.join("pubkey.rs"), src).unwrap();
}
