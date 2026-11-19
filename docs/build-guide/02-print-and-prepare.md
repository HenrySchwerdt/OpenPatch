# 02. Order the prints, post-process, measure, prepare the small parts

> **WARNING: BENCH TEST ONLY.** Test project, not a medical device. Never worn, never used on a person or animal. **Water only: never fill it with insulin or any other drug, not even into a container.** See [DISCLAIMER.md](../../DISCLAIMER.md).

Everything in this chapter happens **before** the first assembly step. Its purpose is to find out cheaply whether your printed parts and bought parts are what the CAD assumes. Write every measurement into `templates/incoming-inspection.csv` (one row per feature). A value outside its go range stops the step that uses it (the "if it fails" column says what to do).

## 02.1 Ordering the prints

1. **Dock insert set and fixture first** (P9, P10) together with one pod set, so the long-pole fit test (chapter 09) runs while the rest is in production.
2. Upload the **STL** files (fine quality) to the quote tool; STEP is the master if the vendor accepts it. Settings per file are in `mechanical/out/bench/fab/README.md` and `MANIFEST.csv` and repeated in chapter 01 (material, quantity, tolerance).
3. Typical vendor names: JLC3DP "PA12-HP Nylon" (MJF) for P1 and P2; JLC3DP "8001 / 9000-type tough resin" (SLA) for P3, P4, P5, P7, P8, P9; clear SLA resin for the reservoir P6. PCBWay equivalents are listed in `vendor-notes.md`.
4. **Do not** select dye, vapour smoothing, polishing or any coating. Ask for support marks on the outside only. Do not let the vendor sand the carriage hex pocket or the bores.
5. If the vendor flags the 0.8 mm snap arms or the 0.4 mm lap tongue of the housing, re-order P1 and P2 in SLA tough resin (stiffer; arm force rises, retest with the insert set) and note it in the report.
6. Check the delivery against the list (chapter 01.6) the day it arrives.

## 02.2 Post-processing

| Material | Steps |
|---|---|
| SLA parts (P3 to P10) | Wash 2 x 5 min in isopropanol (clean bath for the second), blow dry. Remove supports with flush cutters on the **outside** faces only. UV post-cure per the resin sheet (typically 10 to 20 min, both sides). Do not sand bores, the hex pocket or the plunger and seal grooves |
| MJF PA12 (P1, P2) | Blow out all bores and channels with air (powder), tap out loose powder. Do not sand the lap tongue (0.4 mm) |
| All wetted parts (reservoir, plunger core, end cap) | After the isopropanol wash and the cure, **flush with water** and let them dry on a clean wipe. Isopropanol must not stay in a part that will hold water for the tests |
| Label | Put each part in a labelled bag with its ID (P1 to P10) now |

**Post-drilling by hand** (pin vise, light pressure, turn the drill, never push; check each hole with a pin or the real part):

| Feature | Part | Drill | Go criterion |
|---|---|---|---|
| Lid screw pilots (4 pieces at the dry end and next to the reservoir) and board screw pilot (1 piece), M1.2 thread-forming | P1 | d1.0 | the M1.2 screw starts by hand for two turns without cracking the boss |
| Lid screw clearance holes (4 pieces) | P2 | d1.4 | the screw passes freely, the head sits in its counterbore |
| Needle hub seat | P1 (tower) | d2.0 | the hub d2.0 x 0.7 enters with finger pressure and stays without glue |
| Fluid channel from the guard tube to the hub | P1, P7 | d0.7 | a 0.5 mm wire passes through the full length |
| Bush bores | P1 | d3.05 | a bush OD 3.0 enters with light finger pressure |
| Rod bores through bush and gear plane | P1 | d1.7 | rod M1.6 passes with a little radial play |

## 02.3 Measuring the critical dimensions (go / no-go)

Measure with the calipers, three readings per feature, enter the mean. "Source" tells where the nominal comes from. Where the table says **derived**, the go range is this guide's engineering judgment from the stated tolerance, not a drawing value; mark it "verify on your sample". Dimensions in the **frozen interfaces** (`reservoir_frozen`, `dock_interface_frozen`) are never changed by the builder: if the part is out, reprint or ream, do not edit `params.json`.

