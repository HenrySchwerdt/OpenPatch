# OpenPatch Rev A - assembly sequence (no soldering iron)

EXPERIMENTAL DIY bench build, water only. Not a medical device. Never connect to a person.

Tools: **tweezers, small screwdriver (PH000 / 1.5 mm slotted), UV lamp** (needle fallback only), a 4 mm biopsy punch
(septum), a sharp razor blade. Optional: a 1.0 mm / 2.0 mm / 0.5 mm drill in a pin vise to clean printed bores,
a deburring tool. No soldering, no glue (exception: UV adhesive drop on the needle hub if it weeps; cyanoacrylate
drop for the magnet if the friction fit is loose).

All coordinates refer to `out/OP-xx.layout.json` (X = length, Y = width, Z = up, Z = 0 at the skin side).
Everything described as "contact" is defined there under `contacts`.

## 0. Preparation / incoming inspection (15 min)

1. Wash printed parts, blow out all bores (needle bore 0.5, bearing bores 3.05, pilot holes 1.0, hub seat 2.0).
2. Test-fit: the carriage nut pocket (hex AF 3.8 = DIN 934 M1.6 AF 3.2 + 0.6 clearance, closed at the rear by a 0.45 mm wall, 0.3 mm radial float) takes the M1.6 nut dropped in from the top slot; M1.6 rod runs through both bearing
   bores and the carriage (dia 1.9) without binding; plunger core slides in the reservoir bore (0.2 mm per side).
3. Cut the M1.6 rod (DIN 976, stainless) to length: **OP-70 21.0 mm, OP-100 25.0 mm, OP-200 38.5 mm** (rod x range in `mech.json -> thrust.rod_x`: rear end
   about x 1.65 inside the dry bush, front end = `screw_tip`). Deburr both ends.

## 1. Plunger and seal (water test)

1. Mix and cast the lip seals in `mould/` (core in the lower half, close, inject through the dia 0.7 sprues with a
   22G syringe until silicone leaves the dia 0.5 vents). Cure, demould, trim flash. Fit check: ring OD is
   bore + 0.3 mm.
2. Lubricate lightly with silicone oil.
3. Push the plunger core into the reservoir from the open (dry) end until the socket is at the slot.

## 2. Reservoir into the bottom shell

1. Place the reservoir in the bottom: it sits on the floor, its dry end open toward the gears.
2. Press the **fill septum** (dia 4 x 2 mm punched silicone) into the septum bore in the Y wall (`septum`
   position `x_s`, z = 2.9).
3. Press the **outlet needle** (30G blunt, 3 mm free length) into the PTFE/PEEK **hub**, then press the hub into
   the dia 2.0 seat in the cannula tower (from the pocket side, needle pointing down into the pocket). Check
   that the needle tip is 1.9 mm below the pocket ceiling (`z_tip`, TODO-MEASURE after the cannula is measured).

## 3. Drive train

1. **Thrust sleeve (2.05 mm, d2.0/d1.6)** on the rod, **gear B** (z20, GHW 753020, hub turned off) on the sleeve (Loctite 638, sleeve rear face 0.05 mm from the dry bush face), **gear A** (z16, GHW 390754 skimmed to 1.4 mm) onto the gearbox
   output shaft. Check mesh: centre distance 5.51 mm (floor trough + bush bore). The **front thrust collar** (d2.4 x 1.0) sits on the rod against the far bush face; the magnet goes behind it.
2. Slide the two PTFE/brass **bushings** into the bearing bores (dry end wall and wet-end block behind the reservoir).
3. Drop the **M1.6 nut** into the carriage pocket through the top slot (the closed rear and front walls retain it in both directions, no glue), drop the **carriage** onto the rail (rail groove down),
   engage the **stainless tongue shim** (glued into the carriage pocket) in the plunger socket through the reservoir slot.
4. Thread the rod through bushing, sleeve/gear, nut (turn it by hand), bushing, collar; glue the **diametric magnet (d3 x 1.5)** to the rod end face (x = `mag_x`, behind the collar, in front of the hall sensor).
5. Lay the **motor (16.1 mm body = gearbox 8.1 + motor 8.0)** in the floor trough of the Y = 28 lane, gear A meshes with gear B; its leads/FPC lie on the
   motor shelf (see 4).
6. Turn the rod by hand: the carriage must travel the full stroke without binding and without hitting the rail ends.

## 4. Battery and contact preload

1. **Motor terminals:** lay the 4-pad FPC (or the motor flex) on the **motor shelf** (`contacts.motor_shelf`, top at
   z = 3.9): pads at the `motor_fpc` positions (pitch 0.5 mm). Tweezers only.
2. **Battery:** drop the pouch cell into the pocket: against the rib at `bat_x0`, tabs folded flat on the cell top
   at `battery_tabs` positions (x = bat_x0 + 0.8, two pads at y = 21.0 / 22.9, pad 1.5 x 1.2, pad top z = 4.35).
   The rib gap at y = 17.3...20.3 is the tab/cable channel.
