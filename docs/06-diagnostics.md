# Diagnostics, error codes and hardware independence

> **TEST PROJECT, never to be worn or used on a person** (see [DISCLAIMER.md](../DISCLAIMER.md)). This document is a **design**: no code exists yet for most of it.
> It is written so that independent implementation agents can pick up the work packages in section 7.
> Status: design v0.1 (2026-11-19). Related: [02-safety.md](02-safety.md) (hazards H1 to H10), `spec/design-parameters.md` (sections 4, 4a, 5, 7),
> `firmware/docs/openpatch-protocol.md` (wire format v1), `firmware-rs/docs/protocol-extensions.md`, `firmware-rs/docs/architecture.md`.

## 0. Requirement and summary

User requirement (translated): *Most important is security on the board: if there is a software bug, the hardware is still correct. Work with many error codes; modules and error codes are always passed on, so that in the end a system emerges that has hardly any faults, and if a component is faulty, Trio immediately shows which one and that it should be replaced.*

Design in one paragraph: the **hardware layer** (three-gate motor-supply interlock + external watchdog + dock gate) is the last line of defence and is **continuously proven by firmware** (each gate is shown to be able to cut the motor supply, with readbacks), so a silent hardware failure becomes a coded, latched fault. Every anomaly, in every layer, gets a **32-bit diagnostic code** (layer, component, fault, instance) with a **severity**, a **field-replaceable unit (FRU)** and a **recommended action**. Codes are **never swallowed**: each layer forwards the original record and may add its own with a **cause pointer**. Records go into a **persistent fault log** in the pod, are exposed through **protocol extensions** (status summary, `GetFaultLog`, alert notifications), decoded in `OpenPatchCore`, and surfaced in Trio as **LoopKit alerts** ("Replace the controller board", code `1-06-001`) plus a **component health view** (FRU list green/yellow/red) per pod (A/B).

Catalogue size: 150 codes, per-layer counts in 4.8.

## 1. Principles

### 1.1 Defence in depth (layers, outermost last)

| Layer | What | Independent of | Fails to |
|---|---|---|---|
| L0 Physics / mechanics | self-locking M1.6 x 0.35 leadscrew, duckbill check valve, PP reservoir, STSPIN220 current chopper (about 105 to 160 mA per phase) | all electronics and software | no motion without motor current |
| L1 Hardware interlock | `VMOT on = latch AND MCU_EN AND (DOCKED OR DIR_REV)`; latch cleared by TPL5010 reset and `LATCH_CLR_N`; all gates default OFF (pull-downs, P-FET gate pulled to VBUS, DOCK_N pull-up so a missing cable reads "not docked") | firmware | motor supply off |
| L2 External watchdog | TPL5010 (2 s), serviced (DONE) only by the safety task as the last action of a verified tick; RSTn resets the MCU **and** clears the latch through SS14 | firmware liveness | MCU reset, supply off |
| L3 Firmware safety supervisor | separate task (P5 interrupt executor), hard limits (spec section 7), independent bookkeeping (steps, angle, current), approves every step; the delivery engine can not step the motor itself | the delivery engine, BLE, app | veto, latched fault, motor disabled |
| L4 Firmware diagnostics (this document) | proves L1 and L2 can still do their job, plausibility-checks every sensor channel, produces coded records | nothing: it is the observer | coded fault, delivery stopped, replace-part instruction |
| L5 Protocol and app | sequence numbers, AES-CCM, limits again in the app, dose ledger, two-pod arbitration, alerts | the pod | alert, refuse to activate a faulty pod |

Rules that follow from this:

1. A layer never relies on the layer above it for its safety function (L1 and L2 work with no software at all).
2. A layer never assumes the layer below it is healthy: L4 **measures** that L1 and L2 still work (section 3) instead of trusting them.
3. **No delivery with a degraded protection layer.** If any single element of L1/L2 is proven stuck or ineffective, the pod latches (severity L) and refuses to deliver until the element is replaced and re-proven, even though the remaining elements would still protect. Defence in depth that is silently reduced to the one remaining layer is not defence in depth.

### 1.2 Which hazards are covered by hardware alone, and which need firmware

"Hardware alone" means: the safety outcome holds with the MCU firmware arbitrarily wrong (crashed, looping, or malicious), assuming the board is intact.

| Hazard (docs/02-safety.md) | Hardware alone? | What hardware does | What firmware must add | Diagnostic coverage |
|---|---|---|---|---|
| H1 Over-delivery | **partly** | (a) motor can not run unless latch AND MCU_EN AND (docked OR reverse); (b) a hung or crashed MCU loses the latch within the TPL5010 interval (see 1.3); (c) undocked forward motion is impossible; (d) driver chopper limits torque | the **amount**: per-bolus, per-minute and per-hour limits (15 U/h), encoder cross-check, rate limiting. Hardware alone does **not** bound the dose delivered inside the watchdog window (see 1.5) | 6-60-008, 7-70-001..007, 7-77-001..003, 1-06-001, 1-07-*, 1-04-* |
| H2 Under-delivery / occlusion | no (hardware only stops, it does not measure) | dock gate stops delivery when the pod is not on the cannula | angle channel, current rise, shortfall > 2 U | 5-53-*, 6-60-*, 4-42-* |
| H3 Unnoticed delivery stop | partly | after any reset all gates are open; the pod can not resume by itself | boot in SUSPENDED, alarm, app alert, reset cause logging (implemented: an ACTIVE pod after an unplanned reset raises `7-74-002` at FAULT severity, sets the ALARM flag and buzzer and refuses `Resume` until acknowledged; a released pod keeps the catalogue severity W) | 7-74-002/003, 1-01-002, 9-90-* |
| H4 Air in the reservoir | no | duckbill valve prevents air ingress through the outlet (mechanical) | compliance test, prime flow, instructions | 5-50-005 |
| H5 Wrong concentration | no | - | app and fill dialog | (process) |
| H6 Loss of communication | no | - | temp basal fallback after 30 min | 9-90-001, 7-71-* |
| H7 Unauthorized access | no | - | pairing window, AES-CCM, replay protection | 8-81-*, 8-83-* |
| H8 Insulin degradation (heat) | no (bench: no charger) | Rev B: charge path only when undocked | temperature channel, pause above limit | B-B0-* |
| H9 Pod not docked | **yes, for motion** | DOCKED gate (hall + inverter) blocks every forward step | alarm, report "not docked" | 2-21-*, 1-07-003/004/006 |
| H10 Backflow / siphon | partly (mechanical) | leadscrew self-locking, duckbill | uncommanded-motion detector (angle moves while driver off) | 6-60-008 |

Proposed new hazards (to be merged into `02-safety.md` after review; not done here):
**H11** undetected degradation of a protection element (stuck gate, dead watchdog, dead sensor) leaving the system silently unprotected, countered by the proofs of section 3;
**H12** diagnostic false positive that stops therapy needlessly, countered by thresholds with margin, escalation W to F only on repetition, and nominal-run false-positive tests (section 6);
**H13** the diagnostics itself is wrong or lost (log corruption, unknown code), countered by CRC, `7-7C-003 UNKNOWN_CODE_RAISED` (unknown is always treated as a fault) and app-side forward compatibility (`9-95-002`).

### 1.3 How a firmware bug is caught by hardware

| Firmware failure | Hardware mechanism | Bound | Evidence after the event |
|---|---|---|---|
| MCU hangs or crashes with the motor armed | TPL5010 gets no DONE, RSTn resets the MCU (all GPIO high-Z, MCU_EN pull-down) and clears the latch via SS14: VMOT off. The PWM peripheral is reset with the MCU | one TPL5010 interval, about 2 s, up to about 4 s depending on where in the period the hang occurs (**measure on the bench, B11**) | next boot: reset cause (`RESETREAS`, watchdog) in retained RAM, breadcrumb of the last task state, record `7-74-002` |
| Firmware forgets to disarm (motor stays supplied) | latch stays set, but the next tick's idle check (`VMOT_SENSE`, `LATCH_Q_MON` while no burst) sees supply with no burst: HAL withholds DONE, TPL5010 resets | one tick plus one TPL5010 interval | `1-06-001` or `7-76-001` with cause chain |
| Firmware drives STCK while undocked (forward) | DOCKED gate (Q6/Q7; Q10 only passes the reverse direction) keeps VMOT off | immediate, zero steps | `1-07-003` if the supply nevertheless comes up |
| Firmware arms although the dock hall says not docked (bug in dock handling) | same gate | immediate | `7-70-007 VETO_STEP_REQUEST_ILLEGAL` (the supervisor vetoed an illegal request, which is itself evidence of a bug) |
| Delivery engine requests more than the limits | supervisor (L3) vetoes; this is software, but in a separate task with separate bookkeeping, and it writes the evidence | immediate | `7-70-001..003` |
| Motor executes more steps than approved (step generator bug, PWM not stopped) | **hardware counter** TIMER1 counts STCK periods independently of the CPU; PPI stops the PWM after the last period | exact | `7-77-002 STEP_COUNT_EXTRA`, `7-70-004` |
| Firmware lies about the angle, or the sensor is dead | the angle channel is a **separate** sensor (TMAG5273) on another board; plausibility against steps and current | per revolution (3 %) and per window (10 %) | `6-60-*` |
| Corrupt flash (calibration, schedule, pod state) | none | at boot | `7-7D-*`, `7-75-*` |
| Brown-out / power glitch | MCU reset, all gates open | immediate | `1-01-002`, `7-74-002` |

### 1.4 Fail-safe defaults

* Every control input of the interlock defaults to "no motion": `MCU_EN` 100 k pull-down, `PGATE` pulled to VBUS (P-FET off), latch cleared at power-up and by `RSTn`, `DOCK_N` 100 k pull-up (a missing or unplugged FFC reads "not docked"), STSPIN220 `STBY` 100 k pull-down.
* Firmware defaults: boot in SUSPENDED; no calibration means no steps; no angle sensor means no steps; no session key means no commands; an unknown diagnostic code means fault (`7-7C-003`); an unknown FRU state is "UNKNOWN" (grey), never "OK".
* A proof that has not been performed is **UNKNOWN**, never OK. Health is OK only after a passing test within its freshness window (section 3.4).
* Assumptions not yet verified on hardware are not left as comments: they get a code that fires when the assumption is wrong: the `DIR_REV` polarity (`4-40-003`), the TMAG5273 register map (`2-20-002`, `2-20-005`), the gear ratio (`4-41-002`; the firmware preset is `drive-nfp-608-26-45-g16-20`, a pod fitted with another pair, e.g. 18:18, trips it).

### 1.5 Residual gap and recommended hardware additions (decision needed)

With the current interlock the **dose inside the watchdog window is not bounded by hardware**. A firmware fault that keeps `STCK` running while the supply is armed and the pod is docked can deliver for about 2 to 4 s. At 200 Hz (the configured step rate) that is 400 to 800 steps, i.e. 1.6 to 3.2 U on the 16:20 drive (3.95 mU per step); if a bug sets a higher rate, the motor pull-in rate (about 1000 pps, unverified) gives an upper bound of about 16 U. That is above the 10 U default bolus limit. Rev A can therefore **not** claim a hardware dose limit; the dose limit is L3 (software). Two additions are proposed for the electronics work package (WP-7), both optional, both needing the user's decision (open question 1):

* **HW-A, arm window and step budget** (about two small logic chips): `ARM_CLK` starts a non-retriggerable one-shot window (about 0.5 s) and resets a 5-bit counter on `STCK`; an AND gate stops `STCK` to the driver after 32 pulses (about 0.13 U on the 16:20 drive) until the next arm edge, and a dead time of at least 0.5 s separates arm edges. This bounds any "runaway inside one tick" fault to about 0.2 U per 0.5 s, i.e. at most about 1 U before the TPL5010 reset, **independent of firmware**.
* **HW-B, independent monitor** (Rev B): a tiny separate MCU or CPLD that counts `STCK` pulses on its own and enforces 15 U/h and 1.7 U/min by pulling `LATCH_CLR_N`. Only this gives a hardware hourly limit.

The readback of such blocks would get codes in reserved controller components `0x0F` (HW-A) and `0x10` (HW-B).

### 1.6 Every anomaly gets a code; codes are never swallowed

* No `unwrap`, no `_ => {}` and no "ignore and continue" on an error path in the safety-relevant crates without a diagnostic raise. A fallback (for example the RC oscillator when the crystal fails) is allowed only **together with a record** (`1-0B-001`).
* **Cause chain.** Each layer that receives a coded fault from below and acts on it raises its own record and sets `cause_rec` to the record id of the one below. Example: the I2C driver sees NACKs (`7-79-001`), the angle channel concludes the sensor is lost (`6-60-001`, cause `7-79-001`), the isolation logic finds the FFC loop open (`3-30-001`, root). The app headline is the **root** (the deepest cause); the chain is shown in the details.
* Rate limiting never drops information: the same code identity within 10 s is coalesced into the first record (`count` incremented, last context kept); escalations (W to F) and the first occurrence after a clear always create a new record.
* The only legal ways to "lose" a record are the ring overwriting an old one (a gap in the ids tells the app) and a failed flash write (then `7-7C-004` is raised and the RAM ring keeps working).

## 2. Code structure

### 2.1 The 32-bit code

```
 31    28 27        20 19            8 7       0
+--------+------------+---------------+---------+
| layer  | component  |  fault number | inst    |
| 4 bit  | 8 bit      |  12 bit       | 8 bit   |
+--------+------------+---------------+---------+
```

* **layer** (where the problem is): `1` CTRL (controller board hardware), `2` POD (pod sensor board hardware), `3` CABLE, `4` DRIVE (motor, gears, leadscrew, carriage), `5` FLUID (reservoir, plunger, end cap, needle, cannula), `6` SENSE (a sensing channel as a function, spanning boards), `7` FW (firmware module), `8` PROTO (BLE link, session, crypto, pairing), `9` APP (phone), `A` POWER (battery, charger, USB supply), `B` ENV (temperature, wear time), `0`/`C` to `F` reserved (`F` = test/injection only, never in production).
* **component** (8 bit): stable id from the list in 2.5, unique inside the layer.
* **fault number** (12 bit): unique inside the component, **never reused, never renumbered**. Retired codes stay in the catalogue as "retired".
* **inst** (8 bit): instance qualifier, 0 = not applicable. Examples: FFC pin number, GPIO readback id (RB1..), cal record kind (1 missing, 2 CRC, 3 range), reason (1 docked, 2 fault, 3 cancelled). It never changes the meaning, severity or FRU of the code; the **catalogue identity** is `code & 0xFFFFFF00`.
* Human notation: `L-CC-FFF` in hex, for example `1-06-001`; with an instance `1-06-001/03`. On a pod, a line like `E 1-06-001 VMOT_STUCK_ON` is what the bench console and the app "Copy diagnostic report" print.
* The code is **flat 32 bit on the wire** (`u32`, little endian, section 5.4). The 16+16 alternative (16 bit "where" + 16 bit "what") is the same bits cut in the middle; implementations may expose `where()` = bits 31..16 and `what()` = bits 15..0.

### 2.2 Severity (4 levels; carried in every record and defined per code in the catalogue)

| Sev | Name | Behaviour | Persistence | Cleared by |
|---|---|---|---|---|
| `I` 0 | INFO | log only, no alert, no state change | log | n/a |
| `W` 1 | WARNING | delivery continues; the user should act soon; alert in the app (time sensitive) | log + active set | condition gone (auto) or `ClearDiag` |
| `F` 2 | FAULT | **delivery stops** (supervisor latches, driver disabled, alarm); legacy fault bit set | log + active set; survives reboot only if the cause is re-detected by POST | `Acknowledge` / `ClearDiag` once the cause is gone (e.g. refill, re-dock, reseat cable) |
| `L` 3 | LATCHED | as F, **and** persistent across reboot and across `Acknowledge`; the pod refuses `Activate` and `Resume` | flash (latched set) | only by the code's **verification test** passing (section 3.5) after the stated action (replace FRU, update firmware, re-provision). Never by a plain acknowledge. |

Escalation: some codes start as W and escalate to F after repetition (rules in the catalogue); escalation creates a new record with `flags.escalated`.

