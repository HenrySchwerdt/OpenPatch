> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). Bench controller board, never to be worn.

# Bench controller: hardware interlock, hardware limits, diagnostics and FMEA

Design rule (user requirement): **the hardware must be correct even if the software is wrong.** Everything that can cut the motor supply is discrete logic and MOSFETs. There is
no MCU-programmable element in the cut path, the MCU can only *remove* permission, and every safety element has a readback so firmware can name a failed part.
The blocks below are self-contained sub-circuits (A to E) so they can be reused in the integrated pod. Pins: [pin-assignment.md](pin-assignment.md).

```
MOT_ALLOW = MCU_EN AND LATCH_Q (TPL5010 watchdog latch) AND OC_OK (over-current latch) AND ( DOCKED OR DIR_REVERSE )
VMOT      = VBUS (USB 5 V) switched by P-FET Q4 (AO3401A) only while MOT_ALLOW = 1
```

`MCU_EN` and the watchdog latch are mandatory in **every** path (CLAUDE.md hard rule). The OR term only matters when undocked: the automatic draw-mode refill (spec section 4) runs
undocked and reverse only (the plunger retracts, nothing is delivered).

## A. Supply switch and the interlock gate network

`PGATE` (gate of Q4) is pulled up to VBUS by R30 (47 k): **off** unless it is pulled to GND through this network of 2N7002 (all legs in series, the last one is an OR pair):

```
PGATE --Q5 (gate LATCH_Q)--Q8 (gate MCU_EN)--Q13 (gate OC_OK)--+--Q6  (gate DOCKED_H)--+-- GND
                                                               |                      |
                                                               +--Q10 (gate DIR_REV)--+
```

| Gate signal | Source | Level when unpowered / reset / floating / broken cable | Meaning |
|---|---|---|---|
| `LATCH_Q` | U6 SN74AUP1G74 Q. Set by an `ARM_CLK` rising edge (D = 3V3). Cleared by `LATCH_CLR_N` low: at power-up (R46/C29), by the MCU (open drain), by the TPL5010 `RSTn` through D2 | **0** (R42 pull-down, CLR active at power-up, ARM_CLK has a 100 k pull-down R103) | software armed the latch and the watchdog is alive |
| `MCU_EN` | MCU P0.24 direct | **0** (R43 pull-down) | independent enable from the safety task |
| `OC_OK` | U9 Q_N, hardware over-current latch (block C) | **0** when 3V3 is absent, **1** after power-up while `MCU_EN` was low | the supply current has not exceeded the limit since MCU_EN rose |
| `DOCKED_H` | Q7 inverts `DOCK_N` (pod hall, low = docked) | **0**: DOCK_N has a 100 k pull-up, so a missing/cut FFC or dead hall reads "not docked" | pod latched onto the cannula |
| `DIR_REV` | the **`MOT_DIR` net itself** (R96 fitted) or its inverse through Q11 (R97 instead of R96) | **0** (R99/R100 pull-downs) in the default R96 variant: unpowered/floating DIR = forward = blocked | commanded direction is the retract direction |

`MOT_DIR` is the same electrical node for the STSPIN220 `DIR` pin and for the Q10 gate. No firmware flag sits between "which way the motor turns" and "does the supply stay on".

### Truth table (L = LATCH_Q, E = MCU_EN, O = OC_OK)

| L | E | O | DOCKED | DIR | VMOT | Situation |
|---|---|---|---|---|---|---|
| 0 | x | x | x | x | **off** | latch not armed / watchdog expired |
| x | 0 | x | x | x | **off** | MCU enable low (reset, crash, safety task says no) |
| x | x | 0 | x | x | **off** | over-current tripped; stays off until `MCU_EN` is cycled low |
| 1 | 1 | 1 | 0 | forward | **off** | undocked, forward: blocked (the over-delivery case) |
| 1 | 1 | 1 | 0 | reverse | ON | undocked draw / refill (reverse only) |
| 1 | 1 | 1 | 1 | forward | ON | docked delivery |
| 1 | 1 | 1 | 1 | reverse | ON | docked retract |

### DIR polarity (R96 / R97), decide once on the first motor

| Fit | DIR high | DIR low | Firmware `DIR_FORWARD_HIGH` |
|---|---|---|---|
| **R96 (default)** | reverse (retract, draw) | forward (deliver) | `false` |
| R97 instead of R96 | forward | reverse | `true` |

