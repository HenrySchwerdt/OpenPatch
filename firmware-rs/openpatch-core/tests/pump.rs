//! Port of `firmware/tests/test_pump.c` (pump controller + protocol path).
mod common;
use common::*;
use openpatch_core::limits::*;
use openpatch_core::log::{Event, LOG_CAPACITY};
use openpatch_core::*;
use openpatch_proto::{
    self as proto, st, BasalSeg as WireSeg, BasalSegs, Ccm, CcmError, Command, CommandBody, NoCrypto, Response, Session,
    CCM_NONCE_LEN, CCM_TAG_LEN, FLAG_ENCRYPTED, FLAG_RESPONSE, FRAME_HEADER, FRAME_MAX, RSP_BIT, SUBOP_FILL, SUBOP_PRIME,
};

// ---- fixtures ---------------------------------------------------------------------------------

fn steps_of(mu: u32) -> u32 {
    (mu as u64 * 1000 / TEST_UU as u64) as u32
}

fn flat(rate: u32) -> BasalSchedule {
    BasalSchedule::flat(MilliUnitsPerHour(rate))
}

/// C `rig_init`: 200 U capacity, test calibration, restored id 1, never filled (RELAXED config).
fn rig_init() -> (Pump<MockHal>, MockHal) {
    new_pump_cap(CAPACITY_200)
}

/// C `rig_running`: fill + schedule + resume.
fn rig_running(fill_mu: u32, rate: u32) -> (Pump<MockHal>, MockHal) {
    let (mut p, h) = rig_init();
    p.fill(MilliUnits(fill_mu)).unwrap();
    activate(&mut p, rate).unwrap();
    p.resume().unwrap();
    (p, h)
}

fn log_has(p: &Pump<MockHal>, kind: EventType) -> bool {
    log_count(p, kind) > 0
}

fn log_count(p: &Pump<MockHal>, kind: EventType) -> usize {
    let mut e = [Event::default(); LOG_CAPACITY];
    let n = p.log().read(0, &mut e);
    e[..n].iter().filter(|x| x.kind == kind as u8).count()
}

fn has_flag(flags: u16, f: u16) -> bool {
    flags & f != 0
}

fn has_fault(faults: u16, f: Faults) -> bool {
    Faults(faults).intersects(f)
}

// ---- controller tests -------------------------------------------------------------------------

#[test]
fn pump_boots_suspended_with_boot_event_and_restored_ids() {
    let hal = MockHal::new();
    let cal = cal_test();
    let mut p = Pump::new(hal.clone(), Some(&cal), CAPACITY_70, 500);
    let s = p.get_status();
    assert!(has_flag(s.flags, st::SUSPENDED));
    assert!(!has_flag(s.flags, st::FILLED));
    assert_eq!(s.fw_version, FW_VERSION);
    assert_eq!(p.log().oldest_id(), 500);
    assert!(log_has(&p, EventType::Boot));
    assert!(!hal.st().enabled);
}

#[test]
fn pump_basal_hour_delivers_expected_steps_and_updates_reservoir() {
    let (mut p, h) = rig_running(100_000, 1000);
    run_secs(&mut p, &h, 3600);
    assert_eq!(h.st().total_steps, 38);
    assert!(!h.st().stepped_while_disabled);
    assert!(!h.st().enabled); // driver gated off between steps
    let s = p.get_status();
    assert_eq!(s.reservoir_mu, 99_008); // 100000 - 38*26.1 = 99008.2
    assert_eq!(s.delivered_mu, 991);
    assert_eq!(s.faults, 0);
    assert_eq!(s.current_rate_mu_h, 1000);
    assert_eq!(h.st().kicks, 3600);
}

#[test]
fn pump_bolus_flow_and_log() {
    let (mut p, h) = rig_running(100_000, 0);
    p.bolus(MilliUnits(2000)).unwrap();
    run_secs(&mut p, &h, 20);
    let s = p.get_status();
    assert!(has_flag(s.flags, st::BOLUS_ACTIVE));
    assert_eq!(s.bolus_remaining_mu, 1500);
    run_secs(&mut p, &h, 61);
    let s = p.get_status();
    assert!(!has_flag(s.flags, st::BOLUS_ACTIVE));
    assert_eq!(h.st().total_steps, 76); // floor(2000/26.1)
    assert!(log_has(&p, EventType::BolusStart));
    assert!(log_has(&p, EventType::BolusDone));
}

