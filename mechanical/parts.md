# OpenPatch Rev A - purchased and made parts (mechanical)

EXPERIMENTAL DIY device, not a medical device. Rev A is a bench/water-test build.

Status legend used below:

* **VERIFIED-DATASHEET** - I read the manufacturer datasheet / vendor page and the number below is from it.
* **DERIVED** - computed from verified numbers or from a pattern; confirm before ordering.
* **SEARCH-TERM** - I could not open a product page; the part class is standard, the exact listing/price must be found
  by you. Prices are rough estimates (USD) unless marked VERIFIED. No fake product links are given.

All dimensions below are the ones used in `params.json` (single source of truth); the CAD follows them.

## 1. Drive: NFP-608-26.45-SGM geared stepper BESIDE the leadscrew + purchased gear pair (default, `bench.drive_layout = side_gears`; coaxial sleeve-coupler layout kept as option `coaxial`)

**Gear pair (FINAL 2026-11-19, step-down 16 : 20, purchased brass, GHW-Modellbau module 0.3, page <https://ghw-modellbau.de/Spur-gear-Brass-Module-03-10-120-T>; article numbers and prices read from the page on 2026-11-19, check delivery country at checkout):**

| use | GHW order no | z | bore | OD (tip) | face | price (incl. VAT) | remark |
|---|---|---|---|---|---|---|---|
| motor gear (NFP D-shaft d2.0 / flat 1.5) | **390754** (16 Z, only variant) | 16 | 2.0 | 5.4 | 5 mm -> skim to 1.4 mm on a lathe | 16.15 EUR | Loctite 638 on the round bore; the flat leaves a 0.5 mm gap the adhesive fills |
| screw gear (M1.6 rod) | **753020** (20 Z B) | 20 | 2.0 -> **sleeve** d2.0 OD x d1.6 ID, 1.4 mm long (brass tube / SLA) on the rod | 6.6 | 1.4 mm + hub d4 x 2.5 | 3.10 EUR | **turn the hub off** (it does not fit between the dry bush and the reservoir); alternative 390756 (20 Z A, 5 wide, 16.15 EUR) |

Total about **19.25 EUR**. Ratio: the screw turns z_motor/z_screw = **16/20 = 0.8** per motor turn -> **U/step = 0.35 x 0.8 / (20 x 26.45) x 74.63 / 10 = 0.003951 U** (0.05 U = 12.7 steps; firmware preset needs screw advance per step 0.35 x 0.8 / (20 x 26.45) mm, i.e. ratio 26.45 / 0.8 = 33.06). Centre distance: theoretical 0.3 x (16+20) / 2 = 5.40 mm, **built 5.51 mm (+0.11 backlash window, params `bench.gears.centre_add`)**; trough in the floor (motor_d + 0.05) is the motor datum, two zero-preload lid pads hold it down.

**Why not 15:12 (the catalogue cheap pair, 753015 + 753012, 5.95 EUR)?** Centre 4.05 mm: the NFP motor body (d6) beside the leadscrew lane needs centre >= carriage half width (2.4 with the 0.3 mm nut float) + 3.0 + 0.1 = 5.5 mm, otherwise the motor collides with the carriage (checked: carriage x gearhead interference). It also has the lowest thrust of all pairs (sim 1.1: 2.6 N). 15:15 (4.50) fails the same way. The ratio-equivalent 20:16 (centre 5.4) needs a z20 gear on the MOTOR: tip OD 6.6 vs cavity height 6.7 and the +Y wall (y_m + 3.3 > inner wall) - impossible. 18:18 (centre 5.4, tips 6.0) fits but costs 32.30 EUR and gives less thrust (sim 1.1). The chosen 16:20 has the same centre as 18:18, +25 % screw torque, and the z20 tip (6.6) fits only with a 0.25 mm floor relief and a 0.25 mm lid recess over the screw gear (both in the CAD).
The modelled gears are TIP circles (earlier root-circle models hid a collision of the 18:18 gear with the R4 rear corner); `check.py` flags any overlap. Other exact values: U/step = 0.004938 x z_motor / z_screw.

**Leadscrew length (M1.6 rod, DIN 976, cut to length incl. 1.0 dry-bush journal):** OP-70 **21.0 mm**, OP-100 **25.0 mm**, OP-200 **38.5 mm** (from `mech.json`: dry bush start x 1.0 .. end face x_r1 + 0.15). Magnet (diametric d3 x 1.5, glued to the rod end face) adds 1.5 mm. Carriage tongue shim: **stainless 0.5 x 1.4 x ~4 mm** (laser cut or from a feeler gauge), glued into the carriage pocket; plunger nose: printed 0.7 mm stadium disc (`plunger_nose`), glued to the plunger front.

Superseded notes below: the coaxial layout (sleeve coupler d3.0 x 5.6, D-bore on the shaft, M1.6 on the screw) is still generated with `--set bench.drive_layout=\"coaxial\"`; it makes the pod 65/69/83 x 27 mm.

### 1.0 PRIMARY: NFP-608-26.45-SGM, 6 mm planetary-gear stepper (drawing data)

Source: nfpshop.com, datasheet `stepper-gear-motor-spec-NFP-608-26.45-SGM.pdf` (official outline drawing). Numbers below are read from the drawing (**VERIFIED-DATASHEET** unless marked); the drawing is not to scale.

| item | value | status |
|---|---|---|
| body | diameter 6.0 +-0.1, total length **15.1** = gearbox **8.1** +-0.1 + motor **8.0** +-0.1 | VERIFIED-DATASHEET |
| output shaft | diameter **2.0** (+0/-0.05) with D-flat to **1.5** (+0/-0.05), flat length **2.5** +-0.05; 11.7 +-0.1 from the shaft reference line (start of the flat) to the gearbox/motor junction | VERIFIED-DATASHEET |
| front boss | diameter 3.5 x 0.8 (gearbox face) | VERIFIED-DATASHEET |
| rear boss | diameter 2.6, short (0.7 mm assumed) | DERIVED, VERIFY |
| free shaft length | ~5.3 mm beyond the front boss (derived from the not-to-scale drawing). The CAD cuts the shaft at x = 1.2 (`drive.shaft_cut_x`, shaft passes gear A); trim to fit | DERIVED, **VERIFY with calipers** |
| terminals | 4 pins at **1.2 mm pitch (3 x 1.2)** on the motor section, pointing radially "down" in the end view, order B, A-, B+, A; pin length ~1.05 mm beyond the terminal block (block 3.4 x 4.6 x 0.65, 11.0 mm behind the front face) | VERIFIED-DATASHEET / pin and block size DERIVED, VERIFY |
| lead | factory lead 4 x 30 AWG soldered to the pins + JST 1.25 mm plug | per coordinator |
| steps / ratio | 20 steps/rev (18 deg), planetary ratio **26.45** | per datasheet |
| resolution | with the 16:20 gear pair: 0.35 x 0.8 / (20 x 26.45) = 0.529 um/step -> **0.00395 U/step** (U100; 74.6 mm2 bore). Min pulse 0.05 U = 10 steps | computed (`op_layout.u_per_step`) |

Bench pod: the **factory lead is kept** (soldered to the pins by the maker). Because the motor now lies coaxially on the lane the terminal pins point **+Y** (row along Z) and the lead leaves through a
3 x 2.4 mm slot in the +Y wall (strain relief: two staggered posts, the wires weave between them); the JST 1.25 plug goes to the bench controller board. Rev B: bare-pin or FPC-tail motor, pin coordinates in
`out/bench/OP-*.layout.json -> motor.motor_pins_pod`.

CAD: `drive.active_preset = nfp_608_26` (`params.json`). The Zhaowei ZWBPD006006 below is the **backup** (6.43-class listing).

### 1.1 BACKUP: Zhaowei ZWBPD006006, 6 mm planetary-gear stepper, 1 stage

| item | value | status |
|---|---|---|
| vendor page | <https://www.zwgearbox.com/stepper-motor/pd6mm-stepper-gear-motor> (also sold under "6mm planetary gear stepper" on AliExpress/Taobao) | VERIFIED-DATASHEET (page read) |
| models | ZWBPD006006-5 / -6 (1 stage), -23 / -31 / -41 (2 stages), -110 ... (3 stages) | VERIFIED |
| diameter | 6 mm | VERIFIED |
| gearbox length | 9.7 mm (1 stage), 12.1 mm (2 stages) | VERIFIED |
| total length | 23.7 mm (1 stage), 26.1 mm (2 stages) -> motor body 14.0 mm | VERIFIED |
| gearbox torque | 25 mN*m continuous, 60 mN*m peak | VERIFIED |
| ratio | listed as "5/6" for one stage: **5.0 assumed** (exact ratio is not 5:1 or 6:1 integer; ask seller, or measure by counting turns) | DERIVED |
| steps per revolution | **20 (18 deg) ASSUMED**; the page does not list the step angle - confirm with the seller before buying 10 pcs | TODO-VERIFY |
| price | ~10-25 USD each on AliExpress (Zhaowei does not publish prices; enquiry form only) | SEARCH-TERM / estimate |
| quantity per iteration | 1 per pump, reusable; buy 4 for 3 sizes + spare | |

CAD: `drive.active_preset = zw_pd6_1stage` (gearhead_len 9.7, motor_len 14.0, motor_tail 1.0).

### 1.2 Premium alternative: Faulhaber ADM0620-2R-V3-05 + 06/1 planetary gearhead

| item | value | status |
|---|---|---|
| ADM0620 | dia 6 mm, length **9.5 mm**, 20 steps/rev (18 deg), **0.2 mNm** holding torque, V3 winding 3 V / 75 mA / 30 ohm, shaft dia 0.8, lead-screw options M1.2 and M1.6 | VERIFIED-DATASHEET (ADM0620 PRECIstep datasheet, edition 2010-11) |
| 06/1 gearhead | dia 6 mm; ratios 4:1 ... 4096:1 in powers of 4 (nearest to 10:1 is **16:1**; datasheet ratios are rounded); steel train | VERIFIED (trade press / reseller) |
| gearhead length | **11.9 mm for 2 stages is DERIVED** from a reseller length range (9.2 mm ... 22.7 mm over 1 ... 6 stages, 2.7 mm/stage) - VERIFY on the Faulhaber 06/1 datasheet | DERIVED |
| gearhead output shaft | dia unknown (assumed ~1.0-1.5): gear A bore must be reamed to match | TODO-VERIFY |
| resellers | im-tek.com lists "Faulhaber 06/1 16:1 planetary gearhead"; Faulhaber direct (quote) | SEARCH-TERM |
| price | quote only; expect **150-300 USD/EUR per motor+gearhead** | estimate |

Use this only after the cheap drive has proven the mechanism: `python3 generate.py --preset faulhaber_adm0620_16`.
Note the very low motor torque (0.2 mNm x 16 x ~0.8 = ~2.5 mNm output) - the lip-seal friction must stay below ~10 N.

### 1.3 Steps -> insulin (recomputed; spec said 0.0131 U/step at 10:1)

Reservoir bore 16.0 x 5.0 stadium, area 74.63 mm2, M1.6 x 0.35 screw, 100 U/ml (1 U = 10 ul = 10 mm3):

| drive | ratio | steps/rev | travel/full step | **U per full step** | min pulse 0.05 U |
|---|---|---|---|---|---|
| spec (Faulhaber-class, 10:1) | 10 | 20 | 1.75 um | 0.01306 | 3.8 steps (spec: 4) |
| **Rev A default ZW 1 stage** | 5 (5.0 assumed) | 20 | 3.50 um | **0.02612** | 1.9 steps -> use **2 full steps = 0.0522 U** (or 8 micro-steps at 1/4 = 0.0522 U) |
| ZW 1 stage, if ratio is 6 | 6 | 20 | 2.92 um | 0.02177 | 2.3 steps (use 1/4 micro-steps: 9 = 0.0490 U) |
| ZW 2 stages (x2 lanes, longer) | 23 | 20 | 0.76 um | 0.00568 | 8.8 steps -> 9 = 0.0511 U |
| Faulhaber premium | 16 (nominal) | 20 | 1.09 um | 0.00816 | 6.1 steps -> 6 = 0.0490 U |

Firmware must use the measured ratio (calibrate by counting steps per hall-encoder revolution; the encoder sees one
magnet turn per screw turn). 100 U needs 13.4 mm = 38 300 full steps at ratio 5.

### 1.4 Leadscrew + nut (no custom parts)

| item | spec | source | status / price |
|---|---|---|---|
| threaded rod | **M1.6 x 0.35 (ISO coarse pitch)**, A2/304 stainless, 100 mm, cut to 19 / 22 / 37 mm | AliExpress / Misumi / local fastener shop: "M1.6 stainless steel threaded rod 100mm" | SEARCH-TERM, ~1-3 USD |
| nut | **DIN 934 M1.6, AF 3.2, 1.3 mm thick**, brass or stainless | same shops, "M1.6 hex nut" | SEARCH-TERM, ~1-2 USD / 100 |
| thread play | ordinary rod/nut has 0.05-0.1 mm axial play = 0.4-0.7 U one-time backlash (uni-directional, harmless) | | |
| precision option | Faulhaber M1.6 lead screw / nut (only with the premium motor) | Faulhaber quote | |

### 1.5 Gears, bearings, magnet

| item | spec | source | status / price |
|---|---|---|---|
| 2 spur gears (purchased, NOT printed) | **module 0.3, 18 teeth, 1:1**: pitch dia 5.4, OD 6.0 (z+2)*0.3, centre distance 5.4, width ~1.2, brass or POM. Motor gear: **2.0 mm D-hole** (shaft d2.0 with flat 1.5) - or a plain 2.0 bore plus one drop of cyanoacrylate; leadscrew gear: bore **1.5** (press on the M1.6 rod, no glue) or 1.6 if offered. CAD models the root circle d4.65, bore d2.04 / d1.64. Both gears within the 8.5 mm height: OD 6.0 at the leadscrew lane (z 4.2 +- 3.0 = 1.2 .. 7.2) | search terms: "0.3 modulus 18 teeth spur gear 2mm D hole", "0.3M 18T brass pinion gear", "POM micro gear 0.3 mod 18T 1.5mm bore", "0.2M spur gear set 2.0mm D shaft" | SEARCH-TERM; ~3-6 USD / 10 (estimates). **VERIFY every listing** (AliExpress OD/bore/tooth data is unreliable): buy a mixed micro-gear assortment (0.2 / 0.3 module, bores 0.7 / 1.0 / 1.5 / 2.0) and measure before ordering the final set |
| gear alternatives | module 0.2 x 27 T (OD 5.8, pitch 5.4): same centre distance, finer teeth, bores 2.0 D / 1.5; ratio 1:1. Module 0.3 x 16 T (OD 5.4, centre 4.8) fits the envelope but the carriage lane then collides with the motor (not used). Unequal pairs change the resolution: **U/step = 0.35 / (20 x 26.45 x gear_ratio) x 74.6 / 10**; gear_ratio = teeth_leadscrew / teeth_motor (e.g. 18/20 -> 0.9 -> 0.00549 U/step, 20/18 -> 1.11 -> 0.00445 U/step) | same | DERIVED |
| 2 bushings | PTFE or brass sleeve **OD 3.0, ID 1.7, 1.0 long** (cut slices from tube) | AliExpress "PTFE tube OD 3 ID 1.6" | SEARCH-TERM, ~2 USD. **Fallback with zero parts:** print the block with a dia 1.7 bore and run the screw directly (add silicone oil) |
| magnet | **dia 2 x 1 mm NdFeB N35, DIAMETRICALLY magnetised** (axial magnets will not work with the hall angle sensor); glued/pressed to the screw end - use friction fit in a 2.0 pocket or a drop of cyanoacrylate (no UV) | AliExpress "2x1 diametrically magnetized neodymium", K&J-class | SEARCH-TERM, ~3-5 USD / 10 |
| hall sensors | TMAG5273 (I2C) + 2x DRV5032 - see `../electronics/bom.csv`; positions in `out/OP-xx.layout.json` (`hall`, `drv5032`) | electronics | |

## 2. Fluid path

| item | spec | source | status / price |
|---|---|---|---|
| outlet needle | **30G stainless blunt dispensing needle, OD 0.31 mm, ID ~0.15 mm, 1/4 in (6.35 mm)**; snip to 3.0 mm free length below the hub, blunt/ground end toward the cannula septum; deburr | AliExpress "30G blunt dispensing needle 1/4 inch" (EFD/Nordson-style tips, 100 pcs ~5-8 USD) | SEARCH-TERM |
| needle hub (press fit) | PTFE/PEEK disc **dia 2.0 x 0.7**, bore dia 0.3 (cut from 2 mm PTFE tube/rod and drilled, or CNC at PCBWay ~25 USD min). Pressed into the dia 2.0 seat; needle pressed into the hub; no adhesive. **Fallback only if it weeps:** a drop of UV medical adhesive (e.g. Loctite AA 3341-class, ISO 10993) cured with the UV lamp | | DERIVED / TODO-MEASURE |
| fill septum | silicone disc **dia 4.0 x 2.0**, Shore A 40-50: punch with a 4 mm biopsy punch from **2.0 mm silicone sheet** (AliExpress "silicone rubber sheet 2mm" ~3 USD; medical grade USP VI for later). GC-injection-port septa (e.g. <https://www.thomassci.com/p/standard-quality-gc-injection-port-septa>, beige silicone, 60 Shore A) work for water tests but are thicker | | SEARCH-TERM |
| biopsy punch 4 mm | | AliExpress "disposable biopsy punch 4mm" ~5 USD | SEARCH-TERM |
| housing gasket | die-/laser-cut ring from **0.5 mm silicone sheet**, Shore A 40-50, ring 0.4 mm wide on the tongue (fragile - cut with 0.8 mm webs) or dispensed 0.5 mm bead (FIPG); compresses to 0.45 mm at the screw stops | any silicone sheet | |

## 3. Reservoir + plunger (how Rev A is made)

| part | Rev A route | material | use |
|---|---|---|---|
| reservoir (16.0 x 5.0 stadium bore, 0.8 mm wall, dry end open) | **SLA clear resin** from JLC3DP/PCBWay (single piece, `*_reservoir.stl`) | clear resin ("BioMed Clear"-class if offered) | **water ONLY** - never insulin, not sterile |
| reservoir, optional material preparation (never filled with insulin) | **CNC PP halves** (`*_reservoir_cnc_lower/upper.step`, PCBWay CNC, ~25+ USD each), bond halves; later COC/COP injection-moulded | polypropylene (USP VI grade) | preparation for a future manufacturer only; never filled with insulin; leachables/extractables NOT evaluated |
| plunger core | SLA tough resin (`*_plunger_core.stl`); later PP/PEEK CNC | resin | water test only |
| plunger lip seals | **cast silicone** around the core: print `mould/mould_lower` + `mould_upper` (SLA), cast two rings per plunger in the core grooves | 2-part platinum-cure silicone **Shore A 40** (e.g. Smooth-On Smooth-Sil 940 class; later USP Class VI / ISO 10993 grade from NuSil/Elkem/Wacker) | water only; never insulin |
| lubricant | silicone oil 350 cSt (Rev A: any; later "medical fluid" grade, e.g. DOW 360 Medical Fluid 350 cSt class) - thin film in bore and on the lips | | |
| mould details | split plane through bore centre, 4 pins dia 2.0 / holes 2.2, sprue dia 0.7 (22G syringe) + vent dia 0.5 per ring; free ring size = bore + 0.3 (compressed to bore in the assembly = 0.15/side) | | |

Rule: **this pump is never filled with insulin or any other drug, and nothing printed or cast in Rev A is ever connected to a person: water only.** The documents and CAD are for
mechanical development only.

## 4. Battery envelope (decision requested by electronics)

Real envelope per size (X x Y x thickness; Y is limited to 11.2 by the motor-FPC shelf and the 4.5 mm RF keep-out
at the +Y wall; X by motor tail / hall magnet / screw C):

| size | max cell X x Y x T (mm) | volume | est. capacity (0.055 mAh/mm3, typical thin LiPo) |
|---|---|---|---|
| OP-70 | 8.6 x 11.2 x 3.2 | 308 mm3 | **~17 mAh** |
| OP-100 | 12.6 x 11.2 x 3.2 | 452 mm3 | **~25 mAh** |
| OP-200 | 13.2 x 11.2 x 3.2 | 473 mm3 | **~26 mAh** (~38 mAh if screw C is moved to the dry end and Y raised to 12.5) |

**The >= 40 mAh target is NOT met** with a 23.7 mm geared stepper in a 32 mm wide pod. The geared motor, its terminal
shelf and the RF module claim the area that the 17.4 x 19.8 mm cell needed. To get >= 40 mAh (>= 700 mm3) the pod would
have to grow by about +10.9 mm (OP-70), +6.9 mm (OP-100), +6.3 mm (OP-200), or the motor must move under the PCB
(needs height we do not have), or use a shorter gearmotor / external spur reduction. Cells: standard 3.0 mm-thick
pouch cells with nickel tabs (e.g. 301012-class, 3.0 x 10 x 12) from AliExpress/Battery makers; custom sizes need an MOQ.

## 5. Fasteners and small stuff

| item | spec | status / price |
|---|---|---|
| closure screws | **M1.2 x 6 mm** self-tapping (thread-forming) pan head, steel/stainless, 4 per pump (3 at the dry end, 1 at the coil side); pilot dia 1.0, clearance dia 1.4, head recess dia 2.4 x 0.5 | SEARCH-TERM "M1.2 x 6 self tapping screw" ~3 USD / 100 |
| velcro (hook) | die-cut 0.35 mm deep pocket in the bottom | any |

## 6. Rough purchased-parts cost per pump (mechanical only, estimates)

ZW motor 10-25 + rod/nuts 1 + gears 2 + bushings 1 + magnet 1 + needle 1 + septum 1 + screws 1 + silicone/sheet 3 =
**about 20-40 USD per pump, most of it reusable** (motor, gears, screw, magnet). Battery, PCB, coil: electronics BOM.


## 7. Rev B note: SMA ratchet wheel from a standard micro gear

A standard **module 0.1 spur gear (about 56 teeth, pitch dia 5.6, OD 5.8, bore 1.0-2.0)** (search "0.1 modulus 56T spur gear 1mm bore", AliExpress/KHK-class, SEARCH-TERM, ~2-4 USD, VERIFY OD/teeth) can serve as the ratchet wheel of the SMA drive: tooth pitch 0.314 mm, a **stencil-cut stainless (50-100 um) pawl** driven by the SMA wire advances one tooth per stroke. With the 0.35 mm leadscrew pitch one tooth = 0.35/56 mm of carriage travel (6.25 um) = 0.466 ul = 0.0466 U per tooth (U100, 74.6 mm2): about one pulse = the 0.05 U minimum. Not part of Rev A.


## 8. Reservoir: frozen CNC polypropylene part + separate end cap (decision 2026-11-19)

The reservoir is ONE CNC PP piece per size (`out/bench/fab/reservoir-cnc/`, README with the PCBWay order settings): blind stadium bore 16.00 x 5.00 (R2.5 = d5 end mill), wall 0.8, closed end wall 2.5 with a single
d2.0 H7 port, arm slot in the +Y wall; nothing else. Frozen numbers: `params.json -> reservoir_frozen`. The **end cap** (`end_cap`, SLA for water; PP later) presses onto the port (d1.98 spigot) and carries the fill septum
(through a d2.0 hole in the -Y wall), the duckbill valve pocket and the needle-hub guard tube; valve/septum/dock changes only touch the cap. Seal: platinum-cure medical silicone lip seals (mould as before) or a bromobutyl stopper
cut to the stadium shape; see the CNC README. Tests with water only, never a person.
