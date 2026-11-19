# Shopping list (Rev A bench pump)

> Test project, not a medical device; never worn or used on a person. Everything below is for **bench tests into containers only**.
> Research date **2026-11-19**. Only what is marked **(verified 2026-11-19)** was read on the live page; everything else is an **ESTIMATE** (range, not a quote). AliExpress listings change daily: the "listing" column gives a search term, never a promised link. Currency: EUR; USD prices converted at an assumed 0.88 EUR/USD. Replace every estimate with the invoice price in `docs/05-cost-model.md` (price log) after ordering.

## A0. AliExpress-first <= 200 EUR build (requirement `spec §1d`)

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
| 24 | Fill: water (never insulin or any drug) | | | 0 | | | | 0 | 0 |
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
| 2 | PCBWay CNC PP reservoir (25 USD minimum + DHL + VAT + duty) | 55 - 96 | water-only printed SLA/MJF reservoir for the first pump (spec §3 already allows it for water tests); order the PP part only as optional material preparation (never filled with insulin), **one size only, qty 1 - 2, in one PCBWay order with any other CNC part**; JLCCNC has no PP (POM is not insulin-validated) | 50 - 90 | mechanical owner / safety (insulin stays on PP) |
| 3 | Printed parts + coupon incl. DHL | 39 - 71 | one JLC3DP order with the coupon; MJF PA12 vs SLA: compare in the live quote; order together with JLCPCB in one shipment if the account allows | 8 - 20 | sourcing |
| 4 | Motor (US shop shipping + VAT + duty) | 31 - 53 | verify a ZW/AliExpress 6 mm 20-step 26:1 sample; if ratio differs, firmware preset; keep NFP as reference; buy 2 not 5 (already assumed) | 0 - 25 (uncertain) | firmware + mechanical |
| 5 | Separate AliExpress parcels (3 EUR duty/tariff line each) | ~ 25 - 45 incl. duty | consolidate: one hardware seller (rod, nuts, screws), one silicone seller, magnets with the needles if the same shop; or Amazon.de/EU shops for M1.6/M1.2 fasteners, silicone, velcro | 10 - 25 | sourcing |
| 6 | Gears | 10 - 12 (15:12) vs **32.30 + shipping if 18:18 at GHW (2 x 16.15 EUR, verified)** | **keep 15:12 from GHW (5.95 EUR)**; if the CAD stays 18:18, buy AliExpress 0.3 mod 18 T brass (verified listings 8 - 18 T, 2 mm bore, about 1 - 3 USD/pack) instead of GHW: 25 - 30 saved, but bores are 2.0 only and quality unverified (sleeve already planned for the screw gear) | 0 / 25 - 30 | mechanical owner |
| 7 | Cannula heads (box) | 10 - 40 | get 1 - 2 heads from a diabetic user/pharmacy sample | 10 - 30 | user |
| 8 | Casting kit (silicone) | 10 - 20 | water-only: skip; use a punched sheet washer or O-ring for water tests; medical-grade kit only as optional material preparation | 10 - 20 | mechanical |
| 9 | Duckbill / needles / magnets in MOQ packs | 25 - 50 | buy the smallest pack; the pack surplus pays marginal pumps | 5 - 10 | sourcing |

Not a saving: skipping the nRF52840-DK (tool, excluded anyway); 2-layer instead of 4-layer controller saves only ~ 5 - 8 EUR and costs RF/GND integrity: not proposed. JLC "Standard" PCBA costs 17 - 43 USD more setup than Economic: stay on Economic.

### 0.6 Smallest design changes that would close the gap to 200 EUR

Proposals for the mechanical/electronics owners (not done here). B above already assumes #1 - #4:

