> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). OpenPatch v0.1.0 integrated pod. Water only. Never worn, never with insulin or any drug.

# v0.1.0 pod: hardware interlock, over-current cut, HW-A step budget

Rule (unchanged from the bench): **the hardware must be correct even if the software is wrong.** The cut path is discrete logic and MOSFETs only; the MCU can remove permission but never grant it.
Sub-circuits A to C are the final bench blocks (`../bench/INTERLOCK.md`) adapted to the battery supply; D (second series switch) and E (HW-A) are new in v0.1.0.
Simulated with ngspice: `sim/switch_oc_results.md`, `sim/hwa_results.md`, plots `sim/switch_oc.png`, `sim/hwa.png`.

```
MOT_ALLOW = MCU_EN AND LATCH_Q (TPL5010 watchdog latch) AND OC_OK AND ( DOCKED XOR DIR_REVERSE )      [H15] DOCKED = hall A AND hall B
VMOT      = VBAT through TWO series P-FETs (Q4, Q15, common gate PGATE) only while MOT_ALLOW = 1
STCK_DRV  = STCK_MCU through the HW-A budget gate (<= 32 forward pulses per accepted ARM, dead time between arms)
```

## A. Gate network (PGATE)

`PGATE` is pulled to VBAT by **two** 100 k resistors in parallel (R9, R10: one open resistor does not float the gate) plus C11 (100 nF gate-source, soft start). It can only be pulled low through R11 (10 k) and the legs below. **H15 (2026-11-19): forward only when docked, reverse only when undocked** (reverse while docked would aspirate through the cannula): the last leg is an XOR of two parallel series branches.

```
PGATE -R11- Q5 (LATCH_Q) - Q8 (MCU_EN) - Q13 (OC_OK) - +- Q6 (DOCKED_H) - Q21 (FWD)    -+- GND
                                                        +- Q10 (DOCK_NOT) - Q22 (DIR_REV) -+
(DOCK_NOT = inverse of DOCKED_H through Q20/R87; FWD = inverse of DIR_REV through Q11/R12 and R62)
```

| Gate | Source | Unpowered / reset / floating | Meaning |
|---|---|---|---|
| `LATCH_Q` | U6 Q (AUP1G74). Set by an `ARM_CLK` edge. Cleared by `LATCH_CLR_N` low: power-up (R28/C15), MCU (open drain), TPL5010 `RSTn` via D2 | 0 (R17, CLR active at power-up, R29 on ARM_CLK) | armed and the watchdog is alive |
| `MCU_EN` | MCU P0.24 | 0 (R18) | independent enable |
| `OC_OK` | U12 Q_N (block C) | 0 without 3V3; 1 after power-up | no over-current since `MCU_EN` rose |
| `DOCKED_H` | `R21` pull-up, **pulled low by Q7 (hall A not asserted) or Q7B (hall B not asserted) or Q12 (DOCK_TEST)** | 0 (a missing or stuck-open hall reads "not docked") | pod latched: **both** halls must assert (2oo2); gates Q6 (branch 1) and, inverted by Q20, `DOCK_NOT` for Q10 (branch 2) |
| `DIR_REV` / `FWD` | `DIR_REV` = the `MOT_DIR` net itself (R13) or its inverse (R14 instead); `FWD` = its complement (Q11 inverter, R62, or R63 for the R14 variant) | `DIR_REV` 0 and `FWD` 1 (R15/R16: unpowered or floating DIR = forward) | commanded direction; Q22 passes reverse, Q21 passes forward |

`DOCKED_H` is high only when BOTH DRV5032AJ halls pull `DOCK_N`/`DOCK_NB` low. A hall stuck "asserted" (the residual single fault of the bench, `POD.U2 stuck low`) no longer enables undocked forward motion: the other hall still reads not-docked. Stuck "not asserted" blocks delivery (availability, fail safe).
Truth table: identical to the bench (`../bench/INTERLOCK.md`), with `DOCKED = hallA AND hallB`.

