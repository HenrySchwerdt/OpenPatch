//! Command payload codec (TLV). Mirrors `openpatch_msg.c` exactly, including its quirks:
//! unknown tags and tags of other commands are skipped, but some length checks still apply
//! (TIME_OF_DAY_MS and PAIR_ID are length-checked for every command type).

use crate::consts::*;
use crate::error::Error;
use crate::msg::*;
use crate::tlv::{rd16, rd32, TlvReader, TlvWriter};

fn known_cmd(t: u8) -> bool {
    (cmd::GET_STATUS..=cmd::CLEAR_DIAG).contains(&t)
}

fn put_segs(w: &mut TlvWriter<'_>, segs: &BasalSegs) {
    for s in segs.iter().take(BASAL_SEGMENTS_MAX) {
        let r = s.rate_mu_h.to_le_bytes();
        w.put(tag::BASAL_SEG, &[s.start_slot, r[0], r[1]]);
    }
}

/// Encode the TLV payload of a command (no framing).
pub fn encode_command_payload(c: &Command, out: &mut [u8]) -> Result<usize, Error> {
    let mut w = TlvWriter::new(out);
    if let Some(t) = c.time_of_day_ms {
        w.put_u32(tag::TIME_OF_DAY_MS, t);
    }
    match &c.body {
        CommandBody::SetBasalSchedule(s) => put_segs(&mut w, s),
        CommandBody::SetTempBasal { rate_mu_h, duration_min } => {
            w.put_u16(tag::RATE_MU_H, *rate_mu_h);
            w.put_u16(tag::DURATION_MIN, *duration_min);
        }
        CommandBody::Bolus { amount_mu } => w.put_u32(tag::AMOUNT_MU, *amount_mu),
        CommandBody::FillPrime { sub_op, fill_mu, prime_steps } => {
            w.put_u8(tag::SUB_OP, *sub_op);
            if *sub_op == SUBOP_FILL {
                w.put_u32(tag::FILL_MU, *fill_mu);
            } else {
                w.put_u16(tag::PRIME_STEPS, *prime_steps);
            }
        }
        CommandBody::Acknowledge { fault_mask } => w.put_u16(tag::FAULT_MASK, *fault_mask),
        CommandBody::GetHistory { from_id, max_events } => {
            w.put_u32(tag::FROM_ID, *from_id);
            w.put_u8(tag::MAX_EVENTS, *max_events);
        }
        CommandBody::SetPairing { pair_id, role } => {
            w.put_u32(tag::PAIR_ID, *pair_id);
            w.put_u8(tag::ROLE, *role);
        }
        CommandBody::Release { pair_id } => w.put_u32(tag::PAIR_ID, *pair_id),
        CommandBody::FillDraw { amount_mu } => w.put_u32(tag::FILL_MU, *amount_mu),
        CommandBody::GetFaultLog { from_id, max_events } => {
            w.put_u32(tag::FROM_ID, *from_id);
            w.put_u8(tag::MAX_EVENTS, *max_events);
        }
        CommandBody::RunSelfTest { sub_op } => w.put_u8(tag::SUB_OP, *sub_op),
        CommandBody::ClearDiag { code } => w.put_u32(tag::DIAG_CODE, *code),
        CommandBody::Activate { pair_id, activation_id, schedule, temp } => {
            w.put_u32(tag::PAIR_ID, *pair_id);
            w.put_u32(tag::ACTIVATION_ID, *activation_id);
            put_segs(&mut w, schedule);
            if let Some((rate, min)) = temp {
                w.put_u16(tag::RATE_MU_H, *rate);
                w.put_u16(tag::DURATION_MIN, *min);
            }
        }
        CommandBody::GetStatus | CommandBody::CancelTempBasal | CommandBody::CancelBolus | CommandBody::Suspend | CommandBody::Resume => {}
    }
    w.finish().ok_or(Error::TooLarge)
}

