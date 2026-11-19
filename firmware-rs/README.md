# OpenPatch firmware (Rust)

> TEST PROJECT. Not a medical device, never to be worn, bench tests with water only (see `../DISCLAIMER.md`).
> The C firmware in `../firmware` stays untouched as the reference implementation for differential testing.

## Layout

| Path | What |
|---|---|
| `openpatch-proto/` | `no_std` wire protocol v1: frame/TLV codec (byte-identical to `firmware/docs/openpatch-protocol.md`), CRC-16, session (replay, `LAST_SEQ`), `Ccm` trait; feature `aes-ccm` = RustCrypto AES-128-CCM (RFC 3610 vector tested) |
| `openpatch-core/` | `no_std`, no alloc, `forbid(unsafe_code)`: unit newtypes (`MilliUnits`, `Pulses`, `AngleCounts`, `Millis`...), exact-rational drive presets, delivery engine, safety supervisor, reservoir, event log, two-pod logic, draw (refill) mode, bench sequences |
| `differential-tests/` | host only: builds `../firmware/core` with `cc`, FFI-binds it, runs identical random command streams on C and Rust |
| `openpatch-bench/` | Embassy app for nRF52840 (separate workspace) |
| `openpatch-bootloader/` | embassy-boot-nrf bootloader, ed25519-signed images (separate workspace) |
| `docs/` | architecture, BLE stack choice, boards, bench testing, bootloader/key handling, protocol extensions, differential testing, stubs |
| `scripts/` | `build.sh`, `gen-signing-key.sh`, `sign-image.sh` |
| `ci/rust.yml` | GitHub Actions draft (not active) |

## Safety design in one paragraph

Every dose passes the safety supervisor step by step: calibrated drive, docked, active pod, no latched fault, reservoir, 15 U rolling
hour, 1.7 U/min backstop. Delivery is verified by the leadscrew angle sensor (TMAG5273): occlusion (commanded minus confirmed > 2 U,
stall), deviation > 10 % per >= 1 U, deviation > 3 % per leadscrew revolution, and motor-current rise. The drive calibration is an exact
rational of micro-units per step (`drive_cal::PRESETS`), has **no default** (the app refuses to compile without choosing one),
carries a CRC, must equal the preset of its id, and its id is reported in `GetStatus`. Faults are latched and need `Acknowledge`.
Refill is an explicit "draw" mode (only suspended + undocked, step-exact volume, mandatory priming afterwards).

## Build and test (host)

```sh
cd firmware-rs
cargo test --workspace                       # all host tests incl. property and differential tests
cargo test -p openpatch-proto --all-features # + AES-CCM
cargo llvm-cov --workspace --summary-only    # coverage (cargo install cargo-llvm-cov)
cargo clippy --workspace --all-targets
```

## Build (embedded)

Needs `rustup target add thumbv7em-none-eabihf`, `cargo install flip-link cargo-binutils probe-rs-tools`, libclang (bindgen for nrf-sdc).
The drive preset must be chosen explicitly (cargo feature `drive-*`, exactly one) and exactly one board feature
(`board-bench-e73` default, `board-nrf52840-dk`):

```sh
./scripts/build.sh                 # bootloader + app for both boards (explicit preset), prints sizes
cd openpatch-bench && cargo build --release --no-default-features --features "board-nrf52840-dk,drive-nfp-608-26-45-g15-12,angle-tmag,dev-plaintext"
```

## Flash and run (probe-rs, any CMSIS-DAP / J-Link / the DK's on-board debugger)

```sh
./scripts/gen-signing-key.sh                       # once; keys land in firmware-rs/keys/ (git-ignored, back them up)
cd openpatch-bootloader && cargo run --release     # flashes the bootloader
cd ../openpatch-bench && cargo run --release       # flashes + runs the app, defmt/RTT log
```

Bench procedures (gravimetric tests, draw mode, calibration of thresholds): `docs/bench-testing.md`. Production builds accept only
encrypted frames; the session key agreement is an open point of protocol v1 (see `docs/stubs.md`). `dev-plaintext` is for the bench only.

## Status

See `docs/stubs.md` for everything that is stubbed or unverified (nothing has run on hardware yet).
