//! Logical (codec-independent) description of a command / response, convertible to the Rust
//! protocol types and to the flat u32 arrays of the C shim. Equality of two `CmdDesc` after
//! `canon()` means "same decoded fields".

use crate::ffi::{CMD_LEN, RSP_LEN};
use crate::rng::Rng;
use openpatch_proto::*;

#[derive(Clone, Debug, PartialEq, Eq, Default)]
pub struct CmdDesc {
    pub ty: u8,
    pub seq: u16,
    pub tod: Option<u32>,
    pub segs: Vec<(u8, u16)>,
    pub rate: u16,
    pub duration: u16,
    pub amount: u32,
    pub sub_op: u8,
    pub fill_mu: u32,
    pub prime: u16,
    pub fault_mask: u16,
    pub from_id: u32,
    pub max_events: u8,
    pub pair_id: u32,
    pub role: u8,
    pub activation_id: u32,
    pub temp: Option<(u16, u16)>,
}

impl CmdDesc {
    pub fn new(ty: u8) -> Self {
        CmdDesc { ty, ..Default::default() }
    }

    /// Zero every field that does not belong to the command type (so decoded values compare).
    pub fn canon(mut self) -> Self {
        let keep = self.clone();
        let mut c = CmdDesc { ty: keep.ty, seq: keep.seq, tod: keep.tod, ..Default::default() };
        match keep.ty {
            cmd::SET_BASAL_SCHEDULE => c.segs = keep.segs,
            cmd::SET_TEMP_BASAL => {
                c.rate = keep.rate;
                c.duration = keep.duration;
            }
            cmd::BOLUS => c.amount = keep.amount,
            cmd::FILL_PRIME => {
                c.sub_op = keep.sub_op;
                c.fill_mu = keep.fill_mu;
                c.prime = keep.prime;
            }
            cmd::ACKNOWLEDGE => c.fault_mask = keep.fault_mask,
            cmd::GET_HISTORY => {
                c.from_id = keep.from_id;
                c.max_events = keep.max_events;
            }
            cmd::SET_PAIRING => {
                c.pair_id = keep.pair_id;
                c.role = keep.role;
            }
            cmd::RELEASE => c.pair_id = keep.pair_id,
            cmd::ACTIVATE => {
                c.pair_id = keep.pair_id;
                c.activation_id = keep.activation_id;
                c.segs = keep.segs;
                c.temp = keep.temp;
            }
            _ => {}
        }
        self = c;
        self
    }

    /// What an encoder drops: sub-op specific fill/prime value.
    pub fn encodable(mut self) -> Self {
        if self.ty == cmd::FILL_PRIME {
            if self.sub_op == SUBOP_FILL {
                self.prime = 0;
            } else {
                self.fill_mu = 0;
            }
        }
        self.canon()
    }

    pub fn to_command(&self) -> Command {
        let segs = || {
            let mut v = BasalSegs::new();
            for &(s, r) in &self.segs {
                let _ = v.push(BasalSeg { start_slot: s, rate_mu_h: r });
            }
            v
        };
        let body = match self.ty {
            cmd::GET_STATUS => CommandBody::GetStatus,
            cmd::SET_BASAL_SCHEDULE => CommandBody::SetBasalSchedule(segs()),
            cmd::SET_TEMP_BASAL => CommandBody::SetTempBasal { rate_mu_h: self.rate, duration_min: self.duration },
            cmd::CANCEL_TEMP_BASAL => CommandBody::CancelTempBasal,
            cmd::BOLUS => CommandBody::Bolus { amount_mu: self.amount },
            cmd::CANCEL_BOLUS => CommandBody::CancelBolus,
            cmd::SUSPEND => CommandBody::Suspend,
            cmd::RESUME => CommandBody::Resume,
            cmd::FILL_PRIME => {
                CommandBody::FillPrime { sub_op: self.sub_op, fill_mu: self.fill_mu, prime_steps: self.prime }
            }
            cmd::ACKNOWLEDGE => CommandBody::Acknowledge { fault_mask: self.fault_mask },
            cmd::GET_HISTORY => CommandBody::GetHistory { from_id: self.from_id, max_events: self.max_events },
            cmd::SET_PAIRING => CommandBody::SetPairing { pair_id: self.pair_id, role: self.role },
            cmd::ACTIVATE => CommandBody::Activate {
                pair_id: self.pair_id,
                activation_id: self.activation_id,
                schedule: segs(),
                temp: self.temp,
            },
            cmd::RELEASE => CommandBody::Release { pair_id: self.pair_id },
            cmd::FILL_DRAW => CommandBody::FillDraw { amount_mu: self.fill_mu },
            other => panic!("CmdDesc::to_command: unknown type {other:#x}"),
        };
        Command { seq: self.seq, time_of_day_ms: self.tod, body }
    }

