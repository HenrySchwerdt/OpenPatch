> **TEST ONLY - NOT FOR HUMAN USE** (see `../DISCLAIMER.md`). Bench tests with **water only**; cartridges are bought empty; the line ends in a container on a scale. Non-EU parts: bench (water) tests only.

# Cart pump: per-pump cost and order package (2026-11-24)

Design: `mechanical/V010-CART.md` (variants A and B share chip set, motor and gears; since 2026-11-25 A has a yoke drive and its own 20.5 x 28.9 board outline, B the 57.0 x 10.6 strip; board cost per variant is the same, the chip set sets it). Research and prices: `docs/insight-research.md` §3-7, `docs/BUY-LIST.md` §7. V = price read on the listing, E = estimate. EUR, incl. VAT; USD x 0.92.

## Per-pump cost (hardware, without consumables)
| Item | qty 1 | qty 5 | qty 10 | Basis |
|---|---|---|---|---|
| Main board (cart outline, cup chip set), JLC 4-layer PCB + PCBA | 196.4 | 51.9 | 37.0 | PCB 20-25 USD, PCBA setup + stencils 30, extended-part fee 22 x 3 = 66, assembly 2 / board, parts 17.2 / board (cup BOM, JLC API 2026-11-24), DHL 25, 19 % import VAT; JLC minimum 2 assembled boards (E) |
| TMAG5273 strip (panelised with the main board) | 2.0 | 2.0 | 2.0 | E: small breakaway in the same panel, TMAG5273 + 3 passives |
| Motor NFP-608-26.45 (nfpshop) | 24.5 | 11.0 | 8.5 | 6.60 USD V + about 20 USD shipping per order E; 1 spare from qty 5 |
| Spur gears m0.3 z12 + z40 (AliExpress) | 9.3 | 3.6 | 2.9 | z12 4.19 / 10 pcs V, z40 2.15 each V, shipping about 3 E |
| M2 rod + brass M2 nut (GHW) | 9.9 | 2.4 | 1.4 | rod 1.9 per 125 mm (4 pumps) V-family, nuts about 3 / pack E, shipping about 5 E |
| Magnets: angle d2x1 + lock d1x0.5 (AliExpress packs) | 17.9 | 3.6 | 1.8 | packs of 50, V |
| Cell Ampul 301030 | 10.0 | 5.2 | 4.6 | 4.00 EUR V + about 6 shipping E |
| Screws 3 x M2x8, 2 PTFE washers, gasket share | 4.3 | 1.1 | 0.7 | E |
| Housing printed (own FDM, PETG about 30 g + TPU button) | 0.8 | 0.8 | 0.8 | E; JLC3DP resin instead: about 8-12 EUR per pump E |
| Wires, heat shrink, CA, Loctite (shares of packs already bought) | 1.0 | 1.0 | 1.0 | E |
| **Pump total (EUR, without consumables)** | **276** | **82** | **61** | target about 40, max 80 |

**Update 2026-11-25 (board routed, live JLC prices, `electronics/v010/cart/COST.md`):** the B board needs **6 layers** (4 did not route) and 0.2 mm vias, so the PCB is a "high precision" order (77.85 EUR for 5 PCBs instead of about 23). Board per pump **70.5 / 45.2 / 32.5 EUR** at 5 / 10 / 20, pump total about **101 / 69 / 52 EUR**: 5 pumps are above the 80 EUR max, **10 pumps are inside**. Order 10.

**Verdict (2026-11-24 estimate, superseded by the update above):** the ~40 EUR target is **missed** at small quantities: about 82 EUR each for 5 pumps (just over the 80 max), 61 EUR for 10, about 49 EUR for 20. **The main board is the cost driver** (fixed JLC fees: extended-part fee 66 USD, PCBA setup, shipping, spread over the batch); the mechanics are about 15-20 EUR. A single pump costs about 276 EUR because JLC's minimum order (5 PCBs, 2 assembled boards) and every shipping fee land on it.

