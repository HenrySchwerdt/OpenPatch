//! Verification harnesses. Tests live in `tests/`, Kani proofs in `kani_proofs` (cfg(kani) only).
//! Nothing here is linked into firmware.
#[cfg(kani)]
mod kani_proofs;