1. **One PCBA project**: pod sensor board as a break-off tab of the controller panel (or at least one JLC cart with both, one shipment). Needs one board thickness; if 1.6 mm is too thick for the pod, a 1.0 mm common thickness or flex is needed. (-20 to -35 EUR)
2. **<= 6 Extended parts on the controller**: drop the 32.768 kHz crystal (E73 has an internal RC; firmware choice), the SWD 2x5 header (Tag-Connect TC2030 pads are already on the board), duplicate LEDs, switch the USB-C and buzzer to Basic equivalents if they exist, reduce the pod to TMAG5273 + 1 dock sensor. Interlock parts (TPL5010, SN74AUP1G74, STSPIN220, E73) stay. (-8 to -15 EUR)
3. **Water-only printed reservoir for the first pump**; CNC PP reservoir optional (material preparation only, water only), one size. (-50 to -90 EUR)
4. **One JLC shipment** (PCBA + prints). (-12 to -20 EUR)
5. **Gear pair 15:12 (5.95 EUR, GHW)** rather than 18:18 (32.30 EUR at GHW). If 15:12 cannot fit, source 18 T gears from AliExpress. (-25 EUR if 18:18 is chosen)
6. Optional, risky: AliExpress/ZW motor (-0 to -25 EUR) after a sample proves the ratio.

Even with all of the above the first-pump central estimate is ~ 295 EUR (B) or ~ 232 EUR (B+); to reach a robust <= 200 EUR the requirement must be read as "marginal pump" (65 - 95 EUR) or relaxed to "first pump <= 250 EUR with B+, <= 300 EUR with B".

## A1. Per-item AliExpress vs. current shops

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

## A2. Frozen shopping list per Rev A iteration (links to shops)

| Item | Shop (URL) | Notes |
|---|---|---|
| Boards + PCBA | <https://jlcpcb.com/> package in `electronics/bench/fab/jlcpcb/controller/` | Economic PCBA, one cart |
| Prints | <https://jlc3dp.com/> (STEP in `mechanical/out/bench/fab/OP-70/`; OP-100 set when regenerated) | SLA (water) or MJF |
| Reservoir PP | <https://www.pcbway.com/rapid-prototyping/> CNC, README `mechanical/out/bench/fab/reservoir-cnc/` | 25 USD minimum order value |
| Gears | <https://ghw-modellbau.de/Spur-gear-Brass-Module-03-10-120-T> | 15 Z B, 12 Z B |
| Magnets | <https://yourmagnets.net/product/neodymium-magnet-round-2mm-diameter-1mm-height-n52/> (axial only) | |
| Others | search terms in `docs/PARTS-LOCK.md` | |

## A3. Sources (read 2026-11-19)

* JLCPCB PCBA price: <https://jlcpcb.com/help/article/pcb-assembly-price>; FAQ: <https://jlcpcb.com/help/article/PCB-assembly-faqs>; parts <https://jlcpcb.com/partdetail/C2764963>, <https://jlcpcb.com/partdetail/C2150516>
* PCBWay CNC FAQ <https://www.pcbway.com/rapid-prototyping/cnc-faq.html>; JLCCNC <https://jlccnc.com/>; JLC3DP <https://jlc3dp.com/llms.txt>, price update <https://jlc3dp.com/news/materials-finishing-pricing-update-july2026>
* EU 3 EUR duty <https://commission.europa.eu/news-and-media/news/ensuring-fairness-and-safety-eur3-customs-duty-low-value-parcels-2026-06-29_en>
* GHW <https://ghw-modellbau.de/Spur-gear-Brass-Module-03-10-120-T>; supermagnete <https://www.supermagnete.de/eng/disc-magnets-neodymium/disc-magnet-diameter-2-mm-height-1-mm_S-02-01-N>
* Zhaowei <https://www.zwgearbox.com/stepper-motor/pd6mm-stepper-gear-motor>
* AliExpress search pages (listing titles only, prices not verified at checkout): <https://www.aliexpress.com/w/wholesale-0.3-module-brass-gear.html>, <https://www.aliexpress.com/w/wholesale-diametrical-magnet-2x1.html>, <https://www.aliexpress.com/w/wholesale-micro stepper motor.html>
* Alibaba JU duckbill <https://www.alibaba.co.uk/product-detail/JU-Factory-Medical-Grade-Micro-One_1601587509906.html>; Techcon needle <https://gotopac.com/techcon-te730025pk.html>
* Not reachable from this session: nfpshop.com, precisionminidrives.com (host not allowed), LCSC price pages (no prices shown).

---

# Part B — detailed iteration list from the first sourcing pass (2026-11)

> Prices marked [V]/[E]/n/v as in that pass (1 EUR = 1.10 USD). Part A above supersedes the totals.

## B0. Blockers before ordering