### What to cut to reach ~40 EUR (in order of effect)
| Lever | Saving per pump (qty 10) | Cost / risk |
|---|---|---|
| Build 20-30 boards in one JLC order (fees spread) | board 37 -> 29 (20) / 26 (30) | needs the routed cart board and the money up front |
| Replace the 3 extended resistors (6.8k, 220k, 30k) by basic values, check other extended passives | about 0.9-1.5 (3 USD each per order) | divider re-calc (electronics) |
| One AliExpress / GHW / Ampul order for 10-20 pumps (shipping spread) | 1-2 | none |
| Motor: GM12-10BY 10 mm geared stepper (5.09 + 3.90 per order, AliExpress) instead of the NFP-608 | about 3.5 | stall force up to about 140 N (holding torque): needs firmware stall detection + reduced coil voltage; CAD change (10 x 12 x 20 can, direct-drive gearbox) |
| Own FDM housing instead of JLC3DP resin | 8-12 vs resin | already assumed |
| Drop the TMAG angle sensor (step count only) | about 2 | **not recommended**: the angle-shortfall occlusion detection depends on it |
Not cut: the interlock parts (TPL5010, supervisor, TPS2553, AND gates) and the safety sensors stay (spec §1d: safety parts are never downgraded for cost).
**Realistic:** about 45-50 EUR at 20 pumps with the current parts, about 40 EUR at 20-30 pumps with the basic-part swaps and the GM12 motor.

### Compared with the cup pod
Cup pod per pod at 5: board about 60 EUR (6-layer, same chip set) + mechanics about 100 EUR (BUY-LIST §1-5: 212 EUR + motors for 2 pods + spares) + a CNC tank (not quoted) = **about 160-170 EUR**. Cart pump at 5: **about 82 EUR** (no tank, no plunger casting, no dock / needle / clip, a 4-layer board if it routes).

## Consumables (per test, listed apart)
| Item | Variant | Price | Source |
|---|---|---|---|
| Empty 1.6 ml glass cartridge (mylife YpsoPump Reservoir, PZN 11160770) | A + B | 5.02 per cartridge (50.19 / 10, DocMorris, V) | https://www.docmorris.de/mylife-ypsopump-reservoir/11160770 |
| Accu-Chek Insight Adapter & Tubing 70 cm (PZN 15379353) / 40 cm (PZN 08460327) | A | about 4.84 per set (48.44 / 10, medizinfuchs snippet; Roche list 48.45 RRP) | https://www.medizinfuchs.de/accu-chek-insight.html |
| Accu-Chek Insight Flex head set 6 mm (PZN 08459755), optional | A | 8.01 per head (80.10 / 10 list, V) | https://www.docmorris.de/accu-chek-insight-flex-6-mm/08459755 |
| B. Braun Venofix A 25G 0.5 x 19, 30 cm (PZN 17935284): plumbing stand-in only; realistic soft-cannula set see BUY-LIST K8 / K9 (~EUR 4 bench sample from China, or FlexLink ~13.7 EUR) | B | 0.59 each (V) | https://www.docmorris.de/venofix-a-venenpunktionsb25-g-05x19mm/17935284 |
| Male-male Luer-lock coupler (pluriselect Combifix) | B | about 2.5-3 (25-30 / 10, snippet); reusable on the water bench | https://www.pluriselect.com/en/shop/1366 |
| Luer-lock needle 27G 0.40 x 12 (B. Braun Sterican, 100 pcs) | B | about 0.05-0.10 (E) | any pharmacy |
Variant B also takes **any standard Luer-lock pump set** (e.g. mylife Orbit micro Luer, PZN 09892448) without a CAD change; DANA sets do NOT lock (left-hand Luer).
Per test: A about 9.9 EUR (cartridge + adapter & tubing), B about 5.7 EUR (cartridge + Venofix + needle; coupler reused).

