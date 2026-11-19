# Gear selection: ratchet wheel (M1.6 x 0.35 leadscrew) and motor coupling

Bench test project only. Not a medical device, never for on-body use (see `DISCLAIMER.md`).

Research date: 2026-11-19. Status legend: **CONFIRMED** = values read from a fetched supplier page; **SNIPPET** = only seen in a search-result snippet, page not fetched; **UNVERIFIED** = not seen at all.

## 1. Step maths

U per tooth = 0.35 mm / z x 74.6 mm^2 / 10 = 2.611 / z. With N pawls evenly offset by 1/N tooth the step is U/N.
Target step: 0.04-0.06 U. OD <= 6.0 mm.

| z | module 0.3 OD (mm) | U/tooth (1 pawl) | 2 offset pawls | 3 offset pawls |
|---|---|---|---|---|
| 10 | 3.6 | 0.261 | 0.131 | 0.087 |
| 12 | 4.2 | 0.218 | 0.109 | 0.073 |
| 14 | 4.8 | 0.186 | 0.093 | 0.062 |
| 15 | 5.1 | 0.174 | 0.087 | 0.058 |
| 16 | 5.4 | 0.163 | 0.082 | 0.054 |
| 18 | 6.0 | 0.145 | 0.0725 | 0.048 |
| 28 (m0.2, hypothetical) | 6.0 | 0.093 | 0.047 | 0.031 |
| 50 (m0.1, hypothetical) | 5.2 | 0.052 | 0.026 | n/a |

**Key finding.** With OD <= 6.0 mm, no catalogue gear I could confirm reaches the 0.04-0.06 U target with 1 or 2 pawls. The target needs z of roughly 44-65 (1 pawl) or 22-33 (2 pawls), which means module <= 0.2 at OD 6 mm. I found no catalogue source for module 0.1-0.2 spur gears with a bore of 1.5-1.6 mm (see section 5). The best confirmable fit is **module 0.3, z = 15-18, with THREE pawls offset by 1/3 tooth**: 0.058 U (z15) or 0.048 U (z18). Alternatives: two pawls with z18 gives 0.0725 U (about 20 % above target), or a custom-cut module 0.2, z = 28 wheel.

## 2. Confirmed candidates (module 0.3 brass)

All brass Ms58 (2.0401), 20 deg pressure angle, DIN 58405 quality 8d, straight toothed.

### A. GHW-Modellbau (Germany, private orders, prices incl. 19 % VAT, plus shipping), CONFIRMED
Page: https://ghw-modellbau.de/Spur-gear-Brass-Module-03-10-120-T
The page carries a notice "not available in your delivery country". It does not say which countries, so check at checkout.

| Order no | Z | Bore | OD | Pitch dia | Hub (dia x len) | Face width | Price | U/step 1 / 2 / 3 pawls |
|---|---|---|---|---|---|---|---|---|
| 753010 (10 Z B) | 10 | 1.5 | 3.6 | 3.0 | none | 4 | 3.50 EUR | 0.261 / 0.131 / 0.087 |
| 753012 (12 Z B) | 12 | 1.5 | 4.2 | 3.6 | none | 4 | 2.95 EUR | 0.218 / 0.109 / 0.073 |
| 390751 (12 Z A) | 12 | 1.5 | 4.2 | 3.6 | none | 5 | 17.65 EUR | same as 12 Z B |
| 753015 (15 Z B) | 15 | 2.0 | 5.1 | 4.5 | 4 x 2.5 | 1.4 | 3.00 EUR | 0.174 / 0.087 / 0.058 |
| 390754 (16 Z) | 16 | 2.0 | 5.4 | 4.8 | none | 5 | 16.15 EUR | 0.163 / 0.082 / 0.054 |
| 390755 (18 Z) | 18 | 2.0 | 6.0 | 5.4 | none | 5 | 16.15 EUR | 0.145 / 0.0725 / 0.048 |
| 390752 (14 Z) | 14 | 2.0 | 4.8 | 4.2 | none | 5 | 16.15 EUR | 0.186 / 0.093 / 0.062 |

