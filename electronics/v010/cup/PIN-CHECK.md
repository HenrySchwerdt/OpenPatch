> **TEST ONLY - NOT FOR HUMAN USE** (see `../../../DISCLAIMER.md`). Bench sample, water only, never worn.

# PIN-CHECK: independent netlist / footprint / datasheet check of every fitted part (2026-11-20)

**Method.** For every LCSC number of `netlist_v4_cup.json` the official EasyEDA/LCSC symbol and footprint were pulled with `easyeda2kicad 1.0.1` (scratch only, not committed). Three comparisons per part:
1. **netlist pin -> LCSC symbol pin name** (`symtab`-style listing, every pin read by eye),
2. **our footprint vs the LCSC footprint**, pad number by pad number, best rigid transform (rotation, no mirroring allowed): pad topology, pitch and pad size,
3. **netlist pin -> vendor datasheet pin table** (text of the PDFs from ti.com / ww1.microchip.com / datasheet.lcsc.com; the HJ-840 manual V1.8, DS13866 rev 5, ALPS and HRO drawings were read as images). **No PDF is committed.**

JLC stock and price come from the live JLC parts API (2026-11-20), snapshot in `jlc_stock_2026-11-20.json`. The script `../tools/check_pins_vs_fp.py` now checks that every netlist pin exists as a pad of the footprint and vice versa (run it after every netlist change). `../tools/gen_fp_pincheck.py` regenerates the footprints that were wrong.

**Result: 7 real mismatches found and fixed (USB-C, STM32C011 pin map, button part, 3 AND-gate packages, LED and sounder land patterns), 1 ordering blocker (DRV8835 not in stock at JLC), 4 value notes.** Everything else matched.

## Fixed mismatches

| # | Part | Finding | Fix |
|---|---|---|---|
| M1 | **JU1 USB-C TYPE-C-31-M-14 (C223907)** | Footprint was an approximation (A pads on top, B pads on the bottom layer, 17 pads). The real part (HRO drawing, LCSC footprint) is a **sink-board receptacle with 12 SMD pads in ONE row** (A1/B12, B1/A12, A4/B9, B4/A9 are merged pads), 4 shield THT slots (0.5 x 1.65 drill at x +-5.58) and 2 peg holes d0.6, and its body sits in a **9.14 x 6.3 mm board notch (+ 6.4 x 0.7)**; the pad row is 8.0 mm behind the mouth. The old notch was 9.4 x 4.0. | New footprint `USB_C_HRO_31_M_14` (origin = mouth, pad row y 8.02); netlist pins `A1B12, B1A12, A4B9, B4A9, A5, B5, A6, B6, A7, B7, S` (A8/B8 SBU unconnected); outline notch x 18.8-28.2 to y 27.1 and x 20.2-26.8 to y 26.45 in `cupgeom.py`. This matches the mechanics keep-out `usb_receptacle_keepout` y 26.35-33.7, which already assumed the 7 mm body. |
| M2 | **U30 STM32C011F4U6 (C5456188)** | The netlist used the **TSSOP20 pin numbers on the UFQFPN20 footprint** (DS13866 rev 5 table 12: UFQFPN pin = TSSOP pin - 2 modulo 20). VDD was on pin 4 (real VDD = pin 2), NRST on 6 (real 4), BOOT0 on 19 (real 17), etc. Also pad 21 (exposed pad) does not exist: ST table 69 lists 20 terminals only. | Remapped all 18 signals: 19 MCU_EN, 20 SUP_DONE, 1 SUP_WAKE, 2 VDD, 3 VSS, 4 NRST, 5 ARM_CLK, 6 APHASE, 7 MOT_FWD, 8 OC_OK, 10 SUP_PERMIT, 11 SUP_OK, 12 NRST(nRF), 14 TXD, 15 RXD, 16 BPHASE, 17 BOOT0, 18 DOCK_N; pad 21 removed. |
| M3 | **SW1 SKRPACE010 (C139797)** | ALPS SKRP is a **top-push** tact, 2.5 mm high (datasheet "Top push"), not the 4.2 x 3.2 x 1.4 side-push assumed. 2.5 mm would also exceed the 1.5 mm headroom above the board. | Replaced by **ALPS SKSCLAE010, LCSC C130445** (side push, 4.85 x 3.55 x 1.25, JLC stock 873): footprint `SW_SKSCLAE010` from the ALPS land pattern; pins 1+2 / 3+4 are the two contact pairs. It is 4.85 mm wide, so at x 30.0 it collides with the USB notch and the shield slot: **placed at x 33.0 (mechanics request: button actuator, flex window and nub x 30.0 -> 33.0)**. |
| M4 | **U32, U34, U36 TP74AUP1G08S5 (C48886815)** | The part is **SOT-23-5** (EasyEDA footprint, JLC "SOT-23-5"); the netlist used SC-70-5 (0.65 pitch). | Footprint `Package_TO_SOT_SMD:SOT-23-5` (U36 is replaced anyway, see REVIEW-FIXES M1). U33 (now the XOR) really is SC-70-5. |
| M5 | **LD1 SZYY1615RGB-B (C3029071)** | Land pattern was 1.1 x 0.9 mm pitch; the vendor drawing has pads 0.75 x 0.65 at about 1.0 x 1.45 mm. Pin order itself is correct: 4 = common anode, 1 R, 2 G, 3 B (vendor drawing, top view 4 top-left, 1 top-right, 3 bottom-left, 2 bottom-right). | New footprint pads 0.65 x 0.65 at 1.0 x 1.45. Note: green/blue VF 2.8-3.4 V from VBAT through 1 k: dim below about 3.4 V. |
| M6 | **BZ1 FUET-4020 (C391027)** | Pad pitch 3.0 / 1.2 wide vs the vendor pattern (outer span 4.4, gap 0.9, pads 1.75 x 1.8). Vendor data: 4 kHz square wave, 2-4 Vo-p, rated 3 V / max 90 mA, coil 17 +-3 ohm, **MIN 65 dB** at 10 cm (the netlist said "about 80 dB"). DC drive at 4.2 V would draw 0.25 A. | Footprint to the vendor pattern; 22 ohm series resistor RBZ (peak 100 mA at 4.2 V, REVIEW-FIXES m4); note updated. |
| M7 | **U1 HJ-840 (C50052094)** | Pad positions identical to the LCSC footprint (max deviation 0.005 mm, no mirror needed: chirality correct). Pad size 0.30 x 0.40 vs LCSC 0.40 (along 0.65 pitch) x 0.44. | Pad size taken from the LCSC footprint. |

