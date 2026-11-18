# OpenPatch OP-100 Rev A - Fab / Sourcing Research (JLCPCB primary, PCBWay secondary)

Research date: 2026-11-18. All data pulled live that day.

Sources and methods:
- JLC parts data: JLCPCB parts-search API (`jlcpcb.com/api/overseas-pcb-order/.../selectSmtComponentList`) and LCSC product API (`wmsc.lcsc.com/ftps/wm/product/detail`). Prices are USD at the qty-10 tier unless noted. "Stock" is JLC stock unless noted.
- JLC capability pages: `jlcpcb.com/capabilities/pcb-capabilities`, `/capabilities/pcb-assembly-capabilities`.
- JLC fee pages: `jlcpcb.com/help/article/pcb-assembly-price` (last updated 2026-10-22) and `/In-what-cases-will-there-be-charged-extra` (2026-11-10).
- JLC EU customs notice (2026-06-27) and EU customs reform FAQ.
- PCB prices: read from the live JLC instant-quote page (cart.jlcpcb.com/quote) for 4-layer, 20 x 30 mm, FR4, "Industrial/Consumer", 3-4 day build, Single PCB.
- Anything I could not verify is marked **UNVERIFIED**.

Caveats that apply to everything below:
- The JLC quote shows a "Special Offer $8.00" line for the 4-layer prototype. It looks like a promotion. The standard engineering fee appeared as $25.00 in one stale-state quote. Expect the price to move.
- The JLC part "type" (Basic/Extended) comes from the API field `componentLibraryType` (`base` = Basic, `expand` = Extended). The API exposed a `preferredComponentFlag`, but it was false for every part I checked. I cannot confirm any part as Preferred Extended, so treat all `expand` parts as normal Extended ($3.07 feeder fee each on Economic).

---

## PART 1 - BOM line to LCSC part

Legend: B = JLC Basic, E = JLC Extended. "Alt" is a Basic substitute (electrically safe only as noted).

### 1a. Resistors, 0402 (Uniroyal 0402WGF series, 1 %, 62.5 mW)

| Value | LCSC | MPN | Type | Stock | q10 price | Note |
|---|---|---|---|---|---|---|
| 0R | C17168 | 0402WGF0000TCE | **B** | 14.6 M | $0.0012 | |
| 1k | C11702 | 0402WGF1001TCE | **B** | 30.3 M | $0.0013 | |
| 3.16k | C11462 | 0402WGF3161TCE | E | 43 k | $0.0014 | Basic alt: 3.3k C25890 (0402WGF3301TCE, B, 1.5 M, $0.0036). Only use the alt if the circuit tolerates a 4.5 % value change (not for a Vref divider). |
| 4.7k | C25900 | 0402WGF4701TCE | **B** | 12.9 M | $0.0017 | |
| 10k | C25744 | 0402WGF1002TCE | **B** | 36.6 M | $0.0015 | |
| 100k | C25741 | 0402WGF1003TCE | **B** | 8.7 M | $0.0009 | |
| 1M | C26083 | 0402WGF1004TCE | **B** | 2.8 M | $0.0011 | |
| 1.5M | C22276 | 0402WGF1504TCE | E | 650 k | $0.0011 | No Basic 1.5M found. Possible 2-resistor combos (e.g. 1M + 470k) not checked. |
| 200R | C25087 | 0402WGF2000TCE | **B** | 1.6 M | $0.0029 | |
| 330 mR (0.33 R) | C474149 | 0402WGF330LTCE | E | 8,058 | $0.0067 | Other option: Yageo RL0402FR-070R33L C852188, E, 10.9 k, $0.012. No Basic 0.33 R exists in 0402. |
| 47k | C25792 | 0402WGF4702TCE | **B** | 5.4 M | $0.0019 | |
| 10R | C25077 | 0402WGF100JTCE | **B** | 2.6 M | $0.001 | |

### 1b. Capacitors

