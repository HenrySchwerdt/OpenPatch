//! OpenPatch protocol v1 (see `firmware/docs/openpatch-protocol.md`).
//!
//! TEST PROJECT: not a medical device, never to be worn.
//!
//! Byte-compatible with the C reference (`firmware/core/src/openpatch_*.c`) and with the iOS
//! `OpenPatchCore` implementation. `no_std`, no alloc, no `unsafe`.
#![no_std]
#![forbid(unsafe_code)]

#[cfg(feature = "std")]
extern crate std;

mod codec_cmd;
mod codec_rsp;
pub mod consts;
pub mod crc;
pub mod error;
pub mod frame;
pub mod msg;
pub mod session;
pub mod tlv;

#[cfg(feature = "aes-ccm")]
pub mod ccm_impl;
#[cfg(feature = "key-agreement")]
pub mod handshake;

pub use codec_cmd::{decode_command, encode_command_payload};
pub use codec_rsp::{
    decode_notification_payload, decode_response, encode_notification_payload, encode_notification_payload_ex, encode_response_payload,
};
pub use consts::*;
pub use error::Error;
pub use frame::{decode_frame, encode_frame, Frame};
pub use msg::*;
pub use session::{Ccm, CcmError, LinkRole, NoCrypto, Session};