#[test]
fn pump_bolus_rejections() {
    let (mut p, h) = rig_init();
    p.fill(MilliUnits(100_000)).unwrap();
    activate(&mut p, 0).unwrap();
    assert_eq!(p.bolus(MilliUnits(1000)), Err(Error::Suspended));
    let _ = p.resume();
    assert_eq!(p.bolus(MilliUnits(10_050)), Err(Error::Limit));
    assert_eq!(p.bolus(MilliUnits(1025)), Err(Error::BadArg));
    assert_eq!(p.bolus(MilliUnits(10_000)), Ok(()));
    assert_eq!(p.bolus(MilliUnits(1000)), Err(Error::Busy));
    assert_eq!(p.cancel_bolus(), Ok(()));
    run_secs(&mut p, &h, 100); // nothing was delivered after cancel
    assert_eq!(p.bolus(MilliUnits(10_000)), Ok(()));
}

#[test]
fn pump_hourly_cap_rejects_second_large_bolus() {
    let (mut p, h) = rig_running(150_000, 0);
    assert_eq!(p.bolus(MilliUnits(10_000)), Ok(()));
    run_secs(&mut p, &h, 7 * 60); // 10 U at 1.5 U/min = 6.7 min
    assert_eq!(p.bolus(MilliUnits(10_000)), Err(Error::Hourly));
    assert_eq!(p.bolus(MilliUnits(4000)), Ok(()));
}

#[test]
fn pump_bolus_larger_than_reservoir_is_rejected() {
    let (mut p, _h) = rig_running(3000, 0);
    assert_eq!(p.bolus(MilliUnits(4000)), Err(Error::Reservoir));
    let (mut u, _hu) = rig_init(); // never filled, never activated
    assert_eq!(u.resume(), Err(Error::Released));
    assert_eq!(u.bolus(MilliUnits(1000)), Err(Error::Released));
}

#[test]
fn pump_occlusion_stops_everything_until_acknowledged() {
    let (mut p, h) = rig_running(100_000, 0);
    h.st().delivered_pct = 0; // spindle does not move
    assert_eq!(p.bolus(MilliUnits(5000)), Ok(()));
    run_secs(&mut p, &h, 120);
    let s = p.get_status();
    assert!(has_fault(s.faults, Faults::OCCLUSION));
    assert!(has_flag(s.flags, st::ALARM));
    assert!(has_flag(s.flags, st::SUSPENDED));
    assert!(!has_flag(s.flags, st::BOLUS_ACTIVE));
    assert_eq!(h.st().buzzer, Buzzer::Alarm);
    assert!(!h.st().enabled);
    let frozen = h.st().total_steps;
    assert!(frozen < steps_of(2000)); // stopped before 2 U
    run_secs(&mut p, &h, 120);
    assert_eq!(h.st().total_steps, frozen);
    assert!(log_has(&p, EventType::Fault));
    // cannot restart with a latched fault, ack alone does not resume
    assert_eq!(p.resume(), Err(Error::Fault));
    assert_eq!(p.bolus(MilliUnits(1000)), Err(Error::Fault));
    h.st().delivered_pct = 100;
    assert_eq!(p.acknowledge(Faults::ALL), Ok(()));
    assert_eq!(h.st().buzzer, Buzzer::Off);
    let s = p.get_status();
    assert!(has_flag(s.flags, st::SUSPENDED));
    assert_eq!(p.resume(), Ok(()));
    assert!(log_has(&p, EventType::Ack));
}

#[test]
fn pump_encoder_deviation_stops_delivery() {
    let (mut p, h) = rig_running(100_000, 5000);
    h.st().delivered_pct = 80;
    run_secs(&mut p, &h, 1800);
    let s = p.get_status();
    assert!(has_fault(s.faults, Faults::ENCODER_DEVIATION));
    assert!(h.st().total_steps < steps_of(1500));
}

#[test]
fn pump_reservoir_runs_dry_never_over_delivers() {
    let (mut p, h) = rig_running(1000, 5000);
    run_secs(&mut p, &h, 3600);
    let s = p.get_status();
    assert!(has_fault(s.faults, Faults::RESERVOIR_EMPTY));
    assert!(h.st().total_steps <= steps_of(1000));
    assert!(h.st().total_steps >= steps_of(1000) - 2);
    assert!(s.reservoir_mu < 27);
}

#[test]
fn pump_low_reservoir_logged_once() {
    let (mut p, h) = rig_running(10_500, 5000);
    run_secs(&mut p, &h, 600);
    assert_eq!(log_count(&p, EventType::LowReservoir), 1);
    let s = p.get_status();
    assert!(has_flag(s.flags, st::LOW_RESERVOIR));
}

