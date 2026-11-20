#!/usr/bin/env bash
# Runs all SPICE cases of the 45-part cup board (about 10 minutes). Downloads the TI models first (not committed, TI licence).
set -euo pipefail
cd "$(dirname "$0")"
python3 run_all.py
