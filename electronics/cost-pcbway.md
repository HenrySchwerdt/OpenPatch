# Cost estimate: 5 assembled OP-100 boards at PCBWay (Rev A)

> As of 2026-11-18. **All PCBWay prices are estimates**: only the PCBWay online quote with the real BOM gives a binding figure. All that was found: part prices at LCSC/DigiKey (web search), "setup fee 88 – 150 USD" and "10 – 30 % markup on components" from third-party sources that cannot be verified; Faulhaber quotes "price on request" for the DM0620. Currency EUR, net, import VAT of 19 % (DE) not included (line below).

## Assumptions

* 5 boards, 4 layers, 0.6 mm, ENIG, board 17.1 × 29 mm with a corner cutout (per mechanical/out/OP-100.layout.json; small area = hardly any price advantage, fixed costs dominate), panel/array per PCBWay.
* Turnkey (PCBWay sources the parts): ~42 part types, ~75 placements/board (no QFN48/crystals/RF network any more thanks to the module), double-sided, 3 WCSP/DSBGA (BQ51003, BQ25120A, TPS22916C), 1 LGA-78 module (ISP1807, 0.65 mm), X2SON, 0402.
* By hand/separately: Qi coil, LiPo, motor, magnets, housing (not PCBWay SMT).
* Part prices/board from `bom.csv`: SMT parts incl. piezo/button **20.20 EUR** (of which ISP1807 module ~10.3 EUR, price @1 ~11.2 USD from the LCSC/Mouser listing), coil 4.00 EUR.

## Line items (5 boards)

| Item | Low | Mid | High | Remark |
|---|---:|---:|---:|---|
| PCB 4L 0.6 mm ENIG, 5 pcs | 35 | 45 | 70 | 0.6 mm + ENIG + 4L/via-in-pad (0.4 mm BGA) may cost a surcharge |
| Assembly setup | 60 | 85 | 150 | Third-party source: 88–150 USD |
| Stencil | 0 | 15 | 25 | partly included |
| Assembly/soldering (75 parts × 5, 2 sides, 3 BGA types + LGA/X-ray) | 55 | 110 | 190 | biggest uncertainty factor |
| Parts 5 × 20.20 + minimum quantities + 20 % markup | 120 | 150 | 215 | 0402 reel quantities (MOQ), special parts without an LCSC no. (ISP1807 possibly customer-supplied, U6, U7, U9/10, Q2, D1/D2, L4) via DigiKey/Mouser |
| Shipping PCBWay → DE (DHL/UPS) | 25 | 35 | 45 | |
| **Subtotal boards** | **265** | **415** | **665** | |
| Qi coils Ø17.6 (flex PCB spiral/Rx coil) 6 × 4 | 15 | 24 | 40 | Flex spiral at PCBWay or a special coil; type unverified (Würth 760308101104 is a TX coil!) |
| LiPo special format ≤ 3.2 × 17.4 × 17.2 mm (~40 mAh) + PCM, 6 pcs | 15 | 21 | 40 | 302020 (20 × 20) does not fit in the OP-100 layout (length limited to 17.4 mm) → special format/MOQ |
| Magnets Ø2 × 1 diametral | 3 | 4 | 8 | |
| **3 housing sets (PCBWay SLA/MJF)** | 40 | 60 | 110 | per set body + lid + reservoir shell; MJF PA12 ~12–20 EUR/set, SLA resin similar, + shipping/minimum order |
| Small parts (silicone septum, 30G needle, glue, screws, wire) | 20 | 30 | 40 | |

## Motors – both price variants

| Variant | Unit price | 6 pcs (5 + 1 spare) | Remark |
|---|---:|---:|---|
| **A: generic Ø6 mm 2-phase stepper + planetary gearbox + leadscrew** (AliExpress/eBay/Fruugo class) | ~6 – 12 EUR (mid 9) | **36 / 54 / 72** | Stepper alone 1–5 EUR (eBay finds, 0.99–4.98 USD), with gearbox + leadscrew + shipping ~8–12 EUR. No suitable datasheet evidence for 20 steps/rev, torque, lifetime – high spread/backlash → encoder verification mandatory. Namiki micromotors: no verifiable price found. |
| **B: Faulhaber ADM0620/DM0620 class** | 60 – 120 EUR (mid 90, **estimated**, only "price on request" found) | **360 / 540 / 720** | Reference of the spec; only makes sense for the first validated functional sample (1–2 pcs) |

## Overall picture

| | Low | Mid | High |
|---|---:|---:|---:|
| Boards (subtotal) | 265 | 415 | 665 |
| Coil + LiPo + magnets | 33 | 49 | 88 |
| Housing + small parts | 60 | 90 | 150 |
| **Total without motors** | **358** | **554** | **903** |
| + motors A (cheap) | 36 | 54 | 72 |
| **Total with motors A** | **394** | **608** | **975** |
| + motors B (Faulhaber) instead of A | 360 | 540 | 720 |
| **Total with motors B** | **718** | **1094** | **1623** |


## Does it fit in 500 EUR?

**Honestly: narrowly not in the mid case.** With cheap motors (A) the mid value is ~608 EUR (net), in the optimistic case ~394 EUR; with Faulhaber motors (B) the budget is clearly blown (>700 EUR).

Levers to get below 500 EUR (together about −120 … −170 EUR):

1. **Rev A without Qi:** omit BQ51003 + coil + ~15 passives (incl. 0805 C0G ×3), charge via pogo/spring-contact pads on VQI_5V (TP8) → −10 EUR parts/board, less BGA effort, approx. **−60 … −90 EUR**. Then develop Qi in Rev B on its own test board (coil tuning is manual work anyway).
2. **Populate one side only** (assembly setup/labour −30 … −60 EUR), piezo/battery pads/Q1 on the top side; the area in the arm is tight, a 2-layer re-floorplan is needed.
3. **3 instead of 5 boards:** saves only parts/shipping (~−25 EUR) – fixed costs dominate, so hardly any gain.
4. **Only 1 housing set in MJF, 2 in cheap SLA** (−20 EUR); **LiPo/coil from electronics scrap** for bench tests.
5. **Motors A for the series, Faulhaber only 1 sample** (enquiry via Micromo/distributor, secure the price).

With levers 1 + 2 + 4 the mid case comes to ≈ **440 – 500 EUR** (variant A), excluding VAT. **Uncertainty of the PCBWay figures ±30 %.**

**Module decision:** The ISP1807 (~10.3 EUR/pc) replaces nRF54L15 (~3.9 EUR) + crystals + antenna + RF network (~5 EUR) → extra cost ~1.5 EUR/board (~8 EUR for 5 boards), but no RF layout/tuning, a CE/FCC pre-qualified radio part and fewer placements. Price risk: LCSC stock 0, lead time ~4 weeks at DigiKey.

## Recommended order

1. Upload the BOM to a PCBWay quote (DXF + Gerber after layout) → get the real price for setup, BGA fee and parts, mark positions without an LCSC no.
2. First a hardware spike on dev boards: test nRF54L15 DK + STSPIN220 breakout + cheap Ø6 motor + TPL5010 breakout (safety path and encoder) – about 80 – 120 EUR, before 400+ EUR flows into boards.
3. Then Rev A (possibly without Qi).
