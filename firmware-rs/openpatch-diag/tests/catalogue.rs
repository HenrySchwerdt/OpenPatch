//! Catalogue integrity (docs/06-diagnostics.md 2.8 and 6.1 "Catalogue integrity").
//!
//! The generated `catalogue.rs` is checked against `spec/diag-codes.csv` by an independent Rust
//! CSV reader, and the whole drift check (`tools/gen_diag.py --check`: generated files up to date,
//! doc section 4 tables equal to the CSV) runs from here so `cargo test --workspace` fails on drift.

use openpatch_diag::*;
use std::collections::HashSet;
use std::path::PathBuf;
use std::process::Command;

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..").canonicalize().unwrap()
}

/// Minimal RFC 4180 reader (quoted fields, doubled quotes, embedded newlines).
fn parse_csv(s: &str) -> Vec<Vec<String>> {
    let (mut rows, mut row, mut cell) = (Vec::new(), Vec::new(), String::new());
    let mut q = false;
    let mut it = s.chars().peekable();
    while let Some(c) = it.next() {
        match (q, c) {
            (true, '"') => {
                if it.peek() == Some(&'"') {
                    cell.push('"');
                    it.next();
                } else {
                    q = false;
                }
            }
            (true, _) => cell.push(c),
            (false, '"') => q = true,
            (false, ',') => row.push(std::mem::take(&mut cell)),
            (false, '\n') => {
                row.push(std::mem::take(&mut cell));
                rows.push(std::mem::take(&mut row));
            }
            (false, _) => cell.push(c),
        }
    }
    if !cell.is_empty() || !row.is_empty() {
        row.push(cell);
        rows.push(row);
    }
    rows
}

fn code_from_str(s: &str) -> DiagCode {
    let p: Vec<&str> = s.split('-').collect();
    assert_eq!(p.len(), 3, "{s}");
    DiagCode::new(
        u8::from_str_radix(p[0], 16).unwrap(),
        u8::from_str_radix(p[1], 16).unwrap(),
        u16::from_str_radix(p[2], 16).unwrap(),
        0,
    )
}

#[test]
fn catalogue_has_155_codes_with_the_documented_severity_split() {
    assert_eq!(CATALOGUE.len(), 155);
    let n = |s| CATALOGUE.iter().filter(|c| c.severity == s).count();
    assert_eq!((n(Severity::Info), n(Severity::Warning), n(Severity::Fault), n(Severity::Latched)), (2, 55, 70, 28));
}

#[test]
fn catalogue_is_sorted_unique_and_instance_free() {
    for w in CATALOGUE.windows(2) {
        assert!(w[0].code < w[1].code, "{} !< {}", w[0].code, w[1].code);
    }
    let names: HashSet<_> = CATALOGUE.iter().map(|c| c.name).collect();
    assert_eq!(names.len(), CATALOGUE.len());
    for c in CATALOGUE.iter() {
        assert_eq!(c.code.inst(), 0);
        assert_eq!(c.code, c.code.identity());
        assert_eq!(lookup(c.code), Some(c));
        assert_eq!(lookup(c.code.with_inst(7)), Some(c), "lookup ignores the instance");
    }
}

#[test]
fn every_fault_or_latched_code_has_a_legacy_bit_and_no_other_code_has() {
    for c in CATALOGUE.iter() {
        assert_eq!(c.legacy().is_some(), c.severity.stops_delivery(), "{}", c.code);
        assert_eq!(legacy_bit(c.code, c.severity).is_some(), c.severity.stops_delivery());
    }
}

