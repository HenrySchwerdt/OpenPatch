//! FFI to the C reference core via `csrc/shim.c`. `unsafe` is allowed ONLY in this host-only test
//! crate; every block carries a SAFETY comment. Handles own heap objects created by the shim and
//! free them on drop; all calls take `&mut self`/`&self`, so access is exclusive/single-threaded.
#![allow(unsafe_code)]

use std::os::raw::c_int;
use std::ptr::NonNull;

pub const CMD_LEN: usize = 96;
pub const RSP_LEN: usize = 96;
pub const SNAP_LEN: usize = 160;
pub const MOCK_LEN: usize = 8;
pub const DE_SNAP_LEN: usize = 32;
pub const RES_SNAP_LEN: usize = 8;

#[repr(C)]
pub struct Opaque {
    _p: [u8; 0],
}

extern "C" {
    fn shim_crc16(d: *const u8, n: usize) -> u16;
    fn shim_frame_encode(version: u8, ty: u8, flags: u8, seq: u16, payload: *const u8, plen: u16, out: *mut u8, cap: usize) -> c_int;
    fn shim_frame_decode(inp: *const u8, len: usize, out: *mut u32) -> c_int;
    fn shim_sess_new() -> *mut Opaque;
    fn shim_sess_free(s: *mut Opaque);
    fn shim_sess_decode(s: *mut Opaque, inp: *const u8, len: usize, out: *mut u32) -> c_int;
    fn shim_decode_payload(ty: u8, seq: u16, payload: *const u8, len: usize, out: *mut u32) -> c_int;
    fn shim_encode_cmd(inp: *const u32, out: *mut u8, cap: usize) -> c_int;
    fn shim_encode_rsp(inp: *const u32, out: *mut u8, cap: usize) -> c_int;

    fn shim_create(cal_id: u32, cap: u32, next_id: u32) -> *mut Opaque;
    fn shim_destroy(s: *mut Opaque);
    fn shim_new_session(s: *mut Opaque);
    fn shim_set_time(s: *mut Opaque, ms: u64);
    fn shim_set_docked(s: *mut Opaque, v: c_int);
    fn shim_set_charger(s: *mut Opaque, v: c_int);
    fn shim_set_battery(s: *mut Opaque, mv: u16);
    fn shim_set_delivered_pct(s: *mut Opaque, pct: u32);
    fn shim_set_steps_limit(s: *mut Opaque, lim: i32);
    fn shim_tick(s: *mut Opaque);
    fn shim_handle_frame(s: *mut Opaque, inp: *const u8, len: usize, out: *mut u8, cap: usize) -> c_int;
    fn shim_restore_pod(s: *mut Opaque, pair: u32, role: u8, active: c_int, act_id: u32, wear_ms: u64);
    fn shim_mock(s: *const Opaque, out: *mut u64);
    fn shim_snapshot(s: *const Opaque, out: *mut u64);
    fn shim_log_event(s: *const Opaque, id: u32, out: *mut i64) -> c_int;

    fn shim_de_create(uu: u32) -> *mut Opaque;
    fn shim_de_destroy(d: *mut Opaque);
    fn shim_de_set_schedule(d: *mut Opaque, n: u32, slots: *const u8, rates: *const u32) -> c_int;
    fn shim_de_set_tod(d: *mut Opaque, ms: u32);
    fn shim_de_heartbeat(d: *mut Opaque);
    fn shim_de_start_temp(d: *mut Opaque, rate: u32, dur: u32) -> c_int;
    fn shim_de_cancel_temp(d: *mut Opaque) -> c_int;
    fn shim_de_start_bolus(d: *mut Opaque, mu: u32) -> c_int;
    fn shim_de_cancel_bolus(d: *mut Opaque) -> u32;
    fn shim_de_suspend(d: *mut Opaque);
    fn shim_de_resume(d: *mut Opaque);
    fn shim_de_tick(d: *mut Opaque, dt: u32) -> u32;
    fn shim_de_commit(d: *mut Opaque, n: u32);
    fn shim_de_take_events(d: *mut Opaque) -> u32;
    fn shim_de_snap(d: *const Opaque, out: *mut u64);

    fn shim_res_create(cap: u32, uu: u32) -> *mut Opaque;
    fn shim_res_destroy(r: *mut Opaque);
    fn shim_res_fill(r: *mut Opaque, mu: u32) -> c_int;
    fn shim_res_set_low(r: *mut Opaque, mu: u32) -> c_int;
    fn shim_res_consume(r: *mut Opaque, steps: u32);
    fn shim_res_snap(r: *const Opaque, out: *mut u64);

    fn shim_log_create(restore_id: u32) -> *mut Opaque;
    fn shim_log_destroy(l: *mut Opaque);
    fn shim_log_append(l: *mut Opaque, t: u32, ty: u8, a: i32, b: i32) -> u32;
    fn shim_log_next(l: *const Opaque) -> u32;
    fn shim_log_oldest(l: *const Opaque) -> u32;
    fn shim_log_read(l: *const Opaque, from: u32, max: u32, out: *mut i64) -> u32;
}