| LATCH_Q | MCU_EN | OC_OK | DOCKED (A and B) | DIR | HW-A | VMOT | Situation |
|---|---|---|---|---|---|---|---|
| 0 | x | x | x | x | x | off | not armed / watchdog expired |
| x | 0 | x | x | x | x | off | enable low (reset, crash, safety task) |
| x | x | 0 | x | x | x | off | over-current, until `MCU_EN` is cycled |
| 1 | 1 | 1 | no | fwd | x | **off** | undocked + forward blocked (over-delivery) |
| 1 | 1 | 1 | no | rev | n/a (reverse not counted) | ON | undocked + reverse = draw/refill (the only way reverse is allowed) |
| 1 | 1 | 1 | yes | fwd | window open and budget left | ON, steps pass | docked + forward = delivery |
| 1 | 1 | 1 | yes | fwd | window closed or 32 pulses used | ON, **STCK_DRV held low** | runaway bounded (E) |
| 1 | 1 | 1 | yes | rev | x | **off (H15)** | docked + reverse blocked (would aspirate through the cannula) |

Sim (`sim/switch_oc_results.md`, cases A, D, E, H): docked+forward on, undocked+forward 0.000 V, undocked+reverse on, docked+reverse 0.000 V. Safe default: with 3V3 absent or DIR/hall lines floating, FWD/DOCK_NOT/DOCKED_H are low so both branches are open. A hall missing or one hall stuck-not-asserted reads "undocked": forward off, reverse (draw) possible.
**POST proofs of the two wrong combinations (new, A02a/A02b; docked pod, water, motor free or on the bench load):** A02a docked, `MCU_EN` + latch armed, DIR = reverse: `VMOT_SENSE` must stay below 0.3 V for 50 ms and `PGATE_MON` stay low (blocked). A02b `DOCK_TEST` = 1 (forces undocked), DIR = forward: `VMOT_SENSE` below 0.3 V for 50 ms. Positive controls: docked + forward and `DOCK_TEST` + reverse must reach VMOT above 70 % of VBAT within 30 ms. Failure maps to `1-07-003` (undocked forward passes) and the new request `1-07-008 GATE_DOCKED_REVERSE_STUCK_PASS` (docked reverse passes, latched). Readbacks: `DOCKED_H` (pad 10), own-pin `MOT_DIR`, `PGATE_MON`, `VMOT_SENSE`.

## B. Watchdog and DONE qualifier (bench block B, unchanged)

TPL5010 (U5, about 2 s), latch U6, qualifier U10 (a `WDT_DONE` edge counts only while `WDT_WAKE` is high; stuck, early and late edges are rejected; R33 0 ohm DNP bypass for bring-up). `RSTn` resets the MCU and clears the latch through D2. Honest limit (as bench): a peripheral toggling DONE faster than the window can keep the TPL5010 alive; the other legs and HW-A still bound the motor.

## C. Hardware over-current cut (independent of firmware)

Shunt R44 0.22 ohm between `VMOT_PRE` and `VMOT`; INA180A1 (U9, 20 V/V = 4.4 V per A, supplied from the **switched** `VMOT_RAW`, zero idle drain); output through R48 10 k + C27 10 nF (about 0.1 ms blanking, also protects the 3V3-powered comparator input from the 4.2 V INA swing) into the nano-power comparator **U11 TLV7011** (3V3, 335 nA).
Reference `OC_REF` = 3V3 x 110 k / 210 k = 1.73 V, i.e. **trip at about 0.39 A** (tolerance about +-10 %, 3V3 tracks the cell). The motor needs at most 2 x 160 mA = 0.32 A even when stalled (chopper limit), so a stall (occlusion) does not trip; a bridge or winding short does.
A trip clocks **U12** (`Q_N` = `OC_OK` = 0 opens leg Q13). U12 is cleared only by `MCU_EN` low (R54, C30, D5: the release is delayed about 12 ms after `MCU_EN` rises, which blanks the VMOT inrush; assertion is immediate). `OC_TEST` (Q14) pulls the reference down for POST (trip at about 5 mA), it can only make a trip easier.
Sim (`sim/switch_oc_results.md`): bridge short at 150 ms: `OC_OK` low after 0.09 ms, VMOT below 0.5 V after 4.3 ms; no false trip at start-up or with a stalled motor.

## D. Second series switch and bleeder (new: no USB "last off switch" on battery)

* `Q4` and `Q15` (AO3401A) are in series with a common gate. **A drain-source short of either alone cannot keep VMOT on** (sim cases F and G: VMOT below 0.5 V 5.6 ms after `MCU_EN` falls). Cost: 2 x 60 mohm.
* Common-cause remainder: a short between PGATE and GND (pulling the gate low permanently) is the same as an always-true AND; it is caught by `PGATE_MON` high while a leg is commanded off (POST step 1) and by `VMOT_SENSE`. No fuse is fitted: the cell has its own PCM; a polyfuse would add 0.5 to 1 ohm to the motor path (same decision as bench).
* `Q17` + R24/R25 (2 x 100 ohm) discharge `VMOT` whenever PGATE is high (supply off): VMOT below 0.5 V within 5.4 ms (limit 20 ms).
* Soft start: C11 + R11 give a gate time constant of about 1 ms; with the 12 ms over-current clear delay there is no inrush trip (sim A: peak battery current 580 mA during the 2 to 3 ms charge of 32 uF, blanked).