## Per part table (all 30 LCSC numbers)

| Part | LCSC | Source | Result | JLC stock |
|---|---|---|---|---|
| HJ-840 nRF52840 SiP, LGA64 | C50052094 | HJ-840 manual V1.8 table 2-2, LCSC symbol and footprint | **PASS.** All 64 pads, every GPIO name, VDDH H2, VDD H3/H4, VBUS F2, D+/D- F1/G1, ANT A7 / BOARD_ANT A8, SWDIO C2 / SWCLK C3, P0.18/RESET E1, only 2 GND pads (A1, H8) as in the manual. See "HJ-840 land pattern and antenna" below | 91 (low) |
| DRV8835DSSR WSON-12 | C129328 | SLVSB18H pin table, LCSC symbol/footprint | **PASS** (1 VM, 2-5 outputs, 6 GND, 7 BENBL, 8 BPHASE, 9 AENBL, 10 APHASE, 11 MODE tied to VCC = PH/EN, 12 VCC, 13 pad). VCC 2-7 V, VM max 11 V. VCC current 0.45 mA typ / 2 mA max. Footprint topology and pitch match (dev 0.01). **JLC STOCK = 0** | **0 (blocker)** |
| USB-C TYPE-C-31-M-14 | C223907 | HRO drawing (image), LCSC footprint | **FIXED** (M1) | 2143 |
| TPS61023DRLR SOT-563 | C919459 | SLVSF14B-class table | **PASS**: 1 FB, 2 EN, 3 VIN, 4 GND, 5 SW, 6 VOUT (the pinout that was wrong once is right now); true load disconnect in shutdown | 140035 |
| TPS2553DBVR | C55266 | SLVS841G table 5-1 | **PASS**: 1 IN, 2 GND, 3 EN (high = on), 4 FAULT, 5 ILIM, 6 OUT. ILIM 47 k from eq. 1-3: **506 / 557 / 616 mA** (min/typ/max), the old note said 504/552/600 | 42055 |
| TPL5010DDCR | C473912 | SNAS651A | **PASS**: 1 VDD, 2 GND, 3 DELAY/M_RST, 4 DONE, 5 WAKE, 6 RSTn. RSTn is open drain (needs a pull-up, added: SPICE F5). 6.79 k = 2 s (table 3) | 58979 |
| MCP73832T-2ACI/OT | C38066 | DS20001984H table 3-1 | **PASS**: SOT-23-5 1 STAT, 2 VSS, 3 VBAT, 4 VDD, 5 PROG. PROG 47 k -> 21 mA (valid 2-67 k). STAT is open drain on the 73832 (nRF input needs its pull-up) | 7291 |
| DRV5032FADMRR X2SON-4 | C2152496 | SLVSDC7H fig. 5-3 | **PASS**: 1 VCC, 2 GND, 3 NC, 4 OUT, thermal pad (GND); omnipolar push-pull active low, 20 Hz. Footprint dev 0.0 | 2087 |
| STM32C011F4U6 | C5456188 | DS13866 rev 5 | **FIXED** (M2). BOOT0 and bootloader: see below | 37 (low) |
| SN74AUP1G74DCUR | C140267 | SCES644D | **PASS**: 1 CLK, 2 D, 3 Q-bar (NC), 4 GND, 5 Q, 6 CLR, 7 PRE, 8 VCC; VCC 0.8-3.6 V | 17311 |
| TP74AUP1G08S5 (AND) | C48886815 | LCSC symbol (A, B, GND, Y, VCC), TI 74AUP1G08 as reference | pinout **PASS**, package **FIXED** (M4) | 1932 |
| TP74AUP1G00C5 | C51886116 | | replaced by the XOR (review C2); package SC-70-5 was right | 2990 |
| USBLC6-2SC6 | C7519 | ST datasheet via LCSC | **PASS**: 1/6 I/O1, 3/4 I/O2, 2 GND, 5 VBUS | 26191 |
| SKRPACE010 -> SKSCLAE010 | C139797 -> C130445 | ALPS drawings | **FIXED** (M3) | 873 |
| RGB LED SZYY1615RGB-B | C3029071 | vendor drawing | pins **PASS**, footprint **FIXED** (M5) | 10163 |
| FUET-4020 sounder | C391027 | vendor spec | **FIXED** (M6) | 1126 |
| 2N7002 | C8545 | LCSC symbol, JEDEC | **PASS**: 1 G, 2 S, 3 D | 6112747 |
| 1N4148W | C81598 | LCSC symbol | **PASS**: pin 1 = cathode (on VBAT), 2 = anode | 4496641 |
| WPN252012E1R0MT 1 uH | C370610 | LCSC | pads 2, footprint equivalent (1.9 vs 2.15 span); JLC lists 5 A | 6137 |
| 0402 R/C, 0603/0805 C | C25741 ... | LCSC | **PASS** (2-pin parts). C45783 (22 uF 0805) is **25 V** (JLC), not 6.3 V as the old note said; C19702 (10 uF 0603) is 10 V | all > 3000 |

