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
2. Test-fit: carriage hex pocket takes the M1.6 nut with light finger pressure; M1.6 rod runs through both bearing
   bores and the carriage (dia 1.9) without binding; plunger core slides in the reservoir bore (0.2 mm per side).
3. Cut the M1.6 rod to length: OP-70 about 19 mm, OP-100 about 23 mm, OP-200 about 37 mm
   (from x = 1.0 to the screw tip at `screw_tip` in layout.json). Deburr both ends.

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

1. Press **gear B** onto the M1.6 rod at the dry end (rod end 1.0 mm in front of the gear face), **gear A** onto the
   gearbox output shaft. Check mesh: centre distance 5.4 mm (fixed by the bottom shell).
2. Slide the two PTFE/brass **bushings** into the bearing bores (dry end wall and wet-end block behind the reservoir).
3. Drop the **carriage** onto the rail (rail groove down), insert the **M1.6 nut** into its hex pocket from the rear
   with tweezers, engage the carriage tongue in the plunger socket through the reservoir slot.
4. Thread the rod through bushing, gear, nut (turn it by hand), bushing; press the **diametric magnet** onto the
   rod end (x = `mag_x`, between the wet-end block and the hall sensor).
5. Lay the **motor/gearhead** in the saddles of the Y = 28 lane, gear A meshes with gear B; its leads/FPC lie on the
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
3. Drive the four **M1.2 x 6 screws** (3 at the dry end, 1 near the coil side) until the lid skirt seats on the
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

# Bench pod assembly (Rev A bench split, spec 4a)

EXPERIMENTAL bench test sample: **water only, never connect to a person.** The integrated sequence above (steps 4-7: battery, main PCB, coil,
Qi) does **not** apply to the bench pod, and its cannula pocket is superseded by the slide-on dock below. Files: `python3 generate.py --variant bench`
-> `out/bench/` (`OP-xx.layout.json` = board layout for the electronics, `OP-xx.mech.json` = full mechanical layout), upload package `out/bench/fab/`.

Tools: **tweezers, small screwdriver (PH000 / 1.5 mm slotted)**, 0.5 / 1.0 / 2.0 mm drills in a pin vise, deburring tool, UV lamp (hub fallback only),
4 mm biopsy punch + 2 mm punch (septum plugs), razor blade. **No soldering iron:** the pod sensor board arrives assembled (JLC PCBA, spring contacts, hall
sensors and the FFC connector already reflowed).

Parts per pod: printed bottom, top, carriage, reservoir, plunger core, cannula adapter; cast lip seals + gasket; purchased drive (see `parts.md`),
pod sensor board (OP-100, one board for all sizes), 1x spindle magnet d2x1 diametric, 1x dock magnet d2x1 axial (goes into the adapter), motor tail strip,
10-pin 0.5 mm FFC cable, 30G needle with press-fit hub, 4 mm fill septum, M1.2 screws (4x6 mm lid, 1x4 mm board).

## B0. Dock fit test (once per cannula head design, before ordering pods)
Test-fit the printed `dock-coupon` to a spare cannula head as described in `cannula-measurement.md` and enter the winning values in `params.json`.

## B1. Incoming inspection (15 min)
1. Wash printed parts, blow out all bores: needle hub bore d2.0 (dock), fluid channel d0.7, pilot holes d1.0 (3 dry-end posts + 1 board boss), bearing bores 3.05.
2. Check the dock: the two snap arms (0.8 mm) must be free (a 0.3 mm feeler must pass between the arm and the floor opening edge); flex each arm by hand 2 mm and release.
3. Check the adapter: magnet pocket d2.1, septum bore d0.5 free, hose barb channel d0.7 free (pin through it).

## B2. Plunger, seal, reservoir, drive train
Identical to the integrated build: sections 1-3 above (cast the lip seals in `mould/`, reservoir into the bottom, gears, bushings, carriage + nut, leadscrew, spindle magnet,
motor in the saddles). The outlet channel d0.7 now runs from the reservoir end port **at z = 3.0 (septum axis height)** into the dock end block.

## B3. Needle and hub (horizontal)
1. Press the 30G needle into the hub (needle pointing toward the dock mouth), tip protruding 3.5 mm from the hub face.
2. Insert the hub from the dock mouth into the d2.0 bore of the guard tube until it bottoms (hub face at x_r1 + 1.5). Check the tip: it must sit 2.9 mm
   in front of the septum face reference (recess depth 1.0 + needle depth 1.9, TODO-MEASURE).
3. If the hub weeps: one drop of UV adhesive at the hub rim, UV lamp 30 s.

## B4. Pod sensor board
1. Lay the motor tail strip (4 pads) on the **motor shelf** (`bench.shelf`, top z 4.65) with the pad centres at the layout `motor_contacts.mating_strip` positions; keep the strip flat.
2. Seat the board over the two locating pins (d1.0, from the pin posts) and the two support posts; the leg overhangs the dock channel. Check that the four spring contacts land on the strip pads and the spindle
   hall sensors sit above-and-beyond the magnet end (`hall_sensors` in the layout).
3. One **M1.2 x 4 screw** into the board boss (hole d1.4 in the board, pilot d1.0 in the post). Stop when the head touches the board; do not over-torque.
4. Insert the FFC cable into the ZIF connector (flip-lock down), cable leaving toward the +X end wall.

## B5. Closing
1. Place the gasket on the bottom tongue (the cut-out for the dome mouth faces the +X end).
2. Lower the lid straight down: the three lid pads touch the board top (hold-down), the FFC leaves through the slot in the +X wall, the dome mouth lines up with the floor opening.
3. Four M1.2 x 6 lid screws (3 at the dry end, 1 at x_r1 + 3.0).

## B6. Cannula adapter (stands in for the Insight Flex head)
1. Press the d2x1 axial magnet into the rear lug pocket (CA drop if loose), flat face up.
2. Punch a d2 plug from 1 mm silicone sheet, press it into the septum bore behind the recess (needle zone).
3. Slip 1/16" ID silicone tubing on the d1.6 hose barb (rear), other end to the collection vessel.
4. **Dock:** hold the pod flat, mouth first, and push the pod onto the adapter along the table: the dome enters the channel, the arms spread (about 2 N), then snap behind the dome; the needle enters the septum.
   Release by pulling the pod straight back (hook ramps); note the effort for the coupon log.

## B7. Function check (water)
1. Connect the FFC to the bench controller, power from USB-C. The dock hall (above the adapter lug) must read DOCKED only with the adapter latched; pull the adapter 5 mm back: NOT docked.
2. Fill the reservoir through the septum with water (30G syringe), prime until water appears at the barb, weigh delivery (1 mg = 1 ul = 0.1 U), calibrate steps against the spindle hall counts.
3. Occlusion test: pinch the hose, check the current/stall alarm.

## B8. Disassembly
Reverse order. Reusable: motor, gears, screws, magnets, sensor board, FFC. Consumed: lip seals, gasket, septum plugs; needle hubs after 3-5 cycles.
