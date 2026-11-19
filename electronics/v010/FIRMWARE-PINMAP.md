> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). OpenPatch v0.1.0 integrated pod board. Water only. Never worn.

# v0.1.0 integrated pod: E73 pad <-> nRF52840 pin <-> net <-> function (PROPOSAL for `firmware-rs`)

This is a **proposal file** (the firmware owner syncs `firmware-rs/openpatch-bench/src/board/` to it; nothing in `firmware-rs/` was edited). It is derived from `netlist.json`
(single source: `design/netlist.py`) and re-uses the final bench controller map (`../bench/pin-assignment.md`) wherever the function is the same. **All 29 GPIO pads of the E73 are in use, no spare.**
Module: Ebyte E73-2G4M08S1C (nRF52840, ceramic antenna, LCSC C356849; CX variant C2764963 has the same pads), mounted on the **bottom** side. Supply 3V3 from the XC6206 LDO on pad 19.
Pads 23 (VDDH), 25 (DCCH), 27 (VBUS), 29/31 (USB) are not connected. 32.768 kHz crystal Y1 on P0.00/P0.01.

**Required UICR / board init (same as bench):** `P0.09`/`P0.10` (pads 41/43) as GPIO (`nfc_pins_as_gpio`), `P0.18` = RESET driven by the TPL5010 (`UICR.PSELRESET`).
STSPIN220 `MODE1`/`MODE2` are hard-wired low (full step, forced by the driver while both are low), no firmware pins.

## Pin table

| Pad | Pin | Net | Dir | Function / polarity | Bench map |
|---|---|---|---|---|---|
| 1 | P1.11 | `MOT_STBY` | out | STSPIN220 STBY/RESET, high = active, 100 k pull-down | same pad |
| 2 | P1.10 | `DOCK_TEST` | out | POST: high pulls `DOCKED_H` low (forces "undocked" at the gate, cannot force docked) | bench pad 2 |
| 3 | P0.03 | `DOCK_N` | in | dock hall A (DRV5032AJ open drain, low = docked), 1 M pull-up. Hall B is only seen through `DOCKED_H` | bench pad 3 |
| 4 | P0.28 | `WDT_DONE` | out | TPL5010 DONE through the qualifier U10 (idle low, ONE rising edge per WAKE within 20 ms) | bench pad 4 |
| 6 | P1.13 | `WIN` | in diag | **HW-A**: arm window active (U13 Q), high = window open | was `POD_ID_N` |
| 7 | P0.02 / AIN0 | `I_SENSE` | ain | motor supply current: INA180A1 20 V/V on 0.22 ohm: **mA = mV / 4.4** (saturates at the supply). 10 k + 100 nF | same pad, other scale |
| 8 | P0.29 / AIN5 | `NTC` | ain | pod temperature: 10 k NTC (B 3380) + 10 k, powered only while `SENSE_EN` is high | was `BUZ_PWM` |
| 9 | P0.31 / AIN7 | `HWA_FULL` | in diag | **HW-A**: step budget exhausted (U15 Q6), high = 32 pulses used | was `DIR_REV` |
| 10 | P0.30 | `DOCKED_H` | in diag | DOCKED level at the gate (both halls asserted, no DOCK_TEST), high = docked | bench pad 10 |
| 12 | P0.26 | `I2C_SDA` | io | TWIM to the TMAG5273A1 (0x35) on the same board, 4.7 k pull-up | same |
| 14 | P0.06 | `I2C_SCL` | io | TWIM, 4.7 k pull-up | same |
| 15 | P0.05 / AIN3 | `VBAT_SENSE` | ain | cell voltage through 100 k / 100 k (x 2), high-side switched by `SENSE_EN` (reads 0 V while SENSE_EN is low) | was `VBUS_SENSE` |
| 16 | P0.08 | `OC_TEST` | out | POST: high pulls the over-current reference down (trip at about 5 mA of supply current), can only make a trip easier | bench pad 16 |
| 17 | P1.09 | `MOT_EN_FAULT` | io | STSPIN220 EN/FAULT (10 k pull-up + 10 nF): low = fault; driving low disables the power stage | same |
| 18 | P0.04 / AIN2 | `VMOT_SENSE` | ain | motor supply after the switch, 100 k / 100 k (x 2) | same |
| 19 | VCC | `3V3` | - | supply; the SAADC `VDD` channel is RB13 | same |
| 20 | P0.12 | `STCK_MCU` | out | step clock **into HW-A** (the driver sees the gated `STCK_DRV`). PWM1, 100 k pull-down | `MOT_STCK` |
| 22 | P0.07 | `MOT_DIR` | out | STSPIN220 DIR **and** the interlock reverse path (same net) | same |
| 26 | P0.18 | `NRST` | io | reset, driven by TPL5010 RSTn | same |
| 28 | P0.15 | `BTN_N` | in | button, active low, 100 k pull-up | same |
| 30 | P0.17 | `WDT_WAKE` | in | TPL5010 WAKE (<= 20 ms), GPIOTE sense high | same |
| 32 | P0.20 | `ARM_CLK` | out | rising edge = ARM of **both** the interlock latch (U6) **and** the HW-A window (U13); 100 k pull-down | same |
| 33 | P0.13 | `LATCH_Q` | in diag | latch output (`LATCH_Q_MON`) | same |
| 34 | P0.22 | `LATCH_CLR_N` | out (od) | low = clear latch; open drain only | same |
| 35 | P0.24 | `MCU_EN` | out | direct MCU enable (also clears the over-current latch when low). Read back as input too | same |
| 36 | P1.00 | `LED_ST` | out | status LED, active high (1 k) | `LED_ST_G` |
| 37 | SWDIO | `SWDIO` | io | SWD (Tag-Connect TC2030 pads J2) | same |
| 38 | P1.02 | `BUZ_PWM` | out | buzzer NFET, 2.7 kHz 50 %, 100 k pull-down; buzzer is on VBAT (about 90 mA peak) | was `HALL_A` |
| 39 | SWDCLK | `SWDCLK` | in | SWD | same |
| 40 | P1.04 | `SENSE_EN` | out | high enables the VBAT divider and the NTC divider (about 20 uA + 165 uA only while high; pulse it, 5 ms settle) | was `HALL_B` |
| 41 | P0.09 | `OC_OK` | in diag | over-current latch U12 Q_N: high = OK, low = tripped (supply cut). NFC pin as GPIO | same |
| 42 | P1.06 | `CHG_STAT` | in | MCP73832 STAT: low = charging, high = done, high-Z = no supply. Read twice, internal pull-down then pull-up: (0,0) charging, (1,1) done, (0,1) no charger | was `LED_ALM_G` |
| 43 | P0.10 | `PGATE_MON` | in diag | composite MOT_ALLOW: **high = supply allowed** (the gate of the P-FETs is low), low = off. NFC pin as GPIO. (The bench `PGATE_MON` has the opposite polarity: this one is an inverter output, because a divider on PGATE would load the P-FET gate) | inverted |
| 5, 21, 24 | GND | `GND` | - | ground | same |

