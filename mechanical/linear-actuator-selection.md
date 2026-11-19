# Linear actuator selection (single off-the-shelf micro linear stepper)

Bench test project only. Not a medical device, never for on-body use (see `DISCLAIMER.md`).

Research date: 2026-11-19. Status legend: **CONFIRMED** = read by me from a fetched page or from a datasheet/drawing image I looked at; **SNIPPET** = only seen in a search-result summary, page not readable by me; **COMPUTED** = my arithmetic from confirmed inputs (assumptions stated); **UNVERIFIED** = not seen.

Given: reservoir area 74.6 mm^2, 1 U = 10 ul, so **1 mm of plunger travel = 7.46 U**. Strokes 9.4 / 13.4 / 26.8 mm (70/100/200 U).
Resolution formula: U/full step = lead / (steps_per_rev x ratio) x 7.46. Target <= 0.03 U per full step. Force: F = 2 pi eta T_out / lead.

## 1. Bottom line

No single catalogue part met everything. What I found:

| Rank | Part | Orderable (private, DE) | Full drawing | Force >= 5 N | <= 0.03 U/step | Fits envelope | No-solder | Integrated screw+slider |
|---|---|---|---|---|---|---|---|---|
| **Primary** | NFP-0620-531-MG (Ø6 stepper + 4-stage planetary, 530.842:1) **plus the repo's existing M1.6 x 0.35 leadscrew** | Yes, nfpshop.com, 25 USD each (shipping to DE not confirmed) | **Yes** (dimensioned outline) | **Yes**, COMPUTED 300 N class (screw-limited) | **Yes**, 0.00025 U/step | Yes (Ø6, 20.8 mm body) | Not confirmed (drawing shows 4 solder-type tabs; datasheet test text mentions an "FPC") | **No** (rotary output, Ø1.5 D-shaft) |
| **Backup** | Generic "6 mm planetary-gear stepper + Ø2.7 mm screw slider, stroke 30 mm" (Amazon / VXB / AliExpress, brands GUIFANG, Soiveilarh and others) | Yes (Amazon US, VXB, AliExpress); DE shipping not confirmed | **No** (no dimensioned drawing found) | **UNVERIFIED** (no thrust given) | Probably close: 0.0386 U/step, COMPUTED, slightly over target, assumes 1 pulse = 1 full step | Probably (30 mm stroke, Ø6 motor); lengths unverified | No (bare wire leads, 100 mm) | **Yes** |
| Rejected | Vic-Tech VSM0632 (Ø6 direct-drive stepper + M1.7 x 0.3 screw slider with bracket) | Yes (factory, MOQ 1, quote) | **Yes** | **No**, 0.44 N pull-out max | **No**, 0.112 U/step | Yes | FPC/PCB customizable | Yes |
| Not usable | Faulhaber 06L...SL/HL geared linear actuator | Not for private buyers: "request article", price on request, motor must be combined | Partly | 12 N continuous (CONFIRMED on the eshop page) | Depends on motor | Yes | n/a | Yes |
| Not usable | ZhaoWei 6 mm screw drive (stepper + planetary) | MOQ 2000-3000 (Made-in-China), samples possible | No | 9.8 N at 854:1 (SNIPPET) | n/a | n/a | n/a | Yes |

**Closest to the requirement:** the NFP-0620-531-MG motor/gearhead as the *drive*, with the leadscrew and nut kept in their own lane as already specified in `spec/design-parameters.md`. What is missing: an integrated screw+slider+frame and a confirmed no-solder connector. The only integrated Ø6 planetary slider that is orderable (backup) has no drawing and no force figure, so it needs to be bought (2 pcs) and measured before it can be designed in.

## 2. Primary: NFP-0620-531-MG

- Product page (CONFIRMED): https://nfpshop.com/product/6mm-micro-dc-stepper-gear-motor-16mm-type-model-nfp-0620-531-mg
- Datasheet PDF (CONFIRMED, I read all pages of the outline drawing, tables and torque curve): https://nfpshop.com/wp-content/uploads/2026/04/DATASHEET-NFP-0620-531-MG.pdf
- Price: 25.00 USD (product page). Shipping: DHL/FedEx 3-5 days, free above 150 USD per the product page; cost for DE not shown. **Estimate (not a source figure):** 2 pcs about 50 USD + roughly 25-40 USD shipping, plus German import VAT/possible duty.
- Order quantity: quantity selector starts at 1 (product page).

