> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). Bench controller board, never to be worn.

# Bench controller: E73 module pad <-> nRF52840 pin <-> function (SMA channels + optional stepper)

Module: **Ebyte E73-2G4M08S1CX** (nRF52840-QIAA, 13 x 18 mm, 43 castellated pads, IPEX antenna connector; LCSC C2764963). Pad numbers and GPIO names
are from the Ebyte datasheet pin table (C and CX variants identical). Pins are given as `P0.xx` / `P1.xx` for the Rust (Embassy) firmware.
**Supersedes the ISP1807 map in `../pin-assignment.md` for the bench setup.** Several ISP1807 GPIOs (P0.14, P0.16, P0.19, P0.21, P0.23, P0.27, P1.05, P1.14, P1.15) do not exist on the E73 pads.

Supply 3.3 V (XC6206) on pad 19. Pads 23 (VDDH), 25 (DCCH), 27 (VBUS), 29/31 (USB D-/D+) are not connected. 32.768 kHz crystal on P0.00/P0.01.
**P0.09 / P0.10 (pads 41 / 43) are used as plain GPIO: set `UICR.NFCPINS` = GPIO (Embassy: `embassy_nrf::config::Config { nfc_pins_as_gpio: true }`; Zephyr `CONFIG_NFCT_PINS_AS_GPIOS=y`).**
**P0.18 / RESET (pad 26): net `NRST`, driven by the TPL5010; set UICR PSELRESET = P0.18 for a hardware reset (the interlock latch is cleared by RSTn independently).**

## Pin table

| Pad | Pin | Net | Dir | Function / polarity |
|---|---|---|---|---|
| 1 | P1.11 | `DOCK_N` | in | pod dock hall (DRV5032FA push-pull, active **low** = docked), 100 k pull-up on the board, so a missing FFC reads "not docked". Also feeds the hardware interlock |
| 2 | P1.10 | `BUZ_PWM` | out | buzzer NFET (PWM 2.7 kHz, 50 %), 100 k pull-down |
| 3 | P0.03 / AIN1 | `SMA1_DSENSE` | ain | SMA channel 1 wire-low-side node (MOSFET drain), 100 k / 100 k (ratio 0.5) |
| 4 | P0.28 / AIN4 | `SMA_HI_SENSE` | ain | SMA supply after the 10 ohm limiter (wire high side), 100 k / 100 k (ratio 0.5) |
| 6 | P1.13 | `WDT_DONE` | out | TPL5010 DONE (pulse high >= 100 ns after each WAKE; interval about 2 s). Service only from the safety task |
| 7 | P0.02 / AIN0 | `I_SMA1` | ain | channel 1 current: INA180A1 (20 V/V) on a 0.333 ohm low-side shunt, RC 1 k / 100 nF. 2.67 V = 0.4 A, so **I = V / 6.67** |
| 8 | P0.29 / AIN5 | `VBUS_SENSE` | ain | USB 5 V, 100 k / 100 k (ratio 0.5) |
| 9 | P0.31 / AIN7 | `I_MOT` | ain | stepper supply current: INA180A1 on 0.5 ohm shunt, **I = V / 10** (3.3 V = 330 mA) |
| 10 | P0.30 | `MOT_MODE2` | out | STSPIN220 MODE2 (MODE1 is tied high by 10 k; modes latched when STBY goes high) |
| 11 / 13 | P0.00 / P0.01 | `XL1` / `XL2` | - | 32.768 kHz crystal |
| 12 | P0.26 | `I2C_SDA` | io | I2C (TWIM) to the pod TMAG5273 (address 0x35), 4.7 k pull-up |
| 14 | P0.06 | `I2C_SCL` | io | I2C, 4.7 k pull-up |
| 15 | P0.05 / AIN3 | `SMA2_DSENSE` | ain | channel 2 wire-low-side node, ratio 0.5 |
| 16 | P0.08 | `SMA2_TRIG` | out | channel 2 one-shot trigger (B input of the CD74HC221, **rising edge opens the window**) |
| 17 | P1.09 | `SMA1_TRIG` | out | channel 1 one-shot trigger (rising edge) |
| 18 | P0.04 / AIN2 | `I_SMA2` | ain | channel 2 current, **I = V / 6.67** |
| 19 | VCC | `3V3` | - | supply |
| 20 | P0.12 | `SMA1_PWM` | out | channel 1 gate PWM (through 100 ohm to the MOSFET gate; gate is clamped low unless the one-shot window is open) |
| 22 | P0.07 | `SMA2_PWM` | out | channel 2 gate PWM |
| 26 | P0.18 / RESET | `NRST` | io | see above |
| 28 | P0.15 | `BTN_N` | in | button, active low, 100 k pull-up on the board |
| 30 | P0.17 | `WDT_WAKE` | in | TPL5010 WAKE pulse (GPIOTE, sense high) |
| 32 | P0.20 | `ARM_CLK` | out | interlock latch clock: **rising edge = ARM**. Idle low |
| 33 | P0.13 | `SMA_ALLOW` | in | read-back of the latch output (also the reset input of both one-shots) |
| 34 | P0.22 | `LATCH_CLR_N` | out (od) | low = clear latch (supply off). Open drain / drive low only, never high |
| 35 | P0.24 | `MCU_EN` | out | direct MCU enable, second series gate of the supply switch. High = allow. 100 k pull-down |
| 36 | P1.00 | `LED_ST_G` | out | status LED (green), active high |
| 37 | SWDIO | `SWDIO` | io | SWD |
| 38 | P1.02 | `MOT_STCK` | out | STSPIN220 STCK (step clock) |
| 39 | SWDCLK | `SWDCLK` | in | SWD |
| 40 | P1.04 | `MOT_DIR` | out | STSPIN220 DIR |
| 41 | P0.09 | `MOT_STBY` | out | STSPIN220 STBY/RESET, high = active, 100 k pull-down (NFC pin used as GPIO) |
| 42 | P1.06 | `LED_ALM_G` | out | alarm LED (red), active high |
| 43 | P0.10 | `MOT_EN_FAULT` | io | STSPIN220 EN/FAULT: 10 k pull-up + 10 nF; low = fault, driving low disables the power stage (NFC pin used as GPIO) |
| 5, 21, 24 | GND | `GND` | - | ground |