| # | Blocker | Affects |
|---|---|---|
| 1 | **Gear ratio / layout mismatch** (STATUS handoff): CAD snapshot 18:18 (centre 5.40) vs spec 15:12 (centre 4.05, `mechanical/parts.md` says it does not fit the side-gear layout). Decide first; a mismatch is a 25 % dosing error. The list below carries **both** options (section 2.5). | gears, prints |
| 2 | `mechanical/out/bench/fab/` currently holds only **OP-70** (+ coupon + reservoir-cnc); OP-100/OP-200 prints must be regenerated after the parallel-motor layout is finished (STATUS: mechanics interrupted). The print list is for one size. | JLC3DP |
| 3 | Pod sensor board is not built yet; controller BOM CSV in `electronics/bench/fab/jlcpcb/controller/` still has the 16-pin FH12-16S (C596731) while `parts.json` has the 10-pin FH12-10S (C506791). Regenerate, run DRC, then get the JLCPCB quote. | JLCPCB |
| 4 | No verified source for the duckbill valve (OD <= 3 mm), a diametric Ø2 x 1 magnet and EU stock for medical silicone: these need the sample order (section 4), not the iteration order. | sample order |
| 5 | Motor connector type (PicoBlade vs JST GH) is only known once the first motors arrive; the controller carries both footprints (J5 populated, J6 DNP). | motors |

## B1. Per-iteration order (recurring, about once a month)

One bench pod (one size) x 2 pods (two-pod system), 1 controller board, consumables already in stock from section 4.

### 1.1 Boards: JLCPCB (assembled)

| Item | Qty | Unit | Total | Shop / link | Notes |
|---|---|---|---|---|---|
| Bench controller, 4-layer (F.Cu, In1, In2, B.Cu), ~40 x 50 mm, Gerbers `electronics/bench/fab/jlcpcb/controller/openpatch-bench-controller-gerbers.zip`, BOM/CPL in same folder | 5 bare, **2 assembled** | n/v | **$45–60 [E]** | https://jlcpcb.com/ (PCB + PCBA) | Uses E73 module (C2764963, 349 pcs seen), STSPIN220 C2150516, TPL5010 C473912, INA180 C122228 etc. Several are JLC "extended" parts (fee per distinct part). Real quote needed. |
| Pod sensor board, 2-layer, 15.5 x 25.9 mm (`electronics/bench/pod/`) | 5 bare, **2 assembled** | n/v | **$20–30 [E]** | same | TMAG5273A1 C3716049 (mandatory), dock hall DRV5032 (AJ recommended, C2152456; see PARTS-LOCK row 10), FFC connector FH12-10S C506791 |
| JLCPCB shipping to Germany (DHL/UPS) | 1 | n/v | $15–30 [E] | | Order both boards in one parcel. |
| **Boards subtotal (excl. shipping)** | | | **$65–90 [E]** | | Target in cost model: <= $80. Levers: drop optional DRV5032 U1/U2, 2-layer where possible, economic assembly, fewest extended parts. |

### 1.2 3D prints: JLC3DP

Files in `mechanical/out/bench/fab/` (state at this commit, OP-70 set; regenerate for OP-100/200). Print **2 sets** (two pods); orders at JLC3DP have no minimum (listing "from $0.30"), MJF PA12 about $0.28–0.35/g (cached pricing table, date unconfirmed, n/v).

| File (per pod) | Qty / pod | Material (per `mechanical/README.md`) | Note |
|---|---|---|---|
| `OP-70/bottom.stl` | 1 | PA12 MJF | housing bottom |
| `OP-70/top.stl` | 1 | PA12 MJF | housing top / lid |
| `OP-70/cannula_adapter.stl` | 1 | PA12 MJF (two snap arms) | dock |
| `OP-70/carriage.stl` | 1 | PA12 MJF | M1.6 nut pocket |
| `OP-70/coupler.stl` | 1 | PA12 MJF | **only if layout is coaxial**; re-check after the layout decision |
| `OP-70/end_cap.stl` | 1 | SLA resin (water tests only) | septum, duckbill pocket, needle guard |
| `OP-70/plunger_core.stl` | 1 | PA12 MJF or SLA | |
| `OP-70/reservoir.stl` | 0–1 | SLA, water tests only | **replaced by the PP CNC part** (section 1.3); print only as a fit reference |
| `mould_lower.stl`, `mould_upper.stl` (`mechanical/out/bench/`) | 1 set | SLA | casting mould for plunger seals |
| `dock-coupon/dock_coupon.stl` (6 variants, `variants.csv`) | 1 | PA12 MJF or SLA | print **first**, try on a real Insight Flex head |
| *Not ordered:* `reference_not_ordered/gasket.stl`, `plunger_seal.stl` | 0 | | made from silicone |