The default is the restrictive one. Which DIR level physically retracts depends on lead order, gear pair and thread hand: confirm in test T5. A wrong choice is not unsafe by itself
if T5/T3 are run (undocked + forward must stay off), which is why they are mandatory.

### Dynamics

When DIR flips from reverse to forward while undocked with VMOT up, Q10 opens within nanoseconds, PGATE rises through R30 (tens of microseconds), Q4 opens and VMOT falls through the motor, the
20 uF bulk and the 470 ohm bleeder R101 (tau about 10 ms, below the STSPIN220 minimum VS of 1.8 V in about 10 ms). Firmware should stop STCK and pull STBY low before changing DIR.
Test points: TP5 `PGATE`, TP4 `VMOT`, TP20 `MOT_DIR`.

## B. Watchdog latch and DONE qualifier (TPL5010 DONE semantics checked)

TPL5010 (DS SNAS651A section 8.3.2): a valid DONE is a **low-to-high transition**; only the first DONE per interval is processed; DONE must arrive at least 20 ms before the next WAKE; WAKE
is <= 20 ms wide and drops as soon as DONE is recognised. Consequences:
* stuck-high or stuck-low DONE: no edge, the TPL5010 times out and resets (already safe);
* a free-running / toggling DONE (timer or PWM left running by a hung CPU) **would** satisfy the TPL5010 on its own.

**Qualifier (U10, SN74AUP1G74):** DONE from the MCU is AC-coupled (C31 10 nF into R104 1 k to GND, a 10 us pulse per rising edge) and clocks U10; U10's D input is `WDT_WAKE`.
So `DONE_TPL` rises only if the MCU's edge arrives **while WAKE is high** (within 20 ms after the WAKE rising edge). `DONE_TPL` (Q) goes to the TPL5010 DONE pin and is cleared by WAKE falling
(D4 / R105 / C32: fast rise, about 50 us hold on the fall, which keeps the pulse above the 100 ns tDONE minimum). Rejected: stuck high, stuck low, a DONE edge before WAKE (early), an edge after the 20 ms window (late), and a periodic toggle that is slower than the 2 s interval.
**Not rejected (honest limit):** a peripheral that toggles DONE faster than the window (for example a PWM left running by a hung CPU) will hit the 20 ms window after every WAKE and so keeps
the TPL5010 alive, and so does a PPI link from the WAKE edge to a DONE task. A discrete circuit cannot tell that from a healthy MCU without a challenge/response that the MCU computes. This only
keeps `LATCH_Q` alive: the motor still needs `MCU_EN` held high, the DOCKED/DIR gate and the over-current latch, and a hung CPU cannot keep those correct while stepping.
`R119` (0 ohm, DNP) is a bring-up bypass of the qualifier. **Firmware rule:** respond to the WAKE rising edge within 20 ms with one idle-low pulse on `WDT_DONE`.

Watchdog reset path: TPL5010 `RSTn` (open drain, 320 ms) goes to `NRST` and, through Schottky D2, to `LATCH_CLR_N`, so the latch is cleared even if the MCU is dead. After a reset the MCU must run its checks and
ARM again. `LATCH_CLR_N` is pulled up by R46 with C29 so the latch is also cleared at power-up.

## C. Hardware over-current cut (independent of firmware)

* STSPIN220 phase limit: 160 mA per phase from `VREF / R_SNS` (set by resistors only, pin-assignment.md).
* **Comparator U8 (LM393, supplied from VBUS) + latch U9:** `I_SENSE` (INA180A1, 20 V/V on the 0.333 ohm shunt R31 / R39 / R47) is compared with `OC_REF` = 3.0 V (R108 10 k / R109 100 k from 3V3).
  3.0 V = **450 mA** total supply current (the motor needs at most about 320 mA at 2 x 160 mA, the INA saturates at about 3.25 V = 490 mA). A trip clocks U9 (`Q` = OC_TRIP = 1, `Q_N` = OC_OK = 0), which opens Q13 and so Q4.
  U9 is **cleared only by `MCU_EN` low** (it is the CLR input through D5 / R106 / C35). Release of CLR is delayed about 12 ms after MCU_EN rises (blanking of the VMOT inrush), assertion is immediate.
  The MCU can clear the latch but cannot prevent a trip. It cannot mask the comparator either; `OC_TEST` can only pull the reference down (trip easier).