Free/unavailable: P0.14, P0.16, P0.19, P0.21, P0.23, P0.25, P0.27, P1.01, P1.03, P1.05, P1.07, P1.08, P1.12, P1.14, P1.15 are not on the E73 pads. **No UART pads any more (P0.30/P0.31 are used): use RTT over SWD for logs.** No Hall quadrature channel on the controller any more (the DRV5032 pair is not on the pod FFC; the TMAG5273 over I2C is the angle channel).

## Peripheral map (Rust / Embassy)

| Peripheral | Pins | Notes |
|---|---|---|
| **SAADC** | AIN0 `P0.02` I_SMA1, AIN1 `P0.03` SMA1_DSENSE, AIN2 `P0.04` I_SMA2, AIN3 `P0.05` SMA2_DSENSE, AIN4 `P0.28` SMA_HI_SENSE, AIN5 `P0.29` VBUS_SENSE, AIN7 `P0.31` I_MOT | single ended, internal 0.6 V reference, gain 1/6 (3.6 V range), acquisition time >= 20 us for the 1 k sources, oversample for the PWM ripple (RC about 0.16 ms). Wire resistance: `R = (V_hi - V_d) / I` with `V_hi = 2 x SMA_HI_SENSE`, `V_d = 2 x SMAx_DSENSE`; it includes the FFC and ferrule resistance, calibrate with a known resistor |
| **PWM** | `P0.12` SMA1_PWM, `P0.07` SMA2_PWM, `P1.10` BUZ_PWM | PWM0 channels (any frequency; 20 kHz typical for the wire, 2.7 kHz for the buzzer). All idle low |
| **TWIM** | SDA `P0.26`, SCL `P0.06` | TMAG5273A1 at 0x35 on the pod, 4.7 k pull-ups on the board. INT pin of the TMAG is not wired |
| GPIO (SMA safety) | `P1.09` SMA1_TRIG, `P0.08` SMA2_TRIG | rising edge starts a hardware window (one-shot, about 0.2 s, max 0.3 s, non-retriggerable) in which the PWM may act. Trigger first, then start PWM within the window |
| GPIO (interlock) | `P0.20` ARM_CLK, `P0.22` LATCH_CLR_N (open drain), `P0.24` MCU_EN, `P0.13` SMA_ALLOW (in), `P0.17` WDT_WAKE (in), `P1.13` WDT_DONE | |
| GPIO (stepper option) | `P1.02` STCK, `P1.04` DIR, `P0.09` STBY, `P0.10` EN_FAULT, `P0.30` MODE2 | NFC pins as GPIO |
| GPIOTE inputs | `P1.11` DOCK_N, `P0.15` BTN_N, `P0.17` WDT_WAKE | |
| LEDs | `P1.00` green, `P1.06` red | |
| **SWD** | `SWDIO` pad 37, `SWDCLK` pad 39; **RESET** `P0.18` pad 26 | Tag-Connect TC2030 pads and a 2 x 5 1.27 mm header (1 VTref, 2 SWDIO, 4 SWDCLK, 10 nRESET, 3/5/9 GND) |

