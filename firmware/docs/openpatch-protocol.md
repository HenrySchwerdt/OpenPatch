# OpenPatch Protocol v1 (native)

> Status: draft v1, matching `firmware/core` (as of 2026-11-18).
> **Experimental DIY device, not a medical device.** The reference implementation
> (`core/src/openpatch_*.c`) and this specification must stay in sync;
> the example frames below are stored as tests (`tests/test_proto.c`).

Units: **mU** = milli-unit (0.001 U), rates in **mU/h**. The insulin volume of one motor step is **not a protocol constant**: it is the pod's drive calibration (section 3.3), reported in `GetStatus`. Rev A (5:1 gear) = 26100 uU = 0.0261 U per step. The app must read it and refuse a pod whose calibration is missing or unknown.
All multi-byte values are **little-endian**.

## 1. GATT profile

Randomly generated 128-bit base UUID (generated once, UUIDv4, do not change):

```
2E092A48-506C-477E-ADD4-448BF149xxxx
```

The last 16 bits (`xxxx`) select the service resp. characteristic:

| Element | UUID | Properties | Purpose |
|---|---|---|---|
| Service | `2E092A48-506C-477E-ADD4-448BF1490001` | - | OpenPatch service |
| Command | `2E092A48-506C-477E-ADD4-448BF1490002` | Write, Write Without Response | phone -> pod, exactly one frame per write |
| Response | `2E092A48-506C-477E-ADD4-448BF1490003` | Notify | pod -> phone, exactly one frame per notification |
| Alert | `2E092A48-506C-477E-ADD4-448BF1490004` | Notify | reserved for v1.x (unsolicited alarms); not implemented in v1, alarms are read with `GetStatus` |

Constraints:

- A frame is at most **244 bytes** (`OP_FRAME_MAX` = ATT MTU 247 - 3). The phone must perform an MTU exchange to >= 247 before the first command; there is no fragmentation in the protocol.
- Advertising: device name `OpenPatch-XXXX` (last 4 hex digits of the address), service UUID in the advertising packet. No payload data in advertising. Advertising interval approx. 1 s (battery).
- Transport: BLE LE Secure Connections with bonding (link-layer encryption) **in addition to** the application-layer encryption (section 5). The pod accepts pairing **only for a limited window after a button press on the pod** (60 s by default, `CONFIG_OPENPATCH_PAIRING_WINDOW_S`); unbonded peers outside that window are disconnected. The pod has no display, so pairing is Just Works (encrypted, not MITM-protected): the physical button press is the authorisation.
- DFU: signed firmware images (MCUboot, ECDSA-P256) are uploaded with the standard mcumgr SMP service over the same encrypted link. The pod refuses uploads while delivery is not suspended.

## 2. Frame format

```
Offset  Size  Field
0       1     version   = 0x01
1       1     type      command ID (response: command ID | 0x80)
2       1     flags     bit0 = encrypted, bit1 = response
3       2     seq       sequence number (LE)
5       2     len       payload length in bytes (LE)
7       len   payload   TLV list (resp. ciphertext || 8-byte tag)
7+len   2     crc16     CRC-16/CCITT-FALSE over bytes 0 ... 7+len-1 (LE)
```

- **CRC-16/CCITT-FALSE**: polynomial 0x1021, initial value 0xFFFF, no reflection, no final XOR. Check value `"123456789"` -> `0x29B1`.
- Total length = 9 + len, at most 244. The receiver checks in this order: minimum/maximum length and `len` consistency (`OP_ERR_FRAME`), CRC (`OP_ERR_CRC`), version (`OP_ERR_VERSION`).
- Frames with errors are **dropped without a response**; the pod does not change any state in that case.
- The CRC only protects against transmission errors; integrity/authenticity against attackers is provided by AES-CCM (section 5).

### 2.1 TLV payload

```
tag (u8) | length (u8) | value (length bytes)
```