Notes: the cheap "B" variants (753xxx) are thin discs (1.4 mm width, hub 4 mm) for z >= 15, or 4 mm wide without hub for z 10/12. The expensive "A" variants are 5 mm wide, full-length cut, and cost about 16 EUR. Bore tolerance is not stated on this page.

### B. Maedler article series 2600xxxx, seen via Ameco (CZ reseller), CONFIRMED for the two rows below
- 26001200: m0.3, z12, bore 1.5 (BH7), OD 4.2, pitch 3.6, width 5, no hub, 0.2 g. https://eshop.ameco.cz/products/en/1618/1034/1059/g975/26001200/
- 26003000: m0.3, z30, bore 2.0 (BH7), OD 9.6, pitch 9.0, width 5, no hub, 2.3 g. https://eshop.ameco.cz/products/en/1618/1034/1059/g975/26003000/
- 26005000 / 26006000: z50 / z60 with hub, bore 3.0, width 2, hub 10 x 5 (too large for this project).
- Prices are shown only after login. maedler.de itself returned HTTP 403 to my fetch, so I could not read the Maedler shop directly. The z14-z18 Maedler article numbers are **UNVERIFIED** (the pattern suggests 26001800 for z18, but I did not see it).
- Maedler quotes the permissible torque for z12 as 0.18 Ncm and for z30 as 1.0 Ncm.

### C. Kyouiku Gear (via RS Components), SNIPPET only (RS pages returned 403)
Brass, m0.3, bore 2 mm: RS 5031841 (z14, pitch 4.2, hub 5), RS 5031857 (z15, pitch 4.5, hub 5.5), RS 5031891 (z24, pitch 7.2, hub 6, width 3.2; flagged discontinued). The face width of the 14/15 tooth parts is not confirmed. Check the RS pages by hand before ordering. Link example: https://uk.rs-online.com/web/p/spur-gears/5031857

### D. Accu-Components (UK/EU), CONFIRMED only that module 0.3 exists
S30B18K+0402: m0.3, z18, 4 mm width, K2 type, brass. Bore is not stated in the snippet. https://accu-components.com/de/stirnrader/761080-S30B18K+0402 (page not fetched, treat as **SNIPPET**). Its z28 sibling has bore 2 mm H8, OD 9 mm.

## 3. Bore problem (M1.6)

Only z10 and z12 (module 0.3) come with a 1.5 mm bore, and those are far too coarse. Every wheel with a useful tooth count (z14-z18) has a 2.0 mm bore, which is **larger** than the M1.6 thread (major dia 1.6 mm). Options:
1. **Sleeve/hub (recommended for bench):** make a small brass or 3D-printed hub, Ø2.0 OD with a 1.6 mm bore (tap M1.6 or thread-lock onto the screw), then retain the gear with Loctite 638 or similar on the 2.0 mm seat. No catalogue sleeve article was confirmed.
2. **Ream a 1.5 mm bore wheel to 1.6 mm** (z10/z12 only; not useful for the step target).
3. **Press fit 2.0 mm bore onto the screw's unthreaded Ø2.0 journal,** if the leadscrew has or gets a turned Ø2.0 shank (needs a custom screw).
4. The 5 mm wide variants can be parted or skimmed down to 1-3 mm face width on a lathe, or use 753015 (1.4 mm, with 4 mm hub) as a ready-made thin disc.

## 4. Recommendations