fn nn(p: *mut Opaque, what: &str) -> NonNull<Opaque> {
    NonNull::new(p).unwrap_or_else(|| panic!("shim: {what} returned NULL"))
}

// ---------------------------------------------------------------------------------------------
// stateless codec helpers
// ---------------------------------------------------------------------------------------------

pub fn c_crc16(d: &[u8]) -> u16 {
    // SAFETY: pointer/length come from a live slice; the shim only reads `n` bytes.
    unsafe { shim_crc16(d.as_ptr(), d.len()) }
}

/// `Ok(len)` / `Err(code)` (positive `op_err_t`).
pub fn c_frame_encode(version: u8, ty: u8, flags: u8, seq: u16, payload: &[u8], cap: usize) -> Result<Vec<u8>, u8> {
    let mut out = vec![0u8; cap.max(1)];
    // SAFETY: `payload` is a live slice (len fits u16 in all callers, checked below); `out` has
    // `cap` writable bytes and the C encoder bounds-checks against `cap`.
    let rc = unsafe {
        assert!(payload.len() <= u16::MAX as usize);
        shim_frame_encode(version, ty, flags, seq, payload.as_ptr(), payload.len() as u16, out.as_mut_ptr(), cap)
    };
    if rc < 0 {
        Err((-rc) as u8)
    } else {
        out.truncate(rc as usize);
        Ok(out)
    }
}

/// (version, type, flags, seq, payload_len, payload_offset)
pub fn c_frame_decode(inp: &[u8]) -> Result<[u32; 6], u8> {
    let mut o = [0u32; 8];
    // SAFETY: `inp` is a live slice; `o` is the 8-word out array the shim writes to.
    let rc = unsafe { shim_frame_decode(inp.as_ptr(), inp.len(), o.as_mut_ptr()) };
    if rc < 0 {
        Err((-rc) as u8)
    } else {
        Ok([o[0], o[1], o[2], o[3], o[4], o[5]])
    }
}

pub fn c_decode_payload(ty: u8, seq: u16, payload: &[u8]) -> Result<[u32; CMD_LEN], u8> {
    let mut o = [0u32; CMD_LEN];
    // SAFETY: live slice in, CMD_LEN-word array out.
    let rc = unsafe { shim_decode_payload(ty, seq, payload.as_ptr(), payload.len(), o.as_mut_ptr()) };
    if rc < 0 {
        Err((-rc) as u8)
    } else {
        Ok(o)
    }
}

pub fn c_encode_cmd(flat: &[u32; CMD_LEN], cap: usize) -> Result<Vec<u8>, u8> {
    let mut out = vec![0u8; cap.max(1)];
    // SAFETY: `flat` has CMD_LEN words as the shim expects; `out` has `cap` bytes (bounds-checked in C).
    let rc = unsafe { shim_encode_cmd(flat.as_ptr(), out.as_mut_ptr(), cap) };
    if rc < 0 {
        Err((-rc) as u8)
    } else {
        out.truncate(rc as usize);
        Ok(out)
    }
}

pub fn c_encode_rsp(flat: &[u32; RSP_LEN], cap: usize) -> Result<Vec<u8>, u8> {
    let mut out = vec![0u8; cap.max(1)];
    // SAFETY: as for `c_encode_cmd`.
    let rc = unsafe { shim_encode_rsp(flat.as_ptr(), out.as_mut_ptr(), cap) };
    if rc < 0 {
        Err((-rc) as u8)
    } else {
        out.truncate(rc as usize);
        Ok(out)
    }
}

/// C plaintext session (replay state included): `op_session_open` + `op_cmd_decode`.
pub struct CSession(NonNull<Opaque>);
impl CSession {
    pub fn new() -> Self {
        // SAFETY: plain allocation; returns a valid heap object or NULL (checked).
        Self(nn(unsafe { shim_sess_new() }, "sess_new"))
    }
    pub fn decode(&mut self, inp: &[u8]) -> Result<[u32; CMD_LEN], u8> {
        let mut o = [0u32; CMD_LEN];
        // SAFETY: handle valid until drop and exclusively borrowed; slice/array arguments are live.
        let rc = unsafe { shim_sess_decode(self.0.as_ptr(), inp.as_ptr(), inp.len(), o.as_mut_ptr()) };
        if rc < 0 {
            Err((-rc) as u8)
        } else {
            Ok(o)
        }
    }
}
impl Default for CSession {
    fn default() -> Self {
        Self::new()
    }
}
impl Drop for CSession {
    fn drop(&mut self) {
        // SAFETY: pointer came from shim_sess_new and is freed exactly once here.
        unsafe { shim_sess_free(self.0.as_ptr()) }
    }
}

