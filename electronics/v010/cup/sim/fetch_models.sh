#!/usr/bin/env bash
# Download the TI vendor SPICE models into models/ (gitignored: the TI licence does not let us redistribute them).
# Each zip is unpacked into its own directory; nothing in there is executed.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
M="$HERE/models"
mkdir -p "$M"
get() {  # id name
  local id="$1" name="$2"
  if [ -d "$M/$name" ] && [ -n "$(ls -A "$M/$name" 2>/dev/null)" ]; then return 0; fi
  mkdir -p "$M/$name"
  curl -fsSL -m 120 -o "$M/$name.zip" "https://www.ti.com/lit/zip/$id"
  unzip -o -q "$M/$name.zip" -d "$M/$name"
}
get SLVMD68 tps61023_pspice   # TPS61023 unencrypted PSpice transient model (Rev A)
get SLVM425 tps2553_pspice    # TPS2553 PSpice transient model (Final 1.00, plain text)
# Normalised file names for the netlists
cp -f "$M"/tps61023_pspice/*/TPS61023_TRANS_PSPICE/library/TPS61023_TRANS.LIB "$M/TPS61023_TRANS.lib"
cp -f "$M"/tps2553_pspice/*/TPS2553_PSPICE_TRANS/tps2553_trans.lib "$M/TPS2553_TRANS.lib"
echo "models ok: $(ls "$M"/*.lib | xargs -n1 basename | tr '\n' ' ')"
