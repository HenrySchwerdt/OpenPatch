> **TEST ONLY - NOT FOR HUMAN USE** (see `../../../DISCLAIMER.md`). Bench sample, water only, never worn.

# COST: CUP main board (6 layers, 35.6 x 23.1 mm, 54 fitted parts), JLCPCB 6-layer + PCBA, 5 boards

Parts: unit prices from the live JLCPCB parts API on **2026-11-20** (`jlc_stock_2026-11-20.json`, tier price for 5 boards, `../tools/cost_cup.py`). **PCB, setup, stencil, shipping and VAT are estimates** (the JLC quote page needs a login and a Gerber upload); confirm them on the order page. Prices in USD, 1 USD = 0.92 EUR.

**Not orderable yet:** the board is only partly routed (73 connections open, see `ROUTING-GUIDE.md`) and **DRV8835DSSR (C129328) has JLC stock 0** (`PIN-CHECK.md`). The numbers below are what the order will cost once both are solved.

## Parts per board (generated)

| LCSC | Part | Per board | Unit USD (tier for 5 boards) | Line USD | JLC stock | Type |
|---|---|---|---|---|---|---|
| C50052094 | HJ-840 nRF52840 SiP | 1 | 7.9405 | 7.941 | 91 | extended |
| C5456188 | STM32C011F4U6 | 1 | 1.9603 | 1.960 | 37 | extended |
| C129328 | DRV8835DSSR | 1 | 1.1980 | 1.198 | 0 | extended |
| C38066 | MCP73832T-2ACI/OT | 1 | 0.9565 | 0.957 | 7291 | extended |
| C391027 | FUET-4020 SMD magnetic sounder | 1 | 0.8129 | 0.813 | 1126 | extended |
| C140267 | SN74AUP1G74DCUR | 1 | 0.6725 | 0.672 | 17311 | extended |
| C55266 | TPS2553DBVR | 1 | 0.5550 | 0.555 | 44052 | extended |
| C223907 | USB-C 16P sink-board TYPE-C-31-M-14 | 1 | 0.3634 | 0.363 | 2143 | extended |
| C473912 | TPL5010DDCR | 1 | 0.3526 | 0.353 | 58979 | extended |
| C2152496 | DRV5032FADMRR | 1 | 0.2914 | 0.291 | 2087 | extended |
| C919459 | TPS61023DRLR | 1 | 0.2325 | 0.233 | 139885 | extended |
| C45783 | 22uF | 2 | 0.1081 | 0.216 | 3558967 | basic |
| C130445 | SKSCLAE010 side tact | 1 | 0.1673 | 0.167 | 873 | extended |
| C7519 | USBLC6-2SC6 | 1 | 0.1558 | 0.156 | 26078 | extended |
| C48886815 | TP74AUP1G08S5 (AND) | 2 | 0.0601 | 0.120 | 1932 | extended |
| C54929506 | EM74AUP1G11GM (AND3) | 1 | 0.1096 | 0.110 | 9000 | extended |
| C48995440 | 74AUP1G86GW-TP (XOR) | 1 | 0.0614 | 0.061 | 3001 | extended |
| C19702 | 10uF | 3 | 0.0167 | 0.050 | 9950644 | basic |
| C370610 | 1uH 2520 (WPN252012E1R0MT) | 1 | 0.0495 | 0.050 | 6137 | extended |
| C3029071 | RGB LED SZYY1615RGB-B (common anode) | 1 | 0.0454 | 0.045 | 10163 | extended |
| C8545 | 2N7002 | 1 | 0.0156 | 0.016 | 6119023 | basic |
| C19666 | 4.7uF 16V 0603 | 1 | 0.0144 | 0.014 | 3172970 | basic |
| C81598 | 1N4148W (sounder flyback) | 1 | 0.0123 | 0.012 | 4493034 | basic |
| C1525 | 100nF | 4 | 0.0025 | 0.010 | 33911307 | basic |
| C25741 | 100k | 9 | 0.0008 | 0.007 | 12098284 | basic |
| C25792 | 47k | 2 | 0.0019 | 0.004 | 5341726 | basic |
| C25900 | 4.7k | 2 | 0.0017 | 0.003 | 12490043 | basic |
| C25744 | 10k | 2 | 0.0015 | 0.003 | 35418499 | basic |
| C25905 | 5.1k | 2 | 0.0014 | 0.003 | 4062226 | basic |
| C23345 | 22R 0603 | 1 | 0.0015 | 0.002 | 5561987 | basic |
| C25767 | 220k | 1 | 0.0013 | 0.001 | 351225 | extended |
| C17168 | pi match series 0R | 1 | 0.0012 | 0.001 | 13870377 | basic |
| C25917 | 6.8k | 1 | 0.0012 | 0.001 | 969388 | extended |
| C25776 | 30k | 1 | 0.0012 | 0.001 | 5107297 | extended |
| C11702 | 1k | 1 | 0.0011 | 0.001 | 29568761 | basic |

parts per board USD 16.39, 35 BOM lines (21 extended, 14 basic), 54 placements


The two cheapest lines carry the schedule risk, not the cost: **HJ-840 (91 in stock), STM32C011F4U6 (37 in stock)** and the **DRV8835 (0 in stock)** are the only parts with low or no stock. 21 of the 35 BOM lines are **extended** parts (each with the JLC setup fee); the 14 basic lines are free of it. No part is consigned. Everything is on JLC's own shelf (LCSC numbers in `jlc/BOM-jlcpcb.csv`) except the DRV8835 today.

## Order estimate: 5 PCBs, 5 assembled

| Line | USD | Note |
|---|---|---|
| PCB 6 layers 0.8 mm ENIG, 35.6 x 23.1 mm (381 mm2), 5 pcs | about 55 | estimate; 6-layer, ENIG chosen for the 0.65 x 0.9 mm LGA and the 0.5 mm USB-C pads |
| Standard PCBA (two sides) setup + stencils | about 30 | parts on both sides, so economic PCBA (one side only) is not possible |
| Extended parts fee, 21 x 3 | 63 | the largest single item |
| Assembly, about 250 joints per board | about 10 | |
| Components 5 x 16.4 | 82 | the 5-board tier prices above |
| **Subtotal** | **about 240** | |
| Shipping (DHL, 0.5 kg) | about 25 | |
| VAT / import (19 %) | about 50 | |
| **Total delivered** | **about 315 USD = about 290 EUR** | about 58 EUR per assembled board; the marginal cost of one more board in the same order is about 25 EUR (parts + assembly + PCB share) |

Not included: cell, motor, gears, housing, reservoir, cannula (see `../../../docs/BUY-LIST.md`), the 3 sets of rear-strip parts (TMAG5273 flex strip, separate order), spare HJ-840 / STM32 (order 2-3 extra: they are the parts most likely to sell out).

## Cost drivers and levers

1. Extended-part fee 63 USD (26 % of the order): 21 distinct extended lines. Three of them are resistors (6.8 k C25917, 220 k C25767, 30 k C25776); a basic-value divider that still gives 4.96 V on the 0.595 V feedback (if basic-library values exist for the ratio) would save 9 USD but changes the boost output tolerance: not worth a re-spin.
2. 4 layers instead of 6: not possible with the 0.65 x 0.9 mm LGA and 54 parts in 381 mm2.
3. DRV8835 replacement (DRV8837 x 2, C39159, stock 122885, 0.23 USD each) would add one placement and change the supervisor brake logic (`PIN-CHECK.md`).
