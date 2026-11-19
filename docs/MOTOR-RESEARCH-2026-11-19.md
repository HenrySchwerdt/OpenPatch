# Motor research: smaller or more space-efficient drive options (2026-11-19)

Scope: OpenPatch is a bench test project, never used on a person, **water only** (CLAUDE.md, decision 2026-11-19). Nothing here is a design release. All web figures were found on 2026-11-19 via web search (secondary snippets, not full datasheets unless stated). Items marked **[UNVERIFIED]** must be confirmed with the manufacturer before any design decision. No part numbers were invented; where no part was found this is stated.

## 1. Requirement, derived

Numbers below are our own calculation (assumptions in brackets).

| Quantity | Value |
|---|---|
| Plunger force target | >= 6 N (2x margin over ~3 N) |
| Resolution | 0.01 U = 0.1 mm^3; area 75-100 mm^2 -> **1.0-1.3 um plunger travel per increment** |
| Screw | M1.6 x 0.35 -> 0.35 mm/rev, so >= ~270-350 increments per screw revolution |
| Torque needed at the screw | F = 2*pi*eta*T/L -> T = F*L/(2*pi*eta). 6 N, L = 0.35 mm, eta = 0.25 (assumed, small screw) -> **~1.3 mN*m** (eta 0.35 -> ~0.95 mN*m) |
| Current drive (as stated) | 20 steps/rev x 26.45 x 1.25 (16:20) = 661 steps/rev -> 0.53 um/step; OK |

Voltage observation: a stepper's torque follows winding **current**, not voltage. The NFP motor (26.5 ohm) draws 160 mA only at >= 4.24 V. On a Li-Po (3.0-4.2 V, minus H-bridge drop) it gets at most ~113 mA at 3.0 V, i.e. up to ~30 % less current and torque at end of discharge; the 4.2 V end is limited by the chopper/current limit, not a problem. Two fixes: (1) a small 5 V boost (cheap, keeps the current motor), or (2) pick a winding that reaches its rated current at <= 3.0 V (low resistance, e.g. the 3 V-rated motors below) with a current-regulating driver. The hardware interlock (motor only with MCU enable and watchdog) stays in every option.

## 2. Candidates found

### 2.1 Micro geared steppers