#[test]
fn pump_critical_battery_blocks_delivery() {
    let (mut p, h) = rig_running(100_000, 5000);
    h.st().battery_mv = 3200;
    run_secs(&mut p, &h, 60);
    let s = p.get_status();
    assert!(has_fault(s.faults, Faults::BATTERY_CRITICAL));
    let frozen = h.st().total_steps;
    run_secs(&mut p, &h, 600);
    assert_eq!(h.st().total_steps, frozen);
    assert_eq!(p.acknowledge(Faults::ALL), Err(Error::Persists));
    h.st().battery_mv = 3800;
    run_secs(&mut p, &h, 1);
    assert_eq!(p.acknowledge(Faults::ALL), Ok(()));
}

#[test]
fn pump_low_battery_warning_logged() {
    let (mut p, h) = rig_running(100_000, 0);
    h.st().battery_mv = 3450;
    run_secs(&mut p, &h, 2);
    assert!(log_has(&p, EventType::LowBattery));
    let s = p.get_status();
    assert!(has_flag(s.flags, st::LOW_BATTERY));
    assert_eq!(s.faults, 0);
}

#[test]
fn pump_temp_basal_falls_back_after_comm_loss() {
    let (mut p, h) = rig_running(100_000, 1000);
    assert_eq!(p.set_temp_basal(MilliUnitsPerHour(3000), Minutes(120)), Ok(()));
    run_secs(&mut p, &h, 29 * 60);
    let s = p.get_status();
    assert!(has_flag(s.flags, st::TEMP_ACTIVE));
    assert_eq!(s.current_rate_mu_h, 3000);
    run_secs(&mut p, &h, 2 * 60);
    let s = p.get_status();
    assert!(!has_flag(s.flags, st::TEMP_ACTIVE));
    assert_eq!(s.current_rate_mu_h, 1000);
    assert!(log_has(&p, EventType::TempCommFallback));
}

#[test]
fn pump_temp_basal_validation_and_cancel() {
    let (mut p, _h) = rig_running(100_000, 1000);
    assert_eq!(p.set_temp_basal(MilliUnitsPerHour(5050), Minutes(30)), Err(Error::Limit));
    assert_eq!(p.set_temp_basal(MilliUnitsPerHour(2000), Minutes(31)), Err(Error::BadArg));
    assert_eq!(p.set_temp_basal(MilliUnitsPerHour(2000), Minutes(30)), Ok(()));
    assert_eq!(p.cancel_temp_basal(), Ok(()));
    assert_eq!(p.cancel_temp_basal(), Err(Error::NotFound));
    assert!(log_has(&p, EventType::TempStart));
    assert!(log_has(&p, EventType::TempCancel));
}

#[test]
fn pump_temp_basal_end_is_logged() {
    let (mut p, h) = rig_running(100_000, 1000);
    let _ = p.set_temp_basal(MilliUnitsPerHour(2000), Minutes(30));
    run_secs(&mut p, &h, 31 * 60);
    assert!(log_has(&p, EventType::TempDone));
    assert!(!log_has(&p, EventType::TempCommFallback));
}

#[test]
fn pump_schedule_validation_and_log() {
    let (mut p, _h) = rig_init();
    assert_eq!(p.fill(MilliUnits(50_000)), Ok(()));
    assert_eq!(activate(&mut p, 0), Ok(()));
    assert_eq!(p.set_schedule(&flat(5050)), Err(Error::Limit));
    assert_eq!(p.set_schedule(&flat(1000)), Ok(()));
    assert!(log_has(&p, EventType::BasalSet));
}

#[test]
fn pump_fill_and_prime_rules() {
    let (mut p, h) = rig_init();
    assert_eq!(p.fill(MilliUnits(0)), Err(Error::BadArg));
    assert_eq!(p.fill(MilliUnits(CAPACITY_200.0 + 1)), Err(Error::Limit));
    assert_eq!(p.prime(Pulses(10)), Err(Error::Reservoir)); // nothing filled yet
    assert_eq!(p.fill(MilliUnits(50_000)), Ok(()));
    assert_eq!(p.prime(Pulses(steps_of(MAX_PRIME.0) + 1)), Err(Error::Limit));
    assert_eq!(p.prime(Pulses(0)), Err(Error::BadArg));
    assert_eq!(p.prime(Pulses(20)), Err(Error::Released)); // only the active pod primes
    assert_eq!(activate(&mut p, 0), Ok(()));
    assert_eq!(p.prime(Pulses(20)), Ok(()));
    assert_eq!(h.st().total_steps, 20);
    assert!(!h.st().stepped_while_disabled);
    let s = p.get_status();
    assert_eq!(s.reservoir_mu, 50_000 - 522); // 20 steps = 522 mU
    assert!(log_has(&p, EventType::Fill));
    assert!(log_has(&p, EventType::Prime));
    let _ = p.resume();
    assert_eq!(p.fill(MilliUnits(50_000)), Err(Error::NotSuspended));
    assert_eq!(p.prime(Pulses(5)), Err(Error::NotSuspended));
}

