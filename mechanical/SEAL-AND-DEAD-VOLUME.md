# Plunger seal friction and dead / prime volume (design study + CAD change, 2026-11-19)

TEST PROJECT. Bench use, **water only** (never insulin or any drug), never on a person. The frozen CNC reservoir (`params.json -> reservoir_frozen`: stadium bore 16.0 x 5.0 +0.05/0, R2.5, end wall 2.5, port d2.0 H7, wall 0.8) is **not changed**; its length is unchanged too (`dead + plunger_len` stays 4.80 mm).

> **OPEN PROBLEM, NOT SOLVED HERE (coordinator finding, 2026-11-19): the reservoir is not sealed.** The carriage tongue reaches the plunger through a slot in the +Y reservoir wall (x = xrear_full + 1.35 .. xrear_empty + 2.35). Wherever the plunger front seal is *behind* the front end of that slot (e.g. the full position), the slot opens into the water-filled chamber and the reservoir leaks into the pod; the README item 4 claim "leak path to the dry side only" is wrong. The coupling decision (long plunger whose front seal always stays ahead of the slot, push rod from the open end with a fully closed reservoir, or coaxial drive) is pending with the user. **This document is a design study of the seal profile, Shore/lubrication, mould variants and dead volume only. Its per-bead seal numbers (F', contact width, pressure, friction, leak margin) do not depend on the coupling; the plunger length 4.76 / `dead` 0.04, the guide span L_g and the eccentric-push (cocking) factor DO depend on it and must be redone after the decision** (a push rod on the axis removes the cocking factor altogether). Nothing here claims the slot leak is closed. `check.py` now contains a fluid-boundary check that reports the slot as KNOWN-FAIL (see README). Status 2026-11-19: magnetic coupling was rejected by simulation (about 1.2 N vs about 7 N needed, spec 3b); a central push rod was started and abandoned because the user requires the same envelope (47 x 32 x 8.4 for OP-100); a same-envelope drive (tape-spring push band round the open end or similar) is being studied elsewhere. **No coupling change has been made; the slot is still in the CAD and the fluid-boundary check reports it as KNOWN OPEN.** When the coupling changes, the plunger length, L_g and the cocking factor (1.0 for any central push) must be redone.

Numbers come from `sim/seal_model.py` (plane-strain FE of the seal cross-section, validated against the closed form of a confined block), `sim/a6_seal.py` (variants, Monte Carlo) and `sim/a5_fluidics.py` (volumes). Friction coefficients are **[ASM]** ranges; the bench tests at the end decide.

## 1. Seal friction

### 1.1 What was wrong
The old plunger (two full-width 0.8 mm silicone bands, cast oversize 0.3, core clearance 0.2, Shore 40) was modelled at 9.6 N with a block model. The FE with the groove walls (the ring cannot bulge sideways in its groove) gives **23.5 N** at mu 0.40, and nobody had modelled the **eccentric push**: the carriage tongue pushes 7.2 mm off the plunger axis, so the core is pressed against the bore walls by a couple. With guide friction mu_g the force needed is `F = F_seal / (1 - 2 mu_g e / L_g)` (e = 7.2 mm, L_g = 4.3 mm): x1.5 at mu_g 0.10, x2.0 at 0.15, x5.9 at 0.25, **jam at mu_g >= 0.30** (dry resin on PP). Budget at 105 mA: about 1.7 N kinetic (4.0 N thrust, 1.5 x breakaway, 1.5 margin).

### 1.2 Physics used
* Contact pressure of an elastomer ring is set by the squeeze and the **compliance of the ring body**, not by the lip width alone; a narrow land on a thick confined ring is stiffer than a free block. Contact width b: 0.15-0.30 mm. E from Shore A (Gent): A30 = 1.14 MPa, A40 = 1.69 MPa.
* Friction F = mu x F' x perimeter(37.8 mm) x beads. Sliding speed is 3 um/s (bolus) .. 0.13 mm/s (draw): boundary regime, no hydrodynamic film; mu is set by the silicone-oil film (0.1-0.3 for oiled PDMS on PP, 0.5-1 dry). Breakaway/kinetic 1.2-2.5 from dwell adhesion (stick-slip is worst for dry silicone).
* Stadium corners (R2.5 arcs): an oversize ring is compressed circumferentially by only 2 pi x squeeze = 0.2-0.3 mm of the 38 mm perimeter (< 1 %), so no wrinkling; the corner effect is small. The FE is per mm of seal length; the arcs are not modelled in 3D.
* Leak: needs mean contact pressure >= 3 x 40 kPa (peak is 1.3-1.5 x the mean) with clearance-free contact everywhere. Bore finish Ra 0.8 um (frozen) is far below the 30-50 um squeeze.
* Printed-mould surface: layer steps across a land would be axial leak channels; print the halves standing on their short end (cavity axis vertical) so the steps run around the bead.

### 1.3 Options (nominal, mu 0.22 oil-wetted, Shore A 30, bore +0.025)

| option | squeeze / side | contact b | contact p | F seal alone | with guide (mu_g 0.10 / 0.15) | leak margin | hobbyist-makeable | decision |
|---|---|---|---|---|---|---|---|---|
| old: 2 full bands 0.8 wide, Shore 40 (FE) | 0.134 | 0.8 | 975 kPa | 23.5 N (mu 0.40) | x3.4 | huge | yes | **replaced** |
| S1: single front bead, land 0.20, oversize 0.15 | 0.046 | 0.30 | 397 kPa | 0.99 N | 1.48 / 1.97 N | 10x | yes (printed mould) | mould variant (fall-back) |
| **S2: single front bead, land 0.15, oversize 0.12** | 0.032 | 0.21 | 305 kPa | **0.53 N** | **0.79** / 1.05 N | 7.6x nominal, 96 % MC | yes (printed mould) | **chosen (active in CAD)** |
| T: twin bead (front + rear), land 0.20, oversize 0.14 | 0.042 | 0.30 | 351 kPa | 1.75 N | 2.62 / 3.49 N | redundant | yes (printed mould) | mould variant (if single beads leak) |
| O-ring cord d1.0 spliced, Shore 55 | 0.05 | 0.45 | 680 kPa | 2.6 N | x1.5-2 | good | cord + CA splice | rejected (stiff, splice bump, wider groove) |
| back-to-back thin cup lips (t 0.3, L 0.9) | - | - | 3 kPa (30+ energised) | 0.23 N at 30 kPa | low | only when pressurised | needs 1 mm free skirt | Rev B idea |
| PTFE-tape jacket on the bead | = S2 | | | mu 0.10: ~0.25 N | | seam = leak path | tape from the hardware store | option to test |
| rolling diaphragm | none | | | 0.1-0.3 N | | good | no (convolution gap 0.8 mm per side: -25 % area, clamp in the frozen part) | rejected |
| silicone oil film (350 cSt) | | | | mu 0.4 -> 0.22 | | | yes | **required** for every variant |

Monte Carlo (20 000 draws: bore 0..+0.05, printed cavity +-0.05, shrink 0.1-0.3 %, Shore +-4, mu 0.12-0.40, breakaway 1.2-2.5, guide mu 0.06-0.20 with tape):

| variant | median force at plunger (95 %) | P(<= 1.5 N kinetic) | P(breakaway <= 2.5 N) | P(leak-tight, p >= 120 kPa) |
|---|---|---|---|---|
| S1 | 1.77 (3.41) N | 35 % | 34 % | 100 % |
| **S2** | **0.93 (2.03) N** | **83 %** | **80 %** | 96 % |
| T | 3.15 (6.21) N | 7 % | 8 % | 100 % |

Without the PTFE guide tape (bare resin, oil-wetted) S2 drops to 56 %, S1 to 15 %.

### 1.4 Decision and CAD changes
* **Seal S2 (single front bead, trapezoid land 0.15 mm, cast oversize 0.12 mm, Shore A ~30, oil film) is active; S1 and T are cast from their own mould pairs in the same order.** Predicted S2: **0.53 N seal alone, 0.79 N at the plunger** (kinetic), about 1.2 N breakaway; target 1.5 / 2.5 N met nominally with 83 % / 80 % probability over the tolerance and mu ranges. S1 sits exactly on the limit (1.48 N), T is the redundancy option and is above the 105 mA budget (needs 181 mA).
* (coupling-dependent, provisional) Plunger core (`op_drive.build_plunger`): length 4.76 (was 3.8), core clearance 0.10 per side (was 0.20), grooves 0.6 wide x 0.55 deep at 0.4-1.0 (rear) and 3.65-4.25 (front), socket unchanged (1.45-2.25), flanges 0.4 / 0.51 mm, flanges turned down 0.1 per side (`seal.guide.tape_recess`) for an optional PTFE tape wrap, purge grooves in the front face. Seal body in the assembly = trapezoid bead (`op_seal.py`); the separate printed nose is gone (`nose_len` 0).
* Moulds (`op_mould.py`): three pairs, `mould_*` (S1), `mould_s2_*`, `mould_t_*`, sprue d0.8 / vent d0.5 per ring; `fab.py` ships all six files. Shore A can be changed with the PDMS mixing ratio at no mould cost.
* Sim inputs: `params.json -> seal` (variants, guide), `common.CONST` (mu_seal_design, mu_guide, tolerances), `a1_drive.py` (FE-based friction, MC), new `a6_seal.py`; `REPORT.md` rows 6.1-6.6.

### 1.5 Hobbyist recipe
Material: 2-part platinum-cure silicone, low viscosity (Sylgard 184 class, 3.5 Pa s: 10:1 = about A40, 15:1..20:1 = softer A25-30; or Mold Star 30). Degas (or pressure-pot) and inject with a 22G blunt needle into the sprue until it shows at the vent; cure 24-48 h at room temperature (heat accelerates but raises shrink). Cavity: wet-polish with 1500 grit, thin release (soap film/PVA); core pushed against the rear cavity wall. Demould, trim flash with a blade, **measure the OD of the land** with calipers (design: S2 16.09, S1 16.12, T 16.11 after shrink), coat the bore and bead with 350 cSt silicone oil, optionally wrap the two core flanges with one turn of 0.1 mm PTFE tape. Cast 3 plungers per variant, pull-test them all. Alternative without a mould: punch a 0.5-0.6 mm silicone sheet washer (not recommended, no bead).

## 2. Dead volume and prime path

### 2.1 Problem (before)
Wetted channels 22.1 mm3 = 2.21 U (prime path 1.77 U) against MAX_PRIME 0.52 U; 0.3 mm dead layer (nose 0.7 of 1.0) + 0.2 mm core clearance around a 0.7 mm nose = about 2.2 U + 0.7 U of air in front of the plunger.

### 2.2 Changes (`op_cap.py`, `op_drive.py`, `params.json`)
1. **Spigot 2.0 -> 2.4 mm** (`cap.spigot_len`): the pressed-in spigot fills the port (end wall 2.5), only 0.1 mm of d2.0 is left (0.31 mm3 instead of 7.85).
2. **Main path channels d0.7 -> d0.6** (`cap.prime_d`; fill branch and hub stay 0.7); jog moved to x = 0.45 (tangent to the block face at d0.6 broke the boolean).
3. **Valve pocket**: bore with interference (round 2) and printed valve plug close the slot, so the annulus void is zero; the duckbill's own cavity is assumed 12 % of its envelope [ASM] (2.9 mm3, the biggest item left; weigh a wetted valve).
4. **Plunger nose replaced by an integral front**: the core reaches to `dead` = 0.04 mm in front of the end face (nominal), front flange 0.51 mm behind the bead, so the annulus in front of the bead is only 1.9 mm3 (with tape). The plunger is **homed by motor stall against the end face** (the plunger, not the carriage block, is the first hard stop: carriage block gap is about 2 mm), so the real gap is the surface flatness, not the stack of tolerances.
5. **Purge grooves** in the front face (0.4 wide x 0.10 deep: long-axis, cross, centre spot, 1.0 mm3) connect the whole face and the flange annulus to the port.
6. Air purge: stand the pod on its outlet end (X up, septum side down), inject through the septum with the plunger homed (water follows the shortest path to the needle, the check valve opens at 1-5 kPa), then draw. The fill branch is a dead end with a high point at the septum; it is flushed by flow, not by buoyancy.

### 2.3 Numbers (sim 5.1 / 5.2)

| item | before | after |
|---|---|---|
| frozen port wetted | 7.85 mm3 | 0.31 mm3 |
| main path channels (port channel, jog, junction, valve->hub) | 2.3 (d0.7) | 1.75 (d0.6) |
| duckbill pocket void | 7.4 (30 % + annulus) | 2.9 (cavity only) |
| fill side branch + septum port | 4.4 | 4.4 (not in the prime path) |
| **prime path chamber -> needle tip** | **1.77 U** | **0.50 U** (MAX_PRIME 0.524 U) |
| all wetted channels | 2.21 U | 0.95 U |
| unpurgeable air at the plunger stop | about 2.9 U | **0.47 U** (gap film 3.0 mm3 + annulus 1.9 mm3, with PTFE tape; without tape the annulus is 4 mm3 = 0.7 U total) |

Occlusion / thrust (sim 1.3-1.6, 5.4-5.5): thrust margin over static friction at 105 mA rises from 0.28x to **2.9x** (4.0 N vs 1.4 N), P(motor cannot break the plunger loose) from 100 % to **7 %** at 105 mA and **0 %** at 181 mA, budget row 1.6 passes (0.8 N vs 1.7 N). The pressure the pump can build is now real (P_stall 27 kPa at F_kin 2 N, higher with the lower friction), so the compliance-stored volume at the alarm is 0.7-1.7 U on top of the 2 U threshold (sim 5.4/5.5, 2.7-3.7 U total, unchanged compliance model: PP walls + printed train + bubble). The dead-layer air that was a 75 mm3 compliance (0.37 U start-of-flow lag) is now 3 mm3 (0.01 U). The firmware occlusion threshold still has to be lowered by V_st (0.3 U at 181 mA) or a current/pressure criterion added.


## 2b. Cap interfaces and channels (fix after the independent review, coupling-agnostic)

| interface | before | now | check |
|---|---|---|---|
| cap spigot d1.98 in port d2.0 H7 | 0.02-0.03 mm clearance, resin on PP, nothing sealing | **face O-ring 2.0 x 0.5** (catalogue size, NBR or silicone) in a groove of the cap face (inner d2.2, width 0.6, depth 0.4) against the flat PP end face; ring stretch 10 %, axial squeeze **16 %** (limit 8-30 %); the spigot only locates. Cap block raised to z 6.4 (`cap.block_up` 3.4) to hold the groove | `cap_interfaces` in `op_cap.py`, `check_fluid_boundary` |
| fill septum d4.0 punched disc in a d4.2 bore | no squeeze, 1.05 mm air pocket behind the 2.0 mm disc | bore **d3.4 = radial compression 15 %** (limit 10-20 %), cavity 1.8 deep so the disc sits on the bottom (no air pocket) and stands 0.2 proud, the shell wall compresses it 0.1 axially | same |
| needle hub d2.0 in a d2.0 seat | zero interference | bore d1.92 = **0.04 per side press fit** (PTFE, bench only; adhesive on the needle as fallback) | same |
| duckbill valve + slot | bore interference + plug (round 2) | unchanged | same |

Retention of the cap against the O-ring (about 1-3 N for 16 % squeeze of 7.8 mm of cord plus 30 kPa x 7.6 mm2) is **not designed yet**: a printed crush rib or a clamp is an open item; do not rely on the spigot.

`check_fluid_boundary` now also walks the cap interfaces: gap >= 0 without a seal element, an O-ring squeeze outside 8-30 % or a septum compression outside 10-20 % is a FAIL.

**Channels (review item 10):** SLA cleaning limit [ASM]: channels of at least 0.5-0.6 mm that are open at an end and have L/D <= 6 can be flushed with IPA from a syringe; blind or long ones cannot. The main path is therefore d0.6 with the longest straight run 3.15 mm (L/D 5.3, both ends open: port side and valve pocket) to keep the prime path at 0.50 U; the fill branch (not in the prime path, filled by the draw) is **d0.8, 3 straight legs of 2.9 / 2.6 / 6.7 mm** instead of d0.7 / 9.9 mm / 1.05 mm air pocket. It is still 11 mm with two turns: flush it from the septum cavity and the junction and weigh the cap before and after to prove it is empty (bench step); a drilled or open-face-plus-gasket cap is the robust alternative (Rev B).

## 3. Risks
* mu_seal and the breakaway factor are assumptions; an unoiled or dried-out bead (mu 0.4-0.9) is 2-4x over budget. Re-oil before every test series.
* **Eccentric push**: jam at mu_g >= 0.30 (dry resin flange). Mitigation applied: tape recess + PTFE tape + oil. **Recommended next change (not applied, touches the carriage/slot of round 2): push at the plunger centre** with a 1.2 x 1.4 mm stainless blade (about 155 MPa at 5 N, 0.04 mm deflection) through a slot 0.6 mm longer, which removes the cocking factor (x1.5 -> 1.0).
* Cast tolerance: printed cavity +-0.05 mm is of the order of the squeeze (0.064 mm diametral for S2); measure the cast OD, keep S1/T as fall-backs.
* Tape seam and creep (option). Silicone oil swells PDMS slightly (lowers Shore) and migrates; bench only.
* Plunger core in SLA only (PA12 MJF +-0.1 mm would touch the bore at 0.1 clearance); sand/ream the core to slide freely in the CNC bore before casting.
* Bubble in the duckbill cavity (2.9 mm3) can still exceed the 0.5 U target if the real valve is bigger; measure by weighing.
* Homing by stall presses the core front against the PP end face at up to the stall thrust: fine for water tests, add a stall-current threshold in the firmware.

## 4. Bench tests
1. **Seal pull test** (plunger + cast seal in a bore coupon or the real CNC reservoir, hanging digital scale 0.1 g resolution or a luggage scale and a slow hand pull at 5 mm/min, or a spring scale on the carriage): kinetic and breakaway, dry / water-wetted / oil-filmed, dwell 1 min / 1 h / 24 h, S1/S2/T, with and without PTFE tape, 5 pulls each. Accept: kinetic <= 1.5 N and breakaway <= 2.5 N.
2. **Core only** (no silicone): drag with oil and tape/bare, to separate guide friction (cocking) from seal friction; also tilt the plunger by pushing at the socket with the real shim.
3. **Leak**: closed outlet, syringe pressure gauge or a water column: hold 30 kPa 10 min on the front side (occlusion) and 40 kPa vacuum 10 min (draw), no drip / no air; repeat after 24 h dwell and after 50 strokes.
4. **Dead volume**: weigh water to the first drop at the needle (prime), weigh the deliverable volume of a full stroke vs the calculation, photograph a coloured-water fill with the outlet up and down, look for trapped bubbles at the plunger face.
5. **Cast OD and squeeze** with calipers on 3 casts per variant before the pull test; compare with 16.09 / 16.12 / 16.11 mm.
6. **Stall homing**: motor current vs position when the core meets the end face; confirm the dead layer is closed (no air film).