Estimate for 2 pod sets + 1 coupon: **$31–41 [E]** (project estimate in STATUS.md, `mechanical/out/bench/fab/`), plus shipping (n/v, JLC3DP combined with JLCPCB not possible, separate parcel) **$10–20 [E]**.

### 1.3 CNC reservoir: PCBWay (once per size, frozen, not monthly)

| Item | Qty | Total | Link | Notes |
|---|---|---|---|---|
| `reservoir-cnc/OP-xx_reservoir_cnc.step` + `..._drawing.pdf`, PP natural, as machined, std tolerance | **2 per size** | **$30–60 per size [E]** | https://www.pcbway.com/ (CNC Machining) | Settings in `reservoir-cnc/README.md`. OP-200 (6.5 x D) may be refused: ask first, fallback through-bore + plug. Order OP-100 only for the first iteration (all three: $90–180 [E]). |

### 1.4 Motor, gears and mechanical small parts (per iteration, 2 pods)

| Item | Qty | Unit | Total | Shop / link | Notes |
|---|---|---|---|---|---|
| NFP-608-26.45-SGM geared stepper | 2 | $6.60 [V earlier read] ($5.40 at 10+) | **$13.20** | https://nfpshop.com/product/6mm-micro-dc-step-gear-motor-16mm-type-model-nfp-608-26-45-sgm (alt. precisionminidrives.com) | Ships from HK, DHL/FedEx 3–5 d, import VAT/duty n/v. Motors are reusable; buy 5 in the sample order, then 0 per iteration. |
| GHW gear 15 T, bore 2.0, **753015** | 2 | 3.00 € [V] | 6.00 € | https://ghw-modellbau.de/Spur-gear-Brass-Module-03-10-120-T | 15:12 option |
| GHW gear 12 T, bore 1.5, **753012** | 2 | 2.95 € [V] | 5.90 € | same | 15:12 option. Bore 1.5 < M1.6 thread: see PARTS-LOCK row 3 |
| *Alternative (18:18):* GHW **390755** 18 T bore 2.0 | 4 | 16.15 € [V] | 64.60 € | same | only if 18:18 is kept; 5 mm wide, shave to 1.4–2 mm; sleeve needed on the M1.6 rod |
| **Mechanical subtotal (15:12 option)** | | | **about $13.20 + 13.1 = $26.3** | | Gears reusable across pods; buy once, count as iteration cost only for lost parts. |

### 1.5 Per-iteration total

| Group | Low | High |
|---|---|---|
| Boards (JLCPCB, assembled) | 65 | 90 |
| Prints (JLC3DP) | 31 | 41 |
| Motors + gears (if rebought) | 26 | 26 |
| **Subtotal** | **122** | **157** |
| Shipping (JLCPCB + JLC3DP + EU shops) [E] | 25 | 50 |
| **Total per iteration, excl. VAT/duty** | **about 147** | **about 207** |

If motors and gears are reused (typical after the first iteration): **about $96–131 + shipping = $120–180 [E]**. The CNC reservoirs ($30–60 per size, once) are not included.

## B2. Parts for the iteration, bought as packs (stock; see sample order for first purchase)

