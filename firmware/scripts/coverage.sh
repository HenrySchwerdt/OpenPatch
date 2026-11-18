#!/bin/sh
# Host test run with LLVM source-based coverage of firmware/core/src.
# Requires clang + llvm-profdata + llvm-cov from the same LLVM (e.g. brew install llvm).
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
B="$ROOT/build-cov"
LLVM_BIN="${LLVM_BIN:-/opt/homebrew/opt/llvm/bin}"
rm -rf "$B" && mkdir -p "$B"
cmake -S "$ROOT" -B "$B" -DCMAKE_C_COMPILER="$LLVM_BIN/clang" -DOP_COVERAGE=ON -DCMAKE_BUILD_TYPE=Debug >/dev/null
cmake --build "$B" >/dev/null
LLVM_PROFILE_FILE="$B/op.profraw" "$B/op_tests"
"$LLVM_BIN/llvm-profdata" merge -sparse "$B/op.profraw" -o "$B/op.profdata"
"$LLVM_BIN/llvm-cov" report "$B/op_tests" -instr-profile="$B/op.profdata" "$ROOT"/core/src/*.c
"$LLVM_BIN/llvm-cov" show "$B/op_tests" -instr-profile="$B/op.profdata" -format=html -output-dir="$B/html" "$ROOT"/core/src/*.c >/dev/null
echo "HTML report: $B/html/index.html"
