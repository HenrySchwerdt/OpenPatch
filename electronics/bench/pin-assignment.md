> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). Bench controller board, never to be worn.

# Bench controller: E73 module pad <-> nRF52840 pin <-> net <-> function (Rev A, stepper drive)

**This file is the single source of truth for the controller pin map. The firmware (`firmware-rs`, `board-bench-e73`) syncs to it.**
The interlock, its diagnostics and the FMEA are in [INTERLOCK.md](INTERLOCK.md). Controller reference designators are stable: `CTRL.<ref>`.

Module: **Ebyte E73-2G4M08S1CX** (nRF52840-QIAA, 13 x 18 mm, 43 castellated pads, IPEX connector; LCSC C2764963). Pins are `P0.xx` / `P1.xx`.
Supply 3.3 V (XC6206, `CTRL.U2`) on pad 19. Pads 23 (VDDH), 25 (DCCH), 27 (VBUS), 29/31 (USB) are not connected. 32.768 kHz crystal on P0.00/P0.01.

**Required UICR / board init**
* `P0.09` / `P0.10` (pads 41 / 43) are used as plain inputs: set `UICR.NFCPINS` = GPIO (Embassy `nfc_pins_as_gpio: true`).
* `P0.18` / RESET (pad 26) = net `NRST`, driven by the TPL5010 `RSTn`: set `UICR.PSELRESET` = P0.18.
* Mode strapping of the STSPIN220 is done in hardware (see below). The firmware has **no** MODE1/MODE2 pins any more.

## Pin table

Direction is from the MCU. "diag" = safety readback, never able to force an output (see INTERLOCK.md).

| Pad | Pin | Net | Dir | Function / polarity |
|---|---|---|---|---|
| 1 | P1.11 | `MOT_STBY` | out | STSPIN220 STBY/RESET, high = active, 100 k pull-down |
| 2 | P1.10 | `DOCK_TEST` | out | self-test: high pulls `DOCKED_H` low through Q12 (forces "undocked" at the gate). Cannot force docked. 100 k pull-down |
| 3 | P0.03 | `DOCK_N` | in | dock hall from the pod (DRV5032, low = docked), 100 k pull-up, so an unplugged FFC reads "not docked" |
| 4 | P0.28 | `WDT_DONE` | out | TPL5010 DONE **through the qualifier U10**. Idle LOW; ONE rising edge per WAKE, issued while WAKE is high (max 20 ms after the WAKE rising edge). Hold high >= 2 us. Stuck, early or late edges are rejected in hardware |
| 6 | P1.13 | `POD_ID_N` | in | FFC loopback / pod present, low = pod board present (pod ties FFC pin 9 to GND through 10 k), 100 k pull-up on the controller |
| 7 | P0.02 / AIN0 | `I_SENSE` | ain | total motor supply current: INA180A1 (20 V/V) on 0.333 ohm, RC 1 k / 100 nF. **I [mA] = V [mV] / 6.67**. Saturates at about 3.25 V = 490 mA. Also feeds the hardware over-current comparator |
| 8 | P0.29 | `BUZ_PWM` | out | buzzer NFET (2.7 kHz, 50 %), 100 k pull-down |
| 9 | P0.31 | `DIR_REV` | in diag | the DIR_REVERSE level **as seen at the interlock gate** (Q10), high = reverse |
| 10 | P0.30 | `DOCKED_H` | in diag | the DOCKED level as seen at the gate (Q6), high = docked (after the Q7 inverter, Q12 force and pull-up) |
| 11 / 13 | P0.00 / P0.01 | `XL1` / `XL2` | - | 32.768 kHz crystal |
| 12 | P0.26 | `I2C_SDA` | io | TWIM to the pod TMAG5273A1 (0x35), 4.7 k pull-up |
| 14 | P0.06 | `I2C_SCL` | io | TWIM, 4.7 k pull-up |
| 15 | P0.05 / AIN3 | `VBUS_SENSE` | ain | USB 5 V, 100 k / 100 k (x 2) |
| 16 | P0.08 | `OC_TEST` | out | self-test: high pulls the over-current comparator reference to about 0.3 V through Q14 (trips the over-current latch if I > about 45 mA). Can only make the trip easier. 100 k pull-down |
| 17 | P1.09 | `MOT_EN_FAULT` | io | STSPIN220 EN/FAULT, 10 k pull-up + 10 nF; low = fault, driving low disables the power stage |
| 18 | P0.04 / AIN2 | `VMOT_SENSE` | ain | motor supply after the switch, 100 k / 100 k (x 2) |
| 19 | VCC | `3V3` | - | supply (also readable as the SAADC `VDD` channel) |
| 20 | P0.12 | `MOT_STCK` | out | STSPIN220 STCK (step clock, PWM1) |
| 22 | P0.07 | `MOT_DIR` | out | STSPIN220 DIR **and** the gate of the interlock reverse path (same net) |
| 26 | P0.18 / RESET | `NRST` | io | reset, driven by the TPL5010 (see above) |
| 28 | P0.15 | `BTN_N` | in | button, active low, 100 k pull-up |
| 30 | P0.17 | `WDT_WAKE` | in | TPL5010 WAKE (GPIOTE, sense high; the pulse is <= 20 ms, it ends when DONE is accepted) |
| 32 | P0.20 | `ARM_CLK` | out | latch clock: rising edge = ARM. Idle low (100 k pull-down) |
| 33 | P0.13 | `LATCH_Q` | in diag | latch output (firmware name `LATCH_Q_MON`) |
| 34 | P0.22 | `LATCH_CLR_N` | out (od) | low = clear latch. Open drain, drive low only, never high |
| 35 | P0.24 | `MCU_EN` | out | direct MCU enable (high = allow); 100 k pull-down. **Also read it back as an input** (input buffer connected while driven): the level seen by the gate Q8 and the over-current latch clear |
| 36 | P1.00 | `LED_ST_G` | out | status LED, active high |
| 37 | SWDIO | `SWDIO` | io | SWD |
| 38 | P1.02 | `HALL_A` | in | optional DRV5032 output A (pod), 100 k pull-up |
| 39 | SWDCLK | `SWDCLK` | in | SWD |
| 40 | P1.04 | `HALL_B` | in | optional DRV5032 output B (pod), 100 k pull-up |
| 41 | P0.09 | `OC_OK` | in diag | over-current latch OK (U9 Q_N): high = OK, low = tripped (supply is cut). NFC pin as GPIO |
| 42 | P1.06 | `LED_ALM_G` | out | alarm LED, active high |
| 43 | P0.10 | `PGATE_MON` | in diag | the composite MOT_ALLOW: gate node of the supply switch, divided by 2. **Low = MOT_ALLOW true (switch on), high = off**. NFC pin as GPIO |
| 5, 21, 24 | GND | `GND` | - | ground |

