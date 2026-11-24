> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). OpenPatch v0.1.0 integrated pod board. Water only. Never worn.

# v0.1.0 integrated pod: E73 pad <-> nRF52840 pin <-> net <-> function (PROPOSAL for `firmware-rs`)

<!-- GENERATED:BEGIN (tools/gen_cup_docs.py) -->
## Current pin map (generated from `netlist_v4_cup.json`, HJ-840 high-voltage mode: H2 `VDDH` = `VBAT`, H3/H4 `VDD` = `3V3` = nRF52840 REG0 output, no LDO; older ISP1807 / STSPIN tables below are history)

UICR `REGOUT0` = 3.3 V once (flash in normal-voltage mode with 3.3 V on VDDH and VDD); **keep the radio at +4 dBm or less: REG0 external load limit 25 mA at TX <= +4 dBm** (nRF52840 PS v1.7 p. 84, second-hand), the rail load is about 8 mA worst case. The nRF drives `SUP_NRST` open drain only. SAADC `VDDHDIV5` reads the cell (VDDH = VBAT).

| HJ-840 pad | nRF pin | Net | Direction / note |
|---|---|---|---|
| A1 | GND | `GND` |  |
| A7 | ANT | `ANT_A` |  |
| A8 | BOARD_ANT | `ANT_B` |  |
| C2 | SWDIO | `SWDIO` |  |
| C3 | SWCLK | `SWDCLK` |  |
| D1 | P0.19 | `BTN_N` | in (internal pull-up) |
| D7 | P1.13 | `MCU_EN` | out (R18 pull-down; hardware AND input U36) |
| D8 | P0.31 | `DOCK_N` | in (hall, 100 k pull-up RDK) |
| E1 | P0.18/RESET | `NRST` | reset |
| E2 | P0.15 | `MOT_FWD` | out (forward intent, R16 pull-up = forward) |
| E3 | P0.16 | `ARM_CLK` | out (latch set clock) |
| E4 | P1.08 | `SUP_OK` | in |
| E5 | P1.15 | `I2C_SCL` | TWIM (4.7 k pull-up RI2) |
| E6 | P0.02 | `LATCH_Q` | in (readback) |
| E7 | P0.28 | `LED_B` | out, active low |
| E8 | P0.03 | `SUP_RXD` | uart |
| F1 | D+ | `USB_DP` |  |
| F2 | VBUS | `VBUS_P` |  |
| F3 | P0.11 | `CHG_STAT` | in (open drain, internal pull-up) |
| F4 | P0.07 | `APHASE` | out |
| F5 | P0.27 | `I2C_SDA` | TWIM (4.7 k pull-up RI1) |
| F6 | P0.00 | `LED_R` | out, active low |
| F7 | P0.30 | `BPHASE` | out |
| F8 | P0.29 | `SUP_BOOT0` | out (BOOT0 of the supervisor, internal pull-down on the STM32) |
| G1 | D- | `USB_DM` |  |
| G3 | P0.12 | `BUZ_A` | out (4 kHz PWM to the sounder gate, RDA pull-down) |
| G4 | P1.09 | `BENBL` | out |
| G5 | P0.05 | `AENBL` | out |
| G6 | P0.01 | `SUP_NRST` | **open-drain output only** (never drive high: the net is shared with TPL5010 RSTn, supervisor NRST and U32) |
| G7 | P0.26 | `LED_G` | out, active low |
| G8 | P0.06 | `SUP_TXD` | uart (bootloader / supervisor link) |
| H2 | VDDH | `VBAT` |  |
| H3 | VDD | `3V3` |  |
| H4 | VDD | `3V3` |  |
| H5 | P0.08 | `OC_OK` | in (open drain, 100 k pull-up RNR-class R92) |
| H7 | P0.04 | `VMOT_SENSE` | ain (VMOT/2) |
| H8 | GND | `GND` |  |

Supervisor STM32C011F4U6 (U30, UFQFPN20, DS13866 table 12):