### 2.3 Recommended action (u8, defined per code; the app picks the wording)

| Id | Name | Meaning shown to the user |
|---|---|---|
| 0 | NONE | no action |
| 1 | RETRY | repeat the operation |
| 2 | ACK | acknowledge, then resume |
| 3 | REFILL | refill (draw) the reservoir |
| 4 | REDOCK | take the pod off and dock it again |
| 5 | RECABLE | reseat or reconnect the FFC cable |
| 6 | REPHONE | bring the phone closer / restart Bluetooth / reopen the app |
| 7 | CHECK_POWER | check the USB supply / cable (bench) or charge (Rev B) |
| 8 | REPLACE | replace the FRU named in the record |
| 9 | RESEAT | reseat the FRU's connector, then re-run the self-test |
| 10 | SWAP_POD | switch to the other pod |
| 11 | PRIME | prime before resuming |
| 12 | REPROVISION | re-provision the pod (UICR, calibration) with the programmer |
| 13 | UPDATE_FW | update the pod firmware |
| 14 | REPORT_BUG | this should never happen: export the diagnostic report and contact the project |
| 15 | WAIT_COOL | let the pod cool down / warm up |
| 16 | REPAIR | re-pair the pod |
| 17 | UPDATE_APP | update the app |
| 18 | CHECK_CANNULA | check the cannula / infusion set |
| 19 | ISOLATE | guided isolation (the app walks the user through "unplug X and run the self-test") to decide between two suspects |

### 2.4 FRU list (field-replaceable units; stable ids)

| Id | Short | FRU (user wording) | Rev A bench content | Notes |
|---|---|---|---|---|
| 0 | NONE | - | - | |
| 1 | CTRL | controller board | bench controller board (U1 E73, U4 STSPIN220, interlock) | Rev B: part of the pod board |
| 2 | PODB | pod sensor board | pod board with TMAG5273 U4, dock hall U3, optional DRV5032 U1/U2, FFC connector J1 | |
| 3 | FFC | FFC cable | 0.5 mm FFC between J4 (controller) and pod J1 | |
| 4 | MOTOR | motor | NFP-608-26.45 with factory lead and plug (J5) | lead is part of the motor in Rev A |
| 5 | GEAR | gear pair | GHW 16:20 module 0.3 step-down pair | |
| 6 | SCREW | leadscrew and nut (carriage) | M1.6 x 0.35 leadscrew, nut, carriage arm | |
| 7 | RESV | reservoir | frozen CNC PP reservoir | |
| 8 | SEAL | plunger seal | silicone/FKM stadium lip seal | |
| 9 | CAP | end cap (septum and duckbill) | end cap with fill septum and duckbill valve | |
| 10 | NEEDLE | needle | 30G outlet needle | |
| 11 | BATT | battery | Rev B only | |
| 12 | APP | phone app | OpenPatchKit in Trio | not hardware |
| 13 | MAGD | dock magnet (cannula adapter) | magnet in the cannula adapter | |
| 14 | MAGS | spindle magnet | diametric magnet on the leadscrew end | |
| 15 | USB | USB supply / cable | bench 5 V | |
| 16 | CANN | cannula / infusion set | Accu-Chek Insight Flex | shared by pod A and pod B |
| 17 | FW | firmware | image on the pod | action is update or report, not replace |
| 18 | CHG | charger | Rev B (Qi) | |

Pod-level (not shared) FRUs are reported per pod; `CANN`, `APP` and `USB` are shared or external, and the app can attribute a fault seen on both pods to them (`9-91-004`). Rev B (integrated pod) collapses 1, 2, 3 and 4 partly into one "pod board"; ids stay, the Rev B mapping table is added then (ids 19 and up reserved).

### 2.5 Component list (8 bit, per layer; reference designators from `electronics/bench/{controller,pod}/parts.json`)

| Layer | Comp | Name | Reference designators / scope | FRU |
|---|---|---|---|---|
| 1 | 01 | MCU module | U1 E73-2G4M08S1CX (nRF52840): flash, RAM, reset | CTRL |
| 1 | 02 | 3V3 rail | U2 XC6206 | CTRL |
| 1 | 03 | motor driver | U4 STSPIN220, R20/R21 (sense), R23/R24 (VREF) | CTRL |
| 1 | 04 | watchdog | U5 TPL5010 | CTRL |
| 1 | 05 | interlock latch | U6 SN74AUP1G74, D2 SS14 | CTRL |
| 1 | 06 | VMOT switch | Q4 AO3401A (+ PGATE net) | CTRL |
| 1 | 07 | gate chain | Q5 (latch), Q8 (MCU_EN), Q6/Q7 (DOCKED), Q10/Q11 (DIR_REV), R96/R97/R99 | CTRL |
| 1 | 08 | motor current sense | U7 INA180A1, R31 and R39 (0.5 ohm), R32, C26 | CTRL |
| 1 | 09 | voltage sense | R33/R34 (VMOT), VBUS divider | CTRL |
| 1 | 0A | USB input | J1 USB-C, U3 USBLC6 | CTRL |
| 1 | 0B | 32.768 kHz clock | Y1, C6, C7 | CTRL |
| 1 | 0C | user interface | SW1 button, LD2/LD3 LEDs, Q9 buzzer | CTRL |
| 1 | 0D | FFC connector (controller side) | J4 FH12-10S-0.5SH | CTRL |
| 1 | 0E | motor connector | J5 PicoBlade 4P (J6 DNP alternative) | CTRL |
| 1 | 0F, 10 | reserved: HW-A step budget, HW-B monitor | not built | CTRL |
| 2 | 20 | angle sensor | pod U4 TMAG5273A1 | PODB |
| 2 | 21 | dock hall | pod U3 DRV5032FA | PODB |
| 2 | 22 | quadrature halls (optional) | pod U1, U2 DRV5032FA | PODB |
| 2 | 23 | pod FFC connector | pod J1 | PODB |
| 3 | 30 | FFC cable conductors | 10 pins between J4 and pod J1 (inst = pin number) | FFC |
| 3 | 31 | motor lead | factory lead + plug into J5 | MOTOR |
| 4 | 40 | motor | NFP-608-26.45 windings A/B, integral planetary gearhead | MOTOR |
| 4 | 41 | gear pair | 16 T to 20 T | GEAR |
| 4 | 42 | leadscrew, nut, carriage | M1.6 x 0.35 | SCREW |
| 5 | 50 | reservoir volume | fill model, end stops, draw | RESV |
| 5 | 51 | plunger | stadium plunger and lip seal | SEAL |
| 5 | 52 | end cap | septum, duckbill | CAP |
| 5 | 53 | outlet path | needle, cannula, infusion set | CANN / NEEDLE |
| 6 | 60 | angle channel | TMAG5273 + magnet + I2C + unwrap (function) | by cause |
| 6 | 62 | motor current channel | U7 chain (function) | CTRL |
| 7 | 70 | supervisor | `openpatch-core/src/safety.rs` | FW |
| 7 | 71 | delivery engine | `delivery.rs` | FW |
| 7 | 72 | reservoir model | `reservoir.rs` | FW |
| 7 | 73 | draw | `draw.rs` | FW |
| 7 | 74 | pump / pod orchestration | `pump.rs`, `pod.rs` | FW |
| 7 | 75 | storage | `openpatch-bench/src/storage.rs` | FW |
| 7 | 76 | interlock HAL | `hal/driver.rs` | FW |
| 7 | 77 | stepper HAL | `hal/stepper.rs` | FW |
| 7 | 78 | ADC HAL | `hal/adc.rs` | FW |
| 7 | 79 | I2C / TMAG HAL | `hal/tmag.rs`, `hal/angle.rs` | FW |
| 7 | 7A | boot / DFU | bootloader, `dfu.rs` | FW |
| 7 | 7B | timing | tick, executors, stack | FW |
| 7 | 7C | diagnostics itself | `diag` module, panic handler | FW |
| 7 | 7D | drive calibration | `drive_cal.rs` | FW |
| 8 | 80 | frame layer | length, CRC, version | APP/FW |
| 8 | 81 | session and crypto | AES-CCM, seq, key, RNG | FW |
| 8 | 82 | BLE link | trouble/SDC, MTU, notify queue | FW |
| 8 | 83 | pairing and bonding | | FW |
| 9 | 90 | transport | `V1Transport` | APP |
| 9 | 91 | two-pod coordination | `PairSwapCoordinator`, `PodPair` | APP |
| 9 | 92 | drive calibration check | `DriveCalibration` | APP |
| 9 | 93 | pump manager state, dose ledger | `OpenPatchPumpManagerState` | APP |
| 9 | 94 | alert delivery | notifications permission | APP |
| 9 | 95 | version / catalogue | compatibility | APP |
| A | A0 | battery | Rev B cell, PCM | BATT |
| A | A1 | charger | Rev B Qi + charge IC | CHG |
| A | A2 | USB supply | VBUS (bench) | USB |
| B | B0 | temperature | nRF die temperature (proxy) | CTRL |
| B | B1 | wear time | 44 h / 52 h | none |

The electronics agent's FMEA (see 3.6) may allocate new fault numbers inside components 01 to 0E and 20 to 23 by appending rows to the catalogue (rule 2.8); it must not reuse numbers.

### 2.6 The diagnostic record (32 bytes, used in the flash log, the protocol and the app)

Little endian. One record per (code identity, event); `count` coalesces repeats.

| Off | Size | Field | Meaning |
|---|---|---|---|
| 0 | 4 | `rec_id` | persistent, strictly increasing, starts at 1 (same ceiling technique as event ids, `storage.rs`) |
| 4 | 4 | `code` | 32-bit code (2.1) |
| 8 | 1 | `severity` | 0..3 (2.2); can be higher than the catalogue default after escalation |
| 9 | 1 | `action` | 2.3 |
| 10 | 1 | `fru` | primary suspect (2.4); the raiser may override the catalogue default when isolation evidence exists |
| 11 | 1 | `fru2` | secondary suspect, 0 = none |
| 12 | 4 | `t_s` | seconds since boot (the phone maps via BOOT events, as for history) |
| 16 | 4 | `ctx_a` | measured value (i32; unit per code, given in the catalogue "Detection" column) |
| 20 | 4 | `ctx_b` | threshold or expected value (i32) |
| 24 | 4 | `ctx_c` | cumulative step count at the event (u32 pulses), or an angle count; "0" if not meaningful |
| 28 | 1 | `count` | occurrences coalesced into this record (saturates at 255) |
| 29 | 1 | `flags` | bit0 latched, bit1 active (condition still present), bit2 escalated, bit3 first since boot, bit4 raised during POST, bit5 cleared (clear record), bit6 root cause (no `cause_rec`), bit7 reserved |
| 30 | 2 | `cause_rec` | low 16 bits of the `rec_id` of the record that caused this one; 0 = this is a root |

Depth of a cause chain is bounded to 4; the app follows `cause_rec` through records it has (a missing cause is displayed as "cause not in log").

### 2.7 Backward compatibility with the 8 legacy fault bits

The `Faults(u16)` bitfield (`openpatch-core/src/faults.rs`, protocol 4.1 `FAULT_MASK` tag 0x09) stays on the wire and in the API as a **derived projection** of the latched/active set: `FAULT_MASK = OR of legacy_bit(code)` over all active records with severity F or L. Rule: **every F or L code projects to at least one legacy bit** (default bit 5 INTERNAL), so an old app never sees a stopped pod without a fault. I and W never set a bit.

| Legacy bit | Name | New codes that project to it |
|---|---|---|
| 0 | OCCLUSION | `5-53-001`, `5-53-002`, `4-42-001` (carriage jam, the old "spindle stands still despite steps"), `4-40-001` (motor stall) |
| 1 | ENCODER_DEVIATION | `6-60-006`, `6-60-007`, `4-41-002`, `4-41-003`, `4-42-003` |
| 2 | RESERVOIR_EMPTY | `5-50-001`, `7-72-001`, `7-72-002` |
| 3 | BATTERY_CRITICAL | `A-A0-002` (inst 1 = bench VBUS source) |
| 4 | LIMIT_EXCEEDED | `7-70-001`, `7-70-002`, `7-70-003` |
| 5 | INTERNAL | **default** for every other F/L code (all HW, cable, sensor, FW, storage faults) |
| 6 | NO_CALIBRATION | `7-7D-001`, `7-7D-002`, `7-7D-003` |
| 7 | WEAR_EXPIRED | `B-B1-002` |

The existing Swift `FaultCode` enum (1..10, includes `motorStall` and `watchdog` that have no v1 bit) stays as the legacy summary computed by `V1Transport.faultCode(mask:)`; the new `DiagRecord` is the primary source in the kit once the pod reports `DIAG_SUMMARY` (5.4).
The event type 14 `FAULT` (a = new bits) keeps being written; a new event type 31 `DIAG` (a = code, b = `ctx_a`) is added so a v1-only history reader still sees that something happened.

### 2.8 Allocation and stability rules

1. The catalogue (section 4) is the single source of truth. WP-0 generates `catalogue.rs`, `DiagCatalogue.swift` and a CSV from it; no code constant may exist outside the catalogue.
2. New code = new row with the next free fault number of its component; never reuse, never renumber, never change layer/component of an existing code. Severity, FRU, action and text of an existing code may be corrected (the app reads them from its own copy of the catalogue and falls back to the values in the record).
3. A catalogue change needs: row, test tag (or explicit waiver), hazard link, user text. CI enforces it (WP-0).
4. The pod and the app each embed the catalogue; the pod reports `DIAG_SCHEMA` (catalogue version) in `DIAG_SUMMARY`; an app with an older catalogue still works because every record carries severity, action and FRU (`9-95-002`).

## 3. Self-tests: proving the hardware layer works

### 3.1 Readbacks the firmware needs (request to the electronics agent; names `RB1..`)

The existing signals are marked "have". All others are requested; how they reach the MCU (spare pin, one SAADC input with a resistor ladder that encodes several digital nodes, or an analog mux) is the electronics agent's decision. `pin-assignment.md` in the repository still documents the earlier SMA concept and a different pin map than `firmware-rs/docs/boards.md`; both must be reconciled by the electronics work package (this is open point 1 in `docs/stubs.md`).

| Id | Signal | Why | State |
|---|---|---|---|
| RB1 | `PGATE` level (the P-FET gate) | shows whether the gate chain conducts, independent of the VMOT result | requested (TP5 exists) |
| RB2 | `PG_MID1` (between Q5 and Q8) | with RB3, identifies **which** gate in the chain is open | requested |
| RB3 | `PG_MID2` (between Q8 and Q6/Q10) | same | requested |
| RB4 | `DOCKED_H` (after the Q7 inverter) | separates "hall says undocked" from "inverter/gate fault" | requested (TP8) |
| RB5 | `DIR_REV` | proves the reverse gate input sees the intended polarity | requested (TP41) |
| RB6 | `LATCH_Q_MON` | latch output | have |
| RB7 | `VMOT_SENSE` | motor supply present/absent | have |
| RB8 | `I_SENSE` (I_MOT) | motor current | have |
| RB9 | `MCU_EN`, `ARM_CLK`, `LATCH_CLR_N`, `STBY`, `WDT_DONE` own-pin readback (input buffer connected on an output pin) | detects an output shorted or forced by external fault | firmware only (nRF `PIN_CNF.INPUT=Connect`) |
| RB10 | `EN/FAULT` | driver fault | have |
| RB11 | `WDT_WAKE` | watchdog heartbeat | have |
| RB12 | `FFC_DET` (loop: two FFC pins bridged on the pod board, pulled up on the controller) | cable present independent of the TMAG | requested (one pin, or fold into the RB ladder) |
| RB13 | `VDD` (internal SAADC channel) | 3V3 rail | firmware only |

### 3.2 POST-S: passive power-on self test (every boot, at most 1.5 s, the motor is never driven)

