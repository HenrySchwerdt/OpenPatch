> **TEST ONLY - NOT FOR HUMAN USE** (see `../../DISCLAIMER.md`). Water only, bench only, never worn, never filled with insulin.

# Challenge review of the v0.1.0 cup pod (OP-100), 2026-11-24

This is an independent, skeptical review. Nothing in `mechanical/` or `electronics/` was changed. The review was done against `main` at 360a48f plus the uncommitted working tree.

**Inputs:** `params.json -> cup`, `op_cup.py`, `op_cup_dock.py`, `op_cup_asm.py`, `cup_check.py`, `cup_packing.py`, `out/v010-cup/OP-100.mech.json`, the renders, the STLs, `V010-CUP.md`, `ASSEMBLY-CUP.md`, `cannula-measurement.md`, `docs/STATUS.md`, `docs/BUY-LIST.md`, `docs/PARTS-LOCK.md`, `spec/design-parameters.md`, and the cup board docs (PART-AUDIT, FIT-CHECK, PREORDER-REVIEW, `cupgeom.py`, `placement.json`).

**Frame:** pod frame (x = 0 at the motor end, y = 0 at the tank-side wall, z = 0 at the skin side). Units are mm. Volumes are in U, where 1 U = 10 µl.

**Probing:** two claims were checked by ray-casting the exported STLs with a pure-Python point-in-solid test (script in the session scratchpad, not committed): the blocked fill channel and the open seam at the pocket face. The other numbers below are analytic, taken from `geometry()` and `mech.json`.

## 0. Key numbers of the current OP-100 (from `OP-100.mech.json`)

* **Envelope:** 47.96 x 36.6 x 8.5 = 14.92 ml. The tank holds 1.00 ml, which is **6.7 %** of the envelope.
* **Lane 1 stack along x (length-setting):**

| Segment | x range | Length |
|---|---|---|
| Wall | 0 - 0.9 | 0.9 |
| Motor column (axis Y, xc 4.47) | 1.47 - 7.47 | 6.0 (incl. 0.47 corner_clear) |
| Gear B / magnet | 4.43 - 7.79 | |
| Gap, bush, gap, collar | 7.84 - 9.89 | |
| clr_tank | to the tank dry rim 10.17 | 0.28 |
| Tank (closed stadium) | 10.17 - 35.11 | 24.94 |
| Gap to the pocket face | 35.11 - 35.16 | 0.05 |
| Dock pocket | 35.16 - 47.06 | 11.90 |
| End wall / lintel | 47.06 - 47.96 | 0.9 |

* **Tank length:** `tank_len = dry_in 0.4 + L_pl + s + dead 0.02 + end_wall 2.5`, with `L_pl = 3.2 + s` (cup plunger, rod fixed axially). So **tank_len = 6.12 + 2 s** and **lane 1 = 29.14 + 2 s**.
  * Every 1 mm of stroke costs 2 mm of length. This is inherent to a fixed rod screwing into a cup.
  * Bore 20.5 x 5.5, area 106.26 mm². So **1 mm of stroke = 10.6 U**, and **1 mm of lane-1 length = 5.3 U**.
* **Lane 2 minimum length:** `xc + 4.9 + cell 31.5 + 3.1 + wall 0.9` = **44.87**. Lane 2 has 3.09 mm of slack today.
* **Value of each direction (at the current stroke 9.41):**

| Direction | Gain |
|---|---|
| +0.1 mm bore height | +1.81 mm² = **+1.7 U** |
| +0.1 mm bore width | +0.55 mm² = +0.5 U |
| +1 mm lane-1 length | +5.3 U |

Height is the most valuable direction, 3x better than width and better per mm than length. It is also completely used up: the tank fills z 0.9-7.6, the whole cavity.

---

## 1. Owner question 1: "If the cannula-adapter pocket were not so deep, could the tank be bigger?"

**Short answer: not through its depth (height). Partly through its length, and there 3.5 mm are redundant today.**

### 1a. Pocket height (z 0-4.4, roof to 4.9) costs the tank nothing

The tank has a constant stadium section and already fills the full cavity height (z 0.9-7.6) over its whole length (x 10.17-35.11). The pocket sits **after** the tank along x (x 35.16-47.06), not beside it or under it. A shallower pocket frees height only above the dock, where a constant-section tank cannot reach.