### Ratchet (best 2)
1. **GHW 753015, z15 (OD 5.1, bore 2.0, hub 4 x 2.5, width 1.4, 3.00 EUR) with THREE pawls offset by 1/3 tooth: 0.058 U per step** (0.087 with two pawls, 0.174 with one). Thin, cheap, in the target window, comfortably below the 6.0 mm OD limit. Needs the bore sleeve (option 1). Check the 1.4 mm tooth thickness against pawl stiffness.
2. **GHW 390755, z18 (OD 6.0, bore 2.0, width 5, 16.15 EUR; machine to 2-3 mm) with three pawls: 0.048 U per step** (0.0725 with two pawls). Closest to the middle of the window and a finer ratchet pitch. OD exactly 6.0 mm, so check pawl clearance against the 8.5 mm pod height. The Maedler z18 equivalent is unconfirmed.

Neither candidate hits the target with one or two pawls. If three pawls do not fit the layout, the alternative is a custom ratchet wheel (laser cut, wire EDM or 3D-printed) with 44-60 teeth. A catalogue module 0.1-0.2 wheel was not found.

### Motor coupling (Ø2.0 D-flat 1.5 shaft side must have a 2.0 mm bore)
- **Best pair: GHW 753015 (z15, bore 2.0, hub 4 x 2.5, width 1.4) on the motor, driving GHW 753012 (z12, bore 1.5, OD 4.2, width 4) on the leadscrew side.** Ratio 15:12 (leadscrew turns 1.25x per motor turn). Centre distance = 0.3 x (15+12) / 2 = 4.05 mm (add backlash allowance, about +0.05 mm). Total cost about 6 EUR.
- **Near 1:1 alternative: two GHW 753015 (z15/z15) gears,** centre distance 4.50 mm, with a bore sleeve on the leadscrew side. About 6 EUR.
- Neither gear has a D bore or set screw. Fix the 2.0 mm round bore on the D-flat shaft with retaining compound (the flat leaves a 0.5 mm gap, filled by adhesive) or a light press fit. A D-bore gear was not found in any catalogue.
- Maedler z14-z18 (width 5, bore 2.0) are equivalent if you want a wider face, but article numbers are unconfirmed.

## 5. Suppliers checked with no usable result

| Supplier | Finding |
|---|---|
| Maedler (maedler.de) | Shop returned 403. Module 0.3 seen only via Ameco/third-party. No module 0.2 found. **UNVERIFIED** at maedler.de. |
| KHK / Misumi | Brass miniature gears start at module 0.5 (BSS0.5-xx, bore 4-5 mm). Stainless from module 1. No module 0.2-0.3. A Misumi snippet mentioned "module 0.3" but material/bore was not confirmed. |
| HPC Gears | Only large-module steel gears found (m0.75, m1.5). No m0.2. |
| Cousins UK | Clock ratchet wheel "Set Up, English Dial" is 26 mm brass with a 5 mm square. Not suitable. No small ratchet wheel found. |
| Jules Borel, Reely/Conrad, Modelcraft | Not searched in depth, no results obtained. **UNVERIFIED.** |
| RS Components | RS PRO / Igus gears are module 0.5 and up with bores of 4 mm or more. Kyouiku brass m0.3 (see C). |
| Miniature Bearings Australia | m0.4 brass z8 with bore 1.5 mm (OD 4.0) exists but is discontinued and has too few teeth. |
| AliExpress / eBay | Listings for brass module 0.3/0.4/0.5 gears exist (for example m0.4 z8-12 with 1.5 mm bore). Not verified, last resort only. |

## 6. Open items
1. Confirm shipping of GHW to your address (the "not available in your delivery country" notice).
2. Get the Maedler price list or an account for the 2600xxxx series, confirm the z14-z18 article numbers.
3. Decide on 3 offset pawls vs. a custom 44-60 tooth wheel, then update `spec/design-parameters.md`.
4. Check pawl and ratchet tooth profile compatibility: involute gear teeth are symmetric, so a pawl locks only by acting between teeth (the pawl tip engages a tooth gap and holds in both rotational directions unless the pawl is spring-biased and the drive is one-way). This works as a bench test, but is not a true sawtooth ratchet.
