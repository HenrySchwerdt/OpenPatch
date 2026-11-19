//! Golden wire frames of a REAL cup pod (`Nfp608_26_45CupMiter1_1`, production `STRICT` config) driven through the whole bench
//! flow of the phone: pair, assisted pressure fill, activate, prime (with the `Hourly` take-up retry), resume, boluses, temp
//! basal, history, refused commands, a replayed frame, release. Written to `docs/vectors/wire-v1-scenarios.json` and consumed by
//! the Swift suite (`OpenPatchCoreTests/WireGoldenTests`): the Swift encoder must produce every request byte for byte and the
//! Swift decoder must read every response of the pod.
//!
//! The file is written by this test (`OPENPATCH_WRITE_VECTORS=1 cargo test -p openpatch-core --test wire_vectors`) and then only
//! verified: a wire change that is not an intended, re-generated vector change fails here and in the Swift suite.
//! TEST PROJECT: water only, bench only.
mod common;
use common::*;
use openpatch_core::drive_cal::{DriveCal, NFP_608_2645_CUP_MITER_1_1 as CUP};
use openpatch_core::limits::*;
use openpatch_core::*;
use openpatch_proto::{self as proto, cmd, BasalSeg, Command, CommandBody, Error as WireError, NoCrypto, Response, Session};
use serde_json::{json, Value};
use std::path::PathBuf;

const SALT: [u8; 4] = [1, 2, 3, 4];
const TIME_OF_DAY_MS: u32 = 43_200_000;
const PAIR: u32 = 0xCAFE_0001;

fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}

fn session() -> Session<NoCrypto> {
    Session::new(NoCrypto, false, SALT, true)
}

/// One cup pod plus the two plaintext sessions of a link (phone side seals, pod side opens).
struct Rig {
    pod: Pump<MockHal>,
    hal: MockHal,
    phone: Session<NoCrypto>,
    link: Session<NoCrypto>,
    steps: Vec<Value>,
}

fn status_json(r: &Response) -> Value {
    let Some(s) = &r.status else { return Value::Null };
    json!({
        "flags": s.flags, "faults": s.faults, "battery_mv": s.battery_mv, "temp_rate_mu_h": s.temp_rate_mu_h,
        "temp_remaining_min": s.temp_remaining_min, "current_rate_mu_h": s.current_rate_mu_h, "fw_version": s.fw_version,
        "reservoir_mu": s.reservoir_mu, "bolus_remaining_mu": s.bolus_remaining_mu, "delivered_mu": s.delivered_mu,
        "scheduled_mu": s.scheduled_mu, "next_event_id": s.next_event_id, "last_seq": s.last_seq,
        "cal_drive_id": s.cal_drive_id, "cal_steps_per_rev": s.cal_steps_per_rev, "cal_gear_ratio_x100": s.cal_gear_ratio_x100,
        "cal_uu_per_step": s.cal_uu_per_step, "pair_id": s.pair_id, "wear_s": s.wear_s, "role": s.role,
        "delivery_state": s.delivery_state, "draw_state": s.draw_state, "draw_requested_mu": s.draw_requested_mu,
        "draw_done_mu": s.draw_done_mu,
    })
}

fn history_json(r: &Response) -> Value {
    let Some(h) = &r.history else { return Value::Null };
    json!({
        "next_event_id": h.next_event_id, "oldest_event_id": h.oldest_event_id,
        "events": h.events.iter().map(|e| json!({"id": e.id, "time_s": e.time_s, "kind": e.kind, "a": e.a, "b": e.b})).collect::<Vec<_>>(),
    })
}

impl Rig {
    fn new() -> Self {
        let hal = MockHal::new();
        {
            let mut s = hal.st();
            s.counts_per_step = 8; // 4096 angle counts / 529 steps = 7.74 per step
            s.delivered_pct = 97;
            s.docked = false; // a fresh pod sits on the bench: the assisted fill needs it undocked
        }
        let rec = DriveCal::from_preset(&CUP);
        let pod = Pump::new(hal.clone(), Some(&rec), CAPACITY_100, 1); // production config (STRICT), no `set_config`
        Rig { pod, hal, phone: session(), link: session(), steps: Vec::new() }
    }

    fn run(&mut self, secs: u64) {
        run_secs(&mut self.pod, &self.hal, secs);
    }