#[test]
fn documented_legacy_mapping_2_7() {
    use codes::*;
    for (c, bit) in [
        (OCCLUSION_SHORTFALL, 0),
        (OCCLUSION_CURRENT_RISE, 0),
        (CARRIAGE_JAM_FWD, 0),
        (MOTOR_STALL_FREE, 0),
        (ENC_REV_DEVIATION, 1),
        (ENC_WINDOW_DEVIATION, 1),
        (GEAR_RATIO_MISMATCH, 1),
        (GEAR_TOOTH_SKIP, 1),
        (TRAVEL_LENGTH_MISMATCH, 1),
        (RESERVOIR_EMPTY, 2),
        (RES_MODEL_RECORD_CORRUPT, 2),
        (RES_MODEL_NEGATIVE, 2),
        (BATTERY_CRITICAL, 3),
        (HOURLY_LIMIT_VETO, 4),
        (PER_MINUTE_LIMIT_VETO, 4),
        (REQUEST_ABOVE_HARD_CAP, 4),
        (VMOT_STUCK_ON, 5),
        (TMAG_NO_ACK, 5),
        (CAL_RECORD_INVALID, 6),
        (CAL_PRESET_MISMATCH, 6),
        (TEST_CAL_IN_BUILD, 6),
        (WEAR_EXPIRED, 7),
    ] {
        let i = c.info().unwrap();
        assert_eq!(i.legacy(), Some(bit), "{}", c);
    }
    // I and W never project
    assert_eq!(legacy_bit(codes::BATTERY_LOW, Severity::Warning), None);
    // an escalated record projects with the catalogue bit, an unknown code with INTERNAL
    assert_eq!(legacy_bit(codes::TMAG_CRC_ERRORS, Severity::Fault), Some(5));
    assert_eq!(legacy_bit(DiagCode(0x1FFF_FF00), Severity::Fault), Some(5));
}

#[test]
fn matches_the_csv_source_of_truth() {
    let csv = std::fs::read_to_string(repo_root().join("spec/diag-codes.csv")).unwrap();
    let rows = parse_csv(&csv);
    let head = &rows[0];
    let col = |n: &str| head.iter().position(|h| h == n).unwrap_or_else(|| panic!("column {n}"));
    let (cc, cn, cs, cf, cf2, ca, cl, ch) = (col("code"), col("name"), col("sev"), col("fru"), col("fru2"), col("action"), col("legacy_bit"), col("haz"));
    assert_eq!(rows.len() - 1, CATALOGUE.len());
    let fru = |s: &str| match s {
        "" => Fru::None,
        _ => FRU_NAMES.iter().position(|n| *n == s).map(|i| Fru::from_u8(i as u8).unwrap()).unwrap_or_else(|| panic!("fru {s}")),
    };
    for (r, info) in rows[1..].iter().zip(CATALOGUE.iter()) {
        assert_eq!(code_from_str(&r[cc]), info.code);
        assert_eq!(r[cn], info.name);
        let sev = match r[cs].as_str() {
            "I" => Severity::Info,
            "W" => Severity::Warning,
            "F" => Severity::Fault,
            "L" => Severity::Latched,
            s => panic!("sev {s}"),
        };
        assert_eq!(sev, info.severity, "{}", r[cc]);
        assert_eq!(fru(&r[cf]), info.fru, "{}", r[cc]);
        assert_eq!(fru(&r[cf2]), info.fru2, "{}", r[cc]);
        assert_eq!(ACTION_NAMES.iter().position(|n| *n == r[ca]).map(|i| Action::from_u8(i as u8).unwrap()), Some(info.action), "{}", r[cc]);
        assert_eq!(r[cl].parse::<u8>().unwrap_or(0xFF), info.legacy_bit, "{}", r[cc]);
        let mut mask = 0u16;
        for h in r[ch].split_whitespace() {
            mask |= 1 << h[1..].parse::<u16>().unwrap();
        }
        assert_eq!(mask, info.hazards, "{}", r[cc]);
    }
}

const FRU_NAMES: [&str; 19] = [
    "NONE", "CTRL", "PODB", "FFC", "MOTOR", "GEAR", "SCREW", "RESV", "SEAL", "CAP", "NEEDLE", "BATT", "APP", "MAGD", "MAGS", "USB", "CANN", "FW", "CHG",
];
const ACTION_NAMES: [&str; 20] = [
    "NONE", "RETRY", "ACK", "REFILL", "REDOCK", "RECABLE", "REPHONE", "CHECK_POWER", "REPLACE", "RESEAT", "SWAP_POD", "PRIME", "REPROVISION", "UPDATE_FW",
    "REPORT_BUG", "WAIT_COOL", "REPAIR", "UPDATE_APP", "CHECK_CANNULA", "ISOLATE",
];