- Unknown tags are **skipped** (forward compatibility). A truncated TLV makes the frame invalid (`OP_ERR_FRAME`).
- Fixed lengths per tag (see table); wrong length -> `OP_ERR_FRAME`.
- Tags of other commands in the same frame are ignored.

## 3. Commands

| ID | Name | Request tags | Response (in addition to `RESULT`) |
|---|---|---|---|
| 0x01 | GetStatus | - | all status tags (0x10-0x1C, 0x09, 0x0E) |
| 0x02 | SetBasalSchedule | 1-24 x `BASAL_SEG` | - |
| 0x03 | SetTempBasal | `RATE_MU_H`, `DURATION_MIN` (both mandatory) | - |
| 0x04 | CancelTempBasal | - | - (`NOT_FOUND` if none active) |
| 0x05 | Bolus | `AMOUNT_MU` (mandatory) | - |
| 0x06 | CancelBolus | - | - (`NOT_FOUND` if none active) |
| 0x07 | Suspend | - | - |
| 0x08 | Resume | - | - (`FAULT` while a fault is latched) |
| 0x09 | Fill/Prime | `SUB_OP` (1 = Fill, 2 = Prime) + `FILL_MU` resp. `PRIME_STEPS` | - |
| 0x0A | Acknowledge | `FAULT_MASK` (optional, default 0xFFFF) | - |
| 0x0B | GetHistory | `FROM_ID` (opt., default 0), `MAX_EVENTS` (opt., default 10) | `NEXT_EVENT_ID`, `OLDEST_EVENT_ID`, 0-10 x `HISTORY_EVENT` |
| 0x0C | SetPairing | `PAIR_ID`, `ROLE` (both mandatory) | - (`ALREADY_ACTIVE` while active, `BAD_ARG` for id 0 / role not 1 or 2) |
| 0x0D | Activate | `PAIR_ID`, `ACTIVATION_ID`, 1-24 x `BASAL_SEG`, optionally `RATE_MU_H` + `DURATION_MIN` (remaining temp basal, both or neither) | all status tags, section 3.4 |
| 0x0E | Release | `PAIR_ID` | all status tags + `ACT_DELIVERED_MU`; see section 3.4 |

Every command may additionally contain `TIME_OF_DAY_MS` (u32, local milliseconds since midnight); the pod
adopts the time for the basal schedule. The phone sends it at least with `SetBasalSchedule` and after every connection setup.

Response: same `seq`, `type | 0x80`, flag "response", first tag always `RESULT` (u8, error codes section 4).
Unknown command IDs are answered with `RESULT = UNSUPPORTED`, faulty TLVs with `RESULT = FRAME`.

### 3.1 Tag table

