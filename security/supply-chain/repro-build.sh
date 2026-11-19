#!/usr/bin/env bash
# Reproducible-build check for the bench firmware (and bootloader): build the same source twice with fresh target directories
# and compare SHA-256 of the images. TEST PROJECT, not a medical device.
#
# MEASURED (2026-11-19): identical when both builds use the SAME absolute source path (default here); NOT identical when the
# source path differs (DIFFERENT_PATHS=1), because cargo derives the `-C metadata` hash of path dependencies that live outside
# the workspace root (openpatch-core / -proto are `../` of openpatch-bench) from their absolute path, which changes symbol hashes
# and layout (16 byte size difference). `--remap-path-prefix` does not cover that. Release builds therefore run in a fixed
# directory (container `/build/firmware-rs`); the bootloader is reproducible even from different paths.
#
# Usage: security/supply-chain/repro-build.sh [path/to/firmware-rs] [workdir]
# Needs: rustup (thumbv7em-none-eabihf installed), flip-link, cargo-binutils (rust-objcopy). Exit 0 = identical.
#
# What makes it deterministic: --locked (Cargo.lock), pinned toolchain (rust-toolchain.toml / RUSTUP_TOOLCHAIN),
# --remap-path-prefix for the source tree, CARGO_HOME and RUSTUP_HOME, SOURCE_DATE_EPOCH, fresh CARGO_TARGET_DIR,
# identical feature set. The signing public key is compiled in (build.rs), so the same key file is used for both runs.
set -euo pipefail
FW="$(cd "${1:-$(dirname "$0")/../../firmware-rs}" && pwd)"
WORK="${2:-$(mktemp -d)}"
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1700000000}"
export CARGO_INCREMENTAL=0
CARGO_HOME_DIR="${CARGO_HOME:-$HOME/.cargo}"
RUSTUP_HOME_DIR="${RUSTUP_HOME:-$HOME/.rustup}"
FEATURES="${FEATURES:-board-bench-e73,drive-nfp-608-26-45-g15-12,angle-tmag}"

build_one() { # <n>
  local n="$1"
  local src="$WORK/run$n/firmware-rs"
  [ "${DIFFERENT_PATHS:-0}" = 1 ] || src="$WORK/src/firmware-rs"      # same absolute path for both builds
  rm -rf "$WORK/src"; mkdir -p "$WORK/run$n"
  # copy the sources (not target/), at a different path per run
  ( cd "$FW" && tar --exclude='./**/target' --exclude=target --exclude=.git -cf - . ) | ( mkdir -p "$src" && cd "$src" && tar -xf - )
  local remap=( "--remap-path-prefix=$src=/src" "--remap-path-prefix=$CARGO_HOME_DIR=/cargo" "--remap-path-prefix=$RUSTUP_HOME_DIR=/rustup" )
  # cargo MERGES rustflags arrays from the CLI with .cargo/config.toml (linker flags already live there): add only the extras.
  local flags='"-C","strip=none"'
  for r in "${remap[@]}"; do flags="$flags,\"$r\""; done
  local cfg="target.thumbv7em-none-eabihf.rustflags=[$flags]"
  ( cd "$src/openpatch-bench" && CARGO_TARGET_DIR="$WORK/run$n/target-app" \
      cargo build --release --locked --no-default-features --features "$FEATURES" --config "$cfg" )
  ( cd "$src/openpatch-bootloader" && CARGO_TARGET_DIR="$WORK/run$n/target-boot" \
      cargo build --release --locked --features board-bench-e73 --config "$cfg" 2>/dev/null \
    || CARGO_TARGET_DIR="$WORK/run$n/target-boot" cargo build --release --locked --config "$cfg" )
  cp "$WORK/run$n/target-app/thumbv7em-none-eabihf/release/openpatch-bench" "$WORK/run$n/app.elf"
  cp "$WORK/run$n/target-boot/thumbv7em-none-eabihf/release/openpatch-bootloader" "$WORK/run$n/boot.elf"
  rust-objcopy -O binary "$WORK/run$n/app.elf" "$WORK/run$n/app.bin"
  rust-objcopy -O binary "$WORK/run$n/boot.elf" "$WORK/run$n/boot.bin"
}

build_one 1
build_one 2
status=0
for f in app.elf app.bin boot.elf boot.bin; do
  a=$(sha256sum "$WORK/run1/$f" | cut -d' ' -f1); b=$(sha256sum "$WORK/run2/$f" | cut -d' ' -f1)
  if [ "$a" = "$b" ]; then echo "REPRODUCIBLE  $f  $a"; else echo "DIFFERENT     $f  run1=$a run2=$b"; status=1; fi
done
echo "workdir: $WORK"
exit $status