    /// Phone -> pod: encode with the proto encoder (time of day first, as every command of the Swift transport), pass the
    /// frame to the pod, record both wire frames and what the pod answered.
    fn send(&mut self, name: &str, seq: u16, body: CommandBody) -> Response {
        let c = Command { seq, time_of_day_ms: Some(TIME_OF_DAY_MS), body };
        let mut payload = [0u8; 128];
        let n = proto::encode_command_payload(&c, &mut payload).unwrap();
        let mut req = [0u8; proto::FRAME_MAX];
        let rn = self.phone.seal(false, c.body.type_id(), seq, false, &payload[..n], &mut req).unwrap();
        self.exchange(name, c.body.type_id(), seq, &payload[..n], &req[..rn])
    }

    fn exchange(&mut self, name: &str, ty: u8, seq: u16, payload: &[u8], req: &[u8]) -> Response {
        let mut out = [0u8; proto::FRAME_MAX];
        let request = json!({"type": ty, "seq": seq, "payload": hex(payload), "wire": hex(req)});
        match self.pod.handle_frame(&mut self.link, req, &mut out) {
            Ok(m) => {
                let f = proto::decode_frame(&out[..m]).unwrap();
                let r = proto::decode_response(f.type_ & !proto::RSP_BIT, f.seq, f.payload).unwrap();
                self.steps.push(json!({
                    "name": name, "request": request,
                    "response": {
                        "type": f.type_, "seq": f.seq, "payload": hex(f.payload), "wire": hex(&out[..m]),
                        "result": r.result, "status": status_json(&r), "history": history_json(&r),
                        "act_delivered_mu": r.act_delivered_mu,
                    },
                    "dropped": Value::Null,
                }));
                r
            }
            Err(e) => {
                // A frame the pod drops without any answer (replay, ...): the phone sees a timeout.
                self.steps.push(json!({"name": name, "request": request, "response": Value::Null, "dropped": format!("{e:?}")}));
                Response { result: e.code(), ..Default::default() }
            }
        }
    }

    fn ok(&mut self, name: &str, seq: u16, body: CommandBody) -> Response {
        let r = self.send(name, seq, body);
        assert_eq!(r.result, 0, "{name}");
        r
    }
}

fn segs(v: &[(u8, u16)]) -> proto::BasalSegs {
    let mut s = proto::BasalSegs::new();
    for (slot, rate) in v {
        s.push(BasalSeg { start_slot: *slot, rate_mu_h: *rate }).unwrap();
    }
    s
}

