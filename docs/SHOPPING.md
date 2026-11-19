# Shopping list (Rev A bench pump)

> Test project, not a medical device; never worn or used on a person. Everything below is for **bench tests into containers only**.
> Research date **2026-11-19**. Only what is marked **(verified 2026-11-19)** was read on the live page; everything else is an **ESTIMATE** (range, not a quote). AliExpress listings change daily: the "listing" column gives a search term, never a promised link. Currency: EUR; USD prices converted at an assumed 0.88 EUR/USD. Replace every estimate with the invoice price in `docs/05-cost-model.md` (price log) after ordering.

## 0. AliExpress-first <= 200 EUR build (requirement `spec §1d`)

Requirement (from the task text; `spec/design-parameters.md` in this branch has no §1d yet): **one complete bench pump (pod + controller, Rev A) <= 200 EUR all-in**: all parts, PCBA, prints, reservoir, consumables for one fill, shipping + import VAT/duty to Germany; minimum-order overhead is charged to the first pump; one-time tools (programmer, calipers, punch if reused) excluded; safety-relevant parts (interlock, watchdog, TMAG5273 sensor, medical-grade seals for insulin tests) are never downgraded.

### 0.1 Verdict (plain)

| | first pump (all-in, EUR) | marginal 2nd pump (EUR) |
|---|---|---|
| **A. Design as frozen today** (separate pod PCBA + controller PCBA, PCBWay CNC PP reservoir x2, 15:12 gears) | **358 - 607** (central ~ 480) | 95 - 150 (with CNC PP reservoir) |
| **B. Recommended build** (water-only printed reservoir, one PCBA project with sensor tab, <= 6 extended parts, one JLC cart incl. prints, no casting kit) | **223 - 366** (central ~ 295) | **65 - 95** |
| **B+. Stretch** (B plus: ZW/AliExpress motor verified by sample, 5 instead of 10 parcels, trimmed controller BOM, cannula borrowed) | **176 - 288** (central ~ 232) | 60 - 90 |
| **C. B + insulin-capable reservoir** (PCBWay CNC PP, 1 pc added) | 273 - 456 | 85 - 130 |

**<= 200 EUR is NOT reliably reachable for the FIRST pump.** Only the optimistic end of the stretch case B+ touches it; the central estimate of B+ is about 30 EUR over, of B about 95 EUR over, and the pessimistic end of B about 165 EUR over. It **is** reachable per additional pump (65 - 95 EUR water-only), because the cost of the first pump is dominated by fixed fees that do not repeat: PCBA setup + stencil + per-part "extended" feeder fees, minimum order values, 4 - 6 separate shipments and, since 2026-07-01, the EU 3 EUR duty per tariff line per parcel. No safety part had to be downgraded to get B; the gap is closed only by (a) fewer shipments, (b) fewer fixed fees, (c) a water-only reservoir for the first pump and (d) a cheaper motor source, which is not verified. Insulin-contact tests need the CNC PP reservoir and medical-grade silicone, which are outside B (see C).

### 0.2 Rules that decide the price (verified 2026-11-19 unless marked)