Not connected to the MCU: STSPIN220 `MODE1` / `MODE2` (hard-wired low), TPL5010 `RSTn` (goes to NRST and the latch clear), `DONE_TPL`.
All 29 GPIOs on the E73 pads are in use (no spare). Free pins are not available for further diagnostics; non-safety extras would need an I2C expander.

### STSPIN220 step mode (DS11633 section 6.2, Table 8)

The MODEx inputs are latched at power-up and whenever STBY/RESET rises; MODE3 = STCK and MODE4 = DIR share the pins. **"MODE1 = MODE2 = LOW forces full-step mode"
whatever MODE3/MODE4 (STCK/DIR) are** (DS11633 6.2, and footnote 1 of Table 8). MODE1 and MODE2 are strapped to GND with 10 k (R114, R115), so the result is **full step
(20 steps/rev of the motor) for both DIR levels at STBY rising, and there is no sequencing requirement on DIR or STCK**. The previous reading (firmware had to set DIR and STCK low
before STBY) is no longer necessary but harmless. Full-step mode stays latched as long as MODE1/MODE2 stay low (they cannot change).

## Peripheral map (Rust / Embassy)

| Peripheral | Pins | Notes |
|---|---|---|
| **SAADC** | AIN0 `P0.02` I_SENSE, AIN2 `P0.04` VMOT_SENSE, AIN3 `P0.05` VBUS_SENSE, plus `VDD` (3V3 rail monitor) | single ended, 0.6 V ref, gain 1/6 (3.6 V range), 20 us acquisition for 1 k sources. VBUS, VMOT: x 2 |
| **PWM** | `P0.12` MOT_STCK, `P0.29` BUZ_PWM | separate instances |
| **TWIM** | SDA `P0.26`, SCL `P0.06` | TMAG5273A1 at 0x35 (also read DEVICE_ID) |
| **GPIOTE inputs** | `P0.17` WDT_WAKE, `P0.03` DOCK_N, `P0.15` BTN_N, `P1.02` / `P1.04` HALL_A / HALL_B | |
| GPIO (interlock out) | `P0.24` MCU_EN, `P0.20` ARM_CLK, `P0.22` LATCH_CLR_N (od), `P0.28` WDT_DONE, `P0.07` MOT_DIR | |
| GPIO (self-test out) | `P1.10` DOCK_TEST, `P0.08` OC_TEST | pull-down only paths, can never force the supply on |
| GPIO (diag in) | `P0.13` LATCH_Q, `P0.30` DOCKED_H, `P0.31` DIR_REV, `P0.09` OC_OK, `P0.10` PGATE_MON, `P1.13` POD_ID_N, `P0.24` MCU_EN (read back) | |
| GPIO (stepper) | `P1.11` STBY, `P1.09` EN_FAULT, `P0.12` STCK, `P0.07` DIR | |
| LEDs | `P1.00` green, `P1.06` red | |
| **SWD** | `SWDIO` pad 37, `SWDCLK` pad 39; **RESET** `P0.18` pad 26 | Tag-Connect TC2030 pads (J2) and a 2 x 5 1.27 mm header (J3) |

