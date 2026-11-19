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

| Item | USD |
|---|---|
| Controller board (5 PCBs, 2 assembled) + pod sensor boards | ~80 (target, see `electronics/bench/COST.md`) |
| Printed parts incl. dock fit-test coupon | 30–40 (`mechanical/out/bench/fab/`) |
| Motor (NFP-608-26.45), gears, SMA test parts | 20–30 |
| **Total per monthly iteration** | **≈ 130–150** |


## Rev A bench pump all-in budget (requirement <= 200 EUR, 2026-11-19)

Full line-item tables, sources and assumptions: **`docs/SHOPPING.md` §0**. All numbers are ESTIMATES in EUR incl. shipping, 19 % German VAT and the EU 3 EUR/tariff-line duty (since 2026-07-01); only JLCPCB fee schedule, PCBWay CNC minimum order (25 USD), GHW and supermagnete prices were read on live pages.

| Case | First pump | Marginal pump |
|---|---|---|
| A. Design as frozen (2 PCBA projects, CNC PP reservoir x2) | 358 - 607 | 95 - 150 |
| B. Recommended (sensor tab on controller panel, <= 6 extended parts, one JLC cart, water-only printed reservoir) | 223 - 366 (central ~295) | 65 - 95 |
| B+. Stretch (verified AliExpress motor, 5 parcels, trimmed BOM) | 176 - 288 (central ~232) | 60 - 90 |
| C. B + PCBWay CNC PP reservoir (insulin tests) | 273 - 456 | 85 - 130 |

**The <= 200 EUR first-pump target is not reliably reachable**; it is reachable for each further pump. Top drivers (A): JLCPCB PCBA fixed/extended fees + shipping (130 - 193), PCBWay CNC PP reservoir (55 - 96), JLC3DP prints + coupon (39 - 71), motor shipping (31 - 53), duty lines on many AliExpress parcels (25 - 45). Cuts and the smallest design changes are in SHOPPING.md §0.5 - §0.6. The older "one bench iteration" figure below (130 - 150 USD) is **superseded** for budgeting: it omitted shipping, VAT/duty, PCBA fees and minimum orders.

Reference fee data (verified 2026-11-19): JLCPCB economic PCBA setup 8.18 USD, stencil 1.53 USD, extended part 3.07 USD each (preferred extended free), joint 0.0016 USD; standard setup 25.56 / 51.12 USD. PCBWay CNC: PP available, minimum order value 25 USD excl. shipping. JLCCNC: no PP. GHW module 0.3 gears: 15 Z B 3.00, 12 Z B 2.95, 18 Z 16.15 EUR each incl. VAT.

## Price log (fill in after each order)

| Date | Vendor | What | Qty | Price paid | Notes |
|---|---|---|---|---|---|
| | | | | | |