### Reservoir (P6) and end cap (P7)

| Feature | Nominal | Go | No-go action | Source |
|---|---|---|---|---|
| Bore width | 16.00 +0.05/-0 | 16.00 to 16.10 | below 16.00: hone lightly with a wrapped dowel until the plunger core slides; above 16.15: reprint (seal squeeze drops from about 0.13 mm to under 0.06 mm per side, leakage) | `reservoir_frozen`, fab README; upper limit **derived** |
| Bore height | 5.00 +0.05/-0 | 5.00 to 5.10 | as above | same |
| Overall length (OP-100) | 21.70 +-0.1 | 21.6 to 21.8 | reprint | `reservoir-cnc/README.md` |
| Bore depth (OP-100) | 19.20 | 19.1 to 19.3 | reprint | same |
| Outer 17.6 x 6.6 | +-0.1 | within | the carriage lane and the lid clearance depend on it (sim 3.7: lid touches the reservoir at 7.5 mm): if height > 6.7, sand the **outside** top flat | same, sim REPORT 3.7 |
| Port d2.0 H7 | 2.000 to 2.012 (CNC); SLA 2.00 to 2.10 | cap spigot d1.98 enters by hand to the stop, does not fall out | too tight: ream with a 2.0 drill by hand; too loose: reprint the cap (spigot) or use the fallback in chapter 05 | fab README |
| Bore surface | Ra <= 0.8 um (CNC); SLA: not polished | no layer steps you can feel with a fingernail, no resin burrs | scrape burrs with a blunt blade; do not polish | `reservoir-cnc/README.md` |
| End cap fill septum bore | d4.2 | a punched d4.0 plug presses in with a small squeeze | too loose: punch from 2 mm sheet again with a fresh punch; too tight: nothing (silicone gives) | fab README (CAD `septum.bore_clr`, 0.1) |
| End cap duckbill pocket | d3.05 | valve drops in with tweezers | valve OD > 3.05: **no-go for this valve** | fab README |
| End cap channels d0.7 | d0.7 | 0.5 mm wire passes the whole path | clear with the wire | fab README |

### Plunger core (P4), carriage (P3), nose (P5)

| Feature | Nominal | Go | No-go action | Source |
|---|---|---|---|---|
| Plunger core width x height | 15.6 x 4.6 (bore minus 0.2 per side, **derived** from `reservoir.plunger_clr`) | 15.5 to 15.7 x 4.5 to 4.7, slides in the bore with no rocking | sand the outside only if tight; reprint if loose | `params.json` |
| Seal grooves | 0.8 wide x 0.5 deep, two | calipers on both | reprint | `seal` in `params.json` |
| Socket for the steel shim | 0.8 wide x 1.5 high x 1.6 deep | the shim (0.5 x 1.4) enters with 0.1 to 0.2 play, bottoms out | clean with a 0.5 mm blade | `seal.socket_*` |
| Carriage rod bore | d1.9 | M1.6 rod passes freely | drill d1.9 | fab README |
| **Carriage hex pocket across flats (AF)** | **3.3 (fab README) or 3.8 (`drive.nut_af` 3.2 + `nut_hex_clr` 0.6, current CAD)** | measure which one you have; the nut (AF 3.2) must fit in the pocket without tilting | **verify on your sample: the two sources disagree** (gap). If AF is 3.3 the nut is a light press fit, if 3.8 it floats 0.3 mm and must be bonded (chapter 04) | `params.json`, fab README |
| Shim pocket | 0.55 wide x 1.45 high x 1.5 deep | shim fits, pocket open towards the reservoir | clean | `bench.shim` |
| Rail groove | 1.2 wide x 0.3 deep (fab README: 0.5) | the carriage slides on the floor rail (0.9 wide) with no wobble | none | `drive.groove_*` |

### Housing (P1, P2)