#[derive(Default)]
struct Acc {
    time: Option<u32>,
    segs: BasalSegs,
    amount: Option<u32>,
    rate: Option<u16>,
    duration: Option<u16>,
    sub_op: Option<u8>,
    fill: u32,
    fill_seen: bool,
    prime: u16,
    fault_mask: u16,
    from_id: u32,
    max_events: u8,
    pair_id: Option<u32>,
    role: u8,
    role_seen: bool,
    activation_id: Option<u32>,
    diag_code: Option<u32>,
}

/// Returns `false` for a malformed TLV (frame error).
fn take_tag(a: &mut Acc, ty: u8, t: u8, v: &[u8]) -> bool {
    let vl = v.len();
    match t {
        tag::TIME_OF_DAY_MS => {
            if vl != 4 {
                return false;
            }
            a.time = Some(rd32(v));
            true
        }
        tag::BASAL_SEG => {
            if ty != cmd::ACTIVATE && ty != cmd::SET_BASAL_SCHEDULE {
                return true;
            }
            if vl != 3 {
                return false;
            }
            a.segs.push(BasalSeg { start_slot: v[0], rate_mu_h: rd16(&v[1..]) }).is_ok()
        }
        tag::PAIR_ID => {
            if vl != 4 {
                return false;
            }
            if ty == cmd::SET_PAIRING || ty == cmd::RELEASE || ty == cmd::ACTIVATE {
                a.pair_id = Some(rd32(v));
            }
            true
        }
        tag::ROLE => {
            if ty != cmd::SET_PAIRING {
                return true;
            }
            if vl != 1 {
                return false;
            }
            a.role = v[0];
            a.role_seen = true;
            true
        }
        tag::ACTIVATION_ID => {
            if ty != cmd::ACTIVATE {
                return true;
            }
            if vl != 4 {
                return false;
            }
            a.activation_id = Some(rd32(v));
            true
        }
        tag::RATE_MU_H => {
            if ty != cmd::ACTIVATE && ty != cmd::SET_TEMP_BASAL {
                return true;
            }
            if vl != 2 {
                return false;
            }
            a.rate = Some(rd16(v));
            true
        }
        tag::DURATION_MIN => {
            if ty != cmd::ACTIVATE && ty != cmd::SET_TEMP_BASAL {
                return true;
            }
            if vl != 2 {
                return false;
            }
            a.duration = Some(rd16(v));
            true
        }
        tag::AMOUNT_MU => {
            if ty != cmd::BOLUS {
                return true;
            }
            if vl != 4 {
                return false;
            }
            a.amount = Some(rd32(v));
            true
        }
        tag::SUB_OP => {
            if ty != cmd::FILL_PRIME && ty != cmd::RUN_SELF_TEST {
                return true;
            }
            if vl != 1 {
                return false;
            }
            a.sub_op = Some(v[0]);
            true
        }
        tag::FILL_MU => {
            if ty != cmd::FILL_PRIME && ty != cmd::FILL_DRAW {
                return true;
            }
            if vl != 4 {
                return false;
            }
            a.fill = rd32(v);
            a.fill_seen = true;
            true
        }
        tag::PRIME_STEPS => {
            if ty != cmd::FILL_PRIME {
                return true;
            }
            if vl != 2 {
                return false;
            }
            a.prime = rd16(v);
            true
        }
        tag::FAULT_MASK => {
            if ty != cmd::ACKNOWLEDGE {
                return true;
            }
            if vl != 2 {
                return false;
            }
            a.fault_mask = rd16(v);
            true
        }
        tag::FROM_ID => {
            if ty != cmd::GET_HISTORY && ty != cmd::GET_FAULT_LOG {
                return true;
            }
            if vl != 4 {
                return false;
            }
            a.from_id = rd32(v);
            true
        }
        tag::MAX_EVENTS => {
            if ty != cmd::GET_HISTORY && ty != cmd::GET_FAULT_LOG {
                return true;
            }
            if vl != 1 {
                return false;
            }
            a.max_events = v[0];
            true
        }
        tag::DIAG_CODE => {
            if ty != cmd::CLEAR_DIAG {
                return true;
            }
            if vl != 4 {
                return false;
            }
            a.diag_code = Some(rd32(v));
            true
        }
        _ => true, // unknown tags are skipped (forward compatibility)
    }
}