| Step | Checks | Codes |
|---|---|---|
| S01 | image CRC / signature trailer | 1-01-001 |
| S02 | calibration record present, CRC, range, equals the build preset | 7-7D-001, 7-7D-002, 7-7D-003 |
| S03 | `UICR.PSELRESET` = P0.18 (otherwise the TPL5010 can not reset the MCU) | 1-01-003 |
| S04 | `VDD` 3.0 to 3.6 V; reset cause evaluation (brown-out, watchdog, soft) | 1-02-001, 1-02-002, 1-01-002, 7-74-002, 7-74-003 |
| S05 | after reset: `LATCH_Q_MON` low, `MCU_EN`/`ARM_CLK`/`LATCH_CLR_N`/`STBY` read back as driven, `EN/FAULT` high | 1-05-003, 1-03-002, 1-07-007 |
| S06 | all gates open: `VMOT_SENSE` below 0.5 V; `I_SENSE` offset within +/- 8 mA equivalent, not at full scale; `VBUS_SENSE` plausible | 1-06-001, 1-08-001, 1-08-002, 1-09-001 |
| S07 | clocks: LFXO running, RTC against HF timer ratio within 0.5 % over 1 s | 1-0B-001, 1-0B-002 |
| S08 | FFC present (RB12), I2C bus idle (SDA/SCL high), TMAG5273 ACK at 0x35, device ID, device status | 3-30-001, 3-30-003, 2-20-001, 2-20-002, 2-20-005 |
| S09 | magnet field magnitude within 50 % to 160 % of the stored nominal, angle noise at rest | 6-60-002, 6-60-003, 6-60-004 |
| S10 | dock input vs FFC presence plausible (docked without FFC is impossible); no chatter | 3-30-004, 2-21-002, 2-21-003 |
| S11 | temperature plausible | B-B0-004 |
| S12 | button not stuck (a stuck button is only reported in the `7-74-006` failed-steps mask, no code of its own) | (mask) |
| S13 | fault log, latched set, pod record, seq ceiling readable (CRC) | 7-75-002, 7-75-003, 7-75-004 |
| S14 | latched set from the last run: any L code whose test is not re-run keeps the pod latched | (latched codes) |

POST-S ends with the record `7-74-006 POST_RESULT` (INFO, `ctx_a` = bitmask of steps passed, `ctx_b` = steps failed). Delivery is impossible before POST-S completed; a failed step with severity F/L keeps the pod SUSPENDED and the corresponding FRU red.

### 3.3 POST-A: active self test (pod SUSPENDED only; on `Activate`, on app request, after an FRU replacement, at provisioning; at most 5 s)

Motion steps are limited to a net-zero excursion of 16 steps reverse then 16 steps forward (about 0.06 U on the 16:20 drive); forward steps run only when docked (interlock), so on an undocked pod the forward-dependent proofs stay UNKNOWN until the first docked, suspended window. Bench only; with water.

| Step | Proof | Method | Codes |
|---|---|---|---|
| A01 | each gate can **cut** the supply, **one at a time** | arm (docked, or undocked with reverse DIR), VMOT must come up; then cut with `MCU_EN` only: VMOT must collapse (< 0.5 V within `VMOT_FALL_TIMEOUT`); re-arm, cut with `LATCH_CLR_N` only: must collapse; readbacks RB1..RB3 show which gate stuck | 1-06-002, 1-07-001, 1-07-002, 1-07-005 |
| A02 | DOCKED and DIR_REV gates **block**, undocked only | undocked, DIR forward, latch armed, `MCU_EN` high: VMOT must stay below 0.5 V; then DIR reverse: VMOT must come up (draw path works) | 1-07-003, 1-07-004, 1-07-006 |
| A03 | current baseline | 16 reverse steps: peak current stored as baseline on first run, compared later (+/- 25 %); open phase / lead / short signatures | 3-31-001..004, 4-40-002, 6-62-001, 1-08-003 |
| A04 | direction polarity | reverse pulses must **decrease** the angle (retract), forward must increase | 4-40-003 |
| A05 | step ratio | counts per pulse over 32 steps within +/- 5 % of the drive calibration; classification: power-of-two ratio means MODE pins, 0.8 or 1.25 means wrong gear pair (e.g. 18:18 fitted against the 16:20 firmware) | 4-41-002 |
| A06 | backlash | dead travel at the turnaround against baseline | 4-41-001 |
| A07 | compliance (closed system) | reverse 0.2 U with septum and duckbill closed: vacuum signature (current rise, early stall) expected for a liquid-filled closed reservoir | 5-50-005 |
| A08 | watchdog is effective (**service/bench command only**, resets the MCU) | withhold DONE once; the MCU must be reset within 3.5 s; the record is written before and verified after the reset | 1-04-001, 1-04-002 |
| A09 | uncommanded motion baseline | 10 s at rest with the driver off: angle must not move more than noise | 6-60-008 |
| A10 | dock lift proof (app-guided) | the app asks "take the pod off the dock"; the input must change within 10 s, then "dock it again" | 2-21-001, 2-21-002 |
| A11 | alarm path (Rev A: user confirms the beep in the app) | buzzer pattern, user answers | 1-0C-002 |

### 3.4 Continuous proofs during operation

* **Rotating single-gate disarm.** Today every burst disarms with `MCU_EN` low and `KILL_N` low at the same time, so one stuck gate is masked by the other. Change: in round-robin the HAL disarms with **only** `MCU_EN` (burst k), **only** `LATCH_CLR_N` (burst k+1), **both** (burst k+2). VMOT must collapse in each case; if it does not within the timeout, the second cut follows immediately and the specific gate code (`1-07-001` or `1-07-002`) is latched. Costs nothing but a few ms of VMOT on-time and proves every cut path every third burst.
* **Idle check every tick** (exists: `LATCH_Q_MON` and `VMOT_SENSE` while the driver is off) gets codes (`1-05-003`, `1-06-001`).
* **Angle and current plausibility every burst** (`6-60-*`, `4-4x-*`, `5-53-*`).
* **Dock gate** is proven whenever the pod is undocked (A02 runs in the background at the next idle tick after an `UNDOCKED` event).
* **FRU health freshness:** green requires a passing proof younger than 24 h for HW proofs (A01/A02: 24 h or the last undock) and the continuous checks active; otherwise the FRU is grey (UNKNOWN).

### 3.5 Verification tests that clear a latched code

| Latched family | Cleared by | Notes |
|---|---|---|
| 1-04-*, 1-05-*, 1-06-001, 1-07-* | A01 + A02 pass, twice in a row | after the controller board is replaced |
| 1-02-002, 1-03-*, 1-08-*, 1-09-* | S04..S06 pass | |
| 2-21-001 | A10 pass | |
| 4-40-003, 4-41-002 | A04 / A05 pass | gear or wiring corrected |
| 6-60-008 | A09 pass **and** the cause record is clear | |
| 7-70-004, 7-70-006, 7-71-001, 7-74-003, 7-7B-004 | firmware update to a newer build (version greater than the build that raised it) plus POST-S + A01 | REPORT_BUG codes also require the diagnostic report to have been exported once (app flag) |
| 7-7D-002, 7-7D-003 | `REPROVISION` plus S02 | |
| A-A0-003, A-A2-002 | A-battery/supply replaced plus S04 | |

### 3.6 FMEA slot (interface for the electronics agent)

The electronics agent adds `electronics/bench/INTERLOCK.md` or `DIAGNOSTICS.md` with an FMEA table. Interface so it slots in without rework:

* one row per failure mode, id `FM-<ref>-<n>` (for example `FM-Q4-1`), with the reference designator from `parts.json`;
* columns: `FM id | ref | failure mode | effect on VMOT/motion | single-fault safe? | readback (RB id) | detection step (S/A id) | diagnostic code (this catalogue) | FRU`;
* every failure mode whose effect is "protection lost" must have a code with severity L in this catalogue; a mode with no code is a catalogue request (new row, next free fault number in the component, rule 2.8);
* "readback" must be one of RB1..RB13 or a new RB id appended to 3.1.

Seed FMEA (to be replaced and extended by the electronics agent; from the interlock described in `electronics/bench/pin-assignment.md` and `build_controller.py`):

| FM id | Ref | Failure mode | Effect | Safe (single fault)? | Readback | Step | Code | FRU |
|---|---|---|---|---|---|---|---|---|
| FM-Q4-1 | Q4 | drain-source short | VMOT permanently present | yes if driver STBY low; protection reduced | RB7 | S06, idle tick | 1-06-001 | CTRL |
| FM-Q4-2 | Q4 | open | no motor supply | yes (fail-safe) | RB7, RB1 | A01 | 1-06-002 | CTRL |
| FM-Q5-1 | Q5 | stuck conducting | latch gate ineffective | yes (two gates remain) | RB2 | A01 | 1-07-002 | CTRL |
| FM-Q8-1 | Q8 | stuck conducting | MCU_EN gate ineffective | yes | RB2, RB3 | A01 | 1-07-001 | CTRL |
| FM-Q6-1 | Q6, Q7 | stuck conducting | DOCKED gate ineffective | yes | RB4, RB3 | A02 | 1-07-003 | CTRL |
| FM-Q10-1 | Q10, Q11 | stuck conducting | DIR_REV gate always open (undocked forward not blocked) | yes | RB5, RB3 | A02 | 1-07-004 | CTRL |
| FM-Q5-2 | Q5, Q8, Q6 | any open | motor never runs | yes (fail-safe) | RB1..RB3 | A01 | 1-07-005, 1-07-006 | CTRL |
| FM-U6-1 | U6 | output stuck high | latch ineffective | yes | RB6 | S05, A01 | 1-05-003, 1-05-001 | CTRL |
| FM-U6-2 | U6 | output stuck low | no motion | yes | RB6 | A01 | 1-05-002 | CTRL |
| FM-U5-1 | U5 | no WAKE | watchdog dead | yes if gates intact; protection reduced | RB11 | continuous | 1-04-001 | CTRL |
| FM-U5-2 | U5, D2 | RSTn not reaching MCU or latch | watchdog ineffective | yes; protection reduced | RB11 | A08 | 1-04-002 | CTRL |
| FM-R-1 | R (MCU_EN pull-down) | open | MCU_EN floating after reset | partly | RB9 | S05 | 1-07-007 | CTRL |
| FM-J4-1 | J4 / pod J1 | contact open | no angle, dock reads undocked | yes (fail-safe) | RB12 | S08 | 3-30-001, 3-30-002 | FFC |
| FM-U7-1 | U7, R31/R39 | open / offset | current channel dead or biased | yes (encoder remains) | RB8 | S06, A03 | 1-08-001..003 | CTRL |
| FM-U4-1 | U4 | output stage failure | no motion or fault pin | yes | RB10 | S05 | 1-03-002 | CTRL |

## 4. Catalogue

Reading guide. Columns: **Code** (`L-CC-FFF`, instance omitted); **Name**; **Detection and threshold** (mechanism, value, unit of `ctx_a`); **By** (layer that detects: `FW-HAL`, `FW-core`, `FW-boot`, `PROTO`, `APP`; no code is detected by "hardware" alone, hardware protections act without a code and are *proven* by these checks); **Sev** (`I` `W` `F` `L`, section 2.2); **FRU: action** (FRU short names from 2.4, secondary suspect in parentheses; actions from 2.3); **Haz** (hazards of `02-safety.md` plus proposed H11 to H13); **Test** (`C` core host fault-injection test, `H` HAL logic host test with simulated pins, `P` protocol codec test, `S` Swift test, `B nn` bench procedure of 6.3, `D` differential parity test); **Trio text** (English UI string; the app appends the FRU instruction and the code).
Fault numbers are not contiguous on purpose: gaps are reserved or retired numbers (rule 2.8). Thresholds marked *cal* are placeholders to be calibrated on the water bench (`firmware-rs/docs/bench-testing.md`); they live in one `diag_limits` module, not scattered. Instances (`inst`) and units of the context fields are given in the detection column where they matter. The table format is machine readable on purpose (WP-0 parses it).

### 4.1 Layer 1: controller board hardware (31 codes)