| Required | Best LCSC part | Type | Stock | q10 | Note |
|---|---|---|---|---|---|
| 0402 100 nF 16 V X7R | C1525 Samsung CL05B104KO5NNNC | **B** | 35.2 M | $0.0024 | exact match |
| 0402 1 uF 10 V | Exact: C14445 CL05A105KP5NNNC (X5R 10 V) | E | 9.5 M | $0.0028 | **Basic alt:** C52923 CL05A105KA5NQNC (X5R, 25 V rating), B, 9.1 M, $0.0055. Higher rating means less DC-bias loss; same size. |
| 0402 4.7 uF 6.3 V | Exact: C307423 CL05A475MQ5NRNC (6.3 V) | E | 367 k | $0.0079 | **Basic alt:** C23733 CL05A475MP5NRNC (X5R, 10 V, +/-20 %), B, 1.02 M, $0.0077 |
| 0402 10 nF 25 V | Exact: C318576 CL05B103KA5NNNC (25 V X7R) | E | 58 k | $0.0057 | **Basic alt:** C15195 CL05B103KB5NNNC (50 V X7R), B, 5.55 M, $0.0038 |
| 0402 22 nF 25 V | Exact: C318578 CL05B223KA5NNNC (25 V X7R) | E | 10.8 k | $0.0075 | **Basic alt:** C1532 FH 0402B223K500NT (50 V X7R), B, 613 k, $0.0034 |
| 0402 1 nF C0G 50 V | C307441 Samsung CL05C102JB5NNNC | E | 230 k | $0.0104 | Also Murata GRM1555C1H102JA01D C76947, E, 601 k, $0.007. **No Basic C0G 0402 found.** |
| 0603 10 uF 10 V X5R | C19702 Samsung CL10A106KP8NNNC | **B** | 10.7 M | $0.0168 | |
| 0603 10 uF 25 V | C96446 Samsung CL10A106MA8NRNC (X5R, +/-20 %) | **B** | 5.7 M | $0.0343 | |
| 0603 470 nF 25 V | C1623 Samsung CL10B474KA8NNNC (X7R 25 V) | **B** | 1.34 M | $0.0092 | |

#### Qi series cap (C0G 100 nF) - problem found
- I searched 0805, 0603 and 0402 C0G/NP0 100 nF, 47 nF and 22 nF by keyword and by paging results. **No in-stock 0805/0603/0402 C0G/NP0 cap at 22 nF, 47 nF or 100 nF exists at JLC today.** (0402 C0G rarely goes above 10 nF anyway.)
- The only in-stock C0G/NP0 100 nF parts at JLC are 1206:
  - C170182, 1206N104J500CT, 50 V NP0 5 %, E, 140.5 k, $0.1237 (q10 tier shown ~$0.12-0.24; verify)
  - C105970, C1206N104J050T, E, 2.3 k, $0.2248
- Basic X7R 100 nF 0805 exists (C49678 Yageo CC0805KRX7R9BB104, 50 V, B, $0.0138) but it is **X7R, not C0G**. Its capacitance moves with temperature and DC bias, which detunes the Qi resonance. Not recommended as the series resonant cap.
- 0603 C0G alternative: only tiny values (e.g. Murata GCM1885C1H103GA16D 10 nF C20042067, stock 2). A parallel network of C0G parts is possible but not verified in stock.
- Options (pick one):
  1. Move to 1206 C0G (C170182). It is bigger and an Extended part.
  2. Order C0G parts yourself (LCSC or Digikey) and have JLC use customer-supplied parts. Fee and acceptance **UNVERIFIED**.
  3. Re-tune the resonance for a value you can get as a stocked C0G.
- I tried several Samsung, Murata and TDK C0G MPNs that I recalled from memory (for 0805/0603). None exist in the JLC database, so I cannot give exact MPNs for those.

### 1c. Semiconductors and ICs