## E. HW-A: arm window, 32-pulse step budget, re-arm dead time (new, spec 7a)

```
ARM_CLK --> U13 (window FF, set on the rising edge)  --> WIN, WIN_N
WIN_N --R59||R60 (500 k)--> TN --C33 1 uF--> GND ; TN --> U14 Schmitt buffer --> TS --> U13 CLR (TS low = window over AND dead time)
U15 (6-stage ripple counter, reset by WIN_N)  counts CNT_CLK falling edges; Q6 = HWA_FULL after 32 pulses
X = WIN AND NOT FULL (U16)   Y = DIR_REV OR X (U17)   STCK_DRV = STCK_MCU AND Y (U18)   CNT_CLK = STCK_DRV AND FWD (U19)
```

* Window about 0.6 s (0.27 to 0.83 s over tolerance); during the window and the dead time after it (RC recharge from VT- to VT+, 0.03 to 0.53 s) further `ARM_CLK` edges are ignored (CLR dominates). Minimum distance between two accepted arms 0.32 s (`sim/hwa_mc_results.txt`; sim nominal cycle 0.85 s). A stuck-high `ARM_CLK` opens exactly one window.
* Only **forward** pulses are counted and limited (`FWD` = inverse of `DIR_REV`); reverse is free so draw/refill (500-step chunks) works and a reverse excursion cannot deliver.
* Bound: 32 pulses = 0.126 U (16:20, 3.951 mU/step) per accepted ARM. Runaway with `STCK` 1 kHz and `ARM_CLK` 1 kHz for 4 s (sim S2): **224 pulses = 0.89 U** (nominal, 7 windows); worst case over tolerances and a 4 s TPL5010 interval: **416 pulses = 1.64 U** (16:20), 2.06 U on the 18:18 pair. Sustained rate bound 15 to 24 U/min; this is **not** an hourly limit (HW-B stays a Rev B item, `security/proposals/07`): proposal 07 section 4a's 60 s dead time would bound the hour at 7.6 U but forbids the 1.5 U/min bolus (needs 3.4 to 6.3 steps/s sustained), so it is **not** implemented; the RC (R59/R60/C33) is the knob.
* Defaults off: counter held in reset and window closed at power-up (TS low until TN has charged, about 1 s); `STCK_MCU` has a 100 k pull-down.
* HW-A does not cut the supply; it holds the step clock. A stuck-high gate output (U18) is detected by `HWA_FULL`/TIMER1/TMAG mismatch in POST-A A12.

## F. Safe defaults

| Condition | Result |
|---|---|
| Power-up before the MCU runs | `LATCH_Q` 0, `MCU_EN` 0, HW-A window closed, DOCKED 0 until both halls assert: **VMOT = 0**, `STCK_DRV` low |
| MCU reset / brown-out / pins floating | pull-downs on MCU_EN, ARM_CLK, DIR, STCK, DOCK_TEST, OC_TEST; RSTn clears the latch; PGATE is pulled to VBAT: **VMOT = 0** |
| 3V3 lost, VBAT present | all legs open (FET gates fall), PGATE high: VMOT 0 |
| Cell removed / PCM open | everything off |
| Hall missing, cracked solder, magnet absent | `DOCK_N` pulled high = not docked: forward blocked |

## G. Residual single faults (what is NOT stopped in hardware)

| Fault | Effect | Detection |
|---|---|---|
| Common-mode: PGATE shorted to GND | supply on whenever VBAT present; stepping is still limited by HW-A (32 per window) and the driver STBY (100 k pull-down) | `PGATE_MON` high / `VMOT_SENSE` while commanded off (POST step 1) |
| Q4 and Q15 both shorted (double fault) | as above | same |
| U18 output stuck high (HW-A lost) | budget lost, interlock legs remain | A12 |
| STSPIN220 STBY pulled high by a short and STCK static | no stepping | `MOT_EN_FAULT`, TMAG |
| Dose within the budget at the wrong time (15 U/h, 1.7 U/min) | hardware does not bound it | firmware supervisor; HW-B Rev B |

