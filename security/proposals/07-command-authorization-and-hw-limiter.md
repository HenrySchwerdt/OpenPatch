# Proposal 07: Command authorisation model, "pod enforces everything", fresh confirmation for dangerous commands, hardware hourly limiter / independent monitor

Status: proposed, **not implemented**. Priority **P0 for the authorisation model (software), P1 for the hardware limiter (Rev A bench board change / Rev B design)**.
Evidence: `security/verify/tests/safety_props.rs` (limits hold for arbitrary command sequences, except FINDING-003), `docs/02-safety.md`, spec section 7, `firmware-rs/openpatch-core/src/{safety,pump}.rs`, hardware interlock section 2 of the safety concept.

## 1. Principle: the pod is the policy enforcement point
The phone app (Trio, a loop algorithm, possibly an LLM-assisted tool, possibly malware) is **not trusted to stay within limits**. Every limit lives on the pod, is checked by code that cannot be reached by a command path that skips it, and each layer assumes the one above is malicious:

| Layer | Bounds a fully malicious *authenticated* phone? | Evidence |
|---|---|---|
| L1 Command validation (`check_bolus`, `check_temp_basal`, `check_basal_schedule`) | yes: <= configured max <= HARD max (25 U bolus, 30 U/h basal), granularity | `p4_bolus_check`, `p5_rate_check` |
| L2 Step veto `approve_steps` (every step) | yes: <= 1.7 U/min, <= 15 U per 60 wall-minutes, reservoir, docked, active, no fault. True sliding-window worst case 16.7 U/59 min (FINDING-003) | `p1..p3` |
| L3 Encoder/occlusion monitor | detects under/over travel, latches faults | core tests |
| L4 Hardware interlock (MCU_EN AND TPL5010 AND DOCKED) | yes when firmware is *malicious*: no supply to the driver without the watchdog being fed | safety concept 2; electronics |
| L5 (proposed) hardware hourly limiter / independent monitor | yes, even with attacker firmware | section 4 |

