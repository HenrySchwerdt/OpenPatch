# Shopping list: one complete bench iteration (Rev A)

> **Test project, not a medical device. Never worn or used on a person** (see `DISCLAIMER.md`). Everything below is for a bench build; water (or insulin, **only into containers on a balance**) is the only fluid.
>
> Research date: **2026-11** (retrieval date for all URLs). Prices: **[V]** = seen on a shop page or cached snapshot in 2026-11, **[E]** = estimate (project number or my assumption, replace with the quote), **n/v** = not verified, do not rely on it. Stock and price pages of LCSC, nfpshop and Hirose could not be read live by the research tool, so check every line at checkout. Currency conversion used for totals: **1 EUR = 1.10 USD** (assumption). Shipping, VAT and import duty are listed separately because most shops did not state them.
>
> Part choices and status: `docs/PARTS-LOCK.md`. Cost model: `docs/05-cost-model.md`.

## 0. Blockers before ordering

| # | Blocker | Affects |
|---|---|---|
| 1 | **Gear ratio / layout mismatch** (STATUS handoff): CAD snapshot 18:18 (centre 5.40) vs spec 15:12 (centre 4.05, `mechanical/parts.md` says it does not fit the side-gear layout). Decide first; a mismatch is a 25 % dosing error. The list below carries **both** options (section 2.5). | gears, prints |
| 2 | `mechanical/out/bench/fab/` currently holds only **OP-70** (+ coupon + reservoir-cnc); OP-100/OP-200 prints must be regenerated after the parallel-motor layout is finished (STATUS: mechanics interrupted). The print list is for one size. | JLC3DP |
| 3 | Pod sensor board is not built yet; controller BOM CSV in `electronics/bench/fab/jlcpcb/controller/` still has the 16-pin FH12-16S (C596731) while `parts.json` has the 10-pin FH12-10S (C506791). Regenerate, run DRC, then get the JLCPCB quote. | JLCPCB |
| 4 | No verified source for the duckbill valve (OD <= 3 mm), a diametric Ø2 x 1 magnet and EU stock for medical silicone: these need the sample order (section 4), not the iteration order. | sample order |
| 5 | Motor connector type (PicoBlade vs JST GH) is only known once the first motors arrive; the controller carries both footprints (J5 populated, J6 DNP). | motors |

## 1. Per-iteration order (recurring, about once a month)

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

## 2. Parts for the iteration, bought as packs (stock; see sample order for first purchase)

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

## 3. Programmer / target

| Item | Qty | Price | Link | Notes |
|---|---|---|---|---|
| Nordic **nRF52840-DK** (also dev target) | 1 | **41.37 € [V]** (Mouser DE, 1,424 pcs cached); DigiKey NL 41.60 € excl. VAT | https://www.mouser.de/de/ProductDetail/949-NRF52840-DK | One-time. Includes on-board J-Link; SWD cable to the controller's 2x5 1.27 mm header (J3) needs a 10-pin 1.27 mm ribbon (~3 € [E]) or Tag-Connect TC2030 (J2, DNP). |

## 4. Sample order (PARTS-LOCK "recommended action", before freezing CAD/PCB)

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

## 5. One-time tools (bench)

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

## 6. Totals summary

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