/// Pair, assisted fill, activate, prime, resume, doses, errors, release: the cup pod as the phone drives it.
fn bench_flow() -> Value {
    let mut r = Rig::new();
    let mut seq = 0u16;
    let mut next = || {
        seq += 1;
        seq
    };
    r.ok("get_status_fresh", next(), CommandBody::GetStatus);
    r.ok("set_pairing", next(), CommandBody::SetPairing { pair_id: PAIR, role: 1 });
    // ---- refused fills first ----
    let e = r.send("assisted_fill_cancel_without_draw", next(), CommandBody::AssistedFill { amount_mu: 0 });
    assert_eq!(e.result, WireError::NotFound.code());
    let e = r.send("assisted_fill_too_small", next(), CommandBody::AssistedFill { amount_mu: 5 });
    assert_eq!(e.result, WireError::BadArg.code());
    let e = r.send("assisted_fill_above_capacity", next(), CommandBody::AssistedFill { amount_mu: 100_001 });
    assert_eq!(e.result, WireError::Limit.code());
    // ---- the assisted pressure fill: the pod retracts, the user pushes ----
    r.ok("assisted_fill_20u", next(), CommandBody::AssistedFill { amount_mu: 20_000 });
    r.run(1);
    r.ok("get_status_drawing", next(), CommandBody::GetStatus);
    let e = r.send("assisted_fill_busy", next(), CommandBody::AssistedFill { amount_mu: 1_000 });
    assert_eq!(e.result, WireError::Busy.code());
    run_draw(&mut r.pod, &r.hal);
    r.ok("get_status_draw_done", next(), CommandBody::GetStatus);
    // ---- dock, activate with a three segment schedule ----
    r.hal.st().docked = true;
    r.run(1);
    let schedule = segs(&[(0, 800), (12, 1250), (36, 600)]);
    r.ok("activate", next(), CommandBody::Activate { pair_id: PAIR, activation_id: 7, schedule, temp: None });
    // ---- prime: the first answers `Hourly` (take-up of the lost motion), repeat after a minute ----
    let mut n_prime = 0;
    loop {
        n_prime += 1;
        let p = r.send(&format!("prime_71_steps_try_{n_prime}"), next(), CommandBody::FillPrime { sub_op: 2, fill_mu: 0, prime_steps: 71 });
        if p.result == 0 {
            break;
        }
        assert_eq!(p.result, WireError::Hourly.code(), "prime");
        assert!(n_prime < 6);
        r.run(61);
    }
    assert!(n_prime >= 2, "the cup pod needs the take-up retry after an assisted fill");
    r.ok("get_status_primed", next(), CommandBody::GetStatus);
    r.ok("set_basal_schedule", next(), CommandBody::SetBasalSchedule(segs(&[(0, 800), (12, 1250)])));
    r.ok("resume", next(), CommandBody::Resume);
    r.ok("get_status_running", next(), CommandBody::GetStatus);
    // ---- doses ----
    r.ok("bolus_smb_0_05u", next(), CommandBody::Bolus { amount_mu: 50 });
    r.ok("get_status_after_smb", next(), CommandBody::GetStatus);
    r.run(5);
    r.ok("bolus_2u", next(), CommandBody::Bolus { amount_mu: 2_000 });
    r.run(3);
    r.ok("get_status_bolus_active", next(), CommandBody::GetStatus);
    r.ok("cancel_bolus", next(), CommandBody::CancelBolus);
    let e = r.send("cancel_bolus_none_running", next(), CommandBody::CancelBolus);
    assert_eq!(e.result, WireError::NotFound.code());
    r.ok("set_temp_basal_1_5uph_30min", next(), CommandBody::SetTempBasal { rate_mu_h: 1_500, duration_min: 30 });
    r.run(2);
    r.ok("get_status_temp_active", next(), CommandBody::GetStatus);
    r.ok("cancel_temp_basal", next(), CommandBody::CancelTempBasal);
    r.ok("get_history_all", next(), CommandBody::GetHistory { from_id: 0, max_events: 10 });
    r.ok("get_history_page_2", next(), CommandBody::GetHistory { from_id: 10, max_events: 10 });
    // ---- refusals the phone has to map ----
    let e = r.send("bolus_above_hard_limit", next(), CommandBody::Bolus { amount_mu: 30_000 });
    assert_eq!(e.result, WireError::Limit.code());
    let e = r.send("assisted_fill_while_running", next(), CommandBody::AssistedFill { amount_mu: 1_000 });
    assert_eq!(e.result, WireError::NotSuspended.code());
    r.ok("suspend", next(), CommandBody::Suspend);
    let e = r.send("bolus_while_suspended", next(), CommandBody::Bolus { amount_mu: 50 });
    assert_eq!(e.result, WireError::Suspended.code());
    let e = r.send("assisted_fill_while_docked", next(), CommandBody::AssistedFill { amount_mu: 1_000 });
    assert_eq!(e.result, WireError::Docked.code());
    let e = r.send("fill_prime_unknown_sub_op", next(), CommandBody::FillPrime { sub_op: 9, fill_mu: 0, prime_steps: 0 });
    assert_eq!(e.result, WireError::BadArg.code());
    r.ok("acknowledge_all", next(), CommandBody::Acknowledge { fault_mask: 0xFFFF });
    // ---- a replayed frame is dropped without an answer; a fresh seq gets LAST_SEQ back ----
    let replay_seq = 3u16;
    let c = Command { seq: replay_seq, time_of_day_ms: Some(TIME_OF_DAY_MS), body: CommandBody::GetStatus };
    let mut payload = [0u8; 16];
    let n = proto::encode_command_payload(&c, &mut payload).unwrap();
    let mut req = [0u8; proto::FRAME_MAX];
    let rn = r.phone.seal(false, cmd::GET_STATUS, replay_seq, false, &payload[..n], &mut req).unwrap();
    r.exchange("replayed_get_status_is_dropped", cmd::GET_STATUS, replay_seq, &payload[..n], &req[..rn]);
    r.ok("get_status_after_jump", 1_000, CommandBody::GetStatus);
    // ---- release ----
    r.ok("release", 1_001, CommandBody::Release { pair_id: PAIR });
    let e = r.send("bolus_after_release", 1_002, CommandBody::Bolus { amount_mu: 50 });
    assert_ne!(e.result, 0, "a released pod refuses delivery");
    r.ok("get_status_released", 1_003, CommandBody::GetStatus);
    json!({"name": "cup_bench_flow", "preset": {"id": 0x26, "name": "nfp-608-26-45-cup-miter-1-1", "uu_per_step_floor": CUP.cal().micro_u_floor()}, "steps": r.steps})
}

