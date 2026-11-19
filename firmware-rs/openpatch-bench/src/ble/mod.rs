//! BLE: nrf-sdc (SoftDevice Controller) + trouble-host (peripheral, GATT, LE Secure Connections).
//!
//! The BLE task never touches the pump or any motor pin: frames go through `FRAME_IN` /
//! `FRAME_OUT`, bench control and the CSV log through `BENCH_CMD` / `CSV_OUT`.
//!
//! * OpenPatch service (UUIDs from `openpatch_proto::consts`): Command (write / write without
//!   response, one frame per write), Response (notify, one frame per notification), Alert (notify,
//!   reserved, never used).
//! * Bench service (`...1490010`): Control (write) and Log (notify), documented in
//!   docs/bench-testing.md.
//! * All characteristics require an encrypted link. Pairing is Just Works LE Secure Connections with
//!   bonding and is only possible inside the pairing window (button). Outside the window unbonded
//!   peers are disconnected (policy task).
use core::sync::atomic::Ordering;
use embassy_futures::select::{select, select3, Either3};
use embassy_time::{Duration, Timer};
use nrf_sdc::SoftdeviceController;
use trouble_host::prelude::*;

use crate::config::*;
use crate::pairing;
use crate::shared::*;
use crate::storage::{BondRec, PersistMsg};

const CONNECTIONS_MAX: usize = 1;
/// Signalling, ATT, SMP.
const L2CAP_CHANNELS_MAX: usize = 3;

/// Bench service UUIDs, same base as the OpenPatch service (`...1490010` / `11` / `12`).
pub const UUID_BENCH_SERVICE: u128 = 0x2E092A48_506C_477E_ADD4_448BF1490010;
pub const UUID_BENCH_CONTROL: u128 = 0x2E092A48_506C_477E_ADD4_448BF1490011;
pub const UUID_BENCH_LOG: u128 = 0x2E092A48_506C_477E_ADD4_448BF1490012;

pub const BENCH_OP_START: u8 = 1;
pub const BENCH_OP_ABORT: u8 = 2;
/// op u8 | pulses u16 | amount_mu u32 | pause_ms u32, little endian.
pub const BENCH_CONTROL_LEN: usize = 11;

#[gatt_server]
struct Server {
    openpatch: OpenPatchService,
    bench: BenchService,
}

#[gatt_service(uuid = openpatch_proto::UUID_SERVICE)]
struct OpenPatchService {
    #[characteristic(uuid = openpatch_proto::UUID_COMMAND, write, write_without_response, value = [0u8; FRAME_BUF], permissions(encrypted))]
    command: [u8; FRAME_BUF],
    #[characteristic(uuid = openpatch_proto::UUID_RESPONSE, notify, value = [0u8; FRAME_BUF], permissions(encrypted))]
    response: [u8; FRAME_BUF],
    /// Unsolicited notifications (frame type 0x90): draw progress / done / stalled, fault.
    #[characteristic(uuid = openpatch_proto::UUID_ALERT, notify, value = [0u8; FRAME_BUF], permissions(encrypted))]
    alert: [u8; FRAME_BUF],
}

#[gatt_service(uuid = UUID_BENCH_SERVICE)]
struct BenchService {
    #[characteristic(uuid = UUID_BENCH_CONTROL, write, write_without_response, value = [0u8; BENCH_CONTROL_LEN], permissions(encrypted))]
    control: [u8; BENCH_CONTROL_LEN],
    #[characteristic(uuid = UUID_BENCH_LOG, notify, value = [0u8; CSV_LINE_MAX], permissions(encrypted))]
    log: [u8; CSV_LINE_MAX],
}

/// Static random address from FICR DEVICEADDR; name `OpenPatch-XXXX` = last 4 hex digits.
pub fn device_address() -> (Address, [u8; 14]) {
    let ficr = embassy_nrf::pac::FICR;
    let lo = ficr.deviceaddr(0).read();
    let hi = ficr.deviceaddr(1).read();
    let mut a = [0u8; 6];
    a[..4].copy_from_slice(&lo.to_le_bytes());
    a[4..6].copy_from_slice(&(hi as u16).to_le_bytes());
    a[5] |= 0xC0; // static random address: two most significant bits set
    const HEX: &[u8; 16] = b"0123456789ABCDEF";
    let mut name = *b"OpenPatch-0000";
    // printed MSB first: ..:a[1]:a[0]
    name[10] = HEX[(a[1] >> 4) as usize];
    name[11] = HEX[(a[1] & 0xF) as usize];
    name[12] = HEX[(a[0] >> 4) as usize];
    name[13] = HEX[(a[0] & 0xF) as usize];
    (Address::random(a), name)
}

