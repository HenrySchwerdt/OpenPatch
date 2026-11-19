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

## Price log (fill in after each order)

| Date | Vendor | What | Qty | Price paid | Notes |
|---|---|---|---|---|---|
| | | | | | |