#[test]
fn pump_prime_respects_motor_failure_and_encoder() {
    let (mut p, h) = rig_init();
    let _ = p.fill(MilliUnits(50_000));
    assert_eq!(activate(&mut p, 0), Ok(()));
    h.st().steps_limit = 5; // motor only manages 5 of 20
    assert_eq!(p.prime(Pulses(20)), Err(Error::Fault));
    let s = p.get_status();
    assert!(has_fault(s.faults, Faults::INTERNAL));
    assert_eq!(h.st().total_steps, 5);
}

#[test]
fn pump_motor_shortfall_latches_internal_fault() {
    let (mut p, h) = rig_running(100_000, 5000);
    h.st().steps_limit = 0; // motor refuses to move
    run_secs(&mut p, &h, 120);
    let s = p.get_status();
    assert!(has_fault(s.faults, Faults::INTERNAL));
    assert!(has_flag(s.flags, st::SUSPENDED));
}

#[test]
fn pump_suspend_resume_and_log() {
    let (mut p, h) = rig_running(100_000, 5000);
    assert_eq!(p.suspend(), Ok(()));
    run_secs(&mut p, &h, 600);
    assert_eq!(h.st().total_steps, 0);
    assert_eq!(p.resume(), Ok(()));
    run_secs(&mut p, &h, 600);
    assert!(h.st().total_steps > 0);
    assert!(log_has(&p, EventType::Suspend));
    assert!(log_has(&p, EventType::Resume));
}

#[test]
fn pump_tick_clamps_time_jumps_instead_of_catching_up() {
    let (mut p, h) = rig_running(100_000, 5000);
    h.advance_ms(3_600_000); // main loop stalled for an hour
    p.tick();
    assert_eq!(p.tick_overruns(), 1);
    assert!(h.st().total_steps <= 2); // only 5 s worth
}

#[test]
fn pump_watchdog_is_kicked_every_tick() {
    let (mut p, h) = rig_init();
    run_secs(&mut p, &h, 10);
    assert_eq!(h.st().kicks, 10);
}

// ---- protocol path ----------------------------------------------------------------------------

/// TEST-ONLY fake "CCM": XOR keystream + 8-byte FNV-style tag (port of `firmware/tests/fake_ccm.c`).
/// Not secure; never link into firmware.
#[derive(Default)]
struct FakeCcm {
    accepted_calls: u32,
    last_seq: u16,
}

fn keystream_xor(nonce: &[u8; CCM_NONCE_LEN], input: &[u8], out: &mut [u8]) {
    for (i, b) in input.iter().enumerate() {
        out[i] = b ^ nonce[i % 13].wrapping_add(0x5A).wrapping_add(i as u8);
    }
}

fn tag_of(nonce: &[u8; CCM_NONCE_LEN], aad: &[u8], ct: &[u8]) -> [u8; CCM_TAG_LEN] {
    let mut h: u64 = 1_469_598_103_934_665_603;
    for b in nonce.iter().chain(aad).chain(ct) {
        h = (h ^ *b as u64).wrapping_mul(1_099_511_628_211);
    }
    let mut tag = [0u8; CCM_TAG_LEN];
    for (i, t) in tag.iter_mut().enumerate() {
        *t = (h >> (8 * i)) as u8;
    }
    tag
}

impl Ccm for FakeCcm {
    fn encrypt(
        &mut self,
        nonce: &[u8; CCM_NONCE_LEN],
        aad: &[u8],
        pt: &[u8],
        ct: &mut [u8],
        tag: &mut [u8; CCM_TAG_LEN],
    ) -> Result<(), CcmError> {
        keystream_xor(nonce, pt, ct);
        *tag = tag_of(nonce, aad, ct);
        Ok(())
    }
    fn decrypt(
        &mut self,
        nonce: &[u8; CCM_NONCE_LEN],
        aad: &[u8],
        ct: &[u8],
        tag: &[u8; CCM_TAG_LEN],
        pt: &mut [u8],
    ) -> Result<(), CcmError> {
        if tag_of(nonce, aad, ct) != *tag {
            return Err(CcmError);
        }
        keystream_xor(nonce, ct, pt);
        Ok(())
    }
    fn on_seq_accepted(&mut self, seq: u16) {
        self.accepted_calls += 1;
        self.last_seq = seq;
    }
}