| Code | Name | Detection and threshold | By | Sev | FRU: action | Haz | Test | Trio text |
|---|---|---|---|---|---|---|---|---|
| `1-01-001` | FLASH_IMAGE_BAD | POST S01: app image CRC32 or MCUboot signature trailer mismatch (bootloader writes the record to retained RAM) | FW-boot | F | FW: UPDATE_FW | H1 | H, B21 | Firmware image damaged. |
| `1-01-002` | BROWNOUT_RESET | reset cause brown-out (`RESETREAS`, `POFCON` 2.7 V); ctx_a = VBUS mV after boot | FW-core | W | USB (CTRL): CHECK_POWER | H3 | C, B18 | Pod restarted after a power dip. |
| `1-01-003` | UICR_RESET_PIN_WRONG | S03: `UICR.PSELRESET` is not P0.18 after `uicr_setup` retry, so the TPL5010 can not reset the MCU | FW-HAL | F | FW (CTRL): REPROVISION | H1 | H, B12 | Reset pin not set, watchdog can not reset the pod. |
| `1-01-004` | NVM_VERIFY_FAIL | flash write read-back mismatch or erase error in the persistence task; ctx_a = page | FW-HAL | F | CTRL: REPLACE | H3 | H, B21 | Pod memory write failed. |
| `1-01-005` | NVM_WEAR_HIGH | erase counter of a settings or log page above 8000 (of about 10000); ctx_a = count | FW-HAL | W | CTRL: REPLACE | H11 | C | Pod memory wearing out. |
| `1-02-001` | RAIL_3V3_LOW | SAADC internal VDD below 3.0 V (S04, every minute); ctx_a = mV | FW-HAL | F | USB (CTRL): CHECK_POWER | H3 | H, B18 | Controller supply too low. |
| `1-02-002` | RAIL_3V3_HIGH | VDD above 3.6 V; ctx_a = mV | FW-HAL | L | CTRL: REPLACE | H11 | H, B18 | Controller supply too high. |
| `1-03-001` | DRIVER_FAULT_IN_BURST | `EN/FAULT` (U4) low during a burst (over-current, thermal, UVLO); ctx_a = peak mA, ctx_c = step in burst | FW-HAL | F | MOTOR (CTRL): ISOLATE | H1, H2 | H, B06 | Motor driver fault. |
| `1-03-002` | DRIVER_FAULT_AT_IDLE | `EN/FAULT` low while `STBY` low and all gates open (net has a 10 k pull-up and must be high) | FW-HAL | F | CTRL: REPLACE | H11 | H, B05 | Motor driver stuck in fault. |
| `1-04-001` | WDT_TIMING_FAULT | `WDT_WAKE` interval measured with the RTC outside 1.4 to 2.6 s over 3 intervals, or no WAKE within 3 s (inst 1 no WAKE, 2 out of range); ctx_a = interval ms | FW-HAL | L | CTRL: REPLACE | H1, H11 | H, B12 | Watchdog timer not working. |
| `1-04-002` | WDT_RESET_INEFFECTIVE | A08 service test: DONE withheld, MCU not reset within 3.5 s (RSTn path broken) | FW-core | L | CTRL: REPLACE | H1, H11 | B12 | Watchdog can not reset the pod. |
| `1-05-001` | LATCH_CANNOT_CLEAR | `LATCH_Q_MON` still high 1 ms after `LATCH_CLR_N` low | FW-HAL | L | CTRL: REPLACE | H1, H11 | H, B10 | Motor enable latch stuck on. |
| `1-05-002` | LATCH_CANNOT_SET | `LATCH_Q_MON` low after an `ARM_CLK` edge with `MCU_EN` high (fail-safe direction) | FW-HAL | F | CTRL: REPLACE | H11 | H, B10 | Motor enable latch will not set. |
| `1-05-003` | LATCH_SET_WITHOUT_ARM | `LATCH_Q_MON` high after reset (S05) or at an idle tick without an `ARM_CLK` edge | FW-HAL | L | CTRL: REPLACE | H1, H11 | H, B10 | Motor enable latch set by itself. |
| `1-06-001` | VMOT_STUCK_ON | `VMOT_SENSE` above 1.0 V for more than 50 ms while all gates are commanded open (S06 and every idle tick), or not below 0.5 V within `VMOT_FALL_TIMEOUT` after a disarm; ctx_a = mV | FW-HAL | L | CTRL: REPLACE | H1 | H, B07 | Motor supply stuck on. |
| `1-06-002` | VMOT_NOT_PRESENT | armed, VBUS ok, `VMOT_SENSE` below 3.0 V after `VMOT_SETTLE_MS`; ctx_a = mV | FW-HAL | F | CTRL: REPLACE | H2 | H, B09 | Motor supply does not come up. |
| `1-06-003` | VMOT_DROOP | `VMOT_SENSE` below 85 % of `VBUS_SENSE` during a burst; ctx_a = permille | FW-HAL | W | USB (CTRL): CHECK_POWER | H2 | H, B18 | Motor supply sags under load. |
| `1-07-001` | GATE_MCUEN_STUCK_PASS | A01 and rotating disarm: cut with `MCU_EN` only, VMOT stays above 0.5 V; RB2/RB3 identify the gate | FW-HAL | L | CTRL: REPLACE | H1, H11 | H, B08 | Motor enable gate stuck. |
| `1-07-002` | GATE_LATCH_STUCK_PASS | A01 and rotating disarm: cut with `LATCH_CLR_N` only, VMOT stays above 0.5 V | FW-HAL | L | CTRL: REPLACE | H1, H11 | H, B08, B10 | Latch gate stuck. |
| `1-07-003` | GATE_DOCK_STUCK_PASS | A02: undocked, DIR forward, armed, `MCU_EN` high: VMOT comes up (above 3.0 V); cut immediately | FW-HAL | L | CTRL: REPLACE | H1, H9, H11 | H, B08 | Dock gate stuck. |
| `1-07-004` | GATE_DIRREV_STUCK_PASS | A02 with RB5 showing forward: gate passes anyway (reverse gate Q10/Q11 stuck) | FW-HAL | L | CTRL: REPLACE | H1, H9, H11 | H, B08 | Direction gate stuck. |
| `1-07-005` | GATE_MCUEN_STUCK_BLOCK | `MCU_EN` high, latch armed, docked: RB2 stays high / VMOT absent while RB3 shows the other gates open | FW-HAL | F | CTRL: REPLACE | H2 | H, B09 | Motor enable gate will not open. |
| `1-07-006` | GATE_DOCK_STUCK_BLOCK | hall says docked but `DOCKED_H` (RB4) low, or VMOT absent with RB4 low | FW-HAL | F | CTRL (PODB): ISOLATE | H9 | H, B09, B14 | Dock gate never opens. |
| `1-07-007` | GATE_INPUT_READBACK_MISMATCH | own-pin readback of `MCU_EN`, `ARM_CLK`, `LATCH_CLR_N`, `STBY` or `WDT_DONE` differs from the driven level for 2 samples (inst = pin) | FW-HAL | L | CTRL: REPLACE | H1, H11 | H, B08 | A control signal is shorted. |
| `1-07-008` | GATE_REVERSE_DOCKED_STUCK_PASS | A13 (docked, `DOCK_TEST` off): reverse level, armed, `MCU_EN` high: VMOT comes up, or `PGATE_MON` low with `DOCKED_H` and `DIR_REV` both high (the XOR of the dock / DIR pair is lost, H14); cut immediately | FW-HAL | L | CTRL: REPLACE | H1, H14 | H, B08 | Reverse while docked is not blocked. |
| `1-08-001` | ISENSE_IDLE_OFFSET | `I_SENSE` with driver in STBY and gates open: more than 80 mV (about 8 mA at 10 V/A) in magnitude; ctx_a = mV | FW-HAL | F | CTRL: REPLACE | H2 | H, B22 | Motor current sensor offset. |
| `1-08-002` | ISENSE_SATURATED | `I_SENSE` at full scale (3.5 V or more) at idle, or during a burst with a free motor | FW-HAL | F | CTRL: REPLACE | H2 | H, B22 | Motor current sensor stuck high. |
| `1-08-003` | ISENSE_DEAD | 10 bursts in a row with moving angle and `I_SENSE` within 2 counts of the idle value | FW-core | W | CTRL: REPLACE | H2, H11 | C, B22 | Motor current sensor not responding. |
| `1-09-001` | VOLTAGE_SENSE_IMPLAUSIBLE | `VMOT/VBUS` outside 0.80 to 1.05 with Q4 on (inst 1), or `VBUS_SENSE` below 3.0 V while the MCU runs from USB (inst 2) | FW-HAL | F | CTRL: REPLACE | H11 | H, B22 | Supply measurement error. |
| `1-0B-001` | LFXO_NOT_RUNNING | `LFCLKSTAT` source is not the crystal after 1 s; firmware falls back to the RC oscillator **and** raises this | FW-HAL | W | CTRL: REPLACE | H3 | H | Clock crystal not running (backup clock in use). |
| `1-0B-002` | TIMEBASE_MISMATCH | RTC (LF) against HF timer over 1 s differ by more than 0.5 %; ctx_a = ppm | FW-HAL | F | CTRL: REPLACE | H1 | C | Timing error. |
| `1-0C-002` | ALARM_UNCONFIRMED | A11: user answers in the app that no beep was heard (Rev A has no buzzer feedback) | APP | W | CTRL: REPLACE | H3 | S | Alarm sound not heard. |

### 4.2 Layer 2: pod sensor board (9 codes) and layer 3: cable (8 codes)

| Code | Name | Detection and threshold | By | Sev | FRU: action | Haz | Test | Trio text |
|---|---|---|---|---|---|---|---|---|
| `2-20-001` | TMAG_NO_ACK | I2C NACK at 0x35 on 3 retries (S08). **Isolation:** if RB12 (FFC loop) is open the root is `3-30-001`, this record becomes its consequence | FW-HAL | F | PODB (FFC): ISOLATE | H1, H2 | H, B01 | Position sensor does not answer. |
| `2-20-002` | TMAG_ID_MISMATCH | device or manufacturer id differs from expected (register map unverified: `TODO(verify-on-hardware)`); ctx_a = id read | FW-HAL | F | PODB: REPLACE | H1, H11 | H | Position sensor is not the expected part. |
| `2-20-003` | TMAG_FROZEN | identical raw angle for 50 samples while at least 20 steps were executed | FW-core | F | PODB: REPLACE | H1, H2 | C | Position sensor frozen. |
| `2-20-004` | TMAG_CRC_ERRORS | I2C CRC mode: more than 3 of 100 samples bad (W); more than 10 escalates to F | FW-HAL | W | PODB (FFC): ISOLATE | H2 | H, B03 | Position sensor data errors. |
| `2-20-005` | TMAG_DEVICE_STATUS | TMAG device status bits set (supply UV, oscillator error; bit names to be verified); ctx_a = status | FW-HAL | F | PODB: REPLACE | H2 | H | Position sensor reports an internal error. |
| `2-21-001` | DOCK_STUCK_DOCKED | A10: input does not leave "docked" within 10 s after the lift request, or "docked" while a charger is present (Rev B) | APP | L | PODB (MAGD): REPLACE | H9, H11 | S, B14 | Dock sensor always reads docked. |
| `2-21-002` | DOCK_STUCK_UNDOCKED | user confirmed docking, input stays undocked for 3 attempts while the FFC is fine | FW-core | W | MAGD (PODB): REDOCK | H9 | C, B14 | Dock not detected. |
| `2-21-003` | DOCK_CHATTER | more than 6 transitions in 10 s (DRV5032FA threshold switches about 4 mm early, see STATUS) | FW-core | W | MAGD (PODB): REDOCK | H9 | C, B14 | Dock contact unstable. |
| `2-22-001` | QDEC_CROSSCHECK_FAIL | only if the optional DRV5032 pair is fitted: edges per turn differ more than 25 % from the angle channel | FW-core | W | PODB: REPLACE | H2 | C | Secondary position sensor disagrees. |
| `3-30-001` | FFC_ABSENT | RB12 loop open **and** TMAG no ACK **and** `DOCK_N` high | FW-HAL | F | FFC: RECABLE | H1, H2 | H, B01, B02 | Cable to the pod disconnected. |
| `3-30-002` | FFC_INTERMITTENT | 3 or more loss/recover events of RB12 or the TMAG ACK in 10 min (W); a loss during a burst escalates to F | FW-core | W | FFC (PODB): RESEAT | H2 | C, B03 | Cable connection unreliable. |
| `3-30-003` | I2C_BUS_STUCK | SDA or SCL low for more than 1 ms and 9-clock recovery fails; ctx_a = line mask | FW-HAL | F | FFC (PODB): ISOLATE | H2 | H, B03 | Sensor bus blocked. |
| `3-30-004` | FFC_DOCK_LINE_FAULT | `DOCK_N` reads docked while RB12 is open, or while the TMAG does not ACK for 5 s (impossible combination) | FW-core | F | FFC (PODB): REPLACE | H9 | C, B01 | Dock signal fault on the cable. |
| `3-31-001` | MOTOR_LEAD_OPEN | burst with VMOT ok and no driver fault: `I_SENSE` peak below 15 % of the baseline, no angle motion; ctx_a = mA | FW-core | F | MOTOR: RESEAT | H2 | C, B04 | Motor not connected. |
| `3-31-002` | MOTOR_PHASE_OPEN | peak current 35 to 65 % of baseline and angle per pulse irregular (one coil open) | FW-core | F | MOTOR: REPLACE | H2 | C, B05 | Motor winding broken. |
| `3-31-003` | MOTOR_PHASE_SHORT | `EN/FAULT` within 3 steps and peak at or above 1.5 x the chopper limit; ISOLATE: unplug the motor, re-run A03, fault persists means controller | FW-core | F | MOTOR (CTRL): ISOLATE | H1, H2 | C, B06 | Motor winding short. |
| `3-31-004` | MOTOR_CONTACT_INTERMITTENT | 2 or more of 20 bursts with peak below 15 % of baseline while the others are normal | FW-core | W | MOTOR: RESEAT | H2 | C, B04 | Motor connection unreliable. |

### 4.3 Layer 4: drive mechanics (9 codes)

| Code | Name | Detection and threshold | By | Sev | FRU: action | Haz | Test | Trio text |
|---|---|---|---|---|---|---|---|---|
| `4-40-001` | MOTOR_STALL_FREE | stall where no downstream pressure can exist (draw reverse before the expected end stop, or forward in the first part of a stroke after a draw): angle below 50 % of commanded and current above the occlusion threshold | FW-core | F | MOTOR (GEAR): REPLACE | H2 | C, B15 | Drive stalled. |
| `4-40-002` | MOTOR_CURRENT_BASELINE_DRIFT | free-run peak current outside +/- 25 % of the stored baseline (*cal*); ctx_a = mA, ctx_b = baseline | FW-core | W | MOTOR: REPLACE | H2, H11 | C | Motor load is changing. |
| `4-40-003` | DIR_INVERTED | A04: reverse pulses **increase** the angle or forward pulses decrease it; this also proves a wrong `DIR_REV` polarity option (R96/R97), which would let the undocked pod run forward | FW-core | L | MOTOR (CTRL): ISOLATE | H1, H9 | C, B15 | Motor turns the wrong way. |
| `4-41-001` | GEAR_BACKLASH_EXCESS | dead travel at a direction change above 2 x the provisioned baseline; ctx_a = counts | FW-core | W | GEAR: REPLACE | H2, H11 | C | Gear play is increasing. |
| `4-41-002` | GEAR_RATIO_MISMATCH | A05: counts per pulse differ by more than 5 % from the drive calibration; ctx_c classifies: 1 power of two (MODE pins), 2 factor 0.8 or 1.25 (wrong gear pair, e.g. 18:18 fitted for 15:12), 3 other. A 25 % dosing error is otherwise silent | FW-core | L | GEAR (CTRL): REPLACE | H1 | C, B15 | Gear ratio does not match the calibration. |
| `4-41-003` | GEAR_TOOTH_SKIP | one angle-loss event of 1/12 screw turn (about 341 counts, +/- 20 %) or a multiple, otherwise normal motion | FW-core | F | GEAR: REPLACE | H1, H2 | C, B15 | Gear teeth slipped. |
| `4-42-001` | CARRIAGE_JAM_FWD | forward stall **without** a pressure ramp: current at least doubles within one burst and the angle stops, on 2 retries (otherwise `5-53-*`) | FW-core | F | SCREW (GEAR): REPLACE | H2 | C | Drive blocked. |
| `4-42-002` | CARRIAGE_FRICTION_HIGH | free-run current more than 40 % above baseline along the stroke (*cal*) | FW-core | W | SCREW: REPLACE | H2, H11 | C | Drive friction rising. |
| `4-42-003` | TRAVEL_LENGTH_MISMATCH | angle counts between the front and rear end stops differ more than 3 % from stroke x counts per mm (first full draw / provisioning) | FW-core | F | SCREW (MAGS): REPLACE | H1 | C | Drive travel does not match. |

### 4.4 Layer 5: fluid path (9 codes) and layer 6: sensing channels (9 codes)

| Code | Name | Detection and threshold | By | Sev | FRU: action | Haz | Test | Trio text |
|---|---|---|---|---|---|---|---|---|
| `5-50-001` | RESERVOIR_EMPTY | reservoir model at 0, front end stop, or a step vetoed by the model | FW-core | F | NONE: REFILL | H2 | C, D | Reservoir empty. |
| `5-50-002` | RESERVOIR_LOW | at or below the low level (default 10 U, configurable); ctx_a = mU | FW-core | W | NONE: REFILL | H2 | C | Insulin is running low. |
| `5-50-003` | RESERVOIR_MODEL_MISMATCH | front end stop reached with model above 2 U, or rear end stop in a draw with model room above 2 U | FW-core | F | RESV (MAGS): REFILL | H2 | C, B17 | Fill level is uncertain. |
| `5-50-004` | DRAW_NO_SOURCE | reverse current above the threshold with less than 30 % of the requested volume drawn and no end stop expected (vacuum) | FW-core | F | CAP: RETRY | H4 | C, B17 | Nothing is being drawn. |
| `5-50-005` | AIR_OR_LEAK_SUSPECTED | A07: vacuum signature below 60 % of expected on a closed system, or a prime needs more than 2 x the baseline steps to build pressure (*cal*) | FW-core | W | CAP (SEAL): PRIME | H4 | C, B17 | Air or a leak is suspected. |
| `5-51-001` | PLUNGER_FRICTION_PROFILE | peak-to-mean current ratio over a stroke above 2.5 or local deviation above 40 % (stick-slip) (*cal*) | FW-core | W | SEAL: REPLACE | H2, H11 | C | Plunger seal friction is unstable. |
| `5-53-001` | OCCLUSION_SHORTFALL | (commanded minus angle-confirmed) above 2 U (spec section 7); ctx_a = mU | FW-core | F | CANN (NEEDLE): CHECK_CANNULA | H2 | C, D, B16 | Blockage detected. |
| `5-53-002` | OCCLUSION_CURRENT_RISE | boards with a motor current sense only (bench; NOT raised on the cup v4 board, no shunt): 3 consecutive bursts above `OCCLUSION_CURRENT_MA` (140 mA placeholder, *cal*); ctx_a = mA | FW-core | F | CANN (NEEDLE): CHECK_CANNULA | H2 | C, B16 | Blockage detected. |
| `5-53-003` | OCCLUSION_RAMP_WARNING | boards with a motor current sense only (NOT raised on the cup v4 board): burst peak current slope over 5 or more bursts above 3 x baseline slope while below the fault threshold (*cal*) | FW-core | W | CANN: CHECK_CANNULA | H2 | C, B16 | A blockage may be building. |
| `5-53-004` | OCCLUSION_SHORTFALL_WARNING | angle shortfall (commanded minus angle-confirmed) above 1 U (half the spec budget, `occlusion::SHORTFALL_WARN_MU`) on 2 consecutive monitor passes, once per excursion; the only early occlusion warning on the cup v4 board (no current sense); ctx_a = mU | FW-core | W | CANN (NEEDLE): CHECK_CANNULA | H2 | C, B16 | A blockage may be building. |
| `5-54-001` | PRESSURE_ANOMALY_WHILE_DOCKED | docked with the driver off: the angle moves against the self-locking drive or the supply current is not at its idle value, or a delivery stalls with a reservoir pressure signature that no commanded step explains (possible manual injection into the cannula, H15); ctx_a = angle counts, ctx_b = mA | FW-core | L | CANN (CTRL): CHECK_CANNULA | H2, H15 | C | Unexpected pressure while docked. Check the cannula and the pod. |
| `6-60-001` | ANGLE_CHANNEL_LOST | `angle_read` returns `None` on 3 consecutive reads; **forwards the cause** (`7-79-001`, `3-30-*`, `2-20-*`) | FW-core | F | PODB (FFC): ISOLATE | H1, H2 | C, B01 | Position sensor lost. |
| `6-60-002` | FIELD_TOO_WEAK | magnitude below 50 % of the stored nominal (S09 and continuous); ctx_a = LSB, ctx_b = nominal | FW-core | F | MAGS (PODB): REPLACE | H2, H11 | C, B13 | Spindle magnet signal too weak. |
| `6-60-003` | FIELD_TOO_STRONG | magnitude above 160 % of nominal or range saturated (extra magnet near the pod) | FW-core | F | MAGS: RETRY | H2 | C, B13 | Position sensor sees a strong magnet. |
| `6-60-004` | ANGLE_NOISE_HIGH | standard deviation over 32 samples at rest above 4 counts (W) or above 16 counts (F) | FW-core | W | PODB (FFC): ISOLATE | H2 | C, B03 | Position sensor is noisy. |
| `6-60-005` | ANGLE_JUMP | change of more than 2048 counts between 20 ms samples (unwrap invalid); ctx_a = counts | FW-core | F | PODB (FFC): REPLACE | H1, H2 | C | Position sensor jumped. |
| `6-60-006` | ENC_REV_DEVIATION | angle per commanded leadscrew revolution outside 4096 +/- 3 % (`limits::REV_TOLERANCE_PCT`); ctx_a = counts | FW-core | F | GEAR (MOTOR): ISOLATE | H1, H2 | C, D, B15 | Drive position mismatch. |
| `6-60-007` | ENC_WINDOW_DEVIATION | deviation above 10 % over a window of at least 1 U (spec section 7); ctx_a = permille | FW-core | F | GEAR (MOTOR): ISOLATE | H1, H2 | C, D, B15 | Delivered amount does not match steps. |
| `6-60-008` | UNCOMMANDED_MOTION | net forward angle change above 40 counts (about 0.026 U on 15:12) within 10 s while the driver is in STBY and VMOT is verified off (back-driving: SCREW), or any motion while VMOT is present without a burst (interlock leak: CTRL) | FW-core | L | CTRL (SCREW): ISOLATE | H1, H10 | C, B11 | Plunger moved by itself. |
| `6-62-001` | CURRENT_OVER_LIMIT | `I_SENSE` peak above 1.5 x the configured chopper limit | FW-core | F | CTRL (MOTOR): ISOLATE | H2 | C, B06 | Motor current too high. |

