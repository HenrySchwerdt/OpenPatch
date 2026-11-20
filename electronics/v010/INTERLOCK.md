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

---

## I. CUP pod v4 (`design/netlist_v4.py`, single board `cup/`): hardware vs supervisor split (decision 2026-11-19, `DECISION-omnipod-lessons.md`)

Supersedes sections A to F for the cup pod; sections G and H still apply (the supervisor of H is unchanged except for two new pins). The rule stays: **the hardware must be correct even if the software is wrong**: a minimal pure-hardware cut path remains, everything else moved into the independent supervisor MCU (STM32C011) to save about 25 discrete parts.

```
VMOT = VBAT -- Q4 (gate PGATE) -- Q15 (gate PGATE2) -- VMOT_RAW -- shunt R44 -- VMOT
Q4  conducts only if  LATCH_Q (U6, set by ARM_CLK, cleared by TPL5010 timeout / supervisor reset / over-current)
                  AND MCU_EN (main MCU, own leg)
                  AND ( DOCKED_H  OR  MOT_DIR[reverse] )          chain: PGATE -R11- QL - QE - (QD || QR) - GND
Q15 conducts only if  SUP_PERMIT (supervisor, through QS)          independent second series switch
```

| Element | v3 (MAIN/POWER) | v4 (CUP) | Where the function lives now |
|---|---|---|---|
| Latch + watchdog | none (supervisor challenge/response only) | **TPL5010 (U5) + latch (U6) back in hardware**; U5 watches the **supervisor** (`SUP_DONE` after `SUP_WAKE`, 2 s), a missing DONE pulls `SUP_NRST` low: resets the supervisor and clears the latch | hardware, independent of both MCUs' firmware |
| `MCU_EN` leg | Q8 | QE (kept: rule "MCU enable AND watchdog") | hardware |
| Dock leg | Q6 + XOR network (Q10, Q20, Q21, Q22, Q11) = `DOCKED XOR DIR_REV` (H15) | QD (`DOCKED_H`) **OR** QR (`MOT_DIR` reverse): forward undocked blocked, reverse undocked allowed (refill / draw), **docked + reverse is NOT blocked in hardware any more** | undocked-forward: hardware; **H15 docked-reverse: supervisor (`FAULT` when docked and reverse) + firmware + POST A02a only** |
| Over-current | INA180 + TLV7011 + U12 latch + Q13 leg + OC_TEST | INA180 + TLV7011 (trip about 0.39 A) whose output (`OC_OK` low) goes through the AND gate U32 into `LATCH_CLR_N`: **a trip clears the latch in hardware** (about 0.1 ms blanking); no own latch, no Q13 leg, no OC_TEST | hardware trip; lock-out of re-arming (2 s) in the supervisor (`OC_OK` falling edge -> `FAULT`) |
| 2oo2 halls | two DRV5032 + Q7/Q7B NOR | **single hall** centred on the dock magnet | a second hall cannot see a d1 x 0.5 magnet (Bz of a dipole changes sign about 1 mm off axis at 0.7 mm height), so 2oo2 is dropped; a hall stuck asserted now lets the dock leg pass **undocked forward**: still blocked by latch, `MCU_EN` and Q15; the stuck hall itself is NOT detected by hardware (the supervisor only sees the same `DOCKED_H` level; POST A02b with `DOCK_TEST` proves the gate path, not the sensor); **open items: firmware plausibility check (docked while the wear/handshake state says undocked) and, for the mechanics, a second magnet + hall pair** |
| Step budget | U31 AND gate with `SUP_STCK_EN` + supervisor counter | unchanged | hardware gate, supervisor decides |
| Series switches | Q4, Q15 | unchanged (gate of Q15 owned by the supervisor through QS) | |
| Bleeders | Q17, Q17B | unchanged | |
| Readbacks | PGATE_MON, SENSE_EN divider, NTC | `LATCH_Q` on pad 4 (RB6), `VMOT_SENSE`, `OC_OK`, `DOCKED_H`, own pins; VBAT sense is an always-on 4.7 M / 4.7 M divider (0.4 uA); NTC dropped (cell has its own PCM) | |
| Boost | MT3608 5 V (DNP/optional) | **populated, TPS61023 (see I.2)**: VBAT - Q4 - Q15 - `VMOT_RAW` - boost - `VMOT_PRE` (about 4.96 V) - shunt - `VMOT`; boost EN on the switched `VMOT_RAW` (zero idle drain, cut by the interlock switches) | |