Not connected to the MCU: `DOCK_NB` (hall B, visible through `DOCKED_H`), `DONE_TPL`, `OC_TRIP`, `TMAG_INT`, `MODE1/MODE2`.

## Readbacks RB1..RB13 (docs/06-diagnostics.md 3.1) on this board

| RB | v0.1.0 source | Note |
|---|---|---|
| RB1 PGATE | `PGATE_MON` (pad 43) | inverted, high = on |
| RB2/RB3 PG_MID1/2 | **not available** (no pins). Test points TP5.. cover them on the bench; the chain legs are identified by the single-leg disarm of POST-A as in the bench POST | open request for the firmware owner |
| RB4 DOCKED_H | pad 10 | |
| RB5 DIR_REV | own-pin readback of `MOT_DIR` (R13 fitted = same net); with R14 instead the inverse | no extra pad |
| RB6 LATCH_Q_MON | pad 33 | |
| RB7 VMOT_SENSE | pad 18 | |
| RB8 I_SENSE | pad 7, **4.4 mV/mA** | `OCCLUSION_*` constants in `limits.rs` assume 20 V/V x 1.0 ohm (20 mV/mA): scale them |
| RB9 own pins | `MCU_EN`, `ARM_CLK`, `LATCH_CLR_N`, `MOT_STBY`, `WDT_DONE` | `PIN_CNF.INPUT=Connect` |
| RB10 EN/FAULT | pad 17 | |
| RB11 WDT_WAKE | pad 30 | |
| RB12 FFC_DET | **n/a** (no cable, the sensors are on the board) | I2C ACK is the presence test |
| RB13 VDD | SAADC internal | |
| new RB14 OC_OK | pad 41 | |
| new RB15 WIN, RB16 HWA_FULL | pads 6, 9 | HW-A |
| new RB17 VBAT, RB18 NTC, RB19 CHG_STAT | pads 15, 8, 42 | `SENSE_EN` first |

## HW-A firmware contract (new; bench firmware has none)