> **Sections A to G describe the monolithic reference board (`netlist.py`, discrete HW-A).** The decided split design (`netlist_v2.py`, boards MAIN / USB / SENSOR) replaces the TPL5010, DONE qualifier, interlock latch and all discrete HW-A logic by the supervisor MCU of section H. Everything else (gate legs Q8/Q13/Q6/Q10, both series P-FETs, OC comparator + latch U11/U12, 2-of-2 halls, bleeders, readbacks) is unchanged. In v2 the series switch **Q4 is cut by the discrete legs** (MCU_EN, OC_OK, dock/DIR) and **Q15 by the supervisor** (`SUP_PERMIT` through QS), so no single controller or single FET can keep VMOT on.

## H. Supervisor MCU (v2): firmware specification

**Part:** STM32C011F4P6, TSSOP-20 (`C5452432`, JLC stock 238, $1.47; chosen over the MSP430FR2000 `C2053947`, QFN 3 x 3, stock 135, because the FR2000 has only 0.5 kB FRAM, too little for the state machine plus the buckets, and Embassy/Rust supports the STM32C0). Own supply decoupling (C50/C51), internal HSI clock (no shared crystal), own flash, **independent watchdog IWDG enabled in the option bytes** (cannot be switched off by software), BOR on, **read-out protection level 1**, programmed only through the SWD pads J4/J5/J6 (+ GND pad) at provisioning, never over a radio or USB. No radio, no parser, no heap; firmware limited to counters, comparisons and a UART frame of 8 bytes; Rust `no_std`, application crate `#![forbid(unsafe_code)]`, state machine host-tested and Kani-checked (budget never exceeded, outputs low in every error state).

**Pins (TSSOP-20 pin = function):**

| Pin | Name | Net | Dir | Function |
|---|---|---|---|---|
| 4 / 5 | VDD / VSS | 3V3 / GND | | 100 nF + 1 uF |
| 6 | NRST | `SUP_NRST` | in | 100 k pull-up, SWD pad J6 |
| 7 | PA0 | `ARM_CLK` | in (EXTI rising) | arm request from the main MCU (the same edge the bench latch used) |
| 8 | PA1 | `STCK_MCU` | in (EXTI rising) | step clock from the main MCU, **counted here** (<= 1 kHz, polled/EXTI) |
| 9 | PA2 | `DIR_REV` | in | direction at the gate; budget counts only forward (`DIR_REV` low) pulses |
| 10 | PA3 | `OC_OK` | in | over-current latch (hardware U12); low = tripped |
| 11 | PA4 | `SUP_STCK_EN` | out | to the AND gate U31: `STCK_DRV = STCK_MCU AND SUP_STCK_EN`; 100 k pull-down (default blocked) |
| 12 | PA5 | `SUP_PERMIT` | out | drives QS: high pulls `PGATE2` low = Q15 conducts; 100 k pull-down (default off) |
| 13 | PA6 | `SUP_OK` | out | status to the main MCU (high = armed/healthy) |
| 14 | PA7 | `NRST` (main) | out, open drain | pulls the main MCU reset low (watchdog reset) |
| 16 | PA11 [PA9] | `SUP_TXD` | UART TX | to the main MCU (USART1 TX remapped, 115200 8N1) |
| 17 | PA12 [PA10] | `SUP_RXD` | UART RX | from the main MCU |
| 18 / 19 | PA13 / PA14 | `SUP_SWDIO` / `SUP_SWDCLK` | | SWD pads J4 / J5 |
| 1 | PB7 | `MCU_EN` | in | monitored enable |
| 20 | PB6 | `DOCKED_H` | in | monitored dock gate level |

**States and timing (1 kHz tick, all limits are `const`, no runtime configuration, not changeable over any link):**

