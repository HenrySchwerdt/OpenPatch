//! Persistence: one `sequential-storage` map in the STORAGE partition (32 KB at the end of flash).
//!
//! Why `sequential-storage` (map) and not `ekv`: it is no-alloc, tiny, wear levels by appending, is
//! used by the trouble-host bonding example, works with any `embedded-storage-async` NorFlash (here:
//! the MPSL timeslot flash, see below) and the data set is a handful of small keyed records. `ekv`
//! (LSM tree, transactions) is the better choice for large or many records; not needed here.
//!
//! Flash writes go through `nrf_sdc::mpsl::Flash` (embedded-storage-async on top of the MPSL
//! timeslot API): erases/writes are scheduled around radio events so BLE connections survive. The
//! CPU still stalls for the NVMC (about 85 ms per page erase, about 41 us per word), which is why
//! ONLY the persistence task writes flash, never the safety task, and why step timing is in hardware.
//!
//! Records (key: u8, value: little endian bytes, first byte = record version 1):
//!  1 SEQ   u16 command seq ceiling (see `config::SEQ_CEILING_STEP`)
//!  2 EVT   u32 event id ceiling
//!  3 RES   u32 fill mU, u32 consumed steps (stored with a margin, always >= reality)
//!  4 CAL   24 byte DriveCal image (magic + CRC), never silently overwritten
//!  5 POD   u32 pair id, u8 role, u8 active, u32 activation id, u32 wear s (upper bound)
//!  6 PS    32 byte application layer pairing secret (protocol v1.1 section 5.2)
//!  7 SCHED basal schedule: u8 count, count x (u8 slot, u16 rate mU/h) (`openpatch_core::persist::SchedRec`; 1 byte = none)
//!  8 TEMP  active temp basal: u16 rate mU/h, u16 remaining minutes rounded down to 30 (`TempRec`; 0 minutes = none)
//!  16/17   BLE bond slots
use embassy_embedded_hal::flash::partition::Partition;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use nrf_sdc::mpsl::Flash;
use openpatch_core::drive_cal::DriveCal;
use openpatch_core::persist::{SchedRec, TempRec};
use sequential_storage::cache::{Cache, Uncached};
use sequential_storage::map::{MapConfig, MapStorage};
use trouble_host::prelude::{AddrKind, Address, BdAddr, BondInformation, Identity, IdentityResolvingKey, LongTermKey, SecurityLevel};

use crate::config::*;
use crate::layout;
use crate::shared::{PERSIST, SEQ_ACK};

pub type FlashMutex = Mutex<CriticalSectionRawMutex, Flash<'static>>;
type NoCacheT = Cache<Uncached, Uncached, Uncached, u8>;
pub type Part = Partition<'static, CriticalSectionRawMutex, Flash<'static>>;

const KEY_SEQ: u8 = 1;
const KEY_EVT: u8 = 2;
const KEY_RES: u8 = 3;
const KEY_CAL: u8 = 4;
const KEY_POD: u8 = 5;
const KEY_PS: u8 = 6;
const KEY_SCHED: u8 = 7;
const KEY_TEMP: u8 = 8;
const KEY_BOND0: u8 = 16;
const REC_VERSION: u8 = 1;
/// Longest record + item header, rounded up to the flash word size.
const BUF_LEN: usize = 128;

#[derive(Clone, Copy, Debug, PartialEq, Eq, defmt::Format)]
pub struct PodRec {
    pub pair_id: u32,
    pub role: u8,
    pub active: bool,
    pub activation_id: u32,
    pub wear_s: u32,
}

/// A BLE bond in a fixed byte image (no serde, no alloc).
#[derive(Clone, Copy, PartialEq, Eq)]
pub struct BondRec(pub [u8; 43]);

impl BondRec {
    pub fn from_bond(b: &BondInformation) -> BondRec {
        let mut r = [0u8; 43];
        r[0] = REC_VERSION;
        r[1..17].copy_from_slice(&b.ltk.0.to_le_bytes());
        r[17] = b.identity.addr.kind.into_inner();
        r[18..24].copy_from_slice(&b.identity.addr.addr.into_inner());
        match b.identity.irk {
            Some(irk) => {
                r[24] = 1;
                r[25..41].copy_from_slice(&irk.0.get().to_le_bytes());
            }
            None => r[24] = 0,
        }
        r[41] = match b.security_level {
            SecurityLevel::NoEncryption => 0,
            SecurityLevel::Encrypted => 1,
            SecurityLevel::EncryptedAuthenticated => 2,
        };
        r[42] = b.is_bonded as u8;
        BondRec(r)
    }