/// Decode a command payload. Errors: `Unsupported` (unknown id), `Frame` (malformed TLV or a
/// mandatory tag missing).
pub fn decode_command(type_: u8, seq: u16, payload: &[u8]) -> Result<Command, Error> {
    if !known_cmd(type_) {
        return Err(Error::Unsupported);
    }
    let mut a = Acc { fault_mask: 0xFFFF, max_events: HIST_MAX_PER_RESPONSE as u8, ..Default::default() };
    for item in TlvReader::new(payload) {
        let (t, v) = item.map_err(|_| Error::Frame)?;
        if !take_tag(&mut a, type_, t, v) {
            return Err(Error::Frame);
        }
    }
    let body = match type_ {
        cmd::GET_STATUS => CommandBody::GetStatus,
        cmd::SET_BASAL_SCHEDULE => {
            if a.segs.is_empty() {
                return Err(Error::Frame);
            }
            CommandBody::SetBasalSchedule(a.segs)
        }
        cmd::SET_TEMP_BASAL => match (a.rate, a.duration) {
            (Some(rate_mu_h), Some(duration_min)) => CommandBody::SetTempBasal { rate_mu_h, duration_min },
            _ => return Err(Error::Frame),
        },
        cmd::CANCEL_TEMP_BASAL => CommandBody::CancelTempBasal,
        cmd::BOLUS => CommandBody::Bolus { amount_mu: a.amount.ok_or(Error::Frame)? },
        cmd::CANCEL_BOLUS => CommandBody::CancelBolus,
        cmd::SUSPEND => CommandBody::Suspend,
        cmd::RESUME => CommandBody::Resume,
        cmd::FILL_PRIME => CommandBody::FillPrime {
            sub_op: a.sub_op.ok_or(Error::Frame)?,
            fill_mu: a.fill,
            prime_steps: a.prime,
        },
        cmd::ACKNOWLEDGE => CommandBody::Acknowledge { fault_mask: a.fault_mask },
        cmd::GET_HISTORY => CommandBody::GetHistory { from_id: a.from_id, max_events: a.max_events },
        cmd::SET_PAIRING => {
            if !a.role_seen {
                return Err(Error::Frame);
            }
            CommandBody::SetPairing { pair_id: a.pair_id.ok_or(Error::Frame)?, role: a.role }
        }
        cmd::FILL_DRAW => {
            if !a.fill_seen {
                return Err(Error::Frame);
            }
            CommandBody::FillDraw { amount_mu: a.fill }
        }
        cmd::GET_FAULT_LOG => CommandBody::GetFaultLog { from_id: a.from_id, max_events: a.max_events },
        cmd::RUN_SELF_TEST => CommandBody::RunSelfTest { sub_op: a.sub_op.ok_or(Error::Frame)? },
        cmd::CLEAR_DIAG => CommandBody::ClearDiag { code: a.diag_code.ok_or(Error::Frame)? },
        cmd::RELEASE => CommandBody::Release { pair_id: a.pair_id.ok_or(Error::Frame)? },
        cmd::ACTIVATE => {
            let pair_id = a.pair_id.ok_or(Error::Frame)?;
            let activation_id = a.activation_id.ok_or(Error::Frame)?;
            if a.segs.is_empty() {
                return Err(Error::Frame);
            }
            let temp = match (a.rate, a.duration) {
                (Some(r), Some(d)) => Some((r, d)),
                (None, None) => None,
                _ => return Err(Error::Frame), // temp basal needs both or neither
            };
            CommandBody::Activate { pair_id, activation_id, schedule: a.segs, temp }
        }
        _ => return Err(Error::Unsupported),
    };
    Ok(Command { seq, time_of_day_ms: a.time, body })
}