* No polyfuse (it would add 0.5 to 1 ohm in the motor supply). USB host current limit and the 1 A class VBUS path are the last resort.

## D. Evaluation: hardware step-rate / maximum-run-time limiter (decided against for Rev A)

* Maximum step rate: the NFP-608-26.45 cannot follow more than about 800 pps; the firmware caps reverse at 600 pps and forward delivery at a few Hz to 200 Hz. A cheap retriggerable-monostable rate limiter
  (STCK edge period < 1 ms means fault) would catch only a runaway above the motor's own slew limit, which is already self-limiting (the motor stalls, no delivery). Not worth the parts.
* Maximum run time: a legitimate 10 U bolus at 1.5 U/min is a 7 minute continuous run (up to 25 U configurable = 17 minutes), so a continuous-run bound has to be longer than any real delivery
  and would not limit a low-rate runaway; a meaningful bound is a **cumulative step counter** (for example a 74HC4040 clocked by STCK and cleared by the supervising MCU), but its reset would be a
  software-controlled element and the window must be set by firmware policy. For Rev A the bound is provided by: DOCKED/DIR gate, watchdog + qualifier, over-current latch, and the encoder check in firmware.
  **Recommendation for the integrated pod:** add a hardware step budget (counter + comparator with a dock/app-authorised reload) once the policy is final.

## E. Safe defaults (checklist)

| Condition | Result |
|---|---|
| Power-up, MCU not yet running | `LATCH_Q` = 0 (CLR held), `MCU_EN` = 0, `ARM_CLK` low, DOCKED = 0 until the pod pulls `DOCK_N` low: **VMOT = 0** |
| MCU reset / brown-out / unpowered / pins floating | pull-downs on MCU_EN, ARM_CLK, DIR, DOCK_TEST, OC_TEST; TPL5010 RSTn clears the latch; **VMOT = 0** |
| FFC unplugged or a wire broken | `DOCK_N` pulled up = not docked; `POD_ID_N` high; I2C NACK; forward blocked, reverse allowed only with latch + MCU_EN |
| 3V3 lost | all latches and the comparator outputs fall low, Q13/Q5 open: VMOT off |
| Stuck-low / stuck-high / free-running single GPIO | see FMEA (every single stuck pin leaves at least one other independent gate in the AND) |

## F. Diagnostics: readbacks and power-on self-test (POST)

Readbacks (pins in pin-assignment.md): `VMOT_SENSE` (ADC), `I_SENSE` (ADC, total motor current), `VBUS_SENSE` (ADC), 3V3 via SAADC `VDD`, `LATCH_Q`, `OC_OK`, `PGATE_MON` (composite MOT_ALLOW:
low = on), `DOCKED_H` and `DIR_REV` (the levels at the gates), `MCU_EN` (input buffer on the output pin), `DOCK_N`, `HALL_A/B`, `POD_ID_N`, `MOT_EN_FAULT`, `WDT_WAKE`, TMAG over I2C (ACK + DEVICE_ID).
Self-test outputs: `DOCK_TEST` (forces DOCKED_H low) and `OC_TEST` (lowers the over-current reference). Both are pull-down-only, they cannot switch the supply on.

**POST (firmware, STBY low = driver in standby, so no coil current and no motion until step 6):**