    pub fn to_bond(&self) -> Option<BondInformation> {
        let r = &self.0;
        if r[0] != REC_VERSION {
            return None;
        }
        let mut ltk = [0u8; 16];
        ltk.copy_from_slice(&r[1..17]);
        let mut addr = [0u8; 6];
        addr.copy_from_slice(&r[18..24]);
        let irk = if r[24] == 1 {
            let mut k = [0u8; 16];
            k.copy_from_slice(&r[25..41]);
            IdentityResolvingKey::new(u128::from_le_bytes(k))
        } else {
            None
        };
        let security_level = match r[41] {
            1 => SecurityLevel::Encrypted,
            2 => SecurityLevel::EncryptedAuthenticated,
            _ => SecurityLevel::NoEncryption,
        };
        Some(BondInformation {
            ltk: LongTermKey::new(u128::from_le_bytes(ltk)),
            identity: Identity { addr: Address::new(AddrKind::new(r[17]), BdAddr::new(addr)), irk },
            is_bonded: r[42] != 0,
            security_level,
        })
    }
}

/// Messages to the persistence task.
#[derive(Clone, Copy)]
pub enum PersistMsg {
    SeqCeiling(u16),
    EvtCeiling(u32),
    Reservoir { fill_mu: u32, consumed_steps: u32 },
    Pod(PodRec),
    Bond(BondRec),
    /// Basal schedule (F2): rewritten only when it changes.
    Schedule(SchedRec),
    /// Active temp basal (F2): rewritten only when it changes.
    Temp(TempRec),
    /// Application layer pairing secret. Must not be lost: producers `send().await`.
    PairingSecret([u8; 32]),
}

#[derive(Clone, Copy, defmt::Format)]
pub enum CalState {
    /// Nothing stored (first boot): the build's record was written.
    FirstBoot(DriveCal),
    /// Stored record equals the build's preset.
    Match(DriveCal),
    /// Stored record differs from this build or is corrupt: NO delivery. `None` is passed to
    /// `Pump::new` (the core latches NO_CALIBRATION, unacknowledgeable); passing a stored record
    /// of ANOTHER valid preset would validate and deliver with the wrong volume per step.
    Mismatch,
}

impl CalState {
    pub fn cal(&self) -> Option<DriveCal> {
        match self {
            CalState::FirstBoot(c) | CalState::Match(c) => Some(*c),
            CalState::Mismatch => None,
        }
    }
}

pub struct BootData {
    pub seq_ceiling: Option<u16>,
    pub evt_ceiling: u32,
    pub reservoir: Option<(u32, u32)>,
    pub cal: CalState,
    pub pod: Option<PodRec>,
    pub sched: Option<SchedRec>,
    pub temp: Option<TempRec>,
    pub pairing_secret: Option<[u8; 32]>,
    pub bonds: [Option<BondRec>; MAX_BONDS],
}

pub struct Settings {
    map: MapStorage<u8, Part, NoCacheT>,
    buf: [u8; BUF_LEN],
}

fn le16(b: &[u8]) -> u16 {
    u16::from_le_bytes([b[0], b[1]])
}
fn le32(b: &[u8]) -> u32 {
    u32::from_le_bytes([b[0], b[1], b[2], b[3]])
}

impl Settings {
    pub fn new(flash: &'static FlashMutex) -> Self {
        let part = Partition::new(flash, layout::STORAGE_START, layout::STORAGE_SIZE);
        Self { map: MapStorage::new(part, MapConfig::new(0..layout::STORAGE_SIZE), Cache::new_uncached()), buf: [0; BUF_LEN] }
    }

    async fn get(&mut self, key: u8) -> Option<([u8; 80], usize)> {
        match self.map.fetch_item::<&[u8]>(&mut self.buf, &key).await {
            Ok(Some(v)) if !v.is_empty() && v[0] == REC_VERSION && v.len() <= 80 => {
                let mut o = [0u8; 80];
                o[..v.len()].copy_from_slice(v);
                Some((o, v.len()))
            }
            Ok(_) => None,
            Err(_) => {
                defmt::error!("settings: read of key {} failed", key);
                None
            }
        }
    }

    async fn put(&mut self, key: u8, bytes: &[u8]) -> bool {
        match self.map.store_item(&mut self.buf, &key, &bytes).await {
            Ok(()) => true,
            Err(_) => {
                defmt::error!("settings: write of key {} failed", key);
                false
            }
        }
    }