### 4.5 Layer 7: firmware modules (41 codes)

Firmware codes are raised by the module named in the component. When a firmware module acts on a hardware fault it raises its own code **with `cause_rec`** pointing at the hardware record (cause chain, 1.6), so the FRU shown to the user comes from the root.

| Code | Name | Detection and threshold | By | Sev | FRU: action | Haz | Test | Trio text |
|---|---|---|---|---|---|---|---|---|
| `7-70-001` | HOURLY_LIMIT_VETO | supervisor: the 15 U rolling hour would be exceeded (the command layer should have refused first, so this is evidence of a bug) | FW-core | F | FW: REPORT_BUG | H1 | C, D | Hourly insulin limit stopped delivery. |
| `7-70-002` | PER_MINUTE_LIMIT_VETO | more than 1.7 U/min (65 steps/min backstop on the 5:1 drive, scaled by calibration) | FW-core | F | FW: REPORT_BUG | H1 | C, D | Insulin rate limit stopped delivery. |
| `7-70-003` | REQUEST_ABOVE_HARD_CAP | delivery engine asked for a rate above 30 U/h or a bolus above 25 U | FW-core | F | FW: REPORT_BUG | H1 | C | Internal limit check triggered. |
| `7-70-004` | STEPS_EXCEED_APPROVAL | executed steps (hardware TIMER1 count) exceed the steps the supervisor approved; ctx_a = executed, ctx_b = approved | FW-core | L | FW (CTRL): REPORT_BUG | H1 | C, B11 | Motor moved more than allowed. |
| `7-70-005` | STEPS_SHORT_OF_APPROVAL | executed fewer than approved by more than 1 step (driver fault, VMOT not verified); cause chain to `1-03-*`, `3-31-*`, `1-06-*` | FW-core | F | CTRL (MOTOR): ISOLATE | H2 | C | Motor did not follow commands. |
| `7-70-006` | BOOKKEEPING_MISMATCH | delivered total kept in two independent encodings (value and bitwise complement) differs, or the logged events do not add up to the counter | FW-core | L | FW: REPORT_BUG | H1, H13 | C | Internal dose records disagree. |
| `7-70-007` | VETO_STEP_REQUEST_ILLEGAL | engine requested a step while RELEASED, PAUSED_UNDOCKED, SUSPENDED or faulted (inst 1 to 4); the supervisor vetoed it. 3 in 10 min escalate to F | FW-core | W | FW: REPORT_BUG | H1, H9 | C | An internal check blocked an illegal step. |
| `7-70-008` | REVERSE_REQUESTED_WHILE_DOCKED | a reverse step was requested (draw / assisted fill, take-up, engine) while the pod is docked; refused in firmware before any pin moves, in addition to the hardware XOR gate (H14) | FW-core | F | FW: REPORT_BUG | H1, H14 | C | An internal check blocked a reverse step while docked. |
| `7-71-001` | ENGINE_STATE_INVALID | unreachable state or failed invariant in the delivery engine | FW-core | L | FW: REPORT_BUG | H1 | C | Internal state error. |
| `7-71-002` | BASAL_SCHEDULE_CORRUPT | stored schedule CRC or segment ordering invalid | FW-core | F | NONE: RETRY | H6 | C | Basal schedule on the pod is invalid. |
| `7-71-003` | TIME_NOT_SET | no `TIME_OF_DAY_MS` since boot; the schedule can not run | FW-core | W | APP: REPHONE | H6 | C, S | Pod clock not set. |
| `7-72-001` | RES_MODEL_RECORD_CORRUPT | stored fill record CRC fail | FW-core | F | NONE: REFILL | H2 | C | Fill level lost. |
| `7-72-002` | RES_MODEL_NEGATIVE | consumed above filled, or level outside 0..capacity | FW-core | F | NONE: REFILL | H2 | C | Fill level inconsistent. |
| `7-73-001` | DRAW_ABORTED | draw ended early (inst 1 docked, 2 fault, 3 cancelled, 4 stall); ctx_a = drawn mU | FW-core | W | NONE: RETRY | H4 | C | Refill stopped early. |
| `7-73-002` | DRAW_BLOCKED_NO_VMOT | reverse burst executed 0 pulses because VMOT did not come up (bench interlock limitation, `stubs.md` conflict 2); cause chain to `1-06-002` or `1-07-006` | FW-core | F | CTRL: ISOLATE | H4 | C, B17 | Refill not possible: motor supply blocked. |
| `7-74-001` | BOOT | every boot: reset cause, FW version, POST-S summary in ctx | FW-core | I | NONE: NONE | H3 | C | Pod started. |
| `7-74-002` | UNEXPECTED_RESET | reset cause other than power-on or commanded (watchdog, brown-out, lockup, soft); ctx_a = `RESETREAS`, ctx_c = breadcrumb of the last task state. The pod boots SUSPENDED | FW-core | W | NONE: ACK | H3 | C, B11 | Pod restarted unexpectedly and is suspended. |
| `7-74-003` | RESET_LOOP | 3 or more unexpected resets in 60 min | FW-core | L | FW: REPORT_BUG | H3 | C | Pod keeps restarting. |
| `7-74-004` | PAIR_STATE_INCONSISTENT | stored pair id, role, active flag and activation id contradict each other | FW-core | F | NONE: REPAIR | H1 | C | Pair information damaged. |
| `7-74-005` | POST_INCOMPLETE | a POST-A step timed out or was aborted (inst = step) | FW-core | F | NONE: RETRY | H11 | C | Self-test did not finish. |
| `7-74-006` | POST_RESULT | end of POST-S or POST-A: ctx_a = steps passed mask, ctx_b = steps failed mask | FW-core | I | NONE: NONE | H11 | C | Self-test finished. |
| `7-75-001` | NVM_WRITE_TIMEOUT | seq-ceiling write above 500 ms or persistence queue full; the command is refused | FW-core | W | NONE: RETRY | H7 | C, B21 | Pod storage is slow, command refused. |
| `7-75-002` | NVM_RECORD_CRC | settings record (pod state, schedule, bonds) CRC fail (inst = key) | FW-core | F | FW (CTRL): REPROVISION | H13 | C, B21 | Pod settings damaged. |
| `7-75-003` | FAULT_LOG_RECORD_CRC | fault-log item CRC bad; ctx_a = records lost | FW-core | W | NONE: NONE | H13 | C | Part of the error log was unreadable. |
| `7-75-004` | SEQ_CEILING_UNREADABLE | seq ceiling missing or CRC bad: a new session is required | FW-core | F | NONE: REPHONE | H7 | C | Pod lost its command counter. |
| `7-76-001` | INTERLOCK_FAILED_LATCH | HAL `failed` state: supply not verified cut, DONE withheld, MCU reset by the TPL5010 within about 2 s; the cause chain points at `1-05-*`, `1-06-*` or `1-07-*` | FW-HAL | L | CTRL: REPLACE | H1 | H, B07 | Motor safety interlock failed. |
| `7-76-002` | INTERLOCK_SEQUENCE_TIMEOUT | an interlock step (settle, STBY wake, EN/FAULT release) exceeded its timing constant | FW-HAL | F | CTRL: RETRY | H1 | H | Motor safety check timed out. |
| `7-77-001` | STEP_COUNT_SHORT | TIMER1 count below the requested pulses, or burst timeout (n/rate + 25 ms); ctx_a = executed, ctx_b = requested | FW-HAL | F | CTRL (MOTOR): ISOLATE | H2 | H, C | Motor did not complete its steps. |
| `7-77-002` | STEP_COUNT_EXTRA | TIMER1 count above the requested pulses | FW-HAL | L | FW (CTRL): REPORT_BUG | H1 | H, B11 | Motor stepped more than requested. |
| `7-77-003` | PWM_NOT_STOPPED | TIMER1 count still changing 5 ms after the burst ended | FW-HAL | L | FW (CTRL): REPORT_BUG | H1 | H, B11 | Step generator did not stop. |
| `7-78-001` | ADC_FAULT | SAADC timeout, offset calibration failed, or all channels identical (inst 1, 2, 3) | FW-HAL | W | CTRL: REPLACE | H11 | H, C | Analog measurement problem. |
| `7-79-001` | I2C_ERROR_RATE | TWIM errors (ANACK, DNACK, overrun) above 3 in 100 transfers; the cause chain continues in `3-30-*` or `2-20-*` | FW-HAL | W | PODB (FFC): ISOLATE | H2 | H, B03 | Sensor bus errors. |
| `7-7A-001` | TRIAL_BOOT_REVERTED | a new image was not confirmed and the bootloader reverted | FW-boot | W | FW: REPORT_BUG | H13 | H, B21 | Firmware update was rolled back. |
| `7-7B-001` | TICK_OVERRUN | safety tick delta above 2.5 s (nominal 1 s) | FW-core | W | FW: REPORT_BUG | H3 | C | Pod software ran late. |
| `7-7B-002` | TICK_STALL | tick delta at or above `TICK_MAX_DT` (5 s): the supervisor refuses the next steps | FW-core | F | FW: REPORT_BUG | H1, H3 | C | Pod software stalled. |
| `7-7B-004` | STACK_CANARY | stack paint overwritten or high-water mark below 5 % free | FW-core | L | FW: REPORT_BUG | H1 | C, B23 | Pod software memory error. |
| `7-7C-002` | PANIC | panic handler ran: file/line hash in ctx_a, breadcrumb saved to retained RAM, MCU reset; the record is written at the next boot | FW-core | W | FW: REPORT_BUG | H1 | C, B23 | Pod software error, restarted and suspended. |
| `7-7C-003` | UNKNOWN_CODE_RAISED | a raise with a code not in the catalogue; treated as F, FRU FW (never ignored) | FW-core | F | FW: REPORT_BUG | H13 | C | Unknown internal error. |
| `7-7C-004` | LOG_UNAVAILABLE | flash log write failed or CRC bad; the RAM ring keeps working | FW-core | W | CTRL: REPORT_BUG | H13 | C, B21 | Error log can not be saved. |
| `7-7D-001` | CAL_RECORD_INVALID | drive calibration missing, CRC bad or outside 1 to 60 mU per step (inst 1, 2, 3). No step is ever approved; not acknowledgeable | FW-core | F | FW: REPROVISION | H1 | C, D | Drive calibration missing or invalid. |
| `7-7D-002` | CAL_PRESET_MISMATCH | flash holds another preset than the build; the record is never overwritten | FW-core | F | FW: REPROVISION | H1 | C, D | Drive calibration does not match this firmware. |
| `7-7D-003` | TEST_CAL_IN_BUILD | a test calibration (id at or above 0x7F00) is present in the preset table at startup | FW-core | L | FW: UPDATE_FW | H1 | C | Test firmware installed. |

### 4.6 Layer 8: protocol (9 codes) and layer 9: app (13 codes)

| Code | Name | Detection and threshold | By | Sev | FRU: action | Haz | Test | Trio text |
|---|---|---|---|---|---|---|---|---|
| `8-80-001` | LINK_QUALITY_DEGRADED | more than 10 frame, length or CRC errors per minute | PROTO | W | NONE: REPHONE | H6 | P, B20 | Weak Bluetooth link. |
| `8-80-002` | VERSION_MISMATCH | frame version other than 1, or the diag schema is not understood | PROTO | W | APP: UPDATE_APP | H13 | P, S | Pod and app versions do not match. |
| `8-81-001` | AUTH_OR_REPLAY_BURST | 3 or more CCM tag failures (inst 1) or 5 or more replay rejects (inst 2) per minute | PROTO | W | NONE: REPAIR | H7 | P, B20 | The pod rejected commands from a phone. |
| `8-81-002` | SESSION_EXHAUSTED | `seq` reached 0xFFFE, rekey needed | PROTO | W | NONE: REPHONE | H7 | P | Session expired. |
| `8-81-003` | NO_SESSION_KEY | production build has no key agreement (current stub: every frame is answered AUTH) | PROTO | F | FW: UPDATE_FW | H7 | P | Pod can not be controlled: no secure key. |
| `8-81-004` | RNG_FAILURE | RNG health test failed at boot | FW-core | F | CTRL: REPLACE | H7 | C | Random generator failed. |
| `8-82-001` | MTU_TOO_SMALL | negotiated MTU below 247, frames cannot fit | PROTO | W | NONE: REPHONE | H6 | P, S | Bluetooth connection too limited. |
| `8-82-002` | NOTIFY_QUEUE_OVERFLOW | the alert queue (8 entries) dropped the oldest; the app resyncs with `GetFaultLog` | PROTO | W | NONE: NONE | H3 | P | Some pod alerts were missed, the app will refresh. |
| `8-83-002` | BOND_LOST | the app has no matching bond or the key does not match | PROTO | W | NONE: REPAIR | H7 | S | The pod no longer trusts this phone. |
| `9-90-001` | PUMP_UNREACHABLE | no response from the pod for 5 min while active | APP | W | NONE: REPHONE | H6 | S | Can not reach the pod. |
| `9-90-002` | DELIVERY_UNCERTAIN | link lost while a bolus or cancel was in flight; the existing recovery flow reconciles with `GetStatus` | APP | F | NONE: REPHONE | H1, H2 | S | Unsure whether the last bolus was delivered. |
| `9-91-001` | SWAP_OLD_POD_UNCONFIRMED | `Release` of the old pod not confirmed (existing alert `swapOldPodUnconfirmed`) | APP | W | NONE: REPHONE | H1 | S, B24 | Old pod not confirmed. |
| `9-91-002` | TWO_ACTIVE_PODS | both pods report ACTIVE or delivering (existing alert `podConflict`) | APP | F | NONE: SWAP_POD | H1 | S, B24 | Two pods report delivering. |
| `9-91-003` | HANDOVER_TOTALS_MISMATCH | `ACT_DELIVERED_MU` of the old pod differs from the app ledger by more than 0.15 U or 5 % | APP | W | NONE: NONE | H1 | S, B24 | Delivered amount of the old pod does not match. |
| `9-91-004` | SHARED_PART_SUSPECT | the same fault class on pod A and pod B within 24 h: suspect the shared cannula or the phone, not the pods | APP | W | CANN: CHECK_CANNULA | H2 | S | Both pods report the same problem. |
| `9-91-005` | SPARE_NOT_READY | the spare pod has an F or L record, a low level, or only a stale red cached state (existing alert `spareNotReady` extended) | APP | W | by the spare's record | H1 | S, B24 | The spare pod is not ready. |
| `9-92-001` | CAL_UNKNOWN | `DRIVE_CAL` missing, zero or not a known (id, uU per step) pair (existing `calibration` alert) | APP | F | NONE: UPDATE_APP | H1 | S | Pod drive calibration unknown. |
| `9-92-002` | CAL_CHANGED | `DRIVE_CAL` of a known pod UID differs from the stored one (pod rebuilt or drive swapped) | APP | F | NONE: RETRY | H1 | S | The pod's drive has changed. |
| `9-93-001` | DOSE_LEDGER_MISMATCH | pod `DELIVERED_MU` against the app ledger differs by more than 0.15 U or 5 % | APP | W | NONE: NONE | H1 | S | Delivered insulin does not match the records. |
| `9-94-001` | ALERTS_NOT_DELIVERABLE | notifications or critical alerts are switched off, so pod alarms may be missed | APP | W | NONE: NONE | H3 | S | Notifications are off, alarms may be missed. |
| `9-95-001` | POD_FW_UNSUPPORTED | pod firmware older than the app minimum | APP | W | FW: UPDATE_FW | H13 | S | Pod firmware too old for this app. |
| `9-95-002` | UNKNOWN_POD_CODE | the pod reported a code that is not in the app's catalogue; the record's own severity, FRU and action are used and the raw code is shown | APP | W | NONE: UPDATE_APP | H13 | S | Unknown pod error, update the app. |

