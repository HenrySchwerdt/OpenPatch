# OpenPatch protocol: Rust extensions (byte compatible with v1)

> TEST PROJECT, never to be worn. Source of truth: `openpatch-proto/src/{consts,msg,codec_*,session}.rs`. Everything below is additive:
> v1 receivers skip unknown tags, frame layout, CRC, TLV encoding, AAD / nonce rules, `seq` rules and all v1 command ids and tags are unchanged.

## Command 0x0F AssistedFill

* Payload: `FILL_MU` (tag 0x06, u32 mU). **`0` cancels** a running draw.
* Only while the pump is **suspended AND undocked**. Results: `Docked` (27) if docked, `NotSuspended`, `Busy` while a draw runs,
  `Limit` if `amount > capacity - remaining`, `Fault` if a fault is latched or the angle sensor is missing, `BadArg` if smaller than one step,
  `NotFound` when cancelling without a running draw. `Ok` starts the job; it runs from `Pump::tick()` in chunks of 500 reverse steps (<= 1000 pps),
  re-checking the gates every chunk (dock / not suspended / fault abort it).
* The drawn volume is what the angle sensor confirmed; the reservoir level is raised exactly in steps. A mandatory prime follows.

## Error codes

| Code | Name | Meaning |
|---|---|---|
| 26 | PrimeRequired | `Resume` refused until a prime completed after a fill / draw (`PumpConfig::STRICT`) |
| 27 | Docked | `AssistedFill` while docked |
| 31 | NoSchedule | `Resume` refused: no basal schedule held (e.g. not restorable after a reset); send `SetBasalSchedule` first (`PumpConfig::STRICT`) |

(25 is unused/removed.)

## GetStatus additions (appended after POD_INFO)

| Tag | Name | Type | Meaning |
|---|---|---|---|
| 0x21 | DRAW_STATE | u8 | 0 idle, 1 drawing, 2 done, 3 stalled, 4 aborted |
| 0x22 | DRAW_REQUESTED_MU | u32 | requested volume |
| 0x23 | DRAW_DONE_MU | u32 | volume actually drawn (also partial for stalled / aborted) |

`STATE_FLAGS`: bit 11 `DRAWING`, bit 12 `PRIME_REQUIRED`. `FW_VERSION` = 0x0200. `DRIVE_CAL` carries the preset id (0x27 NFP + miter 1:1 cup pod with the 20.5 x 5.9 bore, primary; 0x26 the same cup pod with the previous 20.5 x 5.5 bore; 0x25 NFP + GHW 16:20, 0x24 NFP G15/12, 0x20 NFP coaxial, 0x30 syringe rig, 0x21 / 0x22 Zhaowei,
0x23 Faulhaber), floor uU per step, steps/rev and gear ratio x 100 (the exact rational stays in the pump).

## Notifications on the Alert characteristic (`...0004`, notify)

* Frame type **0x90**, RESPONSE flag set, `seq` = the pump's **own** counter (not a command echo), payload TLV: `NOTIFY_KIND` (0x25, u8):
  1 draw progress, 2 fault, 3 draw done, 4 draw stalled; `NOTIFY_ARG` (0x26, u32): volume mU (kinds 1, 3, 4) or new fault bits (kind 2).
* Encrypted frames use nonce **direction byte 2** so a notification never reuses a command / response nonce. Built by `Pump::notification_frame`.
* The firmware (`safety.rs`) drains `Pump::take_notification` after every tick and frame into `ALERT_OUT`; the BLE task notifies them. Notifications are
  lossy by design (queue of 8, oldest dropped, nobody connected = dropped); `GetStatus` DRAW_* tags are the reliable state.

## Diagnostics extension (docs/06-diagnostics.md 5.4)

