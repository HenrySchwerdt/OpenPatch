> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). OpenPatch v0.1.0 integrated pod. Water only. Never worn, never with insulin or any drug.

# v0.1.0 pod: hardware interlock, over-current cut, HW-A step budget

Rule (unchanged from the bench): **the hardware must be correct even if the software is wrong.** The cut path is discrete logic and MOSFETs only; the MCU can remove permission but never grant it.
Sub-circuits A to C are the final bench blocks (`../bench/INTERLOCK.md`) adapted to the battery supply; D (second series switch) and E (HW-A) are new in v0.1.0.
Simulated with ngspice: `sim/switch_oc_results.md`, `sim/hwa_results.md`, plots `sim/switch_oc.png`, `sim/hwa.png`.

```
MOT_ALLOW = MCU_EN AND LATCH_Q (TPL5010 watchdog latch) AND OC_OK AND ( DOCKED_A AND DOCKED_B  OR  DIR_REVERSE )
VMOT      = VBAT through TWO series P-FETs (Q4, Q15, common gate PGATE) only while MOT_ALLOW = 1
STCK_DRV  = STCK_MCU through the HW-A budget gate (<= 32 forward pulses per accepted ARM, dead time between arms)
```

## A. Gate network (PGATE)

`PGATE` is pulled to VBAT by **two** 100 k resistors in parallel (R9, R10: one open resistor does not float the gate) plus C11 (100 nF gate-source, soft start). It can only be pulled low through R11 (10 k) and **five series 2N7002 legs**:

```
PGATE -R11- Q5 (LATCH_Q) - Q8 (MCU_EN) - Q13 (OC_OK) - +- Q6  (DOCKED_H) -+- GND
                                                        +- Q10 (DIR_REV)  -+
```

| Gate | Source | Unpowered / reset / floating | Meaning |
|---|---|---|---|
| `LATCH_Q` | U6 Q (AUP1G74). Set by an `ARM_CLK` edge. Cleared by `LATCH_CLR_N` low: power-up (R28/C15), MCU (open drain), TPL5010 `RSTn` via D2 | 0 (R17, CLR active at power-up, R29 on ARM_CLK) | armed and the watchdog is alive |
| `MCU_EN` | MCU P0.24 | 0 (R18) | independent enable |
| `OC_OK` | U12 Q_N (block C) | 0 without 3V3; 1 after power-up | no over-current since `MCU_EN` rose |
| `DOCKED_H` | `R21` pull-up, **pulled low by Q7 (hall A not asserted) or Q7B (hall B not asserted) or Q12 (DOCK_TEST)** | 0 (a missing or stuck-open hall reads "not docked") | pod latched: **both** halls must assert (2oo2) |
| `DIR_REV` | the `MOT_DIR` net itself (R13) or its inverse (R14 instead) | 0 (R15/R16) | commanded direction = retract |

`DOCKED_H` is high only when BOTH DRV5032AJ halls pull `DOCK_N`/`DOCK_NB` low. A hall stuck "asserted" (the residual single fault of the bench, `POD.U2 stuck low`) no longer enables undocked forward motion: the other hall still reads not-docked. Stuck "not asserted" blocks delivery (availability, fail safe).
Truth table: identical to the bench (`../bench/INTERLOCK.md`), with `DOCKED = hallA AND hallB`.

| LATCH_Q | MCU_EN | OC_OK | DOCKED_A,B | DIR | HW-A | VMOT | Situation |
|---|---|---|---|---|---|---|---|
| 0 | x | x | x | x | x | off | not armed / watchdog expired |
| x | 0 | x | x | x | x | off | enable low (reset, crash, safety task) |
| x | x | 0 | x | x | x | off | over-current, until `MCU_EN` is cycled |
| 1 | 1 | 1 | not both | fwd | x | off | undocked, forward blocked (the over-delivery case) |
| 1 | 1 | 1 | not both | rev | n/a (reverse not counted) | ON | undocked draw (retract only) |
| 1 | 1 | 1 | both | fwd | window open and budget left | ON, steps pass | docked delivery |
| 1 | 1 | 1 | both | fwd | window closed or 32 pulses used | ON, **STCK_DRV held low** | runaway bounded (E) |
| 1 | 1 | 1 | both | rev | n/a | ON | docked retract |

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
