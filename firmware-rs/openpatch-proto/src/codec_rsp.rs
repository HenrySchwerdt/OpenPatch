//! Response payload codec. Tag order is identical to the C reference (byte-identical output).

use crate::consts::*;
use crate::error::Error;
use crate::msg::*;
use crate::tlv::{rd16, rd32, TlvReader, TlvWriter};

fn put_event(w: &mut TlvWriter<'_>, e: &HistoryEvent) {
    let mut b = [0u8; EVENT_TLV_LEN];
    b[0..4].copy_from_slice(&e.id.to_le_bytes());
    b[4..8].copy_from_slice(&e.time_s.to_le_bytes());
    b[8] = e.kind;
    b[9..13].copy_from_slice(&(e.a as u32).to_le_bytes());
    b[13..17].copy_from_slice(&(e.b as u32).to_le_bytes());
    w.put(tag::HISTORY_EVENT, &b);
}

/// Encode a response payload (`RESULT` first, then optional status / act-delivered / history).
pub fn encode_response_payload(r: &Response, out: &mut [u8]) -> Result<usize, Error> {
    let mut w = TlvWriter::new(out);
    w.put_u8(tag::RESULT, r.result);
    if let Some(s) = &r.status {
        w.put_u16(tag::STATE_FLAGS, s.flags);
        w.put_u16(tag::FAULT_MASK, s.faults);
        w.put_u32(tag::RESERVOIR_MU, s.reservoir_mu);
        w.put_u16(tag::BATTERY_MV, s.battery_mv);
        w.put_u32(tag::BOLUS_REMAINING_MU, s.bolus_remaining_mu);
        w.put_u16(tag::TEMP_RATE_MU_H, s.temp_rate_mu_h);
        w.put_u16(tag::TEMP_REMAINING_MIN, s.temp_remaining_min);
        w.put_u16(tag::CURRENT_RATE_MU_H, s.current_rate_mu_h);
        w.put_u32(tag::DELIVERED_MU, s.delivered_mu);
        w.put_u32(tag::SCHEDULED_MU, s.scheduled_mu);
        w.put_u32(tag::NEXT_EVENT_ID, s.next_event_id);
        w.put_u16(tag::FW_VERSION, s.fw_version);
        w.put_u16(tag::LAST_SEQ, s.last_seq);
        let mut cal = [0u8; DRIVE_CAL_TLV_LEN];
        cal[0..2].copy_from_slice(&s.cal_drive_id.to_le_bytes());
        cal[2..6].copy_from_slice(&s.cal_uu_per_step.to_le_bytes());
        cal[6..8].copy_from_slice(&s.cal_steps_per_rev.to_le_bytes());
        cal[8..10].copy_from_slice(&s.cal_gear_ratio_x100.to_le_bytes());
        w.put(tag::DRIVE_CAL, &cal);
        let mut pod = [0u8; POD_INFO_TLV_LEN];
        pod[0..4].copy_from_slice(&s.pair_id.to_le_bytes());
        pod[4] = s.role;
        pod[5] = s.delivery_state;
        pod[6..10].copy_from_slice(&s.wear_s.to_le_bytes());
        w.put(tag::POD_INFO, &pod);
        w.put_u8(tag::DRAW_STATE, s.draw_state);
        w.put_u32(tag::DRAW_REQUESTED_MU, s.draw_requested_mu);
        w.put_u32(tag::DRAW_DONE_MU, s.draw_done_mu);
        if let Some(d) = &s.diag {
            w.put(tag::DIAG_SUMMARY, &d.to_bytes());
        }
        if let Some(h) = s.fru_health {
            w.put(tag::FRU_HEALTH, &h.to_le_bytes());
        }
        if let Some(u) = s.pod_uid {
            w.put(tag::POD_UID, &u.to_le_bytes());
        }
    }
    if let Some(v) = r.act_delivered_mu {
        w.put_u32(tag::ACT_DELIVERED_MU, v);
    }
    if let Some(h) = &r.history {
        w.put_u32(tag::NEXT_EVENT_ID, h.next_event_id);
        w.put_u32(tag::OLDEST_EVENT_ID, h.oldest_event_id);
        for e in h.events.iter().take(HIST_MAX_PER_RESPONSE) {
            put_event(&mut w, e);
        }
    }
    if let Some(d) = &r.diag {
        if r.status.is_none() {
            w.put(tag::DIAG_SUMMARY, &d.to_bytes());
        }
    }
    if let Some(f) = &r.fault_log {
        w.put_u32(tag::NEXT_DIAG_ID, f.next_id);
        w.put_u32(tag::OLDEST_DIAG_ID, f.oldest_id);
        if !f.latched.is_empty() {
            let mut b = [0u8; DIAG_LATCHED_MAX * 4];
            for (i, c) in f.latched.iter().take(DIAG_LATCHED_MAX).enumerate() {
                b[i * 4..i * 4 + 4].copy_from_slice(&c.to_le_bytes());
            }
            w.put(tag::DIAG_LATCHED, &b[..f.latched.len().min(DIAG_LATCHED_MAX) * 4]);
        }
        for rec in f.records.iter().take(DIAG_RECORDS_PER_RESPONSE) {
            w.put(tag::DIAG_RECORD, &rec.to_bytes());
        }
    }
    if let Some(t) = &r.selftest {
        let mut b = [0u8; SELFTEST_TLV_LEN];
        b[0] = t.state;
        b[1] = t.kind;
        b[2..4].copy_from_slice(&t.steps_passed.to_le_bytes());
        b[4..6].copy_from_slice(&t.steps_failed.to_le_bytes());
        w.put(tag::SELFTEST_STATE, &b);
    }
    if let Some(c) = r.diag_code {
        w.put_u32(tag::DIAG_CODE, c);
    }
    w.finish().ok_or(Error::TooLarge)
}