// ---------------------------------------------------------------------------------------------
// whole pump
// ---------------------------------------------------------------------------------------------

pub struct CPump(NonNull<Opaque>);

impl CPump {
    /// `cal_id`: C preset id (1 = 26100 uU/step, 2 = 8156 uU/step), 0 = no calibration.
    pub fn new(cal_id: u32, capacity_mu: u32, next_event_id: u32) -> Self {
        // SAFETY: plain allocation + init inside the shim; NULL checked.
        Self(nn(unsafe { shim_create(cal_id, capacity_mu, next_event_id) }, "create"))
    }
    fn p(&self) -> *mut Opaque {
        self.0.as_ptr()
    }
    // SAFETY (all methods below): `self.p()` is the live handle from `shim_create` (freed only in
    // Drop); `&mut self`/`&self` guarantees exclusive/shared access on this single thread; any
    // slice or array passed is live for the call and sized as the shim documents.
    pub fn new_session(&mut self) {
        unsafe { shim_new_session(self.p()) }
    }
    pub fn set_time(&mut self, ms: u64) {
        unsafe { shim_set_time(self.p(), ms) }
    }
    pub fn set_docked(&mut self, v: bool) {
        unsafe { shim_set_docked(self.p(), v as c_int) }
    }
    pub fn set_charger(&mut self, v: bool) {
        unsafe { shim_set_charger(self.p(), v as c_int) }
    }
    pub fn set_battery(&mut self, mv: u16) {
        unsafe { shim_set_battery(self.p(), mv) }
    }
    pub fn set_delivered_pct(&mut self, pct: u32) {
        unsafe { shim_set_delivered_pct(self.p(), pct) }
    }
    pub fn set_steps_limit(&mut self, lim: i32) {
        unsafe { shim_set_steps_limit(self.p(), lim) }
    }
    pub fn tick(&mut self) {
        unsafe { shim_tick(self.p()) }
    }
    /// `Ok(frame)` or `Err(code)` when no response is produced.
    pub fn handle_frame(&mut self, inp: &[u8]) -> Result<Vec<u8>, u8> {
        let mut out = [0u8; 256];
        let rc = unsafe { shim_handle_frame(self.p(), inp.as_ptr(), inp.len(), out.as_mut_ptr(), out.len()) };
        if rc < 0 {
            Err((-rc) as u8)
        } else {
            Ok(out[..rc as usize].to_vec())
        }
    }
    pub fn restore_pod(&mut self, pair: u32, role: u8, active: bool, act_id: u32, wear_ms: u64) {
        unsafe { shim_restore_pod(self.p(), pair, role, active as c_int, act_id, wear_ms) }
    }
    pub fn mock(&self) -> [u64; MOCK_LEN] {
        let mut o = [0u64; MOCK_LEN];
        unsafe { shim_mock(self.p(), o.as_mut_ptr()) };
        o
    }
    pub fn snapshot(&self) -> [u64; SNAP_LEN] {
        let mut o = [0u64; SNAP_LEN];
        unsafe { shim_snapshot(self.p(), o.as_mut_ptr()) };
        o
    }
    /// (id, time_s, type, a, b) if the event is still in the ring.
    pub fn log_event(&self, id: u32) -> Option<[i64; 5]> {
        let mut o = [0i64; 5];
        let ok = unsafe { shim_log_event(self.p(), id, o.as_mut_ptr()) };
        (ok != 0).then_some(o)
    }
}
impl Drop for CPump {
    fn drop(&mut self) {
        // SAFETY: allocated by shim_create, freed exactly once.
        unsafe { shim_destroy(self.0.as_ptr()) }
    }
}

// ---------------------------------------------------------------------------------------------
// engine / reservoir / log
// ---------------------------------------------------------------------------------------------