| Required | LCSC | MPN | Package | Type | JLC stock | q10 | Note |
|---|---|---|---|---|---|---|---|
| Schottky SOD-523 | C896535 | RB521S30T5G (onsemi) | SOD-523 | E | 3,661 | $0.0511 | Also C145179 RB521S30T1G (E, 25.7 k, $0.0641). Nexperia RB521S30,115 C179457 (SC-79, E, 85, $0.177). |
| ESD diode | C48260 | TPD1E10B06DPYR (TI) | X1SON-2 (1.0 x 0.6) | E | 300 k | $0.0448 | Cheaper clone: C2937015 TECH PUBLIC DFN1006-2 (0402-size), E, 12.9 k, $0.0241. Clones differ in specs; check capacitance and clamp. |
| N-FET AO3400A | C20917 | AO3400A (AOS) | SOT-23 | **B** | 1.13 M | $0.079 | |
| P-FET AO3401A | C15127 | AO3401A (AOS) | SOT-23 | **B** | 1.38 M | $0.0814 | |
| N-FET 2N7002 | C8545 | 2N7002 (Changjing) | SOT-23 | **B** | 6.1 M | $0.0159 | |
| P-FET SOT-323 | C3040603 | DMG1013UW (TECH PUBLIC, a copy) | SOT-323 | E | 7,946 | $0.0418 | Genuine Diodes DMG1013UWQ-13 C5624098 has stock 5 (not usable). |
| Charger | C38066 | MCP73832T-2ACI/OT | SOT-23-5 | E | 8,018 | $0.7616 | |
| 3.3 V LDO | C5446 | XC6206P332MR-G (Torex) | SOT-23-3L | **B** | 432 k | $0.1381 | Cheaper clone C347376 UMW XC6206P332MR (E, $0.0184). The UMW part is rated 250 mA, ~7 uA Iq (check your sleep budget against the 1 uA Torex). |
| Watchdog timer | C473912 | TPL5010DDCR | SOT-23-Thin-6 | E | 66.3 k | $0.2703 | |
| Flip-flop VSSOP-8 | C140267 | SN74AUP1G74DCUR | VSSOP-8 (0.5 mm) | E | 17.4 k | $0.5405 | JSMSEMI clone C53114336, $0.2978 |
| Flip-flop X2SON-8 | C2677745 | SN74AUP1G74DQER | X2SON-8 (1 x 1.4) | E | 3,505 | $0.208 | cheaper and smaller than the DCUR |
| 3D Hall | C3716049 | TMAG5273A1QDBVR | SOT-23-6 | E | 3,402 | $3.0758 | most expensive passive-class item |
| Hall switch | C2152496 | DRV5032FADMRR | SON-4-EP (1.1 x 1.4) | E | 2,254 | $0.2867 | |
| Stepper driver | C2150516 | STSPIN220 | VFQFPN-16 (3 x 3) | E | 285 | $1.6559 | low stock |
| Qi RX IC (QFN) | C55663 | BQ51013BRHLR | VQFN-20 (4.5 x 3.5) | E | 813 | $3.4427 | |
| Qi RX IC (DSBGA) | C134093 | BQ51003YFPR | DSBGA-28 | E | 319 | $1.1252 | about 1/3 the price of BQ51013 |
| PMIC | C2866577 | BQ25120AYFPR | DSBGA-25 | E | **4** | $6.2531 | **only 4 pcs in JLC stock; price rises; high risk** |
| Load switch | C2680319 | TPS22916CYFPR | DSBGA-4 (0.7 x 0.7) | E | 194 | $0.3975 | |

### 1d. Mechanical and passives

| Item | Finding |
|---|---|
| Tact switch | Omron **B3U-1000P** = C231329, E, 67 k, $0.1879. LCSC lists its height as **1.6 mm** (Omron datasheet height **UNVERIFIED**). Also C2934715 B3U-1000PM (sealed, $1.07). Cheaper copies: C49234121 Hanxia HX-B3U-1000P-1.6N (1.5 mm, E, 119 k, $0.0813); C843684 G-Switch GT-TC032A-H015-L1 (1.5 mm, $0.1938). **I found no stocked SMD tact switch <= 1.3 mm tall at JLC, so nothing meets <= 1.0 mm.** |
| 2.2 uH 0603 inductor | C98327 Sunlord MPL1608S2R2MHT (750 mA, 300 mR), E, 67.8 k, $0.0647. C365953 Chilisin CPY160808T-2R2M-NP (1 A, 200 mR), E, 55 k, $0.023. C337910 Murata LQM18PN2R2MFRL (750 mA), E, 4 k, $0.1145. C76797 TDK MLZ1608A2R2WT000 (500 mA), E, 62 k, $0.0469. All Extended. Heights not checked (**UNVERIFIED**). Check Isat against the BQ25120A peak current. |
| Buzzer, <= 1.05 mm | **None found as a placeable SMD buzzer.** Thinnest packaged piezo: CUI CPT-1117-83-SMT-TR C22359733 (11 x 9 x 1.7 mm, stock 1, $2.45); XHXDZ SMD9018 C49246958 (9 x 9 x **1.8 mm**, 4,682 stock, $0.3129); CUI CPT-9019A-SMT-TR C20181991 (1.9 mm, $1.73); Murata PKMCS0909E4000-R1 C910763 (9 x 9 x **1.9 mm**, 1,229 stock, $0.709); FUET-9018 C391035 (2.1 mm, stock 1). Magnetic types are thicker (2.0-2.5 mm, e.g. INGHAi GSC4317YA 4 x 4 x 2 mm C255307, $0.85). Bare piezo discs are 0.19-0.26 mm thick (FUET FT-12.5T-7.8A1 C48542886, FT-15T-6.0A1 C48542887, FT-20T-4.0A1 C48542877, all ~$0.05-0.07, stock 4-65). They are not pick-and-place parts; they need glue and wires, and a resonant air cavity. Finished-assembly height **UNVERIFIED**. |