The space above the pocket (z 4.9-7.6, about 300 mm³) is already mostly empty: only the 3 mm wide dock leg of the board with the dock hall U4A is there.

**What drives the height:** dome height B = 4.2 + 0.2 clearance, plus a 0.5 roof.

* **B = 4.2 is a guess.** It was scaled from photos by proportion (`cup.dock.head`, "TODO-MEASURE"). Nothing on the head has been measured.
* The measurement sheet `cannula-measurement.md` still carries B = 5.0 as its placeholder. If the real dome is 5.0, the roof moves to z 5.2-5.7 and **hits the board underside (z 5.3) and the dock hall (z 4.9-5.3)**.

So the pocket height matters for the **board**, not for the tank.

A lower pocket would also **weaken** the dock hall signal: the gap from the magnet top to the hall would grow, and B falls with 1/z³. To keep the signal, the dock magnet would have to be raised.

### 1b. Pocket length along x (11.9) costs 5.3 U per mm, or 1 mm of pod length per mm

The length is built as 0.2 clearance + **dome A 8.0 (guessed)** + **3.5 slide reserve** + 0.2 clearance.

* **A = 8.0 is a photo estimate.** The measurement sheet placeholder is 10.0. If the real dome is 10.0, the pocket grows by 2.0 mm and OP-100 goes to 49.96 mm, or the tank loses 10.6 U. **Measuring the Insight Flex head (A, B, C, base J/K, latch) is the precondition for every dock change.** None of the letters A-P is measured. Everything in `cup.dock.head` is an estimate.
* **The 3.5 mm slide reserve inside the pod is redundant since the end was opened (2026-11-24).** The reserve exists so the pod can be lowered over the dome with the dome 3.5 mm away from the needle. With the open +X end (U-slot 9.8 x 4.4, lintel at z 4.4-5.0 above the 4.2 dome), the dome can sit outside the end face in that pre-slide position. That works both for sliding in from the end and for lowering and then sliding. The latched dome needs only x 35.36-43.36, and the base plate (9 x 9) may stick out of the open end.
  * Minimal pocket = 0.2 + A + 0.2 = **8.4** (instead of 11.9): **-3.5 mm**.
* What the pocket length competes with: nothing in lane 1 except the tank. Lane 2 sets a floor of 44.87, so a shorter pocket buys at most -3.09 mm of pod length. Beyond that the freed length can only go into the tank.

### 1c. What actually blocks a longer tank

1. **The dock pocket in series** (11.9 mm, of which 3.5 is redundant).
2. The **rear drive stack:** motor column 6.0 + 0.47 legacy corner offset, gear B, bush, collar, clr_tank (10.17 to the tank rim). About 1.3 mm of this is margin.
3. **The 2:1 stroke law of the cup plunger.** It is unavoidable with one fixed rod. A translating rod would need about s - 4.5 mm of tail behind gear B, out through the rear wall, so it only nets about -4.5 mm whatever the size, at high risk (magnet and angle sensing must move to gear B). Not recommended.

The walls are not the blocker in x, only in z.

**The tank is also tied to the board.** The tank front face fixes `x_bf`, which fixes the dock hall position (39.36, 11.75) and board screw E (`x_bf + 2.24` = 37.40). Moving the tank front therefore moves board items. The SW1 move (H8) already forces a board revision, so that is the moment to bundle the changes below.

### 1d. Maximum tank volume for OP-100 at the current outer size (47.96 x 36.6 x 8.5)