    pub fn from_command(c: &Command) -> Self {
        let mut d = CmdDesc::new(c.body.type_id());
        d.seq = c.seq;
        d.tod = c.time_of_day_ms;
        let segs = |s: &BasalSegs| s.iter().map(|g| (g.start_slot, g.rate_mu_h)).collect::<Vec<_>>();
        match &c.body {
            CommandBody::SetBasalSchedule(s) => d.segs = segs(s),
            CommandBody::SetTempBasal { rate_mu_h, duration_min } => {
                d.rate = *rate_mu_h;
                d.duration = *duration_min;
            }
            CommandBody::Bolus { amount_mu } => d.amount = *amount_mu,
            CommandBody::FillPrime { sub_op, fill_mu, prime_steps } => {
                d.sub_op = *sub_op;
                d.fill_mu = *fill_mu;
                d.prime = *prime_steps;
            }
            CommandBody::Acknowledge { fault_mask } => d.fault_mask = *fault_mask,
            CommandBody::GetHistory { from_id, max_events } => {
                d.from_id = *from_id;
                d.max_events = *max_events;
            }
            CommandBody::SetPairing { pair_id, role } => {
                d.pair_id = *pair_id;
                d.role = *role;
            }
            CommandBody::Release { pair_id } => d.pair_id = *pair_id,
            CommandBody::Activate { pair_id, activation_id, schedule, temp } => {
                d.pair_id = *pair_id;
                d.activation_id = *activation_id;
                d.segs = segs(schedule);
                d.temp = *temp;
            }
            CommandBody::FillDraw { amount_mu } => d.fill_mu = *amount_mu,
            _ => {}
        }
        d.canon()
    }

    /// Flat layout documented at the top of `csrc/shim.c`.
    pub fn to_flat(&self) -> [u32; CMD_LEN] {
        let mut o = [0u32; CMD_LEN];
        o[0] = self.ty as u32;
        o[1] = self.seq as u32;
        o[2] = self.tod.is_some() as u32;
        o[3] = self.tod.unwrap_or(0);
        o[4] = self.segs.len() as u32;
        for (i, &(s, r)) in self.segs.iter().take(24).enumerate() {
            o[5 + i] = s as u32;
            o[29 + i] = r as u32;
        }
        o[53] = self.rate as u32;
        o[54] = self.duration as u32;
        o[55] = self.amount;
        o[56] = self.sub_op as u32;
        o[57] = self.fill_mu;
        o[58] = self.prime as u32;
        o[59] = self.fault_mask as u32;
        o[60] = self.from_id;
        o[61] = self.max_events as u32;
        o[62] = self.pair_id;
        o[63] = self.role as u32;
        o[64] = self.activation_id;
        o[65] = self.temp.is_some() as u32;
        o[66] = self.temp.map(|t| t.0 as u32).unwrap_or(0);
        o[67] = self.temp.map(|t| t.1 as u32).unwrap_or(0);
        o
    }

    pub fn from_flat(o: &[u32; CMD_LEN]) -> Self {
        let n = (o[4] as usize).min(24);
        let d = CmdDesc {
            ty: o[0] as u8,
            seq: o[1] as u16,
            tod: (o[2] != 0).then_some(o[3]),
            segs: (0..n).map(|i| (o[5 + i] as u8, o[29 + i] as u16)).collect(),
            rate: o[53] as u16,
            duration: o[54] as u16,
            amount: o[55],
            sub_op: o[56] as u8,
            fill_mu: o[57],
            prime: o[58] as u16,
            fault_mask: o[59] as u16,
            from_id: o[60],
            max_events: o[61] as u8,
            pair_id: o[62],
            role: o[63] as u8,
            activation_id: o[64],
            temp: (o[65] != 0).then_some((o[66] as u16, o[67] as u16)),
        };
        d.canon()
    }