### 4.7 Layer A: power (6 codes) and layer B: environment (6 codes)

| Code | Name | Detection and threshold | By | Sev | FRU: action | Haz | Test | Trio text |
|---|---|---|---|---|---|---|---|---|
| `A-A0-001` | BATTERY_LOW | at or below 3.5 V (`BATTERY_LOW_MV`, 100 mV hysteresis); inst 1 = bench VBUS source | FW-core | W | BATT (USB): CHARGE | H3 | C, D, B18 | Pod battery low. |
| `A-A0-002` | BATTERY_CRITICAL | below 3.3 V (`BATTERY_CRITICAL_MV`); inst 1 = bench VBUS source; blocks resume until recovered | FW-core | F | BATT (USB): CHARGE | H3 | C, D, B18 | Pod battery critical. |
| `A-A0-003` | BATTERY_OVERVOLT | Rev B: cell above 4.3 V or below 2.5 V persistently | FW-HAL | L | BATT: REPLACE | H8, H11 | C | Pod battery damaged. |
| `A-A1-001` | CHARGER_FAULT | Rev B: charge controller fault or charge timeout | FW-HAL | F | CHG: REPLACE | H8 | C | Charging fault. |
| `A-A2-001` | USB_SUPPLY_LOW | bench: `VBUS_SENSE` below 4.4 V (the 3.5 V and 3.3 V levels use `A-A0-001/002` with inst 1) | FW-HAL | W | USB: CHECK_POWER | H3 | C, B18 | USB power is weak. |
| `A-A2-002` | USB_OVERVOLT | `VBUS_SENSE` above 5.6 V | FW-HAL | L | USB: REPLACE | H11 | H, B18 | USB supply voltage too high. |
| `B-B0-001` | TEMP_HIGH_WARN | die temperature above 37 deg C (proxy; ambient not measured; *cal*); ctx_a = 0.25 deg C | FW-HAL | W | NONE: WAIT_COOL | H8 | C, B19 | Pod is warm. |
| `B-B0-002` | TEMP_HIGH_STOP | die temperature above 42 deg C (*cal*): delivery suspended | FW-HAL | F | NONE: WAIT_COOL | H8 | C, B19 | Pod too hot, delivery stopped. |
| `B-B0-003` | TEMP_LOW | die temperature below 5 deg C | FW-HAL | W | NONE: WAIT_COOL | H8 | C, B19 | Pod is cold. |
| `B-B0-004` | TEMP_SENSOR_IMPLAUSIBLE | frozen reading for 10 min or outside -20 to 85 deg C | FW-HAL | W | CTRL: REPLACE | H8, H11 | C | Temperature sensor error. |
| `B-B1-001` | WEAR_WARNING | 44 h since `Activate` (existing flag bit 8 and event 22) | FW-core | W | NONE: SWAP_POD | H1 | C, D | Pod worn for 44 hours. |
| `B-B1-002` | WEAR_EXPIRED | 52 h since `Activate` (legacy bit 7): delivery stops; cleared by `Activate` | FW-core | F | NONE: SWAP_POD | H1 | C, D | Pod expired, swap pods now. |

Catalogue size by layer: see the count table in 4.8.

### 4.8 Counts

| Layer | Codes | Notes |
|---|---|---|
| 1 CTRL (controller board) | 31 | interlock gate proofs (7), latch (3), watchdog (2), VMOT (3), sensing (4), rails, clock, flash |
| 2 POD (pod sensor board) | 9 | TMAG5273 (5), dock hall (3), optional quadrature (1) |
| 3 CABLE | 8 | FFC (4), motor lead (4) |
| 4 DRIVE | 9 | motor (3), gear pair (3), leadscrew/carriage (3) |
| 5 FLUID | 9 | reservoir and draw (5), plunger (1), outlet and occlusion (3) |
| 6 SENSE | 9 | angle channel (8), current channel (1) |
| 7 FW | 41 | supervisor 7, engine 3, reservoir model 2, draw 2, pod 6, storage 4, interlock HAL 2, stepper HAL 3, ADC 1, I2C 1, boot 1, timing 3, diagnostics 3, calibration 3 |
| 8 PROTO | 9 | |
| 9 APP | 13 | |
| A POWER | 6 | |
| B ENV | 6 | |
| **Total** | **150** | severity: 2 I, 54 W, 68 F, 26 L |

Reserved and not yet allocated: layer 1 components `0F` (HW-A step budget) and `10` (HW-B monitor), layer `C` to `E`, FRU ids 19 and up (Rev B). Codes needed by the electronics FMEA (3.6) or found in bench runs are appended to their component (rule 2.8).

## 5. Propagation design

```
 HW fault ──► HAL (hal/*.rs)  ──► core (diag module, supervisor) ──► persistence ──► protocol ──► OpenPatchCore ──► OpenPatchKit ──► Trio
   proof /     raises HAL code     raises own code with cause,        fault log,      GetStatus     DiagRecord,       Alert + status    Alert,
   plausibility with context       legacy Faults projection           latched set     GetFaultLog   catalogue         highlight, FRU    pump status,
                                                                                      Alert notify                    health view       settings
```

### 5.1 HAL to core

`openpatch-core` stays hardware independent; the HAL reports faults **as data**, never as silent defaults.

* New default methods on `Hal` (all with a no-op default, so mocks, the DK and the differential tests are unchanged until they opt in):
  * `fn take_diag(&mut self) -> Option<DiagEvent>`: drains HAL-detected events (`DiagEvent { code, ctx_a, ctx_b, ctx_c }`), polled by `Pump::tick()` after every HAL call batch and after each burst.
  * `fn motor_step_ex(&mut self, steps: Pulses) -> StepResult` with `StepResult { executed, drv_fault: bool, peak_ma: Option<u16>, vmot_ok: bool }`. This is the "fault return for `Hal::motor_step`" wish in `architecture.md`; the old `motor_step` stays and calls it.
  * `fn interlock_state(&mut self) -> Option<InterlockReadback>` (RB1..RB7, RB9, RB10 snapshot) for the POST and the idle-tick checks.
  * `fn selftest(&mut self, step: SelfTestStep) -> SelfTestOutcome` for the steps that need pin-level control (A01, A02, A08); the core owns the sequencing, the HAL owns the pins. `Pump::tick()` refuses to run a selftest unless SUSPENDED.
  * `fn reset_cause(&mut self) -> ResetCause` and `fn breadcrumb(&mut self) -> u32` (retained RAM).
* Every HAL-detected fault is raised with the **HAL's own code** (layers 1 to 3, `7-76`, `7-77`, `7-78`, `7-79`); the HAL never decides policy (latch, stop). The core decides policy and raises its own record with `cause_rec` (for example `7-70-005` caused by `1-03-001`).
* The core's supervisor receives the same events through `raise()`; `SafetySupervisor::latch(Faults::X)` call sites are converted to `raise(code!(...))`. The `Faults` bits are then **derived** (2.7), so existing callers and the 343 tests keep working.
* Safe-by-type idea for the core agent: `Hal::motor_step` takes an `Approved<Pulses>` that only `safety.rs` can construct (private constructor, `forbid(unsafe_code)` already in force), so a delivery-engine bug cannot even compile into a step.

### 5.2 Core: records, ring, latched set

New module `openpatch-core/src/diag/` (no_std, no alloc, `forbid(unsafe_code)`):

* `DiagCode(u32)` with const constructors and accessors; `Severity`, `Action`, `Fru` as `#[repr(u8)]` enums; `DiagRecord` (the 32 bytes of 2.6) with `to_bytes/from_bytes`.
* `catalogue.rs` **generated** (WP-0): a sorted `const [CodeInfo; N]` (code identity, severity, action, fru, fru2, legacy bit, hazard mask, short name). Lookup by binary search. `code!(1-06-001)` style macros or `pub const VMOT_STUCK_ON: DiagCode` constants are generated too, so a code can not be typed wrongly.
* `Diag` state: RAM ring of 64 records, a latched set of 16 entries `{identity, first_rec_id, count}`, `next_id`, a 10 s coalescing window per identity, the active set (identities whose condition is still present) and the FRU health state (2 bits per FRU, computed from active records and proof ages).
* API: `raise(code, ctx) -> RecId`, `raise_caused_by(code, ctx, cause)`, `condition_gone(code)` (clears the active flag and, for W/F, the active set entry), `clear(code, how)` (policy of 2.2 and 3.5), `legacy_faults() -> Faults`, `summary() -> DiagSummary`, `fru_health() -> u64`, `records_from(id)`, `take_notification()` (extends the existing notification queue with kinds 5 to 7).
* Policy in the core, not in callers: severity F or L stops delivery (supervisor latch + `motor_enable(false)` + alarm), severity L sets the persistent latched entry, severity W only sets the active flag. Escalation rules (W to F) are table entries in the catalogue (`escalate_after: (count, window)`).
* An unknown code raises `7-7C-003` and is treated as F with FRU FW (never dropped, never a panic in the safety path).

### 5.3 Persistence (survives reboot, power loss)

* **Fault log**: a `sequential-storage` queue over its own two flash pages (2 x 4096 B), item = 32-byte record + library CRC; capacity about 200 records; oldest overwritten; ids persistent with the same **ceiling** technique as the event ids (extend by 64, restore at boot, a gap in ids shows a reset). Written **only by the persistence task** (flash stalls the CPU); the safety task does `try_send` of the record. Same-identity repeats are coalesced; flash gets the first record, escalations, and count snapshots at 2, 10 and 100, so a faulty sensor can not wear the flash (worst case about one page erase every 12 h, which is more than 10 years at 10 000 cycles).
* **Latched set**: map key `diag/latched` (16 x {code u32, rec_id u32} + CRC), rewritten whenever the set changes. Delivery is stopped in RAM first; the flash write follows within 500 ms. If power is lost in between, POST re-detects hardware faults (the proofs of section 3 are the source of truth, the flash copy is an accelerator and the only memory for faults that need a state, such as `6-60-008`).
* **Baselines and nominals**: `diag/baseline` (free-run peak current, backlash, magnet field nominal, travel length), provisioned at the first POST-A and never overwritten without an explicit `REPROVISION`.
* **POST history**: `diag/post` (last S and A results with their uptime/wear time, for the freshness rules of 3.4).
* **Retained RAM** (not flash): reset cause, task breadcrumb and panic hash survive a watchdog reset and are turned into `7-74-002` / `7-7C-002` at the next boot.
* On boot the latched set is loaded **before** the interlock is ever armed; a pod with a non-empty latched set starts in state LATCHED (SUSPENDED + `STATE_FLAGS.LATCHED`).
* A failed log write raises `7-7C-004` and the RAM ring keeps serving `GetFaultLog` (records are lost on reboot, which the app sees as an id gap).

### 5.4 Protocol (additive to v1 and to the Rust extensions)

Compatibility: frame `version` stays **1**; frame layout, CRC, TLV encoding, AAD and nonce rules, `seq` rules and all existing commands, tags and result codes are unchanged. Unknown tags are skipped by v1 receivers, so an old app simply never sees the new data. `FW_VERSION` becomes 0x0210 for the first diagnostics build; the presence of `DIAG_SUMMARY` in `GetStatus` is the feature test, not the version. Everything below is encrypted like every other frame (AES-CCM; notifications use nonce direction byte 2).

**New TLV tags** (next free after 0x26):

| Tag | Name | Size | Content |
|---|---|---|---|
| 0x27 | `DIAG_SUMMARY` | 14 B | `u32 top_code` (root code of the most severe active record, 0 = none), `u8 top_sev`, `u8 top_action`, `u8 top_fru`, `u8 n_latched`, `u8 n_active` (W/F/L), `u8 post_state` (0 not run, 1 S passed, 2 A passed, 3 S failed, 4 A failed, 5 running), `u16 next_rec_id_lo`, `u16 schema` (catalogue version) |
| 0x28 | `FRU_HEALTH` | 8 B | `u64`, 2 bits per FRU id 0..31 (bits 2id+1..2id): 0 unknown, 1 ok, 2 degraded (W), 3 failed (F/L) |
| 0x29 | `DIAG_RECORD` | 32 B | the record of 2.6 |
| 0x2A | `NEXT_DIAG_ID` | 4 B | `u32` next record id |
| 0x2B | `OLDEST_DIAG_ID` | 4 B | `u32` oldest id still stored |
| 0x2C | `DIAG_LATCHED` | 4 to 64 B | up to 16 x `u32` code of the latched set |
| 0x2D | `SELFTEST_STATE` | 6 B | `u8 state` (0 idle, 1 running, 2 done), `u8 kind` (1 S, 2 A, 3 watchdog proof), `u16 steps_passed`, `u16 steps_failed` |
| 0x2E | `DIAG_CODE` | 4 B | `u32` code (request for `ClearDiag`; also returned with refusals) |
| 0x2F | `POD_UID` | 8 B | nRF `FICR.DEVICEID` (stable identity of the pod, independent of role A/B) |

`GetStatus` additionally returns `DIAG_SUMMARY`, `FRU_HEALTH` and `POD_UID` (about 36 bytes more; the frame stays far below 244 B). `STATE_FLAGS` gets bit 13 `DIAG_ACTIVE` (any W/F/L active) and bit 14 `LATCHED`. `FAULT_MASK` (0x09) is the derived legacy projection (2.7).

**New commands** (ids continue after 0x0F):

| Id | Name | Request tags | Response (after `RESULT`) |
|---|---|---|---|
| 0x20 (response 0xA0) | `GetFaultLog` | `FROM_ID` (0x0A, optional, default 0), `MAX_EVENTS` (0x0B, optional; 0 or above 4 gives 4) | `NEXT_DIAG_ID`, `OLDEST_DIAG_ID`, `DIAG_LATCHED`, 0 to 4 x `DIAG_RECORD` (4 x 34 B + 15 B + up to 66 B = 217 B, below the 235 B payload budget of 244 - 9) |
| 0x21 (response 0xA1) | `RunSelfTest` | `SUB_OP` (0x08): 1 POST-S again, 2 POST-A, 3 watchdog proof (service) | `SELFTEST_STATE`; progress through notification kind 7; results as `DIAG_RECORD`s (`7-74-006` last) |
| 0x22 (response 0xA2) | `ClearDiag` | `DIAG_CODE` (0 = all clearable W/F records) | `DIAG_SUMMARY`; `NotClearable` if the code is latched and its verification test has not passed |