| Feature | Nominal | Go | No-go action | Source |
|---|---|---|---|---|
| Length x width x height of the closed pod (check after chapter 08) | 47.0 x 32.0 x 8.4 | height 8.3 to 8.5 | sim 3.6: nominal sits at the 8.5 mm limit; if > 8.5 file the bottom outer face of the lid flat | spec §2, sim |
| Floor-to-lid inner height | 7.5 - 0.9 = 6.6 mm cavity at the reservoir | reservoir top (7.5) below the lid underside (7.6) | if touching (sim 3.7, P = 50 %): sand the lid underside **recess** over the reservoir 0.2 mm, or the reservoir outside | `layout.json` |
| Bush bore | d3.05 | OD 3.0 bush fits | drill | `drive.post_bore_d` |
| Dock channel mouth width | 12.4 (half 6.2) | the dummy head dome (d10) slides in, no rubbing at the sides | none: the insert, not the pod, is changed | `dock_interface_frozen` |

### Dummy head (P8) and dock insert (P9)

| Feature | Nominal | Go | No-go action |
|---|---|---|---|
| Dome diameter | 10.0 (placeholder A) | measure and record | enter in the fit log (chapter 11.6) |
| Magnet pocket | d2.1 x 1.05 | the d2 x 1 magnet drops in, flush or 0.05 below | none |
| Barb d1.6 | d1.6 | 1/16 in ID tubing pushes on with a little stretch | none |
| Snap arms | 0.6 mm thick (insert) | flex each arm by hand 2 mm and release: it springs back, no whitening, no crack | arm cracks: that variant is lost; keep the rest |

### Bought parts

| Feature | Nominal | Go | No-go action | Source |
|---|---|---|---|---|
| Motor body | d6.0 +-0.1 x 15.1 (8.1 gearhead + 8.0 motor) | within | none; record | `parts.md` 1.0 |
| Motor shaft | d2.0 with D-flat 1.5, flat length 2.5, **free length unknown (about 5.3 derived)** | d2.0 and flat 1.5 within 0.05; free length >= 1.6 mm beyond the boss front (gear A 1.4 wide plus 0.1 mm gap; the CAD cuts the shaft at x = 1.2, 2.9 mm beyond the boss) | free length too short: do not fit; ask the vendor for the drawing. **Verify on your sample** | `parts.md`, `components/README.md` |
| Motor pins | 4 pins 1.2 pitch under the lead, **plug type open** | note PicoBlade vs JST GH | needed in 10.2 | PARTS-LOCK row 2, 14 |
| Phase resistance | 26.5 ohm +-10 % per phase | multimeter: coil A pins and coil B pins about 24 to 29 ohm | open or very different: motor is dead | datasheet via PARTS-LOCK |
| Gear A (390754) | z16, OD 5.4, bore 2.0 | tooth count and OD within 0.05 | n/a; width is turned in 02.6 | `components/README.md` |
| Gear B (753020) | z20, OD 6.6, bore 2.0, face 1.4 + hub d4 x 2.5 | as above | hub turned in 02.6 | same |
| Rod | M1.6 x 0.35 | a brass or stainless M1.6 nut runs the full length by finger without binding | reject the rod | PARTS-LOCK row 4 |
| Nut | DIN 934 M1.6 AF 3.2, 1.3 thick | AF 3.2 +0/-0.18, thickness 1.3 +0/-0.25, runs on the rod | reject | PARTS-LOCK row 5 |
| Spindle magnet | d3.0 x 1.5 diametric | d3.0 +-0.05, 1.5 +-0.05 | measure and record; wrong size means a CAD change (stop) | `drive.mag_d`, `mag_t` |
| Dock magnet | d2 x 1 axial | d2.0 +-0.05, 1.0 +-0.05 | record | spec |
| Needle | 30G, OD 0.31 | 0.31 +-0.02 | record | PARTS-LOCK row 17 |
| Duckbill valve | OD <= 3.0 (3.05 pocket), length about 3.4 | OD <= 3.0; passes the "air blows one way" test (02.9) | reject | PARTS-LOCK row 16 |