#[embassy_executor::task]
pub async fn ble_task(sdc: SoftdeviceController<'static>, bonds: [Option<BondRec>; MAX_BONDS], address: Address, name: &'static str) -> ! {
    run(sdc, bonds, address, name).await
}

async fn run<C: Controller>(controller: C, bonds: [Option<BondRec>; MAX_BONDS], address: Address, name: &'static str) -> ! {
    let mut resources: HostResources<DefaultPacketPool, CONNECTIONS_MAX, L2CAP_CHANNELS_MAX> = HostResources::new();
    let stack = trouble_host::new(controller, &mut resources)
        .set_random_address(address)
        .set_io_capabilities(IoCapabilities::NoInputNoOutput) // Just Works: the button press is the authorisation
        // trouble-host feature `security` without `legacy-pairing` = LE Secure Connections only
        .build();

    for b in bonds.into_iter().flatten() {
        match b.to_bond() {
            Some(bond) => {
                if stack.add_bond_information(bond).is_err() {
                    defmt::warn!("bond table full / bond rejected");
                }
            }
            None => defmt::warn!("stored bond record unreadable"),
        }
    }

    let mut runner = stack.runner();
    let mut peripheral = stack.peripheral();
    let server = match Server::new_with_config(GapConfig::Peripheral(PeripheralConfig { name, appearance: &appearance::UNKNOWN })) {
        Ok(s) => s,
        Err(_) => defmt::panic!("GATT server table"),
    };
    defmt::info!("BLE: {} at {}", name, address);

    let host = async {
        loop {
            if let Err(e) = runner.run().await {
                defmt::error!("BLE host error: {}", defmt::Debug2Format(&e));
                Timer::after_secs(1).await;
            }
        }
    };

    let app = async {
        loop {
            match advertise(name, &mut peripheral, &server).await {
                Ok(conn) => {
                    BLE_CONNECTED.store(true, Ordering::Relaxed);
                    FRAME_OUT.clear();
                    ALERT_OUT.clear();
                    CSV_OUT.clear();
                    apply_pairing_policy(&conn);
                    let a = gatt_events(&server, &conn);
                    let b = notify_loop(&server, &conn);
                    let c = policy_loop(&conn);
                    select3(a, b, c).await;
                    BLE_CONNECTED.store(false, Ordering::Relaxed);
                    defmt::info!("BLE: disconnected");
                }
                Err(e) => {
                    defmt::warn!("BLE advertise error: {}", defmt::Debug2Format(&e));
                    Timer::after_secs(1).await;
                }
            }
        }
    };

    select(host, app).await;
    unreachable!()
}

/// Bonding only inside the window; unbonded peers outside the window are dropped.
fn apply_pairing_policy<P: PacketPool>(conn: &GattConnection<'_, '_, P>) {
    let open = pairing::is_open();
    let _ = conn.raw().set_bondable(open);
    if !open && !conn.raw().is_bonded_peer() {
        defmt::warn!("BLE: unbonded peer outside the pairing window: disconnect");
        conn.raw().disconnect();
    }
}

async fn policy_loop<P: PacketPool>(conn: &GattConnection<'_, '_, P>) {
    loop {
        Timer::after(Duration::from_millis(250)).await;
        if !conn.raw().is_connected() {
            return;
        }
        apply_pairing_policy(conn);
    }
}

