> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). v0.1.0 integrated pod board, water only.

# v0.1.0 board cost (5 PCBs, 3 assembled)

Parts: LCSC/JLCPCB list prices read from the JLCPCB parts API on 2026-11-19 (tier-1 unit price, `fab/bom_prices.csv`, `tools/cost.py`). **Fee lines (PCB, setup, stencil, shipping, VAT) are estimates; confirm in the JLCPCB quote before paying.** Excluded as in spec 1d: cell (not a JLC part), motor, mechanics, programmer.

## Parts per board: 48 BOM lines, 153 placements, **USD 22.2**

| Group | USD |
|---|---|
| E73 (7.70) + TMAG5273 (3.57) + STSPIN220 (1.96) + 4 x AUP1G74 (2.70) + LV4040 (1.19) + MCP73832 (0.96) + TLV7011 (0.56) + 2 x DRV5032AJ (0.75, **stock 0**) + TPL5010, INA180, gates, buzzer, connector, springs | about 21 |
| 15 x 2N7002, 3 x AO3401A, about 100 basic passives, diodes, LDO, crystal, LED, button | about 1.2 |

21 **extended** lines (each with the JLC setup fee): E73, TMAG5273, STSPIN220, TPL5010, INA180, TLV7011, MCP73832, AUP1G74, LV4040, 3 gate types, Schmitt, 2 x DRV5032, buzzer, PicoBlade, spring contacts, TVS, NTC, 1 ohm, 0.22 ohm, 4.7 M. No Basic equivalents exist for the ICs and connectors.

## Order: 5 PCBs, 3 assembled (estimate)

| Line | USD | Note |
|---|---|---|
| PCB 4L 0.8 mm ENIG 46.7 x 29 mm, 5 pcs | 35 | ENIG + 0.8 mm 4L; quote needed |
| Standard PCBA (two sides) setup + 2 stencils | 30 | economic PCBA is single-sided only |
| Extended parts fee, 21 x $3 | 63 | the largest single item |
| Assembly (about 900 joints x 3) | 5 | |
| Components 3 x 22.2 + minimum-quantity overage | 85 | |
| **Subtotal** | **about 218** | |
| Shipping (DHL, 0.5 kg) | 25 | |
| VAT/import 19 % | 46 | |
| **Total delivered** | **about 289 USD = about 266 EUR** (1 USD = 0.92 EUR) | |

Per assembled board **about 89 EUR averaged over 3**, about 40 EUR marginal (parts + assembly + share of PCB) for a 4th/5th board assembled in the same order. Cell, motor, gears, housing, reservoir are in `docs/v010/calc/cost.py`; they come on top (ARCHITECTURE section 6: 136 to 172 EUR per pod over a 4-pod order, now about +40 EUR because of the larger tail and 21 extended lines, **estimate**).

## Levers (none touches a safety part)

1. Assemble 2 boards instead of 3 (-22 USD parts).
2. Fewer extended lines: replace the 3 gate types by one (NOR with NFET logic, more parts), drop the 4.7 M (use 1 M, +3 uA idle current), one hall type.
3. The HJ-840 / 0201 / spring-pad variant (MINIATURIZATION.md) shrinks the PCB but keeps the extended-part fees.
4. Hand-fit the buzzer and PicoBlade only if JLC refuses bottom-side tall parts (not recommended, rule 1a).

Update this file with the real quote after the first order and log it in `docs/05-cost-model.md`.

## v2 split design (MAIN + USB + SENSOR; `fab/cost_v2.json`, `tools/cost_v2.py`), list prices 2026-11-19

| Board | BOM lines / placements | Parts USD | Extended lines | Stock warnings |
|---|---|---|---|---|
| MAIN | 47 / 134 | 16.6 (E73 7.70, STM32C011 1.47, STSPIN220 1.96, MT3608 0.10, inductor 0.04, charger 0.96, comparator 0.56, INA 0.29, FF 0.67 x 1, ...) | 21 | E73 `C356849` stock 1 |
| SENSOR | 5 / 6 | 4.8 (TMAG5273 3.57, 2 x DRV5032AJ 0.75, FFC 0.51) | 3 | DRV5032AJ `C2152498` stock 0 |
| USB | 9 / 10 | 1.0 (USB-C placeholder 0.19, TVS, ESD, FFC 0.51) | 4 | receptacle is a **placeholder** (IPX7 part to be confirmed) |
| **Per pod** | | **about 22.5** | **26 unique extended lines over the three boards** | |

JLC setup fee per extended line ($3, estimate): **26 x 3 = USD 78 per order**, three PCB types (MAIN 4L 0.8 mm about 42 x 32, SENSOR and USB 2L 0.8 mm) and three PCBA projects (or one PCBA project if JLC accepts the three designs panelised in one order: the quote decides), two FFC cables and PCB fees about USD 15 + 8 + 8 for 5 pieces each. Order of 5 pods, 3 assembled: parts 3 x 22.5 = 68 + minimum-quantity overage 25 + fees 78 + PCBs 31 + SMT setup 3 x 20 + assembly 8 + shipping 25 = **about 295 USD before VAT (about 350 USD incl. 19 % VAT, about 320 EUR)**, i.e. about 105 EUR per assembled pod averaged over 3, parts and assembly marginal about 45 EUR for pods 4 and 5. **All numbers are estimates.**

## v4 CUP pod: single 6-layer board (`design/netlist_v4.py`, `fab/cost_v4.json`), list prices read from the JLC parts API 2026-11-19

| Item | Value |
|---|---|
| CUP board | 136 placements, 49 BOM lines (116 placed parts with an LCSC number), **parts USD 10.1 per board** (STSPIN220 1.96, STM32C011 1.97, MCP73832 0.96, 5 x 2N7002DW 0.51, TLV7011 0.56, TPL5010 0.35, TPS61023 0.23, ...) |
| Not in that sum | ISP1807 (consigned, buy from Insight / distributors, about USD 10 to 12, **check price**), TMAG5273 + 100 nF on the REAR strip (USD 3.6 + FPC), cell, motor, USB-C receptacle is the HRO proxy (0.19) |
| Extended lines | **43 of 49 lines are JLC "extended"**: USD 3 each setup = **about USD 130 per order** (the largest fee; the three-board v3 design had 26) |
| PCB | 6 layers 0.8 mm ENIG, 528 mm2 L/U outline, 5 pcs: about USD 55 to 70 (**estimate**) against about USD 31 for the 4-layer MAIN plus two 2-layer boards of v2/v3; **6-layer delta about +USD 25 to 40 per order, but one PCB type and one PCBA project instead of three** (via-in-pad is only used for the ISP1807 inner pads and GND pads: ask for epoxy-filled and capped vias, +about USD 10 to 20 on the quote) |
| Stock warnings | `C2152498` DRV5032AJDMRR stock 0 (fallback `C2152496` DRV5032FADMRR, threshold fires about 4 mm early, PARTS-LOCK 10), `C5456188` STM32C011F4U6 stock 47 |

Order of 5 boards, 3 assembled (estimate, before VAT): parts 3 x (10.1 + ISP 11) = 63 + minimum-quantity overage 25 + extended fees 130 + PCB 6L 65 + SMT setup 25 + assembly 10 + FPC strips 15 + shipping 25 = **about USD 360 (about USD 430 with 19 % VAT, about EUR 400)**, about EUR 130 per assembled pod averaged over 3. **All numbers are estimates; confirm in the JLC quote.**