| Pin | Function | Net |
|---|---|---|
| 1 | PC15 | `SUP_WAKE` |
| 2 | VDD | `3V3` |
| 3 | VSS | `GND` |
| 4 | PF2-NRST | `SUP_NRST` |
| 5 | PA0 | `ARM_CLK` |
| 6 | PA1 | `APHASE` |
| 7 | PA2 | `MOT_FWD` |
| 8 | PA3 | `OC_OK` |
| 9 | PA4 | - |
| 10 | PA5 | `SUP_PERMIT` |
| 11 | PA6 | `SUP_OK` |
| 12 | PA7 | `NRST` |
| 13 | PA8 | - |
| 14 | PA11 [PA9] (bootloader USART1 TX) | `SUP_TXD` |
| 15 | PA12 [PA10] (bootloader USART1 RX) | `SUP_RXD` |
| 16 | PA13 (SWDIO) | `BPHASE` |
| 17 | PA14-BOOT0 (SWCLK, internal pull-down at reset) | `SUP_BOOT0` |
| 18 | PB6 | `DOCK_N` |
| 19 | PB7 | `MCU_EN` |
| 20 | PC14 | `SUP_DONE` |
<!-- GENERATED:END -->


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


---

# v3 (ISP1807, MAIN / POWER / SENSOR split, `design/netlist_v3.py`) - supersedes the E73 tables above

Radio = Insight SiP **ISP1807-LR** (nRF52840, 8 x 8 x 1.0 mm LGA-78, integrated antenna, CONSIGNED; footprint `V010:ISP1807`, pads verified against the Insight Eagle library, see `../kicad/FOOTPRINT-VERIFICATION.md`). Pad -> pin -> net table (the firmware owner syncs `firmware-rs/` pin definitions to it; nothing in `firmware-rs/` was edited):

| Pad | Pin | Net | Function |
|---|---|---|---|
| 1 | VSS@10 | `GND` | ground |
| 2 | P0.09/NFC1 | `OC_OK` | in: over-current latch Q_N, low = tripped (NFC pin as GPIO) |
| 3 | P0.12 | `DOCK_N` | in: dock hall A (low = docked) |
| 4 | P0.10/NFC2 | `PGATE_MON` | in: high = supply allowed (NFC pin as GPIO) |
| 5 | P0.14 | `SUP_OK` | in: supervisor healthy |
| 6 | P0.26 | `TMAG_INT` | in: TMAG5273 INT |
| 7 | VSS@8 | `GND` | ground |
| 8 | D+ | `USB_DP` | USB D+ |
| 10 | D- | `USB_DM` | USB D- |
| 12 | VBUS | `VBUS_P` | USB VBUS (module needs it to enable USB) |
| 13 | P0.18/NRESET | `NRST` | reset (P0.18 as RESET, UICR PSELRESET); supervisor PA7 pulls it low |
| 14 | VSS@2 | `GND` | ground |
| 16 | VSS@3 | `GND` | ground |
| 18 | VSS@4 | `GND` | ground |
| 20 | OUT_ANT | `RF_BRIDGE` | copper bridge pad 20 - pad 22 (internal antenna) |
| 21 | VSS@5 | `GND` | ground |
| 22 | OUT_MOD | `RF_BRIDGE` | copper bridge pad 20 - pad 22 (internal antenna) |
| 23 | VSS@1 | `GND` | ground |
| 24 | VSS@9 | `GND` | ground |
| 25 | VSS@7 | `GND` | ground |
| 26 | VCC_NRF | `3V3` | supply |
| 27 | P0.17 | `SUP_TXD` | in: UART RX from the supervisor |
| 28 | SWDIO | `SWDIO` | SWD pad J10 |
| 29 | P0.13 | `SUP_RXD` | out: UART TX to the supervisor |
| 30 | SWDCLK | `SWDCLK` | SWD pad J11 |
| 31 | VSS@6 | `GND` | ground |
| 32 | P0.08 | `MOT_STBY` | out: STSPIN220 STBY/RESET (100 k pull-down) |
| 33 | P0.07 | `MOT_DIR` | out: STSPIN220 DIR + interlock reverse path |
| 34 | P0.06 | `STCK_MCU` | out: step clock (through U31 AND gate, supervisor counts the same edges) |
| 35 | P0.04/AIN2 | `MOT_EN_FAULT` | io: STSPIN220 EN/FAULT |
| 36 | P0.05/AIN3 | `VBAT_SENSE` | ain: cell voltage x2 (switched by SENSE_EN) |
| 37 | P0.15 | `BTN_N` | in: side tact button, active low |
| 38 | P0.03/AIN1 | `I_SENSE` | ain: motor supply current, INA180A1, mA = mV / 4.4 |
| 39 | P0.27 | `I2C_SCL` | io: TWIM, 4.7 k pull-up (MAIN) |
| 40 | P0.02/AIN0 | `VMOT_SENSE` | ain: VMOT x2 |
| 41 | P0.25 | `I2C_SDA` | io: TWIM, 4.7 k pull-up (MAIN) |
| 42 | P0.31/AIN7 | `NTC` | ain: pod NTC (switched by SENSE_EN) |
| 43 | P0.11 | `ARM_CLK` | out: arm request to the supervisor (rising edge, once per tick >= 1 s) |
| 44 | P0.30/AIN6 | `DOCKED_H` | in: both halls asserted (2oo2) |
| 45 | P0.19 | `MCU_EN` | out: independent enable (also clears OC latch when low) |
| 46 | P0.29/AIN5 | `VBUS_SENSE` | ain: VBUS_P x2 (high = on a cable, pause delivery) |
| 47 | P0.23 | `SENSE_EN` | out: enables VBAT divider + NTC |
| 48 | P0.28/AIN4 | `CHG_STAT` | in: MCP73832 STAT |
| 49 | P1.02 | `OC_TEST` | out: POST, pulls the OC reference down |
| 50 | P1.06 | `DOCK_TEST` | out: POST, forces undocked at the gate |
| 51 | P1.15 | `BUZ_A` | out: piezo bridge leg A (2.7 kHz) |
| 52 | P1.14 | `BUZ_B` | out: piezo bridge leg B (inverse of A) |
| 53 | P1.13 | `LED_ST` | out: status LED, active high |

