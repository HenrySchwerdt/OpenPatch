# Cost model

> Test project, not a medical device. Planning estimates (2026-11-19), **not quotes**. Replace the ranges with real invoice prices after every order (see the log at the end).

## Final design (Rev B: SMA drive, everything inside the pod), small quantity (one builder, 5–10 boards)

| Group | Content | per pod (USD) |
|---|---|---|
| Assembled PCB | 6-layer HDI fab + assembly, amortised over 5–10 boards | 35–60 |
| ICs + parts | nRF54L15 (~3), TPL5010, hall sensors, Qi receiver, charger, LDO, passives, buzzer | 12–18 |
| Battery + Qi coil | custom flat cell + coil | 6–12 |
| Housing + printed parts | shells, carriage, cannula adapter (JLC3DP) | 12–18 |
| Drive | catalogue gear (e.g. Mädler module 0.2), nitinol wire, crimp ferrules, stencil-cut pawls, leadscrew + nut | 8–15 |
| Small parts | seals, septum, needle, magnets, screws, Velcro | 3–5 |
| **Total per pod** | | **≈ 80–130** |

Two-pod system: 2 pods (160–260) + Qi pad (10–20) + one-off programmer (15–40) → **≈ 190–320 USD**. Cannulas (Insight Flex) are consumables and not included.

Group buy (50–100 pods): setup and HDI premiums amortise → **≈ 30–50 USD per pod** (estimate).

## One bench iteration (Rev A)

Itemised with links and quantities in [`SHOPPING.md`](SHOPPING.md) (research 2026-11). Basis: 2 pods + 1 controller, one size. **[E]** = estimate, no JLCPCB/JLC3DP/PCBWay quote yet; replace after the first order. Conversion 1 EUR = 1.10 USD.

| Item | USD |
|---|---|
| Controller board (4-layer, 5 bare / 2 assembled) | 45-60 [E] |
| Pod sensor boards (2-layer, 5 bare / 2 assembled) | 20-30 [E] |
| **Controller + pod PCBA** (target <= 80) | **65-90 [E]** (low end meets the target; levers: drop optional DRV5032 U1/U2, fewest JLC extended parts, economic assembly) |
| Printed parts, 2 pod sets + dock coupon (JLC3DP) | 31-41 [E] |
| Motors NFP-608-26.45 x2 ($6.60 each [V]) + GHW gears 2 x (3.00 + 2.95 EUR) [V] | 26 (reusable, bought once in the sample order) |
| Consumables (needles, silicone, rod/nuts, screws, magnets, FFC) | stock items, bought in packs (SHOPPING section 2) |
| Shipping (JLCPCB, JLC3DP, EU shops) | 25-50 [E] |
| **Per monthly iteration, motors/gears reused, incl. shipping** | **about 120-180** |
| Per iteration with motors/gears rebought, incl. shipping | about 147-207 |

Once per size (frozen): PCBWay CNC PP reservoir x2, **30-60 [E]** per size (90-180 for 70/100/200 U).

**Affordability:** one iteration per month (the project goal) costs **about $120-180** per month, i.e. roughly a third of the earlier ~$420 integrated-board estimate. The PCBA target of <= $80 is **met only at the low end** of the estimate: the controller alone is dominated by JLC extended-part fees and the E73 module ($6.47 [V]); a real quote from the final Gerber/BOM decides.

### Start-up costs (once)

| Item | USD |
|---|---|
| Sample order (5 motors, gears, magnets, valves, needles, silicone, FFC, rod/nuts/screws) | about 102-188 [E/V] (+ up to 68 optional gears, + 30-60 shipping) |
| One-time tools (nRF52840-DK 41.37 EUR [V], calipers, 0.001 g scale, punches, microscope, ...) | about 250-520 [E] |
| **First month all-in** (samples + tools + CNC OP-100 + one iteration) | **about 540-1,080 [E]** |

Open price risks: no verified source for a diametric Ø2 x 1 magnet, a duckbill valve <= 3 mm OD and EU-stocked medical silicone (see `PARTS-LOCK.md`); nfpshop shipping/VAT to Germany not stated.


## Rev A bench pump all-in budget (requirement <= 200 EUR, 2026-11-19)

Full line-item tables, sources and assumptions: **`docs/SHOPPING.md` §0**. All numbers are ESTIMATES in EUR incl. shipping, 19 % German VAT and the EU 3 EUR/tariff-line duty (since 2026-07-01); only JLCPCB fee schedule, PCBWay CNC minimum order (25 USD), GHW and supermagnete prices were read on live pages.

| Case | First pump | Marginal pump |
|---|---|---|
| A. Design as frozen (2 PCBA projects, CNC PP reservoir x2) | 358 - 607 | 95 - 150 |
| B. Recommended (sensor tab on controller panel, <= 6 extended parts, one JLC cart, water-only printed reservoir) | 223 - 366 (central ~295) | 65 - 95 |
| B+. Stretch (verified AliExpress motor, 5 parcels, trimmed BOM) | 176 - 288 (central ~232) | 60 - 90 |
| C. B + PCBWay CNC PP reservoir (optional material preparation; water only) | 273 - 456 | 85 - 130 |

**The <= 200 EUR first-pump target is not reliably reachable**; it is reachable for each further pump. Top drivers (A): JLCPCB PCBA fixed/extended fees + shipping (130 - 193), PCBWay CNC PP reservoir (55 - 96), JLC3DP prints + coupon (39 - 71), motor shipping (31 - 53), duty lines on many AliExpress parcels (25 - 45). Cuts and the smallest design changes are in SHOPPING.md §0.5 - §0.6. The older "one bench iteration" figure below (130 - 150 USD) is **superseded** for budgeting: it omitted shipping, VAT/duty, PCBA fees and minimum orders.

Reference fee data (verified 2026-11-19): JLCPCB economic PCBA setup 8.18 USD, stencil 1.53 USD, extended part 3.07 USD each (preferred extended free), joint 0.0016 USD; standard setup 25.56 / 51.12 USD. PCBWay CNC: PP available, minimum order value 25 USD excl. shipping. JLCCNC: no PP. GHW module 0.3 gears: 15 Z B 3.00, 12 Z B 2.95, 18 Z 16.15 EUR each incl. VAT.

## Price log (fill in after each order)

| Date | Vendor | What | Qty | Price paid | Notes |
|---|---|---|---|---|---|
| | | | | | |