#[derive(Default)]
struct Acc {
    result: Option<u8>,
    status: Status,
    has_status: bool,
    act: Option<u32>,
    next_event_id: u32,
    oldest_event_id: u32,
    has_history: bool,
    events: heapless::Vec<HistoryEvent, HIST_MAX_PER_RESPONSE>,
    // diagnostics: wrong sizes are skipped (a future schema may change a size), never a frame error
    diag: Option<DiagSummary>,
    fru_health: Option<u64>,
    pod_uid: Option<u64>,
    has_fault_log: bool,
    diag_next: u32,
    diag_oldest: u32,
    diag_latched: heapless::Vec<u32, DIAG_LATCHED_MAX>,
    diag_records: heapless::Vec<DiagRecord, DIAG_RECORDS_PER_RESPONSE>,
    selftest: Option<SelfTestState>,
    diag_code: Option<u32>,
}

fn rd64(p: &[u8]) -> u64 {
    let mut b = [0u8; 8];
    b.copy_from_slice(&p[..8]);
    u64::from_le_bytes(b)
}

fn take_tag(o: &mut Acc, type_: u8, t: u8, v: &[u8]) -> bool {
    let vl = v.len();
    let s = &mut o.status;
    macro_rules! need {
        ($n:expr) => {
            if vl != $n {
                return false;
            }
        };
    }
    match t {
        tag::RESULT => {
            need!(1);
            o.result = Some(v[0]);
        }
        tag::STATE_FLAGS => {
            need!(2);
            s.flags = rd16(v);
            o.has_status = true;
        }
        tag::FAULT_MASK => {
            need!(2);
            s.faults = rd16(v);
        }
        tag::RESERVOIR_MU => {
            need!(4);
            s.reservoir_mu = rd32(v);
        }
        tag::BATTERY_MV => {
            need!(2);
            s.battery_mv = rd16(v);
        }
        tag::BOLUS_REMAINING_MU => {
            need!(4);
            s.bolus_remaining_mu = rd32(v);
        }
        tag::TEMP_RATE_MU_H => {
            need!(2);
            s.temp_rate_mu_h = rd16(v);
        }
        tag::TEMP_REMAINING_MIN => {
            need!(2);
            s.temp_remaining_min = rd16(v);
        }
        tag::CURRENT_RATE_MU_H => {
            need!(2);
            s.current_rate_mu_h = rd16(v);
        }
        tag::DELIVERED_MU => {
            need!(4);
            s.delivered_mu = rd32(v);
        }
        tag::SCHEDULED_MU => {
            need!(4);
            s.scheduled_mu = rd32(v);
        }
        tag::FW_VERSION => {
            need!(2);
            s.fw_version = rd16(v);
        }
        tag::LAST_SEQ => {
            need!(2);
            s.last_seq = rd16(v);
        }
        tag::DRIVE_CAL => {
            need!(DRIVE_CAL_TLV_LEN);
            s.cal_drive_id = rd16(v);
            s.cal_uu_per_step = rd32(&v[2..]);
            s.cal_steps_per_rev = rd16(&v[6..]);
            s.cal_gear_ratio_x100 = rd16(&v[8..]);
        }
        tag::POD_INFO => {
            need!(POD_INFO_TLV_LEN);
            s.pair_id = rd32(v);
            s.role = v[4];
            s.delivery_state = v[5];
            s.wear_s = rd32(&v[6..]);
        }
        tag::DRAW_REQUESTED_MU => {
            need!(4);
            s.draw_requested_mu = rd32(v);
        }
        tag::DRAW_STATE => {
            need!(1);
            s.draw_state = v[0];
        }
        tag::DRAW_DONE_MU => {
            need!(4);
            s.draw_done_mu = rd32(v);
        }
        tag::ACT_DELIVERED_MU => {
            need!(4);
            o.act = Some(rd32(v));
        }
        tag::NEXT_EVENT_ID => {
            need!(4);
            s.next_event_id = rd32(v);
            o.next_event_id = rd32(v);
        }
        tag::OLDEST_EVENT_ID => {
            need!(4);
            o.oldest_event_id = rd32(v);
            o.has_history = type_ == cmd::GET_HISTORY;
        }
        tag::HISTORY_EVENT => {
            need!(EVENT_TLV_LEN);
            let ev = HistoryEvent {
                id: rd32(v),
                time_s: rd32(&v[4..]),
                kind: v[8],
                a: rd32(&v[9..]) as i32,
                b: rd32(&v[13..]) as i32,
            };
            if o.events.push(ev).is_err() {
                return false;
            }
        }
        tag::DIAG_SUMMARY => o.diag = DiagSummary::from_bytes(v),
        tag::FRU_HEALTH => {
            if vl == 8 {
                o.fru_health = Some(rd64(v));
            }
        }
        tag::POD_UID => {
            if vl == 8 {
                o.pod_uid = Some(rd64(v));
            }
        }
        tag::NEXT_DIAG_ID => {
            if vl == 4 {
                o.diag_next = rd32(v);
            }
        }
        tag::OLDEST_DIAG_ID => {
            if vl == 4 {
                o.diag_oldest = rd32(v);
                o.has_fault_log = type_ == cmd::GET_FAULT_LOG;
            }
        }
        tag::DIAG_LATCHED => {
            if vl >= 4 && vl % 4 == 0 && vl <= DIAG_LATCHED_MAX * 4 {
                for c in v.chunks_exact(4) {
                    let _ = o.diag_latched.push(rd32(c));
                }
            }
        }
        tag::DIAG_RECORD => {
            if let Some(r) = DiagRecord::from_bytes(v) {
                if o.diag_records.push(r).is_err() {
                    return false; // more than the 4 a response can carry: a malformed frame
                }
            }
        }
        tag::SELFTEST_STATE => {
            if vl == SELFTEST_TLV_LEN {
                o.selftest = Some(SelfTestState { state: v[0], kind: v[1], steps_passed: rd16(&v[2..]), steps_failed: rd16(&v[4..]) });
            }
        }
        tag::DIAG_CODE => {
            if vl == 4 {
                o.diag_code = Some(rd32(v));
            }
        }
        _ => {}
    }
    true
}

