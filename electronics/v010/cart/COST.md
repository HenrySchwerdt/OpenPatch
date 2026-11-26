> TEST ONLY - NOT FOR HUMAN USE (see ../../../DISCLAIMER.md). Bench only, water only.

# Cart main board (variant B, 57.0 x 10.6 mm, 6 layers): live stock, prices and cost per pump (2026-11-25)

Sources: **V** = read live on 2026-11-24/25 (JLC parts API snapshot `jlc_stock_2026-11-24.json` by `live_stock.py`; PCB prices on the JLC quote
page), **E** = estimate. Regenerate the tables with `python3 cost_cart.py` after `live_stock.py` and the JLC export. EUR, USD x 0.92.

## Live JLC stock and unit prices (all 34 BOM lines, `jlc/BOM-jlcpcb.csv`)
| LCSC | Part | qty / board | stock | type | unit USD (5 boards) |
|---|---|---|---|---|---|
| C5456188 | STM32C011F4U6TR | 1 | 35 | extended | 1.9670 |
| C50052094 | HJ-840 | 1 | 85 | extended | 7.9679 |
| C130445 | SKSCLAE010 | 1 | 842 | extended | 0.1679 |
| C391027 | FUET-4020 | 1 | 1044 | extended | 0.8157 |
| C86667 | DRV8838DSGR | 2 | 1442 | extended | 0.7125 |
| C223907 | TYPE-C-31-M-14 | 1 | 2218 | extended | 0.3646 |
| C48995440 | 74AUP1G86GW-TP | 1 | 3001 | extended | 0.0616 |
| C38066 | MCP73832T-2ACI/OT | 1 | 5677 | extended | 0.9598 |
| C370610 | WPN252012E1R0MT | 1 | 6148 | extended | 0.0497 |
| C507223 | SN74AUP1G08DCKR | 2 | 7338 | extended | 0.3134 |
| C3029071 | SZYY1615RGB-B 4pin | 1 | 8779 | extended | 0.0456 |
| C54929506 | EM74AUP1G11GM | 1 | 9000 | extended | 0.1099 |
| C140267 | SN74AUP1G74DCUR | 1 | 17284 | extended | 0.6748 |
| C138719 | TPS2553DRVR | 1 | 21367 | extended | 0.5831 |
| C2827693 | USBLC6-2P6 | 1 | 58333 | extended | 0.1558 |
| C232391 | 2N7002WT1G | 1 | 94412 | extended | 0.0390 |
| C473912 | TPL5010DDCR | 1 | 136954 | extended | 0.3538 |
| C919459 | TPS61023DRLR | 1 | 136957 | extended | 0.2333 |
| C25767 | 0402WGF2203TCE | 1 | 339055 | extended | 0.0013 |
| C25917 | 0402WGF6801TCE | 1 | 959901 | extended | 0.0012 |
| C15127 | AO3401A | 1 | 1088523 | basic | 0.0821 |
| C2128 | 1N4148WS | 1 | 2997747 | basic | 0.0098 |
| C19666 | CL10A475KO8NNNC | 1 | 3018929 | basic | 0.0169 |
| C45783 | CL21A226MAQNNNE | 2 | 4639692 | basic | 0.1085 |
| C25776 | 0402WGF3002TCE | 1 | 5089911 | extended | 0.0012 |
| C23345 | 0603WAF220JT5E | 1 | 5196277 | basic | 0.0014 |
| C25792 | 0402WGF4702TCE | 2 | 5199210 | basic | 0.0019 |
| C25905 | 0402WGF5101TCE | 2 | 5443900 | basic | 0.0014 |
| C19702 | CL10A106KP8NNNC | 3 | 9197783 | basic | 0.0139 |
| C25741 | 0402WGF1003TCE | 9 | 12289118 | basic | 0.0009 |
| C25900 | 0402WGF4701TCE | 2 | 12606118 | basic | 0.0016 |
| C11702 | 0402WGF1001TCE | 1 | 28571871 | basic | 0.0011 |
| C1525 | CL05B104KO5NNNC | 8 | 31894403 | basic | 0.0029 |
| C25744 | 0402WGF1002TCE | 2 | 33920153 | basic | 0.0010 |