**Command ids (changed 2026-11-19):** the first draft used 0x10 to 0x12, whose response types 0x90 to 0x92 collided with the Alert notification frame type 0x90 (`GetFaultLog` 0x10 | 0x80 = 0x90). The ids are now 0x20 to 0x22 (responses 0xA0 to 0xA2); a test asserts that no response type equals any command, handshake or notification type.

**New result codes** (after 27): 28 `SelfTestRefused` (not suspended, draw running or test running), 29 `Latched` (`Resume`/`Activate` refused; response carries `DIAG_CODE` of the root latched code), 30 `NotClearable`. `Acknowledge` (0x0A) keeps its legacy meaning (clears non-latched F records whose legacy bit is in the mask).

**Alert notifications** on the existing Alert characteristic (frame type 0x90, own sequence counter, as in `protocol-extensions.md`): `NOTIFY_KIND` 5 `DIAG_RAISED` (`NOTIFY_ARG` = code, plus a `DIAG_RECORD` tag in the same frame, so the app has the complete record without a round trip), 6 `DIAG_CLEARED` (arg = code), 7 `SELFTEST_PROGRESS` (arg = passed mask in the high half, failed mask in the low half). Kind 2 `FAULT` (new legacy bits) is still sent. Notifications are lossy by design (queue of 8): the **reliable path is pull**: the app stores `last_rec_id` per pod UID; every `GetStatus` carries `next_rec_id_lo`; if it moved, the app calls `GetFaultLog(from = last + 1)` until drained. The 8-82-002 code reports a queue overflow.

**History**: event type 31 `DIAG` (`a` = code as signed 32 bit, `b` = `ctx_a`) is added to `GetHistory` so a v1-only reader sees that a diagnostic record exists; event 14 `FAULT` stays.

Worked example (TLV level, frame header/CRC omitted; code `1-06-001` = `0x10600100`, little endian `00 01 60 10`):

```
DIAG_SUMMARY  27 0E | 00 01 60 10 | 03 08 01 01 01 03 | 06 00 | 03 00
                     top_code      sev act fru nL nA post  head   schema
DIAG_RECORD   29 20 | 05 00 00 00 | 00 01 60 10 | 03 08 01 00 | 2C 01 00 00 | 30 07 00 00 | E8 03 00 00 | 39 30 00 00 | 01 43 00 00
                     rec_id 5      code          sev act fru fru2  t_s=300       ctx_a=1840 mV ctx_b=1000 mV  ctx_c=12345   cnt flags cause
```

(flags 0x43 = latched + active + root cause.) The golden frames with real CRC and AES-CCM are generated by WP-4 and shared by the Rust and Swift tests (6.1).

The C reference (`firmware/`) is frozen: it never emits these tags; differential tests compare only the legacy projection (6.1).

### 5.5 iOS `OpenPatchCore`

* New types: `DiagCode` (struct over `UInt32` with `layer`, `component`, `fault`, `inst`, `description` `"1-06-001"`), `DiagSeverity`, `DiagAction`, `Fru` (enum with the ids of 2.4), `DiagRecord` (decode of the 32 bytes), `DiagSummary`, `FruHealth` (2-bit decode, `[Fru: HealthState]`), `PodUID`, `DiagCatalogue` (generated, `lookup(code) -> CodeInfo?`).
* `WireV1`: add tags 0x27 to 0x2F, commands 0x20 to 0x22, result codes 28 to 30, notify kinds 5 to 7, history type 31. Decoders are tolerant: a short or long TLV for an unknown future size is skipped with a `DiagCode 9-95-002`-style local record, never a crash.
* `PodStatus` gains `diag: DiagSummary?`, `fruHealth: FruHealth?`, `uid: PodUID?`; `faultCode` stays as the legacy summary.
* `PodEvent` gains `.diag(DiagRecord)`, `.diagCleared(DiagCode)`, `.selfTest(passed: UInt16, failed: UInt16)`.
* `V1Transport` gains `getFaultLog(from:)` (paging until `NEXT_DIAG_ID`), `runSelfTest(_:)`, `clearDiag(_:)`; `Transport` protocol gets the same with default "unsupported" for the simulator until extended.
* `NackReason` gains `.selfTestRefused`, `.latched`, `.notClearable`.
* `SimulatedPod` gets a fault injector `inject(_ code: DiagCode, ctx:)` so every catalogue code can be driven end to end in kit tests without hardware.

### 5.6 iOS `OpenPatchKit`: mapping to LoopKit alerts and the Trio status

| Severity | LoopKit `Alert` | Behaviour |
|---|---|---|
| I | no alert | shown only in the log view and the diagnostic report |
| W | `interruptionLevel: .timeSensitive`, `trigger: .immediate` | one alert per (pod, code identity); a repeat only bumps the count in the log; escalation (W to F) issues a new alert |
| F | `.critical`, `.immediate` | delivery stopped (H3 requires the user to notice); retracted when the record clears |
| L | `.critical`, `.repeating(repeatInterval: 15 min)` until retracted | repeats until the latched code is cleared by its verification test; the swap flow is offered |

* **Identifier**: `Alert.Identifier(managerIdentifier: pluginIdentifier, alertIdentifier: "diag-<L-CC-FFF>-<role>")`, for example `diag-1-06-001-A`; stable per code and pod, so Trio can de-duplicate, retract (`retractAlert`) and, if wanted, list them in `AlertCatalogRegistry` (optional, `ios/INTEGRATION.md` section 5).
* **Content**: title `"Pod A: Controller board"` (pod name + FRU name; for non-hardware codes the catalogue short name); body = catalogue **Trio text** + the action sentence + code, for example `"Motor supply stuck on. Replace the controller board. Code 1-06-001. Delivery is stopped; swap to the other pod."`. The action sentence comes from the action id (`REPLACE`: "Replace the <FRU>."; `RECABLE`: "Reconnect the FFC cable."; `REFILL`: "Refill the pod."; `ISOLATE`: "Open Pump settings, Component health, to find the faulty part."; `REPORT_BUG`: "This should never happen. Export the diagnostic report and contact the project."). All strings English and localizable (`NSLocalizedString` with the existing bundle).
* **Root-cause rule**: the alert is built from the **root** record of the chain; the chain is in the details. If the catalogue and the record disagree (app older than pod), the record's severity, action and FRU win.
* **Unknown code**: `9-95-002`: title "Unknown pod error", body "Code 0x%08X (severity N). Update the app." with the record's own severity and action.
* **Pump status** (`pumpStatusHighlight` in `OpenPatchPumpManager+UI.swift`): today "Pump Error" for any fault. New: for an active F/L record the message is the FRU instruction (`"Replace controller board"`, `"Reconnect FFC cable"`, `"No Insulin"`, `"Pump Error"` only as the last fallback) with state `.critical`; for W: `.warning` with a short text; the active pod's records win over the spare's.
* **State**: `OpenPatchPumpManagerState` stores `podDiag: [PodUID: PodDiagState]` (role, last seen, summary, FRU health, active records, `last_rec_id`, cached-at). `faultCode`/`phase = .faulted` stay for legacy flows and are set from the legacy projection.
* **Existing alerts** (`lowReservoir`, `podFault`, `batteryLow`, `podWearWarning`, `podWearExpired`, `podUndocked`, `calibration`, `spareNotReady`, `swapOldPodUnconfirmed`, `podConflict`) keep their identifiers; they now also carry the code in the body. `podFault` is replaced by the per-code `diag-*` alerts when the pod reports `DIAG_SUMMARY` (a v1-only pod still gets `podFault`).
* **Delivery uncertainty**: F records whose action involves a stop during a bolus set the existing `deliveryUncertainSince` path unchanged.

### 5.7 Component health view (pump settings)

A new section in `OpenPatchSettingsView` ("Component health"), per pod (segmented control Pod A / Pod B, the active pod first):

* One row per FRU of 2.4 that exists in this build: icon (grey unknown, green OK, yellow degraded, red failed), FRU name, one-line state ("OK, checked 2 h ago", "Replace: motor supply stuck on", "Not checked yet"), code, and the root cause. Tapping a row shows the cause chain with the original codes of every layer, the measured value against the threshold, the time (pod time mapped through BOOT events) and the recommended steps.
* Buttons: **Run self-test** (`RunSelfTest` 2 with a step-by-step checklist that mirrors POST-A, including the guided "take the pod off the dock" and "did you hear the beep" prompts), **I replaced this part** (runs the self-test, then `ClearDiag` for the latched codes of that FRU; the pod, not the app, decides if the code clears), **Copy diagnostic report** (pod UID, FW and catalogue version, FRU health, all records with chains, as text for a bug report; contains no insulin or glucose data).
* `ISOLATE` actions open a small wizard ("Unplug the motor plug J5, then tap Run test") that runs the test and then tells which of the two suspects is the faulty one (rules in the catalogue: for example `3-31-003`: fault persists with the motor unplugged means controller board).
* The same data feeds the swap flow (5.8).

### 5.8 Two-pod handover: which pod has the faulty part

* **Identity**: each pod reports a stable `POD_UID` (and the role A/B from `POD_INFO`). The app keys all diagnostic state by UID, so a role reassignment (`SetPairing`) can not misattribute a fault. Records carry no role; the BLE connection determines the pod, and the UID confirms it.
* **Attribution in the UI and alerts**: every alert title and every health row names the pod ("Pod A", "Pod B"). The spare pod is parked and usually asleep, so its state is the **cached** state with "last seen"; a cached red or yellow state is **sticky**: silence is never interpreted as OK (fail-safe, 1.4).
* **Swap gating** (`PairSwapCoordinator`): `Activate(new)` is refused by the app if the new pod's last known summary has an active F/L record, an unknown POST state, or no passing POST-A since its last fill; the pod itself also refuses (`Latched`, result 29). The refusal text names the pod and the FRU ("Pod B cannot be used: replace the controller board"), via `9-91-005`.
* **Faulty active pod**: an F/L record on the active pod triggers the existing swap flow proposal ("Swap to Pod B now") if the spare is ready; if the spare is not ready, the user sees what is wrong with each pod (for example "Pod A: replace the motor. Pod B: refill").
* **Handover consistency**: `Release(old)` response totals (`ACT_DELIVERED_MU`) are compared with the app ledger (`9-91-003`); both pods ACTIVE (`9-91-002`) is critical.
* **Shared parts**: occlusion or similar faults that appear on pod A and then on pod B within 24 h raise `9-91-004`: the likely culprit is the shared cannula/infusion set (or the phone), and the alert says so instead of telling the user to replace pods.
* **Unreachable old pod**: the existing rule stands (the new pod is not activated until the user confirms the old pod is physically removed); the old pod's undocked state blocks its motion in hardware.

## 6. Test strategy

Principle: **every code has a test that makes it fire, at the lowest layer that can detect it, plus a test at each layer that must forward it.** A code without a test is not allowed into the catalogue (waiver list with a reason, reviewed). The Test column of section 4 is the contract; WP-0 generates the coverage report from it.

### 6.1 Automated levels

| Level | What | How | Gate |
|---|---|---|---|
| `C` core fault injection | every code detected by `FW-core` | `FaultyHal` wrapper around the existing mock HAL with injectors (`I2cNack`, `AngleFrozen`, `AngleJump`, `AngleScale(f)`, `FieldScale(f)`, `VmotStuck(mv)`, `LatchStuckHigh`, `StepShort(n)`, `StepExtra(n)`, `PwmRunsOn`, `CurrentScale(f)`, `DriverFault`, `BrownOut`, `TickStall(ms)`, `NvmFail`); one test per code named `diag_<code>` asserting code, severity, FRU, action, legacy bit, cause chain, active/latched state, persistence snapshot, `Acknowledge` and `ClearDiag` behaviour | `cargo test --workspace` plus `tools/diag_coverage.py` (fails when a catalogue row with tag `C` has no `diag_<code>` test) |
| `H` HAL logic | interlock sequencing, rotating disarm, POST-S/A state machines, step-count checks, I2C recovery, TMAG decode | move the pin-level logic of `hal/driver.rs`, `hal/stepper.rs`, POST into a host-testable module behind a `Pins` trait (WP-3); a **simulated board** models the gate truth table (latch, `MCU_EN`, DOCKED, DIR_REV), VMOT rise/fall, TPL5010 and a TMAG; switches for stuck-pass, stuck-block, shorted-to-rail per gate and per readback | `cargo test` on the host; every `1-0x`, `1-07-*`, `7-76-*`, `7-77-*` code fires from a simulated hardware fault |
| `D` differential | back-compat of the legacy projection | for the existing 32 differential scenarios and a new randomised scenario generator: Rust `legacy_faults()` equals the C reference's fault mask; **no new code at severity W or above fires in any nominal scenario** | CI differential job |
| Soak / false positives (H12) | thresholds have margin | 72 h simulated run (basal, boluses, temp basals, draws) with sensor noise (angle +/- 1 count, current ripple, tick jitter +/- 50 ms, BLE drops): zero records at W or above; `proptest` command sequences; mutation test on the `diag` module (`cargo mutants`): changing a threshold by one step must break a test | CI nightly |
| `P` protocol | tags, commands, notifications, sizes | encode/decode round trips, golden frames (real CRC and AES-CCM) written once by Rust into `firmware-rs/openpatch-proto/tests/fixtures/diag/`, worst-case frame (4 records + 16 latched codes) at most 244 B, fuzz of truncated/garbage TLVs (no panic, no state change), **old-parser test**: the v1 parser (the existing Swift decoder at the commit before WP-5 and the C `op_*` parser) skips the new tags and still decodes the old ones | `cargo test`, `swift test` |
| `S` Swift | decode, catalogue, alerts, health, swap | decode the golden fixtures; table-driven over **every** catalogue row: identifier, title, body (contains FRU instruction and code), interruption level, repeat trigger; unknown code path (`9-95-002`); chain headline is the root; `FruHealth` decode; swap gating (`9-91-005`); sticky cached state; view-model tests of the health view; `SimulatedPod.inject` drives every F/L code to exactly one alert and one retract | `swift test` for OpenPatchCore and OpenPatchKit |
| Catalogue integrity | the three copies cannot drift | `tools/gen_diag.py --check`: Rust and Swift catalogues equal the table; codes unique; every F/L row has a legacy bit (default 5); every row has text of at most 90 characters, an action and a test tag; FRU ids valid | CI |

### 6.2 Fault injection feature in the firmware

A cargo feature `fault-inject` (never in a release/production build; `compile_error!` together with `production`) adds a bench command `inject <code> [ctx]` that raises the record through the normal path and, for hardware-style faults, drives the simulated condition (for example forces the `STCK` counter result) so the **whole** chain (core, persistence, protocol, app) can be exercised without breaking hardware. Layer `F` of the code space is reserved for test-only codes.

### 6.3 Bench procedures for hardware faults (water only, never a person, never insulin; the jig is used only with an empty or water-filled reservoir)

A **fault jig** (WP-7) is a small board that plugs onto the controller test points and the FFC and has DIP switches for: open or short of each interlock gate input (`PGATE`, `PG_MID1/2`, `MCU_EN`, `DOCKED_H`, `DIR_REV`, `LATCH_CLR_N`, `ARM_CLK`), `WDT_WAKE`/`WDT_DONE` open, motor phase open and short, `I_SENSE` open, FFC pin open/short. Faults that need a destroyed part (Q4 drain-source short) use a sacrificial controller board with a jumper wire.