* **EU 3 EUR customs duty** on low-value imports (value <= 150 EUR), since 2026-07-01 until 2028-07-01: **3 EUR per item "based on tariff classification and not quantity"** (5 T-shirts = 3 EUR, 3 T-shirts + watch = 6 EUR), declared and paid by seller/importer. <https://commission.europa.eu/news-and-media/news/ensuring-fairness-and-safety-eur3-customs-duty-low-value-parcels-2026-06-29_en>. Whether it is per parcel or per consignment per line and whether it applies to non-IOSS sellers is **unclear in the sources found** (<https://www.vatcalc.com/eu/eu-e3-levy-low-value-e-commerce-import-package-july-2026/> returned 403; summary pages conflict). Model used here: **3 EUR per tariff line per parcel**, i.e. 10 separate AliExpress parcels with one line each = about 30 EUR. **Consolidate sellers / buy fasteners and silicone in EU shops** to avoid it.
* **VAT 19 %** on every non-EU parcel (collected at checkout via IOSS for consignments <= 150 EUR; above that at import by the carrier, plus a carrier handling fee that DHL/UPS/FedEx often charge: ESTIMATE 6 - 15 EUR, not included, avoid by keeping each parcel <= 150 EUR). EU shops (GHW Modellbau, supermagnete, Amazon.de) list prices **incl. 19 % VAT**, no duty.
* **JLCPCB PCBA (verified, <https://jlcpcb.com/help/article/pcb-assembly-price>, <https://jlcpcb.com/help/article/PCB-assembly-faqs>)**: setup **8.18 USD economic** (25.56 / 51.12 USD standard 1-/2-sided); stencil **1.53 USD economic**; **extended-part feeder fee 3.07 USD per unique extended part** (Preferred Extended parts are free on Economic); SMT 0.0016 USD/joint; hand-soldering labour 3.58 USD/order; economic needs mouse-bite panels, <= 250 x 250 mm. E73-2G4M08S1CX (C2764963) and STSPIN220 (C2150516) are **Extended** (verified on jlcpcb.com/partdetail); price and stock are not shown to anonymous visitors - check in the cart.
* **PCBWay CNC (verified, <https://www.pcbway.com/rapid-prototyping/cnc-faq.html>)**: Polypropylene is offered; **minimum order value 25 USD excluding shipping** (parts cost less -> charged 25), no minimum quantity; DHL/FedEx/UPS/TNT/EMS; duties are the customer's. **JLCCNC does not list PP** (POM, nylon PA6, PC, PMMA, ABS; <https://jlccnc.com/>, from 5 USD, single piece). **JLC3DP does not do CNC at all** (that is JLCCNC) (<https://jlc3dp.com/llms.txt>). So the PP reservoir stays at PCBWay or an AliExpress/Alibaba CNC seller (not researched in detail: no listing price found).
* **No AliExpress listing was found for a 6 mm 20-step 26:1 geared stepper** (search 2026-11-19). The only look-alike is the Zhaowei ZWBPD006006 family (<https://www.zwgearbox.com/stepper-motor/pd6mm-stepper-gear-motor>, verified): datasheet drawing and PDF `pd006006-en.pdf` available, ratios 4.8 / 6.43 (1 stage), 23.04 / 30.86 / 41.33 (2 stages) etc. - **no 26.45, step angle not stated on the page, no price (enquiry form)**, "ratios for reference, can be customized". RISK: a different ratio changes U/step (firmware preset must follow, see `mechanical/parts.md` §1.3), step angle must be confirmed (20/rev assumed), terminals/shaft D-flat differ from the NFP drawing. Treat as an unverified backup, not a saving, until a sample is measured.

### 0.3 First-pump line items (OP-100, one pump, EUR all-in; ESTIMATES unless noted)

"Bought / used": quantity ordered vs. quantity consumed by pump 1. Surplus is paid by pump 1 (minimum-order overhead rule). Every line is ex-VAT before the VAT/duty column; the right-hand column is the per-parcel all-in. Bill A = design as frozen; Bill B = recommended (cuts in §0.5; B+ is not itemised here, it is B with the §0.6 item 6 and the consolidations of §0.5 rows 5, 7).

| # | Item | Bought / used | Unit (ex VAT) | Line | Shop / listing (search term) | Ship | VAT / duty rule | Bill A all-in | Bill B all-in |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Controller PCB 4-layer 40 x 50, 1.6 mm | 5 / 1 | 1.4 - 2.6 | 7 - 13 | JLCPCB | in cart | 19 % + 3 | in row 10 | in row 10 |
| 2 | Pod sensor PCB 2-layer 15.5 x 25.9 | 5 / 1 | 0.4 - 1 | 2 - 5 | JLCPCB (Bill B: tab on controller panel, row 1 only) | in cart | | in row 10 | 0 |
| 3 | PCBA setup x2 (controller, pod) / x1 in B | 2 / 2 | 7.2 | 14.4 / 7.2 | JLCPCB economic | | | in row 10 | in row 10 |
| 4 | Stencil x2 / x1 | | 1.35 | 2.7 / 1.4 | JLCPCB | | | | |
| 5 | Extended feeder fees: ~9 - 12 ctrl + 3 pod (A) / <= 6 ctrl (B) | 12 / 12 | 2.7 | 22 - 36 / 15 - 22 | JLCPCB | | | | |
| 6 | Controller components, 2 assembled boards (E73 ~ 6 USD, STSPIN220, TPL5010, passives, MOQ rounding) | 2 / 1 | 15 - 21 | 30 - 42 / 26 - 36 | LCSC via JLCPCB | | | | |
| 7 | Pod components x2 (TMAG5273, 3 x DRV5032 -> 1 in B, FH12, caps) | 2 / 1 | 3 - 5 | 6 - 10 / 2 - 3 | LCSC via JLCPCB | | | | |
| 8 | SMT joints + misc | | | 2 - 4 | | | | | |
| 9 | Shipping JLCPCB -> DE (DHL) | | | 18 - 30 | | | | | |
| 10 | **JLCPCB parcel total** (Bill B: includes the JLC3DP prints of rows 11 - 12 in one cart and one shipment) | | | | | | 19 % + 3 - 6 | **130 - 193** | **117 - 178** |
| 11 | JLC3DP resin/MJF: OP-100 shells, carriage, end cap, plunger core, cannula adapter (+ SLA water reservoir in B) | 1 set / 1 | | 10 - 25 | JLC3DP SLA 8001/ MJF PA12, one order | 12 - 20 | 19 % + 3 | 39 - 71 (incl. coupon) | in row 10 |
| 12 | Dock fit-test coupon (6 variants) | 1 / 1 | | 5 - 12 | JLC3DP, same order as row 11 | | | in row 11 | in row 10 |
| 13 | CNC PP reservoir OP-100 (PCBWay, 25 USD min. order) | 2 / 1 (A) | | 26 - 48 | PCBWay CNC, PP, as machined | 18 - 30 | 19 % + 3 | **55 - 96** | 0 (printed, in row 11) |
| 14 | NFP-608-26.45-SGM (nfpshop.com / precisionminidrives.com, 6.60 USD; price/shipping not re-verified, site unreachable from this session) | 2 / 1 | 5.8 | 11.6 | nfpshop.com | 12 - 30 (est.) | 19 % + 3 | 31 - 53 | 31 - 53 |
| 15 | Gears module 0.3 brass 15T (bore 2) + 12T (bore 1.5): GHW 15 Z B 3.00 + 12 Z B 2.95 EUR incl. VAT (verified) | 1 / 1 | | 5.95 | ghw-modellbau.de | 4 - 6 (est.) | VAT incl., no duty | 10 - 12 | 10 - 12 |
| 16 | M1.6 x 0.35 rod A2 + M1.6 brass nuts + M1.2 screws (assortments) | 1 set | | 5 - 9 | AliExpress/Amazon.de "M1.6 threaded rod", "M1.6 brass nut", "M1.2 screw set" | 0 | 19 % + 3/line | 12 - 17 | 9 - 14 |
| 17 | Magnets: dock axial Ø2 x 1 (AliExpress 2x1 N35/N52 listings ~ 1.1 USD per pack, verified as search result, quantity per pack not stated); **spindle diametric Ø2 x 1: no listing found** | 20 / 2 | | 5 - 11 | AliExpress custom "diametrically magnetized 2x1" (risk); yourmagnets.net axial 0.14 EUR/pc | 0 - 3 | 19 % + 3/line | 12 - 23 | 12 - 23 |
| 18 | 30G blunt dispensing needle 1/4" | 100 / 3 | | 5 - 9 (est.) | AliExpress "30G blunt dispensing needle 1/4" (Techcon TE730025PK = 22.42 USD per 50, verified) | 0 | 19 % + 3 | 9 - 14 | 9 - 14 |
| 19 | Silicone sheet 0.5/2 mm + 4 mm biopsy punch (reusable tool, counted once) + 2-part platinum silicone small kit (Shore 20-40, NOT medical) | 1 each | | 15 - 28 | AliExpress; kit not USP VI | 0 | 19 % + 3/line | 27 - 42 | 14 - 22 (no casting kit) |
| 20 | Duckbill valve, mini silicone, 3 mm | 5 / 1 | | 4 - 12 | AliExpress (no 3 mm listing found); Alibaba JU DBCV604 3.2 mm GBP 0.98 each from 25 pcs (verified) | 0 | | 8 - 17 | 8 - 17 |
| 21 | FFC 0.5 mm, 10-pin (same-side contacts), 5 pcs | 5 / 1 | | 1.5 - 3 | AliExpress | | | 5 - 7 | 5 - 7 |
| 22 | Velcro, silicone oil 350 cSt, 1 mL syringe, fill needles | 1 / 1 | | 10 - 18 | Amazon.de / EU | 0 - 4 | incl. | 10 - 22 | 8 - 16 |
| 23 | Accu-Chek Insight Flex cannula head (consumable; sold in boxes, price not verified) | 1 box / 1 | | 10 - 40 | pharmacy / supplier | | | 10 - 40 | 0 - 10 (single/borrowed) |
| 24 | Fill: water (insulin tests excluded) | | | 0 | | | | 0 | 0 |
| | **TOTAL (rounded)** | | | | | | | **358 - 607** | **186 - 310** |

Excluded (one-time tools, per requirement): programmer (nRF52840-DK ~ 40 EUR or CMSIS-DAP/J-Link clone ~ 8 - 15 EUR), calipers, tweezers, side cutters, hot-air gun not needed (no soldering).

Notes: (1) Parts.json mismatch to fix: `BOM-jlcpcb.csv` uses **FH12-16S-0.5SH (C596731)** for the controller connector but `parts.json` and the pod board use **FH12-10S (C506791)**; FFC pin count and the same-side/bottom-contact orientation must match before ordering. (2) Controller BOM = 40 line items; Extended-part count could not be read from the BOM (library type not stored); I assumed ~9 - 12 of the 40 lines to be Extended (E73, STSPIN220, TPL5010, SN74AUP1G74, INA180, USB-C, FH12, PicoBlade, buzzer, switch, SWD header, crystal): check "Extended" flags in the JLCPCB cart; every one removed saves 2.7 EUR + MOQ rounding.

### 0.4 Marginal additional pump (identical, same orders, EUR all-in, ESTIMATE)

| Item | Qty | Cost |
|---|---|---|
| Controller PCBA board (components + joints; bare PCB from the 5-pc batch) | 1 | 17 - 23 |
| Pod sensor (tab) | 1 | 2 - 4 |
| Motor NFP (+ share of shipping) | 1 | 9 - 18 |
| Gears 15T/12T | 1 | 6 |
| Printed shell set + SLA water reservoir (marginal, no setup, MJF/SLA min. order shared) | 1 | 10 - 19 |
| Rod, nut, 4 x M1.2, magnets, needle, silicone sheet, duckbill, FFC, velcro (from the first pump's kits) | 1 | 4 - 8 |
| Cannula head | 1 | 3 - 5 |
| Fill + oil + syringe | 1 | 1 - 3 |
| 19 % VAT on the non-EU part (~ 55 %) | | 7 - 11 |
| **Total water-only** | | **65 - 95** (A with CNC PP reservoir: +20 - 35 if ordered in the same PCBWay order as qty 2, +30 - 60 as a separate order) |

Because the first pump already pays for the MOQ surplus (second assembled board, second motor, boxes of needles/magnets/valves), a "second pump from stock" is almost free apart from the CNC reservoir; the table above is the cost if the same parts are bought again.

### 0.5 Cost drivers and cuts (EUR, vs. Bill A)

| Rank | Driver | Cost in A | Cut | Saving (EUR) | Who decides |
|---|---|---|---|---|---|
| 1 | JLCPCB PCBA fixed + extended fees, 2 projects, shipping | 130 - 193 | merge pod sensor into the controller panel as a break-off tab (one PCBA project: 1 setup, 1 stencil, 1 FH12 feeder, 1 shipment), cut Extended parts to <= 6, drop 2 optional DRV5032 | 20 - 45 | electronics owner (tab thickness 1.6 mm vs. 0.6 - 0.8 mm pod board space; needs Z-budget check) |
| 2 | PCBWay CNC PP reservoir (25 USD minimum + DHL + VAT + duty) | 55 - 96 | water-only printed SLA/MJF reservoir for the first pump (spec §3 already allows it for water tests); order the PP part only when insulin tests start, **one size only, qty 1 - 2, in one PCBWay order with any other CNC part**; JLCCNC has no PP (POM is not insulin-validated) | 50 - 90 | mechanical owner / safety (insulin stays on PP) |
| 3 | Printed parts + coupon incl. DHL | 39 - 71 | one JLC3DP order with the coupon; MJF PA12 vs SLA: compare in the live quote; order together with JLCPCB in one shipment if the account allows | 8 - 20 | sourcing |
| 4 | Motor (US shop shipping + VAT + duty) | 31 - 53 | verify a ZW/AliExpress 6 mm 20-step 26:1 sample; if ratio differs, firmware preset; keep NFP as reference; buy 2 not 5 (already assumed) | 0 - 25 (uncertain) | firmware + mechanical |
| 5 | Separate AliExpress parcels (3 EUR duty/tariff line each) | ~ 25 - 45 incl. duty | consolidate: one hardware seller (rod, nuts, screws), one silicone seller, magnets with the needles if the same shop; or Amazon.de/EU shops for M1.6/M1.2 fasteners, silicone, velcro | 10 - 25 | sourcing |
| 6 | Gears | 10 - 12 (15:12) vs **32.30 + shipping if 18:18 at GHW (2 x 16.15 EUR, verified)** | **keep 15:12 from GHW (5.95 EUR)**; if the CAD stays 18:18, buy AliExpress 0.3 mod 18 T brass (verified listings 8 - 18 T, 2 mm bore, about 1 - 3 USD/pack) instead of GHW: 25 - 30 saved, but bores are 2.0 only and quality unverified (sleeve already planned for the screw gear) | 0 / 25 - 30 | mechanical owner |
| 7 | Cannula heads (box) | 10 - 40 | get 1 - 2 heads from a diabetic user/pharmacy sample | 10 - 30 | user |
| 8 | Casting kit (silicone) | 10 - 20 | water-only: skip; use a punched sheet washer or O-ring for water tests; kit only for insulin tests (medical grade) | 10 - 20 | mechanical |
| 9 | Duckbill / needles / magnets in MOQ packs | 25 - 50 | buy the smallest pack; the pack surplus pays marginal pumps | 5 - 10 | sourcing |

Not a saving: skipping the nRF52840-DK (tool, excluded anyway); 2-layer instead of 4-layer controller saves only ~ 5 - 8 EUR and costs RF/GND integrity: not proposed. JLC "Standard" PCBA costs 17 - 43 USD more setup than Economic: stay on Economic.

### 0.6 Smallest design changes that would close the gap to 200 EUR

Proposals for the mechanical/electronics owners (not done here). B above already assumes #1 - #4:

1. **One PCBA project**: pod sensor board as a break-off tab of the controller panel (or at least one JLC cart with both, one shipment). Needs one board thickness; if 1.6 mm is too thick for the pod, a 1.0 mm common thickness or flex is needed. (-20 to -35 EUR)
2. **<= 6 Extended parts on the controller**: drop the 32.768 kHz crystal (E73 has an internal RC; firmware choice), the SWD 2x5 header (Tag-Connect TC2030 pads are already on the board), duplicate LEDs, switch the USB-C and buzzer to Basic equivalents if they exist, reduce the pod to TMAG5273 + 1 dock sensor. Interlock parts (TPL5010, SN74AUP1G74, STSPIN220, E73) stay. (-8 to -15 EUR)
3. **Water-only printed reservoir for the first pump**; CNC PP reservoir only for insulin tests, one size. (-50 to -90 EUR)
4. **One JLC shipment** (PCBA + prints). (-12 to -20 EUR)
5. **Gear pair 15:12 (5.95 EUR, GHW)** rather than 18:18 (32.30 EUR at GHW). If 15:12 cannot fit, source 18 T gears from AliExpress. (-25 EUR if 18:18 is chosen)
6. Optional, risky: AliExpress/ZW motor (-0 to -25 EUR) after a sample proves the ratio.

Even with all of the above the first-pump central estimate is ~ 295 EUR (B) or ~ 232 EUR (B+); to reach a robust <= 200 EUR the requirement must be read as "marginal pump" (65 - 95 EUR) or relaxed to "first pump <= 250 EUR with B+, <= 300 EUR with B".

## 1. Per-item AliExpress vs. current shops

| Part | Current shop (verified 2026-11-19) | AliExpress equivalent | Risk / verdict |
|---|---|---|---|
| NFP-608-26.45-SGM Ø6 20-step 26.45:1 geared stepper | nfpshop.com 6.60 USD (10+: 5.40), full drawing; site not reachable from this session, price from `PARTS-LOCK.md` | **none found with 20 steps/rev and ~26:1**; ZW ZWBPD006006 family (drawing + PDF public, ratios 4.8 / 6.43 / 23.04 / 30.86, price on request, ~ 10 - 25 USD per `mechanical/parts.md`); generic "6 mm planetary" results are mostly brushed DC gearmotors (e.g. Pololu 26:1 is DC) | Not a drop-in. Buy NFP; sample a ZW 23:1 later (U/step changes). |
| Module 0.3 brass gears 15T (bore 2) / 12T (bore 1.5) | ghw-modellbau.de 15 Z B 3.00, 12 Z B 2.95 EUR incl. VAT (18 Z = 16.15 EUR) | AliExpress "0.3 Modulus brass gear 8 - 18 teeth" about 1 - 3 USD/pack, **2 mm bore only, no 1.5 mm bore, unverified tooth data** | 12 T bore 1.5 -> needs 2 mm sleeve. Use GHW for 15:12; AliExpress only for the 18:18 option |
| M1.6 stainless rod, brass nuts | Amazon.de / Mädler / element14 DIN 934 M1.6 | no M1.6 rod listing found in search (only M4); available in fastener sellers | buy in EU assortment, avoids duty line |
| M1.2 screws | Amazon.de sets ~ 3 EUR | AliExpress sets | same; EU if 1 parcel saved |
| Ø2 x 1 axial NdFeB | supermagnete.de 4.00 EUR per 20 (0.20 EUR each; **min. order value 20 EUR**) or yourmagnets.net 0.14 EUR each | AliExpress 2x1 N35/N52 ~ 1.1 USD pack | AliExpress or yourmagnets; supermagnete is not cheaper due to the 20 EUR minimum |
| Ø2 x 1 diametric NdFeB | **not found at supermagnete** (only Ø10 x 5 diametric 0.93 EUR each) | AliExpress custom diametric: none verified | RISK: angle sensor unusable with axial magnet. Ask seller for diametric, or use a larger diametric magnet (needs CAD change) |
| 30G blunt needles | Techcon TE730025PK 22.42 USD per 50 | AliExpress "30G blunt dispensing needle" ~ 5 - 9 USD per 100 (estimate) | AliExpress |
| Silicone sheet, Pt casting silicone | Smooth-On kits 15 - 25 EUR | AliExpress sheets 3 - 7 EUR; Pt-silicone small kits 8 - 15 EUR, not medical | water tests only |
| Duckbill valves | Vernay/Minivalve (quote), Nordson | AliExpress/Alibaba mini duckbill; JU DBCV604 3.2 mm GBP 0.98 from 25 pcs | no 3 mm listing verified; measure |
| 0.5 mm FFC | LCSC/Mouser | AliExpress 10 pin 0.5 mm 100 mm, 5 pcs ~ 1.5 - 3 EUR | check contact side |
| nRF52840 module | LCSC E73-2G4M08S1CX via JLCPCB assembly (Extended) | AliExpress Ebyte E73: no benefit, the module is assembled by JLC | keep JLC |
| Velcro | any | AliExpress | buy in EU (1 duty line) |

## 2. Frozen shopping list per Rev A iteration (links to shops)

| Item | Shop (URL) | Notes |
|---|---|---|
| Boards + PCBA | <https://jlcpcb.com/> package in `electronics/bench/fab/jlcpcb/controller/` | Economic PCBA, one cart |
| Prints | <https://jlc3dp.com/> (STEP in `mechanical/out/bench/fab/OP-70/`; OP-100 set when regenerated) | SLA (water) or MJF |
| Reservoir PP | <https://www.pcbway.com/rapid-prototyping/> CNC, README `mechanical/out/bench/fab/reservoir-cnc/` | 25 USD minimum order value |
| Gears | <https://ghw-modellbau.de/Spur-gear-Brass-Module-03-10-120-T> | 15 Z B, 12 Z B |
| Magnets | <https://yourmagnets.net/product/neodymium-magnet-round-2mm-diameter-1mm-height-n52/> (axial only) | |
| Others | search terms in `docs/PARTS-LOCK.md` | |

## 3. Sources (read 2026-11-19)

* JLCPCB PCBA price: <https://jlcpcb.com/help/article/pcb-assembly-price>; FAQ: <https://jlcpcb.com/help/article/PCB-assembly-faqs>; parts <https://jlcpcb.com/partdetail/C2764963>, <https://jlcpcb.com/partdetail/C2150516>
* PCBWay CNC FAQ <https://www.pcbway.com/rapid-prototyping/cnc-faq.html>; JLCCNC <https://jlccnc.com/>; JLC3DP <https://jlc3dp.com/llms.txt>, price update <https://jlc3dp.com/news/materials-finishing-pricing-update-july2026>
* EU 3 EUR duty <https://commission.europa.eu/news-and-media/news/ensuring-fairness-and-safety-eur3-customs-duty-low-value-parcels-2026-06-29_en>
* GHW <https://ghw-modellbau.de/Spur-gear-Brass-Module-03-10-120-T>; supermagnete <https://www.supermagnete.de/eng/disc-magnets-neodymium/disc-magnet-diameter-2-mm-height-1-mm_S-02-01-N>
* Zhaowei <https://www.zwgearbox.com/stepper-motor/pd6mm-stepper-gear-motor>
* AliExpress search pages (listing titles only, prices not verified at checkout): <https://www.aliexpress.com/w/wholesale-0.3-module-brass-gear.html>, <https://www.aliexpress.com/w/wholesale-diametrical-magnet-2x1.html>, <https://www.aliexpress.com/w/wholesale-micro stepper motor.html>
* Alibaba JU duckbill <https://www.alibaba.co.uk/product-detail/JU-Factory-Medical-Grade-Micro-One_1601587509906.html>; Techcon needle <https://gotopac.com/techcon-te730025pk.html>
* Not reachable from this session: nfpshop.com, precisionminidrives.com (host not allowed), LCSC price pages (no prices shown).
