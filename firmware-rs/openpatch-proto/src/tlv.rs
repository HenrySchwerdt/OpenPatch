//! TLV payload: `tag(u8) | length(u8) | value`.

/// Writer into a caller buffer. Overflow is sticky and reported once at the end.
pub struct TlvWriter<'a> {
    buf: &'a mut [u8],
    len: usize,
    overflow: bool,
}

impl<'a> TlvWriter<'a> {
    pub fn new(buf: &'a mut [u8]) -> Self {
        Self { buf, len: 0, overflow: false }
    }

    pub fn put(&mut self, tag: u8, value: &[u8]) {
        debug_assert!(value.len() <= 255);
        if self.overflow {
            return;
        }
        if self.len + 2 + value.len() > self.buf.len() || value.len() > 255 {
            self.overflow = true;
            return;
        }
        self.buf[self.len] = tag;
        self.buf[self.len + 1] = value.len() as u8;
        self.buf[self.len + 2..self.len + 2 + value.len()].copy_from_slice(value);
        self.len += 2 + value.len();
    }

    pub fn put_u8(&mut self, tag: u8, v: u8) {
        self.put(tag, &[v]);
    }
    pub fn put_u16(&mut self, tag: u8, v: u16) {
        self.put(tag, &v.to_le_bytes());
    }
    pub fn put_u32(&mut self, tag: u8, v: u32) {
        self.put(tag, &v.to_le_bytes());
    }

    /// Bytes written, or `None` on overflow.
    pub fn finish(self) -> Option<usize> {
        if self.overflow {
            None
        } else {
            Some(self.len)
        }
    }
}

/// Reader yielding `(tag, value)`; a truncated TLV yields one `Err(())` and then ends.
pub struct TlvReader<'a> {
    p: &'a [u8],
    pos: usize,
    failed: bool,
}

impl<'a> TlvReader<'a> {
    pub fn new(p: &'a [u8]) -> Self {
        Self { p, pos: 0, failed: false }
    }
}

impl<'a> Iterator for TlvReader<'a> {
    type Item = Result<(u8, &'a [u8]), ()>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.failed || self.pos >= self.p.len() {
            return None;
        }
        if self.p.len() - self.pos < 2 {
            self.failed = true;
            return Some(Err(()));
        }
        let tag = self.p[self.pos];
        let l = self.p[self.pos + 1] as usize;
        if l > self.p.len() - self.pos - 2 {
            self.failed = true;
            return Some(Err(()));
        }
        let v = &self.p[self.pos + 2..self.pos + 2 + l];
        self.pos += 2 + l;
        Some(Ok((tag, v)))
    }
}

#[inline]
pub(crate) fn rd16(p: &[u8]) -> u16 {
    u16::from_le_bytes([p[0], p[1]])
}
#[inline]
pub(crate) fn rd32(p: &[u8]) -> u32 {
    u32::from_le_bytes([p[0], p[1], p[2], p[3]])
}