### Dimensions (read from the datasheet outline drawing, unit mm)

| Item | Value | Source |
|---|---|---|
| Motor / gearbox diameter | Ø6 +-0.05 | datasheet p.1 drawing |
| Motor (rear) section length | 7.65 | drawing dimension line |
| Gearbox section length | 13.15 +-0.3 | drawing |
| Body total (motor + gearbox) | 20.8 (COMPUTED 7.65 + 13.15) | drawing |
| Output shaft | length 9.65 +-0.3 from gearbox face, Ø1.5, D-flat (reads 1.1 across flat); boss 3 +-0.2 long; flat length 1.67 +-0.05 | drawing (small print, re-check at 2x zoom before milling) |
| Overall length with shaft | about 30.45 (COMPUTED) | |
| Rear terminal tab | width 5.4 +-0.1 across, 4 terminals A+ A- B+ B-, 3.55 long | drawing |
| Weight | 5 g total, 1.1 g motor only | datasheet p.1-2 |

### Electrical and mechanical

| Item | Value | Source |
|---|---|---|
| Type, step angle | 2-phase stepper, 18 deg (= 20 full steps/rev) | datasheet p.2 |
| Rated voltage / range | 5.0 V / 3.0-7.0 V, constant-voltage drive, 2-2 phase excitation | datasheet p.1-2 |
| Phase resistance | 15 ohm +-8 % (so about 0.33 A at 5 V, COMPUTED) | datasheet p.2 |
| Rated pulse rate | 500-1000 pps | datasheet p.2 |
| Gearbox | 4 stages, ratio **530.842:1**, 0.8 efficiency per stage, backlash <= 4 deg, "minimum load" >= 900 gf.cm at 2000 pps | datasheet p.1 |
| Motor torque curve | about 8 gf.cm at 200 pps falling to about 6.3 gf.cm at 1000 pps and 3.4 gf.cm at 2800 pps (upper trace; the lower dashed trace is not labelled) | datasheet p.2 graph |
| Life test | >= 50,000 cycles at 900 gf.cm, 500-1000 pps | datasheet p.4 |
| Connector | datasheet test method says "Connect the product FPC ..." but the outline shows 4 solder-type tabs and no FPC dimensions. **Ask NFP (info@nfpmotor.com, address printed on the datasheet) for an FPC-tail version** | datasheet p.1, p.3 |

### Derived numbers for this project (COMPUTED)

Assumes the leadscrew is the repo's M1.6 x 0.35 (spec, direct 1:1 on the Ø1.5 shaft via sleeve/Loctite or the existing gear coupling from `mechanical/gear-selection.md`).

- Steps per output rev: 20 x 530.842 = 10,617.
- Travel per full step: 0.35 / 10,617 = 3.30e-5 mm, i.e. **2.5e-4 U per full step** (120x finer than the 0.03 U target; no microstepping needed).
- Full 100 U stroke (13.4 mm) = 406,000 full steps; at 1000 pps that is 406 s. Max delivery speed at 1000 pps: 0.033 mm/s = 0.25 U/s (a 10 U bolus in about 41 s).
- Axial force: gearbox "minimum load" 900 gf.cm = 88 mN.m; with screw efficiency eta = 0.2 (conservative guess for a small thread) F = 2 pi x 0.2 x 88e-3 / 0.35e-3 = about 317 N. Even at 10 % of the rated torque and eta 0.2 the thrust is 30 N, so the 5-10 N requirement is met with a large margin; the limit becomes screw/nut/gear strength, not the motor. A thrust limiter in firmware or a slip clutch is advisable.
- Envelope: Ø6, body 20.8 mm. Fits the 8.5 mm pod height with the screw lane beside it. The 26.8 mm stroke for 200 U has to come from the screw/nut lane (the motor does not grow with stroke).