| Tag | Name | Type | Meaning |
|---|---|---|---|
| 0x01 | RESULT | u8 | error code (0 = OK) |
| 0x02 | BASAL_SEG | u8 start_slot, u16 rate | segment; slot 0-47 (30 min); first segment slot 0; strictly ascending; a segment ends at the next start resp. at midnight |
| 0x03 | RATE_MU_H | u16 | temp basal rate in mU/h |
| 0x04 | DURATION_MIN | u16 | temp duration, multiple of 30, 30...720 |
| 0x05 | AMOUNT_MU | u32 | bolus amount, multiple of 50 mU (0.05 U) |
| 0x06 | FILL_MU | u32 | filled insulin amount in mU |
| 0x07 | PRIME_STEPS | u16 | prime steps, 1...(0.52 U in steps): 20 on the 5:1 drive, 64 on the 16:1 drive |
| 0x08 | SUB_OP | u8 | 1 = Fill (report fill amount), 2 = Prime |
| 0x09 | FAULT_MASK | u16 | fault bits (section 4.1) |
| 0x0A | FROM_ID | u32 | history from this ID (inclusive) |
| 0x0B | MAX_EVENTS | u8 | max. events per response (0 or > 10 -> 10) |
| 0x0C | TIME_OF_DAY_MS | u32 | local time of day, optional with every command |
| 0x0D | HISTORY_EVENT | 17 B | `u32 id, u32 time_s, u8 type, i32 a, i32 b` |
| 0x0E | NEXT_EVENT_ID | u32 | ID of the next (not yet assigned) event |
| 0x0F | OLDEST_EVENT_ID | u32 | oldest ID still stored |
| 0x10 | STATE_FLAGS | u16 | bit0 suspended, 1 bolus active, 2 temp active, 3 basal schedule present, 4 reservoir low, 5 alarm, 6 filled, 7 battery low, 8 wear warning (>= 44 h), 9 docked, 10 active pod |
| 0x11 | RESERVOIR_MU | u32 | remaining amount (conservatively rounded down) |
| 0x12 | BATTERY_MV | u16 | battery voltage |
| 0x13 | BOLUS_REMAINING_MU | u32 | part of the bolus not yet delivered |
| 0x14 | TEMP_RATE_MU_H | u16 | 0 if no temp active |
| 0x15 | TEMP_REMAINING_MIN | u16 | rounded up |
| 0x16 | CURRENT_RATE_MU_H | u16 | currently valid basal rate (temp or schedule) |
| 0x17 | DELIVERED_MU | u32 | amount delivered since boot (from steps) |
| 0x18 | SCHEDULED_MU | u32 | amount programmed since boot (shows deficit on suspend/veto) |
| 0x19 | FW_VERSION | u16 | `major<<8 \| minor` |
| 0x1A | LAST_SEQ | u16 | highest accepted command sequence number (see below) |
| 0x1B | DRIVE_CAL | 10 B | `u16 drive_id, u32 micro_u_per_step, u16 steps_per_rev, u16 gear_ratio_x100` (GetStatus, section 3.3). All zero = the pod has no valid calibration and refuses to deliver |
| 0x1C | POD_INFO | 10 B | `u32 pair_id (0 = unpaired), u8 role (0 none, 1 A, 2 B), u8 delivery_state, u32 wear_s` (GetStatus, section 3.4) |
| 0x1D | PAIR_ID | u32 | pair identifier chosen by the app (SetPairing / Activate / Release) |
| 0x1E | ROLE | u8 | 1 = pod A, 2 = pod B |
| 0x1F | ACTIVATION_ID | u32 | non-zero, chosen by the app per swap; makes Activate idempotent |
| 0x20 | ACT_DELIVERED_MU | u32 | insulin delivered since the activation (Release response) |

`GetStatus` carries `FAULT_MASK` (0x09) as the currently latched faults and `NEXT_EVENT_ID` (0x0E) as the next event ID.

**`LAST_SEQ` (resync after a pod reboot).** `GetStatus` returns in `LAST_SEQ` the highest command `seq` the pod has accepted so far. As the request itself is accepted before the response is built, the value is at least the `seq` of that `GetStatus`. The pod stores the highest accepted `seq` persistently (section 5.2) and restores it at boot, so the phone can read it after a pod reboot or a reconnect and continue its counter above it. Command `seq` values must be strictly increasing (gaps are allowed), so a phone whose counter fell behind the pod's persisted value must jump ahead; a frame with `seq <= LAST_SEQ` is dropped silently as a replay (it cannot be answered), therefore the phone should always start a session with a `seq` that is clearly above the last value it knows (e.g. last known + 16) and then align its counter with `LAST_SEQ`.

### 3.3 Drive calibration (`DRIVE_CAL`)

SAFETY CRITICAL. The insulin volume per motor step scales every dose, and it depends on the motor/gearbox that is built in (Rev A Zhaowei ZWBPD006006 5:1: 0.0261 U/step; Faulhaber ADM0620 + 16:1: 0.0082 U/step). The earlier 10:1 concept (0.0131 U/step) is gone: a pod or app that still assumes it delivers **twice** the commanded insulin.