## HJ-840: land pattern and antenna keep-out (C50052094)

* **Land pattern: verified.** 8 x 8 grid, 0.9 mm between rows A..H, 0.65 mm between columns 1..8, same as the LCSC footprint to 0.005 mm. A1 at the corner marked on the module; our footprint is the proper rotation of the LCSC one (no mirroring).
* **Antenna keep-out: NOT verifiable from the manual.** The manual (V1.8) gives no antenna dimensions (figure 7.1 has only symbols e1/e2/a/b), and the EasyEDA footprint has no keep-out drawing. What it says: no device or cable near the antenna, nothing on the back of the module, **no copper in the antenna area**, antenna toward a board edge/corner, A7/A8 are the antenna feed/board-antenna pads (pi match). Our keep-out (x 42.0-43.3 east of the module, all 6 layers, nothing on the opposite side) follows that rule with row A / A7 / A8 at the east edge, but the real antenna area on the module is **unmeasured**: ask HJSIP for the keep-out drawing or measure a sample before the layout is frozen. A steel M1.2 lid screw 2.3 mm from the module corner is flagged for the mechanics (use brass/A2).
* The "REG0 as 3V3 rail" topology: see below.

## STM32C011: package, BOOT0, bootloader pins

* UFQFPN20 3 x 3 x 0.55, 0.5 pitch, **no exposed pad** (DS13866 table 69). Pin table fixed (M2).
* **BOOT0 = PA14 (pin 17).** DS13866 table 12 note 3: *"upon reset this pin is configured as SWD alternate function, and the internal pull-up on PA13 and the internal pull-down on PA14 are activated"*, so the pin reads low by default and **no external BOOT0 pull-down is needed**. The pin only takes effect when the option bit `nBOOT_SEL` = 0 (DS13866 section 3.5: "the boot pin can be enabled through the boot selector option bit"); otherwise boot is decided by the `nBOOT0` option bit. A blank part from JLC boots the system loader through the empty-flash check, so the first flash over USART works; **the supervisor image must clear `nBOOT_SEL` (or the loader must write the option byte) so that the nRF can later enter the loader with BOOT0** (VERIFY against RM0490 section FLASH_OPTR; ST site not reachable from this container).
* **Bootloader pins.** DS13866 section 3.5: USART on PA9/PA10, I2C on PB6/PB7. On this package PA9/PA10 are remapped on package pins PA11/PA12 (14 / 15, "PA11 [PA9]", "PA12 [PA10]"); an AN2606 statement for packages with 20 pins or fewer is quoted on the ST community forum (nets SUP_TXD / SUP_RXD on pins 14 / 15 are consistent with it). Verify on the first board.
* **NRST** has an embedded weak pull-up (RST I/O structure, table 11); an external 100 k is added anyway (SPICE F5) because the TPL5010 RSTn is open drain.
* SWD of the supervisor: **SWDIO = PA13 (pin 16, net BPHASE), SWCLK = PA14 (pin 17, net SUP_BOOT0)**; test pads added on these nets (review M4).