Truth table of the hardware path (per leg):

| LATCH_Q | MCU_EN | DOCKED_H | MOT_DIR | SUP_PERMIT | VMOT |
|---|---|---|---|---|---|
| 0 | x | x | x | x | off |
| x | 0 | x | x | x | off |
| 1 | 1 | 0 | 0 (fwd) | x | **off (undocked + forward)** |
| 1 | 1 | 0 | 1 (rev) | 1 | on (undocked + reverse: refill / draw) |
| 1 | 1 | 1 | 0 | 1 | on (docked + forward: delivery) |
| 1 | 1 | 1 | 1 | x | **hardware passes, supervisor withholds `SUP_PERMIT` (H15)** |
| 1 | 1 | x | x | 0 | off (supervisor leg) |

Supervisor pins added on UFQFPN-20: pin 2 `SUP_DONE` (out, to TPL5010 DONE), pin 3 `SUP_WAKE` (in, TPL5010 WAKE, EXTI): **assignment to be verified against DS13866**. The supervisor keeps its `FAULT`/`LOCKED` behaviour of section H; `OC_OK` is now the raw comparator output (no latch), so the supervisor must treat any falling edge as a trip (it already does).
Safe defaults: `SUP_NRST` low (power-up, reset, TPL5010 timeout) clears the latch (U32), `LATCH_Q` has a pull-down, `MCU_EN`, `MOT_DIR`, `SUP_PERMIT`, `ARM_CLK`, `DOCK_TEST` have pull-downs, PGATE/PGATE2 are pulled to the supply: **VMOT = 0** in every unpowered, floating or reset state.
Honest limits of the reduction: (1) docked reverse is software-only (hazard H15 class: aspiration through the cannula, water only on this project); (2) over-current re-arming is blocked by the supervisor, not by an own hardware latch (an ARM_CLK edge from a runaway main MCU can re-arm Q4, Q15 still needs the supervisor); (3) a single dock hall; (4) the TPL5010 now watches the supervisor, the main MCU is watched by the supervisor's challenge/response as before.

### I.1 Open items of the v4 reduction (coordinator list, 2026-11-19)

* **(a) Stuck-asserted dock hall.** Firmware plus supervisor plausibility check: `DOCKED_H` must toggle on every undock/dock cycle (cannula release, pod swap, refill with the pod off the dock); a hall that has not changed level since the last known undock event, or reads docked while the wear/handshake state says undocked, is never trusted: forward motion is withheld (`SUP_PERMIT` low) and a diagnostic is raised. Not implemented yet.
* **(b) Supervisor test vector for H15 (reverse while docked).** The hardware dock leg is an OR and passes docked + reverse, so the supervisor firmware needs a host-test and a bench vector: inputs `DOCKED_H`=1, `MOT_DIR`=1 (reverse), `MCU_EN`=1, latch armed: expected `SUP_PERMIT` stays 0 within 1 ms (state `FAULT`), `VMOT_SENSE` below 0.3 V for 50 ms (POST A02a); positive controls: docked + forward permits, undocked + reverse permits. Must also hold for a `DOCKED_H` glitch during reverse. Not implemented yet.
* **(c) Why the second dock hall was dropped.** The dock magnet is d1 x 0.5 mm and the hall sits about 0.7 mm from it. The axial field Bz of a small dipole is proportional to (3 cos^2 t - 1) / r^3 and changes sign at t = 54.7 degrees, i.e. about 1.0 mm lateral offset at 0.7 mm height; a second DRV5032 (1.1 x 1.4 mm package) beside the first cannot sit closer than about 1.8 mm and would see no field or the wrong sign, and a hall on the top side of the 0.8 mm board sees about 5 % of the field. **A DNP footprint for a second hall was not added: there is no position on this board where it would see the magnet.** The fix is mechanical (a second magnet plus hall pair, or a larger magnet); until then single hall plus items (a) and (b).


