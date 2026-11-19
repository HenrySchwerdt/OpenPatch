# BLE stack choice (embedded app `openpatch-bench`)

> TEST PROJECT, not a medical device, never to be worn (see `../../DISCLAIMER.md`).

## Decision

**nrf-sdc 0.4.0 + nrf-mpsl 0.4.0 (Nordic SoftDevice Controller as a link-layer library) + trouble-host 0.8.0 (Rust BLE host)**,
on embassy-nrf 0.11.0. `nrf-softdevice` was rejected.

All versions are pinned with `=x.y.z` in `openpatch-bench/Cargo.toml`; transitive versions are fixed by the committed
`openpatch-bench/Cargo.lock`. No git dependency is used (everything is a published crates.io version).

| Crate | Version |
|---|---|
| embassy-nrf / embassy-executor / embassy-time / embassy-sync / embassy-futures | 0.11.0 / 0.10.0 / 0.5.1 / 0.8.0 / 0.1.2 |
| nrf-sdc (+ nrf-sdc-sys) / nrf-mpsl (+ nrf-mpsl-sys) | 0.4.0 (0.3.0) / 0.4.0 (0.3.0) |
| trouble-host (+ trouble-host-macros) / bt-hci | 0.8.0 (0.6.0) / 0.10.1 |
| embassy-boot / embassy-boot-nrf | 0.7.0 / 0.12.0 |
| sequential-storage / embedded-storage(-async) | 8.0.2 / 0.3.2 (0.4.2) |
| defmt / defmt-rtt / panic-probe | 1.2.0 / 1.3.1 / 1.0.0 |
| cortex-m / cortex-m-rt / static_cell | 0.7.10 / 0.7.7 / 2.1.1 |

## Research (2026-11-19)

* `cargo search` / `cargo info`: `nrf-sdc` 0.4.0 and `trouble-host` 0.8.0 are the current releases and depend on
  `embassy-nrf 0.11`, `embassy-sync 0.8`, `bt-hci 0.10`; `nrf-softdevice` is at 0.1.0 (last release long ago).
* `embassy-rs/trouble` tag `trouble-host-v0.8.0`, `examples/nrf52`: `ble_bas_peripheral_bonding.rs` is exactly this use case
  (nrf52840, SDC, peripheral, LE Secure Connections, bond stored with `sequential-storage` through the MPSL flash).
  `main.rs` of the firmware follows its MPSL / SDC bring-up (interrupt bindings, PPI channel split, `with_timeslots`).
  The example's `Cargo.toml` patches `nrf-mpsl` to a git rev; the crates.io 0.4.0 pair compiles without a patch.
* trouble-host 0.8.0 features used: `gatt`, `derive`, `peripheral`, `security` (LE Secure Connections, bonding, `is_bonded_peer`,
  `set_bondable`; without `legacy-pairing` = Secure Connections only), `default-packet-pool-mtu-251` (ATT MTU 247 = 251 - 4).
* `nrf-softdevice 0.1.0` needs the proprietary S140 SoftDevice hex flashed next to the application (extra partition and
  MBR, vector forwarding), pins an older embassy-nrf and is not maintained against embassy-nrf 0.11. It would also
  conflict with `embassy-boot-nrf` + timeslot flash design chosen here.

## Why SDC + trouble

* One mixed Rust build: no separate SoftDevice image, one ELF, one memory map (`../layout/layout.rs`).
* The SDC is Nordic's qualified controller; only the host (L2CAP, ATT, GATT, SMP) is Rust.
* MPSL timeslot **flash** API (`nrf_sdc::mpsl::Flash`, `embedded-storage-async`) gives radio-safe flash erase/write for
  settings and DFU (docs/architecture.md, "flash and the safety task").
* trouble's GATT server macros give the typed OpenPatch / bench services with `permissions(encrypted)`.

## How the SDC libraries are shipped (offline reproducibility)

`nrf-sdc-sys 0.3.0` and `nrf-mpsl-sys 0.3.0` contain Nordic's prebuilt static libraries inside the crate package
(`third_party/nordic/nrfxlib/softdevice_controller/lib/nrf52/hard-float/libsoftdevice_controller_{peripheral,central,multirole}.a`,
`third_party/nordic/nrfxlib/mpsl/lib/nrf52/hard-float/libmpsl.a`). The crate's `build.rs` runs `bindgen` over the shipped headers
and emits `cargo:rustc-link-search` for the library directory. The feature `peripheral` links the smaller peripheral-only
library. The shipped changelog's top entry is nRF Connect SDK v3.4.0.

Consequences:

* Nothing is downloaded during the build apart from crates.io packages. `cargo fetch` once, then `cargo build --offline` works,
  and `cargo vendor` captures the blobs (the packages are ~43 MB). `Cargo.lock` pins the exact packages.
* Build host requirement: **libclang** (bindgen). On macOS it comes with the Xcode command line tools (already present here).
* **Licence note:** the `.a` files are `LicenseRef-Nordic-5-Clause` (use only with Nordic ICs, redistribution conditions), while
  this repository is GPL-3.0-or-later. Fine for a private bench test project; review before distributing binaries.

## Known limits of the chosen versions

* LE Secure Connections pairing uses the pure Rust `p256` (the faster assembly variant `security-p256-cortex-m4` needs
  `arm-none-eabi-gcc`, not installed here). `p256`/`crypto-bigint`/`primeorder`/`elliptic-curve` are built with opt-level 3 to
  keep pairing in the low seconds. Pairing happens once per bond, inside the button window.
* trouble-host 0.8.0 has no hook to *refuse* an SMP pairing request; the pairing window is enforced by disconnecting unbonded
  peers, `set_bondable(false)` outside the window and `permissions(encrypted)` on every characteristic (docs/stubs.md).
* The advertising packet cannot hold flags + 128 bit service UUID + the 14 character name in 31 bytes: the service UUID is in the
  advertising data, the name `OpenPatch-XXXX` is in the scan response (central sees both with an active scan, as iOS does).
* SDC memory: `main.rs` reserves 16 KB (the formulas of `sdc.h` give about 4 KB for 1 peripheral link with 251 byte buffers);
  the controller logs the exact requirement at every boot.
* Nothing in this firmware was run on hardware yet (no probe available during development): see docs/stubs.md.
