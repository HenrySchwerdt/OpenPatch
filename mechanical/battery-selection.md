# Battery selection research (bench test pod only)

Date: 2026-11-19. Scope: bench test project, never worn or used on a person.
Targets: T <= 4.2 mm, W as small as possible (max 10.5), L <= 32 mm, >= 25 mAh, PCM, tabs or wires, buyable in DE in qty 1-5.

Legend: **V** = product page read in this session. **S** = search snippet only (not confirmed). **C** = manufacturer catalogue table only, no retail source found.
Naming rule used for pouch cells: TTWWLL = thickness, width, length in mm (e.g. 301030 = 3.0 x 10 x 30). Vendors are not fully consistent, so always verify the drawing/caliper.

## Ranking (smallest width with >= 25 mAh, then availability)

| # | Part | T x W x L (mm) | mAh | Chem / V | PCM | Connection | Price | Shop | Ship to DE | Status |
|---|------|----------------|-----|----------|-----|------------|-------|------|-----------|--------|
| 1 | Panasonic CG-425A (round pin) | Ø4.7 x 25 | 32 typ | Li-ion 3.8 V (charge 4.35 V) | No, external PCM required | M3 lead / through-hole / SMT variants | ichome.com listing about USD 21.9 (unverified) | Panasonic, ichome | Unknown | S. Mouser lists it obsolete, DigiKey forum (Sep 2025) says lead versions obsolete and out of stock. Treat as NOT buyable. |
| 2 | Panasonic CG-420B (round pin) | Ø4.7 x (length not verified) | 27 rated / 29 typ | Li-ion 3.8 V | No | leads | DigiKey page seen, price not read | DigiKey | Unknown | S. DigiKey AU page says no longer manufactured. Not buyable. |
| 3 | Perfect Amperex PATL003-400529 | 4.0 x 5 x 29 | 30 | Li-polymer 3.7 V | Not stated | Not stated | Not stated (B2B) | Globalsources knowledge page | Unknown, likely MOQ | S. Narrowest flat cell found; needs an inquiry (MOQ, PCM, tabs). |
| 4 | Soldered 350824 | 3.5 x 8 x 24 by name; BerryBase page prints "24 x 8 x 35 mm" (axis order unclear, must verify) | 40 | Li-polymer 3.7 V | Yes (integrated protection, per page) | JST-PH 2.0 mm 2-pin socket on leads | EUR 3.80 | BerryBase.de (SOL-333275); also soldered.com | Yes, DE shop, in stock 1-3 days | **V (BerryBase)**. Best realistic buy: 8 mm wide, protected, plug-in. Thickness is the open point (3.5 mm if the name is right, 3.5 or 8 mm if the page axes are literal). Order 1, measure. |
| 5 | Liter/"Lipo" 400830 | 4.0 x 8 x 30 | 70 | Li-polymer 3.7 V | Not stated | Not stated | n/a | none found | n/a | C (battery-lipo.com table). No retail listing found. |
| 6 | Liter 350829 / 350830 (DNK350830 55 mAh with PCM) | 3.5 x 8 x 29-30 | 55 (350829) / 55-60 (350830) | Li-polymer 3.7 V | DNK sheet title says "with PCM" | Not read | n/a | dnkpower.com datasheet (PDF unreadable) | n/a | C/S. Retail unknown; manufacturer-direct possible. |
| 7 | Liter 370730 | 3.7 x 7 x 30 | 42-50 | Li-polymer 3.7 V | n/a | n/a | n/a | none found | n/a | C. 7 mm wide; no retail found. |
| 8 | Ampul 350926 | 3.5 x 9 x 26 | 90 (snippet; Liter table says 55 for 350926, so conflict) | Li-pol 3.7 V | Likely (ampul cells carry a chip) | Not read | not read | ampul.eu item 3472 | EU shop (PL), DE shipping not stated | S. Worth fetching/ordering; capacity claim suspicious. |
| 9 | **Ampul 301030** | 3.0 x 10 x 30 | 90 (0.33 Wh) | Li-polymer 3.7 V, charge 4.2 V | Yes ("integrated protection chip") | Two wires (red/black), no connector | EUR 4.00 incl. VAT | ampul.eu/en/battery/6782-li-pol-battery-90mah-37v-301030 | Not stated on page (EU shop, delivery page not read) | **V**. Best verified "10 mm class" cell, 3.0 mm thin, 3x capacity margin. |
| 10 | Ampul 401012 | 4.0 x 10 x 12 (page: 12 x 10 x 4) | 40 | Li-polymer 3.7 V | Yes | No connector (wires/tabs) | EUR 3.23 incl. VAT | ampul.eu/en/components/6411-li-pol-battery-40mah-37v-401012 | Not stated | **V**. Very short (12 mm) but only 40 mAh, 4.0 mm thick (0.2 mm margin). |
| 11 | 401030 (generic) | 4.0 x 10 x 30 | 80-130 (varies by seller) | Li-polymer 3.7 V | Usually yes | Wires; one listing with JST 1.25 mm 2-pin | about EUR 3-8 | eBay.de e.g. items 357161444108 (110 mAh + JST 1.25), 114762316388 (120 mAh), 175891076543 (5-pack, 110 mAh) | eBay.de, likely CN/DE stock | S only (eBay returned 403). Capacities inflated; treat as 80-90 mAh. 4.0 mm leaves only 0.2 mm margin after swelling/wrap. |
| 12 | polybattery LP401030 | 4.0 x 10 x 30 | 90 min / 100 typ | Li-polymer 3.7 V | Yes | Wires | Quote only | polybattery.com | Inquiry | **V** (page read). Not retail. |
| 13 | Tempero 251020 | 3.0 x 10 x 22.1 | 25 | Li-polymer 3.7 V (3.0 V cutoff) | Not stated | JST PH 2.0 | not read | temperosystems.com.au | AU shop | S. Capacity at the minimum; overseas. |
| 14 | AKZYTUE / YTKavq 301020 | 3.0 x 10 x 20 | 40 (claimed) | Li-polymer 3.7 V | Not stated | JST PH 2.0 | not read | amazon.com (US) listings | Check Amazon.de | S only. |
| 15 | Grepow GRP7854F1-1C-3.7V-30mAh | Not stated on page | 30 | Li-polymer 3.7 V | Not stated | Not stated | USD 9.99 + USD 20 shipping, 1 order per 30 days | DigiKey | Unclear | **V** (page read), but dimensions missing, so not rankable. Ask Grepow for a drawing. |