### I.2 Motor supply for the locked NFP-608-26.45-SGM (4.8 V, 26.5 ohm/phase, 0.18 A/phase)

* **Boost**: TI **TPS61023DRLR** (LCSC `C919459`, SOT-563 1.6 x 1.6, 3.7 A switch, 0.5 to 5.5 V in, about 1 uA off, about 90 % at 0.3 A; better than the MT3608: synchronous, no external diode, 1 uH inductor). Inductor **Sunlord WPN252012E1R0MT** (`C370610`, 1 uH, 2.5 x 2.0 x 1.2), FB divider 220 k / 30 k -> 4.96 V. EN and VIN on the switched `VMOT_RAW`, so the interlock switches cut the boost input; the output caps are bled by R24/R25 through Q17/Q17B when the supply is off (time constant about 5 ms). 6.2 V clamp DZ1 stays on `VMOT_PRE` (a floating FB would otherwise run the output up). The over-current shunt now sees the **output** current (trip 0.39 A at 5 V = about 0.55 A from the cell).
* **Bulk**: 3 x 47 uF 0805 X5R 6.3 V (`C7503494` CGA0805X5R476M6R3MT, 1.25 mm class) + 10 uF on `VMOT_PRE`, before the shunt (no charging inrush through the shunt): 141 uF nominal, **about 50 uF effective at 5 V DC bias**. A 100 to 220 uF low-ESR part under 1.3 mm was not found at JLC (no 1.2 mm polymer/tantalum in stock); MLCCs are the only option here.
* **Driver current limit**: R38 5.6 k -> VREF 0.175 V, 1.0 ohm sense, **about 0.175 A per phase** (datasheet formula VERIFY).
* **Cell current (90 mAh Ampul 301030, `battery-selection.md`)**: motor at full step draws 2 x 0.175 A = 0.35 A at 4.96 V = 1.74 W; with the boost at 88 % the cell supplies 1.98 W: **0.58 A at 3.4 V, 0.66 A at 3.0 V (peak = average during a step burst, 6 to 7 C on a 90 mAh cell)**; with the coordinator's 0.3 A figure 0.50 A. **The bulk capacitor does not change this**: 50 uF x 0.5 V swing carries 0.35 A for only 0.07 ms, so the cell sees the same 0.5 to 0.6 A average during a burst with or without it; what the capacitors do is remove the chopper ripple and the boost's inductor-current pulses from the cell (input cap C24 10 uF) and carry the step transients. Without the bulk the cell additionally sees about 1 A inductor-peak ripple at the boost frequency; the bulk adds a start-up charge of about 0.7 mC (a few ms, soft-start limited). Cell internal resistance about 0.5 to 1 ohm sags the terminal 0.3 to 0.6 V under load. **Mitigation is duty cycle, not capacitance**: delivery steps are short bursts (a 1.5 U/min bolus needs 3 to 6 steps/s, each a few ms), average motor current about 17 mA; the firmware must not hold full current, use the STBY/hold current feature between steps, and limit burst length. Whether the 301030 PCM trips at 0.6 A is **unverified** (listing says nothing about the discharge rating).
* **Thrust at a 3.4 V cell with boost**: the boost holds 4.96 V (at least the 4.8 V rating) down to a cell terminal voltage far below 3.4 V, so the motor delivers its rated torque limited by the chopper: 0.175 / 0.18 = 97 %, **about 8.4 N at the plunger** (8.6 N at full rated current, `V010-CUP.md`) against 5.2 N needed (1.6x). Without the boost the motor would see about 2.4 V and a quarter of the power.
* **Undervoltage lockout (kept)**: firmware refuses motor starts below about **3.4 V open circuit** (cell sag under 0.6 A plus the PCM cut-off at 2.5 to 2.9 V leave no margin below that); `VBAT_SENSE` is sampled at rest and again after the first step; see `FIRMWARE-PINMAP.md`.

### I.3 Part-count reduction of the CUP board (2026-11-20): 132 -> 98 parts (placements incl. pads)