### 1e. JLC assembly feasibility notes (from the capabilities page, 2026-11-18)

| Feature | Economic PCBA | Standard PCBA |
|---|---|---|
| Sides placed | **single side only** | single and double side |
| Minimum package | **0402** (no 0201) | 01005 |
| Minimum IC lead pitch | 0.40 mm | 0.35 mm |
| Minimum BGA pitch (centre to centre) | **0.5 mm** | 0.3 mm |
| Board size (single PCB) | 10 x 10 to 470 x 500 mm | **70 x 70 to 460 x 500 mm** |
| Panel size | 10 x 10 to 250 x 250 | 70 x 70 to 250 x 250 |
| Layers | 2, 4, 6 | 1-32 |
| Thickness | 0.8-1.6 mm (see table below) | no limit |
| Qty | 2-50 | 2-80,000 |
| Edge rails / fiducials | not needed | required |
| Reflow | 255 +/- 5 C, not adjustable | 240 +/- 5 C |
| SPI | no | yes |
| AOI, visual | yes | yes |
| X-ray | yes (BGA, QFN, LGA etc.; billed per part) | yes |
| Build time | 1-3 days | >= 4 days |

Economic 4-layer options (the table's layer column was lost in extraction; read as): 1.0 mm green, 1.2 mm green: lead-free or leaded HASL only; 1.6 mm green: HASL or **ENIG**. Qty 2-50. ENIG on Economic is therefore available only at 1.6 mm green (**read with some uncertainty**).

Direct answers:
- **Can JLC place 0.4 mm pitch WLCSP such as the BQ25120A YFP?** On **Standard PCBA only.** Economic stops at 0.5 mm BGA pitch. (The BQ25120A YFP/DSBGA-25 is a 0.4 mm pitch part per TI; I did not re-check the TI datasheet today - **UNVERIFIED**.) TPS22916CYFP and BQ51003YFP are likewise YFP/DSBGA parts with fine pitch, so the same limit applies (pitch **UNVERIFIED**).
- Standard requires a 70 x 70 mm minimum board, so a 20 x 30 mm board must go in a panel with rails and fiducials. **UNVERIFIED how JLC counts quantity** (panels vs boards) and whether you can leave panel positions unpopulated. If every position is populated, the parts cost multiplies (see the estimate).
- **0402** is fine on both processes. **0201 is Standard only.**
- X-ray is applied automatically for BGA/QFN/LGA parts, and is billed per part.
- Step stencil is recommended when package sizes differ a lot (JLC FAQ).
- ISP1807 (LGA-62) is **not in JLC stock** (C5264268 stock 0), so it needs consigned parts or hand soldering. LGA hand soldering is not realistic.

---

## PART 2 - JLCPCB capabilities and pricing

### 2a. Capabilities relevant to a 4-layer Rev A

Source: jlcpcb.com/capabilities/pcb-capabilities, 2026-11-18.

| Item | Value |
|---|---|
| Min track/space, multilayer 1 oz | **0.09 / 0.09 mm (3.5 / 3.5 mil)**; 3 mil is accepted in BGA fan-outs |
| Min track/space, 1-2 layer 1 oz | 0.10 / 0.10 mm |
| Min via, multilayer | 0.15 mm hole / 0.25 mm pad (preferred min hole 0.2 mm). 0.1 mm hole / 0.2 mm pad only for board <= 1.0 mm and ENIG/OSP. Pad should be 0.10-0.15 mm bigger than the hole. |
| Default via in the quote UI | 0.3 mm hole / 0.4-0.45 mm pad. Smaller options cost more (see 2c). |
| PTH annular ring, multilayer 1 oz | recommended >= 0.20 mm; absolute min 0.15 mm |
| BGA | min pad 0.2 mm; 0.2-0.25 mm pads need ENIG; pad-to-trace >= 0.10 mm (0.09 mm on multilayer); vias in BGA pads must be filled and plated over |
| Trace coils | 0.15 / 0.15 mm under soldermask (relevant for a PCB coil) |
| Soldermask opening to trace | >= 0.09 mm; min pad spacing 0.10 mm (green, red, yellow, blue, purple), 0.13 mm (black, white) |
| Min board size (FR4) | 3 x 3 mm (manual review may apply below 0.6 mm thickness) |
| Thickness list (page) | 0.4 / 0.6 / 0.8 / 1.0 / 1.2 / 1.6 / 2.0 mm. In the 4-layer quote UI, **0.4 and 0.6 were greyed out**; selectable: 0.8, 1.0, 1.2, 1.6, 2.0. |
| Surface finish | HASL (leaded / lead-free), ENIG, OSP |
| Impedance control | available, not needed here |
| HDI | offered: 1-, 2-, 3-step; laser blind via 0.075-0.15 mm; min trace 3 mil. **HDI price not obtained (UNVERIFIED).** Min HDI board 5 x 5 mm. |

### 2b. Measured PCB prices (quote page, 2026-11-18)

Config: 4-layer, 20 x 30 mm, FR4 TG135, 1 oz outer / 0.5 oz inner, green, "Single PCB", default 0.3 mm vias, 3-4 day build, USD, before shipping.

| Option | 5 pcs | 10 pcs |
|---|---|---|
| Leaded HASL (base, "Special Offer" $8.00 + $0.10/$0.20 deburr) | **$8.10** (measured at 1.2 mm; rows below say the thickness effect was nil) | **$8.20** |
| Lead-free HASL (+$5.00) | **$13.10** | **$13.20** |
| ENIG 1 u" (+$16.70) | **$24.80** | **$24.90** |
| 2 u" ENIG | not measured | not measured |

Thickness: at 5 pcs lead-free HASL cost **$13.10 at 0.8, 1.0 and 1.6 mm alike**, and leaded HASL cost $8.10 at 1.2 mm. **I saw no thickness surcharge between 0.8 and 1.6 mm for 4-layer at these quantities.** 2.0 mm not measured. 0.4/0.6 mm unavailable for 4-layer in the UI.

Selecting a 4-layer board with "Aerospace/Medical" product type, or some TG155/Kelvin-test options, adds items (4-wire Kelvin test $16.58-16.62, material type +$3.32-3.34). Keep "Industrial/Consumer electronics" and FR4 TG135.

### 2c. Via options (4-layer ENIG, 5 pcs, 20 x 30 mm)

| Config | Total | vs. $24.80 base |
|---|---|---|
| Default plugged vias, 0.3 mm | $24.80 | - |
| Epoxy-filled and capped vias, 0.3 mm | **$44.74** | +$19.94 (via covering +$16.62, forced "horizontal electroless" plating +$3.32) |
| Copper-paste filled and capped | **$354-360** | far too expensive; avoid |
| Plugged, 0.2 mm min via | **$64.64** | +$39.84 (min-via fee $16.62, 4-wire Kelvin test $16.58, horizontal plating $3.32, TG155 material $3.32) |
| Plugged, 0.15 mm min via | **$81.25** | +$56.45 (min-via fee $33.23 plus same extras) |
| Epoxy-filled + 0.25 mm | $81.23 | |
| Epoxy-filled + 0.2 mm | $81.26 | |
| Epoxy-filled + 0.15 mm | **$97.87** | |

Notes:
- The help page says epoxy-filled and capped via-in-pad is the default (no charge) on **6+ layer** boards, but charged on 4-layer. 4-layer measured above.
- ENIG forced the "Plugged" via cover option in the UI (tented was greyed out).
- These look mostly like fixed per-order fees, not per-board. They would likely not scale much with 10 pcs (**UNVERIFIED**; I only measured 10 pcs for the base finishes).

### 2d. Does a 0.4 mm pitch BGA/WLCSP need HDI at JLC?
My inference from the capability numbers (not a JLC statement):
- Pad 0.2-0.25 mm on a 0.4 mm pitch leaves 0.15-0.20 mm between pads. Min trace/space 0.09 mm needs about 0.27 mm for one trace between two pads. So only **outer-row balls can break out on the surface**. Inner balls (e.g. the 9 inner balls of a 5 x 5 array) need **via-in-pad**.
- Via-in-pad on 4-layer = epoxy-filled and capped vias with a 0.15-0.20 mm via: about **$81-98 per order at 5 pcs** (vs $24.80). That is about **$56-73 extra per iteration** from the quote page.
- True HDI (laser microvias) is available but price **UNVERIFIED**. A cheaper path: use only ball positions that can be routed from the outside (dog-bone with the 0.2 mm/0.3 mm via priced above), or choose a larger-pitch alternative part.

### 2e. Assembly fees (official page, updated 2026-10-22)

| Fee | Economic PCBA | Standard PCBA |
|---|---|---|
| Setup | **$8.18** | **$25.56** single-side / **$51.12** double-side |
| Stencil | **$1.53** | **$8.21** single / **$16.42** double |
| SMT assembly | $0.0016 per joint (1-100,000) | $0.0016 per joint (1-50,000) |
| Feeder loading | **$3.07 per Extended part type** (Basic free) | **$1.53 per part type, Basic and Extended** |
| Hand-soldering labor | $3.58 per order if used | $3.58 per order if used |
| Packing | free | $0.50 + $0.00003 x PCB area (cm2) |
| X-ray (BGA/QFN/LGA etc., per part count) | 1-10 pcs $1.64/pc; 11-50 pcs $0.82/pc; 51-200 $0.49/pc | same |
| Handling fee | n/a | >= $14.93 (applies only when both options are offered for the same order and the price gap is smaller) |
| Single-board surcharge | n/a | $0.48 per board minimum SMT charge |
| Fixture (rigid) | n/a | $8.21 per fixture; 1-29 pcs: 2 fixtures = $16.42 |
| Stencil / fixture storage | n/a | $4.93 each (likely optional, **UNVERIFIED**) |
| Confirm parts placement | $0.45 | $0.45 |

Extra PCB fees from the "extra costs" page: boards <= 3 cm on a side delivered as "Single PCB" get a small-board charge (table not extracted), and boards < 1.5 cm or 1.5-3 cm get a deburr/rounding charge ($0.05 / $0.02 per pcs). Choosing delivery format "Panel by JLCPCB" is the usual way around this (**UNVERIFIED for this board**).

### 2f. Shipping, customs, VAT (Germany)
- JLC quote page showed **UPS Express Saver (DDP), 2-4 business days, $26.08** for 0.14 kg of bare boards. The cart defaulted to a US destination, so the exact **Germany price is UNVERIFIED**. I did not find DHL-specific prices. Expect about $26-35 for boards plus assembled parts.
- EU customs reform (JLC notice 2026-06-27, in force since 2026-07-01): B2C shipments <= EUR 150 pay a flat **EUR 3.00 "temporary customs duty" per HS code line**; above EUR 150 standard tariff applies; B2B shipments need formal clearance. JLC says IOSS lets it collect and remit **import VAT** only, not the temporary duty. From 2026-11-01 an extra EUR 2 handling fee per customs line is charged on B2C imports.
- Carrier "duty and tax disbursement fee" for Germany if a carrier advances duty/tax (JLC FAQ): DHL **2 %, min EUR 15**; UPS **3 %, min EUR 15.70** (EUR 7.60 if shipment value < EUR 22); FedEx 2.5 %, min EUR 15. Whether the DDP service avoids them is **UNVERIFIED**.
- German import VAT: **19 %**, on goods plus shipping.
- A PCB order and an assembly order would likely carry separate HS lines: budget about EUR 6-9 of temporary duty, **UNVERIFIED**.

### 2g. Per-iteration estimate (5 bare boards ordered, 2 assembled)

Assumptions (mine, not from JLC): about 220 solder joints per board; about 22 distinct Extended part types after the Basic substitutions in Part 1 (20 if 3.16k becomes 3.3k); parts cost about $18.6 per board (q10 prices; BQ51013 variant; ISP1807 not supplied by JLC; q1-q9 tiers are higher, so $20 per board is more likely), plus about $3 for passive pack minimums; about 7 hidden-joint parts per board for X-ray (13 pcs for 2 boards). All figures USD.

**A. Economic PCBA, one-sided (2 assembled boards; PCB 5 pcs ENIG 1.6 mm)**

| Line | $ |
|---|---|
| 5 PCBs, ENIG | 24.80 |
| Setup | 8.18 |
| Stencil | 1.53 |
| SMT joints (about 440 x $0.0016) | 0.70 |
| Extended feeder fee, 20-22 types x $3.07 | 61-68 |
| X-ray (13 parts) | about 19 |
| Parts (2 boards) | about 43 |
| **Subtotal** | **about 158-165** |
| Shipping (estimate) | 26-35 |
| German import VAT 19 % on (subtotal + shipping) | about 35-38 |
| Temporary duty (EUR 6-9) | about 7-10 |
| **Total** | **about $225-250** |

Note: the **0.4 mm WLCSP parts cannot be placed on Economic** (BGA min pitch 0.5 mm). This option works only if the BQ25120A, BQ51003 and TPS22916 DSBGA parts are replaced or hand-placed. So A is the cheapest option only for a redesigned BOM. Cheaper bare-board-only route (hand assembly): 5 PCBs ENIG $24.80 (or $8.10-13.10 on HASL) + shipping $26 + VAT 19 % is about **$45-65**.

**B. Economic PCBA, two-sided: not available.** The capabilities page lists Economic as single-sided placement only. Two-sided placement needs Standard.

**C. Standard PCBA, two-sided (needed for 0.4 mm WLCSP and two-sided placement)**

| Line | $ |
|---|---|
| PCB: panel of at least 70 x 70 mm, ENIG, 4-layer (price **UNVERIFIED**; the quote page measured only 20 x 30) | about 40-70 |
| Setup, two-sided | 51.12 |
| Stencil, two-sided | 16.42 |
| Feeder loading, about 42 part types x $1.53 | about 64 |
| Fixture (1-29 pcs: 2 fixtures) | about 16.42 |
| Joints, packing | about 2 |
| X-ray | about 19 |
| Parts | about 43 **per 2 boards**; see warning |
| **Subtotal** | **about 250-285** |
| Shipping + VAT 19 % + duty | about 90-110 |
| **Total** | **about $340-395** |

**Warning (UNVERIFIED):** if the 70 x 70 mm panel holds six 20 x 30 mm boards and every position is populated, parts cost rises about 6x, to roughly $130-260 per panel. You may be able to limit populated boards or to fill only some sites; confirm with JLC engineering before ordering.

Cost-down levers:
1. Cut the number of distinct Extended part types (each costs $3.07 on Economic, $1.53 on Standard).
2. Prefer the Basic substitutions listed in Part 1.
3. Keep via at 0.3 mm and avoid via-in-pad. Via-in-pad costs about $20-73 per order.
4. Use HASL for early iterations (saves about $11-17 vs ENIG at 5 pcs).
5. Move BQ25120A and the other DSBGA parts to hand soldering or a different part.

### 2h. PCBWay (secondary, mostly UNVERIFIED)
I did not retrieve PCBWay's own price pages (a web search returned only third-party pages). A third-party 2026 small-batch guide (not PCBWay itself) claims PCBWay turnkey setup of about $88-150, component markup of 10-30 % over distributor price, and consignment assembly from $30-50. **None of this is verified.** Treat PCBWay as a quote-by-RFQ fallback, not the baseline.

---

## PART 3 - Parts JLC will not (or cannot) assemble

| Item | Finding | Price / stock |
|---|---|---|
| **Insight SiP ISP1807-LR-RS** (nRF52840 module, LGA-62, 8 x 8 mm) | LCSC/JLC: **C5264268**, Extended, **stock 0** (both JLC and LCSC, 2026-11-18). Digikey US page (via search snippet, not fetched): $12.48, 9,390 in stock. Digikey DE/ES/NL pages: 0 in stock, about 4 weeks, ~EUR 8.7-9.1 at 500-1,000. Mouser: **UNVERIFIED** (Mouser refused automated access). Reseller Ebee: $13.05 at 50+, RFQ. | LCSC $11.27 @1, $10.98 @10. Eval boards: ISP1807-LR-TB C17557202 (presale, $116 @1). |
| **KYOCERA AVX 709155001610004** SMD spring contact | LCSC **C6700681**, listed as beryllium copper gold "Button and strip battery connector", Extended | stock **90**; $0.1436 @5, $0.14 @50, $0.1353 @500. Your Digikey figure (478-8741-2-ND, about $0.34 qty 1) not re-checked. LCSC is cheaper. Check footprint equality before use. |
| **Hirose FH12-4S-0.5SH(55)** FPC connector | **LCSC C-number not found** (no 4-pin entry located). Neighbours exist: 6S C202118, 8S C597995, 10S C506791, 22S C597981, 24S C202112 (stock/price on those not checked). Possible LCSC substitute: HCTL **XW05202-040R-00 C2906108** (4P, 0.5 mm, 0.3 mm FFC, bottom contact, flip-lock, E, stock 12.7 k, $0.1121 @10). Footprint compatibility with FH12 **UNVERIFIED**. | |
| **Qi RX coil, flex, 17-18 mm OD, 6-8 uH** | **No verified coil in this size.** Closest verified parts: Wuerth 760308103206 (7.5 uH, 340 mR): LCSC **C5525402**, $12.83 @10, stock 0; Digikey about EUR 8.17 @1 falling to EUR 4.75 @432 (search snippet). Wuerth 760308103211 (7.3 uH, 200 mR) LCSC C7193782, $10.31, stock 0; Digikey EUR 7.33, 26-week lead. Wuerth 760308102207 (8 uH, 60 mR) LCSC C5543414, $10.49, stock 0. TDK WR202010-18M8-SM (10.68 uH) C3606554, $1.11, stock 0; TDK WR222230-26M8-G (27 uH) C3606555, $3.77, stock 80. Cheap CND-tek YX-A11 series at LCSC ($0.40-0.62, stock 79-357) are 6.3 uH **transmitter** coils, not receivers. Outer diameters of the Wuerth and TDK parts **UNVERIFIED** (not shown in listings), so I cannot confirm any fits 17-18 mm. No AliExpress listing verified. | |
| **3.7 V LiPo, about 16 x 17 x 3 mm or 302020 class with PCM** | **Nothing verified.** Search did not surface a 302020 cell with PCM on AliExpress or LCSC. Seen elsewhere: Electrokit 3.7 V 40 mAh pouch cell (product page electrokit.com/en/battery-lipo-3.7v-40mah-bec; price and PCM **UNVERIFIED**); Core Electronics 120 mAh at $5.65 incl. GST (likely AUD); Kiwi Electronics 150 mAh. Retail price benchmark only. | **UNVERIFIED** |
| **6 mm diameter 2-phase stepper with gearbox** | **No AliExpress listing verified.** Retail (not AliExpress): Fruugo 6 mm planetary-gear stepper linear actuator, 30 mm stroke, $19.95 + $7.99 shipping (US site); VXB 6 mm planetary gear stepper $48.95 (price inconsistent on the page). eBay listings at $0.99-3.25 are 6 mm steppers with a lead screw and **no gearbox**. | **UNVERIFIED** |

---

## Top findings

1. **Economic PCBA cannot place the 0.4 mm WLCSP/DSBGA parts (BQ25120A, TPS22916, likely BQ51003), and it is single-sided only.** Those parts force Standard PCBA, which costs about $140+ more per run (setup, stencil, per-part feeder, fixtures) and needs a 70 x 70 mm panel. The BQ25120A also has only 4 pcs in JLC stock at $6.25.
2. **Per-run cost is driven by Extended parts, not PCBs.** The bare 4-layer board is $8-25 for 5 pcs. Each Extended type costs $3.07 on Economic. About 22 types cost about $65, more than the board, the setup and the stencil combined. Use the Basic substitutions in Part 1 where the circuit allows.
3. **Two parts have no clean source.** (a) No stocked C0G 100 nF (or 22/47 nF) in 0805/0603/0402 exists at JLC; only 1206 C0G, so the Qi series cap needs a bigger part or consigned parts. (b) No SMD buzzer or tact switch near 1.0 mm exists at JLC: thinnest buzzers are 1.8-1.9 mm, thinnest tact switch 1.5-1.6 mm. Also: via-in-pad or 0.2 mm vias (needed for 0.4 mm WLCSP fan-out) add about $20-73 per order on 4-layer, and ISP1807 is out of stock at JLC/LCSC (Digikey US lists stock).