34 BOM lines, 21 extended, 235 solder joints per board (approx.) (cup board: 22 / 12; the cart has no dock hall, +1 basic P-FET Q1).
**Stock warning:** STM32C011F4U6 (**35**) and HJ-840 (**85**) are low and shared with the cup-board order: 5 cart boards + 2 spares and
5 cup boards + 2 spares need 14 of each. Order both boards together or reserve the parts (JLC "parts pre-order") first.

## PCB (V, JLC quote page, 2026-11-25)
FR-4 **6 layers**, 57 x 10.6 mm, 0.8 mm, ENIG 1 U", 1 / 0.5 oz, via covering "Epoxy Filled & Capped" (POFV, default and free on 6 layers:
the board has filled vias in the HJ-840 and USB D- pads), min via 0.2 / 0.4 mm. The 0.2 mm via drill makes it a "high precision" board:
TG155 (+3.0), via tier (+15.2), 4-wire Kelvin test (+15.1) are added. 7-8 days build.
| PCBs | 5 | 10 | 20 |
|---|---|---|---|
| 6 layers as routed (V) | 77.85 | 91.91 | 111.47 |
| 4 layers, same outline (V 2026-11-24, did not route) | 22.79 | 28.56 | 40.54 |

## Board cost per pump (PCB + parts + assembly)
PCBA fees (E): standard two-sided PCBA, setup 25 USD + stencil 7 USD per side, 3 USD per extended part line (21), 0.0017 USD per joint; DHL
21.42 EUR (V); 19 % import VAT on everything.
| Boards (= pumps) | PCB (V) | parts | PCBA fees (E) | shipping (V) | import VAT 19 % | **total** | **per board** |
|---|---|---|---|---|---|---|---|
| 5 | 77.85 | 78.28 | 118.68 | 21.42 | 56.28 | **353** | **70.5** |
| 10 | 91.91 | 145.73 | 120.52 | 21.42 | 72.12 | **452** | **45.2** |
| 20 | 111.47 | 288.33 | 124.19 | 21.42 | 103.63 | **649** | **32.5** |

## Cost per pump (board above + mechanics)
Mechanics, motor, gears, rod, magnets, cell, screws, printed housing and the TMAG strip share from `../../../docs/CART-ORDER.md` (E there:
about 30 / 24 / 20 EUR per pump at 5 / 10 / 20). The adapter-lock hall strip (DRV5032 + 100 nF) is not designed yet: about 1-2 EUR (E).
| Pumps | board / pump | mechanics / pump (E) | **pump total** |
|---|---|---|---|
| 5 | 70.5 | 30.1 | **101** |
| 10 | 45.2 | 24.0 | **69** |
| 20 | 32.5 | 20.0 | **52** |

**Verdict:** 5 pumps cost about **101 EUR** each, **above the 80 EUR maximum** (the 6-layer high-precision PCB and the fixed PCBA fees land on 5 boards); **10 pumps about 69 EUR** (inside 40-80), 20 about 52 EUR. Recommendation: order 10 boards.
Fixed fees dominate at 5 (PCBA setup + stencils + extended-part fees about 119 EUR, the 6-layer high-precision PCB about 78). Levers, in order:
(1) order 10-20 boards in one batch; (2) together with the cup boards in one PCBA order (one shipment, one set of extended-part fees only
if JLC pools them per order: check on the quote page); (3) a 0.25 mm via drill tier would remove the 15 EUR via surcharge but needs a
re-route with 0.45 mm vias (not done: the board routes only just); (4) the basic-part swaps listed in CART-ORDER (220 k, 30 k, 6.8 k).
Not cut: the interlock parts (TPL5010, supervisor, TPS2553, AND / XOR gates) and the safety sensors (spec §1d).