struct Link<C: Ccm> {
    s: Session<C>,
    seq: u16,
}

fn link_plain() -> Link<NoCrypto> {
    Link { s: Session::new(NoCrypto, false, [9, 9, 9, 9], true), seq: 1 }
}

fn body_cmd(body: CommandBody) -> Command {
    Command::new(0, body)
}

/// Send one command through the full frame path and decode the response. Returns the response
/// length alongside it.
fn exchange<C: Ccm>(p: &mut Pump<MockHal>, l: &mut Link<C>, cmd: &mut Command, enc: bool) -> (usize, Response) {
    let mut payload = [0u8; 200];
    let mut frame = [0u8; FRAME_MAX];
    let mut out = [0u8; FRAME_MAX];
    let mut plain = [0u8; FRAME_MAX];
    cmd.seq = l.seq;
    l.seq += 1;
    let ty = cmd.body.type_id();
    let pl = proto::encode_command_payload(cmd, &mut payload).unwrap();
    let n = l.s.seal(false, ty, cmd.seq, enc, &payload[..pl], &mut frame).unwrap();
    assert!(n > 0);
    let m = p.handle_frame(&mut l.s, &frame[..n], &mut out).unwrap();
    let f = proto::decode_frame(&out[..m]).unwrap();
    assert!(f.flags & FLAG_RESPONSE != 0);
    assert_eq!(f.flags & FLAG_ENCRYPTED, if enc { FLAG_ENCRYPTED } else { 0 });
    assert_eq!(f.type_, ty | RSP_BIT);
    assert_eq!(f.seq, cmd.seq);
    let mut pn = f.payload.len();
    let pp: &[u8] = if enc {
        // decrypt the response with the response nonce
        let nonce = l.s.nonce(true, f.seq);
        pn -= CCM_TAG_LEN;
        let mut tag = [0u8; CCM_TAG_LEN];
        tag.copy_from_slice(&f.payload[pn..]);
        l.s.ccm_mut()
            .decrypt(&nonce, &out[..FRAME_HEADER], &f.payload[..pn], &tag, &mut plain[..pn])
            .unwrap();
        &plain[..pn]
    } else {
        f.payload
    };
    let rsp = proto::decode_response(ty, f.seq, &pp[..pn]).unwrap();
    (m, rsp)
}

fn xchg(p: &mut Pump<MockHal>, l: &mut Link<NoCrypto>, body: CommandBody) -> Response {
    exchange(p, l, &mut body_cmd(body), false).1
}

#[test]
fn proto_get_status_over_frames() {
    let (mut p, _h) = rig_running(100_000, 1000);
    let mut l = link_plain();
    let (m, rsp) = exchange(&mut p, &mut l, &mut body_cmd(CommandBody::GetStatus), false);
    assert!(m > 0);
    assert_eq!(rsp.result, 0);
    let s = rsp.status.expect("status");
    assert_eq!(s.reservoir_mu, 100_000);
    assert_eq!(s.current_rate_mu_h, 1000);
    assert!(!has_flag(s.flags, st::SUSPENDED));
    assert_eq!(s.last_seq, 1); // the request itself is the last accepted sequence number
}

#[test]
fn proto_get_status_reports_last_accepted_seq() {
    let (mut p, _h) = rig_running(100_000, 1000);
    let mut l = link_plain();
    let (m, _) = exchange(&mut p, &mut l, &mut body_cmd(CommandBody::Suspend), false);
    assert!(m > 0);
    l.seq = 40; // the phone skips ahead; gaps are legal
    let (m, rsp) = exchange(&mut p, &mut l, &mut body_cmd(CommandBody::GetStatus), false);
    assert!(m > 0);
    assert_eq!(rsp.status.unwrap().last_seq, 40);
    // a pod restoring last_seq after a reboot reports it in the next GetStatus
    let mut restored = link_plain();
    restored.s.restore_last_seq(100);
    restored.seq = 101;
    let (m, rsp) = exchange(&mut p, &mut restored, &mut body_cmd(CommandBody::GetStatus), false);
    assert!(m > 0);
    assert_eq!(rsp.status.unwrap().last_seq, 101);
}

