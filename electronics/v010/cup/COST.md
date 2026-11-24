> **TEST ONLY - NOT FOR HUMAN USE** (see `../../../DISCLAIMER.md`). Bench sample, water only, never worn.

# COST: CUP main board (6 layers, 38.8 x 25.2 mm bounding box, 56 placements), JLCPCB 6-layer + PCBA, 5 boards

Parts: unit prices from the live JLCPCB parts API on **2026-11-24** (`jlc_stock_2026-11-24.json`, tier price for 5 boards, `../tools/cost_cup.py`). **PCB, setup, stencil, shipping and VAT are estimates** (the JLC quote page needs a login and a Gerber upload); confirm them on the order page. Prices in USD, 1 USD = 0.92 EUR.

**All parts are in JLC stock (2026-11-24).** The board is fully routed (DRC 0, `ROUTING-GUIDE.md`). The motor driver is now 2 x DRV8838 (C86667) instead of the DRV8835 (stock 0).

## Parts per board (generated)

| LCSC | Part | Per board | Unit USD (tier for 5 boards) | Line USD | JLC stock | Type |
|---|---|---|---|---|---|---|
| C50052094 | HJ-840 nRF52840 SiP | 1 | 7.9679 | 7.968 | 85 | extended |
| C5456188 | STM32C011F4U6 | 1 | 1.9670 | 1.967 | 35 | extended |
| C86667 | DRV8838DSGR | 2 | 0.7125 | 1.425 | 1457 | extended |
| C38066 | MCP73832T-2ACI/OT | 1 | 0.9598 | 0.960 | 5675 | extended |
| C391027 | FUET-4020 SMD magnetic sounder | 1 | 0.8157 | 0.816 | 1044 | extended |
| C140267 | SN74AUP1G74DCUR | 1 | 0.6748 | 0.675 | 17284 | extended |
| C507223 | SN74AUP1G08DCKR (AND) | 2 | 0.3134 | 0.627 | 7338 | extended |
| C138719 | TPS2553DRVR | 1 | 0.5831 | 0.583 | 21382 | extended |
| C223907 | USB-C 16P sink-board TYPE-C-31-M-14 | 1 | 0.3646 | 0.365 | 2068 | extended |
| C473912 | TPL5010DDCR | 1 | 0.3538 | 0.354 | 78072 | extended |
| C2152496 | DRV5032FADMRR | 1 | 0.2924 | 0.292 | 2042 | extended |
| C919459 | TPS61023DRLR | 1 | 0.2333 | 0.233 | 6244 | extended |
| C45783 | 22uF | 2 | 0.1085 | 0.217 | 4636784 | basic |
| C130445 | SKSCLAE010 side tact | 1 | 0.1679 | 0.168 | 854 | extended |
| C2827693 | USBLC6-2P6 | 1 | 0.1558 | 0.156 | 58327 | extended |
| C54929506 | EM74AUP1G11GM (AND3) | 1 | 0.1099 | 0.110 | 9000 | extended |
| C48995440 | 74AUP1G86GW-TP (XOR) | 1 | 0.0616 | 0.062 | 3001 | extended |
| C19702 | 10uF | 3 | 0.0168 | 0.050 | 9182843 | basic |
| C370610 | 1uH 2520 (WPN252012E1R0MT) | 1 | 0.0497 | 0.050 | 6157 | extended |
| C3029071 | RGB LED SZYY1615RGB-B (common anode) | 1 | 0.0456 | 0.046 | 8857 | extended |
| C232391 | 2N7002W | 1 | 0.0390 | 0.039 | 94422 | extended |
| C1525 | 100nF | 6 | 0.0029 | 0.017 | 32343591 | basic |
| C19666 | 4.7uF 16V 0603 | 1 | 0.0169 | 0.017 | 3020886 | basic |
| C2128 | 1N4148WS (sounder flyback) | 1 | 0.0098 | 0.010 | 3021684 | basic |
| C25741 | 100k | 9 | 0.0009 | 0.008 | 12322124 | basic |
| C25792 | 47k | 2 | 0.0019 | 0.004 | 5198502 | basic |
| C25900 | 4.7k | 2 | 0.0016 | 0.003 | 12612345 | basic |
| C25905 | 5.1k | 2 | 0.0014 | 0.003 | 5463731 | basic |
| C25744 | 10k | 2 | 0.0010 | 0.002 | 33864578 | basic |
| C23345 | 22R 0603 | 1 | 0.0014 | 0.001 | 5190528 | basic |
| C25767 | 220k | 1 | 0.0013 | 0.001 | 339564 | extended |
| C25917 | 6.8k | 1 | 0.0012 | 0.001 | 960436 | extended |
| C25776 | 30k | 1 | 0.0012 | 0.001 | 5088300 | extended |
| C11702 | 1k | 1 | 0.0011 | 0.001 | 28650140 | basic |

parts per board USD 17.23, 34 BOM lines (22 extended, 12 basic), 56 placements


The schedule risk is in two lines, not in the cost: **STM32C011F4U6 (35 in stock) and HJ-840 (85 in stock)** are the only parts with low stock; order 2-3 spares of each in the same order. 22 of the 34 BOM lines are **extended** parts (each with the JLC setup fee); the 12 basic lines are free of it. No part is consigned; every line is on JLC's own shelf (LCSC numbers in `jlc/BOM-jlcpcb.csv`).

## Order estimate: 5 PCBs, 5 assembled

| Line | USD | Note |
|---|---|---|
| PCB 6 layers 0.8 mm ENIG, 38.8 x 25.2 mm bounding box, 5 pcs, filled vias in pads | about 55 | estimate; 6-layer, ENIG chosen for the 0.65 x 0.9 mm LGA and the 0.5 mm USB-C pads |
| Standard PCBA (two sides) setup + stencils | about 30 | parts on both sides, so economic PCBA (one side only) is not possible |
| Extended parts fee, 22 x 3 | 66 | the largest single item |
| Assembly, about 250 joints per board | about 10 | |
| Components 5 x 17.2 | 86 | the 5-board tier prices above |
| **Subtotal** | **about 247** | |
| Shipping (DHL, 0.5 kg) | about 25 | |
| VAT / import (19 %) | about 52 | |
| **Total delivered** | **about 324 USD = about 300 EUR** | about 60 EUR per assembled board; the marginal cost of one more board in the same order is about 25 EUR (parts + assembly + PCB share) |

Not included: cell, motor, gears, housing, reservoir, cannula (see `../../../docs/BUY-LIST.md`), the 3 sets of rear-strip parts (TMAG5273 flex strip, separate order), spare HJ-840 / STM32 (order 2-3 extra: they are the parts most likely to sell out).

## Cost drivers and levers

1. Extended-part fee 66 USD (27 % of the order): 22 distinct extended lines. Three of them are resistors (6.8 k C25917, 220 k C25767, 30 k C25776); a basic-value divider that still gives 4.96 V on the 0.595 V feedback (if basic-library values exist for the ratio) would save 9 USD but changes the boost output tolerance: not worth a re-spin.
2. 4 layers instead of 6: not possible with the 0.65 x 0.9 mm LGA and 56 placements on this board.
3. Done 2026-11-24: the DRV8835 (stock 0) was replaced by 2 x DRV8838 (C86667, same PHASE/ENABLE logic, no firmware change), +3 placements, +0.2 USD per board.
