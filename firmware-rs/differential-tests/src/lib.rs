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
