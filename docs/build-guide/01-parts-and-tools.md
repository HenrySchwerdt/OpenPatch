# 01. Parts, tools and consumables

> **WARNING: BENCH TEST ONLY.** Test project, not a medical device. Never worn, never used on a person or animal. **Water only: never fill it with insulin or any other drug, not even into a container.** See [DISCLAIMER.md](../../DISCLAIMER.md).

This chapter is the bill of materials for **one OP-100 bench pod**, the controller board, the tools and the consumables. Sources: `docs/PARTS-LOCK.md` (lock status), `docs/SHOPPING.md` (shops, estimates), `mechanical/parts.md`, `mechanical/out/bench/fab/` (print files), `electronics/bench/` (boards). Prices are the estimates of those files (EUR or USD as given there), **not quotes**; only check them in the shop. Status words follow PARTS-LOCK: **LOCKED** (dimensions from a datasheet), **LOCK-AFTER-SAMPLE** (measure your sample before you trust it), **CANDIDATE** (no verified listing yet, you must find and measure a part).

> **Order the dock insert set and the dock fit-test parts first** (chapter 09). It is the only slow-to-get-right part and it decides nothing else in the pod.

## 1.1 Printed and made parts (per pod)

Files are in `mechanical/out/bench/fab/OP-100/` unless stated. Orders: JLC3DP (default), PCBWay as fallback (`mechanical/out/bench/fab/vendor-notes.md`). Regenerate with `python3 mechanical/generate.py --variant bench` if you change `params.json`; the upload package is `mechanical/out/bench/fab/`.

| ID | Part | File | Process, material | Qty | Notes |
|---|---|---|---|---|---|
| P1 | Bottom shell (with dock channel and snap-arm frame) | `bottom.stl` | MJF PA12, grey, bead-blasted, no dye or vapour smoothing | 1 | +-0.2 mm. Porous: not watertight. Post-drill by hand (chapter 02) |
| P2 | Lid (top) | `top.stl` | MJF PA12 | 1 | FFC slot 8.0 x 1.1 mm in the +X wall; screw holes d1.4 may need a drill |
| P3 | Carriage | `carriage.stl` | SLA tough resin | 2 | +-0.1 mm. Order 2: the nut pocket fit is the first test. Hex pocket: **verify AF** (fab README says AF 3.3, current `params.json` gives AF 3.8: see chapter 04) |
| P4 | Plunger core | `plunger_core.stl` | SLA tough or clear resin | 2 | Two seal grooves 0.8 mm wide, socket for the steel shim |
| P5 | Plunger nose (0.7 mm stadium disc) | `mechanical/out/bench/OP-100_plunger_nose.stl` | SLA | 2 | **Not in the fab upload folder (gap G5): add it to your order.** Water test only |
| P6 | Reservoir (water-only print copy of the frozen CNC geometry) | `mechanical/out/bench/fab/reservoir-sla-water-only/OP-100_reservoir_WATER-ONLY_sla.stl` | SLA clear resin, wash and UV post-cure, bore not polished | 1 | **WATER ONLY.** The CNC polypropylene part (`reservoir-cnc/`, PCBWay, 25 USD minimum order) is optional material preparation and is also never filled with anything but water |
| P7 | End cap | `end_cap.stl` | SLA tough resin | 2 | +-0.05 mm. Fill septum bore d4.2, duckbill pocket d3.05, guard tube, channels d0.7 (clear with a 0.5 mm wire) |
| P8 | Dummy cannula head (cannula adapter) | `cannula_adapter.stl` | SLA tough resin | 2 | Dome d10, septum recess, latch notches, hose barb d1.6, magnet pocket d2.1 x 1.05. All `cannula.*` dimensions are placeholders until measured |
| P9 | Dock insert set (12 variants) | `mechanical/out/bench/fab/dock-inserts/insert_v01.stl` to `insert_v12.stl`, `variants.csv` | SLA tough resin (or MJF PA12) | 12 (shared by all sizes) | Embossed ID on the -Y arm. **Order first** |
| P10 | Dock fixture (pod-less fixture with the frozen dock interface) | `mechanical/out/bench/fab/dock-inserts/dock_fixture.stl` | MJF PA12 or SLA | 1 | For the fit test without a pod |
| P11 | Seal mould (only for cast seals, one set for all sizes) | `mechanical/out/bench/fab/mould/mould_lower.stl`, `mould_upper.stl` | SLA, high detail | 1 set | Only if you cast the lip seals (chapter 03, route A) |
| (made) | Plunger lip seals | `reference_not_ordered/plunger_seal.stl` (reference) | cast Pt-cure silicone Shore A 40, or cut rings (chapter 03) | 2 per plunger | Not printed |
| (made) | Housing gasket | `reference_not_ordered/gasket.stl` (outline reference) | 0.5 mm silicone sheet, die- or laser-cut | 1 | Ring 0.4 mm wide on the tongue: cut with 0.8 mm webs |