/// Decode a response payload. A missing `RESULT` tag is a frame error.
pub fn decode_response(type_: u8, seq: u16, payload: &[u8]) -> Result<Response, Error> {
    let mut o = Acc::default();
    for item in TlvReader::new(payload) {
        let (t, v) = item.map_err(|_| Error::Frame)?;
        if !take_tag(&mut o, type_, t, v) {
            return Err(Error::Frame);
        }
    }
    let result = o.result.ok_or(Error::Frame)?;
    let status = o.has_status.then(|| {
        let mut s = o.status;
        s.diag = o.diag;
        s.fru_health = o.fru_health;
        s.pod_uid = o.pod_uid;
        s
    });
    Ok(Response {
        diag: if o.has_status { None } else { o.diag },
        fault_log: o.has_fault_log.then(|| FaultLog {
            next_id: o.diag_next,
            oldest_id: o.diag_oldest,
            latched: o.diag_latched.clone(),
            records: o.diag_records.clone(),
        }),
        selftest: o.selftest,
        diag_code: o.diag_code,
        type_,
        seq,
        result,
        status,
        act_delivered_mu: o.act,
        history: o.has_history.then_some(History {
            next_event_id: o.next_event_id,
            oldest_event_id: o.oldest_event_id,
            events: o.events,
        }),
    })
}

/// Encode an unsolicited notification frame payload (`kind`, `arg`).
pub fn encode_notification_payload(kind: u8, arg: u32, out: &mut [u8]) -> Result<usize, Error> {
    encode_notification_payload_ex(kind, arg, None, out)
}

/// Like [`encode_notification_payload`], with the complete diagnostic record of a
/// `DIAG_RAISED` notification (so the app needs no round trip).
pub fn encode_notification_payload_ex(kind: u8, arg: u32, record: Option<&DiagRecord>, out: &mut [u8]) -> Result<usize, Error> {
    let mut w = TlvWriter::new(out);
    w.put_u8(tag::NOTIFY_KIND, kind);
    w.put_u32(tag::NOTIFY_ARG, arg);
    if let Some(r) = record {
        w.put(tag::DIAG_RECORD, &r.to_bytes());
    }
    w.finish().ok_or(Error::TooLarge)
}

/// Decode a notification payload (the phone side; used by tests and the simulator).
pub fn decode_notification_payload(payload: &[u8]) -> Result<NotifyBody, Error> {
    let (mut kind, mut arg, mut record) = (None, None, None);
    for item in TlvReader::new(payload) {
        let (t, v) = item.map_err(|_| Error::Frame)?;
        match t {
            tag::NOTIFY_KIND if v.len() == 1 => kind = Some(v[0]),
            tag::NOTIFY_ARG if v.len() == 4 => arg = Some(rd32(v)),
            tag::DIAG_RECORD => record = DiagRecord::from_bytes(v),
            _ => {}
        }
    }
    Ok(NotifyBody { kind: kind.ok_or(Error::Frame)?, arg: arg.ok_or(Error::Frame)?, record })
}