Differences to `firmware-rs/docs/boards.md` as of the previous revision (the firmware agent must apply): pad 2 is now `DOCK_TEST` (was MODE2), pad 6 is `POD_ID_N` (was MODE1),
pads 9/10 are `DIR_REV` / `DOCKED_H` (were UART), pad 16 is `OC_TEST` (was TMAG_INT), pads 41/43 are `OC_OK` / `PGATE_MON` (NFC pins, new),
`I_SENSE` scaling is **I = mV / 6.67** (was 1.0 ohm: mV / 20), **`DIR_FORWARD_HIGH = false`** for the default hardware (R96 fitted, see INTERLOCK.md),
`WDT_DONE` must be an idle-low pulse issued within 20 ms after the WAKE rising edge.

## FFC to the pod (10 pin, 0.5 mm pitch, Hirose FH12-10S-0.5SH(55); the pod board uses the same numbering, same-side contacts, bottom-contact ZIF)

| Pin | Net | Pod side | Note |
|---|---|---|---|
| 1 | `GND` | all grounds | |
| 2 | `3V3` | TMAG5273 + DRV5032 supply | about 3 mA |
| 3 | `I2C_SDA` | TMAG5273 SDA | |
| 4 | `I2C_SCL` | TMAG5273 SCL | |
| 5 | `GND` | guard between I2C and the digital lines | |
| 6 | `DOCK_N` | dock hall output (DRV5032, low = docked) | |
| 7 | `HALL_A` | optional DRV5032 output A | |
| 8 | `HALL_B` | optional DRV5032 output B | |
| 9 | `POD_ID_N` | **10 k resistor to GND on the pod** (loopback: pod present / cable intact) | |
| 10 | `GND` | | |

Pod board reserved references: `POD.U1` TMAG5273A1, `POD.U2` dock DRV5032, `POD.U3` / `POD.U4` optional DRV5032 pair, `POD.R1` 10 k POD_ID, `POD.J1` FFC.
Use a **same-side-contact** cable (type A) so it cannot be mated end-for-end. A broken wire is seen as: DOCK_N high (undocked), HALL pins at their pull-up level, `POD_ID_N` high, TMAG I2C NACK.
Check pin 1 against the silkscreen and do a continuity test before powering the first board.

## Motor (NFP-608-26.45-SGM, 4.8 V, 26.5 ohm/phase, 0.18 A max) and current limit

Factory lead plugs into `J5` (Molex PicoBlade 53261-0471 compatible, CJT A1251WR-S-4P-LCP, LCSC C225113). `J6` is a **DNP** JST GH SM04B-GHS-TB footprint **superimposed on J5** (same 1.25 mm pitch and nets, shield tabs on GND, so it needs no extra routing; fit one or the other, the DRC shows one intentional courtyard-overlap warning). Pin order 1..4 = `MOT_B2`, `MOT_A2`, `MOT_B1`, `MOT_A1` (silk "B- A- B+ A+"; confirm on the first motor).

STSPIN220 peak phase current (DS11633 Equation 1, full step = 100 % of VREF on each phase): **I_peak = VREF / R_SNS**.
* `R_SNS` = 1.0 ohm (R20 / R21, 0603, 1 %).
* `VREF` = 3.3 V x 5.1 k / (100 k + 5.1 k) = **0.160 V** (R23 / R24, 1 %, C20 100 nF filter). The datasheet allows VREF 0.1 to 0.5 V, so 0.16 V is inside the range.
* I_peak = 0.160 V / 1.0 ohm = **160 mA per phase** (nominal), 89 % of the motor limit of 180 mA. Worst case: sensing offset +-15 mV (datasheet, at VREF = 0.5 V) and 1 % resistors give up to about 177 mA, below 180 mA.
  The winding is 26.5 ohm, so 4.8 V gives 181 mA DC; at the 4.85 V supply the chopper regulates to the 160 mA limit.
* Dissipation in the sense resistor 26 mW. TOFF: 47 k (about 37 us) with the datasheet RC (1 k + 10 nF) across it for loop stability (R102, C30).
* Independent hardware protection on the supply (not firmware): the chopper limit above, the over-current latch (trip about 450 mA total supply current, INTERLOCK.md), and the USB host limit.