| Scenario | Board change | Stroke | Volume |
|---|---|---|---|
| Today | | 9.41 | **100 U** |
| A: margins only (§3 #3); tank front x_t0 stays, so the hall and screw E stay | none | 10.0 | **106 U** |
| A + front wall 2.5 -> 2.0 (septum moved, §3 #11) | none | 10.25 | 109 U |
| B: A + minimal pocket 8.4, dock moved +3.1 to the end | yes: dock leg, hall, screw E +3.1 | 11.55 | **123 U** |
| B + floor/roof 0.9 -> 0.7 over lane 1 (bore 20.5 x 5.9, §3 #9) | yes | 11.55 | **131 U** |
| B + tank wall 0.6 -> 0.5 (bore 20.7 x 6.1) | yes | 11.55 | 137 U |
| (B + lane2_extra 2.0 given back to the tank, bore 22.5 x 5.9) | kills the board routing room: not recommended | 11.85 | 148 U |
| C (Rev B architecture): dock under the board in lane 2, shorter cell (about 20 mm, 301020 class, not sourced), tank runs to the east wall | everything | 15.4 | **about 163 U** |

**Alternatives for where the dock goes:**

* **Dock under the board lane (C):** frees 11.95 mm of lane 1 for the tank, which is +63 U at the same size. At 100 U it gives about 42.7 mm (set by lane 2: wire channel + 20 mm cell + dock).
  * Cost: a tube from the tank outlet (east end of lane 1) back to a needle hub in lane 2 (about 28 mm, dead volume about 0.14 U with ID 0.25), a smaller cell (about 40 mAh, still more than 8 days), and a new board outline.
  * Rev B only.
* **Pocket shorter (B):** see §3 #2. With the pod length kept, it gives +18.6 U. With 100 U kept, the pod gets shorter instead.
* **Slide shorter (3.5 -> 3.0):** 0.5 mm, +2.7 U. Irrelevant once the reserve is out of the pod (#2), because the slide then happens outside the end face.

---

## 2. Owner question 2: "Is everything inside really needed exactly as planned?"

### 2a. The packing check is masked by reservation boxes that contain nothing

`cup_packing.py` marks every `ko_*` box as occupied. Several of them are empty leftovers of the multi-board era. The PART-AUDIT itself says the side_a foot is gone and the board outline (`cupgeom.OUTLINE_POD_BOARD`) ends at y 10.4.

| Empty or nearly empty space | Box | Volume |
|---|---|---|
| `ko_side_a` | x 35.16-44.16, y 1.0-6.35, z 1-7.5 | **313 mm³, empty** |
| `ko_io` (rear corner of lane 1) | x 4.0-9.97, y 1.0-7.25 | **243 mm³, empty** (button, LED, buzzer and charger all moved to the main board) |
| Above the dock pocket | z 4.9-7.6 | about 300 mm³ (only the 3 x 6.75 dock leg) |
| `ko_side_b` below the board tab | z 1-3.3, except boss E | about 140 mm³ |
| Lane-2 east end | x 40.97-47.06, y 22.8-35.6, z 0.9-5.3 | about 340 mm³ (2 ledges only) |
| Lane-2 routing strip beside the cell | y 33.4-35.6 below z 4.1 | about 220 mm³ |
| `ko_dock_board` | 6 x 6 x 0.6 | the real leg is x 37.9-40.9, y 10.4-17.15 (3.0 wide) |

**About 1.5 ml of empty volume, more than the 1.0 ml of water.**

With honest keep-outs, `cup_packing` would **FAIL**: side_a alone is an empty 9.0 x 5.35 full-height rectangle, more than 4 x 4. None of this space can become tank volume (the tank section is constant). It is only usable for the vent, the guard, or by making the pod shorter (#2).

### 2b. Every body

**Legend:** K = keep, S = shrink or change, R = remove.

#### Tank and drive

| Body | Function | Needed? | Minimal? | Without it | Simpler / smaller | Verdict |
|---|---|---|---|---|---|---|
| `reservoir` (CNC PP, outer 21.7 x 6.7 x 24.94, wall 0.6, front wall 2.5) | Water volume, bore for the seal | yes | Wall 0.6 is backed by the shell (could be 0.5). The front wall 2.5 holds septum + hub and is close to minimal. **BUG: the fill channel does not reach the bore (0.1 mm web, see §4)** | | Bench water only: PARTS-LOCK #6 allows an SLA tank. Not integrated into the shell (the bore finish needs one part) | **S** (fix channel; wall 0.5 optional) |
| `plunger_core` (20.3 x 5.3 x 12.61, cup) | Carries the seals and the nut; the rod stays dry | yes | Length = s + 3.2, of which 1.2 is margin: tip_clear_full 0.4, tip_in_nut_empty 0.5, front_wall 0.9 | No pump | -0.5 by tip_clear 0.2 + tip_in_nut 0.2 | **S** |
| `seal_a`, `seal_b` (two cast beads) | Sealing | one yes, two questionable | The seal study activates **S2 = single front bead** (`seal.active_variant`, rings ["b"]). The twin bead "T" is 1.7x the friction and "above the budget". The cup CAD carries both rings, yet `cup_check.thrust` uses 1.6 N (single-bead class) | One bead fewer = about -40 % friction | Drop `ring_front_a` (keep the groove as an option) or budget about 3.4 N seal friction | **S** (decide; see thrust) |
| `nut` (DIN 934 M1.6 brass AF 3.5 h 1.3) | Converts rotation to translation | yes | Yes; hex wall 0.57 | | | K |
| `rod` (M1.6 x 16.45) | Screw | yes | Yes | | Brass rod (non-magnetic behind the angle magnet; eta 0.185 instead of 0.2) | K |
| `thrust_collar` (tube 2.5 x 0.45, 1.0 long, bonded) | Forward-thrust stop | yes | 1.0 -> 0.7 is enough (bond 3.5 mm² -> 2.5 MPa at 8.6 N) | Forward thrust has no stop | **Its friction on the bush (r about 1.05) is missing from the thrust model**, see §4. Add a 0.1 PTFE shim or grease | **S** |
| `bush_rod` (3 x 1.0 bonded in the U rib) | Thrust bearing, both directions | yes | Rib bending 28 MPa (marginal) | | | K |
| `gear_a`, `gear_b` (m0.3 z12 miter 1:1) | 90 degree transfer, height-neutral | yes (only height-neutral option; the analysis stands) | Gear A is faced; gear B as delivered | | | K |
| `magnet` (d2 x 1 diametric on gear B) + `hall_tmag` + `ko_tmag_board` (rear strip) | Per-revolution angle, occlusion by angle shortfall | yes (study: 0.3 mT at the board, not usable) | **Costs no tank length**: the strip sits beside the magnet in the rear corner, in the motor column's x range | | Flex tail of the main board instead of 4 hand-soldered wires (assembly, not volume) | K |
| `motor` + `gearhead`, `motor_boss`, `motor_shaft`, `motor_rear_boss`, `motor_term` (NFP-608-26.45, transverse) | Drive | yes | Transverse is the shortest option: 6.0 mm of x instead of 17.6 axially. Its 21.1 mm y reach is not the width driver (lane 2 is: limit 27.2 vs 21.7 used). **But xc carries a 0.47 mm legacy offset**: `geometry()` references the corner of the old 34.6 width (`W_x = W - lane2_extra`); against the real 36.6 corner `corner_clear` = 0 | | -0.47 length when the board west items move with it | **S** (0.47) |

#### Lane 2 and electronics

| Body | Function | Needed? | Minimal? | Without it | Simpler / smaller | Verdict |
|---|---|---|---|---|---|---|
| `ko_battery` (301030, 31.5 x 10.6 x 3.2) | Energy | yes | 60-90 mAh vs a need of about 7 mAh/48 h: 8-12x oversized in capacity, but the cell length sets lane 2 = 44.87 | | 301020 class (about 20 mm) would shorten lane 2 by about 10 mm (only useful with the dock in lane 2, scenario C) | K (Rev B: S) |
| `ko_board` (6-layer, x 7.8-43.4, y 22.9-35.5) + `ko_board_tab` | Electronics | yes | `lane2_extra` 2.0 is empty under the board beside the cell (routing room, owner decision) | | | K |
| Board east tab (`cupgeom`, x 43.4-46.5, y 17.15-22.5; U33, QBA, RDA at pod x 44.8-44.9) | Extra routing room | movable | It is the part that stops the pod from shrinking below 47.7 | | Pull it back to x <= 43.67 in the H8 board revision | **S** |
| `ko_side_b` (x 35.16-46.76, y 17.15-22.5) | Board tab + sounder BZ1 (bottom, 2 mm) + screw E | yes | Box much larger than its content | | Shrink to the real tab outline | **S** |
| `ko_side_a` | Was: side button / J1 foot | **no** (empty) | | Nothing | | **R** (box) |
| `ko_io` | Was: button, LED, buzzer, charger strip | **no** (empty) | | Nothing | Use for nothing, or for the vent membrane | **R** (box) |
| `ko_aux` (antenna clearance x 43.5-44.4) | Antenna keep-out | yes, as a copper-free zone; plastic is fine | | | | K |
| `ko_dock_board` (6 x 6) + `hall_dock` (U4A) | Dock interlock (spec §7, H15) | yes | Box 2x the real leg | | Shrink to x 37.9-40.9, y 10.4-17.15 | S (box) |
| `ko_usb` + USB-C receptacle | Charge + DFU | yes | Mouth 1.1 mm inside the outer face (see §4) | | | K |
| Wire channel x 7.5-9.37 | Motor 4 + cell 2 + strip wires | yes | 1.87 wide | | | K |

#### Housing features

| Body | Function | Needed? | Minimal? | Without it | Simpler / smaller | Verdict |
|---|---|---|---|---|---|---|
| Board screw bosses W, E (d1.8) | Board retention, USB plug forces | yes | | | | K |
| Ledges x 2 + wall shelf | 3-point board support (USB-C insertion force) | yes | | Board flexes when the plug goes in | | K |
| Lid hold-down ribs x 3 | Board lift limit (the 2 screws already hold it) | marginal | | Little | Could go; cheap, keep | K |
| Corner posts x 3 + M1.2 lid screws | Lid clamp on the rim | yes | | | | K (the NE post must move if the pod shrinks, #2) |
| Rim band, groove 0.45, tongue 0.13, `lid_gasket` (cast ring 0.32 x 0.4) | Shell seal | yes for a sealed shell | Thin spots 0.15-0.225 (SLA only) | | | K |
| Motor saddles x 2, pin pocket, floor groove (old "FPC groove", now a wire groove) | Motor retention | yes | | | | K |
| Tank stop blocks x 2 | Axial datum of the tank (rear) | yes | | | | K |
| Battery tray (0.4 recess) | Cell location / swell | yes | Only 0.5 of floor below it; with a 0.7 floor (#9) it must go | | | K / S with #9 |
| U rib for the bush | Thrust path | yes | Rib = bush length; bending marginal | | | K |

#### Dock

| Body | Function | Needed? | Minimal? | Without it | Simpler / smaller | Verdict |
|---|---|---|---|---|---|---|
| Dock pocket (11.9 x 9.8 x 4.4, roof 0.5, walls 0.4, anchor blocks, lintel, chamfers) | Head interface | yes | **3.5 mm reserve redundant** with the open end; every head dimension is guessed | | Pocket 8.4 long (#2) | **S** |
| `dock_clip` (2 L-springs 301 FH 0.1, arm 7.55) | Latch | yes | With an 8.4 pocket the arm becomes 4.46: 0.1 sheet -> 1003 MPa (too high); **0.05 sheet -> 501 MPa, 0.11 N per spring** | Head falls out | | **S** |
| `needle` 30G + `needle_hub` (tube 1.5 x 0.2, ID 1.1) | Fluid path into the head | yes | **The 0.31 needle bonded in a 1.1 bore is not centred (+-0.4)** | | Fill the hub with a centring sleeve (e.g. 0.6/0.32) or a printed bush; or press the needle directly into a d0.30 printed bore | **S** (centring) |
| `needle_guard` + spring (0.27 N/mm, **not a catalogue part**) | Covers the tip when undocked | useful (finger prick, needle protection) | | Exposed tip recessed about 2.6 mm in the pocket | A **silicone tube sleeve** (e.g. 0.3 ID) that buckles or compresses as guard and spring in one part, or a fixed guard + recessed tip (bench only) | **S** (remove the non-catalogue spring) |
| `hub_gasket` (flat ring 2.5/3.3 x 0.5) | Seals around the hub at the tank face | **the wrong seal**: the real leak path is the 0.05 mm seam around the whole pocket mouth (§4) | | | Replace with a frame gasket over the full tank-face / pocket perimeter, or bond the tank face to the pocket walls with silicone | **S** |
| `septum` (d1.6 x 1.0 in d1.7) | Fill port | yes | PARTS-LOCK #18 still says Ø4 x 2 (stale) | | | K |
| `cannula_adapter`, `dock_magnet` | Test fixture (dummy head), not a pod part | (fixture) | | | | K |

#### Seals and button

| Body | Function | Needed? | Minimal? | Without it | Simpler / smaller | Verdict |
|---|---|---|---|---|---|---|
| `usb_gasket` (stadium frame 0.4) | Seals the USB-C opening and carries the rim seal across | yes for a sealed shell | | | | K |
| `button_cap` + `button_oring` | Side button | yes | Key face recessed 0.2, stroke 0.30, more after the SW1 move (§4) | | Flush key face | **S** |
| Vent (d0.8 + ePTFE, `cup.vent`) | Pressure equalisation | **yes, but not built** (`ASSEMBLY-CUP.md`: "no vent") | | Vacuum at empty, see §4 | Put it hidden in the pocket side wall into the empty side_a space (clean top kept) | **ADD** |

---

## 3. Ranked changes (gain vs risk)

Packages:

* **A** = mechanics only, no board change.
* **B** = bundle with the board revision that H8 (SW1 0.45 mm) forces anyway.
* **C** = Rev B architecture.

| # | Change | Exact parameter / code | Expected result | Gain | Risk | Pkg |
|---|---|---|---|---|---|---|
| 1 | **Fix the blocked fill channel** (CAD bug, confirmed in the STL: solid PP at x 32.61-32.71 on the channel axis at y 7.75, z 2.2; the septum pocket starts at 32.66 and stays 0.05 from the bore) | `op_cup.py build_tank_and_plunger`: `t_fC` end `L["x_in"] + 0.1` -> `L["x_in"] - 0.1` (like `t_oA`). Add a connectivity probe to `cup_check` (bore <-> septum, bore <-> outlet). Regenerate `reservoir-cnc/` | The fill path works; the volume check does not catch this today | Function | none | A |
| 2 | **Take the 3.5 mm slide reserve out of the pod** (open end) + **measure the head first** | `op_cup_dock.layout`: `pocket_len = clr + A_dome_d + (0 if open_end else travel) + clr`; `plate_x` upper end to `x_end`. `cup.dock.clip.t` 0.1 -> **0.05** (arm 4.46: 501 MPa, 0.11 N per spring). `cup_check`: slide sweep from outside the end face, drop the "slide 3..4" budget for the in-pod part. Board: east tab x 46.5 -> **<= 43.67** (move U33, QBA, RDA), NE board corner cut (cavity arc R3.1 centre (40.87, 32.6): about 1.5 x 1.5 chamfer), NE lid post moved (e.g. to (43.0, 21.0) or through the board). Dock hall (39.36, 11.75) and screw E (37.40) **unchanged** | **OP-100 47.96 -> 44.87 x 36.6 x 8.5 (meets the 45 target), about 106 U** with #3 (lane 2 sets 44.87). Envelope 14.92 -> 13.96 ml. OP-200 66.78 -> about 62.4. Alternative: keep 47.96 and move the dock, hall and screw E +3.09: **about 121-123 U** | -3.09 mm or +18 U | medium: board edit, latch force 0.11 N, head dimensions unknown (A = 10 instead of 8 eats 2 mm of it) | B |
| 3 | **Remove the stacked micro-margins** (tank front x_t0 fixed, so the board is unchanged) | `cup.plunger.dry_in` 0.4 -> 0.2, `tip_clear_full` 0.4 -> 0.2, `tip_in_nut_empty` 0.5 -> 0.2, `cup.gears.clr_tank` 0.28 -> 0.10, `cup.collar.len` 1.0 -> 0.7 | Tank 24.94 -> 25.42 inner use, stroke 9.41 -> **10.0, 106 U** at the same size (or -1.18 mm at 100 U once #2 is done) | +6 U | low (nut engagement stays 1.3 mm, collar bond 2.5 MPa) | A |
| 4 | **Correct the thrust model and add lubrication + a low-friction collar face** | `cup_check.thrust`: add the collar friction torque `mu_c * F * r_c` (r_c about 1.05, collar 2.5 vs bush ID 1.7) and the reverse hub face. `cup.rod.eta_screw` per lubricant. ASSEMBLY: grease the thread + a PTFE shim 0.1 at the collar (or grease) | Today's 8.6 N is **only about 5.5 N** with a dry brass collar (mu_c 0.15) and **4.9 N at 0.2**, below the 5.2 N need (1.05x / 0.94x, not 1.65x). With grease (thread mu 0.15 -> eta 0.3) + PTFE shim (mu 0.08): **8.9 N, 1.7x** | Pumps at all | low | A |
| 5 | **Decide the shell sealing: add the vent, close the pocket seam** | STL probe: the housing pocket walls and roof start at x 35.16, the tank face at 35.11: a **0.05 mm open seam around the whole pocket mouth** (about 20 mm long) joins the dock pocket (outside) to the pod interior. The `hub_gasket` seals only around the hub. Either (a) frame gasket / silicone bond around the tank front face, **plus** (b) build `cup.vent` d0.8 + ePTFE as a hidden hole from the pocket side wall into side_a. Without (b) a sealed pod reaches **-16 kPa at empty** (about 5.2 ml air + 1.0 ml): **+1.7 N** on the plunger (need 5.2 -> 6.9 N) | A sealed shell that still pumps | Function | low | A |
| 6 | **One seal bead (S2) or budget two** | Drop `cup.plunger.ring_front_a` (`seal_a`), or set the seal force in `thrust()` to twin-bead about 1.7x | Need 5.2 N (single) vs about 6.6 N (twin) | about -1.4 N | low-medium (redundancy; bench decides) | A |
| 7 | **Delete leftover keep-outs, size the others to the real board** | `op_cup.build_electronics_boxes`: drop `ko_side_a`, `ko_io` (and from `KEEPOUT`, `ORDER`); `L["side_b"]`, `L["dock_board"]` from `cupgeom.OUTLINE_POD_BOARD` | `cup_packing` then reports the truth (it FAILs on side_a 9.0 x 5.35, about 1.5 ml empty in total); the check must then accept "empty but not convertible to tank" zones explicitly | Honesty, design freedom | none | A |
| 8 | **Remove the 0.47 mm legacy corner offset of the motor column** | `op_cup.geometry`: `W_x = W` (not `W - lane2_extra`) | xc 4.47 -> 4.00; lane 1 and lane 2 both -0.47: OP-100 with #2 about **44.4** (or +2.5 U). Board: west edge 7.8 -> 7.33, screw W 8.9 -> 8.43, saddle and wire channel -0.47 | -0.47 mm | medium (board edit) | B |
| 9 | **Floor and roof 0.9 -> 0.7 over the tank** (side walls stay 0.9 for the groove) | New `cup.floor` / `cup.roof` 0.7 (today `shell.wall`); `cup.reservoir.bore_h` 5.5 -> **5.9**; drop or flatten the 0.4 battery tray; check the R1.8 fillet wall | Area 106.3 -> 113.5 mm² (+6.8 %): stroke for 100 U 9.41 -> 8.81 = **-1.2 mm**, or **+6.8 U** at the same length. Note: z changes (cell, board z 5.3, hall, USB-C z 5.7) shift by -0.2 unless kept at absolute z: board side to confirm | +7 U / -1.2 mm | medium (SLA stiffness of a 0.7 roof over about 34 mm, z-interface) | B |
| 10 | **Tank wall 0.6 -> 0.5** | `cup.reservoir.wall` 0.5 | Bore 20.7 x 5.7 (or 6.1 with #9): about +4 to 5 U | +5 U | medium (CNC thin wall; it is backed by the shell) | A |
| 11 | **Front wall 2.5 -> 2.0** (septum moved beside the hub instead of behind it) | `cup.reservoir.end_wall` 2.0, `cup.fill.septum_dy`, the `x_s` formula | +0.25 stroke = +2.7 U | +2.7 U | medium-high (the septum pocket is already 0.05 from the bore) | A |
| 12 | **Guard spring -> silicone tube sleeve; needle centring sleeve in the hub** | `cup.dock.guard` (spring_N removed, sleeve part), `cup.dock.hub` + inner sleeve | Removes a non-catalogue part; needle on axis +-0.05 instead of +-0.4 | Buildability | low | A |
| 13 | **Button cap after the SW1 move** | `cup.button.face_recess` 0.2 -> **0.0**, `pad.face_y` 35.4 -> **35.37** once the tip is at 35.20-35.32 | Rest gap 0.05-0.17, stroke 0.30-0.42 from a flush key (today: key face 0.53-0.65 below the surface in a d1.75 hole, which a fingertip cannot reach) | Usability | low | A |
| 14 | **Dock under the board in lane 2 + shorter cell** | Architecture (layout, board outline, tank outlet tube) | **About 163 U at 47.96, or about 42.7 mm at 100 U** | Large | high | C |

Not recommended:

* Translating rod (net -4.5 mm, magnet relocation).
* Cord seal (+2 mm width and length).
* Bore width from `lane2_extra` (kills the board routing).
* Motor beside the tank, or a worm (analysis in V010-CUP stands).
* Dropping the TMAG strip (0.3 mT).

---

## 4. Sanity of function

* **Thrust:** **not 1.65x.** The model ignores the collar sliding on the bush. Rod torque 2.39 N mm = F x (p / 2 pi eta + mu_c r_c).
  * With eta 0.2 and a dry collar (mu_c 0.15-0.2): **4.9-5.5 N vs 5.2 N needed.**
  * With two seal beads (the CAD) the need rises to about 6.6 N.
  * With a sealed, unvented shell, +1.7 N more at empty.
  * Worst case about 8.3 N needed against 4.9 N available: **it would stall.** Fix: #4 + #5 + #6.
  * Bench item: run the thrust test with the lid on and the seam sealed.
* **Plunger reaches the front wall:** yes, 0.02 gap at empty (`x_pf_empty` 32.593, `x_in` 32.613). The front wall is the hard stop; firmware sees an angle shortfall. The front bead (0.51-1.11 from the plunger face) stays in the bore.
* **Fill septum reachable:** from below with the pod upside down, yes: floor hole d1.7 at (33.51, 7.75), inside the Velcro footprint. It is 0.1 mm outside the dock window in x (H14 passes narrowly).
  * **But the fill path is blocked in the CAD** (#1, STL-confirmed: the channel ends 0.1 mm short of the bore, and the septum pocket is 0.05 mm from the bore).
  * Target size d1.6 under a d1.7 hole: add a 45 degree lead-in on the floor hole.
* **Needle vs head septum after the 3.5 slide:** nominally coaxial (needle axis y 11.75 = dome centre, z 2.6 = estimated septum axis).
  * Capture: recess d3.0 vs guard OD 1.4, so +-0.8. Lateral guidance: base plate 9.0 in a 9.8 pocket (+-0.4) plus the springs.
  * Unknowns: the real septum height (sheet placeholder C = 3.0 vs CAD 2.6: 0.4 offset, still inside the +-0.8) and the needle off-centre in the hub (+-0.4, #12). Worst-case stack 0.4 + 0.4 + 0.4 = 1.2 > 0.8: **can miss**. Measure C and centre the needle.
  * The latch geometry (side notches at z 1.9-3.3) is invented; the measurement sheet describes the hooks gripping **behind** the dome (G = 3.2 behind the centre).
* **USB-C:** centred (receptacle x 23.5 / z 5.7 = opening centre; JU1 at pod x 23.5 on the board north edge 35.5). Opening 9.0 x 3.4 vs mouth 8.94 x 3.26: 0.03 / 0.07 per side.
  * Risk: the mouth sits **1.1 mm behind the outer face**, and a standard overmold (about 12 x 6.5) cannot enter a 9.0 x 3.4 opening, so the plug inserts at most about 1.1 mm less than full mating. **VERIFY with a real cable on the 1:1 print before the board order.**
  * Mitigation: thin the wall locally around the opening to about 0.5 from outside (10.6 x 5.0 counterbore), which recovers 0.4.
* **Button cap vs SW1:** after the board move (SW1 0.45 back, tip y 35.20-35.32) the cap pad (face 35.4) has a 0.08-0.20 rest gap, so the stroke to actuate is 0.33-0.45 against the designed 0.30, in z OK (pad z 6.35-7.05 covers the actuator at about 6.7).
  * With the key face 0.2 below the surface, the user must push 0.53-0.65 deep into a d1.75 hole: fingernail or tool only. #13 fixes it. The flange at 0.42 travel reaches y 35.08: SW1 body face must be < 35.08 (VERIFY, ALPS drawing).
  * Until the board actually moves SW1, the tip at 35.65-35.77 **pre-loads the switch (pressed permanently)**.
* **Other drift found:**
  * PARTS-LOCK rows #4 (A2 rod vs zinc-plated steel), #7 (Ø3 x 1.5 magnet vs d2 x 1), #12 (STSPIN220 vs DRV8838) and #18 (septum Ø4 x 2 vs d1.6 x 1.0) contradict the CAD.
  * The 2:1 print files in `mechanical/print/OP-100_x2/` are from the old geometry (STATUS says so).

---

## 5. Recommended order

1. #1 fill channel, #4 thrust model + lubrication, #5 vent + seam, #6 seal decision. These are mechanics only and fix functional errors.
2. Measure the Insight Flex head (A, B, C, J/K, latch). Without it, #2 and the whole pocket are guesswork worth +-2 mm / +-10 U.
3. #3 micro-margins (+6 U, no board change) and #7 honest keep-outs.
4. With the H8 board revision: #2 (tab cut, NE corner, NE post) + #8. This gives **OP-100 about 44.4-44.9 mm at 104-106 U**, meeting the 45 mm target. Alternatively, at 47.96 mm, about 121-123 U.
5. Rev B: #9 / #10 (height), #14 (dock in lane 2).
