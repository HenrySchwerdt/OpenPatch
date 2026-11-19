> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). Bench electronics, never to be worn.

# Bench electronics cost (controller board, Rev A)

Prices are LCSC/JLCPCB list prices read from the JLCPCB parts API on 2026-11-19 (tier-1 unit price) plus JLCPCB fee schedules as known to the author. **The fee lines (PCB, setup, stencil, shipping) are estimates and must be confirmed in the JLCPCB quote before paying.**

## Parts per controller board (BOM-jlcpcb.csv, 37 lines, 119 placements)

| Group | Parts | USD |
|---|---|---|
| Extended parts (9 distinct) | E73-2G4M08S1CX 6.38, STSPIN220 1.96, TPL5010 0.35, INA180A1 0.29, SN74AUP1G74 x 3 2.02, USB-C TYPE-C-31-M-12 0.19, FH12-10S FFC 0.51, PicoBlade-compatible 4P 0.11, 1 ohm 0603 x 5 0.01 | 11.8 |
| Basic parts (resistors, caps, 2N7002 x 10, AO3401A, LM393, XC6206, LEDs, diodes, crystal, button) | 28 lines | 1.0 |
| **Components total per board** | | **about 12.8** |

Not assembled (DNP): BZ1 buzzer, J3 2 x 5 SWD header (extended parts, $3 setup fee each; use the Tag-Connect pads J2), J6 JST GH alternative, R97, R119.
Dropped for cost: USBLC6 TVS (extended). There is **no Basic equivalent** for the connectors, the 1 ohm resistors or any of the ICs, so the minimum is **9 extended parts** (5 are the safety-relevant ICs: E73, STSPIN220, TPL5010, SN74AUP1G74, INA180A1; the rest are USB-C, FFC, motor connector, 1 ohm). The earlier target of 6 is not reachable without removing USB power, the FFC or the motor connector.

## Minimum JLCPCB order for the controller alone: 5 PCBs, 2 assembled (estimate)

| Line | USD | Note |
|---|---|---|
| PCB 4-layer 1.6 mm, 44 x 60 mm, 5 pcs, ENIG not needed (HASL lead-free) | 10 | 2-layer (about $2) was tried first and did not route completely |
| SMT setup fee (economic, top side only) | 8 | |
| Stencil | 1.5 | |
| Extended parts fee, 9 x $3 | 27 | the largest single item |
| Assembly (about 400 joints x 2 boards) | 1.5 | |
| Components 2 x 12.8 plus min-quantity overage (e.g. 10 / 20 pcs of passives) | 29 | |
| **Subtotal before shipping** | **about 77** | |
| Shipping (DHL / UPS, 0.5 kg, EU) | 20 to 25 | |
| VAT / import (19 to 21 %, EU) | about 20 | |
| **Total, delivered** | **about 120** | |

Adding **5 pod sensor boards** (2-layer, 2 assembled): about $2 PCB + $8 setup + 3 extended parts x $3 (TMAG5273, DRV5032, FFC) + parts $6 = about $25 if ordered as a separate PCBA project. Panelising the pod board as a break-off tab on the controller order makes it one PCBA project (saves the second $8 setup and the shipping share, about $12 to $15) but needs a common board thickness (1.6 mm controller, pod wants 0.6 to 1.0 mm): a 1.0 mm controller board is acceptable electrically (the USB-C connector and M3 holes are not thickness sensitive), so **recommendation: 1.0 mm for both when the pod board is built** (the pod height budget is decided in `mechanical/`).

**Result: controller + pod boards about $95 to $145 delivered**, against the earlier target of $80 per iteration. The target is not met at the minimum order of two assembled boards because of the nine $3 extended-part fees and shipping; the overhead is charged once to the first pump.

## Levers (in order of effect), none of which touch a safety part

1. Order assembly of **one** controller (JLC minimum is 2 for economic PCBA; the second board is the spare) or accept 2.
2. Join pod and controller in one PCBA project (see above).
3. Do not assemble J1 (USB-C) but power through two bare pads: saves one extended fee ($3), costs the convenience.
4. Hand-fit the PicoBlade motor connector (no-soldering rule: not recommended).
5. 2-layer board ($8 saved) if a re-layout with more space routes completely; the controller was held at 4 layers because the 2-layer attempt left 9 nets unrouted (E73 pad fan-out) and a continuous GND plane under the module is wanted anyway.

## Reproduce

`python3 -I tools/jlccode.py <LCSC code>` prints stock, type and price for a code. Update this file with the checkout quote after the first order (and log it in `docs/05-cost-model.md`).