| Step | Action | Expected (threshold) | Proves |
|---|---|---|---|
| 1 | all off | VMOT_SENSE < 0.3 V, PGATE_MON high (> 2 V), LATCH_Q = 0, OC_OK = 1, VBUS 4.5 to 5.5 V, 3V3 3.0 to 3.6 V | Q4 not shorted, rails ok |
| 2 | POD_ID_N, TMAG ACK + DEVICE_ID, DOCK_N vs DOCKED_H consistent (DOCKED_H = not DOCK_N) | low, ACK, consistent | FFC, pod, Q7, Q6 gate net |
| 3 | `ARM_CLK` edge, MCU_EN low | LATCH_Q = 1, VMOT < 0.3 V | Q8 leg blocks, U6 sets |
| 4 | MCU_EN high, DOCK_TEST = 1, DIR = forward level | VMOT < 0.3 V for 50 ms | Q6 / Q10 pair blocks (undocked forward) |
| 5 | DIR = reverse level (DOCK_TEST still 1) | VMOT > 4.3 V within 30 ms, PGATE_MON low, DIR_REV = 1 | chain conducts, Q10 path |
| 6 | DIR = forward level again | VMOT < 1.8 V within 30 ms | **Q10 leg cuts**, Q4 opens, R101 bleeds |
| 7 | reverse level, `LATCH_CLR_N` low then release | VMOT < 1.8 V within 30 ms, LATCH_Q = 0 | **Q5 leg / U6 clear cuts** |
| 8 | re-ARM, MCU_EN low | VMOT < 1.8 V within 30 ms | **Q8 leg cuts** |
| 9 | MCU_EN high, reverse level, STBY high (coils hold, no step), `OC_TEST` = 1 | OC_OK = 0, VMOT < 1.8 V within 30 ms | **Q13 leg / comparator / U9 cut** (needs I_SENSE > 45 mA: holding current about 160 mA) |
| 10 | `OC_TEST` = 0, MCU_EN low then high | OC_OK = 1 again, VMOT recovers only after re-ARM | latch clear path |
| 11 | remove DOCK_TEST; docked: both DIR levels may run; undocked: forward must be blocked (repeat 4) | | DOCKED leg (Q6) with the real dock |

A POST failure leaves `MCU_EN` low, `LED_ALM` on and reports the diagnostic code of the failing part below.

## G. FMEA (stable component IDs for the fault-code catalogue)

Reference designators are `CTRL.<ref>` (controller), `POD.<ref>` (pod board, reserved: U1 TMAG5273A1, U2 dock hall, U3/U4 optional DRV5032, R1 10 k POD_ID, J1 FFC), `CABLE.FFC`, `MOTOR`, `USB`.
"Over-delivery?" means: can this single failure, with the rest working, allow forward delivery that the firmware did not authorise?