#[test]
fn proto_full_command_set_works_end_to_end() {
    let (mut p, h) = rig_init();
    let mut l = link_plain();
    let seg = |slot: u8, rate: u16| WireSeg { start_slot: slot, rate_mu_h: rate };

    let rsp = xchg(&mut p, &mut l, CommandBody::FillPrime { sub_op: SUBOP_FILL, fill_mu: 120_000, prime_steps: 0 });
    assert_eq!(rsp.result, 0);

    let rsp = xchg(&mut p, &mut l, CommandBody::SetPairing { pair_id: TEST_PAIR, role: 1 });
    assert_eq!(rsp.result, 0);

    let rsp = xchg(
        &mut p,
        &mut l,
        CommandBody::Activate {
            pair_id: TEST_PAIR,
            activation_id: 9,
            schedule: BasalSegs::from_slice(&[seg(0, 800)]).unwrap(),
            temp: None,
        },
    );
    assert_eq!(rsp.result, 0);
    assert_eq!(rsp.status.expect("status").delivery_state, DeliveryState::Active as u8);

    let rsp = xchg(&mut p, &mut l, CommandBody::FillPrime { sub_op: SUBOP_PRIME, fill_mu: 0, prime_steps: 10 });
    assert_eq!(rsp.result, 0);
    assert_eq!(h.st().total_steps, 10);

    let mut c = body_cmd(CommandBody::SetBasalSchedule(BasalSegs::from_slice(&[seg(0, 800), seg(30, 1200)]).unwrap()));
    c.time_of_day_ms = Some(12 * 3_600_000); // seg 30 = 15:00
    let (_, rsp) = exchange(&mut p, &mut l, &mut c, false);
    assert_eq!(rsp.result, 0);
    assert_eq!(p.engine().ms_of_day(), 12 * 3_600_000);

    assert_eq!(xchg(&mut p, &mut l, CommandBody::Resume).result, 0);
    assert_eq!(xchg(&mut p, &mut l, CommandBody::SetTempBasal { rate_mu_h: 2000, duration_min: 60 }).result, 0);
    assert_eq!(xchg(&mut p, &mut l, CommandBody::CancelTempBasal).result, 0);
    assert_eq!(xchg(&mut p, &mut l, CommandBody::Bolus { amount_mu: 1000 }).result, 0);
    assert_eq!(xchg(&mut p, &mut l, CommandBody::CancelBolus).result, 0);
    assert_eq!(xchg(&mut p, &mut l, CommandBody::Suspend).result, 0);
    assert_eq!(xchg(&mut p, &mut l, CommandBody::Acknowledge { fault_mask: 0xFFFF }).result, 0);
}

#[test]
fn proto_errors_are_reported_in_result_tag() {
    let (mut p, h) = rig_running(100_000, 1000);
    let mut l = link_plain();
    let rsp = xchg(&mut p, &mut l, CommandBody::Bolus { amount_mu: 20_000 }); // above 10 U max
    assert_eq!(rsp.result, Error::Limit.code());
    assert_eq!(h.st().total_steps, 0);
}

#[test]
fn proto_unknown_command_gets_unsupported_response() {
    let (mut p, _h) = rig_init();
    let mut l = link_plain();
    let mut frame = [0u8; 32];
    let mut out = [0u8; 64];
    let n = l.s.seal(false, 0x7E, 1, false, &[], &mut frame).unwrap();
    let m = p.handle_frame(&mut l.s, &frame[..n], &mut out).unwrap();
    assert!(m > 0);
    let f = proto::decode_frame(&out[..m]).unwrap();
    assert_eq!(f.type_, 0x7E | RSP_BIT);
    let rsp = proto::decode_response(0x7E, f.seq, f.payload).unwrap();
    assert_eq!(rsp.result, Error::Unsupported.code());
}

#[test]
fn proto_malformed_payload_gets_frame_error_response() {
    let (mut p, _h) = rig_init();
    let mut l = link_plain();
    let mut frame = [0u8; 32];
    let mut out = [0u8; 64];
    // amount missing
    let n = l.s.seal(false, proto::cmd::BOLUS, 1, false, &[], &mut frame).unwrap();
    let m = p.handle_frame(&mut l.s, &frame[..n], &mut out).unwrap();
    assert!(m > 0);
    let f = proto::decode_frame(&out[..m]).unwrap();
    let rsp = proto::decode_response(proto::cmd::BOLUS, f.seq, f.payload).unwrap();
    assert_eq!(rsp.result, Error::Frame.code());
}

