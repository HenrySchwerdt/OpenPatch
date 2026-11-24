# Buy list: bought-in hardware for the "cup" pod (2 pods + spares)

> **TEST ONLY, NOT FOR HUMAN USE** (see `../DISCLAIMER.md`). Bench only, water only, never worn, never filled with insulin or any other drug.
> Scope: every bought-in **hardware** part of the v0.1.0 cup pod (`mechanical/V010-CUP.md`, `mechanical/ASSEMBLY-CUP.md`, `params.json -> cup`). **Out of scope:** PCB + JLC-assembled parts, printed/CNC parts (shells, tank, plunger core, sleeve/collar if printed, U-clip stencil part, needle guard).
> Already bought: 2 x Ampul 301030 cells. **Not in this order:** Accu-Chek Insight Flex cannula heads (pharmacy / prescription).
> Research date **2026-11-20**, shipping address Germany. Prices are incl. 19 % VAT as shown on the page that day; they change daily.
> Status: **VERIFIED** = product page opened and read in this pass (title, variant, price; for gears also the dimension drawing). **CANDIDATE** = seen only in a search result list (title + price), or a spec on the page is missing/ambiguous: re-check in the shop before paying.

## 0. Most important finding: the miter gear pair

**A module 0.3, z16, 1:1 miter pair (CAD `cup.gears`: m0.3, z16, tip OD 5.4) is not orderable as a catalogue part.** What really exists in small quantity:

| Option | Source | Pitch d | OD | Fits 6.7 mm cavity? | Status |
|---|---|---|---|---|---|
| **m0.3 z12 miter, 1:1, 90 deg, brass, bore 1 mm or 2 mm** | AliExpress "MiMi Hotsell" 1005010269458834, 7.19 EUR per lot of **2 gears**, EU DHL delivery (page: "Zustellung Nov 29-30", free shipping over 10 EUR) | 3.6 | **4.02** (drawing) | yes (more room than today) | **VERIFIED** incl. dimension drawing |
| same part, 5 pcs | AliExpress "YH Hobby Store" 1005009147007928, 18.99 EUR / 5 pcs, bore 1 or 2 mm | 3.6 | n/v | yes | VERIFIED (title/price/variants; no drawing read) |
| m0.4 z12 bevel, 90 deg, brass, bore 2 mm "tight fit", 0.5 mm step (hub) | AliExpress "Devota Store" 1005007902363549, 2.89 EUR per gear, shipping 4.76 EUR, delivery Dec 8-15 | 4.8 | ~5.37 (computed, no drawing on the page) | yes | VERIFIED (title/variant/price), dims CANDIDATE |
| m0.5 1:1 pairs | modellbau-profi.de: smallest 1:1 is **z20/z20** (01220512820/20, 11.20 EUR/pair) and z27/27; AliExpress m0.5 1:1 sets start at z12 (OD ~6.7) | >= 6.0 | 6.7 .. 10.7 | **no** (z20 OD ~10.7; z12 OD ~6.7 = whole cavity height) | page read (modellbau-profi), AliExpress search list |

Drawing of the m0.3 z12 part (seller drawing, read 2026-11-20): OD **4.02**; 2 mm-bore version: bore **2 -0.02/-0.04** (press fit on the D-shaft), hub **3.0 -0/-0.03**, overall length 3.26, **mounting distance (pitch-cone apex to back face) 4.22**; 1 mm-bore version: hub 2.8, length 2.36, **mounting distance 3.32**. Assembled pair (1 mm gear + 2 mm gear): tooth front 1.59 from the mating axis, gear front face **0.96** from the mating axis.