Notes (v3):

* **No TPL5010, latch, DONE qualifier, `WDT_*`, `LATCH_*`, `HWA_*`, `WIN`**: the supervisor MCU (STM32C011F4U6, UFQFPN-20, `INTERLOCK.md` section H) replaces them. `SUP_RXD` is the UART TX of the nRF52840 (to the supervisor RX), `SUP_TXD` its RX.
* **NFC pins P0.09 / P0.10 (pads 2 / 4) are GPIO** (`OC_OK`, `PGATE_MON`): `UICR.NFCPINS` = 1 (as on the E73 map). `P0.18` = RESET (`UICR.PSELRESET`).
* The 32.768 kHz crystal is inside the ISP1807 (no Y1, no XL1/XL2 pads).
* USB is native on pads 8 / 10 / 12 (`USB_DP`, `USB_DM`, `VBUS_P`); VBUS_SENSE (pad 46) = VBUS divider on POWER.
* Piezo: two complementary pins `BUZ_A` / `BUZ_B` (2.7 kHz) drive a 2-NFET bridge on POWER (replaces the single `BUZ_PWM` and the magnetic buzzer).
* `TMAG_INT` is now wired (pad 6); `DOCK_NB` (hall B) is only seen through `DOCKED_H`.
* `MODE1/MODE2` of the STSPIN220 are hard-wired to GND (no resistors).
* Spare module pads: all pads not listed (about 15 GPIO of the P1.xx grid) are unconnected; they are inner-grid pads that would need via-in-pad.
* Via-in-pad (0.20 / 0.40 mm, filled and capped) is placed on every connected module pad of the second row and the inner grid (pads 3, 5, 8-19 odd/even rows, 21, 23, 24, 27, 29, 33-47 odd, 49-53): 27 vias.
* The cross-board nets (MAIN <-> POWER, 32 pads, 26 unique nets): `design/netlist_v3.py` `B2B_A` / `B2B_B`; `netlist_v3_cross.json`.


---

# v0.1.0 CUP pod v4 (single board `cup/`, `design/netlist_v4.py`): ISP1807 pad table

Changes against the v3 table above: no `OC_TEST`, `SENSE_EN`, `NTC`, `PGATE_MON`, `TMAG_INT`; pad 4 is now `LATCH_Q`; **new RGB LED** on pads 53/6/42; battery sense is always on (no switch). GND pads 1, 7, 14, 16, 18, 21, 23, 24, 25, 31. **All pad numbers are the ISP1807 land pads of the `V010:ISP1807` footprint; the nRF pin behind each pad comes from the v3 table, the PWM capability of P0.xx pins must be checked by the firmware owner (every nRF52840 GPIO can be routed to a PWM channel).** NFC pins P0.09/P0.10 as GPIO (UICR `NFCPINS`), P0.18 as reset.

