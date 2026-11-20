> TEST ONLY - NOT FOR HUMAN USE (see ../../../DISCLAIMER.md). Water only, never worn.

# PART-AUDIT: every part of the CUP board netlist v4 (80 parts after this audit; 91 before; frozen routed fallback `cup_v4r91_routed.kicad_pcb` of the 91-part version)

Frozen fallback of the 91-part STSPIN220 board: `cup_v4r91_routed.kicad_pcb`, Freerouting 40 passes (11 min): 206 unrouted nets at the start, 55 unrouted at the end (about 73 % of the connections routed, 44 unconnected items after zone fill, 22 copper-edge errors and 4 starved thermals in DRC, no clearance/short errors). Netlist: `design/netlist_v4_r91_stspin.py`.

## Before / after
| Block | 91 parts | 80 parts | Change |
|---|---|---|---|
| mcu | 6 | 4 | C1, R1 removed |
| drv | 11 | 6 | STSPIN220 + 9 support parts -> DRV8835 + 2 bypass caps + 2 pull-downs + VM bulk |
| mot | 1 (socket) | 4 (pads) | J1 -> 4 solder pads MP1..MP4 |
| rear | 6 | 4 | I2C pull-ups removed |
| sup | 6 | 6 | R80 removed, second AND gate U35 added |
| wdt | 6 | 5 | R18 removed |
| sw | 12 | 11 | R24 removed |
| boost | 8 | 7 | CB2 removed |
| tp | 2 | 0 | TP1, TP2 removed |