    /// Read everything at boot and run the drive calibration check (writes the build's record on
    /// the very first boot).
    pub async fn load(&mut self) -> BootData {
        let build = build_drive_cal();
        let seq_ceiling = self.get(KEY_SEQ).await.filter(|(_, n)| *n == 3).map(|(b, _)| le16(&b[1..3]));
        let evt_ceiling = self.get(KEY_EVT).await.filter(|(_, n)| *n == 5).map(|(b, _)| le32(&b[1..5])).unwrap_or(0);
        let reservoir = self.get(KEY_RES).await.filter(|(_, n)| *n == 9).map(|(b, _)| (le32(&b[1..5]), le32(&b[5..9])));
        let pod = self.get(KEY_POD).await.filter(|(_, n)| *n == 15).map(|(b, _)| PodRec {
            pair_id: le32(&b[1..5]),
            role: b[5],
            active: b[6] != 0,
            activation_id: le32(&b[7..11]),
            wear_s: le32(&b[11..15]),
        });
        let sched = self.get(KEY_SCHED).await.and_then(|(b, n)| SchedRec::from_slice(&b[1..n]));
        let temp = self.get(KEY_TEMP).await.filter(|(_, n)| *n == 5).and_then(|(b, _)| TempRec::from_bytes(&b[1..5]));
        let pairing_secret = self.get(KEY_PS).await.filter(|(_, n)| *n == 33).map(|(b, _)| {
            let mut ps = [0u8; 32];
            ps.copy_from_slice(&b[1..33]);
            ps
        });
        let cal = match self.get(KEY_CAL).await {
            None => {
                let img = build.to_bytes();
                let mut rec = [0u8; 25];
                rec[0] = REC_VERSION;
                rec[1..].copy_from_slice(&img);
                if self.put(KEY_CAL, &rec).await {
                    CalState::FirstBoot(build)
                } else {
                    CalState::Mismatch
                }
            }
            Some((b, 25)) => {
                let mut img = [0u8; 24];
                img.copy_from_slice(&b[1..25]);
                let stored = DriveCal::from_bytes(&img);
                if DriveCal::validate(Some(&stored)).is_ok() && stored == build {
                    CalState::Match(stored)
                } else {
                    defmt::error!(
                        "drive calibration in flash (id {:#x}, {}/{} uU/step) does not match this build (id {:#x}, {}/{} uU/step): NO delivery, the record is NOT overwritten",
                        stored.drive_id,
                        stored.uu_num,
                        stored.uu_den,
                        build.drive_id,
                        build.uu_num,
                        build.uu_den
                    );
                    CalState::Mismatch
                }
            }
            Some(_) => CalState::Mismatch,
        };
        let mut bonds = [None; MAX_BONDS];
        for (i, slot) in bonds.iter_mut().enumerate() {
            if let Some((b, 43)) = self.get(KEY_BOND0 + i as u8).await {
                let mut r = [0u8; 43];
                r.copy_from_slice(&b[..43]);
                *slot = Some(BondRec(r));
            }
        }
        BootData { seq_ceiling, evt_ceiling, reservoir, cal, pod, sched, temp, pairing_secret, bonds }
    }

    async fn write_bond(&mut self, rec: BondRec) {
        // Replace a slot of the same peer, else the first free slot, else slot 0.
        let same_peer = |a: &BondRec, b: &BondRec| a.0[17..24] == b.0[17..24];
        let mut target = None;
        let mut free = None;
        for i in 0..MAX_BONDS {
            match self.get(KEY_BOND0 + i as u8).await {
                Some((b, 43)) => {
                    let mut r = [0u8; 43];
                    r.copy_from_slice(&b[..43]);
                    if same_peer(&BondRec(r), &rec) {
                        target = Some(i);
                    }
                }
                _ => free = free.or(Some(i)),
            }
        }
        let slot = target.or(free).unwrap_or(0);
        self.put(KEY_BOND0 + slot as u8, &rec.0).await;
    }