## 3. Backup: generic Ø6 planetary stepper + screw slider (30 mm stroke)

The same listing text appears under several names: GUIFANG https://www.amazon.com/GUIFANG-Precision-Planetary-Stepper-Stepping/dp/B0FLQ6NR1C, Soiveilarh https://www.amazon.com/Soiveilarh-Precision-Planetary-Stepper-Stepping/dp/B0GZYJTJZH, Amazon https://www.amazon.com/Precision-Planetary-Stepper-2-Phase-Stepping/dp/B0GKVQBPRJ, AliExpress https://www.aliexpress.us/item/3256806989595160.html, VXB https://vxb.com/products/tiny-6mm-precision-planetary-stepper-motor-with-mi.

Amazon and AliExpress returned 503/login redirects to my fetcher, so the numbers below come from the VXB page (CONFIRMED, fetched) and from search-result summaries of the Amazon listings (SNIPPET).

| Item | Value | Status / source |
|---|---|---|
| Motor | Ø6 mm 2-phase 4-wire planetary-geared stepper, motor body about 6 x 7.5 mm per one listing | SNIPPET (Amazon) |
| Gear ratio | not stated | UNVERIFIED (an eBay listing of a similar Ø6 part says 1:47, 12 mm, 14 ohm, 18 deg; not proven the same part) |
| Screw | Ø2.7 mm, tube Ø2.5 mm, lead-screw length 100 mm, pitch/lead not stated | VXB page, CONFIRMED |
| Stroke | about 30 mm slider travel, 5800 pulses for full travel | VXB page |
| Electrical | 5 V, 0.32 A, about 13.2 ohm (one Amazon.ca listing says 14 ohm), 9 g | VXB page; Amazon.ca SNIPPET |
| Leads | bare wires 100 mm | VXB/Amazon |
| Price | VXB shows 39.99 USD / 80.00 USD (labels look swapped); Amazon and AliExpress prices not read | VXB page |
| Resolution | 30 / 5800 = 0.00517 mm per pulse = **0.0386 U per pulse** (assumes pulse = full step, which is not stated) | COMPUTED |
| Force | **not given by any seller.** The vxb.com page text that mentions a 0.5 N.m torque / 3 kg load figure appears in search summaries only and is not credible for a Ø2.7 screw | UNVERIFIED |
| Drawing | none; stroke 30 mm is below the 26.8 mm + margin only in the sense that 30 mm is enough for 200 U, but overall length is unknown | UNVERIFIED |

Use: buy 2 pcs, measure dimensions with calipers, measure thrust with a luggage scale or hanging-weight test, then decide. The listing is a hobby part with no datasheet, so the project must not depend on it without that measurement.

## 4. Rejected or unusable candidates (with the evidence)

### Vic-Tech VSM0632 (Ø6 direct-drive micro slider with bracket)
Product page (CONFIRMED): https://www.vic-motor.com/6mm-micro-slider-linear-stepper-motor-screw-motor-with-bracket-stepper-motor-2-product/ ; drawings (CONFIRMED, I read both): https://www.vic-motor.com/uploads/0141d2e7.png and https://www.vic-motor.com/uploads/83bd95b2.png

- Ø6 x 15 mm motor, 18 deg step (20 steps/rev), M1.7 screw, lead 0.3 mm, 0.015 mm/step, 4.6 V, 40 ohm, 100 mA/phase, bare needle output, FPC/PCB customizable, MOQ none, sample lead time 3 days in stock / 15 days otherwise, price on inquiry.
- Drawing: bracket about 7.6 mm wide, 6.0 mm max motor diameter, screw thread length 6.70 mm (only about 6.7 mm of travel), 2 x Ø1.50 mounting holes, nut Ø3.6, 4 solder pins.
- **Fails force:** pull-out thrust graph reads 45 g at 200 pps down to 12 g at 1200 pps (0.12-0.44 N). **Fails resolution:** 0.015 mm x 7.46 = 0.112 U/step. **Fails stroke:** about 6.7 mm. Useful only as a reference for the FPC option and the bracket geometry.