## 02.4 Seal friction pre-check (go / no-go before you go further)

The simulation says the available thrust is **4.0 N at 105 mA (7.0 N at 181 mA)** while a cast two-ring seal at 0.13 mm squeeze is modelled at **9.6 N kinetic** (plausible 3 to 20 N). If your seal friction is above the thrust, the pod will not work, and no amount of assembly will change that. Measure it after chapter 03 and **before** chapter 06 (the pull test is described in 03.5 with its go / no-go values).

## 02.5 Cutting and deburring the M1.6 rod

Lengths come from `mechanical/parts.md` and the `mech.json` files (dry-end bush start at x = 0.9 to the rod end face), tolerance **+0 / -0.2 mm**. The magnet (1.5 mm) sits on the end face and is **not** part of the length.

| Size | Cut length | Source |
|---|---|---|
| OP-70 | 21.0 mm | `parts.md` 1 |
| **OP-100** | **25.0 mm** | same |
| OP-200 | 38.5 mm | same |

(`mechanical/ASSEMBLY.md` says 19/23/37 mm: that is the old coaxial layout, do not use it.)

1. Eye protection on. Mark the length on the rod with a fine marker, add 0.5 mm, clamp the rod in the pin vise with 3 mm free beyond the jaw.
2. Cut with the 0.3 to 0.5 mm cut-off wheel at low speed, rod rotating slowly by hand between cuts; let the wheel cut, do not lever.
3. Dress the cut end square on a fine stone or file to the final length. **Thread a nut over the end** and back off again: this straightens the first thread. Chamfer the end by about 0.2 mm x 45 degrees. Do both ends; the **bush journal end** (dry end) must be clean for the bush.
4. Check: length 25.0 (+0/-0.2); the nut runs the whole length by finger; roll the rod on a flat glass plate: no visible wobble (bent rod: discard); end faces square within about 0.1 mm (hold a feeler to a straight edge). Cut a second rod to the same length as a spare.
5. **If it fails:** a rod with a bent end or a damaged first thread is the usual cause of a once-per-turn error and carriage drag. Discard it, do not straighten.

## 02.6 Gear hub turning and the screw sleeve

The pair is module 0.3 brass: **gear A, z16, GHW 390754, on the motor; gear B, z20, GHW 753020, on the rod.** The cavity between the dry-end bush and the reservoir is only 1.4 mm wide for the gear plane (CAD `bench.gears.x0 = 2.6` to `x1 = 4.0`).

| Gear | Turn to | How |
|---|---|---|
| Gear A, 390754 (face 5 mm) | **face width 1.4 mm** (keep the bore d2.0 clean) | collet on a d2.0 mandrel or a 3-jaw on the toothed part with the face protruding; face off 3.6 mm in 0.2 mm passes, light feed (brass, sharp HSS tool); deburr the bore edge |
| Gear B, 753020 (face 1.4 + hub d4 x 2.5) | **hub removed, web 1.4 mm kept** | grip the hub in a collet, part the web off **at the hub face** (0.5 mm parting tool, light feed), face the hub stub flush; deburr |