- Pod: the calibration is selected at build time (`CONFIG_OPENPATCH_DRIVE_ZWBPD006006_5_1` default, `CONFIG_OPENPATCH_DRIVE_FAULHABER_16_1`), stored with magic + CRC-32 on first boot and compared with the build on every later boot. Missing, corrupt, out-of-range (4000..60000 uU) or unknown calibration latches `NO_CALIBRATION` (fault bit 6): no step is ever approved.
- Wire: `DRIVE_CAL` = `u16 drive_id` (1 = ZWBPD006006 5:1, 2 = Faulhaber 16:1), `u32 micro_u_per_step` (uU per step; 26100 / 8156), `u16 steps_per_rev` (20), `u16 gear_ratio_x100` (500 / 1600). Little-endian, 10 bytes. `steps_per_rev` and the ratio are informational.
- App: reads `DRIVE_CAL` from every `GetStatus`; `micro_u_per_step` is the only conversion factor between insulin and steps. It must refuse to operate when the tag is missing, all zero, or not one of the known (`drive_id`, `micro_u_per_step`) pairs.

### 3.4 Two-pod system (pair, role, Activate, Release, dock, wear)

Spec: `spec/design-parameters.md` section 1b. One user owns two identical pods (A and B); only one may ever deliver. The pods do not talk to each other; the app is the arbiter, the pod enforces what it can alone.

**Pairing.** `SetPairing(PAIR_ID, ROLE)` stores a non-zero pair id and role A/B. Only a released pod accepts it (`ALREADY_ACTIVE` otherwise); `Activate` and `Release` carry the pair id and are refused with `PAIR` on a mismatch or an unpaired pod.

**Delivery state** (`POD_INFO.delivery_state`):

| Value | Name | Meaning |
|---|---|---|
| 0 | RELEASED | not the active pod: never delivers; all delivery commands (`SetBasalSchedule`, `SetTempBasal`, `Bolus`, `Resume`, `Prime`) answer `RELEASED`. `Fill`, `Suspend`, `Acknowledge`, `GetStatus`, `GetHistory` still work (the spare is refilled while parked) |
| 1 | ACTIVE | active and docked |
| 2 | PAUSED_UNDOCKED | active but the DOCKED input is off: **no step is executed**. Not a latched fault: basal continues without catch-up when the pod is docked again; a running bolus is cancelled at the moment of undocking (`BOLUS_CANCEL` event) and not resumed |
| 3 | STOPPED_WEAR | wear limit reached (fault bit 7) |

**DOCKED input.** Magnet in the cannula adapter + Hall switch (`dock-gpios` in the devicetree; the dev kit simulates it with Button 2). It is read by the safety supervisor path, not by the command layer: the supervisor vetoes every step while the input is false or the pod is not active, regardless of what the engine requested. The input is sampled at every tick and again immediately before every bolus, resume, prime and activate. A missing HAL hook or unready GPIO reads as "not docked". Events: `UNDOCKED` (18), `DOCKED` (19).

**Wear timer.** Starts at `Activate` (not at fill), counts only while active (a stalled main loop is counted in full), is persisted as an upper bound across resets and reported as `POD_INFO.wear_s`. At 44 h the pod sets state flag bit 8 (wear warning), logs `WEAR_WARNING` (22) once and beeps. At 52 h it latches fault bit 7, stops delivery, sounds the alarm and logs `WEAR_EXPIRED` (23). The fault cannot be acknowledged; `Release` still works and a new `Activate` restarts the timer and clears it. (The 48 h figure in the spec is the nominal wear time; the app should schedule a swap before the 44 h warning.)

**Activate** (`PAIR_ID`, `ACTIVATION_ID` != 0, basal schedule, optional temp basal `RATE_MU_H` + remaining `DURATION_MIN`). Order of checks and results:

1. not paired / wrong pair id -> `PAIR`
2. already active: same `ACTIVATION_ID` -> `OK` (idempotent no-op, lost response), different id -> `ALREADY_ACTIVE`
3. on a charger -> `CHARGING`; not docked -> `NOT_DOCKED`; any latched fault other than an old wear fault -> `FAULT`; not filled -> `RESERVOIR`
4. schedule / temp basal validation (0.05 U raster, max basal, 30 min temp granularity) -> `BAD_ARG` / `LIMIT`

Activate is all-or-nothing. On success the pod is active with the schedule set, the wear timer at 0, and **delivery still suspended**: the app then primes the cannula connector (`Prime`, at most 0.52 U) and sends `Resume`, which also starts the handed-over temp basal with the remaining duration. The response carries the full status block.

**Release** (`PAIR_ID`). Stops motor and delivery (cancels bolus and temp basal), makes the pod released, and answers with the full status block (final `RESERVOIR_MU`, lifetime `DELIVERED_MU`) plus `ACT_DELIVERED_MU` (insulin delivered since the activation; since the last boot if the pod rebooted meanwhile). Works while undocked, is idempotent (a repeat returns the same totals) and logs `RELEASE` (21) once.

**Charger.** A pod that is on a charger is forced to `RELEASED` on the next tick (reason 1 in the `RELEASE` event); leaving the charger does not re-activate it, `Activate` is refused with `CHARGING`.

**Handover sequence (app side).** `Release(old)` -> wait for `OK` + totals -> user moves the adapter / docks the new pod -> `GetStatus(new)` confirms docked, filled, charged -> `Activate(new)` -> `Prime` connector -> `Resume`. If the old pod cannot be reached, the app must not activate the new pod until the user confirms that the old pod is physically removed; an undocked old pod cannot deliver (dock hard-gate) even if its `Release` never arrived.

### 3.2 Semantics (DASH-like)

- After power-up the pod is **suspended**; only `Resume` starts basal delivery.
- Bolus speed 1.5 U/min. During a bolus basal delivery rests, without catch-up.
- `Suspend` cancels bolus and temp basal; `Resume` returns to the programmed basal rate.
- **Communication loss**: every authenticated, fresh command resets the timer. 30 min after the last command a running temp basal falls back to the programmed basal schedule (event `TEMP_COMM_FALLBACK`). Boluses are not affected (they last at most 17 min at 25 U).
- `Fill` is only allowed in the suspended state (`NOT_SUSPENDED` otherwise), sets the reservoir level and the encoder reference point. `Prime` (suspended only, max. 0.52 U = `OP_MAX_PRIME_MU`, i.e. 20 steps on the 5:1 drive and 64 on the 16:1 drive) delivers insulin through the safety supervisor and is verified by the encoder. Only the active, docked pod can prime (`RELEASED` / `NOT_DOCKED` otherwise): in the two-pod flow this is the cannula connector prime after `Activate`. **Never prime a pod that is connected to a body.**
- `Acknowledge` acknowledges latched faults. It **never** starts delivery automatically (explicit `Resume` afterwards). Faults whose cause persists (battery critical, reservoir empty) stay latched (`PERSISTS`).
- Physical button on the pod: short press = open the pairing window and silence an active alarm; hold >= 3 s = emergency stop (cancel bolus, suspend). Placing the pod on a charger suspends delivery and forces the pod to `RELEASED` (section 3.4).

## 4. Error codes and fault bits