Additive; frame version stays 1, v1 receivers skip the new tags. **The presence of `DIAG_SUMMARY` in `GetStatus` is the feature test** (`FW_VERSION` stays 0x0200 until the
release that bundles the diagnostics firmware; the design doc's 0x0210 is not used as a feature test). The catalogue (codes, severity, FRU, action) lives in
`spec/diag-codes.csv`; `schema` in `DIAG_SUMMARY` is its version.

| Tag | Name | Size | Content |
|---|---|---|---|
| 0x27 | DIAG_SUMMARY | 14 | `u32 top_code` (root of the most severe active record), `u8 top_sev, top_action, top_fru, n_latched, n_active, post_state`, `u16 next_rec_id_lo`, `u16 schema` |
| 0x28 | FRU_HEALTH | 8 | `u64`, 2 bits per FRU id 0..31: 0 unknown, 1 ok, 2 degraded, 3 failed |
| 0x29 | DIAG_RECORD | 32 | the record of 2.6 (little endian) |
| 0x2A / 0x2B | NEXT_DIAG_ID / OLDEST_DIAG_ID | 4 | `u32` |
| 0x2C | DIAG_LATCHED | 4..64 | up to 16 x `u32` code of the latched set |
| 0x2D | SELFTEST_STATE | 6 | `u8 state` (0 idle, 1 running, 2 done), `u8 kind` (1 S, 2 A, 3 watchdog), `u16 steps_passed`, `u16 steps_failed` |
| 0x2E | DIAG_CODE | 4 | `u32` code (request of `ClearDiag`; returned with `NotClearable` / `Latched`) |
| 0x2F | POD_UID | 8 | `u64` nRF `FICR.DEVICEID` (omitted when the HAL does not know it) |

`GetStatus` (and the status of `Activate` / `Release`) appends `DIAG_SUMMARY`, `FRU_HEALTH`, `POD_UID`; `STATE_FLAGS` bit 13 `DIAG_ACTIVE`, bit 14 `LATCHED`.
`FAULT_MASK` is the **derived** legacy projection of the active F/L records (every F/L code projects to a bit, default INTERNAL).

| Cmd | Name | Request | Response after `RESULT` |
|---|---|---|---|
| 0x20 (rsp 0xA0) | GetFaultLog | `FROM_ID`, `MAX_EVENTS` (0 or above 4 gives 4) | `NEXT_DIAG_ID`, `OLDEST_DIAG_ID`, `DIAG_LATCHED` (if any), 0..4 x `DIAG_RECORD` (worst case 217 B of payload) |
| 0x21 (rsp 0xA1) | RunSelfTest | `SUB_OP` 1 POST-S, 2 POST-A, 3 watchdog proof | `SELFTEST_STATE`; ends with record `7-74-006`; a proof the board cannot do stays UNKNOWN |
| 0x22 (rsp 0xA2) | ClearDiag | `DIAG_CODE` (0 = all clearable W/F records) | `DIAG_SUMMARY` |

Result codes: 28 `SelfTestRefused` (not suspended, draw running, test running), 29 `Latched` (`Resume` / `Activate` refused, `DIAG_CODE` = root latched code), 30 `NotClearable`
(latched and its verification test has not passed, or the cause persists). `Acknowledge` keeps its legacy meaning (never clears a latched record).

Notification kinds on the Alert characteristic: 5 `DIAG_RAISED` (`NOTIFY_ARG` = code **plus a `DIAG_RECORD` tag** with the complete record), 6 `DIAG_CLEARED` (arg = code),
7 `SELFTEST_PROGRESS` (arg = passed mask << 16 | failed mask). Information records are log only (no notification). Kind 2 `FAULT` is still sent first. The reliable path is
pull: `next_rec_id_lo` moves, the app calls `GetFaultLog(from = last + 1)`. History event 31 `DIAG` (`a` = code, `b` = `ctx_a`) is written only after
`Pump::set_diag_history(true)` (off by default so the event log stays identical to the C reference in the differential tests).

Decoders are tolerant: a diagnostic TLV with an unexpected size is skipped (never a frame error), more than 4 records in one response is a frame error.
Worked example (`1-06-001`, little endian `00 01 60 10`): `27 0E 00 01 60 10 03 08 01 01 01 03 06 00 01 00` is a `DIAG_SUMMARY`; golden frames with real CRC and AES-CCM are in
`docs/vectors/diag-frames.json` (written by `openpatch-proto/tests/diag_vectors.rs`, verified by Rust and Swift; regenerate with `OPENPATCH_WRITE_VECTORS=1`).
The C reference never emits these tags and answers `UNSUPPORTED` to 0x20..0x22; the differential tests compare only the legacy projection and normalise tags 0x27, 0x28, 0x2F
and flag bits 13/14 (`differential-tests/tests/diag_compat.rs` pins that the C parser skips them).

## Unchanged

GATT UUIDs (Command ...0002, Response ...0003), MTU 247 / frame <= 244 B, pairing window, CRC-16, AES-CCM M = 8 L = 2, replay rules, all v1 commands
(0x01..0x0E) and error codes, event ids and `LAST_SEQ` semantics.