**Recommendation: buy the m0.3 z12 pair (primary) and 4 x m0.4 z12 (fallback).** Ratio stays 1:1, so the thrust (8.6 N computed) and U/step (0.00703, firmware preset `nfp-608-26-45-cup-miter-1-1`, id 0x26) do **not** change. Geometry impact for the CAD (`params.json -> cup.gears`, `op_cup.py`):
* m0.3 z12: `z_motor = z_rod = 12`, `tip_od` 5.4 -> **4.02**, gear body from **0.96** (front) to **4.22** (2 mm bore, back face) / **3.32** (1 mm bore) from the mating axis (today 1.2 .. 3.4 = `bevel_back`). The hub can be faced shorter on the back if 4.22 is too long. Cone distance 2.55 instead of 3.39; the gear stage gets **0.7 mm smaller in radius** (frees width/height). Check the motor shaft end (shaft r 1.0) against gear B's front at 0.96 from the motor axis.
* m0.4 z12: same pitch cone as the CAD's m0.3 z16 (pitch d 4.8, cone distance 3.39): **near drop-in for today's CAD**; real OD/hub length to be measured on arrival.
* **Conflict:** the angle magnet (`cup.magnet` d2.0 x 1.0) sits in the apex region between the two gear fronts (today x = motor axis +0.2 .. +1.2, gear fronts at 1.2). With z12 the fronts move to 0.96 < magnet radius 1.0, so a d2 magnet collides with gear A's front. Fixes: face 0.25 mm off both gear fronts (back to 1.2), or use a smaller diametric magnet (d1 x 0.5 is in the same listing), or move the magnet.
* Rod side: use the **1 mm-bore** z12 as gear B and drill 1.25 + tap M1.6 (screw onto the rod, lock with retaining compound) or drill 1.6 and bond: this **removes the 2.0/1.64 thrust sleeve**, which has no matching catalogue tube anyway (see §4).

## 1. Cart A: AliExpress (one checkout, 3 stores)

| # | Function | Spec from CAD / params | Listing (opened) | Price | Pack | Qty | Line | Ship / lead time | Status |
|---|---|---|---|---|---|---|---|---|---|
| A1 | Gear A (motor side, on the D-shaft d2.0) | miter 1:1 90 deg; see §0 | MiMi Hotsell "0,3 m 12 Zähne 1/2 mm 90-Grad-Getriebe ... 1:1", variant **2mm**, https://de.aliexpress.com/item/1005010269458834.html | 7.19 | 2 gears | 2 lots | 14.38 | EU DHL/Hermes, free > 10 EUR, ~1 week | VERIFIED (drawing) |
| A2 | Gear B (rod side, drill/tap for M1.6) | same | same listing, variant **1mm** (price read with 2 mm selected) | 7.19 | 2 gears | 2 lots | 14.38 | same parcel | VERIFIED |
| A3 | Fallback drop-in pair (m0.4 z12) | pitch d 4.8 = today's CAD | Devota Store "0,4 m 12 t 2 mm Messing ... Kegelrad ... 90-Grad", variant 12T 0.5 mm step, 2 mm, https://de.aliexpress.com/item/1005007902363549.html | 2.89 | 1 gear | 4 | 11.56 | 4.76 shipping, Dec 8-15 | VERIFIED (no drawing) |
| A4 | Angle magnet (gear B, TMAG5273) | `cup.magnet` d2.0 x 1.0, diametric, N52 | Tengrunfa Store "Radialmagnet ...", variant **Radial-D2x1mm**, https://de.aliexpress.com/item/1005010279518166.html | 9.59 | 50 pcs | 1 | 9.59 | n/v (not read) | CANDIDATE: page text is AI-generated; "radial" is the Chinese sellers' word for diametric discs. Verify with magnetic viewing film / compass. Same listing has D1x0.5, D2x0.5, D3x1.5 radial |
| A5 | Dock magnet (in the cannula head adapter / coupon) | `cup.dock.head.magnet` **d1.0 x 0.5**, axial | Tengrunfa Store "Runde Mikromagnete 1x0,5 ...", variant **1x0.5mm**, https://de.aliexpress.com/item/1005009598719720.html | 8.29 | 50 pcs | 1 | 8.29 | n/v | VERIFIED (variant/price; grade and axial direction not stated: magnets this size are axial by default) |
| | | | | | | | **58.20 + 4.76 = 62.96** | + Tengrunfa shipping n/v | |

Note: `docs/PARTS-LOCK.md` #8 says the dock magnet is d2 x 1; the current CAD (`cup.dock.head`) uses **d1.0 x 0.5**. If the d2 x 1 is kept, use supermagnete S-02-01-N (axial N48, 0.20 EUR/pc, 20 pcs, **20 EUR minimum order**, page read) or a Tengrunfa 2x1 axial.

## 2. Cart B: GHW-Modellbau (ghw-modellbau.de, DE, DHL)