**Not needed:** `coupler.stl` (sleeve coupler of the coaxial layout; the default `side_gears` layout of this guide has none), `OP-70_dry_hub.stl` and `ratchet_hub.stl` (old SMA drive).

## 1.2 Bought parts (per pod)

Quantities include one spare where the part is cheap and easy to lose or ruin.

| ID | Part | Spec | Qty | Status (PARTS-LOCK) | Shop and link (from SHOPPING/PARTS-LOCK) | Estimate |
|---|---|---|---|---|---|---|
| B1 | Geared stepper motor | NFP-608-26.45-SGM: d6.0 x 15.1 mm, 20 steps/rev, ratio 26.45, 4.8 V, 26.5 ohm per phase, shaft d2.0 with D-flat 1.5, factory lead with 4-pin 1.25 mm plug | 2 (1 + spare) | LOCK-AFTER-SAMPLE | nfpshop.com: <https://nfpshop.com/product/6mm-micro-dc-step-gear-motor-16mm-type-model-nfp-608-26-45-sgm> (alternative precisionminidrives.com). Plug type (Molex PicoBlade or JST GH) **unconfirmed**: look at the plug when it arrives | 6.60 USD each (5.40 from 10) |
| B2 | Motor gear | GHW-Modellbau **390754**, module 0.3, brass, 16 teeth, bore 2.0 (only variant, face 5 mm, to be turned to 1.4 mm) | 1 | LOCK-AFTER-SAMPLE | <https://ghw-modellbau.de/Spur-gear-Brass-Module-03-10-120-T> | 16.15 EUR |
| B3 | Screw gear | GHW-Modellbau **753020** ("20 Z B"), module 0.3, brass, 20 teeth, bore 2.0, face 1.4 mm with hub d4 x 2.5 mm (hub to be turned off) | 1 | LOCK-AFTER-SAMPLE | same page | 3.10 EUR |
| B4 | Leadscrew sleeve | brass tube or SLA sleeve d2.0 OD x d1.6 ID, **2.1 mm long** (carries gear B on the M1.6 rod and bridges the 0.7 mm gap to the dry bush; `parts.md` says 1.4 mm, see 02.6) | 2 | not locked | model shop brass tube "2.0 x 1.6" or print with SLA | about 1 EUR |
| B5 | Leadscrew | M1.6 x 0.35 threaded rod, stainless A2 (DIN 976), 100 mm, cut per size | 1 rod | LOCKED | eBay/AliExpress/fastener shop, search "M1.6 threaded rod 100mm"; no EU shop with a stock listing was found (PARTS-LOCK row 4) | about 2 EUR |
| B6 | Carriage nut | DIN 934 M1.6, brass (AF 3.2, 1.3 thick) | 4 | LOCKED | e.g. Accu-Components HPN-M1.6-A2 (stainless): <https://accu-components.com/de/metrische-sechskantmuttern/7882-HPN-M1-6-A2> ; or a brass mixed lot | < 1 EUR |
| B7 | Bushes | PTFE or brass sleeve OD 3.0 x ID 1.7 x 1.0 long, cut from tube (fallback: none, the printed bore d1.7 runs the screw directly, add silicone oil) | 4 | not locked | AliExpress "PTFE tube OD 3 ID 1.6" | about 2 EUR |
| B8 | Spindle magnet | **NdFeB d3.0 x 1.5 mm, DIAMETRICALLY magnetised** (the CAD value; d2 x 1 diametric is not orderable) | 3 (spares and test) | **CANDIDATE: no verified listing (gap G6)** | ask AliExpress custom-magnet makers for "diametrically magnetized 3x1.5"; fallback larger diametric magnet (Radial Magnets 6 x 2.5, Digikey) only with a CAD change | about 0.30 EUR |
| B9 | Dock magnet | NdFeB d2 x 1 mm N52, **axially** magnetised (goes into the dummy head) | 4 | LOCKED | supermagnete S-02-01-N (N48): <https://www.supermagnete.de/eng/disc-magnets-neodymium/disc-magnet-2mm-1mm_S-02-01-N> (20 EUR minimum order); cheaper: <https://yourmagnets.net/product/neodymium-magnet-round-2mm-diameter-1mm-height-n52/> | 0.14 to 0.20 EUR each |
| B10 | Tongue shim | stainless steel 0.5 x 1.4 x about 4 mm strip (laser cut or from 0.5 mm shim stock) | 4 | not locked, not in the fab folder (G5) | laser-cut service (JLCCNC sheet), or hand-cut 0.5 mm stainless shim | about 3 EUR |
| B11 | Outlet needle | 30G blunt dispensing needle, 1/4 in (6.35 mm), OD 0.31 mm (Nordson EFD type) | 3 | LOCKED | AliExpress "30G blunt dispensing needle 1/4 inch" (100 pcs about 5 to 8 USD) or Techcon TE730025PK 22.42 USD per 50: <https://gotopac.com/techcon-te730025pk.html> | about 0.10 each |
| B12 | Needle hub | PTFE or PEEK disc d2.0 x 0.7 mm with a 0.3 mm bore (cut from 2 mm rod, drilled), press fit | 4 | not locked | 2 mm PTFE rod + 0.3 mm drill, or a CNC service | about 1 EUR |
| B13 | Duckbill check valve | silicone, **OD <= 3.0 mm (bore in the cap d3.05), length about 3.4 mm**, cracking pressure 1 to 5 kPa | 3 | **CANDIDATE: no verified listing (gap G6)** | Minivalve (NL) for samples (<https://minivalve.com/about-us>); Alibaba JU DBCV604 3.2 mm is **0.2 mm too large**: measure before you buy more | 1 to 4 USD |
| B14 | Silicone sheet, platinum-cure, Shore A 40 to 50 | 2.0 mm (fill septum) and 0.5 mm (gasket), about 50 x 50 mm each | 1 each | CANDIDATE | AliExpress "silicone rubber sheet 2mm / 0.5mm"; medical sheet (ElastaPro 40 durometer, <https://elastapro.com/?p=3522>) is **not required** for water | about 3 USD |
| B15 | Seal material | route A: 2-part platinum-cure silicone, Shore A 40 (Smooth-On Smooth-Sil 940 class, 15 to 25 EUR kit); route B: 0.8 mm silicone sheet | 1 | CANDIDATE | see chapter 03 | 15 to 25 EUR |
| B16 | Screws | M1.2 pan head, stainless (ISO 7045): **4 x 6 mm** (lid) and **1 x 4 mm** (board); order 10 of each | 1 set | LOCKED | Amazon.de / AliExpress "M1.2 screw set" (the CAD has four lid bosses and one board boss; `ASSEMBLY.md` still says six lid screws, count the bosses on your print) | about 3 EUR |
| B17 | FFC cable | 0.5 mm pitch, **same-side contacts**, 0.3 mm thick, 100 mm, pin count to match the connectors (10 on the pod board; see 10.1) | 2 | CANDIDATE | AliExpress "FFC 10 pin 0.5mm 100mm" (5 pcs about 1.5 to 3 EUR) | about 1 EUR |
| B18 | Silicone tube for the dummy head | 1/16 in ID (1.6 mm) silicone tubing, 300 mm | 1 | n/a | any lab supplier | about 3 EUR |

**Pod sensor board** (PCBA, JLCPCB; `electronics/bench/pod/parts.json`, 2-layer 15.5 x 25.9 mm, same board for all sizes). **There is no fab package for it in the repository yet (gap G8)**: only the KiCad project `electronics/bench/pod/pod.kicad_pcb`. Export gerbers, BOM and CPL with KiCad (`kicad-cli`) and order 5 bare / 2 assembled:

| Ref | Part | LCSC | Note |
|---|---|---|---|
| U4 | TMAG5273A1QDBVR (3-axis hall angle sensor, SOT-23-6, I2C 0x35) | C3716049 | mandatory |
| U3 | DRV5032 dock hall switch (X2SON). The listed part is **FADMR C2152496, which switches about 4 mm early** (STATUS, PARTS-LOCK row 10). PARTS-LOCK recommends **AJDMRT C2152456** (BOP 4 to 9.5 mT), stock not verified | C2152496 / C2152456 | decide before ordering; check the JLC parts library |
| U1, U2 | DRV5032FADMR, optional coarse quadrature channel, leave unpopulated | C2152496 | not on the 10-pin FFC |
| C1, C3, C4 | 100 nF 0402 | C1525 | |
| J1 | Hirose FH12-10S-0.5SH(55), 10-pos 0.5 mm ZIF, nominal 1.0 mm high | C506791 | confirm the height <= 1.2 mm on the Hirose drawing |

**Bench controller board** (JLCPCB assembled; package in `electronics/bench/fab/jlcpcb/controller/`: `openpatch-bench-controller-gerbers.zip`, `BOM-jlcpcb.csv`, `CPL-jlcpcb.csv`, STEP and renders). Main parts: E73-2G4M08S1CX (LCSC C2764963), STSPIN220 (C2150516), TPL5010DDCR (C473912), SN74AUP1G74 (C140267), INA180A1 (C122228), USB-C power-only receptacle (C165948), SWD 2 x 5 1.27 mm header (C41376037), buzzer MLT-8530 (C94599). **To be confirmed when the controller board is final:** the BOM currently lists the **16-pin FH12-16S (C596731)** for J4, `parts.json` another connector, and `electronics/bench/pin-assignment.md` a 12-pin FFC (gap G4). A repeat order: 5 bare, 2 assembled, about 45 to 60 USD plus shipping (SHOPPING B1.1).

**Programmer/target:** Nordic **nRF52840-DK** (Mouser DE 41.37 EUR, <https://www.mouser.de/de/ProductDetail/949-NRF52840-DK>), or a CMSIS-DAP / J-Link probe, plus a 10-pin 1.27 mm SWD ribbon (about 3 EUR) or Tag-Connect TC2030.

## 1.3 Tools

| Tool | Why | Note |
|---|---|---|
| Digital calipers, 0.01 mm | all incoming inspection in chapter 02 | check the zero and a gauge block |
| **Precision balance, 0.001 g (1 mg) with draft shield**, plus 10 g and 100 g calibration weights (E2/F1) | gravimetric tests (chapter 11) | 1 U = 10 ul = 9.98 mg, so 1 mg = 0.1 U. Warm up and calibrate before every session |
| Fine tweezers (anti-magnetic, stainless), flush cutters | all small parts | the magnet and the steel shim stick to ordinary tweezers |
| Screwdriver for M1.2 (PH000 or 1.5 mm slotted, match your screws) | lid and board screws | **torque by feel**: stop when the head touches the counterbore (about 0.1 N m is the strip limit in PA12) |
| **UV lamp (365/405 nm)** | post-cure SLA parts; UV adhesive fallback on the needle hub | |
| **Cut-off wheel (rotary tool, 0.3 to 0.5 mm disc), pin vise, small file or stone, loupe** | cut and deburr the M1.6 rod and the needle | wear eye protection; clamp the rod in the pin vise, not in your fingers |
| Pin vise with drills 0.3, 0.5, 0.7, 1.0, 2.0 mm | post-drill pilot holes, channels, hub bore | drills break at 0.3 mm: buy spares |
| Small lathe or a machinist (30 minutes) | turn the hub off gear B and skim gear A to 1.4 mm (chapter 02.6) | **or** mill/file by hand with the gear on a mandrel; do not skip |
| Biopsy punches 4 mm and 2 mm | fill septum d4 x 2 and the 2 mm dummy-head plug | about 5 to 10 EUR |
| Razor blade, hobby knife, cutting mat | silicone gasket and seal rings | new blade for each cut |
| Feeler gauges or shim stock | air gap 0.6 mm magnet to TMAG5273 | |
| Multimeter, USB microscope or loupe | continuity of the FFC, inspect X2SON and FFC | |
| Force gauge 0 to 10 N (0.01 N), **or** a string, pulley and a set of small masses | seal friction pull test (chapter 03.5), thrust test (chapter 11.1), dock pull-off | with masses: 1 g is 9.8 mN |
| Thermometer and hygrometer | water density and evaporation correction | |
| Stopwatch | gravimetric drift measurement | |
| Oscilloscope or logic analyser (optional) | interlock test (VMOT drops within about 2 s after a hang; `firmware-rs/docs/bench-testing.md`) | |
| Computer with Rust, probe-rs and the repository | flashing (chapter 10) | `docs/SETUP.md` |

## 1.4 Consumables

| Item | Use |
|---|---|
| Retaining compound (Loctite 638 or similar) and cyanoacrylate (thin and gel) | gear A on the shaft, sleeve and gear B, nut, shim, nose, magnets. Keep it off the thread section where the nut runs, off the bushes and off the seal |
| Silicone oil 350 cSt (a few drops) | thin film in the bore and on the seal lips, printed bore of the bushes |
| 2-part platinum-cure silicone (Shore A 40) or silicone sheet 0.8 mm | seal rings (chapter 03) |
| Isopropanol (99 %) and lint-free wipes | wash SLA parts before assembly. **Flush every wetted part with water afterwards and let it dry.** |
| Distilled or deionised water (1 l), labelled WATER ONLY | the only fluid |
| Syringes 1 ml and 2.5 ml with blunt 27G fill needles | fill and draw tests |
| Glass vial (10 ml) with rubber stopper | water source for the draw test |
| Beakers or small cups, mineral oil (a drop) | evaporation trap on the balance |
| Silicone tubing 1/16 in ID (1.6 mm), micro clamp or hemostat | occlusion test (clamped outlet line) |
| Kapton tape, ESD-safe tray, small zip bags with labels | part handling; label every bag with the part ID |
| **Not needed: Velcro, adhesive patch, any skin contact material.** | the pod is never attached to a person |

## 1.5 Spares and tolerances you will need

Order **two** of: carriage, plunger core, end cap, dummy head, motor (one spare), nut, shim, needle, hub, duckbill, magnets. Seals, the gasket, the septum plug and needle hubs are consumed on disassembly (3 to 5 cycles). The dock insert set already holds 12 variants.

## 1.6 Receiving inspection of the order

Weigh the incoming bags against the order list, label each part with its ID, and keep a photo of the motor plug (chapter 10.2 needs it). Anything that is missing or wrong goes into the first row of the test report (templates/test-report-template.md, section 2).

Next: [02-print-and-prepare.md](02-print-and-prepare.md).
