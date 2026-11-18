#!/usr/bin/env bash
# Re-render the product photography from the CAD output (mechanical/out/*.sc) and refresh public/renders/.
#   scripts/render-product.sh            all shots at full quality (~25 min on an M-series Mac)
#   scripts/render-product.sh hero       only the named shots
#   QUICK=1 scripts/render-product.sh    one-third resolution preview
# Requires SolidCraft (override with SOLIDCRAFT_CLI) and python3. Output: transparent PNG -> AVIF/WebP/PNG.
set -euo pipefail
cd "$(dirname "$0")/.."
export OP_RENDER_WORK="${OP_RENDER_WORK:-$PWD/.render-work}"
shots=("$@"); [ ${#shots[@]} -eq 0 ] && shots=(top70 top100 top200 hero hero_graphite exploded)
flags=(); [ "${QUICK:-0}" = "1" ] && flags=(--quick)
python3 scripts/render-product.py "${shots[@]}" "${flags[@]}"
node scripts/convert-renders.mjs