/// The user cancels a fill, and a fill that stalls: the pod reports what it actually drew.
fn fill_abort_and_stall() -> Value {
    let mut r = Rig::new();
    r.ok("set_pairing", 1, CommandBody::SetPairing { pair_id: PAIR, role: 1 });
    r.ok("assisted_fill_20u", 2, CommandBody::AssistedFill { amount_mu: 20_000 });
    r.run(2);
    r.ok("assisted_fill_cancel", 3, CommandBody::AssistedFill { amount_mu: 0 });
    r.ok("get_status_aborted", 4, CommandBody::GetStatus);
    r.hal.st().reverse_limit = 100; // the plunger hits the rear stop after 100 steps of every chunk
    r.ok("assisted_fill_30u", 5, CommandBody::AssistedFill { amount_mu: 30_000 });
    run_draw(&mut r.pod, &r.hal);
    r.ok("get_status_stalled", 6, CommandBody::GetStatus);
    json!({"name": "fill_abort_and_stall", "preset": {"id": 0x26, "name": "nfp-608-26-45-cup-miter-1-1", "uu_per_step_floor": CUP.cal().micro_u_floor()}, "steps": r.steps})
}

fn build() -> Value {
    json!({
        "description": "OpenPatch wire v1 scenarios of a real cup pod (Nfp608_26_45CupMiter1_1 = DRIVE_CAL id 0x26, production STRICT config), \
generated by firmware-rs/openpatch-core/tests/wire_vectors.rs and consumed by ios/OpenPatchKit/OpenPatchCore/Tests/OpenPatchCoreTests/WireGoldenTests.swift. \
Plaintext frames (header, TLV, real CRC-16); every command carries TIME_OF_DAY_MS = 43200000 as its FIRST tag. All bytes are hex. \
Steps are in order: the pod state evolves from step to step.",
        "time_of_day_ms": TIME_OF_DAY_MS,
        "scenarios": [bench_flow(), fill_abort_and_stall()],
    })
}

fn path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../docs/vectors/wire-v1-scenarios.json")
}

#[test]
fn golden_file_is_up_to_date() {
    let want = serde_json::to_string_pretty(&build()).unwrap() + "\n";
    if std::env::var("OPENPATCH_WRITE_VECTORS").is_ok() {
        std::fs::write(path(), &want).unwrap();
    }
    let have = std::fs::read_to_string(path()).expect("docs/vectors/wire-v1-scenarios.json (generate with OPENPATCH_WRITE_VECTORS=1)");
    assert_eq!(have, want, "wire-v1-scenarios.json is stale: wire format or pod behaviour changed? regenerate with OPENPATCH_WRITE_VECTORS=1 and review");
}

#[test]
fn scenario_covers_the_cup_pod_facts_the_phone_relies_on() {
    let v = build();
    let flow = &v["scenarios"][0]["steps"];
    let step = |name: &str| flow.as_array().unwrap().iter().find(|s| s["name"] == name).unwrap_or_else(|| panic!("{name}"));
    let st = |name: &str| step(name)["response"]["status"].clone();
    // DRIVE_CAL of the cup preset
    let fresh = st("get_status_fresh");
    assert_eq!((fresh["cal_drive_id"].as_u64(), fresh["cal_uu_per_step"].as_u64()), (Some(0x26), Some(7_030)));
    assert_eq!((fresh["cal_steps_per_rev"].as_u64(), fresh["cal_gear_ratio_x100"].as_u64()), (Some(20), Some(2645)));
    // the fill: DRAWING flag while the pod retracts, DONE with the drawn volume, PRIME_REQUIRED afterwards
    let drawing = st("get_status_drawing");
    assert_eq!(drawing["draw_state"], 1);
    assert_ne!(drawing["flags"].as_u64().unwrap() & u64::from(proto::st::DRAWING), 0);
    let done = st("get_status_draw_done");
    assert_eq!(done["draw_state"], 2);
    assert_ne!(done["flags"].as_u64().unwrap() & u64::from(proto::st::PRIME_REQUIRED), 0);
    assert!(done["draw_done_mu"].as_u64().unwrap() <= 20_000 && done["draw_done_mu"].as_u64().unwrap() >= 19_900);
    assert_eq!(done["reservoir_mu"], done["draw_done_mu"], "the reservoir is exactly what was drawn");
    // a replayed frame gets no answer
    assert!(step("replayed_get_status_is_dropped")["dropped"].is_string());
    // LAST_SEQ after the jump
    assert_eq!(st("get_status_after_jump")["last_seq"], 1_000);
}