| Block | before | after | What changed |
|---|---|---|---|
| sw (switch + legs + bleeders) | 19 | 14 | **`MCU_EN` hardware leg removed**; second 100 k gate pull-up and gate cap C60 removed; second bleeder resistor removed; DOCK_TEST (Q12, R22) removed |
| oc | 14 | 10 | C25, C28, R51, C32 removed; reference divider 1M/1M (trip about 0.375 A) |
| drv | 14 | 11 | C20, C22, C23 removed, one 22 uF 0805 |
| ui | 9 | 7 | one anode resistor for the RGB LED instead of three; sounder + flyback diode are **DNP** (4 x 4 x 2.0 mm, the smallest at JLC; nothing <= 1.5 mm exists) |
| usb | 9 | 6 | ideal-diode P-FET QU1, RU3 and CU2 removed (VBUS has the TVS and the charger input protection) |
| chg | 6 | 2 | VBUS divider removed (USB detect by the module's VBUS pad), PROG as one resistor, one capacitor |
| wdt / sup | 9 + 7 | 6 + 5 | R27, R17, C14, C52, C51 removed |
| swd + tp | 7 + 6 | 6 + 2 | SUP_NRST pad, UART and ARM_CLK test pads removed |
| others | | | cell pad, rear pads, LDO input cap, 2 boost bulk caps instead of 3 |

**Safety changes caused by this reduction (all documented here and in FMEA.md):**
1. **The main-MCU enable is now the latch itself.** The pure-hardware cut path is exactly: `Q4 conducts only if LATCH_Q (set by an ARM_CLK edge of the main MCU, cleared by the TPL5010 watching the supervisor, by a supervisor reset or by the over-current comparator) AND (DOCKED_H OR MOT_DIR[reverse])`, in series with Q15 (supervisor). `MCU_EN` stays a **supervisor input** (the supervisor withholds `SUP_PERMIT` whenever `MCU_EN` is low), no longer a gate leg: the main MCU can no longer remove motor permission in pure hardware, only through the supervisor; CLAUDE.md's "MCU enable AND watchdog" is met by latch (armed by the main MCU) AND TPL5010, which was the coordinator's instruction.
2. **DOCK_TEST removed** (POST A02b "force undocked" and the DOCKED_H pull-down test): the gate path is then proven by removing the magnet / docked-undocked cycle, not by a firmware pin. Open item: POST step using the user's dock/undock action.
3. One gate pull-up resistor instead of two: **a single open pull-up lets the P-FET gate float**; the gate cap C11 and the leg chain still pull it up through R11 only while all legs conduct; an open R9 with all legs closed gives the same state as before; with R9 open and a leg open the gate floats (not driven low by anything, leakage only): accepted for a lid-open bench pod, detected by `VMOT_SENSE` while commanded off.
4. VMOT bleeder has one 100 ohm resistor (time constant about 5 ms with the 22 + 10 uF + 2 x 22 uF caps instead of 2.5 ms).
5. The over-current trip stays on the same latch; trip point 0.375 A; no `OC_TEST` (unchanged since I).
6. Dock hall = **DRV5032FA** (push-pull, `C2152496`), no pull-up.
Previous variants: `design/netlist_v4_unreduced.py` (132 parts).

### I.4 Programming without a debug connector (2026-11-20): deviation from supervisor independence

* **No header, no Tag-Connect, no cable.** Bare SWD test pads only, 0.8 mm, zero parts: `SWDIO`, `SWDCLK`, `NRST`, `GND`, `3V3` of the ISP1807, for the one-time bootloader flash (pogo pins or clip). The supervisor has **no SWD pads** (the former `SUP_SWDIO`/`SUP_SWDCLK`/`SUP_NRST` pads are removed).
* **All later nRF firmware updates: signed USB DFU** through the USB-C receptacle (`USB_DP`/`USB_DM` to the module pads 8/10 through the USBLC6 ESD array, `VBUS_P` to pad 12 = the VBUS sense the nRF52840 needs). Routing rule: D+/D- as a 90 ohm differential pair, shortest path, on one layer next to a GND plane (see `cup/ROUTING-GUIDE.md`).
* **Supervisor (STM32C011) is programmed from the nRF through the ST system bootloader**: nRF pad 47 `SUP_BOOT0` drives the BOOT0 strap (supervisor pin 19, 100 k pull-down R79 for normal boot), nRF pad 49 `SUP_NRST` pulls the supervisor `NRST` (open drain; the same net is driven by the TPL5010 and the AND gate U32, so **a programming reset also clears the latch**), the existing UART `SUP_TXD`/`SUP_RXD` (pads 27/29) carry the bootloader protocol (PA9/PA10 remap) at 115200. Read-out protection and option bytes stay as in section H.
* **Rule: the nRF may re-flash the supervisor only while the motor supply is cut.** Entering bootloader mode (`SUP_BOOT0` high + `SUP_NRST` pulse) holds the latch cleared (U32) and `SUP_PERMIT` low (pull-down R82), so Q4 and Q15 are both open; the main firmware must refuse the update when `VMOT_SENSE` is above 0.3 V, when docked, or when a delivery is active, and must verify a signature of the supervisor image before entering the bootloader.
* **Deviation (accepted for a bench test project, never worn):** the supervisor is no longer independent of the main MCU firmware: the main MCU (or an attacker with a signed update path) can replace the supervisor image, so the supervisor protects against main-firmware bugs at run time but not against a malicious or faulty update. Mitigations: signed images, update only with the supply cut, supervisor read-out protection level 1 stays (the bootloader needs RDP 0: **RDP 1 must be re-set by the supervisor image itself after each flash**, open item), a power cycle is needed after the update.
* Removed parts in the reduction report: SWD pads for the supervisor (2), UART/ARM_CLK/test pads; added: R79 and the SWD 3V3 pad (net -0 parts: 98 before, 98 after).

### I.5 Simplification: one current-limited load switch instead of the discrete motor switch and the comparator chain (2026-11-20, `design/netlist_v4.py`; previous 100-part version `netlist_v4_pre_loadswitch.py`)

```
VBAT -> boost TPS61023 (EN = SUP_PERMIT, supervisor)  -> VMOT_PRE (4.96 V)
VMOT_PRE -> TPS2553 load switch (EN = MOT_ALLOW, hardware)  -> VMOT -> STSPIN220 VS
MOT_ALLOW = LATCH_Q AND ( DOCKED_H OR MOT_DIR[reverse] )     U33 (OR) + U34 (AND), 3V3 powered, EN pull-down R90
FAULT of the TPS2553 (open drain, low while the current limit is active longer than the deglitch) = OC_OK -> U32: LATCH_CLR_N = SUP_NRST AND OC_OK -> clears the latch
```

* **Parts removed (all existed only for the discrete switch / comparator):** Q4, Q15, R9, C11, R11, R83, R84, the four dual NFETs QD1 to QD4 (latch, dock, reverse and supervisor legs, both bleeder FETs, hall inverter pairing), shunt R44, INA180 U9, filter R48 + C27, TLV7011 U11, reference divider R49 + R50, boost input cap C24. **Added:** TPS2553DBVR U20 (`C55266`), R_ILIM 56 k, FAULT pull-up, OR gate U33, AND gate U34, EN pull-down, two 10 k bleeders, single hall inverter Q7. **Part count 100 -> 91** (sw 14 -> 12, oc 10 -> 2, ui +1 for the single sounder NFET).
* **Current limit (TI datasheet table, -40 to 125 C):** R_ILIM 49.9 k gives 475 / 520 / 565 mA (min / typ / max), 210 k gives 110 / 130 / 150 mA, 20 k gives 1200 / 1295 / 1375 mA. Scaling the 49.9 k row by 49.9/47 for **R_ILIM = 47 k (changed from 56 k in I.6)** gives **about 504 / 552 / 600 mA**, plus 1 % resistor tolerance: **0.50 to 0.60 A**. The motor needs 2 x 0.16 A = 0.32 A at the 5.1 k VREF set point (0.35 A at 0.175 A per phase), so the minimum limit (0.42 A) stays above the motor maximum with a 1.2x margin; the start-up inrush into the 22 uF on `VMOT` is limited by the switch soft start and the 0.42 A limit (22 uF x 5 V = 0.11 mC, about 0.3 ms, far below the 7.5 ms deglitch), so it does not raise FAULT. A stall (chopper limited) does not reach the limit; a bridge or winding short is limited to 0.42 to 0.51 A (5 V side, about 0.7 to 0.85 A at the cell), responds in 2 us (short circuit) and is reported on FAULT after the **7.5 ms typical** overcurrent deglitch. The switch is on the **boost output**, i.e. it limits the motor current, not the cell current; the cell-side peak (about 0.58 A at 3.4 V) is set by the motor and the boost, not limited separately (cell protection circuit).
* **What the hardware cut path is now:** EN of the load switch = `LATCH_Q AND (DOCKED_H OR MOT_DIR)` (pure hardware, powered from 3V3: an unpowered or reset gate pair gives MOT_ALLOW = 0, R90 pulls EN low); independent second cut: the supervisor holds the boost EN (`SUP_PERMIT`, R82 pull-down). Single faults: load switch short -> boost still off by the supervisor; supervisor wrong in the permitting direction -> load switch EN still needs latch AND docked. The old series P-FET pair, the 12 ms OC blanking and the discrete OC latch are gone.
* **Over-current in hardware:** FAULT low pulls `OC_OK` low, U32 clears `LATCH_Q` (same latch as before), the supervisor sees the falling edge and goes to `FAULT`. Differences against the comparator chain: the trip is the **limit-active + deglitch (7.5 ms typ)** not 0.1 ms, the current is limited (not cut) during the deglitch, and the limit tolerance is wider (0.42 to 0.51 A). The TPS2553 also has thermal shutdown; with FAULT it re-tries automatically unless the latch is cleared (it is: re-arming needs a new ARM_CLK edge and the supervisor holds FAULT for 2 s).
* **Lost observability (not safety):** no motor current readback by shunt/INA (`I_SENSE`); the nRF now reads `SNSA` (the 1 ohm sense resistor of phase A, 0 to 0.18 V) on ADC pad E6 for stall/occlusion trends; `VMOT_SENSE` (100 k/100 k) stays. OC_TEST and the 0.39 A comparator trip are gone (no POST A09; the limit is proven by a bench short through a resistor).
* **Not a safety relaxation:** watchdog latch, DOCKED gate, hardware over-current action on the latch and the supervisor permission are all kept. Honest changes: (1) the H15 docked-reverse block stays software-only (as I.0), (2) two series switches became one switch plus the boost EN (the boost EN is a second, independent cut, but the boost output caps and the VMOT caps are only bled through 10 k, time constants 0.3 s and 1.5 s, instead of 5 ms through the MOSFET bleeders; the switch blocks reverse current when disabled), (3) the trip latency.


### I.6 Motor driver DRV8835 instead of STSPIN220 (2026-11-20)
* **Why it works without a chopper:** the NFP-608 coil is 26.5 ohm per phase. At 4.96 V (boost) and about 1 ohm of bridge resistance the current is resistance limited: 4.96 / 27.5 = **0.18 A per phase**, 0.36 A with both phases on; worst case (coil -10 %, 5 V + 3 %): 5.1 / 24.9 = 0.205 A per phase = **0.41 A**. That is below the TPS2553 minimum limit with **R_ILIM changed to 47 k: 0.50 to 0.60 A** (it was 0.42 min with 56 k: the margin was only 3 %). Thrust: unchanged (0.18 A at full steps, 8.6 N class).
* **DRV8835DSSR** (`C129328`, WSON-12 2 x 3 mm, TI SLVSB18H read in full for pins, modes and limits): VM 0 to 11 V (here VMOT from the TPS2553), VCC 2 to 7 V (3V3), 1.5 A per bridge, PHASE/ENABLE mode with MODE tied to VCC (`ENABLE` low = both outputs low = brake; direction by `PHASE`), VM and VCC bypass 0.1 uF minimum plus the 22 uF bulk. No sense pins, no current limit, no fault output: nothing else needed.
* **Hardware cut path unchanged:** no VM (load switch EN low) means no motion whatever the four GPIOs do; in addition the supervisor can **brake** both bridges through the two AND gates (`AENBL = AENBL_MCU AND SUP_STCK_EN`, `BENBL = ...`): enable low shorts both windings (no torque change, no step).
* **Supervisor motion monitoring:** the supervisor no longer sees a step clock. It watches `APHASE` (pin 8) and `BPHASE` (pin 18) with EXTI: **each full step toggles exactly one PHASE line** (sequence A+B+, A-B+, A-B-, A+B-), so steps = transitions of A + transitions of B; the direction is decoded from the order of the transitions and **must agree with `MOT_DIR`** (the reverse-intent line of the hardware gate), otherwise `FAULT`. The step budget (32 steps per armed window), dead time and leaky buckets of section H count these transitions instead of `STCK_MCU` edges; `SUP_STCK_EN` low brakes the bridges before the 33rd step. Pin 18 was `SUP_SWDIO` (freed).
* **Occlusion / current:** the primary detection stays the TMAG angle shortfall; the **current-rise warning is dropped**: a single shunt would have to sit in the VM supply (high-side 0.18 V at 0.36 A, no ADC pin can read a 5 V node differentially without a divider, at least 4 parts) or in the DRV ground return (breaks the driver ground reference): more than two parts, so it is documented as removed. The remaining current protection is the load switch limit (0.50 to 0.60 A).
* **Firmware (`firmware-rs`) change needed:** the driver no longer has STEP/DIR/STBY/EN-FAULT pins: drive `APHASE`, `AENBL_MCU`, `BPHASE`, `BENBL_MCU` (4 GPIOs, low at reset) with the full-step sequence in software (timer interrupt) with `AENBL_MCU = BENBL_MCU = 1` while stepping and 0 (brake) between bursts; direction reverses the sequence and sets `MOT_DIR`. The pull-downs on `AENBL_MCU`/`BENBL_MCU` keep the bridges braked at reset. The TIMER1 step counter of the old design becomes a PWM-free timer tick counter.

### I.7 Reduction pass to 45 fitted parts (2026-11-20; `design/netlist_v4.py`, previous 63-fitted version `netlist_v4_r80_gates.py`)

| Block (fitted parts) | before | after | Change |
|---|---|---|---|
| pwr | 3 | 1 | LDO U2 and C7 removed: **HJ-840 in high-voltage mode** |
| sense | 3 | 0 | R6, R7, C10 removed: battery voltage by the SAADC `VDDHDIV5` channel |
| sup | 6 | 2 | brake gates U31, U35, R81, R79 and the SUP_STCK_EN line removed (the supervisor cuts VM through the load switch enable) |
| sw | 11 | 10 | OR gate U33 + AND gate U34 + hall inverter Q7 -> NAND U33 + two AND gates U36, U34 (hall inverter absorbed) |
| dock | 2 | 1 | R21 removed |
| drv | 6 | 3 | R43, R93 (DRV8835 inputs have internal pull-downs, TI SLVSB18H pin table), C23 (22 uF C21 is the VM bypass) removed |
| usb | 6 | 5 | DU1 removed (USBLC6-2SC6 clamps VBUS; the charger sits behind 10 uF; no PD, CC 5.1 k = 5 V only) |
| boost | 7 | 5 | DZ1 removed (TPS61023 has output OVP 5.7 V typ, 5.5 to 6.0, datasheet SLVSF14B), C31 removed (CB1 is the output capacitor) |
| ui | 8 | 7 | D5 removed (charging indication by firmware from `CHG_STAT`, the MCU wakes on VBUS) |
| others | | | unchanged: oc 2 (VMOT_SENSE divider, now also the VM bleeder at 10 k / 10 k), wdt 5, chg 2, mcu 2 |
| **fitted parts** | **63** | **45** | pads (15: 5 SWD, 4 motor, 2 cell, 4 TMAG strip) and 2 DNP match shunts counted separately; 62 entries in total |

**Corrections found while checking datasheets:** the TPS61023 pinout in the earlier netlist was wrong (pin 1 FB, 2 EN, 3 VIN, 4 GND, 5 SW, 6 VOUT per SLVSF14B): fixed. The TPS2553 pinout matches (1 IN, 2 GND, 3 EN, 4 FAULT, 5 ILIM, 6 OUT); the plain TPS2553 has **no** output discharge, so the VMOT bleeder stays.

**Single hardware enable:** `MOT_ALLOW = LATCH_Q AND SUP_PERMIT AND NOT(DOCK_N AND MOT_FWD)` (U36, U33 NAND, U34) drives the EN of the TPS2553. `MOT_FWD` is the forward-intent line of the nRF (high = forward, pull-up R16: reset default = forward = blocked when undocked); `DOCK_N` is the active-low output of the DRV5032FA, so docked or reverse allows motion. The boost keeps its own enable (`SUP_PERMIT`, R82 pull-down): the supervisor can still cut the boost alone. The step-budget brake gates are gone: the supervisor budget now acts by dropping `SUP_PERMIT`, which opens the load switch (VM cut, the motor holds by its detent) instead of braking the bridges.

**Every safety function still present:** (1) watchdog latch: TPL5010 + U6 + U32 (CLR = SUP_NRST AND OC_OK); (2) DOCKED gate: hall + U33; (3) hardware over-current: TPS2553 limit 0.50 to 0.60 A + FAULT clears the latch via U32; (4) supervisor cut: `SUP_PERMIT` into the AND gate U36 **and** the boost EN; (5) forward-undocked block with refill reverse allowed; (6) POST readback of the cut: `VMOT_SENSE`.

**HJ-840 high-voltage mode (from the HJ-840 manual figures 2.4/2.5 and tables 4-1/4-2):** VDDH 2.5 to 5.5 V (VBAT 3.0 to 4.2 V fits), the VDD pins are shown unconnected in the manual's HV figure and used here as the 3V3 rail output of the nRF52840 regulator REG0. **Not verifiable from the HJ-840 manual: the REG0 load current limit and the default output voltage** (nRF52840 product specification: UICR REGOUT0 default 1.8 V, programmable 3.3 V; the maximum external load must be checked against the nRF52840 PS before ordering). Load on the rail: STM32C011 supervisor about 1 to 3 mA running (12 MHz, sleeping most of the time), TPL5010 35 nA, four logic gates < 1 uA each, DRV5032FA 1.6 uA, TMAG5273 about 2.3 mA while measuring (1 uA asleep), DRV8835 VCC about 1 mA while the bridges are enabled (a few uA in sleep): **about 4 to 7 mA peak, well under 10 mA average**. Requirements: set UICR `REGOUT0` = 3.3 V once; **flash with 3.3 V applied to both the cell + pad (VDDH) and the SWD 3V3 pad (VDD)** so that the module is in normal-voltage mode as the manual demands; the supervisor now depends on the nRF regulator for its supply: a failed or unpowered nRF regulator leaves the supervisor, the gates and the hall unpowered, which opens the hardware enable (fail-safe), but the supervisor is **no longer independent in its power source** (accepted deviation, same family as the programming deviation I.4). Idle current: no LDO quiescent (about 1 uA saved), the REG0 quiescent is part of the module's 2 uA sleep figure.

**Candidates rejected (with reason):**
* Piezo sounder: no SMD piezo transducer smaller than 9 x 9 mm is stocked at JLC (CPT-9019S-SMT stock 19, GSC9018RA 9 x 9 x 1.8 stock 115, Murata PKLCS1212E4001 12 x 12 x 1.0 stock 3267): 144 mm2 of top side area does not fit the board; the magnetic 4 x 4 x 2.0 sounder stays with QBA, RDA, D6 (stray field check in `REVIEW-FIXES.md`).
* R82 (SUP_PERMIT pull-down) kept: TPS61023 EN has no internal pull-down specified and the AND input must not float; R90 (EN pull-down) kept: the gate outputs are high-Z when 3V3 is absent and the TPS2553 EN has no internal pull-down; R16 kept (pull-up now); R92 kept (open-drain FAULT needs it, it also feeds U32); R29 kept (floating latch clock at reset); R57/R58 kept as divider and bleeder (10 k / 10 k, one resistor fewer than before).
* BOOT0 pull-down R79 removed on the assumption of the STM32C0 internal pull-down on the BOOT0/PA14 pin (**VERIFY with DS13866 before ordering; if not, add 100 k back**).