pub struct CEngine(NonNull<Opaque>);
impl CEngine {
    pub fn new(uu: u32) -> Self {
        // SAFETY: allocation + init in the shim; NULL checked.
        Self(nn(unsafe { shim_de_create(uu) }, "de_create"))
    }
    fn p(&self) -> *mut Opaque {
        self.0.as_ptr()
    }
    // SAFETY (all methods below): live handle, exclusive access via &mut self, arguments live.
    pub fn set_schedule(&mut self, pairs: &[(u8, u32)]) -> i32 {
        let slots: Vec<u8> = pairs.iter().map(|p| p.0).collect();
        let rates: Vec<u32> = pairs.iter().map(|p| p.1).collect();
        assert!(pairs.len() <= 24);
        unsafe { shim_de_set_schedule(self.p(), pairs.len() as u32, slots.as_ptr(), rates.as_ptr()) }
    }
    pub fn set_tod(&mut self, ms: u32) {
        unsafe { shim_de_set_tod(self.p(), ms) }
    }
    pub fn heartbeat(&mut self) {
        unsafe { shim_de_heartbeat(self.p()) }
    }
    pub fn start_temp(&mut self, rate: u32, dur: u32) -> i32 {
        unsafe { shim_de_start_temp(self.p(), rate, dur) }
    }
    pub fn cancel_temp(&mut self) -> bool {
        unsafe { shim_de_cancel_temp(self.p()) != 0 }
    }
    pub fn start_bolus(&mut self, mu: u32) -> i32 {
        unsafe { shim_de_start_bolus(self.p(), mu) }
    }
    pub fn cancel_bolus(&mut self) -> u32 {
        unsafe { shim_de_cancel_bolus(self.p()) }
    }
    pub fn suspend(&mut self) {
        unsafe { shim_de_suspend(self.p()) }
    }
    pub fn resume(&mut self) {
        unsafe { shim_de_resume(self.p()) }
    }
    pub fn tick(&mut self, dt: u32) -> u32 {
        unsafe { shim_de_tick(self.p(), dt) }
    }
    pub fn commit(&mut self, n: u32) {
        unsafe { shim_de_commit(self.p(), n) }
    }
    pub fn take_events(&mut self) -> u32 {
        unsafe { shim_de_take_events(self.p()) }
    }
    pub fn snap(&self) -> [u64; DE_SNAP_LEN] {
        let mut o = [0u64; DE_SNAP_LEN];
        unsafe { shim_de_snap(self.p(), o.as_mut_ptr()) };
        o
    }
}
impl Drop for CEngine {
    fn drop(&mut self) {
        // SAFETY: allocated by shim_de_create, freed once.
        unsafe { shim_de_destroy(self.0.as_ptr()) }
    }
}

pub struct CReservoir(NonNull<Opaque>);
impl CReservoir {
    pub fn new(cap: u32, uu: u32) -> Self {
        // SAFETY: allocation + init in the shim; NULL checked.
        Self(nn(unsafe { shim_res_create(cap, uu) }, "res_create"))
    }
    fn p(&self) -> *mut Opaque {
        self.0.as_ptr()
    }
    // SAFETY (methods): live handle, exclusive access via &mut self.
    pub fn fill(&mut self, mu: u32) -> i32 {
        unsafe { shim_res_fill(self.p(), mu) }
    }
    pub fn set_low(&mut self, mu: u32) -> i32 {
        unsafe { shim_res_set_low(self.p(), mu) }
    }
    pub fn consume(&mut self, steps: u32) {
        unsafe { shim_res_consume(self.p(), steps) }
    }
    /// fill, consumed, filled, low_threshold, remaining, empty, low, capacity
    pub fn snap(&self) -> [u64; RES_SNAP_LEN] {
        let mut o = [0u64; RES_SNAP_LEN];
        unsafe { shim_res_snap(self.p(), o.as_mut_ptr()) };
        o
    }
}
impl Drop for CReservoir {
    fn drop(&mut self) {
        // SAFETY: allocated by shim_res_create, freed once.
        unsafe { shim_res_destroy(self.0.as_ptr()) }
    }
}

pub struct CLog(NonNull<Opaque>);
impl CLog {
    pub fn new(restore_id: u32) -> Self {
        // SAFETY: allocation + init in the shim; NULL checked.
        Self(nn(unsafe { shim_log_create(restore_id) }, "log_create"))
    }
    fn p(&self) -> *mut Opaque {
        self.0.as_ptr()
    }
    // SAFETY (methods): live handle, exclusive/shared access per receiver, out buffers sized below.
    pub fn append(&mut self, t: u32, ty: u8, a: i32, b: i32) -> u32 {
        unsafe { shim_log_append(self.p(), t, ty, a, b) }
    }
    pub fn next_id(&self) -> u32 {
        unsafe { shim_log_next(self.p()) }
    }
    pub fn oldest_id(&self) -> u32 {
        unsafe { shim_log_oldest(self.p()) }
    }
    pub fn read(&self, from: u32, max: u32) -> Vec<[i64; 5]> {
        let max = max.min(128);
        let mut buf = vec![0i64; 5 * 128];
        let n = unsafe { shim_log_read(self.p(), from, max, buf.as_mut_ptr()) } as usize;
        (0..n).map(|i| [buf[5 * i], buf[5 * i + 1], buf[5 * i + 2], buf[5 * i + 3], buf[5 * i + 4]]).collect()
    }
}
impl Drop for CLog {
    fn drop(&mut self) {
        // SAFETY: allocated by shim_log_create, freed once.
        unsafe { shim_log_destroy(self.0.as_ptr()) }
    }
}
