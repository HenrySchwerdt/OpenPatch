> TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md). Bench sample, never to be worn.

# Cost per iteration (JLCPCB primary, PCBWay secondary)

Prices from `research.md` (JLC quote page / parts API / fee pages, 2026-11-18). **UNVERIFIED** items are marked; the JLC "Special Offer"
prices and fees change often, re-quote before ordering. USD, German import VAT 19 % included where stated.

## What the design forces

| Design fact | Consequence |
|---|---|
| Hall sensors, FPC connector, battery contacts and 0402 passives sit on the **bottom** side (mechanical layout) | needs **two-sided placement = JLC Standard PCBA** (Economic is single-sided only): +$100-140 per run vs Economic |
| Board 17.1 x 29 mm | Standard PCBA needs panel/rails (min 70 x 70 mm) -> "Panel by JLCPCB"; how many panel sites are populated is **UNVERIFIED** (ask JLC; parts cost x sites if all populated) |
| ISP1807 LGA: inner pads need via-in-pad | 0.2 mm via, epoxy-filled + capped: **$81.26** for 5 PCBs vs $24.80 base (measured on quote page) |
| 4-layer thickness at JLC | 0.6 mm is greyed out for 4-layer; cheapest selectable is **0.8 mm with no price difference to 1.6 mm** (measured). **Height impact: +0.2 mm** vs the 0.6 mm in the mechanical stack (components under the coil lose 0.2 mm: 1.4 -> 1.2 mm; lid/coil clearance must be re-checked by mechanical) |
| 0.4 mm WCSP parts (BQ25120A, BQ51003, TPS22916) | removed (Standard could place them but inner balls need via-in-pad/HDI; BQ25120A stock 4 pcs) |

## Per-iteration estimate: 5 bare boards, 2 assembled (Standard, two-sided)

| Line | USD |
|---|---|
| 5 PCBs, 4L 0.8 mm, ENIG, 0.2 mm vias epoxy-filled and capped | 81.3 |
| Setup (two-sided) | 51.1 |
| Stencil (two-sided) | 16.4 |
| Feeder loading, 37 part types x $1.53 (Basic and Extended) | 56.6 |
| Fixtures 2 x $8.21 | 16.4 |
| Joints (about 330 x 2 boards), packing | about 2 |
| X-ray (QFN/LGA parts, per part) | about 10 |
| Parts, 2 boards (about $12 per board at q10 prices; q2 tier higher) | about 28 |
| **Subtotal JLC** | **about 262** |
| Shipping (UPS, estimate; Germany price UNVERIFIED) | 30 |
| German import VAT 19 % on subtotal + shipping | about 56 |
| EU temporary customs duty (about EUR 3 per HS line, 2-3 lines) | about 10 |
| **Total JLC order** | **about $360** |
| Parts JLC cannot supply (below) for 2 boards | about 60 |
| **Total per monthly iteration** | **about $420** (2 assembled boards) |

PCB-only variant (5 bare boards ENIG + epoxy vias, no assembly): about $81 + shipping + VAT = about $140. Not useful without assembly (no soldering iron rule).

## Cheapest order configuration (and what it costs in the design)

1. **Standard PCBA, two-sided, panel by JLCPCB**, FR4 TG135, 4 layers, **0.8 mm**, ENIG (needed for the 0.4 mm pads/via-in-pad), 1 oz outer / 0.5 oz inner, min via 0.2 mm, via covering "epoxy filled and capped", green mask, quantity 5, assembly qty 2.
2. Biggest levers: (a) go **single-sided** to use Economic PCBA (about $100-140 less, 0.5 mm min BGA pitch is irrelevant now) - needs the mechanical agent to move the Hall sensors/battery contacts or accept hand placement of the bottom parts; (b) cut part types (each costs $1.53, Extended also hits Economic at $3.07): 37 types now, about 12 are Extended; (c) skip epoxy vias by moving the ISP1807 inner-pad signals to outer pads (saves about $56 per run but changes the pin map and still needs 0.2 mm vias, see ORDER-jlcpcb.md); (d) HASL instead of ENIG saves about $11-17 but the 0.4 mm pitch pads/via-in-pad need ENIG.
3. Per-iteration target "every month": about $420 per run for 2 assembled boards (about $210 per board).

## Parts not assembled by JLC (sourcing)

| Item | MPN | Source | Price | Status |
|---|---|---|---|---|
| BLE module | Insight SiP ISP1807-LR-RS | LCSC C5264268 (stock 0, JLC consignment), Digikey (about $12.5, stock varies, US page 9,390), Mouser UNVERIFIED | about $12.5 each | consign to JLC (they accept customer parts: UNVERIFIED fee), LGA cannot be hand-soldered |
| Battery spring contact (verified-height candidate) | KYOCERA AVX 709155001610004 (Stript 9155, nominal 1.00 mm, operating range 0.75-1.25 mm, 3 A, gold) | LCSC C6700681 ($0.14, stock 90), Digikey 478-8741-2-ND ($0.34 qty 1) | about $0.15-0.34 | **footprint/size not compatible with the layout**: contact is about 2.7 mm wide, land pattern is only in the AVX sales drawing (not retrievable); layout.json has 1.5 x 1.2 mm pads at 1.9 mm pitch. Gap in the stack is 0.55 mm (below the 0.75 mm minimum). **Contact part still open** |
| Motor FPC connector | Hirose FH12-4S-0.5SH(55), height 1.0 mm | not on LCSC (4-pin); substitute HCTL XW05202-040R-00 C2906108 UNVERIFIED | about $0.5 | consigned / substitute needs footprint check |
| Qi RX coil | Wuerth 760308103206 (7.5 uH, 340 mR) LCSC C5525402 / Digikey about EUR 8 qty 1 | stock 0 at LCSC | $10-13 | diameter vs 17.6 mm not verified |
| LiPo cell with PCM | none verified for 17-26 mAh class | AliExpress / Electrokit 40 mAh | about $3-6 | UNVERIFIED |
| Motor Ø6 mm planetary-gear stepper | Zhaowei ZWBPD006006 (mechanical/parts.md) | AliExpress | $10-25 | UNVERIFIED price |

## PCBWay (secondary)

PCBWay prices were not retrievable (see research.md 2h). Third-party reports: turnkey setup about $88-150, component markup 10-30 %. For comparable
"4L 0.8-1.0 mm ENIG, epoxy-filled vias, two-sided assembly, 2 pcs" expect roughly $300-450 before shipping; treat as unverified.
Files for PCBWay are in `pcbway/` (Gerber zip, BOM with MPN/manufacturer, CPL).