| Code | Name | Meaning |
|---|---|---|
| 0 | OK | |
| 1 | BAD_ARG | invalid value (0.05 U raster, duration, segment order ...) |
| 2 | LIMIT | above max bolus/max basal (configurable, hard caps 25 U / 30 U/h) |
| 3 | BUSY | a bolus is already running |
| 4 | FAULT | fault latched |
| 5 | SUSPENDED | delivery suspended |
| 6 | NOT_SUSPENDED | command only allowed in the suspended state |
| 7 | RESERVOIR | amount exceeds reservoir content / not filled |
| 8 | PERSISTS | cause of the fault still exists |
| 9 | UNSUPPORTED | unknown command |
| 10 | FRAME | faulty frame/TLV |
| 11 | CRC | (local only, no response is sent) |
| 12 | VERSION | (local only) |
| 13 | REPLAY | (local only) |
| 14 | AUTH | (local only) |
| 15 | TOO_LARGE | buffer/frame too large |
| 16 | HOURLY | bolus would violate the 15 U hourly limit |
| 17 | NOT_FOUND | nothing to cancel |
| 18 | SESSION | sequence space exhausted, new key required |
| 19 | NOT_DOCKED | the DOCKED input is not asserted (pod is not on the cannula adapter) |
| 20 | RELEASED | the pod is not the active pod of its pair: delivery commands refused |
| 21 | ALREADY_ACTIVE | Activate with a different activation id while active; SetPairing while active |
| 22 | PAIR | pod not paired, or `PAIR_ID` does not match |
| 23 | WEAR_EXPIRED | reserved (a wear-expired pod answers `FAULT`) |
| 24 | CHARGING | Activate refused: the pod is on a charger |

### 4.1 Fault bits (`FAULT_MASK`)

| Bit | Name | Trigger |
|---|---|---|
| 0 | OCCLUSION | (commanded - encoder-confirmed) > 2 U, or spindle stands still despite steps |
| 1 | ENCODER_DEVIATION | deviation > 10 % over a window of >= 1 U |
| 2 | RESERVOIR_EMPTY | reservoir empty or step vetoed by the reservoir model |
| 3 | BATTERY_CRITICAL | < 3.3 V (assumption, adjustable in `op_types.h`) |
| 4 | LIMIT_EXCEEDED | veto by the 15 U/h window or the per-minute backstop (1.7 U/min = 65 steps/min on the 5:1 drive) |
| 5 | INTERNAL | motor did not execute approved steps |
| 6 | NO_CALIBRATION | drive calibration missing, corrupt, outside 4..60 mU/step or not a known drive: no step is ever approved; cannot be acknowledged |
| 7 | WEAR_EXPIRED | >= 52 h since activation: delivery stopped, alarm; cannot be acknowledged, released by a new `Activate` |

Latched faults immediately stop any delivery, activate the alarm buzzer and the driver enable gate. Acknowledgement only via `Acknowledge`.

## 5. Security

### 5.1 AES-CCM (interface, placeholder)

With the flag `encrypted` the payload consists of `ciphertext || tag` (tag = 8 bytes, AES-128-CCM, L = 2).

- **AAD** = the 7 header bytes (incl. `type`, `flags`, `seq`, `len`) -> the header cannot be manipulated.
- **Nonce (13 bytes)** = `salt[4] || dir[1] || seq[2, LE] || 0x00 x 6`; `dir` = 0 for commands, 1 for responses; `salt` comes from the key agreement of the session.
- The interface (`op_ccm_ops_t` in `openpatch_proto.h`) encapsulates `encrypt`/`decrypt`; the real implementation (PSA Crypto) will be plugged in later. **Only an insecure test dummy exists in the repository** (`tests/fake_ccm.c`); it must never get into firmware.
- Production: `allow_plaintext = false`. Plaintext frames are then dropped with `AUTH`. Until the CCM backend exists, a production-configured pod therefore **cannot be commanded at all**; only the development configuration (`dev.conf`, `CONFIG_OPENPATCH_ALLOW_PLAINTEXT`) accepts frames.
- Response frames use the command `seq` with `dir = 1`; thus a nonce is never used twice.

### 5.2 Replay protection