| State | Outputs (`PERMIT`, `STCK_EN`, `SUP_OK`) | Entry / exit |
|---|---|---|
| `BOOT` | 0, 0, 0 | power-up/IWDG/BOR reset; 200 ms self-check (pull-down levels, `OC_OK` high, `STCK_MCU` idle low); then `LINK_WAIT` |
| `LINK_WAIT` | 0, 0, 0 | waits for a valid response frame within 5 s; fails -> pulse `NRST` of the main MCU low 50 ms, retry (max 5, then `LOCKED`) |
| `IDLE` | 0, 0, 1 | healthy link; challenge/response every 500 ms |
| `ARMED` | 1, 1, 1 | entered on a rising `ARM_CLK` **only if** link ok, `MCU_EN` high, `OC_OK` high, (`DOCKED_H` or `DIR_REV`), HW dead time over, hourly/minute buckets below their limit. Window 600 ms, budget 32 forward `STCK_MCU` pulses (counted by EXTI); `STCK_EN` falls after the 32nd pulse (the gate is closed before the 33rd edge, <= 5 us after the count) |
| `DEAD` | 0, 0, 1 | after the window or the budget: 400 ms during which `ARM_CLK` is ignored; minimum arm-to-arm distance 1.0 s |
| `FAULT` | 0, 0, 0 | any of: missing/wrong response twice in a row (-> also pulses main `NRST`), `OC_OK` low, `MCU_EN` or the dock-xor-dir condition lost (docked and reverse, or undocked and forward), a forward pulse counted outside `ARMED`, bucket overflow, internal inconsistency. Leaves `FAULT` only after 2 s with all inputs quiet and a fresh response (not for bucket overflow and not after `LOCKED`) |
| `LOCKED` | 0, 0, 0 | bucket overflow, 5 link failures, or 3 faults in 10 min: stays until power cycle (battery out) **and** a button press seen by the main MCU (`GetStatus`) |

Permission drops within 1 ms of any input change (EXTI on `MCU_EN`, `OC_OK`, `DOCKED_H`, `DIR_REV` rising/falling) and the supervisor never raises an output from `FAULT`/`LOCKED` without a state transition. Reverse pulses are not counted (draw mode, POST reverse excursions).

**Watchdog challenge/response (replaces TPL5010 + DONE qualifier + latch):** supervisor sends `[0xA5, seq, ch0, ch1, ch2, ch3, crc8]`; the main MCU must answer within 20 ms with `[0x5A, seq, crc16(ch XOR K[seq mod 16])]` and a status byte (its `MCU_EN` intent, steps requested in this tick). `K[]` is a public 16-entry table in both firmwares: it detects a hung or looping main MCU (a stuck loop cannot compute it), not an attacker; the attacker case is bounded by the buckets and the discrete legs. Two consecutive failures -> `FAULT` + main reset (`NRST` low 50 ms).

**Dose buckets (HW-B of `security/proposals/07`, pulled in):** leaky buckets on the counted forward steps: **15 U/h** = 3796 steps capacity, leak 1.05 steps/s; **1.7 U/min** = 430 steps capacity, leak 7.2 steps/s (16:20 drive, 3.951 mU/step; the 18:18 pair needs 3036 / 344 steps, selected at provisioning by a compile-time constant, **not** over the air). Exceeding a bucket -> `LOCKED`. These limits equal the firmware limits of spec section 7, the supervisor does not know about boluses or schedules.

**Status frame (supervisor -> main, every 500 ms and on every state change):** state, last fault reason, window pulses counted, bucket levels, `ARM_CLK`/`STCK_MCU` edge counters; the main firmware turns it into diagnostic records (proposed `1-0F-*`: SUP_LINK_LOST, SUP_BUDGET_HIT (info), SUP_FAULT, SUP_LOCKED (latched), SUP_BUCKET_OVERFLOW (latched), SUP_COUNT_MISMATCH = main `TIMER1` count differs from the supervisor count by more than 2).

**Independence argument:** diverse core and vendor (Cortex-M0+ STM32C0 vs Cortex-M4 nRF52840), own clock, own flash with RDP, separate decoupling, wire-only provisioning, no shared writable memory, outputs default to no permission through external pull-downs; the supervisor is **one more AND leg** (Q15) and the STCK gate, so a supervisor that is wrong in the permitting direction still meets the discrete MCU_EN / OC / dock-DIR legs on Q4, and a runaway main MCU is bounded by the 32-pulse windows and the buckets. Residual common cause: the shared 3V3 LDO and the battery (both fail safe: all gates open), and the same engineer/toolchain family (mitigated by separate review). Software item class C (IEC 62304 view in `regulatory/SOFTWARE`): the supervisor firmware must be listed as its own software item.

**USB must not bypass authorisation:** USB (CDC log, DFU) is a transport of the main MCU only; the supervisor pins have no connection to USB or SWD of the main MCU; the main firmware applies the same authenticated session layer on USB as on BLE and stops delivery while `VBUS_SENSE` is high.