## Hardware interlock (fail-safe, independent of firmware)

The interlocked supply `VSMA` = `VBUS` through P-FET Q4 (AO3401A). Its gate `PGATE` is pulled to VBUS (off) by 100 k and can only be pulled low through **three series N-FETs**:

| FET | Gate | Meaning | Default (unpowered / fault) |
|---|---|---|---|
| Q5 | `SMA_ALLOW` | latch SN74AUP1G74 output (set by an `ARM_CLK` rising edge, cleared by the TPL5010 RSTn through SS14, by `LATCH_CLR_N` and at power-up) | 0 |
| Q8 | `MCU_EN` | direct MCU enable | 0 (100 k pull-down) |
| Q6 | `DOCKED_H` | inverted `DOCK_N` (Q7) | 0 (pull-up on `DOCK_N` = not docked) |

`VSMA on = latch AND MCU_EN AND DOCKED`. `VSMA` feeds (a) the SMA branch: polyfuse F1 (0.5 A hold) then **R_LIM 10 ohm / 1 W** (a stuck-on MOSFET with a 2 ohm wire is limited to about 0.4 A), net `SMA_HI`, and (b) the STSPIN220 supply (`VMOT`, through the 0.5 ohm shunt and the 0 ohm link R95; remove R95 when no stepper is used).

**SMA hardware pulse-width limiter (per channel).** Gate path: `SMAx_PWM` -> 100 ohm -> MOSFET gate. A 2N7002 clamps the gate to ground whenever the CD74HC221 output `WINx_N` is high (idle). `SMAx_TRIG` rising edge starts a non-retriggerable monostable, tW = 0.7 x 300 k x 1 uF = about 0.21 s nominal (worst case about 0.3 s), during which the clamp is released. A static (stuck) MCU output therefore heats the wire for at most one window. `SMA_ALLOW` is the reset input of both monostables. Limits of the scheme: a toggling MCU can re-trigger after each window (the TPL5010 / latch still cut the supply within about 2 s), and `WINx_N` has a 100 k pull-up so a dead one-shot keeps the clamp on.

## FFC to the pod (12 pin, Hirose FH12-12S-0.5SH, 0.5 mm; pod board has the same numbering)

| Pin | Net | Pin | Net |
|---|---|---|---|
| 1 | GND | 12 | GND |
| 2 | `SMA_HI` | 11 | `SMA_HI` |
| 3 | `SMA1_D` | 10 | `SMA1_D` |
| 4 | `SMA2_D` | 9 | `SMA2_D` |
| 5 | `I2C_SDA` | 8 | `I2C_SCL` |
| 6 | `3V3` | 7 | `DOCK_N` |

Two conductors per SMA line (about 200 mA peak). The pinout is symmetric, so a reversed cable swaps like nets (SDA/SCL swap is harmless); the only unsafe pair is 3V3 / DOCK_N. **Check pin 1 against the silkscreen mark and do a continuity test before powering.**
Wire connection on the pod: wire 1 between clamp pads `SMA1_HI` (net `SMA_HI`) and `SMA1_LO` (net `SMA1_D`); wire 2 between `SMA2_HI` and `SMA2_LO` (`SMA2_D`). Current flows `VSMA` -> R_LIM -> FFC -> wire -> FFC -> MOSFET -> 0.333 ohm shunt -> GND.

## Stepper option (NFP-608-26.45-SGM, 4.8 V, 26.5 ohm, 0.18 A max)

Factory lead plugs into J5 (4-pin 1.25 mm, Molex PicoBlade 53261-0471 compatible, CJT A1251WR-S-4P-LCP; DNP footprint J6 for a JST GH plug). Pin order B-, A-, B+, A+ is silk-marked and wired to `MOT_B2`, `MOT_A2`, `MOT_B1`, `MOT_A1` (STSPIN220 OUTB2, OUTA2, OUTB1, OUTA1). Current setting: sense 1.0 ohm, VREF 0.160 V (100 k / 5.1 k) = 160 mA peak per phase. Change R24 to retune. Supply 5 V USB is within the 4.8 V rating at chopper current control.