| ISP1807 pad | Net | Function |
|---|---|---|
| 2 | `OC_OK` | in: over-current comparator, low = tripped (hardware cleared the latch) |
| 3 | `DOCK_N` | in: dock hall output (low = docked) |
| 4 | `LATCH_Q` | in: interlock latch Q readback (RB6) (was PGATE_MON) |
| 5 | `SUP_OK` | in: supervisor healthy |
| 6 | `LED_G` | out PWM, active low: RGB LED green (470 R) |
| 8 | `USB_DP` | USB D+ |
| 10 | `USB_DM` | USB D- |
| 12 | `VBUS_P` | USB VBUS |
| 13 | `NRST` | reset (P0.18), pulled low by the supervisor |
| 20 | `RF_BRIDGE` | copper bridge pad 20-22 |
| 22 | `RF_BRIDGE` | copper bridge pad 20-22 |
| 26 | `3V3` | supply |
| 27 | `SUP_TXD` | in: UART RX from the supervisor |
| 28 | `SWDIO` | SWD pad |
| 29 | `SUP_RXD` | out: UART TX to the supervisor |
| 30 | `SWDCLK` | SWD pad |
| 32 | `MOT_STBY` | out: STSPIN220 STBY, 100 k pull-down |
| 33 | `MOT_DIR` | out: STSPIN220 DIR and interlock reverse leg, high = reverse, 100 k pull-down |
| 34 | `STCK_MCU` | out PWM: step clock into the step gate U31 (STCK_DRV = STCK_MCU AND SUP_STCK_EN) |
| 35 | `MOT_EN_FAULT` | io: STSPIN220 EN/FAULT |
| 36 | `VBAT_SENSE` | ain: cell voltage, 4.7 M/4.7 M always on (x2), sample with long acquisition |
| 37 | `BTN_N` | in: button, internal pull-up (no external resistor) |
| 38 | `I_SENSE` | ain: INA180 output after 10 k + 10 nF, 4.4 mV/mA (saturates at the supply) |
| 39 | `I2C_SCL` | io: TMAG5273 (on the REAR strip), 4.7 k pull-up |
| 40 | `VMOT_SENSE` | ain: motor supply after the switch, 100 k/100 k (x2) |
| 41 | `I2C_SDA` | io: TMAG5273, 4.7 k pull-up |
| 42 | `LED_B` | out PWM, active low: RGB LED blue (470 R) |
| 43 | `ARM_CLK` | out: rising edge sets the latch U6 and arms the supervisor, 100 k pull-down |
| 44 | `DOCKED_H` | in: dock hall level (high = docked), single hall |
| 45 | `MCU_EN` | out: own leg QE, 100 k pull-down |
| 46 | `VBUS_SENSE` | in/ain: VBUS 100 k/100 k (x2), high = cable present (pause delivery) |
| 48 | `CHG_STAT` | in: MCP73832 STAT (low = charging, high = done, high-Z = no VBUS); also diode-ORed to the red LED cathode |
| 50 | `DOCK_TEST` | out: high forces DOCKED_H low (POST) |
| 51 | `BUZ_A` | out: piezo bridge leg A (NFET gate, 100 k pull-down) |
| 52 | `BUZ_B` | out: piezo bridge leg B |
| 53 | `LED_R` | out PWM, active low: RGB LED red (1 k, also driven low by CHG_STAT through D5) |

## Status LED (RGB, top-facing under the clear lid, `LD1`, SZYY1615RGB-B, common anode on VBAT)

| Pad | Net | Series R | Channel | Idle |
|---|---|---|---|---|
| 53 | `LED_R` | 1 k (R74) | red, also lit by `CHG_STAT` low through D5 (diode-OR, works while the MCU sleeps) | GPIO high or high-Z = off, no current |
| 6 | `LED_G` | 470 R (R75) | green | off |
| 42 | `LED_B` | 470 R (R76) | blue | off |

Pins are **active low** (sink current); the anode is on VBAT (3.0 to 4.2 V), so a GPIO at 3.3 V never lights a channel (red needs more than 1.8 V across the LED, green/blue more than 2.7 V). About 1.5 to 2 mA per channel at 3.7 V (red about 1.7 mA); run PWM at 20 to 50 percent for indication. `CHG_STAT` (pad 48) is also an MCU input: low = charging, high = done, high-Z = no VBUS (read with internal pull-down then pull-up, as before). **Pad order and common-anode polarity of the LED are unverified (vendor drawing)**: check the first board before programming.