## nRF52840 REG0 external load (HV mode, 3V3 rail = REG0 output)

* HJ-840 manual: HV mode (VDDH only, VDD not powered) is 2.5-5.5 V; flashing must be done in normal-voltage mode (VDD + VDDH about 3.3 V) as the netlist note already says.
* **External current limit:** the nRF52840 product specification v1.7 p. 84 is quoted on Nordic DevZone as *"external current draw allowed in High voltage mode when radio output power is lower than or equal to +4 dBm: 25 mA"*. The Nordic documentation site and DevZone were not directly readable from this container (HTTP 403), so this figure is **second-hand**; the radio TX power must be limited to +4 dBm or less. The old estimate of 4 to 7 mA is plausible: STM32C011 about 1-3 mA, DRV8835 VCC 0.45 mA typ (2 mA max), TMAG5273 2.3 mA while measuring, the rest below 0.2 mA: **worst case about 8 mA, margin about 3x**.
* **Dropout (new finding):** REG0 needs VDDH at least about 0.3 V above its output. With REGOUT0 = 3.3 V the rail only holds 3.3 V for VBAT above about 3.6 V and then follows VBAT - 0.3 V (2.7 V at a 3.0 V cell). Every rail consumer accepts 2.7 V (STM32 2-3.6, DRV8835 VCC 2-7, TPL5010 1.8-5.5, AUP gates 0.8-3.6, DRV5032 1.65-5.5), but the 2N7002 gate drive and the logic margins are smaller: **bring-up test at cell 3.0 / 3.4 / 4.2 V with the motor running**.
* The datasheet-quoted maximum VDD for the gates is 3.6 V, REG0 stays below that.

## Not changed but worth knowing

* **TPS2553 ILIM** 0.505 / 0.557 / 0.616 A (min/typ/max); the interlock text said 0.50 to 0.60 A.
* **Low stock at JLC (2026-11-20):** HJ-840 91, STM32C011F4U6 37, SKSCLAE010 873, FUET-4020 1126: fine for a 2-5 board prototype order, not for production.
* **Motor driver (resolved 2026-11-24):** DRV8835DSSR (C129328) had JLC stock 0; replaced by **2 x DRV8838DSGR (C86667, stock 1457)**, same PHASE/ENABLE truth table, pins checked in TI SLVSBA4F rev F (1 VM, 2 OUT1, 3 OUT2, 4 GND, 5 EN, 6 PH, 7 nSLEEP, 8 VCC, pad GND); the KiCad footprint `Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm` and the LCSC footprint have identical pad positions (rotation offset 0). See `../INTERLOCK.md` I.6b.
* **Live JLC stock 2026-11-24 of every BOM line:** all in stock; lowest STM32C011F4U6 35, HJ-840 85, SKSCLAE010 854, FUET-4020 1044.