| ID | Part | Failure mode | Effect | Over-delivery? | Detection (pin / threshold) | Code family |
|---|---|---|---|---|---|---|
| CTRL.U1 | E73 nRF52840 | pin stuck high/low, free-running peripheral, hang | other legs hold; see rows below per pin | no (AND of independent legs, watchdog) | TPL5010 reset; POST | CTRL.U1.* |
| CTRL.U1 | `MCU_EN` stuck high | enable leg lost | latch, OC, dock/dir legs hold | no | POST step 8 (VMOT must fall) | CTRL.U1.MCU_EN |
| CTRL.U1 | `ARM_CLK` stuck/noisy | latch set early | `MCU_EN` still 0 | no | LATCH_Q readback vs expectation | CTRL.U1.ARM |
| CTRL.U1 | `WDT_DONE` stuck / toggling | stuck, early and late edges rejected by U10; a fast free-running toggle is accepted (see B) | watchdog partially defeated | no | WDT_WAKE counting, POST | CTRL.U10.DONE |
| CTRL.U1 | `MOT_DIR` stuck reverse | motor can only retract | none | no | encoder / TMAG direction, DIR_REV readback | CTRL.U1.DIR |
| CTRL.U1 | `MOT_DIR` stuck forward | undocked: VMOT off; draw impossible | none | no | POST step 5 fails | CTRL.U1.DIR |
| CTRL.U2 | XC6206 LDO | no output / out of range | all logic off, VMOT off | no | VDD channel < 3.0 V (MCU also resets) | CTRL.U2.3V3 |
| CTRL.U3 | USBLC6 | short on CC lines | no USB power | no | VBUS_SENSE < 4.5 V | CTRL.U3.CC |
| CTRL.U4 | STSPIN220 | open / failed output, fault | no motion or fault | no | `MOT_EN_FAULT` low, I_SENSE inconsistent with steps, encoder | CTRL.U4.FAULT |
| CTRL.U4 | STSPIN220 | shorted bridge | over-current latch trips (> 450 mA) | no | OC_OK = 0, I_SENSE high | CTRL.U4.OC |
| CTRL.R20/R21/R23/R24 | current limit set | wrong VREF / sense resistor | current up to 2x | no | I_SENSE level versus 2 x 160 mA expectation | CTRL.U4.ILIM |
| CTRL.U5 | TPL5010 | no WAKE / stuck | no watchdog service | no | no WAKE edge within 2.5 s, POST | CTRL.U5.WAKE |
| CTRL.U5 | TPL5010 | RSTn never asserts | watchdog dead | no, other legs hold | forced-timeout test (stop DONE) | CTRL.U5.RSTN |
| CTRL.D2 | SS14 | open | latch not cleared by watchdog | no | forced-timeout test: LATCH_Q must fall | CTRL.D2.RST |
| CTRL.U6 | 74AUP1G74 latch | Q stuck 1 | watchdog cannot cut | no (MCU_EN, OC, dock/dir) | LATCH_Q = 1 after `LATCH_CLR_N` low (POST 7) | CTRL.U6.Q |
| CTRL.U6 | latch | Q stuck 0 | VMOT never on | no | LATCH_Q = 0 after ARM (POST 3) | CTRL.U6.Q |
| CTRL.U7 | INA180A1 | output stuck / offset | wrong current, comparator wrong | no | I_SENSE not ~0 at idle, > 45 mA when holding (POST 9) | CTRL.U7.OUT |
| CTRL.R31/R39/R47 | shunt | open | I_SENSE low, VMOT low or open | no | VMOT_SENSE low with PGATE_MON low | CTRL.R31.SHUNT |
| CTRL.U8 | LM393 | output stuck low | no trip (OC protection lost) | no (chopper limit remains) | POST 9 (OC_TEST must trip) | CTRL.U8.CMP |
| CTRL.U8 | LM393 | output stuck high | trips at once, VMOT never on | no | OC_OK = 0 after MCU_EN cycle | CTRL.U8.CMP |
| CTRL.U9 | OC latch | Q_N stuck 1 | OC leg lost | no (chopper, other legs) | POST 9 | CTRL.U9.OK |
| CTRL.U9 | OC latch | Q_N stuck 0 | VMOT never on | no | OC_OK = 0 after clear | CTRL.U9.OK |
| CTRL.U10 | DONE qualifier | Q stuck 1 | watchdog never fires on silence | no (other legs) | forced-timeout test | CTRL.U10.DONE |
| CTRL.U10 | DONE qualifier | Q stuck 0 / D4 open | TPL5010 resets the MCU every 2 s | no | repeated resets, WAKE seen but DONE not accepted | CTRL.U10.DONE |
| CTRL.Q4 | AO3401A | D-S short | VMOT cannot be cut | **yes, the one single fault the board cannot stop; USB is the last off switch** | VMOT_SENSE > 1 V while PGATE_MON high (POST 1) | CTRL.Q4.SHORT |
| CTRL.Q4 | AO3401A | open | VMOT never on | no | POST 5 | CTRL.Q4.OPEN |
| CTRL.R30 | pull-up | open | gate floats (may turn on by leakage) | possible if chain conducts only | PGATE_MON high at POST 1 | CTRL.R30.PU |
| CTRL.Q5 | 2N7002 | D-S short | latch leg lost, others hold | no | POST 7 (VMOT must fall) | CTRL.Q5.SHORT |
| CTRL.Q8 | 2N7002 | D-S short | MCU_EN leg lost | no | POST 8 | CTRL.Q8.SHORT |
| CTRL.Q13 | 2N7002 | D-S short | OC leg lost | no | POST 9 | CTRL.Q13.SHORT |
| CTRL.Q6 | 2N7002 | D-S short | equals DOCKED stuck: undocked forward not blocked | **yes if firmware also commands it** | POST 4 (undocked forward, VMOT must stay 0) | CTRL.Q6.SHORT |
| CTRL.Q10 | 2N7002 | D-S short | equals DOCKED stuck | **yes if firmware also commands it** | POST 4 / 6 | CTRL.Q10.SHORT |
| CTRL.Q5/Q8/Q13/Q6/Q10 | 2N7002 | open | VMOT never on | no | POST 3 / 5 | CTRL.Qn.OPEN |
| CTRL.Q7 | 2N7002 | stuck on / off | DOCKED_H wrong | stuck-off = docked stuck: **yes if firmware also commands it** | DOCKED_H vs DOCK_N consistency (POST 2) | CTRL.Q7.INV |
| CTRL.Q11 / R96 / R97 | DIR polarity | wrong polarity fitted | draw blocked or undocked forward allowed | yes (if wrong polarity not caught) | POST 4 and 5 and T5 | CTRL.Q11.POL |
| CTRL.Q12 | 2N7002 | stuck on | DOCKED_H forced low, forward never allowed | no | DOCKED_H = 0 while DOCK_N = low | CTRL.Q12.TEST |
| CTRL.Q14 | 2N7002 | stuck on | OC reference low, trips at once | no | OC_OK = 0 after MCU_EN cycle with idle current | CTRL.Q14.TEST |
| CTRL.R101 | VMOT bleeder | open | VMOT falls slowly after a cut | small | POST 6 timing > 30 ms | CTRL.R101.BLEED |
| CTRL.R41 | DOCK_N pull-up | open | DOCK_N floats | possible (floating high = undocked is safe, picked up low = docked) | POD_ID_N + DOCK_N consistency | CTRL.R41.PU |
| CABLE.FFC | FFC / J4 | open / broken wire | undocked, no TMAG | no | POD_ID_N high, I2C NACK | CABLE.FFC.OPEN |
| CABLE.FFC | FFC | short between pins | wrong signals | depends | DOCK_N / HALL consistency, POD_ID_N | CABLE.FFC.SHORT |
| POD.U1 | TMAG5273A1 | no ACK / wrong ID / stuck angle | delivery cannot be verified: firmware refuses to deliver | no | I2C ACK, DEVICE_ID, angle vs steps | POD.U1.* |
| POD.U2 | dock hall | stuck low (docked stuck) | undocked forward not blocked | **yes if firmware also commands it** | DOCK_N low while the dock magnet is absent: cross-check with TMAG field, POST 11 | POD.U2.DOCK |
| POD.U2 | dock hall | stuck high | forward blocked | no | pod never docks | POD.U2.DOCK |
| POD.U3/U4 | DRV5032 pair | stuck | optional quadrature wrong | no | A/B vs steps | POD.U3.HALL |
| MOTOR | NFP-608-26.45 | open phase | no motion, I_SENSE low | no | I_SENSE below expectation, encoder | MOTOR.PHASE |
| MOTOR | NFP-608-26.45 | shorted phase / stall | I_SENSE high, OC trip at 450 mA | no | I_SENSE, OC_OK | MOTOR.STALL |
| CTRL.J5 | motor connector | open | like open phase | no | I_SENSE low | CTRL.J5.OPEN |
| USB | VBUS | out of range / sag | brown-out | no | VBUS_SENSE < 4.5 V | USB.VBUS |