    /// Random logical command with arbitrary field values (types 0x01..=0x0E), valid for the
    /// encoder (sub_op 1/2/other, schedules of 1..=24 segments for the types that need them).
    pub fn random(r: &mut Rng) -> Self {
        let ty = r.range(1, 0x0E) as u8;
        let mut d = CmdDesc::new(ty);
        d.seq = r.below(0xFFFF) as u16;
        d.tod = r.chance(300).then(|| r.u32());
        let nseg = r.range(1, 24) as usize;
        d.segs = (0..nseg).map(|_| (r.below(256) as u8, r.below(65536) as u16)).collect();
        d.rate = r.below(65536) as u16;
        d.duration = r.below(65536) as u16;
        d.amount = r.u32();
        d.sub_op = *r.pick(&[SUBOP_FILL, SUBOP_PRIME, SUBOP_PRIME, 0, 3, 255]);
        d.fill_mu = r.u32();
        d.prime = r.below(65536) as u16;
        d.fault_mask = r.below(65536) as u16;
        d.from_id = r.u32();
        d.max_events = r.below(256) as u8;
        d.pair_id = r.u32();
        d.role = r.below(256) as u8;
        d.activation_id = r.u32();
        d.temp = r.chance(500).then(|| (r.below(65536) as u16, r.below(65536) as u16));
        d.encodable()
    }
}

// ---------------------------------------------------------------------------------------------
// responses
// ---------------------------------------------------------------------------------------------

pub fn rsp_to_flat(r: &Response) -> [u32; RSP_LEN] {
    let mut o = [0u32; RSP_LEN];
    o[0] = r.type_ as u32;
    o[1] = r.seq as u32;
    o[2] = r.result as u32;
    if let Some(s) = &r.status {
        o[3] = 1;
        o[4] = s.flags as u32;
        o[5] = s.faults as u32;
        o[6] = s.battery_mv as u32;
        o[7] = s.temp_rate_mu_h as u32;
        o[8] = s.temp_remaining_min as u32;
        o[9] = s.current_rate_mu_h as u32;
        o[10] = s.fw_version as u32;
        o[11] = s.reservoir_mu;
        o[12] = s.bolus_remaining_mu;
        o[13] = s.delivered_mu;
        o[14] = s.scheduled_mu;
        o[15] = s.next_event_id;
        o[16] = s.last_seq as u32;
        o[17] = s.cal_drive_id as u32;
        o[18] = s.cal_steps_per_rev as u32;
        o[19] = s.cal_gear_ratio_x100 as u32;
        o[20] = s.cal_uu_per_step;
        o[21] = s.pair_id;
        o[22] = s.wear_s;
        o[23] = s.role as u32;
        o[24] = s.delivery_state as u32;
    }
    if let Some(a) = r.act_delivered_mu {
        o[25] = 1;
        o[26] = a;
    }
    if let Some(h) = &r.history {
        o[27] = 1;
        o[28] = h.next_event_id;
        o[29] = h.oldest_event_id;
        o[30] = h.events.len() as u32;
        for (i, e) in h.events.iter().enumerate() {
            o[31 + 5 * i] = e.id;
            o[32 + 5 * i] = e.time_s;
            o[33 + 5 * i] = e.kind as u32;
            o[34 + 5 * i] = e.a as u32;
            o[35 + 5 * i] = e.b as u32;
        }
    }
    o
}

pub fn random_status(r: &mut Rng) -> Status {
    Status {
        flags: r.below(65536) as u16 & 0x07FF, // C-known bits only
        faults: r.below(65536) as u16,
        battery_mv: r.below(65536) as u16,
        temp_rate_mu_h: r.below(65536) as u16,
        temp_remaining_min: r.below(65536) as u16,
        current_rate_mu_h: r.below(65536) as u16,
        fw_version: r.below(65536) as u16,
        reservoir_mu: r.u32(),
        bolus_remaining_mu: r.u32(),
        delivered_mu: r.u32(),
        scheduled_mu: r.u32(),
        next_event_id: r.u32(),
        last_seq: r.below(65536) as u16,
        cal_drive_id: r.below(65536) as u16,
        cal_steps_per_rev: r.below(65536) as u16,
        cal_gear_ratio_x100: r.below(65536) as u16,
        cal_uu_per_step: r.u32(),
        pair_id: r.u32(),
        wear_s: r.u32(),
        role: r.below(256) as u8,
        delivery_state: r.below(256) as u8,
        ..Default::default()
    }
}

pub fn random_history(r: &mut Rng) -> History {
    let n = r.below(11) as usize;
    let mut h = History { next_event_id: r.u32(), oldest_event_id: r.u32(), ..Default::default() };
    for _ in 0..n {
        let _ = h.events.push(HistoryEvent {
            id: r.u32(),
            time_s: r.u32(),
            kind: r.below(256) as u8,
            a: r.u32() as i32,
            b: r.u32() as i32,
        });
    }
    h
}