#[test]
fn proto_replay_corruption_and_oversized_output_are_dropped() {
    let (mut p, _h) = rig_running(100_000, 0);
    let mut l = link_plain();
    let mut payload = [0u8; 8];
    let mut frame = [0u8; 64];
    let mut out = [0u8; 64];
    let c = Command::new(1, CommandBody::Bolus { amount_mu: 500 });
    let pl = proto::encode_command_payload(&c, &mut payload).unwrap();
    let n = l.s.seal(false, proto::cmd::BOLUS, 1, false, &payload[..pl], &mut frame).unwrap();
    assert!(p.handle_frame(&mut l.s, &frame[..n], &mut out).unwrap() > 0);
    let _ = p.cancel_bolus();
    // the same bytes again: must NOT start a second bolus
    assert_eq!(p.handle_frame(&mut l.s, &frame[..n], &mut out), Err(Error::Replay));
    assert!(!p.engine().bolus_active());
    frame[3] ^= 0x40;
    assert_eq!(p.handle_frame(&mut l.s, &frame[..n], &mut out), Err(Error::Crc));
    // checked before output
    assert_eq!(p.handle_frame(&mut l.s, &frame[..n], &mut out[..4]), Err(Error::Crc));
}

#[test]
fn proto_response_buffer_too_small_reports_error() {
    let (mut p, _h) = rig_init();
    let mut l = link_plain();
    let mut frame = [0u8; 32];
    let mut out = [0u8; 8];
    let n = l.s.seal(false, proto::cmd::GET_STATUS, 1, false, &[], &mut frame).unwrap();
    assert_eq!(p.handle_frame(&mut l.s, &frame[..n], &mut out), Err(Error::TooLarge));
}

#[test]
fn proto_any_valid_command_resets_comm_loss_timer() {
    let (mut p, h) = rig_running(100_000, 1000);
    let mut l = link_plain();
    let rsp = xchg(&mut p, &mut l, CommandBody::SetTempBasal { rate_mu_h: 3000, duration_min: 120 });
    assert_eq!(rsp.result, 0);
    for _ in 0..4 {
        // a status poll every 20 min keeps the temp alive
        run_secs(&mut p, &h, 20 * 60);
        let rsp = xchg(&mut p, &mut l, CommandBody::GetStatus);
        assert!(has_flag(rsp.status.unwrap().flags, st::TEMP_ACTIVE));
    }
    run_secs(&mut p, &h, 31 * 60);
    let s = p.get_status();
    assert!(!has_flag(s.flags, st::TEMP_ACTIVE));
}

#[test]
fn proto_history_paging_with_persistent_ids() {
    let (mut p, _h) = rig_init();
    for i in 0..25 {
        p.log_mut().append(0, EventType::Prime, i, 0);
    }
    let mut l = link_plain();
    let rsp = xchg(&mut p, &mut l, CommandBody::GetHistory { from_id: 0, max_events: 10 });
    let h = rsp.history.expect("history");
    assert_eq!(h.events.len(), 10);
    assert_eq!(h.events[0].id, 1); // BOOT
    assert_eq!(h.next_event_id, 27);
    assert_eq!(h.oldest_event_id, 1);
    let next = h.events[9].id + 1;
    // clamped to 10 per response
    let rsp = xchg(&mut p, &mut l, CommandBody::GetHistory { from_id: next, max_events: 100 });
    let h = rsp.history.expect("history");
    assert_eq!(h.events.len(), 10);
    assert_eq!(h.events[0].id, 11);
}

#[test]
fn proto_encrypted_path_end_to_end() {
    let (mut p, _h) = rig_running(100_000, 1000);
    let mut l = Link { s: Session::new(FakeCcm::default(), true, [5, 6, 7, 8], false), seq: 1 };
    let (m, rsp) = exchange(&mut p, &mut l, &mut body_cmd(CommandBody::GetStatus), true);
    assert!(m > 0);
    assert_eq!(rsp.result, 0);
    assert_eq!(rsp.status.unwrap().reservoir_mu, 100_000);
}

// ---- stepper-rework additions (per-revolution check, current occlusion, strict priming, sensor) ----

#[test]
fn pump_strict_config_refuses_resume_until_prime_completed() {
    let hal = MockHal::new();
    let cal = cal_test();
    let mut p = Pump::new(hal.clone(), Some(&cal), CAPACITY_100, 1);
    p.set_config(PumpConfig::STRICT);
    assert_eq!(p.fill(MilliUnits(50_000)), Ok(()));
    assert!(p.prime_required());
    assert_eq!(activate(&mut p, 1000), Ok(()));
    assert!(has_flag(p.get_status().flags, 1 << 12)); // PRIME_REQUIRED
    assert_eq!(p.resume(), Err(Error::PrimeRequired));
    assert_eq!(p.prime(Pulses(5)), Ok(()));
    assert!(!p.prime_required());
    assert!(!has_flag(p.get_status().flags, 1 << 12));
    assert_eq!(p.resume(), Ok(()));
    assert_eq!(hal.st().total_steps, 5);
}

