#!/usr/bin/env bash
# Generate CycloneDX 1.5 SBOMs (JSON) for every Rust lockfile of the repository. TEST PROJECT, not a medical device.
# Usage: security/supply-chain/sbom.sh [outdir]      Needs: cargo-cyclonedx (cargo install --locked cargo-cyclonedx --version 0.5.10)
# One SBOM per workspace / standalone crate; file name = crate path with '/' replaced by '_'. The SBOM is published with every
# release together with its SHA-256 and signature (security/proposals/08-incident-response-disclosure.md).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-$ROOT/security/supply-chain/results/sbom}"
mkdir -p "$OUT"
for m in firmware-rs firmware-rs/openpatch-bench firmware-rs/openpatch-bootloader firmware-rs/tools/sigtool firmware-rs/fuzz security/verify; do
  [ -f "$ROOT/$m/Cargo.toml" ] || continue
  name="$(echo "$m" | tr '/' '_')"
  ( cd "$ROOT/$m" && cargo cyclonedx --format json --spec-version 1.5 --all-features --target-in-filename >/dev/null 2>&1 || cargo cyclonedx --format json )
  # cargo-cyclonedx writes <crate>.cdx.json next to each Cargo.toml: collect and rename, then clean the tree.
  find "$ROOT/$m" -maxdepth 2 -name '*.cdx.json' -not -path '*/target/*' | while read -r f; do
    cp "$f" "$OUT/${name}__$(basename "$f")"; rm -f "$f"
  done
done
( cd "$OUT" && sha256sum *.json > SHA256SUMS && ls -l )