| Item | Qty needed / iteration | Pack | Price | Shop / link | Notes |
|---|---|---|---|---|---|
| M1.6 x 0.35 rod A2 (DIN 976), cut to length | ~2 x 25 mm | 1 m | ~2 € [E] | eBay / AliExpress (no EU M1.6 listing found; Accu-Components starts at M2) | n/v |
| M1.6 nut DIN 934, brass or A2 (AF 3.2, 1.3 thick) | 2 | pack | A2: Accu-Components HPN-M1.6-A2 https://accu-components.com/de/metrische-sechskantmuttern/7882-HPN-M1-6-A2 (price/availability n/v); SFS CH 100 pcs CHF 27.90 net [V]; eBay mixed brass lots ~3 € [E] | | |
| M1.2 pan head ISO 7045, 3 / 4 / 6 mm | ~10 | set | ~3 € [E] | Amazon / AliExpress | |
| Magnet Ø2 x 1 N52 **axial** (dock) | 2 | pack | n/v (S-02-01-N is N48) | https://www.supermagnete.de/eng/disc-magnets-neodymium/disc-magnet-2mm-1mm_S-02-01-N | row 8 |
| Magnet Ø2 x 1 **diametric** (spindle) | 2 | pack | $3–5 per 10 [E] | AliExpress custom / maker | **no verified listing** (PARTS-LOCK row 7) |
| Duckbill valve OD <= 3 mm | 2 | | $1–4 [E] | Minivalve info@minivalve.com / Alibaba | **no verified listing** |
| 30G blunt needle 1/4" | 2 | 50 / 100 | Techcon TE730025PK **$22.42 / 50 [V]**; AliExpress 100 pcs $5–8 [E] | https://gotopac.com/techcon-te730025pk.html | |
| Silicone sheet Pt-cure Shore A 40–50, 0.5 mm + 2 mm | ~50 x 50 mm | sheet | ~3 $ [E] (water tests) | AliExpress; medical: ElastaPro https://elastapro.com/?p=3522 (EU shipping n/v) | septum + gasket |
| Plunger seal silicone (2-part Pt-cure) | 4 rings | kit | 15–25 € [E] | Smooth-On Smooth-Sil 940 class; medical: Wacker SILPURAN 6000/40 (distributor n/v) | needs the SLA mould |
| FFC 0.5 mm, 10 pin, same-side contacts, ~50–100 mm | 2 | 5-pack | ~1 $ each [E] | AliExpress / LCSC | 0.3 mm thick (FH12 flip lock) |
| Silicone oil 350 cSt | few drops | | n/v | | |

## B3. Programmer / target

| Item | Qty | Price | Link | Notes |
|---|---|---|---|---|
| Nordic **nRF52840-DK** (also dev target) | 1 | **41.37 € [V]** (Mouser DE, 1,424 pcs cached); DigiKey NL 41.60 € excl. VAT | https://www.mouser.de/de/ProductDetail/949-NRF52840-DK | One-time. Includes on-board J-Link; SWD cable to the controller's 2x5 1.27 mm header (J3) needs a 10-pin 1.27 mm ribbon (~3 € [E]) or Tag-Connect TC2030 (J2, DNP). |

## B4. Sample order (PARTS-LOCK "recommended action", before freezing CAD/PCB)

Buy samples of every LOCK-AFTER-SAMPLE and CANDIDATE part, measure with calipers, write the real dimensions into `docs/PARTS-LOCK.md` and `spec/design-parameters.md`, then lock.