No lathe: any model shop or maker space can do both in 30 minutes. A hand method (jeweller's saw plus file on a 2 mm mandrel) works for gear B's hub but not for gear A's 3.6 mm of tooth width: ask for a lathe.

**Sleeve for gear B:** gear B's bore is 2.0, the rod is M1.6, so the gear sits on a **sleeve d2.0 OD x d1.6 ID** (brass tube or an SLA printed sleeve) that rides on the thread crests. `mechanical/parts.md` and `ASSEMBLY.md` give 1.4 mm (the gear width). In the CAD the gear plane starts at x = 2.6 while the dry bush ends at x = 1.9, a gap of 0.7 mm that the sleeve must bridge, because **the sleeve end face on the bush face carries the delivery thrust** (sim 1: thrust collar at the bush face). Cut the sleeve **2.1 mm long** (0.7 gap + 1.4 gear) and **measure the real gap on your bottom shell first** (verify on your sample). Retain with one drop of retaining compound between sleeve and gear and sleeve and rod; keep it off the bush.

| Check | Go | If it fails |
|---|---|---|
| Gear A width and gear B width | 1.40 +-0.05 | re-face; wider than 1.45 will collide with the bush or the reservoir |
| Bores | d2.00 +0.02 | a damaged bore: use the spare gear |
| Mesh test on a gauge: two 2.0 mm pins 5.51 mm apart (calipers on a drilled plate or a piece of printed sheet) | gears turn by hand with a **small amount of rattle** (backlash about 0.1 mm), no binding at any angle | binding: your centre is too small. **Sim 3.1: a theoretical centre 5.40 binds 35 % of the time; the housing builds 5.51 mm.** Never pre-load the gears |
| Sleeve length (see below) | measured gap between the dry bush end face and the gear plane, about 0.7 mm in the CAD (bush end x = 1.9, gear plane from x = 2.6) | sleeve = gap + gear width = **2.1 mm** if your gap is 0.7 | the sleeve is the thrust spacer: if it is too short the screw gets axial play (lost dose at every reversal, sim 2.9) |

## 02.7 Stainless tongue shim

0.5 x 1.4 x about 4 mm, laser cut or cut from 0.5 mm stainless shim stock with the cut-off wheel and a file. Flatten it on a stone, deburr. Check: it enters the carriage shim pocket (0.55 wide) with a slight clearance and 1.5 mm of it stays inside, the free end (about 2.5 mm) enters the plunger socket. **Do not bend it.** The simulation says the printed tongue of the old CAD was 22 MPa per newton in bending; the steel shim is the fix (sim 4.4 to 4.6).

## 02.8 Magnet polarity check

1. Keep all magnets away from the controller board, the pod board, your phone and watch while testing. Anyone with a pacemaker or other implant must not handle the magnets.
2. **Spindle magnet (diametric d3 x 1.5).** A diametrically magnetised disc has its poles on opposite sides of the **rim**, not on the faces. Put it near a compass: **turn the disc about its axis**: the needle must follow through 360 degrees. If turning the disc changes nothing and only **flipping it face to face** reverses the needle, it is **axially magnetised** and the TMAG5273 will not see a rotating field: reject that lot. Put a dot of paint on the rim side that **attracts the compass's north-seeking end**: that side is the magnet's south pole; write "S" in the log. (The sign does not matter for the angle reading, but you want a record.)
3. **Dock magnet (axial d2 x 1).** Find which face attracts the compass north end (south pole face) and mark it. Fit all dock magnets with the **same face up** (towards the pod hall sensor). The pod's DRV5032 may respond to one pole only; verify in 10.5 that DOCKED asserts with your fitting, and if not, flip the magnet.
4. Record the result in `incoming-inspection.csv` for each magnet.

## 02.9 Small parts, duckbill test, bushes, hub

| Part | Preparation | Go |
|---|---|---|
| **Bushes** (4): slice PTFE or brass tube OD 3.0 x ID 1.7 into 1.0 mm lengths with a new razor on a flat plate; deburr | OD 3.0, ID 1.7, 1.0 long | rod passes the bush with slight play |
| **Needle hub** (4): drill the 0.3 mm bore through a 0.7 mm slice of d2 rod in a pin vise (turn the drill, do not push; use a jig plate) | d2.0 x 0.7, bore 0.3 | the needle (OD 0.31) presses through with a slight interference, hub presses into the d2.0 seat by finger |
| **Duckbill valve** | flow test: put it on a 1 ml syringe filled with water with a short tube; push gently: water must pass at low pressure; reverse: pull gently with water: it must **not** pass or let air in | forward flow starts below about 5 kPa (about 4 cm water column is much lower than the syringe push: it should open with almost no force); reverse blocks at 20 kPa (a firm pull on a plugged tube) | passes both ways: reject; does not open until firmly pushed: record, probably a cracking pressure above 5 kPa (sim assumes 1 to 5 kPa) |

Next: [03-plunger-and-seal.md](03-plunger-and-seal.md).
