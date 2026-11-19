//! Frame layout: `version | type | flags | seq(2) | len(2) | payload | crc16(2)`, little-endian.

use crate::consts::*;
use crate::crc::crc16_ccitt_false;
use crate::error::Error;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Frame<'a> {
    pub version: u8,
    pub type_: u8,
    pub flags: u8,
    pub seq: u16,
    pub payload: &'a [u8],
}

/// Serialise a frame. Errors: `TooLarge` when it exceeds [`FRAME_MAX`] or `out`.
pub fn encode_frame(f: &Frame<'_>, out: &mut [u8]) -> Result<usize, Error> {
    let total = FRAME_HEADER + f.payload.len() + FRAME_CRC;
    if total > FRAME_MAX || total > out.len() {
        return Err(Error::TooLarge);
    }
    out[0] = f.version;
    out[1] = f.type_;
    out[2] = f.flags;
    out[3..5].copy_from_slice(&f.seq.to_le_bytes());
    out[5..7].copy_from_slice(&(f.payload.len() as u16).to_le_bytes());
    out[FRAME_HEADER..FRAME_HEADER + f.payload.len()].copy_from_slice(f.payload);
    let crc = crc16_ccitt_false(&out[..total - FRAME_CRC]);
    out[total - FRAME_CRC..total].copy_from_slice(&crc.to_le_bytes());
    Ok(total)
}

/// Parse and verify a frame. Check order (spec section 2): length / `len` consistency (`Frame`),
/// CRC (`Crc`), version (`Version`).
pub fn decode_frame(input: &[u8]) -> Result<Frame<'_>, Error> {
    let len = input.len();
    if !(FRAME_HEADER + FRAME_CRC..=FRAME_MAX).contains(&len) {
        return Err(Error::Frame);
    }
    let plen = u16::from_le_bytes([input[5], input[6]]) as usize;
    if FRAME_HEADER + plen + FRAME_CRC != len {
        return Err(Error::Frame);
    }
    let want = u16::from_le_bytes([input[len - 2], input[len - 1]]);
    if crc16_ccitt_false(&input[..len - FRAME_CRC]) != want {
        return Err(Error::Crc);
    }
    if input[0] != PROTO_VERSION {
        return Err(Error::Version);
    }
    Ok(Frame {
        version: input[0],
        type_: input[1],
        flags: input[2],
        seq: u16::from_le_bytes([input[3], input[4]]),
        payload: &input[FRAME_HEADER..FRAME_HEADER + plen],
    })
}