## Rejected

- EEMB LP401230: 4.3 mm thick, 12.5 x 31 mm, 60 mAh min / 65 typ / 100 label. Fails thickness (**V**, eemb.com/product-121).
- Liter 500527 (5.0 x 5 x 27, 35 mAh) and 500522: 5.0 mm thick. Fails thickness (C).
- Varta CP1254 / CP0854 coins: Ø12 / Ø8, noted only.
- Panasonic BR425: primary, not rechargeable.

## Findings and caveats

1. **True pin cells (Ø <= 5 mm) are effectively not buyable by a private person.** Only Panasonic's CG-4xx/CG-320 family showed up, and the lead versions are obsolete/out of stock at distributors. Panasonic also states external overcharge/over-discharge protection is required. Samples would need a business inquiry (Panasonic EU / ACTEC DK was named as a distributor in search results).
2. **Narrowest practical option:** the 8 mm class (Soldered 350824, BerryBase DE, EUR 3.80, protected, JST-PH). Order one and measure thickness and length before locking the CAD.
3. **Best "known good" fit if 10 mm width is acceptable:** Ampul 301030 (3 x 10 x 30, 90 mAh, PCM, EUR 4.00). Width 10 leaves only 0.5 mm margin to the 10.5 mm limit; pouch tolerance is typically +/-0.5 mm, so keep a swelling/tolerance allowance.
4. Capacity figures for the same code differ strongly between sellers (401030: 80 to 180 mAh). Use the Liter table values (301030 = 60, 401030 = 90) as realistic.
5. Pouch size codes: 300830 and 301230 returned no confirmed listing at all; 301230 and 401230 only appeared via EEMB (4.3 mm) and a Melopero PDF (not read).
6. Power budget check: 7-10 mAh for 48 h at 0.15 mA, so even 25-40 mAh gives >= 2.5x margin. Capacity is not the limiter, width is.

## Not covered / could not verify

- Eremit, Reichelt, Conrad, Akkuteile, lipo-shop, Amazon.de and AliExpress product pages: no product pages surfaced or they were not fetchable (eBay returned 403, aspower.com.de did not resolve, ufine returned 403). Eremit in particular returned zero hits.
- Great Power, BAK, GMB, VDL, AEC, PKCELL catalogues: no relevant cell confirmed.
- Shipping to Germany for ampul.eu and the Panasonic distributors was not confirmed.

## Recommended next steps

1. Order 2x Soldered 350824 (BerryBase) and 2x Ampul 301030; measure with a caliper.
2. Request the Perfect Amperex PATL003-400529 spec and MOQ (4 x 5 x 29, 30 mAh) if a 5 mm width is required.
3. Request samples of Panasonic CG-425A via ACTEC or Panasonic EU only if the pin form factor is essential.
4. Once measured, update `spec/design-parameters.md` first, then propagate.

## Sources (read in this session unless marked S)

- https://ampul.eu/en/battery/6782-li-pol-battery-90mah-37v-301030
- https://ampul.eu/en/components/6411-li-pol-battery-40mah-37v-401012
- https://www.berrybase.de/it/soldered-li-ion-akku-lithium-polymer-350824-3-7v-40mah-mit-2-pin-jst-stecker
- https://www.battery-lipo.com/index.php?c=category&id=29 (Liter table, catalogue data)
- https://polybattery.com/lp401030-90mah-small-3-7-v-4mm-flat-lipo-battery
- https://eemb.com/product-121
- https://www.digikey.com/en/products/detail/grepow-inc/GRP7854F1-1C-3-7V-30mAh/25603166
- https://forum.digikey.com/t/cg-425a-m3-status/60326
- S: https://www.globalsources.com/knowledge/30mah-ultranarrow-li-polymer-battery/, https://temperosystems.com.au/?p=9290, https://ampul.eu/en/battery/3472-li-pol-battery-90mah-37v-350926, eBay.de items listed above, Panasonic CG-425A/CG-420B pages and leaflet (search snippets), https://www.dnkpower.com/wp-content/uploads/2023/11/DNK350830-3.7V-55mAh-Lipo-Battery-Specification.pdf (PDF unreadable)
