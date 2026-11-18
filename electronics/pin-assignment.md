> TEST ONLY - NOT FOR HUMAN USE (see ../DISCLAIMER.md). Experimental bench sample.

# ISP1807 pin assignment (Rev A "fab" netlist, `kicad/netlist-fab.json`)

Pad numbers and pad names are VERIFIED against the Insight SiP datasheet isp_ble_DS1807 R19 (section 3) and the
official Insight Eagle library (`datasheets/isp/eagle/ISP1807LR_Int.lbr`). Firmware consumes this file.
Changes versus the SKiDL netlist are marked **CHANGED**.

| Module pin | Pad | Signal | Dir | Function |
|---|---|---|---|---|
| P0.15 | 37 | `BTN_N` | in | Button, wake from System OFF (GPIO SENSE) |
| P0.17 | 27 | `QI_CHG_N` | in | BQ51013B CHG (open drain): Qi field present / charging, wake |
| P0.13 | 29 | `CHG_STAT` | in | **CHANGED** was `BQ_INT`: MCP73832 STAT (open drain, low = charging, 100k pull-up R31). No I2C charger any more |
| P0.14 | 5 | `WDT_WAKE` | in | TPL5010 WAKE pulse (GPIOTE) |
| P0.16 | 9 | `LATCH_Q_MON` | in | read-back of the safety latch Q (`MOT_ALLOW`) |
| P0.26 | 6 | `I2C_SDA` | io | I2C (TWIM): TMAG5273 (0x35) only, 4.7k pull-up to 3V3 (**CHANGED**: BQ25120A removed) |
| P0.27 | 39 | `I2C_SCL` | io | I2C |
| P0.20 | 15 | `ARM_CLK` | out | safety latch clock (rising edge = ARM) |
| P0.22 | 17 | `KILL_N` | out(od) | open drain, low = clear latch |
| P0.24 | 19 | `PER_EN` | - | **CHANGED** unused (no switched hall rail; halls run from 3V3). Leave unconfigured |
| P1.02 | 49 | `HALL_A` | in | DRV5032 #1 -> QDEC A |
| P1.06 | 50 | `HALL_B` | in | DRV5032 #2 -> QDEC B |
| P0.04/AIN2 | 35 | `VMOT_SENSE` | - | **CHANGED** unused (lean board: VMOT divider removed) |
| P0.05/AIN3 | 36 | `VBAT_SENSE` | ain | SAADC AIN3: 1.5M/1M divider on VBAT (now the only battery-voltage measurement; BQ25120A VBMON is gone) |
| P0.08 | 32 | `TMAG_INT` | in | TMAG5273 INT |
| P0.06 | 34 | `WDT_DONE` | out | TPL5010 DONE (CPU-serviced only, never by PPI while motor armed). TPL5010 interval is now **~2 s** (R50 = 6.8k, DS Table 3: 6.788k) |
| P0.23 | 47 | `BUZ_PWM` | - | **CHANGED** unused (no buzzer on Rev A; alarms via BLE/Trio) |
| P0.19 | 45 | `MOT_STCK` | out | STSPIN220 STCK/MODE3 (direct, series R removed) |
| P0.21 | 11 | `MOT_DIR` | out | STSPIN220 DIR/MODE4 (direct) |
| P1.15 | 51 | `MOT_MODE1` | out | STSPIN220 MODE1 (direct) |
| P1.14 | 52 | `MOT_MODE2` | out | STSPIN220 MODE2 (direct) |
| P1.13 | 53 | `MOT_STBY` | out | STSPIN220 STBY/RESET: high = driver active; 100k pull-down R72 = fail-safe |
| P1.05 | 54 | `MOT_EN_FAULT` | io(od) | STSPIN220 EN/FAULT (read fault; internal pull-up, NOT fail-safe) |
| P0.18/RESET | 13 | `NRST` | io | TPL5010 RSTn + TC2030 pin 3; configure P0.18 as RESET (UICR PSELRESET) |
| SWDIO | 28 | `SWDIO` | io | SWD (J1 pin 2) |
| SWDCLK | 30 | `SWDCLK` | in | SWD (J1 pin 4) |
| P0.03/AIN1 | 38 | `DOCK_N` | in | **NEW** dock Hall switch DRV5032FA (U13) output, active low = magnet of the cannula adapter present = docked. GPIO interrupt (sense low). Also drives the hardware interlock (below) |
| OUT_MOD / OUT_ANT | 22 / 20 | `RF_LINK` | rf | **CHANGED** direct copper bridge between pads 20 and 22 (R90 removed); datasheet: connect 20 to 22 for the internal antenna |
| P0.09/NFC1, P0.10/NFC2 | 2, 4 | (free) | - | NC |
| other GPIO pads | - | (free) | - | NC (P0.02, P0.07, P0.11, P0.12, P0.25, P0.28-P0.31, P1.00, P1.01, P1.03, P1.04, P1.07-P1.12) |

NC pads 65-78 are isolated mechanical pads (datasheet), left unconnected. VBUS/D+/D- unconnected.
Supply range of VCC_nRF is 1.7-3.6 V (datasheet; the earlier note of 5.5 V was wrong), fed from the 3.3 V LDO.

## Motor interlock (hardware, fail-safe)

`VMOT` (STSPIN220 VS) is supplied through high-side switch Q4 (AO3401A). Its gate is pulled to VBAT (off) by R92 and can only
be pulled low through two series N-FETs: Q5 (gate = `MOT_ALLOW`, latch Q) and Q6 (gate = `DOCKED_H`).
`DOCKED_H` = inverted `DOCK_N` (Q7, pull-up R93). `DOCK_N` has pull-up R96, so a dead or unpowered hall sensor means **not docked**.
`VMOT on = MOT_ALLOW AND DOCKED`; MCU cannot set either alone. Firmware additionally reads `DOCK_N` (P0.03).
Encoder halls (x = 26.15 mm) are > 8 mm from the dock hall (x = 35 mm, y = 14.6 mm): distance >= 12 mm.

## STSPIN220 settings on the board

SENSEA/SENSEB: 1.0 ohm to GND (R97/R98); REF divider R68 100k / R69 3.3k gives VREF = 0.105 V (datasheet range 0.1-0.5 V),
peak coil current about VREF / RSNS = 105 mA (verify against the motor, tune R69); TOFF: 47k to GND (R99, datasheet typical).
