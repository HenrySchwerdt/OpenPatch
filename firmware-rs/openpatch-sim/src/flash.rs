//! Flash model with write latency and power-loss injection.
//!
//! The firmware stores a few small keyed records through one writer (`persistence task`, latest
//! write per key wins, `sequential-storage` map). A write occupies the flash for `write_ms`
//! (page erase ~85 ms). A power cut during a write leaves a torn record: the map falls back to the
//! previous valid copy (A/B atomic, default) or, in the pessimistic setting
//! `tear_destroys_previous_prob`, loses the key entirely.

use crate::rng::Rng;
use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PodRec {
    pub pair_id: u32,
    pub role: u8,
    pub active: bool,
    pub activation_id: u32,
    pub wear_s: u32,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Stored {
    Pod(PodRec),
    /// fill_mu, consumed steps (with the safety margin already added by the policy).
    Reservoir(u32, u32),
    EvtCeiling(u32),
    SeqCeiling(u16),
    /// Basal schedule record (`openpatch_core::persist::SchedRec`, F2).
    Sched(openpatch_core::persist::SchedRec),
    /// Active temp basal (`openpatch_core::persist::TempRec`).
    Temp(openpatch_core::persist::TempRec),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Key {
    Pod,
    Reservoir,
    EvtCeiling,
    SeqCeiling,
    Sched,
    Temp,
}

impl Stored {
    pub fn key(&self) -> Key {
        match self {
            Stored::Pod(_) => Key::Pod,
            Stored::Reservoir(..) => Key::Reservoir,
            Stored::EvtCeiling(_) => Key::EvtCeiling,
            Stored::SeqCeiling(_) => Key::SeqCeiling,
            Stored::Sched(_) => Key::Sched,
            Stored::Temp(_) => Key::Temp,
        }
    }
}

#[derive(Clone, Debug, Default)]
pub struct Flash {
    committed: BTreeMap<Key, Stored>,
    queue: BTreeMap<Key, Stored>,
    /// (value, finishes at us)
    in_flight: Option<(Stored, u64)>,
    pub writes_completed: u64,
    pub writes_torn: u64,
    pub records_destroyed: u64,
    write_us: u64,
    tear_destroys: f64,
}

impl Flash {
    pub fn new(write_ms: f64, tear_destroys_previous_prob: f64) -> Self {
        Flash { write_us: (write_ms * 1000.0) as u64, tear_destroys: tear_destroys_previous_prob, ..Default::default() }
    }

    /// Queue a record (non-blocking, latest per key wins), like `PERSIST.try_send`.
    pub fn queue(&mut self, v: Stored) {
        self.queue.insert(v.key(), v);
    }

    pub fn read(&self, k: Key) -> Option<Stored> {
        self.committed.get(&k).copied()
    }

    pub fn busy(&self) -> bool {
        self.in_flight.is_some()
    }

    /// Time at which the current write started, for power-cut scheduling, if any.
    pub fn in_flight_window(&self) -> Option<(u64, u64)> {
        self.in_flight.map(|(_, end)| (end - self.write_us, end))
    }

    /// Advance to `now_us`: finish and start writes. Returns the start time of a newly started write.
    pub fn advance(&mut self, now_us: u64) -> Option<u64> {
        let mut started = None;
        loop {
            if let Some((v, end)) = self.in_flight {
                if end <= now_us {
                    self.committed.insert(v.key(), v);
                    self.writes_completed += 1;
                    self.in_flight = None;
                    // next write begins when this one ended
                    if let Some((&k, &nv)) = self.queue.iter().next() {
                        self.queue.remove(&k);
                        self.in_flight = Some((nv, end + self.write_us));
                        started = Some(end);
                        continue;
                    }
                }
                break;
            } else if let Some((&k, &nv)) = self.queue.iter().next() {
                self.queue.remove(&k);
                self.in_flight = Some((nv, now_us + self.write_us));
                started = Some(now_us);
                continue;
            } else {
                break;
            }
        }
        started
    }

    /// Power cut: the in-flight write is torn, the queue (RAM) is lost.
    pub fn power_cut(&mut self, rng: &mut Rng) {
        if let Some((v, _)) = self.in_flight.take() {
            self.writes_torn += 1;
            if self.tear_destroys > 0.0 && rng.uniform() < self.tear_destroys {
                self.committed.remove(&v.key());
                self.records_destroyed += 1;
            }
        }
        self.queue.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn write_takes_time_and_commits() {
        let mut f = Flash::new(90.0, 0.0);
        f.queue(Stored::EvtCeiling(64));
        f.advance(1_000_000);
        assert!(f.busy());
        assert_eq!(f.read(Key::EvtCeiling), None);
        f.advance(1_000_000 + 90_000);
        assert_eq!(f.read(Key::EvtCeiling), Some(Stored::EvtCeiling(64)));
    }

    #[test]
    fn torn_write_keeps_previous_copy() {
        let mut f = Flash::new(90.0, 0.0);
        let mut rng = Rng::new(1);
        f.queue(Stored::EvtCeiling(64));
        f.advance(0);
        f.advance(100_000);
        f.queue(Stored::EvtCeiling(128));
        f.advance(200_000);
        f.power_cut(&mut rng);
        assert_eq!(f.read(Key::EvtCeiling), Some(Stored::EvtCeiling(64)));
        assert_eq!(f.writes_torn, 1);
    }

    #[test]
    fn pessimistic_tear_loses_the_record() {
        let mut f = Flash::new(90.0, 1.0);
        let mut rng = Rng::new(1);
        f.queue(Stored::EvtCeiling(64));
        f.advance(0);
        f.advance(100_000);
        f.queue(Stored::EvtCeiling(128));
        f.advance(200_000);
        f.power_cut(&mut rng);
        assert_eq!(f.read(Key::EvtCeiling), None);
    }
}