**Zhaowei 3.4 mm stepper + planetary gearbox, "MD004004" family** (ZWBMD004004-6 / -36 / -216 / -1296). Sources: [zwgearbox.com 4mm stepper page](https://www.zwgearbox.com/stepper-motor/4mm-stepper-motor) (fetched 2026-11-19), [directindustry listing](https://www.directindustry.com/prod/shenzhen-zhaowei-machinery-electronics-co-lt/product-217841-2541846.html), [directindustry datasheet PDF](https://pdf.directindustry.com/pdf/shenzhen-zhaowei-machinery-electronics-co-lt/stepper-gear-motor-datesheet-4mm-md/217841-906807.html) (403 on fetch, snippet only).
- Verified on the vendor page: motor diameter 3.4 mm (page title says 4.3, internally inconsistent), performance data at 3.0 V, 50 mA max, rated voltage 1.5-5 V; overall length (motor + gearbox) 11.78 mm (6:1), 13.27 mm (36:1), 14.77 mm (216:1), 16.32 mm (1296:1); efficiency 85 / 73 / 65 / 58 %; max rated gearbox torque 140 gf*cm (13.7 mN*m), instant 200 or 400 gf*cm (page contradicts itself); backlash <= 3 deg; radial load on output shaft <= 0.3 N; porous bearing. Step count derived: 1000 rpm at 2000 pps at 6:1 -> 20 steps/rev motor.
- **Not found: winding resistance, motor pull-out torque, price, MOQ.** [UNVERIFIED] 3 V / 50 mA implies ~60 ohm.
- Fit with our screw (our calculation): required motor torque = 1.3 mN*m / (ratio x eta) -> 36:1: ~0.05 mN*m (0.5 gf*cm); 216:1: ~0.009 mN*m (0.09 gf*cm). Whether a Ø3.4 motor delivers that is unknown [UNVERIFIED]; the 216:1 stage has the most margin. Gearbox torque limit (13.7 mN*m) is >10x our need. Resolution: 36:1 coaxial -> 720 steps/rev -> 0.49 um; 216:1 -> 4320 steps/rev -> 0.08 um (a 250 mm^3 bolus, ~45 k steps, takes ~45 s at 1 kpps). Direct coaxial drive of the screw possible (no 16:20 pair), total motor length 13-15 mm at Ø3.4.
- Older Zhaowei 4 mm pages disagree (5/25/125/625 ratios, 1.5-5 V, 3 V, 140 or 150 gf*cm), so confirm the exact model with Zhaowei in writing. Search also returned the DC "ZWBPD004004" plastic gearbox; I did not find a stepper datasheet under the name "ZWBPD004" [UNVERIFIED mapping].
- Zhaowei 6 mm series (PD/MD006006) also exists ([listing](https://www.directindustry.com/prod/shenzhen-zhaowei-machinery-electronics-co-lt/product-217841-2353428.html)), gearbox 9.7-16.9 mm, 250-600 gf*cm; no direct size gain over NFP-608, not pursued.

**Faulhaber DM0620 / FDM0620 (Ø6 mm stepper, 20 steps/rev, no gear)**. Sources: [GlobalSpec/MICROMO launch](https://www.globalspec.com/FeaturedProducts/Detail/FaulhaberMICROMO/260591/MICROMO_Launches_6_mm_Stepper_Motor_FDM_0620), [im-tek DM0620SB013011 datasheet](https://www.im-tek.com/docs/faulhaber-dm0620sb013011-stepper-motor-377340.pdf), [MedicalExpo](https://www.medicalexpo.com/prod/faulhaber-drive-systems/product-96825-834769.html).
- FDM0620: Ø6 x 9.7 mm, holding torque 0.25 mN*m, dynamic up to 0.2 mN*m (search summary). Planetary gearheads reported for the series; no ratio/price found.
- Fit (our calculation): needs ~8:1 or more (0.2 mN*m x ~0.8 x ratio >= 1.3 -> >= ~8:1) with our own gear pair; a stage of 16:20 alone is not enough, a 2-stage spur set or a Faulhaber gearhead is needed. Resolution fine with 4x microstepping.
- Price/availability: no distributor price found; quote-only likely. Poor fit for a private buyer [UNVERIFIED].

**Faulhaber AM0820 (Ø8 x ~13.8 mm)**. Sources: [RS UK listing](https://uk.rs-online.com/web/p/stepper-motors/9211347), [im-tek PDF](https://www.im-tek.com/docs/faulhaber-am0820sb008001-stepper-motor-274758.pdf). 3 V, 0.65 mN*m holding, 20 steps/rev, 2 mm shaft. RS UK shows GBP 482.44 ex VAT for a single unit, temporarily out of stock (date shown is stale). Larger than Ø6, so not an improvement; needs ~4-6:1 reduction. Ruled out.

**Namiki / Adamant, Nidec Copal, Moons, NFP smaller models, AliExpress "4 mm stepper gear motor"**: not individually researched in this pass; no verified datasheet or part number was found [UNVERIFIED, open]. AliExpress 4 mm listings, if any, are the same Zhaowei-type parts with no usable datasheet.

### 2.2 Micro linear stepper actuators with integrated leadscrew

- **No verified Ø4-6 mm unit found** with force data from NFP, Zhaowei or Tiny Motion. The search returned only larger classes: [Portescap can-stack with built-in leadscrew](https://www.directindustry.com/prod/portescap-sa/product-24824-2033558.html), Haydon Kerk, NEMA 8/11/14 non-captive screw steppers (e.g. [Oyostepper NEMA 11](https://www.oyostepper.com/goods-178-Nema-11-Non-captive-32mm-Stack-042A-Lead-508mm02-Length-150mm.html), >= 10 N at 5.08 mm lead, far too large) and a Chihai "SM15xx/SM20xx" family ([rcdrone.top](https://rcdrone.top/bn/products/chihai-miniature-linear-stepper-actuator-sm1545-sm1530-sm1519-sm2016)), page content not verified; sizes appear > 10 mm [UNVERIFIED].
- Concept check (our reasoning): a non-captive or captive rotor-nut screw could act as the push rod, but the plunger tip needs a swivel/thrust bearing (screw rotates relative to the stopper) or an anti-rotation guide, and a typical lens-module screw (lead ~0.2-0.3 mm) gives high force per torque, which is favourable. Real parts at Ø4-6 with >= 6 N are not documented in what I found. Treat as an open lead: ask Zhaowei/NFP whether a Ø4-6 mm stepper with threaded rotor exists.

### 2.3 Piezo motors

- **New Scale M3-L**: 27.5-28 x 13 x 7.5 mm, 6 mm travel, 0.5 um resolution, force < 0.2 N, "not designed to carry a load" ([New Scale](https://newscaletech.com/micro-mechatronics/m3-l-linear-actuator-modules/), [datasheet](https://cdn.shopify.com/s/files/1/0048/8092/4739/files/M3-L_datasheet.pdf)). Far below 6 N; price not published. Other SQUIGGLE sizes were not verified [UNVERIFIED].
- **PI PILine**: holding force up to ~6-15 N and push/pull up to 7 N on stages, but those are large stages; small P-652/P-653 are 0.15-0.2 N ([PI](https://www.physikinstrumente.com/en/technology/piezoelectric-drives/piline-ultrasonic-motors/), [Vision Systems](https://www.vision-systems.com/factory/manufacturing/article/16747613/piezomotor-slide-achieves-200-mm-s-velocity)). Needs a dedicated HF driver; price on request.
- **PiezoMotor PiezoLEGS**: search returned nothing, no data [UNVERIFIED].
- Verdict: force/size does not match, driver is complex, price high, no private-buyer path. Ruled out.

### 2.4 SMA (nitinol) wire ratchet (note only)

Patents describe SMA wire + pawl/ratchet pumps (Tandem [US 12758702](https://mtec-sc.org/patents/US-12758702-B2), one tooth per actuation; Abbott [US 8079983](https://patents.google.com/patent/US8079983), 125 um wire, 0.1 uL per cycle; Omnipod-specific details not found [UNVERIFIED]). Pros: tiny, silent. Cons for us: high pulse current (heating), cycle life and thermal drift unknown, step size fixed by ratchet pitch (resolution needs a fine ratchet + gear), plus patent exposure (see docs/03-patents.md). Not for v0.1.x; note only.

### 2.5 Brushed micro gearmotors with encoder

- **Pololu Micro Metal** (10 x 12 x 25 mm, 6 V, 10:1 LP: stall 0.10 kg*cm, 0.36 A stall; HP ~0.22 kg*cm; encoder variant exists) ([Pololu 1099](https://www.pololu.com/product/1099), [Pololu 999](https://www.pololu.com/product/999)). Easy to buy but a 10 x 12 mm cross-section and 25 mm length: **larger** than Ø6 x 16. 6 V parts degrade at 3.0-4.2 V.
- **Faulhaber 0620 brushed / Maxon**: no verified data or price found this pass [UNVERIFIED].
- All need closed loop (existing angle sensor) and a stall/overspeed safety path; no inherent step resolution, so the interlock and dose accounting are harder to justify than with a stepper. Ruled out for v0.1.x.

## 3. Ranked table

Size = L x diameter of motor+gear. Plunger force = our M1.6x0.35 screw, eta 0.25 assumed (calculation). "Verified" only where a source above states it.

| Rank | Option | Size L x Ø (mm) | Plunger force with our screw | Resolution | Li-Po fit | Driver | Price | Availability (private, small qty) | Risk |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Zhaowei ZWBMD004004-36 or -216 (Ø3.4 stepper + 3-stage planetary) | 13.3 / 14.8 x 3.4 (verified) | gearbox limit ~13.7 mN*m verified (>10x need); motor torque unknown -> force **UNVERIFIED**, plausible at 216:1 | 0.49 um (36:1) / 0.08 um (216:1) per full step, coaxial | 3.0 V rated, 50 mA: good (needs chopper or limiting at 4.2 V) | 2-phase stepper driver, microstepping optional | not found, quote | Zhaowei direct / marketplaces, MOQ unknown | Medium: motor torque, 3 deg backlash, plastic-gear life, contradictory vendor pages |
| 2 | Current NFP-608-26.45-SGM + 5 V boost (baseline) | 16.1 x 6 | ~6 N (stated by owner) | 0.53 um/step | needs boost, or accept torque loss below ~4.2 V | existing | existing | owned | Low technical risk, but no size gain |
| 3 | Faulhaber FDM0620 / DM0620 + own 8-10:1 reduction | 9.7 x 6 motor (+ gear stage) | motor 0.25 mN*m holding; ~6 N needs >= ~8:1 (calculation) | fine with 4x microsteps | check rated V per variant [UNVERIFIED] | 2-phase stepper driver | not found (quote-only likely) | poor for private buyer | Medium: cost, supply, extra gear length |
| 4 | Faulhaber AM0820 + 4-6:1 | ~13.8 x 8 | 0.65 mN*m holding | fine | 3 V version OK | stepper driver | GBP 482 (RS, stale) | RS, out of stock | Large and expensive; ruled out |
| 5 | Micro linear stepper with screw (Ø4-6) | unknown | unknown | unknown | unknown | stepper | unknown | **no verified part found** | Open lead; ask vendors |
| 6 | Pololu Micro Metal + encoder, closed loop | 25 x 10 x 12 | stall ~9.8 mN*m at 6 V at 10:1 (verified); lower at 3.7 V | needs encoder + loop | 6 V motor, weak at 3-4 V | brushed H-bridge + control loop | see Pololu | easy | Larger than now; closed-loop safety cost |
| 7 | New Scale M3-L / PI PILine small | 27.5 x 13 x 7.5 / larger | < 0.2 N (M3-L) | sub-um | HV/special driver | piezo driver | on request | difficult | Fails force requirement |
| 8 | SMA ratchet | n/a | n/a | ratchet pitch | n/a | pulse driver | n/a | n/a | Note only; patent and life risk |

## 4. Recommendation

**(a) Bench v0.1** (size not critical): keep the NFP-608 motor already specified and fix the voltage problem, either a small 5 V boost or a current-regulating driver, whichever the existing driver design (docs/STATUS.md) supports; measure thrust with a spring scale/load cell on the real screw. In parallel, ask Zhaowei in writing for the ZWBMD004004 datasheet (winding resistance, pull-out torque at 3 V, price/MOQ) and order 2-3 samples each of -36 and -216 for a thrust test on the same screw with water-filled reservoir only.

**(b) Integrated v0.1.0** (size dominates): first choice is the Zhaowei Ø3.4 mm stepper gear motor, 216:1 (or 36:1 if torque allows), driving the screw coaxially; adopt only if the bench thrust test shows >= 6 N at 3.0 V with margin, acceptable backlash (<= 3 deg of output shaft is 3/360 x 0.35 mm = 2.9 um, so use unidirectional dose approach, see spec §7) and endurance. If it fails, fall back to FDM0620 with a custom reduction (if cost/availability can be solved) or stay with NFP-608 + boost. Piezo, SMA and brushed gearmotors are not recommended.

Top 3: 1) Zhaowei Ø3.4 stepper + planetary, 2) NFP-608 + boost (baseline), 3) Faulhaber FDM0620 + external reduction.

## 5. Open items / caveats

- Zhaowei motor torque/resistance, price and MOQ are not published; page figures conflict (4.3 vs 3.4 mm, 5/25/125/625 vs 6/36/216/1296, 200 vs 400 gf*cm).
- Efficiency eta 0.25 for the M1.6x0.35 screw is an assumption; the owner's "~6 N at 160 mA" figure was not re-derived from the 1.6 gf*cm pull-out value (1.6 gf*cm x 26.45 x 1.25 x eta_gear would give more than 6 N at eta_screw 0.25, so one of the stated figures probably refers to a different point of the chain; please re-check against spec/design-parameters.md).
- No changes were made to spec/design-parameters.md or other files; any adoption must update the spec first (CLAUDE.md).
- The Tandem patent entry's 2026-10-13 date was not verified.
