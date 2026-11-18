#!/usr/bin/env bash
# Build the OpenPatch firmware with MCUboot (sysbuild) for the Rev A board and/or the nRF52840-DK.
# Usage: firmware/scripts/build.sh [reva|dk|all] [--dev] [--pristine]
#   reva  : openpatch_reva/nrf52840   (default: production-like, plaintext frames rejected)
#   dk    : nrf52840dk/nrf52840       (always built with dev.conf: plaintext + simulated encoder/battery)
#   --dev : also apply dev.conf to the reva build (bench pod WITHOUT insulin only)
# Environment overrides: NCS_ROOT (~/ncs/v3.4.2), NCS_VENV (~/ncs/venv), ZEPHYR_SDK_INSTALL_DIR (~/zephyr-sdk-1.0.1)
set -euo pipefail

FW="$(cd "$(dirname "$0")/.." && pwd)"
NCS_ROOT="${NCS_ROOT:-$HOME/ncs/v3.4.2}"
NCS_VENV="${NCS_VENV:-$HOME/ncs/venv}"
export ZEPHYR_SDK_INSTALL_DIR="${ZEPHYR_SDK_INSTALL_DIR:-$HOME/zephyr-sdk-1.0.1}"
export ZEPHYR_TOOLCHAIN_VARIANT=zephyr
export ZEPHYR_BASE="$NCS_ROOT/zephyr"
# shellcheck disable=SC1091
source "$NCS_VENV/bin/activate"

target="${1:-all}"; shift || true
dev=0; pristine=""
for a in "$@"; do
  case "$a" in --dev) dev=1 ;; --pristine) pristine="--pristine=always" ;; *) echo "unknown option $a"; exit 2 ;; esac
done

# Signing key: generated once, never committed (firmware/keys/ is git-ignored). Back it up:
# whoever holds it can sign firmware that every pod with this key will accept.
KEY="${OP_SIGN_KEY:-$FW/keys/mcuboot-ecdsa-p256.pem}"
if [[ ! -f "$KEY" ]]; then
  mkdir -p "$(dirname "$KEY")"
  python "$NCS_ROOT/bootloader/mcuboot/scripts/imgtool.py" keygen -k "$KEY" -t ecdsa-p256
  echo "generated new MCUboot signing key: $KEY (back it up!)"
fi

build_one() { # board dirname extra-args...
  local board="$1" name="$2" dir="$FW/build-zephyr/$2"; shift 2
  west build --sysbuild $pristine -b "$board" -d "$dir" "$FW/zephyr" -- \
    -DBOARD_ROOT="$FW/zephyr" -DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE="\"$KEY\"" "$@"
  local app="$dir/zephyr/zephyr" boot="$dir/mcuboot/zephyr"
  # sysbuild on nRF52 does not emit merged.hex (no partition manager): merge bootloader + signed app
  python "$ZEPHYR_BASE/scripts/build/mergehex.py" -o "$dir/openpatch-$name-merged.hex" \
    "$boot/zephyr.hex" "$app/zephyr.signed.hex"
  echo "== $board"
  echo "   merged hex (bootloader + signed app): $dir/openpatch-$name-merged.hex"
  echo "   signed DFU image (SMP / mcumgr)     : $app/zephyr.signed.bin  (zip: $dir/dfu_application.zip)"
  "$ZEPHYR_SDK_INSTALL_DIR/gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-size" "$boot/zephyr.elf" "$app/zephyr.elf"
}

case "$target" in
  reva|all) build_one openpatch_reva/nrf52840 reva $([[ $dev == 1 ]] && echo "-DEXTRA_CONF_FILE=dev.conf") ;;
esac
case "$target" in
  dk|all) build_one nrf52840dk/nrf52840 dk -DEXTRA_CONF_FILE=dev.conf ;;
esac
case "$target" in reva|dk|all) ;; *) echo "usage: $0 [reva|dk|all] [--dev] [--pristine]"; exit 2 ;; esac