3. Spring contacts on the PCB bottom (<= 1.2 mm free height) will compress by 0.6 mm (battery tabs: PCB bottom 4.9 -
   pad top 4.35) and 0.9 mm (motor shelf: 4.9 - 4.0) when the PCB is held down.

## 5. PCB

1. Seat the PCB on the tower top and the two locating pins (dia 1.0 pins at tower top), around the dome of screw C
   (2.8 x 2.8 mm cut-out) and the magnet notch. Check that the hall sensors (`hall`, `drv5032`) sit 0.9 mm from the
   magnet end and the contacts land on the pads.
2. Coil: PCB-trace coil is part of the PCB. A separate coil (dia 17.6 x 0.6) is laid on the PCB top keep-out and
   later retained by the four lid tabs (it floats at z = 6.9 ... 7.5).

## 6. Closing

1. Place the **gasket** (0.5 mm silicone ring) on the bottom tongue (z = 5.5).
2. Lower the lid straight down; the lid tabs surround the coil, the two **hold-down pads** (lid underside, at
   `contacts.hold_down_pads`) push the PCB onto the spring contacts (one pad rests on the RF module top).
3. Drive the four **M1.2 x 6 screws** (3 at the dry end, 1 beside the board) until the lid skirt seats on the
   bottom (hard stop = gasket compressed to 0.45 mm, 25 %). Do not over-torque (PA12 thread-forming screws strip
   above ~0.1 N*m): stop when the head touches the counterbore.

## 7. Function check

1. Insert a charged cell / connect the charger on the coil pad; run the firmware self-test: motor moves, encoder
   (TMAG5273 + 2x DRV5032) counts one revolution per rod turn.
2. Fill the reservoir with water through the septum (use a 30G syringe needle), run the pump against a closed
   channel: occlusion must be detected; open channel: measure delivered volume by weight (1 mg = 1 ul = 0.1 U).
3. Calibrate the real gear ratio from the encoder (steps per magnet turn) and write it into the firmware.

## 8. Disassembly

Unscrew 4 screws, lift lid, lift PCB, then battery/motor/carriage out - everything is reusable except the lip seals,
gasket and septum. Re-use tolerance: bushings and the needle hub are friction fits; expect to replace them after 3-5
cycles.

---

# Bench pod assembly (Rev A bench split, spec 4a; NFP geared stepper, coaxial, spec 4)

EXPERIMENTAL bench test sample: **water only, never connect to a person.** The integrated sequence above (battery, main PCB, coil, Qi, gears) does **not** apply.
Files: `python3 generate.py --variant bench` -> `out/bench/` (`OP-xx.layout.json` = pod board layout, `OP-xx.mech.json` = full mechanical layout), upload package `out/bench/fab/`
(printed parts, mould, `dock-coupon/`). Refill: `REFILL.md` (automatic draw mode).

Tools: **tweezers, small screwdriver (PH000 / 1.5 mm slotted)**, 0.5 / 1.0 / 2.0 mm drills in a pin vise, deburring tool, cyanoacrylate (thread-locker 638 optional), 4 mm + 2 mm biopsy punches,
razor blade. **No soldering iron:** the pod sensor board arrives assembled (JLC PCBA); the motor keeps its factory lead with the JST 1.25 plug (soldered by the manufacturer).

Parts per pod: printed bottom, top, carriage, plunger core, cannula adapter, sleeve coupler, **end cap** (SLA); **CNC PP reservoir** (`fab/reservoir-cnc`; SLA copy for water); cast lip seals + gasket; NFP-608-26.45-SGM motor with lead; M1.6 leadscrew + M1.6 nut;
duckbill check valve (OD <= 3 mm); pod sensor board (OP-100, same for all sizes); magnets d2x1: spindle (diametric), dock (axial, goes into the adapter); 10-pin FFC cable; 30G needle with press-fit hub;
4 mm fill septum; M1.2 screws (4 x 6 mm lid, 1 x 4 mm board).

## B0. Dock fit test (once per cannula head design, before ordering pods)
Test-fit the printed `dock-coupon` to a spare cannula head as described in `cannula-measurement.md` and enter the winning values in `params.json`.

## B1. Incoming inspection (15 min)
1. Wash printed parts, blow out all bores: coupler bores (d2.04 D-bore, d1.64 M1.6), pilot holes d1.0 (lid posts, board boss), bearing bore 3.05, needle hub bore d2.0, valve bore d3.05.
2. Dock: flex each snap arm by hand 2 mm and release. Adapter: magnet pocket d2.1, septum bore d0.5, hose barb channel d0.7.
3. Motor: measure the shaft (d2.0 with D-flat 1.5), free shaft length and the pin block position on the real part; correct `drive_presets.nfp_608_26` if different, regenerate.