#[test]
fn pump_strict_config_draw_requires_priming_again() {
    let hal = MockHal::new();
    let cal = cal_test();
    let mut p = Pump::new(hal.clone(), Some(&cal), CAPACITY_100, 1);
    p.set_config(PumpConfig::STRICT);
    assert_eq!(p.fill(MilliUnits(20_000)), Ok(()));
    assert_eq!(activate(&mut p, 0), Ok(()));
    assert_eq!(p.prime(Pulses(3)), Ok(()));
    assert_eq!(p.resume(), Ok(()));
    assert_eq!(p.suspend(), Ok(()));
    hal.st().docked = false;
    assert_eq!(p.fill_draw(MilliUnits(5000)), Ok(()));
    run_draw(&mut p, &hal);
    assert!(p.prime_required());
    hal.st().docked = true;
    run_secs(&mut p, &hal, 1);
    assert_eq!(p.resume(), Err(Error::PrimeRequired));
    assert_eq!(p.prime(Pulses(3)), Ok(()));
    assert_eq!(p.resume(), Ok(()));
}

#[test]
fn pump_motor_current_occlusion_latches_after_three_bursts() {
    let (mut p, h) = rig_running(100_000, 0);
    h.st().current_ma = Some(OCCLUSION_CURRENT_MA + 60); // encoder is fine, motor strains
    assert_eq!(p.bolus(MilliUnits(5000)), Ok(()));
    run_secs(&mut p, &h, 120);
    let s = p.get_status();
    assert!(has_fault(s.faults, Faults::OCCLUSION));
    assert!(has_flag(s.flags, st::ALARM));
    assert!(has_flag(s.flags, st::SUSPENDED));
    assert_eq!(h.st().buzzer, Buzzer::Alarm);
    assert!(!h.st().enabled);
    assert!(log_has(&p, EventType::Fault));
    assert!(h.st().total_steps < steps_of(1000)); // stopped after a few bursts, not at the end
    assert_eq!(p.resume(), Err(Error::Fault));
}

#[test]
fn pump_motor_current_below_threshold_never_alarms() {
    let (mut p, h) = rig_running(100_000, 0);
    h.st().current_ma = Some(OCCLUSION_CURRENT_MA); // at, not above, the threshold
    assert_eq!(p.bolus(MilliUnits(2000)), Ok(()));
    run_secs(&mut p, &h, 100);
    assert_eq!(p.get_status().faults, 0);
}

#[test]
fn pump_per_revolution_check_trips_alone_at_95_percent() {
    // 95 % delivered: 5 % per revolution (> 3 %), but only 5 % per >= 1 U window (< 10 %) and
    // far from 2 U undelivered per window, so ONLY the per-revolution check can fire. The first
    // revolution (256 steps = 6.7 U) completes inside a 10 U bolus.
    let (mut p, h) = rig_running(100_000, 0);
    h.st().delivered_pct = 95;
    assert_eq!(p.bolus(MilliUnits(10_000)), Ok(()));
    run_secs(&mut p, &h, 600);
    let s = p.get_status();
    assert!(has_fault(s.faults, Faults::ENCODER_DEVIATION));
    assert!(!has_fault(s.faults, Faults::OCCLUSION));
    assert!(has_flag(s.flags, st::SUSPENDED));
    assert!(has_flag(s.flags, st::ALARM));
    assert!(h.st().total_steps >= 256);
    assert!(h.st().total_steps < steps_of(10_000));
}

#[test]
fn pump_per_revolution_check_accepts_99_percent() {
    let (mut p, h) = rig_running(100_000, 0);
    h.st().delivered_pct = 99; // 1 % off per revolution, within 3 %
    assert_eq!(p.bolus(MilliUnits(10_000)), Ok(()));
    run_secs(&mut p, &h, 600);
    assert_eq!(p.get_status().faults, 0);
    assert!(h.st().total_steps > 256);
}

#[test]
fn pump_missing_angle_sensor_latches_internal_and_delivers_nothing() {
    let (mut p, h) = rig_running(100_000, 5000);
    run_secs(&mut p, &h, 60);
    let before = h.st().total_steps;
    h.st().angle_missing = true;
    run_secs(&mut p, &h, 120);
    let s = p.get_status();
    assert!(has_fault(s.faults, Faults::INTERNAL));
    assert!(has_flag(s.flags, st::SUSPENDED));
    let frozen = h.st().total_steps;
    run_secs(&mut p, &h, 600);
    assert_eq!(h.st().total_steps, frozen);
    assert!(frozen >= before);
}