| Item | Qty | Unit | Total low | Total high | Shop / link | Notes |
|---|---|---|---|---|---|---|
| NFP-608-26.45-SGM | 5 | $6.60 [V] | 33.0 | 33.0 | nfpshop.com | email info@nfpmotor.com for the 26.45 outline drawing first (shaft length, connector) |
| GHW 753015 (15 T / 2.0) | 3 | 3.00 € | 9.9 | 9.9 | ghw-modellbau.de | |
| GHW 753012 (12 T / 1.5) | 3 | 2.95 € | 9.7 | 9.7 | same | |
| *Optional:* GHW 390753 (15 Z A 11.95 €), 390751 (12 Z A 17.65 €), 390755 (18 Z, 16.15 € x 2) | 1 each | | 0 | 68 | same | the wide "A" variants and the 18:18 pair, only if the thin discs or the 15:12 layout fail |
| Magnet Ø2 x 1 axial (S-02-01-N) | 20 | n/v | 3 [E] | 6 [E] | supermagnete.de | |
| Magnet Ø2 x 1 diametric | 10 | $3–5 per 10 [E] | 4 | 8 | AliExpress custom / maker enquiry | plus 1 pack of larger diametric (e.g. Radial Magnets 6 x 2.5, Digikey) as a sensor fallback |
| DRV5032 variants for the dock A/B test: AJ DMR C2152456, FA DMR C2152496 (on pod board U3/U1/U2 as assembled by JLC), optional ZE SOT-23 C266118 / AJ SOT-23 C266120 loose | 5 each | ~$0.3–1 [E] | 0 (on the JLC pod boards) | 8 | LCSC | X2SON parts cannot be hand-soldered here: test them populated on the pod board |
| FFC 0.5 mm 10P cables + 2 alternative connectors (XKB C388667, Ckmtw C183655) | 5 + 2 | ~$1 [E] | 5 | 10 | LCSC / AliExpress | measure connector height (<= 1.2 mm) |
| Duckbill valves: Minivalve samples + 3 Alibaba/AliExpress minis | 3–6 | $1–4 [E] | 5 | 15 | Minivalve info@minivalve.com | measure OD and cracking pressure (water column) |
| 30G blunt needles | 50–100 | | 6 [E] | 25 | AliExpress / Techcon | |
| Silicone sheet 0.5 + 2 mm | 2 | | 3 [E] | 8 [E] | AliExpress / ElastaPro | |
| Silicone casting kit (2-part Pt-cure Shore A 40) | 1 | | 16.5 [E] | 27.5 [E] | Smooth-On class | |
| M1.6 rod | 1 m | | 2.2 [E] | 4 | eBay / AliExpress | |
| M1.6 nuts | 100 | | 3.3 [E] | 31 | eBay / SFS | |
| M1.2 screws (3/4/6 mm) | 1 set | | 3.3 [E] | 5 | AliExpress | |
| **Sample order total (excl. shipping, VAT)** | | | **about $102** | **about $188** | | plus optional gears up to $68; shipping from 4–6 shops **$30–60 [E]** |

Matches the PARTS-LOCK estimate (roughly 60–100 EUR) at the low end; the high end is driven by the nut pack and the casting kit.

## B5. One-time tools (bench)

| Item | Qty | Price | Notes |
|---|---|---|---|
| nRF52840-DK | 1 | 41.37 € (see 3) | |
| Digital calipers, 0.01 mm | 1 | 15–25 € [E] | all LOCK-AFTER-SAMPLE measurements |
| **Precision scale, 0.001 g (1 mg)** with draft shield | 1 | 80–200 € [E] | gravimetric delivery accuracy: 1 U = 10 ul = ~10 mg of water, so 1 mg resolution = 0.1 U. Calibrate with a check weight. n/v model. |
| Calibration weights 10 g / 100 g (E2/F1) | 1 set | 20–40 € [E] | |
| 4 mm biopsy punch + 1 mm punch | 1 | ~10 € [E] | fill septum Ø4 |
| Fine tweezers, flush cutters, pin vice, 0.3 mm drill bits | 1 set | 15–25 € [E] | needle hub, rod trimming |
| USB microscope or loupe | 1 | 20–60 € [E] | inspect X2SON/FFC, needle, valve |
| Multimeter, USB-C cable, bench supply (optional) | 1 | 20–60 € [E] | motor 4.8 V / 0.18 A per phase |
| Test vials/containers, syringes, water, silicone oil | | ~10 € [E] | **containers only; never connected to a person** |
| **One-time total (incl. DK)** | | **about 230–470 € [E]** | DK 41 € [V], rest estimates |

## B6. Totals summary

| Bucket | Low | High | Basis |
|---|---|---|---|
| Per iteration (reusing motors/gears), excl. shipping | $96 | $131 | boards [E], prints [E] |
| Per iteration incl. shipping | $120 | $180 | [E] |
| Per iteration with rebought motors/gears incl. shipping | $147 | $207 | [E] |
| CNC reservoir, once per size (x2 pcs) | $30 | $60 | [E] (all three sizes $90–180) |
| Sample order (once) | $102 | $188 (+ up to $68 optional gears, + $30–60 shipping) | mixed [V]/[E] |
| One-time tools | about 250 | about 520 (USD, 1.10 EUR) | mostly [E] |
| **First month, all-in** | **about $540** | **about $1,080** | sample + shipping + tools + CNC OP-100 + one iteration (high includes optional gears) |

A monthly iteration at **$120–180** is within a modest hobby budget; the first month is 4–6 x that because of tools and samples.
