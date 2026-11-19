# Motor selection (O6 mm geared micro stepper) - research 2026-11-19

BENCH TEST PROJECT, water only, never on a person. Status tags: [V] read from datasheet/vendor page, [D] derived, [?] unverified.

Formula: U/step = 0.35 mm / (steps_per_rev x ratio) x 74.6 / 10. Target 0.008 ... 0.03 U/step.

## Findings that change the current pick
* Zhaowei PD006006 datasheet (https://www.zwgearbox.com/uploads/2608/pd006006-en.pdf, read as image): 1-stage ratios are **4.8 (-5) and 6.43 (-6)**, not 5:1. Plastic gearbox, 250 gf.cm rated / 600 peak, efficiency 85 %, backlash <= 3 deg, 9.7 mm gearbox, 23.7 mm overall. Motor "coreless OR stepper (optional)", 3-12 V, 100 mA max. The datasheet gives **no step angle, resistance, shaft diameter or flat**; drawing shows 2 solder tabs per side (4 tabs) at the tail [V drawing, dimensions L3/L4 unreadable].
* Many Ebay/Fruugo "6 mm planetary stepper" items are lead-screw slider actuators (30 mm stroke), not gearheads. Not usable.
* No Digikey/Mouser/Conrad/Pololu listing of a O6 geared stepper found. Faulhaber ADM0620 + 06/1: no price/stock found anywhere (quote only, im-tek returns 403). Treat as reference only.

## Candidates

| | A: NFP-608-26.45-SGM | B: Zhaowei ZWBPD006006-6 | C: NFP-608-136-SGM (rejected) |
|---|---|---|---|
| Link | https://nfpshop.com/product/6mm-micro-dc-step-gear-motor-16mm-type-model-nfp-608-26-45-sgm (same item: precisionminidrives.com) | https://www.zwgearbox.com/stepper-motor/pd6mm-stepper-gear-motor | https://nfpshop.com/product/6mm-micro-stepper-gear-motor-model-nfp-608-136-sgm |
| Price | $6.60 (1-9), $5.40 (10+) [V]; shipping DE not stated, DHL/FedEx 3-5 d from HK, ships 1-3 d after payment; import VAT/duty [?] | enquiry only; AliExpress/Taobao $10-25 [?]; no AliExpress listing confirmed | $7.80 [V] |
| MOQ / stock | none stated; page shows "In stock" [V] | MOQ [?] | as A |
| Step angle | 18 deg = 20 steps/rev [V], 2-2 phase, bipolar | [?] (assume 20) | 18 deg [V] |
| Ratio | 26.45, 2-stage [V] | 6.43 exact [V] | 136.02, 3-stage [V] |
| Length | "16 mm type" [?]; no drawing for this variant (136 variant: body 17.45 mm, shaft protrudes ~2.5 mm) | 23.7 mm incl. shaft [V] | 17.45 mm body [V] |
| Shaft | 2-stage [?]; sibling -136 has O2.0 with 1.5 flat [V] | [?] | O2.0, 1.5 flat [V] |
| Terminals | JST 1.25 mm connector + 200 mm lead (page text) [V]; sibling drawing shows 4 solder pins, 1.2 mm pitch - CONFLICT, ask | solder tabs [V drawing] | as A |
| Electrical | 4.8 V, 26.5 ohm +/-7 % (=0.18 A) [V]; pull-out 1.6 gf.cm @500 pps | 3-12 V, 100 mA [V]; ohm [?] | same as A |
| Output torque | [D] ~ 1.6 gf.cm x 26.45 x 0.64 = ~27 gf.cm (2.7 mN.m) | 250 gf.cm gearbox rating [V]; motor-limited [?] | high |
| U/step | **0.00494** (below target) | **0.0203** (in range); if 4.8: 0.0272 | 0.00096 |
| Datasheet | none (product page + outline image only) | PDF, incomplete | none |

Speed check for A: 100 U = 38.3 screw turns x 529 steps = 20 300 steps = 41 s @500 pps, 20 s @1000 pps (OK for bench). C would need 104k steps: too slow.

## Recommendation
* **Primary: A, NFP-608-26.45-SGM** - the only candidate that is demonstrably orderable by a private buyer today, with step angle, resistance, voltage and connector published. Costs: 5 pcs ~ $27 + shipping + VAT. Resolution 0.0049 U/step is finer than target (min pulse 0.05 U = ~10 steps, fine); bolus speed adequate. Before ordering email info@nfpmotor.com for the outline drawing of the 26.45 variant (length, shaft O/flat, terminal type) and ask whether a ~6-12:1 variant exists.
* **Backup: B, Zhaowei -6 (6.43:1)** - best geometry/resolution (0.0203 U/step) but unverified orderability, step angle and terminals; enquire at sales@zwgearbox.com for stepper version, step angle, resistance, price/MOQ, sample qty 2-10.
* Premium reference: Faulhaber ADM0620 + 06/1 16:1 (0.0082 U/step), quote only.

Design impact: spec/parts.md ratio "5:1" is wrong (4.8 or 6.43). Pinion/gear bore must follow the verified shaft O (2.0 with flat for NFP sibling).
