//! Host-only differential tests: the Rust pump core (`openpatch-core`, `openpatch-proto`) against
//! the C reference core (`firmware/core`, built by `build.rs` together with `csrc/shim.c`).
//!
//! TEST PROJECT: not a medical device. This crate may use `unsafe` (FFI) because it never runs on
//! a target; the firmware crates stay `forbid(unsafe_code)`.
pub mod desc;
pub mod ffi;
pub mod gen;
pub mod harness;
pub mod pair;
pub mod rmock;
pub mod rng;

/// Command ids that exist only in the Rust protocol (C answers `Unsupported` at decode time):
/// 0x0F FillDraw and the diagnostics commands 0x10..0x12 (docs/06-diagnostics.md 5.4). They never
/// occur in streams shared with the C reference; each has its own Rust-only tests.
pub fn rust_only_cmd(t: u8) -> bool {
    (openpatch_proto::cmd::FILL_DRAW..=openpatch_proto::cmd::CLEAR_DIAG).contains(&t)
}