### Faulhaber 06L...SL / HL geared linear actuator (Ø6)
Eshop page (CONFIRMED): https://eshop.faulhaber.com/en/06L-...-SL/Serie-06L-...-SL . Ratios 4:1 to 1024:1, "3x0.5 mm" proprietary screw, 12 N continuous (16 N peak static), 20.6 mm length without motor, 6 mm diameter, standard screw length 50 mm (max 100 mm), mass 5.8 g. The page says it can only be bought as a combination with a motor, delivery "on request", no price. Lead per revolution is not stated on the page (3x0.5 could be thread pitch 0.5, UNVERIFIED). I did not find a Ø6 stepper in the Faulhaber portfolio from the pages read. Not a private-buyer route; keep as a design reference (the Micromo/Faulhaber integrated gearhead + screw concept is exactly what we want).

### ZhaoWei (Shenzhen) Ø6 stepper gear motors and screw drive
- Catalog: https://www.zwgearbox.com/stepper-motor ; 6 mm PD/MD stepper gear motors, ratio 4.8-1708, max continuous torque 0.025 / 0.033 N.m, 3 V (CONFIRMED on page).
- Screw drive: continuous force 1.8 / 2.8 / 3.8 / 9.8 N for 1-4 stages, 9.8 N at ratio 854, max feed 0.2 mm/s, radial 5 N max (SNIPPET from directindustry PDF catalog, page returned 403): https://pdf.directindustry.com/pdf/shenzhen-zhaowei-machinery-electronics-co-lt/linear-actuator-motor-6mm-screw-drive/217841-922698.html
- Made-in-China listings state MOQ 2000-3000 pieces (CONFIRMED): https://zwgearbox.en.made-in-china.com/product/nFPGuRVdazca/China-6mm-Micro-Stepper-Gear-Motor-Linear-Screw-Thread-Shaft-for-TV-Lifting-Motor-Small.html . Not orderable in qty 2-10 without a special agreement; a sample request via https://www.zwgearbox.com/customisation is possible but unproven.

### Other leads checked
- Precision Mini Drives / NFP 6 mm family (CONFIRMED list): https://precisionminidrives.com/6mm-planetary-gear-motor . Only NFP-608-26.45-SGM (6.60 USD) and NFP-0620-531-MG are stepper types. The screw variant (NFP-612-266-MG-M3, 33 USD, M3 brass screw 105 mm) is a **brushed DC** motor, not a stepper, so it cannot be positioned open-loop. https://precisionminidrives.com/product/6mm-dc-gear-metal-motor-with-brass-threaded-screw-23mm-type-model-nfp-612-266-mg-m3
- NFP-SM1519/1530/1545 linear steppers (M3 x 0.5 screw, 19-45 mm travel): too large (Ø15+, about 30 g), not Ø6.5.
- Moons' B series (6 mm screw) and PM linear actuators (20-35 mm): frames too large; not fetched in full (PDF over the 10 MB fetch limit).
- Nidec, Mitsumi/Minebea, Shicoh, Sanyo/Kinmore, Seiko micro-stepper lens drives, Digikey/Mouser/LCSC, Pololu: searched; no Ø6.5 mm lens-type linear stepper with a public datasheet and small-quantity sale found. Not conclusive: these catalogs are mostly OEM-only.

## 5. Gaps and next actions

1. Email NFP (info@nfpmotor.com): FPC-tail option for NFP-0620-531-MG (pad pitch, pinout), shipping cost to Germany, and whether a ratio of about 50-150:1 (lower reduction, higher speed) is available for the same body; ask for the rated *axial* load of the output shaft bearing (not given in the datasheet).
2. Ask Vic-Tech whether a geared Ø6 slider (e.g. with planetary stage and 30 mm screw) exists; their VSM06 motor core plus gearbox would match the backup class but with a real drawing.
3. Buy 2 pcs of the generic 30 mm slider as a measurement sample; record thrust and exact lengths here.
4. The current design (`spec/design-parameters.md`) uses a SMA ratchet drive on an M1.6 x 0.35 screw; the geared-stepper route is a **bench alternative**, so any switch must go through the spec file first.
5. Keep the hardware interlock (motor only with MCU enable and watchdog) in any stepper variant.
