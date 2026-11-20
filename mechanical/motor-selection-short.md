# Shorter micro geared stepper - search (2026-11-19)

BENCH TEST PROJECT, water only, never on a person. Tags: [V] read from datasheet/drawing/page, [D] derived by me, VERIFY = not readable / not confirmed. Nothing here is a quote or an order.

## 1. Requirement maths

* Rod thrust F = 2*pi * T_out * 0.2 / 0.35 mm  ->  F >= 7 N needs **T_out >= 1.95 mN.m (19.9 gf.cm)** at the bevel/rod input [D].
* U/step = 0.35 / (steps x ratio) x 10.626. With 20 steps/rev, U/step <= 0.01 needs **ratio >= 18.6** [D].
* Consequence: ratio >= 18.6 needs at least a 2-stage planetary at O6 (1-stage = 4.8 ... 6.4 only), unless the missing ratio is made up in the pod (bevel/spur 3-4:1).
* Direct drive (no gearbox): pull-out 1.0 gf.cm (VSM0613) ... 2.5 gf.cm (Faulhaber DM0620, 0.25 mNm holding) gives F = 0.35 ... 0.9 N with M1.6x0.35. To reach 7 N the lead would have to be about 0.03 mm (a finer screw does not exist at this size). **Direct drive rejected.**
* Baseline, NFP-608-26.45-SGM [V drawing, https://nfpshop.com/wp-content/uploads/2025/11/nidec-micro-dc-motor-NFP-608-26-outline-drawing.jpg]: motor 8.0, gearbox 8.1 (2-stage), body 15.1, shaft O2.0 (D-flat 1.5 mm, 2.5 mm protrusion), 4 solder pins 1.2 mm pitch. U/step = 0.00703 [D]. Thrust 8.6 N (given).

## 2. Key finding

At O6 the **motor alone is 7.0-9.5 mm** and a **2-stage gearbox is ~8.1 mm (metal, NFP) to 12.1 mm (plastic, Zhaowei)**. Per-stage pitch on the NFP drawings is ~2.5 mm [D: NFP-0620-531 4-stage 13.15 mm vs NFP-608 2-stage 8.1 mm]. So the current part (15.1 mm) is already the shortest verifiable O6 unit with ratio >= 18.6. **No purchasable O6 geared stepper with body <= 11 mm and ratio >= 18.6 was found.** The 11 mm target is only reachable at O5/O4 (thrust problems) or by splitting the reduction into the pod.

## 3. Candidates

| # | Candidate | Link | Price / stock | O x body (motor / gearbox) / shaft | Steps | Ratio | Elec | Torque | Thrust [D] | U/step [D] | Connection | Drawing |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | **NFP-608-26.45-SGM** (current) | https://nfpshop.com/product/6mm-micro-dc-step-gear-motor-16mm-type-model-nfp-608-26-45-sgm | $6.60 qty 1-9, $5.40 qty 10+, in stock (page) | O6.0 x 15.1 (8.0 / 8.1); shaft O2.0 D1.5, 2.5 prot. | 20 | 26.45 | 4.8 V, 26.5 ohm | pull-out 1.6 gf.cm @500 pps; ~27 gf.cm out [D] | 8.6 N (given) | 0.00703 | 4 solder pins 1.2 mm (drawing) | yes [V] |
| 1 | NFP-0620-531-MG | https://nfpshop.com/product/6mm-micro-dc-stepper-gear-motor-16mm-type-model-nfp-0620-531-mg | $25.00, stock not stated | O6.0 x **20.8** (7.65 / 13.15 incl. 3 mm boss); shaft O1.5 (tip O1.1), 9.65 prot. | 20 (18 deg) | 530.842 (4-stage metal) | 5 V (3-7), 15 ohm +-8 %, 2-2 phase | >= 900 gf.cm @2000 pps | far above need | 0.00035 (100 U = 285k steps, too slow) | FPC | yes [V] https://nfpshop.com/wp-content/uploads/2026/04/DATASHEET-NFP-0620-531-MG.pdf |
| 2 | NFP 0620 motor with 2-stage gearbox (not listed) | enquiry info@nfpmotor.com | - | 7.65 + ~8.1 = ~15.75 [D]; saves nothing vs #0 | 20 | ~23-30 | as #1 | - | - | ~0.007-0.008 | FPC | VERIFY, custom |
| 3 | Zhaowei ZWBPD006006-23 (2-stage) | https://www.zwgearbox.com/stepper-motor/pd6mm-stepper-gear-motor ; https://www.zwgearbox.com/uploads/2608/pd006006-en.pdf | enquiry only; MOQ VERIFY | O6 x gearbox **12.1**, overall 26.1 (incl. shaft); motor length VERIFY | not stated (assume 20, VERIFY) | 23.04 (also 30.86, 41.33) | 3-12 V, 100 mA max; ohm VERIFY | gearbox 250 gf.cm rated | motor-limited, probably OK [D] | 0.0081 | solder tabs | partial (dims unreadable) |
| 4 | Zhaowei -5/-6 1-stage | same page | enquiry | gearbox 9.7, overall 23.7 | VERIFY | 4.8 / 6.43 | as #3 | - | OK only with extra 3-4:1 in pod | 0.0387 / 0.0289 | solder tabs | partial |
| 5 | Faulhaber DM0620 + 06/1, 16:1 | https://shop.faulhaber.com/fdm0620-v6-15-06-1-64-1-mg32.html (403 for me); datasheets https://www.faulhaber.com/fileadmin/Import/Media/EN_DM0620_FPS.pdf, https://eshop.faulhaber.com/media/f6/aa/4d/1775629824/EN_06-1_FMM.pdf | price "on request" (eshop: available, delivery on request); private buyer VERIFY | O6 x **21.4** (9.5 motor + 11.9 gearhead) [V]; 64:1 = 24.1; 4:1 = 18.7 | 20 (18 deg) | 16:1 (eff. 80 %) | DM0620-0080: 3 V, 30 ohm; -0130: 2 V, 13.6 ohm | holding 0.25 mNm; ~0.17 mNm @500 pps (curve) | ~7.8 N [D] | 0.0116 (marginal fail); 64:1 = 0.0029 | not stated (cable options) | yes [V]; shaft O1.0 (not O2) |
| 6 | Faulhaber ADM0620 (older) | - | no listing found | 9.3 mm motor (secondary source) | - | - | - | - | - | - | - | - |
| 7 | O5 x 12.1 mm 1:20 planetary stepper (generic; eBay 136696165290, 404215663581; Amazon B0C2TK9LGJ; AliExpress 3256804756573549; flat-shaft variant Amazon B0DG8HZCH2) | pages returned 403/503, data from search snippets only | price, DE shipping VERIFY | **O5 x 12.1** gear motor (slider version 30.4 total) | VERIFY | 1:20 (stated) | 14 ohm (10.2-14.5 in different listings), voltage VERIFY | not stated | est. 2.7-5.7 N [D, assumed 0.5-1 gf.cm motor] - likely < 7 N | 0.0093 | VERIFY | no |
| 8 | O4.25 generic planetary stepper (Amazon.de B0CY2SZ9RJ, eBay.de 388599851749) | listings | VERIFY | length, ratio VERIFY | VERIFY | VERIFY | 14.4 ohm, 5 V | not stated | VERIFY | VERIFY | fragile lead feet | no |
| 9 | Zhaowei ZWBMD003003 / MD004004 (O4) | https://zwgearbox.en.made-in-china.com/product/hXzJtreAbvkO/China-4mm-Small-Stepper-Geared-Motor-with-Planetary-Gearbox.html | US$12.8-16, **MOQ 1000** | O4 x 12.25 (2-stage: 4.75 motor + 7.5 gearbox) | not stated | 25 | 3 V | 2.5 gf.cm out | **0.9 N** [D] | ~0.0075 | - | no |
| 10 | VSM0613 O6 x 7 bare stepper | https://www.vt-motor.com/low-noise-high-quality-3-3v-6mm-micro-stepper-motor-2-phase-4-wire-stepper-motor.html | enquiry, MOQ 1 | O6 x **7.0** motor; shaft O1.0 x 3.1 (D-cut or 9T module 0.2 gear possible) | 20 | gearboxes 2:1 ... 1000:1 offered, lengths not stated | 3.3 V, 12 ohm, 0.2 A | pull-out 1.0 gf.cm @500 pps | direct 0.35 N | - | - | image only |
| 11 | Leobot D6 x H10 bare | https://leobot.net/product/2792 | R 27.48, 18 in stock (South Africa) | O6 x 10, shaft O1 x 4 | - | none | not stated | - | - | - | 4-wire | no |
| 12 | Pololu 26:1 sub-micro 6D x 16L (DC coreless, not stepper) | https://www.pololu.com/product/2357 | - | O6 x 16 | n/a | 26:1 | DC | - | - | not open-loop | - | - |

Not found: Namiki/Nidec, Shicoh, Kinmore datasheets (only marketplace pages), any O6 geared stepper at Digikey/Mouser/Conrad. NFP stepper catalogue pages (https://nfpshop.com/stepper-gear-motor, /stepping-motor) list no O4/O5 and no other O6 geared stepper; NFP-KS-06BY25 (bare O6 stepper, 3.7 V, 11 ohm, $15) is out of stock, no dimensions.

## 4. Pod width effect (length axis only) [D]

| Option | Body length | Change vs 15.1 | Condition |
|---|---|---|---|
| Keep #0 | 15.1 | 0 | - |
| #7 O5 1:20 | 12.1 | **-3.0 mm** | thrust >= 7 N unproven (probably short); shaft/bevel interface must be redone |
| NFP-style 1-stage (~5.6 mm, extrapolated) on 7.65 motor + 3-4:1 spur/bevel in pod | ~13.3 | -1.8 mm | custom gearbox; wheel in pod may break the 8.5 mm height limit |
| #10 7.0 motor + own 2-stage | ~15.1 | ~0 | no real gain |
| #5 Faulhaber | 21.4 | +6.3 mm | worse |

## 5. Recommendation

1. **No drop-in replacement meets all requirements.** NFP-608-26.45 remains the best verified part.
2. **Only real shortening path: O5 x 12.1 mm 1:20 stepper gear motor (#7)**, saving ~3.0 mm pod width. Buy 2 samples for a bench thrust test (water, load cell) before changing CAD. Risks: torque unknown, voltage/steps/shaft unverified, German availability VERIFY.
3. Email info@nfpmotor.com for 1- and 2-stage gearboxes on the 7.65 mm 0620 stepper and any O5 unit; email sales@zwgearbox.com for PD006006-23 step angle, ohm, shaft, sample quantity.
4. Do not pursue direct drive (0.35-0.9 N) or the O4 variants (MOQ 1000 / 0.9 N).