## H. Acceptance tests (every first board, before any delivery test; water only, motor free on the bench)

| # | Test | Pass |
|---|---|---|
| T1 | Power up with no firmware: VMOT (TP4) | 0 V |
| T2 | Arm, then stop servicing the watchdog | VMOT falls within about 2.5 s and the MCU resets |
| T3 | No dock magnet, MCU_EN and latch on, DIR = forward level | VMOT 0 V |
| T4 | Same, DIR = reverse level | VMOT about 4.8 V (LD4 on) |
| T5 | Flip DIR to forward while undocked and stepping | VMOT collapses within about 10 ms; **confirm physically that the reverse level retracts the plunger, otherwise swap R96 for R97 and the firmware flag** |
| T6 | Magnet at the dock hall | VMOT on at both DIR levels |
| T7 | Unplug the FFC with DIR = forward | VMOT 0 V |
| T8 | MCU_EN low with everything else true | VMOT 0 V |
| T9 | 10 ohm across the motor header phase (about 500 mA), driver enabled | over-current latch trips, VMOT cut, `OC_OK` low |
| T10 | Drive `WDT_DONE` high permanently, then pulse it once 100 ms after WAKE (late), then once 5 ms after WAKE (in the window) | stuck and late: TPL5010 resets; in-window: accepted |


## I. Documented difference to v0.1.0 (hazard H15, 2026-11-19)

The v0.1.0 pod board (`../v010/INTERLOCK.md`) uses `DOCKED XOR DIR_REVERSE` (forward only when docked, reverse only when undocked; reverse while docked would aspirate through the cannula). This parked bench controller keeps the older `DOCKED OR DIR_REVERSE` (Q6 / Q10 in parallel): **docked + reverse is not blocked here**. If the bench controller is ever used again, replace the parallel pair by two series branches (Q6 + FWD leg, Q10 on an inverted DOCKED + DIR_REV leg) as in v010.
