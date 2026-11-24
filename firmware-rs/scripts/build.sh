#!/usr/bin/env bash
# Build the bootloader and both application configurations (release) and print the sizes.
#   scripts/build.sh            production-like (no dev-plaintext)
#   scripts/build.sh --dev      additionally enables `dev-plaintext` (bench use only)
# Outputs: openpatch-bench/target/{e73,dk}/..., openpatch-bootloader/target/..., images in
# openpatch-bench/target/images/ (raw .bin of each app configuration).
# TEST PROJECT: never to be worn, bench tests with WATER ONLY.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTRA=""
[[ "${1:-}" == "--dev" ]] && EXTRA=",dev-plaintext"
# No implicit drive default in the app: pass it explicitly. Matrix: bench-e73 and nrf52840-dk, NFP-608-26.45 + miter pair 1:1 into the cup plunger (v0.1.0 cup pod, the current CAD) + a syringe rig build on the DK.
# Bench variants (NOT the cup pod): DRIVE=drive-nfp-608-26-45-g16-20 | drive-nfp-608-26-45-g15-12 | drive-nfp-608-26-45-g1-1 | drive-syringe-rig-1ml | drive-zwbpd006006-6-43 | drive-zwbpd006006-4-8 | drive-faulhaber-adm0620-16
DRIVE="${DRIVE:-drive-nfp-608-26-45-cup-miter-1-1}"
# Angle source: angle-tmag (default) or angle-qdec-fallback (NOT sufficient for the 3 %/turn check).
ANGLE="${ANGLE:-angle-tmag}"

echo "== drive guard (exactly one drive feature)"
"$ROOT/scripts/check-drive-guard.sh"

echo "== bootloader"
( cd "$ROOT/openpatch-bootloader" && cargo build --release )
rust-size "$ROOT/openpatch-bootloader/target/thumbv7em-none-eabihf/release/openpatch-bootloader"
echo "== bootloader (cup pod v4)"
( cd "$ROOT/openpatch-bootloader" && cargo build --release --target-dir target/cup --no-default-features --features board-cup-v4 )
rust-size "$ROOT/openpatch-bootloader/target/cup/thumbv7em-none-eabihf/release/openpatch-bootloader"

mkdir -p "$ROOT/openpatch-bench/target/images"
build_app() { # <name> <board feature> [drive override]
  local name="$1" board="$2" DRIVE="${3:-$DRIVE}"
  echo "== app: $name ($board, $DRIVE, $ANGLE$EXTRA)"
  ( cd "$ROOT/openpatch-bench" && \
    cargo build --release --target-dir "target/$name" --no-default-features --features "$board,$DRIVE,$ANGLE$EXTRA" )
  local elf="$ROOT/openpatch-bench/target/$name/thumbv7em-none-eabihf/release/openpatch-bench"
  rust-size "$elf"
  rust-objcopy -O binary "$elf" "$ROOT/openpatch-bench/target/images/openpatch-bench-$name.bin"
  ls -l "$ROOT/openpatch-bench/target/images/openpatch-bench-$name.bin" | awk '{print "image bytes:", $5}'
}
build_app e73 board-bench-e73
build_app dk board-nrf52840-dk
# cup pod v4 (HJ-840, 2 x DRV8838, STM32C011 supervisor): the pump application on the integrated board (angle-tmag only)
ANGLE=angle-tmag build_app cup board-cup-v4
# bench rig: NFP direct on a 1 ml U100 syringe, software DOCKED (DK only); draw capable
build_app rig board-nrf52840-dk,dock-simulated drive-syringe-rig-1ml
echo "done. Flash: probe-rs download --chip nRF52840_xxAA <bootloader elf>, then the app elf (see docs/bootloader.md)."
