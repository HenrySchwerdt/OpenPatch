#!/bin/sh
# Host test run under AddressSanitizer + UndefinedBehaviorSanitizer.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
B="$ROOT/build-asan"
rm -rf "$B" && mkdir -p "$B"
cmake -S "$ROOT" -B "$B" -DOP_SANITIZE=ON -DCMAKE_BUILD_TYPE=Debug >/dev/null
cmake --build "$B" >/dev/null
"$B/op_tests"