async fn gatt_events<P: PacketPool>(server: &Server<'_>, conn: &GattConnection<'_, '_, P>) {
    let cmd_handle = server.openpatch.command.handle;
    let bench_ctl_handle = server.bench.control.handle;
    loop {
        match conn.next().await {
            GattConnectionEvent::Disconnected { reason } => {
                defmt::info!("BLE: link closed: {}", reason);
                return;
            }
            GattConnectionEvent::PairingComplete { security_level, bond } => {
                defmt::info!("BLE: pairing complete, level {}", defmt::Debug2Format(&security_level));
                if let Some(b) = bond {
                    let _ = PERSIST.try_send(PersistMsg::Bond(BondRec::from_bond(&b)));
                    pairing::close(); // one pairing per button press
                    defmt::info!("BLE: bond stored, pairing window closed");
                }
            }
            GattConnectionEvent::PairingFailed(e) => defmt::warn!("BLE: pairing failed: {}", defmt::Debug2Format(&e)),
            GattConnectionEvent::Gatt { event } => {
                let encrypted = conn.raw().security_level().map(|l| l.encrypted()).unwrap_or(false);
                let mut reject = None;
                if let GattEvent::Write(w) = &event {
                    let h = w.handle();
                    if h == cmd_handle || h == bench_ctl_handle {
                        if !encrypted {
                            reject = Some(AttErrorCode::INSUFFICIENT_ENCRYPTION);
                        } else if h == cmd_handle {
                            w.with_data(|_, d| match Frame::from_slice(d) {
                                Some(f) => {
                                    if FRAME_IN.try_send(f).is_err() {
                                        defmt::warn!("BLE: frame dropped, safety queue full");
                                    }
                                }
                                None => defmt::warn!("BLE: oversized write ({} bytes) dropped", d.len()),
                            });
                        } else {
                            w.with_data(|_, d| handle_bench_control(d));
                        }
                    }
                }
                let reply = match reject {
                    Some(code) => event.reject(code),
                    None => event.accept(),
                };
                match reply {
                    Ok(r) => r.send().await,
                    Err(e) => defmt::warn!("BLE: reply error {}", defmt::Debug2Format(&e)),
                }
            }
            _ => {}
        }
    }
}

fn handle_bench_control(d: &[u8]) {
    match d.first().copied() {
        Some(BENCH_OP_START) if d.len() >= BENCH_CONTROL_LEN => {
            let pulses = u16::from_le_bytes([d[1], d[2]]);
            let amount_mu = u32::from_le_bytes([d[3], d[4], d[5], d[6]]);
            let pause_ms = u32::from_le_bytes([d[7], d[8], d[9], d[10]]);
            if BENCH_CMD.try_send(BenchCmd::Start { pulses, amount_mu, pause_ms }).is_err() {
                defmt::warn!("bench command queue full");
            }
        }
        Some(BENCH_OP_ABORT) => {
            let _ = BENCH_CMD.try_send(BenchCmd::Abort);
        }
        _ => defmt::warn!("bench control: malformed write ({} bytes)", d.len()),
    }
}

async fn notify_loop<P: PacketPool>(server: &Server<'_>, conn: &GattConnection<'_, '_, P>) {
    loop {
        match select3(FRAME_OUT.receive(), CSV_OUT.receive(), ALERT_OUT.receive()).await {
            Either3::First(f) => {
                if server.openpatch.response.notify_raw(conn, f.bytes(), false).await.is_err() {
                    return;
                }
            }
            Either3::Third(a) => {
                if server.openpatch.alert.notify_raw(conn, a.bytes(), false).await.is_err() {
                    return;
                }
            }
            Either3::Second(l) => {
                if server.bench.log.notify_raw(conn, l.bytes(), false).await.is_err() {
                    return;
                }
            }
        }
    }
}

async fn advertise<'values, 'server, C: Controller>(
    name: &'values str,
    peripheral: &mut Peripheral<'values, C, DefaultPacketPool>,
    server: &'server Server<'values>,
) -> Result<GattConnection<'values, 'server, DefaultPacketPool>, BleHostError<C::Error>> {
    // A 128 bit service UUID (18 bytes) plus flags (3) leaves no room for the 14 character name in
    // the 31 byte advertising packet: the name goes into the scan response.
    let service_uuid = openpatch_proto::UUID_SERVICE.to_le_bytes();
    let mut adv = [0u8; 31];
    let adv_len = AdStructure::encode_slice(
        &[
            AdStructure::Flags(LE_GENERAL_DISCOVERABLE | BR_EDR_NOT_SUPPORTED),
            AdStructure::CompleteServiceUuids128(&[service_uuid]),
        ],
        &mut adv[..],
    )?;
    let mut scan = [0u8; 31];
    let scan_len = AdStructure::encode_slice(&[AdStructure::CompleteLocalName(name.as_bytes())], &mut scan[..])?;
    let params = AdvertisementParameters {
        interval_min: Duration::from_millis(ADV_INTERVAL_MS),
        interval_max: Duration::from_millis(ADV_INTERVAL_MS),
        ..Default::default()
    };
    let advertiser = peripheral
        .advertise(
            &params,
            Advertisement::ConnectableScannableUndirected { adv_data: &adv[..adv_len], scan_data: &scan[..scan_len] },
        )
        .await?;
    defmt::info!("BLE: advertising");
    let conn = advertiser.accept().await?.with_attribute_server(server)?;
    defmt::info!("BLE: connected");
    Ok(conn)
}