## 2. Authorisation model (software, P0)
1. **Roles per session** (a session is bound to the PS of exactly one pairing; the role is decided by *how the pairing was made*, never claimed by the phone): a bench pod has exactly one pairing = `Owner`. Define `Role::{Owner, Observer}` now and pass it to every command handler (unknown future roles = least privilege); `Observer` (a caregiver's second phone, Rev B) may only use *Safe* commands.
2. **Command classes**:
   - *Safe* (GetStatus, GetHistory, Acknowledge of non-limit alarms): any authenticated session.
   - *Dosing* (Bolus, SetTempBasal, SetBasalSchedule, Resume): authenticated session + pod-side limits (L1-L2). No other gating (usability).
   - *Dangerous* (new category): `SetLimits` (raising max bolus/basal), `FillPrime`/`FillDraw`, `Release`/`SetPairing`/`Activate`, DFU start, factory reset/`forget PS`, diagnostic commands that change calibration, time set. Require a **fresh confirmation**: see 3.
3. **No command may raise a hard limit.** The hard limits (spec section 7) are `const`; `configure()` already rejects above them. Keep a compile-time test that no code path writes `HARD_MAX_*`.
4. **Rate limits on dosing commands** independent of the amount: at most N dose-changing commands per minute per session (default 12, burst 4), so a malicious phone cannot spam `SetTempBasal` to cause log eviction / flash wear / pump-state thrash (wear: the seq ceiling write-ahead already costs a flash write per 8 commands).
5. **Reservoir/occlusion/over-delivery semantics are pod-side** (the phone's idea of "delivered" never changes a limit).
6. **`Resume` after a fault requires physical presence for limit-class faults** (`LIMIT_EXCEEDED`, `ENCODER_DEVIATION`, `OCCLUSION`): button on the pod (the button exists on the bench controller board). A compromised phone can thus not clear a safety fault and continue; today `Acknowledge` over BLE can (the proptest P1-P3 includes an adversary that acknowledges every fault immediately, limits still hold, but the *fault is the alarm* for the human).

## 3. Fresh confirmation for dangerous commands
Two mechanisms, strongest feasible first:
1. **Physical confirmation on the pod** (button press within 30 s of the request, LED/buzzer pattern shows the pending class): required for `Release`, `SetPairing`, factory reset, DFU start, `SetLimits` raise, `FillPrime`.
2. **Fresh-session challenge** for the rest: the command must be sent in a session established **< 60 s ago** and carry the pod's last `challenge` (8 random bytes returned in `GetStatus`/in a `Challenge` response, single use). Stops replay of captured-but-still-valid authenticated frames across a long-lived session and ties the action to a recent, user-driven interaction (the app asks for Face ID before establishing a *dangerous* session: the Face ID gate lives in the app, enforced by the pod only through the "fresh" requirement). A malicious app that already holds the PS can still establish fresh sessions; hence the physical button for the most dangerous commands.
3. Replay/ordering stays as today (strict seq); add `ConfirmToken` TLV (0x2B proposed; coordinate numbering with the diagnostics owner's 0x27-0x2F block).

## 4. Hardware hourly limiter / independent monitor (P1, hardware)
Residual after L1-L4: firmware that is *fully attacker controlled* (malicious update that passes signing, glitched flash, supply-chain implant in a dependency) can run the motor at the **hardware step budget** the interlock allows: the interlock stops *unattended motor supply* but not "motor runs while the watchdog is fed", and the firmware feeds the watchdog. Today's hardware bound is only the physical drive speed and the reservoir (100-200 U) - far above 15 U/h.

Add an **independent hardware dose budget** that does not trust the MCU:
1. **Option A (cheapest, Rev A board respin): a tiny second MCU (supervisor, e.g. nRF/STM32G0/RP2040-class or a CPLD/MSP430 FRAM part) in the motor-supply path.** It sees *only* the STSPIN220 STCK step pulses and DIR (via the existing step line, tapped), counts steps in a hardware timer window, and **opens the motor supply gate** when the count in any rolling window exceeds a limit set at provisioning (e.g. 16.7 U equivalent steps/60 min and 2 U/min). It has its own clock, no BLE, a ~2 KB audited firmware (Rust, `forbid(unsafe)`, formally verified with Kani: the counter + window is ~100 lines), **latches until a physical power cycle plus button**. Limit values are in its read-only flash and **cannot be raised through any radio interface**. It reports its decision on a GPIO the main MCU reads (so Trio shows `HW_LIMIT`).
2. **Option B (no new MCU): an analogue/TTL budget** - a counter IC (74HC4040 chain) + RC leak is crude and drift-prone; not recommended for a mg-level dose argument.
3. **Option C (Rev B, nRF54L15)**: use the second CPU domain/FLPR RISC-V core as the monitor with separate RAM/flash protection (nRF54L has a RISC-V coprocessor and TrustZone-M); weaker than a separate die because a flash-write/glitch attacker reaches both, but stronger than none. A separate die remains the recommended design for the product.
4. **Independence rules** (what makes it a real barrier): different clock; no shared writable flash; limits provisioned over a separate wired interface (SWD-locked), not OTA; the monitor firmware changes only with the physical bench programmer; its fault output is *also* wired to the TPL5010 `DONE` gating (it can starve the watchdog).
5. **Budget semantic must be a true sliding window** (a ring of 60 one-minute counters aligned to its own timer has the same 61-bucket problem as FINDING-003: use 1-second sub-buckets with a 3600-entry u16 ring = 7 KB, or a leaky bucket with a fill level, which is exactly 15 U/h with no bucket boundary effect; recommended: **leaky bucket** `level += steps; level -= leak*dt; trip if level > capacity`).
6. **What it still does not bound**: dose *within* the budget that is wrongly timed (e.g. 15 U at once). The per-minute rate and per-bolus cap are also enforced by the monitor (two leaky buckets: 1.7 U/min and 15 U/h), so the worst case a fully malicious firmware can deliver is **15 U in the first hour then 15 U/h**; that is an *insulin overdose risk for a human* and exactly why the project never leaves the bench. Using water on a bench, the budget makes the demonstration measurable: the **hardware limiter test** (fault injection) runs on the bench with a balance.

## 5. FINDING-003 (software)
Make the software window a true sliding window or a leaky bucket (same arithmetic as the monitor), or change the spec text to "15 U per wall-clock 60 minutes, at most 16.7 U in any 60 minutes". Decision for the spec owner (`spec/design-parameters.md` section 7: "must never be relaxed silently" - the deviation is *discovered*, so record it and decide).

## 6. Test plan
- `security/verify/tests/safety_props.rs` stays the spec; extend with a `Role`/command-class matrix test and a rate-limit proptest.
- Kani proofs for `approve_steps` bounds (`security/verify/src/kani_proofs.rs`) and, when written, for the monitor firmware (leaky bucket never exceeds capacity; trip is latched).
- Hardware-in-loop fault injection (bench): firmware that deliberately ignores `approve_steps` (test build `unsafe-bench-override`-style, never shipped) while a logic analyser and the balance record the delivered water: the monitor must cut the supply at the budget; measure the actual cut-off latency and the overshoot in steps.
- Physical-confirmation test: dangerous command without button press returns `AUTH`/`NEED_CONFIRM` and has no effect.

## 4a. Rev A partial step: re-arm dead time (discrete logic, bench board)
The existing hardware step budget (HW-A, spec s.7a) bounds a runaway *per arm window*. Because the arm edge (`ARM_CLK`) comes from the MCU, attacker firmware can re-arm after every window. A non-retriggerable long monostable (the board already uses CD74HC221-class one-shots for the SMA pulse limiter, `electronics/bench/pin-assignment.md`) in series with `ARM_CLK`, T = 60 s, ignores arm edges for 60 s after each accepted arm. Effect: worst case per hour drops from "limited only by motor speed" to ~60 windows x ~1.6 U, i.e. a *bounded, measurable* figure (~96 U/h) that the bench can verify with the balance. It is not a substitute for section 4 (still far above 15 U/h) and costs one SOT/TSSOP part plus RC; it must be reviewed against the interlock timing of the controller-board redesign that is in progress (`docs/STATUS.md`).