| # | Function | Spec | Listing (opened) | Price | Pack | Qty | Line | Status |
|---|---|---|---|---|---|---|---|---|
| G1 | Leadscrew | M1.6 x 0.35; rod length OP-100 16.2 / OP-200 25.6 mm (`mech.json`) | DIN 975 Gewindestange **Stahl verzinkt**, **M1.6 x 125**, art. 340975 M1.6, https://ghw-modellbau.de/DIN-975-Gewindestange-Stahl | 1.85 | 1 rod | 2 | 3.70 | VERIFIED (product "Auf Lager", per-variant stock not shown) |
| G2 | Leadscrew alternative | same, brass | DIN 975 Gewindestange **Messing**, M1.6 x 125, art. 350975 M1.6, https://ghw-modellbau.de/DIN-975-Gewindestange-Messing-blank | 1.85 | 1 rod | 1 | 1.85 | VERIFIED |
| G3 | Plunger nut, brass | DIN 934 M1.6, CAD AF **3.2** | DIN 934 6KT-Mutter **Messing** M1.6: **SW 3.5**, h 1.3, art. 350934, https://ghw-modellbau.de/DIN-934-6KT-Mutter-Messing-blank | 10.40 | 50 | 1 | 10.40 | VERIFIED: **AF 3.5, not 3.2** |
| G4 | Plunger nut, A2 (fits today's pocket) | AF <= 3.2 | 6KT-Mutter (ähnlich DIN 934) **Edelstahl A2** M1.6: **SW 3.0**, h 1.3, art. 860934, https://ghw-modellbau.de/6KT-Mutter-aehnlich-DIN-934-Edelstahl-A2-blank | 2.60 | 10 | 1 | 2.60 | VERIFIED (fits the 3.2 pocket with 0.2 clearance + glue) |
| G5 | Lid screws | M1.2 countersunk, head d2.4 x 0.6, 3 per pod, pilot d1.0 x 4 deep | DIN 963 Senkkopf **Edelstahl A2 M1.2 x 5**, art. 360963, https://ghw-modellbau.de/DIN-963-Senkkopf-Schraube-Edelstahl-A2-blank | 14.45 | 50 | 1 | 14.45 | VERIFIED (head dims not on the page; DIN 963 M1.2 nominal dk 2.3). M1.2 x 4 is 12.90 if the lid roof is < 1 mm |
| G6 | Thrust collar | `cup.collar` 2.4 / 1.64 x 1.0 | Messing Rundrohr MS63 **2.5 x 0.45** (ID 1.6) x 500, art. 913025, https://ghw-modellbau.de/Messing-Rundrohr-MS63-alle-Groessen | 2.95 | 1 | 1 | 2.95 | VERIFIED (OD 2.5 instead of 2.4) |
| G7 | Bush (thrust bearing in the U rib) | `cup.bush` 3.0 / 1.7 x 1.0 | same page, **3 x 1.0** (ID 1.0) x 500, art. 913031, drill to 1.7 | 5.95 | 1 | 1 | 5.95 | VERIFIED (needs a 1.7 drill; no 3.0 / 1.7 tube exists) |
| G8 | Needle hub sleeve | `cup.dock.hub` d1.5 x 0.7, press 0.08 | same page, **1.5 x 0.2** (ID 1.1) x 500, art. 913015; 30G needle bonded in with CA | 1.95 | 1 | 1 | 1.95 | VERIFIED tube; use as hub = CANDIDATE (CAD has no hub part spec) |
| G9 | Board screws (added 2026-11-20) | M1.2 x 4 cheese head (ISO 1207 / DIN 84, head d2.0 x 0.8), **brass** (non-magnetic, near the HJ-840), 2 per pod, thread-forming into a d0.95 resin pilot | GHW DIN 84 Zylinderkopf **Messing** M1.2 x 4 (same shop family as G5) | n/v | n/v | 1 | n/v | CANDIDATE (listing not opened in this pass; A2 is weakly magnetic, titanium M1.2 is the other option) |
| | | | | | | | **43.85** + G9 | + shipping (amount only shown in the cart, not read) |

GHW also sells the A2 DIN 975 rod only from M2 (sold out): **no stainless M1.6 rod found in any EU shop** (also not on AliExpress: the only M1.6 "full thread" listing, 1005013654231446, was sold out for M1.6).

## 3. Cart C: Amazon.de

| # | Function | Spec | Listing | Price | Pack | Qty | Line | Ship | Status |
|---|---|---|---|---|---|---|---|---|---|
| Z1 | Outlet needle 30G + fill needle 27G (`cup.fill.needle_d` 0.4) | 30G blunt, OD 0.31, cut to length | KSJEHW 90-pc blunt dosing needle set 14G-30G, 13 mm (6 per size), https://www.amazon.de/dp/B0H11LP18S | 7.99 | 90 | 1 | 7.99 | ~Nov 25 | VERIFIED |
| Z2 | Rim gasket + head washers | gasket 0.5 thick, 20 % squeeze; washer 0.3 (d2.4/d1.3) | sarian silicone sheet 200 x 300, **0.5 mm translucent**, https://www.amazon.de/dp/B0CHYYJBYV | 7.64 | 1 | 1 | 7.64 | ~Nov 25 | VERIFIED: **Shore A 60** (spec 40-50); no 0.3 mm thickness offered |
| Z3 | Fill septum | d1.6 x 1.0 in a d1.7 pocket | same listing, **1 mm translucent** | 8.49 | 1 | 1 | 8.49 | same | VERIFIED (Shore 60) |
| Z4 | Plunger seals (cast) | 2-part silicone, Shore A ~40, 1:1 | TFC Baseline 200 Shore **35**, 1:1, 1 kg, https://www.amazon.de/dp/B0CZRW8RLX | 26.80 | 1 kg | 1 | 26.80 | Nov 21-23 | CANDIDATE: page does not say platinum/addition cure. RESION 40 Shore A 1:1 1 kg (https://www.amazon.de/dp/B0B5S25NNL, 33.99, page read, cure system also not stated) is the alternative |
| Z5 | Retaining compound (gear A on the D-shaft) | Loctite 638 | **Loctite 648**, 5 ml (sold by Amazon), https://www.amazon.de/dp/B0000WRNVM | 8.29 | 5 ml | 1 | 8.29 | ~Nov 25 | VERIFIED (648 = high-strength retaining compound, substitute; 638 not confirmed on amazon.de) |
| Z6 | CA glue (magnet on gear B, needle in hub) | cyanoacrylate | Loctite Super Glue Power Flex gel 3 g, https://www.amazon.de/dp/B005HJQ3FK | 6.99 | 3 g | 1 | 6.99 | ~Nov 25 | VERIFIED |
| Z7 | Motor / cell wires | 30 AWG | sourcing map 30 AWG silicone stranded, 3 m, B0CHVKG8NL | 8.19 | 3 m | 1 | 8.19 | n/v | CANDIDATE (search list) |
| Z8 | Heat shrink | 1-1.5 mm | Vinabo heat shrink set 900 pcs, 1-13 mm, B0C143M8ZH | 8.49 | 900 | 1 | 8.49 | n/v | CANDIDATE |
| Z9 | Kapton tape | 5 mm | QUARKZMAN polyimide tape 5 mm x 33 m, 2 rolls, B0F1XTLVXW | 4.59 | 2 | 1 | 4.59 | n/v | CANDIDATE |
| Z10 | Hook-and-loop (bench fixture mounting only) | self-adhesive | Velcro tape 20 mm x 5 m, black, B0DTKPGH2X | 6.79 | 5 m | 1 | 6.79 | n/v | CANDIDATE |
| Z11 | Punch for septum discs | d1.5-1.6 | Biopsy punch 1.5 mm, B0CJ8C32GF | 10.99 | 1 | 1 | 10.99 | n/v | CANDIDATE |
| | | | | | | | **105.25** | free delivery on most lines | |

## 4. Cart D: motor (nfpshop.com / precisionminidrives.com)

| # | Function | Spec | Listing | Price | Qty | Line | Status |
|---|---|---|---|---|---|---|---|
| M1 | Drive motor | NFP-608-26.45-SGM, d6, 26.45:1, d2 D-shaft | nfpshop.com (page **could not be opened** from this session: navigation refused; price from `docs/PARTS-LOCK.md` #2) | 6.60 USD (10+: 5.40) | 5 (2 pods + 3 spares, connector/shaft sample) | ~33 USD + shipping 12-30 USD (estimate) + EU duty/VAT | CANDIDATE |

## 5. Totals (incl. VAT, without the shipping amounts not shown)

| Cart | Total |
|---|---|
| A AliExpress (3 stores) | **62.96 EUR** (+ Tengrunfa shipping n/v) |
| B GHW-Modellbau | **43.85 EUR** (+ shipping, shown only in the cart) |
| C Amazon.de | **105.25 EUR** |
| D Motor (nfpshop) | **~33 USD + ~12-30 USD shipping** (estimate, page not read) |
| **Sum A-C** | **212.06 EUR** + motor + 2 shipping lines |

Big-ticket items that can be dropped: Z4 casting silicone (26.80, only if the seals are cast at home), A3 fallback gears (16.32), Z11 punch (10.99, a sharpened 1.5 mm brass tube works).

## 6. Parts that do NOT exist as specified (CAD / spec must change)

> CAD status 2026-11-20: items 1-8 and 11 (hub) are adapted in `params.json -> cup` / `op_cup.py` (table "Parts adaptation" in `mechanical/V010-CUP.md`). Item 9 (washers) cannot be solved in the 0.9 mm lid roof: no washer, seal the heads with silicone. Open: guard spring (11), 3.3 mm punch for the flat hub ring (8). New rod length 16.4 / 25.9 mm.

1. **Miter pair m0.3 z16 1:1**: not a catalogue part. Use **m0.3 z12** (OD 4.02, drawing in §0) or **m0.4 z12** (same pitch cone as today's CAD). Module 0.5 1:1 does not fit the 6.7 mm cavity. Update `cup.gears` (z, tip_od, front 0.96 / back 4.22 or 3.32) and the PARTS-LOCK row 3 (still lists the old GHW spur pair).
2. **Angle magnet d2 in the apex**: collides with z12 gear fronts (0.96 < r 1.0). Face the gear fronts 0.25 mm or use d1 x 0.5 / relocate.
3. **M1.6 nut AF 3.2**: brass DIN 934 M1.6 is **AF 3.5** (GHW); the only AF <= 3.2 found is GHW A2 "ähnlich DIN 934" **AF 3.0**. Either keep the 3.2 pocket with the A2 nut + glue, or change the pocket to 3.5 for brass.
4. **Stainless A2 M1.6 rod**: not found in small quantity anywhere; use zinc-plated steel or brass DIN 975 M1.6 x 125 (GHW). The rod never touches water (checked in `cup_check.py`).
5. **Thrust sleeve 2.0 / 1.64**: no tube OD 2.0 / ID 1.6 (GHW: 2 x 0.3 = ID 1.4). Remove it: 1 mm-bore z12 gear B drilled 1.25 + tapped M1.6 (or drilled 1.6 + bonded) directly on the rod.
6. **Collar 2.4 / 1.64**: use tube 2.5 x 0.45 (ID 1.6): collar OD 2.4 -> **2.5**.
7. **Bush 3.0 / 1.7**: no tube; drill a 3 x 1.0 tube to 1.7 or print the bush (SLA).
8. **Hub O-ring 3.2 / 2.4 (cross-section 0.4)**: no listing found (searches returned 2.4 mm cross-sections only; specialist micro O-ring shops not checked). Change the groove to a standard micro O-ring (cross-section 0.5) or punch a flat silicone ring from the 0.5 mm sheet.
9. **0.3 mm silicone head washers**: no 0.3 mm sheet found; use 0.5 mm and deepen the countersink by 0.2 mm.
10. **Shore A 40-50 silicone sheet**: the sheet found is Shore A 60; acceptable for water bench tests but the 20 % gasket squeeze needs more screw force. Real Shore 40 sheet: CS Hyde / ElastaPro (see PARTS-LOCK #18, EU shipping n/v).
11. **Needle hub d1.5** and **guard spring 0.3 N**: no catalogue parts; the CAD does not define the spring (wire, OD, length). Hub = 1.5 x 0.2 brass tube + CA (G8); spring not in this order.
12. **Loctite 638** not confirmed on amazon.de; Loctite 648 (same class) listed.
13. **Soldering**: 30 AWG wire + heat shrink are for the motor/cell leads soldered to the board pads (user decision 2026-11-20); this contradicts "assembly without a soldering iron" (spec §1a, CLAUDE.md) and needs a decision entry.

Tools assumed but not priced: pin vise, drills 1.25 / 1.6 / 1.7, M1.6 tap, calipers, tweezers.

## Evidence (all retrieved 2026-11-20)
AliExpress pages read in a browser session (cookies declined): 1005010269458834 (drawing in the description), 1005009147007928, 1005007902363549, 1005010279518166, 1005009598719720, 1005013654231446. GHW pages: Gewindestange Stahl / Messing / Edelstahl A2, DIN 934 Messing, 6KT A2 ähnlich DIN 934, DIN 934 A2 (M1.6 = SW 3.5, 10 pcs 2.30 EUR), DIN 963 A2, Messing Rundrohr alle Größen. modellbau-profi.de Kegelrad Modul 0,5 catalogue. supermagnete S-02-01-N. Amazon.de product pages B0H11LP18S, B0CHYYJBYV, B0CZRW8RLX, B0B5S25NNL, B0000WRNVM, B005HJQ3FK (read); B0CHVKG8NL, B0C143M8ZH, B0F1XTLVXW, B0DTKPGH2X, B0CJ8C32GF from search result lists only. nfpshop.com: not reachable.

## 7. "Cart" pump (Insight-class cartridge variant, `mechanical/V010-CART.md`, added 2026-11-24)

> Water only: the cartridges are bought EMPTY and filled with water; never buy or use a prefilled drug cartridge (NovoRapid PumpCart is prescription-only and out of scope). Sources and REF/PZN checks: `docs/insight-research.md`.
> Reused unchanged from the cup pod (no extra line): NFP-608-26.45 motor (D), angle magnet d2 x 1 (A4), dock magnet d1 x 0.5 for the lock flag (A5), Ampul 301030 cell, main board (JLC order), wires / heat shrink / Loctite 648 / CA (Z5-Z8), lid screws (G5).

| # | Function | Spec from CAD / params | Listing | Price | Pack | Qty | Status |
|---|---|---|---|---|---|---|---|
| K1 | Insight Adapter & Tubing (adapter with needle + vent, tubing integrated) | original part, unmodified; 40 cm for the smallest dead volume (90 ul) | Accu-Chek Insight Adapter & Schlauch 40 cm, REF 06485472001, **PZN 08460327**, any German pharmacy; or https://www.ebay.de/itm/136429243755 | 37.50 list / 48.45 RRP | 10 | 1 | VERIFIED (Roche price list 09-2026); avoid the 2022 recall lots |
| K2 | Empty 1.6 ml glass cartridge | `cart.cartridge` (all ESTIMATE: OD 11.6 / ID 9.7 / barrel 36) | mylife YpsoPump Reservoir 1.6 ml, **PZN 11160770**, https://www.docmorris.de/mylife-ypsopump-reservoir/11160770 | about 50-61 | 10 | 1 | CANDIDATE: same 1.6 ml cartridge class as PumpCart; fit and seal with K1 UNVERIFIED (first thing to test) |
| K3 | Spur pinion | m0.3 **z12**, brass, bore **2.0** (NFP D-shaft, Loctite 648) | AliExpress search "0.3 module brass gear 12T 2mm" | n/v | n/v | 2 | CANDIDATE (no listing opened in this pass) |
| K4 | Spur gear (gear nut) | m0.3 **z40**, brass, tip d12.6, face 2.0, bore <= 2.0 (opened up for the M2 nut hex pocket AF 4.0 or a bonded nut on the face) | AliExpress search "0.3 module brass gear 40T" | n/v | n/v | 2 | CANDIDATE; fallback m0.5 z10 : z20 (tip d11.0, ratio 2: thrust 1.0x of need, too weak) |
| K5 | Piston rod | DIN 975 **M2 x 0.4**, brass or zinc-plated steel, cut to 29.55 | GHW DIN 975 Gewindestange (same pages as G1 / G2), variant M2 | ~1.9 | 1 rod | 1 | CANDIDATE (variant M2 not read) |
| K6 | Gear nut | DIN 934 **M2 brass**, AF 4.0, h 1.6 | GHW DIN 934 6KT-Mutter Messing (same page as G3), variant M2 | n/v | n/v | 1 | CANDIDATE (variant M2 not read) |
| K7 | Thrust washers (2 per pump) | 0.2 thick, d5.0 / d2.2 | PTFE film 0.2 mm or brass shim, punched | n/v | | | CANDIDATE |
| K8 | Lock hall (only if the board's own DRV5032 cannot see the flag) | DRV5032FA SOT-23 on a 3-wire pigtail | LCSC / JLC part already in the board BOM | ~0.5 | | 2 | CANDIDATE |
| P | Printed parts | `out/v010-cart/OP-CART_{bottom,top,slider,pusher,lock_flag}.stl`; lid gasket from the 0.5 mm silicone sheet (Z2) | JLC3DP SLA (clear resin for the lid) | n/v | | 2 sets | first print: bottom + top only to test the cartridge / adapter fit |

Not needed for the cart pump (cup-only lines): miter gears A1-A3, M1.6 rod / nuts G1-G4, collar / bush tubes G6-G8, 30G needles Z1, septum sheet Z3, casting silicone Z4, punch Z11.
