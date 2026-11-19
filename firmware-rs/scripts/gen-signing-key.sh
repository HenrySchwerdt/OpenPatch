#!/usr/bin/env bash
# Generate the ed25519 firmware signing keypair into firmware-rs/keys/ (git-ignored).
#   keys/ed25519-secret.bin  32 byte seed   PRIVATE: never commit, never share, back it up offline
#   keys/ed25519-public.bin  32 byte public key (compiled into the bootloader and the app updater)
# Refuses to overwrite an existing key. Override the directory with KEYS_DIR.
# TEST PROJECT: the signature protects the bench firmware only; the device is never worn.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEYS_DIR="${KEYS_DIR:-$ROOT/keys}"
cargo build --release --quiet --manifest-path "$ROOT/tools/sigtool/Cargo.toml"
"$ROOT/tools/sigtool/target/release/sigtool" gen "$KEYS_DIR"
echo "public key: $("$ROOT/tools/sigtool/target/release/sigtool" pubkey "$KEYS_DIR")"
echo "Rebuild the bootloader and the app so that they embed this key (scripts/build.sh)."
