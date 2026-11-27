> TEST ONLY - NOT FOR HUMAN USE (see ../../../../DISCLAIMER.md). Bench only, **water only**: never insulin or any other drug, never on a person.

# Cart A main board: live stock, prices and cost per pump (2026-11-27)

Sources: **V** = read live on 2026-11-27 (JLC parts API snapshot `jlc_stock_2026-11-27.json` by `live_stock_a.py`), **E** = estimate.
Regenerate with `python3 live_stock_a.py`, then `python3 cost_cart_a.py 4` / `python3 cost_cart_a.py 6` after the JLC export. EUR, USD x 0.92.
Both boards carry the same BOM (same netlist, `jlc/` and `jlc-a6/` differ only in copper): the PCB line is the difference.

**Out of stock at JLC (V, 2026-11-27): STM32C011F4U6TR (C5456188), stock 0** (35 on 2026-11-25 for B): the supervisor of the
interlock; it is not replaceable without a netlist change. Low: HJ-840 68, AVX 9175 IDC 94 (both enough for 5 to 20 boards).

## Live JLC stock and unit prices (`jlc/BOM-jlcpcb.csv`)

| LCSC | Part | qty / board | stock | type | unit USD (5 boards) |
|---|---|---|---|---|---|
| C5456188 | STM32C011F4U6TR | 1 | 0 | extended | 1.9683 |
| C50052094 | HJ-840 | 1 | 68 | extended | 7.9729 |
| C7434809 | 009175002702996 | 1 | 94 | extended | 1.0997 |
| C86667 | DRV8838DSGR | 2 | 1085 | extended | 0.7129 |
| C223907 | TYPE-C-31-M-14 | 1 | 2103 | extended | 0.3649 |
| C48995440 | 74AUP1G86GW-TP | 1 | 3001 | extended | 0.0617 |
| C3716049 | TMAG5273A1QDBVR | 1 | 3149 | extended | 3.5743 |
| C38066 | MCP73832T-2ACI/OT | 1 | 3895 | extended | 0.9604 |
| C370610 | WPN252012E1R0MT | 1 | 5737 | extended | 0.0497 |
| C507223 | SN74AUP1G08DCKR | 2 | 7318 | extended | 0.3136 |
| C160857 | SPVS410100 | 1 | 7711 | extended | 0.2069 |
| C3029071 | SZYY1615RGB-B 4pin | 1 | 8367 | extended | 0.0456 |
| C54929506 | EM74AUP1G11GM | 1 | 9000 | extended | 0.1100 |
| C391027 | FUET-4020 | 1 | 9939 | extended | 0.8162 |
| C919459 | TPS61023DRLR | 1 | 10729 | extended | 0.2334 |
| C232391 | 2N7002WT1G | 1 | 14188 | extended | 0.0376 |
| C696092 | 532610471 | 1 | 14390 | extended | 0.1390 |
| C138719 | TPS2553DRVR | 1 | 19767 | extended | 0.5835 |
| C127465 | SKSGACE010 | 1 | 21634 | extended | 0.1451 |
| C140267 | SN74AUP1G74DCUR | 1 | 26227 | extended | 0.4950 |
| C2827693 | USBLC6-2P6 | 1 | 56975 | extended | 0.1559 |
| C473912 | TPL5010DDCR | 1 | 144941 | extended | 0.3540 |
| C25767 | 0402WGF2203TCE | 1 | 320770 | extended | 0.0013 |
| C15127 | AO3401A | 1 | 863495 | basic | 0.0822 |
| C25917 | 0402WGF6801TCE | 1 | 916434 | extended | 0.0012 |
| C2128 | 1N4148WS | 1 | 2782357 | basic | 0.0097 |
| C19666 | CL10A475KO8NNNC | 1 | 2826344 | basic | 0.0169 |
| C45783 | CL21A226MAQNNNE | 2 | 4360667 | basic | 0.0915 |
| C25792 | 0402WGF4702TCE | 2 | 4708028 | basic | 0.0019 |
| C25776 | 0402WGF3002TCE | 1 | 5142707 | extended | 0.0012 |
| C25905 | 0402WGF5101TCE | 2 | 5184963 | basic | 0.0014 |
| C23345 | 0603WAF220JT5E | 1 | 5312229 | basic | 0.0014 |
| C19702 | CL10A106KP8NNNC | 3 | 10249470 | basic | 0.0111 |
| C25741 | 0402WGF1003TCE | 9 | 10939050 | basic | 0.0009 |
| C25900 | 0402WGF4701TCE | 2 | 11734296 | basic | 0.0016 |
| C11702 | 0402WGF1001TCE | 1 | 25156201 | basic | 0.0010 |
| C1525 | CL05B104KO5NNNC | 10 | 28212445 | basic | 0.0029 |
| C25744 | 0402WGF1002TCE | 3 | 31144121 | basic | 0.0009 |

## 4-layer board (`cart_a.kicad_pcb`, preferred)
38 BOM lines, 25 extended, 256 solder joints per board (approx.)

| Boards (= pumps) | PCB (E) | parts | PCBA fees (E) | shipping (V) | import VAT 19 % | **total** | **per board** |
|---|---|---|---|---|---|---|---|
| 5 | 56.09 | 100.32 | 129.88 | 21.42 | 58.46 | **366** | **73.2** |
| 10 | 61.86 | 183.91 | 131.88 | 21.42 | 75.82 | **475** | **47.5** |
| 20 | 73.84 | 364.69 | 135.89 | 21.42 | 113.21 | **709** | **35.5** |

4-layer board (BOM from jlc/).
PCB (E): 4 layers 56.09 / 61.86 / 73.84 EUR at 5 / 10 / 20 (B's 4-layer quote + 33.3 high-precision extras, POFV not priced); B's 6-layer board for comparison 77.85 / 91.91 / 111.47 EUR (V)

## 6-layer board (`cart_a6.kicad_pcb`, fallback)
38 BOM lines, 25 extended, 256 solder joints per board (approx.)

| Boards (= pumps) | PCB (E) | parts | PCBA fees (E) | shipping (V) | import VAT 19 % | **total** | **per board** |
|---|---|---|---|---|---|---|---|
| 5 | 77.85 | 100.32 | 129.88 | 21.42 | 62.60 | **392** | **78.4** |
| 10 | 91.91 | 183.91 | 131.88 | 21.42 | 81.53 | **511** | **51.1** |
| 20 | 111.47 | 364.69 | 135.89 | 21.42 | 120.36 | **754** | **37.7** |

6-layer board (BOM from jlc-a6/).
PCB (E): 4 layers 56.09 / 61.86 / 73.84 EUR at 5 / 10 / 20 (B's 4-layer quote + 33.3 high-precision extras, POFV not priced); B's 6-layer board for comparison 77.85 / 91.91 / 111.47 EUR (V)

Difference at 5 boards: 6 layers +21.76 EUR on the PCB (77.85 vs 56.09), +25.9 EUR with VAT, +5.2 EUR per board. The 4-layer figure
is B's live 4-layer quote plus the high-precision extras B's 6-layer quote listed (0.2 mm drill, 4-wire test, TG155): **re-quote it**;
the 4-layer board also needs filled + capped vias in pads (HJ-840, U30 pad 6, USB D-, J2, driver pads), free on 6 layers but an
extra option on 4 layers that is **not priced** here. PCBA fees are JLC's published standard model (E).