    pub async fn write(&mut self, m: PersistMsg) {
        match m {
            PersistMsg::SeqCeiling(c) => {
                let mut r = [REC_VERSION, 0, 0];
                r[1..3].copy_from_slice(&c.to_le_bytes());
                if self.put(KEY_SEQ, &r).await {
                    SEQ_ACK.signal(c);
                }
            }
            PersistMsg::EvtCeiling(c) => {
                let mut r = [REC_VERSION, 0, 0, 0, 0];
                r[1..5].copy_from_slice(&c.to_le_bytes());
                self.put(KEY_EVT, &r).await;
            }
            PersistMsg::Reservoir { fill_mu, consumed_steps } => {
                let mut r = [REC_VERSION, 0, 0, 0, 0, 0, 0, 0, 0];
                r[1..5].copy_from_slice(&fill_mu.to_le_bytes());
                r[5..9].copy_from_slice(&consumed_steps.to_le_bytes());
                self.put(KEY_RES, &r).await;
            }
            PersistMsg::Pod(p) => {
                let mut r = [0u8; 15];
                r[0] = REC_VERSION;
                r[1..5].copy_from_slice(&p.pair_id.to_le_bytes());
                r[5] = p.role;
                r[6] = p.active as u8;
                r[7..11].copy_from_slice(&p.activation_id.to_le_bytes());
                r[11..15].copy_from_slice(&p.wear_s.to_le_bytes());
                self.put(KEY_POD, &r).await;
            }
            PersistMsg::Bond(b) => self.write_bond(b).await,
            PersistMsg::Schedule(s) => {
                let mut r = [0u8; 80];
                r[0] = REC_VERSION;
                let b = s.as_bytes();
                r[1..1 + b.len()].copy_from_slice(b);
                self.put(KEY_SCHED, &r[..1 + b.len()]).await;
            }
            PersistMsg::Temp(t) => {
                let mut r = [REC_VERSION, 0, 0, 0, 0];
                r[1..5].copy_from_slice(&t.to_bytes());
                self.put(KEY_TEMP, &r).await;
            }
            PersistMsg::PairingSecret(ps) => {
                let mut r = [0u8; 33];
                r[0] = REC_VERSION;
                r[1..].copy_from_slice(&ps);
                self.put(KEY_PS, &r).await;
            }
        }
    }
}

/// Latest-wins merge of everything queued, so a burst of reservoir updates is one flash write.
#[derive(Default)]
struct Pending {
    seq: Option<u16>,
    evt: Option<u32>,
    res: Option<(u32, u32)>,
    pod: Option<PodRec>,
    sched: Option<SchedRec>,
    temp: Option<TempRec>,
    ps: Option<[u8; 32]>,
    bonds: heapless_bonds::Bonds,
}

mod heapless_bonds {
    use super::BondRec;
    use crate::config::MAX_BONDS;
    #[derive(Default)]
    pub struct Bonds {
        pub items: [Option<BondRec>; MAX_BONDS + 2],
    }
    impl Bonds {
        pub fn push(&mut self, b: BondRec) {
            if let Some(s) = self.items.iter_mut().find(|s| s.is_none()) {
                *s = Some(b);
            }
        }
    }
}

impl Pending {
    fn merge(&mut self, m: PersistMsg) {
        match m {
            PersistMsg::SeqCeiling(c) => self.seq = Some(self.seq.map_or(c, |o| o.max(c))),
            PersistMsg::EvtCeiling(c) => self.evt = Some(self.evt.map_or(c, |o| o.max(c))),
            PersistMsg::Reservoir { fill_mu, consumed_steps } => self.res = Some((fill_mu, consumed_steps)),
            PersistMsg::Pod(p) => self.pod = Some(p),
            PersistMsg::Schedule(s) => self.sched = Some(s),
            PersistMsg::Temp(t) => self.temp = Some(t),
            PersistMsg::Bond(b) => self.bonds.push(b),
            PersistMsg::PairingSecret(ps) => self.ps = Some(ps),
        }
    }
}

/// The only task that writes the settings. The seq ceiling is written first (the safety task waits
/// for it).
#[embassy_executor::task]
pub async fn persist_task(mut settings: Settings) -> ! {
    loop {
        let first = PERSIST.receive().await;
        let mut p = Pending::default();
        p.merge(first);
        while let Ok(m) = PERSIST.try_receive() {
            p.merge(m);
        }
        if let Some(c) = p.seq {
            settings.write(PersistMsg::SeqCeiling(c)).await;
        }
        if let Some(c) = p.evt {
            settings.write(PersistMsg::EvtCeiling(c)).await;
        }
        if let Some((fill_mu, consumed_steps)) = p.res {
            settings.write(PersistMsg::Reservoir { fill_mu, consumed_steps }).await;
        }
        if let Some(pod) = p.pod {
            settings.write(PersistMsg::Pod(pod)).await;
        }
        if let Some(s) = p.sched {
            settings.write(PersistMsg::Schedule(s)).await;
        }
        if let Some(t) = p.temp {
            settings.write(PersistMsg::Temp(t)).await;
        }
        if let Some(ps) = p.ps {
            settings.write(PersistMsg::PairingSecret(ps)).await;
        }
        for b in p.bonds.items.into_iter().flatten() {
            settings.write(PersistMsg::Bond(b)).await;
        }
    }
}