## B2. Plunger, seal, reservoir, end cap, carriage
Cast the lip seals in `mould/`, assemble plunger core + seals, push into the reservoir from the open end (sections 1-2 above). Press the **end cap** (d1.98 spigot) onto the d2.0 port of the closed end by hand until the cap block touches the reservoir end face; the fill septum plug (d4 x 2, punched) goes into the cap's side bore (access hole in the -Y shell wall). Carriage with the **fixed M1.6 nut** (press into the hex pocket).

## B3. Motor, gear pair, leadscrew (default side-by-side layout)
1. Lay the motor in its three cradles beside the lane (shaft toward the dry end wall). Press **gear A** (z16, GHW 390754, bore 2.0, skimmed to 1.4 mm) onto the D-shaft with one drop of Loctite 638 on the round bore; the flat leaves a 0.5 mm gap that the adhesive fills.
2. **Gear B** (z20, GHW 753020, bore 2.0, **hub turned off**) on a d2.0 x d1.6 sleeve (1.4 mm) pressed on the M1.6 rod end (Loctite 638), so it meshes with gear A (centre 5.51 mm; the floor trough and the screw bush bore fix it, the two lid pads hold the motor down without preload). The 0.25 mm floor relief and lid recess over gear B are intentional (tip OD 6.6). Do not glue the sleeve to the dry bush.
3. The factory lead (4 wires) hangs from the pins under the motor: lay it in the floor pocket under the terminal block and the 2.2 mm channel to the +X end wall, weave the wires between the three printed posts (strain relief), out through the end-wall slot.
   **Pins:** as delivered they point down (-Z); trim/bend the pin tips flat toward the rear (VERIFY) so the block sits in its floor pocket; never pull on the wires.
4. Thread the leadscrew through the dry bush (x = 0.9), the carriage nut and the far bearing; put the spindle magnet (diametric, d2 x 1) on the wet end. Turn it by hand: the carriage runs between the rear stop and the far block.
(Coaxial option, `bench.drive_layout=coaxial`: sleeve coupler on the shaft and screw, lead to the dry-end wall slot, see parts.md.)

## B4. Duckbill valve and needle
1. Drop the **duckbill valve** into the open slot of the end cap (flow direction toward the needle, i.e. toward +X), press it into the d2.9 bore (0.1 mm interference, silicone), then press the **valve plug** into the slot (flush with the cap top; closes the slot to the pod interior).
2. Needle in its hub (tip protruding 4.8 mm), hub into the bore of the guard tube from the dock mouth, until it bottoms. Check the tip position as in section B7 of the coupon notes.

## B5. Pod sensor board
1. Seat the board over the 2 locating pins and the support posts; the leg overhangs the dock channel. The TMAG5273 must sit under the spindle magnet end.
2. One **M1.2 x 4 screw** into the board boss. FFC cable into the ZIF connector (flip-lock), cable leaving toward the +X end wall.

## B6. Closing
Gasket on the bottom tongue, lower the lid (the hold-down pads touch the board, the FFC leaves through its slot, the fill window sits over the carriage lane), 4 lid screws (M1.2 x 6).

## B7. Cannula adapter and dock
Magnet d2x1 axial into the rear lug pocket (CA drop), punched d2 silicone plug into the septum bore, 1/16" ID silicone tubing on the d1.6 barb. **Dock:** push the pod flat, mouth first, onto the adapter along
the table: the dome enters the channel, the arms spread (under 1 N), snap behind the dome, the needle enters the septum. Release by pulling the pod straight back.

## B8. Function check (water)
1. FFC to the bench controller, motor lead (JST 1.25) into the controller board, USB-C power. Dock hall reads DOCKED only when latched; TMAG angle changes when the screw turns.
2. Draw water (REFILL.md), prime, then deliver steps: 0.00395 U/step (16:20 pair), weigh (1 mg = 1 ul = 0.1 U), calibrate steps/U against the weight.
3. Occlusion: pinch the hose; the current/angle monitor must alarm.

## B9. Disassembly
Reverse order. Reusable: motor, sensor board, magnets, FFC, screws, coupler (brass), duckbill valve (check). Consumed: lip seals, gasket, septum plugs, needle hubs after 3-5 cycles.


## B4. Dock insert, tongue shim, plunger nose (2026-11-19)
* **Dock insert** (`out/bench/fab/dock-inserts/insert_vNN`): slide the insert into the dock window from the +X mouth (arms toward you) until its front face meets the rear dock face and the two detent bumps click into the flange holes. Swap: push it out with a pin from the open end. Same fit on a bare `dock_fixture` for fit tests (permissive, CERN-OHL-P-2.0). The needle stays in the end cap.
* **Tongue shim:** glue a 0.5 x 1.4 mm stainless strip (about 4 mm long) into the carriage pocket (open face toward the reservoir) with one drop of cyanoacrylate; the free end enters the plunger socket. Do not bend it.
* **Plunger nose:** glue the printed 0.7 mm nose disc onto the plunger front face (dead layer in front of the plunger becomes 0.3 mm). Water test only.
