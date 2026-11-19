#!/usr/bin/env bash
# Sign an application image for the OpenPatch bootloader.
#   sign-image.sh <app.elf | app.bin> [out-prefix]
# Writes <out-prefix>.manifest.bin (76 byte manifest: magic, length, ed25519 signature over the
# SHA-512 digest of the image) and <out-prefix>.dfu.hex (image at the DFU partition address and
# manifest at its manifest page, ready for `probe-rs download --format hex` during development).
# Uses the secret key in keys/ (override with KEYS_DIR). Never commit the key.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEYS_DIR="${KEYS_DIR:-$ROOT/keys}"
IN="${1:?usage: sign-image.sh <app.elf|app.bin> [out-prefix]}"
OUT="${2:-${IN%.*}}"
if [[ ! -f "$KEYS_DIR/ed25519-secret.bin" ]]; then
  echo "no signing key in $KEYS_DIR: run scripts/gen-signing-key.sh first" >&2
  exit 1
fi
BIN="$IN"
if [[ "$IN" != *.bin ]]; then
  BIN="$OUT.bin"
  rust-objcopy -O binary "$IN" "$BIN"
fi
cargo build --release --quiet --manifest-path "$ROOT/tools/sigtool/Cargo.toml"
"$ROOT/tools/sigtool/target/release/sigtool" sign "$KEYS_DIR" "$BIN" "$OUT"
"$ROOT/tools/sigtool/target/release/sigtool" verify "$KEYS_DIR" "$BIN" "$OUT.manifest.bin"