Firmware behaviour to implement:
* default: all three pins high-Z / high, no PWM, the PWM peripheral off between indications (idle current stays negligible);
* **charging** (`CHG_STAT` low): red pulses (breathing, about 1 Hz); the diode-OR lights red steadily even if the MCU sleeps, the MCU may overlay the pulse;
* **charge complete** (`CHG_STAT` high with `VBUS_SENSE` high): steady green;
* **low battery** (below the firmware limit, default 3.5 V open circuit, `VBAT_SENSE`): red blink 1 short flash every 4 s while not charging; critical (below the motor-start limit 3.4 V): double flash;
* normal state: LED off, short blue/green flash on a button press with the battery state (green above 3.8 V, orange = red + green around 3.5 to 3.8 V, red below);
* faults from the supervisor / diagnostics: fast red blink (4 Hz) until acknowledged.


## Motor supply and undervoltage lockout (v4, locked motor NFP-608-26.45-SGM)

* VMOT path: cell -> Q4 -> Q15 -> `VMOT_RAW` -> TPS61023 (4.96 V) -> `VMOT_PRE` -> 0.22 ohm shunt -> `VMOT`. `VMOT_SENSE` (100 k/100 k) reads half of the boosted rail (about 2.5 V).
* **No motor start below about 3.4 V open circuit** (`VBAT_SENSE` x 2, measured with no load for 50 ms, no charger): constant `MOTOR_MIN_VBAT_MV = 3400`; refuse, raise `BATTERY_LOW`, light the red LED (blink pattern above). Re-measure after the first 20 steps: if `VBAT_SENSE` falls below 3.0 V under load stop and retry only after rest. The cell supplies about 0.5 to 0.6 A during a step burst (INTERLOCK.md I.2): keep bursts short, use the driver STBY/hold feature between steps, never hold full current.
* Driver current limit about 0.175 A per phase (R38 5.6 k): `I_SENSE` at 4.4 mV/mA is the cell-side-free output current (0.175 A -> 0.77 V per phase peak, a stall does not trip the 0.39 A comparator).

## v4 programming and USB pins (2026-11-20, no debug connector)

| ISP1807 pad | Net | Function |
|---|---|---|
| 8 / 10 | `USB_DP` / `USB_DM` | native USB to the USB-C receptacle (through USBLC6-2SC6), 90 ohm differential pair, signed USB DFU bootloader for all later updates |
| 12 | `VBUS_P` | USB VBUS sense (the module needs it to enable USB; also the charger input, no divider any more) |
| 47 | `SUP_BOOT0` | out: supervisor BOOT0 strap (STM32C011 pin 19, 100 k pull-down): high + `SUP_NRST` pulse = ST system bootloader |
| 49 | `SUP_NRST` | io, open drain: pulls the supervisor `NRST` low (also clears the interlock latch via U32); also driven by the TPL5010 |
| 27 / 29 | `SUP_TXD` / `SUP_RXD` | UART to the supervisor (115200 8N1): bootloader protocol (AN2606, RDP 0) while updating, challenge/response otherwise |
| 28 / 30 / 13 | `SWDIO` / `SWDCLK` / `NRST` | bare pads with `GND` and `3V3`: one-time bootloader flash only |

Supervisor update procedure (firmware owner): verify the signed supervisor image; require `VMOT_SENSE` < 0.3 V, undocked, no delivery; `SUP_BOOT0` high, pulse `SUP_NRST` low 10 ms, wait 100 ms, speak the ST UART bootloader, write, verify, `SUP_BOOT0` low, pulse `SUP_NRST`; the supervisor image re-sets RDP level 1 on first boot (open item). Pads 46 (`VBUS_SENSE`), 50 (`DOCK_TEST`), 52 (`BUZ_B`) are free after the reduction.


---

# v4 HJ-840 pin table (2026-11-20; replaces the ISP1807 tables above; GPIO pads chosen by `cup/pinassign.py` after placement, regenerate with `python3 design/netlist_v4.py`)

Module: HJSIP HJ-840 (nRF52840 SiP, LGA64, `C50052094`), normal-voltage mode (VDD = VDDH = 3V3 from the XC6206), USB through D+/D-/VBUS, **no 32 kHz crystal (use the internal LFRC: `LfclkSource::InternalRC`)**, NFC pins P0.09/P0.10 are not used, P0.18 = RESET (`E1`). DC/DC (REG1) may be enabled in firmware (inductors are inside the module, DCCH not connected). Internal antenna: A7 `ANT_A` -> 0 ohm (PI2) -> A8 `ANT_B`, PI1/PI3 are DNP shunt capacitor footprints for tuning.