1. `ARM_CLK` rising edge opens the **arm window** (about 0.6 s, 0.27 to 0.83 s over tolerance) and resets a 32-pulse counter; a second `ARM_CLK` edge while the window is open or in the following dead time is ignored (hardware). The minimum distance between two accepted arms is 0.32 s (typical 0.85 s): arm at most once per tick (the tick is 1 s).
2. In the window the hardware passes **at most 32 forward `STCK` pulses** (0.126 U on the 16:20 drive) to the driver. `STCK_MCU` pulses beyond that are dropped; `HWA_FULL` goes high. **Reverse pulses (`DIR_REV` = 1) are not counted and not limited** (they cannot deliver), so draw mode (500-step chunks at 600 pps) and POST-A reverse excursions are unchanged.
3. Firmware must therefore step in chunks of <= 32 forward steps per arm. `PRIME_CHUNK_STEPS = 64` and a forward POST-A excursion of 16 steps need one arm per 32 (two ticks for a 64-step prime). A step count mismatch between `TIMER1` (counts `STCK_MCU`) and the TMAG angle with `HWA_FULL` high is **not** a fault; without `HWA_FULL` it is a stuck-gate suspicion (see FMEA).
4. POST-A step A12 (new): arm, command 40 forward pulses, expect `HWA_FULL` = 1 and TMAG motion of 32 steps (+-5 %); wait for `WIN` low (<= 1 s); command 8 pulses without ARM, expect 0 motion and `WIN` = 0. Docked, water only, 0.13 U.
5. Worst-case runaway inside one TPL5010 interval (4 s hang position): 13 windows x 32 = 416 pulses = 1.64 U (16:20) / 2.06 U (18:18); 7 windows = 0.89 U for 2 s (`sim/hwa_mc_results.txt`).

## Other firmware notes

* Boot order for a delivery burst: `MOT_DIR` first, `ARM_CLK` (latch and window), then `MCU_EN` high (the over-current latch is released 12 ms after `MCU_EN` rises, which blanks the VMOT inrush), wait >= 10 ms for `PGATE_MON`/`VMOT_SENSE`, then `STBY` high, then `STCK`.
* Cutting: `STBY` low, `STCK` low, `MCU_EN` low. VMOT is below 0.5 V 5.4 ms after `MCU_EN` falls (sim); `VMOT_FALL_TIMEOUT_MS` = 20 ms still holds.
* Battery policy (see README power budget): no motor start below 3.4 V open circuit; the sim shows only 2.4 V at the motor for a 3.1 V cell with 4 ohm internal resistance.
* Charger: `CHG_STAT`/charge pads active means the pod is off the cannula; delivery paused (H8) is firmware policy, the dock gate already blocks forward motion when undocked.

## v2 (split design, `design/netlist_v2.py`): changes to the table above

The discrete HW-A, TPL5010, latch and DONE qualifier are gone; the supervisor MCU (`INTERLOCK.md` section H) replaces them. USB-C replaces the charge pads. Pads of the E73 that change:

| Pad | Pin | v1 net | **v2 net** | Function |
|---|---|---|---|---|
| 4 | P0.28 | `WDT_DONE` | **`SUP_RXD`** | UART TX of the main MCU to the supervisor (115200 8N1): challenge response |
| 30 | P0.17 | `WDT_WAKE` | **`SUP_TXD`** | UART RX from the supervisor: challenge + status frames |
| 33 | P0.13 | `LATCH_Q` | **`SUP_OK`** | in: supervisor healthy/armed |
| 6 | P1.13 | `WIN` | unused | spare |
| 9 | P0.31 / AIN7 | `HWA_FULL` | **`VBUS_SENSE`** | analog, VBUS_P through 100 k / 100 k (x 2); high = on a cable (H8: pause delivery) |
| 34 | P0.22 | `LATCH_CLR_N` | unused | spare (no latch to clear) |
| 27 / 29 / 31 | VBUS / D- / D+ | n.c. | **`VBUS_P`, `USB_DM`, `USB_DP`** | native USB (CDC log, signed DFU) through the USB board FFC |
| 20 | P0.12 | `STCK_MCU` | `STCK_MCU` | now gated by U31 (`SUP_STCK_EN`); the supervisor counts the same edges |
| 32 | P0.20 | `ARM_CLK` | `ARM_CLK` | goes to the supervisor PA0 (no hardware latch any more) |
| 26 | P0.18 | `NRST` | `NRST` | also pulled low by the supervisor (open drain) |

Firmware changes for v2: arm once per tick (>= 1.0 s apart), answer the supervisor challenge within 20 ms, treat `SUP_OK` low or a supervisor status of `FAULT/LOCKED` as no delivery, keep forward steps <= 32 per arm, **USB CDC and DFU only through the authenticated session layer** (no unauthenticated command, no dosing or limit change over USB without the BLE-equivalent authorisation and the physical button where proposal 07 requires it), pause delivery while `VBUS_SENSE` is high. Test pads for debugging (all >= 1.0 mm, silk-labelled): GND, 3V3, VBAT, VMOT, VMOT_RAW, PGATE, PGATE2, INA_OUT (motor current, 4.4 mV/mA), ARM_CLK, SUP_PERMIT, SUP_STCK_EN, SUP_OK, SUP_TXD/SUP_RXD (watchdog link), OC_OK, OC_CMP, VBUS_P, NRST, STCK_DRV, MCU_EN, DOCKED_H, SWDIO, SWDCLK, I2C_SDA, I2C_SCL, PGATE_MON; supervisor SWD pads J4 (SWDIO), J5 (SWCLK), J6 (NRST) + GND pad.
