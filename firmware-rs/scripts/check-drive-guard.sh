#!/usr/bin/env bash
# A firmware build must name exactly ONE drive preset (a wrong gear ratio is a dosing error).
# Verifies that zero and two drive features both FAIL to compile. TEST PROJECT: never to be worn.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/openpatch-bench"
base="board-bench-e73,angle-tmag"
fail=0
for drives in "" "drive-nfp-608-26-45-g16-20,drive-nfp-608-26-45-g15-12"; do
  feats="$base${drives:+,$drives}"
  if cargo check --release --no-default-features --features "$feats" >/dev/null 2>&1; then
    echo "FAIL: build with [$feats] compiled but must not"; fail=1
  else
    echo "ok: build with [$feats] is refused"
  fi
done
if ! cargo check --release --no-default-features --features "$base,drive-nfp-608-26-45-g16-20" >/dev/null 2>&1; then
  echo "FAIL: build with exactly one drive feature must compile"; fail=1
else
  echo "ok: exactly one drive feature compiles"
fi
exit $fail