## Order package for 5 pumps (first real bench test, after the fit print works)
| # | Shop | Items (qty) | Approx. total |
|---|---|---|---|
| 1 | **JLCPCB** | cart board **B**, 6 layers 0.8 mm ENIG, filled vias, 10 PCBs, 5 (or 10) assembled both sides: `electronics/v010/cart/jlc/` (gerbers, BOM, CPL with the verified bottom-side rotation rule, NOT-ASSEMBLED; DEV variant in `jlc-dev/`). **Routed 2026-11-25, DRC 0.** Board cost per pump 70.5 / 45.2 / 32.5 EUR at 5 / 10 / 20 (`electronics/v010/cart/COST.md`, live JLC prices). TMAG strip and lock-hall strip still to design; A board (20.5 x 28.9) not routed | about 350 EUR (5) / 450 EUR (10) |
| 2 | **nfpshop.com** | NFP-608-26.45-SGM x 6 | about 55 EUR |
| 3 | **AliExpress** | z12 m0.3 brass gears (1 lot of 10, 1005009996910236), z40 m0.3 brass (5, 1005010114512381), angle magnets d2x1 (1 pack, 1005010279518166), lock magnets d1x0.5 (1 pack, 1005009598719720) | about 35 EUR |
| 4 | **GHW-Modellbau** | DIN 975 M2 rod brass x 2, DIN 934 M2 brass nuts (1 pack), DIN 84 / 7985 M2 x 8 screws (1 pack) | about 15 EUR |
| 5 | **ampul.eu** | Ampul 301030 x 6 | about 30 EUR |
| 6 | **Pharmacy (DocMorris / medpex)** | YpsoPump Reservoir 1 box (10), Insight Adapter & Tubing 40 or 70 cm 1 box (10), Venofix A 25G x 10, Sterican 27G 0.40 x 12 (1 box), Insight Flex 6 mm 1 box (optional) | about 160-240 EUR (consumables, about 10 tests per variant) |
| 7 | **pluriselect** | Combifix male-male Luer-lock x 10 | about 30 EUR |
| 8 | own printer | PETG + TPU (housings, slider, pusher, button, B cap, coupons) | - |
Hardware for 5 pumps: about **410 EUR** (about 82 per pump); consumables about 190-270 EUR.

## Cart A v2: mechanical order (2026-11-27, read live in the owner's browser; V = price on the page that day)
Design: `mechanical/CART-A-V2-BRIEF.md`. One pump plus spares; no soldering on the board (motor plug + cell terminal).
| Shop | Item | Variant / note | Price |
|---|---|---|---|
| **precisionminidrives.com** (NFP, EU prices) | NFP-608-26.45-SGM stepper gearmotor | 200 mm 30 AWG leads, connector "JST 1.25 pitch"; shaft d2.0 with flat, 2.5 long; front boss d3.5 x 0.8 (outline drawing on the page). No accessory needed (its pinions are m0.2) | 6.03 EUR (1-9), 5.40 (10-19); shipping at checkout, free above 150 USD; V |
| **AliExpress** (one Choice order, free shipping above 10 EUR) | Pinion m0.3 z12 brass | listing 1005009996910236, "12 Teeth", bore **1.98 mm**, 4 mm long (10 pcs) | 4.19 EUR / 10; V |
| | Gear m0.3 z40 brass | listing 1005010114512381, "40T", 2 mm thick, bore 1.98, no hub | 2.15 EUR each; V |
| | Angle magnet, **diametric** ("radial") | listing 1005010279518166, variant "Radial-D2x1mm" (50 pcs). Axial 2 x 1 magnets (Amazon) do not work for the angle sensor | 8.29 EUR / 50; V |
| **GHW-Modellbau** | DIN 975 threaded rod M2 brass, 500 mm | screw 31.4 + stem 26.9 cut from it | 2.60 EUR; V |
| | DIN 934 nut M2 brass (50) | 1 in the yoke | 3.80 EUR; V |
| | DIN 963 countersunk M2 x 10, A2 (50) | 2 through the head face | 7.85 EUR; V |
| **Amazon** | Steel balls 2 mm (100Cr6 / bearing balls) | lock ball; many packs listed (e.g. 20 or 100 pcs) | about 5-8 EUR; E |
| | Loctite 648 + CA glue | pinion on the D-shaft, gear on the screw | E |
| | 1 mm double-sided foam tape | under the cell | E |
| | Clear 2 mm acrylic rod (or a piece of clear 1.75 filament) | LED light pipe, 9 mm | E |
| owner has | Ampul 301030 cell (bare red / black leads), cartridges + Insight adapter | | |
Not needed any more in v2: lock magnets, hall pigtail, lid screws. GHW's own m0.3 gears do not fit 1:1 (z12 bore 1.5; z40 "B" has a 2.5 mm hub).

**Market part dimension that changed the CAD:** m0.3 z12 pinions are sold 4 mm long (AliExpress and GHW), the CAD had 2 mm. The pinion now
runs x 28.66-32.66 through a d4.8 window in rib_f, the d2 x 1 magnet sits in its free front bore, the board gets a notch at the rear-far
corner (x 32.6-33.0, y 31.0-36.3) and the TMAG5273 moves to x 33.2-35.2 (package + shells check PASS, G-codes re-sliced).