| HJ-840 pad | nRF pin | Net |
|---|---|---|
| A1 | GND | `GND` |
| A7 | ANT | `ANT_A` |
| A8 | BOARD_ANT | `ANT_B` |
| B8 | P1.14 | `BTN_N` |
| C2 | SWDIO | `SWDIO` |
| C3 | SWCLK | `SWDCLK` |
| C8 | P1.12 | `DOCK_N` |
| D6 | P1.10 | `I2C_SCL` |
| D7 | P1.13 | `DOCKED_H` |
| D8 | P0.31 | `OC_OK` |
| E1 | P0.18/RESET | `NRST` |
| E2 | P0.15 | `LED_G` |
| E3 | P0.16 | `LED_B` |
| E4 | P1.08 | `SUP_BOOT0` |
| E5 | P1.15 | `ARM_CLK` |
| E6 | P0.02 | `SNSA` |
| E7 | P0.28 | `LATCH_Q` |
| E8 | P0.03 | `SUP_NRST` |
| F1 | D+ | `USB_DP` |
| F2 | VBUS | `VBUS_P` |
| F3 | P0.11 | `LED_R` |
| F4 | P0.07 | `SUP_OK` |
| F5 | P0.27 | `MOT_STBY` |
| F6 | P0.00 | `BUZ_A` |
| F7 | P0.30 | `MOT_DIR` |
| F8 | P0.29 | `STCK_MCU` |
| G1 | D- | `USB_DM` |
| G3 | P0.12 | `CHG_STAT` |
| G4 | P1.09 | `MOT_EN_FAULT` |
| G5 | P0.05 | `VBAT_SENSE` |
| G6 | P0.01 | `SUP_RXD` |
| G7 | P0.26 | `I2C_SDA` |
| G8 | P0.06 | `MCU_EN` |
| H2 | VDDH | `3V3` |
| H3 | VDD | `3V3` |
| H4 | VDD | `3V3` |
| H5 | P0.08 | `SUP_TXD` |
| H7 | P0.04 | `VMOT_SENSE` |
| H8 | GND | `GND` |

Analog: `VBAT_SENSE` P0.05 (AIN3), `SNSA` P0.02 (AIN0: phase A sense resistor 1 ohm, 0 to 0.18 V, use gain 4), `VMOT_SENSE` P0.04 (AIN2). Changes against the ISP table: `I_SENSE` is gone (no shunt/INA), `OC_OK` = FAULT of the TPS2553 (open drain, 100 k pull-up, low = current limit active), `MOT_ALLOW` is internal (not on a pad), `LATCH_Q` is read back on a GPIO. Firmware owner: all GPIO choices are free (any nRF52840 pin can be PWM/UART/I2C through the crossbars), only the analog pads and the USB/SWD/RESET pads are fixed.


## v4 motor driver pins (2026-11-20; replaces `MOT_STBY`, `STCK_MCU`, `MOT_EN_FAULT`, `I_SENSE`/`SNSA`)
Driver since 2026-11-24: **two DRV8838** (U7A coil A, U7B coil B, `INTERLOCK.md` I.6b), same PHASE/ENABLE truth table as the DRV8835 before; the table below is unchanged.

| Net | Direction | Function |
|---|---|---|
| `APHASE`, `BPHASE` | nRF output, also supervisor inputs (pins 8, 18) | PHASE of bridge A / B (direction of each winding); one toggles per full step |
| `AENBL_MCU`, `BENBL_MCU` | nRF output (100 k pull-down) | ENABLE of the bridges through the supervisor AND gates (`AENBL = AENBL_MCU AND SUP_STCK_EN`): 1 = driven, 0 = brake |
| `MOT_DIR` | nRF output | reverse-intent line (hardware OR gate and supervisor consistency check), not a driver pin any more |
Full-step sequence (A, B phase): (0,0) -> (1,0) -> (1,1) -> (0,1) -> (0,0)... forward, reversed order for reverse (A+B+, A-B+, A-B-, A+B-). `VCC` and `nSLEEP` of both DRV8838 are on 3V3 (DRV8835 before: `MODE` and `VCC`). The GPIO pads on the HJ-840 are chosen by `cup/pinassign.py` (table in the HJ-840 section above is regenerated by `design/netlist_v4.py`). **Firmware change needed in `firmware-rs`:** bit-banged full steps from a timer interrupt instead of the STEP/DIR/STBY driver (no hardware step clock any more); no `EN/FAULT` input; no motor current reading (`I_SENSE`/`SNSA` removed).
