//! OpenPatch pump core (Rust port of `firmware/core`).
//!
//! TEST PROJECT: experimental, **not a medical device, never to be worn** (see `DISCLAIMER.md`).
//!
//! `no_std`, no alloc, no `unsafe`. Fixed point only. Unit newtypes make U/step mix-ups compile
//! errors. Behaviour is verified against the C reference by differential tests.
#![no_std]
#![forbid(unsafe_code)]

pub mod battery;
pub mod bench;
pub mod bench_ctl;
pub mod burst;
pub mod delivery;
pub mod diag;
pub mod drive_cal;
pub mod faults;
pub mod hal;
pub mod interlock;
pub mod led;
pub mod limits;
pub mod log;
pub mod occlusion;
pub mod persist;
pub mod phase_drive;
pub mod pod;
mod draw;
pub mod pump;
pub mod reservoir;
pub mod safety;
pub mod tmag5273;
pub mod units;

pub use delivery::{BasalSchedule, BasalSeg, DeliveryEngine, EngineEvents, EngineReport};
pub use draw::FillMode;
pub use drive_cal::{DriveCal, DriveId};
pub use faults::Faults;
pub use hal::{Buzzer, Hal, MotorDir, MotorFault};
pub use log::{Event, EventLog, EventType};
pub use openpatch_proto::Error;
pub use pod::{ActivateArgs, DeliveryState, PodState, Role};
pub use pump::{draw_state, Notification, Pump, PumpConfig};
pub use reservoir::Reservoir;
pub use safety::{Observation, SafetySupervisor};
pub use units::*;
