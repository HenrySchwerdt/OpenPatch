//! OpenPatch virtual pod (TEST PROJECT: not a medical device, never to be worn).
//!
//! Physics-based plant models (stepper, gears, leadscrew, stick-slip plunger, stadium reservoir,
//! compliance, duckbill, occlusion, bubbles; TMAG5273, dock hall, current sense, interlock,
//! TPL5010, battery, flash with power-loss injection) behind the `openpatch-core` `Hal` trait, a
//! deterministic seeded clock, a scenario runner (`opsim`), Monte Carlo and a JSON line interface.
#![forbid(unsafe_code)]

pub mod board;
pub mod device;
pub mod electrical;
pub mod flash;
pub mod montecarlo;
pub mod params;
pub mod plant;
pub mod report;
pub mod report_text;
pub mod rng;
pub mod runner;
pub mod scenario;
pub mod scenarios;
pub mod server;
pub mod world;
