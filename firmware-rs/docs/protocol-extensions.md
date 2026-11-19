# OpenPatch protocol: Rust extensions (byte compatible with v1)

> TEST PROJECT, never to be worn. Source of truth: `openpatch-proto/src/{consts,msg,codec_*,session}.rs`. Everything below is additive:
> v1 receivers skip unknown tags, frame layout, CRC, TLV encoding, AAD / nonce rules, `seq` rules and all v1 command ids and tags are unchanged.

## Command 0x0F FillDraw

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
| 27 | Docked | `FillDraw` while docked |

(25 is unused/removed.)

## GetStatus additions (appended after POD_INFO)

| Tag | Name | Type | Meaning |
|---|---|---|---|
| 0x21 | DRAW_STATE | u8 | 0 idle, 1 drawing, 2 done, 3 stalled, 4 aborted |
| 0x22 | DRAW_REQUESTED_MU | u32 | requested volume |
| 0x23 | DRAW_DONE_MU | u32 | volume actually drawn (also partial for stalled / aborted) |

`STATE_FLAGS`: bit 11 `DRAWING`, bit 12 `PRIME_REQUIRED`. `FW_VERSION` = 0x0200. `DRIVE_CAL` carries the preset id (0x20 NFP-608-26.45, 0x21 / 0x22 Zhaowei,
0x23 Faulhaber), floor uU per step, steps/rev and gear ratio x 100 (the exact rational stays in the pump).

## Notifications on the Alert characteristic (`...0004`, notify)

* Frame type **0x90**, RESPONSE flag set, `seq` = the pump's **own** counter (not a command echo), payload TLV: `NOTIFY_KIND` (0x25, u8):
  1 draw progress, 2 fault, 3 draw done, 4 draw stalled; `NOTIFY_ARG` (0x26, u32): volume mU (kinds 1, 3, 4) or new fault bits (kind 2).
* Encrypted frames use nonce **direction byte 2** so a notification never reuses a command / response nonce. Built by `Pump::notification_frame`.
* The firmware (`safety.rs`) drains `Pump::take_notification` after every tick and frame into `ALERT_OUT`; the BLE task notifies them. Notifications are
  lossy by design (queue of 8, oldest dropped, nobody connected = dropped); `GetStatus` DRAW_* tags are the reliable state.

## Unchanged

GATT UUIDs (Command ...0002, Response ...0003), MTU 247 / frame <= 244 B, pairing window, CRC-16, AES-CCM M = 8 L = 2, replay rules, all v1 commands
(0x01..0x0E) and error codes, event ids and `LAST_SEQ` semantics.