| Id | Procedure | Expected |
|---|---|---|
| B01 | unplug the FFC while idle (docked magnet in place) | `3-30-001`, then `6-60-001` with cause; FRU FFC; pod SUSPENDED |
| B02 | unplug the FFC during a prime | burst aborted, `3-30-001`, `7-77-001`/`7-70-005` chained; VMOT off |
| B03 | wiggle / half-insert the FFC; add a 1 k to 10 k leak on SDA | `3-30-002`, `3-30-003`, `2-20-004`, `6-60-004`, `7-79-001` |
| B04 | unplug the motor plug J5; intermittent contact | `3-31-001`, `3-31-004` |
| B05 | one motor phase open (jig); `EN/FAULT` forced low at idle | `3-31-002`; `1-03-002` |
| B06 | motor phase short (jig); both phases shorted together | `3-31-003`, `1-03-001`, `6-62-001`; unplugged motor + persists points to controller |
| B07 | sacrificial board: Q4 drain-source jumper; check `VMOT` in the scope | `1-06-001` within one tick, `7-76-001` chained, DONE withheld, TPL5010 reset within the measured time; STBY keeps the driver off |
| B08 | jig: force each gate input stuck-pass (`Q5`, `Q8`, `Q6/Q7`, `Q10/Q11` gates high) and `MCU_EN`/`ARM_CLK`/`LATCH_CLR_N` own-pin shorts | `1-07-001` to `1-07-004`, `1-07-007` from A01/A02 and from the rotating disarm; the pod latches |
| B09 | jig: force each gate stuck-block (shorted to GND) | `1-07-005`, `1-07-006`, `1-06-002`; pod can not arm (fail-safe) |
| B10 | jig: latch output held high / low; `LATCH_CLR_N` open | `1-05-001`, `1-05-002`, `1-05-003` |
| B11 | stop the firmware in the debugger with the motor armed and `STCK` running (and a variant with the PWM left running); measure with a scope and count steps | VMOT collapse time (TPL5010) recorded: **this number replaces the estimate in 1.5**; at the next boot `7-74-002` with `RESETREAS` watchdog; also `7-70-004`/`7-77-002` when a counter overrun is staged |
| B12 | TPL5010: cut `WAKE`, short `DONE`, withhold DONE (A08), break the `RSTn` path | `1-04-001`, `1-04-002`, `1-01-003` |
| B13 | remove the spindle magnet; shim it 0.5 mm away; add a strong magnet near TMAG | `6-60-002`, `6-60-003`, `2-20-003` |
| B14 | remove the dock magnet; hold it at the switching distance (jitter); fix a magnet permanently near the hall | `2-21-002`, `2-21-003`, `2-21-001` (via the lift test), `1-07-006` |
| B15 | fit the wrong gear pair (18:18 against 16:20 firmware); swap the DIR_REV option (R96/R97); swap motor phases; insert a damaged/skipping gear | `4-41-002` (class 2), `4-40-003`, `4-41-003`, `6-60-006`; **this resolves the open gear-ratio question with evidence** |
| B16 | outlet blocked with a clamp (water), slow restriction | `5-53-003` then `5-53-002`/`5-53-001` before 2 U shortfall |
| B17 | draw with an empty syringe / needle out of the septum / air at the outlet; with the DOCKED jumper missing | `5-50-004`, `5-50-005`, `5-50-003`, `7-73-002` |
| B18 | programmable supply: ramp 5.0 to 3.0 V and back, 5.0 to 6.0 V, 100 ms dips; load step | `A-A2-001`, `A-A0-001/002`, `1-02-001`, `1-06-003`, `1-01-002`, `A-A2-002` |
| B19 | heat gun to 38 and 43 deg C, cold spray | `B-B0-001`, `B-B0-002`, `B-B0-003` |
| B20 | BLE out of range, interference, MTU 23, wrong key, replayed frames, kill the link mid-bolus | `8-80-001`, `8-82-001`, `8-81-001`, `9-90-001`, `9-90-002` |
| B21 | power loss during a flash write (relay on the supply, random timing, 1000 cycles); corrupt a settings page; unconfirmed update image | `1-01-004`, `7-75-*`, `7-7C-004`, `7-7A-001`, no silent default |
| B22 | known resistor across the shunt; shunt open (jig); `I_SENSE` shorted high | `1-08-001` to `1-08-003`, `1-09-001` |
| B23 | build with `fault-inject`: panic, stack overflow, tick stall | `7-7C-002`, `7-7B-004`, `7-7B-002`, `7-74-003` after 3 |
| B24 | two bench pods: old pod unreachable, both active, totals differ | `9-91-001`, `9-91-002`, `9-91-003`, `9-91-005` |

Each procedure is logged as a short entry (date, board revision, code seen, ctx values, scope capture where relevant) in `electronics/bench/` or `firmware-rs/docs/bench-testing.md`; the thresholds marked *cal* are tuned from these runs.

### 6.4 Traceability matrix: hazard, codes, tests

(The per-code matrix is the Haz and Test columns of section 4; `tools/gen_diag.py` also writes it as `docs/06-diagnostics-trace.md`. Below the hazard-level view with the acceptance criterion that closes the hazard line.)

| Hazard | Codes | Tests | Acceptance |
|---|---|---|---|
| H1 Over-delivery | `1-04-*`, `1-05-*`, `1-06-001`, `1-07-*`, `4-40-003`, `4-41-002`, `6-60-008`, `7-70-*`, `7-76-*`, `7-77-002/003`, `7-7B-002/004`, `7-7D-*` | `C` per code, `H` interlock model, `D` parity, B07 to B12, B15, B23 | every single stuck-pass fault of the interlock is detected within 3 bursts (rotating disarm) or at the next POST; B11 gives the measured watchdog dose bound |
| H2 Under-delivery / occlusion | `5-53-*`, `6-60-001..007`, `6-62-001`, `3-31-*`, `4-40-001/002`, `4-41-001/003`, `4-42-*`, `1-03-*`, `1-06-002/003`, `1-08-*` | `C`, `H`, B01 to B06, B13, B16 | occlusion alarms before 2 U shortfall; a dead angle sensor stops delivery |
| H3 Unnoticed stop | `1-01-002`, `7-74-002/003`, `7-7B-*`, `7-7C-002`, `9-90-001`, `9-94-001`, `A-A0-*`, `A-A2-001`, `1-0C-002` | `C`, `S`, B11, B18, B20, B23 | every unexpected reset raises a visible alert; critical alerts for F/L |
| H4 Air | `5-50-004/005`, `7-73-*` | `C`, B17 | compliance test distinguishes closed liquid system from air in the bench rig |
| H6 Comms loss | `7-71-002/003`, `8-80-*`, `8-82-*`, `9-90-*` | `P`, `S`, B20 | |
| H7 Unauthorized access | `8-81-*`, `8-83-002`, `7-75-004` | `P`, `S`, B20 | |
| H8 Heat / charge | `B-B0-*`, `A-A0-003`, `A-A1-001` | `C`, B19 | |
| H9 Not docked | `1-07-003/004/006`, `2-21-*`, `3-30-004`, `7-70-007` | `H`, `C`, B08, B09, B14 | |
| H10 Backflow / siphon | `6-60-008` | `C`, B11 | |
| H11 Undetected degradation (new) | all `L` codes of layers 1 and 4, `1-01-005`, `1-08-003`, `4-40-002`, `4-41-001`, `4-42-002`, `5-51-001`, `7-74-005/006` | `H`, `C`, B07 to B12, B22 | each FMEA row of 3.6 has a code and a test; FRU health is never OK without a proof |
| H12 False positive (new) | all W/F codes | soak, mutation, `D` no-new-code-in-nominal | 72 h nominal run with zero W or above |
| H13 Diagnostics wrong or lost (new) | `7-7C-*`, `7-75-003`, `9-95-*`, `8-80-002` | `C`, `P`, `S`, B21, B23 | unknown code handled; log gap visible; catalogue drift check in CI |

## 7. Implementation plan (work packages)

Ordering: **WP-0 first** (shared catalogue), then WP-1, WP-4 and WP-7 in parallel, then WP-2, WP-5, then WP-3 and WP-6, WP-8 last. Other agents are editing `firmware-rs/`, `ios/` and `electronics/` now; each package below names the files it owns and must rebase onto their changes, keeping their tests green. Everything stays test-first; `forbid(unsafe_code)` in the core; update `docs/STATUS.md` and commit (Conventional Commits) after each package as the repository rules require.

| WP | Scope (owner dir) | Depends on | Acceptance criteria |
|---|---|---|---|
| **WP-0 Catalogue source and generator** (`tools/gen_diag.py`, `spec/diag-codes.csv` or the section 4 tables, generated `openpatch-core/src/diag/catalogue.rs`, `ios/.../DiagCatalogue.swift`, `docs/06-diagnostics-trace.md`) | single source of truth; parse the section 4 tables once into the CSV, then the CSV is the source and the tables are generated | none | codes unique and well formed; FRU, action, severity valid; every F/L has a legacy bit (default 5); text at most 90 chars; every row has a test tag or a waiver; `--check` mode fails CI on drift; generated Rust and Swift compile; coverage report lists codes without tests |
| **WP-1 Core diag module** (`firmware-rs/openpatch-core/src/diag/`, `faults.rs`, `safety.rs`, `pump.rs`, `hal.rs`) | `DiagCode`, records, ring, latched set, `raise`/`raise_caused_by`/`clear`, legacy projection, convert `latch(Faults::X)` sites, extend `Hal` with default methods, notification kinds 5 to 7, `Approved<Pulses>` | WP-0 | **all 343 existing tests and the 32 differential tests pass unchanged**; new tests for ring, coalescing (10 s), cause chain depth, latch and clear rules per severity, unknown code (`7-7C-003`), legacy projection equals the old bits for every legacy scenario; no alloc, no unsafe; code size increase reported |
| **WP-2 Core detectors** (`openpatch-core/src/diag/detect/*`, `safety.rs`, `reservoir.rs`, `draw.rs`) | angle plausibility (frozen, jump, noise, field, ratio, tooth skip, backlash, travel), uncommanded motion, step bookkeeping (dual encoding, executed vs approved), baselines (current, friction, ramp), reservoir model checks, tick overrun/stall, reset cause and loop, time-of-day, battery and temperature, wear; `FaultyHal` | WP-1 | one `diag_<code>` test per `FW-core` row; 72 h nominal soak has zero W-or-above records; mutation test on thresholds; differential parity (6.1) green |
| **WP-3 Bench HAL, POST and persistence** (`firmware-rs/openpatch-bench/src/hal/*`, `safety.rs`, `storage.rs`, `board/e73.rs`) | host-testable interlock and POST module behind `Pins`; rotating single-gate disarm; A01 to A11; readbacks RB1..RB13 (stage 1 with existing signals `LATCH_Q_MON`, `VMOT_SENSE`, own-pin readback, `EN/FAULT`; stage 2 when WP-7 delivers RB1..RB5, RB12); `motor_step_ex` with driver fault; I2C bus recovery and TMAG ID/status; retained-RAM breadcrumb and panic handler; fault log and latched set persistence; `fault-inject` feature | WP-1; WP-7 for stage 2 | host simulated-board tests for every `H` row; bench B01 to B12 and B21 give the expected codes; step timing and tick jitter not worse than today (measure); DK build reports interlock proofs as UNKNOWN, never OK; no new `unsafe` |
| **WP-4 Protocol** (`firmware-rs/openpatch-proto/`, `docs/`: `firmware-rs/docs/protocol-extensions.md`, `firmware/docs/openpatch-protocol.md` addendum) | tags 0x27 to 0x2F, commands 0x20 to 0x22, results 28 to 30, notify kinds 5 to 7, event 31, flags 13/14; codec, session; golden fixtures | WP-0 (record layout), WP-1 for the types | round-trip and golden tests; worst-case frame at most 244 B; fuzz clean; v1 old-parser test passes; encrypted notifications use nonce direction 2; document updated with the example of 5.4 |
| **WP-5 iOS core** (`ios/OpenPatchKit/OpenPatchCore/`) | models, catalogue, `WireV1` additions, `V1Transport` calls, `PodStatus`/`PodEvent` extensions, `SimulatedPod.inject` | WP-0, WP-4 fixtures | Swift tests decode all golden fixtures; every catalogue row maps; unknown/short TLV never crashes; the existing 143 core tests pass |
| **WP-6 iOS kit and UI** (`ios/OpenPatchKit/OpenPatchKit/`, `OpenPatchKitUI/`) | per-code alerts (identifier, text, level, repeat), retract, `pumpStatusHighlight` with FRU text, state persistence per pod UID, swap gating, component health view, isolation wizard, diagnostic report export | WP-5 | alert tests over every catalogue row; exactly one alert per (pod, code), retracted on clear; swap refused for a faulty spare with a naming message; health view view-model tests; legacy `podFault` still works for a v1-only pod; existing 49 kit tests pass; `ios/INTEGRATION.md` updated (optional `AlertCatalogRegistry` entries) |
| **WP-7 Electronics readbacks, FMEA, jig** (`electronics/bench/controller`, `pod`, `pin-assignment.md`, `INTERLOCK.md`/`DIAGNOSTICS.md`) | RB1..RB5 and RB12 (FFC loop on the pod board), shared pin or resistor-ladder decision, test points for the jig, FMEA in the 3.6 format with codes, fault jig design, optional HW-A step budget (1.5), reconcile `pin-assignment.md` with `firmware-rs/docs/boards.md` | none (in parallel with WP-1) | pin map identical in `pin-assignment.md`, `boards.md` and the core; DRC 0; FMEA rows reference catalogue codes, every "protection lost" mode has an L code; jig drawing and BOM; the DRAW jumper question (`stubs.md` conflict 2) decided |
| **WP-8 Validation and documentation** (`firmware-rs/docs/bench-testing.md`, `docs/`) | run B01 to B24, record results, tune *cal* thresholds, replace the 1.5 estimate by the B11 measurement, `docs/STATUS.md` update, merge the §7a text into `spec/design-parameters.md` and H11 to H13 into `02-safety.md` after user review | WP-3, WP-6, WP-7 | every F/L code observed on hardware or explicitly waived; traceability report with no gaps; thresholds committed |

## 8. Open questions, assumptions, known gaps

**Questions for the user**

1. **Hardware dose bound (1.5):** add HW-A (about two logic chips, step budget and arm window) to the Rev A controller? Add the independent monitor (HW-B) in Rev B? Without them the dose inside the watchdog window is a software guarantee only.
2. **Latched policy:** a latched code clears only by its verification test passing after the stated action. Do you want an explicit "service override" (for example to keep working on the bench with a known-bad sensor)? Default proposed: no override, use the DK/rig builds for that.
3. **Is a net-zero 0.1 U excursion in POST-A acceptable** on a docked pod (bench, water only)? For Rev B (on a real cannula) it would need a different test or no motion at all.
4. **FRU granularity for Rev B** (integrated pod): keep the 18 ids and map several to "pod board", or collapse? Proposed: keep ids, collapse in the UI.
5. **Critical Alerts entitlement:** `.critical` interruption needs Apple's entitlement in Trio; without it Trio falls back to time sensitive. Acceptable for the bench project?
6. **Gear ratio:** the pair is decided (GHW 16:20, firmware preset `drive-nfp-608-26-45-g16-20`, id 0x25); `4-41-002` latches a pod built with another pair.

**Assumptions (each has a code that fires if it is wrong)**: `DIR_REV` polarity (R96/R97, `4-40-003`); TMAG5273 register map and status bits (`2-20-002`, `2-20-005`); thresholds marked *cal*; TPL5010 timing (about 2 s, B11); nRF die temperature as a proxy for pod temperature (`B-B0-*`).

**Known detection gaps (not solvable on the pod, documented on purpose)**: plunger seal or duckbill leaks without a pressure signature (only the compliance test A07 hints at them; gravimetric bench tests remain the real check); delivered volume accuracy itself (angle confirms steps, not microlitres: gravimetric procedure in `02-safety.md` section 3); a magnet that slips on the leadscrew while the angle still turns (only the travel-length test `4-42-003` can see it); dock magnet orientation errors in the adapter. These are process or bench-test items, not silent pod behaviours: the Component health view shows such FRUs as UNKNOWN until a test covers them.

**Not verified on hardware**: nothing in this document has run on a target (see `firmware-rs/docs/stubs.md`). Every threshold is a design value.