- Command `seq` values must **increase strictly monotonically** (gaps allowed). Equal or smaller values -> `REPLAY`. State is updated only after successful authentication, so forgeries cannot burn the counter.
- `seq = 0xFFFF` is reserved; from `0xFFFE` the session must be re-established (`SESSION`) before a nonce could repeat.
- Hook `on_seq_accepted(ctx, seq)`: the Zephyr application persists the highest accepted `seq` (settings key `op/seq`) on every accepted command and restores it at boot (replay protection across restarts); the same value is reported as `LAST_SEQ` in `GetStatus`.
- Open point: the key agreement (e.g. ephemeral X25519 + HKDF based on the BLE bonding) is not defined in v1; it supplies keys and `salt`.

## 6. History (event log)

- Ring buffer (128 entries) with **persistent, strictly increasing 32-bit IDs** starting at 1. The platform stores an ID **ceiling** (always >= every issued ID, extended in steps of 64) and passes it to `op_log_restore` at boot, so IDs survive restarts; after a reset the log continues at the ceiling, i.e. a gap in the IDs shows that the pod restarted. The events themselves live in RAM (flash persistence of the event contents is an open point).
- `GetHistory(FROM_ID)` returns, from `max(FROM_ID, OLDEST_EVENT_ID)`, up to 10 events (fits one frame incl. 8-byte tag). Paging: next `FROM_ID` = last ID + 1; done when `FROM_ID >= NEXT_EVENT_ID`. A gap (`FROM_ID < OLDEST`) indicates overwritten events.
- Event types (`type`, fields `a`/`b`): 1 BOOT, 2 BOLUS_START (a = mU), 3 BOLUS_DONE, 4 BOLUS_CANCEL (a = undelivered mU), 5 TEMP_START (a = mU/h, b = min), 6 TEMP_DONE, 7 TEMP_CANCEL, 8 TEMP_COMM_FALLBACK, 9 BASAL_SET (a = segments), 10 SUSPEND, 11 RESUME, 12 FILL (a = mU), 13 PRIME (a = steps), 14 FAULT (a = new bits), 15 ACK (a = mask), 16 LOW_RESERVOIR (a = mU), 17 LOW_BATTERY (a = mV).
- `time_s` = seconds since boot (the pod has no wall clock; the phone maps via BOOT events).

### 6.1 Persistent pod state (Zephyr settings, NVS)

| Key | Content | Write policy |
|---|---|---|
| `op/evt` | event-ID ceiling | when fewer than 16 IDs of headroom remain |
| `op/seq` | highest accepted command `seq` | every accepted command |
| `op/res` | reservoir fill (mU) and consumed steps | on fill, and every ~64 consumed steps; stored with a margin of 48-64 steps, so after a power loss the model can only be *lower* than reality (up to ~0.84 U per reset) |

## 7. Examples (hex)

GetStatus, `seq = 1` (plaintext):

```
01 01 00 01 00 00 00 BB 7A
```

Bolus 2.00 U (`AMOUNT_MU = 2000`), `seq = 0x0102`:

```
01 05 00 02 01 06 00 05 04 D0 07 00 00 38 31
```

Response `OK` to this bolus:

```
01 85 02 02 01 03 00 01 01 00 34 06
```

## 8. Versioning

- `version` in the frame is the major version; incompatible changes increase it (`VERSION` error on mismatch).
- Compatible extensions = new tags / new optional fields (old receivers skip them). New command IDs are assigned from 0x0C. Tag 0x1A (`LAST_SEQ`) was added as such an extension to v1.
- `FW_VERSION` in the status lets the phone detect features.

## 9. Open points

1. Key agreement and pairing flow (section 5.2).
2. Real AES-CCM connection (PSA); persistence of the event contents (not only the IDs) in flash. *Closed in the Zephyr port: persistence of `seq`, event IDs and reservoir level (section 6.1).*
3. Alert characteristic (unsolicited alarms) for v1.x.
4. Motor current/back-EMF as an additional occlusion input (today encoder only).
5. Limits `BATTERY_CRITICAL`/`LOW` are assumptions, to be matched with the real battery discharge curve.