## Kept parts (all 80)
| Ref | Value | Block | Why it exists | Required by | Decision |
|---|---|---|---|---|---|
| U1 | HJ-840 nRF52840 SiP | mcu | Radio + BLE + USB DFU + all application GPIO | spec 4 (radio), 6 (USB DFU) | keep |
| PI1 | pi match shunt C (DNP) | mcu | pi match shunt C, tuning of the internal antenna (DNP) | HJ-840 manual 3.2.1 | keep (DNP footprint) |
| PI2 | pi match series 0R | mcu | 0 ohm A7 to A8 = internal antenna | HJ-840 manual 3.2.1 | keep |
| PI3 | pi match shunt C (DNP) | mcu | pi match shunt C (DNP) | HJ-840 manual 3.2.1 | keep (DNP footprint) |
| SP1 | cell lead pad + | batt | cell lead pad + | battery (user solders the wires) | keep |
| SP2 | cell lead pad - | batt | cell lead pad - | battery | keep |
| C5 | 10uF | pwr | VBAT bulk (cell, LDO and boost input) | power | keep |
| U2 | XC6206P332MR-G | pwr | 3V3 LDO for the logic | power | keep |
| C7 | 10uF | pwr | 3V3 bulk at the LDO | power (HJ-840 manual: 4.7 uF on VDD in the reference) | keep |
| JU1 | USB-C receptacle (proxy: TYPE-C-31-M | usb | USB-C receptacle (charge + DFU), PROXY part | spec 2d | keep (part to be replaced by a mid-mount) |
| DU1 | SMF5.0A TVS | usb | TVS on VBUS (hot-plug) | USB-C hot plug protection | keep (low value; could go: USBLC6 clamps VBUS) |
| RU1 | 5.1k | usb | CC1 5.1k (sink) | USB-C | keep |
| RU2 | 5.1k | usb | CC2 5.1k (sink) | USB-C | keep |
| UU1 | USBLC6-2SC6 | usb | ESD array on D+/D- | USB ESD | keep |
| CU1 | 10uF | usb | VBUS bulk | charger input | keep |
| U3 | MCP73832T-2ACI/OT | chg | LiPo charger MCP73832 | spec 2d (rechargeable) | keep |
| R3 | 47k | chg | PROG 47k = 21 mA | charger | keep |
| R6 | 1M | sense | VBAT sense divider top | undervoltage lockout (INTERLOCK I.2) | keep |
| R7 | 1M | sense | VBAT sense divider bottom | same | keep |
| C10 | 100nF | sense | SAADC sample hold on the sense node | same | keep |
| U7 | DRV8835DSSR | drv | DRV8835 dual H-bridge | motor drive | NEW (replaces STSPIN220 + 9 parts) |
| C23 | 100nF | drv | VM bypass (datasheet: 0.1 uF minimum) | DRV8835 SLVSB18H | keep |
| C19 | 100nF | drv | VCC bypass (0.1 uF minimum) | DRV8835 | keep |
| R43 | 100k | drv | AENBL_MCU pull-down (gate input defined at reset) | default off | keep |
| R93 | 100k | drv | BENBL_MCU pull-down | default off | keep |
| C21 | 22uF | drv | VM bulk 22 uF | motor supply | keep |
| MP1 | motor lead pad A+ | mot | motor lead pad A+ | motor (user solders the wires) | keep |
| MP2 | motor lead pad A- | mot | motor lead pad A- | motor | keep |
| MP3 | motor lead pad B+ | mot | motor lead pad B+ | motor | keep |
| MP4 | motor lead pad B- | mot | motor lead pad B- | motor | keep |
| TL1 | REAR strip pad (3V3) | rear | REAR strip pad 3V3 | TMAG5273 on the REAR strip | keep |
| TL2 | REAR strip pad (GND) | rear | REAR strip pad GND | same | keep |
| TL3 | REAR strip pad (I2C_SDA) | rear | REAR strip pad SDA | same | keep |
| TL4 | REAR strip pad (I2C_SCL) | rear | REAR strip pad SCL | same | keep |
| LD1 | RGB LED SZYY1615RGB-B (common anode) | ui | RGB status LED (user request) | UI | keep |
| R74 | 1k | ui | LED anode resistor | UI | keep |
| D5 | 1N4148W | ui | charging indicator diode-OR with the red channel (works while the MCU sleeps) | UI request | keep |
| SW1 | SKRPACE010 side tact | ui | side tact button | UI request | keep |
| BZ1 | FUET-4020 SMD magnetic sounder | ui | on-board sounder | UI request | keep |
| D6 | 1N4148W (sounder flyback) | ui | sounder flyback | magnetic coil | keep |
| RDA | 100k | ui | sounder NFET gate pull-down (default off) | safety default | keep |
| U4A | DRV5032FADMRR | dock | dock hall | spec 7 (dock interlock) | keep |
| R21 | 100k | dock | hall inverter pull-up | dock gate | keep |
| U30 | STM32C011F4U6 | sup | supervisor MCU | spec 7a | keep |
| C50 | 100nF | sup | supervisor decoupling | supervisor | keep |
| R79 | 100k | sup | BOOT0 pull-down (normal boot) | supervisor flashing by the nRF | keep |
| R81 | 100k | sup | SUP_STCK_EN pull-down (default blocked) | HW budget gate | keep |
| U31 | SN74AUP1G08DCKR (AND, A bridge) | sup | AND gate AENBL = AENBL_MCU AND SUP_STCK_EN | step budget gate | keep |
| U35 | TP74AUP1G08S5 (AND, B bridge) | sup | AND gate for BENBL | same | NEW |
| U5 | TPL5010DDCR | wdt | TPL5010 watchdog | spec 7 (hardware watchdog, CLAUDE.md) | keep |
| R26 | 10k | wdt | TPL5010 delay resistor | watchdog 2 s | keep |
| U6 | SN74AUP1G74DCUR | wdt | interlock latch | spec 7 (hardware cut path) | keep |
| U32 | TP74AUP1G08S5 (AND) | wdt | latch clear = SUP_NRST AND OC_OK | spec 7 | keep |
| R29 | 100k | wdt | ARM_CLK pull-down (latch clock defined at reset) | safety default | keep |
| R82 | 100k | sw | SUP_PERMIT pull-down (boost off at reset) | safety default | keep |
| R16 | 100k | sw | MOT_DIR pull-down (forward default) | hardware gate input | keep |
| Q7 | 2N7002 | sw | hall inverter | dock gate | keep (could go if a high-active hall is used) |
| QBA | 2N7002 | ui | sounder NFET | UI | keep |
| U33 | TP74AUP1G32S5 (OR) | sw | OR gate DOCKED OR reverse | dock interlock | keep |
| U34 | TP74AUP1G08S5 (AND) | sw | AND gate LATCH AND DOCK_OR = MOT_ALLOW | hardware cut path | keep |
| R90 | 100k | sw | EN pull-down of the load switch | safety default | keep |
| U20 | TPS2553DBVR | sw | TPS2553 current-limited switch (hardware cut + over-current) | spec 7 | keep |
| R91 | 56k | sw | ILIM resistor | over-current | keep (47 k after this change) |
| R92 | 100k | sw | FAULT pull-up | OC_OK level | keep |
| C60 | 100nF | sw | load switch IN bypass | datasheet recommendation | keep |
| R25 | 10k | sw | VMOT bleeder (cap discharge after a cut) | keeps VMOT from floating | keep |
| R57 | 100k | oc | VMOT_SENSE divider top | cut-proof POST | keep |
| R58 | 100k | oc | VMOT_SENSE bottom | same | keep |
| U8 | TPS61023DRLR | boost | 5 V boost | motor 4.8 V rating | keep |
| L1 | 1uH 2520 (WPN252012E1R0MT) | boost | boost inductor | boost | keep |
| R55 | 220k | boost | boost FB top | boost | keep |
| R56 | 30k | boost | boost FB bottom | boost | keep |
| DZ1 | BZT52C6V2 (VMOT overvoltage clamp) | boost | 6.2 V clamp on the boost output | protects VM (11 V) if FB opens | keep (remove if the TPS61023 OVP is confirmed) |
| CB1 | 22uF 6.3V X5R 0805 | boost | boost output bulk | boost | keep |
| C31 | 10uF | boost | boost output 10 uF | boost | keep |
| J10 | SWD pad SWDIO | swd | SWD pad SWDIO | one-time flash | keep |
| J11 | SWD pad SWDCLK | swd | SWD pad SWDCLK | same | keep |
| J12 | SWD pad NRST | swd | SWD pad NRST | same | keep |
| J13 | SWD pad GND | swd | SWD pad GND | same | keep |
| J14 | SWD pad 3V3 | swd | SWD pad 3V3 | same | keep |

## Removed / replaced
| Ref | Why it existed | Decision |
|---|---|---|
| C1 | 3V3 decoupling at the HJ-840 (module has its own filter caps, manual section 6) | removed |
| R1 | NRST pull-up (nRF has an internal pull-up on the reset pin, pin is connected to I/O) | removed |
| R67 | I2C pull-up (use the nRF internal pull-ups at 100 kHz on the 30 mm strip; fit external 4.7 k if the bus is flaky) | removed |
| R68 | I2C pull-up | removed |
| R80 | SUP_NRST pull-up (STM32 NRST has an internal pull-up, TPL5010 drives it push-pull) | removed |
| R18 | MCU_EN pull-down (supervisor input: use its internal pull-down) | removed |
| R24 | VMOT_PRE bleeder (the load switch isolates the motor side; the boost output decays through its FB divider) | removed (legacy of the series P-FET switch) |
| CB2 | second boost bulk cap (needed for the chopper ripple only) | removed |
| TP1 | test pad VMOT (legacy of the three-board bench era) | removed |
| TP2 | test pad STCK_DRV (the signal no longer exists) | removed |
| J1 | motor socket (the motor lead is cut and soldered to 4 pads) | replaced by MP1-MP4 |
| R34 | STSPIN220 sense 1 ohm A | gone with the STSPIN220 |
| R35 | STSPIN220 sense B | gone |
| R36 | TOFF resistor | gone |
| R37 | VREF divider top | gone |
| R38 | VREF divider bottom | gone |
| R39 | STBY pull-down | gone |
| R40 | EN/FAULT pull-up | gone |

## Legacy check (v1 to v3 multi-board era)
Bleeders (Q17/Q17B and two resistors), test pads, OC_TEST/DOCK_TEST hooks, the series P-FET pair, the INA/comparator chain, diodes of the old latch clear, board-to-board pads, SENSOR/USB boards: all gone in earlier passes; this audit removed the last pieces (R24, TP1/TP2, R67/R68, R18, R80, C1, R1, CB2). Remaining judgement calls: DU1 (TVS on VBUS) and DZ1 (boost output clamp) are kept as cheap protection; Q7 + R21 (hall inverter) could be replaced by a high-active hall.

## Does the dock leg / side_a block still need to exist without J1?
* **Dock leg: yes**, it carries the dock hall U4A (hangs below the board at (39.36, 11.75), z 4.9 to 5.3) and its 3V3, GND and `DOCK_N` traces; the hall must sit over the dock magnet in the pocket roof area.
* **side_a: shrink.** It only has to hold the **side button** SW1 at (39.8, 1.0 actuator tip, 3.0 body centre): the widening to x 35.4 to 44.2 was for J1 (8 mm wide). The outline now ends the corridor at y 1.1 with the corridor width (x 36.0 to 42.0, 6 mm): the block shrinks from 8.8 x 5.35 to 6.0 x 5.25 minus the old corridor, about 15 mm2 saved, and the bottom side of the corridor end is free (sounder BZ1 stays in side_b).
* side_b (x 35.4 to 42, y 17.15 to 22.9) keeps the 2.0 mm sounder on the bottom.

<!-- GENERATED:BEGIN (tools/gen_cup_docs.py) -->
## Current part list (generated from `netlist_v4_cup.json`: 54 fitted parts, 31 without BOM: pads / DNP)

| Ref | Value | LCSC | Footprint | Group | Nets |
|---|---|---|---|---|---|
| U1 | HJ-840 nRF52840 SiP | C50052094 | HJ840 | mcu | 3V3, AENBL, ANT_A, ANT_B, APHASE, ARM_CLK, BENBL, BPHASE, BTN_N, BUZ_A, CHG_STAT, DOCK_N, GND, I2C_SCL, I2C_SDA, LATCH_Q, LED_B, LED_G, LED_R, MCU_EN, MOT_FWD, NRST, OC_OK, SUP_BOOT0, SUP_NRST, SUP_OK, SUP_RXD, SUP_TXD, SWDCLK, SWDIO, USB_DM, USB_DP, VBAT, VBUS_P, VMOT_SENSE |
| C70 | 4.7uF 16V 0603 | C19666 | C_0603_1608Metric | mcu | 3V3, GND |
| PI2 | pi match series 0R | C17168 | R_0402_1005Metric | mcu | ANT_A, ANT_B |
| C5 | 10uF | C19702 | C_0603_1608Metric | pwr | GND, VBAT |
| JU1 | USB-C 16P sink-board TYPE-C-31-M-14 | C223907 | USB_C_HRO_31_M_14 | usb | CC1, CC2, GND, USB_DM, USB_DP, VBUS_P |
| RU1 | 5.1k | C25905 | R_0402_1005Metric | usb | CC1, GND |
| RU2 | 5.1k | C25905 | R_0402_1005Metric | usb | CC2, GND |
| UU1 | USBLC6-2SC6 | C7519 | SOT-23-6 | usb | GND, USB_DM, USB_DP, VBUS_P |
| CU1 | 10uF | C19702 | C_0603_1608Metric | usb | GND, VBUS_P |
| U3 | MCP73832T-2ACI/OT | C38066 | SOT-23-5 | chg | CHG_PROG, CHG_STAT, GND, VBAT, VBUS_P |
| R3 | 47k | C25792 | R_0402_1005Metric | chg | CHG_PROG, GND |
| U7 | DRV8835DSSR | C129328 | WSON-12-1EP_3x2mm_P0.5mm_EP1x2.65 | drv | 3V3, AENBL, APHASE, BENBL, BPHASE, GND, MOT_A1, MOT_A2, MOT_B1, MOT_B2, VMOT |
| C19 | 100nF | C1525 | C_0402_1005Metric | drv | 3V3, GND |
| C21 | 22uF | C45783 | C_0805_2012Metric | drv | GND, VMOT |
| LD1 | RGB LED SZYY1615RGB-B (common anode) | C3029071 | LED_RGB_1615_4P | ui | LED_A, LED_B, LED_G, LED_R |
| R74 | 1k | C11702 | R_0402_1005Metric | ui | LED_A, VBAT |
| SW1 | SKSCLAE010 side tact | C130445 | SW_SKSCLAE010 | ui | BTN_N, GND |
| BZ1 | FUET-4020 SMD magnetic sounder | C391027 | BZ_4020 | ui | PZ_C, VBAT |
| D6 | 1N4148W (sounder flyback) | C81598 | D_SOD-123 | ui | PZ_C, VBAT |
| RDA | 100k | C25741 | R_0402_1005Metric | ui | BUZ_A, GND |
| RBZ | 22R 0603 | C23345 | R_0603_1608Metric | ui | PZ_A, PZ_C |
| RI1 | 4.7k | C25900 | R_0402_1005Metric | mcu | 3V3, I2C_SDA |
| RI2 | 4.7k | C25900 | R_0402_1005Metric | mcu | 3V3, I2C_SCL |
| U4A | DRV5032FADMRR | C2152496 | DRV5032_X2SON-4_DMR0004B | dock | 3V3, DOCK_N, GND |
| U30 | STM32C011F4U6 | C5456188 | UFQFPN-20_3x3_P0.5 | sup | 3V3, APHASE, ARM_CLK, BPHASE, DOCK_N, GND, MCU_EN, MOT_FWD, NRST, OC_OK, SUP_BOOT0, SUP_DONE, SUP_NRST, SUP_OK, SUP_PERMIT, SUP_RXD, SUP_TXD, SUP_WAKE |
| C50 | 100nF | C1525 | C_0402_1005Metric | sup | 3V3, GND |
| U5 | TPL5010DDCR | C473912 | SOT-23-6 | wdt | 3V3, GND, SUP_DONE, SUP_NRST, SUP_WAKE, WDT_DELAY |
| R26 | 6.8k | C25917 | R_0402_1005Metric | wdt | GND, WDT_DELAY |
| U6 | SN74AUP1G74DCUR | C140267 | VSSOP-8_2.3x2mm_P0.5mm | wdt | 3V3, ARM_CLK, GND, LATCH_CLR_N, LATCH_Q |
| U32 | TP74AUP1G08S5 (AND) | C48886815 | SOT-23-5 | wdt | 3V3, GND, LATCH_CLR_N, OC_OK, SUP_NRST |
| R29 | 100k | C25741 | R_0402_1005Metric | wdt | ARM_CLK, GND |
| R82 | 100k | C25741 | R_0402_1005Metric | sw | GND, SUP_PERMIT |
| R16 | 100k | C25741 | R_0402_1005Metric | sw | 3V3, MOT_FWD |
| QBA | 2N7002 | C8545 | SOT-23 | ui | BUZ_A, GND, PZ_A |
| U33 | 74AUP1G86GW-TP (XOR) | C48995440 | SOT-353_SC-70-5 | sw | 3V3, DOCK_N, DOCK_XOR, GND, MOT_FWD |
| U36 | EM74AUP1G11GM (AND3) | C54929506 | UFDFN-6_1.45x1.0_P0.5 | sw | 3V3, GND, LATCH_Q, MCU_EN, PERM_L, SUP_PERMIT |
| R18 | 100k | C25741 | R_0402_1005Metric | sw | GND, MCU_EN |
| U34 | TP74AUP1G08S5 (AND) | C48886815 | SOT-23-5 | sw | 3V3, DOCK_XOR, GND, MOT_ALLOW, PERM_L |
| R90 | 100k | C25741 | R_0402_1005Metric | sw | GND, MOT_ALLOW |
| RDK | 100k | C25741 | R_0402_1005Metric | sw | 3V3, DOCK_N |
| RNR | 100k | C25741 | R_0402_1005Metric | wdt | 3V3, SUP_NRST |
| C61 | 100nF | C1525 | C_0402_1005Metric | drv | GND, VMOT |
| C71 | 10uF 10V 0603 | C19702 | C_0603_1608Metric | boost | GND, VBAT |
| U20 | TPS2553DBVR | C55266 | SOT-23-6 | sw | GND, ILIM, MOT_ALLOW, OC_OK, VMOT, VMOT_PRE |
| R91 | 47k | C25792 | R_0402_1005Metric | sw | GND, ILIM |
| R92 | 100k | C25741 | R_0402_1005Metric | sw | 3V3, OC_OK |
| C60 | 100nF | C1525 | C_0402_1005Metric | sw | GND, VMOT_PRE |
| R57 | 10k | C25744 | R_0402_1005Metric | oc | VMOT, VMOT_SENSE |
| R58 | 10k | C25744 | R_0402_1005Metric | oc | GND, VMOT_SENSE |
| U8 | TPS61023DRLR | C919459 | SOT-563 | boost | BST_FB, BST_SW, GND, SUP_PERMIT, VBAT, VMOT_PRE |
| L1 | 1uH 2520 (WPN252012E1R0MT) | C370610 | L_1008_2520Metric | boost | BST_SW, VBAT |
| R55 | 220k | C25767 | R_0402_1005Metric | boost | BST_FB, VMOT_PRE |
| R56 | 30k | C25776 | R_0402_1005Metric | boost | BST_FB, GND |
| CB1 | 22uF 6.3V X5R 0805 | C45783 | C_0805_2012Metric | boost | GND, VMOT_PRE |

Not fitted by the assembler (bare pads, wire pads, DNP match parts): PI1 (DNP), PI3 (DNP), SP1, SP2, MP1, MP2, MP3, MP4, TL1, TL2, TL3, TL4, TP1, TP2, TP3, TP4, TP5, TP6, TP7, TP8, TP9, TP10, TP11, TP12, TP13, TP14, J10, J11, J12, J13, J14.
<!-- GENERATED:END -->