#[test]
fn drift_check_generated_files_and_doc_tables() {
    let root = repo_root();
    let out = match Command::new("python3").arg(root.join("tools/gen_diag.py")).arg("--check").output() {
        Ok(o) => o,
        Err(e) => {
            // CI always has python3; a developer box without it still gets the Rust-side CSV test above
            eprintln!("python3 not available, skipping the generator drift check: {e}");
            return;
        }
    };
    assert!(
        out.status.success(),
        "catalogue drift: {}{}",
        String::from_utf8_lossy(&out.stdout),
        String::from_utf8_lossy(&out.stderr)
    );
}

#[test]
fn code_fields_and_display() {
    let c = codes::VMOT_STUCK_ON;
    assert_eq!(c.raw(), 0x1060_0100, "worked example of 5.4");
    assert_eq!((c.layer(), c.component(), c.fault(), c.inst()), (1, 0x06, 1, 0));
    assert_eq!(std::format!("{c}"), "1-06-001");
    assert_eq!(std::format!("{}", c.with_inst(3)), "1-06-001/03");
    assert_eq!(std::format!("{}", codes::LFXO_NOT_RUNNING), "1-0B-001");
    assert_eq!(std::format!("{}", codes::BATTERY_LOW.with_inst(1)), "A-A0-001/01");
    assert_eq!(c.where_(), 0x1060);
    assert_eq!(c.what(), 0x0100);
    assert_eq!(DiagCode::new(1, 0x06, 1, 0), c);
    assert_eq!(c.with_inst(9).identity(), c);
}

#[test]
fn record_layout_matches_the_worked_example() {
    // docs/06-diagnostics.md 5.4: DIAG_RECORD of 1-06-001
    let wire: [u8; 32] = [
        0x05, 0, 0, 0, 0x00, 0x01, 0x60, 0x10, 0x03, 0x08, 0x01, 0x00, 0x2C, 0x01, 0, 0, 0x30, 0x07, 0, 0, 0xE8, 0x03, 0, 0, 0x39, 0x30, 0, 0, 0x01, 0x43, 0, 0,
    ];
    let r = DiagRecord::from_bytes(&wire).unwrap();
    assert_eq!(r.rec_id, 5);
    assert_eq!(r.code, codes::VMOT_STUCK_ON);
    assert_eq!((r.severity(), r.action(), r.fru()), (Severity::Latched, Some(Action::Replace), Some(Fru::Ctrl)));
    assert_eq!((r.t_s, r.ctx_a, r.ctx_b, r.ctx_c, r.count), (300, 1840, 1000, 12345, 1));
    assert_eq!(r.flags, flags::LATCHED | flags::ACTIVE | flags::ROOT);
    assert!(r.is_root() && r.is_active() && r.is_latched() && !r.is_clear_record());
    assert_eq!(r.to_bytes(), wire);
}

#[test]
fn record_decoder_is_total_and_unknown_values_are_failsafe() {
    assert!(DiagRecord::from_bytes(&[0; 31]).is_none());
    assert!(DiagRecord::from_bytes(&[0; 33]).is_none());
    let mut b = [0u8; 32];
    b[8] = 9; // unknown severity
    b[9] = 200;
    b[10] = 99;
    let r = DiagRecord::from_bytes(&b).unwrap();
    assert_eq!(r.severity(), Severity::Fault, "unknown severity is a fault, never ignored");
    assert_eq!((r.action(), r.fru()), (None, None));
    assert_eq!(r.to_bytes(), b, "lossless");
}

#[test]
fn every_enum_value_round_trips() {
    for v in 0..=255u8 {
        if let Some(s) = Severity::from_u8(v) {
            assert_eq!(s as u8, v);
        }
        if let Some(a) = Action::from_u8(v) {
            assert_eq!(a as u8, v);
        }
        if let Some(f) = Fru::from_u8(v) {
            assert_eq!(f as u8, v);
        }
    }
    assert!(Fru::from_u8(Fru::COUNT).is_none());
    assert!(Fru::from_u8(Fru::COUNT - 1).is_some());
}
